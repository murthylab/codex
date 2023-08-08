import string
from collections import defaultdict
from unittest import TestCase

from src.configuration import TYPE_PREDICATES_METADATA
from src.data.visual_neuron_types import (
    VISUAL_NEURON_TYPES,
    VISUAL_NEURON_MEGA_TYPE_TO_TYPES,
)
from src.etl.olr_types_classification import OlrPredicatesGenerator
from src.service.optic_lobe_types_catalog import (
    assign_types_to_neurons,
    rewrite,
)
from src.utils.formatting import (
    format_dict_by_largest_value,
    format_dict_by_key,
    percentage,
)
from src.utils.markers import extract_markers, extract_at_most_one_marker
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
        self.assertEqual("T1; L", rewrite("T1; L"))
        self.assertEqual("R1-6", rewrite("R1"))
        self.assertEqual("R1-6", rewrite("R3"))
        self.assertEqual("R7", rewrite("R7"))
        self.assertEqual("r7", rewrite("r7"))

    def test_assign_types_to_neurons(self):
        def make_map(labels):
            return {123: labels}

        def make_list(types):
            return {123: types}

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["Mi1"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["this is Mi 1"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"Mi1": [], "Unknown-labeled": [123], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["Mi2"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["Mi1; R"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"R1-6": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["R2"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["R1-6", "Unknown-labeled", "Unknown-not-labeled"],
            ),
        )

        self.assertEqual(
            {"R1-6": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map([]),
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

    def test_incorrect_types(self):
        def all_labels(rid):
            res = []
            for lbl in sorted(
                self.neuron_db.get_label_data(rid) or [],
                key=lambda x: x["date_created"],
                reverse=True,
            ):
                res.append(lbl["label"])
            return res

        failed = False
        for rid, nd in self.neuron_db.neuron_data.items():
            for mrk in extract_markers(nd, "olr_type"):
                if any(
                    [
                        f"{mrk} label incorrect".lower() in lbl.lower()
                        for lbl in all_labels(rid)
                    ]
                ):
                    print(f"{mrk}: {all_labels(rid)}")
        self.assertFalse(failed)

    def test_predicates_coverage(self):
        def is_ol_neuron(rid):
            return extract_at_most_one_marker(
                self.neuron_db.neuron_data[rid], "olr_type"
            )

        # map each neuron to it's upstream/downstream partner types set
        ins, outs = self.neuron_db.input_output_partner_sets()
        ins_type, outs_type = defaultdict(set), defaultdict(set)
        for k, v in ins.items():
            for r in v:
                ins_type[k].add(is_ol_neuron(r))
        for k, v in outs.items():
            for r in v:
                outs_type[k].add(is_ol_neuron(r))

        # map each neuron (not just olr) to set of types with matching predicates
        rid_to_matched_predicates = defaultdict(set)
        for k, v in TYPE_PREDICATES_METADATA.items():
            if v["f_score"] < 0.6:
                continue
            ins_p, outs_p = set(v["predicate_input_types"]), set(
                v["predicate_output_types"]
            )
            matching_rids = {
                r
                for r in self.neuron_db.neuron_data.keys()
                if ins_p.issubset(ins_type[r]) and outs_p.issubset(outs_type[r])
            }
            for mr in matching_rids:
                rid_to_matched_predicates[mr].add(k)

        # count how many predicates match each neuron
        ol_rids_with_pred_match_counts = defaultdict(int)
        all_rids_with_pred_match_counts = defaultdict(int)
        num_ol_neurons = 0
        for rid, nd in self.neuron_db.neuron_data.items():
            all_rids_with_pred_match_counts[len(rid_to_matched_predicates[rid])] += 1
            mrk = extract_at_most_one_marker(nd, "olr_type")
            if mrk:
                num_ol_neurons += 1
                ol_rids_with_pred_match_counts[len(rid_to_matched_predicates[rid])] += 1

        print(
            "All neurons:\n"
            + format_dict_by_largest_value(all_rids_with_pred_match_counts)
        )
        print(
            "OL neurons:\n"
            + format_dict_by_largest_value(ol_rids_with_pred_match_counts)
        )

        # check the fraction of OL neurons that have exactly one match (ideally this should reach close to 100%)
        prct = percentage(ol_rids_with_pred_match_counts[1], num_ol_neurons)
        print(f"OL one-match percentage: {prct}")
        self.assertEqual("69%", prct)

    def test_missing_predicates(self):
        def shorten(dct):
            return {
                k: (len(v) if isinstance(v, list) else v)
                for k, v in dct.items()
                if not k.endswith("types")
            }

        big_unknown_types = []
        for k, v in TYPE_PREDICATES_METADATA.items():
            if v["f_score"] < 0.6 and v["cells"] > 100:
                print(f'{k}: {v["cells"]}')
                big_unknown_types.append(k)

        for i in range(1):
            for tp in big_unknown_types:
                print(f"========== {tp} ==============")
                cell_ids = [
                    rid
                    for rid, nd in self.neuron_db.neuron_data.items()
                    if extract_at_most_one_marker(nd, "olr_type") == tp
                ]

                olr_predicates_generator = OlrPredicatesGenerator(
                    self.neuron_db, max_set_size=5, up_threshold=0.2, down_threshold=0.2
                )
                print(
                    f"Looking for best precision subset for {tp} with {len(cell_ids)} cells"
                )
                pdata = olr_predicates_generator.find_best_predicate_for_list(
                    cell_ids, optimization_metric="precision", min_score=0
                )
                print(shorten(pdata))
                true_pos = pdata["true_positives"]
                if pdata["precision"] > 0.85:
                    for tp_rid in true_pos:
                        self.neuron_db.neuron_data[tp_rid]["marker"] = [
                            f"olr_type:{tp}_{i}"
                        ]
