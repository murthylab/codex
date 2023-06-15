import json
from unittest import TestCase

from src.data.download_catalog import (
    DOWNLOADABLE_FILE_SIZES,
    DOWNLOADABLE_FILE_CONTENTS,
)
from src.configuration import (
    DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS,
)
from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION
from src.etl.update_download_catalog import fetch_file_sizes, fetch_file_contents
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    def test_downloadable_products_descriptions_and_contents(self):
        products = list(DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.values())
        for i, p1 in enumerate(products):
            for p2 in products[i + 1 :]:
                self.assertNotEqual(p1, p2)

        self.assertEqual(
            sorted(DATA_SNAPSHOT_VERSIONS), sorted(DOWNLOADABLE_FILE_CONTENTS.keys())
        )
        files_list = [
            "cell_stats.csv.gz",
            "classification.csv.gz",
            "connections.csv.gz",
            "coordinates.csv.gz",
            "labels.csv.gz",
            "morphology_clusters.csv.gz",
            "neurons.csv.gz",
            "neuropil_synapse_table.csv.gz",
        ]
        for v in DATA_SNAPSHOT_VERSIONS:
            self.assertTrue(
                set(files_list).issubset(set(DOWNLOADABLE_FILE_CONTENTS[v].keys()))
            )

    def test_file_sizes_fetching(self):
        # test full update
        actual_file_sizes = fetch_file_sizes(
            versions=DATA_SNAPSHOT_VERSIONS,
            products=DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.keys(),
            data_root_path=TEST_DATA_ROOT_PATH,
        )
        self.assertEqual(DOWNLOADABLE_FILE_SIZES, actual_file_sizes)

        # test partial update
        actual_file_sizes = fetch_file_sizes(
            versions=[DEFAULT_DATA_SNAPSHOT_VERSION],
            products=["labels"],
            data_root_path=TEST_DATA_ROOT_PATH,
        )
        for v, d1 in actual_file_sizes.items():
            for p, d2 in d1.items():
                self.assertEqual(DOWNLOADABLE_FILE_SIZES[v][p], actual_file_sizes[v][p])

    def test_file_contents_fetching(self):
        self.maxDiff = None

        # test full update
        actual_file_contents = fetch_file_contents(
            versions=DATA_SNAPSHOT_VERSIONS,
            products=DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.keys(),
            data_root_path=TEST_DATA_ROOT_PATH,
        )
        for v in DATA_SNAPSHOT_VERSIONS:
            self.assertEqual(
                DOWNLOADABLE_FILE_CONTENTS[v],
                actual_file_contents[v],
                f"Mismatch for {v=}: \n{json.dumps(actual_file_contents, indent=2)}",
            )

        # test partial update
        actual_file_contents = fetch_file_contents(
            versions=[DEFAULT_DATA_SNAPSHOT_VERSION],
            products=["labels"],
            data_root_path=TEST_DATA_ROOT_PATH,
        )
        for v, d1 in actual_file_contents.items():
            for p, d2 in d1.items():
                self.assertEqual(
                    DOWNLOADABLE_FILE_CONTENTS[v][p], actual_file_contents[v][p]
                )
