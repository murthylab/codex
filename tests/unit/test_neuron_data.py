import os
import string
from collections import defaultdict
from unittest import TestCase

from codex.data.auto_naming import assign_names_from_annotations
from codex.data.brain_regions import REGIONS, HEMISPHERES
from codex.data.local_data_loader import (
    read_csv,
)
from codex.data.neuron_data_initializer import (
    NEURON_DATA_ATTRIBUTE_TYPES,
)
from codex.data.structured_search_filters import STRUCTURED_SEARCH_ATTRIBUTES
from codex.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from codex.utils.formatting import (
    make_web_safe,
    is_proper_textual_annotation,
)
from codex.utils.label_cleaning import significant_diff_chars
from codex.utils.parsing import tokenize
from tests import TEST_DATA_ROOT_PATH, log_dev_url_for_root_ids, get_testing_neuron_db
from codex.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


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
            "hemilineage": 128000,
            "flow": 5150,
            "side": 14000,
            "nerve": 130000,
            "input_cells": 18500,
            "input_neuropils": 18500,
            "input_synapses": 18500,
            "output_cells": 17000,
            "output_neuropils": 17000,
            "output_synapses": 17000,
            "nt_type": 19658,
            "nt_type_score": 19658,
            "ach_avg": 17200,
            "da_avg": 35500,
            "gaba_avg": 31000,
            "glut_avg": 32000,
            "oct_avg": 89000,
            "ser_avg": 98000,
            "similar_cell_scores": 20000,
            "similar_connectivity_scores": 20000,
            "marker": 139255,
            "mirror_twin_root_id": 139255,
            "length_nm": 1000,
            "area_nm": 1000,
            "size_nm": 1000,
            "connectivity_tag": 21000,
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
        rid = self.neuron_db.search("cell_type == CT1")[0]
        downstream = self.neuron_db.search("{downstream} " + str(rid))
        self.assertEqual(6399, len(downstream))

        upstream = self.neuron_db.search("{upstream} " + str(rid))
        self.assertEqual(5080, len(upstream))

        reciprocal = self.neuron_db.search("{reciprocal} " + str(rid))
        self.assertEqual(3684, len(reciprocal))

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
            "CX",
            "DAN",
            "Kenyon_Cell",
            "LHCENT",
            "LHLN",
            "MBIN",
            "MBON",
            "TPN",
            "TuBu",
            "bilateral",
            "gustatory",
            "hygrosensory",
            "mechanosensory",
            "ocellar",
            "olfactory",
            "optic_lobe_intrinsic",
            "optic_lobes",
            "pars_intercerebralis",
            "pars_lateralis",
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
            "AN_AMMC_SAD",
            "AN_AVLP",
            "AN_AVLP_GNG",
            "AN_AVLP_PVLP",
            "AN_AVLP_SAD",
            "AN_FLA",
            "AN_FLA_GNG",
            "AN_FLA_PRW",
            "AN_FLA_SMP",
            "AN_FLA_VES",
            "AN_GNG",
            "AN_GNG_AMMC",
            "AN_GNG_AVLP",
            "AN_GNG_FLA",
            "AN_GNG_IPS",
            "AN_GNG_PRW",
            "AN_GNG_SAD",
            "AN_GNG_SPS",
            "AN_GNG_VES",
            "AN_GNG_WED",
            "AN_IPS_GNG",
            "AN_IPS_LAL",
            "AN_IPS_SPS",
            "AN_IPS_WED",
            "AN_LAL",
            "AN_LH_AVLP",
            "AN_PRW_FLA",
            "AN_SAD_GNG",
            "AN_SLP_AVLP",
            "AN_SLP_LH",
            "AN_SMP",
            "AN_SMP_FLA",
            "AN_SPS_GNG",
            "AN_SPS_IPS",
            "AN_VES_GNG",
            "AN_VES_WED",
            "AN_WED_GNG",
            "AN_multi",
            "DRA",
            "L1-5",
            "SA_DMT_ADMN",
            "SA_DMT_DMetaN",
            "SA_MDA",
            "SA_VTV_DProN",
            "SA_VTV_PDMN",
            "SA_VTV_pro_meso_meta",
            "accessory_pharyngeal_nerve_sensory_group1",
            "accessory_pharyngeal_nerve_sensory_group2",
            "auditory",
            "bitter",
            "centrifugal",
            "circadian_clock",
            "columnar",
            "descending",
            "distal_medulla",
            "distal_medulla_dorsal_rim_area",
            "eye_bristle",
            "head_bristle",
            "lamina_intrinsic",
            "lamina_monopolar",
            "lamina_tangential",
            "lamina_wide_field",
            "lobula_intrinsic",
            "lobula_lobula_plate_tangential",
            "lobula_medulla_amacrine",
            "lobula_medulla_tangential",
            "lobula_plate_intrinsic",
            "low-salt",
            "medulla_intrinsic",
            "medulla_lobula_lobula_plate_amacrine",
            "medulla_lobula_tangential",
            "multiglomerular",
            "ocellar",
            "ocellar_interneuron",
            "pharyngeal_nerve_sensory_group1",
            "pharyngeal_nerve_sensory_group2",
            "photo_receptor",
            "proximal_distal_medulla_tangential",
            "proximal_medulla",
            "ring_neuron",
            "serpentine_medulla",
            "sugar/water",
            "t1_neuron",
            "t2_neuron",
            "t3_neuron",
            "t4_neuron",
            "t5_neuron",
            "tangential",
            "taste_peg",
            "translobula_plate",
            "transmedullary",
            "transmedullary_y",
            "uniglomerular",
            "water_PN",
            "weirdos",
            "y_neuron",
        ]
        self.assertEqual(expected_list, self.neuron_db.unique_values("sub_class"))

    def test_cell_types(self):
        expected_list_length = 8547
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("cell_type"))
        )

    def test_hemilineage(self):
        expected_list_length = 199
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("hemilineage"))
        )

    def test_connectivity_tag(self):
        expected_list_length = 8
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("connectivity_tag"))
        )

    def test_sizes(self):
        for nd in self.neuron_db.neuron_data.values():
            ln = nd["length_nm"]
            area = nd["area_nm"]
            volume = nd["size_nm"]
            if ln:
                self.assertGreater(ln, 1000)
                self.assertGreater(area, 1000 * 1000)
                self.assertGreater(volume, 1000 * 1000)
                self.assertGreater(area, ln)
                self.assertGreater(volume, area + ln)

    def test_get_neuron_data(self):
        self.assertGreater(
            len(self.neuron_db.get_neuron_data(root_id=720575940624056624)), 5
        )
        self.assertGreater(
            len(self.neuron_db.get_neuron_data(root_id="720575940624056624")), 5
        )

    def test_no_garbage_labels(self):
        for nd in self.neuron_db.neuron_data.values():
            labels = nd["label"]
            self.assertEqual(len(labels), len(set(labels)))
            self.assertTrue(all(labels))
            for lbl in labels:
                self.assertFalse(lbl.startswith("72"), lbl)
                for garbage in [
                    "sorry",
                    "wrong",
                    "accident",
                    "mistake",
                    "error",
                    "part of comprehensive neck connective tracing",
                ]:
                    self.assertFalse(
                        garbage.lower() in lbl.lower(),
                        f"{lbl} contains {garbage}, all labels: {labels}",
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
            "da_avg",
            "oct_avg",
            "ser_avg",
            "class",
            "sub_class",
            "cell_type",
            "hemilineage",
            "connectivity_tag",
            "marker",
        }
        for k, v in NEURON_DATA_ATTRIBUTE_TYPES.items():
            if k in sparse_attrs:
                continue
            num_vals = len([n[k] for n in self.neuron_db.neuron_data.values() if n[k]])
            self.assertGreater(num_vals / len(self.neuron_db.neuron_data), 0.85, k)

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
                                    f"Separator '{sep}' breaks prefix: {lbl1} -> {lbl2}",
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
        self.assertEqual(1465, len(similar_cell_scores))

    def test_dynamic_ranges(self):
        self.assertEqual(
            {
                "data_class_range": [
                    "optic_lobe_intrinsic",
                    "visual",
                    "Kenyon_Cell",
                    "CX",
                    "mechanosensory",
                    "AN",
                    "olfactory",
                    "ALPN",
                    "LHLN",
                    "ALLN",
                    "gustatory",
                    "DAN",
                    "bilateral",
                    "TuBu",
                    "unknown_sensory",
                    "MBON",
                    "hygrosensory",
                    "ocellar",
                    "LHCENT",
                    "pars_intercerebralis",
                    "thermosensory",
                    "pars_lateralis",
                    "ALIN",
                    "optic_lobes",
                    "ALON",
                    "MBIN",
                    "TPN",
                ],
                "data_connectivity_tag_range": [
                    "feedforward_loop_participant",
                    "reciprocal",
                    "3_cycle_participant",
                    "rich_club",
                    "highly_reciprocal_neuron",
                    "nsrn",
                    "integrator",
                    "broadcaster",
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
                "data_nt_type_range": ["ACH", "GLUT", "GABA", "SER", "DA", "OCT"],
                "data_side_range": ["left", "right", "center"],
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
                        data_range_key not in self.neuron_db.dynamic_ranges(), attr.name
                    )
                else:
                    self.assertEqual(
                        set(attr.value_range),
                        set(self.neuron_db.dynamic_ranges()[data_range_key]),
                        attr.name,
                    )

    def test_naming(self):
        all_nds = list(self.neuron_db.neuron_data.values())

        # all names are unique ignoring case
        self.assertEqual(len(set([nd["name"].lower() for nd in all_nds])), len(all_nds))

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

    def test_connectivity_tags(self):
        ct_counts = defaultdict(int)
        for nd in self.neuron_db.neuron_data.values():
            for ct in nd["connectivity_tag"]:
                ct_counts[ct] += 1
        self.assertEqual(
            {
                "3_cycle_participant": 68791,
                "broadcaster": 477,
                "feedforward_loop_participant": 118277,
                "highly_reciprocal_neuron": 2440,
                "integrator": 671,
                "nsrn": 684,
                "reciprocal": 81245,
                "rich_club": 41760,
            },
            ct_counts,
        )
