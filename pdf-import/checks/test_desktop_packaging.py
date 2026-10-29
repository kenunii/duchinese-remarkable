"""Desktop packaging must rebuild stale cross-line word rectangles."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'desktop_package', Path(__file__).resolve().parents[2] / 'scripts/open-desktop-reader.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class DesktopPackagingTests(unittest.TestCase):
    def test_rebuilds_wrapped_word_from_character_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / 'pages/001'
            annotation = page / 'annotation/result'
            annotation.mkdir(parents=True)
            word = dict(start=0, end=2, hanzi='学习', pinyin='xue xi', meaning='study',
                        sentence=0, boxes=[[10, 10, 90, 50]])
            book = dict(image_width=100, image_height=100, words=[word],
                        sentences=[dict(text='学习', translation='Study.')])
            chars = dict(characters=[
                dict(offset=0, text='学', line=0, box=[80, 10, 20, 20]),
                dict(offset=1, text='习', line=0, box=[10, 40, 20, 20])])
            (page / 'book.json').write_text(json.dumps(book))
            (annotation / 'characters.json').write_text(json.dumps(chars))
            (root / 'manifest.json').write_text(json.dumps(dict(pdf_sha256='test', title='Test',
                pages=[dict(page=1, status='validated', book='pages/001/book.json',
                            image='pages/001/page.png')])))
            output = root / 'output'
            package.build(root, output)
            result = json.loads((output / 'book.js').read_text()[len('const book = '):-2])
            self.assertEqual(result['pages'][0]['data']['words'][0]['boxes'],
                             [[80, 10, 20, 20], [10, 40, 20, 20]])
            self.assertEqual(result['pages'][0]['data']['sentences'], book['sentences'])
            self.assertEqual(json.loads((page / 'book.json').read_text()), book)


if __name__ == '__main__':
    unittest.main()
