import math
from collections import defaultdict
from functools import lru_cache

from src.utils.formatting import display

GROUP_BY_ATTRIBUTES = {
    "Side": "side",
    "Flow": "flow",
    "NT Type": "nt_type",
    "Super Class": "super_class",
    "Class": "class",
    "Sub Class": "sub_class",
}

ALL = "All"
UNKNOWN = "Unknown"


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


def make_table(counts_data, group_sizes):
    groups = sorted(group_sizes.keys(), key=lambda x: -group_sizes[x])

    def header_caption(cln):
        return f"<b>{cln}</b>&nbsp;<small>{round(100 * group_sizes[cln] / group_sizes[ALL])}%</small>"

    table = [["from \\ to"] + [header_caption(c) for c in groups]]

    def num_pairs(from_group, to_group):
        if from_group != to_group:
            return group_sizes[from_group] * group_sizes[to_group]
        else:
            return group_sizes[from_group] * (group_sizes[from_group] - 1)

    density_data = {
        k: v / max(1, num_pairs(k[0], k[1])) for k, v in counts_data.items()
    }
    tot_density = density_data[(ALL, ALL)]
    min_density = min(density_data.values())
    max_density = max(density_data.values())
    tot_cnt = counts_data[(ALL, ALL)]

    def table_value_caption(groups_pair):
        count = counts_data[groups_pair]
        count_pct = round(100 * count / tot_cnt)
        density = density_data.get(groups_pair, 0)
        return f"{display(count)} <small>({count_pct}%)<br><b>{display(density)}</b> (density)</small>"

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
def group_data(neuron_db):
    res = {attr: defaultdict(int) for attr in GROUP_BY_ATTRIBUTES.values()}
    for r in neuron_db.connection_rows:
        from_neuron = neuron_db.get_neuron_data(r[0])
        to_neuron = neuron_db.get_neuron_data(r[1])
        for attr in GROUP_BY_ATTRIBUTES.values():
            from_group = for_display(from_neuron[attr])
            to_group = for_display(to_neuron[attr])
            res[attr][(from_group, to_group)] += r[3]
            res[attr][(ALL, to_group)] += r[3]
            res[attr][(from_group, ALL)] += r[3]
            res[attr][(ALL, ALL)] += r[3]
    return res


def compute_group_sizes(neuron_db, group_attr):
    group_sizes = defaultdict(int)
    for v in neuron_db.neuron_data.values():
        cl = for_display(v[group_attr])
        group_sizes[cl] += 1
        group_sizes[ALL] += 1
    return group_sizes


def synapse_density_data(neuron_db, group_by):
    group_by = group_by or list(GROUP_BY_ATTRIBUTES.keys())[0]
    group_attr = GROUP_BY_ATTRIBUTES[group_by]
    group_sizes = compute_group_sizes(neuron_db, group_attr)
    # make a copy to not mutate cached values
    attr_group_data = group_data(neuron_db)[group_attr].copy()

    table = make_table(
        counts_data=attr_group_data,
        group_sizes=group_sizes,
    )

    return dict(
        table=table,
        group_by=group_by,
        group_by_options=list(GROUP_BY_ATTRIBUTES.keys()),
    )
