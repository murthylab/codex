import string
from itertools import zip_longest

from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.utils.formatting import make_web_safe, can_be_flywire_root_id

# removes left/right hemisphere annotations (this might be inaccurate due to left/right inversion problem from May 2023)
def remove_left_right(lbl):
    lbl_words = lbl.split()
    clean_words = []
    for w in lbl_words:
        w = w.strip()
        for bt in [
            "_left",
            "_right",
            "left_",
            "right_",
            "left",
            "right",
            "Left",
            "Right",
            "-RHS",
            "-LHS",
        ]:
            w = w.replace(bt, "")
        for delim in [";", ":", ",", "_", "-"]:
            for bt in ["_l", "_r", "-l", "-r"]:
                w = w.replace(f"{bt}{delim}", delim)
                w = w.replace(f"{bt.upper()}{delim}", delim)
                if w.endswith(bt) or w.endswith(bt.upper()):
                    w = w[: -len(bt)]
        if w:
            clean_words.append(w)
    res = " ".join(clean_words)
    # if res != lbl:
    #    print(f"{lbl} ----> {res}")
    return res


# dedupes identical parts of the label
def remove_duplicate_tokens(lbl, delim):
    tokens = [t.strip() for t in lbl.split(delim)]
    tokens = [t for t in tokens if t]
    seen_set = set()
    new_tokens = []
    for t in tokens:
        if t not in seen_set:
            seen_set.add(t)
            new_tokens.append(t)
    res = f"{delim} ".join(new_tokens)
    # if res != lbl:
    #    print(f"{lbl} ----> {res}")
    return res


# removes parts that are subsumed in the rest of the label (e.g. "LC10; LC10 neuron;" -> "LC10 neuron")
def remove_subsumed_tokens(lbl, delim):
    tokens = [t.strip() for t in lbl.split(delim)]
    tokens = [t for t in tokens if t]
    new_tokens = []
    for i, t in enumerate(tokens):
        if i < len(tokens) - 1:
            next_token = tokens[i + 1]
            if (
                next_token.startswith(f"{t}:")
                or next_token.endswith(f" {t}")
                or f" {t}," in next_token
                or f" {t};" in next_token
            ):
                continue
        new_tokens.append(t)
    res = f"{delim} ".join(new_tokens)
    return res


# shortens labels
def compact_label(label):
    parts_to_hide = [
        "; Part of comprehensive neck connective tracing, contact Connectomics Group Cambridge for more detailed "
        "information on descending/ascending neurons",
        " (total brain fart (not part of the name of the neuron))",
        "Taisz ... Galili 2022 doi:10.1101/2022.05.13.491877",
        "; https://doi.org/10.1101/2021.12.20.473513",
    ]
    for p in parts_to_hide:
        label = label.replace(p, "")
    return label


# filters out labels that repeat other attributes of the neuron
def remove_redundant_parts(labels, neuron_data):
    attribs_lc = set(
        [
            attrib.lower()
            for attrib in (
                [
                    neuron_data[k]
                    for k in [
                        "nt_type",
                        "flow",
                        "super_class",
                        "class",
                        "sub_class",
                        "hemilineage",
                        "side",
                        "nerve",
                    ]
                ]
                + neuron_data["cell_type"]
                + neuron_data["hemibrain_type"]
                + [NEURO_TRANSMITTER_NAMES.get(neuron_data["nt_type"])]
            )
            if attrib
        ]
    )

    res = [
        ";".join(
            [
                part
                for part in label.split(";")
                if part.lower().strip() not in attribs_lc
            ]
        ).strip()
        for label in labels
    ]
    return [lbl for lbl in res if lbl]


# removes all labels older than correction.
def remove_corrected(labels_latest_to_oldest):
    correction_prefixes = [
        "Correction: ",
        "(correction) ",
        "Tm16 is wrong. this is: ",
        "L1 label is wrong",
    ]
    for cp in correction_prefixes:
        for i, lbl in enumerate(labels_latest_to_oldest):
            if lbl.startswith(cp):
                return labels_latest_to_oldest[:i] + [lbl[len(cp) :]]

    correction_suffixes = [
        " (correction)",
        " (corrected)",
        " - L1 Label Incorrect",
        " - L2 Label Incorrect",
        " - R2 Label Incorrect (spelling error)",
        "; L5 label is incorrect",
        "; L1 - Lamina monopolar 3; L3 is incorrect and submitted by accident",
        " (I just pasted a segment ID here and accidentally submitted. sorry)",
    ]
    for cp in correction_suffixes:
        for i, lbl in enumerate(labels_latest_to_oldest):
            if lbl.endswith(cp):
                return labels_latest_to_oldest[:i] + [lbl[: -len(cp)]]

    return labels_latest_to_oldest


# labels we want to exclude (non-informative wrt all other corrections)
def blacklisted(lbl):
    blacklisted_labels = {"not a neuron", "correction - not optic lobe"}
    return lbl.lower() in blacklisted_labels or can_be_flywire_root_id(lbl)


def significant_diff_chars(str1, str2):
    res = set()
    for c in zip_longest(str1, str2):
        if c[0] != c[1]:
            res.add(c[0])
            res.add(c[1])
    return not res.issubset({"'", "`", ".", ",", "-", "_", ":", ";", " ", None})


def dedupe_up_to_insignificant_chars(labels):
    if len(labels) < 2:
        return labels
    dupe_indices = []
    for i, lbl1 in enumerate(labels):
        for j, lbl2 in enumerate(labels):
            if j > i:
                if not significant_diff_chars(lbl1, lbl2):
                    dupe_indices.append(j)
    if dupe_indices:
        labels = [lbl for i, lbl in enumerate(labels) if i not in dupe_indices]
    return labels


def dedupe_prefixes(labels):
    if len(labels) < 2:
        return labels
    alphanum_ = string.digits + string.ascii_letters + "_"
    dupe_indices = []
    for i, lbl1 in enumerate(labels):
        for j, lbl2 in enumerate(labels):
            if len(lbl1) > len(lbl2) and lbl1.startswith(lbl2):
                sep_char = lbl1[len(lbl2)]
                if sep_char not in alphanum_:
                    dupe_indices.append(j)
    if dupe_indices:
        # print(f"{labels} -->")
        labels = [lbl for i, lbl in enumerate(labels) if i not in dupe_indices]
        # print(f"--> {labels}")
    return labels


def clean_and_reduce_labels(labels_latest_to_oldest, neuron_data):
    labels = [make_web_safe(compact_label(lbl)) for lbl in labels_latest_to_oldest]
    labels = [lbl for lbl in labels if not blacklisted(lbl)]
    labels = remove_redundant_parts(labels, neuron_data)
    labels = remove_corrected(labels)
    labels = [remove_left_right(lbl) for lbl in labels if lbl]

    labels = [remove_duplicate_tokens(lbl, ";") for lbl in labels if lbl]
    labels = [remove_duplicate_tokens(lbl, ",") for lbl in labels if lbl]
    labels = [remove_subsumed_tokens(lbl, ";") for lbl in labels if lbl]
    labels = [remove_subsumed_tokens(lbl, ",") for lbl in labels if lbl]
    # remove redundant once more (after the round of corrections)
    labels = remove_redundant_parts(labels, neuron_data)
    labels = sorted(set([lbl for lbl in labels if lbl]))
    labels = dedupe_up_to_insignificant_chars(labels)
    labels = dedupe_prefixes(labels)

    return labels
