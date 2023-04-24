from collections import defaultdict

from src.data.brain_regions import REGIONS, neuropil_hemisphere
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.formatting import display
from src.utils.graph_vis import make_graph_html


def compile_network_html(
    root_ids,
    contable,
    data_version,
    show_regions,
    reduce,
    connections_cap,
    hide_weights,
    log_request,
    layers=None,
    page_title="Network Graph",
):
    neuron_db = NeuronDataFactory.instance().get(version=data_version)
    if show_regions and layers is None:  # exclude unknown region connections
        connection_table = [list(r) for r in contable if r[2] in REGIONS]
    else:
        connection_table = contable
    if reduce:

        def node_projection(nd):
            if not nd["class"] or nd["class"].lower() in [
                "na",
                "undefined",
                "unspecified",
                "none",
            ]:
                return None
            res = display(f"{nd['class']}".replace(" neuron", ""))
            if nd["side"] and nd["side"].lower() not in [
                "na",
                "undefined",
                "unspecified",
                "none",
            ]:
                res += f"/{nd['side']}"
            return res

        projection_sets = defaultdict(set)
        projections = defaultdict(str)
        for rid, nd in neuron_db.neuron_data.items():
            proj = node_projection(nd)
            if proj:
                projection_sets[proj].add(rid)
                projections[rid] = proj
        projection_set_fractions = {
            k: round(100 * len(v) / len(neuron_db.neuron_data))
            for k, v in projection_sets.items()
        }
        projections = {
            rid: f"{proj} {projection_set_fractions[proj] or '<1'}%"
            for rid, proj in projections.items()
        }

        def pil_projection(pil):
            return neuropil_hemisphere(pil)

        def project_row(row):
            return [
                projections[row[0]],
                projections[row[1]],
                pil_projection(row[2]),
            ] + row[3:]

        connection_table = [
            project_row(r)
            for r in connection_table
            if r[0] in projections and r[1] in projections
        ]

        def name_getter(x):
            return f"Class {x}"

        def caption_getter(x):
            return x

        label_getter = None
        class_getter = None
        nt_type_getter = None

        def size_getter(x):
            return 1 + int(x.replace("<1", "0").replace("%", "").split()[-1])

        center_ids = list(
            set([r[0] for r in connection_table]).union(
                [r[1] for r in connection_table]
            )
        )
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
            return 1

        center_ids = root_ids

    return make_graph_html(
        connection_table=connection_table,
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
