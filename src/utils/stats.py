from collections import defaultdict

from src.data.brain_regions import NEUROPIL_DESCRIPTIONS
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


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
    sort_by_freq=False,
):
    sorted_counts = (
        sorted(counts_dict.items(), key=lambda p: p[1], reverse=True)
        if sort_by_freq
        else sorted(counts_dict.items(), key=lambda p: p[0])
    )

    if sort_by_freq and len(sorted_counts) > 10:
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
    sort_by_freq=False,
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
        sort_by_freq=sort_by_freq,
    )


def _make_data_charts(data_list):
    nt_types = []
    input_output_regions = []
    input_neuropils = []
    output_neuropils = []
    classes = []
    unknown_key = "Unknown"
    for d in data_list:
        nt_types.append(d["nt_type"] or unknown_key)
        input_output_regions.append(d["hemisphere_fingerprint"] or unknown_key)
        input_neuropils.extend(d["input_neuropils"] or [unknown_key])
        output_neuropils.extend(d["output_neuropils"] or [unknown_key])
        classes.append(str(len(d["classes"]) if d["classes"] else 0))

    result = {}
    if nt_types:
        result["Num cells with neurotransmitter types"] = make_chart_from_list(
            chart_type="donut",
            key_title="Type",
            val_title="Num Cells",
            item_list=nt_types,
            descriptions_dict=NEURO_TRANSMITTER_NAMES,
            search_filter="nt",
        )
    if classes and len(set(classes)) > 1:
        result["Num. Assigned Neuron Classes"] = make_chart_from_list(
            chart_type="donut",
            key_title="Num Classes",
            val_title="Count",
            item_list=classes,
        )
    if input_neuropils:
        result["Top inputs regions"] = make_chart_from_list(
            chart_type="bar",
            key_title="Input neuropils",
            val_title="Num Cells",
            item_list=input_neuropils,
            descriptions_dict=NEUROPIL_DESCRIPTIONS,
            search_filter="input_neuropil",
            sort_by_freq=True,
        )
    if output_neuropils:
        result["Top outputs regions"] = make_chart_from_list(
            chart_type="bar",
            key_title="Output neuropils",
            val_title="Num Cells",
            item_list=output_neuropils,
            descriptions_dict=NEUROPIL_DESCRIPTIONS,
            search_filter="output_neuropil",
            sort_by_freq=True,
        )
    if input_output_regions:
        result["Num cells with inputs/outputs in hemispheres"] = make_chart_from_list(
            chart_type="donut",
            key_title="Output regions",
            val_title="Num Cells",
            item_list=input_output_regions,
        )

    return result


def _make_data_stats(data_list):
    annotated_neurons = 0
    classified_neurons = 0
    anno_counts = defaultdict(int)
    class_counts = defaultdict(int)
    for d in data_list:
        if d["tag"]:
            annotated_neurons += 1
            for t in d["tag"]:
                anno_counts[t] += 1
        if d["classes"]:
            classified_neurons += 1
            for t in d["classes"]:
                class_counts[t] += 1

    result = {
        "": {
            "Cells": len(data_list),
            "- Annotated": annotated_neurons,
            "- Classified": classified_neurons,
        }
    }
    if class_counts:
        result["Top Classes"] = {
            k: class_counts[k]
            for k in sorted(class_counts, key=class_counts.get, reverse=True)[:5]
        }
    if anno_counts:
        result["Top Annotations"] = {
            k: anno_counts[k]
            for k in sorted(anno_counts, key=anno_counts.get, reverse=True)[:5]
        }

    return result


def _format_val(val):
    return "{:,}".format(val) if isinstance(val, int) else val


def _format_for_display(dict_of_dicts):
    def _format_dict(dct):
        return {k: _format_val(v) for k, v in dct.items()}

    return {k: _format_dict(d) for k, d in dict_of_dicts.items()}


def compile_data(data, search_query, case_sensitive, match_words, data_version):
    stats_caption = []
    if search_query:
        stats_caption.append(f"search query: '{search_query}'")
    if case_sensitive:
        stats_caption.append("case sensitive")
    if match_words:
        stats_caption.append("match words")
    stats_caption.append(f"data version: {data_version}")
    caption = "Stats for " + ", ".join(stats_caption)

    data_stats = _make_data_stats(data)
    data_stats = _format_for_display(data_stats)

    data_charts = _make_data_charts(data)

    return caption, data_stats, data_charts
