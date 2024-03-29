from functools import lru_cache

from codex.utils.parsing import tokenize

from codex import logger

LEFT = "Left"
RIGHT = "Right"
CENTER = "Center"
HEMISPHERES = [LEFT, RIGHT, CENTER]

REGIONS = {
    # region abbreviation: [segment ID, description]
    "AME_L": [56, "accessory medulla"],
    "AME_R": [29, "accessory medulla"],
    "LO_L": [51, "lobula"],
    "LO_R": [14, "lobula"],
    "NO": [58, "noduli"],
    "BU_L": [73, "bulb (in lateral complex)"],
    "BU_R": [11, "bulb (in lateral complex)"],
    "PB": [68, "protocerebral bridge"],
    "LH_L": [20, "lateral horn"],
    "LH_R": [54, "lateral horn"],
    "LAL_L": [46, "lateral accessory lobe"],
    "LAL_R": [25, "lateral accessory lobe"],
    "SAD": [70, "saddle"],
    "CAN_L": [3, "cantle"],
    "CAN_R": [61, "cantle"],
    "AMMC_L": [45, "antennal mechanosensory and motor center"],
    "AMMC_R": [71, "antennal mechanosensory and motor center"],
    "ICL_L": [31, "inferior clamp"],
    "ICL_R": [33, "inferior clamp"],
    "VES_L": [44, "vest"],
    "VES_R": [40, "vest"],
    "IB_L": [67, "inferior bridge"],
    "IB_R": [17, "inferior bridge"],
    "ATL_L": [18, "antler"],
    "ATL_R": [23, "antler"],
    "CRE_L": [30, "crepine"],
    "CRE_R": [19, "crepine"],
    "MB_PED_L": [48, "mushroom body → pedunculus"],
    "MB_PED_R": [28, "mushroom body → pedunculus"],
    "MB_VL_L": [4, "mushroom body → vertical lobe"],
    "MB_VL_R": [55, "mushroom body → vertical lobe"],
    "MB_ML_L": [10, "mushroom body → medial lobe"],
    "MB_ML_R": [41, "mushroom body → medial lobe"],
    "FLA_L": [74, "flange"],
    "FLA_R": [5, "flange"],
    "LOP_L": [6, "lobula plate"],
    "LOP_R": [36, "lobula plate"],
    "EB": [35, "ellipsoid body"],
    "AL_L": [57, "antennal lobe"],
    "AL_R": [27, "antennal lobe"],
    "ME_L": [43, "medulla"],
    "ME_R": [2, "medulla"],
    "FB": [65, "fanshaped body"],
    "SLP_L": [62, "superior lateral protocerebrum"],
    "SLP_R": [47, "superior lateral protocerebrum"],
    "SIP_L": [72, "superior intermediate protocerebrum"],
    "SIP_R": [63, "superior intermediate protocerebrum"],
    "SMP_L": [42, "superior medial protocerebrum"],
    "SMP_R": [1, "superior medial protocerebrum"],
    "AVLP_L": [69, "anterior VLP (ventrolateral protocerebrum)"],
    "AVLP_R": [49, "anterior VLP (ventrolateral protocerebrum)"],
    "PVLP_L": [39, "posterior VLP (ventrolateral protocerebrum)"],
    "PVLP_R": [37, "posterior VLP (ventrolateral protocerebrum)"],
    "WED_L": [50, "wedge"],
    "WED_R": [60, "wedge"],
    "PLP_L": [59, "posteriorlateral protocerebrum"],
    "PLP_R": [9, "posteriorlateral protocerebrum"],
    "AOTU_L": [22, "anterior optic tubercle"],
    "AOTU_R": [24, "anterior optic tubercle"],
    "GOR_L": [12, "gorget"],
    "GOR_R": [32, "gorget"],
    "MB_CA_L": [66, "mushroom body → calyx"],
    "MB_CA_R": [21, "mushroom body → calyx"],
    "SPS_L": [13, "superior posterior slope"],
    "SPS_R": [64, "superior posterior slope"],
    "IPS_L": [7, "inferior posterior slope"],
    "IPS_R": [38, "inferior posterior slope"],
    "SCL_L": [15, "superior clamp"],
    "SCL_R": [0, "superior clamp"],
    "EPA_L": [8, "epaulette"],
    "EPA_R": [52, "epaulette"],
    "GNG": [26, "gnathal ganglia"],
    "PRW": [53, "prow"],
    "GA_L": [34, "gall"],
    "GA_R": [16, "gall"],
    "LA_R": [75, "lamina of the compound eyes"],
    "LA_L": [76, "lamina of the compound eyes"],
    "OCG": [77, "ocellar ganglion"],
    "UNASGD": [-1, "unassigned"],
}

REGION_CATEGORIES = {
    "optic lobe": [
        "AME_R",
        "AME_L",
        "LA_L",
        "LA_R",
        "LO_R",
        "LO_L",
        "LOP_R",
        "LOP_L",
        "ME_R",
        "ME_L",
    ],
    "central complex": ["NO", "PB", "EB", "FB"],
    "lateral complex": ["BU_R", "BU_L", "LAL_R", "LAL_L", "GA_R", "GA_L"],
    "lateral horn": ["LH_R", "LH_L"],
    "periesophageal neuropils": [
        "SAD",
        "CAN_R",
        "CAN_L",
        "AMMC_R",
        "AMMC_L",
        "FLA_R",
        "FLA_L",
        "PRW",
    ],
    "inferior neuropils": [
        "ICL_R",
        "ICL_L",
        "IB_R",
        "IB_L",
        "ATL_R",
        "ATL_L",
        "CRE_R",
        "CRE_L",
        "SCL_R",
        "SCL_L",
    ],
    "ventromedial neuropils": [
        "VES_R",
        "VES_L",
        "GOR_R",
        "GOR_L",
        "SPS_R",
        "SPS_L",
        "IPS_R",
        "IPS_L",
        "EPA_R",
        "EPA_L",
    ],
    "mushroom body": [
        "MB_PED_R",
        "MB_PED_L",
        "MB_VL_R",
        "MB_VL_L",
        "MB_ML_R",
        "MB_ML_L",
        "MB_CA_R",
        "MB_CA_L",
    ],
    "antennal lobe": ["AL_R", "AL_L"],
    "superior neuropils": ["SLP_R", "SLP_L", "SIP_R", "SIP_L", "SMP_R", "SMP_L"],
    "ventrolateral neuropils": [
        "AVLP_R",
        "AVLP_L",
        "PVLP_R",
        "PVLP_L",
        "WED_R",
        "WED_L",
        "PLP_R",
        "PLP_L",
        "AOTU_R",
        "AOTU_L",
    ],
    "gnathal ganglia": ["GNG"],
    "ocelli": ["OCG"],
    "other regions": ["UNASGD"],
}

COLORS = {
    "ME_L": "#dd41d3",
    "BU_L": "#5479ef",
    "LH_L": "#fe99b8",
    "SLP_L": "#fed942",
    "CRE_L": "#febd3b",
    "VES_L": "#02dcc0",
    "AOTU_L": "#4c9efe",
    "MB_CA_L": "#fe9e3f",
    "AL_L": "#30d2fe",
    "FB": "#049a93",
    "AMMC_L": "#145ddc",
    "GNG": "#603ee4",
    "ME_R": "#dd41d3",
    "BU_R": "#5479ef",
    "LH_R": "#fe99b8",
    "SLP_R": "#fed942",
    "CRE_R": "#febd3b",
    "VES_R": "#02dcc0",
    "AOTU_R": "#4c9efe",
    "MB_CA_R": "#fe9e3f",
    "AL_R": "#30d2fe",
    "EB": "#10cac8",
    "AMMC_R": "#145ddc",
    "AME_L": "#bc21a2",
    "GA_L": "#3d8ce2",
    "GA_R": "#3d8ce2",
    "SIP_L": "#feb13a",
    "SCL_L": "#fdb95d",
    "EPA_L": "#07c4ac",
    "AVLP_L": "#3d89fe",
    "MB_PED_L": "#ffa88d",
    "PB": "#36cfdc",
    "FLA_L": "#274bfe",
    "AME_R": "#bc21a2",
    "LAL_L": "#285bfa",
    "SIP_R": "#feb13a",
    "SCL_R": "#fdb95d",
    "EPA_R": "#07c4ac",
    "AVLP_R": "#3d89fe",
    "MB_PED_R": "#ffa88d",
    "NO": "#21adc4",
    "FLA_R": "#274bfe",
    "LO_L": "#8a34d4",
    "LAL_R": "#285bfa",
    "SMP_L": "#ffda59",
    "ICL_L": "#fbb256",
    "GOR_L": "#00b5d3",
    "PVLP_L": "#1a57ee",
    "MB_VL_L": "#ffae79",
    "CAN_L": "#2081f2",
    "LO_R": "#8a34d4",
    "SMP_R": "#ffda59",
    "ICL_R": "#fbb256",
    "GOR_R": "#00b5d3",
    "PVLP_R": "#1a57ee",
    "MB_VL_R": "#ffae79",
    "CAN_R": "#2081f",
    "LOP_L": "#bc21a2",
    "IB_L": "#fe9e3e",
    "SPS_L": "#00957e",
    "PLP_L": "#50bcfe",
    "MB_ML_L": "#ff9e69",
    "PRW": "#513bfe",
    "LOP_R": "#bc21a2",
    "IB_R": "#fe9e3e",
    "SPS_R": "#00957e",
    "PLP_R": "#50bcfe",
    "MB_ML_R": "#ff9e69",
    "SAD": "#543bfe",
    "ATL_L": "#fead49",
    "IPS_L": "#0dbfc2",
    "WED_L": "#3b8dfe",
    "ATL_R": "#fead49",
    "IPS_R": "#0dbfc2",
    "WED_R": "#3b8dfe",
    "LA_L": "#a21a78",
    "LA_R": "#a21a78",
    "OCG": "#ea4bea",
    "UNASGD": "#ff0000",
}


@lru_cache
def neuropil_hemisphere(pil):
    pil = pil.upper()
    if pil.endswith("_L"):
        return LEFT
    elif pil.endswith("_R"):
        return RIGHT
    else:
        return CENTER


def without_side_suffix(pil):
    pil = pil.upper()
    return pil[:-2] if pil.endswith("_L") or pil.endswith("_R") else pil


def neuropil_description(txt):
    pil = match_to_neuropil(txt)
    if pil not in REGIONS:
        return pil or "Unknown brain region"
    val = REGIONS[pil]
    hs = neuropil_hemisphere(pil)
    return val[1] if hs == CENTER else f"{hs.lower()} {val[1]}"


# find a matching neuropil from free-form text. if no matches, return unchanged
def match_to_neuropil(txt):
    nset = lookup_neuropil_set(txt)
    if len(nset) == 1:
        return nset.pop()
    else:
        if txt not in HEMISPHERES:
            logger.error(f"Could not match a single neuropil to {txt}: got {nset}")
        return txt


# find a set of matching neuropils from free-form text
def lookup_neuropil_set(txt):
    if not txt:
        return None

    txt_uc = txt.upper()
    txt_lc = txt.lower()

    if txt_uc in REGIONS:
        return {txt_uc}

    prefix_regions = set([k for k in REGIONS.keys() if k.startswith(txt_uc)])
    if prefix_regions:
        return prefix_regions

    for hs in HEMISPHERES:
        if hs.lower() == txt_lc:
            return set(
                [rgn for rgn in REGIONS.keys() if neuropil_hemisphere(rgn) == hs]
            )

    txt_lc_tokens = set(tokenize(txt_lc))
    token_wise_matched_regions = set()
    for r, v in REGIONS.items():
        rgn_tokens = set(tokenize(v[1].lower()))
        rgn_tokens.add(neuropil_hemisphere(r).lower())
        if txt_lc_tokens.issubset(rgn_tokens):
            token_wise_matched_regions.add(r)
    if token_wise_matched_regions:
        return token_wise_matched_regions

    return set()


NEUROPIL_DESCRIPTIONS = {k: neuropil_description(k) for k in REGIONS.keys()}


def hemisphere_categories(hemisphere):
    categories = []

    for category in REGION_CATEGORIES.items():
        regions = []

        for region_id in category[1]:
            if neuropil_hemisphere(region_id) == hemisphere:
                segment_id = REGIONS[region_id][0]
                description = REGIONS[region_id][1]
                regions.append(
                    {
                        "segment_id": segment_id,
                        "id": region_id,
                        "description": description,
                    }
                )

        if len(regions) > 0:
            categories.append({"name": category[0], "regions": regions})

    return categories


REGIONS_JSON = {h: hemisphere_categories(h) for h in HEMISPHERES}
