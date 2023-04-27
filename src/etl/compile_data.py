import os.path
import shutil

import numpy as np

import pandas
from caveclient import CAVEclient
from networkx import Graph, community

from src.configuration import MIN_SYN_THRESHOLD
from src.data.local_data_loader import read_csv, write_csv

# FlyWire data snapshots are exported periodically in 2 Google Drive folders (within them snapshot sub-folders are
# named by internal version, e.g. 630.):
# Raw synapse table with neuro-transmitter types are here:
# https://drive.google.com/drive/folders/1B1_-yLi-ED7U8af8OJHhCHr8STq3bf1H
#  - look for file named something like 'neuron_proof_analysis_ntavg_630.feather' (assuming version 630)
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
from src.utils.formatting import can_be_flywire_root_id

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
    print(f"Loaded {len(df_data)} rows")

    columns = df_data.columns.to_list()
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
            print("!! Missing cave token. See comment for how to obtain it.")
            exit(1)
    return CAVEclient(CAVE_DATASTACK_NAME, auth_token=auth_token)


def load_neuron_info_from_cave(client, version, write_user_infos_table=False):
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

    if write_user_infos_table:
        print("Writing user infos table...")
        user_infos_table = [["id", "name", "affiliation"]]
        for u in user_infos:
            user_infos_table.append([u["id"], u["name"], u["pi"]])
        write_csv("user_infos.csv", rows=user_infos_table)

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
        uvals = list(set([r[i] for r in table[1:] if len(r) > i and r[i]]))
        unique_counts[c] = (len(uvals), uvals if len(uvals) < 20 else "")
        missing_counts[c] = len([r for r in table[1:] if len(r) <= i or not r[i]])
        undefined_counts[c] = len(
            [
                r[i]
                for r in table[1:]
                if len(r) > i
                and str(r[i]).lower()
                in ["na", "none", "undefined", "unspecified", "unknown"]
            ]
        )
        types[c] = list(set([type(r[i]) for r in table[1:] if len(r) > i]))
        try:
            bounds[c] = (
                min([r[i] for r in table[1:] if len(r) > i]),
                max([r[i] for r in table[1:] if len(r) > i]),
            )
        except Exception:
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
    if dfset:
        if summarize_diffs:
            summarize(hdr, dfset)
        if print_diffs:
            prntdiffs(dfset)

    dfset = new_row_set - old_row_set
    print(f"Rows in new but not old: {len(dfset)}")
    if dfset:
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


def update_neuron_classification_table_file(version):
    dirpath = raw_data_file_path(version=version, filename="meta")
    files = os.listdir(dirpath)
    print(f"Loading metadata files from {dirpath}: {files}")

    classification_table = [
        [
            "root_id",
            "flow",
            "super_class",
            "class",
            "sub_class",
            "cell_type",
            "hemibrain_type",
            "hemilineage",
            "side",
            "nerve",
        ]
    ]

    super_class_dict = {}
    class_dict = {}
    sub_class_dict = {}
    cell_type_dict = {}
    hemibrain_type = {}
    hemilineage = {}
    flow_dict = {}
    nerve_dict = {}
    side_dict = {}
    all_root_ids = set()

    for f in files:
        if not f.endswith(".feather"):
            print(f"Skipping unknown file: {f}")
            continue
        print(f"Processing file: {f}..")
        fpath = os.path.join(dirpath, f)
        f_content = load_feather_data_to_table(fpath)

        def load(dct, tbl, rid_col, val_col):
            for r in tbl[1:]:
                assert r[rid_col] not in dct
                dct[r[rid_col]] = r[val_col]
                all_root_ids.add(r[rid_col])

        if f == "coarse_cell_classes.feather":
            assert f_content[0] == ["root_id", "class"]
            load(
                dct=class_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("class"),
            )
        elif f == "coarse_anno.feather":
            if int(version) < 571:
                expected_columns = ["root_id", "flow", "super_class", "cell_class"]
            else:
                expected_columns = [
                    "root_id",
                    "flow",
                    "super_class",
                    "cell_class",
                    "cell_sub_class",
                    "cell_type",
                ]
            assert all([col in f_content[0] for col in expected_columns])
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
                dct=class_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("cell_class"),
            )
            if int(version) >= 571:
                load(
                    dct=sub_class_dict,
                    tbl=f_content,
                    rid_col=f_content[0].index("root_id"),
                    val_col=f_content[0].index("cell_sub_class"),
                )
                load(
                    dct=cell_type_dict,
                    tbl=f_content,
                    rid_col=f_content[0].index("root_id"),
                    val_col=f_content[0].index("cell_type"),
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
        elif f == "hemilineage_anno.feather":
            assert all(
                [col in f_content[0] for col in ["root_id", "ito_lee_hemilineage"]]
            )
            load(
                dct=hemilineage,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("ito_lee_hemilineage"),
            )
        elif f == "hemibrain_anno.feather":
            assert all([col in f_content[0] for col in ["root_id", "hemibrain_type"]])
            load(
                dct=hemibrain_type,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("hemibrain_type"),
            )
        else:
            print(f"!! Skipping unknown file: {f} !!")

        print(f"Done processing {f}")

    for rid in all_root_ids:
        classification_table.append(
            [
                rid,
                flow_dict.get(rid, NA_STR),
                super_class_dict.get(rid),
                class_dict.get(rid),
                sub_class_dict.get(rid),
                cell_type_dict.get(rid),
                hemibrain_type.get(rid),
                hemilineage.get(rid),
                side_dict.get(rid, NA_STR),
                nerve_dict.get(rid, NA_STR),
            ]
        )

    neurons_fpath = compiled_data_file_path(
        version=version, filename="classification.csv.gz"
    )
    comp_backup_and_update_csv(fpath=neurons_fpath, content=classification_table)


def update_cell_stats_table_file(version):
    # Produces these columns:
    stats_table = [
        [
            "root_id",
            "length_nm",
            "area_nm",
            "size_nm",
        ]
    ]

    fpath = raw_data_file_path(version=version, filename="meta/cell_stats.feather")
    if not os.path.isfile(fpath):
        print(f"File {fpath} not found. Skipping.")
        return

    print(f"Loading cell stats from {fpath}...")
    f_content = load_feather_data_to_table(fpath)
    print(f"Loaded {len(f_content)} rows from {fpath}")

    length_dict = {}
    area_dict = {}
    size_dict = {}
    all_root_ids = set()

    def load(dct, tbl, rid_col, val_col):
        for r in tbl[1:]:
            assert r[rid_col] not in dct
            dct[r[rid_col]] = r[val_col]
            all_root_ids.add(r[rid_col])

    # older than 571:
    if int(version) < 571:
        size_cols = ["area_nm2", "size_nm3", "path_length_nm"]
    else:
        size_cols = ["area", "volume", "path_length"]
    assert all([col in f_content[0] for col in ["root_id"] + size_cols])
    load(
        dct=area_dict,
        tbl=f_content,
        rid_col=f_content[0].index("root_id"),
        val_col=f_content[0].index(size_cols[0]),
    )
    load(
        dct=size_dict,
        tbl=f_content,
        rid_col=f_content[0].index("root_id"),
        val_col=f_content[0].index(size_cols[1]),
    )
    load(
        dct=length_dict,
        tbl=f_content,
        rid_col=f_content[0].index("root_id"),
        val_col=f_content[0].index(size_cols[2]),
    )

    print(f"Done processing {fpath}")

    for rid in all_root_ids:
        stats_table.append(
            [
                rid,
                round(float(length_dict.get(rid, NA_INT))),
                round(float(area_dict.get(rid, NA_INT))),
                round(float(size_dict.get(rid, NA_INT))),
            ]
        )

    compiled_stats_file_fpath = compiled_data_file_path(
        version=version, filename="cell_stats.csv.gz"
    )
    comp_backup_and_update_csv(fpath=compiled_stats_file_fpath, content=stats_table)


def update_connectome_files(version):
    proofread_rids_filepath = raw_data_file_path(
        version=version, filename=f"{PROOFREAD_ROOT_IDS_FILE_NAME}"
    )
    print(f"Loading proofread rids from {proofread_rids_filepath}..")
    proofread_rids_set = set(np.load(proofread_rids_filepath))
    assert all([can_be_flywire_root_id(rid) for rid in proofread_rids_set])
    print(f"Loaded {len(proofread_rids_set)} rows")

    neurons_with_nt_filepath = raw_data_file_path(
        version=version, filename=f"{NEURONS_WITH_NT_TYPES_FILE_NAME}"
    )
    print(f"Loading neurons table from {neurons_with_nt_filepath}..")
    neuron_nt_content = load_feather_data_to_table(neurons_with_nt_filepath)
    assert all(
        [c in neuron_nt_content[0] for c in NEURON_NT_TYPE_PREDICTIONS_COLUMN_NAMES]
    )
    print(f"Loaded {len(neuron_nt_content)} rows")

    syn_table_with_nt_filepath = raw_data_file_path(
        version=version, filename=f"{SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME}"
    )
    print(f"Loading synapse table from {syn_table_with_nt_filepath}")
    st_nt_content = load_feather_data_to_table(syn_table_with_nt_filepath)
    print(f"Loaded {len(st_nt_content)} rows")

    n_rid_set = set([r[0] for r in neuron_nt_content[1:]])
    st_rid_set = set([r[0] for r in st_nt_content[1:]]) | set(
        [r[1] for r in st_nt_content[1:]]
    )
    print(
        f"Proofread root IDs vs Neuron NT root IDs: {len(proofread_rids_set)} : {len(n_rid_set)} (intersection: {len(proofread_rids_set.intersection(n_rid_set))})"
    )
    print(
        f"Proofread root IDs vs Synapse Table root IDs: {len(proofread_rids_set)} : {len(st_rid_set)} (intersection: {len(proofread_rids_set.intersection(st_rid_set))})"
    )
    print(
        f"Neuron NT root IDs vs Synapse Table root IDs: {len(n_rid_set)} : {len(st_rid_set)} (intersection: {len(n_rid_set.intersection(st_rid_set))})"
    )

    filtered_rows = filter_connection_rows(
        syn_table_content=st_nt_content,
        columns=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
        min_syn_count=MIN_SYN_THRESHOLD,
        proofread_rids=proofread_rids_set,
    )

    # compile neuron rows
    neurons = compile_neuron_rows(
        proofread_rids_set=proofread_rids_set,
        neuron_nt_type_predictions_content=neuron_nt_content,
        syn_table_content=filtered_rows,
        syn_table_columns=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
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
    columns = df_data.columns.to_list()
    print(f"Loaded {len(df_data)} rows with columns: {columns}")

    scores_dict = {}
    rows_scanned = 0
    for row in df_data.itertuples():
        rows_scanned += 1
        from_root_id = row[1]
        to_root_id = row[2]
        score = row[3]
        if from_root_id == to_root_id:
            assert score == 1.0
            continue
        assert score < 1
        if score < 0.4:
            continue
        if from_root_id not in scores_dict:
            scores_dict[from_root_id] = {}
        elif to_root_id in scores_dict[from_root_id]:
            print(
                f"Warning: more than one rows for {from_root_id} {to_root_id}. Ignoring."
            )
            continue
        simple_score = int(str(score)[2])
        assert 1 <= simple_score <= 9
        scores_dict[from_root_id][to_root_id] = simple_score
        reverse_score = scores_dict.get(to_root_id, {}).get(from_root_id)
        if reverse_score is not None:
            assert reverse_score == simple_score

        if rows_scanned % 1000 == 0 or rows_scanned == len(df_data):
            print(f"Rows scanned: {rows_scanned}, score dict len: {len(scores_dict)}")

    scores_table = [["root_id", "scores"]]
    scores_table.extend(
        [
            [rid, ";".join([f"{k}:{v}" for k, v in scores.items()])]
            for rid, scores in scores_dict.items()
        ]
    )
    print(f"Sample rows: {scores_table[:5]}")
    nblast_fpath = compiled_data_file_path(version=version, filename="nblast.csv.gz")
    comp_backup_and_update_csv(fpath=nblast_fpath, content=scores_table)
    # group cells into morphology clusters based on similarity matches
    generate_morphology_cluster_groups(scores_dict, version)


def generate_morphology_cluster_groups(scores_dict, version):
    score_threshold = 4
    G = Graph()
    for rid, scores in scores_dict.items():
        G.add_node(rid)
        for m, s in scores.items():
            if s >= score_threshold and m > rid:
                G.add_node(m)
                G.add_edge(rid, m, weight=s)

    communities_generator = community.louvain_communities(G, resolution=200)
    clusters_dict = {}
    component_id = 0
    max_xluster_size = 0
    for s in sorted(communities_generator, key=lambda x: -len(x)):
        if len(s) > 1:
            max_xluster_size = max(max_xluster_size, len(s))
            component_id += 1
            cluster_name = f"C{component_id}.{len(s)}"
            for rid in s:
                clusters_dict[rid] = cluster_name

    print(
        f"Total clustered rids: {len(clusters_dict)}, {max_xluster_size=}, # clusters: {component_id}"
    )
    clusters_table = [["root_id", "cluster"]]
    for rid, cl in clusters_dict.items():
        clusters_table.append([rid, cl])

    clusters_fpath = compiled_data_file_path(
        version=version, filename="morphology_clusters.csv.gz"
    )
    comp_backup_and_update_csv(fpath=clusters_fpath, content=clusters_table)


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
        "update_classification": False,
        "update_cell_stats": False,
        "update_coordinates": False,
        "update_nblast_scores": False,
        "update_labels": True,
    }

    cave_client = init_cave_client()
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
        if config["update_classification"]:
            update_neuron_classification_table_file(version=v)
        if config["update_cell_stats"]:
            update_cell_stats_table_file(version=v)
        if config["update_coordinates"]:
            update_cave_data_file(
                name="coordinates",
                db_load_func=load_proofreading_info_from_cave,
                cave_client=cave_client,
                version=v,
            )
        if config["update_labels"]:
            update_cave_data_file(
                name="labels",
                db_load_func=load_neuron_info_from_cave,
                cave_client=cave_client,
                version=v,
            )
        if config["update_nblast_scores"]:
            process_nblast_file(version=v)
