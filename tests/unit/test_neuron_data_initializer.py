from unittest import TestCase

from src.data.neuron_data_initializer import remove_redundant_parts


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
            "VLPl1", remove_redundant_parts("VLPl1; right; acetylcholine", nd)
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
            "VLPl1; right; acetylcholine",
            remove_redundant_parts("VLPl1; right; acetylcholine", nd),
        )
