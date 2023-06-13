import json
from unittest import TestCase

from src.data.download_catalog import (
    DOWNLOADABLE_FILE_SIZES,
    DOWNLOADABLE_FILE_CONTENTS,
)
from src.configuration import (
    DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS,
)
from src.data.versions import DATA_SNAPSHOT_VERSIONS
from src.etl.update_download_catalog import fetch_file_sizes, fetch_file_contents
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    def test_downloadable_products_descriptions(self):
        products = list(DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.values())
        for i, p1 in enumerate(products):
            for p2 in products[i + 1 :]:
                self.assertNotEqual(p1, p2)

    def test_file_sizes(self):
        actual_file_sizes = fetch_file_sizes(data_root_path=TEST_DATA_ROOT_PATH)
        self.assertEqual(DOWNLOADABLE_FILE_SIZES, actual_file_sizes)

    def test_file_contents(self):
        self.maxDiff = None
        actual_file_contents = fetch_file_contents(data_root_path=TEST_DATA_ROOT_PATH)
        for v in DATA_SNAPSHOT_VERSIONS:
            self.assertEqual(
                DOWNLOADABLE_FILE_CONTENTS[v],
                actual_file_contents[v],
                f"Mismatch for {v=}: \n{json.dumps(actual_file_contents, indent=2)}",
            )
