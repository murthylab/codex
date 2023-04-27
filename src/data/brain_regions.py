from src.utils.logging import log_error
from src.utils.parsing import tokenize

LEFT = "Left"
RIGHT = "Right"
CENTER = "Center"
HEMISPHERES = [LEFT, RIGHT, CENTER]

REGIONS = {
    # region abbreviation: [segment ID, description]
    "AME_R": [56, "accessory medulla"],
    "AME_L": [29, "accessory medulla"],
    "LO_R": [51, "lobula"],
    "LO_L": [14, "lobula"],
    "NO": [58, "noduli"],
    "BU_R": [73, "bulb (in lateral complex)"],
    "BU_L": [11, "bulb (in lateral complex)"],
    "PB": [68, "protocerebral bridge"],
    "LH_R": [20, "lateral horn"],
    "LH_L": [54, "lateral horn"],
    "LAL_R": [46, "lateral accessory lobe"],
    "LAL_L": [25, "lateral accessory lobe"],
    "SAD": [70, "saddle"],
    "CAN_R": [3, "cantle"],
    "CAN_L": [61, "cantle"],
    "AMMC_R": [45, "antennal mechanosensory and motor center"],
    "AMMC_L": [71, "antennal mechanosensory and motor center"],
    "ICL_R": [31, "inferior clamp"],
    "ICL_L": [33, "inferior clamp"],
    "VES_R": [44, "vest"],
    "VES_L": [40, "vest"],
    "IB_R": [67, "inferior bridge"],
    "IB_L": [17, "inferior bridge"],
    "ATL_R": [18, "antler"],
    "ATL_L": [23, "antler"],
    "CRE_R": [30, "crepine"],
    "CRE_L": [19, "crepine"],
    "MB_PED_R": [48, "mushroom body → pedunculus"],
    "MB_PED_L": [28, "mushroom body → pedunculus"],
    "MB_VL_R": [4, "mushroom body → vertical lobe"],
    "MB_VL_L": [55, "mushroom body → vertical lobe"],
    "MB_ML_R": [10, "mushroom body → medial lobe"],
    "MB_ML_L": [41, "mushroom body → medial lobe"],
    "FLA_R": [74, "flange"],
    "FLA_L": [5, "flange"],
    "LOP_R": [6, "lobula plate"],
    "LOP_L": [36, "lobula plate"],
    "EB": [35, "ellipsoid body"],
    "AL_R": [57, "antennal lobe"],
    "AL_L": [27, "antennal lobe"],
    "ME_R": [43, "medulla"],
    "ME_L": [2, "medulla"],
    "FB": [65, "fanshaped body"],
    "SLP_R": [62, "superior lateral protocerebrum"],
    "SLP_L": [47, "superior lateral protocerebrum"],
    "SIP_R": [72, "superior intermediate protocerebrum"],
    "SIP_L": [63, "superior intermediate protocerebrum"],
    "SMP_R": [42, "superior medial protocerebrum"],
    "SMP_L": [1, "superior medial protocerebrum"],
    "AVLP_R": [69, "anterior VLP (ventrolateral protocerebrum)"],
    "AVLP_L": [49, "anterior VLP (ventrolateral protocerebrum)"],
    "PVLP_R": [39, "posterior VLP (ventrolateral protocerebrum)"],
    "PVLP_L": [37, "posterior VLP (ventrolateral protocerebrum)"],
    "WED_R": [50, "wedge"],
    "WED_L": [60, "wedge"],
    "PLP_R": [59, "posteriorlateral protocerebrum"],
    "PLP_L": [9, "posteriorlateral protocerebrum"],
    "AOTU_R": [22, "anterior optic tubercle"],
    "AOTU_L": [24, "anterior optic tubercle"],
    "GOR_R": [12, "gorget"],
    "GOR_L": [32, "gorget"],
    "MB_CA_R": [66, "mushroom body → calyx"],
    "MB_CA_L": [21, "mushroom body → calyx"],
    "SPS_R": [13, "superior posterior slope"],
    "SPS_L": [64, "superior posterior slope"],
    "IPS_R": [7, "inferior posterior slope"],
    "IPS_L": [38, "inferior posterior slope"],
    "SCL_R": [15, "superior clamp"],
    "SCL_L": [0, "superior clamp"],
    "EPA_R": [8, "epaulette"],
    "EPA_L": [52, "epaulette"],
    "GNG": [26, "gnathal ganglia"],
    "PRW": [53, "prow"],
    "GA_R": [34, "gall"],
    "GA_L": [16, "gall"],
    "LA_L": [75, "lamina of the compound eyes"],
    "LA_R": [76, "lamina of the compound eyes"],
    "OCG": [77, "ocellar ganglion"],
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
}


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
