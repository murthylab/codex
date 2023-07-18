from collections import defaultdict

from src.data.neuron_data_factory import NeuronDataFactory
from src.data.versions import DATA_SNAPSHOT_VERSIONS
from src.etl.utils import raw_data_file_path, comp_backup_and_update_csv


def collect_simple_connectivity_tags(neuron_db):
    ins, outs = neuron_db.input_output_partner_sets()
    rich_club = {
        rid
        for rid in neuron_db.neuron_data.keys()
        if len(ins[rid]) + len(outs[rid]) >= 37
    }
    broadcasters = {
        rid
        for rid in rich_club
        if neuron_db.neuron_data[rid]["flow"] == "intrinsic"
        and len(outs[rid]) >= 5 * len(ins[rid])
    }
    integrators = {
        rid
        for rid in rich_club
        if neuron_db.neuron_data[rid]["flow"] == "intrinsic"
        and len(ins[rid]) >= 5 * len(outs[rid])
    }
    reciprocals = {
        rid
        for rid in neuron_db.neuron_data.keys()
        if not ins[rid].isdisjoint(outs[rid])
    }
    return {
        "rich_club": rich_club,
        "broadcaster": broadcasters,
        "integrator": integrators,
        "reciprocal": reciprocals,
    }


def compute_connectivity_tags(neuron_db):
    ins, outs = neuron_db.input_output_partner_sets()
    rids = list(neuron_db.neuron_data.keys())

    feed_forward_nodes = set()
    feedback_loop_nodes = set()
    highly_reciprocal_nodes = set()
    nsrns = set()

    def is_regional_rich_club(rid_):
        if len(ins[rid_]) + len(outs[rid_]) < 37:
            return False  # not rich club
        con_rows = neuron_db.cell_connections(rid_)
        in_total_syn_count = 0
        out_total_syn_count = 0
        in_pil_syn_counts = defaultdict(int)
        out_pil_syn_counts = defaultdict(int)
        for row in con_rows:
            if row[0] == a:
                in_pil_syn_counts[row[2]] += row[3]
                in_total_syn_count += row[3]
            else:
                out_pil_syn_counts[row[2]] += row[3]
                out_total_syn_count += row[3]
        return (2 * max(in_pil_syn_counts.values()) > in_total_syn_count) and (
            2 * max(out_pil_syn_counts.values()) > out_total_syn_count
        )

    for a in rids:
        reciprocal_partners = outs[a].intersection(ins[a])
        if 2 * len(reciprocal_partners) > (
            len(outs[a]) + len(ins[a]) - 2 * len(reciprocal_partners)
        ):
            highly_reciprocal_nodes.add(a)

            nd = neuron_db.get_neuron_data(a)
            if nd["flow"] == "intrinsic" and is_regional_rich_club(a):
                nsrns.add(a)

        for b in outs[a]:
            if a in outs[b]:
                continue
            for c in outs[b].intersection(outs[a]):
                if b in outs[c] or c in ins[a]:
                    continue
                else:
                    assert 3 == len({a, b, c})
                    feed_forward_nodes |= {a, b, c}

            if a >= b:  # loops are symmetric
                continue
            for c in outs[b].intersection(ins[a]):
                if b in outs[c] or c in outs[a]:
                    continue
                else:
                    assert 3 == len({a, b, c})
                    feedback_loop_nodes |= {a, b, c}

    con_labels = collect_simple_connectivity_tags(neuron_db)
    con_labels["feedforward_loop_participant"] = feed_forward_nodes
    con_labels["3_cycle_participant"] = feedback_loop_nodes
    con_labels["highly_reciprocal_neuron"] = highly_reciprocal_nodes
    con_labels["nsrn"] = nsrns
    print(
        "Connectivity tag counts:\n" + str({k: len(v) for k, v in con_labels.items()})
    )
    con_tags_dict = defaultdict(list)
    for tag, rids in con_labels.items():
        for rid in rids:
            con_tags_dict[rid].append(tag)
    return con_tags_dict


if __name__ == "__main__":
    for version in DATA_SNAPSHOT_VERSIONS:
        print(f"Computing connectivity tags for version {version}...")
        rid_to_tags = compute_connectivity_tags(
            NeuronDataFactory.instance().get(version=version)
        )
        print(f"Computed for {len(rid_to_tags)} cells")

        con_tags_table = [["root_id", "connectivity_tag"]]
        for root_id, tags in rid_to_tags.items():
            con_tags_table.append([root_id, ",".join(sorted(tags))])
        fname = raw_data_file_path(
            version, filename=f"computed_connectivity_tags_v{version}.csv.gz"
        )
        print(f"Writing {len(con_tags_table)} rows to {fname}...")
        comp_backup_and_update_csv(fpath=fname, content=con_tags_table)
        print(f"Done generating connectivity tags for {version}")
