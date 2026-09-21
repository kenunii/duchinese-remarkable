import unittest
from PIL import Image,ImageDraw
from duchinese_pdf.page_view import content_view

class PageViewTests(unittest.TestCase):
    def test_asymmetric_blank_margins_removed(self):
        image=Image.new('RGB',(2000,1400),'white');ImageDraw.Draw(image).rectangle((1100,200,1800,1200),fill='black')
        x,y,w,h=content_view(image)
        self.assertTrue(1000<x<1100 and 100<y<200)
        self.assertTrue(x+w>1800 and y+h>1200)
        self.assertLess(w,900)
    def test_faint_ocr_and_illustration_both_retained(self):
        image=Image.new('RGB',(2000,1400),'white');ImageDraw.Draw(image).rectangle((1100,200,1300,400),fill='black')
        x,y,w,h=content_view(image,[[900,1100,500,100]])
        self.assertLessEqual(x,900);self.assertLessEqual(y,200)
        self.assertGreaterEqual(x+w,1400);self.assertGreaterEqual(y+h,1200)
    def test_blank_page_and_full_bleed(self):
        self.assertEqual(content_view(Image.new('RGB',(100,150),'white')),[0,0,100,150])
        self.assertEqual(content_view(Image.new('RGB',(100,150),'black')),[0,0,100,150])
