from collections import defaultdict
import random

from networkx import DiGraph, connected_components, strongly_connected_components

from src.data.local_data_loader import write_csv, unpickle_neuron_db, read_csv
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.neuron_data_initializer import NEURON_DATA_ATTRIBUTE_TYPES
from src.utils.formatting import percentage
from networkx import Graph, community

from src.utils.stats import jaccard_weighted

"""
Clusters a set of neurons by morphological similarity. Uses iterative application of the connected component analysis on
a graph induced by NBLAST similarity scores with increasing thresholds for refinement.
"""


def check_morphology_clusters():
    neuron_db = NeuronDataFactory.instance().get()

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
    neuron_db = NeuronDataFactory.instance().get()

    def neuron_type(ndata):
        return f'{ndata["class"]}:{ndata["nt_type"]}:{".".join(sorted(set(ndata["input_neuropils"] + ndata["output_neuropils"])))}'

    type_lists = defaultdict(list)
    for ndata in neuron_db.neuron_data.values():
        type_lists[neuron_type(ndata)].append(ndata["root_id"])

    print({t: v for t, v in type_lists.items() if 100 > len(v) > 10})
    print(len(type_lists.items()))


def cluster_neurons(predicate, directed=True, print_markdown=False, csv_filename=None):
    neuron_db = NeuronDataFactory.instance().get()

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


def compare_versions(v1, v2):
    ndb1 = unpickle_neuron_db(version=v1)
    ndb2 = unpickle_neuron_db(version=v2)

    if set(ndb1.neuron_data.keys()) == set(ndb2.neuron_data.keys()):
        print(f"All {len(ndb1.neuron_data)} neuron IDs equal")
    else:
        print(
            f"Num neurons in {v1}: {len(ndb1.neuron_data)}, {v2}: {len(ndb2.neuron_data)}"
        )
        print(
            f"Num neurons in {v1} and {v2}: {len(set(ndb1.neuron_data.keys()) & set(ndb2.neuron_data.keys()))}"
        )
        print(
            f"Num neurons in {v1} - {v2}: {len(set(ndb1.neuron_data.keys()) - set(ndb2.neuron_data.keys()))}"
        )
        print(
            f"Num neurons in {v2} - {v1}: {len(set(ndb2.neuron_data.keys()) - set(ndb1.neuron_data.keys()))}"
        )

    common_neuron_rids = set(ndb1.neuron_data.keys()).intersection(
        ndb2.neuron_data.keys()
    )
    equal_attrs = []
    for attr in NEURON_DATA_ATTRIBUTE_TYPES.keys():
        if any(
            [
                r
                for r in common_neuron_rids
                if ndb1.neuron_data[r][attr] != ndb2.neuron_data[r][attr]
            ]
        ):
            only_in_1 = [
                ndb1.neuron_data[r][attr]
                for r in common_neuron_rids
                if ndb1.neuron_data[r][attr] and not ndb2.neuron_data[r][attr]
            ]

            only_in_2 = [
                ndb2.neuron_data[r][attr]
                for r in common_neuron_rids
                if ndb2.neuron_data[r][attr] and not ndb1.neuron_data[r][attr]
            ]

            both_have_same = len(
                [
                    r
                    for r in common_neuron_rids
                    if ndb1.neuron_data[r][attr]
                    and ndb2.neuron_data[r][attr]
                    and ndb1.neuron_data[r][attr] == ndb2.neuron_data[r][attr]
                ]
            )
            both_have_diff = [
                f"{ndb1.neuron_data[r][attr]} vs {ndb2.neuron_data[r][attr]}"
                for r in common_neuron_rids
                if ndb1.neuron_data[r][attr]
                and ndb2.neuron_data[r][attr]
                and ndb1.neuron_data[r][attr] != ndb2.neuron_data[r][attr]
            ]

            print(
                f"- {attr}:"
                f"\n   Both have same: {both_have_same}"
                f"\n   Both have diff {len(both_have_diff)}: {both_have_diff[:500]}"
                f"\n   Only in 1 {len(only_in_1)}: {only_in_1[:500]}"
                f"\n   Only in 2 {len(only_in_2)}: {only_in_2[:500]}"
            )
        else:
            equal_attrs.append(attr)
    if equal_attrs:
        print(f"- all values equal for attributes {', '.join(equal_attrs)}")


def cluster_SEZ_cells():
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


def generate_con_jaccard_similarity_table(neuron_db):
    # split neurons into buckets by similarity heuristic (to reduce number of candidate pairs)
    candidate_buckets = defaultdict(list)
    for rid, nd in neuron_db.neuron_data.items():
        candidate_buckets[
            f"{nd['side']}:{nd['input_neuropils']}:{nd['output_neuropils']}:{len(str(nd['input_synapses']))}:{len(str(nd['output_synapses']))}"
        ].append(rid)
    num_candidate_pairs = sum(
        [len(s) * (len(s) - 1) // 2 for s in candidate_buckets.values()]
    )
    print(
        f"{len(candidate_buckets)} buckets, {num_candidate_pairs} candidates, max bucket size: {max([len(v) for v in candidate_buckets.values()])}"
    )
    # print out large buckets (for tuning bucketing method)
    for k, v in candidate_buckets.items():
        if len(v) > 3000:
            print(f"{k}: {len(v)}")

    ins, outs = neuron_db.input_output_partners_with_synapse_counts()

    s = 0
    combined_score = 0

    tbl = [["id1", "id2", "jaccard score", "ins 1", "outs 1", "ins 2", "outs 2"]]
    for i, rids in enumerate(candidate_buckets.values()):
        for j, r1 in enumerate(rids):
            r1_ins = ins[r1]
            r1_outs = outs[r1]
            for k, r2 in enumerate(rids[j + 1 :]):
                r2_ins = ins[r2]
                r2_outs = outs[r2]
                jscore = (
                    jaccard_weighted(r1_ins, r2_ins)
                    + jaccard_weighted(r1_outs, r2_outs)
                ) / 2
                combined_score += jscore
                s += 1
                if s % (num_candidate_pairs // 100) == 0:
                    print(
                        f"scanned {s}, added {len(tbl)}, {percentage(s, num_candidate_pairs)}"
                    )
                if jscore > 0:
                    tbl.append(
                        [
                            r1,
                            r2,
                            jscore,
                            neuron_db.get_neuron_data(r1)["input_cells"],
                            neuron_db.get_neuron_data(r1)["output_cells"],
                            neuron_db.get_neuron_data(r2)["input_cells"],
                            neuron_db.get_neuron_data(r2)["output_cells"],
                        ]
                    )

    print(f"{s} {combined_score}")
    write_csv(
        filename="static/experimental_data/jaccard_scores_weighted.csv.gz",
        rows=tbl,
        compress=True,
    )


def analyse_con_jaccard_similarities(neuron_db):
    scores_table = read_csv(
        filename="static/experimental_data/jaccard_scores_weighted.csv.gz"
    )
    print(f"{len(scores_table)=}")

    scores_dict = {}
    tot_score = 0.0
    score_sets = defaultdict(set)
    for r in scores_table[1:]:
        score = float(r[2])
        scores_dict[(int(r[0]), int(r[1]))] = score
        tot_score += score
        score_sets[r[2][2]].add(r[0])
        score_sets[r[2][2]].add(r[1])
        if score > 0.7 and sum([int(v) for v in r[3:]]) > 10:
            print(r)

    print(
        f"Number of neurons with any jaccard score: {len(set.union(*list(score_sets.values())))}"
    )
    for k, v in score_sets.items():
        print(f"{len(v)} neurons with jaccard score ~ 0.{k}")

    print(f"Avg score: {tot_score / len(scores_dict)}")

    def measure_internal_score(attr_name):
        def compare_attr(pair):
            nd1, nd2 = (
                neuron_db.neuron_data[pair[0]],
                neuron_db.neuron_data[pair[1]],
            )
            attr1, attr2 = nd1[attr_name], nd2[attr_name]
            if not attr1 or not attr2:
                return None
            if isinstance(nd1[attr_name], list):
                return (
                    "eq"
                    if len(set(nd1[attr_name]).intersection(nd2[attr_name])) > 0
                    else "neq"
                )
            else:
                return "eq" if nd1[attr_name] == nd2[attr_name] else "neq"

        same_scores = 0
        same_pairs = 0
        diff_scores = 0
        diff_pairs = 0
        for p, s in scores_dict.items():
            ca = compare_attr(p)
            if ca == "eq":
                same_scores += s
                same_pairs += 1
            elif ca == "neq":
                diff_scores += s
                diff_pairs += 1

        print(
            f"in {attr_name}\n   "
            f"avg same: {same_scores / same_pairs} from {same_pairs} pairs\n   "
            f"avg diff: {diff_scores / diff_pairs} from {diff_pairs} pairs"
        )

    measure_internal_score("cell_type")
    measure_internal_score("hemibrain_type")
    measure_internal_score("morphology_cluster")
    measure_internal_score("class")
    measure_internal_score("super_class")
    measure_internal_score("label")
    measure_internal_score("sub_class")
    measure_internal_score("group")
    measure_internal_score("nerve")


def cluster_by_jaccard_similarities():
    scores_table = read_csv(
        filename="static/experimental_data/jaccard_scores_weighted.csv.gz"
    )
    print("Building score graph..")
    G = Graph()
    for r in scores_table[1:]:
        n1, n2, score = int(r[0]), int(r[1]), float(r[2])
        G.add_node(n1)
        G.add_node(n2)
        G.add_edge(n1, n2, weight=100 / score)

    print("Running community analysis..")
    communities_generator = community.louvain_communities(G, resolution=200)
    clusters_dict = {}
    component_id = 0
    max_xluster_size = 0
    for s in sorted(communities_generator, key=lambda x: -len(x)):
        if len(s) > 1:
            max_xluster_size = max(max_xluster_size, len(s))
            component_id += 1
            cluster_name = f"CC_{component_id}.{len(s)}"
            for rid in s:
                clusters_dict[rid] = cluster_name

    print(
        f"Total clustered rids: {len(clusters_dict)}, {max_xluster_size=}, # clusters: {component_id}"
    )
    clusters_table = [["root_id", "connectivity_cluster"]]
    for rid, cl in clusters_dict.items():
        clusters_table.append([rid, cl])

    print("Writing results to file..")
    write_csv(
        filename="static/experimental_data/connectivity_clusters.csv.gz",
        rows=clusters_table,
        compress=True,
    )


def make_rid_to_morpho_cluster_map_for_dsxfru(neuron_db):
    rid_to_morpho_cluster = {}
    morpho_cluster_to_rids = defaultdict(list)
    for rid, nd in neuron_db.neuron_data.items():
        mc = nd["morphology_cluster"] or f"c_{rid}"
        rid_to_morpho_cluster[rid] = mc
        morpho_cluster_to_rids[mc].append(rid)
    print(f"Num clusters: {len(set(rid_to_morpho_cluster.values()))}")
    return rid_to_morpho_cluster, morpho_cluster_to_rids


def make_morphology_graph_jscores_for_dsxfru(neuron_db, jscores_fname):
    rid_to_morpho_cluster, _ = make_rid_to_morpho_cluster_map_for_dsxfru(neuron_db)
    # build projected morpho cluster graph
    morpho_graph_ins, morpho_graph_outs = {}, {}
    for r in neuron_db.connections_.all_rows():
        fn, tn = rid_to_morpho_cluster[r[0]], rid_to_morpho_cluster[r[1]]
        if tn not in morpho_graph_ins:
            morpho_graph_ins[tn] = defaultdict(int)
            morpho_graph_ins[tn][fn] += r[3]
        if fn not in morpho_graph_outs:
            morpho_graph_outs[fn] = defaultdict(int)
            morpho_graph_outs[fn][tn] += r[3]

    # calculate jaccard scores
    jscores = {}
    morpho_nodes = sorted(set(rid_to_morpho_cluster.values()))
    for i1, n1 in enumerate(morpho_nodes):
        for i2, n2 in enumerate(morpho_nodes):
            if i2 <= i1:
                continue

            jscore = (
                jaccard_weighted(morpho_graph_ins.get(n1), morpho_graph_ins.get(n2))
                + jaccard_weighted(morpho_graph_outs.get(n1), morpho_graph_outs.get(n2))
            ) / 2
            if jscore:
                jscores[(n1, n2)] = jscore
    print(f"Num jscores: {len(jscores)}")
    write_csv(
        jscores_fname, rows=[[k[0], k[1], v] for k, v in jscores.items()], compress=True
    )


def cluster_with_morpho_jscores_for_dsxfru(neuron_db, morpho_jscores_fname):
    _, mc_to_rids = make_rid_to_morpho_cluster_map_for_dsxfru(neuron_db)
    morpho_jscores = read_csv(morpho_jscores_fname)
    print("Building score graph..")
    G = Graph()
    for r in morpho_jscores:
        n1, n2, score = r[0], r[1], float(r[2])
        G.add_node(n1)
        G.add_node(n2)
        G.add_edge(n1, n2, weight=100 * score)

    print("Running community analysis..")
    communities_generator = community.louvain_communities(G, resolution=10)
    clusters_dict = {}
    component_id = 0
    max_xluster_size = 0
    for s in sorted(communities_generator, key=lambda x: -len(x)):
        max_xluster_size = max(max_xluster_size, len(s))
        component_id += 1
        cluster_name = f"CC_{component_id}"
        rids = []
        for mc in s:
            for rid in mc_to_rids[mc]:
                clusters_dict[rid] = cluster_name
                rids.append(rid)
        print(f"{len(rids)}: {sorted(rids)[:10]}")

    print(
        f"Total clustered rids: {len(clusters_dict)}, {max_xluster_size=}, # clusters: {component_id}"
    )
    clusters_table = [["root_id", "morpho_connectivity_cluster"]]
    for rid, cl in clusters_dict.items():
        clusters_table.append([rid, cl])

    print("Writing results to file..")
    write_csv(
        filename="static/experimental_data/morpho_connectivity_clusters.csv.gz",
        rows=clusters_table,
        compress=True,
    )


def generate_untyped_ol_cosine_matrix(neuron_db, fname):
    def untyped_ol_cell(nd):
        if nd["side"] != "right" or nd["super_class"] != "optic":
            return False
        for mrk in nd["marker"]:
            if mrk.startswith("olr_type:"):
                return mrk.split(":")[1].lower().startswith("unknown")
        print("ERROR: OLR cell without a marker!!")
        assert False

    untyped_ol_cell_ids = [
        rid for rid, nd in neuron_db.neuron_data.items() if untyped_ol_cell(nd)
    ]
    print(
        f"Identified {len(untyped_ol_cell_ids)} untyped cells in the right OL. Calculating scores..."
    )
    scores_matrix = [untyped_ol_cell_ids]
    for i1, rid1 in enumerate(untyped_ol_cell_ids):
        row = []
        for i2, rid2 in enumerate(untyped_ol_cell_ids):
            if i2 > i1:
                score = neuron_db.svd.calculate_cosine_similarity(
                    rid1, rid2, up=True, down=True
                )
            elif i1 > i2:
                score = scores_matrix[i2 + 1][i1]
            else:
                score = 1
            row.append(score)
        scores_matrix.append(row)
    print(f"Calculated score matrix of length {len(scores_matrix)}. Writing to file...")
    write_csv(filename=fname, rows=scores_matrix, compress=True)


def cluster_untyped_ol_cells(scores_fname, clusters_fname):
    scores_matrix = read_csv(scores_fname)
    print(f"Read {len(scores_matrix)} score rows. Building score graph..")
    rids = scores_matrix[0]
    G = Graph()
    for i1, rid1 in enumerate(rids):
        G.add_node(rid1)
        for i2, rid2 in enumerate(rids):
            if i1 >= i2:
                continue
            if i1 == 0:
                G.add_node(rid2)
            score = scores_matrix[i1 + 1][i2]
            if score == "":
                score = -1
            G.add_edge(rid1, rid2, weight=100 * (float(score) + 1))

    print("Running community analysis..")
    communities_generator = community.louvain_communities(G, resolution=2)
    clusters_dict = {}
    component_id = 0
    max_xluster_size = 0
    for s in sorted(communities_generator, key=lambda x: -len(x)):
        max_xluster_size = max(max_xluster_size, len(s))
        component_id += 1
        cluster_name = f"CC_{component_id}"
        rids = []
        for rid in s:
            clusters_dict[rid] = cluster_name
            rids.append(rid)
        print(f"{len(rids)}: {sorted(rids)[:10]}")

    print(
        f"Total clustered rids: {len(clusters_dict)}, {max_xluster_size=}, # clusters: {component_id}"
    )
    clusters_table = [["root_id", "morpho_connectivity_cluster"]]
    for rid, cl in clusters_dict.items():
        clusters_table.append([rid, cl])

    print(f"Writing results to file {clusters_fname}..")
    write_csv(
        filename=clusters_fname,
        rows=clusters_table,
        compress=True,
    )


def predict_ol_types(neuron_db):
    def is_unknown_ol(nd):
        return "olr_type:Unknown-not-labeled" in nd["marker"]

    unknown_ol = [rid for rid, nd in neuron_db.neuron_data.items() if is_unknown_ol(nd)]
    assert 1000 < len(unknown_ol)

    def ol_type(rid):
        for mrk in neuron_db.get_neuron_data(rid)["marker"]:
            if mrk.startswith("olr_type:"):
                olt = mrk.split(":")[1]
                if olt.startswith("Unknown"):
                    return None
                else:
                    return olt
        return None

    def argmax_keys(counts):
        mv = max(counts.values())
        return mv, [k for k, v in counts.items() if v == mv]

    def infer_type(primary_type_lists, secondary_type_lists):
        primary_counts = {k: len(v) for k, v in primary_type_lists.items()}
        secondary_counts = {k: len(v) for k, v in secondary_type_lists.items()}

        if primary_counts and secondary_counts:
            c1, argmax1 = argmax_keys(primary_counts)
            c2, argmax2 = argmax_keys(secondary_counts)
            if (
                len(argmax1) == 1
                and len(argmax2) == 1
                and min(c1, c2) > 1
                and argmax1[0] == argmax2[0]
            ):
                olt_type = argmax1[0]
                evidence_list = primary_type_lists[olt_type]
                return olt_type, evidence_list
        elif primary_counts:
            count, types = argmax_keys(primary_counts)
            if count > 2 and len(types) == 1:
                return types[0], primary_type_lists[types[0]]
        return None, None

    predictions = {}
    predictions_fname = "static/data/630/olt_type_predictions.csv"
    for i, rid in enumerate(unknown_ol):
        jac_olt_to_cells = defaultdict(set)
        cos_olt_to_cells = defaultdict(set)
        jac_sim_cells = neuron_db.get_similar_connectivity_cells(
            rid, include_upstream=True, include_downstream=True
        )
        for sc in jac_sim_cells:
            olt = ol_type(sc)
            if olt:
                jac_olt_to_cells[olt].add(sc)

        cos_sim_cells = neuron_db.get_similar_embedding_cells(
            rid, include_upstream=True, include_downstream=True, limit=20
        )
        for sc in cos_sim_cells:
            olt = ol_type(sc)
            if olt:
                cos_olt_to_cells[olt].add(sc)

        inf_type, evidence_cells = infer_type(jac_olt_to_cells, cos_olt_to_cells)
        if inf_type:
            predictions[rid] = (inf_type, evidence_cells)
            print("======= prediction below =======")
        print(
            f"{i} of {len(unknown_ol)} / {len(predictions)}: {rid}\n"
            f"  Jac {len(jac_sim_cells)}: {dict(jac_olt_to_cells)}\n"
            f"  Cos {len(cos_sim_cells)}: {dict(cos_olt_to_cells)}\n"
            f"  --> {rid}, {inf_type}, {evidence_cells}"
        )

        if i % 100 == 10 or i >= len(unknown_ol) - 1:
            prows = [
                [k, v[0], ",".join([str(rid) for rid in v[1]])]
                for k, v in predictions.items()
            ]
            write_csv(filename=predictions_fname, rows=prows)


if __name__ == "__main__":
    predict_ol_types(NeuronDataFactory.instance().get())

    # untyped_ol_cosine_matrix_file = (
    #    "static/experimental_data/untyped_ol_cosine_matrix.csv.gz"
    # )
    # untyped_ol_clusters_file = "static/experimental_data/untyped_ol_clusters.csv.gz"
    # generate_untyped_ol_cosine_matrix(NeuronDataFactory.instance().get(), untyped_ol_cosine_matrix_file)
    # cluster_untyped_ol_cells(
    #    scores_fname=untyped_ol_cosine_matrix_file,
    #    clusters_fname=untyped_ol_clusters_file,
    # )

    # morpho_jscores_fname = "static/experimental_data/morpho_jaccard_scores.csv.gz"
    # make_morphology_graph_jscores_for_dsxfru(NeuronDataFactory.instance().get(), morpho_jscores_fname)
    # cluster_with_morpho_jscores_for_dsxfru(NeuronDataFactory.instance().get(), morpho_jscores_fname)

    # compare_versions("630_before_cb_matches", "630")

    # generate_con_jaccard_similarity_table(NeuronDataFactory.instance().get())
    # analyse_con_jaccard_similarities(NeuronDataFactory.instance().get())
    # cluster_by_jaccard_similarities()
