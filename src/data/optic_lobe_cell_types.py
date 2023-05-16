# Most groups are of size 1. R1-6 is a lump of 6 indistinguishable types.
COLUMNAR_CELL_TYPE_GROUPS = {
    tn: [tn]
    for tn in [
        "C2",
        "C3",
        "Dm2",
        "Dm8",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "Mi1",
        "Mi4",
        "Mi9",
        "R7",
        "R8",
        "T1",
        "T4a",
        "T4b",
        "T4c",
        "T4d",
        "T5a",
        "T5b",
        "T5c",
        "T5d",
        "Tm1",
        "Tm2",
        "Tm20",
        "Tm9",
    ]
}
COLUMNAR_CELL_TYPE_GROUPS["R1-6"] = ["R1", "R2", "R3", "R4", "R5", "R6"]

COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR = {
    t: {
        "left": 790 * len(lst),
        "right": 780 * len(lst),
    }
    for t, lst in COLUMNAR_CELL_TYPE_GROUPS.items()
}

COLUMNAR_CELL_SUPER_CLASSES = {
    "optic",
    "sensory",
    "visual_projection",
}
