import string
from collections import defaultdict
from unittest import TestCase

from src.configuration import TYPE_PREDICATES_METADATA
from src.data.visual_neuron_types import (
    VISUAL_NEURON_TYPES,
    VISUAL_NEURON_MEGA_TYPE_TO_TYPES,
)
from src.service.optic_lobe_types_catalog import assign_types_to_neurons, rewrite
from src.utils.formatting import format_dict_by_largest_value, format_dict_by_key
from src.utils.markers import extract_markers
from tests import get_testing_neuron_db


class OlCatalogTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def test_types_list(self):
        types_list = []
        for mt, tl in VISUAL_NEURON_MEGA_TYPE_TO_TYPES.items():
            types_list.extend(tl)

        self.assertEqual(sorted(types_list), sorted(VISUAL_NEURON_TYPES))
        self.assertEqual(len(types_list), len(set(types_list)))

        allowed_chars = string.ascii_letters + string.digits + "_-"
        for t in VISUAL_NEURON_TYPES:
            for c in t:
                self.assertTrue(c in allowed_chars, c)

    def test_rewrite(self):
        self.assertEqual("T1", rewrite("T1"))
        self.assertEqual("T1", rewrite("T1_L"))
        self.assertEqual("R1-6", rewrite("R1"))
        self.assertEqual("R1-6", rewrite("R1_L"))
        self.assertEqual("R7", rewrite("R7"))
        self.assertEqual("r7", rewrite("r7_r"))

    def test_assign_types_to_neurons(self):
        def make_map(labels):
            return {
                123: [{"label": lbl, "date_created": i} for i, lbl in enumerate(labels)]
            }

        def make_list(types):
            return {123: types}

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels_data=make_map(["Mi1"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels_data=make_map(["this is Mi 1"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"Mi1": [], "Unknown-labeled": [123], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels_data=make_map(["Mi2"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels_data=make_map(["Mi1_R"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"R1-6": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels_data=make_map(["R2"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["R1-6", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"R1-6": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels_data=make_map([]),
                rid_to_cell_types_list=make_list(["R1-6"]),
                target_type_list=["R1-6", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

    def test_ol_unknown_types(self):
        tag_counts = defaultdict(int)
        for nd in self.neuron_db.neuron_data.values():
            if "Unknown-labeled" in extract_markers(nd, "olr_type"):
                for lbl in nd["label"]:
                    if "#temp" in lbl:
                        tag_counts[lbl.split("; ")[1]] += 1
        if tag_counts:
            print(format_dict_by_largest_value(tag_counts))
            print("\n")
            print(format_dict_by_key(tag_counts))
            print("\n Missing from catalog:")
            print(
                '"'
                + '",\n"'.join(
                    sorted(
                        [t for t in tag_counts.keys() if t not in VISUAL_NEURON_TYPES]
                    )
                )
            )
            self.fail(f"Found {len(tag_counts)} OL tags not assigned to catalog types")

    def test_predicates(self):
        in_lengths, out_lengths = [], []
        for k, v in TYPE_PREDICATES_METADATA.items():
            in_lengths.append(len(v["predicate_input_types"]))
            out_lengths.append(len(v["predicate_output_types"]))
        print(max(in_lengths))
        print(max(out_lengths))

        types_with_predicate = [t for t, v in TYPE_PREDICATES_METADATA.items() if v["f_score"] >= 0.9]
        for t1 in types_with_predicate:
            for t2 in types_with_predicate:
                if t1 == t2:
                    continue

                t1_to_t2 = set(TYPE_PREDICATES_METADATA[t1]["false_negatives"]).intersection(set(TYPE_PREDICATES_METADATA[t2]["false_positives"]))
                if t1_to_t2:
                    print(f"{t1} -> {t2}: {sorted(t1_to_t2)}")
