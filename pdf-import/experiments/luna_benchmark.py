#!/usr/bin/env python3
"""Replay DeepSeek benchmark prompts against Luna; no retries or repairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import request, error
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from duchinese_pdf.annotate import compile_annotations, NoRedirect
from duchinese_pdf.prepare import write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file', type=Path)
    p.add_argument('--baseline', type=Path, default=Path('tests/deepseek-benchmark'))
    p.add_argument('--work', type=Path, default=Path('build/luna-benchmark'))
    a = p.parse_args()
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        if not a.key_file:
            p.error('Set OPENAI_API_KEY or pass --key-file PATH')
        content = a.key_file.expanduser().read_text()
        match = re.search(r'\bsk-[A-Za-z0-9_-]{20,}\b', content)
        if not match: raise RuntimeError('No OpenAI credential found')
        key = match.group(0)
    a.work.mkdir(parents=True, exist_ok=False)

    def run(job):
        effort, case = job
        baseline = a.baseline / ('deepseek-flash-' + case)
        source = json.loads((baseline / 'source.json').read_text())
        original = json.loads((baseline / 'request.json').read_text())
        body = dict(model='gpt-5.6-luna', messages=original['messages'], response_format=original['response_format'],
                    reasoning_effort=effort, max_completion_tokens=14000, stream=False, store=False, service_tier='default')
        if effort == 'none': body['temperature'] = 0
        out = a.work / (effort + '-' + case)
        out.mkdir()
        write_json(out / 'request.json', body)
        write_json(out / 'source.json', source)
        record = dict(case=case, reasoning_effort=effort, requested_model=body['model'],
                      started_utc=datetime.now(timezone.utc).isoformat(),
                      messages_sha256=hashlib.sha256(json.dumps(body['messages'], ensure_ascii=False, sort_keys=True).encode()).hexdigest())
        start = time.monotonic()
        try:
            req = request.Request('https://api.openai.com/v1/chat/completions',
                                  data=json.dumps(body, ensure_ascii=False).encode(),
                                  headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            try:
                with request.build_opener(NoRedirect()).open(req, timeout=240) as response:
                    raw = json.load(response)
            except error.HTTPError as exc:
                # Save only structured error fields, never headers or credentials.
                try: detail = json.loads(exc.read()).get('error', {})
                except Exception: detail = {}
                record['api_error'] = {k: str(detail.get(k, '')).replace(key, '[redacted]') for k in ('code', 'param', 'message')}
                raise RuntimeError(f'OpenAI HTTP {exc.code}') from None
            write_json(out / 'response.json', raw)
            record.update(returned_model=raw.get('model'), service_tier=raw.get('service_tier'), usage=raw.get('usage'))
            choice = raw['choices'][0]
            record['finish_reason'] = choice['finish_reason']
            if choice['finish_reason'] != 'stop': raise ValueError('Incomplete generation')
            answer = json.loads(choice['message']['content'])
            write_json(out / 'answer.json', answer)
            corrected, annotations, corrections = compile_annotations(source, answer)
            for name, value in [('characters', corrected), ('annotations', annotations), ('corrections', corrections)]:
                write_json(out / (name + '.json'), value)
            record.update(valid=True, words=len(annotations['words']), sentences=len(annotations['sentences']), corrections=corrections['changes'])
        except Exception as exc:
            record.update(valid=False, error=(type(exc).__name__ + ': ' + str(exc)).replace(key, '[redacted]'))
        record['seconds'] = time.monotonic() - start
        usage = record.get('usage')
        if usage:
            cached = usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)
            uncached = usage['prompt_tokens'] - cached
            # Published standard rates 2026-09-16. Upper bound allows all
            # uncached tokens to incur cache-write pricing if not itemized.
            record['estimated_usd'] = (cached * .02 + uncached * .20 + usage['completion_tokens'] * 1.20) / 1e6
            record['estimated_usd_cache_write_upper'] = (cached * .02 + uncached * .25 + usage['completion_tokens'] * 1.20) / 1e6
            writes = usage.get('prompt_tokens_details', {}).get('cache_write_tokens')
            if writes is not None:
                record['estimated_usd'] += writes * .05 / 1e6
                record['cost_includes_itemized_cache_writes'] = True
        write_json(out / 'result.json', record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        return record
    jobs = [('none', c) for c in ['challenge', 'page26', 'page25']] + [('medium', c) for c in ['challenge', 'page25']]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, jobs))
    write_json(a.work / 'summary.json', results)

if __name__ == '__main__': main()
