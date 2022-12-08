import os.path
import shutil
from collections import defaultdict
from datetime import datetime
from random import sample
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
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS

CAVE_AUTH_TOKEN_FILE_NAME = f"static/secrets/cave_auth_token.txt"
CAVE_DATASTACK_NAME = "flywire_fafb_production"

COMPILED_DATA_ROOT_FOLDER = f"static/data/{LATEST_DATA_SNAPSHOT_VERSION}"
COMPILED_RAW_DATA_FILE_NAME = "flywire_data.csv.gz"

RAW_DATA_ROOT_FOLDER = f"static/raw_data/{LATEST_DATA_SNAPSHOT_VERSION}"

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

NEURON_NT_TYPES_FILE_NAME = "neuron_nt_types.feather"
NEURON_NT_TYPES_COLUMN_NAMES = [
    "pre_pt_root_id",
    "gaba_avg",
    "ach_avg",
    "glut_avg",
    "oct_avg",
    "ser_avg",
    "da_avg",
]

NEURON_INFO_FILE_NAME = "neuron_info.feather"
NEURON_INFO_COLUMN_NAMES = [
    "id",
    "valid",
    "pt_supervoxel_id",
    "pt_root_id",
    "tag",
    "user_id",
    "pt_position",
]


def load_feather_data_to_table(filename, columns_to_read):
    df_data = pandas.read_feather(filename)
    print(f"Loaded {len(df_data)} rows")

    columns = df_data.columns.to_list()
    if columns_to_read:
        if not all([c in columns for c in columns_to_read]):
            print(
                f"Missing columns in file {filename}. Expected {columns_to_read}, found {columns}."
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


def load_feather_file(filename, columns_to_read=None):
    full_path = f"{RAW_DATA_ROOT_FOLDER}/{filename}"
    if not os.path.isfile(full_path):
        print(f'Error: file "{full_path}" not found')
        exit(1)

    return load_feather_data_to_table(full_path, columns_to_read=columns_to_read)


def compile_data():
    client = init_cave_client()
    mat_timestamp = client.materialize.get_version_metadata(
        LATEST_DATA_SNAPSHOT_VERSION
    )["time_stamp"]
    print(f"Materialization timestamp: {mat_timestamp}\n\n")

    pr_info_db = load_proofreading_info_from_cave(client)
    print(f"{pr_info_db[:2]=}\n\n")

    neuron_info_db = load_neuron_info_from_cave(client)
    print(f"{neuron_info_db[:2]=}\n\n")

    neuron_info_feather = load_feather_file(
        filename=NEURON_INFO_FILE_NAME, columns_to_read=NEURON_INFO_COLUMN_NAMES
    )
    print(f"{neuron_info_feather[:2]=}\n\n")

    nt_types_feather = load_feather_file(
        filename=NEURON_NT_TYPES_FILE_NAME, columns_to_read=NEURON_NT_TYPES_COLUMN_NAMES
    )
    print(f"{nt_types_feather[:2]=}\n\n")

    syn_table_feather = load_feather_file(
        filename=SYNAPSE_TABLE_FILE_NAME, columns_to_read=SYNAPSE_TABLE_COLUMN_NAMES
    )
    # remove weak connections
    syn_table_feather = [syn_table_feather[0]] + [
        r for r in syn_table_feather[1:] if r[3] >= MIN_SYN_COUNT
    ]
    print(f"{syn_table_feather[:2]=}\n\n")

    rids_from_neuron_info_feather = set([r[3] for r in neuron_info_feather[1:]])
    rids_from_syn_feather = set([r[0] for r in syn_table_feather[1:]]).union(
        set([r[1] for r in syn_table_feather[1:]])
    )
    rids_from_nt_feather = set([r[0] for r in nt_types_feather[1:]])
    rids_from_pr_db = set([r[0] for r in pr_info_db[1:]])
    rids_from_neuron_info_db = set([r[0] for r in neuron_info_db[1:]])

    rid_sets = [
        rids_from_neuron_info_feather,
        rids_from_syn_feather,
        rids_from_nt_feather,
        rids_from_pr_db,
        rids_from_neuron_info_db,
    ]
    rid_set_names = [
        "neuron_info_feather",
        "syn_feather",
        "nt_feather",
        "pr_db",
        "neuron_info_db",
    ]
    for i, s1 in enumerate(rid_sets):
        for j in range(i + 1, len(rid_sets)):
            s2 = rid_sets[j]
            print(f"{rid_set_names[i]} vs {rid_set_names[j]}")
            print(
                f"{len(s1)=} {len(s2)=} {len(s1.intersection(s2))=} {len(s1 - s2)=} {len(s2 - s1)=}\n\n"
            )

    # map all missing root ids to the specified data snapshot

    super_voxel_ids_of_missing_root_ids_ninfo = list(
        set([r[4] for r in neuron_info_table[1:] if r[0] not in rids_from_syn_table])
    )
    print(f"{len(super_voxel_ids_of_missing_root_ids_ninfo)=}")
    mapped_root_ids_ninfo = client.chunkedgraph.get_roots(
        super_voxel_ids_of_missing_root_ids_ninfo, timestamp=mat_timestamp
    ).tolist()
    print(
        sample(
            list(zip(super_voxel_ids_of_missing_root_ids_ninfo, mapped_root_ids_ninfo)),
            10,
        )
    )
    print(
        f"{len(mapped_root_ids_ninfo)=} {len(rids_from_syn_table.intersection(set(mapped_root_ids_ninfo)))=}"
    )
    super_voxel_id_to_root_id_ninfo = {
        i: j
        for (i, j) in zip(
            super_voxel_ids_of_missing_root_ids_ninfo, mapped_root_ids_ninfo
        )
    }
    print(
        f"Unresolved tags count: {len([r for r in neuron_info_table[1:] if r[0] not in rids_from_syn_table and super_voxel_id_to_root_id_ninfo[r[4]] not in rids_from_syn_table])}"
    )

    super_voxel_ids_of_missing_root_ids_pr = list(
        set([r[2] for r in pr_info_table[1:] if r[0] not in rids_from_syn_table])
    )
    print(f"{len(super_voxel_ids_of_missing_root_ids_pr)=}")
    mapped_root_ids_pr = client.chunkedgraph.get_roots(
        super_voxel_ids_of_missing_root_ids_pr, timestamp=mat_timestamp
    ).tolist()
    print(
        sample(
            list(zip(super_voxel_ids_of_missing_root_ids_pr, mapped_root_ids_pr)), 10
        )
    )
    print(
        f"{len(mapped_root_ids_pr)=} {len(rids_from_syn_table.intersection(set(mapped_root_ids_pr)))=}"
    )
    super_voxel_id_to_root_id_pr = {
        i: j
        for (i, j) in zip(super_voxel_ids_of_missing_root_ids_pr, mapped_root_ids_pr)
    }
    print(
        f"Unresolved tags count: {len([r for r in pr_info_table[1:] if r[0] not in rids_from_syn_table and super_voxel_id_to_root_id_pr[r[2]] not in rids_from_syn_table])}"
    )

    # sanity check
    rids_syn_table_list = list(rids_from_syn_table)
    mapped_root_ids_syn_table = client.chunkedgraph.get_roots(
        rids_syn_table_list, timestamp=mat_timestamp
    ).tolist()
    print(f"{len(set(mapped_root_ids_syn_table).intersection(rids_from_syn_table))}")


def augment_existing_data():
    fname = f"static/data/{LATEST_DATA_SNAPSHOT_VERSION}/neuron_data.csv.gz"
    content = read_csv(fname)
    print("\n".join([f"{r[0]} | {r[12]} | {r[17]}" for r in content[:20]]))
    content_pos_dict = defaultdict(set)
    content_tag_dict = defaultdict(set)
    for r in content[1:]:
        if r[12]:
            for v in r[12].split(","):
                if v:
                    content_tag_dict[int(r[0])].add(v)
        if r[17]:
            for v in r[17].split(","):
                if v:
                    content_pos_dict[int(r[0])].add(v)
    print(f"{len(content_tag_dict)=} {len(content_pos_dict)=}\n\n")

    client = init_cave_client()
    mat_timestamp = client.materialize.get_version_metadata(
        FLYWIRE_DATA_SNAPSHOT_VERSION
    )["time_stamp"]
    print(f"Materialization timestamp: {mat_timestamp}\n\n")

    pr_info_db = load_proofreading_info_from_cave(client)
    print("\n".join([f"{r[0]} | {r[1]}" for r in pr_info_db[:20]]))
    pr_pos_dict = defaultdict(set)
    for r in pr_info_db[1:]:
        if r[1]:
            pr_pos_dict[int(r[0])].add(r[1])
    print(f"{len(pr_pos_dict)=}\n\n")

    neuron_info_db = load_neuron_info_from_cave(client)
    print("\n".join([f"{r[0]} | {r[1]} | {r[3]}" for r in neuron_info_db[:20]]))
    ni_pos_dict = defaultdict(set)
    ni_tag_dict = defaultdict(set)
    for r in neuron_info_db[1:]:
        if r[1]:
            ni_tag_dict[int(r[0])].add(r[1].replace(",", ";"))
        if r[3]:
            ni_pos_dict[int(r[0])].add(r[3])
    print(f"{len(ni_tag_dict)=} {len(ni_pos_dict)=}\n\n")

    # update
    for r in content[1:]:
        rid = int(r[0])
        r[12] = ",".join(list(ni_tag_dict[rid].union(content_tag_dict[rid])))
        r[17] = ",".join(list(ni_pos_dict[rid].union(content_pos_dict[rid])))

    write_csv(filename=fname, rows=content, compress=True)


def replace_classes_in_existing_data():
    fname_in = (
        f"static/data/{LATEST_DATA_SNAPSHOT_VERSION}/neuron_data_augmented.csv.gz"
    )
    fname_out = f"static/data/{LATEST_DATA_SNAPSHOT_VERSION}/neuron_data.csv.gz"
    content = read_csv(fname_in)

    coarse_labels = load_feather_file(f"coarse_cell_classes.feather")
    coarse_labels = {r[0]: r[1] for r in coarse_labels[1:]}

    for r in content[1:]:
        cl = coarse_labels.get(int(r[0]))
        r[4] = cl

    write_csv(filename=f"{fname_out}_new", rows=content, compress=True)


def compact_nt_scores_data():
    nt_scores_data = load_feather_file(
        filename=SYNAPSE_TABLE_WITH_NT_TYPES_FILE_NAME,
        columns_to_read=SYNAPSE_TABLE_WITH_NT_TYPES_COLUMN_NAMES,
    )

    header = nt_scores_data[0]
    rid_to_scores = {}

    def isnan(v):
        return v != v

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


def augment_with_nt_scores(version=LATEST_DATA_SNAPSHOT_VERSION):
    fname_in = f"static/data/{version}/neuron_data.csv.gz"
    fname_out = f"static/data/{version}/neuron_data_with_scores.csv.gz"
    content = read_csv(fname_in)

    nt_scores_data = compact_nt_scores_data()
    nt_scores_dict = {r[0]: r[1:] for r in nt_scores_data[1:]}

    not_found = 0
    content[0].extend(nt_scores_data[0][1:])
    for r in content[1:]:
        rid = int(r[0])
        if rid in nt_scores_dict:
            r.extend(nt_scores_dict[int(r[0])])
        else:
            not_found += 1
            r.extend([0] * 6)

    print(f"{not_found=}")
    write_csv(filename=f"{fname_out}_new", rows=content, compress=True)


def correct_nt_scores(version=LATEST_DATA_SNAPSHOT_VERSION):
    fname_in = f"static/data/{version}/neuron_data.csv.gz"
    fname_out = f"static/data/{version}/neuron_data_with_corrected_nt_scores.csv.gz"
    content = read_csv(fname_in)

    nt_scores_dict = compact_nt_scores_data()

    not_found = 0
    cols_idx = {
        c: content[0].index(c)
        for c in ["gaba_avg", "ach_avg", "glut_avg", "oct_avg", "ser_avg", "da_avg"]
    }
    nt_type_idx = content[0].index("nt_type")

    def max_nt_type(sd):
        max_pair = max(sd.items(), key=lambda p: p[1])
        if max_pair[1] > 0.1:
            return max_pair[0].replace("_avg", "").upper()
        else:
            return ""

    for r in content[1:]:
        rid = int(r[0])
        if rid in nt_scores_dict:
            for c, idx in cols_idx.items():
                r[idx] = nt_scores_dict[rid][c]
            r[nt_type_idx] = max_nt_type(nt_scores_dict[rid])
        else:
            # use existing scores to fill in NT type
            sdict = {c: float(r[i]) for c, i in cols_idx.items()}
            r[nt_type_idx] = max_nt_type(sdict)
            if r[nt_type_idx]:
                print(
                    f"recovered: {r[nt_type_idx]} {[r[i] for i in cols_idx.values()]}"
                )
            else:
                print(
                    f"not found: {r[nt_type_idx]} {[r[i] for i in cols_idx.values()]}"
                )
                not_found += 1

    print(f"{not_found=}")
    write_csv(filename=fname_out, rows=content, compress=True)


def fill_missing_positions(version=LATEST_DATA_SNAPSHOT_VERSION):
    fname_in = f"static/data/{version}/neuron_data.csv.gz"
    fname_out = f"static/data/{version}/neuron_data_with_filled_positions.csv.gz"

    prinfo = load_proofreading_info_from_cave(client=init_cave_client())
    position_dict = {str(r[0]): r[1] for r in prinfo}

    content = read_csv(fname_in)

    mismatch = match = not_found = filled = contained = 0
    pos_col_idx = content[0].index("position")
    for r in content[1:]:
        pos = position_dict.get(r[0])
        if not pos:
            not_found += 1
        elif not r[pos_col_idx]:
            r[pos_col_idx] = pos
            filled += 1
        elif r[pos_col_idx] == pos:
            match += 1
        elif pos in r[pos_col_idx]:
            contained += 1
        else:
            r[pos_col_idx] = f"{pos},{r[pos_col_idx]}"
            mismatch += 1
    print(f"{not_found=} {filled=} {match=} {mismatch=} {contained=}")
    write_csv(filename=fname_out, rows=content, compress=True)


def fill_new_annotations(version=LATEST_DATA_SNAPSHOT_VERSION):
    fname_in = f"static/data/{version}/neuron_data.csv.gz"
    fname_out = (
        f"static/data/{version}/neuron_data_with_annotations_{datetime.now()}.csv.gz"
    )

    content = read_csv(fname_in)
    print(content[0])
    tag_col_idx = content[0].index("tag")

    annotations = load_neuron_info_from_cave(client=init_cave_client(), version=version)
    print(f"Writing labels file with {len(annotations)} lines")
    write_csv(f"static/data/{version}/labels.csv.gz", rows=annotations, compress=True)
    print(annotations[0])
    rid_to_tags = defaultdict(list)
    for r in annotations:
        rid_to_tags[r[0]].append(r[1])

    mismatch = match = not_found = filled = contained = 0
    for r in content[1:]:
        new_tags = rid_to_tags.get(int(r[0]))
        new_tags = set([t.replace(",", ";") for t in new_tags or []])
        old_tags = set(
            [t for t in r[tag_col_idx].split(",") if t and not t.endswith("*")]
        )

        if not new_tags and old_tags:
            print(f"Not found: {old_tags}")
            r[tag_col_idx] = ",".join(old_tags)
            not_found += 1
        elif not old_tags and new_tags:
            r[tag_col_idx] = ",".join(new_tags)
            filled += 1
        elif new_tags == old_tags:
            r[tag_col_idx] = ",".join(new_tags)
            match += 1
        elif all([t in new_tags for t in old_tags]):
            r[tag_col_idx] = ",".join(new_tags)
            contained += 1
        else:
            print(f"Mismatch: {old_tags} -> {new_tags}")
            r[tag_col_idx] = ",".join(old_tags.union(new_tags))
            mismatch += 1
    print(f"{not_found=} {filled=} {match=} {mismatch=} {contained=}")
    write_csv(filename=fname_out, rows=content, compress=True)


# CLEAN


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


def compare_csvs(old_table, new_table):
    old_row_set = set([",".join([str(d) for d in r]) for r in old_table])
    new_row_set = set([",".join([str(d) for d in r]) for r in new_table])
    print(f"Rows in old but not new: {len(old_row_set - new_row_set)}")
    print(f"Rows in new but not old: {len(new_row_set - old_row_set)}")


def update_cave_data_file(name, db_load_func, cave_client, version):
    print(f"Updating {name} file..")
    fname = f"static/data/{version}/{name}.csv.gz"
    backup_fname = f"static/data/{version}/{name}_bkp.csv.gz"
    old_content = None
    if os.path.isfile(fname):
        print(f"Reading {fname}...")
        old_content = read_csv(fname)
        summarize_csv(old_content)
        print(f"Copying to {backup_fname}..")
        shutil.copy2(fname, backup_fname)
    else:
        print(f"Previous file {fname} not found.")

    print(f"Loading {name} from DB..")
    new_content = db_load_func(client=cave_client, version=version)
    summarize_csv(new_content)
    if old_content:
        compare_csvs(old_content, new_content)
    print(f"Writing {name} file with {len(new_content)} lines to {fname}")
    write_csv(fname, rows=new_content, compress=True)


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
    # compile_data()
    # augment_existing_data()
    # replace_classes_in_existing_data()
    # augment_with_nt_scores()
    # correct_nt_scores()
    # fill_missing_positions()
    # fill_new_annotations()

    columns_to_remove = []
    if columns_to_remove:
        for v in DATA_SNAPSHOT_VERSIONS:
            remove_columns(v, columns_to_remove)

    client = init_cave_client()
    for v in DATA_SNAPSHOT_VERSIONS:
        update_cave_data_file(
            name="coordinates",
            db_load_func=load_proofreading_info_from_cave,
            cave_client=client,
            version=v,
        )
        update_cave_data_file(
            name="labels",
            db_load_func=load_neuron_info_from_cave,
            cave_client=client,
            version=v,
        )
