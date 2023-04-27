from collections import defaultdict

from src.data.brain_regions import REGIONS, without_side_suffix
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


def compile_nt_scores_data(neuron_nt_type_predictions_content):
    header = neuron_nt_type_predictions_content[0]
    rid_to_scores = {}
    rid_col_id = header.index("root_id")
    nt_score_col_indices = {
        nt_type: header.index(f"{nt_type.lower()}_avg")
        for nt_type in NEURO_TRANSMITTER_NAMES
    }

    def isnan(val):
        return val != val

    for r in neuron_nt_type_predictions_content[1:]:
        rid = int(r[rid_col_id])
        if rid not in rid_to_scores:
            rid_to_scores[rid] = defaultdict(int)
        for nt, i in nt_score_col_indices.items():
            if not isnan(r[i]):
                rid_to_scores[rid][header[i]] = r[i]

    def round_float(f):
        return float("{:0.2f}".format(f))

    def round_all(scores_dict, normalize=False):
        tot = sum(scores_dict.values()) if normalize else 1
        for k, v in scores_dict.items():
            scores_dict[k] = round_float(v / tot)

    for rid, scores in rid_to_scores.items():
        round_all(scores)

    return rid_to_scores


def infer_nt_type_and_score(scores):
    scores = sorted([(sc, k) for k, sc in scores.items()], reverse=True)
    if scores and scores[0][0] > 0.2 and scores[0][0] > scores[1][0] + 0.1:
        nt_type = scores[0][1].replace("_avg", "").upper()
        assert nt_type in NEURO_TRANSMITTER_NAMES
        return nt_type, scores[0][0]
    else:
        return "", -1.0


def assign_names_and_groups(
    all_neurons_set, input_neuropill_counts, output_neuropill_counts
):
    def make_group_name(root_id):
        def max_pil(counts):
            return (
                max([(kk, vv) for kk, vv in counts.items()], key=lambda p: p[1])[0]
                if counts
                else None
            )

        prom_in = max_pil(input_neuropill_counts.get(root_id))
        prom_out = max_pil(output_neuropill_counts.get(root_id))
        prom_in = without_side_suffix(prom_in) if prom_in else None
        prom_out = without_side_suffix(prom_out) if prom_out else None
        if not prom_in and not prom_out:
            return "NO_CONS"
        elif not prom_out:
            return prom_in
        elif not prom_in:
            return prom_out
        else:
            return f"{prom_in}.{prom_out}" if prom_in != prom_out else prom_in

    group_lists = defaultdict(list)
    for rid in sorted(all_neurons_set):
        group_lists[make_group_name(rid)].append(rid)

    groups = {}
    names = {}
    for k, v in group_lists.items():
        for i, rid in enumerate(v):
            groups[rid] = k
            names[rid] = f"{k}.{i + 1}"

    print(f"Num groups: {len(group_lists)}")
    print(f"Largest bucket: {max([(len(v), k) for k, v in group_lists.items()])}")
    print(
        f"Buckets with 1 cell: {len([v for v in group_lists.values() if len(v) == 1])}"
    )
    print(
        f"Buckets with >100 cells: {len([v for v in group_lists.values() if len(v) > 100])}"
    )
    print(f"Sample: {list(names.values())[500:5000:1000]}")
    return names, groups


def compile_neuron_rows(
    proofread_rids_set,
    neuron_nt_type_predictions_content,
    syn_table_content,
    syn_table_columns,
):
    from_col_id = syn_table_columns.index("pre_pt_root_id")
    to_col_id = syn_table_columns.index("post_pt_root_id")
    pil_col_id = syn_table_columns.index("neuropil")
    syn_cnt_col_id = syn_table_columns.index("syn_count")

    input_neuropill_counts = {rid: defaultdict(int) for rid in proofread_rids_set}
    output_neuropill_counts = {rid: defaultdict(int) for rid in proofread_rids_set}

    for i, r in enumerate(syn_table_content):
        if i == 0:
            assert r == syn_table_columns
            continue
        syn_cnt = r[syn_cnt_col_id]
        from_rid = r[from_col_id]
        to_rid = r[to_col_id]
        pil = r[pil_col_id]
        assert isinstance(syn_cnt, int)
        assert isinstance(from_rid, int) and from_rid in proofread_rids_set
        assert isinstance(to_rid, int) and to_rid in proofread_rids_set
        assert pil in REGIONS

        output_neuropill_counts[from_rid][pil] += syn_cnt
        input_neuropill_counts[to_rid][pil] += syn_cnt

    print(
        f"Collected neuropil counts for cell naming from {len(syn_table_content) - 1} rows"
    )

    # assign names and groups based on in/out neuropils
    names, groups = assign_names_and_groups(
        proofread_rids_set, input_neuropill_counts, output_neuropill_counts
    )

    # compute nt type info
    rid_to_nt_scores = compile_nt_scores_data(neuron_nt_type_predictions_content)
    rid_to_nt_type = {
        rid: infer_nt_type_and_score(scores) for rid, scores in rid_to_nt_scores.items()
    }
    print(
        f"Neurons without NT type: {len([v for v in proofread_rids_set if not rid_to_nt_type.get(v, [0, 0])[1]])}"
    )

    neuron_rows = [
        ["root_id", "name", "group", "nt_type", "nt_type_score"]
        + [f"{nt_type.lower()}_avg" for nt_type in NEURO_TRANSMITTER_NAMES]
    ]
    for rid in sorted(proofread_rids_set):
        row = [rid]
        row.append(names[rid])
        row.append(groups[rid])
        row.append(rid_to_nt_type[rid][0] if rid in rid_to_nt_type else "")
        row.append(rid_to_nt_type[rid][1] if rid in rid_to_nt_type else 0.0)
        row += (
            [
                rid_to_nt_scores[rid][f"{nt.lower()}_avg"]
                for nt in NEURO_TRANSMITTER_NAMES
            ]
            if rid in rid_to_nt_scores
            else [0.0] * len(NEURO_TRANSMITTER_NAMES)
        )
        neuron_rows.append(row)
    print(f"Sample: {neuron_rows[0:100000:10000]}")

    # check that all rows have the right length
    for i, r in enumerate(neuron_rows):
        assert len(r) == len(neuron_rows[0])

    return neuron_rows


def compile_connection_rows(filtered_syn_table_content, columns):
    connections = []
    from_col_id = columns.index("pre_pt_root_id")
    to_col_id = columns.index("post_pt_root_id")
    pil_col_id = columns.index("neuropil")
    syn_cnt_col_id = columns.index("syn_count")
    nt_score_col_indices = {
        nt_type: columns.index(f"{nt_type.lower()}_avg")
        for nt_type in NEURO_TRANSMITTER_NAMES
    }
    for i, r in enumerate(filtered_syn_table_content):
        if i == 0:
            assert r == columns
            connections.append(
                ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"]
            )
        else:
            syn_cnt = r[syn_cnt_col_id]
            assert isinstance(syn_cnt, int)
            nt_scores = [
                (float(r[nt_score_col_indices[ntt]]), ntt)
                for ntt in NEURO_TRANSMITTER_NAMES
            ]
            nt_type = max(nt_scores)[1]
            connections.append(
                [r[from_col_id], r[to_col_id], r[pil_col_id], syn_cnt, nt_type]
            )
    return connections


def compile_neuropil_synapse_rows(filtered_syn_table_content, columns):
    print("Compiling neuropil synapse table...")
    rid_to_counts = {}
    rid_to_input_partners = defaultdict(set)
    rid_to_output_partners = defaultdict(set)
    from_col_id = columns.index("pre_pt_root_id")
    to_col_id = columns.index("post_pt_root_id")
    pil_col_id = columns.index("neuropil")
    syn_cnt_col_id = columns.index("syn_count")

    neuropils = sorted(REGIONS.keys())
    neuropil_syn_table_columns = (
        [
            "root_id",
            "input synapses",
            "input partners",
            "output synapses",
            "output partners",
        ]
        + [f"input synapses in {p}" for p in neuropils]
        + [f"input partners in {p}" for p in neuropils]
        + [f"output synapses in {p}" for p in neuropils]
        + [f"output partners in {p}" for p in neuropils]
    )

    def col_idx(flow, count_type, neuropil=None):
        if neuropil:
            return neuropil_syn_table_columns.index(
                f"{flow} {count_type} in {neuropil}"
            )
        else:
            return neuropil_syn_table_columns.index(f"{flow} {count_type}")

    for i, r in enumerate(filtered_syn_table_content):
        if i == 0:
            assert r == columns
        else:
            pil = r[pil_col_id]
            assert pil in REGIONS
            syn_cnt = r[syn_cnt_col_id]
            from_rid = r[from_col_id]
            to_rid = r[to_col_id]
            if from_rid not in rid_to_counts:
                rid_to_counts[from_rid] = [0] * len(neuropil_syn_table_columns)
                rid_to_counts[from_rid][0] = from_rid
            rid_to_counts[from_rid][
                col_idx(flow="output", count_type="synapses")
            ] += syn_cnt
            rid_to_counts[from_rid][
                col_idx(flow="output", count_type="synapses", neuropil=pil)
            ] += syn_cnt
            rid_to_counts[from_rid][
                col_idx(flow="output", count_type="partners", neuropil=pil)
            ] += 1
            rid_to_output_partners[from_rid].add(to_rid)

            if to_rid not in rid_to_counts:
                rid_to_counts[to_rid] = [0] * len(neuropil_syn_table_columns)
                rid_to_counts[to_rid][0] = to_rid
            rid_to_counts[to_rid][
                col_idx(flow="input", count_type="synapses")
            ] += syn_cnt
            rid_to_counts[to_rid][
                col_idx(flow="input", count_type="synapses", neuropil=pil)
            ] += syn_cnt
            rid_to_counts[to_rid][
                col_idx(flow="input", count_type="partners", neuropil=pil)
            ] += 1
            rid_to_input_partners[to_rid].add(from_rid)

    # update unique partner counts
    for rid, counts in rid_to_counts.items():
        counts[col_idx(flow="input", count_type="partners")] = len(
            rid_to_input_partners[rid]
        )
        counts[col_idx(flow="output", count_type="partners")] = len(
            rid_to_output_partners[rid]
        )

    res = [neuropil_syn_table_columns] + sorted(
        rid_to_counts.values(), key=lambda v: v[0]
    )
    assert len(res) == len(rid_to_counts) + 1
    assert all([len(r) == len(neuropil_syn_table_columns) for r in res])
    return res


def filter_connection_rows(syn_table_content, columns, min_syn_count, proofread_rids):
    filtered_rows = []
    pre_root_id = columns.index("pre_pt_root_id")
    post_root_id = columns.index("post_pt_root_id")
    pil_col_id = columns.index("neuropil")
    syn_cnt_col_id = columns.index("syn_count")
    invalid_row_counts = defaultdict(int)
    pair_syn_counts = defaultdict(int)

    # first pass: aggregate syn counts across neuropils for thresholding
    for i, r in enumerate(syn_table_content):
        if i == 0:
            assert r == columns
        else:
            pre_rid = r[pre_root_id]
            post_rid = r[post_root_id]
            syn_cnt = r[syn_cnt_col_id]
            pair_syn_counts[(pre_rid, post_rid)] += syn_cnt

    # second pass: filter out invalid rows / below threshold rows
    for i, r in enumerate(syn_table_content):
        if i == 0:
            filtered_rows.append(r)
        else:
            pre_rid = r[pre_root_id]
            post_rid = r[post_root_id]
            region = r[pil_col_id]
            if pre_rid not in proofread_rids:
                invalid_row_counts["pre_root_id is not in proofread set"] += 1
            elif post_rid not in proofread_rids:
                invalid_row_counts["post_root_id is not in proofread set"] += 1
            elif pair_syn_counts[(pre_rid, post_rid)] < min_syn_count:
                invalid_row_counts[
                    f"total syn count {pair_syn_counts[(pre_rid, post_rid)]}"
                ] += 1
            elif region not in REGIONS:
                invalid_row_counts[f"unknown region '{region}'"] += 1
            else:
                # all kosher
                filtered_rows.append(r)
    print(
        f"Filtered out {len(syn_table_content) - len(filtered_rows)} rows out of {len(syn_table_content)}. Reasons: {dict(invalid_row_counts)}"
    )
    return filtered_rows
