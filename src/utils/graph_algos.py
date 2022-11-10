# Finds the set of neurons reachable in one step from a given set of source neurons 's'.
from collections import defaultdict

from src.utils.formatting import percentage


# computes the set of nodes reachable in 1 hop from given sources
def neighbors(sources, neighbor_sets):
    res = set()
    for s in sources:
        oset = neighbor_sets.get(s)
        if oset:
            res |= oset
    return res


# given set of sources, calculates the distance to all other reachable nodes into a dict (rid -> distance)
def reachable_nodes(sources, neighbor_sets):
    depth = 0
    reached = {s: 0 for s in sources}
    frontier = set(sources)
    while frontier:
        depth += 1
        ngh = neighbors(sources=frontier, neighbor_sets=neighbor_sets)
        frontier = ngh - reached.keys()
        for f in frontier:
            reached[f] = depth
    return reached


# given set of sources, calculates and formats the number of nodes reachable within 1, 2, 3... steps
def reachable_node_counts(sources, neighbor_sets, total_count):
    reached = reachable_nodes(sources=sources, neighbor_sets=neighbor_sets)
    res = defaultdict(int)
    for k, v in reached.items():
        res[v] += 1

    aggregated = {}
    for i in range(1, 100):
        if i not in res:
            break
        agg_val = sum([res[j] for j in range(i + 1)])
        aggregated[
            f"{i} hop{'s' if i > 1 else ''}"
        ] = f"{'{:,}'.format(agg_val)} ({percentage(agg_val, total_count)})"
    print(f"{res} -> {aggregated}")
    return aggregated


# given set of sources and target nodes, calculates the pairwise distance matrix from any source to any target
def distance_matrix(sources, targets, neighbor_sets):
    matrix = [['from \ to'] + targets]
    for s in sources:
        reached = reachable_nodes(sources=[s], neighbor_sets=neighbor_sets)
        matrix.append([s] + [reached.get(t, -1) for t in targets])
        del reached
    return matrix
