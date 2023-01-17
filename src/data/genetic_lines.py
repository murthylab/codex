import csv
from functools import lru_cache
from src.data.gcs_data_loader import load_jennet_lines_from_gcs
from src.data.brain_regions import REGIONS, REGION_CATEGORIES


def jennet_compartment_to_neuropils(compartment):
    if compartment in REGIONS:
        return [compartment]

    if lr := [n for n in [f"{compartment}_L", f"{compartment}_R"] if n in REGIONS]:
        return lr

    if substr := [n for n in REGIONS if compartment in n]:
        return substr

    if compartment == "OL":
        return REGION_CATEGORIES["optic lobe"]

    if compartment == "SEG":
        # "subesophageal ganglion" -> “gnathal ganglia”
        return ["GNG"]

    return []


def add_neuropils_to_jennet_lines(lines):
    for line, compartments in lines.items():
        for compartment, data in compartments.items():
            data["neuropils"] = jennet_compartment_to_neuropils(compartment)
    return lines


LINES = add_neuropils_to_jennet_lines(load_jennet_lines_from_gcs())
