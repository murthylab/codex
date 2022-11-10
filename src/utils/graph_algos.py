from collections import defaultdict
from src.utils.logging import log_error
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
    matrix = [["from \ to"] + targets]
    for s in sources:
        reached = reachable_nodes(sources=[s], neighbor_sets=neighbor_sets)
        matrix.append([s] + [reached.get(t, -1) for t in targets])
        del reached
    return matrix


# given a source and a target node, finds all nodes along shortest-path pathways from source to target
# and their distance from source (or None if not reachable)
def pathways(source, target, input_sets, output_sets):
    try:
        source = int(source)
        target = int(target)
    except:
        log_error(f"Invalid Cell IDs for pathways: {source=} {target=}")
        return None

    if source == target or source not in output_sets or target not in input_sets:
        return None

    fwd = reachable_nodes(sources=[source], neighbor_sets=output_sets)
    if target not in fwd:
        return None
    distance = fwd[target]
    assert distance > 0

    bwd = reachable_nodes(sources=[target], neighbor_sets=input_sets)
    assert source in bwd and distance == bwd[source]

    path_nodes = defaultdict(int)
    for n, df in fwd.items():
        if n in bwd:
            db = bwd[n]

            if df + db == distance:
                path_nodes[n] = df
            else:
                assert df + db >= distance
    distant_nodes = [n for n, d in path_nodes.items() if d == distance]
    assert distant_nodes == [target]

    return path_nodes
