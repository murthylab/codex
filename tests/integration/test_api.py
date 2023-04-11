import os
from unittest import TestCase

from src.blueprints.api import (
    DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS,
    DOWNLOADABLE_FILE_SIZES,
    DOWNLOADABLE_FILE_CONTENTS,
    DOWNLOADABLE_FILE_EXTENSION,
)
from src.data.local_data_loader import read_csv
from src.data.versions import DATA_SNAPSHOT_VERSIONS
from src.utils.formatting import display
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    def test_downloadable_products_descriptions(self):
        products = list(DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS.values())
        for i, p1 in enumerate(products):
            for p2 in products[i + 1 :]:
                for j in range(len(p1)):
                    self.assertNotEqual(p1[j], p2[j])

    def test_file_sizes(self):
        actual_file_sizes = {}
        for v in DATA_SNAPSHOT_VERSIONS:
            actual_file_sizes[v] = {}
            for p, desc in DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS.items():
                fname = f"{p}{DOWNLOADABLE_FILE_EXTENSION}"
                fpath = f"{TEST_DATA_ROOT_PATH}/{v}/{fname}"
                if os.path.isfile(fpath):
                    actual_file_sizes[v][
                        fname
                    ] = f"{display(os.path.getsize(fpath))} bytes"
        self.assertEqual(DOWNLOADABLE_FILE_SIZES, actual_file_sizes)

    def test_file_contents(self):
        self.maxDiff = None

        def extract_contents(fpath):
            rows = read_csv(fpath)

            def infer_int_or_float(val_set):
                types_set = set()
                for val in val_set:
                    self.assertTrue(val)
                    try:
                        if str(int(val)) == val:
                            types_set.add("int")
                            continue
                    except ValueError:
                        pass
                    try:
                        if str(float(val)) == val:
                            types_set.add("float")
                            continue
                    except ValueError:
                        pass

                    # not int/float, return none
                    return None

                if "float" in types_set:
                    return "float"
                elif "int" in types_set:
                    return "int"
                else:
                    self.fail(f"Unexpected types: {types_set=} {val_set=}")

            def col_stats(col_idx):
                nonempty_val_list = [r[col_idx] for r in rows[1:] if r[col_idx]]
                if not nonempty_val_list:
                    return "all empty"
                nonempty_val_set = set(nonempty_val_list)
                missing_count = len(rows) - (len(nonempty_val_list) + 1)
                iof = infer_int_or_float(nonempty_val_set)

                if missing_count == 0 and len(nonempty_val_list) == len(
                    nonempty_val_set
                ):
                    col_attrs = "all rows contain unique values"
                    if iof:
                        col_attrs += f" of type {iof}"
                else:
                    col_attrs = f"{display(len(nonempty_val_set))} unique values"
                    if iof:
                        col_attrs += f" of type {iof}"
                    if missing_count:
                        col_attrs += f" in {display(len(nonempty_val_list))} rows"
                        col_attrs += (
                            f", empty in remaining {display(missing_count)} rows"
                        )

                return col_attrs

            res = {
                "# rows": f"{display(len(rows) - 1)} (+ header)",
                "# columns": display(len(rows[0])),
            }
            if len(rows[0]) < 50:
                res.update(
                    {
                        f"column  {i + 1}: {col}": col_stats(i)
                        for i, col in enumerate(rows[0])
                    }
                )

            return res

        for v in DATA_SNAPSHOT_VERSIONS:
            actual_file_contents = {}
            for p, desc in DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS.items():
                fname = f"{p}{DOWNLOADABLE_FILE_EXTENSION}"
                fpath = f"{TEST_DATA_ROOT_PATH}/{v}/{fname}"
                if os.path.isfile(fpath):
                    actual_file_contents[fname] = extract_contents(fpath)
            self.assertEqual(
                str(DOWNLOADABLE_FILE_CONTENTS[v]),
                str(actual_file_contents),
                f"Mismatch for {v=}",
            )
