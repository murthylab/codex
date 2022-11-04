from src.data.gcs_data_loader import load_connection_table_for_root_id
from src.utils.logging import log_error

DOWNSTREAM_SYNAPSE_COUNT = "downstream_synapse_count"
UPSTREAM_SYNAPSE_COUNT = "upstream_synapse_count"

def infer_sort_by(query):
    pass

def sort_search_results(ids, sort_by):
    try:
        parts = sort_by.split(":")
        if len(parts) != 2 or parts[0] not in [
            DOWNSTREAM_SYNAPSE_COUNT,
            UPSTREAM_SYNAPSE_COUNT,
        ]:
            raise ValueError(f"Unsupported sort_by parameter: {sort_by}")
        sort_by_target_cell_rid = int(parts[1])
        con_table = load_connection_table_for_root_id(
            sort_by_target_cell_rid
        )
        if parts[0] == DOWNSTREAM_SYNAPSE_COUNT:
            dct = {r[1]: r[3] for r in con_table if r[0] == sort_by_target_cell_rid}
        else:
            dct = {r[0]: r[3] for r in con_table if r[1] == sort_by_target_cell_rid}
        extra_data = ("Syn", dct)
        ids = sorted(ids, key=lambda x: -dct[x])
        return ids, extra_data
    except Exception as e:
        log_error(f"Sort by failed for {sort_by=} and {len(ids)=}: {e}")
        return ids, None


