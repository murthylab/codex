from unittest import TestCase
from src.data.brain_regions import (
    match_to_neuropil,
    lookup_neuropil_set,
    neuropil_description,
    REGIONS,
)


class RegionsTest(TestCase):
    def test_lookup_neuropil(self):
        for k, v in REGIONS.items():
            self.assertEqual(k, match_to_neuropil(k))
            self.assertEqual(k, match_to_neuropil(k.lower()))
            if not v[1]:
                self.assertEqual(k, match_to_neuropil(v[2]))
        self.assertEqual("ME_L", match_to_neuropil("medulla/left"))
        self.assertEqual("ME_R", match_to_neuropil("right side medulla"))

    def test_lookup_neuropil_set_by_side(self):
        pil_set = lookup_neuropil_set("left")
        self.assertEqual(34, len(pil_set))
        for p in pil_set:
            self.assertTrue(p.endswith("_L"))

        pil_set = lookup_neuropil_set("right")
        self.assertEqual(34, len(pil_set))
        for p in pil_set:
            self.assertTrue(p.endswith("_R"))

        pil_set = lookup_neuropil_set("Center")
        self.assertEqual(7, len(pil_set))
        for p in pil_set:
            self.assertFalse(p.endswith("_L"))
            self.assertFalse(p.endswith("_R"))

    def test_lookup_neuropil_set_by_abrv(self):
        pil_set = lookup_neuropil_set("ame")
        self.assertEqual({"AME_L", "AME_R"}, pil_set)

        pil_set = lookup_neuropil_set("AME")
        self.assertEqual({"AME_L", "AME_R"}, pil_set)

        pil_set = lookup_neuropil_set("AM")
        self.assertEqual({"AME_L", "AMMC_L", "AMMC_R", "AME_R"}, pil_set)

    def test_lookup_neuropil_set_by_description(self):
        pil_set = lookup_neuropil_set("lobula")
        self.assertEqual({"LO_R", "LO_L", "LOP_L", "LOP_R"}, pil_set)

        pil_set = lookup_neuropil_set("Medulla")
        self.assertEqual({"ME_R", "AME_R", "ME_L", "AME_L"}, pil_set)

        pil_set = lookup_neuropil_set("Lateral Horn")
        self.assertEqual({"LH_R", "LH_L"}, pil_set)

    def test_neuropil_description(self):
        descriptions = set([neuropil_description(k) for k in REGIONS.keys()])
        self.assertEqual(len(REGIONS), len(descriptions))
        self.assertTrue(all(descriptions))
