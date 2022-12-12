from unittest import TestCase

from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.graph_algos import pathways, reachable_node_counts
from tests import TEST_DATA_ROOT_PATH


class TestGraphAlgos(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = NeuronDataFactory(data_root_path=TEST_DATA_ROOT_PATH).get()

    def test_reachable_node_counts(self):
        num_cells = len(self.neuron_db.neuron_data)
        isets = self.neuron_db.input_sets()
        for n in sorted(self.neuron_db.neuron_data.keys())[1000:1001]:
            self.assertEqual(
                {
                    "1 hop": "16 (0%)",
                    "2 hops": "853 (0%)",
                    "3 hops": "12,229 (11%)",
                    "4 hops": "66,772 (64%)",
                    "5 hops": "97,299 (93%)",
                    "6 hops": "98,922 (95%)",
                    "7 hops": "98,982 (95%)",
                    "8 hops": "98,983 (95%)",
                },
                reachable_node_counts({n}, isets, num_cells),
            )

    def test_pathways(self):
        s = t = 0
        isets = self.neuron_db.input_sets()
        osets = self.neuron_db.output_sets()

        self.assertEqual(None, pathways(s, t, isets, osets))

        s = 720575940615460364
        t = 720575940621787661

        self.assertEqual(None, pathways(s, s, isets, osets))
        self.assertEqual(
            {
                720575940605294764: 3,
                720575940608062985: 2,
                720575940613335779: 3,
                720575940615460364: 0,
                720575940615669058: 3,
                720575940616689781: 2,
                720575940618868417: 4,
                720575940620582168: 1,
                720575940620649051: 4,
                720575940620900113: 4,
                720575940621428513: 2,
                720575940621445808: 1,
                720575940621787661: 6,
                720575940623590663: 4,
                720575940625487949: 3,
                720575940627163464: 3,
                720575940629010448: 4,
                720575940632373535: 3,
                720575940633551004: 2,
                720575940633728156: 5,
                720575940635440120: 4,
                720575940636859504: 5,
                720575940639480654: 4,
                720575940639482685: 5,
                720575940646559540: 4,
                720575940647361668: 4,
            },
            pathways(s, t, isets, osets),
        )

        s = 720575940624711216
        t = 720575940624552974
        self.assertEqual(
            {
                720575940604954289: 3,
                720575940608491356: 5,
                720575940608621835: 2,
                720575940611997297: 5,
                720575940613179363: 5,
                720575940613221585: 3,
                720575940614474407: 2,
                720575940614623634: 5,
                720575940616070598: 4,
                720575940618886710: 3,
                720575940619318321: 3,
                720575940619498968: 3,
                720575940619807397: 1,
                720575940620231407: 5,
                720575940620257671: 5,
                720575940622343036: 5,
                720575940624552974: 6,
                720575940624711216: 0,
                720575940626339130: 3,
                720575940628620879: 2,
                720575940629640439: 4,
                720575940630199084: 4,
                720575940634433632: 3,
                720575940634585952: 4,
                720575940635119723: 2,
                720575940636069487: 3,
                720575940639789475: 3,
            },
            pathways(s, t, isets, osets),
        )

        s = 720575940608491356
        t = 720575940626339130

        # lots of paths
        self.assertEqual(6, len(pathways(s, t, isets, osets)))

        t = 720575940634585952

        # single hop
        self.assertEqual(
            {
                720575940605360230: 2,
                720575940605833248: 2,
                720575940606888393: 4,
                720575940608491356: 0,
                720575940609225685: 3,
                720575940610646392: 4,
                720575940610692142: 1,
                720575940611217358: 2,
                720575940611223665: 2,
                720575940611718642: 3,
                720575940612030957: 4,
                720575940612272554: 3,
                720575940612331798: 3,
                720575940613432803: 3,
                720575940613657342: 4,
                720575940613787303: 3,
                720575940615171122: 3,
                720575940615476166: 1,
                720575940615723314: 4,
                720575940616169845: 3,
                720575940616240571: 4,
                720575940616434260: 3,
                720575940616452025: 3,
                720575940616928651: 2,
                720575940617335453: 3,
                720575940617403550: 3,
                720575940617741339: 2,
                720575940618440517: 2,
                720575940618757534: 3,
                720575940619072566: 4,
                720575940619134936: 3,
                720575940619475416: 3,
                720575940619625837: 4,
                720575940619832667: 3,
                720575940619967435: 2,
                720575940620298223: 2,
                720575940620311467: 3,
                720575940620386725: 2,
                720575940620588826: 3,
                720575940620902313: 3,
                720575940620941921: 4,
                720575940620965185: 3,
                720575940621025396: 3,
                720575940621311670: 3,
                720575940621729770: 4,
                720575940621876092: 2,
                720575940622539817: 3,
                720575940622554248: 1,
                720575940622712004: 4,
                720575940623243402: 4,
                720575940623276168: 4,
                720575940623440678: 2,
                720575940623564617: 4,
                720575940623948012: 2,
                720575940623984108: 3,
                720575940624163303: 4,
                720575940624224807: 3,
                720575940624293961: 3,
                720575940624868196: 3,
                720575940625414288: 3,
                720575940625494093: 1,
                720575940625803824: 4,
                720575940625903356: 3,
                720575940626179197: 4,
                720575940626326334: 2,
                720575940626661660: 3,
                720575940626711427: 3,
                720575940626779011: 3,
                720575940626949894: 2,
                720575940627044358: 3,
                720575940627102280: 4,
                720575940627336553: 3,
                720575940627583144: 3,
                720575940627700136: 3,
                720575940628063996: 2,
                720575940628182095: 3,
                720575940628613223: 4,
                720575940628672811: 4,
                720575940628810139: 3,
                720575940628906599: 3,
                720575940629757036: 4,
                720575940629780858: 4,
                720575940629846775: 2,
                720575940629881964: 3,
                720575940630006521: 4,
                720575940630755858: 4,
                720575940631698340: 4,
                720575940631785064: 4,
                720575940631965364: 3,
                720575940632616078: 3,
                720575940633013355: 3,
                720575940634027188: 3,
                720575940634500856: 3,
                720575940634585952: 5,
                720575940635496366: 2,
                720575940635588788: 1,
                720575940636004215: 3,
                720575940636600944: 2,
                720575940636711566: 2,
                720575940638786118: 1,
                720575940642604596: 3,
                720575940643084488: 3,
                720575940643467886: 4,
                720575940645372270: 2,
            },
            pathways(s, t, isets, osets),
        )
