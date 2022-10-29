from collections import defaultdict

def make_donut_chart_from_counts(key_title, val_title, counts_dict):
    return [[key_title, val_title]] + [[t, c] for t, c in sorted(counts_dict.items(), key=lambda p: p[0])]

def make_donut_chart_from_list(key_title, val_title, item_list):
    counts = defaultdict(int)
    for i in item_list:
        counts[i] += 1
    return make_donut_chart_from_counts(key_title=key_title, val_title=val_title, counts_dict=counts)

def _make_data_charts(data_list):
    nt_types = []
    input_output_regions = []
    input_neuropils = []
    output_neuropils = []
    classes = []
    unknown_key = "Unknown"
    for d in data_list:
        nt_types.append(d['nt_type'] or unknown_key)
        input_output_regions.append(d['hemisphere_fingerprint'] or unknown_key)
        input_neuropils.extend(d['input_neuropils'] or [unknown_key])
        output_neuropils.extend(d['output_neuropils'] or [unknown_key])
        classes.append(str(len(d['classes']) if d['classes'] else 0))

    result = {}
    if nt_types:
        result['Neurotransmitter Types'] = make_donut_chart_from_list(
            key_title="Type", val_title="Count", item_list=nt_types)
    if input_output_regions:
        result['Input/Output hemispheres'] = make_donut_chart_from_list(
            key_title="Output regions", val_title="Count", item_list=input_output_regions)
    if classes:
        result['Num. Assigned Neuron Classes'] = make_donut_chart_from_list(
            key_title="Num Classes", val_title="Count", item_list=classes)
    if input_neuropils:
        result['Input neuropils'] = make_donut_chart_from_list(
            key_title="Input neuropils", val_title="Count", item_list=input_neuropils)
    if output_neuropils:
        result['Output neuropils'] = make_donut_chart_from_list(
            key_title="Output neuropils", val_title="Count", item_list=output_neuropils)

    return result

def _make_data_stats(data_list):
    annotated_neurons = 0
    classified_neurons = 0
    anno_counts = defaultdict(int)
    class_counts = defaultdict(int)
    for d in data_list:
        if d['tag']:
            annotated_neurons += 1
            for t in d['tag']:
                anno_counts[t] += 1
        if d['classes']:
            classified_neurons += 1
            for t in d['classes']:
                class_counts[t] += 1

    result = {
        '': {
            'Cells': len(data_list),
            '- Annotated': annotated_neurons,
            '- Classified': classified_neurons
        }
    }
    if anno_counts:
        result['Top Annotations'] = {
            k: anno_counts[k] for k in sorted(anno_counts, key=anno_counts.get, reverse=True)[:5]
        }

    if class_counts:
        result['Top Classes'] = {
            k: class_counts[k] for k in sorted(class_counts, key=class_counts.get, reverse=True)[:5]
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
        stats_caption.append('case sensitive')
    if match_words:
        stats_caption.append('match words')
    stats_caption.append(f'data version: {data_version}')
    caption = "Stats for " + ', '.join(stats_caption)

    data_stats = _make_data_stats(data)
    data_stats = _format_for_display(data_stats)

    data_charts = _make_data_charts(data)

    return caption, data_stats, data_charts
