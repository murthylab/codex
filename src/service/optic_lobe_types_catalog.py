from src.data.visual_neuron_types import VISUAL_NEURON_TYPES
from src.utils.parsing import tokenize

LABEL_DELIMS = [",", ";", ":", "(", ")", "/"]
UPDATED_TYPES_LC = {f"r{i}": "R1-6" for i in range(1, 7)}
UPDATED_TYPES_LC["mi8"] = "Mi9"


RIGHT_OL_REGIONS = {"AME_R", "LA_R", "LO_R", "LOP_R", "ME_R"}
UNASSIGNED_REGION = "UNASGD"
MAX_PERCENT_SYNAPSES_OUTSIDE_OLR_REGIONS = 5


def is_ol_right_by_synapse_regions(
    ndata, in_regions_synapse_counts, out_regions_synapse_counts
):
    if ndata["side"] != "right" or ndata["super_class"] not in [
        "optic",
        "sensory",
    ]:
        return False

    # from sensory we only take these two mislabeled cells (suggested by Szi-chieh). Exclude the retinula axons for now.
    if ndata["super_class"] == "sensory" and ndata["root_id"] not in [
        720575940626605630,
        720575940627333465,
    ]:
        return False

    # check how many synapses vs allowed outside OLR regions
    if MAX_PERCENT_SYNAPSES_OUTSIDE_OLR_REGIONS:
        synapse_regions = set(ndata["input_neuropils"]) | set(ndata["output_neuropils"])
        if not synapse_regions.intersection(RIGHT_OL_REGIONS):
            return False
        total_syn_count, non_olr_syn_count = 0, 0
        for pil, cnt in in_regions_synapse_counts[ndata["root_id"]].items():
            total_syn_count += cnt
            if pil != UNASSIGNED_REGION and pil not in RIGHT_OL_REGIONS:
                non_olr_syn_count += cnt
        for pil, cnt in out_regions_synapse_counts[ndata["root_id"]].items():
            total_syn_count += cnt
            if pil != UNASSIGNED_REGION and pil not in RIGHT_OL_REGIONS:
                non_olr_syn_count += cnt
        return (
            non_olr_syn_count * 100 / total_syn_count
        ) <= MAX_PERCENT_SYNAPSES_OUTSIDE_OLR_REGIONS
    else:
        syn_regions = (
            set(ndata["input_neuropils"]) | set(ndata["output_neuropils"])
        ) - {UNASSIGNED_REGION}
        return syn_regions and syn_regions.issubset(RIGHT_OL_REGIONS)


# This used to be the previous definer for target set. But it contained many unconnected cells + bilateral and
# projection/centrifugal cells. So instead we now use regions.
def is_ol_right_neuron_by_annotations(nd):
    return nd["super_class"] == "optic" and nd["side"] == "right"


def rewrite(t):
    return UPDATED_TYPES_LC.get(t.replace("`", "").lower(), t)


def infer_ol_type(labels, types_list, target_type_list, unknown_labels):
    for lbl in labels:
        tokens = [rewrite(t) for t in tokenize(lbl, LABEL_DELIMS)]
        tokens_lower = [t.lower() for t in tokens]
        for t_lower in tokens_lower:
            for olt in target_type_list:
                if t_lower == olt.lower():
                    return olt

        # try consecutive token pairs (e.g. L 5 -> L5)
        for i, t in enumerate(tokens):
            if i < len(tokens) - 1:
                ctoken = t + tokens[i + 1]
                if ctoken in target_type_list:
                    if ctoken not in ["R1-6"]:  # known concatenations
                        print(
                            f"Caution: inferred {ctoken} by concatenating to {t + tokens[i + 1]}: {lbl}"
                        )
                    return ctoken

    for lbl in labels:
        unknown_labels.add(lbl)

    if types_list:
        # try to infer by cell / hemibrain type
        matched_types = []
        target_types_lc_no_spaces = {
            t.lower().replace(" ", ""): t for t in target_type_list
        }
        for t in types_list:
            matched_type = target_types_lc_no_spaces.get(t.lower().replace(" ", ""))
            if matched_type:
                matched_types.append(matched_type)
        if len(set(matched_types)) == 1:
            # print(f"Inferred {matched_types[0]} from types: {types_list}")
            return matched_types[0]
        elif len(set(matched_types)) > 1:
            print(
                f"WARNING!!! Inferred multiple: {matched_types} from types: {types_list}"
            )

    return "Unknown-labeled" if labels else "Unknown-not-labeled"


def assign_types_to_neurons(rid_to_labels, rid_to_cell_types_list, target_type_list):
    unknown_labels = set()
    neuron_to_type = {
        rid: infer_ol_type(
            labels=labels,
            types_list=rid_to_cell_types_list[rid],
            target_type_list=target_type_list,
            unknown_labels=unknown_labels,
        )
        for rid, labels in rid_to_labels.items()
    }

    if unknown_labels:
        print(f"\nUnknown labels: {len(unknown_labels)}")
        for ul in list(unknown_labels)[:5]:
            print(ul)

    type_to_neurons_list = {t: [] for t in target_type_list}
    for k, v in neuron_to_type.items():
        type_to_neurons_list[v].append(k)

    return type_to_neurons_list


def assign_types_for_right_optic_lobe_catalog(neuron_db):
    ins, outs = neuron_db.input_output_regions_with_synapse_counts()

    # collect all types (even if undefined) for olr neurons
    olr_neuron_rid_list = [
        nd["root_id"]
        for nd in neuron_db.neuron_data.values()
        if is_ol_right_by_synapse_regions(nd, ins, outs)
    ]

    print(f"Identified {len(olr_neuron_rid_list)} neurons in the OL Right side")
    olr_type_lists = assign_types_to_neurons(
        rid_to_labels={
            rid: neuron_db.get_neuron_data(rid)["label"] for rid in olr_neuron_rid_list
        },
        rid_to_cell_types_list={
            rid: neuron_db.get_all_cell_types(rid) for rid in olr_neuron_rid_list
        },
        target_type_list=list(VISUAL_NEURON_TYPES),
    )

    # collect types for non-olr neurons that were successfully mapped to OL type
    def non_olr_labeled(nd):
        return neuron_db.get_label_data(
            nd["root_id"]
        ) and not is_ol_right_by_synapse_regions(nd, ins, outs)

    non_olr_neuron_rid_list = [
        nd["root_id"] for nd in neuron_db.neuron_data.values() if non_olr_labeled(nd)
    ]
    non_olr_type_list = assign_types_to_neurons(
        rid_to_labels={
            rid: neuron_db.get_neuron_data(rid)["label"]
            for rid in non_olr_neuron_rid_list
        },
        rid_to_cell_types_list={
            rid: neuron_db.get_all_cell_types(rid) for rid in non_olr_neuron_rid_list
        },
        target_type_list=list(VISUAL_NEURON_TYPES),
    )
    # exclude unknowns for non olr
    non_olr_type_list = {
        k: v
        for k, v in non_olr_type_list.items()
        if not k.lower().startswith("unknown")
    }

    return olr_type_lists, non_olr_type_list
