_CODEX_DATA_SCHEMA = {
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
    ],
    "classes": ["root_id", "class"],
    "labels": [
        "root_id",
        "tag",
        "user_id",
        "position",
        "supervoxel_id",
        "tag_id",
        "user_name",
        "user_affiliation",
    ],
    "connections": [
        "pre_root_id",
        "post_root_id",
        "neuropil",
        "syn_count",
        "nt_type",
    ],
    "coordinates": [
        "root_id",
        "position",
        "supervoxel_id",
    ],
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
