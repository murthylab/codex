from collections import defaultdict

from src.data.brain_regions import REGIONS, neuropil_hemisphere
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.graph_vis import make_graph_html


def compile_network_html(
    root_ids,
    contable,
    data_version,
    group_regions,
    reduce,
    connections_cap,
    hide_weights,
    log_request,
):
    neuron_db = NeuronDataFactory.instance().get(version=data_version)
    if not group_regions:  # exclude unknown region connections
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
            res = f"{nd['class']}".replace(" neuron", "").replace("_", " ")
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
        name_getter = lambda x: f"Class {x}"
        caption_getter = lambda x: x
        tag_getter = None
        class_getter = None
        nt_type_getter = None
        size_getter = lambda x: 1 + int(
            x.replace("<1", "0").replace("%", "").split()[-1]
        )
        center_ids = list(
            set([r[0] for r in connection_table]).union(
                [r[1] for r in connection_table]
            )
        )
    else:
        name_getter = lambda x: neuron_db.get_neuron_data(x)["name"]
        caption_getter = lambda x: neuron_db.get_neuron_caption(x)
        tag_getter = lambda x: neuron_db.get_neuron_data(x)["tag"]
        class_getter = lambda x: neuron_db.get_neuron_data(x)["class"]
        nt_type_getter = lambda x: neuron_db.get_neuron_data(x)["nt_type"]
        size_getter = lambda x: 1
        center_ids = root_ids

    network_html = make_graph_html(
        connection_table=connection_table,
        center_ids=center_ids,
        connections_cap=connections_cap,
        name_getter=name_getter,
        caption_getter=caption_getter,
        tag_getter=tag_getter,
        class_getter=class_getter,
        nt_type_getter=nt_type_getter,
        size_getter=size_getter,
        group_regions=group_regions,
        show_edge_weights=not hide_weights,
        show_warnings=log_request,
    )
