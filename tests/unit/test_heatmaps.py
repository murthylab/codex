from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
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
            version=DEFAULT_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
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
            ("All", "All"): 29003052,
            ("All", "Center"): 94063,
            ("All", "Left"): 15684269,
            ("All", "Right"): 13216178,
            ("All", "Unknown"): 8542,
            ("Center", "All"): 87273,
            ("Center", "Center"): 1883,
            ("Center", "Left"): 43503,
            ("Center", "Right"): 41860,
            ("Center", "Unknown"): 27,
            ("Left", "All"): 15560906,
            ("Left", "Center"): 46456,
            ("Left", "Left"): 13202977,
            ("Left", "Right"): 2307293,
            ("Left", "Unknown"): 4180,
            ("Right", "All"): 13344889,
            ("Right", "Center"): 45637,
            ("Right", "Left"): 2431334,
            ("Right", "Right"): 10863588,
            ("Right", "Unknown"): 4330,
            ("Unknown", "All"): 9984,
            ("Unknown", "Center"): 87,
            ("Unknown", "Left"): 6455,
            ("Unknown", "Right"): 3437,
            ("Unknown", "Unknown"): 5,
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
                "All": 117605,
                "Alln": 425,
                "Alon": 15,
                "Alpn": 678,
                "An": 1929,
                "Bilateral": 219,
                "Csd": 2,
                "Cx": 2195,
                "Dan": 300,
                "Dn": 1266,
                "Endocrine": 69,
                "Fragment": 25,
                "Glia": 1,
                "Gustatory": 334,
                "Hygrosensory": 74,
                "Kenyon Cell": 5177,
                "L1-5": 4249,
                "Lhcent": 42,
                "Mal": 77,
                "Mbin": 4,
                "Mbon": 94,
                "Mechanosensory": 2048,
                "Motor": 100,
                "Ocellar": 42,
                "Olfactory": 2158,
                "Optic Lobes": 64319,
                "Ring Neuron": 276,
                "Thermosensory": 29,
                "Tubu": 150,
                "Unknown": 31029,
                "Unknown Sensory": 131,
                "Visual": 124,
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
                    ("100%<small> (29,003,052)<br><b>13</b> avg.</small>", "#AAAAAA0"),
                    ("54%<small> (15,684,269)<br><b>13</b> avg.</small>", "#00FF007"),
                    ("46%<small> (13,216,178)<br><b>13</b> avg.</small>", "#AAAAAA8"),
                    ("0%<small> (94,063)<br><b>16</b> avg.</small>", "#00FF0079"),
                    ("0%<small> (8,542)<br><b>11</b> avg.</small>", "#AAAAAA42"),
                ],
                [
                    ("<b>Left</b>&nbsp;<small>51%</small>", 0),
                    ("54%<small> (15,560,906)<br><b>13</b> avg.</small>", "#00FF004"),
                    ("46%<small> (13,202,977)<br><b>12</b> avg.</small>", "#AAAAAA21"),
                    ("8%<small> (2,307,293)<br><b>15</b> avg.</small>", "#00FF0073"),
                    ("0%<small> (46,456)<br><b>16</b> avg.</small>", "#00FF0078"),
                    ("0%<small> (4,180)<br><b>10</b> avg.</small>", "#AAAAAA58"),
                ],
                [
                    ("<b>Right</b>&nbsp;<small>49%</small>", 0),
                    ("46%<small> (13,344,889)<br><b>13</b> avg.</small>", "#AAAAAA6"),
                    ("8%<small> (2,431,334)<br><b>15</b> avg.</small>", "#00FF0072"),
                    ("37%<small> (10,863,588)<br><b>12</b> avg.</small>", "#AAAAAA25"),
                    ("0%<small> (45,637)<br><b>16</b> avg.</small>", "#00FF0079"),
                    ("0%<small> (4,330)<br><b>13</b> avg.</small>", "#00FF0020"),
                ],
                [
                    ("<b>Center</b>&nbsp;<small>0%</small>", 0),
                    ("0%<small> (87,273)<br><b>17</b> avg.</small>", "#00FF0091"),
                    ("0%<small> (43,503)<br><b>17</b> avg.</small>", "#00FF0094"),
                    ("0%<small> (41,860)<br><b>16</b> avg.</small>", "#00FF0088"),
                    ("0%<small> (1,883)<br><b>17</b> avg.</small>", "#00FF0099"),
                    ("0%<small> (27)<br><b>9</b> avg.</small>", "#AAAAAA69"),
                ],
                [
                    ("<b>Unknown</b>&nbsp;<small>0%</small>", 0),
                    ("0%<small> (9,984)<br><b>11</b> avg.</small>", "#AAAAAA46"),
                    ("0%<small> (6,455)<br><b>12</b> avg.</small>", "#AAAAAA33"),
                    ("0%<small> (3,437)<br><b>9.76</b> avg.</small>", "#AAAAAA62"),
                    ("0%<small> (87)<br><b>17</b> avg.</small>", "#00FF0099"),
                    ("0%<small> (5)<br><b>5</b> avg.</small>", "#AAAAAA99"),
                ],
            ],
        }
        self.assertEqual(
            expected,
            heatmap_data(self.neuron_db, group_by="Side", count_type="Synapses"),
        )
