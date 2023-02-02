from collections import defaultdict

from src.data.local_data_loader import write_csv, read_csv
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.graph_algos import reachable_nodes

"""
For every neuron in the dataset, calculates the number of neurons reachable within i hops (for i=0,1,2...)
Generates sharded CSV tables with root id of the neuron in 1st column, and the counts of reachable neurons in second
column in the following format: <# reachable in 0 hops>:<# reachable in 1 hops>:<# reachable in 2 hops>...
"""


def compute_distance_counts():
    neuron_db = NeuronDataFactory().get(version="571")
    osets = neuron_db.output_sets()
    sorted_rids = sorted(neuron_db.neuron_data.keys())
    chunk_size = 1000

    def chunks(lst):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), chunk_size):
            yield lst[i : i + chunk_size]

    for chunk_idx, chunk in enumerate(chunks(sorted_rids)):
        print(f"Processing chunk {chunk_idx}")
        rows = []
        for n in chunk:
            reached = reachable_nodes(sources={n}, neighbor_sets=osets)
            res = defaultdict(int)
            for k, v in reached.items():
                res[v] += 1
            val = ":".join([str(v[1]) for v in sorted(res.items(), key=lambda p: p[0])])
            rows.append([n, val])
        write_csv(filename=f"chunk_{chunk_idx}.csv.gz", rows=rows, compress=True)


def compile_distance_counts_table(self):
    rows = []
    for i in range(118):
        print(f"Reading chunk {i}")
        chunk_rows = read_csv(filename=f"chunk_{i}.csv.gz")
        print(f"Read {len(chunk_rows)} rows")
        rows.extend(chunk_rows)

    print(f"Total num rows: {len(rows)}")
    max_dist = max([len(r[1].split(":")) for r in rows])
    print(f"Max dist: {max_dist}")
    formatted_rows = [["root_id"] + [f"distance {i}" for i in range(max_dist + 1)]]
    for r in rows:
        frow = [r[0]] + [0] * (max_dist + 1)
        for i, d in enumerate(r[1].split(":")):
            frow[i + 1] = d
        formatted_rows.append(frow)
    write_csv(filename="distance_counts.csv", rows=formatted_rows, compress=False)
    print(f"Wrote {len(formatted_rows)} rows")


if __name__ == "__main__":
    compute_distance_counts()
    compile_distance_counts_table()
