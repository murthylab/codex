import math
from collections import defaultdict
from functools import lru_cache

from src.utils.formatting import display


ALL = "All"
UNKNOWN = "Unknown"
COUNT_TYPE_OPTIONS = ["Synapses", "Connections", "Reciprocal Connections"]


@lru_cache
def for_display(val):
    if not val or val.lower() in ["na"]:
        val = UNKNOWN
    return display(val)


def heatmap_color(value, min_value, mid_value, max_value):
    cold_color = "#AAAAAA"
    hot_color = "#00FF00"
    if value <= mid_value:
        color = cold_color
        offset = math.sqrt((mid_value - value) / max(0.1, mid_value - min_value))
    else:
        color = hot_color
        offset = math.sqrt((value - mid_value) / max(0.1, max_value - mid_value))

    opacity = max(0, min(99, round(offset * 100)))
    return f"{color}{opacity}"


def make_table(counts_table, group_sizes, normalization_table=None):
    groups = sorted(group_sizes.keys(), key=lambda x: -group_sizes[x])

    def header_caption(cln):
        return f"<b>{cln}</b>&nbsp;<small>{round(100 * group_sizes[cln] / group_sizes[ALL])}%</small>"

    table = [["from \\ to"] + [header_caption(c) for c in groups]]

    if normalization_table is None:

        def num_pairs(from_group, to_group):
            if from_group != to_group:
                return group_sizes[from_group] * group_sizes[to_group]
            else:
                return group_sizes[from_group] * (group_sizes[from_group] - 1)

        normalization_table = {k: num_pairs(k[0], k[1]) for k in counts_table.keys()}

    density_data = {
        k: v / max(1, normalization_table[k]) for k, v in counts_table.items()
    }
    tot_density = density_data[(ALL, ALL)]
    min_density = min(density_data.values())
    max_density = max(density_data.values())
    tot_cnt = counts_table[(ALL, ALL)]

    def table_value_caption(groups_pair):
        count = counts_table.get(groups_pair, 0)
        count_pct = round(100 * count / tot_cnt)
        density = density_data.get(groups_pair, 0)
        return f"{count_pct}%<small> ({display(count)})<br><b>{display(density)}</b> avg.</small>"

    for c1 in groups:
        row = [(header_caption(c1), 0)]
        for c2 in groups:
            group_pair = (c1, c2)
            row.append(
                (
                    table_value_caption(group_pair),
                    heatmap_color(
                        value=density_data.get(group_pair, 0),
                        min_value=min_density,
                        mid_value=tot_density,
                        max_value=max_density,
                    ),
                )
            )
        table.append(row)
    return table


@lru_cache
def counts_data(neuron_db, group_by, count_type):
    res_counts = defaultdict(int)
    if count_type == "Synapses":
        counts_dict = neuron_db.grouped_synapse_counts[group_by]
    elif count_type == "Connections":
        counts_dict = neuron_db.grouped_connection_counts[group_by]
    elif count_type == "Reciprocal Connections":
        counts_dict = neuron_db.grouped_reciprocal_connection_counts[group_by]
    else:
        raise ValueError(f"Unknown count type option: {count_type}")

    def update_count(fr, to, count):
        res_counts[(fr, to)] += count

    for k, v in counts_dict.items():
        from_p = for_display(k[0])
        to_p = for_display(k[1])
        update_count(from_p, to_p, v)
        update_count(ALL, to_p, v)
        update_count(from_p, ALL, v)
        update_count(ALL, ALL, v)

    if count_type == "Reciprocal Connections":
        # reciprocal connections are undirected, adjust for double counting
        res_counts = {k: v / 2 for k, v in res_counts.items()}
    return res_counts


def compute_group_sizes(neuron_db, group_attr):
    group_sizes = defaultdict(int)
    for v in neuron_db.neuron_data.values():
        cl = for_display(v[group_attr])
        group_sizes[cl] += 1
        group_sizes[ALL] += 1
    return group_sizes


def heatmap_data(neuron_db, group_by, count_type):
    group_by_attributes = {
        display(attr): attr for attr in neuron_db.grouped_synapse_counts.keys()
    }
    count_type = count_type or COUNT_TYPE_OPTIONS[0]
    group_by = group_by or list(group_by_attributes.keys())[0]
    group_attr = group_by_attributes[group_by]
    group_sizes = compute_group_sizes(neuron_db, group_attr)
    attr_group_data = counts_data(neuron_db, group_attr, count_type)
    if count_type == "Connections":
        normalization_table = None
        normalized_by = "number of pairs of neurons in the group pair"
    else:
        normalization_table = counts_data(
            neuron_db=neuron_db, group_by=group_attr, count_type="Connections"
        )
        normalized_by = "number of connected neurons in the group pair"
    table = make_table(
        counts_table=attr_group_data,
        group_sizes=group_sizes,
        normalization_table=normalization_table,
    )

    explanations = [
        f"This table shows the distribution of <b>{count_type.lower()}</b> across neurons grouped "
        f"by <b>{display(group_by).lower()}</b>.",
        "In each cell, the first line shows the number "
        f"of <b>{count_type.lower()}</b> for the corresponding pair of neuron groups, and the second line shows "
        f"the average value, normalized by <b>{normalized_by}</b>.",
        "Cell colors are assigned to highlight the "
        "group pairs for which average value deviates from the overall average.",
    ]

    return dict(
        table=table,
        group_by=group_by,
        group_by_options=list(group_by_attributes.keys()),
        count_type=count_type,
        count_type_options=COUNT_TYPE_OPTIONS,
        explanations=explanations,
    )
