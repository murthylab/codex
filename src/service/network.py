from collections import defaultdict

from src.data.brain_regions import neuropil_hemisphere
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.formatting import display
from src.utils.graph_vis import make_graph_html


def compile_network_html(
    center_ids,
    contable,
    data_version,
    show_regions,
    connections_cap,
    hide_weights,
    log_request,
    group_by_attribute_name=None,
    split_groups_by_side=False,
    layers=None,
    page_title="Network Graph",
):
    neuron_db = NeuronDataFactory.instance().get(version=data_version)
    all_cell_ids = list(
        set([r[0] for r in contable]).union([r[1] for r in contable]).union(center_ids)
    )

    if group_by_attribute_name:

        def node_projection(ndata):
            if not ndata[group_by_attribute_name]:
                return f"Unassigned {display(group_by_attribute_name)}"
            res = display(ndata[group_by_attribute_name])
            if split_groups_by_side and ndata["side"]:
                res += f"/{ndata['side']}"
            return res

        projection_sets = defaultdict(set)
        projections = defaultdict(str)
        for rid in all_cell_ids:
            nd = neuron_db.get_neuron_data(rid)
            proj = node_projection(nd)
            projection_sets[proj].add(rid)
            projections[rid] = proj
        projection_set_sizes = {k: len(v) for k, v in projection_sets.items()}
        projection_set_fractions = {
            k: round(100 * v / len(all_cell_ids))
            for k, v in projection_set_sizes.items()
        }

        def project_row(row):
            return (
                projections[row[0]],
                projections[row[1]],
                neuropil_hemisphere(row[2]),
                row[3],
            )

        contable = [
            project_row(r)
            for r in contable
            if r[0] in projections and r[1] in projections
        ]

        def name_getter(x):
            return f"Queried nodes for which '{display(group_by_attribute_name)}' equals '{x}', {projection_set_sizes[x]} cells"

        def caption_getter(x):
            return f"{x} {projection_set_fractions[x] or '<1'}%"

        label_getter = None
        class_getter = None
        nt_type_getter = None

        def size_getter(x):
            return 1 + projection_set_fractions[x]

        center_ids = list(set([r[0] for r in contable]).union([r[1] for r in contable]))
    else:

        def name_getter(x):
            return neuron_db.get_neuron_data(x)["name"]

        def caption_getter(x):
            return neuron_db.get_neuron_data(x)["name"]

        def label_getter(x):
            return neuron_db.get_neuron_data(x)["label"]

        def class_getter(x):
            return neuron_db.get_neuron_data(x)["class"]

        def nt_type_getter(x):
            return neuron_db.get_neuron_data(x)["nt_type"]

        def size_getter(x):
            if x in center_ids:
                return max(1, 20 // len(center_ids))
            else:
                return 1

    return make_graph_html(
        connection_table=contable,
        center_ids=center_ids,
        connections_cap=connections_cap,
        name_getter=name_getter,
        caption_getter=caption_getter,
        label_getter=label_getter,
        class_getter=class_getter,
        nt_type_getter=nt_type_getter,
        size_getter=size_getter,
        show_regions=show_regions,
        show_edge_weights=not hide_weights,
        show_warnings=log_request,
        page_title=page_title,
        layers=layers,
    )
