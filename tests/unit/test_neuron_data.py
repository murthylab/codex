import json
from unittest import TestCase

from src.data.brain_regions import neuropil_description
from src.data.neuron_data import *
from src.data.structured_search_filters import *
from src.data.local_data_loader import unpickle_all_neuron_db_versions

# for IDE test
from src.data.versions import DATA_SNAPSHOT_VERSIONS, LATEST_DATA_SNAPSHOT_VERSION
from src.utils.graph_algos import neighbors
from tests import TEST_DATA_ROOT_PATH


class NeuronDataTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_dbs = unpickle_all_neuron_db_versions(
            data_root_path=TEST_DATA_ROOT_PATH
        )
        cls.neuron_db = cls.neuron_dbs[LATEST_DATA_SNAPSHOT_VERSION]

    def test_loading(self):
        # check that all versions loaded
        versions = DATA_SNAPSHOT_VERSIONS
        for v in versions:
            self.assertIsNotNone(self.neuron_dbs[v])
            self.assertEqual(
                set(self.neuron_dbs[v].neuron_data.keys()),
                set(self.neuron_dbs[v].search_index.all_doc_ids()),
            )

    def test_index_data(self):
        assert 60000 < len(self.neuron_db.neuron_data)

        def check_min_values_present(attrib, lower_bound):
            num_present = len(
                [1 for nd in self.neuron_db.neuron_data.values() if nd[attrib]]
            )
            self.assertGreaterEqual(num_present, lower_bound)

        check_min_values_present("name", 66812)
        check_min_values_present("nt_type", 67852)
        check_min_values_present("hemisphere_fingerprint", 66633)
        check_min_values_present("classes", 10782)
        check_min_values_present("similar_root_ids", 66633)
        check_min_values_present("similar_root_id_scores", 66633)
        check_min_values_present("symmetrical_root_ids", 66633)
        check_min_values_present("symmetrical_root_id_scores", 66633)
        check_min_values_present("input_neuropils", 63308)
        check_min_values_present("output_neuropils", 64302)
        check_min_values_present("supervoxel_id", 22155)
        check_min_values_present("tag", 30026)
        check_min_values_present("inherited_tag_root_id", 2871)
        check_min_values_present("inherited_tag_score", 2871)
        check_min_values_present("user_id", 23155)
        check_min_values_present("position", 68375)

    def test_annotations(self):
        neurons_with_tags = [n for n in self.neuron_db.neuron_data.values() if n["tag"]]
        self.assertGreater(len(neurons_with_tags), 25000)

        neurons_with_annotations = [
            n for n in self.neuron_db.neuron_data.values() if n["annotations"]
        ]
        self.assertEqual(len(neurons_with_tags), len(neurons_with_annotations))

        neurons_with_inherited_labels = [
            n for n in neurons_with_annotations if "*" in n["annotations"]
        ]
        self.assertGreater(len(neurons_with_inherited_labels), 2800)

        for n in self.neuron_db.neuron_data.values():
            for col in [
                "classes",
                "similar_root_ids",
                "symmetrical_root_ids",
                "input_neuropils",
                "output_neuropils",
                "supervoxel_id",
                "tag",
                "user_id",
                "position",
            ]:
                self.assertEqual(len(set(n[col])), len(n[col]))

        # closest term search
        self.assertEqual(
            self.neuron_db.closest_token("blobe", case_sensitive=False), "lobe"
        )
        self.assertEqual(
            self.neuron_db.closest_token("blobe", case_sensitive=True), "lobe"
        )
        self.assertEqual(
            self.neuron_db.closest_token("BLOBE", case_sensitive=True), "LB3"
        )

        # don't suggest in structured queries
        self.assertEqual(
            self.neuron_db.closest_token("BLO==BE", case_sensitive=True), None
        )
        self.assertEqual(
            self.neuron_db.closest_token("BLOBE && Lb3", case_sensitive=False), None
        )

        self.assertEqual(
            self.neuron_db.closest_token_from_inherited_tags(
                "blobe", case_sensitive=False
            ),
            "lobe",
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
                    if nd["classes"]
                ]
            ),
        )

    def test_structured_search_case(self):
        # case sensitive vs insensitive search
        class_matches = self.neuron_db.search(
            "class == descending", case_sensitive=True
        )
        self.assertEqual(len(class_matches), 0)
        class_matches = self.neuron_db.search("class == descending")
        self.assertGreater(len(class_matches), 1000)

        # starts with op
        self.assertGreater(len(self.neuron_db.search("label {starts_with} LC")), 500)
        self.assertGreater(len(self.neuron_db.search("label {starts_with} lc")), 500)
        self.assertEqual(
            len(self.neuron_db.search("label {starts_with} lc", case_sensitive=True)), 0
        )
        self.assertGreater(len(self.neuron_db.search("id {starts_with} 72")), 65000)

    def test_structured_search_lists(self):
        # explicit searches
        hundred_root_ids = list(self.neuron_db.neuron_data.keys())[:100]
        root_id_search_explicit = self.neuron_db.search(
            " || ".join([f"id == {rid}" for rid in hundred_root_ids])
        )
        self.assertEqual(set(root_id_search_explicit), set(hundred_root_ids))
        root_id_search_membership = self.neuron_db.search(
            f"id << {','.join([str(rid) for rid in hundred_root_ids])}"
        )
        self.assertEqual(set(root_id_search_explicit), set(root_id_search_membership))
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(hundred_root_ids)
            + len(
                self.neuron_db.search(
                    " && ".join([f"id != {rid}" for rid in hundred_root_ids])
                )
            ),
        )
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(hundred_root_ids)
            + len(
                self.neuron_db.search(
                    f"id !< {','.join([str(rid) for rid in hundred_root_ids])}"
                )
            ),
        )

    def test_structured_search_misc(self):
        self.assertLess(len(self.neuron_db.search("gaba && nt != gaba")), 700)

        self.assertEqual(
            2, len(self.neuron_db.search("720575940624284903 720575940625504714"))
        )
        self.assertEqual(
            2, len(self.neuron_db.search("720575940624284903,720575940625504714"))
        )
        self.assertEqual(
            2, len(self.neuron_db.search("720575940624284903, 720575940625504714"))
        )

    def test_downstream_upstream_queries(self):
        downstream = self.neuron_db.search("{downstream} 720575940629495808")
        self.assertEqual(55, len(downstream))

        upstream = self.neuron_db.search("{upstream} 720575940629495808")
        self.assertEqual(18, len(upstream))

    def test_downstream_upstream_region_queries(self):
        downstream = self.neuron_db.search(
            "left {downstream_region} 720575940629495808"
        )
        self.assertEqual(40, len(downstream))
        downstream = self.neuron_db.search(
            "right {downstream_region} 720575940629495808"
        )
        self.assertEqual(15, len(downstream))
        downstream = self.neuron_db.search(
            "center {downstream_region} 720575940629495808"
        )
        self.assertEqual(
            [720575940611639794, 720575940636691824, 720575940626476038], downstream
        )

        upstream = self.neuron_db.search("left {upstream_region} 720575940629495808")
        self.assertEqual(8, len(upstream))
        upstream = self.neuron_db.search("right {upstream_region} 720575940629495808")
        self.assertEqual(3, len(upstream))
        upstream = self.neuron_db.search("center {upstream_region} 720575940629495808")
        self.assertEqual(10, len(upstream))

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

    def test_neuropils(self):
        expected_list = [
            "AL_L",
            "AL_R",
            "AME_L",
            "AME_R",
            "AMMC_L",
            "AMMC_R",
            "AOTU_L",
            "AOTU_R",
            "ATL_L",
            "ATL_R",
            "AVLP_L",
            "AVLP_R",
            "BU_L",
            "BU_R",
            "CAN_L",
            "CAN_R",
            "CRE_L",
            "CRE_R",
            "EB",
            "EPA_L",
            "EPA_R",
            "FB",
            "FLA_L",
            "FLA_R",
            "GA_L",
            "GA_R",
            "GNG",
            "GOR_L",
            "GOR_R",
            "IB_L",
            "IB_R",
            "ICL_L",
            "ICL_R",
            "IPS_L",
            "IPS_R",
            "LAL_L",
            "LAL_R",
            "LH_L",
            "LH_R",
            "LOP_L",
            "LOP_R",
            "LO_L",
            "LO_R",
            "MB_CA_L",
            "MB_CA_R",
            "MB_ML_L",
            "MB_ML_R",
            "MB_PED_L",
            "MB_PED_R",
            "MB_VL_L",
            "MB_VL_R",
            "ME_L",
            "ME_R",
            "NO",
            "PB",
            "PLP_L",
            "PLP_R",
            "PRW",
            "PVLP_L",
            "PVLP_R",
            "SAD",
            "SCL_L",
            "SCL_R",
            "SIP_L",
            "SIP_R",
            "SLP_L",
            "SLP_R",
            "SMP_L",
            "SMP_R",
            "SPS_L",
            "SPS_R",
            "VES_L",
            "VES_R",
            "WED_L",
            "WED_R",
        ]
        self.assertEqual(set(expected_list), set(REGIONS.keys()))
        self.assertEqual(expected_list, self.neuron_db.neuropils())

    def test_classes(self):
        expected_list = [
            "Ascending",
            "Central Brain",
            "Descending",
            "Optic Lobe",
            "Sensory",
            "Visual Projection",
        ]
        self.assertEqual(expected_list, self.neuron_db.classes())

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

    def test_augmentation_loading(self):
        self.assertGreater(
            len(self.neuron_db.search_in_neurons_with_inherited_labels("")), 2800
        )
        self.assertGreater(
            len(self.neuron_db.search_in_neurons_with_inherited_labels("da")), 500
        )

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

        def analyze_set(rid_set):
            def class_breakdown(rids):
                res = defaultdict(int)
                for rid in rids:
                    res[self.neuron_db.get_neuron_data(rid)["class"]] += 1
                return json.dumps(res, indent=4)

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

            found_rids = [i for i in rid_set if i in self.neuron_db.neuron_data]
            print(
                f"### Num seg ids: {len(rid_set)}, found in 447 dataset: {len(found_rids)}"
            )
            ustream = neighbors(found_rids, self.neuron_db.input_sets())
            dstream = neighbors(found_rids, self.neuron_db.output_sets())
            print(
                f"### Upstream partners (# cells): {len(ustream)}, downstream partners: {len(dstream)}"
            )
            print(f"### Upstream partners breakdown: {class_breakdown(ustream)}")
            print(f"### Downstream partners breakdown: {class_breakdown(dstream)}")
            in_pils, out_pils = pil_breakdown(rid_set)
            print(f"### Input brain regions breakdown (# synapses): {in_pils}")
            print(f"### Output brain regions breakdown (# synapses): {out_pils}")

        for k, v in cell_lines.items():
            print(f"\n\n## Cell line {k}")
            analyze_set(v)

        # TODO: remove this: self.fail()
