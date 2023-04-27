from collections import defaultdict
from unittest import TestCase
from src.data.brain_regions import (
    match_to_neuropil,
    lookup_neuropil_set,
    neuropil_description,
    REGIONS,
    REGION_CATEGORIES,
    neuropil_hemisphere,
    without_side_suffix,
)


class RegionsTest(TestCase):
    def test_lookup_neuropil(self):
        for k, v in REGIONS.items():
            self.assertEqual(k, match_to_neuropil(k))
            self.assertEqual(k, match_to_neuropil(k.lower()))
            if not v[1]:
                self.assertEqual(k, match_to_neuropil(v[2]))
        self.assertEqual("AME_L", match_to_neuropil("accessory medulla/left"))
        self.assertEqual({"ME_R", "AME_R"}, lookup_neuropil_set("right medulla"))

    def test_lookup_neuropil_set_by_side(self):
        pil_set = lookup_neuropil_set("left")
        self.assertEqual(35, len(pil_set))
        for p in pil_set:
            self.assertTrue(p.endswith("_L"))

        pil_set = lookup_neuropil_set("right")
        self.assertEqual(35, len(pil_set))
        for p in pil_set:
            self.assertTrue(p.endswith("_R"))

        pil_set = lookup_neuropil_set("Center")
        self.assertEqual(8, len(pil_set))
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

        pil_set = lookup_neuropil_set("Medulla left")
        self.assertEqual({"ME_L", "AME_L"}, pil_set)

        pil_set = lookup_neuropil_set("Lateral Horn")
        self.assertEqual({"LH_R", "LH_L"}, pil_set)

    def test_neuropil_description(self):
        descriptions = set([neuropil_description(k) for k in REGIONS.keys()])
        self.assertEqual(len(REGIONS), len(descriptions))
        self.assertTrue(all(descriptions))

    def test_neuropil_categories(self):
        dct = defaultdict(list)
        for key, value in REGION_CATEGORIES.items():
            for pil in value:
                dct[pil].append(key)

        for p in REGIONS.keys():
            self.assertEqual(1, len(dct[p]), p)
            self.assertGreater(len(dct[p][0]), 5)

    def test_neuropil_hemisphere(self):
        for k, v in REGIONS.items():
            if k.endswith("_L"):
                self.assertEqual("Left", neuropil_hemisphere(k))
            elif k.endswith("_R"):
                self.assertEqual("Right", neuropil_hemisphere(k))
            else:
                self.assertEqual("Center", neuropil_hemisphere(k))

    def test_without_side_suffix(self):
        for k, v in REGIONS.items():
            if k.endswith("_L"):
                self.assertEqual(k.replace("_L", ""), without_side_suffix(k))
            elif k.endswith("_R"):
                self.assertEqual(k.replace("_R", ""), without_side_suffix(k))
            else:
                self.assertEqual(k, without_side_suffix(k))
