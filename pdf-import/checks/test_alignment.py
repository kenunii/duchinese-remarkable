#!/usr/bin/env python3
"""Synthetic checks for exact OCR alignment and words crossing line breaks."""
from pathlib import Path
import unittest
from duchinese_pdf import assemble as module

class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.chars={'characters':[
            {'text':'学','offset':0,'line':0,'box':[10,10,20,20]},
            {'text':'习','offset':1,'line':1,'box':[10,40,20,20]}]}
        self.annotations={'words':[{'hanzi':'学习','pinyin':'xué xí','meaning':'to study','start':0,'end':2,'sentence':0}],
                          'sentences':[{'text':'学习','translation':'Study.'}]}
    def test_word_across_lines_keeps_two_boxes(self):
        result=module.assemble(self.chars,self.annotations,(100,100))
        self.assertEqual(result['words'][0]['boxes'],[[10,10,20,20],[10,40,20,20]])
    def test_rewritten_text_is_rejected(self):
        self.annotations['words'][0]['hanzi']='学生'
        with self.assertRaises(ValueError):module.assemble(self.chars,self.annotations,(100,100))
    def test_missing_character_is_rejected(self):
        self.annotations['words']=[]
        with self.assertRaises(ValueError):module.assemble(self.chars,self.annotations,(100,100))
    def test_box_outside_page_is_rejected(self):
        self.chars['characters'][0]['box']=[90,10,20,20]
        with self.assertRaises(ValueError):module.assemble(self.chars,self.annotations,(100,100))
    def test_wrong_sentence_is_rejected(self):
        self.annotations['sentences'][0]['text']='学生'
        with self.assertRaises(ValueError):module.assemble(self.chars,self.annotations,(100,100))
    def test_prepared_raster_dimensions_are_checked(self):
        self.chars['image_size'] = [200, 200]
        with self.assertRaises(ValueError):module.assemble(self.chars,self.annotations,(100,100))

if __name__=='__main__':unittest.main()
