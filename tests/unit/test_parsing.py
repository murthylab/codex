from unittest import TestCase
from src.utils.parsing import tokenize_for_highlight


class TestTokenizeForHighlight(TestCase):
    def test_tokenize_for_highlight(self):
        tags = [
            "Mushroom Body Kenyon cell KC",
            "name from DOI: 10.7554/eLife.66039",
            "ventral unpaired medial/VUM?",
        ]
        for tag in tags:
            tokens = tokenize_for_highlight(tag)
            assert len(tokens) > 0
            for token, start, end in tokens:
                assert start >= 0
                assert end >= 0
                assert end > start
                assert len(token) > 0
                assert token == tag[start:end].casefold()
