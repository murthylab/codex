from collections import defaultdict, namedtuple

from src.data.brain_regions import NEUROPIL_DESCRIPTIONS
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.utils.graph_vis import format_number


def group_counts(count_pairs):
    key = f"{len(count_pairs)} others"
    val = sum([p[1] for p in count_pairs])
    return key, val


def make_chart_from_counts(
    chart_type,
    key_title,
    val_title,
    counts_dict,
    colors_dict=None,  # keyed by count_dict keys
    descriptions_dict=None,  # keyed by count_dict keys, used in tooltips
    search_filter="",
):
    sorted_counts = (
        sorted(counts_dict.items(), key=lambda p: p[1], reverse=True)
        if chart_type == "bar"
        else sorted(counts_dict.items(), key=lambda p: p[0])
    )

    if chart_type == "bar" and len(sorted_counts) > 10:
        sorted_counts = sorted_counts[:10]

    height_px = max(300, 150 + 4 * len(counts_dict)) if chart_type == "bar" else 400

    def _color(key):
        return colors_dict.get(key) if colors_dict else None

    def _tooltip(key):
        return (
            f"<b>{key}</b><br>{descriptions_dict.get(key)}<br><b>{counts_dict[key]}</b>"
            if descriptions_dict
            else None
        )

    return {
        "type": chart_type,
        "searchable": bool(search_filter),
        "search_filter": search_filter,
        "height_px": height_px,
        "data": [
            [
                key_title,
                val_title,
                {"role": "style"},
                {"type": "string", "role": "tooltip", "p": {"html": "true"}},
            ]
        ]
        + [[k, c, _color(k), _tooltip(k)] for k, c in sorted_counts],
    }


def make_chart_from_list(
    chart_type,
    key_title,
    val_title,
    item_list,
    descriptions_dict=None,
    search_filter="",
):
    counts = defaultdict(int)
    for i in item_list:
        counts[i] += 1
    return make_chart_from_counts(
        chart_type=chart_type,
        key_title=key_title,
        val_title=val_title,
        counts_dict=counts,
        descriptions_dict=descriptions_dict,
        search_filter=search_filter,
    )


def _make_data_charts(data_list):
    StatGroupProps = namedtuple("StatGroupProps", "title filter_key type descriptions")
    stat_groups = {
        "nt_type": StatGroupProps(
            "Neurotransmitter Types", "nt", "bar", NEURO_TRANSMITTER_NAMES
        ),
        "input_neuropils": StatGroupProps(
            "Top Input Regions", "input_neuropil", "bar", NEUROPIL_DESCRIPTIONS
        ),
        "output_neuropils": StatGroupProps(
            "Top Output Regions", "output_neuropil", "bar", NEUROPIL_DESCRIPTIONS
        ),
        "flow": StatGroupProps("Flow", "flow", "donut", None),
        "class": StatGroupProps("Super Class", "class", "donut", None),
        "side": StatGroupProps("Soma Side", "side", "donut", None),
        "nerve_type": StatGroupProps("Nerve", "nerve", "bar", None),
    }
    stat_lists = {k: [] for k in stat_groups.keys()}
    unknown_key = "Unknown"

    for d in data_list:
        for k, props in stat_groups.items():
            val = d[k]
            if isinstance(val, list):
                stat_lists[k].extend(val)
            elif (
                val or props.type == "donut"
            ):  # donut charts should sum up to 100%, so we include missing values
                stat_lists[k].append(val or unknown_key)

    result = {}

    for k, props in stat_groups.items():
        if stat_lists[k]:
            result[props.title] = make_chart_from_list(
                chart_type=props.type,
                key_title=props.title,
                val_title="Num Cells",
                item_list=stat_lists[k],
                search_filter=props.filter_key,
                descriptions_dict=props.descriptions,
            )

    return result


def _make_data_stats(neuron_data, label_data, include_leaderboard=False):
    labeled_neurons = 0
    classified_neurons = 0
    anno_counts = defaultdict(int)
    total_length = 0
    total_area = 0
    total_volume = 0
    for nd in neuron_data:
        if nd["label"]:
            labeled_neurons += 1
            for t in nd["label"]:
                anno_counts[t] += 1
        if nd["class"]:
            classified_neurons += 1
        total_length += nd["length_nm"]
        total_area += nd["area_nm"]
        total_volume += nd["size_nm"]

    result = {
        "": {
            "Cells": len(neuron_data),
            "- Labeled": labeled_neurons,
            "- Classified": classified_neurons,
            "- Avg. length": format_number(total_length // (1000 * len(neuron_data)))
            + " &#181;m"
            if neuron_data
            else "NA",
            "- Avg. area": format_number(total_area // (1000000 * len(neuron_data)))
            + " &#181;m<sup>2</sup>"
            if neuron_data
            else "NA",
            "- Avg. volume": format_number(
                total_volume // (1000000000 * len(neuron_data))
            )
            + " &#181;m<sup>3</sup>"
            if neuron_data
            else "NA",
        }
    }
    if anno_counts:
        result["Top Labels"] = {
            k: anno_counts[k]
            for k in sorted(anno_counts, key=anno_counts.get, reverse=True)[:10]
        }

    if include_leaderboard:
        fill_in_leaderboard_data(
            label_data=label_data,
            top_n=5,
            include_lab_leaderboard=False,
            destination=result,
        )

    return result


def _format_val(val):
    return "{:,}".format(val) if isinstance(val, int) else val


def format_for_display(dict_of_dicts):
    def _format_dict(dct):
        return {k: _format_val(v) for k, v in dct.items()}

    return {k: _format_dict(d) for k, d in dict_of_dicts.items()}


def compile_data(
    neuron_data, label_data, search_query, case_sensitive, match_words, data_version
):
    stats_caption = []
    if search_query:
        stats_caption.append(f"search query: '{search_query}'")
    if case_sensitive:
        stats_caption.append("case sensitive")
    if match_words:
        stats_caption.append("match words")
    stats_caption.append(f"data version: {data_version}")
    caption = "Stats for " + ", ".join(stats_caption)

    data_stats = _make_data_stats(neuron_data, label_data)
    data_stats = format_for_display(data_stats)

    data_charts = _make_data_charts(neuron_data)

    return caption, data_stats, data_charts


def fill_in_leaderboard_data(label_data, top_n, include_lab_leaderboard, destination):
    all_labels = []
    for ld in label_data:
        if ld:
            all_labels.extend(ld)
    recent_labels = sorted(all_labels, key=lambda t: t["label_id"])[-500:]

    if include_lab_leaderboard:
        contributors_by_lab = defaultdict(set)
        for t in all_labels:
            contributors_by_lab[t["user_affiliation"]].add(t["user_name"])
        lab_lb = defaultdict(int)
        for ld_item in all_labels:
            lab_name = ld_item["user_affiliation"]
            if lab_name:
                lab_lb[lab_name] += 1

        destination["Labs by label contributions"] = {
            k
            if len(contributors_by_lab[k]) <= 1
            else f"{k}<br><small>{len(contributors_by_lab[k])} contributors</small>": lab_lb[
                k
            ]
            for k in sorted(
                lab_lb,
                key=lab_lb.get,
                reverse=True,
            )[:top_n]
        }

    def user_cred_counts(labels_list):
        res = defaultdict(int)
        for ld_item in labels_list:
            if ld_item["user_name"] and "members" not in ld_item["user_name"].lower():
                caption = ld_item["user_name"]
                if ld_item["user_affiliation"]:
                    caption += "<br><small>" + ld_item["user_affiliation"] + "</small>"
                res[caption] += 1
        return res

    user_credit_counts_all = user_cred_counts(all_labels)
    if user_credit_counts_all:
        destination["Top Labelers (all time)"] = {
            k: user_credit_counts_all[k]
            for k in sorted(
                user_credit_counts_all, key=user_credit_counts_all.get, reverse=True
            )[:top_n]
        }

    user_credit_counts_recent = user_cred_counts(recent_labels)
    if user_credit_counts_recent:
        destination[f"Top Labelers (last {len(recent_labels)})"] = {
            k: user_credit_counts_recent[k]
            for k in sorted(
                user_credit_counts_recent,
                key=user_credit_counts_recent.get,
                reverse=True,
            )[:top_n]
        }
