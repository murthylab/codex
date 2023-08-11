from src.configuration import DM3_SUBTYPES
from src.data.visual_neuron_types import VISUAL_NEURON_TYPES
from src.utils.parsing import tokenize

LABEL_DELIMS = [",", ";", ":", "(", ")", "/"]
UPDATED_TYPES_LC = {f"r{i}": "R1-6" for i in range(1, 7)}
UPDATED_TYPES_LC["mi8"] = "Mi9"
UPDATED_TYPES_LC["tmy(new)1"] = "TmY1_new"


RIGHT_OL_REGIONS = {"AME_R", "LA_R", "LO_R", "LOP_R", "ME_R"}
UNASSIGNED_REGION = "UNASGD"
MAX_PERCENT_SYNAPSES_OUTSIDE_OLR_REGIONS = 5


def is_ol_right_by_synapse_regions(
    ndata, in_regions_synapse_counts, out_regions_synapse_counts
):
    if ndata["class"] == "bilateral" or ndata["super_class"] not in [
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

    # known not to be neurons
    if ndata["root_id"] in [
        720575940645930862,
        720575940637141605,
        720575940607725954,
        720575940628656636,
        720575940630246393,
        720575940627196291,
        720575940611929237,
        720575940635860087,
        720575940615593282,
        720575940615953932,
        720575940637856489,
        720575940615599035,
        720575940644573896,
        720575940641082064,
        720575940624481308,
        720575940607871666,
        720575940621555565,
        720575940625077483,
        720575940628164457,
        720575940606249318,
        720575940617860411,
        720575940610915186,
        720575940612223962,
        720575940639387763,
        720575940620451425,
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


def has_exclude_label(nd):
    return any([lbl.startswith("#exclude") for lbl in nd["label"]])


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


def assign_types_to_neurons(
    rid_to_labels, rid_to_cell_types_list, target_type_list, input_partner_sets
):
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

    # TODO: remove this once Dm3 subtypes are labeled
    dm3_subtypes = {}
    for dm3_subtype, rids in DM3_SUBTYPES.items():
        accepted_set = set()
        for rid in rids:
            tp = neuron_to_type.get(rid)
            if tp == "Dm3":
                neuron_to_type[rid] = dm3_subtype
                accepted_set.add(rid)
            else:
                print(
                    f"Dm3 subtype {dm3_subtype}: rid {rid} is of type {tp}, expecting Dm3"
                )
        dm3_subtypes[dm3_subtype] = accepted_set
    # split TmY9 into subsets based on Dm3 subsets
    tmy9_rids = [rid for rid, tp in neuron_to_type.items() if tp == "TmY9"]
    for rid in tmy9_rids:
        p_ins = len(input_partner_sets[rid].intersection(dm3_subtypes["Dm3p"]))
        q_ins = len(input_partner_sets[rid].intersection(dm3_subtypes["Dm3q"]))
        if p_ins > q_ins or q_ins > p_ins:
            if p_ins > q_ins:
                neuron_to_type[rid] = "TmY9q"
            else:
                neuron_to_type[rid] = "TmY9p"
        else:
            print(
                f"No or equal input distribution of TmY9 cell {rid}: {p_ins=} {q_ins=}"
            )

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
    input_partner_sets, _ = neuron_db.input_output_partner_sets()

    # collect all types (even if undefined) for olr neurons
    olr_neuron_rid_list = [
        nd["root_id"]
        for nd in neuron_db.neuron_data.values()
        if is_ol_right_by_synapse_regions(nd, ins, outs) and not has_exclude_label(nd)
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
        input_partner_sets=input_partner_sets,
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
        input_partner_sets=input_partner_sets,
    )
    # exclude unknowns for non olr
    non_olr_type_list = {
        k: v
        for k, v in non_olr_type_list.items()
        if not k.lower().startswith("unknown")
    }

    return olr_type_lists, non_olr_type_list
