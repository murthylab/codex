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
CAVE_AUTH_TOKEN_FILE_NAME = f'static/secrets/cave_auth_token.txt'
CAVE_DATASTACK_NAME = "flywire_fafb_production"

FLYWIRE_DATA_SNAPSHOT_VERSION = 447

COMPILED_DATA_ROOT_FOLDER = f'static/data/{FLYWIRE_DATA_SNAPSHOT_VERSION}'
COMPILED_RAW_DATA_FILE_NAME = "flywire_data.csv.gz"

RAW_DATA_ROOT_FOLDER = f'static/raw_data/{FLYWIRE_DATA_SNAPSHOT_VERSION}'

SYNAPSE_TABLE_FILE_NAME = "synapse_table.feather"
SYNAPSE_TABLE_COLUMN_NAMES = ['pre_pt_root_id', 'post_pt_root_id', 'neuropil', 'syn_count']

NEURON_NT_TYPES_FILE_NAME = "neuron_nt_types.feather"
NEURON_NT_TYPES_COLUMN_NAMES = ['pre_pt_root_id', 'gaba_avg', 'ach_avg', 'glut_avg', 'oct_avg', 'ser_avg', 'da_avg']
NT_TYPES = ['gaba', 'ach', 'glut', 'oct', 'ser', 'da']

def load_feather_data_to_table(filename, columns=None):
    df_data = pandas.read_feather(filename)
    print(f"Loaded {len(df_data)} rows")

    df_columns = df_data.columns.to_list()
    if columns is None:
        columns = df_columns
    df_column_indices = [df_columns.index(c) + 1 for c in columns]
    print(f"Reading columns {columns}")

    rows = []
    rows_scanned = 0
    for row in df_data.itertuples():
        rows_scanned += 1
        rows.append([row[idx] for idx in df_column_indices])
        if rows_scanned % 1000000 == 0:
            print(f"Rows scanned: {rows_scanned}")
    print(f"Rows scanned: {rows_scanned}")
    return rows

def load_feather_files():
    syn_table_fname = f'{RAW_DATA_ROOT_FOLDER}/{SYNAPSE_TABLE_FILE_NAME}'
    if not os.path.isfile(syn_table_fname):
        print(f'Error: synapse table file "{syn_table_fname}" not found')
        exit(1)

    nt_types_fname = f'{RAW_DATA_ROOT_FOLDER}/{NEURON_NT_TYPES_FILE_NAME}'
    if not os.path.isfile(nt_types_fname):
        print(f'Error: neurotransmitter types file "{nt_types_fname}" not found')
        exit(1)

    return load_feather_data_to_table(syn_table_fname, SYNAPSE_TABLE_COLUMN_NAMES), \
        load_feather_data_to_table(nt_types_fname, NEURON_NT_TYPES_COLUMN_NAMES)

def init_cave_client():
    with open(CAVE_AUTH_TOKEN_FILE_NAME) as fn:
        auth_token = str(fn.readline()).strip()
        if not auth_token:
            print("!! Missing access token. See link in the comment for how to obtain it.")
            exit(1)
    return CAVEclient(CAVE_DATASTACK_NAME, auth_token=auth_token)

def load_neuron_info_from_cave():
    client = init_cave_client()
    print("Downloading 'neuron_information_v2' with CAVE client..")
    df2 = client.materialize.query_table('neuron_information_v2')
    print(f"Downloaded {len(df2)} rows")
    root_id_to_info_list = {}
    for index, d in df2.iterrows():
        rid = int(d['pt_root_id'])
        info = {
            'tag': str(d['tag']),
            'user_id': str(d['user_id']),
            'coordinates': str(d['pt_position'])
        }
        root_id_to_info_list[rid] = root_id_to_info_list.get(rid, []) + [info]
    return root_id_to_info_list

def load_proofreading_info_from_cave():
    client = init_cave_client()
    print("Downloading 'proofreading_status_public_v1' with CAVE client..")
    df2 = client.materialize.query_table('proofreading_status_public_v1')
    print(f"Downloaded {len(df2)} rows")
    root_id_to_pos = {}
    pos_to_root_id = {}
    for index, d in df2.iterrows():
        rid = int(d['pt_root_id'])
        pos = str(d['pt_position'])
        root_id_to_pos[rid] = root_id_to_pos.get(rid, []) + [pos]
        pos_to_root_id[pos] = root_id_to_pos.get(pos, []) + [rid]
    print(f'{len(root_id_to_pos)=}, {len(pos_to_root_id)=}')
    return root_id_to_pos, pos_to_root_id


if __name__ == "__main__":
    _, _ = load_proofreading_info_from_cave()
    neuron_info = load_neuron_info_from_cave()
    syn_table_rows, nt_types_rows = load_feather_files()

