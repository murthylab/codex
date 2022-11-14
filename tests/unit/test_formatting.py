from unittest import TestCase
from src.utils.parsing import tokenize_and_fold_for_highlight
from src.utils.formatting import highlight_annotations


class TestHighlighting(TestCase):
    def test_tokenize_for_highlight(self):
        cases = [
            (
                "Mushroom Body Kenyon cell KC",
                [
                    ("mushroom", 0, 8),
                    ("body", 9, 13),
                    ("kenyon", 14, 20),
                    ("cell", 21, 25),
                    ("kc", 26, 28),
                ],
            ),
            (
                "name from DOI: 10.7554/eLife.66039",
                [
                    ("name", 0, 4),
                    ("from", 5, 9),
                    ("doi", 10, 13),
                    ("10", 15, 17),
                    ("7554", 18, 22),
                    ("elife", 23, 28),
                    ("66039", 29, 34),
                ],
            ),
            (
                "ventral unpaired medial/VUM?",
                [
                    ("ventral", 0, 7),
                    ("unpaired", 8, 16),
                    ("medial", 17, 23),
                    ("vum", 24, 27),
                ],
            ),
        ]
        for case in cases:
            tag = case[0]
            expected = case[1]
            actual = tokenize_and_fold_for_highlight(tag)
            self.assertGreater(len(actual), 0)
            self.assertEqual(actual, expected)

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
