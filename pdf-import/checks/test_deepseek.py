"""Provider routing, truncation, audit retention and offline replay regression tests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from duchinese_pdf import annotate


def source():
    return {'image_size':[100,100],'characters':[{'offset':i,'text':c,'line':0,'box':[i*20,0,20,20]} for i,c in enumerate('自已。')]}


def response(finish='stop'):
    answer={'lines':[{'id':'L1','text':'自己。','correction_reason':'自己 is the intended word.'}],
            'sentences':[{'translation':'Oneself.','words':[{'text':'自己','pinyin':'zì jǐ','meaning':'oneself'},{'text':'。','pinyin':'','meaning':''}]}]}
    return {'id':'synthetic','model':'deepseek-flash','usage':{'completion_tokens':123},
            'choices':[{'finish_reason':finish,'message':{'content':json.dumps(answer)}}]}


class DeepSeekTests(unittest.TestCase):
    def test_default_route_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'DEEPSEEK_API_KEY':'synthetic-key'},clear=True):
            root=Path(tmp)
            with patch.object(annotate,'call_deepseek',return_value=response()) as api, patch.object(annotate,'call_api') as other:
                meta=annotate.run(source(),root/'live')
                self.assertEqual(meta['status'],'validated')
                body,key,timeout=api.call_args.args
                self.assertEqual(body['model'],'deepseek-flash')
                self.assertEqual(body['max_tokens'],48000)
                self.assertEqual(body['thinking'],{'type':'enabled'})
                self.assertEqual(timeout,900)
                self.assertEqual(api.call_count,1);other.assert_not_called()
            with patch.object(annotate,'call_deepseek') as api:
                replay=annotate.run(source(),root/'replay',replay=root/'live/response.json')
                self.assertEqual(replay['requests_sent'],0);api.assert_not_called()
                with self.assertRaises(ValueError):
                    annotate.run(source(),root/'wrong',max_output_tokens=14000,replay=root/'live/response.json')
            self.assertNotIn('synthetic-key',(root/'live/request.json').read_text())

    def test_truncation_retains_usage_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test'},clear=True), patch.object(annotate,'call_deepseek',return_value=response('length')) as api:
            root=Path(tmp)/'failed'
            with self.assertRaises(ValueError):annotate.run(source(),root)
            self.assertEqual(api.call_count,1)
            meta=json.loads((root/'run.json').read_text())
            self.assertEqual(meta['usage']['completion_tokens'],123)
            self.assertTrue((root/'response.json').exists());self.assertFalse((root/'result').exists())

    def test_http_error_not_retried(self):
        with patch.object(annotate.request,'build_opener') as factory:
            factory.return_value.open.side_effect=HTTPError('https://api.deepseek.com/chat/completions',429,'limited',{},None)
            with self.assertRaisesRegex(RuntimeError,'HTTP 429'):annotate.call_deepseek({},'test')
            self.assertEqual(factory.return_value.open.call_count,1)
            self.assertEqual(factory.return_value.open.call_args.args[0].full_url,'https://api.deepseek.com/chat/completions')

    def test_dry_run_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch.object(annotate,'call_deepseek') as api:
            meta=annotate.run(source(),Path(tmp)/'dry',dry_run=True)
            self.assertEqual(meta['model'],'deepseek-flash');api.assert_not_called()

    def test_explicit_key_file_stays_out_of_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{},clear=True):
            root=Path(tmp);path=root/'key.md';secret='sk-'+'x'*30
            path.write_text('# Test credential\n'+secret+'\n')
            key=annotate.read_api_key(path)
            with patch.object(annotate,'call_deepseek',return_value=response()) as api:
                annotate.run(source(),root/'live',api_key=key)
                self.assertEqual(api.call_args.args[1],secret)
            self.assertFalse(any(secret in p.read_text() for p in (root/'live').rglob('*.json')))
