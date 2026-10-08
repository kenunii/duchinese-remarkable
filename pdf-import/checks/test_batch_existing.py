from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from duchinese_pdf.batch_existing import annotate_existing
from duchinese_pdf.prepare import write_json


class ExistingBatchTests(unittest.TestCase):
    def test_image_only_pages_complete_without_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / 'source.pdf'
            pdf.write_bytes(b'fixture')
            images = root / 'images'
            images.mkdir()
            ocr = root / 'ocr'
            ocr.mkdir()
            for n in (1, 2):
                stem = f'page-{n:03d}'
                Image.new('RGB', (100, 100)).save(images / f'{stem}.png')
                (ocr / stem).mkdir()
                write_json(ocr / stem / f'{stem}_res.json', {'rec_texts': ['English only']})
            key = root / 'key'
            key.write_text('sk-' + 'x' * 30)
            output = root / 'work'
            with patch('duchinese_pdf.batch.run') as api:
                result = annotate_existing(pdf, images, ocr, output, 1, 2, 2,
                                           'Fixture', key)
            api.assert_not_called()
            self.assertEqual(result['status'], 'completed')
            self.assertEqual([p['status'] for p in result['pages']],
                             ['image-only', 'image-only'])
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual(len(result['ocr_hashes']), 2)

    def test_interrupted_annotation_is_not_resent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / 'source.pdf'
            pdf.write_bytes(b'fixture')
            images = root / 'images'
            images.mkdir()
            ocr = root / 'ocr'
            (ocr / 'page-001').mkdir(parents=True)
            Image.new('RGB', (100, 100)).save(images / 'page-001.png')
            write_json(ocr / 'page-001/page-001_res.json', {'rec_texts': ['English only']})
            key = root / 'key'
            key.write_text('sk-' + 'x' * 30)
            output = root / 'work'
            first = annotate_existing(pdf, images, ocr, output, 1, 1, 1,
                                      'Fixture', key)
            first['status'] = 'running'
            write_json(output / 'manifest.json', first)
            (output / 'pages/001/status.json').unlink()
            (output / 'pages/001/annotation').mkdir()
            with patch('duchinese_pdf.batch_existing.process_page') as process:
                resumed = annotate_existing(pdf, images, ocr, output, 1, 1, 1,
                                            'Fixture', key)
            process.assert_not_called()
            self.assertEqual(resumed['status'], 'completed-with-errors')
            self.assertIn('Interrupted', resumed['pages'][0]['error'])


if __name__ == '__main__':
    unittest.main()
