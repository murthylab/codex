from unittest import TestCase

from src.data.structured_search_filters import parse_search_query
from src.utils.parsing import tokenize_and_fold_for_highlight
from src.utils.formatting import (
    highlight_annotations,
    truncate,
    nanometer_to_flywire_coordinates,
    nanos_to_formatted_micros,
    display,
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
            label = case[0]
            expected = case[1]
            actual = tokenize_and_fold_for_highlight(label)
            self.assertGreater(len(actual), 0)
            self.assertEqual(actual, expected)

    def test_highlight_annotations(self):
        self.maxDiff = None
        input = [  # (filter_string, labels, expected)
            (
                "Kenyon cell KC",
                ["Mushroom Body Kenyon cell KC"],
                [
                    'Mushroom Body <span class="highlight-green">Kenyon</span> <span class="highlight-green">cell</span> <span class="highlight-green">KC</span>'
                ],
            ),
            (
                "mushroom body",
                ["Mushroom Body Kenyon cell KC"],
                [
                    '<span class="highlight-green">Mushroom</span> <span class="highlight-green">Body</span> Kenyon cell KC'
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
                    '<span class="highlight-yellow">pMP</span>3a; put_PDM15gC; pCd1?*',
                    "SMPpv1; right; acetylcholine*",
                    "pCd1?",
                    "putative fru*",
                    "putative dsx",
                ],
            ),
            (
                "shroo",
                ["Mushroom Body Kenyon cell KC"],
                ['Mu<span class="highlight-yellow">shroo</span>m Body Kenyon cell KC'],
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
                    '<span class="highlight-green">some</span> <span class="highlight-green">label</span>*'
                ],
            ),
        ]
        for filter_string, labels, expected in input:
            free_form_search_terms = parse_search_query(filter_string)[1]
            actual = highlight_annotations(free_form_search_terms, labels)
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

    def test_nanos_to_formatted_micros(self):
        self.assertEqual("1 &#181;m", nanos_to_formatted_micros(1000, 1))
        self.assertEqual("1 &#181;m", nanos_to_formatted_micros(1234, 1))
        self.assertEqual("2 &#181;m", nanos_to_formatted_micros(1560, 1))
        self.assertEqual(
            "47 &#181;m<sup>2</sup>", nanos_to_formatted_micros(46546541, 2)
        )
        self.assertEqual(
            "12 &#181;m<sup>2</sup>", nanos_to_formatted_micros(12344565, 2)
        )
        self.assertEqual(
            "16 &#181;m<sup>2</sup>", nanos_to_formatted_micros(15604456, 2)
        )
        self.assertEqual("0 &#181;m<sup>3</sup>", nanos_to_formatted_micros(1000, 3))
        self.assertEqual(
            "1 &#181;m<sup>3</sup>", nanos_to_formatted_micros(1234456789, 3)
        )
        self.assertEqual(
            "78,775,445,549 &#181;m<sup>3</sup>",
            nanos_to_formatted_micros(78775445548744654654, 3),
        )

    def test_display(self):
        self.assertEqual("Side", display("side"))
        self.assertEqual("Soma Side", display("soma_side"))
        self.assertEqual("123,456", display(123456))
        self.assertEqual(123456.0, display(123456.0))
        self.assertEqual(None, display(None))
