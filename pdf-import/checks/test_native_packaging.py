"""Native lookup packages must not reuse stale cross-line word rectangles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'native_package', Path(__file__).resolve().parents[2] / 'scripts/build-native-pdf-overlay.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class NativePackagingTests(unittest.TestCase):
    def test_rebuilds_stale_boxes_without_changing_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / 'source.pdf'
            pdf.write_bytes(b'fixture')
            page = root / 'pages/001'
            annotation = page / 'annotation/result'
            annotation.mkdir(parents=True)
            word = dict(start=0, end=2, hanzi='学习', pinyin='xue xi', meaning='study',
                        sentence=0, boxes=[[10, 10, 90, 50]])
            book = dict(source_page=1, image_width=100, image_height=100, words=[word],
                        sentences=[dict(text='学习', translation='Study.')])
            chars = dict(characters=[
                dict(offset=0, text='学', line=0, box=[80, 10, 20, 20]),
                dict(offset=1, text='习', line=0, box=[10, 40, 20, 20])])
            (page / 'book.json').write_text(json.dumps(book))
            (annotation / 'characters.json').write_text(json.dumps(chars))
            (root / 'manifest.json').write_text(json.dumps(dict(status='completed',
                pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(), first_page=1,
                last_page=1, pages=[dict(page=1, status='validated', book='pages/001/book.json')])))
            with patch.object(package.subprocess, 'check_output', return_value=
                              'Page 1 MediaBox: 0 0 100 100\nPage 1 CropBox: 0 0 100 100\n'):
                result = package.package(root, pdf)['pages'][1]
            self.assertEqual(result['words'][0], dict(hanzi='学习', pinyin='xue xi',
                meaning='study', sentence=0, boxes=[[80, 10, 20, 20], [10, 40, 20, 20]]))
            self.assertEqual(result['sentences'], book['sentences'])
            self.assertEqual(json.loads((page / 'book.json').read_text()), book)
