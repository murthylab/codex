from functools import lru_cache

from codex.configuration import MIN_SYN_THRESHOLD
from codex.data.neuron_data_factory import NeuronDataFactory
from codex.utils.formatting import percentage, display
from codex.utils.graph_algos import reachable_node_counts
from codex.utils import stats as stats_utils

from codex import logger


@lru_cache
def stats_cached(filter_string, data_version, case_sensitive, whole_word):
    neuron_db = NeuronDataFactory.instance().get(data_version)
    filtered_root_id_list = neuron_db.search(
        search_query=filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    if filtered_root_id_list:
        hint = None
    else:
        hint, edist = neuron_db.closest_token(
            filter_string, case_sensitive=case_sensitive
        )
        logger.warning(
            f"No stats results for {filter_string}. Sending hint '{hint}' {edist=}"
        )

    neuron_data = [neuron_db.get_neuron_data(i) for i in filtered_root_id_list]
    caption, data_stats, data_charts = stats_utils.compile_data(
        neuron_data=neuron_data,
        search_query=filter_string,
        case_sensitive=case_sensitive,
        match_words=whole_word,
        data_version=data_version,
    )

    reachable_counts = reachable_node_counts(
        sources=filtered_root_id_list,
        neighbor_sets=neuron_db.output_sets(),
        total_count=neuron_db.num_cells(),
    )
    if reachable_counts:
        data_stats[
            f"Downstream Reachable Cells ({MIN_SYN_THRESHOLD}+ syn)"
        ] = reachable_counts
    reachable_counts = reachable_node_counts(
        sources=filtered_root_id_list,
        neighbor_sets=neuron_db.input_sets(),
        total_count=neuron_db.num_cells(),
    )
    if reachable_counts:
        data_stats[
            f"Upstream Reachable Cells ({MIN_SYN_THRESHOLD}+ syn)"
        ] = reachable_counts
    return (
        filtered_root_id_list,
        len(filtered_root_id_list),
        hint,
        data_stats,
        data_charts,
    )


@lru_cache
def leaderboard_cached(query, user_filter, lab_filter, data_version):
    neuron_db = NeuronDataFactory.instance().get(version=data_version)
    query_filtered_ids = neuron_db.search(query)
    rid_to_label_data = neuron_db.label_data_for_ids(
        query_filtered_ids, user_filter=user_filter, lab_filter=lab_filter
    )
    ld = stats_utils.collect_leaderboard_data(
        label_data=list(rid_to_label_data.values()),
        top_n=20,
        include_lab_leaderboard=True,
    )
    if not user_filter and not lab_filter:
        labeled_cells = len(
            [
                rid
                for rid in query_filtered_ids
                if neuron_db.get_neuron_data(rid)["label"]
            ]
        )
        labeled_cells_caption = f"{display(labeled_cells)} out of {display(len(query_filtered_ids))} ({percentage(labeled_cells, len(query_filtered_ids))})"
    else:
        labeled_cells_caption = (
            f"{display(len(rid_to_label_data))}" if rid_to_label_data else ""
        )
    return (
        labeled_cells_caption,
        stats_utils.format_for_display(ld),
    )
