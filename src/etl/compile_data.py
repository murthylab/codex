import os.path
import shutil
import numpy as np

import pandas
from caveclient import CAVEclient

from src.configuration import MIN_SYN_COUNT
from src.data.local_data_loader import read_csv, write_csv

# FlyWire data snapshots are exported periodically in 2 Google Drive folders (within them snapshot sub-folders are
# named by internal version, e.g. 526.):
# Raw synapse table is here: https://drive.google.com/drive/folders/1g7i3LMmDFcZXDXzevy3eUSrmcMJl2B6a/
#  - look for file named something like 'syn_proof_analysis_filtered_consolidated_526.feather' (assuming version 526)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as SYNAPSE_TABLE_FILE_NAME below
# Neurotransmitter types are here: https://drive.google.com/drive/folders/1B1_-yLi-ED7U8af8OJHhCHr8STq3bf1H
#  - look for file named something like 'neuron_proof_analysis_ntavg_526.feather' (assuming version 526)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as NEURON_NT_TYPES_FILE_NAME below
# Get token from here: https://global.daf-apis.com/auth/api/v1/create_token
# and store it in this file (no quotes)
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.versions import DATA_SNAPSHOT_VERSIONS
from src.etl.synapse_table_processor import (
    compile_connection_rows,
    compile_neuron_rows,
    filter_connection_rows,
)

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

NBLAST_SCORES_FILE_NAME = "nblast_scores.feather"


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
    print(f"Reading {len(columns)} columns: {columns[:25]}")

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
        compare_csvs(old_content, content)
        fpath_bkp = fpath.replace(".csv.gz", "_bkp.csv.gz")
        print(f"Backing up {fpath} to {fpath_bkp}..")
        shutil.copy2(fpath, fpath_bkp)
        print("Old content summary")
        summarize_csv(old_content)
    else:
        print(f"Previous file {fpath} not found.")

    print("New content summary")
    summarize_csv(content)
    print(f"Writing to {fpath}..")
    write_csv(filename=fpath, rows=content, compress=True)


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
    types = {}
    bounds = {}
    for i, c in enumerate(table[0]):
        uvals = list(set([r[i] for r in table[1:] if r[i]]))
        unique_counts[c] = (len(uvals), uvals if len(uvals) < 20 else '')
        missing_counts[c] = len([r[i] for r in table[1:] if not r[i]])
        types[c] = list(set([type(r[i]) for r in table[1:]]))
        try:
            bounds[c] = (min([r[i] for r in table[1:]]), max([r[i] for r in table[1:]]))
        except:
            pass
    return unique_counts, missing_counts, types, bounds


def summarize_csv(content):
    print(f"- header: {content[0]}")
    uniq_counts, miss_counts, types, bounds = val_counts(content)
    print(f"- unique val counts: {uniq_counts}")
    print(f"- missing val counts: {miss_counts}")
    print(f"- data types: {types}")
    print(f"- numeral type bounds: {bounds}")
    return content


def compare_csvs(
    old_table, new_table, summarize_diffs=True, print_diffs=0, first_cols=999999
):
    def summarize(hdr, diff_rows):
        summarize_csv([hdr] + [r.split(",") for r in diff_rows])

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

    dfset = old_row_set - new_row_set
    print(f"Rows in old but not new: {len(dfset)}")
    if summarize_diffs:
        summarize(hdr, dfset)
    if print_diffs:
        prntdiffs(dfset)

    dfset = new_row_set - old_row_set
    print(f"Rows in new but not old: {len(dfset)}")
    if summarize_diffs:
        summarize(hdr, dfset)
    if print_diffs:
        prntdiffs(dfset)


def update_cave_data_file(name, db_load_func, cave_client, version):
    print(f"Updating {name} file..")
    fpath = compiled_data_file_path(version=version, filename=f"{name}.csv.gz")

    print(f"Loading {name} from DB..")
    new_content = db_load_func(client=cave_client, version=version)

    comp_backup_and_update_csv(fpath, content=new_content)


def process_classification_file(version, summarize_files=False):
    dirpath = raw_data_file_path(version=version, filename=f"classes")
    files = os.listdir(dirpath)
    print(f"Loading coarse labels from {dirpath}: {files}")

    def summarize(rows):
        res = ""
        for i, c in enumerate(rows[0]):
            if c in ["x", "y", "z", "supervoxel_id"]:
                continue
            vals = set([row[i] for row in rows[1:]])
            vals_str = str(vals) if len(vals) < 20 else ""
            res += f"{c}: {len(vals)} {vals_str}\n"
        return res

    new_content = [["root_id", "class"]]

    for f in files:
        fpath = raw_data_file_path(version=version, filename=f"classes/{f}")
        f_content = load_feather_data_to_table(fpath)
        if summarize_files:
            print(
                f"=================\n"
                f"{f}, {len(f_content)}:\n{f_content[:2]}\n{summarize(f_content)}\n"
                f"------------------"
            )
        if f == "coarse_cell_classes.feather":
            assert f_content[0] == new_content[0]
            new_content.extend(f_content[1:])
        elif f in [
            "coarse_anno_BOL_526.feather",
            "coarse_anno_endocrine_526.feather",
            "coarse_anno_sensory_526.feather",
            "coarse_anno_DN_526.feather",
            "coarse_anno_BVP_526.feather",
            "coarse_anno_VP_526.feather",
            "coarse_anno_motor_526.feather",
            "coarse_anno_VC_526.feather",
            "coarse_anno_AN_526.feather",
        ]:
            assert f_content[0] == ["x", "y", "z", "supervoxel_id", "root_id", "label"]
            new_content.extend([[r[4], r[5]] for r in f_content[1:]])
        elif f in ["coarse_anno_cb_526.feather"]:
            assert f_content[0] == ["root_id", "label", "x", "y", "z", "supervoxel_id"]
            new_content.extend([[r[0], r[1]] for r in f_content[1:]])
        elif f in ["coarse_anno_ol_526.feather"]:
            assert f_content[0] == ["root_id", "label", "x", "y", "z", "supervoxel_id"]
            new_content.extend([[r[0], "Optic Lobe"] for r in f_content[1:]])
        elif f in ["coarse_anno_nerve_type_526.feather", "coarse_anno_526.feather"]:
            print(f"Skipping {f}")
        else:
            assert f"Unknown file: {f}" is None

        print(f"Class rows after processing {f}: {len(new_content)}")

    fpath = compiled_data_file_path(version=version, filename="classification.csv.gz")
    comp_backup_and_update_csv(fpath=fpath, content=new_content)


def process_synapse_table_file(version):
    st_nt_filepath = raw_data_file_path(
        version=version, filename=f"{SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME}"
    )

    print(f"Loading synapse table from {st_nt_filepath}")
    st_nt_content = load_feather_data_to_table(st_nt_filepath)

    filtered_rows = filter_connection_rows(
        syn_table_content=st_nt_content,
        columns=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
        min_syn_count=MIN_SYN_COUNT,
    )

    # compile neuron rows
    neurons = compile_neuron_rows(
        filtered_syn_table_content=filtered_rows,
        columns=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
    )
    neurons_fpath = compiled_data_file_path(version=version, filename="neurons.csv.gz")
    comp_backup_and_update_csv(fpath=neurons_fpath, content=neurons)

    # compile connection rows
    connections = compile_connection_rows(
        filtered_syn_table_content=filtered_rows,
        columns=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
    )
    connections_fpath = compiled_data_file_path(
        version=version, filename="connections.csv.gz"
    )
    comp_backup_and_update_csv(fpath=connections_fpath, content=connections)


def process_nblast_file(version):
    nblast_raw_filepath = raw_data_file_path(
        version=version, filename=f"{NBLAST_SCORES_FILE_NAME}"
    )
    if not os.path.isfile(nblast_raw_filepath):
        print(f"No NBLAST file found in {nblast_raw_filepath}")
        return

    print(f"Loading NBLAST scores from {nblast_raw_filepath}")

    df_data = pandas.read_feather(nblast_raw_filepath)
    print(f"Loaded {len(df_data)} rows")

    columns = df_data.columns.to_list()
    df_column_index = {i: int(c.split(",")[0]) for i, c in enumerate(columns[1:])}
    print(f"Reading {len(columns)} columns: {columns[:5]}...")

    similarity_dict = {}
    rows_scanned = 0
    for row in df_data.itertuples():
        rows_scanned += 1
        if rows_scanned == 1:
            continue
        similar_list = []
        for i, score in enumerate(row[2:]):
            if i == rows_scanned - 1:
                assert score == 1.0
            elif score > 0.3:
                similar_list.append((df_column_index[i], score))
        from_root_id = int(row[1].split(",")[0])
        similarity_dict[from_root_id] = similar_list
        if rows_scanned % 1000 == 0:
            print(
                f"Rows scanned: {rows_scanned}, similar pairs: {sum([len(vals) for vals in similarity_dict.values()])}"
            )
    print(
        f"Rows scanned: {rows_scanned}, similar pairs: {sum([len(vals) for vals in similarity_dict.values()])}"
    )

    def flatten(sim_pairs):
        return ";".join([f"{p[0]}:{str(p[1])[:5]}" for p in sim_pairs])

    nblast_content = [[rid, flatten(sims)] for rid, sims in similarity_dict.items()]

    print(f"Sample rows: {nblast_content[:2]}")
    nblast_fpath = compiled_data_file_path(version=version, filename="nblast.csv.gz")
    comp_backup_and_update_csv(fpath=nblast_fpath, content=nblast_content)


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
    fpath = raw_data_file_path(
        version=version, filename=fname
    )
    if not os.path.isfile(fpath):
        print(f"File {fpath} does not exit.")
        return

    print(f"Loading feather file from {fpath}")
    content = load_feather_data_to_table(fpath)
    summarize_csv(content)
    print(f"Sample:\n{content[1]}\n{content[2]}")

if __name__ == "__main__":
    config = {
        "versions": DATA_SNAPSHOT_VERSIONS,
        "columns_to_remove": {},
        "headers_to_add": {},
        "compare_with_backup": [],
        "inspect_feather": ["cell_stats.feather", "classes/nerve_anno.feather", "classes/coarse_anno.feather", "classes/side_anno.feather"],
        "update_coordinates": False,
        "update_classifications": False,
        "update_connections": False,
        "update_nblast_scores": False,
        "update_labels": False,
    }

    client = init_cave_client()
    for v in config["versions"]:
        print(
            f"#######################\nCompiling version {v}..\n#######################"
        )
        for f in config["compare_with_backup"]:
            compare_with_backup(resource=f, version=v)
        for f in config["inspect_feather"]:
            inspect_feather(version=v, fname=f)
        if config["columns_to_remove"]:
            for fname, cols in config["columns_to_remove"].items():
                remove_columns(v, filename=fname, columns_to_remove=cols)
        if config["headers_to_add"]:
            for fname, hdr in config["headers_to_add"].items():
                add_header(v, filename=fname, header=hdr)
        if config["update_connections"]:
            process_synapse_table_file(version=v)
        if config["update_classifications"]:
            process_classification_file(version=v, summarize_files=True)
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
        if config["update_nblast_scores"]:
            process_nblast_file(version=v)
