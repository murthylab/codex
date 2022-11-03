REGIONS = {
    "AME_R": [1, "right", "accessory medulla"],
    "AME_L": [42, "left", "accessory medulla"],
    "LO_R": [2, "right", "lobula"],
    "LO_L": [43, "left", "lobula"],
    "NO": [3, "", "noduli"],
    "BU_R": [4, "right", "bulb (in lateral complex)"],
    "BU_L": [44, "left", "bulb (in lateral complex)"],
    "PB": [5, "", "protocerebral bridge"],
    "LH_R": [6, "right", "lateral horn"],
    "LH_L": [45, "left", "lateral horn"],
    "LAL_R": [7, "right", "lateral accessory lobe"],
    "LAL_L": [46, "left", "lateral accessory lobe"],
    "SAD": [8, "", "saddle"],
    "CAN_R": [9, "right", "cantle"],
    "CAN_L": [47, "left", "cantle"],
    "AMMC_R": [10, "right", "antennal mechanosensory and motor center"],
    "AMMC_L": [48, "left", "antennal mechanosensory and motor center"],
    "ICL_R": [11, "right", "inferior clamp"],
    "ICL_L": [49, "left", "inferior clamp"],
    "VES_R": [12, "right", "vest"],
    "VES_L": [50, "left", "vest"],
    "IB_R": [13, "right", "inferior bridge"],
    "IB_L": [51, "left", "inferior bridge"],
    "ATL_R": [14, "right", "antler"],
    "ATL_L": [52, "left", "antler"],
    "CRE_R": [15, "right", "crepine"],
    "CRE_L": [53, "left", "crepine"],
    "MB_PED_R": [16, "right", "mushroom body → pedunculus"],
    "MB_PED_L": [54, "left", "mushroom body → pedunculus"],
    "MB_VL_R": [17, "right", "mushroom body → vertical lobe"],
    "MB_VL_L": [55, "left", "mushroom body → vertical lobe"],
    "MB_ML_R": [18, "right", "mushroom body → medial lobe"],
    "MB_ML_L": [56, "left", "mushroom body → medial lobe"],
    "FLA_R": [19, "right", "flange"],
    "FLA_L": [57, "left", "flange"],
    "LOP_R": [20, "right", "lobula plate"],
    "LOP_L": [58, "left", "lobula plate"],
    "EB": [21, "", "ellipsoid body"],
    "AL_R": [22, "right", "antennal lobe"],
    "AL_L": [59, "left", "antennal lobe"],
    "ME_R": [23, "right", "medulla"],
    "ME_L": [60, "left", "medulla"],
    "FB": [24, "", "fanshaped body"],
    "SLP_R": [25, "right", "superior lateral protocerebrum"],
    "SLP_L": [61, "left", "superior lateral protocerebrum"],
    "SIP_R": [26, "right", "superior intermediate protocerebrum"],
    "SIP_L": [62, "left", "superior intermediate protocerebrum"],
    "SMP_R": [27, "right", "superior medial protocerebrum"],
    "SMP_L": [63, "left", "superior medial protocerebrum"],
    "AVLP_R": [28, "right", "anterior VLP (ventrolateral protocerebrum)"],
    "AVLP_L": [64, "left", "anterior VLP (ventrolateral protocerebrum)"],
    "PVLP_R": [29, "right", "posterior VLP (ventrolateral protocerebrum)"],
    "PVLP_L": [65, "left", "posterior VLP (ventrolateral protocerebrum)"],
    "WED_R": [30, "right", "wedge"],
    "WED_L": [66, "left", "wedge"],
    "PLP_R": [31, "right", "posteriorlateral protocerebrum"],
    "PLP_L": [67, "left", "posteriorlateral protocerebrum"],
    "AOTU_R": [32, "right", "anterior optic tubercle"],
    "AOTU_L": [68, "left", "anterior optic tubercle"],
    "GOR_R": [33, "right", "gorget"],
    "GOR_L": [69, "left", "gorget"],
    "MB_CA_R": [34, "right", "mushroom body → calyx"],
    "MB_CA_L": [70, "left", "mushroom body → calyx"],
    "SPS_R": [35, "right", "superior posterior slope"],
    "SPS_L": [71, "left", "superior posterior slope"],
    "IPS_R": [36, "right", "inferior posterior slope"],
    "IPS_L": [72, "left", "inferior posterior slope"],
    "SCL_R": [37, "right", "superior clamp"],
    "SCL_L": [73, "left", "superior clamp"],
    "EPA_R": [38, "right", "epaulette"],
    "EPA_L": [74, "left", "epaulette"],
    "GNG": [39, "", "gnathal ganglia"],
    "PRW": [40, "", "prow"],
    "GA_R": [41, "right", "gall"],
    "GA_L": [75, "left", "gall"],
}


def neuropil_description(txt):
    pil = match_to_neuropil(txt)
    if pil not in REGIONS:
        return pil or "Unspecified Region"
    val = REGIONS[pil]
    return f"{val[2]}" + (f" / {val[1]}" if val[1] else "")


# find a matching neuropil from free-form text. if no matches, return unchanged
def match_to_neuropil(txt):
    nset = lookup_neuropil_set(txt)
    return nset.pop() if len(nset) == 1 else txt


# find a set of matching neuropils from free-form text
def lookup_neuropil_set(txt):
    res = None
    if txt:
        txt_uc = txt.upper()
        txt_lc = txt.lower()
        if txt_uc in REGIONS:
            res = {txt_uc}
        elif txt_lc in ["left", "right"]:
            res = set([k for k, v in REGIONS.items() if v[1] == txt_lc])
        elif txt_lc in ["center", "mid", "middle"]:
            res = set([k for k, v in REGIONS.items() if not v[1]])
        else:
            res = set()
            for k, v in REGIONS.items():
                if (
                    k.startswith(txt_uc)
                    or txt_lc == v[2]
                    or any([txt_lc == t for t in v[2].split()])
                ):
                    res.add(k)
    return res
