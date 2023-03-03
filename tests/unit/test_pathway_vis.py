from unittest import TestCase
from src.utils.pathway_vis import sort_connections


class Test(TestCase):
    def test_sort_connections(self):

        levels = {1: 0, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 2, 9: 3}
        connections = [
            (1, 2, 10),
            (1, 3, 5),
            (1, 4, 1),
            (2, 5, 1),
            (2, 6, 10),
            (3, 6, 1),
            (4, 7, 1),
            (4, 8, 5),
            (5, 9, 5),
            (6, 9, 1),
            (7, 9, 10),
            (8, 9, 1),
        ]

        connections = sort_connections(levels, connections)

        self.assertEqual(
            connections,
            [
                (1, 2, 10),
                (1, 4, 1),
                (1, 3, 5),
                (2, 5, 1),
                (2, 6, 10),
                (4, 7, 1),
                (4, 8, 5),
                (3, 6, 1),
                (5, 9, 5),
                (6, 9, 1),
                (7, 9, 10),
                (8, 9, 1),
            ],
        )
