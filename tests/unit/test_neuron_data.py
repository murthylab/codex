import json
import os
from unittest import TestCase
from collections import defaultdict

from src.data.brain_regions import neuropil_description, REGIONS
from src.data.neuron_data import NEURON_DATA_ATTRIBUTES, NeuronDB
from src.data.local_data_loader import (
    unpickle_all_neuron_db_versions,
    unpickle_neuron_db,
    read_csv,
)
from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION
from src.utils.formatting import compact_label, make_web_safe
from src.utils.graph_algos import neighbors
from tests import TEST_DATA_ROOT_PATH
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


class NeuronDataTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=DEFAULT_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

    def test_loading(self):
        # check that all versions loaded
        neuron_dbs = unpickle_all_neuron_db_versions(data_root_path=TEST_DATA_ROOT_PATH)
        for v in DATA_SNAPSHOT_VERSIONS:
            self.assertIsNotNone(neuron_dbs[v])
            self.assertEqual(
                set(neuron_dbs[v].neuron_data.keys()),
                set(neuron_dbs[v].search_index.all_doc_ids()),
            )

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
            "label": 76000,
            "super_class": 5200,
            "class": 37000,
            "sub_class": 116000,
            "cell_type": 100000,
            "flow": 5150,
            "side": 14000,
            "nerve_type": 110000,
            "input_cells": 4000,
            "input_neuropils": 4000,
            "input_synapses": 4000,
            "output_cells": 4000,
            "output_neuropils": 4000,
            "output_synapses": 4000,
            "similar_cell_scores": 76000,  # TODO: import 571 NBLAST scores and reduce bound
            "nt_type": 11000,
            "nt_type_score": 10000,
            "ach_avg": 4000,
            "da_avg": 9500,
            "gaba_avg": 6000,
            "glut_avg": 6500,
            "oct_avg": 35000,
            "ser_avg": 61000,
        }

        for k in NEURON_DATA_ATTRIBUTES.keys():
            check_num_values_missing(k, expected_missing_value_bounds.get(k, 0))

    def test_annotations_web_safe(self):
        set_of_all_annotations = set()
        for nd in self.neuron_db.neuron_data.values():
            for v in nd.values():
                if isinstance(v, dict):
                    set_of_all_annotations |= set(v.keys())
                    set_of_all_annotations |= set(v.values())
                elif isinstance(v, list) or isinstance(v, set):
                    set_of_all_annotations |= set(v)
                else:
                    set_of_all_annotations.add(v)
        self.assertEqual(
            set([type(a) for a in set_of_all_annotations]), {str, int, float}
        )

        for anno in set_of_all_annotations:
            if type(anno) != str:
                continue
            self.assertEqual(anno, make_web_safe(anno))

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
        self.assertGreater(len(self.neuron_db.search("da")), 6000)
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

    def test_downstream_upstream_queries(self):
        downstream = self.neuron_db.search("{downstream} 720575940646952324")
        self.assertEqual(104, len(downstream))

        upstream = self.neuron_db.search("{upstream} 720575940646952324")
        self.assertEqual(180, len(upstream))

    def test_downstream_upstream_region_queries(self):
        downstream = self.neuron_db.search(
            "left {downstream_region} 720575940643467886"
        )
        self.assertEqual(14, len(downstream))
        downstream = self.neuron_db.search(
            "right {downstream_region} 720575940643467886"
        )
        self.assertEqual(0, len(downstream))
        downstream = self.neuron_db.search(
            "center {downstream_region} 720575940643467886"
        )
        self.assertEqual(
            sorted([720575940619266870, 720575940620960347, 720575940632905164]),
            sorted(downstream),
        )

        upstream = self.neuron_db.search("left {upstream_region} 720575940643467886")
        self.assertEqual(34, len(upstream))
        upstream = self.neuron_db.search("right {upstream_region} 720575940643467886")
        self.assertEqual(0, len(upstream))
        upstream = self.neuron_db.search("center {upstream_region} 720575940643467886")
        self.assertEqual(5, len(upstream))

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
        self.assertLess(
            len(
                self.neuron_db.search(
                    "label {contains} dsx && label {not_contains} dsx"
                )
            ),
            100,
        )

    def test_not_connected_cells(self):
        connected_cells = set(self.neuron_db.input_sets().keys()).union(
            set(self.neuron_db.output_sets().keys())
        )
        not_connected_cells = set(self.neuron_db.neuron_data.keys()) - connected_cells
        self.assertGreater(2000, len(not_connected_cells))

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

        input_neuropils = defaultdict(set)
        output_neuropils = defaultdict(set)
        for r in self.neuron_db.connection_rows:
            self.assertTrue(r[2] in REGIONS)
            input_neuropils[r[1]].add(r[2])
            output_neuropils[r[0]].add(r[2])
        for nd in self.neuron_db.neuron_data.values():
            self.assertEqual(
                sorted(input_neuropils[nd["root_id"]]), sorted(nd["input_neuropils"])
            )
            self.assertEqual(
                sorted(output_neuropils[nd["root_id"]]), sorted(nd["output_neuropils"])
            )

    def test_classes(self):
        expected_list = [
            "ALIN",
            "ALLN",
            "ALON",
            "ALPN",
            "AMMC",
            "AN",
            "CSD",
            "CX",
            "DAN",
            "DN",
            "Kenyon_Cell",
            "LHCENT",
            "MBIN",
            "MBON",
            "bilateral",
            "endocrine",
            "fragment",
            "gustatory",
            "hygrosensory",
            "mAL",
            "mechanosensory",
            "motor",
            "ocellar",
            "olfactory",
            "optic_lobes",
            "putative_glia",
            "ring neuron",
            "thermosensory",
            "unknown_sensory",
        ]
        self.assertEqual(expected_list, self.neuron_db.classes())

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
        self.assertEqual(expected_list, self.neuron_db.super_classes())

    def test_sub_classes(self):
        expected_list = [
            "auditory",
            "eye bristle",
            "multiglomerular",
            "ocellar_interneuron",
            "taste bristle",
            "taste peg",
            "uniglomerular",
        ]
        self.assertEqual(expected_list, self.neuron_db.sub_classes())

    def test_cell_types(self):
        expected_list_length = 1412
        self.assertEqual(expected_list_length, len(self.neuron_db.cell_types()))

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
            NeuronDB.hemisphere_fingerprint(["AMMC_L", "IPS_L"], ["IPS_R"]),
        )
        self.assertEqual(
            "Mix/Mix",
            NeuronDB.hemisphere_fingerprint(
                ["AMMC_L", "GNG", "IPS_L", "IPS_R", "SAD"], ["GNG", "IPS_R", "SAD"]
            ),
        )
        self.assertEqual(
            "None/Mix", NeuronDB.hemisphere_fingerprint([], ["GNG", "IPS_R", "SAD"])
        )
        self.assertEqual("", NeuronDB.hemisphere_fingerprint([], []))

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

    def test_cell_lines(self):
        cell_lines = {
            "SS16374": [
                20575940630957779,
                720575940625450312,
                720575940615424546,
                720575940618654017,
                720575940625952074,
                720575940625430856,
                720575940602224096,
                720575940602245088,
                720575940626442139,
                720575940622314995,
                720575940630043729,
                720575940632927736,
                720575940625481032,
                720575940619709609,
                720575940602629548,
                720575940603683505,
                720575940608425336,
                720575940621713672,
                720575940610457458,
            ],
            "SS27885": [
                720575940644319796,
                720575940619583749,
                720575940620171478,
                720575940633065720,
                720575940627354368,
                720575940617390027,
            ],
            "SS23281": [
                720575940618477806,
                720575940627513079,
                720575940615798045,
                720575940617193009,
                720575940625839345,
                720575940615348770,
                720575940623748298,
                720575940620191453,
                720575940603331686,
                720575940617943205,
                720575940624172290,
                720575940615530580,
                720575940629414201,
                720575940632722527,
                720575940624150168,
                720575940611667251,
                720575940614662027,
                720575940641565600,
                720575940612965791,
                720575940619587422,
                720575940615729179,
                720575940639821965,
                720575940627775292,
                720575940606202891,
                720575940617842196,
            ],
            "SS29378": [],
            "SS40354": [],
        }

        raw_data = {}

        def analyze_set(rid_set):
            def class_breakdown(rids):
                counts = defaultdict(int)
                lists = defaultdict(list)
                for rid in rids:
                    counts[self.neuron_db.get_neuron_data(rid)["class"]] += 1
                    lists[self.neuron_db.get_neuron_data(rid)["class"]].append(rid)
                res = {
                    cl: f"{cnt} {codex_link(lists[cl])}" for cl, cnt in counts.items()
                }
                str_res = "\n"
                for k, v in res.items():
                    str_res += f"{k}: {v}\n"
                return str_res

            def pil_breakdown(rids):
                rids = set(rids)
                in_pils = defaultdict(int)
                out_pils = defaultdict(int)
                for r in self.neuron_db.connection_rows:
                    if r[0] in rids:
                        out_pils[f"{r[2]} {neuropil_description(r[2])}"] += r[3]
                    if r[1] in rids:
                        in_pils[f"{r[2]} {neuropil_description(r[2])}"] += r[3]
                return json.dumps(in_pils, indent=4), json.dumps(out_pils, indent=4)

            def codex_link(rids):
                return (
                    f"[(see in codex)](https://codex.flywire.ai/app/search?filter_string="
                    f"id<<{','.join([str(rid) for rid in rids])})"
                )

            found_rids = [i for i in rid_set if i in self.neuron_db.neuron_data]
            print(
                f"### Num seg ids: {len(rid_set)}, found in {DEFAULT_DATA_SNAPSHOT_VERSION} dataset: {len(found_rids)} {codex_link(found_rids)}"
            )
            ustream = neighbors(found_rids, self.neuron_db.input_sets())
            dstream = neighbors(found_rids, self.neuron_db.output_sets())

            print(
                f"#### Upstream partners: {len(ustream)} {codex_link(ustream)}, downstream partners: {len(dstream)} {codex_link(dstream)}"
            )
            print(f"#### Upstream partners breakdown:{class_breakdown(ustream)}")
            print(f"#### Downstream partners breakdown:{class_breakdown(dstream)}")
            in_pils, out_pils = pil_breakdown(rid_set)
            print(f"#### Input brain regions breakdown (# synapses): {in_pils}")
            print(f"#### Output brain regions breakdown (# synapses): {out_pils}")
            return {
                "Root IDs": rid_set,
                "Found Root IDs": found_rids,
                "Upstream": {
                    int(rid): self.neuron_db.get_neuron_data(rid)["class"]
                    for rid in ustream
                },
                "Downstream": {
                    int(rid): self.neuron_db.get_neuron_data(rid)["class"]
                    for rid in dstream
                },
            }

        for k, v in cell_lines.items():
            print(f"\n\n## Cell line {k}")
            rawd = analyze_set(v)
            raw_data[k] = rawd

        print(f"## Raw data: {json.dumps(raw_data, indent=4)}")

        # TODO: remove this: self.fail()

    def test_motifs(self):
        roots = {
            "pC1a": [720575940618558379, 720575940618558379],
            "pC1b": [720575940617856320],
            "pC1c": [720575940629430978],
            "pC1d": [720575940618771952, 720575940634370411],
            "pC1e": [720575940636374128, 720575940624024812],
        }

        osets = self.neuron_db.output_sets()
        nt_set = {"GABA"}

        def find_motifs(rid):
            res = []
            dstream = neighbors([rid], neighbor_sets=osets)
            dstream = [
                d
                for d in dstream
                if self.neuron_db.get_neuron_data(d)["nt_type"] in nt_set
            ]
            for d in dstream:
                dstream2 = [
                    d2
                    for d2 in osets[d]
                    if self.neuron_db.get_neuron_data(d2)["nt_type"] in nt_set
                ]
                for d2 in dstream2:
                    res.append((d, d2))
            return res

        def codex_link(rids):
            return (
                f"[(see in codex)](https://codex.flywire.ai/app/search?filter_string="
                f"id<<{','.join([str(rid) for rid in rids])})"
            )

        for k, v in roots.items():
            for rid in v:
                motifs = find_motifs(rid)
                for mtf in motifs:
                    print(
                        f"{k}: {rid} {self.neuron_db.get_neuron_data(rid)['nt_type']}"
                        f" -> {mtf[0]} {self.neuron_db.get_neuron_data(mtf[0])['nt_type']}"
                        f" -> {mtf[1]} {self.neuron_db.get_neuron_data(mtf[1])['nt_type']}"
                    )

        # self.fail()

    def test_thumbnails(self):
        # Run this first to collect existing skeleton root ids:
        # gsutil du gs://flywire-data/codex/526/skeleton_thumbnails | grep png | cut -d"/" -f 6 | cut -d "." -f 1 > static/raw_data/526/thumbnails_tmp.csv
        fname = f"{TEST_DATA_ROOT_PATH}/../raw_data/{DEFAULT_DATA_SNAPSHOT_VERSION}/thumbnails_tmp.csv"
        if os.path.isfile(fname):
            content = set([int(r[0]) for r in read_csv(fname)])
            self.assertEqual(
                [], [r for r in self.neuron_db.neuron_data.keys() if r not in content]
            )

    def test_twins(self):
        for nd in self.neuron_db.neuron_data.values():
            side = nd["side"]
            size_nm = nd["size_nm"]
            if size_nm < 1097185208320:
                continue
            if len(nd["similar_cell_scores"]) > 50000:
                continue
            for k, v in nd["similar_cell_scores"].items():
                if v > 0.6:
                    twin_side = self.neuron_db.neuron_data[k]["side"]
                    if twin_side != side:
                        print(
                            f"{nd['root_id']}, {k}  score={v}, {nd['size_nm']} side={side}, twin_side={twin_side}"
                        )

    def test_epsilon_nets(self):
        in_pil_sets, out_pil_sets = self.neuron_db.input_output_neuropil_sets()

        all_pils = set(REGIONS.keys())
        covered_in_pils = set()
        covered_out_pils = set()

        remaining_rids = sorted(self.neuron_db.neuron_data.keys())
        epsilon_net = []

        def pick_best():
            return max(
                remaining_rids,
                key=lambda rid: len(in_pil_sets[rid] - covered_in_pils)
                + len(out_pil_sets[rid] - covered_out_pils),
            )

        for i in range(100):
            bst = pick_best()
            covered_in_pils |= in_pil_sets[bst]
            covered_out_pils |= out_pil_sets[bst]
            epsilon_net.append(bst)
            remaining_rids.remove(bst)
            print(f"{i}: {len(covered_in_pils)=} {len(covered_out_pils)=}")
            if len(covered_in_pils) == len(all_pils) and len(covered_out_pils) == len(
                all_pils
            ):
                break

        self.assertLess(len(epsilon_net), 14)

    def test_bridge_neurons(self):
        in_pil_sets, out_pil_sets = self.neuron_db.input_output_neuropil_sets()

        rids = sorted(self.neuron_db.neuron_data.keys())
        region_pairs_to_bridges = defaultdict(list)

        def is_bridge(rid):
            if (
                len(in_pil_sets[rid]) != 1
                or len(out_pil_sets[rid]) != 1
                or in_pil_sets[rid] == out_pil_sets[rid]
            ):
                return False
            region_pairs_to_bridges[
                (next(iter(in_pil_sets[rid])), next(iter(out_pil_sets[rid])))
            ].append(rid)
            return True

        def is_mirror_bridge(rid):
            if (
                len(in_pil_sets[rid]) != 1
                or len(out_pil_sets[rid]) != 1
                or in_pil_sets[rid] == out_pil_sets[rid]
            ):
                return False
            pil_in = list(in_pil_sets[rid])[0]
            if pil_in[-2] != "_":
                return False
            pil_out = list(out_pil_sets[rid])[0]
            if pil_out[-2] != "_":
                return False
            return pil_in[:-2] == pil_out[:-2]

        bridges = [rid for rid in rids if is_bridge(rid)]

        bset = set()
        for k, v in region_pairs_to_bridges.items():
            bset.add(k[0])
            bset.add(k[1])
            print(f"{k}: {v}")

        self.assertLess(60, len(bset))
        self.assertLess(1000, len(bridges))

    def test_attribute_coverage(self):
        sparse_attrs = {
            "similar_cell_scores",
            "label",
            "nerve_type",
            "oct_avg",
            "ser_avg",
            "class",
            "sub_class",
            "cell_type",
        }
        for k, v in NEURON_DATA_ATTRIBUTES.items():
            if k in sparse_attrs:
                continue
            num_vals = len([n[k] for n in self.neuron_db.neuron_data.values() if n[k]])
            self.assertGreater(num_vals / len(self.neuron_db.neuron_data), 0.9, k)
