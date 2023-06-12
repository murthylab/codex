from collections import defaultdict


def assign_names_from_annotations(neuron_data):
    assigned_set = set()
    token_to_cell_counts = defaultdict(int)
    cell_to_potential_names = defaultdict(list)
    case_deduped_tokens = {}
    lc_groups = set([nd["group"].lower() for nd in neuron_data.values()])

    def is_valid_token(t):
        if any([c in t for c in [" ", ".", ",", "?"]]):
            return False
        if any(
            [
                c in t.lower()
                for c in [
                    "ascending",
                    "descending",
                    "unclassified",
                    "clone",
                    "test",
                    "odd",
                    "putative",
                    "fbbt_",
                    "eye_",
                    "murthy",
                    "seung",
                ]
            ]
        ):
            return False
        if t.isalpha() and (t == t.lower() or t == t.capitalize()):
            return False
        if t.lower() in lc_groups:
            return False
        return True

    for rid, nd in neuron_data.items():
        cell_tokens = set()
        for t in nd["cell_type"] + nd["hemibrain_type"]:
            if is_valid_token(t):
                cell_tokens.add(t)
        for lb in nd["label"]:
            for part in lb.split(";"):
                part = part.strip()
                if is_valid_token(part):
                    cell_tokens.add(part)
        if cell_tokens:
            # if there are tokens differing only by case, default to one (the first occurance)
            cell_tokens = set(
                [case_deduped_tokens.setdefault(t.lower(), t) for t in cell_tokens]
            )
            assigned_set.add(rid)
        else:
            cell_tokens.add(nd["group"])

        for t in cell_tokens:
            token_to_cell_counts[t] += 1
            cell_to_potential_names[rid].append(t)

    print(f"{len(assigned_set)=}")
    assert len(cell_to_potential_names) == len(neuron_data)

    for t1 in list(token_to_cell_counts.keys()):
        for t2 in list(token_to_cell_counts.keys()):
            if t1 != t2 and t1.lower() == t2.lower():
                print(f"{t1} --> {t2}")
                assert False

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
