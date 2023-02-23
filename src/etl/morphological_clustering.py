from collections import defaultdict
import random

from networkx import Graph, DiGraph, connected_components, strongly_connected_components

from src.data.local_data_loader import write_csv
from src.data.neuron_data_factory import NeuronDataFactory

"""
Clusters a set of neurons by morphological similarity. Uses iterative application of the connected component analysis on
a graph induced by NBLAST similarity scores with increasing thresholds for refinement.
"""


def check_morphology_clusters():
    neuron_db = NeuronDataFactory().get()

    clusters = []
    clustered_rids = set()
    unclustered_rids = set(neuron_db.neuron_data.keys())
    while True:
        ndata_rid = max(
            unclustered_rids,
            key=lambda rid: -len(
                set(neuron_db.neuron_data[rid]["similar_cell_scores"]) - clustered_rids
            ),
        )
        ndata = neuron_db.neuron_data[ndata_rid]
        cluster_rids = {ndata_rid}
        cluster_rids |= set(ndata["similar_cell_scores"].keys()) - clustered_rids
        clusters.append(cluster_rids)
        clustered_rids |= cluster_rids
        unclustered_rids -= cluster_rids
        if not unclustered_rids:
            break
    assert len(neuron_db.neuron_data) == sum([len(c) for c in clusters])
    print(f"{len(clusters)}: {sum([len(c) for c in clusters]) / len(clusters)}")
    print([len(c) for c in clusters[:30]])
    print(len([len(c) for c in clusters if len(c) > 10]))
    print(len([len(c) for c in clusters if len(c) > 5]))
    print(len([len(c) for c in clusters if len(c) > 1]))
    print(len([len(c) for c in clusters if len(c) == 1]))
    print(clusters[-3:])


def pil_based_typing():
    neuron_db = NeuronDataFactory().get()

    def neuron_type(ndata):
        return f'{ndata["class"]}:{ndata["nt_type"]}:{".".join(sorted(set(ndata["input_neuropils"] + ndata["output_neuropils"])))}'

    type_lists = defaultdict(list)
    for ndata in neuron_db.neuron_data.values():
        type_lists[neuron_type(ndata)].append(ndata["root_id"])

    print({t: v for t, v in type_lists.items() if 100 > len(v) > 10})
    print(len(type_lists.items()))


def cluster_neurons(predicate, directed=True, print_markdown=False, csv_filename=None):
    neuron_db = NeuronDataFactory().get()

    def cluster_rids(rids, nblast_score_threshold):
        rids = set(rids)
        G = DiGraph() if directed else Graph()
        for r in rids:
            G.add_node(r)
        for rid in rids:
            ndata = neuron_db.neuron_data[rid]
            for rid_to, score in ndata["similar_cell_scores"].items():
                if rid_to in rids and score >= nblast_score_threshold:
                    G.add_edge(rid, rid_to, weight=score)
        return [
            list(s)
            for s in (
                strongly_connected_components(G)
                if directed
                else connected_components(G)
            )
        ]

    neuron_rids = set(
        [
            ndata["root_id"]
            for ndata in neuron_db.neuron_data.values()
            if predicate(ndata)
        ]
    )

    score_threshold = 4
    MAX_SCORE_THRESHOLD = 6
    MAX_CLUSTER_SIZE = 50
    clusters = [neuron_rids]

    def report_cluster_sizes():
        print(
            f"Num clusters: {len(clusters)}, large clusters: {len(large_clusters)}, "
            f"largest cluster: {max([len(c) for c in clusters])}, "
            f"singletons: {len([c for c in clusters if len(c) == 1])}, "
            f"empties: {len([c for c in clusters if len(c) == 0])}, "
            f"threshold: {score_threshold}"
        )

    while True:
        large_clusters = [cl for cl in clusters if len(cl) > MAX_CLUSTER_SIZE]
        if score_threshold >= MAX_SCORE_THRESHOLD or not large_clusters:
            break
        report_cluster_sizes()
        clusters = [cl for cl in clusters if len(cl) <= MAX_CLUSTER_SIZE]
        for lc in large_clusters:
            clusters.extend(cluster_rids(lc, score_threshold))
        score_threshold += 1

    report_cluster_sizes()

    clusters = sorted(clusters, key=lambda c: -len(c))
    if csv_filename:
        write_csv(rows=clusters, filename=csv_filename)

    if print_markdown:
        for i, c in enumerate(clusters):
            if len(c) <= 1:
                break
            name = f"Cluster with {len(c)} cells"
            if len(c) > 50:
                c = random.sample(c, 50)
                name += " (sample)"
            link = f"http://codex.flywire.ai/app/search?filter_string={','.join([str(r) for r in c])}"
            print(f"1. [{name}]({link})")


if __name__ == "__main__":
    SEZ_PILS = {"PRW", "GNG", "SAD", "AMMC_R", "AMMC_L"}

    def is_sez(ndata):
        return any([p in SEZ_PILS for p in ndata["input_neuropils"]]) or any(
            [p in SEZ_PILS for p in ndata["output_neuropils"]]
        )

    cluster_neurons(
        predicate=lambda n: is_sez(n),
        directed=False,
        csv_filename="sez_clusters_v2.csv",
        print_markdown=True,
    )
