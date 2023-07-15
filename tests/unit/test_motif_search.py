from unittest import TestCase

from src.service.motif_search import MotifSearchQuery, EdgeConstraints
from tests import _TEST_NEURON_DATA_FACTORY


class TestMotifSearchQuery(TestCase):
    def test_add_node(self):
        msq = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "")

        with self.assertRaises(ValueError) as context:
            msq.add_node("a", "")
        self.assertEqual(
            "Node name is empty or already exists: a", str(context.exception)
        )

        with self.assertRaises(ValueError) as context:
            msq.add_node("", "")
        self.assertEqual(
            "Node name is empty or already exists: ", str(context.exception)
        )

        with self.assertRaises(ValueError) as context:
            msq.add_node("b", "1 == 2 == 3")
        self.assertTrue(
            "Invalid query '1 == 2 == 3': Malformed structured search query."
            in str(context.exception),
            str(context.exception),
        )

        msq.add_node("b", "class == optic")
        msq.add_node("c", "nt_type {in} GABA, ACH")

        with self.assertRaises(ValueError) as context:
            msq.add_node("d", "")
        self.assertEqual("Max nodes limit of 3 exceeded", str(context.exception))

    def test_add_edge(self):
        msq = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "")
        msq.add_node("b", "")
        msq.add_node("c", "")

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "d", regions=None, nt_type=None, min_synapse_count=0)
        self.assertEqual(
            "Node(s) a and d need to be added first", str(context.exception)
        )

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "a", regions=None, nt_type=None, min_synapse_count=0)
        self.assertEqual("Self loops not allowed", str(context.exception))

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "b", ["foo"], nt_type=None, min_synapse_count=0)
        self.assertEqual("Unknown region foo", str(context.exception))

        msq.add_edge("a", "b", regions=None, nt_type=None, min_synapse_count=0)

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "b", regions=None, nt_type=None, min_synapse_count=0)
        self.assertEqual(
            "Edge ('a', 'b') already exists. Parallel edges not allowed.",
            str(context.exception),
        )

    def test_satisfies_edge_constraints(self):
        ec = EdgeConstraints(
            regions=["GNG", "LAL_L"], min_synapse_count=50, nt_type="ACH"
        )
        self.assertTrue(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="GNG", syn_count=90, nt_type="ACH"
            )
        )
        self.assertFalse(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="OP", syn_count=90, nt_type="ACH"
            )
        )
        self.assertFalse(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="LAL_L", syn_count=10, nt_type="ACH"
            )
        )
        self.assertFalse(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="LAL_L", syn_count=90, nt_type="GABA"
            )
        )

        ec = EdgeConstraints(regions=None, min_synapse_count=50, nt_type="ACH")
        self.assertTrue(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="OP", syn_count=90, nt_type="ACH"
            )
        )

        ec = EdgeConstraints(
            regions=["GNG", "LAL_L"], min_synapse_count=None, nt_type="ACH"
        )
        self.assertTrue(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="LAL_L", syn_count=10, nt_type="ACH"
            )
        )

        ec = EdgeConstraints(
            regions=["GNG", "LAL_L"], min_synapse_count=50, nt_type=None
        )
        self.assertTrue(
            MotifSearchQuery._satisfies_edge_constraints(
                constraints=ec, region="LAL_L", syn_count=90, nt_type="GABA"
            )
        )

    def test_fetch_feasible_connections(self):
        neuron_db = _TEST_NEURON_DATA_FACTORY.get()
        edge_constraints = [
            EdgeConstraints(regions=["GNG"], min_synapse_count=6, nt_type=None),
            EdgeConstraints(regions=["LAL_L"], min_synapse_count=10, nt_type="ACH"),
        ]
        cset1 = set(neuron_db.search("side == left"))
        cset2 = set(neuron_db.search("side == right"))
        self.assertGreater(len(cset1), 100)
        self.assertGreater(len(cset2), 100)
        self.assertEqual(0, len(cset1.intersection(cset2)))
        feasible_connections = MotifSearchQuery._fetch_feasible_connections(
            neuron_db=neuron_db,
            edge_constraints_list=edge_constraints,
            candidate_sets_list=[cset1, cset2],
        )
        self.assertGreater(len(feasible_connections), 200)
        for r in feasible_connections:
            self.assertTrue(
                r[0] in cset1 and r[1] in cset2 or r[0] in cset2 and r[1] in cset1
            )
            self.assertTrue(r[2] in ["GNG", "LAL_L"])
            self.assertTrue(r[3] >= 6)

    def test_search_size_1(self):
        msq_id = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq_id.add_node("a", "id == 720575940619600449")
        res_id = msq_id.search()
        self.assertEqual(
            [
                {
                    "edges": [],
                    "nodes": {"a": {"id": "720575940619600449", "name": "LO.PVLP.231"}},
                }
            ],
            res_id,
        )

        msq_many = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq_many.add_node("a", "fru")
        limit = 5
        res_many = msq_many.search(limit=limit)
        self.assertEqual(limit, len(res_many))
        self.assertEqual(
            [
                {
                    "edges": [],
                    "nodes": {"a": {"id": "720575940627410944", "name": "AMMC.14"}},
                },
                {
                    "edges": [],
                    "nodes": {"a": {"id": "720575940629327872", "name": "LO.AOTU.54"}},
                },
                {
                    "edges": [],
                    "nodes": {"a": {"id": "720575940628023296", "name": "AOTU.265"}},
                },
                {
                    "edges": [],
                    "nodes": {"a": {"id": "720575940628471811", "name": "SLP.1377"}},
                },
                {
                    "edges": [],
                    "nodes": {"a": {"id": "720575940625829892", "name": "AOTU.SIP.5"}},
                },
            ],
            res_many,
        )

    def test_search_size_2(self):
        limit = 3

        msq_a = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq_a.add_node("a", "dsx")
        res_a = msq_a.search(limit=limit)
        self.assertEqual(limit, len(res_a))
        self.assertTrue(all([len(d["nodes"]) == 1 for d in res_a]))
        self.assertTrue(all([len(d["edges"]) == 0 for d in res_a]))

        msq_b = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq_b.add_node("b", "rr")
        res_b = msq_b.search(limit=limit)
        self.assertEqual(limit, len(res_b))
        self.assertTrue(all([len(d["nodes"]) == 1 for d in res_a]))
        self.assertTrue(all([len(d["edges"]) == 0 for d in res_a]))

        msq_ab = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq_ab.add_node("a", "dsx")
        msq_ab.add_node("b", "rr")
        msq_ab.add_edge("a", "b", regions=None, nt_type=None, min_synapse_count=0)
        res_ab = msq_ab.search(limit=limit)
        self.assertEqual(limit, len(res_ab))
        self.assertEqual(
            [
                {
                    "edges": [
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "FLA_L",
                            "syn_count": 2,
                            "to": "b",
                        },
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "ICL_L",
                            "syn_count": 1,
                            "to": "b",
                        },
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "SMP_L",
                            "syn_count": 6,
                            "to": "b",
                        },
                    ],
                    "nodes": {
                        "a": {"id": "720575940622227197", "name": "SMP.331"},
                        "b": {"id": "720575940620440129", "name": "LAL.VES.3"},
                    },
                },
                {
                    "edges": [
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "FLA_L",
                            "syn_count": 6,
                            "to": "b",
                        },
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "VES_L",
                            "syn_count": 2,
                            "to": "b",
                        },
                    ],
                    "nodes": {
                        "a": {"id": "720575940635950426", "name": "SMP.402"},
                        "b": {"id": "720575940620440129", "name": "LAL.VES.3"},
                    },
                },
                {
                    "edges": [
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "SMP_L",
                            "syn_count": 1,
                            "to": "b",
                        },
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "SMP_R",
                            "syn_count": 21,
                            "to": "b",
                        },
                    ],
                    "nodes": {
                        "a": {"id": "720575940613871046", "name": "SMP.813"},
                        "b": {"id": "720575940622839786", "name": "SMP.FLA.5"},
                    },
                },
            ],
            res_ab,
        )

    def test_search_pair_multiple_edges(self):
        msq = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "id == 720575940636612709")
        msq.add_node("b", "id == 720575940627154569")
        msq.add_edge("a", "b", regions=None, min_synapse_count=0, nt_type=None)
        res = msq.search()
        self.assertEqual(1, len(res))
        self.assertGreater(len(res[0]["edges"]), 5)
        msq.add_edge("b", "a", regions=None, min_synapse_count=0, nt_type=None)
        res = msq.search()
        self.assertEqual(0, len(res))

    def test_search_size_3(self):
        limit = 10

        msq = MotifSearchQuery(_TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "id == 720575940620881078")
        msq.add_node("b", "id == 720575940620181077")
        msq.add_node("c", "id == 720575940626634789")
        msq.add_edge("a", "b", regions=None, min_synapse_count=0, nt_type=None)
        msq.add_edge("b", "a", regions=None, min_synapse_count=0, nt_type=None)
        msq.add_edge("b", "c", regions=None, min_synapse_count=0, nt_type=None)
        msq.add_edge("a", "c", regions=None, min_synapse_count=0, nt_type=None)
        res = msq.search(limit=limit)
        self.assertEqual(
            [
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940620881078", "name": "ME.LO.215"},
                        "b": {"id": "720575940620181077", "name": "ME.LO.3129"},
                        "c": {"id": "720575940626634789", "name": "LO.8"},
                    },
                }
            ],
            res,
        )

        # TODO: write a proper test
