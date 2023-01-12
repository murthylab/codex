import csv
from functools import lru_cache

@lru_cache
def load_genetic_lines(tsv_filename="Jenett.2012.9.24.tsv"): # TODO: store this somewhere sensible
    lines = {}
    with open(tsv_filename) as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            line = row["Sample"].split("_")[1]  ## sample name to line name
            line_data = lines.get(line, {})
            neuropil = row["Compartment"]
            line_data[neuropil] = { "intensity": row["Intensity"], \
				"distribution": row["Distribution"] }
            lines[line] = line_data
    return lines