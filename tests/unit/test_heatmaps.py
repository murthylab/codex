from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import (
    TESTING_DATA_SNAPSHOT_VERSION,
)
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
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

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
            ("All", "All"): 30360387,
            ("All", "Center"): 96934,
            ("All", "Left"): 16321615,
            ("All", "Right"): 13941668,
            ("All", "Unknown"): 170,
            ("Center", "All"): 87644,
            ("Center", "Center"): 1982,
            ("Center", "Left"): 44531,
            ("Center", "Right"): 41131,
            ("Left", "All"): 16169831,
            ("Left", "Center"): 48772,
            ("Left", "Left"): 13696816,
            ("Left", "Right"): 2424180,
            ("Left", "Unknown"): 63,
            ("Right", "All"): 14101854,
            ("Right", "Center"): 46180,
            ("Right", "Left"): 2579866,
            ("Right", "Right"): 11475701,
            ("Right", "Unknown"): 107,
            ("Unknown", "All"): 1058,
            ("Unknown", "Left"): 402,
            ("Unknown", "Right"): 656,
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
                "All": 124733,
                "Alln": 424,
                "Alon": 16,
                "Alpn": 685,
                "An": 1974,
                "Bilateral": 216,
                "Csd": 2,
                "Cx": 2824,
                "Dan": 301,
                "Dn": 1267,
                "Gustatory": 333,
                "Hygrosensory": 74,
                "Kenyon Cell": 5177,
                "L1-5": 4552,
                "Lhcent": 42,
                "Lhln": 479,
                "Mal": 77,
                "Mbin": 4,
                "Mbon": 97,
                "Mechanosensory": 2098,
                "Medulla Intrinsic": 1514,
                "Motor": 100,
                "Ocellar": 62,
                "Olfactory": 2169,
                "Optic Lobes": 67101,
                "Pars Intercerebralis": 37,
                "Pars Lateralis": 26,
                "Thermosensory": 29,
                "Tubu": 150,
                "Unknown": 30190,
                "Unknown Sensory": 127,
                "Visual": 2562,
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
                    "<b>Left</b>&nbsp;<small>51%</small>",
                    "<b>Right</b>&nbsp;<small>49%</small>",
                    "<b>Center</b>&nbsp;<small>0%</small>",
                    "<b>Unknown</b>&nbsp;<small>0%</small>",
                ],
                [
                    ("<b>All</b>&nbsp;<small>100%</small>", 0),
                    ("100%<small> (30,360,387)<br><b>13</b> avg.</small>", "#AAAAAA0"),
                    ("54%<small> (16,321,615)<br><b>13</b> avg.</small>", "#00FF0011"),
                    ("46%<small> (13,941,668)<br><b>13</b> avg.</small>", "#AAAAAA11"),
                    ("0%<small> (96,934)<br><b>16</b> avg.</small>", "#00FF0083"),
                    ("0%<small> (170)<br><b>6.8</b> avg.</small>", "#AAAAAA92"),
                ],
                [
                    ("<b>Left</b>&nbsp;<small>51%</small>", 0),
                    ("53%<small> (16,169,831)<br><b>13</b> avg.</small>", "#00FF008"),
                    ("45%<small> (13,696,816)<br><b>12</b> avg.</small>", "#AAAAAA22"),
                    ("8%<small> (2,424,180)<br><b>15</b> avg.</small>", "#00FF0072"),
                    ("0%<small> (48,772)<br><b>16</b> avg.</small>", "#00FF0082"),
                    ("0%<small> (63)<br><b>5.73</b> avg.</small>", "#AAAAAA99"),
                ],
                [
                    ("<b>Right</b>&nbsp;<small>49%</small>", 0),
                    ("46%<small> (14,101,854)<br><b>13</b> avg.</small>", "#AAAAAA8"),
                    ("8%<small> (2,579,866)<br><b>15</b> avg.</small>", "#00FF0074"),
                    ("38%<small> (11,475,701)<br><b>12</b> avg.</small>", "#AAAAAA27"),
                    ("0%<small> (46,180)<br><b>16</b> avg.</small>", "#00FF0083"),
                    ("0%<small> (107)<br><b>7.64</b> avg.</small>", "#AAAAAA85"),
                ],
                [
                    ("<b>Center</b>&nbsp;<small>0%</small>", 0),
                    ("0%<small> (87,644)<br><b>17</b> avg.</small>", "#00FF0093"),
                    ("0%<small> (44,531)<br><b>17</b> avg.</small>", "#00FF0095"),
                    ("0%<small> (41,131)<br><b>16</b> avg.</small>", "#00FF0091"),
                    ("0%<small> (1,982)<br><b>17</b> avg.</small>", "#00FF0099"),
                    ("0%<small> (0)<br><b>0</b> avg.</small>", "#AAAAAA99"),
                ],
                [
                    ("<b>Unknown</b>&nbsp;<small>0%</small>", 0),
                    ("0%<small> (1,058)<br><b>10</b> avg.</small>", "#AAAAAA56"),
                    ("0%<small> (402)<br><b>9.57</b> avg.</small>", "#AAAAAA67"),
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
