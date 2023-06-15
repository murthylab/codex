import json
import os
import sys

from src.configuration import (
    DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS,
    DOWNLOADABLE_FILE_EXTENSION,
    DOWNLOADABLE_FILES_METADATA_FILE,
)
from src.data.local_data_loader import DATA_ROOT_PATH, read_csv
from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION
from src.utils.formatting import display


def fetch_file_sizes(versions, products, data_root_path=DATA_ROOT_PATH):
    print("fetching file sizes...")
    file_sizes = {}
    for v in versions:
        file_sizes[v] = {}
        for p in products:
            fname = f"{p}{DOWNLOADABLE_FILE_EXTENSION}"
            fpath = f"{data_root_path}/{v}/{fname}"
            if os.path.isfile(fpath):
                file_sizes[v][fname] = os.path.getsize(fpath)
    return file_sizes


def fetch_file_contents(versions, products, data_root_path=DATA_ROOT_PATH):
    print("fetching file contents...")

    def extract_contents(fpath):
        rows = read_csv(fpath)

        def infer_int_or_float(val_set):
            types_set = set()
            for val in val_set:
                assert val
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

            for tp in ["float", "int"]:  # from broadest to narrowest
                if tp in types_set:
                    return tp
            print(f"Unexpected types: {types_set=} {val_set=}")
            assert False

        def col_stats(col_idx):
            nonempty_val_list = [r[col_idx] for r in rows[1:] if r[col_idx]]
            if not nonempty_val_list:
                return "all empty"
            nonempty_val_set = set(nonempty_val_list)
            missing_count = len(rows) - (len(nonempty_val_list) + 1)
            iof = infer_int_or_float(nonempty_val_set)

            def type_and_range():
                if not iof or rows[0][col_idx].endswith("_id"):
                    return ""
                tp = eval(iof)
                assert tp in [float, int]
                typed_vals = [tp(val) for val in nonempty_val_set]
                return f" of type {iof.upper()} in range [{display(min(typed_vals))} .. {display(max(typed_vals))}]"

            if missing_count == 0 and len(nonempty_val_list) == len(nonempty_val_set):
                col_attrs = "all rows contain unique values" + type_and_range()
            else:
                col_attrs = (
                    f"{display(len(nonempty_val_set))} unique values" + type_and_range()
                )
                if missing_count:
                    col_attrs += f" in {display(len(nonempty_val_list))} rows"
                    col_attrs += f", empty in {display(missing_count)} rows"

            return col_attrs

        res = {
            "# rows": f"{display(len(rows) - 1)} (+ header)",
            "# columns": display(len(rows[0])),
        }
        if len(rows[0]) < 500:
            res.update(
                {f"col {i + 1} - {col}": col_stats(i) for i, col in enumerate(rows[0])}
            )

        return res

    file_contents = {}
    for v in versions:
        file_contents[v] = {}
        for p in products:
            fname = f"{p}{DOWNLOADABLE_FILE_EXTENSION}"
            fpath = f"{data_root_path}/{v}/{fname}"
            if os.path.isfile(fpath):
                file_contents[v][fname] = extract_contents(fpath)
    return file_contents


def update_catalog(versions, products, merge_to):
    print(
        f"Updating catalog for versions: {','.join(versions)} and products: {','.join(products)}"
    )
    fsizes = fetch_file_sizes(versions, products)
    fcontents = fetch_file_contents(versions, products)
    if merge_to:
        metadata = merge_to
        for v in versions:
            metadata["file_sizes"][v].update(fsizes[v])
            metadata["file_contents"][v].update(fcontents[v])
    else:
        metadata = {
            "file_sizes": fsizes,
            "file_contents": fcontents,
        }

    print("writing to file")
    with open(DOWNLOADABLE_FILES_METADATA_FILE, mode="w") as f:
        json.dump(metadata, f, indent=2)
    print("done.")


if __name__ == "__main__":
    versions_ = DATA_SNAPSHOT_VERSIONS
    products_ = list(DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.keys())
    merge_to_ = None
    if len(sys.argv) > 1:
        if len(sys.argv) == 2 and sys.argv[1] == "-labels_in_default_version_only":
            versions_ = [DEFAULT_DATA_SNAPSHOT_VERSION]
            products_ = ["labels"]
            with open(DOWNLOADABLE_FILES_METADATA_FILE) as f:
                merge_to_ = json.load(f)
                if not merge_to_:
                    print(
                        f"Partial update failed because existing catalog json file could not be loaded from {DOWNLOADABLE_FILES_METADATA_FILE}"
                    )
                    exit(1)
        else:
            print(f"Unrecognized args: {sys.argv[1:]}")
            exit(1)
    update_catalog(versions=versions_, products=products_, merge_to=merge_to_)
