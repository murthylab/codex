from unittest import TestCase

from src.utils.parsing import tokenize


class Test(TestCase):
    def test_tokenize(self):
        self.assertEqual(["1", "2", "3"], tokenize("'1', '2', '3'"))
        self.assertEqual(["hello", "world"], tokenize("hello world'"))
        self.assertEqual(["who's", "home"], tokenize("who's home?"))
