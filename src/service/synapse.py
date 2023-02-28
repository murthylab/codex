import math
from collections import defaultdict
from functools import lru_cache

from src.data.neuron_data_factory import NeuronDataFactory
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.utils.formatting import format_number


@lru_cache
def synapse_density_cached(data_version, normalized, directed, group_by):
    neuron_db = NeuronDataFactory.instance().get(data_version)

    num_cells = len(neuron_db.neuron_data)
    group_to_rids = defaultdict(set)
    rid_to_class = {}

    def class_group_name(nd):
        return (
            nd["class"]
            .lower()
            .replace(" neuron", "")
            .replace("ending", "")
            .replace("ection", "")
            .replace("optic", "opt")
            .replace("central", "centr")
            .replace("bilateral", "bi")
            .replace("visual", "vis")
            .replace("_", " ")
            .capitalize()
        )

    def nt_type_group_name(nd):
        return NEURO_TRANSMITTER_NAMES.get(nd["nt_type"], "unknown").capitalize()

    group_by_options = {
        "Neuron Class": class_group_name,
        "NT Type": nt_type_group_name,
    }
    if not group_by:
        group_by = list(group_by_options.keys())[0]
    group_func = group_by_options[group_by]

    all_groups = "All"
    for v in neuron_db.neuron_data.values():
        cl = group_func(v)
        rid = v["root_id"]
        group_to_rids[cl].add(rid)
        group_to_rids[all_groups].add(rid)
        rid_to_class[rid] = cl

    tot_syn_cnt = 0
    group_to_group_syn_cnt = defaultdict(int)

    def update_syn_counts(cf, ct, syn):
        group_to_group_syn_cnt[f"{cf}:{ct}"] += syn
        group_to_group_syn_cnt[f"{all_groups}:{ct}"] += syn
        group_to_group_syn_cnt[f"{cf}:{all_groups}"] += syn
        group_to_group_syn_cnt[f"{all_groups}:{all_groups}"] += syn

    for r in neuron_db.connection_rows:
        assert r[0] != r[1]
        clfrom = rid_to_class[r[0]]
        clto = rid_to_class[r[1]]
        tot_syn_cnt += r[3]
        update_syn_counts(clfrom, clto, r[3])
        if not directed:
            update_syn_counts(clto, clfrom, r[3])
    if not directed:  # reverse double counting
        group_to_group_syn_cnt = {
            k: round(v / 2) for k, v in group_to_group_syn_cnt.items()
        }

    tot_density = tot_syn_cnt / (num_cells * (num_cells - 1))
    group_to_group_density = {}
    for k, v in group_to_group_syn_cnt.items():
        if normalized:
            parts = k.split(":")
            sizefrom = (
                len(group_to_rids[parts[0]]) if parts[0] != all_groups else num_cells
            )
            sizeto = (
                len(group_to_rids[parts[1]]) if parts[1] != all_groups else num_cells
            )
            density = v / (sizefrom * sizeto)
            density /= tot_density
        else:
            density = v
        group_to_group_density[k] = density

    def heatmap_color(value, min_value, mid_value, max_value):
        cold_color = "#AAAAAA"
        hot_color = "#00FF00"
        if value <= mid_value:
            color = cold_color
            offset = math.sqrt((mid_value - value) / (mid_value - min_value))
        else:
            color = hot_color
            offset = math.sqrt((value - mid_value) / (max_value - mid_value))

        opacity = round(max(0, min(99, offset * 100)))
        return f"{color}{opacity}"

    classes = sorted(group_to_rids.keys(), key=lambda x: -len(group_to_rids[x]))

    def class_caption(cln):
        return f"<b>{cln}</b>&nbsp;<small>{round(100 * len(group_to_rids[cln]) / num_cells)}%</small>"

    def density_caption(d):
        if normalized:
            pct_diff = round(100 * (density - 1))
            if pct_diff == 0:
                return "+0% (baseline)"
            return ("+" if pct_diff >= 0 else "") + format_number(pct_diff) + "%"
        else:
            pct = round(100 * d / tot_syn_cnt)
            return format_number(d) + f"<br><small>{pct}%</small>"

    table = [["from \\ to"] + [class_caption(c) for c in classes]]
    min_density = min(group_to_group_density.values())
    max_density = max(group_to_group_density.values())
    mid_density = 1 if normalized else tot_syn_cnt / len(group_to_group_density)
    for c1 in classes:
        row = [(class_caption(c1), 0)]
        for c2 in classes:
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

    return dict(
        table=table,
        total_density=tot_density,
        directed=directed,
        normalized=normalized,
        group_by=group_by,
        group_by_options=list(group_by_options.keys()),
    )
