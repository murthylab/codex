from unittest import TestCase

from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.graph_algos import pathways
from tests import TEST_DATA_ROOT_PATH


class TestGraphAlgos(TestCase):
    def test_pathways(self):
        neuronDB = NeuronDataFactory(data_root_path=TEST_DATA_ROOT_PATH).get()
        s = t = 0
        isets = neuronDB.adjacencies["input_sets"]
        osets = neuronDB.adjacencies["output_sets"]
        self.assertEqual(None, pathways(s, t, isets, osets))

        s = 720575940615460364
        t = 720575940621787661

        self.assertEqual(None, pathways(s, s, isets, osets))
        self.assertEqual(
            {
                720575940605809794: 3,
                720575940615460364: 0,
                720575940617296541: 4,
                720575940618868417: 5,
                720575940620280929: 5,
                720575940620582168: 1,
                720575940621787661: 7,
                720575940622287752: 5,
                720575940623283383: 3,
                720575940624091431: 4,
                720575940625906716: 3,
                720575940626939398: 5,
                720575940628481691: 4,
                720575940629800645: 2,
                720575940633551004: 2,
                720575940633728156: 6,
                720575940636028046: 2,
            },
            pathways(s, t, isets, osets),
        )

        s = 720575940624711216
        t = 720575940624552974
        self.assertEqual(
            {
                720575940603893984: 2,
                720575940604954289: 3,
                720575940607981065: 5,
                720575940613221585: 3,
                720575940617265477: 4,
                720575940617431074: 5,
                720575940617948480: 3,
                720575940618910293: 4,
                720575940619169365: 2,
                720575940619807397: 1,
                720575940621720541: 3,
                720575940621733708: 3,
                720575940622523272: 4,
                720575940622745641: 5,
                720575940624552974: 6,
                720575940624711216: 0,
                720575940626187651: 2,
                720575940626339130: 3,
                720575940630433879: 3,
                720575940639007549: 3,
            },
            pathways(s, t, isets, osets),
        )
