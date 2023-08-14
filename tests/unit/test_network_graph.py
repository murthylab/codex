from unittest import TestCase
from codex.utils.graph_vis import Network


class Test(TestCase):
    def test_clusters(self):
        net = Network(show_edge_weights=True)
        net.add_node(
            "center",
            1,
            1,
            "center",
            "dot",
            "#00ff00",
            cluster_inputs=True,
            cluster_outputs=True,
        )
        net.add_node(
            "inputs",
            1,
            1,
            "inputs",
            "dot",
            "#00ff00",
            cluster_inputs=True,
            cluster_outputs=False,
        )
        net.add_node("input1", 1, 1, "input1", "dot", "#00ff00")
        net.add_node(
            "outputs",
            1,
            1,
            "outputs",
            "dot",
            "#00ff00",
            cluster_inputs=False,
            cluster_outputs=True,
        )
        net.add_node("output1", 1, 1, "output1", "dot", "#00ff00")
        net.add_node("between", 1, 1, "between", "dot", "#00ff00")
        net.add_edge("inputs", "center", False, "", "")
        net.add_edge("center", "outputs", False, "", "")
        net.add_edge("input1", "inputs", True, "", "")
        net.add_edge("between", "inputs", True, "", "")
        net.add_edge("outputs", "output1", True, "", "")
        net.add_edge("outputs", "between", True, "", "")

        self.assertEqual(len(net.cluster_data["center"]["edges"]), 2)
        self.assertEqual(net.cluster_data["center"]["nodes"], ["inputs", "outputs"])
        self.assertEqual(net.active_edges["center"], 2)

        self.assertEqual(len(net.cluster_data["inputs"]["edges"]), 2)
        self.assertEqual(net.cluster_data["inputs"]["nodes"], ["input1", "between"])
        self.assertEqual(net.active_edges["inputs"], 3)

        self.assertEqual(len(net.cluster_data["outputs"]["edges"]), 2)
        self.assertEqual(net.cluster_data["outputs"]["nodes"], ["output1", "between"])
        self.assertEqual(net.active_edges["outputs"], 3)

        self.assertNotIn("between", net.cluster_data)
        self.assertEqual(net.active_edges["between"], 2)

        self.assertNotIn("input1", net.cluster_data)
        self.assertEqual(net.active_edges["input1"], 1)

        self.assertNotIn("output1", net.cluster_data)
        self.assertEqual(net.active_edges["output1"], 1)
