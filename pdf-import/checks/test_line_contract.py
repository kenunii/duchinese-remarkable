"""Regression checks for the experimental model-independent alignment contract."""
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from line_contract import compile_lines

class LineContractTests(unittest.TestCase):
    def setUp(self):
        self.source={'image_size':[200,100],'characters':[{'offset':i,'text':c,'line':0,'box':[i*20,0,20,20]} for i,c in enumerate('自已。')]}
        self.answer={'lines':[{'id':'L1','text':'自己。','correction_reason':'自己 is the intended word.'}],
                     'sentences':[{'translation':'Oneself.','words':[{'text':'自己','pinyin':'zì jǐ','meaning':'oneself'},{'text':'。','pinyin':'','meaning':''}]}]}
    def test_derives_position_and_preserves_geometry(self):
        before=copy.deepcopy(self.source)
        corrected,_,audit=compile_lines(self.source,self.answer)
        self.assertEqual(audit['changes'][0]['offset'],1)
        self.assertEqual(self.source,before)
        self.assertEqual([c['box'] for c in corrected['characters']],[c['box'] for c in before['characters']])
    def test_rejects_bad_line_coverage(self):
        for lines in [[],self.answer['lines']*2,[dict(self.answer['lines'][0],id='L2')]]:
            with self.subTest(lines=lines),self.assertRaises(ValueError):compile_lines(self.source,dict(self.answer,lines=lines))
    def test_rejects_insert_delete_and_disallowed_substitution(self):
        for text in ['自[blank]己。','自。','自己！']:
            a=copy.deepcopy(self.answer);a['lines'][0]['text']=text
            with self.subTest(text=text),self.assertRaises(ValueError):compile_lines(self.source,a)
    def test_rejects_word_coverage_even_when_lines_correct(self):
        a=copy.deepcopy(self.answer);a['sentences'][0]['words'].pop()
        with self.assertRaises(ValueError):compile_lines(self.source,a)
    def test_rejects_reason_without_change(self):
        a=copy.deepcopy(self.answer);a['lines'][0]['text']='自已。'
        with self.assertRaises(ValueError):compile_lines(self.source,a)
