_CODEX_DATA_SCHEMA = {
    # one row per id
    "neurons": [
        "root_id",
        "name",
        "group",
        "nt_type",
        "nt_type_score",
        "da_avg",
        "ser_avg",
        "gaba_avg",
        "glut_avg",
        "ach_avg",
        "oct_avg",
        "flow",
        "super_class",
        "class",
        "sub_class",
        "cell_type",
        "side",
        "nerve_type",
        "length_nm",
        "area_nm",
        "size_nm",
    ],
    # multiple rows per id
    "labels": [
        "root_id",
        "label",
        "user_id",
        "position",
        "supervoxel_id",
        "label_id",
        "user_name",
        "user_affiliation",
    ],
    # one row per (pre_root_id,post_root_id,neuropil) tuple
    "connections": [
        "pre_root_id",
        "post_root_id",
        "neuropil",
        "syn_count",
        "nt_type",
    ],
    # multiple rows per id
    "coordinates": [
        "root_id",
        "position",
        "supervoxel_id",
    ],
    # multiple rows per id
    "nblast": [
        "root_id",
        "scores",
    ],
}


def get_neurons_file_columns():
    return list(_CODEX_DATA_SCHEMA["neurons"])


def get_classes_file_columns():
    return list(_CODEX_DATA_SCHEMA["classes"])


def get_labels_file_columns():
    return list(_CODEX_DATA_SCHEMA["labels"])


def get_connections_file_columns():
    return list(_CODEX_DATA_SCHEMA["connections"])


def get_coordinates_file_columns():
    return list(_CODEX_DATA_SCHEMA["coordinates"])


def get_nblast_file_columns():
    return list(_CODEX_DATA_SCHEMA["nblast"])
