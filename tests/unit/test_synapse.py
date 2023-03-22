from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
from src.service.synapse import (
    for_display,
    heatmap_color,
    make_table,
    ALL,
    UNKNOWN,
    compute_group_sizes,
    synapse_density_data,
    group_data,
    GROUP_BY_ATTRIBUTES,
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
                ("10 <small>(100%)<br><b>0.0476</b> (density)</small>", "#AAAAAA0"),
                ("6 <small>(60%)<br><b>0.04</b> (density)</small>", "#AAAAAA28"),
                ("4 <small>(40%)<br><b>0.0533</b> (density)</small>", "#00FF0024"),
            ],
            [
                ("<b>b</b>&nbsp;<small>67%</small>", 0),
                ("7 <small>(70%)<br><b>0.0467</b> (density)</small>", "#AAAAAA10"),
                ("4 <small>(40%)<br><b>0.0444</b> (density)</small>", "#AAAAAA18"),
                ("3 <small>(30%)<br><b>0.06</b> (density)</small>", "#00FF0035"),
            ],
            [
                ("<b>a</b>&nbsp;<small>33%</small>", 0),
                ("3 <small>(30%)<br><b>0.04</b> (density)</small>", "#AAAAAA28"),
                ("2 <small>(20%)<br><b>0.04</b> (density)</small>", "#AAAAAA28"),
                ("1 <small>(10%)<br><b>0.05</b> (density)</small>", "#00FF0015"),
            ],
        ]

        self.assertEqual(
            expected_table,
            make_table(group_to_group_density, group_sizes),
        )

    def test_group_data(self):
        gdata = group_data(self.neuron_db)
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
        self.assertEqual(expected_side_data, gdata["side"])
        total_count = sum(expected_side_data.values())
        self.assertEqual(
            [total_count] * len(GROUP_BY_ATTRIBUTES),
            [sum(gdata[attr].values()) for attr in GROUP_BY_ATTRIBUTES.values()],
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
            "group_by": "Side",
            "group_by_options": [
                "Side",
                "Flow",
                "NT Type",
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
                    (
                        "29,003,052 <small>(100%)<br><b>0.0021</b> (density)</small>",
                        "#AAAAAA0",
                    ),
                    (
                        "15,684,269 <small>(54%)<br><b>0.00221</b> (density)</small>",
                        "#00FF003",
                    ),
                    (
                        "13,216,178 <small>(46%)<br><b>0.00197</b> (density)</small>",
                        "#AAAAAA4",
                    ),
                    (
                        "94,063 <small>(0%)<br><b>0.00702</b> (density)</small>",
                        "#00FF0018",
                    ),
                    (
                        "8,542 <small>(0%)<br><b>0.000943</b> (density)</small>",
                        "#AAAAAA11",
                    ),
                ],
                [
                    ("<b>Left</b>&nbsp;<small>51%</small>", 0),
                    (
                        "15,560,906 <small>(54%)<br><b>0.00219</b> (density)</small>",
                        "#00FF003",
                    ),
                    (
                        "13,202,977 <small>(46%)<br><b>0.00362</b> (density)</small>",
                        "#00FF0010",
                    ),
                    (
                        "2,307,293 <small>(8%)<br><b>0.00067</b> (density)</small>",
                        "#AAAAAA12",
                    ),
                    (
                        "46,456 <small>(0%)<br><b>0.00675</b> (density)</small>",
                        "#00FF0018",
                    ),
                    (
                        "4,180 <small>(0%)<br><b>0.000899</b> (density)</small>",
                        "#AAAAAA11",
                    ),
                ],
                [
                    ("<b>Right</b>&nbsp;<small>49%</small>", 0),
                    (
                        "13,344,889 <small>(46%)<br><b>0.00199</b> (density)</small>",
                        "#AAAAAA3",
                    ),
                    (
                        "2,431,334 <small>(8%)<br><b>0.000706</b> (density)</small>",
                        "#AAAAAA12",
                    ),
                    (
                        "10,863,588 <small>(37%)<br><b>0.00334</b> (density)</small>",
                        "#00FF009",
                    ),
                    (
                        "45,637 <small>(0%)<br><b>0.00702</b> (density)</small>",
                        "#00FF0018",
                    ),
                    (
                        "4,330 <small>(0%)<br><b>0.000986</b> (density)</small>",
                        "#AAAAAA11",
                    ),
                ],
                [
                    ("<b>Center</b>&nbsp;<small>0%</small>", 0),
                    (
                        "87,273 <small>(0%)<br><b>0.00651</b> (density)</small>",
                        "#00FF0018",
                    ),
                    (
                        "43,503 <small>(0%)<br><b>0.00632</b> (density)</small>",
                        "#00FF0017",
                    ),
                    (
                        "41,860 <small>(0%)<br><b>0.00644</b> (density)</small>",
                        "#00FF0017",
                    ),
                    (
                        "1,883 <small>(0%)<br><b>0.146</b> (density)</small>",
                        "#00FF0099",
                    ),
                    ("27 <small>(0%)<br><b>0.00308</b> (density)</small>", "#00FF008"),
                ],
                [
                    ("<b>Unknown</b>&nbsp;<small>0%</small>", 0),
                    (
                        "9,984 <small>(0%)<br><b>0.0011</b> (density)</small>",
                        "#AAAAAA10",
                    ),
                    (
                        "6,455 <small>(0%)<br><b>0.00139</b> (density)</small>",
                        "#AAAAAA8",
                    ),
                    (
                        "3,437 <small>(0%)<br><b>0.000782</b> (density)</small>",
                        "#AAAAAA11",
                    ),
                    ("87 <small>(0%)<br><b>0.00991</b> (density)</small>", "#00FF0023"),
                    ("5 <small>(0%)<br><b>0.000854</b> (density)</small>", "#AAAAAA11"),
                ],
            ],
        }
        self.assertEqual(
            expected,
            synapse_density_data(
                self.neuron_db,
                group_by="Side",
            ),
        )
