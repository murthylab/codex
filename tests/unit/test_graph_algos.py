from unittest import TestCase

from codex.utils.graph_algos import pathways, reachable_node_counts
from tests import get_testing_neuron_db


class TestGraphAlgos(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def test_reachable_node_counts(self):
        num_cells = len(self.neuron_db.neuron_data)
        isets = self.neuron_db.input_sets()
        for n in sorted(self.neuron_db.neuron_data.keys())[1000:1001]:
            self.assertEqual(
                {
                    "1 hop": "12 (0%)",
                    "2 hops": "5,261 (3%)",
                    "3 hops": "23,733 (17%)",
                    "4 hops": "77,092 (55%)",
                    "5 hops": "118,010 (84%)",
                    "6 hops": "127,454 (91%)",
                    "7 hops": "127,815 (91%)",
                    "8 hops": "127,837 (91%)",
                },
                reachable_node_counts({n}, isets, num_cells),
            )

    def test_pathways(self):
        s = t = 0
        isets = self.neuron_db.input_sets()
        osets = self.neuron_db.output_sets()
        all_rids = sorted(self.neuron_db.neuron_data.keys())

        self.assertEqual(None, pathways(s, t, isets, osets))

        s = all_rids[100]
        t = all_rids[101]

        self.assertEqual(None, pathways(s, s, isets, osets))
        self.assertEqual(
            {
                720575940602928608: 0,
                720575940602943968: 4,
                720575940603526005: 2,
                720575940604636789: 2,
                720575940605413129: 2,
                720575940607902682: 2,
                720575940608187778: 3,
                720575940608288523: 2,
                720575940609744733: 2,
                720575940612276578: 3,
                720575940613416744: 2,
                720575940617572609: 2,
                720575940618009318: 2,
                720575940618490782: 2,
                720575940618755638: 2,
                720575940619209408: 2,
                720575940620034932: 2,
                720575940620851695: 3,
                720575940624193255: 2,
                720575940625242882: 2,
                720575940626783507: 1,
                720575940626872932: 3,
                720575940626979621: 1,
                720575940627201929: 2,
                720575940627598852: 2,
                720575940628259594: 2,
                720575940629385594: 2,
                720575940629548800: 1,
                720575940632375379: 2,
                720575940632621988: 2,
                720575940634594411: 1,
                720575940634612194: 2,
                720575940634753983: 2,
                720575940635232180: 2,
                720575940635542452: 2,
                720575940644255904: 3,
                720575940645745262: 3,
            },
            dict(pathways(s, t, isets, osets)),
        )

        s = all_rids[400]
        t = all_rids[401]
        self.assertEqual(
            {
                720575940603942828: 0,
                720575940603942846: 4,
                720575940605607392: 1,
                720575940612149362: 1,
                720575940613560994: 3,
                720575940620320902: 1,
                720575940622462612: 1,
                720575940624615462: 1,
                720575940624923655: 2,
                720575940625967546: 3,
                720575940628350567: 1,
                720575940628694019: 2,
                720575940629437545: 2,
                720575940634874266: 2,
                720575940635967886: 1,
                720575940638910040: 1,
                720575940641706184: 2,
            },
            dict(pathways(s, t, isets, osets)),
        )
