COLUMNAR_CELL_TYPES = [
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
    "R1-6",
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

COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR = {
    t: {
        "left": 790,
        "right": 780,
    }
    for t in COLUMNAR_CELL_TYPES
}
# R1-6 is a lump of 6 indistinguishable types
COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR["R1-6"] = {"left": 6 * 790, "right": 6 * 780}

COLUMNAR_CELL_SUPER_CLASSES = {
    "optic", "sensory", "visual_projection",
}
