from unittest import TestCase

from src.data.structured_search_filters import parse_search_query
from src.utils.parsing import tokenize_and_fold_for_highlight
from src.utils.formatting import (
    highlight_annotations,
    truncate,
    nanometer_to_flywire_coordinates,
)


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
        self.maxDiff = None
        input = [  # (filter_string, tags, expected)
            (
                "Kenyon cell KC",
                ["Mushroom Body Kenyon cell KC"],
                [
                    'Mushroom Body <span style="padding:1px;border-radius:5px;background-color:#C5FCB8">Kenyon</span> <span style="padding:1px;border-radius:5px;background-color:#C5FCB8">cell</span> <span style="padding:1px;border-radius:5px;background-color:#C5FCB8">KC</span>'
                ],
            ),
            (
                "mushroom body",
                ["Mushroom Body Kenyon cell KC"],
                [
                    '<span style="padding:1px;border-radius:5px;background-color:#C5FCB8">Mushroom</span> <span style="padding:1px;border-radius:5px;background-color:#C5FCB8">Body</span> Kenyon cell KC'
                ],
            ),
            (
                "pMP",
                [
                    "pCd1(FW)/SMP487(HB) *",
                    "SMPpv1; left",
                    "pMP3a; put_PDM15gC; pCd1?*",
                    "SMPpv1; right; acetylcholine*",
                    "pCd1?",
                    "putative fru*",
                    "putative dsx",
                ],
                [
                    "pCd1(FW)/SMP487(HB) *",
                    "SMPpv1; left",
                    '<span style="padding:1px;border-radius:5px;background-color:#F7FCB8">pMP</span>3a; put_PDM15gC; pCd1?*',
                    "SMPpv1; right; acetylcholine*",
                    "pCd1?",
                    "putative fru*",
                    "putative dsx",
                ],
            ),
            (
                "shroo",
                ["Mushroom Body Kenyon cell KC"],
                [
                    'Mu<span style="padding:1px;border-radius:5px;background-color:#F7FCB8">shroo</span>m Body Kenyon cell KC'
                ],
            ),
            (
                "{has} name",
                ["there is name here but it should not be highlighted"],
                ["there is name here but it should not be highlighted"],
            ),
            (
                "some label",
                ["some label*"],
                [
                    '<span style="padding:1px;border-radius:5px;background-color:#C5FCB8">some</span> <span style="padding:1px;border-radius:5px;background-color:#C5FCB8">label</span>*'
                ],
            ),
        ]
        for filter_string, tags, expected in input:
            free_form_search_terms = parse_search_query(filter_string)[1]
            actual = highlight_annotations(free_form_search_terms, tags)
            self.assertEqual(expected, actual, filter_string)

    def test_truncate(self):
        self.assertEqual("bit", truncate("bit", 5))
        self.assertEqual("bit..", truncate("bit longer", 5))
        self.assertEqual(
            "bit..(21)", truncate("bit longer with count", 5, include_length=True)
        )
        self.assertEqual("bits", truncate("bits", 5))
        self.assertEqual("bitim", truncate("bitim", 5))
        self.assertEqual("", truncate("", 5))
        self.assertEqual("123", truncate(123, 5))
        self.assertEqual("123..", truncate(123456789, 5))

    def test_nanometer_to_flywire_coordinates(self):
        self.assertEqual((1, 1, 1), nanometer_to_flywire_coordinates("[4, 4, 40]"))
        self.assertEqual((1, 1, 1), nanometer_to_flywire_coordinates("[4, 4, 41]"))
        self.assertEqual((1, 1, 2), nanometer_to_flywire_coordinates("[3, 3, 61]"))
        self.assertEqual((1, 1, 2), nanometer_to_flywire_coordinates("[3 3 61]"))
        self.assertEqual((1, 1, 2), nanometer_to_flywire_coordinates("3, 3, 61"))
        self.assertEqual((1, 1, 2), nanometer_to_flywire_coordinates("3 3  61"))
        with self.assertRaises(ValueError):
            nanometer_to_flywire_coordinates("3, 3, foo")
        with self.assertRaises(AssertionError):
            nanometer_to_flywire_coordinates("3, 33")
        with self.assertRaises(AssertionError):
            nanometer_to_flywire_coordinates("3, 3, 3 2")
