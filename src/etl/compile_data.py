import os.path
import shutil
from collections import defaultdict
import numpy as np

import pandas
from caveclient import CAVEclient

from src.configuration import MIN_SYN_COUNT
from src.data.local_data_loader import read_csv, write_csv

# FlyWire data snapshots are exported periodically in 2 Google Drive folders (within them snapshot sub-folders are
# named by internal version, e.g. 447.):
# Raw synapse table is here: https://drive.google.com/drive/folders/1g7i3LMmDFcZXDXzevy3eUSrmcMJl2B6a/
#  - look for file named something like 'syn_proof_analysis_filtered_consolidated_447.feather' (assuming version 447)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as SYNAPSE_TABLE_FILE_NAME below
# Neurotransmitter types are here: https://drive.google.com/drive/folders/1B1_-yLi-ED7U8af8OJHhCHr8STq3bf1H
#  - look for file named something like 'neuron_proof_analysis_ntavg_447.feather' (assuming version 447)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as NEURON_NT_TYPES_FILE_NAME below
# Get token from here: https://global.daf-apis.com/auth/api/v1/create_token
# and store it in this file (no quotes)
from src.data.versions import DATA_SNAPSHOT_VERSIONS

CAVE_AUTH_TOKEN_FILE_NAME = f"static/secrets/cave_auth_token.txt"
CAVE_DATASTACK_NAME = "flywire_fafb_production"


def raw_data_folder(version):
    return f"static/raw_data/{version}"


def raw_data_file_path(version, filename):
    return f"{raw_data_folder(version)}/{filename}"


def compiled_data_folder(version):
    return f"static/data/{version}"


def compiled_data_file_path(version, filename):
    return f"{compiled_data_folder(version)}/{filename}"


SYNAPSE_TABLE_FILE_NAME = "synapse_table.feather"
SYNAPSE_TABLE_COLUMN_NAMES = [
    "pre_pt_root_id",
    "post_pt_root_id",
    "neuropil",
    "syn_count",
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


def load_feather_data_to_table(filepath, columns_to_read=None):
    df_data = pandas.read_feather(filepath)
    print(f"Loaded {len(df_data)} rows")

    columns = df_data.columns.to_list()
    if columns_to_read:
        if not all([c in columns for c in columns_to_read]):
            print(
                f"Missing columns in file {filepath}. Expected {columns_to_read}, found {columns}."
            )
            exit(1)
        columns = columns_to_read
    df_column_indices = [columns.index(c) + 1 for c in columns]
    print(f"Reading columns {columns}")

    rows = [columns]
    rows_scanned = 0
    for row in df_data.itertuples():
        rows_scanned += 1
        rows.append([row[idx] for idx in df_column_indices])
        if rows_scanned % 1000000 == 0:
            print(f"Rows scanned: {rows_scanned}")
    print(f"Rows scanned: {rows_scanned}")
    return rows


def compact_nt_scores_data(version):
    nt_scores_data = load_feather_data_to_table(
        filepath=raw_data_file_path(version, SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME),
        columns_to_read=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
    )

    header = nt_scores_data[0]
    rid_to_scores = {}

    def isnan(val):
        return val != val

    for r in nt_scores_data[1:]:
        if r[0] not in rid_to_scores:
            rid_to_scores[r[0]] = defaultdict(int)
        for i in [4, 5, 6, 7, 8, 9]:
            if not isnan(r[3]) and not isnan(r[i]):
                rid_to_scores[r[0]][header[i]] += r[3] * r[i]

    def round_float(f):
        return float("{:0.2f}".format(f))

    def normalize(scores_dict):
        tot = sum(scores_dict.values())
        for k, v in scores_dict.items():
            scores_dict[k] = round_float(v / tot)

    for rid, scores in rid_to_scores.items():
        normalize(scores)

    for r in nt_scores_data[1:5]:
        print(f"{r[0]}: {rid_to_scores[r[0]]}")

    return rid_to_scores


def init_cave_client():
    with open(CAVE_AUTH_TOKEN_FILE_NAME) as fn:
        auth_token = str(fn.readline()).strip()
        if not auth_token:
            print(
                "!! Missing access token. See link in the comment for how to obtain it."
            )
            exit(1)
    return CAVEclient(CAVE_DATASTACK_NAME, auth_token=auth_token)


def load_neuron_info_from_cave(client, version):
    print("Downloading 'neuron_information_v2' with CAVE client..")
    df = client.materialize.query_table("neuron_information_v2")
    print(f"Downloaded {len(df)} rows with columns {df.columns.to_list()}")
    supervoxel_ids = df["pt_supervoxel_id"].astype(np.uint64)
    mat_timestamp = client.materialize.get_version_metadata(version)["time_stamp"]
    df["pt_root_id"] = client.chunkedgraph.get_roots(
        supervoxel_ids, timestamp=mat_timestamp
    )
    print(f"Mapped to version {version}")
    neuron_info_table = [
        ["root_id", "tag", "user_id", "position", "supervoxel_id", "tag_id"]
    ]
    user_ids = set()
    for index, d in df.iterrows():
        user_ids.add(d["user_id"])
        neuron_info_table.append(
            [
                int(d["pt_root_id"]),
                str(d["tag"]),
                int(d["user_id"]),
                str(d["pt_position"]),
                int(d["pt_supervoxel_id"]),
                int(d["id"]),
            ]
        )

    user_infos = client.auth.get_user_information(user_ids)
    user_id_to_info = {u["id"]: (u["name"], u["pi"]) for u in user_infos}
    print(
        f"Fetched user infos: {len(user_infos)}, not found: {len(user_ids - set(user_id_to_info.keys()))}"
    )
    uinfo_not_found = 0
    neuron_info_table[0].extend(["user_name", "user_affiliation"])
    for r in neuron_info_table[1:]:
        uinfo = user_id_to_info.get(r[2])
        if uinfo:
            r.extend([uinfo[0], uinfo[1]])
        else:
            r.extend(["", ""])
            uinfo_not_found += 1
    print(f"Annos without uinfo: {uinfo_not_found}")
    return neuron_info_table


def load_proofreading_info_from_cave(client, version):
    print("Downloading 'proofreading_status_public_v1' with CAVE client..")
    df = client.materialize.query_table("proofreading_status_public_v1")
    print(f"Downloaded {len(df)} rows with columns {df.columns.to_list()}")
    supervoxel_ids = df["pt_supervoxel_id"].astype(np.uint64)
    mat_timestamp = client.materialize.get_version_metadata(version)["time_stamp"]
    df["pt_root_id"] = client.chunkedgraph.get_roots(
        supervoxel_ids, timestamp=mat_timestamp
    )
    print(f"Mapped to version {version}")
    pr_info_table = [["root_id", "position", "supervoxel_id"]]
    for index, d in df.iterrows():
        pr_info_table.append(
            [int(d["pt_root_id"]), str(d["pt_position"]), int(d["pt_supervoxel_id"])]
        )
    return pr_info_table


def val_counts(table):
    unique_counts = {}
    missing_counts = {}
    for i, c in enumerate(table[0]):
        unique_counts[c] = len(set([r[i] for r in table[1:] if r[i]]))
        missing_counts[c] = len([r[i] for r in table[1:] if not r[i]])
    return unique_counts, missing_counts


def summarize_csv(content):
    print(f"- header: {content[0]}")
    uniq_counts, miss_counts = val_counts(content)
    print(f"- unique val counts: {uniq_counts}")
    print(f"- missing val counts: {miss_counts}")
    return content


def compare_csvs(old_table, new_table, first_cols=999999):
    old_row_set = set([",".join([str(d) for d in r[:first_cols]]) for r in old_table])
    new_row_set = set([",".join([str(d) for d in r[:first_cols]]) for r in new_table])
    print(f"Rows in old but not new: {len(old_row_set - new_row_set)}")
    print(f"Rows in new but not old: {len(new_row_set - old_row_set)}")


def update_cave_data_file(name, db_load_func, cave_client, version):
    print(f"Updating {name} file..")
    fpath = compiled_data_file_path(version=version, filename="{name}.csv.gz")
    backup_fpath = compiled_data_file_path(
        version=version, filename="{name}_bkp.csv.gz"
    )
    old_content = None
    if os.path.isfile(fpath):
        print(f"Reading {fpath}...")
        old_content = read_csv(fpath)
        summarize_csv(old_content)
        print(f"Copying to {backup_fpath}..")
        shutil.copy2(fpath, backup_fpath)
    else:
        print(f"Previous file {fpath} not found.")

    print(f"Loading {name} from DB..")
    new_content = db_load_func(client=cave_client, version=version)
    summarize_csv(new_content)
    if old_content:
        compare_csvs(old_content, new_content)
    print(f"Writing {name} file with {len(new_content)} lines to {fpath}")
    write_csv(fpath, rows=new_content, compress=True)


def process_classification_file(version):
    filepath = raw_data_file_path(
        version=version, filename=f"coarse_cell_classes.feather"
    )
    print(f"Loading coarse labels from {filepath}")
    new_content = load_feather_data_to_table(filepath)

    fpath = compiled_data_file_path(version=version, filename="classification.csv.gz")

    if os.path.isfile(fpath):
        old_content = read_csv(fpath)
        print("Comparing with current")
        compare_csvs(old_content, new_content)
        fpath_bkp = compiled_data_file_path(
            version=version, filename="classification_bkp.csv.gz"
        )
        print(f"Backing up {fpath} to {fpath_bkp}..")
        shutil.copy2(fpath, fpath_bkp)

    print(f"Saving {len(new_content)} coarse labels to {fpath}")
    write_csv(filename=fpath, rows=new_content, compress=True)


def process_synapse_table_file(version):
    st_filepath = raw_data_file_path(
        version=version, filename=f"{SYNAPSE_TABLE_FILE_NAME}"
    )
    st_nt_filepath = raw_data_file_path(
        version=version, filename=f"{SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME}"
    )

    print(f"Loading synapse table from {st_filepath}")
    st_new_content = load_feather_data_to_table(st_filepath)
    st_nt_new_content = load_feather_data_to_table(st_nt_filepath)

    compare_csvs(st_new_content, st_nt_new_content, first_cols=4)
    exit(1)


def remove_columns(version, columns_to_remove):
    fname = f"static/data/{version}/neuron_data.csv.gz"
    fname_bkp = f"static/data/{version}/neuron_data_bkp.csv.gz"
    content = read_csv(fname)

    columns_to_remove = {
        i: c for i, c in enumerate(content[0]) if c in columns_to_remove
    }
    if columns_to_remove:
        print(f"Backing up {fname} to {fname_bkp}..")
        shutil.copy2(fname, fname_bkp)
        print(f"Removing columns {columns_to_remove} from {fname}")

        def project(row):
            return [val for i, val in enumerate(row) if i not in columns_to_remove]

        new_content = [project(r) for r in content]
        print(f"Writing new content with cols {new_content[0]} to {fname}..")
        write_csv(fname, rows=new_content, compress=True)
        print("Done.")
    else:
        print(f"None of the columns {columns_to_remove} found in {fname}.")


if __name__ == "__main__":
    config = {
        "columns_to_remove": [],
        "update_coordinates": False,
        "update_labels": False,
        "update_classifications": False,
        "update_connections": True,
    }
    if config["columns_to_remove"]:
        for v in DATA_SNAPSHOT_VERSIONS:
            remove_columns(v, config["columns_to_remove"])

    client = init_cave_client()
    for v in DATA_SNAPSHOT_VERSIONS:
        if config["update_connections"]:
            process_synapse_table_file(version=v)
        if config["update_classifications"]:
            process_classification_file(version=v)
        if config["update_coordinates"]:
            update_cave_data_file(
                name="coordinates",
                db_load_func=load_proofreading_info_from_cave,
                cave_client=client,
                version=v,
            )
        if config["update_labels"]:
            update_cave_data_file(
                name="labels",
                db_load_func=load_neuron_info_from_cave,
                cave_client=client,
                version=v,
            )
