import json
import os

from src.configuration import (
    DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS,
    DOWNLOADABLE_FILE_EXTENSION,
    DOWNLOADABLE_FILES_METADATA_FILE,
)
from src.data.local_data_loader import DATA_ROOT_PATH, read_csv
from src.data.versions import DATA_SNAPSHOT_VERSIONS
from src.utils.formatting import display


def fetch_file_sizes(data_root_path=DATA_ROOT_PATH):
    file_sizes = {}
    for v in DATA_SNAPSHOT_VERSIONS:
        file_sizes[v] = {}
        for p, desc in DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.items():
            fname = f"{p}{DOWNLOADABLE_FILE_EXTENSION}"
            fpath = f"{data_root_path}/{v}/{fname}"
            if os.path.isfile(fpath):
                file_sizes[v][fname] = os.path.getsize(fpath)
    return file_sizes


def fetch_file_contents(data_root_path=DATA_ROOT_PATH):
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
    for v in DATA_SNAPSHOT_VERSIONS:
        file_contents[v] = {}
        for p, desc in DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS.items():
            fname = f"{p}{DOWNLOADABLE_FILE_EXTENSION}"
            fpath = f"{data_root_path}/{v}/{fname}"
            if os.path.isfile(fpath):
                file_contents[v][fname] = extract_contents(fpath)
    return file_contents


def update_catalog():

    metadata = {
        "file_sizes": fetch_file_sizes(),
        "file_contents": fetch_file_contents(),
    }
    with open(DOWNLOADABLE_FILES_METADATA_FILE, mode="w") as f:
        json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    update_catalog()
