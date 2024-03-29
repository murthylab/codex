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
                    "1 hop": "7 (0%)",
                    "2 hops": "562 (0%)",
                    "3 hops": "16,175 (12%)",
                    "4 hops": "73,050 (57%)",
                    "5 hops": "115,822 (90%)",
                    "6 hops": "120,940 (94%)",
                    "7 hops": "121,097 (94%)",
                    "8 hops": "121,127 (94%)",
                    "9 hops": "121,128 (94%)",
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
                720575940602893228: 0,
                720575940602914988: 4,
                720575940606332629: 2,
                720575940607188036: 2,
                720575940609927141: 3,
                720575940610638434: 2,
                720575940611384306: 3,
                720575940613954194: 1,
                720575940616611382: 3,
                720575940616809401: 2,
                720575940617505629: 1,
                720575940618524481: 2,
                720575940619405812: 2,
                720575940620980323: 2,
                720575940621308341: 3,
                720575940622123981: 3,
                720575940622579967: 3,
                720575940623776491: 3,
                720575940624872179: 2,
                720575940625989904: 3,
                720575940627410944: 2,
                720575940627439592: 2,
                720575940629204674: 2,
                720575940631693354: 3,
                720575940641359776: 3,
                720575940643270692: 1,
            },
            dict(pathways(s, t, isets, osets)),
        )

        s = all_rids[200]
        t = all_rids[201]
        self.assertEqual(
            {
                720575940603409632: 0,
                720575940603430112: 6,
                720575940606776009: 4,
                720575940611160930: 3,
                720575940620321670: 4,
                720575940623387786: 3,
                720575940625518736: 2,
                720575940628050950: 2,
                720575940630939855: 4,
                720575940638128474: 5,
                720575940643576224: 1,
            },
            dict(pathways(s, t, isets, osets)),
        )

        s = all_rids[400]
        t = all_rids[401]
        self.assertEqual(
            {
                720575940603094700: 4,
                720575940603893280: 0,
                720575940603895584: 5,
                720575940605824945: 3,
                720575940606042144: 1,
                720575940607621059: 4,
                720575940608180949: 3,
                720575940610263665: 4,
                720575940610602410: 4,
                720575940610974577: 3,
                720575940616695947: 3,
                720575940617314939: 4,
                720575940618804603: 3,
                720575940619103142: 4,
                720575940619310641: 3,
                720575940622252493: 4,
                720575940622991252: 4,
                720575940623496035: 2,
                720575940624822680: 4,
                720575940625486910: 3,
                720575940626291998: 4,
                720575940627761162: 3,
                720575940628070460: 4,
                720575940628093895: 4,
                720575940628319400: 3,
                720575940630013143: 4,
                720575940630348140: 4,
                720575940631043139: 2,
                720575940631264849: 4,
                720575940632742099: 3,
                720575940633171916: 2,
                720575940636455280: 3,
                720575940639209461: 4,
                720575940641679245: 3,
                720575940650254582: 4,
            },
            dict(pathways(s, t, isets, osets)),
        )
