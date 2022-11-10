from src.data.gcs_data_loader import load_connection_table_for_root_id
from src.data.structured_search_filters import (
    OP_DOWNSTREAM,
    OP_UPSTREAM,
    parse_search_query,
    OP_PATHWAYS,
)
from src.utils.graph_algos import reachable_nodes
from src.utils.logging import log_error, log

DOWNSTREAM_SYNAPSE_COUNT = "downstream_synapse_count"
UPSTREAM_SYNAPSE_COUNT = "upstream_synapse_count"
DISTANCE_FROM = "distance_from"

SORTABLE_OPS = {
    OP_DOWNSTREAM: DOWNSTREAM_SYNAPSE_COUNT,
    OP_UPSTREAM: UPSTREAM_SYNAPSE_COUNT,
    OP_PATHWAYS: DISTANCE_FROM,
}


def infer_sort_by(query):
    sort_by = None
    chaining_rule, free_form, structured = parse_search_query(query)
    if structured:
        sortable_terms = [t for t in structured if t["op"] in SORTABLE_OPS]
        if len(sortable_terms) == 1:
            part = sortable_terms[0]
            sort_type = SORTABLE_OPS[part["op"]]
            if sort_type in [DOWNSTREAM_SYNAPSE_COUNT, UPSTREAM_SYNAPSE_COUNT]:
                target_cell_id = part["rhs"]
            else:
                target_cell_id = part["lhs"]
            sort_by = f"{sort_type}:{target_cell_id}"
            log(f"Inferred sort by {sort_by} from query: {query}")
    return sort_by


def sort_search_results(query, ids, output_sets, sort_by=None):
    try:
        sort_by = sort_by or infer_sort_by(query)
        if sort_by:
            parts = sort_by.split(":")
            if len(parts) != 2 or parts[0] not in SORTABLE_OPS.values():
                raise ValueError(f"Unsupported sort_by parameter: {sort_by}")
            sort_by_target_cell_rid = int(parts[1])

            if parts[0] in [DOWNSTREAM_SYNAPSE_COUNT, UPSTREAM_SYNAPSE_COUNT]:
                con_table = load_connection_table_for_root_id(sort_by_target_cell_rid)
                if parts[0] == DOWNSTREAM_SYNAPSE_COUNT:
                    extra_data_title = (
                        f"Number of input synapses from {sort_by_target_cell_rid}"
                    )
                    dct = {
                        r[1]: r[3] for r in con_table if r[0] == sort_by_target_cell_rid
                    }
                else:
                    extra_data_title = (
                        f"Number of output synapses to {sort_by_target_cell_rid}"
                    )
                    dct = {
                        r[0]: r[3] for r in con_table if r[1] == sort_by_target_cell_rid
                    }
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
            else:
                raise ValueError(f"Unsupported sort_by parameter: {sort_by}")

            return ids, extra_data
    except Exception as e:
        log_error(f"Sort by failed for {sort_by=} and {len(ids)=}: {e}")

    return ids, None
