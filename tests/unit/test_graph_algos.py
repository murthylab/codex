from unittest import TestCase

from src.utils.graph_algos import pathways, reachable_node_counts
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
                    "1 hop": "7 (0%)",
                    "2 hops": "5,856 (4%)",
                    "3 hops": "22,613 (18%)",
                    "4 hops": "69,399 (55%)",
                    "5 hops": "107,902 (86%)",
                    "6 hops": "120,186 (96%)",
                    "7 hops": "120,699 (96%)",
                    "8 hops": "120,725 (96%)",
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
                720575940608288523: 2,
                720575940609744733: 2,
                720575940613416744: 2,
                720575940615970783: 1,
                720575940617572609: 2,
                720575940618009318: 2,
                720575940618490782: 2,
                720575940618755638: 2,
                720575940619209408: 2,
                720575940620034932: 2,
                720575940620851695: 3,
                720575940624193255: 2,
                720575940625095864: 3,
                720575940625242882: 2,
                720575940626783507: 1,
                720575940626872932: 3,
                720575940627201929: 2,
                720575940627598852: 2,
                720575940629385594: 2,
                720575940629548800: 1,
                720575940630435831: 3,
                720575940632375379: 2,
                720575940632621988: 2,
                720575940634594411: 1,
                720575940634753983: 2,
                720575940635232180: 2,
                720575940635542452: 2,
                720575940640754304: 2,
                720575940645745262: 3,
            },
            dict(pathways(s, t, isets, osets)),
        )

        s = all_rids[200]
        t = all_rids[201]
        self.assertEqual(
            {
                720575940603452384: 0,
                720575940603453286: 5,
                720575940603825120: 1,
                720575940608526089: 1,
                720575940615391638: 1,
                720575940615802674: 1,
                720575940619481803: 3,
                720575940619633787: 3,
                720575940625117130: 1,
                720575940628858306: 2,
                720575940635119723: 2,
                720575940638128474: 3,
                720575940641159157: 4,
                720575940641464309: 2,
            },
            dict(pathways(s, t, isets, osets)),
        )

        s = all_rids[400]
        t = all_rids[401]
        self.assertEqual(
            {
                720575940603918769: 0,
                720575940603919537: 3,
                720575940624314468: 1,
                720575940626228329: 1,
                720575940628443127: 2,
            },
            dict(pathways(s, t, isets, osets)),
        )
