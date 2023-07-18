import datetime
import os.path
import sys
from collections import defaultdict

import numpy as np

import pandas
from networkx import Graph, community

from src.configuration import MIN_SYN_THRESHOLD
from src.data.local_data_loader import read_csv

# FlyWire data snapshots are exported periodically in 2 Google Drive folders (within them snapshot sub-folders are
# named by internal version, e.g. 630.):
# Raw synapse table with neuro-transmitter types are here:
# https://drive.google.com/drive/folders/1B1_-yLi-ED7U8af8OJHhCHr8STq3bf1H
#  - look for file named something like 'neuron_proof_analysis_ntavg_630.feather' (assuming version 630)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as NEURON_NT_TYPES_FILE_NAME below
# Get token from here: https://global.daf-apis.com/auth/api/v1/create_token
# and store it in this file (no quotes)
from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION
from src.etl.synapse_table_processor import (
    compile_connection_rows,
    compile_neuron_rows,
    filter_connection_rows,
    compile_neuropil_synapse_rows,
)
from src.etl.utils import (
    compare_with_backup,
    inspect_feather,
    remove_columns,
    add_header,
    init_cave_client,
    compiled_data_file_path,
    comp_backup_and_update_csv,
    raw_data_file_path,
    load_feather_data_to_table,
    NA_STR,
    NA_INT,
    PROOFREAD_ROOT_IDS_FILE_NAME,
    NEURONS_WITH_NT_TYPES_FILE_NAME,
    NEURON_NT_TYPE_PREDICTIONS_COLUMN_NAMES,
    SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME,
    SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
    NBLAST_SCORES_FILE_NAME,
)
from src.utils.formatting import (
    can_be_flywire_root_id,
    is_proper_textual_annotation,
)


def load_neuron_info_from_cave(client, old_content, materialization_version):
    output_table_columns = [
        "root_id",
        "label",
        "user_id",
        "position",
        "supervoxel_id",
        "label_id",
        "date_created",
        "user_name",
        "user_affiliation",
    ]

    print("Downloading 'neuron_information_v2' with CAVE client..")
    df = client.materialize.live_live_query(
        "neuron_information_v2",
        timestamp=datetime.datetime.utcnow(),
        allow_missing_lookups=True,
    )
    df_columns_list = df.columns.to_list()
    print(f"Downloaded {len(df)} rows with columns {df_columns_list}")

    if old_content:
        assert old_content[0] == output_table_columns
        label_id_col = output_table_columns.index("label_id")
        old_label_ids = set([int(r[label_id_col]) for r in old_content[1:]])
        df = df[~df["id"].isin(old_label_ids)]
        print(
            f"Old content has {len(old_label_ids)} labels, reduced data frame to {len(df)} new labels"
        )
    else:
        print("No old content, ingesting all")

    supervoxel_ids = df["pt_supervoxel_id"].astype(np.uint64)
    mat_timestamp = client.materialize.get_version_metadata(materialization_version)[
        "time_stamp"
    ]
    df["pt_root_id"] = client.chunkedgraph.get_roots(
        supervoxel_ids, timestamp=mat_timestamp
    )
    print(f"Mapped to version {materialization_version}")

    user_ids = set()
    col_idx_dict = {
        col_name: df_columns_list.index(col_name) + 1
        for col_name in [
            "pt_root_id",
            "tag",
            "user_id",
            "pt_position",
            "pt_supervoxel_id",
            "id",
            "created",
        ]
    }
    new_labels_table = []
    for d in df.itertuples():
        user_ids.add(d[col_idx_dict["user_id"]])
        new_labels_table.append(
            [
                int(d[col_idx_dict["pt_root_id"]]),
                str(d[col_idx_dict["tag"]]),
                int(d[col_idx_dict["user_id"]]),
                str(d[col_idx_dict["pt_position"]]),
                int(d[col_idx_dict["pt_supervoxel_id"]]),
                int(d[col_idx_dict["id"]]),
                str(d[col_idx_dict["created"]]).split(".")[0],
            ]
        )

    user_infos = client.auth.get_user_information(user_ids)
    user_id_to_info = {u["id"]: (u["name"], u["pi"]) for u in user_infos}
    print(
        f"Fetched user infos: {len(user_infos)}, not found: {len(user_ids - set(user_id_to_info.keys()))}"
    )

    uinfo_not_found = 0
    for r in new_labels_table:
        uinfo = user_id_to_info.get(r[2])
        if uinfo:
            r.extend([uinfo[0], uinfo[1]])
        else:
            r.extend(["", ""])
            uinfo_not_found += 1
    print(f"Annos without uinfo: {uinfo_not_found}")

    output_table = old_content if old_content else [output_table_columns]
    output_table.extend(new_labels_table)
    return output_table


def load_proofreading_info_from_cave(client, old_content, version):
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


def update_cave_data_file(name, db_load_func, client, version):
    print(f"Updating {name} file..")
    fpath = compiled_data_file_path(version=version, filename=f"{name}.csv.gz")
    old_content = read_csv(fpath) if os.path.isfile(fpath) else None

    print(f"Loading {name} from DB..")
    new_content = db_load_func(
        client=client,
        old_content=old_content,
        materialization_version=version.split("_")[0],
    )

    # project to neurons in dataset
    neurons_table = read_csv(
        compiled_data_file_path(version=version, filename="neurons.csv.gz")
    )
    root_id_col = neurons_table[0].index("root_id")
    neuron_rids_in_dataset = set([int(r[root_id_col]) for r in neurons_table[1:]])

    root_id_col = new_content[0].index("root_id")
    filtered_content = [new_content[0]] + [
        r for r in new_content[1:] if int(r[root_id_col]) in neuron_rids_in_dataset
    ]
    if len(filtered_content) < len(new_content):
        print(
            f"Filtered out {len(new_content) - len(filtered_content)} rows referring to root ids outside of the dataset"
        )

    comp_backup_and_update_csv(fpath, content=filtered_content)


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

    for f in sorted(files):
        print("----------------------------")
        if not f.endswith(".feather"):
            print(f"Skipping non feather file: {f}")
            continue
        print(f"Processing file: {f}..")
        fpath = os.path.join(dirpath, f)
        f_content = load_feather_data_to_table(fpath)

        def load(dct, tbl, rid_col, val_col):
            excluded_values = defaultdict(int)
            for r in tbl[1:]:
                assert r[rid_col] not in dct
                if r[val_col] is None:
                    continue
                if isinstance(r[val_col], str) and not is_proper_textual_annotation(
                    r[val_col]
                ):
                    excluded_values[r[val_col]] += 1
                    continue
                dct[r[rid_col]] = r[val_col]
                all_root_ids.add(r[rid_col])
            if excluded_values:
                print(f"  !! excluded non proper values {dict(excluded_values)} !!")

        if f == f"coarse_anno_{version}.feather":
            expected_columns = [
                "root_id",
                "flow",
                "super_class",
                "cell_class",
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
        elif f == f"cell_sub_class_anno_{version}.feather":
            expected_columns = [
                "root_id",
                "cell_sub_class",
            ]
            assert all([col in f_content[0] for col in expected_columns])
            load(
                dct=sub_class_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("cell_sub_class"),
            )
        elif f == f"cell_type_anno_{version}.feather":
            expected_columns = [
                "root_id",
                "cell_type",
            ]
            assert all([col in f_content[0] for col in expected_columns])
            load(
                dct=cell_type_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("cell_type"),
            )
        elif f == f"nerve_anno_{version}.feather":
            assert all([col in f_content[0] for col in ["root_id", "nerve"]])
            load(
                dct=nerve_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("nerve"),
            )
        elif f == f"side_anno_{version}.feather":
            assert all([col in f_content[0] for col in ["root_id", "side"]])
            load(
                dct=side_dict,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("side"),
            )
        elif f == f"hemilineage_anno_{version}.feather":
            assert all(
                [col in f_content[0] for col in ["root_id", "ito_lee_hemilineage"]]
            )
            load(
                dct=hemilineage,
                tbl=f_content,
                rid_col=f_content[0].index("root_id"),
                val_col=f_content[0].index("ito_lee_hemilineage"),
            )
        elif f == f"hemibrain_anno_{version}.feather":
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

    print("----------------------------")
    for rid in all_root_ids:
        classification_table.append(
            [
                rid,
                flow_dict.get(rid, NA_STR),
                super_class_dict.get(rid, NA_STR),
                class_dict.get(rid, NA_STR),
                sub_class_dict.get(rid, NA_STR),
                cell_type_dict.get(rid, NA_STR),
                hemibrain_type.get(rid, NA_STR),
                hemilineage.get(rid, NA_STR),
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

    fpath = raw_data_file_path(
        version=version, filename=f"meta/skeleton_stats_l2+skeletor_{version}.feather"
    )
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

    def isnan(vl):
        return vl != vl

    def load(dct, tbl, rid_col, val_col):
        for r in tbl[1:]:
            assert r[rid_col] not in dct
            all_root_ids.add(r[rid_col])
            if not isnan(r[val_col]):
                dct[r[rid_col]] = r[val_col]

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


def load_nblast_scores(version, score_threshold=0.4):
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
        if rows_scanned % 1000000 == 0 or rows_scanned == len(df_data):
            print(f"Rows scanned: {rows_scanned}, score dict len: {len(scores_dict)}")

        from_root_id = row[1]
        to_root_id = row[2]
        score = row[3]
        if from_root_id == to_root_id:
            assert score == 1.0
            continue
        assert score < 1
        if score < score_threshold:
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

    return scores_dict


def update_nblast_scores(version):
    scores_dict = load_nblast_scores(version)
    scores_table = [["root_id", "scores"]]
    scores_table.extend(
        [
            [rid, ";".join([f"{to_rid}:{score}" for to_rid, score in scores.items()])]
            for rid, scores in scores_dict.items()
        ]
    )
    print(f"Sample rows: {scores_table[:5]}")
    nblast_fpath = compiled_data_file_path(version=version, filename="nblast.csv.gz")
    comp_backup_and_update_csv(fpath=nblast_fpath, content=scores_table)


def update_connectivity_tags(version):
    con_tags_dict = defaultdict(set)

    # load the precomputed random-walk data
    attractor_repeller_fname = raw_data_file_path(
        version, filename=f"attractor_and_repeller_v{version}.csv"
    )
    if os.path.isfile(attractor_repeller_fname):
        attractor_repeller_table = read_csv(attractor_repeller_fname)
        assert attractor_repeller_table[0] == ["attractor", "repeller"]
        for r in attractor_repeller_table[1:]:
            con_tags_dict[int(r[0])].add("attractor")
            con_tags_dict[int(r[1])].add("repeller")

    # load the remaining connectivity tags (computed from data)
    tags_fname = raw_data_file_path(
        version, filename=f"computed_connectivity_tags_v{version}.csv.gz"
    )
    if os.path.isfile(tags_fname):
        tags_table = read_csv(tags_fname)
        assert tags_table[0] == ["root_id", "connectivity_tag"]
        print(f"Loading connectivity tags for {len(tags_table) - 1} cells")
        for r in tags_table[1:]:
            con_tags_dict[int(r[0])] |= set(r[1].split(";"))

    combined_con_tags_table = [["root_id", "connectivity_tag"]]
    for rid, tags in con_tags_dict.items():
        combined_con_tags_table.append([rid, ",".join(sorted(tags))])

    con_tags_fpath = compiled_data_file_path(
        version=version, filename="connectivity_tags.csv.gz"
    )
    comp_backup_and_update_csv(fpath=con_tags_fpath, content=combined_con_tags_table)


def update_morphology_clusters(version):
    scores_dict = load_nblast_scores(version)
    if not scores_dict:
        print(f"No scores loaded for version {version}")
        return

    print("Building score graph..")
    G = Graph()
    for rid, scores in scores_dict.items():
        G.add_node(rid)
        for m, s in scores.items():
            if m > rid:
                G.add_node(m)
                G.add_edge(rid, m, weight=s)

    print("Running community analysis..")
    communities_generator = community.louvain_communities(G, resolution=200)
    clusters_dict = {}
    component_id = 0
    max_xluster_size = 0
    for s in sorted(communities_generator, key=lambda x: -len(x)):
        if len(s) > 1:
            max_xluster_size = max(max_xluster_size, len(s))
            component_id += 1
            cluster_name = f"MC_{component_id}.{len(s)}"
            for rid in s:
                clusters_dict[rid] = cluster_name

    print(
        f"Total clustered rids: {len(clusters_dict)}, {max_xluster_size=}, # clusters: {component_id}"
    )
    clusters_table = [["root_id", "morphology_cluster"]]
    for rid, cl in clusters_dict.items():
        clusters_table.append([rid, cl])

    clusters_fpath = compiled_data_file_path(
        version=version, filename="morphology_clusters.csv.gz"
    )
    comp_backup_and_update_csv(fpath=clusters_fpath, content=clusters_table)


if __name__ == "__main__":
    versions_ = DATA_SNAPSHOT_VERSIONS
    if len(sys.argv) > 1:
        if len(sys.argv) == 2 and sys.argv[1] == "-default_version_only":
            versions_ = [DEFAULT_DATA_SNAPSHOT_VERSION]
        else:
            print(f"Unrecognized args: {sys.argv[1:]}")
            exit(1)

    config = {
        "versions": versions_,
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
        "update_connectivity_tags": False,
        "update_morphology_clusters": False,
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
                client=cave_client,
                version=v,
            )
        if config["update_labels"]:
            update_cave_data_file(
                name="labels",
                db_load_func=load_neuron_info_from_cave,
                client=cave_client,
                version=v,
            )
        if config["update_nblast_scores"]:
            update_nblast_scores(version=v)
        if config["update_connectivity_tags"]:
            update_connectivity_tags(version=v)
        if config["update_morphology_clusters"]:
            update_morphology_clusters(version=v)
