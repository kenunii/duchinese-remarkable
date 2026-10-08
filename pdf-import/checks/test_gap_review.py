import unittest

from duchinese_pdf.assemble import assemble
from duchinese_pdf.line_contract import compile_lines


class GapReviewTests(unittest.TestCase):
    def setUp(self):
        self.source = {'image_size': [300, 100], 'characters': [
            {'offset': 0, 'text': '双', 'line': 0, 'box': [10, 10, 20, 20]},
            {'offset': 1, 'text': '塔', 'line': 0, 'box': [100, 10, 20, 20]},
        ]}
        self.answer = {'lines': [{'id': 'L1', 'text': '双塔',
                                  'correction_reason': ''}],
                       'sentences': [{'translation': 'Twin towers.', 'words': [
                           {'text': '双塔', 'pinyin': 'shuāng tǎ',
                            'meaning': 'twin towers'}]}]}

    def test_reviewed_title_gap_keeps_separate_highlight_boxes(self):
        with self.assertRaisesRegex(ValueError, 'large horizontal layout gap'):
            compile_lines(self.source, self.answer)
        corrected, annotations, _ = compile_lines(
            self.source, self.answer, allowed_word_gaps=[1])
        book = assemble(corrected, annotations, (300, 100))
        self.assertEqual(book['words'][0]['boxes'],
                         [[10, 10, 20, 20], [100, 10, 20, 20]])

    def test_cannot_whitelist_nonexistent_gap(self):
        with self.assertRaisesRegex(ValueError, 'not an observed layout gap'):
            compile_lines(self.source, self.answer, allowed_word_gaps=[2])


if __name__ == '__main__':
    unittest.main()
