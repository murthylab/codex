from collections import defaultdict


def assign_names_from_annotations(neuron_data):
    token_to_cell_counts = defaultdict(int)
    cell_to_potential_names = defaultdict(list)

    for rid, nd in neuron_data.items():
        token_to_cell_counts[nd["group"]] += 1
        cell_to_potential_names[rid].append(nd["group"])

    assert len(cell_to_potential_names) == len(neuron_data)

    assigned_name_counts = defaultdict(int)

    # if there are multiple options, chose one deterministically
    def least_used_name(lst):
        least_used_count = min([token_to_cell_counts[tk] for tk in lst])
        return sorted(
            [tk for tk in lst if token_to_cell_counts[tk] == least_used_count]
        )[0]

    # assign running numbers by size (num partners), and to make deterministic secondary sort is by root id
    # if there are 2 neurons only with same base name on opposite hemispheres, assign L/R instead of numbers
    anno_base_name_to_neurons_list = defaultdict(list)
    for nd in sorted(
        neuron_data.values(),
        key=lambda x: -((x["input_cells"] + x["output_cells"]) * x["root_id"]),
    ):
        rid = nd["root_id"]
        base_name = least_used_name(cell_to_potential_names[rid])
        assigned_name_counts[base_name] += 1
        nd["name"] = f"{base_name}.{assigned_name_counts[base_name]}"
        if base_name != nd["group"]:
            anno_base_name_to_neurons_list[base_name].append(nd)

    def swap_id_with_side(nd):
        side_letter = nd["side"][0].upper()
        assert side_letter in ["L", "R"]
        name_parts = nd["name"].split(".")
        assert name_parts[-1].isnumeric()
        name_parts[-1] = side_letter
        nd["name"] = ".".join(name_parts)

    for nm, lst in anno_base_name_to_neurons_list.items():
        if len(lst) == 1:
            nd = lst[0]
            assert nd["name"].endswith(".1")
            nd["name"] = nd["name"][:-2]
        elif len(lst) == 2:
            s0, s1 = lst[0]["side"], lst[1]["side"]
            if s0 != s1 and s0 in ["left", "right"] and s1 in ["left", "right"]:
                swap_id_with_side(lst[0])
                swap_id_with_side(lst[1])
