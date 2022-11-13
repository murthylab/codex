from src.utils.parsing import tokenize

LEFT = "Left"
RIGHT = "Right"
CENTER = "Center"
HEMISPHERES = [LEFT, RIGHT, CENTER]

REGIONS = {
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


def neuropil_hemisphere(pil):
    pil = pil.upper()
    if pil.endswith('_L'):
        return LEFT
    elif pil.endswith('_R'):
        return RIGHT
    else:
        return CENTER
        

def neuropil_description(txt):
    pil = match_to_neuropil(txt)
    if pil not in REGIONS:
        return pil or "Unspecified Region"
    val = REGIONS[pil]
    hs = neuropil_hemisphere(pil)
    return val[1] if hs == CENTER else f"{val[1]} / {hs}"


# find a matching neuropil from free-form text. if no matches, return unchanged
def match_to_neuropil(txt):
    nset = lookup_neuropil_set(txt)
    return nset.pop() if len(nset) == 1 else txt


# find a set of matching neuropils from free-form text
def lookup_neuropil_set(txt):
    if not txt:
        return None

    txt_uc = txt.upper()
    txt_lc = txt.lower()

    if txt_uc in REGIONS:
        return {txt_uc}

    for hs in HEMISPHERES:
        if hs.lower() == txt_lc:
            return set([rgn for rgn in REGIONS.keys() if neuropil_hemisphere(rgn) == hs])

    res = set()
    txt_lc_tokens = tokenize(txt_lc)
    for rgn, attrs in REGIONS.items():
        desc_lc = attrs[1].lower()
        if (
            rgn.startswith(txt_uc)
            or txt_lc == desc_lc
            or (desc_lc in txt_lc_tokens and neuropil_hemisphere(rgn).lower() in txt_lc_tokens)
            or any([txt_lc == t for t in tokenize(desc_lc)])
        ):
            res.add(rgn)
    return res
