from collections import defaultdict

from src.data.brain_regions import REGIONS
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES


def compile_nt_scores_data(syn_table_content):
    header = syn_table_content[0]
    rid_to_scores = {}
    from_col_id = header.index("pre_pt_root_id")
    syn_cnt_col_id = header.index("syn_count")
    nt_score_col_indices = {
        nt_type: header.index(f"{nt_type.lower()}_avg")
        for nt_type in NEURO_TRANSMITTER_NAMES
    }

    def isnan(val):
        return val != val

    for r in syn_table_content[1:]:
        syn_cnt = int(r[syn_cnt_col_id])
        from_rid = r[from_col_id]

        if from_rid not in rid_to_scores:
            rid_to_scores[from_rid] = defaultdict(int)
        for nt, i in nt_score_col_indices.items():
            if not isnan(syn_cnt) and not isnan(r[i]):
                rid_to_scores[from_rid][header[i]] += syn_cnt * r[i]

    def round_float(f):
        return float("{:0.2f}".format(f))

    def normalize(scores_dict):
        tot = sum(scores_dict.values())
        for k, v in scores_dict.items():
            scores_dict[k] = round_float(v / tot)

    for rid, scores in rid_to_scores.items():
        normalize(scores)

    return rid_to_scores


def infer_nt_type_and_score(scores):
    scores = sorted([(sc, k) for k, sc in scores.items()], reverse=True)
    if scores[0][0] > 0.2 and scores[0][0] > scores[1][0] + 0.1:
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
            if counts:
                return max([(kk, vv) for kk, vv in counts.items()], key=lambda p: p[1])[
                    0
                ]

        prom_in = max_pil(input_neuropill_counts.get(root_id)) or "NO_IN"
        prom_out = max_pil(output_neuropill_counts.get(root_id)) or "NO_OUT"
        return f"{prom_in}.{prom_out}"

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


def compile_neuron_rows(syn_table_content, min_syn_count):
    columns = syn_table_content[0]
    from_col_id = columns.index("pre_pt_root_id")
    to_col_id = columns.index("post_pt_root_id")
    pil_col_id = columns.index("neuropil")
    syn_cnt_col_id = columns.index("syn_count")

    all_neurons_set = set()
    connected_neurons_set = set()
    input_neuropill_counts = {}
    output_neuropill_counts = {}

    syn_threshold_row_count = 0
    missing_pil_count = 0
    for i, r in enumerate(syn_table_content[1:]):
        syn_cnt = int(r[syn_cnt_col_id])
        from_rid = r[from_col_id]
        to_rid = r[to_col_id]
        pil = r[pil_col_id]

        all_neurons_set.add(from_rid)
        all_neurons_set.add(to_rid)

        if syn_cnt >= min_syn_count:
            syn_threshold_row_count += 1
            connected_neurons_set.add(from_rid)
            connected_neurons_set.add(to_rid)
            if pil in REGIONS:
                if from_rid not in output_neuropill_counts:
                    output_neuropill_counts[from_rid] = defaultdict(int)
                output_neuropill_counts[from_rid][pil] += syn_cnt
                if to_rid not in input_neuropill_counts:
                    input_neuropill_counts[to_rid] = defaultdict(int)
                input_neuropill_counts[to_rid][pil] += syn_cnt
            else:
                missing_pil_count += 1

    print(
        f"Processed {syn_threshold_row_count} rows out of {len(syn_table_content) - 1}, "
        f"all neurons: {len(all_neurons_set)}, connected neurons: {len(connected_neurons_set)}, "
        f"missing pils: {missing_pil_count}"
    )

    # assign names and groups based on in/out neuropils
    names, groups = assign_names_and_groups(
        all_neurons_set, input_neuropill_counts, output_neuropill_counts
    )

    # compute nt type info
    rid_to_nt_scores = compile_nt_scores_data(syn_table_content=syn_table_content)
    rid_to_nt_type = {
        rid: infer_nt_type_and_score(scores) for rid, scores in rid_to_nt_scores.items()
    }
    print(
        f"Neurons without NT type: {len([v for v in rid_to_nt_type.values() if not v[1]])}"
    )

    neuron_rows = [
        ["root_id", "name", "group", "nt_type", "nt_type_score"]
        + [f"{nt_type.lower()}_avg" for nt_type in NEURO_TRANSMITTER_NAMES]
    ]
    for rid in sorted(all_neurons_set):
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
    print(f"Sample: {neuron_rows[0:50000:10000]}")

    # check that all rows have the right length
    for i, r in enumerate(neuron_rows):
        assert len(r) == len(neuron_rows[0])

    return neuron_rows


def compile_connection_rows(syn_table_content, columns, min_syn_count):
    connections = []
    from_col_id = columns.index("pre_pt_root_id")
    to_col_id = columns.index("post_pt_root_id")
    pil_col_id = columns.index("neuropil")
    syn_cnt_col_id = columns.index("syn_count")
    nt_score_col_indices = {
        nt_type: columns.index(f"{nt_type.lower()}_avg")
        for nt_type in NEURO_TRANSMITTER_NAMES
    }
    for i, r in enumerate(syn_table_content):
        if i == 0:
            assert r == columns
            connections.append(
                ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"]
            )
        else:
            syn_cnt = int(r[syn_cnt_col_id])
            if syn_cnt >= min_syn_count:
                nt_scores = [
                    (float(r[nt_score_col_indices[ntt]]), ntt)
                    for ntt in NEURO_TRANSMITTER_NAMES
                ]
                nt_type = max(nt_scores)[1]
                connections.append(
                    [r[from_col_id], r[to_col_id], r[pil_col_id], syn_cnt, nt_type]
                )
    return connections