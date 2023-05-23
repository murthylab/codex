from unittest import TestCase

from src.data.brain_regions import REGIONS
from src.data.optic_lobe_cell_types import (
    COLUMNAR_CELL_TYPE_OUTPUT_NEUROPIL_FILTERS,
    COLUMNAR_CELL_TYPE_GROUPS,
)


class Test(TestCase):
    def test_neuropil_filters(self):
        for k, v in COLUMNAR_CELL_TYPE_OUTPUT_NEUROPIL_FILTERS.items():
            self.assertTrue(k in COLUMNAR_CELL_TYPE_GROUPS)
            self.assertTrue(v)
            for pil in v:
                self.assertTrue(pil in REGIONS)

    def test_group_contents(self):
        type_names = set()
        for k, v in COLUMNAR_CELL_TYPE_GROUPS.items():
            for tn in v:
                tn = tn.lower()
                self.assertTrue(tn not in type_names)
                type_names.add(tn)
