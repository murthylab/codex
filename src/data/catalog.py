_CODEX_DATA_SCHEMA = {
    # one row per id
    "neurons": [
        "root_id",
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
    # LR matching
    "lr_matching": [
        "left_root_id",
        "right_root_id",
    ],
    # one row per id
    "classification": [
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
    ],
    # one row per id
    "cell_stats": [
        "root_id",
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
        "date_created",
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
    # one row per id
    "nblast": [
        "root_id",
        "scores",
    ],
    # one row (or none) per id
    "morphology_clusters": ["root_id", "morphology_cluster"],
    # one row (or none) per id
    "connectivity_clusters": ["root_id", "connectivity_cluster"],
}


def get_neurons_file_columns():
    return list(_CODEX_DATA_SCHEMA["neurons"])


def get_lr_matching_file_columns():
    return list(_CODEX_DATA_SCHEMA["lr_matching"])


def get_classification_file_columns():
    return list(_CODEX_DATA_SCHEMA["classification"])


def get_cell_stats_file_columns():
    return list(_CODEX_DATA_SCHEMA["cell_stats"])


def get_labels_file_columns():
    return list(_CODEX_DATA_SCHEMA["labels"])


def get_connections_file_columns():
    return list(_CODEX_DATA_SCHEMA["connections"])


def get_coordinates_file_columns():
    return list(_CODEX_DATA_SCHEMA["coordinates"])


def get_nblast_file_columns():
    return list(_CODEX_DATA_SCHEMA["nblast"])


def get_morphology_clusters_columns():
    return list(_CODEX_DATA_SCHEMA["morphology_clusters"])


def get_connectivity_clusters_columns():
    return list(_CODEX_DATA_SCHEMA["connectivity_clusters"])
