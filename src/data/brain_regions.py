from src.utils.logging import log_error
from src.utils.parsing import tokenize

LEFT = "Left"
RIGHT = "Right"
CENTER = "Center"
HEMISPHERES = [LEFT, RIGHT, CENTER]

REGIONS = {
    # region abbreviation: [segment ID, description]
    "AME_R": [1, "accessory medulla"],
    "AME_L": [42, "accessory medulla"],
    "LO_R": [2, "lobula"],
    "LO_L": [43, "lobula"],
    "NO": [3, "noduli"],
    "BU_R": [4, "bulb (in lateral complex)"],
    "BU_L": [44, "bulb (in lateral complex)"],
    "PB": [5, "protocerebral bridge"],
    "LH_R": [6, "lateral horn"],
    "LH_L": [45, "lateral horn"],
    "LAL_R": [7, "lateral accessory lobe"],
    "LAL_L": [46, "lateral accessory lobe"],
    "SAD": [8, "saddle"],
    "CAN_R": [9, "cantle"],
    "CAN_L": [47, "cantle"],
    "AMMC_R": [10, "antennal mechanosensory and motor center"],
    "AMMC_L": [48, "antennal mechanosensory and motor center"],
    "ICL_R": [11, "inferior clamp"],
    "ICL_L": [49, "inferior clamp"],
    "VES_R": [12, "vest"],
    "VES_L": [50, "vest"],
    "IB_R": [13, "inferior bridge"],
    "IB_L": [51, "inferior bridge"],
    "ATL_R": [14, "antler"],
    "ATL_L": [52, "antler"],
    "CRE_R": [15, "crepine"],
    "CRE_L": [53, "crepine"],
    "MB_PED_R": [16, "mushroom body → pedunculus"],
    "MB_PED_L": [54, "mushroom body → pedunculus"],
    "MB_VL_R": [17, "mushroom body → vertical lobe"],
    "MB_VL_L": [55, "mushroom body → vertical lobe"],
    "MB_ML_R": [18, "mushroom body → medial lobe"],
    "MB_ML_L": [56, "mushroom body → medial lobe"],
    "FLA_R": [19, "flange"],
    "FLA_L": [57, "flange"],
    "LOP_R": [20, "lobula plate"],
    "LOP_L": [58, "lobula plate"],
    "EB": [21, "ellipsoid body"],
    "AL_R": [22, "antennal lobe"],
    "AL_L": [59, "antennal lobe"],
    "ME_R": [23, "medulla"],
    "ME_L": [60, "medulla"],
    "FB": [24, "fanshaped body"],
    "SLP_R": [25, "superior lateral protocerebrum"],
    "SLP_L": [61, "superior lateral protocerebrum"],
    "SIP_R": [26, "superior intermediate protocerebrum"],
    "SIP_L": [62, "superior intermediate protocerebrum"],
    "SMP_R": [27, "superior medial protocerebrum"],
    "SMP_L": [63, "superior medial protocerebrum"],
    "AVLP_R": [28, "anterior VLP (ventrolateral protocerebrum)"],
    "AVLP_L": [64, "anterior VLP (ventrolateral protocerebrum)"],
    "PVLP_R": [29, "posterior VLP (ventrolateral protocerebrum)"],
    "PVLP_L": [65, "posterior VLP (ventrolateral protocerebrum)"],
    "WED_R": [30, "wedge"],
    "WED_L": [66, "wedge"],
    "PLP_R": [31, "posteriorlateral protocerebrum"],
    "PLP_L": [67, "posteriorlateral protocerebrum"],
    "AOTU_R": [32, "anterior optic tubercle"],
    "AOTU_L": [68, "anterior optic tubercle"],
    "GOR_R": [33, "gorget"],
    "GOR_L": [69, "gorget"],
    "MB_CA_R": [34, "mushroom body → calyx"],
    "MB_CA_L": [70, "mushroom body → calyx"],
    "SPS_R": [35, "superior posterior slope"],
    "SPS_L": [71, "superior posterior slope"],
    "IPS_R": [36, "inferior posterior slope"],
    "IPS_L": [72, "inferior posterior slope"],
    "SCL_R": [37, "superior clamp"],
    "SCL_L": [73, "superior clamp"],
    "EPA_R": [38, "epaulette"],
    "EPA_L": [74, "epaulette"],
    "GNG": [39, "gnathal ganglia"],
    "PRW": [40, "prow"],
    "GA_R": [41, "gall"],
    "GA_L": [75, "gall"],
}

REGION_CATEGORIES = {
    "optic lobe": ["AME_R", "AME_L", "LO_R", "LO_L", "LOP_R", "LOP_L", "ME_R", "ME_L"],
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
}


def neuropil_hemisphere(pil):
    pil = pil.upper()
    if pil.endswith("_L"):
        return LEFT
    elif pil.endswith("_R"):
        return RIGHT
    else:
        return CENTER


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
            log_error(f"Could not match a single neuropil to {txt}: got {nset}")
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
