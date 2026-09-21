import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from duchinese_pdf.merge import merge_batches
from duchinese_pdf.prepare import write_json

class MergeTests(unittest.TestCase):
    def batch(self,root,n,pdf='same-pdf'):
        image=f'images/page-{n:03d}.png';book=f'pages/{n:03d}/book.json'
        (root/'images').mkdir(parents=True);(root/'pages'/f'{n:03d}').mkdir(parents=True);(root/'ocr'/f'page-{n:03d}').mkdir(parents=True)
        (root/image).write_bytes(b'image');write_json(root/book,{'source_page':n})
        write_json(root/'manifest.json',{'status':'completed','pdf_sha256':pdf,'dpi':240,'title':'Test','first_page':n,'last_page':n,
          'pages':[{'page':n,'status':'image-only','image':image,'book':book}],'image_hashes':{str(n):hashlib.sha256(b'image').hexdigest()}})
        return root
    def test_preserves_pdf_identity_and_page_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);a=self.batch(r/'a',1);b=self.batch(r/'b',2)
            m=merge_batches([b,a],r/'merged')
            self.assertEqual(m['pdf_sha256'],'same-pdf');self.assertEqual([p['page'] for p in m['pages']],[1,2])
            self.assertEqual((r/'merged/images/page-002.png').read_bytes(),b'image')
    def test_rejects_duplicate_gap_wrong_pdf_and_changed_image(self):
        for case in ['duplicate','gap','pdf','image']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp);a=self.batch(r/'a',1);b=self.batch(r/'b',1 if case=='duplicate' else 3 if case=='gap' else 2,'other' if case=='pdf' else 'same-pdf')
                if case=='image':(b/'images/page-002.png').write_bytes(b'changed')
                with self.assertRaises(ValueError):merge_batches([a,b],r/'merged')
                self.assertFalse((r/'merged').exists())
