from collections import defaultdict

from codex.data.auto_naming import assign_names_from_annotations
from codex.data.brain_regions import REGIONS
from codex.data.catalog import (
    get_neurons_file_columns,
    get_labels_file_columns,
    get_coordinates_file_columns,
    get_connections_file_columns,
    get_nblast_file_columns,
    get_classification_file_columns,
    get_cell_stats_file_columns,
    get_connectivity_tags_file_columns,
    get_cell_types_file_columns,
)
from codex.data.neuron_data import NeuronDB
from codex.data.neurotransmitters import NEURO_TRANSMITTER_NAMES

from codex.configuration import MIN_NBLAST_SCORE_SIMILARITY
from codex.utils.formatting import (
    nanometer_to_flywire_coordinates,
    make_web_safe,
)
from codex.utils.label_cleaning import clean_and_reduce_labels
from codex import logger

NEURON_DATA_ATTRIBUTE_TYPES = {
    # auto assigned based on most prominent input and output neuropils
    "group": str,
    # group + running id (to make unique)
    "name": str,
    # FlyWire identifiers. Root IDs change with every edit -> not stable across data snapshots.
    "root_id": int,
    "supervoxel_id": list,
    # optional mirror/twin cell (LR matching)
    "mirror_twin_root_id": int,
    # community identification labels
    "label": list,
    # generic badges for marking special cells (e.g. labeling candidates)
    "marker": list,
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
    "hemilineage": str,
    "nerve": str,
    "side": str,
    # I/O counts + regions and network properties
    "input_cells": int,
    "input_synapses": int,
    "input_neuropils": list,
    "output_cells": int,
    "output_synapses": int,
    "output_neuropils": list,
    "connectivity_tag": list,
    # Marked coordinates by FlyWire community
    "position": list,
    # Cell size measurements
    "length_nm": int,
    "area_nm": int,
    "size_nm": int,
}

HEATMAP_GROUP_BY_ATTRIBUTES = [
    "side",
    "flow",
    "nt_type",
    "super_class",
    "class",
    "sub_class",
]
NETWORK_GROUP_BY_ATTRIBUTES = [
    "side",
    "flow",
    "nt_type",
    "super_class",
    "class",
    "sub_class",
]


def initialize_neuron_data(
    neuron_file_rows,
    classification_rows,
    cell_type_rows,
    cell_stats_rows,
    connection_rows,
    label_rows,
    labels_file_timestamp,
    coordinate_rows,
    nblast_rows,
    connectivity_tag_rows,
):
    neuron_attributes = {}
    neuron_connection_rows = []
    label_data = defaultdict(list)

    def _get_value(row, col_index, attr_name):
        attr_val = make_web_safe(row[col_index[attr_name]])
        attr_type = NEURON_DATA_ATTRIBUTE_TYPES[attr_name]
        if not attr_val:
            return attr_type()
        elif attr_type == list:
            return attr_val.split(",")
        else:
            return attr_type(attr_val)

    logger.debug("App initialization processing neuron data..")
    assert neuron_file_rows[0] == get_neurons_file_columns()
    neurons_column_index = {c: i for i, c in enumerate(neuron_file_rows[0])}
    for i, r in enumerate(neuron_file_rows[1:]):
        root_id = _get_value(r, neurons_column_index, "root_id")
        assert root_id not in neuron_attributes
        neuron_attributes[root_id] = {"root_id": root_id}
        neuron_attributes[root_id].update(
            {
                attr_name: (
                    _get_value(r, neurons_column_index, attr_name)
                    if attr_name in neurons_column_index
                    else attr_type()
                )
                for attr_name, attr_type in NEURON_DATA_ATTRIBUTE_TYPES.items()
            }
        )

    logger.debug(
        f"App initialization processing classification data with {len(classification_rows)} rows.."
    )
    not_found_classified_root_ids = 0
    assert (
        classification_rows[0] == get_classification_file_columns()
    ), classification_rows[0]
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
    logger.debug(
        f"App initialization: {not_found_classified_root_ids} classified ids not found in set of neurons"
    )

    logger.debug(
        f"App initialization processing cell types data with {len(cell_type_rows)} rows.."
    )
    assert cell_type_rows[0] == get_cell_types_file_columns(), cell_type_rows[0]
    cell_types_column_index = {c: i for i, c in enumerate(cell_type_rows[0])}
    for i, r in enumerate(cell_type_rows[1:]):
        root_id = int(r[cell_types_column_index["root_id"]])
        assert (
            root_id in neuron_attributes
        ), f"Invalid root ID in cell types file: {root_id}"
        primary_type = r[cell_types_column_index["primary_type"]]
        if primary_type:
            neuron_attributes[root_id]["cell_type"].append(primary_type)

    logger.debug(
        f"App initialization processing connectivity tags data with {len(connectivity_tag_rows)} rows.."
    )
    not_found_connectivity_tagged_root_ids = 0
    assert connectivity_tag_rows[0] == get_connectivity_tags_file_columns()
    connectivity_tag_column_index = {
        c: i for i, c in enumerate(connectivity_tag_rows[0])
    }
    for i, r in enumerate(connectivity_tag_rows[1:]):
        root_id = _get_value(r, connectivity_tag_column_index, "root_id")
        if root_id not in neuron_attributes:
            not_found_connectivity_tagged_root_ids += 1
            continue
        neuron_attributes[root_id]["connectivity_tag"] = _get_value(
            r, connectivity_tag_column_index, "connectivity_tag"
        )
    logger.debug(
        f"App initialization: {not_found_connectivity_tagged_root_ids} connectivity tag ids not found in set of neurons"
    )

    if cell_stats_rows:
        logger.debug(
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
        logger.debug(
            f"App initialization: {not_found_stats_root_ids} stats root ids not found in set of neurons"
        )

    logger.debug("App initialization processing label data..")
    labels_file_columns = get_labels_file_columns()
    rid_col_idx = labels_file_columns.index("root_id")
    label_col_idx = labels_file_columns.index("label")
    not_found_rids = set()
    not_found_labels = defaultdict(int)
    filtered_labels = 0
    cleaned_labels = 0

    def label_row_to_dict(row):
        res = {}
        for col_i, col_name in enumerate(labels_file_columns):
            if col_name == "root_id":
                continue
            elif col_name in {"user_id", "supervoxel_id", "label_id"}:
                res[col_name] = int(row[col_i])
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
        label_data[rid].append(label_row_to_dict(r))
    logger.debug(
        f"App initialization {len(label_rows)} labels loaded for {len(label_data)} root ids, "
        f"not found rids: {len(not_found_rids)}"
    )
    for rid, label_dicts in label_data.items():
        labels = [
            label_dict["label"]
            for label_dict in sorted(
                label_dicts, key=lambda x: x["date_created"], reverse=True
            )
        ]
        assert all(labels)
        clean_labels = clean_and_reduce_labels(labels, neuron_attributes[rid])
        assert len(clean_labels) == len(set(clean_labels))
        if clean_labels != labels:
            filtered_labels += len(labels) - len(clean_labels)
            cleaned_labels += 1
        neuron_attributes[rid]["label"].extend(clean_labels)

    if not_found_labels:
        logger.debug("Top 10 not found labels:")
        for p in sorted(not_found_labels.items(), key=lambda x: -x[1])[:10]:
            logger.debug(f"  {p}")

    logger.debug("App initialization processing coordinates data..")
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
    logger.debug(
        f"App initialization coordinates loaded for "
        f"{len([nd for nd in neuron_attributes.values() if nd['position']])} root ids, supervoxel ids loaded for "
        f"{len([nd for nd in neuron_attributes.values() if nd['supervoxel_id']])} root ids, "
        f"not found rids: {len(not_found_rids)}, max list val: {max([(len(nd['position']), nd['root_id']) for nd in neuron_attributes.values()])} "
        f"{filtered_labels=} {cleaned_labels=}"
    )

    logger.debug("App initialization loading connections..")
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

    logger.debug("App initialization processing NBLAST data..")
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
    logger.debug(
        f"App initialization NBLAST scores loaded for all root ids. "
        f"Not found rids: {len(not_found_rids)}, "
        f"max list val: {max([0] + [len(nd['similar_cell_scores']) for nd in neuron_attributes.values() if nd['similar_cell_scores']])}, "
        f"neruons with similar cells: {len([1 for nd in neuron_attributes.values() if nd['similar_cell_scores']])}"
    )

    logger.debug("App initialization augmenting..")
    for rid, nd in neuron_attributes.items():
        nd["input_neuropils"] = sorted(input_neuropils[rid])
        nd["output_neuropils"] = sorted(output_neuropils[rid])
        nd["input_synapses"] = input_synapses[rid]
        nd["output_synapses"] = output_synapses[rid]
        nd["input_cells"] = len(input_cells[rid])
        nd["output_cells"] = len(output_cells[rid])

    logger.debug("App initialization calculating grouped counts..")
    grouped_synapse_counts = {
        attr: defaultdict(int) for attr in HEATMAP_GROUP_BY_ATTRIBUTES
    }
    grouped_connection_counts = {
        attr: defaultdict(int) for attr in HEATMAP_GROUP_BY_ATTRIBUTES
    }
    grouped_reciprocal_connection_counts = {
        attr: defaultdict(int) for attr in HEATMAP_GROUP_BY_ATTRIBUTES
    }
    connected_pairs = set()
    # update synapse counts and collect connected pairs (de-duped across regions)
    for r in neuron_connection_rows:
        from_neuron = neuron_attributes[r[0]]
        to_neuron = neuron_attributes[r[1]]
        connected_pairs.add((r[0], r[1]))
        for attr in HEATMAP_GROUP_BY_ATTRIBUTES:
            from_group = from_neuron[attr]
            to_group = to_neuron[attr]
            grouped_synapse_counts[attr][(from_group, to_group)] += r[3]
    # update connection counts
    for p in connected_pairs:
        from_neuron = neuron_attributes[p[0]]
        to_neuron = neuron_attributes[p[1]]
        for attr in HEATMAP_GROUP_BY_ATTRIBUTES:
            from_group = from_neuron[attr]
            to_group = to_neuron[attr]
            grouped_connection_counts[attr][(from_group, to_group)] += 1
    # update reciprocal connection counts
    reciprocal_connections = set(
        [p for p in connected_pairs if (p[1], p[0]) in connected_pairs]
    )
    for p in reciprocal_connections:
        from_neuron = neuron_attributes[p[0]]
        to_neuron = neuron_attributes[p[1]]
        for attr in HEATMAP_GROUP_BY_ATTRIBUTES:
            from_group = from_neuron[attr]
            to_group = to_neuron[attr]
            grouped_reciprocal_connection_counts[attr][(from_group, to_group)] += 1
            grouped_reciprocal_connection_counts[attr][(to_group, from_group)] += 1
    logger.debug(
        f"App initialization found {len(reciprocal_connections)} reciprocal connections out of {len(connected_pairs)}.."
    )

    assign_names_from_annotations(neuron_attributes)

    return NeuronDB(
        neuron_attributes=neuron_attributes,
        neuron_connection_rows=neuron_connection_rows,
        label_data=label_data,
        labels_file_timestamp=labels_file_timestamp,
        grouped_synapse_counts=grouped_synapse_counts,
        grouped_connection_counts=grouped_connection_counts,
        grouped_reciprocal_connection_counts=grouped_reciprocal_connection_counts,
    )
