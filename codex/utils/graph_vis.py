import math
from collections import defaultdict

from flask import url_for

from codex.blueprints.base import render_template

from codex.data.brain_regions import neuropil_description, lookup_neuropil_set
from codex.utils.formatting import shorten_and_concat_labels, display

INPUT_NEUROPIL_COLOR = "#97c2fc"
OUTPUT_NEUROPIL_COLOR = "#fcc297"
NT_COLORS = {
    "ach": "#95A3CE",
    "gaba": "#D5A848",
    "glut": "#86A859",
    "oct": "#725C98",
    "ser": "#8C6295",
    "da": "#B87969",
}

UNKNOWN_NT_COLOR = "#cccccc"
UNSPECIFIED_COLOR = "#fafafa"


def aggregate_and_cap(connection_table, connections_cap, show_regions):
    syn_counts = defaultdict(int)
    aggregated_syn_count = 0
    if show_regions:
        for r in connection_table:
            syn_counts[r[0], r[1], r[2]] += r[3]
            aggregated_syn_count += r[3]
    else:
        for r in connection_table:
            syn_counts[r[0], r[1]] += r[3]
            aggregated_syn_count += r[3]

    aggregated_con_count = len(syn_counts)

    connections_res = []
    non_self_loop_connections = 0
    for p in sorted(syn_counts.items(), key=lambda p: -p[1]):
        connections_res.append(
            [p[0][0], p[0][1], p[0][2] if show_regions else None, p[1]]
        )
        if p[0][0] != p[0][1]:
            non_self_loop_connections += 1
            if non_self_loop_connections == connections_cap:
                break

    return connections_res, aggregated_con_count, aggregated_syn_count


def make_graph_html(
    connection_table,
    center_ids,
    connections_cap,
    name_getter,
    caption_getter,
    label_getter,
    class_getter,
    nt_type_getter,
    size_getter,
    show_regions,
    show_edge_weights,
    show_warnings,
    page_title,
    layers=None,
):
    """
    connection_table has 4 columns: pre root id, post root id, neuropil, syn count
    neuron_data_fetcher is a lambda that returns neuron metadata given it's id
    center_ids is the ids of the neurons that are being inspected
    """
    center_ids = center_ids or []

    if layers is None:
        (
            connection_table,
            aggregated_con_count,
            aggregated_syn_count,
        ) = aggregate_and_cap(
            connection_table=connection_table,
            connections_cap=connections_cap,
            show_regions=show_regions,
        )
    else:
        aggregated_con_count, aggregated_syn_count = 0, 0

    node_ids = set([r[0] for r in connection_table]).union(
        [r[1] for r in connection_table]
    )
    # as long as connection cap not reached, add center ids back in
    for cid in center_ids:
        if len(node_ids) >= connections_cap:
            break
        node_ids.add(cid)

    total_syn_count = sum([r[3] for r in connection_table]) if connection_table else 0
    max_syn_count = max([r[3] for r in connection_table]) if connection_table else 0
    large_weights = total_syn_count >= 50000

    if layers is None and show_warnings:
        if aggregated_con_count > connections_cap:
            warning_msg = (
                f"Top {display(len(node_ids))} nodes and {display(connections_cap)} connections out of {display(aggregated_con_count)} "
                f"({display(total_syn_count)} of {display(aggregated_syn_count)} syn.)"
            )
        else:
            warning_msg = f"{display(len(node_ids))} nodes and {display(len(connection_table))} connections ({display(total_syn_count)} syn.)"
    else:
        warning_msg = None

    layer_heights = defaultdict(int)
    if layers is not None:
        for node in layers:
            layer_heights[layers[node][0]] += 1

    def node_size(nid):
        nsz = size_getter(nid)
        res = (10 if nid in center_ids else 5) * math.sqrt(math.sqrt(nsz))
        return round(res)

    def pil_size():
        return 5

    def node_mass(node_id):
        if node_id == "neuropil":
            return 5
        else:
            return 3 if node_id in center_ids else 1

    def node_shape(nid):
        return "ellipse" if nid in center_ids else "dot"

    def node_position(nid):
        if layers is None:
            return None, None

        layer, layer_pos = layers[int(nid)]
        layer_pos -= (layer_heights[layer] - 1) / 2
        width = 1600
        height = 900
        x = layer * width / len(layer_heights)
        y = layer_pos * height / layer_heights[layer]
        return x, y

    def node_color(nid):
        return nt_color(nt_type_getter(nid)) if nt_type_getter else UNSPECIFIED_COLOR

    def node_clusterable(node_id):
        return node_id in center_ids

    def node_label(nid):
        if nid in center_ids or len(node_ids) < 10:
            return caption_getter(nid)
        else:
            return " "

    def node_title(nid):
        name = name_getter(nid)
        if not label_getter or not class_getter:
            return name
        class_and_annotations = class_getter(nid)
        labels = label_getter(nid)
        if labels:
            labels_str = shorten_and_concat_labels(labels)
            class_and_annotations += f"<br>{labels_str}"

        prefix = "queried cell" if nid in center_ids else "connected cell"
        cell_detail_url = url_for("app.cell_details", root_id=nid)
        thumbnail_url = url_for("base.skeleton_thumbnail_url", cell_or_neuropil=nid)
        return (
            f'<a href="{cell_detail_url}" target="_parent">{name}</a> [{prefix}]<br><small>{nid}'
            f"</small><br><small>{class_and_annotations}</small><br>"
            f'<a href="{cell_detail_url}" target="_parent">'
            f'<img src="{thumbnail_url}" width="200px" height="150px;" border="0px;"></a>'
        )

    def neuropil_title(pil):
        nset = lookup_neuropil_set(pil)
        npil_explorer_url = url_for("app.neuropils", selected=",".join(nset))
        one_pil = nset.pop() if len(nset) == 1 else None
        description = neuropil_description(one_pil) if one_pil else pil
        thumbnail_url = (
            url_for("base.skeleton_thumbnail_url", cell_or_neuropil=one_pil)
            if one_pil
            else None
        )
        return (
            f"Brain Region: {pil}<br><small>{description}</small>"
            + (
                f'<br><img src="{thumbnail_url}" width="200px" height="150px;" border="0px;"></a>'
                if thumbnail_url
                else ""
            )
            + f'<br><a href="{npil_explorer_url}" target="_blank">see in neuropil explorer</a> '
        )

    def edge_title(num):
        return f"{display(num)} synapses"

    def nt_color(nt_type):
        return NT_COLORS.get(nt_type.lower() if nt_type else None, UNKNOWN_NT_COLOR)

    def edge_label(weight):
        if large_weights:
            rk = round(weight / 1000)
            return display(rk) + "K" if rk > 0 else display(weight)
        else:
            return display(weight)

    def edge_width(weight):
        if large_weights or layers is not None:
            return min(10, 50 * weight / (max_syn_count or 1))
        else:
            return len(str(weight))

    net = Network(
        show_edge_weights=show_edge_weights,
        layers=layers[center_ids[1]][0] + 1 if layers is not None else 0,
    )

    added_cell_nodes = set()

    def add_cell_node(nid):
        if nid not in added_cell_nodes:
            x, y = node_position(nid)
            net.add_node(
                name=nid,
                label=node_label(nid),
                title=node_title(nid),
                color=node_color(nid),
                shape=node_shape(nid),
                size=node_size(nid),
                mass=node_mass(nid),
                x=x,
                y=y,
                cluster_inputs=node_clusterable(nid),
                cluster_outputs=node_clusterable(nid),
            )
            added_cell_nodes.add(nid)
            if nt_type_getter:
                nt_type = nt_type_getter(nid)
                net.add_legend(
                    (nt_type.upper() if nt_type else "Unknown NT type"),
                    color=nt_color(nt_type),
                )

    added_pil_nodes = set()

    def add_pil_node(pil, is_input):
        node_name = f"{pil}_{'in' if is_input else 'out'}"
        if node_name not in added_pil_nodes:
            net.add_node(
                name=node_name,
                label=pil,
                title=neuropil_title(pil),
                shape="box",
                size=pil_size(),
                mass=node_mass("neuropil"),
                color=INPUT_NEUROPIL_COLOR if is_input else OUTPUT_NEUROPIL_COLOR,
                cluster_inputs=is_input,
                cluster_outputs=not is_input,
            )
            added_pil_nodes.add(node_name)
            net.add_legend("Input Neuropil", color=INPUT_NEUROPIL_COLOR)
            net.add_legend("Output Neuropil", color=OUTPUT_NEUROPIL_COLOR)
        return node_name

    for n in node_ids:
        add_cell_node(n)

    if layers is not None:
        for r in connection_table:
            net.add_edge(
                source=r[0],
                target=r[1],
                width=edge_width(r[3]),
                label=edge_label(r[3]),
                title=edge_title(r[3]),
            )
    elif not show_regions:
        cell_to_cell_counts = defaultdict(int)
        cell_loop_counts = defaultdict(int)
        for r in connection_table:
            if r[0] != r[1]:
                cell_to_cell_counts[(r[0], r[1])] += r[3]
            else:
                cell_loop_counts[r[0]] += r[3]

        for k, v in cell_to_cell_counts.items():
            net.add_edge(
                source=k[0],
                target=k[1],
                width=edge_width(v),
                label=edge_label(v),
                title=edge_title(v),
            )
        if not show_edge_weights:
            net.add_legend("Top Cross Synapse Counts", "white")
            for k, v in sorted(cell_to_cell_counts.items(), key=lambda x: -x[1])[:5]:
                net.add_legend(f"- {edge_label(v)} from {k[0]} to {k[1]}", "white")

        if cell_loop_counts:
            net.add_legend("Top Internal Synapse Counts", "white")
            for k, v in sorted(cell_loop_counts.items(), key=lambda x: -x[1])[:5]:
                net.add_legend(f"- {edge_label(v)} in {k}", "white")
    else:
        cell_to_pil_counts = defaultdict(int)
        pil_to_cell_counts = defaultdict(int)
        for r in connection_table:
            pil_name = r[2]
            cell_to_pil_counts[(r[0], pil_name)] += r[3]
            pil_to_cell_counts[(pil_name, r[1])] += r[3]

        for k, v in cell_to_pil_counts.items():
            pnid = add_pil_node(k[1], is_input=k[0] not in center_ids)
            net.add_edge(
                source=k[0],
                target=pnid,
                width=edge_width(v),
                label=edge_label(v),
                title=edge_title(v),
            )
        for k, v in pil_to_cell_counts.items():
            pnid = add_pil_node(k[0], is_input=k[1] in center_ids)
            net.add_edge(
                source=pnid,
                target=k[1],
                width=edge_width(v),
                label=edge_label(v),
                title=edge_title(v),
            )

    return net.generate_html(warning_msg=warning_msg, page_title=page_title)


class Network(object):
    def __init__(
        self, show_edge_weights, edge_physics=True, node_physics=True, layers=None
    ):
        self.edges = []
        self.node_map = {}
        self.legend = []
        self.show_edge_weights = show_edge_weights
        self.edge_physics = edge_physics
        self.node_physics = node_physics
        self.cluster_data = {}
        self.active_edges = {}
        self.layers = layers

    def add_node(
        self,
        name,
        size,
        mass,
        label,
        shape,
        color,
        title=None,
        x=None,
        y=None,
        level=None,
        cluster_inputs=False,
        cluster_outputs=False,
    ):
        name = str(name)
        if name not in self.node_map:
            node = {
                "id": name,
                "label": label or name,
                "shape": shape,
                "physics": self.node_physics,
                "size": size,
                "mass": mass,
                "color": color,
                "title": title,
                "font": f"{max(14, size)}px arial black",
            }
            if x is not None:
                node["x"] = x
                node["fixed.x"] = True
            if y is not None:
                node["y"] = y
                node["fixed.y"] = True
            if level is not None:
                node["level"] = level

            self.node_map[name] = node
            if cluster_inputs or cluster_outputs:
                self.cluster_data[name] = {
                    "edges": [],
                    "nodes": [],
                    "node_details": node,
                    "cluster_inputs": cluster_inputs,
                    "cluster_outputs": cluster_outputs,
                    "collapsed": False,
                }
            self.active_edges[name] = 0

    def add_edge(self, source, target, width, label, title):
        source = str(source)
        target = str(target)
        assert source in self.node_map, f"non existent node '{str(source)}'"
        assert target in self.node_map, f"non existent node '{str(target)}'"

        edge = {
            "id": source + "_to_" + target,
            "from": source,
            "to": target,
            "physics": self.edge_physics,
            "label": label if self.show_edge_weights else "",
            "title": title,
            "arrows": None if self.layers else "to",
            "arrowStrikethrough": True,
            "width": width,
            "dashes": False,
            "selfReference": {"size": 20},
        }
        self.edges.append(edge)

        if target in self.cluster_data:
            if self.cluster_data[target]["cluster_inputs"]:
                self.cluster_data[target]["edges"].append(edge)
                self.cluster_data[target]["nodes"].append(source)
        if source in self.cluster_data:
            if self.cluster_data[source]["cluster_outputs"]:
                self.cluster_data[source]["edges"].append(edge)
                self.cluster_data[source]["nodes"].append(target)
        self.active_edges[target] += 1
        self.active_edges[source] += 1

    def add_legend(self, label, color):
        legend_entry = {"label": label, "color": color}
        if legend_entry not in self.legend:
            self.legend.append(legend_entry)

    def generate_html(self, warning_msg, page_title):
        return render_template(
            "network_graph.html",
            nodes=list(self.node_map.values()),
            edges=self.edges,
            cluster_data=self.cluster_data,
            active_edges=self.active_edges,
            legend=self.legend,
            layers=self.layers,
            warning_msg=warning_msg,
            page_title=page_title,
        )
