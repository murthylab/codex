import csv
from functools import lru_cache
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

@lru_cache
def load_genetic_lines(tsv_filename="Jenett.2012.9.24.tsv"):
    # TODO: move data somewhere sensible
    # sourced from https://flybase.org/reports/FBrf0219498.html
    lines = {}
    with open(tsv_filename) as file:
        reader = csv.DictReader(file, delimiter="\t")
        rows_read = 0
        for row in reader:
            line = f"R{row['Sample'].split('_')[1]}"  ## sample name to line name
            line_data = lines.get(line, {})
            compartment = row["Compartment"]
            line_data[compartment] = {
                "intensity": row["Intensity"],
                "distribution": row["Distribution"],
                "neuropils": jennet_compartment_to_neuropils(compartment),
            }
            lines[line] = line_data
            rows_read += 1
    print(f"Loaded {rows_read} rows for {len(lines)} lines from {tsv_filename}")
    return dict(sorted(lines.items()))

LINES = load_genetic_lines()
