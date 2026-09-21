import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from duchinese_pdf.batch import process_page
from duchinese_pdf.preview import build_preview
from duchinese_pdf.prepare import write_json

class BatchTests(unittest.TestCase):
    def test_image_only_never_calls_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'page.png';Image.new('RGB',(100,100)).save(image)
            raw=root/'raw.json';write_json(raw,{'rec_texts':['English only']})
            with patch('duchinese_pdf.batch.run') as api:record=process_page(1,image,raw,root,'Test')
            api.assert_not_called();self.assertEqual(record['status'],'image-only')
            self.assertEqual(json.loads((root/record['book']).read_text())['words'],[])

    def test_preparation_failure_never_publishes_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'page.png';Image.new('RGB',(100,100)).save(image)
            raw=root/'raw.json';write_json(raw,{'rec_texts':['中国'],'text_word':[['中','国']],'text_word_boxes':[[[0,0,20,20],[-1,0,20,20]]]})
            with patch('duchinese_pdf.batch.run') as api:record=process_page(1,image,raw,root,'Test')
            api.assert_not_called();self.assertEqual(record['status'],'failed')
            self.assertFalse((root/'pages/001/book.json').exists())

    def test_preview_escapes_document_text_and_includes_pending_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            write_json(root/'manifest.json',{'title':'</script><script>bad()</script>','first_page':1,'last_page':2,'pages':[]})
            text=build_preview(root).read_text()
            self.assertNotIn('</script><script>bad()',text)
            self.assertIn('images/page-002.png',text)
