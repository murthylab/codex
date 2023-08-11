import json
from collections import defaultdict

from src.configuration import TYPE_PREDICATES_METADATA
from src.data.local_data_loader import write_csv
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.markers import extract_markers
from itertools import chain, combinations


class OlrPredicatesGenerator(object):
    def __init__(
        self,
        neuron_db,
        verbose=False,
        up_threshold=0.4,
        down_threshold=0.4,
        max_set_size=5,
    ):
        self.verbose = verbose
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self.max_set_size = max_set_size

        ins, outs = neuron_db.input_output_partner_sets()

        self.rid_to_olr_type = {}
        self.olr_type_to_rid_lists = defaultdict(list)
        for rid, nd in neuron_db.neuron_data.items():
            for mrk in extract_markers(nd, "olr_type"):
                assert rid not in self.rid_to_olr_type
                self.rid_to_olr_type[rid] = mrk
                self.olr_type_to_rid_lists[mrk].append(rid)
        self.dbg(f"Collected {len(self.rid_to_olr_type)} with OLR types")

        self.in_type_projections = {}
        self.out_type_projections = {}
        for root_id in self.rid_to_olr_type.keys():
            self.in_type_projections[root_id] = set(
                [
                    self.rid_to_olr_type[rid]
                    for rid in ins[root_id]
                    if rid in self.rid_to_olr_type
                    and not self.rid_to_olr_type[rid].startswith("Unknown")
                ]
            )
            self.out_type_projections[root_id] = set(
                [
                    self.rid_to_olr_type[rid]
                    for rid in outs[root_id]
                    if rid in self.rid_to_olr_type
                    and not self.rid_to_olr_type[rid].startswith("Unknown")
                ]
            )

        self.upstream_types_count_for_type = {}
        self.downstream_types_count_for_type = {}
        for tp, tp_rid_list in self.olr_type_to_rid_lists.items():
            (
                upstream_types_count,
                downstream_types_count,
            ) = self.count_upstream_downstream_types(tp_rid_list)
            self.upstream_types_count_for_type[tp] = upstream_types_count
            self.downstream_types_count_for_type[tp] = downstream_types_count

    def dbg(self, msg):
        if self.verbose:
            print(msg)

    def olr_types(self):
        return sorted(self.olr_type_to_rid_lists.keys())

    def predicate_matching_cells(
        self,
        types_downstream,
        types_upstream,
    ):
        matching_cells = []
        for rid, tp in self.rid_to_olr_type.items():
            if types_downstream.issubset(
                self.out_type_projections[rid]
            ) and types_upstream.issubset(self.in_type_projections[rid]):
                matching_cells.append(rid)
        return matching_cells

    @staticmethod
    def compute_predicate_data(true_list, matching_cells):
        matching_cells_set = set(matching_cells)
        assert len(matching_cells) == len(matching_cells_set)

        true_positive_set = matching_cells_set.intersection(true_list)
        false_positive_set = matching_cells_set - true_positive_set
        false_negative_set = set(true_list) - true_positive_set

        precision = len(true_positive_set) / (len(matching_cells_set) or 1)
        recall = len(true_positive_set) / (len(true_list) or 1)
        f_score = (2 * precision * recall) / (precision + recall or 1)

        return {
            "precision": precision,
            "recall": recall,
            "f_score": f_score,
            "true_positives": sorted(true_positive_set),
            "false_positives": sorted(false_positive_set),
            "false_negatives": sorted(false_negative_set),
        }

    @staticmethod
    def all_up_down_type_subsets(predicate_types_up, predicate_types_down):
        def powerset(iterable):
            "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
            s = list(iterable)
            return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))

        def subsets(s):
            return map(set, powerset(s))

        for up_sset in subsets(predicate_types_up):
            for dn_sset in subsets(predicate_types_down):
                yield up_sset, dn_sset

    def find_best_predicate_for_type(self, target_olr_type):
        tp_rid_list = self.olr_type_to_rid_lists[target_olr_type]
        upstream_types_count = self.upstream_types_count_for_type[target_olr_type]
        downstream_types_count = self.downstream_types_count_for_type[target_olr_type]
        self.dbg(
            f"Finding the best predicate for {target_olr_type} with {len(tp_rid_list)} cells"
        )
        return self.find_best_predicate_for_list(
            tp_rid_list, upstream_types_count, downstream_types_count
        )

    def find_best_predicate_for_list(
        self,
        cell_ids,
        upstream_types_count=None,
        downstream_types_count=None,
        min_score=0.5,
        optimization_metric="f_score",
    ):
        if upstream_types_count is None and downstream_types_count is None:
            (
                upstream_types_count,
                downstream_types_count,
            ) = self.count_upstream_downstream_types(cell_ids)

        result = {
            "cells": len(cell_ids),
            "all_input_types": sorted(upstream_types_count.keys()),
            "all_output_types": sorted(downstream_types_count.keys()),
            "predicate_input_types": [],
            "predicate_output_types": [],
            "precision": 0,
            "recall": 0,
            "f_score": 0,
            "true_positives": [],
            "false_positives": [],
            "false_negatives": [],
        }
        if not downstream_types_count and not upstream_types_count:
            self.dbg("No up/down type counts, can't make a predicate")
            return result

        predicate_types_down = set()
        predicate_types_up = set()

        for p in sorted(downstream_types_count.items(), key=lambda x: -x[1]):
            if (
                len(predicate_types_down) < self.max_set_size
                and p[1] / len(cell_ids) > self.down_threshold
            ):
                predicate_types_down.add(p[0])
        for p in sorted(upstream_types_count.items(), key=lambda x: -x[1]):
            if (
                len(predicate_types_up) < self.max_set_size
                and p[1] / len(cell_ids) > self.up_threshold
            ):
                predicate_types_up.add(p[0])

        if not predicate_types_down and not predicate_types_up:
            self.dbg(
                f"No up/down type counts above threshold of {self.up_threshold} / {self.down_threshold}, can't make a predicate"
            )
            return result

        best_predicate_data = None

        self.dbg(
            f"Predicate types down/up: {len(predicate_types_down)} / {len(predicate_types_up)}"
        )
        for up_types, down_types in self.all_up_down_type_subsets(
            predicate_types_up, predicate_types_down
        ):
            matching_cells = self.predicate_matching_cells(
                types_downstream=down_types,
                types_upstream=up_types,
            )

            predicate_data = self.compute_predicate_data(
                true_list=cell_ids,
                matching_cells=matching_cells,
            )
            if predicate_data[optimization_metric] < min_score:
                continue

            predicate_data["predicate_input_types"] = sorted(up_types)
            predicate_data["predicate_output_types"] = sorted(down_types)

            if (
                best_predicate_data is None
                or predicate_data[optimization_metric]
                > best_predicate_data[optimization_metric]
                or (
                    predicate_data[optimization_metric]
                    == best_predicate_data[optimization_metric]
                    and (
                        len(predicate_data["predicate_input_types"])
                        + len(predicate_data["predicate_output_types"])
                    )
                    < (
                        len(best_predicate_data["predicate_input_types"])
                        + len(best_predicate_data["predicate_output_types"])
                    )
                )
            ):
                best_predicate_data = predicate_data
        self.dbg(f"best predicate data: {best_predicate_data}")

        if best_predicate_data:
            result.update(best_predicate_data)
        return result

    def count_upstream_downstream_types(self, rid_list):
        upstream_types_count = defaultdict(int)
        downstream_types_count = defaultdict(int)
        for rid in rid_list:
            for drid_type in self.out_type_projections[rid]:
                downstream_types_count[drid_type] += 1
            for urid_type in self.in_type_projections[rid]:
                upstream_types_count[urid_type] += 1
        return dict(upstream_types_count), dict(downstream_types_count)


def generate_predicates():
    olr_predicates_generator = OlrPredicatesGenerator(
        neuron_db=NeuronDataFactory.instance().get()
    )

    predictions_table_columns = [
        "type",
        "cells",
        "predicate_input_types",
        "predicate_output_types",
        "precision",
        "recall",
        "f_score",
    ]
    prediction_rows = [predictions_table_columns]
    prediction_json = {}

    def add_row(olr_type, dct):
        prediction_rows.append(
            [olr_type] + [str(dct[c]) for c in predictions_table_columns[1:]]
        )

    olr_types = olr_predicates_generator.olr_types()
    for tp in olr_types:
        predictions_dict = olr_predicates_generator.find_best_predicate_for_type(tp)
        add_row(tp, predictions_dict)
        prediction_json[tp] = predictions_dict
        print(f"{len(prediction_rows) - 1} / {len(olr_types)}: {prediction_rows[-1]}")

    write_csv(
        filename="static/experimental_data/type_predicates.csv", rows=prediction_rows
    )
    with open("src/data/type_predicates.json", "w") as f:
        json.dump(prediction_json, fp=f, indent=2)


def generate_correction_suggestions():
    in_lengths, out_lengths = [], []
    for k, v in TYPE_PREDICATES_METADATA.items():
        in_lengths.append(len(v["predicate_input_types"]))
        out_lengths.append(len(v["predicate_output_types"]))
    print(max(in_lengths))
    print(max(out_lengths))

    types_with_predicate = [
        t for t, v in TYPE_PREDICATES_METADATA.items() if v["f_score"] >= 0.9
    ]
    for t1 in types_with_predicate:
        for t2 in types_with_predicate:
            if t1 == t2:
                continue

            t1_to_t2 = set(
                TYPE_PREDICATES_METADATA[t1]["false_negatives"]
            ).intersection(set(TYPE_PREDICATES_METADATA[t2]["false_positives"]))
            if t1_to_t2:
                print(f"{t1} -> {t2}: {sorted(t1_to_t2)}")


if __name__ == "__main__":
    generate_predicates()
    generate_correction_suggestions()
