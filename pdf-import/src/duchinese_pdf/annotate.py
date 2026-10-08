"""Annotate one prepared page in one LLM request, with auditable corrections."""
import argparse
import copy
import json
import os
import re
from importlib.resources import files
from pathlib import Path
from urllib import error, request

from .annotation_schema import CONFUSABLE_GROUPS, SCHEMA
from .assemble import assemble
from .prepare import HAN, digest, validate_source, write_json


def gap_offsets(characters):
    """Offsets immediately after large horizontal gaps, not confirmed blanks."""
    gaps = []
    for left, right in zip(characters, characters[1:]):
        x, y, w, h = left['box']
        nx, ny, nw, nh = right['box']
        if abs((y+h/2)-(ny+nh/2)) < min(h, nh)/2 and nx-(x+w) > 1.5*max(h, nh):
            gaps.append(right['offset'])
    return gaps


def validate_schema(value, schema, path='response'):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError(f'{path}: missing or unexpected fields')
        for key, sub in schema['properties'].items():
            validate_schema(value[key], sub, f'{path}.{key}')
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError(f'{path}: expected array')
        for i, item in enumerate(value):
            validate_schema(item, schema['items'], f'{path}[{i}]')
    elif (kind == 'string' and not isinstance(value, str)) or (kind == 'integer' and type(value) is not int):
        raise ValueError(f'{path}: expected {kind}')


def compile_annotations(source, answer, allowed_word_gaps=None):
    original = validate_source(source)
    validate_schema(answer, SCHEMA)
    corrected = copy.deepcopy(source)
    seen = set()
    for change in answer['corrections']:
        pos, before, after = change['offset'], change['before'], change['after']
        if pos in seen or not 0 <= pos < len(original):
            raise ValueError('Correction offset duplicated or outside source')
        if len(before) != 1 or len(after) != 1 or original[pos] != before or before == after:
            raise ValueError('Correction must replace exactly one matching source character')
        if not any(before in group and after in group for group in CONFUSABLE_GROUPS):
            raise ValueError('Correction is outside the allowed visual-confusion groups')
        if not change['reason'].strip():
            raise ValueError('Correction lacks a contextual reason')
        seen.add(pos)
        corrected['characters'][pos]['text'] = after
    text = ''.join(c['text'] for c in corrected['characters'])
    gaps = gap_offsets(corrected['characters'])
    allowed_word_gaps = set(allowed_word_gaps or ())
    if not allowed_word_gaps.issubset(gaps):
        raise ValueError('Allowed word gap is not an observed layout gap')
    words, sentences, cursor = [], [], 0
    for sid, sentence in enumerate(answer['sentences']):
        if not sentence['translation'].strip() or not sentence['words']:
            raise ValueError('Empty sentence or translation')
        start = cursor
        for word in sentence['words']:
            token = word['text']
            end = cursor + len(token)
            if not token or text[cursor:end] != token:
                raise ValueError(f'Word does not match corrected OCR at offset {cursor}')
            if HAN.search(token) and (not word['pinyin'].strip() or not word['meaning'].strip()):
                raise ValueError('Chinese word lacks pinyin or contextual meaning')
            # Reject words bridging conspicuous horizontal gaps within a row.
            if any(cursor < offset < end for offset in gaps
                   if offset not in allowed_word_gaps):
                raise ValueError('Word crosses a large horizontal layout gap')
            words.append({'start': cursor, 'end': end, 'hanzi': token,
                          'pinyin': word['pinyin'], 'meaning': word['meaning'], 'sentence': sid})
            cursor = end
        sentences.append({'text': text[start:cursor], 'translation': sentence['translation']})
    if cursor != len(text):
        raise ValueError('Response omitted trailing source characters')
    annotations = {'words': words, 'sentences': sentences}
    assemble(corrected, annotations, source['image_size'])
    corrections = {'original_text': original, 'corrected_text': text,
                   'changes': answer['corrections'], 'allowed_confusable_groups': list(CONFUSABLE_GROUPS)}
    return corrected, annotations, corrections


def make_request(source, model, max_output_tokens=24000):
    validate_source(source)
    # Reconstruct line records from the actual characters, never trust a stale
    # transcript in the input metadata. Offsets are absolute within this page.
    lines = []
    previous_line = None
    for char in source['characters']:
        if not lines or previous_line != char['line']:
            lines.append({'start': char['offset'], 'text': ''})
        lines[-1]['text'] += char['text']
        previous_line = char['line']
    payload = {'lines': lines, 'gaps_before': gap_offsets(source['characters']),
               'allowed_confusable_groups': list(CONFUSABLE_GROUPS)}
    return {'model': model, 'store': False, 'max_output_tokens': max_output_tokens,
            'instructions': files('duchinese_pdf').joinpath('prompts/annotate.txt').read_text(encoding='utf-8'),
            'input': [{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}],
            'text': {'format': {'type': 'json_schema', 'name': 'chinese_page_annotation',
                                'strict': True, 'schema': SCHEMA}}}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def call_api(body, api_key, timeout=300):
    req = request.Request('https://api.openai.com/v1/responses',
                          data=json.dumps(body).encode(), method='POST',
                          headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
    # Exactly one request. No automatic retries after HTTP/timeout errors and
    # no model-assisted repairs after validation failure.
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            return json.load(response)
    except error.HTTPError as exc:
        raise RuntimeError(f'LLM request failed with HTTP {exc.code}; no automatic retry') from None
    except (error.URLError, TimeoutError):
        raise RuntimeError('LLM connection failed or timed out; no automatic retry') from None


def extract_answer(response):
    if response.get('status') != 'completed':
        raise ValueError('LLM response did not complete; refusing partial output')
    texts = []
    for item in response.get('output', []):
        if item.get('type') != 'message':
            continue
        for content in item.get('content', []):
            if content.get('type') == 'refusal':
                raise ValueError('LLM refused the annotation request')
            if content.get('type') == 'output_text':
                texts.append(content['text'])
    if len(texts) != 1:
        raise ValueError('Expected exactly one structured annotation response')
    return json.loads(texts[0])


def read_api_key(path):
    """Read an explicitly selected credential file without exposing its contents."""
    match = re.search(r'\bsk-[A-Za-z0-9_-]{20,}\b', path.expanduser().read_text())
    if not match:
        raise ValueError('No API credential found in the selected key file')
    return match.group(0)


def make_deepseek_request(source, model='deepseek-flash', max_output_tokens=48000):
    from .line_contract import messages
    return {'model': model, 'messages': messages(source),
            'response_format': {'type': 'json_object'}, 'stream': False,
            'thinking': {'type': 'enabled'}, 'max_tokens': max_output_tokens, 'temperature': 0}


def call_deepseek(body, api_key, timeout=900):
    req = request.Request('https://api.deepseek.com/chat/completions',
                          data=json.dumps(body, ensure_ascii=False).encode(), method='POST',
                          headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            return json.load(response)
    except error.HTTPError as exc:
        raise RuntimeError(f'LLM request failed with HTTP {exc.code}; no automatic retry') from None
    except (error.URLError, TimeoutError):
        raise RuntimeError('LLM connection failed or timed out; no automatic retry') from None


def extract_deepseek_answer(response):
    choices = response.get('choices', [])
    if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
        raise ValueError('LLM response did not complete; refusing partial output')
    message = choices[0]['message']
    if message.get('refusal') or not isinstance(message.get('content'), str):
        raise ValueError('LLM refused or returned no annotation')
    return json.loads(message['content'])


def run(source, output, model=None, *, provider=None, dry_run=False, replay=None, max_output_tokens=48000, timeout=900, api_key=None):
    validate_source(source)
    if provider is None:
        provider = 'deepseek' if model is None or model.startswith('deepseek-') else 'openai'
    if provider not in ('deepseek', 'openai'):
        raise ValueError('Provider must be deepseek or openai')
    if model is None and provider == 'deepseek':
        model = 'deepseek-flash'
    if not model or not model.strip():
        raise ValueError('Set --model or PDF_IMPORT_MODEL for this provider')
    key_name = 'DEEPSEEK_API_KEY' if provider == 'deepseek' else 'OPENAI_API_KEY'
    api_key = api_key or os.environ.get(key_name)
    request_builder = make_deepseek_request if provider == 'deepseek' else make_request
    transport = call_deepseek if provider == 'deepseek' else call_api
    if len(source['characters']) > 2000:
        raise ValueError('Page exceeds 2000 characters; prepare a smaller region selection')
    if max_output_tokens < 1 or timeout <= 0:
        raise ValueError('Token limit and timeout must be positive')
    body = request_builder(source, model, max_output_tokens)
    # Bind replays to both request and exact source geometry/provenance.
    fingerprint = digest({'source': source, 'request': body})
    if not dry_run and replay is None and not api_key:
        raise ValueError(f'{key_name} is not configured; use --dry-run to prepare offline')
    if output.exists():
        raise ValueError('Output directory already exists; use a new directory to preserve previous runs')
    output.mkdir(parents=True)
    write_json(output/'source.json', source)
    write_json(output/'request.json', body)
    meta = {'request_sha256': fingerprint, 'source_sha256': digest(source),
            'model': model, 'provider': provider, 'mode': 'dry-run' if dry_run else ('replay' if replay else 'live'),
            'status': 'prepared', 'requests_sent': 0}
    write_json(output/'run.json', meta)
    if dry_run:
        return meta
    try:
        if replay is not None:
            envelope = json.loads(replay.read_text(encoding='utf-8'))
            if envelope.get('request_sha256') != fingerprint:
                raise ValueError('Saved response belongs to a different request/source')
        else:
            meta['requests_sent'] = 1
            write_json(output/'run.json', meta)
            envelope = {'request_sha256': fingerprint,
                        'provider_response': transport(body, api_key, timeout)}
        write_json(output/'response.json', envelope)
        response = envelope['provider_response']
        meta.update(response_id=response.get('id'), usage=response.get('usage'), returned_model=response.get('model'))
        if provider == 'deepseek':
            from .line_contract import compile_lines
            answer = extract_deepseek_answer(response)
            corrected, annotations, corrections = compile_lines(source, answer)
        else:
            answer = extract_answer(response)
            corrected, annotations, corrections = compile_annotations(source, answer)
        stage = output/'result.tmp'
        stage.mkdir()
        write_json(stage/'characters.json', corrected)
        write_json(stage/'annotations.json', annotations)
        write_json(stage/'corrections.json', corrections)
        stage.rename(output/'result')
        meta.update(status='validated', corrections=len(corrections['changes']),
                    words=len(annotations['words']), sentences=len(annotations['sentences']),
                    response_id=response.get('id'), usage=response.get('usage'))
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        meta.update(status='failed', error=str(exc))
        write_json(output/'run.json', meta)
        raise
    write_json(output/'run.json', meta)
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path, help='Output of the prepare command')
    p.add_argument('output', type=Path, help='New run directory; existing runs are never overwritten')
    p.add_argument('--model', default=os.environ.get('PDF_IMPORT_MODEL'), help='Defaults to deepseek-flash')
    p.add_argument('--provider', choices=['deepseek', 'openai'], default=os.environ.get('PDF_IMPORT_PROVIDER'), help='Inferred from model; DeepSeek by default')
    p.add_argument('--key-file', type=Path, help='Optional local credential file; key stays in memory')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Save source, prompt and schema without any API call')
    mode.add_argument('--response', type=Path, help='Replay a saved response.json bound to the same request')
    p.add_argument('--max-output-tokens', type=int, default=48000)
    p.add_argument('--timeout', type=float, default=900)
    a = p.parse_args()
    try:
        meta = run(json.loads(a.source.read_text()), a.output, a.model, dry_run=a.dry_run,
                   provider=a.provider, replay=a.response, max_output_tokens=a.max_output_tokens, timeout=a.timeout,
                   api_key=read_api_key(a.key_file) if a.key_file and not a.dry_run and not a.response else None)
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        p.exit(1, f'Annotation failed: {exc}\n')
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == '__main__':
    main()
