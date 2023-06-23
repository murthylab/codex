import os
import string
from collections import defaultdict
from datetime import datetime
from unittest import TestCase

from src.configuration import ASSIGN_NAMES_FROM_ANNOTATIONS
from src.data.auto_naming import assign_names_from_annotations
from src.data.brain_regions import REGIONS, HEMISPHERES
from src.data.local_data_loader import (
    read_csv,
)
from src.data.neuron_data_initializer import (
    NEURON_DATA_ATTRIBUTE_TYPES,
    clean_and_reduce_labels,
)
from src.data.optic_lobe_cell_types import (
    COLUMNAR_CELL_TYPE_GROUPS,
    COLUMNAR_CELL_SUPER_CLASSES,
    feasible_candidate,
)
from src.data.structured_search_filters import STRUCTURED_SEARCH_ATTRIBUTES
from src.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from src.utils.formatting import (
    make_web_safe,
    is_proper_textual_annotation,
)
from src.utils.label_cleaning import significant_diff_chars
from src.utils.parsing import tokenize
from src.utils.stats import jaccard_binary
from tests import TEST_DATA_ROOT_PATH, log_dev_url_for_root_ids, get_testing_neuron_db
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


class NeuronDataTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def all_annotations(self):
        for nd in self.neuron_db.neuron_data.values():
            for attrib_name, attrib_value in nd.items():
                if isinstance(attrib_value, dict):
                    for k, v in attrib_value.items():
                        yield attrib_name, k
                        yield attrib_name, v
                elif isinstance(attrib_value, list) or isinstance(attrib_value, set):
                    for v in attrib_value:
                        yield attrib_name, v
                else:
                    yield attrib_name, attrib_value

    def test_index_data(self):
        self.assertGreater(len(self.neuron_db.neuron_data), 100000)

        def check_num_values_missing(attrib, expected_count):
            num_missing = len(
                [1 for nd in self.neuron_db.neuron_data.values() if not nd[attrib]]
            )
            self.assertLessEqual(
                num_missing,
                expected_count,
                f"Too many missing values for attribute: {attrib}",
            )

        expected_missing_value_bounds = {
            "label": 79000,
            "super_class": 5200,
            "class": 37000,
            "sub_class": 122000,
            "cell_type": 115000,
            "hemibrain_type": 105000,
            "hemilineage": 98000,
            "flow": 5150,
            "side": 14000,
            "nerve": 120000,
            "input_cells": 8500,
            "input_neuropils": 8500,
            "input_synapses": 8500,
            "output_cells": 7000,
            "output_neuropils": 7000,
            "output_synapses": 7000,
            "nt_type": 13000,
            "nt_type_score": 10000,
            "ach_avg": 4200,
            "da_avg": 15500,
            "gaba_avg": 11000,
            "glut_avg": 12000,
            "oct_avg": 37000,
            "ser_avg": 68000,
            "similar_cell_scores": 20000,
            "similar_connectivity_scores": 20000,
            "morphology_cluster": 84000,
            "connectivity_cluster": 84000,
            "marker": 102000,
            "mirror_twin_root_id": 75000,
            "length_nm": 7,
        }

        for k in NEURON_DATA_ATTRIBUTE_TYPES.keys():
            check_num_values_missing(k, expected_missing_value_bounds.get(k, 0))

    def test_annotations_web_safe(self):
        for attrib_name, attrib_value in self.all_annotations():
            if isinstance(attrib_value, str):
                self.assertEqual(
                    attrib_value,
                    make_web_safe(attrib_value),
                    f"Non web safe annotation '{attrib_value}' for attribute '{attrib_name}'",
                )

    def test_annotations_meaningful(self):
        excluded_attributes = ["position", "label"]
        empty_vals, nonempty_vals = 0, 0
        for attrib_name, attrib_value in self.all_annotations():
            self.assertIsNotNone(
                attrib_value,
                f"Annotation is absent ('{attrib_value}') for attribute '{attrib_name}'",
            )
            if attrib_value == "":
                empty_vals += 1
                continue
            nonempty_vals += 1
            if not isinstance(attrib_value, str) or attrib_name in excluded_attributes:
                continue
            self.assertTrue(
                is_proper_textual_annotation(attrib_value),
                f"Meaningless annotation '{attrib_value}' for attribute '{attrib_name}'",
            )

        self.assertGreater(
            nonempty_vals, 10 * empty_vals, f"Too many empty annotations: {empty_vals}"
        )

    def test_annotations(self):
        neurons_with_labels = [
            n for n in self.neuron_db.neuron_data.values() if n["label"]
        ]
        self.assertGreater(len(neurons_with_labels), 25000)

        neurons_with_annotations = [
            n for n in self.neuron_db.neuron_data.values() if n["label"]
        ]
        self.assertEqual(len(neurons_with_labels), len(neurons_with_annotations))

        for n in self.neuron_db.neuron_data.values():
            for col in [
                "input_neuropils",
                "output_neuropils",
                "label",
                "position",
            ]:
                self.assertEqual(len(set(n[col])), len(n[col]))
            self.assertEqual(len(n["supervoxel_id"]), len(n["position"]))

        # closest term search
        self.assertEqual(
            self.neuron_db.closest_token("blobe", case_sensitive=False), ("lobe", 1)
        )
        self.assertEqual(
            self.neuron_db.closest_token("blobe", case_sensitive=True), ("lobe", 1)
        )
        self.assertEqual(
            self.neuron_db.closest_token("BLOBE", case_sensitive=True), ("LB3", 3)
        )

        # don't suggest in structured queries
        self.assertEqual(
            self.neuron_db.closest_token("BLO==BE", case_sensitive=True), (None, None)
        )
        self.assertEqual(
            self.neuron_db.closest_token("BLOBE && Lb3", case_sensitive=False),
            (None, None),
        )

    def test_search(self):
        # search results
        self.assertGreater(len(self.neuron_db.search("da")), 900)
        self.assertEqual(len(self.neuron_db.search("dadadeadbeef")), 0)

    def test_structured_search(self):
        # structured search
        gaba_rids = self.neuron_db.search("nt_type == gaba")
        self.assertGreater(len(gaba_rids), 1000)
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(gaba_rids) + len(self.neuron_db.search("nt_type != gaba")),
        )
        for rid in gaba_rids:
            self.assertEqual("GABA", self.neuron_db.get_neuron_data(rid)["nt_type"])

        ach_rids = self.neuron_db.search("nt_type == ACH")
        self.assertGreater(len(ach_rids), 1000)
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(ach_rids) + len(self.neuron_db.search("nt_type != ACH")),
        )
        for rid in ach_rids:
            self.assertEqual("ACH", self.neuron_db.get_neuron_data(rid)["nt_type"])

        gaba_and_ach_rids = self.neuron_db.search("nt_type == ACH && nt_type == gaba")
        self.assertEqual(0, len(gaba_and_ach_rids))

        gaba_or_ach_rids = self.neuron_db.search("nt_type == ACH || nt_type == gaba")
        self.assertEqual(len(ach_rids) + len(gaba_rids), len(gaba_or_ach_rids))

        ids_with_name = self.neuron_db.search("{has} name")
        ids_without_name = self.neuron_db.search("{not} name")
        self.assertEqual(len(self.neuron_db.neuron_data), len(ids_with_name))
        self.assertEqual(0, len(ids_without_name))

        ids_with_class = self.neuron_db.search("$$ class")
        ids_without_class = self.neuron_db.search("!$ class")
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(ids_with_class) + len(ids_without_class),
        )
        self.assertEqual(
            set(ids_with_class),
            set(
                [
                    nd["root_id"]
                    for nd in self.neuron_db.neuron_data.values()
                    if nd["class"]
                ]
            ),
        )

    def test_structured_search_case(self):
        # case sensitive vs insensitive search
        class_matches = self.neuron_db.search("class == dn", case_sensitive=True)
        self.assertEqual(len(class_matches), 0)
        class_matches = self.neuron_db.search("class == DN")
        self.assertGreater(len(class_matches), 1000)

        # starts with op
        self.assertGreater(len(self.neuron_db.search("label {starts_with} LC")), 350)
        self.assertGreater(len(self.neuron_db.search("label {starts_with} lc")), 350)
        self.assertEqual(
            len(self.neuron_db.search("label {starts_with} lc", case_sensitive=True)), 0
        )
        self.assertGreater(len(self.neuron_db.search("id {starts_with} 72")), 65000)

    def test_structured_search_lists(self):
        # explicit searches
        many_root_ids = list(self.neuron_db.neuron_data.keys())[:30]
        root_id_search_explicit = self.neuron_db.search(
            " || ".join([f"id == {rid}" for rid in many_root_ids])
        )
        self.assertEqual(set(root_id_search_explicit), set(many_root_ids))
        root_id_search_membership = self.neuron_db.search(
            f"id << {','.join([str(rid) for rid in many_root_ids])}"
        )
        self.assertEqual(set(root_id_search_explicit), set(root_id_search_membership))
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(many_root_ids)
            + len(
                self.neuron_db.search(
                    " && ".join([f"id != {rid}" for rid in many_root_ids])
                )
            ),
        )
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(many_root_ids)
            + len(
                self.neuron_db.search(
                    f"id !< {','.join([str(rid) for rid in many_root_ids])}"
                )
            ),
        )

    def test_structured_search_misc(self):
        self.assertLess(len(self.neuron_db.search("gaba && nt_type != gaba")), 700)

        self.assertEqual(
            2, len(self.neuron_db.search("720575940643084488 720575940643467886"))
        )
        self.assertEqual(
            2, len(self.neuron_db.search("720575940643084488,720575940643467886"))
        )
        self.assertEqual(
            2, len(self.neuron_db.search("720575940643084488, 720575940643467886"))
        )

    def test_structured_search_operator_combos(self):
        self.assertGreater(
            len(self.neuron_db.search("fru {and} central && nt_type != gaba")), 500
        )

    def test_downstream_upstream_queries(self):
        downstream = self.neuron_db.search("{downstream} 720575940646952324")
        self.assertEqual(115, len(downstream))

        upstream = self.neuron_db.search("{upstream} 720575940646952324")
        self.assertEqual(204, len(upstream))

        reciprocal = self.neuron_db.search("{reciprocal} 720575940646952324")
        self.assertEqual(29, len(reciprocal))

    def test_downstream_upstream_region_queries(self):
        downstream = self.neuron_db.search(
            "right {downstream_region} 720575940643467886"
        )
        self.assertEqual(16, len(downstream))
        downstream = self.neuron_db.search(
            "left {downstream_region} 720575940643467886"
        )
        self.assertEqual(0, len(downstream))
        downstream = self.neuron_db.search(
            "center {downstream_region} 720575940643467886"
        )
        self.assertEqual(
            sorted(
                [
                    720575940615933919,
                    720575940620960347,
                    720575940623618708,
                    720575940627079938,
                    720575940629148007,
                    720575940630026812,
                    720575940633182291,
                ]
            ),
            sorted(downstream),
        )

        upstream = self.neuron_db.search("right {upstream_region} 720575940643467886")
        self.assertEqual(38, len(upstream))
        upstream = self.neuron_db.search("left {upstream_region} 720575940643467886")
        self.assertEqual(0, len(upstream))
        upstream = self.neuron_db.search("center {upstream_region} 720575940643467886")
        self.assertEqual(11, len(upstream))

    def test_neuropil_queries(self):
        self.assertGreater(
            len(self.neuron_db.search("input_neuropil {equal} gng")), 5000
        )
        self.assertGreater(
            len(self.neuron_db.search("input_neuropil {equal} accessory medulla left")),
            50,
        )
        self.assertGreater(
            len(self.neuron_db.search("input_neuropil {in} medulla")), 10000
        )

    def test_contains_queries(self):
        self.assertGreater(len(self.neuron_db.search("label {contains} dsx")), 100)
        self.assertEqual(
            len(
                self.neuron_db.search(
                    "label {contains} dsx && label {not_contains} dsx"
                )
            ),
            0,
        )
        self.assertGreater(
            len(
                self.neuron_db.search(
                    "label {contains} dsx && label {not_contains} fru"
                )
            ),
            80,
        )

    def test_not_connected_cells(self):
        connected_cells = set(self.neuron_db.input_sets().keys()).union(
            set(self.neuron_db.output_sets().keys())
        )
        not_connected_cells = set(self.neuron_db.neuron_data.keys()) - connected_cells
        self.assertGreater(3500, len(not_connected_cells))

    def test_nt_score_stats(self):
        for nd in self.neuron_db.neuron_data.values():
            scores_list = [
                nd[f"{nt_type.lower()}_avg"] for nt_type in NEURO_TRANSMITTER_NAMES
            ]
            for s in scores_list:
                self.assertGreaterEqual(1, s)
                self.assertLessEqual(0, s)
            total = sum(scores_list)
            self.assertGreaterEqual(1.05, total)
            self.assertLessEqual(0.0, total, nd)

    def test_neuropils(self):
        res = set()
        for nd in self.neuron_db.neuron_data.values():
            for p in nd["input_neuropils"]:
                res.add(p)
            for p in nd["output_neuropils"]:
                res.add(p)
        self.assertEqual(set(REGIONS.keys()), res)

    def test_classes(self):
        expected_list = [
            "ALIN",
            "ALLN",
            "ALON",
            "ALPN",
            "AN",
            "CSD",
            "CX",
            "DAN",
            "DN",
            "Kenyon_Cell",
            "L1-5",
            "LHCENT",
            "LHLN",
            "MBIN",
            "MBON",
            "TuBu",
            "bilateral",
            "gustatory",
            "hygrosensory",
            "mAL",
            "mechanosensory",
            "medulla_intrinsic",
            "motor",
            "ocellar",
            "olfactory",
            "optic_lobes",
            "pars intercerebralis",
            "pars lateralis",
            "thermosensory",
            "unknown_sensory",
            "visual",
        ]
        self.assertEqual(expected_list, self.neuron_db.unique_values("class"))

    def test_super_classes(self):
        expected_list = [
            "ascending",
            "central",
            "descending",
            "endocrine",
            "motor",
            "optic",
            "sensory",
            "visual_centrifugal",
            "visual_projection",
        ]
        self.assertEqual(expected_list, self.neuron_db.unique_values("super_class"))

    def test_sub_classes(self):
        expected_list = [
            "LNOa",
            "accessory_pharyngeal_nerve_sensory_group1",
            "accessory_pharyngeal_nerve_sensory_group2",
            "antennal_nerve_ascending_sensory",
            "auditory",
            "columnar",
            "descending",
            "eye bristle",
            "head bristle",
            "multiglomerular",
            "ocellar",
            "ocellar_interneuron",
            "pharyngeal_nerve_sensory_group1",
            "pharyngeal_nerve_sensory_group2",
            "ring neuron",
            "tangential",
            "taste peg",
            "uniglomerular",
        ]
        self.assertEqual(expected_list, self.neuron_db.unique_values("sub_class"))

    def test_cell_types(self):
        expected_list_length = 797
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("cell_type"))
        )

    def test_hemibrain_types(self):
        expected_list_length = 3080
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("hemibrain_type"))
        )

    def test_hemilineage(self):
        expected_list_length = 201
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("hemilineage"))
        )

    def test_sizes(self):
        for nd in self.neuron_db.neuron_data.values():
            ln = nd["length_nm"]
            area = nd["area_nm"]
            volume = nd["size_nm"]
            if ln:
                self.assertGreater(ln, 1000)
                self.assertGreater(area, 1000 * 1000)
                self.assertGreater(volume, 1000 * 1000 * 1000)
                self.assertGreater(area, ln)
                self.assertGreater(volume, area + ln)

    def test_get_neuron_data(self):
        self.assertGreater(
            len(self.neuron_db.get_neuron_data(root_id=720575940624056624)), 5
        )
        self.assertGreater(
            len(self.neuron_db.get_neuron_data(root_id="720575940624056624")), 5
        )

    def test_label_data_consistency(self):
        label_data = self.neuron_db.label_data
        neuron_data = self.neuron_db.neuron_data
        mismatch = 0
        for rid, nd in neuron_data.items():
            ld = clean_and_reduce_labels(
                [
                    label["label"]
                    for label in sorted(
                        label_data.get(rid, []),
                        key=lambda x: x["date_created"],
                        reverse=True,
                    )
                ],
                nd,
            )
            if sorted(set(nd["label"])) != sorted(set(ld)):
                print(f'{rid}: {sorted(set(nd["label"]))} -> {sorted(set(ld))}')
                mismatch += 1
        self.assertEqual(mismatch, 0)

    def test_no_garbage_labels(self):
        for nd in self.neuron_db.neuron_data.values():
            labels = nd["label"]
            self.assertEqual(len(labels), len(set(labels)))
            self.assertTrue(all(labels))
            for lbl in labels:
                self.assertFalse(lbl.startswith("72"), lbl)
                for garbage in [
                    "not a neuron",
                    "sorry",
                    "correct",
                    "wrong",
                    "accident",
                    "brain fart",
                    "mistake",
                    "error",
                    "part of comprehensive neck connective tracing",
                ]:
                    self.assertFalse(
                        garbage.lower() in lbl.lower(), f"{lbl} contains {garbage}"
                    )

    def test_thumbnails(self):
        # Run this first to collect existing skeleton root ids:
        # gsutil du gs://flywire-data/codex/skeleton_thumbnails | grep png | cut -d"/" -f 6 | cut -d "." -f 1 > static/raw_data/thumbnails_tmp.csv
        fname = f"{TEST_DATA_ROOT_PATH}/../raw_data/{DEFAULT_DATA_SNAPSHOT_VERSION}/thumbnails_tmp.csv"
        if os.path.isfile(fname):
            content = set([int(r[0]) for r in read_csv(fname)])
            self.assertEqual(
                [], [r for r in self.neuron_db.neuron_data.keys() if r not in content]
            )

    def test_attribute_coverage(self):
        sparse_attrs = {
            "similar_cell_scores",
            "mirror_twin_root_id",
            "similar_connectivity_scores",
            "label",
            "nerve",
            "oct_avg",
            "ser_avg",
            "class",
            "sub_class",
            "cell_type",
            "hemibrain_type",
            "hemilineage",
            "morphology_cluster",
            "connectivity_cluster",
            "marker",
        }
        for k, v in NEURON_DATA_ATTRIBUTE_TYPES.items():
            if k in sparse_attrs:
                continue
            num_vals = len([n[k] for n in self.neuron_db.neuron_data.values() if n[k]])
            self.assertGreater(num_vals / len(self.neuron_db.neuron_data), 0.85, k)

    def test_nblast_scores_consistency(self):
        for from_rid, nd in self.neuron_db.neuron_data.items():
            for to_rid, score in nd["similar_cell_scores"].items():
                self.assertEqual(
                    score,
                    self.neuron_db.neuron_data[to_rid]["similar_cell_scores"][from_rid],
                )

    def test_labels_redundancy(self):
        complete_redundancy_cnt = 0
        partial_redundancy_cnt = 0
        for nd in self.neuron_db.neuron_data.values():
            annos = []
            for k, v in nd.items():
                if k in ["label", "name", "marker", "cell_type", "hemibrain_type"]:
                    continue
                if isinstance(v, str):
                    annos.append(v)
                elif isinstance(v, list):
                    for vv in v:
                        if isinstance(vv, str):
                            annos.append(vv)
            annos = set([a.lower() for a in annos if a])
            if annos:
                for lbl in nd["label"]:
                    lbl_tokens = set([t.strip() for t in lbl.lower().split(";")])
                    if lbl_tokens.issubset(annos):
                        print(f"Subset: {lbl_tokens}, {annos}")
                        complete_redundancy_cnt += 1
                    elif lbl_tokens.intersection(annos):
                        print(f"Not subset: {lbl_tokens}, {annos}")
                        partial_redundancy_cnt += 1
        self.assertEqual(0, complete_redundancy_cnt)
        self.assertEqual(0, partial_redundancy_cnt)

    def test_labels_duplication(self):
        self.assertTrue(significant_diff_chars("ba", "bfc"))
        self.assertFalse(significant_diff_chars("ba:", "ba"))

        seps = string.ascii_letters + string.digits + "_"

        for nd in self.neuron_db.neuron_data.values():
            labels = nd["label"]
            if len(labels) > 1:
                for i, lbl1 in enumerate(labels):
                    for j, lbl2 in enumerate(labels):
                        if j > i:
                            self.assertTrue(
                                significant_diff_chars(lbl1, lbl2), f"{lbl1} --> {lbl2}"
                            )
                            if len(lbl1) == len(lbl2):
                                continue
                            sl, ll = (
                                (lbl1, lbl2) if len(lbl1) < len(lbl2) else (lbl2, lbl1)
                            )
                            if ll.startswith(sl):
                                sep = ll[len(sl)]
                                self.assertTrue(
                                    sep in seps,
                                    f"Separator {sep} breaks prefix: {lbl1} -> {lbl2}",
                                )

    def test_label_cleaning(self):
        for nd in self.neuron_db.neuron_data.values():
            labels = nd["label"]
            self.assertEqual(len(labels), len(set(labels)))
            self.assertTrue(all([len(lbl) > 1 for lbl in labels]), labels)
            for lbl in labels:
                lbllc = lbl.lower()
                self.assertFalse(
                    any(
                        [
                            b in lbllc
                            for b in [
                                "left",
                                "right",
                                "lhs",
                                "rhs",
                                "correction",
                                "correct",
                                "wrong",
                            ]
                        ]
                    ),
                    f"{nd['root_id']}: {labels}",
                )
                tokens = tokenize(lbllc)
                self.assertFalse(
                    any(
                        [
                            any([tk.endswith(s) for s in ["_l", "_r", "-l", "-r"]])
                            for tk in tokens
                        ]
                    ),
                    lbllc,
                )

    def test_connection_filters(self):
        rid_list = list(self.neuron_db.neuron_data.keys())[:100]
        cons = self.neuron_db.connections(
            rid_list, induced=False, min_syn_count=5, nt_type="GABA"
        )
        self.assertGreater(len(cons), 0)
        for r in cons:
            self.assertTrue(r[0] in rid_list or r[1] in rid_list)
            self.assertGreaterEqual(r[3], 5)
            self.assertEqual("GABA", r[4])

        rid_list = list(self.neuron_db.neuron_data.keys())[:10000]
        cons = self.neuron_db.connections(rid_list, induced=True)
        self.assertGreater(len(cons), 0)
        for r in cons:
            self.assertTrue(r[0] in rid_list and r[1] in rid_list)

    def test_connection_query_consistency(self):
        for rid in sorted(self.neuron_db.neuron_data.keys())[10000:10020]:
            cons1 = sorted(self.neuron_db.cell_connections(rid))
            cons2 = sorted(
                self.neuron_db.connections_._rows_from_predicates(
                    rids_predicate=lambda x, y: rid == x or rid == y
                )
            )
            self.assertEqual(cons1, cons2)

    def test_nt_types_consistency(self):
        rid_to_nt_counts = {}
        for r in self.neuron_db.connections_.all_rows():
            self.assertTrue(r[4] in NEURO_TRANSMITTER_NAMES.keys())
            ntd = rid_to_nt_counts.setdefault(r[0], {})
            ntd[r[4]] = ntd.get(r[4], 0) + r[3]

        rid_to_con_nts = {rid: max(v, key=v.get) for rid, v in rid_to_nt_counts.items()}

        def vague_nt_type(ndata):
            scores = sorted(
                [ndata[f"{ntt.lower()}_avg"] for ntt in NEURO_TRANSMITTER_NAMES.keys()],
                reverse=True,
            )
            return scores[0] <= 0.2 or scores[0] <= scores[1] + 0.1

        eq, df, missing_con, vague = 0, 0, 0, 0
        diff_pairs = defaultdict(int)
        for rid, nd in self.neuron_db.neuron_data.items():
            if nd["nt_type"] == rid_to_con_nts.get(rid):
                eq += 1
            elif not rid_to_con_nts.get(rid):
                missing_con += 1
            elif vague_nt_type(nd):
                vague += 1
            else:
                diff_pairs[(nd["nt_type"], rid_to_con_nts.get(rid))] += 1
                df += 1
        print(f"{eq=} {df=} {missing_con=} {vague=}")
        print(diff_pairs)
        self.assertGreater(2000, df)

    def test_similar_connectivity(self):
        cell_rid = 720575940639310150
        self.assertEqual(
            {
                720575940611395448: 0.3776573129251701,
                720575940613079781: 0.14162237978330947,
                720575940617296757: 0.1008808760775308,
                720575940629573904: 0.10245754895423853,
                720575940633212876: 0.1422941578692817,
                720575940639310150: 1.0,
            },
            self.neuron_db.get_similar_connectivity_cells(cell_rid),
        )

        self.assertEqual(
            {
                720575940611395448: 0.5580357142857143,
                720575940612919219: 0.12446351931330472,
                720575940617296757: 0.11627906976744186,
                720575940620975892: 0.11981566820276497,
                720575940638306163: 0.10661764705882353,
                720575940639310150: 1.0,
            },
            self.neuron_db.get_similar_connectivity_cells(
                cell_rid, include_downstream=False
            ),
        )

        self.assertEqual(
            {
                720575940611395448: 0.6313019390581718,
                720575940612919219: 0.13367609254498714,
                720575940613079781: 0.11390532544378698,
                720575940617296757: 0.12254259501965924,
                720575940620975892: 0.11640995260663507,
                720575940629573904: 0.12778628551982305,
                720575940633212876: 0.11902193455591514,
                720575940639310150: 1.0,
            },
            self.neuron_db.get_similar_connectivity_cells(
                cell_rid, include_downstream=False, weighted=True
            ),
        )

    def test_similar_embeddings(self):
        cell_rid = 720575940639310150
        self.assertEqual(
            {
                720575940611395448: 0.9946819747467505,
                720575940628445956: 0.9052906941935155,
                720575940630857276: 0.9045391666934834,
                720575940637468846: 0.9045594959601143,
                720575940639310150: 1.0000000000000002,
            },
            self.neuron_db.get_similar_spectral_cells(cell_rid, limit=5),
        )

        self.assertEqual(
            {
                720575940611395448: 0.9980352471507598,
                720575940613079781: 0.9834430769303121,
                720575940613163286: 0.9274571235206494,
                720575940633212876: 0.9845749911264506,
                720575940639310150: 1.0,
            },
            self.neuron_db.get_similar_spectral_cells(
                cell_rid, include_downstream=False, limit=5
            ),
        )

        self.assertEqual(
            {
                720575940611395448: 0.9408080274764601,
                720575940613079781: 0.9857815760993802,
                720575940623889800: 0.8985033709058498,
                720575940633212876: 0.9856090812591819,
                720575940639310150: 0.9408301772985264,
            },
            self.neuron_db.get_similar_spectral_cells(
                cell_rid,
                include_downstream=False,
                projected_to_root_id=720575940633212876,
                limit=5,
            ),
        )

    def test_find_similar_cells(self):
        cell_ids = sorted(self.neuron_db.neuron_data.keys())[10000:10020]
        similar_cell_scores = {}
        for cell_id in cell_ids:
            dct = self.neuron_db.get_similar_connectivity_cells(
                cell_id, with_same_attributes="side,super_class"
            )
            for k, v in dct.items():
                if k in cell_ids:
                    continue
                if k not in similar_cell_scores or v > similar_cell_scores[k]:
                    similar_cell_scores[k] = v
        self.assertEqual(840, len(similar_cell_scores))

    def test_columnar_cell_tags(self):
        # check marked cells
        for rid, ndata in self.neuron_db.neuron_data.items():
            ol_tag_markers = [mrk for mrk in ndata["marker"] if ":" in mrk]
            if ol_tag_markers:
                self.assertTrue(ndata["super_class"] in COLUMNAR_CELL_SUPER_CLASSES)
                if all(
                    [mrk.startswith("columnar_candidate:") for mrk in ol_tag_markers]
                ):
                    for mrk in ol_tag_markers:
                        self.assertTrue(mrk.split(":")[1] in COLUMNAR_CELL_TYPE_GROUPS)
                elif len(ol_tag_markers) == 1:
                    mrk = ol_tag_markers[0].split(":")[1]
                    self.assertTrue(mrk in COLUMNAR_CELL_TYPE_GROUPS)
                    if ndata["cell_type"]:
                        for ct in ndata["cell_type"]:
                            self.assertTrue(
                                ct not in COLUMNAR_CELL_TYPE_GROUPS or ct == mrk
                            )
                    elif ndata["label"]:
                        lbl = " | ".join(ndata["label"])
                        if mrk.lower() not in lbl.lower():
                            for t in COLUMNAR_CELL_TYPE_GROUPS.keys():
                                self.assertTrue(
                                    t.lower() not in lbl.lower().split(),
                                    f"{t=} {mrk=} {lbl=}",
                                )
                else:
                    self.fail(f"Too many OL tag markers: {ndata['marker']}")
            elif ndata["cell_type"]:
                for ct in ndata["cell_type"]:
                    self.assertTrue(ct not in COLUMNAR_CELL_TYPE_GROUPS)
            elif ndata["label"] and ndata["super_class"] in COLUMNAR_CELL_SUPER_CLASSES:
                for lbl in ndata["label"]:
                    for t in COLUMNAR_CELL_TYPE_GROUPS.keys():
                        self.assertTrue(t.lower() not in lbl.lower().split(), lbl)

    def test_columnar_candidate_neuropil_filter(self):
        pils = self.neuron_db.neuron_data[720575940604570046]["output_neuropils"]
        self.assertFalse(feasible_candidate("T4a", pils), pils)

    def test_dynamic_ranges(self):
        self.assertEqual(
            {
                "data_class_range": [
                    "optic_lobes",
                    "Kenyon_Cell",
                    "L1-5",
                    "visual",
                    "CX",
                    "mechanosensory",
                    "AN",
                    "olfactory",
                    "medulla_intrinsic",
                    "DN",
                    "ALPN",
                    "LHLN",
                    "ALLN",
                    "gustatory",
                    "DAN",
                    "bilateral",
                    "TuBu",
                    "unknown_sensory",
                    "motor",
                    "MBON",
                    "mAL",
                    "hygrosensory",
                    "ocellar",
                    "LHCENT",
                    "pars intercerebralis",
                    "thermosensory",
                    "pars lateralis",
                    "ALIN",
                    "ALON",
                    "MBIN",
                    "CSD",
                ],
                "data_flow_range": ["intrinsic", "afferent", "efferent"],
                "data_nerve_range": [
                    "CV",
                    "AN",
                    "MxLbN",
                    "OCN",
                    "PhN",
                    "aPhN",
                    "NCC",
                    "ON",
                ],
                "data_nt_type_range": ["ACH", "GLUT", "GABA", "DA", "SER", "OCT"],
                "data_side_range": ["right", "left", "center"],
                "data_sub_class_range": [
                    "columnar",
                    "eye bristle",
                    "tangential",
                    "multiglomerular",
                    "auditory",
                    "head bristle",
                    "uniglomerular",
                    "ring neuron",
                    "ocellar",
                    "taste peg",
                    "pharyngeal_nerve_sensory_group2",
                    "accessory_pharyngeal_nerve_sensory_group2",
                    "accessory_pharyngeal_nerve_sensory_group1",
                    "pharyngeal_nerve_sensory_group1",
                    "ocellar_interneuron",
                    "descending",
                    "antennal_nerve_ascending_sensory",
                    "LNOa",
                ],
                "data_super_class_range": [
                    "optic",
                    "central",
                    "sensory",
                    "visual_projection",
                    "ascending",
                    "descending",
                    "visual_centrifugal",
                    "motor",
                    "endocrine",
                ],
            },
            self.neuron_db.dynamic_ranges(),
        )

        for attr in STRUCTURED_SEARCH_ATTRIBUTES:
            if attr.name in ["input_neuropils", "output_neuropils"]:
                self.assertEqual(set(attr.value_range), set(REGIONS.keys()))
            elif attr.name in ["input_hemisphere", "output_hemisphere"]:
                self.assertEqual(set(attr.value_range), set(HEMISPHERES))
            else:
                data_range_key = f"data_{attr.name}_range"
                if not attr.value_range:
                    self.assertTrue(
                        data_range_key not in self.neuron_db.dynamic_ranges()
                    )
                else:
                    self.assertEqual(
                        set(attr.value_range),
                        set(self.neuron_db.dynamic_ranges()[data_range_key]),
                        attr.name,
                    )

    def test_svd(self):
        rid = 720575940621675174
        print(datetime.now())
        score_pairs = self.neuron_db.svd.rid_score_pairs_sorted(
            rid, up=True, down=True
        )[:10]
        self.assertEqual(
            [
                720575940621675174,
                720575940646126190,
                720575940626457406,
                720575940628452520,
                720575940646114926,
                720575940626477498,
                720575940627152668,
                720575940605688492,
                720575940633017939,
                720575940622831740,
            ],
            [p[0] for p in score_pairs],
        )
        score_pairs = self.neuron_db.svd.rid_score_pairs_sorted(
            rid, up=False, down=True
        )[:10]
        self.assertEqual(
            [
                720575940621675174,
                720575940646114926,
                720575940626662346,
                720575940636372335,
                720575940626947971,
                720575940636258423,
                720575940622831740,
                720575940607420290,
                720575940626379568,
                720575940628452520,
            ],
            [p[0] for p in score_pairs],
        )
        score_pairs = self.neuron_db.svd.rid_score_pairs_sorted(
            rid, up=True, down=False
        )[:10]
        self.assertEqual(
            [
                720575940621675174,
                720575940646126190,
                720575940626457406,
                720575940626477498,
                720575940633017939,
                720575940605688492,
                720575940624931564,
                720575940636933751,
                720575940628452520,
                720575940635615339,
            ],
            [p[0] for p in score_pairs],
        )
        print(datetime.now())

        for rid in self.neuron_db.svd.vecs.keys():
            self.assertTrue(rid in self.neuron_db.neuron_data)

    def test_naming(self):
        all_nds = list(self.neuron_db.neuron_data.values())

        # all names are unique ignoring case
        self.assertEqual(len(set([nd["name"].lower() for nd in all_nds])), len(all_nds))

        if ASSIGN_NAMES_FROM_ANNOTATIONS:
            # most names are extracted from annotations (not from neuropils)
            nds_with_neuropil_name = set(
                [nd["root_id"] for nd in all_nds if nd["name"].startswith(nd["group"])]
            )
            self.assertLess(len(nds_with_neuropil_name), 0.6 * len(all_nds))

        # check names have 1 or 2 parts (and if 2, second is counter)
        for nd in all_nds:
            name_parts = nd["name"].split(".")
            suffix = name_parts[-1]

            # region based name
            if nd["name"] == nd["group"] or nd["name"].startswith(f'{nd["group"]}.'):
                group_parts = nd["group"].split(".")
                if len(name_parts) > len(group_parts):
                    self.assertEqual(len(name_parts), len(group_parts) + 1)
                    self.assertFalse(suffix in "LR", f'{nd["group"]} {nd["name"]}')
                    self.assertGreater(int(suffix), 0)
                continue

            base_name = name_parts[0]
            self.assertGreater(len(base_name), 1)
            if len(name_parts) == 2:
                self.assertTrue(suffix in ["L", "R"] or int(suffix) > 0)
            else:
                self.assertEqual(len(name_parts), 1, name_parts)

            # check forbidden substrings
            for fbd in [
                " ",
                ".",
                ",",
                "?",
                "ascending",
                "descending",
                "unclassified",
                "clone",
                "test",
                "odd",
                "putative",
                "fbbt_",
                "eye_",
                "murthy",
                "seung",
            ]:
                self.assertTrue(fbd not in base_name.lower())

        # Check that for pairs, L/R is used instead of running index.
        # Also check that for singleton basenames, no running index is appended
        base_name_to_neurons = defaultdict(list)
        for nd in self.neuron_db.neuron_data.values():
            if nd["name"] == nd["group"] or nd["name"].startswith(nd["group"] + "."):
                continue
            name_parts = nd["name"].split(".")
            if len(name_parts) == 2:
                base_name_to_neurons[name_parts[0]].append(nd)
            else:
                self.assertFalse(name_parts[-1] in ["L", "R"], name_parts)

        for n, lst in base_name_to_neurons.items():
            if len(lst) == 2:
                s0, s1 = lst[0]["side"], lst[1]["side"]
                if s0 != s1 and s0 in ["left", "right"] and s1 in ["left", "right"]:
                    self.assertEqual(
                        s0[0].upper(), lst[0]["name"].split(".")[-1], lst[0]["name"]
                    )
                    self.assertEqual(
                        s1[0].upper(), lst[1]["name"].split(".")[-1], lst[1]["name"]
                    )

        for bn, lst in base_name_to_neurons.items():
            if len(lst) == 1:
                self.assertFalse(
                    lst[0]["name"].split(".")[-1].isnumeric(), lst[0]["name"]
                )

    def test_norms(self):
        # TODO: tighten these tests
        norms = self.neuron_db.svd.norms
        max_up = max([n.up for n in norms.values()])
        min_up = min([n.up for n in norms.values()])
        print(f"{max_up=} {min_up=}")
        self.assertGreater(30 * min_up, max_up)

        max_down = max([n.down for n in norms.values()])
        min_down = min([n.down for n in norms.values()])
        print(f"{max_down=} {min_down=}")
        self.assertGreater(15 * min_down, max_down)

        max_up_down = max([n.up_down for n in norms.values()])
        min_up_down = min([n.up_down for n in norms.values()])
        print(f"{max_up_down=} {min_up_down=}")
        self.assertGreater(20 * min_up_down, max_up_down)

    def test_alternative_naming(self):
        neuron_data = self.neuron_db.neuron_data
        old_names = {rid: nd["name"] for rid, nd in neuron_data.items()}
        assign_names_from_annotations(neuron_data)

        def strip_id(n):
            parts = n.split(".")
            if parts[-1].isnumeric():
                return ".".join(parts[:-1])
            else:
                return n

        diff_count = 0
        for rid, nd in neuron_data.items():
            if strip_id(old_names[rid]) != strip_id(nd["name"]):
                diff_count += 1
                log_dev_url_for_root_ids(f'{old_names[rid]} -> {nd["name"]}', [rid])
        self.assertEqual(0, diff_count)

    def test_mirror_twins(self):
        twin_rids = set()
        twin_map = {}
        for rid, nd in self.neuron_db.neuron_data.items():
            if nd["mirror_twin_root_id"]:
                self.assertTrue(nd["side"] in ["left", "right"], nd["side"])
                twin_cell = self.neuron_db.neuron_data[nd["mirror_twin_root_id"]]
                self.assertTrue(twin_cell["side"] in ["left", "right"])
                self.assertNotEqual(nd["side"], twin_cell["side"])
                self.assertEqual(rid, twin_cell["mirror_twin_root_id"])
                twin_rids.add(rid)
                twin_rids.add(twin_cell["root_id"])
                twin_map[rid] = twin_cell["root_id"]

        ins, outs = self.neuron_db.input_output_partner_sets()

        ins = {rid: s.intersection(twin_rids) for rid, s in ins.items()}
        outs = {rid: s.intersection(twin_rids) for rid, s in outs.items()}
        ins_mirror = {rid: set([twin_map[rid] for rid in s]) for rid, s in ins.items()}
        outs_mirror = {
            rid: set([twin_map[rid] for rid in s]) for rid, s in outs.items()
        }

        jscores = []
        for lft, rgt in twin_map.items():
            if lft >= rgt:
                continue
            score = (
                jaccard_binary(ins[lft], ins_mirror[rgt])
                + jaccard_binary(outs[lft], outs_mirror[rgt])
            ) / 2
            jscores.append(score)
        jscores.sort()

        self.assertGreater(jscores[round(len(jscores) * 0.5)], 0.15)
        self.assertGreater(jscores[round(len(jscores) * 0.75)], 0.3)
        self.assertGreater(jscores[round(len(jscores) * 0.9)], 0.45)
