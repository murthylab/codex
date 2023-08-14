from collections import defaultdict
from unittest import TestCase
from codex.data.catalog import _CODEX_DATA_SCHEMA


class CatalogTest(TestCase):
    def test_column_intersections(self):
        col_counts = defaultdict(int)
        for cols in _CODEX_DATA_SCHEMA.values():
            for c in cols:
                col_counts[c] += 1
        for k, v in col_counts.items():
            if (
                k == "root_id"
            ):  # apart from connections file and LR matching file, all should contain a root_id col as key
                self.assertEqual(len(_CODEX_DATA_SCHEMA) - 2, v)
            elif k in ["nt_type", "position", "supervoxel_id"]:
                self.assertEqual(2, v)
            else:
                self.assertEqual(1, v, k)
