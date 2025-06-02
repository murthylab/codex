from unittest import TestCase

from codex.service.heatmaps import (
    for_display,
    heatmap_color,
    make_table,
    ALL,
    UNKNOWN,
    compute_group_sizes,
    counts_data,
)
from tests import get_testing_neuron_db


class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def test_for_display(self):
        self.assertEqual("Foo", for_display("foo"))
        self.assertEqual("Foo Bar", for_display("foo BAR"))
        self.assertEqual(UNKNOWN, for_display("NA"))
        self.assertEqual(UNKNOWN, for_display(""))
        self.assertEqual(UNKNOWN, for_display(None))

    def test_heatmap_color(self):
        self.assertEqual("#00FF0099", heatmap_color(5, 1, 3, 5))
        self.assertEqual("#00FF0099", heatmap_color(50, 1, 3, 5))
        self.assertEqual("#AAAAAA99", heatmap_color(1, 1, 3, 5))
        self.assertEqual("#AAAAAA99", heatmap_color(-5, 1, 3, 5))
        self.assertEqual("#AAAAAA0", heatmap_color(3, 1, 3, 5))

    def test_make_table(self):
        group_to_group_density = {
            ("a", "a"): 1,
            ("a", "b"): 2,
            ("b", "a"): 3,
            ("b", "b"): 4,
            (ALL, "a"): 4,
            (ALL, "b"): 6,
            ("a", ALL): 3,
            ("b", ALL): 7,
            (ALL, ALL): 10,
        }
        group_sizes = {ALL: 15, "a": 5, "b": 10}
        expected_table = [
            [
                "from \\ to",
                "<b>All</b>&nbsp;<small>100%</small>",
                "<b>b</b>&nbsp;<small>67%</small>",
                "<b>a</b>&nbsp;<small>33%</small>",
            ],
            [
                ("<b>All</b>&nbsp;<small>100%</small>", 0),
                ("100%<small> (10)<br><b>0.0476</b> avg.</small>", "#AAAAAA0"),
                ("60%<small> (6)<br><b>0.04</b> avg.</small>", "#AAAAAA28"),
                ("40%<small> (4)<br><b>0.0533</b> avg.</small>", "#00FF0024"),
            ],
            [
                ("<b>b</b>&nbsp;<small>67%</small>", 0),
                ("70%<small> (7)<br><b>0.0467</b> avg.</small>", "#AAAAAA10"),
                ("40%<small> (4)<br><b>0.0444</b> avg.</small>", "#AAAAAA18"),
                ("30%<small> (3)<br><b>0.06</b> avg.</small>", "#00FF0035"),
            ],
            [
                ("<b>a</b>&nbsp;<small>33%</small>", 0),
                ("30%<small> (3)<br><b>0.04</b> avg.</small>", "#AAAAAA28"),
                ("20%<small> (2)<br><b>0.04</b> avg.</small>", "#AAAAAA28"),
                ("10%<small> (1)<br><b>0.05</b> avg.</small>", "#00FF0015"),
            ],
        ]

        self.assertEqual(
            expected_table,
            make_table(group_to_group_density, group_sizes),
        )

    def test_group_data(self):
        expected_side_data = {
            ("All", "All"): 34153566,
            ("All", "Center"): 106466,
            ("All", "Left"): 15918456,
            ("All", "Right"): 18128464,
            ("All", "Unknown"): 180,
            ("Center", "All"): 102394,
            ("Center", "Center"): 2296,
            ("Center", "Left"): 49589,
            ("Center", "Right"): 50509,
            ("Left", "All"): 16100603,
            ("Left", "Center"): 51894,
            ("Left", "Left"): 13159934,
            ("Left", "Right"): 2888658,
            ("Left", "Unknown"): 117,
            ("Right", "All"): 17949504,
            ("Right", "Center"): 52276,
            ("Right", "Left"): 2708270,
            ("Right", "Right"): 15188895,
            ("Right", "Unknown"): 63,
            ("Unknown", "All"): 1065,
            ("Unknown", "Left"): 663,
            ("Unknown", "Right"): 402,
        }
        self.assertEqual(
            expected_side_data, counts_data(self.neuron_db, "side", "Synapses")
        )
        total_count = sum(expected_side_data.values())
        self.assertEqual(
            [total_count] * len(self.neuron_db.grouped_synapse_counts),
            [
                sum(counts_data(self.neuron_db, attr, "Synapses").values())
                for attr in self.neuron_db.grouped_synapse_counts.keys()
            ],
        )

    def test_compute_group_sizes(self):
        self.assertEqual(
            {
                "Alin": 24,
                "All": 139255,
                "Alln": 427,
                "Alon": 14,
                "Alpn": 685,
                "An": 2362,
                "Bilateral": 220,
                "Cx": 2869,
                "Dan": 331,
                "Gustatory": 343,
                "Hygrosensory": 74,
                "Kenyon Cell": 5177,
                "Lhcent": 42,
                "Lhln": 514,
                "Mbin": 4,
                "Mbon": 96,
                "Mechanosensory": 2648,
                "Ocellar": 63,
                "Olfactory": 2281,
                "Optic Lobe Intrinsic": 76928,
                "Optic Lobes": 16,
                "Pars Intercerebralis": 40,
                "Pars Lateralis": 26,
                "Thermosensory": 29,
                "Tpn": 2,
                "Tubu": 150,
                "Unknown": 32286,
                "Unknown Sensory": 135,
                "Visual": 11469,
            },
            compute_group_sizes(self.neuron_db, "class"),
        )
