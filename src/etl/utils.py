import os.path
import shutil


import pandas
from caveclient import CAVEclient

from src.data.local_data_loader import read_csv, write_csv

# FlyWire data snapshots are exported periodically in 2 Google Drive folders (within them snapshot sub-folders are
# named by internal version, e.g. 630.):
# Raw synapse table with neuro-transmitter types are here:
# https://drive.google.com/drive/folders/1B1_-yLi-ED7U8af8OJHhCHr8STq3bf1H
#  - look for file named something like 'neuron_proof_analysis_ntavg_630.feather' (assuming version 630)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as NEURON_NT_TYPES_FILE_NAME below
# Get token from here: https://global.daf-apis.com/auth/api/v1/create_token
# and store it in this file (no quotes)
from src.utils.formatting import (
    UNDEFINED_THINGS,
)

CAVE_AUTH_TOKEN_FILE_NAME = "static/secrets/cave_auth_token.txt"
CAVE_DATASTACK_NAME = "flywire_fafb_production"


def raw_data_folder(version):
    return f"static/raw_data/{version}"


def raw_data_file_path(version, filename):
    return f"{raw_data_folder(version)}/{filename}"


def compiled_data_folder(version):
    return f"static/data/{version}"


def compiled_data_file_path(version, filename):
    return f"{compiled_data_folder(version)}/{filename}"


PROOFREAD_ROOT_IDS_FILE_NAME = "proofread_root_ids.npy"
NEURONS_WITH_NT_TYPES_FILE_NAME = "neuron_nt_types.feather"
NEURON_NT_TYPE_PREDICTIONS_COLUMN_NAMES = [
    "root_id",
    "ach_avg",
    "gaba_avg",
    "glut_avg",
    "ser_avg",
    "oct_avg",
    "da_avg",
]
SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME = "synapse_table_with_nt_types.feather"
SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES = [
    "pre_pt_root_id",
    "post_pt_root_id",
    "neuropil",
    "syn_count",
    "gaba_avg",
    "ach_avg",
    "glut_avg",
    "oct_avg",
    "ser_avg",
    "da_avg",
]

NBLAST_SCORES_FILE_NAME = "nblast_scores_thresholded.feather"

NA_STR = ""
NA_INT = 0


def load_feather_data_to_table(filepath):
    df_data = pandas.read_feather(filepath)
    columns = df_data.columns.to_list()
    df_column_indices = [columns.index(c) + 1 for c in columns]
    print(f"Reading {len(columns)} columns from {len(df_data)} rows: {columns[:25]}")

    rows = [columns]
    rows_scanned = 0
    for row in df_data.itertuples():
        rows_scanned += 1
        rows.append([row[idx] for idx in df_column_indices])
        if rows_scanned % 1000000 == 0:
            print(f"Rows scanned: {rows_scanned}")
    print(f"Rows scanned: {rows_scanned}")
    return rows


def comp_backup_and_update_csv(fpath, content):
    if os.path.isfile(fpath):
        old_content = read_csv(fpath)
        print(f"Comparing {fpath} content with new")
        diff_rows = compare_csvs(old_content, content)
        fpath_bkp = fpath.replace(".csv.gz", "_bkp.csv.gz")
        print(f"Backing up {fpath} to {fpath_bkp}..")
        shutil.copy2(fpath, fpath_bkp)
        if diff_rows:
            print(f"Diff rows {diff_rows}, old content summary:")
            summarize_csv(old_content)
    else:
        print(f"Previous file {fpath} not found.")
    print("New content summary:")
    summarize_csv(content)
    print(f"Writing to {fpath}..")
    write_csv(filename=fpath, rows=content, compress=True)


def init_cave_client():
    with open(CAVE_AUTH_TOKEN_FILE_NAME) as fn:
        auth_token = str(fn.readline()).strip()
        if not auth_token:
            print("!! Missing cave token. See comment for how to obtain it.")
            exit(1)
    return CAVEclient(CAVE_DATASTACK_NAME, auth_token=auth_token)


def val_counts(table):
    unique_counts = {}
    missing_counts = {}
    undefined_counts = {}
    types = {}
    bounds = {}
    for i, c in enumerate(table[0]):
        uvals = list(set([r[i] for r in table[1:] if len(r) > i and r[i]]))
        unique_counts[c] = (len(uvals), uvals if len(uvals) < 20 else "")
        missing_counts[c] = len([r for r in table[1:] if len(r) <= i or not r[i]])
        undefined_counts[c] = len(
            [
                r[i]
                for r in table[1:]
                if len(r) > i and str(r[i]).lower() in UNDEFINED_THINGS
            ]
        )
        types[c] = ", ".join(
            list(set([str(type(r[i])).split("'")[1] for r in table[1:] if len(r) > i]))
        )
        try:
            if not c.endswith("_id"):
                bounds[c] = (
                    min([float(r[i]) for r in table[1:] if len(r) > i]),
                    max([float(r[i]) for r in table[1:] if len(r) > i]),
                )
        except Exception:
            pass

    return unique_counts, missing_counts, undefined_counts, types, bounds


def summarize_csv(content):
    uniq_counts, miss_counts, undefined_counts, types, bounds = val_counts(content)
    for c in content[0]:
        col_text = f"    {c}:"
        col_text += f" unique {uniq_counts[c][0]} {uniq_counts[c][1]}"
        if miss_counts.get(c):
            col_text += f"; missing {miss_counts[c]}"
        if undefined_counts.get(c):
            col_text += f"; undefined {undefined_counts[c]}"
        col_text += f"; types {types[c]}"
        if bounds.get(c):
            col_text += f"; bounds {bounds[c]}"
        print(col_text)


def compare_csvs(old_table, new_table, print_diffs=3, first_cols=999):
    def prntdiffs(diff_rows):
        for i, r in enumerate(diff_rows):
            if i >= print_diffs:
                print(
                    f"Reached limit, skipping {len(diff_rows) - print_diffs} of the remaining diffs"
                )
                break
            print(f"   {r}")

    hdr = old_table[0]
    if hdr != new_table[0]:
        print(f"Uncomparable tables:\n{hdr}\n{new_table[0]}")
        return

    old_row_set = set(
        [
            ",".join([str(d).replace(",", ";") for d in r[:first_cols]])
            for r in old_table
        ]
    )
    new_row_set = set(
        [
            ",".join([str(d).replace(",", ";") for d in r[:first_cols]])
            for r in new_table
        ]
    )

    on_dfset = old_row_set - new_row_set
    print(f"Rows in old but not new: {len(on_dfset)}")
    if on_dfset:
        if print_diffs:
            prntdiffs(on_dfset)

    no_dfset = new_row_set - old_row_set
    print(f"Rows in new but not old: {len(no_dfset)}")
    if no_dfset:
        if print_diffs:
            prntdiffs(no_dfset)

    return len(on_dfset) + len(no_dfset)


def remove_columns(version, columns_to_remove, filename):
    fpath = compiled_data_file_path(version=version, filename=filename)
    content = read_csv(fpath)
    columns_to_remove = {
        i: c for i, c in enumerate(content[0]) if c in columns_to_remove
    }
    if columns_to_remove:
        print(f"Removing columns {list(columns_to_remove.values())} from {fpath}")

        def project(row):
            return [val for i, val in enumerate(row) if i not in columns_to_remove]

        content = [project(r) for r in content]
        comp_backup_and_update_csv(fpath=fpath, content=content)
    else:
        print(f"None of the columns {columns_to_remove} found in {fpath}.")


def add_header(version, filename, header):
    fpath = compiled_data_file_path(version=version, filename=filename)
    print(f"Adding header {header} to {fpath}..")
    if not os.path.isfile(fpath):
        print(f"File not found: {fpath}")
        return
    content = read_csv(fpath)
    if len(content[0]) != len(header):
        print(f"Length mismatch: {header} vs {content[0]} in {fpath}. Aborting.")
        return
    if content[0] == header:
        print(f"Header {header} already present in {fpath}. Aborting.")
        return
    comp_backup_and_update_csv(fpath=fpath, content=[header] + content)
    print("Done.")


def compare_with_backup(version, resource):
    print(f"Comparing {resource} against backup, {version=}..")
    fpath = compiled_data_file_path(version=version, filename=f"{resource}.csv.gz")
    fpath_bkp = compiled_data_file_path(
        version=version, filename=f"{resource}_bkp.csv.gz"
    )

    new_content = read_csv(fpath)
    old_content = read_csv(fpath_bkp)
    compare_csvs(old_content, new_content, print_diffs=10)


def inspect_feather(version, fname):
    fpath = raw_data_file_path(version=version, filename=fname)
    if not os.path.isfile(fpath):
        print(f"File {fpath} does not exit.")
        return

    print(f"Loading feather file from {fpath}")
    content = load_feather_data_to_table(fpath)
    summarize_csv(content)
    print(f"Sample:\n{content[1]}\n{content[2]}")
