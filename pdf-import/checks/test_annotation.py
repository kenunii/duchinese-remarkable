"""Deterministic contract tests; all model answers are synthetic, no API calls."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from duchinese_pdf import annotate
from duchinese_pdf.prepare import prepare, validate_source


def source(text='自已学习。'):
    return {'image_size': [200, 100], 'characters': [
        {'offset': i, 'text': c, 'line': 0, 'box': [i*20, 0, 20, 20]}
        for i, c in enumerate(text)]}


def answer():
    return {'corrections': [{'offset': 1, 'before': '已', 'after': '己', 'reason': '自己 means oneself in this sentence.'}],
            'sentences': [{'translation': 'Study by oneself.', 'words': [
                {'text': '自己', 'pinyin': 'zì jǐ', 'meaning': 'oneself'},
                {'text': '学习', 'pinyin': 'xué xí', 'meaning': 'to study'},
                {'text': '。', 'pinyin': '', 'meaning': ''}]}]}


def response(value=None):
    return {'id': 'synthetic-test-only', 'status': 'completed', 'usage': {'total_tokens': 100},
            'output': [{'type': 'message', 'content': [{'type': 'output_text',
                        'text': json.dumps(value if value is not None else answer())}]}]}


class AnnotationTests(unittest.TestCase):
    def test_compact_input_preserves_offsets_and_gap_hints_without_coordinates(self):
        raw = source()
        raw['characters'][2]['box'] = [100, 0, 20, 20]
        raw['characters'][3].update(line=1, box=[0, 30, 20, 20])
        raw['characters'][4].update(line=1, box=[20, 30, 20, 20])
        raw['lines'] = [{'text': 'stale metadata'}]
        payload = json.loads(annotate.make_request(raw, 'test-model')['input'][0]['content'])
        self.assertEqual(payload['lines'], [{'start': 0, 'text': '自已学'}, {'start': 3, 'text': '习。'}])
        self.assertEqual(payload['gaps_before'], [2])
        self.assertEqual(set(payload), {'lines', 'gaps_before', 'allowed_confusable_groups'})
        self.assertNotIn('box', json.dumps(payload))
        self.assertEqual(''.join(line['text'] for line in payload['lines']), validate_source(raw))

    def test_correction_preserves_geometry_and_original(self):
        raw = source(); before = copy.deepcopy(raw)
        corrected, annotations, audit = annotate.compile_annotations(raw, answer())
        self.assertEqual(raw, before)
        self.assertEqual(corrected['characters'][1]['text'], '己')
        self.assertEqual([c['box'] for c in corrected['characters']], [c['box'] for c in raw['characters']])
        self.assertEqual(annotations['words'][1]['start'], 2)
        self.assertEqual(audit['original_text'], '自已学习。')
        self.assertEqual(audit['corrected_text'], '自己学习。')

    def test_unlisted_or_multi_character_corrections_rejected(self):
        for replacement in ['我', '己己', '', '已']:
            value = answer(); value['corrections'][0]['after'] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                annotate.compile_annotations(source(), value)

    def test_duplicate_wrong_and_negative_offsets_rejected(self):
        for offset in [-1, 0, 99, True]:
            value = answer(); value['corrections'][0]['offset'] = offset
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                annotate.compile_annotations(source(), value)
        value = answer(); value['corrections'] *= 2
        with self.assertRaises(ValueError): annotate.compile_annotations(source(), value)

    def test_unreported_rewrite_and_omission_rejected(self):
        value = answer(); value['corrections'] = []
        with self.assertRaises(ValueError): annotate.compile_annotations(source(), value)
        value = answer(); value['sentences'][0]['words'].pop()
        with self.assertRaises(ValueError): annotate.compile_annotations(source(), value)

    def test_missing_gloss_or_pinyin_rejected(self):
        for key in ['meaning', 'pinyin']:
            value = answer(); value['sentences'][0]['words'][0][key] = ''
            with self.assertRaises(ValueError): annotate.compile_annotations(source(), value)

    def test_unknown_output_fields_rejected(self):
        value = answer(); value['coordinates'] = []
        with self.assertRaises(ValueError): annotate.compile_annotations(source(), value)

    def test_valid_uncorrected_text_can_remain_unchanged(self):
        value = answer(); value['corrections'] = []
        corrected, _, audit = annotate.compile_annotations(source('自己学习。'), value)
        self.assertEqual(validate_source(corrected), '自己学习。')
        self.assertEqual(audit['changes'], [])

    def test_line_wrap_allowed_but_large_inline_gap_rejected(self):
        raw = source(); raw['characters'][1].update(line=1, box=[0, 30, 20, 20])
        annotate.compile_annotations(raw, answer())
        raw = source(); raw['characters'][1]['box'] = [90, 0, 20, 20]
        with self.assertRaises(ValueError): annotate.compile_annotations(raw, answer())

    def test_refusal_and_incomplete_response_rejected(self):
        value = response(); value['status'] = 'incomplete'
        with self.assertRaises(ValueError): annotate.extract_answer(value)
        value = response(); value['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'no'}]
        with self.assertRaises(ValueError): annotate.extract_answer(value)

    def test_http_error_is_not_retried(self):
        from urllib.error import HTTPError
        with patch.object(annotate.request, 'build_opener') as factory:
            factory.return_value.open.side_effect = HTTPError('https://api.openai.com/v1/responses', 429, 'limited', {}, None)
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429'):
                annotate.call_api({'model': 'test-model'}, 'synthetic-secret')
            self.assertEqual(factory.return_value.open.call_count, 1)
            req = factory.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, 'https://api.openai.com/v1/responses')
            self.assertEqual(json.loads(req.data), {'model': 'test-model'})

    def test_prepare_preserves_numbers_and_records_omitted_notes(self):
        raw = {'rec_texts': ['工作35.7%', 'English note'],
               'text_word': [['工', '作', '35.7', '%'], ['English', 'note']],
               'text_word_boxes': [[[0, 0, 20, 20], [20, 0, 40, 20], [40, 0, 80, 20], [80, 0, 90, 20]],
                                   [[0, 30, 50, 40], [50, 30, 90, 40]]]}
        value = prepare(raw, [100, 100])
        self.assertEqual(validate_source(value), '工作35.7%')
        self.assertEqual(value['characters'][2]['box'], value['characters'][5]['box'])
        self.assertEqual(value['omitted_lines'][0]['text'], 'English note')
        raw['text_word'][0][0] = '学'
        with self.assertRaises(ValueError): prepare(raw, [100, 100])

    def test_invalid_geometry_stops_before_provider(self):
        raw = source(); raw['characters'][0]['box'][0] = float('nan')
        with tempfile.TemporaryDirectory() as temp, patch.object(annotate, 'call_api') as api:
            with self.assertRaises(ValueError):
                annotate.run(raw, Path(temp)/'run', 'test-model', dry_run=True)
            api.assert_not_called()

    def test_live_path_one_request_and_replay_binding(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret'}):
            root = Path(temp)
            with patch.object(annotate, 'call_api', return_value=response()) as api:
                meta = annotate.run(source(), root/'live', 'test-model')
                self.assertEqual(api.call_count, 1)
                self.assertEqual(meta['status'], 'validated')
                self.assertEqual(meta['requests_sent'], 1)
                request_body = api.call_args.args[0]
                self.assertFalse(request_body['store'])
                self.assertTrue(request_body['text']['format']['strict'])
            self.assertNotIn('test-secret', (root/'live/request.json').read_text())
            with patch.object(annotate, 'call_api') as api:
                meta = annotate.run(source(), root/'replay', 'test-model', replay=root/'live/response.json')
                self.assertEqual(meta['requests_sent'], 0)
                api.assert_not_called()
            self.assertEqual((root/'live/result/annotations.json').read_bytes(), (root/'replay/result/annotations.json').read_bytes())
            with self.assertRaises(ValueError):
                annotate.run(source('自己学习。'), root/'wrong-source', 'test-model', replay=root/'live/response.json')
            self.assertFalse((root/'wrong-source/result').exists())

    def test_failure_preserves_response_without_retry_or_publish(self):
        value = answer(); value['corrections'] = []
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret'}):
            out = Path(temp)/'failed'
            with patch.object(annotate, 'call_api', return_value=response(value)) as api:
                with self.assertRaises(ValueError): annotate.run(source(), out, 'test-model')
                self.assertEqual(api.call_count, 1)
            self.assertTrue((out/'response.json').exists())
            self.assertFalse((out/'result').exists())
            self.assertEqual(json.loads((out/'run.json').read_text())['status'], 'failed')

    def test_dry_run_no_key_and_existing_run_preserved(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True), patch.object(annotate, 'call_api') as api:
            out = Path(temp)/'dry'
            meta = annotate.run(source(), out, 'test-model', dry_run=True)
            self.assertEqual(meta['status'], 'prepared')
            self.assertFalse((out/'result').exists())
            api.assert_not_called()
            with self.assertRaises(ValueError): annotate.run(source(), out, 'test-model', dry_run=True)
            with self.assertRaises(ValueError): annotate.run(source(), Path(temp)/'live', 'test-model')


if __name__ == '__main__':
    unittest.main()
