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
from src.data.versions import DATA_SNAPSHOT_VERSIONS
from src.etl.synapse_table_processor import (
    compile_connection_rows,
    compile_neuron_rows,
    filter_connection_rows,
    compile_neuropil_synapse_rows,
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

NA_STR = ""
NA_INT = 0


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
        ["root_id", "label", "user_id", "position", "supervoxel_id", "label_id"]
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
    undefined_counts = {}
    types = {}
    bounds = {}
    for i, c in enumerate(table[0]):
        uvals = list(set([r[i] for r in table[1:] if r[i]]))
        unique_counts[c] = (len(uvals), uvals if len(uvals) < 20 else "")
        missing_counts[c] = len([r[i] for r in table[1:] if not r[i]])
        undefined_counts[c] = len(
            [
                r[i]
                for r in table[1:]
                if str(r[i]).lower()
                in ["na", "none", "undefined", "unspecified", "unknown"]
            ]
        )
        types[c] = list(set([type(r[i]) for r in table[1:]]))
        try:
            bounds[c] = (min([r[i] for r in table[1:]]), max([r[i] for r in table[1:]]))
        except:
            pass
    return unique_counts, missing_counts, undefined_counts, types, bounds


def summarize_csv(content):
    print(f"- header: {content[0]}")
    uniq_counts, miss_counts, undefined_counts, types, bounds = val_counts(content)
    print(f"- unique val counts: {uniq_counts}")
    print(f"- missing val counts: {miss_counts}")
    print(f"- undefined val counts: {undefined_counts}")
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


def compile_neuron_metadata_table(version, summarize_files=False):
    # Produces these columns:
    new_content = [
        [
            "root_id",
            "flow",
            "class",
            "side",
            "nerve_type",
            "length_nm",
            "area_nm",
            "size_nm",
        ]
    ]

    dirpath = raw_data_file_path(version=version, filename="meta")
    files = os.listdir(dirpath)
    print(f"Loading metadata files from {dirpath}: {files}")

    def summarize(rows):
        res = ""
        for i, c in enumerate(rows[0]):
            if c in ["x", "y", "z", "supervoxel_id"]:
                continue
            vals = set([row[i] for row in rows[1:]])
            vals_str = str(vals) if len(vals) < 20 else ""
            res += f"{c}: {len(vals)} {vals_str}\n"
        return res

    super_class_dict = {}
    cell_class_dict = {}
    flow_dict = {}
    nerve_dict = {}
    side_dict = {}
    length_dict = {}
    area_dict = {}
    size_dict = {}
    all_root_ids = set()

    for f in files:
        if not f.endswith(".feather"):
            print(f"Skipping unknown file: {f}")
            continue
        print(f"Processing file: {f}..")
        fpath = os.path.join(dirpath, f)
        f_content = load_feather_data_to_table(fpath)
        if summarize_files:
            print(
                f"=================\n"
                f"{f}, {len(f_content)}:\n{f_content[:2]}\n{summarize(f_content)}\n"
                f"------------------"
            )

        def load(dct, tbl, rid_col, val_col):
            for r in tbl[1:]:
                assert r[rid_col] not in dct
                dct[r[rid_col]] = r[val_col]
                all_root_ids.add(r[rid_col])

        if f == "coarse_cell_classes.feather":
            assert f_content[0] == ["root_id", "class"]
            load(
                dct=cell_class_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("class"),
            )
        elif f == "coarse_anno.feather":
            assert all(
                [
                    col in f_content[0]
                    for col in ["root_id", "flow", "super_class", "cell_class"]
                ]
            )
            load(
                dct=flow_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("flow"),
            )
            load(
                dct=super_class_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("super_class"),
            )
            load(
                dct=cell_class_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("cell_class"),
            )
        elif f == "nerve_anno.feather":
            assert all([col in f_content[0] for col in ["root_id", "nerve"]])
            load(
                dct=nerve_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("nerve"),
            )
        elif f == "side_anno.feather":
            assert all([col in f_content[0] for col in ["root_id", "side"]])
            load(
                dct=side_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("side"),
            )
        elif f == "cell_stats.feather":
            assert all(
                [
                    col in f_content[0]
                    for col in ["root_id", "area_nm2", "size_nm3", "path_length_nm"]
                ]
            )
            load(
                dct=area_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("area_nm2"),
            )
            load(
                dct=size_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("size_nm3"),
            )
            load(
                dct=length_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("path_length_nm"),
            )
        else:
            assert f"Unknown file: {f}" is None

        print(f"Class rows after processing {f}: {len(new_content)}")

    def make_class(sclass, cclass):
        res = sclass or NA_STR
        if cclass and not cclass.startswith("unknown"):
            res += f"/{cclass}"
        return res

    for rid in all_root_ids:
        new_content.append(
            [
                rid,
                flow_dict.get(rid, NA_STR),
                make_class(super_class_dict.get(rid), cell_class_dict.get(rid)),
                side_dict.get(rid, NA_STR),
                nerve_dict.get(rid, NA_STR),
                round(float(length_dict.get(rid, NA_INT))),
                round(float(area_dict.get(rid, NA_INT))),
                round(float(size_dict.get(rid, NA_INT))),
            ]
        )

    return new_content


def update_connectome_files(version):
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
    neuron_metadata = compile_neuron_metadata_table(version=version)
    assert [
        "root_id",
        "flow",
        "class",
        "side",
        "nerve_type",
        "length_nm",
        "area_nm",
        "size_nm",
    ] == neuron_metadata[0]
    assert len(set([r[0] for r in neuron_metadata])) == len(neuron_metadata)
    rid_to_row = {r[0]: i for i, r in enumerate(neuron_metadata)}
    meta_columns = len(neuron_metadata[0])
    for i, r in enumerate(neurons):
        meta_row_idx = rid_to_row.get(r[0])
        meta_row = (
            [NA_STR] * meta_columns
            if meta_row_idx is None
            else neuron_metadata[meta_row_idx]
        )
        r.extend(meta_row[1:])
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

    # compile neuropil synapse tables
    neuropil_synapse_table = compile_neuropil_synapse_rows(
        filtered_syn_table_content=filtered_rows,
        columns=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
    )
    neuropil_synapse_table_fpath = compiled_data_file_path(
        version=version, filename="neuropil_synapse_table.csv.gz"
    )
    comp_backup_and_update_csv(
        fpath=neuropil_synapse_table_fpath, content=neuropil_synapse_table
    )


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

    scores_dict = {}
    rows_scanned = 0
    for row in df_data.itertuples():
        rows_scanned += 1
        if rows_scanned == 1:
            continue
        similar_pairs = []
        for i, score in enumerate(row[2:]):
            if i == rows_scanned - 1:
                assert score == 1.0
            else:
                assert 0 <= score < 1
                if score >= 0.1:
                    simple_score = int(str(score)[2])
                    assert 1 <= simple_score <= 9
                    similar_pairs.append([df_column_index[i], simple_score])
        from_root_id = int(row[1].split(",")[0])
        if from_root_id in scores_dict:
            print(f"Warning: more than one rows for {from_root_id}. Ignoring.")
        else:
            scores_dict[from_root_id] = similar_pairs
        if rows_scanned % 1000 == 0 or rows_scanned == len(df_data):
            print(f"Rows scanned: {rows_scanned}, score dict len: {len(scores_dict)}")

    scores_table = ["root_id", "scores"]
    scores_table.extend(
        [
            [rid, ";".join([f"{p[0]}:{p[1]}" for p in score_pairs])]
            for rid, score_pairs in scores_dict.items()
        ]
    )
    print(f"Sample rows: {scores_table[:5]}")
    nblast_fpath = compiled_data_file_path(version=version, filename="nblast.csv.gz")
    comp_backup_and_update_csv(fpath=nblast_fpath, content=scores_table)


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


if __name__ == "__main__":
    config = {
        "versions": DATA_SNAPSHOT_VERSIONS,
        # UTILS
        "columns_to_remove": {},
        "headers_to_add": {},
        "compare_with_backup": [],
        "inspect_feather": [],
        # INGEST
        "update_connectome": False,
        "update_coordinates": False,
        "update_nblast_scores": False,
        "update_labels": True,
    }

    client = init_cave_client()
    for v in config["versions"]:
        print(
            f"#######################\nCompiling version {v}..\n#######################"
        )

        # Utils
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

        # Ingest
        if config["update_connectome"]:
            update_connectome_files(version=v)
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
