import pandas
import os.path

# FlyWire data snapshots are exported periodically in 2 Google Drive folders (within them snapshot sub-folders are
# named by internal version, e.g. 447.):
# Raw synapse table is here: https://drive.google.com/drive/folders/1g7i3LMmDFcZXDXzevy3eUSrmcMJl2B6a/
#  - look for file named something like 'syn_proof_analysis_filtered_consolidated_447.feather' (assuming version 447)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as SYNAPSE_TABLE_FILE_NAME below
# Neurotransmitter types are here: https://drive.google.com/drive/folders/1B1_-yLi-ED7U8af8OJHhCHr8STq3bf1H
#  - look for file named something like 'neuron_proof_analysis_ntavg_447.feather' (assuming version 447)
#  - download it into RAW_DATA_ROOT_FOLDER and name it as NEURON_NT_TYPES_FILE_NAME below

FLYWIRE_DATA_SNAPSHOT_VERSION = 447

RAW_DATA_ROOT_FOLDER = f'static/data/raw/{FLYWIRE_DATA_SNAPSHOT_VERSION}'

SYNAPSE_TABLE_FILE_NAME = "synapse_table.feather"
SYNAPSE_TABLE_COLUMN_NAMES = ['pre_pt_root_id', 'post_pt_root_id', 'neuropil', 'syn_count']

NEURON_NT_TYPES_FILE_NAME = "neuron_nt_types.feather"
NEURON_NT_TYPES_COLUMN_NAMES = ['pre_pt_root_id', 'post_pt_root_id', 'neuropil', 'syn_count']
NT_TYPES = ['gaba', 'ach', 'glut', 'oct', 'ser', 'da']

COMPILED_RAW_DATA_FILE_NAME = "flywire_data.csv.gz"

def process_feather_files():
    if not os.path.isfile(f'{RAW_DATA_ROOT_FOLDER}/{SYNAPSE_TABLE_FILE_NAME}'):
        print(f'Error: synapse table file "{RAW_DATA_ROOT_FOLDER}/{SYNAPSE_TABLE_FILE_NAME}" not found')
        exit(1)

    if not os.path.isfile(f'{RAW_DATA_ROOT_FOLDER}/{NEURON_NT_TYPES_FILE_NAME}'):
        print(f'Error: synapse table file "{RAW_DATA_ROOT_FOLDER}/{NEURON_NT_TYPES_FILE_NAME}" not found')
        exit(1)


if __name__ == "__main__":
    process_feather_files()
