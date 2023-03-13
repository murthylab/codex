from collections import defaultdict

from src.data.brain_regions import neuropil_hemisphere, REGIONS
from src.data.catalog import (
    get_neurons_file_columns,
    get_labels_file_columns,
    get_coordinates_file_columns,
    get_connections_file_columns,
    get_nblast_file_columns,
    get_classification_file_columns,
    get_cell_stats_file_columns,
    get_morphology_clusters_columns,
)
from src.data.neuron_data import NeuronDB
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES

from src.configuration import MIN_SYN_COUNT, MIN_NBLAST_SCORE_SIMILARITY
from src.utils.formatting import (
    compact_label,
    nanometer_to_flywire_coordinates,
    make_web_safe,
)
from src.utils.logging import log

NEURON_DATA_ATTRIBUTE_TYPES = {
    # auto assigned based on most prominent input and output neuropils
    "group": str,
    # group + running id (to make unique)
    "name": str,
    # FlyWire identifiers. Root IDs change with every edit -> not stable across data snapshots.
    "root_id": int,
    "supervoxel_id": list,
    # community identification labels
    "label": list,
    # nblast-based similarity. Cell ids + 1-digit scores, mapping all negative to 0 and multiplying by 10,
    # e.g.: 0.14 -> 1, 0.28 -> 3, -0.5 -> 0)
    "similar_cell_scores": dict,
    # neurotransmitter type info with prediction confidence scores
    "nt_type": str,
    "nt_type_score": float,
    "ach_avg": float,
    "gaba_avg": float,
    "glut_avg": float,
    "ser_avg": float,
    "oct_avg": float,
    "da_avg": float,
    # hierarchical annotations & classification
    "flow": str,
    "super_class": str,
    "class": str,
    "sub_class": str,
    "cell_type": list,
    "hemibrain_type": list,
    "hemilineage": str,
    "nerve": str,
    "side": str,
    # I/O counts + regions
    "input_cells": int,
    "input_synapses": int,
    "input_neuropils": list,
    "output_cells": int,
    "output_synapses": int,
    "output_neuropils": list,
    # Left/Center/Right X In/Out
    "hemisphere_fingerprint": str,
    # Marked coordinates by FlyWire community
    "position": list,
    # Cell size measurements
    "length_nm": int,
    "area_nm": int,
    "size_nm": int,
    # morphology clusters (based on NBLAST scores + SCC analysis)
    "cluster": str,
}


def initialize_neuron_data(
    neuron_file_rows,
    classification_rows,
    cell_stats_rows,
    connection_rows,
    label_rows,
    labels_file_timestamp,
    coordinate_rows,
    nblast_rows,
    morphology_cluster_rows,
):
    neuron_attributes = {}
    neuron_connection_rows = []
    label_data = defaultdict(list)

    def _get_value(row, column_index, attr_name):
        attr_val = make_web_safe(row[column_index[attr_name]])
        attr_type = NEURON_DATA_ATTRIBUTE_TYPES[attr_name]
        if not attr_val:
            return attr_type()
        elif attr_type == list:
            return attr_val.split(",")
        else:
            return attr_type(attr_val)

    log("App initialization processing neuron data..")
    assert neuron_file_rows[0] == get_neurons_file_columns()
    neurons_column_index = {c: i for i, c in enumerate(neuron_file_rows[0])}
    for i, r in enumerate(neuron_file_rows[1:]):
        root_id = _get_value(r, neurons_column_index, "root_id")
        assert root_id not in neuron_attributes
        neuron_attributes[root_id] = {"root_id": root_id}
        neuron_attributes[root_id].update(
            {
                attr_name: _get_value(r, neurons_column_index, attr_name)
                if attr_name in neurons_column_index
                else attr_type()
                for attr_name, attr_type in NEURON_DATA_ATTRIBUTE_TYPES.items()
            }
        )

    log(
        f"App initialization processing classification data with {len(classification_rows)} rows.."
    )
    not_found_classified_root_ids = 0
    assert classification_rows[0] == get_classification_file_columns()
    classification_column_index = {c: i for i, c in enumerate(classification_rows[0])}
    for i, r in enumerate(classification_rows[1:]):
        root_id = _get_value(r, classification_column_index, "root_id")
        if root_id not in neuron_attributes:
            not_found_classified_root_ids += 1
            continue
        neuron_attributes[root_id].update(
            {
                attr_name: _get_value(r, classification_column_index, attr_name)
                for attr_name in get_classification_file_columns()[1:]
            }
        )
    log(
        f"App initialization: {not_found_classified_root_ids} classified ids not found in set of neurons"
    )

    if cell_stats_rows:
        log(
            f"App initialization processing cell stats data with {len(cell_stats_rows)} rows.."
        )
        not_found_stats_root_ids = 0
        assert cell_stats_rows[0] == get_cell_stats_file_columns()
        cell_stats_column_index = {c: i for i, c in enumerate(cell_stats_rows[0])}
        for i, r in enumerate(cell_stats_rows[1:]):
            root_id = _get_value(r, cell_stats_column_index, "root_id")
            if root_id not in neuron_attributes:
                not_found_stats_root_ids += 1
                continue
            neuron_attributes[root_id].update(
                {
                    attr_name: _get_value(r, cell_stats_column_index, attr_name)
                    for attr_name in get_cell_stats_file_columns()[1:]
                }
            )
        log(
            f"App initialization: {not_found_stats_root_ids} stats root ids not found in set of neurons"
        )

    if morphology_cluster_rows:
        log(
            f"App initialization processing morpho cluster data with {len(morphology_cluster_rows)} rows.."
        )
        not_found_morpho_cluster_root_ids = 0
        assert morphology_cluster_rows[0] == get_morphology_clusters_columns()
        morpho_clusters_column_index = {
            c: i for i, c in enumerate(morphology_cluster_rows[0])
        }
        for i, r in enumerate(morphology_cluster_rows[1:]):
            root_id = _get_value(r, morpho_clusters_column_index, "root_id")
            if root_id not in neuron_attributes:
                not_found_morpho_cluster_root_ids += 1
                continue
            neuron_attributes[root_id].update(
                {
                    attr_name: _get_value(r, morpho_clusters_column_index, attr_name)
                    for attr_name in get_morphology_clusters_columns()[1:]
                }
            )
        log(
            f"App initialization: {not_found_morpho_cluster_root_ids} morpho cluster ids not found"
        )

    log("App initialization processing label data..")
    labels_file_columns = get_labels_file_columns()
    rid_col_idx = labels_file_columns.index("root_id")
    label_col_idx = labels_file_columns.index("label")
    not_found_rids = set()
    not_found_labels = defaultdict(int)

    def label_row_to_dict(row):
        res = {}
        for col_i, col_name in enumerate(labels_file_columns):
            if col_name == "root_id":
                continue
            elif col_name in {"user_id", "supervoxel_id", "label_id"}:
                res[col_name] = int(row[col_i])
            elif col_name == "label":
                res[col_name] = make_web_safe(compact_label(row[col_i]))
            else:
                res[col_name] = row[col_i]
        return res

    for i, r in enumerate(label_rows or []):
        if i == 0:
            # check header
            assert r == labels_file_columns
            continue
        rid = int(r[rid_col_idx])
        if rid not in neuron_attributes:
            not_found_rids.add(rid)
            not_found_labels[r[label_col_idx]] += 1
            continue
        label_dict = label_row_to_dict(r)
        assert label_dict["label"]
        if label_dict["label"] not in neuron_attributes[rid]["label"]:
            neuron_attributes[rid]["label"].append(label_dict["label"])
        label_data[rid].append(label_dict)
    log(
        f"App initialization labels loaded for {len(label_data)} root ids, "
        f"not found rids: {len(not_found_rids)}"
    )
    if not_found_labels:
        log("Top 10 not found labels:")
        for p in sorted(not_found_labels.items(), key=lambda x: -x[1])[:10]:
            log(f"  {p}")

    log("App initialization processing coordinates data..")
    coordinates_file_columns = get_coordinates_file_columns()
    rid_col_idx = coordinates_file_columns.index("root_id")
    pos_col_idx = coordinates_file_columns.index("position")
    vox_col_idx = coordinates_file_columns.index("supervoxel_id")
    not_found_rids = set()
    for i, r in enumerate(coordinate_rows or []):
        if i == 0:
            # check header
            assert r == coordinates_file_columns
            continue
        rid = int(r[rid_col_idx])
        if rid not in neuron_attributes:
            not_found_rids.add(rid)
            continue
        pos = r[pos_col_idx]
        vox = int(r[vox_col_idx])
        if (
            vox not in neuron_attributes[rid]["supervoxel_id"]
            or pos not in neuron_attributes[rid]["position"]
        ):
            neuron_attributes[rid]["position"].append(pos)
            neuron_attributes[rid]["supervoxel_id"].append(vox)
            fw_x, fw_y, fw_z = nanometer_to_flywire_coordinates(pos)
            assert fw_x and fw_y and fw_z
    for nd in neuron_attributes.values():
        assert len(nd["position"]) == len(nd["supervoxel_id"])
    log(
        f"App initialization coordinates loaded for "
        f"{len([nd for nd in neuron_attributes.values() if nd['position']])} root ids, supervoxel ids loaded for "
        f"{len([nd for nd in neuron_attributes.values() if nd['supervoxel_id']])} root ids, "
        f"not found rids: {len(not_found_rids)}, max list val: {max([(len(nd['position']), nd['root_id']) for nd in neuron_attributes.values()])}"
    )

    log("App initialization loading connections..")
    input_neuropils = defaultdict(set)
    output_neuropils = defaultdict(set)
    input_cells = defaultdict(set)
    output_cells = defaultdict(set)
    input_synapses = defaultdict(int)
    output_synapses = defaultdict(int)
    for i, r in enumerate(connection_rows or []):
        if i == 0:
            assert r == get_connections_file_columns()
            continue
        from_node, to_node, neuropil, syn_count, nt_type = (
            int(r[0]),
            int(r[1]),
            r[2].upper(),
            int(r[3]),
            r[4].upper(),
        )
        assert from_node in neuron_attributes and to_node in neuron_attributes
        assert syn_count >= MIN_SYN_COUNT
        assert nt_type in NEURO_TRANSMITTER_NAMES
        assert neuropil in REGIONS
        input_cells[to_node].add(from_node)
        output_cells[from_node].add(to_node)
        input_neuropils[to_node].add(neuropil)
        output_neuropils[from_node].add(neuropil)
        input_synapses[to_node] += syn_count
        output_synapses[from_node] += syn_count
        neuron_connection_rows.append(
            [from_node, to_node, neuropil, syn_count, nt_type]
        )

    log("App initialization processing NBLAST data..")
    nblast_file_columns = get_nblast_file_columns()
    rid_col_idx = nblast_file_columns.index("root_id")
    scores_col_idx = nblast_file_columns.index("scores")
    not_found_rids = set()
    for i, r in enumerate(nblast_rows or []):
        if i == 0:
            # check header
            assert r == nblast_file_columns
            continue
        from_rid = int(r[rid_col_idx])
        if from_rid not in neuron_attributes:
            not_found_rids.add(from_rid)
            continue
        assert not neuron_attributes[from_rid]["similar_cell_scores"]
        scores_dict = {}
        if r[scores_col_idx]:
            for score_pair in r[scores_col_idx].split(";"):
                vals = score_pair.split(":")
                to_rid = int(vals[0])
                if to_rid in neuron_attributes:
                    score = int(vals[1])
                    assert 0 < score < 10
                    if score >= MIN_NBLAST_SCORE_SIMILARITY:
                        scores_dict[to_rid] = score
                else:
                    not_found_rids.add(to_rid)
        neuron_attributes[from_rid]["similar_cell_scores"] = scores_dict
    for nd in neuron_attributes.values():
        if "similar_cell_scores" not in nd:
            nd["similar_cell_scores"] = {}
    log(
        f"App initialization NBLAST scores loaded for all root ids. "
        f"Not found rids: {len(not_found_rids)}, "
        f"max list val: {max([0] + [len(nd['similar_cell_scores']) for nd in neuron_attributes.values() if nd['similar_cell_scores']])}, "
        f"neruons with similar cells: {len([1 for nd in neuron_attributes.values() if nd['similar_cell_scores']])}"
    )

    log("App initialization augmenting..")
    for rid, nd in neuron_attributes.items():
        nd["input_neuropils"] = sorted(input_neuropils[rid])
        nd["output_neuropils"] = sorted(output_neuropils[rid])
        nd["input_synapses"] = input_synapses[rid]
        nd["output_synapses"] = output_synapses[rid]
        nd["hemisphere_fingerprint"] = hemisphere_fingerprint(
            nd["input_neuropils"], nd["output_neuropils"]
        )
        nd["input_cells"] = len(input_cells[rid])
        nd["output_cells"] = len(output_cells[rid])

    log("App initialization building search index..")

    return NeuronDB(
        neuron_attributes, neuron_connection_rows, label_data, labels_file_timestamp
    )


def hemisphere_fingerprint(input_pils, output_pils):
    def fp(pils):
        if pils:
            hemispheres = set([neuropil_hemisphere(p) for p in pils])
            if len(hemispheres) > 1:
                return "Mix"
            else:
                return hemispheres.pop()

    if input_pils or output_pils:
        return f"{fp(input_pils)}/{fp(output_pils)}"
    else:
        return ""
