import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from duchinese_pdf import annotate
from duchinese_pdf.prepare import write_json
from duchinese_pdf.retry import retry_pages
from test_deepseek import source,response

class ExplicitRetryTests(unittest.TestCase):
    def test_preserves_rejected_response_and_never_repeats_successful_page(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test'},clear=True):
            root=Path(tmp);page=root/'pages/001';page.mkdir(parents=True)
            raw=source();raw['provenance']={'test':'synthetic'};write_json(page/'source.json',raw)
            with patch.object(annotate,'call_deepseek',return_value=response('length')):
                with self.assertRaises(ValueError):annotate.run(raw,page/'annotation')
            original=(page/'annotation/response.json').read_bytes()
            write_json(root/'manifest.json',{'title':'Test','status':'completed-with-errors','pages':[{'page':1,'image':'images/page-001.png','status':'failed'}]})
            with patch.object(annotate,'call_deepseek',return_value=response()) as api:
                result=retry_pages(root,[1]);self.assertEqual(api.call_count,1)
                self.assertEqual(result['status'],'completed')
                self.assertEqual((page/'annotation/response.json').read_bytes(),original)
                self.assertTrue((page/'annotation-retry-1/result/annotations.json').exists())
                with self.assertRaises(ValueError):retry_pages(root,[1])
                self.assertEqual(api.call_count,1)
