from unittest import TestCase
from src.utils.parsing import tokenize_and_fold_for_highlight
from src.utils.formatting import highlight_annotations


class TestHighlighting(TestCase):
    def test_tokenize_for_highlight(self):
        tags = [
            "Mushroom Body Kenyon cell KC",
            "name from DOI: 10.7554/eLife.66039",
            "ventral unpaired medial/VUM?",
        ]
        for tag in tags:
            tokens = tokenize_and_fold_for_highlight(tag)
            self.assertGreater(len(tokens), 0)

            for token, start, end in tokens:
                self.assertGreaterEqual(start, 0)
                self.assertGreaterEqual(end, 0)
                self.assertGreater(end, start)
                self.assertGreater(len(token), 0)
                self.assertEqual(token, tag[start:end].casefold())

    def test_highlight_annotations(self):
        input = [  # (filter_string, tags, expected)
            (
                "KC",
                ["Mushroom Body Kenyon cell KC"],
                'Mushroom Body <span style="padding:1px;border-radius:5px;background-color:lightgreen">Kenyon cell</span> <span style="padding:1px;border-radius:5px;background-color:lightgreen">KC</span>',
            ),
            (
                "mushroom body",
                ["Mushroom Body Kenyon cell KC"],
                '<span style="padding:1px;border-radius:5px;background-color:lightgreen">Mushroom Body</span> Kenyon cell KC',
            ),
            (
                "shroo",
                ["Mushroom Body Kenyon cell KC"],
                'Mu<span style="padding:1px;border-radius:5px;background-color:yellow">shroo</span>m Body Kenyon cell KC',
            ),
        ]
        for filter_string, tags, expected in input:
            actual = highlight_annotations(filter_string, tags)
            self.assertEqual(actual, expected)
