from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import TESTING_DATA_SNAPSHOT_VERSION
from src.utils.pathway_vis import sort_layers, pathway_chart_data_rows
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

    def test_sort_layers(self):

        layers = {1: 0, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 2, 9: 3}
        connections = [
            (1, 2, 10),
            (1, 3, 5),
            (1, 4, 1),
            (2, 5, 1),
            (2, 6, 10),
            (3, 7, 1),
            (3, 8, 5),
            (4, 6, 1),
            (5, 9, 5),
            (6, 9, 1),
            (7, 9, 10),
            (8, 9, 1),
        ]

        sort_layers(layers, connections)

        self.assertEqual(
            layers,
            {
                1: (0, 0),
                2: (1, 0),
                3: (1, 2),
                4: (1, 1),
                5: (2, 0),
                6: (2, 1),
                7: (2, 2),
                8: (2, 3),
                9: (3, 0),
            },
        )

    def test_pathway_chart_data_rows(self):
        for min_syn in [1, 5, 10]:
            pathway_nodes, data_rows = pathway_chart_data_rows(
                source=720575940621982413,
                target=720575940647030324,
                neuron_db=self.neuron_db,
                min_syn_count=min_syn,
            )
            for r in data_rows:
                self.assertTrue(r[2] >= min_syn, r)
