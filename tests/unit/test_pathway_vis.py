from unittest import TestCase
from src.utils.pathway_vis import sort_layers


class Test(TestCase):
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
