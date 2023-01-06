from functools import lru_cache

from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.graph_algos import reachable_node_counts
from src.utils.logging import log_warning
from src.utils import stats as stats_utils


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
        log_warning(
            f"No stats results for {filter_string}. Sending hint '{hint}' {edist=}"
        )

    neuron_data = [neuron_db.get_neuron_data(i) for i in filtered_root_id_list]
    label_data = [neuron_db.get_label_data(i) for i in filtered_root_id_list]
    caption, data_stats, data_charts = stats_utils.compile_data(
        neuron_data=neuron_data,
        label_data=label_data,
        search_query=filter_string,
        case_sensitive=case_sensitive,
        match_words=whole_word,
        data_version=data_version,
    )
    if neuron_db.connection_rows:
        reachable_counts = reachable_node_counts(
            sources=filtered_root_id_list,
            neighbor_sets=neuron_db.output_sets(),
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            data_stats["Downstream Reachable Cells (5+ syn)"] = reachable_counts
        reachable_counts = reachable_node_counts(
            sources=filtered_root_id_list,
            neighbor_sets=neuron_db.input_sets(),
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            data_stats["Upstream Reachable Cells (5+ syn)"] = reachable_counts
    return (
        filtered_root_id_list,
        len(filtered_root_id_list),
        hint,
        data_stats,
        data_charts,
    )


@lru_cache
def leaderboard_cached():
    res = {}
    stats_utils.fill_in_leaderboard_data(
        label_data=NeuronDataFactory.instance().get().all_label_data(),
        top_n=20,
        include_lab_leaderboard=True,
        destination=res,
    )
    return stats_utils.format_for_display(res)
