from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import TESTING_DATA_SNAPSHOT_VERSION
from src.utils.label_cleaning import (
    remove_left_right,
    remove_duplicate_tokens,
    remove_subsumed_tokens,
    compact_label,
    remove_redundant_parts,
    remove_corrected,
    blacklisted,
    dedupe_up_to_insignificant_chars,
    dedupe_prefixes,
    dedupe_with_order,
    clean_and_reduce_labels,
)
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

        cls.raw_labels = set()
        for ld_list in cls.neuron_db.label_data.values():
            for ld in ld_list:
                cls.raw_labels.add(ld["label"])

    def test_dedupe_with_order(self):
        self.assertEqual(
            ["MBp1; right"], dedupe_with_order(["MBp1; right", "MBp1; right"])
        )
        self.assertEqual(
            ["MBp1; right; dopamine"],
            dedupe_with_order(["MBp1; right; dopamine", "MBp1; right; dopamine"]),
        )
        self.assertEqual(
            ["MBp1; right; acetylcholine"],
            dedupe_with_order(
                ["MBp1; right; acetylcholine", "MBp1; right; acetylcholine"]
            ),
        )

    def test_dedupe_prefixes(self):
        self.assertEqual(
            ["SH-JOvd16; Catmaid ID: 10997627", "JO-F"],
            dedupe_prefixes(["SH-JOvd16", "SH-JOvd16; Catmaid ID: 10997627", "JO-F"]),
        )
        self.assertEqual(
            ["JO-FDA_10; Catmaid ID: 3505588"],
            dedupe_prefixes(["JO-FDA_10; Catmaid ID: 3505588", "JO-FDA_10"]),
        )
        self.assertEqual(
            ["JO-FDP_5; Catmaid ID: 11008033"],
            dedupe_prefixes(["JO-FDP_5", "JO-FDP_5; Catmaid ID: 11008033"]),
        )
        self.assertEqual(
            ["JO-FDA_14; Catmaid ID: 8646111"],
            dedupe_prefixes(["JO-FDA_14", "JO-FDA_14; Catmaid ID: 8646111"]),
        )
        self.assertEqual(
            ["AVLP_pr04", "AVLP538 (HB)"],
            dedupe_prefixes(["AVLP_pr04", "AVLP538 (HB)", "AVLP538"]),
        )
        self.assertEqual(
            ["Dm8_L;Dm8; Lacking soma"],
            dedupe_prefixes(["Dm8_L;Dm8", "Dm8_L;Dm8; Lacking soma"]),
        )
        self.assertEqual(
            ["Dm8_L;Dm8; Lacking soma"],
            dedupe_prefixes(["Dm8_L;Dm8", "Dm8_L;Dm8; Lacking soma"]),
        )
        self.assertEqual(
            ["T2; FBbt_00003728"], dedupe_prefixes(["T2", "T2; FBbt_00003728"])
        )
        self.assertEqual(
            ["T2; FBbt_00003728"], dedupe_prefixes(["T2", "T2; FBbt_00003728"])
        )

    def test_dedupe_up_to_insignificant_chars(self):
        self.assertEqual(
            ["PAM01", "PAM01-RHS, y5", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM01-RHS, y5", "putative fru", "PAM01-RHS; y5"]
            ),
        )
        self.assertEqual(
            ["PAM01-RHS, y5", "putative fru", "CREa1_dorsal; right; dopamine", "PAM01"],
            dedupe_up_to_insignificant_chars(
                [
                    "PAM01-RHS, y5",
                    "putative fru",
                    "PAM01-RHS; y5",
                    "CREa1_dorsal; right; dopamine",
                    "PAM01",
                ]
            ),
        )
        self.assertEqual(
            ["PAM01", "PAM01-RHS, y5", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM01-RHS, y5", "putative fru", "PAM01-RHS; y5"]
            ),
        )
        self.assertEqual(
            ["PAM01-LHS; y5", "putative fru", "PAM01"],
            dedupe_up_to_insignificant_chars(
                ["PAM01-LHS; y5", "putative fru", "PAM01", "PAM01-LHS, y5"]
            ),
        )
        self.assertEqual(
            ["PAM01", "PAM01-RHS, y5", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM01-RHS, y5", "putative fru", "PAM01-RHS; y5"]
            ),
        )
        self.assertEqual(
            ["PAM01", "PAM01-RHS, y5", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM01-RHS, y5", "putative fru", "PAM01-RHS; y5"]
            ),
        )
        self.assertEqual(
            ["PAM01", "PAM02-RHS, B`2a", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM02-RHS, B`2a", "PAM02-RHS; B`2a", "putative fru"]
            ),
        )
        self.assertEqual(
            ["PAM01-RHS, y5", "putative fru", "CREa1_dorsal; right; dopamine", "PAM01"],
            dedupe_up_to_insignificant_chars(
                [
                    "PAM01-RHS, y5",
                    "putative fru",
                    "PAM01-RHS; y5",
                    "CREa1_dorsal; right; dopamine",
                    "PAM01",
                ]
            ),
        )
        self.assertEqual(
            ["PAM01", "PAM02-RHS, B`2a", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM02-RHS, B`2a", "PAM02-RHS; B`2a", "putative fru"]
            ),
        )
        self.assertEqual(
            ["PAM01-RHS, y5", "putative fru", "CREa1_dorsal; right; dopamine", "PAM01"],
            dedupe_up_to_insignificant_chars(
                [
                    "PAM01-RHS, y5",
                    "putative fru",
                    "PAM01-RHS; y5",
                    "CREa1_dorsal; right; dopamine",
                    "PAM01",
                ]
            ),
        )
        self.assertEqual(
            ["PAM01-RHS, y5", "putative fru", "CREa1_dorsal; right; dopamine", "PAM01"],
            dedupe_up_to_insignificant_chars(
                [
                    "PAM01-RHS, y5",
                    "putative fru",
                    "PAM01-RHS; y5",
                    "CREa1_dorsal; right; dopamine",
                    "PAM01",
                ]
            ),
        )
        self.assertEqual(
            ["PAM01", "PAM02-RHS, B`2a", "putative fru"],
            dedupe_up_to_insignificant_chars(
                ["PAM01", "PAM02-RHS, B`2a", "PAM02-RHS; B`2a", "putative fru"]
            ),
        )
        self.assertEqual(
            ["Retinula axon; R1-6"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon; R1-6", "Retinula axon: R1-6"]
            ),
        )
        self.assertEqual(
            ["Retinula axon; R7", "Retinula axon; R1-6", "Retinula axon; R8"],
            dedupe_up_to_insignificant_chars(
                [
                    "Retinula axon; R7",
                    "Retinula axon; R1-6",
                    "Retinula axon; R8",
                    "Retinula axon: R8",
                ]
            ),
        )
        self.assertEqual(
            ["Retinula axon", "Retinula axon; R1-6"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon", "Retinula axon; R1-6", "Retinula axon: R1-6"]
            ),
        )
        self.assertEqual(
            ["Retinula axon; R1-6", "Retinula axon\n"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon; R1-6", "Retinula axon: R1-6", "Retinula axon\n"]
            ),
        )
        self.assertEqual(
            ["Retinula axon", "Retinula axon; R1-6"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon", "Retinula axon; R1-6", "Retinula axon: R1-6"]
            ),
        )
        self.assertEqual(
            ["Retinula axon", "Retinula axon; R1-6"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon", "Retinula axon; R1-6", "Retinula axon: R1-6"]
            ),
        )
        self.assertEqual(["T1"], dedupe_up_to_insignificant_chars(["T1", "T1 "]))
        self.assertEqual(
            ["Retinula axon: R8"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon: R8", "Retinula axon; R8"]
            ),
        )
        self.assertEqual(
            ["Retinula axon; R1-6"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon; R1-6", "Retinula axon: R1-6"]
            ),
        )
        self.assertEqual(
            ["Retinula axon; R1-6"],
            dedupe_up_to_insignificant_chars(
                ["Retinula axon; R1-6", "Retinula axon: R1-6"]
            ),
        )
        self.assertEqual(
            [
                "Transmedullary neuron 20, Tm20 [FBbt_00003808] (Fischbach and Dittrich, 1989 and Neuprint)"
            ],
            dedupe_up_to_insignificant_chars(
                [
                    "Transmedullary neuron 20, Tm20 [FBbt_00003808] (Fischbach and Dittrich, 1989 and Neuprint)",
                    "Transmedullary neuron 20, Tm20,[FBbt_00003808] (Fischbach and Dittrich, 1989 and Neuprint)",
                ]
            ),
        )

    def test_blacklisted(self):
        self.assertTrue(blacklisted("720575940611408241"))
        self.assertTrue(blacklisted("correction - not optic lobe"))
        self.assertTrue(blacklisted("not a neuron"))

    def test_remove_blacklisted_2(self):
        nd = {
            "nt_type": "ACH",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "right",
        }
        self.assertEqual(
            ["VLPl1"], clean_and_reduce_labels(["VLPl1", "not a neuron"], nd)
        )

        self.assertEqual(
            ["VLPl1"],
            clean_and_reduce_labels(
                ["720575940611408241", "VLPl1", "not a neuron"], nd
            ),
        )

    def test_remove_corrected(self):
        self.assertEqual(
            ["T1"],
            remove_corrected(["T1; L1 label is wrong", "L1"]),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2"],
            remove_corrected(["Correction: Lamina monopolar 2; L2"]),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2"],
            remove_corrected(["Correction: Lamina monopolar 2; L2", "T1"]),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2"],
            remove_corrected(
                ["Correction: Lamina monopolar 2; L2", "Retinula axon; R"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1"],
            remove_corrected(
                ["Correction: Lamina monopolar 1; L1", "Retinula axon; R"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2"],
            remove_corrected(
                ["Correction: Lamina monopolar 2; L2", "Retinula axon; R"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "Lamina monopolar 2; L2"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "Correction: Lamina monopolar 2; L2",
                    "L1 Lamina Monopolar\n",
                ]
            ),
        )
        self.assertEqual(
            ["L3 Lamina Monopolar"],
            remove_corrected(
                ["L3 Lamina Monopolar - L2 Label Incorrect", "L2 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "L2 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "L2 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar\n",
                ]
            ),
        )
        self.assertEqual(
            ["L1 Lamina Monopolar"],
            remove_corrected(
                [
                    "L1 Lamina Monopolar - L2 Label Incorrect",
                    "L1 Lamina Monopolar - L2 Label Incorrect",
                    "L2 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["L1 Lamina Monopolar"],
            remove_corrected(
                ["L1 Lamina Monopolar - L2 Label Incorrect", "L2 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["L2 Lamina Monopolar"],
            remove_corrected(
                ["L2 Lamina Monopolar - L1 Label Incorrect", "L1 Laminar Monopolar\n"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "L2 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "L2 Lamina Monopolar - R2 Label Incorrect (spelling error)",
                    "R2 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 5; L5", "L5 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 5; L5",
                    "L5 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 5; L5", "L5 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 5; L5",
                    "L5 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 3; L3", "L3 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 3; L3",
                    "L3 Lamina Monopolar - L2 Label Incorrect",
                    "L2 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1", "L1 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 1; L1",
                    "L1 Lamina Monopolar - L2 Label Incorrect",
                    "L2 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1", "L1 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 1; L1",
                    "L1 Lamina Monopolar - L2 Label Incorrect",
                    "L2 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2"],
            remove_corrected(
                ["Correction: Lamina monopolar 2; L2", "L1 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["L3 Lamina Monopolar"],
            remove_corrected(
                ["L3 Lamina Monopolar - L2 Label Incorrect", "L2 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "L2 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "L2 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["L3 Lamina Monopolar"],
            remove_corrected(
                ["L3 Lamina Monopolar - L1 Label Incorrect", "L1 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["L3 Lamina Monopolar"],
            remove_corrected(
                ["L3 Lamina Monopolar - L1 Label Incorrect", "L1 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["L2 Lamina Monopolar"],
            remove_corrected(
                ["L2 Lamina Monopolar - L1 Label Incorrect", "L1 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "L2 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "L2 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 5; L5", "L5 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 5; L5",
                    "L5 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "L2 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "L2 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 2; L2", "L3 Lamina Monopolar"],
            remove_corrected(
                [
                    "Lamina monopolar 2; L2",
                    "L3 Lamina Monopolar - L1 Label Incorrect",
                    "L1 Lamina Monopolar",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 3; L3", "Lamina monopolar 3; L3"],
            remove_corrected(
                [
                    "Lamina monopolar 3; L3",
                    "Correction: Lamina monopolar 3; L3",
                    "L1 Lamina Monopolar\n",
                ]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1"],
            remove_corrected(
                ["Correction: Lamina monopolar 1; L1", "L2 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1"],
            remove_corrected(
                ["Correction: Lamina monopolar 1; L1", "L2 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1"],
            remove_corrected(
                ["Correction: Lamina monopolar 1; L1", "L2 Lamina Monopolar"]
            ),
        )
        self.assertEqual(
            [
                "Lamina monopolar 1; L1",
                "Retinula axon 1-6; R1-6",
                "Lamina monopolar 1; L1",
            ],
            remove_corrected(
                [
                    "Lamina monopolar 1; L1",
                    "Retinula axon 1-6; R1-6",
                    "Correction: Lamina monopolar 1; L1",
                ]
            ),
        )
        self.assertEqual(
            [
                "Lamina monopolar 1; L1",
                "Retinula axon 1-6; R1-6",
                "Lamina monopolar 1; L1",
            ],
            remove_corrected(
                [
                    "Lamina monopolar 1; L1",
                    "Retinula axon 1-6; R1-6",
                    "Correction: Lamina monopolar 1; L1",
                ]
            ),
        )
        self.assertEqual(
            ["Retinula axon 1-6; R1-6", "Lamina monopolar 1; L1"],
            remove_corrected(
                ["Retinula axon 1-6; R1-6", "Correction: Lamina monopolar 1; L1"]
            ),
        )
        self.assertEqual(
            ["Lamina monopolar 1; L1"],
            remove_corrected(
                ["Correction: Lamina monopolar 1; L1", "Retinula axon 1-6; R1-6"]
            ),
        )

    def test_remove_corrected_2(self):
        nd = {
            "nt_type": "ACH",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "right",
        }
        self.assertEqual(
            ["lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "putative LC25_R, lobula columnar neuron LC25 (corrected)",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )
        self.assertEqual(
            ["post correction label", "lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "post correction label",
                    "putative LC25_R, lobula columnar neuron LC25 (corrected)",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )

        self.assertEqual(
            ["lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "putative LC25_R, lobula columnar neuron LC25 (corrected)",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )
        self.assertEqual(
            ["post correction label", "LC25, lobula columnar neuron LC25"],
            clean_and_reduce_labels(
                [
                    "post correction label",
                    "Correction: putative LC25_R, lobula columnar neuron LC25",
                    "LC26_R, lobula columnar neuron LC26",
                ],
                nd,
            ),
        )

    def test_remove_redundant_parts(self):
        self.assertEqual(
            [],
            remove_redundant_parts(
                ["sensory"], self.neuron_db.neuron_data[720575940632968161]
            ),
        )
        self.assertEqual(
            [],
            remove_redundant_parts(
                ["sensory", "sensory"], self.neuron_db.neuron_data[720575940626188490]
            ),
        )
        self.assertEqual(
            ["JO-F"],
            remove_redundant_parts(
                ["sensory", "Putative JO-F"],
                self.neuron_db.neuron_data[720575940613078993],
            ),
        )

        self.assertEqual(
            ["octopaminergic ASM neuron, putative OA-ASM, putative ADM"],
            remove_redundant_parts(
                ["putative octopaminergic ASM neuron, putative OA-ASM, putative ADM"],
                self.neuron_db.neuron_data[720575940625405479],
            ),
        )
        self.assertEqual(
            ["medulla intrinsic neuron; occupies DRA columns"],
            remove_redundant_parts(
                ["Putative medulla intrinsic neuron; occupies DRA columns "],
                self.neuron_db.neuron_data[720575940612973226],
            ),
        )

    def test_remove_redundant_parts_2(self):
        nd = {
            "nt_type": "ACH",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "right",
        }
        self.assertEqual(
            ["VLPl1"], clean_and_reduce_labels(["VLPl1; right; acetylcholine"], nd)
        )

        nd = {
            "nt_type": "GABA",
            "flow": "intrinsic",
            "super_class": "central",
            "class": "",
            "sub_class": "",
            "cell_type": [],
            "hemibrain_type": [],
            "hemilineage": "VLPl1_or_VLPl5",
            "nerve": "",
            "side": "left",
        }
        self.assertEqual(
            ["VLPl1; acetylcholine"],
            clean_and_reduce_labels(["VLPl1; right; acetylcholine"], nd),
        )

    def test_compact_label(self):
        self.assertEqual(
            82, len([lbl for lbl in self.raw_labels if lbl != compact_label(lbl)])
        )

    def test_remove_subsumed_tokens(self):
        self.assertEqual(
            "MeTu_m_r; MeTu_m; MC64: Hulse, 2020",
            remove_subsumed_tokens("MeTu_m_r;MeTu_m;MC64; MC64: Hulse, 2020"),
        )
        self.assertEqual(
            "TuTu_a_r; TuTu_a; TuTuB_a: Hulse, 2020",
            remove_subsumed_tokens("TuTu_a_r;TuTu_a;TuTuB_a; TuTuB_a: Hulse, 2020"),
        )
        self.assertEqual(
            "Dm20_L; Dm20: Nern, 2015",
            remove_subsumed_tokens("Dm20_L;Dm20; Dm20: Nern, 2015"),
        )
        self.assertEqual(
            "MeTu_a_l; MeTu_a; MeTu; MC61: Otsuna, 2014",
            remove_subsumed_tokens("MeTu_a_l;MeTu_a;MeTu;MC61; MC61: Otsuna, 2014"),
        )
        self.assertEqual(
            "transmedullary neuron Tm5, but not sure which type (a/b/c)",
            remove_subsumed_tokens(
                "Tm5, transmedullary neuron Tm5, but not sure which type (a/b/c)"
            ),
        )
        self.assertEqual(
            "ER3m_l; ER3m: Hulse, 2020",
            remove_subsumed_tokens("ER3m_l;ER3m; ER3m: Hulse, 2020"),
        )
        self.assertEqual(
            "MeTu_pc_l; MeTu_pc; MeTu; MC61: Otsuna, 2014",
            remove_subsumed_tokens("MeTu_pc_l;MeTu_pc;MeTu;MC61; MC61: Otsuna, 2014"),
        )
        self.assertEqual(
            "Dm17_L; Dm17: Nern, 2015",
            remove_subsumed_tokens("Dm17_L;Dm17; Dm17: Nern, 2015"),
        )
        self.assertEqual(
            "Dm14_L; Dm14: Nern, 2015",
            remove_subsumed_tokens("Dm14_L;Dm14; Dm14: Nern, 2015"),
        )
        self.assertEqual(
            "ER2c_r; ER2c_centripetal_r; ER2c: Hulse, 2020",
            remove_subsumed_tokens("ER2c_r;ER2c_centripetal_r;ER2c; ER2c: Hulse, 2020"),
        )
        self.assertEqual(
            "Dm4_L; Dm4: Fischbach and Dittrich, 1989, Missing branches",
            remove_subsumed_tokens(
                "Dm4_L;Dm4; Dm4: Fischbach and Dittrich, 1989, Missing branches"
            ),
        )
        self.assertEqual(
            "MeTu_m_l; MeTu_m; MC64: Hulse, 2020",
            remove_subsumed_tokens("MeTu_m_l;MeTu_m;MC64; MC64: Hulse, 2020"),
        )
        self.assertEqual(
            "DN1pB_R; DN1pB: Neuprint",
            remove_subsumed_tokens("DN1pB_R;DN1pB; DN1pB: Neuprint"),
        )

    def test_remove_duplicate_tokens(self):
        self.assertEqual(
            "BPN downstream DN; We are currently preparing split-Gal4 reagent for this "
            "descending neuron which is downstream to BPNs (Bidaye et al 2020). "
            "It is not a part of any published report",
            remove_duplicate_tokens(
                "BPN downstream DN; BPN downstream DN; We are currently preparing split-Gal4 reagent for this "
                "descending neuron which is downstream to BPNs (Bidaye et al 2020). "
                "It is not a part of any published report"
            ),
        )

    def test_remove_left_right(self):
        self.assertEqual("12A_DN_X_37", remove_left_right("12A_DN_right_X_37"))
        self.assertEqual("ER3w;ER3w", remove_left_right("ER3w_l;ER3w"))
        self.assertEqual(
            "LC24, lobula columnar neuron LC24, FBbt_00111759",
            remove_left_right("LC24_R, lobula columnar neuron LC24, FBbt_00111759"),
        )
        self.assertEqual(
            "unclassified_IN_FW_315", remove_left_right("unclassified_IN_FW_315_left")
        )
        self.assertEqual(
            "ALlv1; acetylcholine", remove_left_right("ALlv1; right; acetylcholine")
        )
        self.assertEqual(
            "SLPpm3; acetylcholine", remove_left_right("SLPpm3; left; acetylcholine")
        )
        self.assertEqual(
            "CREa2_medial; dopamine", remove_left_right("CREa2_medial; left; dopamine")
        )
        self.assertEqual(
            "Centrifugal neuron 3, C3, C3, FBbt_00003744 (Fischbach & Dittrich, 1989)",
            remove_left_right(
                "Centrifugal neuron 3, C3, C3_R, FBbt_00003744 (Fischbach & Dittrich, 1989)"
            ),
        )
        self.assertEqual(
            "MBON17, a`3m, FBbt_00111064",
            remove_left_right("MBON17-RHS, a`3m, FBbt_00111064"),
        )
        self.assertEqual(
            "unclassified_IN_FW_256", remove_left_right("unclassified_IN_FW_256_left")
        )
        self.assertEqual(
            "up_DN2_ascending_16", remove_left_right("up_DN2_ascending_16_left")
        )
        self.assertEqual(
            "Lobula Columnar neuron 24; LC24; LC24; Lcn24; FBbt_00111759",
            remove_left_right(
                "Lobula Columnar neuron 24; LC24; LC24_R; Lcn24; FBbt_00111759"
            ),
        )
        self.assertEqual(
            "SMPpv2; glutamate", remove_left_right("SMPpv2; left; glutamate")
        )
        self.assertEqual(
            "SLPa&l1_anterior;", remove_left_right("SLPa&l1_anterior; left")
        )
        self.assertEqual("new_clone_4;", remove_left_right("new_clone_4; right"))
        self.assertEqual(
            "KE-SCS_unclassified_14_ascending",
            remove_left_right("KE-SCS_unclassified_14_ascending_left"),
        )
        self.assertEqual(
            "DM3_canonical; acetylcholine",
            remove_left_right("DM3_canonical; left; acetylcholine"),
        )
        self.assertEqual("MBON26; B`2d", remove_left_right("MBON26-LHS; B`2d"))
        self.assertEqual(
            "VLPl2_ventral; acetylcholine",
            remove_left_right("VLPl2_ventral; right; acetylcholine"),
        )
        self.assertEqual(
            "MX12_medial; acetylcholine",
            remove_left_right("MX12_medial; left; acetylcholine"),
        )
        self.assertEqual(
            "ER4d;ER4d; ER4d: Hulse, 2020",
            remove_left_right("ER4d_l;ER4d; ER4d: Hulse, 2020"),
        )
        self.assertEqual("ALv2; GABA", remove_left_right("ALv2; left; GABA"))
        self.assertEqual(
            "DM6_dorsal; acetylcholine",
            remove_left_right("DM6_dorsal; left; acetylcholine"),
        )
        self.assertEqual(
            "VLPl2_dorsal; acetylcholine",
            remove_left_right("VLPl2_dorsal; left; acetylcholine"),
        )
        self.assertEqual(
            "Transmedullary neuron 16, Tm16, Tm16, [FBbt_00003804]",
            remove_left_right(
                "Transmedullary neuron 16, Tm16, Tm16_R, [FBbt_00003804]"
            ),
        )
        self.assertEqual(
            "R7;R7; Neuron doesnt include soma because EM is cut off on side of brain",
            remove_left_right(
                "R7_R;R7; Neuron doesnt include soma because EM is cut off on right side of brain"
            ),
        )
        self.assertEqual("VLPa1_medial;", remove_left_right("VLPa1_medial; left"))
        self.assertEqual("descending_FW_25", remove_left_right("descending_FW_25_left"))
        self.assertEqual("MBON27; y5d", remove_left_right("MBON27-RHS; y5d"))
        self.assertEqual(
            "LHl4_anterior; GABA", remove_left_right("LHl4_anterior; right; GABA")
        )
        self.assertEqual(
            "DM3_medial; glutamate", remove_left_right("DM3_medial; left; glutamate")
        )
        self.assertEqual(
            "TuBu_ER3w;TuBu_ER3w;TuBu07_SBU;TuBu; TuBu07: Hulse, 2020",
            remove_left_right(
                "TuBu_ER3w_l;TuBu_ER3w;TuBu07_SBU_L;TuBu; TuBu07: Hulse, 2020"
            ),
        )
        self.assertEqual("DM4_medial;", remove_left_right("DM4_medial; right"))
        self.assertEqual("WEDa1_dorsal;", remove_left_right("WEDa1_dorsal; left"))
        self.assertEqual("12A_DN_X_20", remove_left_right("12A_DN_right_X_20"))
        self.assertEqual("DL1_dorsal;", remove_left_right("DL1_dorsal; right"))
        self.assertEqual(
            "unclassified_IN_FW_93", remove_left_right("unclassified_IN_FW_93_left")
        )

    def test_misc_clean_and_reduce_labels(self):
        for nd in self.neuron_db.neuron_data.values():
            for lbl in nd["label"]:
                self.assertFalse(lbl.lower().startswith("putative"), lbl)

            self.assertEqual(len(nd["label"]), len(set(nd["label"])))
