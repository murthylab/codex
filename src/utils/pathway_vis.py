from collections import defaultdict

from src.configuration import MIN_SYN_COUNT
from src.utils.graph_algos import pathways


def pathway_chart_data_rows(source, target, neuron_db, min_syn_count=MIN_SYN_COUNT):
    input_sets = neuron_db.input_sets(min_syn_count=min_syn_count)
    output_sets = neuron_db.output_sets(min_syn_count=min_syn_count)
    pathway_nodes = pathways(
        source=source, target=target, input_sets=input_sets, output_sets=output_sets
    )

    if not pathway_nodes:
        return None, None

    path_edges = []
    for n1 in pathway_nodes.keys():
        for n2 in pathway_nodes.keys():
            if (
                n1 != n2
                and n2 in output_sets[n1]
                and pathway_nodes[n2] == pathway_nodes[n1] + 1
            ):
                path_edges.append((n1, n2))

    combined_edge_weights = defaultdict(int)
    connection_rows = neuron_db.connections(ids=pathway_nodes.keys(), min_syn_count=min_syn_count)
    for r in connection_rows:
        combined_edge_weights[(r[0], r[1])] += r[3]

    data_rows = []
    for p in path_edges:
        label1 = neuron_db.get_neuron_data(p[0])["name"]
        label2 = neuron_db.get_neuron_data(p[1])["name"]
        data_rows.append(
            [
                f"{label1} {pathway_nodes[p[0]]}",
                f"{label2} {pathway_nodes[p[1]]}",
                combined_edge_weights[(p[0], p[1])],
            ]
        )

    return max(pathway_nodes.values()), data_rows
