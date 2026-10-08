import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from duchinese_pdf.google_vision import convert_response, read_key, run
from duchinese_pdf.prepare import prepare


def sample_response():
    def symbol(text, x):
        return {'text': text, 'boundingBox': {'vertices': [
            {'x': x, 'y': 10}, {'x': x + 10, 'y': 10},
            {'x': x + 10, 'y': 30}, {'x': x, 'y': 30}]}}
    word = {'symbols': [symbol('中', 10), symbol('国', 20), symbol('。', 30)]}
    paragraph = {'words': [word]}
    page = {'width': 100, 'height': 80,
            'blocks': [{'paragraphs': [paragraph]}]}
    return {'fullTextAnnotation': {'pages': [page]}}


class GoogleVisionTests(unittest.TestCase):
    def test_symbol_geometry_flows_into_existing_preparer(self):
        converted = convert_response(sample_response())
        source = prepare(converted, (100, 80))
        self.assertEqual(''.join(c['text'] for c in source['characters']), '中国。')
        self.assertEqual(source['characters'][1]['box'], [20, 10, 10, 20])

    def test_trial_preserves_response_and_does_not_store_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'page-001.png'
            Image.new('RGB', (100, 80)).save(image)
            key_file = root / 'key'
            key_file.write_text('synthetic-key\n')
            key_file.chmod(0o600)
            with patch('duchinese_pdf.google_vision.call_vision', return_value=sample_response()) as api:
                records = run([image], root / 'private-output', read_key(key_file))
            self.assertEqual(records['page-001']['status'], 'completed')
            api.assert_called_once()
            self.assertEqual(json.loads((root / 'private-output/page-001/page-001_res.json').read_text())['rec_texts'], ['中国。'])
            self.assertEqual((root / 'private-output').stat().st_mode & 0o777, 0o700)
            self.assertFalse(any('synthetic-key' in p.read_text() for p in (root / 'private-output').rglob('*.json')))

    def test_spatial_rows_reorder_out_of_order_chinese_paragraphs(self):
        def paragraph(text, y):
            return {'words': [{'symbols': [{'text': text, 'boundingBox': {
                'vertices': [{'x': 10, 'y': y}, {'x': 20, 'y': y},
                             {'x': 20, 'y': y + 20}, {'x': 10, 'y': y + 20}]}}]}]}
        block = {'paragraphs': [paragraph('国', 200), paragraph('中', 100)]}
        page = {'width': 100, 'height': 1000, 'blocks': [block]}
        response = {'fullTextAnnotation': {'pages': [page]}}
        converted = convert_response(response)
        self.assertEqual(converted['reading_order'], 'spatial-rows')
        self.assertEqual(converted['rec_texts'], ['中', '国'])


if __name__ == '__main__':
    unittest.main()
