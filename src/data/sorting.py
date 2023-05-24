from collections import defaultdict

from src.data.structured_search_filters import (
    OP_DOWNSTREAM,
    OP_UPSTREAM,
    OP_RECIPROCAL,
    parse_search_query,
    OP_PATHWAYS,
    OP_SIMILAR_SHAPE,
    OP_SIMILAR_CONNECTIVITY_UPSTREAM,
    OP_SIMILAR_CONNECTIVITY_DOWNSTREAM,
)
from src.utils.graph_algos import reachable_nodes
from src.utils.logging import log_error, log

DOWNSTREAM_SYNAPSE_COUNT = "downstream_synapse_count"
UPSTREAM_SYNAPSE_COUNT = "upstream_synapse_count"
RECIPROCAL_SYNAPSE_COUNT = "reciprocal_synapse_count"
DISTANCE_FROM = "distance_from"
NBLAST_SCORE = "nblast_score"
JACCARD_SIMILARITY_UPSTREAM = "jaccard_upstream"
JACCARD_SIMILARITY_DOWNSTREAM = "jaccard_downstream"
ITEM_COUNT = "item_count"

SORTABLE_OPS = {
    OP_DOWNSTREAM: DOWNSTREAM_SYNAPSE_COUNT,
    OP_UPSTREAM: UPSTREAM_SYNAPSE_COUNT,
    OP_RECIPROCAL: RECIPROCAL_SYNAPSE_COUNT,
    OP_PATHWAYS: DISTANCE_FROM,
    OP_SIMILAR_SHAPE: NBLAST_SCORE,
    OP_SIMILAR_CONNECTIVITY_UPSTREAM: JACCARD_SIMILARITY_UPSTREAM,
    OP_SIMILAR_CONNECTIVITY_DOWNSTREAM: JACCARD_SIMILARITY_DOWNSTREAM,
    None: ITEM_COUNT,
}

SORT_BY_OPTIONS = {
    "": "Default",
    "-size": "Cell Volume (high -> low)",
    "size": "Cell Volume (low -> high)",
    "-partners": "# Partners (high -> low)",
    "partners": "# Partners (low -> high)",
    "-synapse_neuropils": "# Synapse Regions (high -> low)",
    "synapse_neuropils": "# Synapse Regions (low -> high)",
    "-labels": "# Labels (high -> low)",
    "labels": "# Labels (low -> high)",
    "twin_cells": "# Twin cells (high -> low)",
    "nt_type": "Neurotransmitter Type",
    "morphology_cluster": "Morphology Cluster",
}


def infer_sort_by(query):
    sort_by = None
    chaining_rule, free_form, structured = parse_search_query(query)
    if structured:
        sortable_terms = [t for t in structured if t["op"] in SORTABLE_OPS]
        if len(sortable_terms) == 1:
            part = sortable_terms[0]
            sort_type = SORTABLE_OPS[part["op"]]
            if sort_type in [
                DOWNSTREAM_SYNAPSE_COUNT,
                UPSTREAM_SYNAPSE_COUNT,
                RECIPROCAL_SYNAPSE_COUNT,
                NBLAST_SCORE,
                JACCARD_SIMILARITY_UPSTREAM,
                JACCARD_SIMILARITY_DOWNSTREAM,
            ]:
                target_cell_id = part["rhs"]
            else:
                target_cell_id = part["lhs"]
            sort_by = f"{sort_type}:{target_cell_id}"
            log(f"Inferred sort by {sort_by} from query: {query}")
        elif len(sortable_terms) == 0 and not free_form:
            sort_by = f"{ITEM_COUNT}:label"

    return sort_by


def sort_search_results(
    query,
    ids,
    output_sets,
    label_count_getter,
    nt_type_getter,
    morphology_cluster_getter,
    synapse_neuropil_count_getter,
    size_getter,
    partner_count_getter,
    similar_shape_cells_getter,
    similar_connectivity_cells_getter,
    connections_getter,
    sort_by=None,
):
    try:
        sort_by = sort_by or infer_sort_by(query)
        if sort_by:
            if sort_by == "-partners":
                ids = sorted(ids, key=lambda x: -partner_count_getter(x))
                return ids, None
            if sort_by == "partners":
                ids = sorted(ids, key=lambda x: partner_count_getter(x))
                return ids, None
            if sort_by == "-labels":
                ids = sorted(ids, key=lambda x: -label_count_getter(x))
                return ids, None
            if sort_by == "labels":
                ids = sorted(ids, key=lambda x: label_count_getter(x))
                return ids, None
            if sort_by == "twin_cells":
                dct = {
                    rid: len(similar_shape_cells_getter(rid, include_self=False))
                    for rid in ids
                }
                ids = sorted(ids, key=lambda x: -dct[x])
                extra_data = {
                    "title": "Number of morphologically similar cells",
                    "column_name": "Twins",
                    "values_dict": dct,
                }
                return ids, extra_data
            if sort_by == "nt_type":
                ids = sorted(ids, key=lambda x: nt_type_getter(x))
                return ids, None
            if sort_by == "morphology_cluster":
                cluster_to_rids = defaultdict(list)
                for rid in ids:
                    cluster = morphology_cluster_getter(rid)
                    if cluster:
                        cluster_to_rids[cluster].append(rid)
                # useful size clusters first
                sorted_ids = []
                for p in sorted(
                    cluster_to_rids.items(), key=lambda x: abs(30 - len(x[1]))
                ):
                    sorted_ids.extend(p[1])
                sorted_ids.extend(list(set(ids) - set(sorted_ids)))
                dct = {rid: morphology_cluster_getter(rid) for rid in ids}
                extra_data = {
                    "title": "Morphologically Cluster",
                    "column_name": "Morphology Cluster",
                    "values_dict": dct,
                }
                return sorted_ids, extra_data
            if sort_by in ["synapse_neuropils", "-synapse_neuropils"]:
                dct = {rid: synapse_neuropil_count_getter(rid) for rid in ids}
                extra_data = {
                    "title": "Number of neuropils with synapses",
                    "column_name": "Syn Rgns",
                    "values_dict": dct,
                }
                ids = (
                    sorted(ids, key=lambda x: -dct[x])
                    if sort_by.startswith("-")
                    else sorted(ids, key=lambda x: dct[x])
                )
                return ids, extra_data

            if sort_by in ["size", "-size"]:
                dct = {rid: size_getter(rid) for rid in ids}
                ids = (
                    sorted(ids, key=lambda x: -dct[x])
                    if sort_by.startswith("-")
                    else sorted(ids, key=lambda x: dct[x])
                )
                return ids, None

            parts = sort_by.split(":")
            if len(parts) != 2 or parts[0] not in SORTABLE_OPS.values():
                raise ValueError(f"Unsupported sort_by parameter: {sort_by}")
            if parts[0] == ITEM_COUNT:
                ids = sorted(ids, key=lambda x: -label_count_getter(x))
                return ids, None

            sort_by_target_cell_rid = int(parts[1])

            if parts[0] in [
                DOWNSTREAM_SYNAPSE_COUNT,
                UPSTREAM_SYNAPSE_COUNT,
                RECIPROCAL_SYNAPSE_COUNT,
            ]:
                con_table = connections_getter(sort_by_target_cell_rid)
                if parts[0] == DOWNSTREAM_SYNAPSE_COUNT:
                    extra_data_title = (
                        f"Number of input synapses from {sort_by_target_cell_rid}"
                    )
                    dct = defaultdict(int)
                    for r in con_table:
                        if r[0] == sort_by_target_cell_rid:
                            dct[r[1]] += r[3]
                elif parts[0] == UPSTREAM_SYNAPSE_COUNT:
                    extra_data_title = (
                        f"Number of output synapses to {sort_by_target_cell_rid}"
                    )
                    dct = defaultdict(int)
                    for r in con_table:
                        if r[1] == sort_by_target_cell_rid:
                            dct[r[0]] += r[3]
                else:
                    extra_data_title = (
                        f"Number of in + out synapses to {sort_by_target_cell_rid}"
                    )
                    dct = defaultdict(int)
                    for r in con_table:
                        if (
                            r[0] == sort_by_target_cell_rid
                            or r[1] == sort_by_target_cell_rid
                        ):
                            dct[r[0]] += r[3]
                extra_data = {
                    "title": extra_data_title,
                    "column_name": "Syn",
                    "values_dict": dct,
                }
                ids = sorted(ids, key=lambda x: -dct[x])
            elif parts[0] == DISTANCE_FROM:
                distance_map = reachable_nodes([sort_by_target_cell_rid], output_sets)
                extra_data = {
                    "title": "Number of hops from source cell",
                    "column_name": "Hops from source",
                    "values_dict": distance_map,
                }
                ids = sorted(ids, key=lambda x: distance_map[x])
            elif parts[0] == NBLAST_SCORE:
                sim_scores = similar_shape_cells_getter(
                    sort_by_target_cell_rid, include_self=True
                )
                extra_data = {
                    "title": "Morphological Similarity Score",
                    "column_name": "NBLAST",
                    "values_dict": {k: v / 10 for k, v in sim_scores.items()},
                }
                ids = sorted(ids, key=lambda x: -sim_scores[x])
            elif parts[0] in [
                JACCARD_SIMILARITY_UPSTREAM,
                JACCARD_SIMILARITY_DOWNSTREAM,
            ]:
                con_scores = similar_connectivity_cells_getter(
                    sort_by_target_cell_rid,
                    weighted=False,
                    include_upstream=parts[0] == JACCARD_SIMILARITY_UPSTREAM,
                    include_downstream=parts[0] == JACCARD_SIMILARITY_DOWNSTREAM,
                )
                extra_data = {
                    "title": "Overlap Jaccard Similarity Score",
                    "column_name": "Overlap",
                    "values_dict": {k: str(v)[:4] for k, v in con_scores.items()},
                }
                ids = sorted(ids, key=lambda x: -con_scores[x])
            else:
                raise ValueError(f"Unsupported sort_by parameter: {sort_by}")

            return ids, extra_data
    except Exception as e:
        log_error(f"Sort by failed for {sort_by=} and {len(ids)=}: {e}")

    return ids, None
