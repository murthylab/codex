from src.data.visual_neuron_types import VISUAL_NEURON_TYPES
from src.utils.parsing import tokenize


def assign_types_to_neurons(rid_to_labels_data, target_type_list):
    delims = [",", ";", ":", "(", ")", "/"]
    unknown_labels = set()

    def infer_ol_type(label_data):
        if not label_data:
            return "Unknown-not-labeled"
        labels_latest_to_oldest = sorted(
            label_data, key=lambda x: x["date_created"], reverse=True
        )

        for lbl in labels_latest_to_oldest:
            tokens_lower = [t.lower() for t in tokenize(lbl["label"], delims)]
            for olt in target_type_list:
                olt_lower = olt.lower()
                for i, t_lower in enumerate(tokens_lower):
                    if t_lower == olt_lower:
                        return olt

        # try consecutive token pairs (e.g. L 5 -> L5)
        for lbl in labels_latest_to_oldest:
            tokens = tokenize(lbl["label"], delims)
            for olt in target_type_list:
                for i, t in enumerate(tokens):
                    if i < len(tokens) - 1 and t + tokens[i + 1] == olt:
                        print(
                            f"Caution: inferred {olt} by concatenating to {t + tokens[i + 1]}: {lbl}"
                        )
                        return olt

        for lbl in labels_latest_to_oldest:
            unknown_labels.add(lbl["label"])
        return "Unknown-labeled"

    neuron_to_type = {
        rid: infer_ol_type(label_data) for rid, label_data in rid_to_labels_data.items()
    }

    if unknown_labels:
        print(f"\nUnknown labels: {len(unknown_labels)}")
        for ul in list(unknown_labels)[:5]:
            print(ul)

    type_to_neurons_list = {t: [] for t in target_type_list}
    for k, v in neuron_to_type.items():
        type_to_neurons_list[v].append(k)

    return type_to_neurons_list


def is_ol_right(nd):
    return nd["super_class"] == "optic" and nd["side"] == "right"


def assign_types_for_right_optic_lobe_catalog(neuron_db):
    # collect all types (even if undefined) for olr neurons
    olr_neuron_rid_list = [
        nd["root_id"] for nd in neuron_db.neuron_data.values() if is_ol_right(nd)
    ]

    print(f"Identified {len(olr_neuron_rid_list)} neurons in the OL Right side")
    olr_type_lists = assign_types_to_neurons(
        rid_to_labels_data={
            rid: neuron_db.get_label_data(rid) for rid in olr_neuron_rid_list
        },
        target_type_list=list(VISUAL_NEURON_TYPES),
    )

    # collect types for non-olr neurons that were successfully mapped to OL type
    def non_olr_labeled(nd):
        return neuron_db.get_label_data(nd["root_id"]) and not is_ol_right(nd)

    non_olr_neuron_rid_list = [
        nd["root_id"] for nd in neuron_db.neuron_data.values() if non_olr_labeled(nd)
    ]
    non_olr_type_list = assign_types_to_neurons(
        rid_to_labels_data={
            rid: neuron_db.get_label_data(rid) for rid in non_olr_neuron_rid_list
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
