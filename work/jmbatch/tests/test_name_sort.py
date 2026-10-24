from unittest import TestCase
from name_sort import name_key


class NameSortTest(TestCase):
    def test_pinyin_continues_through_every_character(self):
        self.assertEqual(sorted(['安中白', '白安', '安中阿', '安波', '安', '安阿'], key=name_key),
                         ['安', '安阿', '安波', '安中阿', '安中白', '白安'])

    def test_full_syllables_and_character_boundaries(self):
        self.assertEqual(sorted(['先安', '西中', '先', '西安', '西'], key=name_key),
                         ['西', '西安', '西中', '先', '先安'])
        self.assertEqual(sorted(['波', '白', '包'], key=name_key), ['白', '包', '波'])

    def test_homophones_compare_later_characters_and_ties_are_stable(self):
        self.assertEqual(sorted(['安白', '鞍阿', '安阿'], key=name_key), ['鞍阿', '安阿', '安白'])

    def test_digits_case_punctuation_empty_and_supplementary_characters(self):
        self.assertEqual(sorted(['A2', 'a10', 'A1', 'a', '[安]', '', '安'], key=name_key),
                         ['', '[安]', 'a', 'A1', 'a10', 'A2', '安'])
        self.assertEqual(name_key('𠀀阿'), ('he', 'a'))
        self.assertEqual(name_key('𠮷阿'), ('𠮷', 'a'))  # Unmapped characters are preserved.
        self.assertLess(name_key('\ue000'), name_key('😀'))
        self.assertEqual(name_key('女'), ('nv',))
        self.assertEqual(name_key('繁體'), ('fan', 'ti'))
