from src.data.gcs_data_loader import load_jennet_lines_from_gcs
from src.data.brain_regions import REGIONS, REGION_CATEGORIES


def add_neuropils_to_jennet_lines(lines):
    for compartments in lines.values():
        for compartment, data in compartments.items():
            if compartment in REGIONS:
                data["neuropils"] = [compartment]

            elif lr := [
                n for n in [f"{compartment}_L", f"{compartment}_R"] if n in REGIONS
            ]:
                data["neuropils"] = lr

            elif substr := [n for n in REGIONS if compartment in n]:
                data["neuropils"] = substr

            elif compartment == "OL":
                data["neuropils"] = REGION_CATEGORIES["optic lobe"]

            elif compartment == "SEG":  # "subesophageal ganglion" -> “gnathal ganglia”
                data["neuropils"] = ["GNG"]

    return lines


LINES = add_neuropils_to_jennet_lines(load_jennet_lines_from_gcs())
