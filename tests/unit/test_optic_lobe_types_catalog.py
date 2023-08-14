import gzip
import pickle
import string
from collections import defaultdict
from unittest import TestCase

from src.configuration import TYPE_PREDICATES_METADATA, APP_ROOT_PATH
from src.data.versions import TESTING_DATA_SNAPSHOT_VERSION
from src.data.visual_neuron_types import (
    VISUAL_NEURON_TYPES,
    VISUAL_NEURON_MEGA_TYPE_TO_TYPES,
)
from src.service.optic_lobe_types_catalog import (
    assign_types_to_neurons,
    rewrite,
    has_exclude_label,
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

        ins, outs = self.neuron_db.input_output_partner_sets()

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["Mi1"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
                input_partner_sets=ins,
            ),
        )

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["this is Mi 1"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
                input_partner_sets=ins,
            ),
        )

        self.assertEqual(
            {"Mi1": [], "Unknown-labeled": [123], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["Mi2"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
                input_partner_sets=ins,
            ),
        )

        self.assertEqual(
            {"Mi1": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["Mi1; R"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["Mi1", "Unknown-labeled", "Unknown-not-labeled"],
                input_partner_sets=ins,
            ),
        )

        self.assertEqual(
            {"R1-6": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map(["R2"]),
                rid_to_cell_types_list=make_list([]),
                target_type_list=["R1-6", "Unknown-labeled", "Unknown-not-labeled"],
                input_partner_sets=ins,
            ),
        )

        self.assertEqual(
            {"R1-6": [123], "Unknown-labeled": [], "Unknown-not-labeled": []},
            assign_types_to_neurons(
                rid_to_labels=make_map([]),
                rid_to_cell_types_list=make_list(["R1-6"]),
                target_type_list=["R1-6", "Unknown-labeled", "Unknown-not-labeled"],
                input_partner_sets=ins,
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
        # load connections with threshold 2 (instead of 5)
        # TODO: make this a util, and update predicate computation module accordingly
        with gzip.open(
            f"{APP_ROOT_PATH}/static/data/{TESTING_DATA_SNAPSHOT_VERSION}/no_threshold_connections.pickle.gz",
            "rb",
        ) as handle:
            self.neuron_db.connections_ = pickle.load(handle)
        ins, outs = self.neuron_db.input_output_partner_sets(min_syn_count=2)

        def is_ol_neuron(rid):
            return extract_at_most_one_marker(
                self.neuron_db.neuron_data[rid], "olr_type"
            )

        # map each neuron to it's upstream/downstream partner types set
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
            if not v["f_score"]:
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
        self.assertEqual("79%", prct)

    def test_excluded_cells(self):
        excluded_and_olr_rids = []
        for rid, nd in self.neuron_db.neuron_data.items():
            if has_exclude_label(nd):
                if extract_at_most_one_marker(nd, "olr_type"):
                    excluded_and_olr_rids.append(rid)
        self.assertEqual([], excluded_and_olr_rids)
