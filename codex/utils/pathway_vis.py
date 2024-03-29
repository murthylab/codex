from collections import defaultdict
from functools import lru_cache

from codex.utils.graph_algos import pathways


def sort_layers(node_layers, cons):
    # layers: {i: [nodes in layer i]}
    layers = defaultdict(list)
    for node in node_layers:
        layer = node_layers[node]
        layers[layer].append(node)

    if len(layers) > 3:
        # node_cons: {node id: [(connected node id, weight of connection) for all connections]}
        node_cons = defaultdict(list)
        for con in cons:
            node_cons[con[0]].append((con[1], con[2]))
            node_cons[con[1]].append((con[0], con[2]))

        # layer1_weights: {node id: total weight of node's connections to layer 2} for all layer 1 nodes
        layer1_weights = defaultdict(int)
        for node in layers[1]:
            for con in node_cons[node]:
                if node_layers[con[0]] == 2:
                    layer1_weights[node] += con[1]

        # initially sort first layer by weights from root
        layers[1].sort(key=lambda x: layer1_weights[x], reverse=True)

        def sort_layer(sort_i, ref_i):
            print(f"Sorting layer {sort_i} in ref to {ref_i}")
            layer_ref = layers[ref_i]
            layer_sort = layers[sort_i]
            layer_matches = {}
            for rnode in layer_sort:
                best_weight = -1
                best_node = None
                for node_con in node_cons[rnode]:
                    if node_layers[node_con[0]] == ref_i and node_con[1] > best_weight:
                        best_weight = node_con[1]
                        best_node = node_con[0]
                match_pos = layer_ref.index(best_node)
                layer_matches[rnode] = match_pos
            layer_sort.sort(key=lambda x: layer_matches[x])

        # sort layer lists by best matching with prior layer
        for i in range(1, len(layers) - 2):
            sort_layer(i + 1, i)

        # re-sort first layer to match second layer
        sort_layer(1, 2)

    # add node position in layer to node_layers
    for node in node_layers:
        layer_i = node_layers[node]
        layer = layers[layer_i]
        node_layers[node] = (layer_i, layer.index(node))


@lru_cache
def pathway_chart_data_rows(source, target, neuron_db, min_syn_count=0):
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

    _, outs_with_synapse_counts = neuron_db.input_output_partners_with_synapse_counts(
        min_syn_count=min_syn_count
    )

    data_rows = [
        [
            p[0],
            p[1],
            outs_with_synapse_counts[p[0]][p[1]],
        ]
        for p in path_edges
    ]
    sort_layers(pathway_nodes, data_rows)

    return pathway_nodes, data_rows
