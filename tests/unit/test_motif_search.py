from unittest import TestCase

from codex.service.motif_search import MotifSearchQuery, EdgeConstraints
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
            "Invalid query '1 == 2 == 3': " in str(context.exception),
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
