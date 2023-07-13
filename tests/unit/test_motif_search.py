from unittest import TestCase

from src.service.motif_search import MotifSearchQuery, EdgeConstraints
from tests import TEST_NEURON_DATA_FACTORY


class TestMotifSearchQuery(TestCase):
    def test_add_node(self):
        msq = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
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
        msq = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "")
        msq.add_node("b", "")
        msq.add_node("c", "")

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "d", None)
        self.assertEqual(
            "Node(s) a and d need to be added first", str(context.exception)
        )

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "a", None)
        self.assertEqual("Self loops not allowed", str(context.exception))

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "b", ["foo"])
        self.assertEqual("Unknown region foo", str(context.exception))

        msq.add_edge("a", "b", None)

        with self.assertRaises(ValueError) as context:
            msq.add_edge("a", "b", None)
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
        neuron_db = TEST_NEURON_DATA_FACTORY.get()
        edge_constraints = [
            EdgeConstraints(regions=["GNG"], min_synapse_count=6, nt_type=None),
            EdgeConstraints(regions=["LAL_L"], min_synapse_count=10, nt_type="ACH"),
        ]
        cset1 = set(neuron_db.search("putative && side == left"))
        cset2 = set(neuron_db.search("putative && side == right"))
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
        msq_id = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq_id.add_node("a", "id == 720575940624743404")
        res_id = msq_id.search()
        self.assertEqual(
            [
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940624743404", "name": "MB_ML_R.MB_ML_R.62"}
                    },
                }
            ],
            res_id,
        )

        msq_many = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq_many.add_node("a", "fru")
        limit = 5
        res_many = msq_many.search(limit=limit)
        self.assertEqual(limit, len(res_many))
        self.assertEqual(
            [
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940627410944", "name": "AMMC_R.AMMC_R.33"}
                    },
                },
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940629327872", "name": "LO_L.AOTU_L.127"}
                    },
                },
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940628023296", "name": "AOTU_L.AOTU_L.144"}
                    },
                },
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940628471811", "name": "SLP_R.SLP_R.539"}
                    },
                },
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940625829892", "name": "AOTU_R.SIP_R.4"}
                    },
                },
            ],
            res_many,
        )

    def test_search_size_2(self):
        limit = 3

        msq_a = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq_a.add_node("a", "dsx")
        res_a = msq_a.search(limit=limit)
        self.assertEqual(limit, len(res_a))
        self.assertTrue(all([len(d["nodes"]) == 1 for d in res_a]))
        self.assertTrue(all([len(d["edges"]) == 0 for d in res_a]))

        msq_b = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq_b.add_node("b", "rr")
        res_b = msq_b.search(limit=limit)
        self.assertEqual(limit, len(res_b))
        self.assertTrue(all([len(d["nodes"]) == 1 for d in res_a]))
        self.assertTrue(all([len(d["edges"]) == 0 for d in res_a]))

        msq_ab = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq_ab.add_node("a", "dsx")
        msq_ab.add_node("b", "rr")
        msq_ab.add_edge("a", "b")
        res_ab = msq_ab.search(limit=limit)
        self.assertEqual(limit, len(res_ab))
        self.assertEqual(
            [
                {
                    "edges": [
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "SMP_L",
                            "syn_count": 19,
                            "to": "b",
                        }
                    ],
                    "nodes": {
                        "a": {"id": "720575940613871046", "name": "SMP_L.FLA_R.3"},
                        "b": {"id": "720575940622839786", "name": "SMP_L.FLA_L.17"},
                    },
                },
                {
                    "edges": [
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "SMP_L",
                            "syn_count": 7,
                            "to": "b",
                        }
                    ],
                    "nodes": {
                        "a": {"id": "720575940617779029", "name": "SMP_L.FLA_R.6"},
                        "b": {"id": "720575940622839786", "name": "SMP_L.FLA_L.17"},
                    },
                },
                {
                    "edges": [
                        {
                            "from": "a",
                            "nt_type": "ACH",
                            "region": "SMP_L",
                            "syn_count": 5,
                            "to": "b",
                        }
                    ],
                    "nodes": {
                        "a": {"id": "720575940612808086", "name": "SMP_L.SMP_L.128"},
                        "b": {"id": "720575940622839786", "name": "SMP_L.FLA_L.17"},
                    },
                },
            ],
            res_ab,
        )

    def test_search_pair_multiple_edges(self):
        msq = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "id == 720575940636612709")
        msq.add_node("b", "id == 720575940627154569")
        msq.add_edge("a", "b")
        res = msq.search()
        self.assertEqual(1, len(res))
        self.assertGreater(len(res[0]["edges"]), 5)
        msq.add_edge("b", "a")
        res = msq.search()
        self.assertEqual(0, len(res))

    def test_search_size_3(self):
        limit = 10

        msq = MotifSearchQuery(TEST_NEURON_DATA_FACTORY)
        msq.add_node("a", "id == 720575940631845004")
        msq.add_node("b", "id == 720575940622397133")
        msq.add_node("c", "id == 720575940607667723")
        msq.add_edge("a", "b")
        msq.add_edge("b", "c")
        msq.add_edge("c", "a")
        res = msq.search(limit=limit)
        self.assertEqual(
            [
                {
                    "edges": [],
                    "nodes": {
                        "a": {"id": "720575940631845004", "name": "CRE_R.IB_R.3"},
                        "b": {"id": "720575940622397133", "name": "CRE_R.LAL_R.13"},
                        "c": {"id": "720575940607667723", "name": "LAL_R.CRE_R.3"},
                    },
                }
            ],
            res,
        )

        # TODO: write a proper test
