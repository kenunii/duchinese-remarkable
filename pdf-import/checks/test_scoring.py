#!/usr/bin/env python3
"""Synthetic checks for benchmark scoring; no textbook content."""
import json
from pathlib import Path
import tempfile
import unittest
from duchinese_pdf import score as s

class ScoringTests(unittest.TestCase):
    def test_insert_delete_substitute(self):
        for ref,hyp,count in [('学习','学生',1),('学习','学',1),('学','学习',1),('甲乙丙','丙甲乙',2)]:
            with self.subTest(ref=ref,hyp=hyp):self.assertEqual(s.edit_distance(ref,hyp)[0],count)
    def test_chinese_only_scope(self):
        self.assertEqual(s.han('学习 xué xí 35.7% __。'),'学习')
    def test_tesseract_headers_and_captions_are_not_dropped(self):
        xml='<html><body>'
        for i,cls in enumerate(['ocr_line','ocr_header','ocr_caption','ocr_textfloat']):
            xml+=f'<span id="line_1_{i}" class="{cls}" title="bbox 0 0 20 20"><span class="ocrx_word" title="x_wconf 95"><span class="ocrx_cinfo" title="x_bboxes 0 0 20 20">学</span></span></span>'
        xml+='</body></html>'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ocr.hocr';p.write_text(xml)
            self.assertEqual(len(s.tess_lines(p)),4)
    def test_spatial_sort_does_not_modify_raw_lines(self):
        a={'text':'甲','box':[0,0,10,10]};b={'text':'乙','box':[30,1,40,11]};c={'text':'丙','box':[0,30,10,40]}
        raw=[a,c,b];self.assertEqual(s.spatial_order(raw),[a,b,c]);self.assertEqual(raw,[a,c,b])
    def test_paddle_exported_character_boxes(self):
        value={'rec_texts':['学习'],'rec_boxes':[[0,0,20,10]],'rec_scores':[.99],
               'text_word':[['学','习']],'text_word_boxes':[[[0,0,10,10],[10,0,20,10]]]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ocr.json';p.write_text(json.dumps(value))
            lines=s.paddle_lines(p)
            self.assertEqual([c['text'] for c in lines[0]['characters']],['学','习'])
            self.assertEqual(lines[0]['characters'][1]['polygon'],[[10,0],[20,0],[20,10],[10,10]])

if __name__=='__main__':unittest.main()
