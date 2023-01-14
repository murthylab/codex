from unittest import TestCase

from src.service.search import page_size_options, pagination_data


class TestSearch(TestCase):
    def test_page_size_options(self):
        self.assertEqual([20], page_size_options(0))
        self.assertEqual([20], page_size_options(1))
        self.assertEqual([20], page_size_options(20))
        self.assertEqual([20, 50], page_size_options(21))
        self.assertEqual([20, 50], page_size_options(50))
        self.assertEqual([20, 50, 100], page_size_options(51))
        self.assertEqual([20, 50, 100], page_size_options(5001))

    def test_pagination_data(self):
        self.assertEqual(
            ([], [1, 2, 3], [20]),
            pagination_data(items_list=[1, 2, 3], page_number=1, page_size=20),
        )
        self.assertEqual(
            (
                [
                    {"label": 1, "number": 1, "status": "active"},
                    {"label": 2, "number": 2, "status": ""},
                    {"label": 3, "number": 3, "status": ""},
                    {"label": 4, "number": 4, "status": ""},
                    {"label": 5, "number": 5, "status": ""},
                ],
                range(20),
                [20, 50, 100],
            ),
            pagination_data(items_list=range(100), page_number=1, page_size=20),
        )
        self.assertEqual(
            (
                [
                    {"label": 1, "number": 1, "status": ""},
                    {"label": 2, "number": 2, "status": "active"},
                    {"label": 3, "number": 3, "status": ""},
                    {"label": 4, "number": 4, "status": ""},
                    {"label": 5, "number": 5, "status": ""},
                ],
                range(20, 40),
                [20, 50, 100],
            ),
            pagination_data(items_list=range(100), page_number=2, page_size=20),
        )
        self.assertEqual(
            (
                [
                    {"label": "1 ..", "number": 1, "status": ""},
                    {"label": 17, "number": 17, "status": ""},
                    {"label": 18, "number": 18, "status": ""},
                    {"label": 19, "number": 19, "status": ""},
                    {"label": 20, "number": 20, "status": "active"},
                    {"label": 21, "number": 21, "status": ""},
                    {"label": 22, "number": 22, "status": ""},
                    {"label": 23, "number": 23, "status": ""},
                    {"label": ".. 50", "number": 50, "status": ""},
                ],
                range(380, 400),
                [20, 50, 100],
            ),
            pagination_data(items_list=range(1000), page_number=20, page_size=20),
        )
        self.assertEqual(
            (
                [
                    {"label": "1 ..", "number": 1, "status": ""},
                    {"label": 13, "number": 13, "status": ""},
                    {"label": 14, "number": 14, "status": ""},
                    {"label": 15, "number": 15, "status": ""},
                    {"label": 16, "number": 16, "status": "active"},
                    {"label": 17, "number": 17, "status": ""},
                    {"label": 18, "number": 18, "status": ""},
                    {"label": 19, "number": 19, "status": ""},
                    {"label": 20, "number": 20, "status": ""},
                ],
                range(750, 800),
                [20, 50, 100],
            ),
            pagination_data(items_list=range(1000), page_number=16, page_size=50),
        )
