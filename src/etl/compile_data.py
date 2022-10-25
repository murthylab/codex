from collections import defaultdict
from random import sample
import pandas
import os.path
from caveclient import CAVEclient

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
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION
from src.data.local_data_loader import read_csv, write_csv

CAVE_AUTH_TOKEN_FILE_NAME = f'static/secrets/cave_auth_token.txt'
CAVE_DATASTACK_NAME = "flywire_fafb_production"

MIN_SYN_COUNT = 5

COMPILED_DATA_ROOT_FOLDER = f'static/data/{LATEST_DATA_SNAPSHOT_VERSION}'
COMPILED_RAW_DATA_FILE_NAME = "flywire_data.csv.gz"

RAW_DATA_ROOT_FOLDER = f'static/raw_data/{LATEST_DATA_SNAPSHOT_VERSION}'

SYNAPSE_TABLE_FILE_NAME = "synapse_table.feather"
SYNAPSE_TABLE_COLUMN_NAMES = ['pre_pt_root_id', 'post_pt_root_id', 'neuropil', 'syn_count']

NEURON_NT_TYPES_FILE_NAME = "neuron_nt_types.feather"
NEURON_NT_TYPES_COLUMN_NAMES = ['pre_pt_root_id', 'gaba_avg', 'ach_avg', 'glut_avg', 'oct_avg', 'ser_avg', 'da_avg']
NT_TYPES = ['gaba', 'ach', 'glut', 'oct', 'ser', 'da']

NEURON_INFO_FILE_NAME = "neuron_info.feather"
NEURON_INFO_COLUMN_NAMES = ['id', 'valid', 'pt_supervoxel_id', 'pt_root_id', 'tag', 'user_id', 'pt_position']


def load_feather_data_to_table(filename, columns_to_read):
    df_data = pandas.read_feather(filename)
    print(f"Loaded {len(df_data)} rows")

    columns = df_data.columns.to_list()
    if columns_to_read:
        if not all([c in columns for c in columns_to_read]):
            print(f"Missing columns in file {filename}. Expected {columns_to_read}, found {columns}.")
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
    full_path = f'{RAW_DATA_ROOT_FOLDER}/{filename}'
    if not os.path.isfile(full_path):
        print(f'Error: file "{full_path}" not found')
        exit(1)

    return load_feather_data_to_table(full_path, columns_to_read=columns_to_read)

def init_cave_client():
    with open(CAVE_AUTH_TOKEN_FILE_NAME) as fn:
        auth_token = str(fn.readline()).strip()
        if not auth_token:
            print("!! Missing access token. See link in the comment for how to obtain it.")
            exit(1)
    return CAVEclient(CAVE_DATASTACK_NAME, auth_token=auth_token)

def load_neuron_info_from_cave(client):
    print("Downloading 'neuron_information_v2' with CAVE client..")
    df = client.materialize.query_table('neuron_information_v2', materialization_version=LATEST_DATA_SNAPSHOT_VERSION)
    print(f"Downloaded {len(df)} rows with columns {df.columns.to_list()}")
    neuron_info_table = [['root_id', 'tag', 'user_id', 'position', 'supervoxel_id']]
    for index, d in df.iterrows():
        neuron_info_table.append([
            int(d['pt_root_id']),
            str(d['tag']),
            str(d['user_id']),
            str(d['pt_position']),
            int(d['pt_supervoxel_id'])
        ])
    return neuron_info_table

def load_proofreading_info_from_cave(client):
    print("Downloading 'proofreading_status_public_v1' with CAVE client..")
    df = client.materialize.query_table('proofreading_status_public_v1', materialization_version=LATEST_DATA_SNAPSHOT_VERSION)
    print(f"Downloaded {len(df)} rows with columns {df.columns.to_list()}")
    pr_info_table = [['root_id', 'position', 'supervoxel_id']]
    for index, d in df.iterrows():
        pr_info_table.append([int(d['pt_root_id']), str(d['pt_position']), int(d['pt_supervoxel_id'])])
    return pr_info_table

def compile_data():
    client = init_cave_client()
    mat_timestamp = client.materialize.get_version_metadata(LATEST_DATA_SNAPSHOT_VERSION)["time_stamp"]
    print(f'Materialization timestamp: {mat_timestamp}\n\n')

    pr_info_db = load_proofreading_info_from_cave(client)
    print(f'{pr_info_db[:2]=}\n\n')

    neuron_info_db = load_neuron_info_from_cave(client)
    print(f'{neuron_info_db[:2]=}\n\n')

    neuron_info_feather = load_feather_file(filename=NEURON_INFO_FILE_NAME, columns_to_read=NEURON_INFO_COLUMN_NAMES)
    print(f'{neuron_info_feather[:2]=}\n\n')

    nt_types_feather = load_feather_file(filename=NEURON_NT_TYPES_FILE_NAME, columns_to_read=NEURON_NT_TYPES_COLUMN_NAMES)
    print(f'{nt_types_feather[:2]=}\n\n')

    syn_table_feather = load_feather_file(filename=SYNAPSE_TABLE_FILE_NAME, columns_to_read=SYNAPSE_TABLE_COLUMN_NAMES)
    # remove weak connections
    syn_table_feather = [syn_table_feather[0]] + [r for r in syn_table_feather[1:] if r[3] >= MIN_SYN_COUNT]
    print(f'{syn_table_feather[:2]=}\n\n')

    rids_from_neuron_info_feather = set([r[3] for r in neuron_info_feather[1:]])
    rids_from_syn_feather = set([r[0] for r in syn_table_feather[1:]]).union(set([r[1] for r in syn_table_feather[1:]]))
    rids_from_nt_feather = set([r[0] for r in nt_types_feather[1:]])
    rids_from_pr_db = set([r[0] for r in pr_info_db[1:]])
    rids_from_neuron_info_db = set([r[0] for r in neuron_info_db[1:]])

    rid_sets = [
        rids_from_neuron_info_feather, rids_from_syn_feather, rids_from_nt_feather, rids_from_pr_db, rids_from_neuron_info_db
    ]
    rid_set_names = [
        'neuron_info_feather', 'syn_feather', 'nt_feather', 'pr_db', 'neuron_info_db'
    ]
    for i, s1 in enumerate(rid_sets):
        for j in range(i + 1, len(rid_sets)):
            s2 = rid_sets[j]
            print(f'{rid_set_names[i]} vs {rid_set_names[j]}')
            print(f'{len(s1)=} {len(s2)=} {len(s1.intersection(s2))=} {len(s1 - s2)=} {len(s2 - s1)=}\n\n')



    # map all missing root ids to the specified data snapshot

    super_voxel_ids_of_missing_root_ids_ninfo = list(set([r[4] for r in neuron_info_table[1:] if r[0] not in rids_from_syn_table]))
    print(f'{len(super_voxel_ids_of_missing_root_ids_ninfo)=}')
    mapped_root_ids_ninfo = client.chunkedgraph.get_roots(super_voxel_ids_of_missing_root_ids_ninfo, timestamp=mat_timestamp).tolist()
    print(sample(list(zip(super_voxel_ids_of_missing_root_ids_ninfo, mapped_root_ids_ninfo)), 10))
    print(f'{len(mapped_root_ids_ninfo)=} {len(rids_from_syn_table.intersection(set(mapped_root_ids_ninfo)))=}')
    super_voxel_id_to_root_id_ninfo = {i: j for (i, j) in zip(super_voxel_ids_of_missing_root_ids_ninfo, mapped_root_ids_ninfo)}
    print(f'Unresolved tags count: {len([r for r in neuron_info_table[1:] if r[0] not in rids_from_syn_table and super_voxel_id_to_root_id_ninfo[r[4]] not in rids_from_syn_table])}')

    super_voxel_ids_of_missing_root_ids_pr = list(set([r[2] for r in pr_info_table[1:] if r[0] not in rids_from_syn_table]))
    print(f'{len(super_voxel_ids_of_missing_root_ids_pr)=}')
    mapped_root_ids_pr = client.chunkedgraph.get_roots(super_voxel_ids_of_missing_root_ids_pr, timestamp=mat_timestamp).tolist()
    print(sample(list(zip(super_voxel_ids_of_missing_root_ids_pr, mapped_root_ids_pr)), 10))
    print(f'{len(mapped_root_ids_pr)=} {len(rids_from_syn_table.intersection(set(mapped_root_ids_pr)))=}')
    super_voxel_id_to_root_id_pr = {i: j for (i, j) in zip(super_voxel_ids_of_missing_root_ids_pr, mapped_root_ids_pr)}
    print(f'Unresolved tags count: {len([r for r in pr_info_table[1:] if r[0] not in rids_from_syn_table and super_voxel_id_to_root_id_pr[r[2]] not in rids_from_syn_table])}')

    # sanity check
    rids_syn_table_list = list(rids_from_syn_table)
    mapped_root_ids_syn_table = client.chunkedgraph.get_roots(rids_syn_table_list, timestamp=mat_timestamp).tolist()
    print(f'{len(set(mapped_root_ids_syn_table).intersection(rids_from_syn_table))}')


def augment_existing_data():
    fname = f'static/data/{LATEST_DATA_SNAPSHOT_VERSION}/neuron_data.csv.gz'
    content = read_csv(fname)
    print('\n'.join([f'{r[0]} | {r[12]} | {r[17]}' for r in content[:20]]))
    content_pos_dict = defaultdict(set)
    content_tag_dict = defaultdict(set)
    for r in content[1:]:
        if r[12]:
            for v in r[12].split(','):
                if v:
                    content_tag_dict[int(r[0])].add(v)
        if r[17]:
            for v in r[17].split(','):
                if v:
                    content_pos_dict[int(r[0])].add(v)
    print(f'{len(content_tag_dict)=} {len(content_pos_dict)=}\n\n')

    client = init_cave_client()
    mat_timestamp = client.materialize.get_version_metadata(FLYWIRE_DATA_SNAPSHOT_VERSION)["time_stamp"]
    print(f'Materialization timestamp: {mat_timestamp}\n\n')

    pr_info_db = load_proofreading_info_from_cave(client)
    print('\n'.join([f'{r[0]} | {r[1]}' for r in pr_info_db[:20]]))
    pr_pos_dict = defaultdict(set)
    for r in pr_info_db[1:]:
        if r[1]:
            pr_pos_dict[int(r[0])].add(r[1])
    print(f'{len(pr_pos_dict)=}\n\n')

    neuron_info_db = load_neuron_info_from_cave(client)
    print('\n'.join([f'{r[0]} | {r[1]} | {r[3]}' for r in neuron_info_db[:20]]))
    ni_pos_dict = defaultdict(set)
    ni_tag_dict = defaultdict(set)
    for r in neuron_info_db[1:]:
        if r[1]:
            ni_tag_dict[int(r[0])].add(r[1].replace(',', ';'))
        if r[3]:
            ni_pos_dict[int(r[0])].add(r[3])
    print(f'{len(ni_tag_dict)=} {len(ni_pos_dict)=}\n\n')

    # update
    for r in content[1:]:
        rid = int(r[0])
        r[12] = ','.join(list(ni_tag_dict[rid].union(content_tag_dict[rid])))
        r[17] = ','.join(list(ni_pos_dict[rid].union(content_pos_dict[rid])))

    write_csv(filename=fname, rows=content, compress=True)


if __name__ == "__main__":
    #compile_data()
    augment_existing_data()





