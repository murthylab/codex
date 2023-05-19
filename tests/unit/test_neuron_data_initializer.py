from unittest import TestCase

from src.data.neuron_data_initializer import (
    clean_and_reduce_labels,
    HEATMAP_GROUP_BY_ATTRIBUTES,
    NEURON_DATA_ATTRIBUTE_TYPES,
    NETWORK_GROUP_BY_ATTRIBUTES,
)


class Test(TestCase):
    def test_remove_redundant_parts(self):
        nd = {
            "nt_type": "ACH",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "right",
        }
        self.assertEqual(
            ["VLPl1"], clean_and_reduce_labels(["VLPl1; right; acetylcholine"], nd)
        )

        nd = {
            "nt_type": "GABA",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "left",
        }
        self.assertEqual(
            ["VLPl1; right; acetylcholine"],
            clean_and_reduce_labels(["VLPl1; right; acetylcholine"], nd),
        )

    def test_remove_blacklisted(self):
        nd = {
            "nt_type": "ACH",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "right",
        }
        self.assertEqual(
            ["VLPl1"], clean_and_reduce_labels(["VLPl1", "not a neuron"], nd)
        )

        self.assertEqual(
            ["VLPl1"],
            clean_and_reduce_labels(
                ["720575940611408241", "VLPl1", "not a neuron"], nd
            ),
        )

    def test_remove_corrected(self):
        nd = {
            "nt_type": "ACH",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "right",
        }
        self.assertEqual(
            ["putative LC25_R, lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "putative LC25_R, lobula columnar neuron LC25 (corrected)",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )
        self.assertEqual(
            ["post correction label", "putative LC25_R, lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "post correction label",
                    "putative LC25_R, lobula columnar neuron LC25 (corrected)",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )

        self.assertEqual(
            ["putative LC25_R, lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "putative LC25_R, lobula columnar neuron LC25 (corrected)",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )
        self.assertEqual(
            ["post correction label", "putative LC25_R, lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "post correction label",
                    "Correction: putative LC25_R, lobula columnar neuron LC25",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )

    def test_group_by_attribute_types(self):
        for k in HEATMAP_GROUP_BY_ATTRIBUTES + NETWORK_GROUP_BY_ATTRIBUTES:
            self.assertEqual(NEURON_DATA_ATTRIBUTE_TYPES[k], str)
