import math
from collections import defaultdict
from functools import lru_cache

from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.formatting import display

GROUP_BY_ATTRIBUTES = {
    "Side": "side",
    "Flow": "flow",
    "NT Type": "nt_type",
    "Super Class": "super_class",
    "Class": "super_class",
    "Sub Class": "sub_class",
}

ALL = "All"


def attribute_for_display(nd, attr_key):
    val = nd[attr_key]
    if not val or val.lower() in ["na"]:
        val = "unknown"
    return display(val)


def update_counts(counts_dict, from_group, to_group, count):
    counts_dict[f"{from_group}:{to_group}"] += count
    counts_dict[f"{ALL}:{to_group}"] += count
    counts_dict[f"{from_group}:{ALL}"] += count
    counts_dict[f"{ALL}:{ALL}"] += count


def heatmap_color(value, min_value, mid_value, max_value):
    cold_color = "#AAAAAA"
    hot_color = "#00FF00"
    if value <= mid_value:
        color = cold_color
        offset = math.sqrt((mid_value - value) / (mid_value - min_value))
    else:
        color = hot_color
        offset = math.sqrt((value - mid_value) / (max_value - mid_value))

    opacity = max(0, min(99, round(offset * 100)))
    return f"{color}{opacity}"


def make_table(group_to_group_density, group_sizes, num_cells, tot_cnt, normalized):
    groups = sorted(group_sizes.keys(), key=lambda x: -group_sizes[x])

    def header_caption(cln):
        return f"<b>{cln}</b>&nbsp;<small>{round(100 * group_sizes[cln] / num_cells)}%</small>"

    def density_caption(d):
        if normalized:
            pct_diff = round(100 * (density - 1))
            if pct_diff == 0:
                return "+0% (baseline)"
            return ("+" if pct_diff >= 0 else "") + display(pct_diff) + "%"
        else:
            pct = round(100 * d / tot_cnt)
            return display(d) + f"<br><small>{pct}%</small>"

    table = [["from \\ to"] + [header_caption(c) for c in groups]]
    min_density = min(group_to_group_density.values())
    max_density = max(group_to_group_density.values())
    mid_density = 1 if normalized else tot_cnt / len(group_to_group_density)
    for c1 in groups:
        row = [(header_caption(c1), 0)]
        for c2 in groups:
            density = group_to_group_density.get(f"{c1}:{c2}", 0)
            row.append(
                (
                    density_caption(density),
                    heatmap_color(
                        value=density,
                        min_value=min_density,
                        mid_value=mid_density,
                        max_value=max_density,
                    ),
                )
            )
        table.append(row)
    return table


@lru_cache
def synapse_density_cached(data_version, normalized, directed, group_by):
    neuron_db = NeuronDataFactory.instance().get(data_version)

    num_cells = len(neuron_db.neuron_data)
    group_sizes = defaultdict(int)
    rid_to_group = {}

    if not group_by:
        group_by = list(GROUP_BY_ATTRIBUTES.keys())[0]
    group_attr = GROUP_BY_ATTRIBUTES[group_by]

    for v in neuron_db.neuron_data.values():
        cl = attribute_for_display(v, group_attr)
        rid = v["root_id"]
        group_sizes[cl] += 1
        group_sizes[ALL] += 1
        rid_to_group[rid] = cl

    tot_cnt = 0
    group_to_group_cnt = defaultdict(int)

    for r in neuron_db.connection_rows:
        assert r[0] != r[1]
        clfrom = rid_to_group[r[0]]
        clto = rid_to_group[r[1]]
        tot_cnt += r[3]
        update_counts(group_to_group_cnt, clfrom, clto, r[3])
        if not directed:
            update_counts(group_to_group_cnt, clto, clfrom, r[3])
    if not directed:  # reverse double counting
        group_to_group_cnt = {k: round(v / 2) for k, v in group_to_group_cnt.items()}

    tot_density = tot_cnt / (num_cells * (num_cells - 1))
    group_to_group_density = {}
    for k, v in group_to_group_cnt.items():
        if normalized:
            parts = k.split(":")
            sizefrom = group_sizes[parts[0]] if parts[0] != ALL else num_cells
            sizeto = group_sizes[parts[1]] if parts[1] != ALL else num_cells
            density = v / (sizefrom * sizeto)
            density /= tot_density
        else:
            density = v
        group_to_group_density[k] = density

    table = make_table(
        group_to_group_density=group_to_group_density,
        group_sizes=group_sizes,
        num_cells=num_cells,
        tot_cnt=tot_cnt,
        normalized=normalized,
    )

    return dict(
        table=table,
        total_density=tot_density,
        directed=directed,
        normalized=normalized,
        group_by=group_by,
        group_by_options=list(GROUP_BY_ATTRIBUTES.keys()),
    )
