import string
from math import floor, log10

from src.utils.parsing import tokenize, tokenize_and_fold_for_highlight


# Replaces all newline/return/tab chars with plain whitespace, and string delimiters with back quotes.
# This enables passing strings safely back and forth to jinja templates without urlencoding them.
WEB_SAFE_MAP = {c: " " for c in set(string.whitespace)}  # Whitespaces
WEB_SAFE_MAP.update({c: "`" for c in ['"', "'"]})  # String delimiters

UNDEFINED_THINGS = [
    "",
    "na",
    "nan",
    "none",
    "null",
    "nil",
    "unknown",
    "undefined",
    "unspecified",
    "unassigned",
    "unavailable",
]


def make_web_safe(txt):
    return (
        "".join([WEB_SAFE_MAP.get(c, c) for c in txt]) if isinstance(txt, str) else txt
    )


def synapse_table_to_csv_string(table):
    table = [["From", "To", "Neuropil", "Synapses", "Neuro Transmitter"]] + table
    return "\n".join([",".join([str(r) for r in row]) for row in table])


def neuron_json(ndata):
    return {
        attrib: ndata[attrib]
        for attrib in ["name", "nt_type", "root_id", "class"]
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
    return f"{max(0, min(100, int(100 * float(part) / float(max(whole, 1)))))}%"


def highlight_annotations(free_form_search_terms, terms_to_annotate):
    search_tokens = []
    for free_from_search_term in free_form_search_terms:
        search_tokens.extend(tokenize(free_from_search_term))
    folded_search_tokens = set([t.lower() for t in search_tokens])

    highlighted_terms = {}
    for term_to_annotate in terms_to_annotate:
        trimmed_term_str = trim_long_tokens(str(term_to_annotate))
        token_parts = tokenize_and_fold_for_highlight(trimmed_term_str)
        # looks like this: [(class_name, start, end), (class_name, start, end), ...]
        highlight_locations = []
        for tp in token_parts:
            token, start, end = tp
            if token in folded_search_tokens:
                # mark for green highlighting

                # only add if not overlapping
                if not_intersecting(highlight_locations, start, end):
                    highlight_locations.append(
                        ("highlight-green", start, end)
                    )  # use the CSS class

            else:
                for search_token in folded_search_tokens:
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
                                    "highlight-yellow",
                                    start + index,
                                    start + index + len(search_token),
                                )
                            )

        # now highlight the label string
        highlighted_term = ""
        if not highlight_locations:
            highlighted_term = trimmed_term_str
        else:
            for i, (class_name, start, end) in enumerate(highlight_locations):
                if i == 0:
                    highlighted_term += trimmed_term_str[:start]
                else:
                    highlighted_term += trimmed_term_str[
                        highlight_locations[i - 1][2] : start
                    ]
                highlighted_term += f'<span class="{class_name}">{trimmed_term_str[start:end]}</span>'  # use the CSS class
            highlighted_term += trimmed_term_str[end:]
        highlighted_terms[term_to_annotate] = highlighted_term
    return highlighted_terms


def not_intersecting(list_of_ranges, start, end):
    if not list_of_ranges:
        return True
    for r in list_of_ranges:
        if r[1] <= start <= r[2] or r[1] <= end <= r[2]:
            return False
    return True


def trim_long_tokens(text, limit=50):
    def trim(token):
        if len(token) > limit:
            token = token[: limit - 5] + "..."
        return token

    if text and len(text) > limit:
        return " ".join([trim(t) for t in text.split()])
    return text


def concat_labels(labels, linker=None):
    res = []
    for lbl in labels:
        url = linker(lbl) if linker else None
        if url:
            res.append(f'<a href="{url}" target="_blank">{trim_long_tokens(lbl)}</a>')
        else:
            res.append(trim_long_tokens(lbl))
    return "<br>".join(["&nbsp; <b>&#x2022;</b> &nbsp; " + t for t in res])


def shorten_and_concat_labels(labels):
    return concat_labels([trim_long_tokens(t) for t in labels])


def truncate(txt, charlim, include_length=False):
    if not isinstance(txt, str):
        txt = str(txt)
    if len(txt) <= charlim:
        return txt
    else:
        res = txt[: charlim - 2] + ".."
        if include_length:
            res += f"({len(txt)})"
        return res


def display(w):
    if isinstance(w, str):
        return w.replace("_", " ").title()
    elif isinstance(w, int):
        return "{:,}".format(w)
    elif isinstance(w, float):
        if w >= 10 or round(w) == w:
            return display(round(w))
        elif w <= 0.0:
            return w
        else:
            return round(w, 3 - int(floor(log10(abs(w)))) - 1)
    else:
        return w


def nanometer_to_flywire_coordinates(coordinates):
    coordinates = tokenize(coordinates)
    assert len(coordinates) == 3
    return (
        round(int(coordinates[0]) / 4),
        round(int(coordinates[1]) / 4),
        round(int(coordinates[2]) / 40),
    )


def nanos_to_formatted_micros(nanos, degree):
    divisor = pow(1000, degree)
    micros = round(nanos / divisor)
    return f"{display(micros)} &#181;m" + (f"<sup>{degree}</sup>" if degree > 1 else "")


def can_be_flywire_root_id(txt):
    try:
        txt = str(txt)
        return len(txt) == 18 and txt.startswith("72") and int(txt)
    except Exception:
        return False


def is_proper_textual_annotation(t):
    if isinstance(t, str):
        t = t.lower()
        return (
            any([c in t for c in string.ascii_lowercase]) and t not in UNDEFINED_THINGS
        )
    else:
        return False


def format_dict_by_largest_value(dct, top_k=1000000):
    return "\n".join(
        [
            f"   {k}: {v}"
            for k, v in sorted(dct.items(), key=lambda p: p[1], reverse=True)
        ][:top_k]
    )


def format_dict_by_key(dct):
    return "\n".join(
        [f"   {k}: {v}" for k, v in sorted(dct.items(), key=lambda p: p[0])]
    )
