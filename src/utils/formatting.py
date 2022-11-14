from src.utils.parsing import tokenize, tokenize_for_highlight


def synapse_table_to_csv_string(table):
    table = [["From", "To", "Neuropil", "Synapses", "Neuro Transmitter"]] + table
    return "\n".join([",".join([str(r) for r in row]) for row in table])


def neuron_json(ndata):
    return {
        attrib: ndata[attrib]
        for attrib in ["name", "nt_type", "root_id", "classes"]
        if ndata[attrib]
    }


def synapse_json(synapse_table_row):
    return {
        "from": synapse_table_row[0],
        "to": synapse_table_row[1],
        "neuropil": synapse_table_row[2],
        "synapses": synapse_table_row[3],
        "nt_type": synapse_table_row[4],
    }


def synapse_table_to_json_dict(table, neuron_data_fetcher, meta_data):
    network_dict = {}
    node_set = set([r[0] for r in table]).union(set([r[1] for r in table]))
    network_dict["nodes"] = {
        rid: neuron_json(neuron_data_fetcher(rid)) for rid in sorted(node_set)
    }
    network_dict["edges"] = [synapse_json(r) for r in table]
    return {"meta": meta_data, "network": network_dict} if meta_data else network_dict


def percentage(part, whole):
    return f"{max(0, min(100, int(100 * float(part) / float(whole))))}%"


def highlight_annotations(filter_string, tags):
    search_tokens = tokenize(filter_string)
    folded_search_tokens = [t.casefold() for t in search_tokens]
    parsed_tags = [
        (tag_string, tokenize_for_highlight(tag_string)) for tag_string in tags
    ]
    highlighted_annotations = []
    for tag_string, tag_tokens in parsed_tags:

        # looks like this: [(color, start, end), (color, start, end), ...]
        highlight_locations = []
        for tag_token in tag_tokens:
            token, start, end = tag_token
            if token in folded_search_tokens:
                # mark for green highlighting

                # only add if not overlapping
                if not_intersecting(highlight_locations, start, end):
                    highlight_locations.append(("lightgreen", start, end))
            else:
                for search_token in search_tokens:
                    if search_token in token:
                        index = token.index(search_token)
                        # mark for yellow highlighting
                        if not_intersecting(
                            highlight_locations,
                            start + index,
                            start + index + len(search_token),
                        ):
                            highlight_locations.append(
                                (
                                    "yellow",
                                    start + index,
                                    start + index + len(search_token),
                                )
                            )

        # now highlight the tag string
        highlighted_tag_string = ""
        if highlight_locations == []:
            highlighted_tag_string = tag_string

        else:
            for i, (color, start, end) in enumerate(highlight_locations):
                if i == 0:
                    highlighted_tag_string += tag_string[:start]
                else:
                    highlighted_tag_string += tag_string[
                        highlight_locations[i - 1][2] : start
                    ]
                highlighted_tag_string += f'<span style="padding:1px;border-radius:5px;background-color:{color}">{tag_string[start:end]}</span>'
            highlighted_tag_string += tag_string[end:]

        highlighted_annotations.append(highlighted_tag_string)

    return " • ".join(highlighted_annotations)


def not_intersecting(list_of_ranges, start, end):
    if list_of_ranges == []:
        return True
    for r in list_of_ranges:
        if r[1] <= start <= r[2] or r[1] <= end <= r[2]:
            return False
    return True
