import os
from collections import defaultdict
from unittest import TestCase

from src.data.brain_regions import REGIONS
from src.data.local_data_loader import (
    unpickle_neuron_db,
    read_csv,
)
from src.data.neuron_data_initializer import (
    NEURON_DATA_ATTRIBUTE_TYPES,
    hemisphere_fingerprint,
)
from src.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
    TESTING_DATA_SNAPSHOT_VERSION,
)
from src.utils.formatting import (
    compact_label,
    make_web_safe,
    is_proper_textual_annotation,
)
from tests import TEST_DATA_ROOT_PATH
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


class NeuronDataTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

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

        def check_num_values_missing(attrib, upper_bound):
            num_missing = len(
                [1 for nd in self.neuron_db.neuron_data.values() if not nd[attrib]]
            )
            self.assertLessEqual(
                num_missing,
                upper_bound,
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
            "morphology_cluster": 84000,
            "connectivity_cluster": 84000,
            "hemisphere_fingerprint": 5000,
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
        gaba_rids = self.neuron_db.search("nt == gaba")
        self.assertGreater(len(gaba_rids), 1000)
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(gaba_rids) + len(self.neuron_db.search("nt != gaba")),
        )
        for rid in gaba_rids:
            self.assertEqual("GABA", self.neuron_db.get_neuron_data(rid)["nt_type"])

        ach_rids = self.neuron_db.search("nt == ACH")
        self.assertGreater(len(ach_rids), 1000)
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(ach_rids) + len(self.neuron_db.search("nt != ACH")),
        )
        for rid in ach_rids:
            self.assertEqual("ACH", self.neuron_db.get_neuron_data(rid)["nt_type"])

        gaba_and_ach_rids = self.neuron_db.search("nt == ACH && nt == gaba")
        self.assertEqual(0, len(gaba_and_ach_rids))

        gaba_or_ach_rids = self.neuron_db.search("nt == ACH || nt == gaba")
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
        self.assertLess(len(self.neuron_db.search("gaba && nt != gaba")), 700)

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
            len(self.neuron_db.search("fru {and} central && nt != gaba")), 500
        )

    def test_downstream_upstream_queries(self):
        downstream = self.neuron_db.search("{downstream} 720575940646952324")
        self.assertEqual(115, len(downstream))

        upstream = self.neuron_db.search("{upstream} 720575940646952324")
        self.assertEqual(204, len(upstream))

    def test_downstream_upstream_region_queries(self):
        downstream = self.neuron_db.search(
            "left {downstream_region} 720575940643467886"
        )
        self.assertEqual(16, len(downstream))
        downstream = self.neuron_db.search(
            "right {downstream_region} 720575940643467886"
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

        upstream = self.neuron_db.search("left {upstream_region} 720575940643467886")
        self.assertEqual(38, len(upstream))
        upstream = self.neuron_db.search("right {upstream_region} 720575940643467886")
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
        expected_list_length = 340
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("cell_type"))
        )

    def test_hemibrain_types(self):
        expected_list_length = 2897
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("hemibrain_type"))
        )

    def test_hemilineage(self):
        expected_list_length = 188
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("hemilineage"))
        )

    def test_sizes(self):
        for nd in self.neuron_db.neuron_data.values():
            ln = nd["length_nm"]
            area = nd["area_nm"]
            volume = nd["size_nm"]
            self.assertGreater(ln, 1000)
            self.assertGreater(area, 1000 * 1000)
            self.assertGreater(volume, 1000 * 1000 * 1000)
            self.assertGreater(area, ln)
            self.assertGreater(volume, area + ln)

    def test_hemisphere_fingerprint(self):
        self.assertEqual(
            "Left/Right",
            hemisphere_fingerprint(["AMMC_L", "IPS_L"], ["IPS_R"]),
        )
        self.assertEqual(
            "Mix/Mix",
            hemisphere_fingerprint(
                ["AMMC_L", "GNG", "IPS_L", "IPS_R", "SAD"], ["GNG", "IPS_R", "SAD"]
            ),
        )
        self.assertEqual(
            "None/Mix", hemisphere_fingerprint([], ["GNG", "IPS_R", "SAD"])
        )
        self.assertEqual("", hemisphere_fingerprint([], []))

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
            ld = [compact_label(label["label"]) for label in label_data.get(rid, [])]
            if sorted(set(nd["label"])) != sorted(set(ld)):
                print(f'{sorted(set(nd["label"]))} -> {sorted(set(ld))}')
                mismatch += 1
        self.assertLess(mismatch, 10)

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
                if k == "label":
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
