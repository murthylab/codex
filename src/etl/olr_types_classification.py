from collections import defaultdict
from src.utils.formatting import percentage
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.markers import extract_markers


def predicate_matching_cell_types(
    in_type_projections,
    out_type_projections,
    rid_to_olr_type,
    types_downstream,
    types_upstream,
):
    matching_type_counts = defaultdict(int)
    for rid, tp in rid_to_olr_type.items():
        if types_downstream.issubset(
            out_type_projections[rid]
        ) and types_upstream.issubset(in_type_projections[rid]):
            matching_type_counts[tp] += 1
    return matching_type_counts


def compute_f_score(olr_type, olr_type_size, predicate_matching_types):
    predicate_total = sum(predicate_matching_types.values())

    true_positive = predicate_matching_types[olr_type]
    false_positive = predicate_total - true_positive
    false_negative = olr_type_size - true_positive

    return (2 * true_positive) / (2 * true_positive + false_positive + false_negative)


def classify_types_connectivity(
    rid_to_olr_type,
    tp_rid_lists,
    in_type_projections,
    out_type_projections,
    down_threshold,
    up_threshold,
):
    f_score_and_size = []
    correct_predictions = 0
    for tp in sorted(set(rid_to_olr_type.values())):
        upstream_types_count = defaultdict(int)
        downstream_types_count = defaultdict(int)
        tp_rid_list = tp_rid_lists[tp]
        for rid in tp_rid_list:
            for drid_type in out_type_projections[rid]:
                downstream_types_count[drid_type] += 1
            for urid_type in in_type_projections[rid]:
                upstream_types_count[urid_type] += 1

        predicate_types_down = set()
        predicate_types_up = set()

        for p in sorted(downstream_types_count.items(), key=lambda x: -x[1]):
            if p[1] / len(tp_rid_list) > down_threshold:
                # print(f"  o {percentage(p[1], len(tp_rid_list))} of cells have downstream partner of type {p[0]}")
                predicate_types_down.add(p[0])
        for p in sorted(upstream_types_count.items(), key=lambda x: -x[1]):
            if p[1] / len(tp_rid_list) > up_threshold:
                # print(f"  x {percentage(p[1], len(tp_rid_list))} of cells have upstream partner of type {p[0]}")
                predicate_types_up.add(p[0])

        if predicate_types_down or predicate_types_up:
            # print(f"Predicate types down/up: {len(predicate_types_down)} / {len(predicate_types_up)}")
            matching_types = predicate_matching_cell_types(
                in_type_projections,
                out_type_projections,
                rid_to_olr_type,
                predicate_types_down,
                predicate_types_up,
            )

            # print(format_dict_by_largest_value(matching_types, top_k=3))
            correct_predictions += matching_types[tp]
            f_score = compute_f_score(tp, len(tp_rid_list), matching_types)
            # print(f"F score: {f_score}")
        else:
            # print("No common types above threshold down/up")
            f_score = 0

        tot_f_score = sum([p[0] * p[1] for p in f_score_and_size])
        avg_f_score = tot_f_score / max(1, sum([p[1] for p in f_score_and_size]))
        # print(f"{tp}: {len(tp_rid_list)} cells, {len(predicate_types_down) + len(predicate_types_up)} predicates, f-score {f_score} (avg. f-score: {avg_f_score})")
        f_score_and_size.append((f_score, len(tp_rid_list)))

    tot_f_score = sum([p[0] * p[1] for p in f_score_and_size])
    avg_f_score = tot_f_score / max(1, sum([p[1] for p in f_score_and_size]))
    med_f_score = sorted(f_score_and_size, key=lambda p: p[0])[
        round(len(f_score_and_size) / 2)
    ]
    print(
        f"{down_threshold}/{up_threshold}: avg. f-score: {avg_f_score}, median f-score: {med_f_score}, correct: {percentage(correct_predictions, len(rid_to_olr_type))}"
    )


def run():
    neuron_db = NeuronDataFactory.instance().get()
    rid_to_olr_type = {}
    tp_rid_lists = defaultdict(list)
    for rid, nd in neuron_db.neuron_data.items():
        for mrk in extract_markers(nd, "olr_type"):
            if not mrk.lower().startswith("unknown"):
                assert rid not in rid_to_olr_type
                rid_to_olr_type[rid] = mrk
                tp_rid_lists[mrk].append(rid)
    print(f"Collected {len(rid_to_olr_type)} with OLR types")

    ins, outs = neuron_db.input_output_partner_sets()

    in_type_projections = {}
    out_type_projections = {}
    for root_id in rid_to_olr_type.keys():
        in_type_projections[root_id] = set(
            [rid_to_olr_type[rid] for rid in ins[root_id] if rid in rid_to_olr_type]
        )
        out_type_projections[root_id] = set(
            [rid_to_olr_type[rid] for rid in outs[root_id] if rid in rid_to_olr_type]
        )

    for dt in [0.9, 0.91, 0.92, 0.93, 0.94, 0.95]:
        for ut in [0.9, 0.91, 0.92, 0.93, 0.94, 0.95]:
            classify_types_connectivity(
                rid_to_olr_type,
                tp_rid_lists,
                in_type_projections,
                out_type_projections,
                dt,
                ut,
            )


if __name__ == "__main__":
    run()
