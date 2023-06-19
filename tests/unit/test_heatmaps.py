from unittest import TestCase

from src.service.heatmaps import (
    for_display,
    heatmap_color,
    make_table,
    ALL,
    UNKNOWN,
    compute_group_sizes,
    heatmap_data,
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
            ("All", "All"): 32970606,
            ("All", "Center"): 119588,
            ("All", "Left"): 15166501,
            ("All", "Right"): 17684342,
            ("All", "Unknown"): 175,
            ("Center", "All"): 106808,
            ("Center", "Center"): 2483,
            ("Center", "Left"): 50615,
            ("Center", "Right"): 53710,
            ("Left", "All"): 15346024,
            ("Left", "Center"): 57547,
            ("Left", "Left"): 12423291,
            ("Left", "Right"): 2865074,
            ("Left", "Unknown"): 112,
            ("Right", "All"): 17516716,
            ("Right", "Center"): 59558,
            ("Right", "Left"): 2691939,
            ("Right", "Right"): 14765156,
            ("Right", "Unknown"): 63,
            ("Unknown", "All"): 1058,
            ("Unknown", "Left"): 656,
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
                "All": 127978,
                "Alln": 424,
                "Alon": 16,
                "Alpn": 685,
                "An": 2364,
                "Bilateral": 216,
                "Csd": 2,
                "Cx": 2859,
                "Dan": 326,
                "Dn": 1301,
                "Gustatory": 335,
                "Hygrosensory": 74,
                "Kenyon Cell": 5177,
                "L1-5": 4588,
                "Lhcent": 42,
                "Lhln": 479,
                "Mal": 77,
                "Mbin": 4,
                "Mbon": 97,
                "Mechanosensory": 2646,
                "Medulla Intrinsic": 1515,
                "Motor": 100,
                "Ocellar": 62,
                "Olfactory": 2276,
                "Optic Lobes": 67390,
                "Pars Intercerebralis": 40,
                "Pars Lateralis": 28,
                "Thermosensory": 29,
                "Tubu": 150,
                "Unknown": 30306,
                "Unknown Sensory": 133,
                "Visual": 4213,
            },
            compute_group_sizes(self.neuron_db, "class"),
        )

    def test_synapse_density_data(self):
        expected = {
            "count_type": "Synapses",
            "count_type_options": ["Synapses", "Connections", "Reciprocal Connections"],
            "explanations": [
                "This table shows the distribution of <b>synapses</b> across "
                "neurons grouped by <b>side</b>.",
                "In each cell, the first line shows the number of "
                "<b>synapses</b> for the corresponding pair of neuron "
                "groups, and the second line shows the average value, "
                "normalized by <b>number of connected neurons in the group "
                "pair</b>.",
                "Cell colors are assigned to highlight the group pairs for "
                "which average value deviates from the overall average.",
            ],
            "group_by": "Side",
            "group_by_options": [
                "Side",
                "Flow",
                "Nt Type",
                "Super Class",
                "Class",
                "Sub Class",
            ],
            "table": [
                [
                    "from \\ to",
                    "<b>All</b>&nbsp;<small>100%</small>",
                    "<b>Right</b>&nbsp;<small>51%</small>",
                    "<b>Left</b>&nbsp;<small>49%</small>",
                    "<b>Center</b>&nbsp;<small>0%</small>",
                    "<b>Unknown</b>&nbsp;<small>0%</small>",
                ],
                [
                    ("<b>All</b>&nbsp;<small>100%</small>", 0),
                    ("100%<small> (32,970,606)<br><b>13</b> avg.</small>", "#AAAAAA0"),
                    ("54%<small> (17,684,342)<br><b>13</b> avg.</small>", "#00FF0012"),
                    ("46%<small> (15,166,501)<br><b>13</b> avg.</small>", "#AAAAAA11"),
                    ("0%<small> (119,588)<br><b>15</b> avg.</small>", "#00FF0084"),
                    ("0%<small> (175)<br><b>6.73</b> avg.</small>", "#AAAAAA92"),
                ],
                [
                    ("<b>Right</b>&nbsp;<small>51%</small>", 0),
                    ("53%<small> (17,516,716)<br><b>13</b> avg.</small>", "#00FF008"),
                    ("45%<small> (14,765,156)<br><b>12</b> avg.</small>", "#AAAAAA21"),
                    ("8%<small> (2,691,939)<br><b>15</b> avg.</small>", "#00FF0074"),
                    ("0%<small> (59,558)<br><b>15</b> avg.</small>", "#00FF0085"),
                    ("0%<small> (63)<br><b>5.73</b> avg.</small>", "#AAAAAA99"),
                ],
                [
                    ("<b>Left</b>&nbsp;<small>49%</small>", 0),
                    ("47%<small> (15,346,024)<br><b>13</b> avg.</small>", "#AAAAAA8"),
                    ("9%<small> (2,865,074)<br><b>15</b> avg.</small>", "#00FF0076"),
                    ("38%<small> (12,423,291)<br><b>12</b> avg.</small>", "#AAAAAA26"),
                    ("0%<small> (57,547)<br><b>15</b> avg.</small>", "#00FF0082"),
                    ("0%<small> (112)<br><b>7.47</b> avg.</small>", "#AAAAAA86"),
                ],
                [
                    ("<b>Center</b>&nbsp;<small>0%</small>", 0),
                    ("0%<small> (106,808)<br><b>15</b> avg.</small>", "#00FF0084"),
                    ("0%<small> (53,710)<br><b>15</b> avg.</small>", "#00FF0085"),
                    ("0%<small> (50,615)<br><b>15</b> avg.</small>", "#00FF0081"),
                    ("0%<small> (2,483)<br><b>16</b> avg.</small>", "#00FF0099"),
                    ("0%<small> (0)<br><b>0</b> avg.</small>", "#AAAAAA99"),
                ],
                [
                    ("<b>Unknown</b>&nbsp;<small>0%</small>", 0),
                    ("0%<small> (1,058)<br><b>10</b> avg.</small>", "#AAAAAA56"),
                    ("0%<small> (402)<br><b>9.57</b> avg.</small>", "#AAAAAA66"),
                    ("0%<small> (656)<br><b>11</b> avg.</small>", "#AAAAAA47"),
                    ("0%<small> (0)<br><b>0</b> avg.</small>", "#AAAAAA99"),
                    ("0%<small> (0)<br><b>0</b> avg.</small>", "#AAAAAA99"),
                ],
            ],
        }
        self.assertEqual(
            expected,
            heatmap_data(self.neuron_db, group_by="Side", count_type="Synapses"),
        )
