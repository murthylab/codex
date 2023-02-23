from collections import defaultdict
from functools import lru_cache

from src.configuration import MIN_SYN_COUNT
from src.utils.graph_algos import pathways


def sort_connections(node_layers, cons):
    # TODO improve matching algorithm

    # layers: {i: [nodes in layer i]}
    layers = {}
    for node in node_layers:
        layer = node_layers[node]
        if layer not in layers:
            layers[layer] = []
        layers[layer].append(node)
    if len(layers) <= 3:
        return cons

    # node_cons: {node id: [(connected node id, weight of connection) for all connections]}
    node_cons = {}
    for con in cons:
        if con[0] not in node_cons:
            node_cons[con[0]] = []
        if con[1] not in node_cons:
            node_cons[con[1]] = []
        node_cons[con[0]].append((con[1], con[2]))
        node_cons[con[1]].append((con[0], con[2]))

    # layer1_weights: {node id: total weight of node's connections to layer 2} for all layer 1 nodes
    layer1_weights = {}
    for node in layers[1]:
        layer1_weights[node] = 0
        for con in node_cons[node]:
            if node_layers[con[0]] == 2:
                layer1_weights[node] += con[1]

    layers[1].sort(key=lambda x: layer1_weights[x], reverse=True)

    # sort layer lists by best matching with prior layer
    for i in range(1, len(layers) - 2):
        layer_l = layers[i]
        layer_r = layers[i + 1]
        best_weight = 0
        best_node = None
        layer_matches = {}
        for rnode in layer_r:
            for con in node_cons[rnode]:
                if node_layers[con[0]] == i and con[1] > best_weight:
                    best_weight = con[1]
                    best_node = con[0]
            match_pos = layer_l.index(best_node)
            layer_matches[rnode] = match_pos
        layer_r.sort(key=lambda x: layer_matches[x])

    # sort node_cons lists by layer and position within layer
    def layer_pos(node):
        n = node[0]
        layer_i = node_layers[n]
        layer = layers[layer_i]
        return layer_i * 100 + layer.index(n)

    for node in node_cons:
        node_con = node_cons[node]
        node_con.sort(key=layer_pos)

    # sorted_cons: [(node 1, node 2, weight) for each node connection]
    # same as cons but in proper matched order
    sorted_cons = []
    for l in layers:
        layer = layers[l]
        for layer_node in layer:
            node_con = node_cons[layer_node]
            for con in node_con:
                sorted_cons.append((layer_node, con[0], con[1]))

    return sorted_cons


@lru_cache
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
    connection_rows = neuron_db.connections(
        ids=pathway_nodes.keys(), min_syn_count=min_syn_count
    )
    for r in connection_rows:
        combined_edge_weights[(r[0], r[1])] += r[3]

    data_rows = []
    for p in path_edges:
        data_rows.append(
            [
                p[0],
                p[1],
                combined_edge_weights[(p[0], p[1])],
            ]
        )
    data_rows = sort_connections(pathway_nodes, data_rows)

    return pathway_nodes, data_rows
