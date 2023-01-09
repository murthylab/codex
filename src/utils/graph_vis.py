import math
from collections import defaultdict

from flask import render_template, url_for

from src.data.brain_regions import neuropil_description, lookup_neuropil_set
from src.utils.formatting import shorten_and_concat_labels

INPUT_NEUROPIL_COLOR = "#97c2fc"
OUTPUT_NEUROPIL_COLOR = "#fcc297"
NT_COLORS = {
    "ach": "#ff9999",
    "gaba": "#99ff99",
    "glut": "#9999ff",
    "oct": "#ffff99",
    "ser": "#ff99ff",
    "da": "#99ffff",
}
UNKNOWN_NT_COLOR = "#cccccc"
UNSPECIFIED_COLOR = "#fafafa"


def aggregate_and_cap(connection_table, connections_cap, group_regions):
    def row_key(row):
        if group_regions:
            return row[0], row[1], None
        else:
            return row[0], row[1], row[2]

    syn_counts = defaultdict(int)
    aggregated_syn_count = 0
    for r in connection_table:
        syn_counts[row_key(r)] += r[3]
        aggregated_syn_count += r[3]
    aggregated_con_count = len(syn_counts)

    connections_res = []
    non_self_loop_connections = 0
    for p in sorted(syn_counts.items(), key=lambda p: -p[1]):
        connections_res.append([p[0][0], p[0][1], p[0][2], p[1]])
        if p[0][0] != p[0][1]:
            non_self_loop_connections += 1
            if non_self_loop_connections == connections_cap:
                break

    return connections_res, aggregated_con_count, aggregated_syn_count


def format_number(n):
    return "{:,}".format(n)


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
    group_regions,
    show_edge_weights,
    show_warnings,
):
    """
    connection_table has 4 columns: pre root id, post root id, neuropil, syn count
    neuron_data_fetcher is a lambda that returns neuron metadata given it's id
    center_ids is the ids of the neurons that are being inspected
    """
    center_ids = center_ids or []
    connection_table, aggregated_con_count, aggregated_syn_count = aggregate_and_cap(
        connection_table=connection_table,
        connections_cap=connections_cap,
        group_regions=group_regions,
    )

    node_ids = set([r[0] for r in connection_table]).union(
        [r[1] for r in connection_table]
    )
    total_syn_count = sum([r[3] for r in connection_table])
    max_syn_count = max([r[3] for r in connection_table])
    large_weights = total_syn_count >= 50000

    if show_warnings:
        if aggregated_con_count > connections_cap:
            warning_msg = (
                f"Top {format_number(connections_cap)} connections out of {format_number(aggregated_con_count)} "
                f"({format_number(total_syn_count)} of {format_number(aggregated_syn_count)} syn.)"
            )
        else:
            warning_msg = f"{format_number(len(connection_table))} connections ({format_number(total_syn_count)} syn.)"
    else:
        warning_msg = None

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
        return None, None

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
        thumbnail_url = url_for("base.skeleton_thumbnail_url", root_id=nid)
        return (
            f'<a href="{cell_detail_url}" target="_parent">{name}</a> [{prefix}]<br><small>{nid}'
            f"</small><br><small>{class_and_annotations}</small><br>"
            f'<a href="{cell_detail_url}" target="_parent">'
            f'<img src="{thumbnail_url}" width="200px" height="150px;" border="0px;"></a>'
        )

    def neuropil_title(pil):
        nset = lookup_neuropil_set(pil)
        npil_explorer_url = url_for("app.neuropils", selected=",".join(nset))
        description = neuropil_description(nset.pop()) if len(nset) == 1 else pil
        return (
            f"Brain Region: {pil}<br><small>{description}</small>"
            f'<br><a href="{npil_explorer_url}" target="_blank">see in neuropil explorer</a> '
        )

    def edge_title(num):
        return f"{format_number(num)} synapses"

    def nt_color(nt_type):
        return NT_COLORS.get(nt_type.lower() if nt_type else None, UNKNOWN_NT_COLOR)

    def edge_label(weight):
        if large_weights:
            rk = round(weight / 1000)
            return format_number(rk) + "K" if rk > 0 else format_number(weight)
        else:
            return format_number(weight)

    def edge_width(weight):
        if large_weights:
            return 50 * weight / max_syn_count
        else:
            return len(str(weight))

    net = Network(show_edge_weights=show_edge_weights)

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
                    nt_type.upper() if nt_type else "Unspecified NT type",
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

    if group_regions:
        cell_to_cell_counts = defaultdict(int)
        cell_loop_counts = defaultdict(int)
        for r in connection_table:
            if r[0] != r[1]:
                cell_to_cell_counts[(r[0], r[1])] += r[3]
            else:
                cell_loop_counts[r[0]] += r[3]

        for k, v in cell_to_cell_counts.items():
            add_cell_node(k[0])
            add_cell_node(k[1])
            net.add_edge(
                source=k[0],
                target=k[1],
                width=edge_width(v),
                label=edge_label(v),
                title=edge_title(v),
            )
        if not show_edge_weights:
            net.add_legend(f"Top Cross Synapse Counts", "white")
            for k, v in sorted(cell_to_cell_counts.items(), key=lambda x: -x[1])[:5]:
                net.add_legend(f"- {edge_label(v)} from {k[0]} to {k[1]}", "white")

        if cell_loop_counts:
            net.add_legend(f"Top Internal Synapse Counts", "white")
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
            add_cell_node(k[0])
            pnid = add_pil_node(k[1], is_input=k[0] not in center_ids)
            net.add_edge(
                source=k[0],
                target=pnid,
                width=edge_width(v),
                label=edge_label(v),
                title=edge_title(v),
            )
        for k, v in pil_to_cell_counts.items():
            add_cell_node(k[1])
            pnid = add_pil_node(k[0], is_input=k[1] in center_ids)
            net.add_edge(
                source=pnid,
                target=k[1],
                width=edge_width(v),
                label=edge_label(v),
                title=edge_title(v),
            )

    return net.generate_html(warning_msg=warning_msg)


class Network(object):
    def __init__(self, show_edge_weights, edge_physics=True, node_physics=False):
        self.edges = []
        self.node_map = {}
        self.legend = []
        self.show_edge_weights = show_edge_weights
        self.edge_physics = edge_physics
        self.node_physics = node_physics
        self.cluster_data = {}
        self.active_edges = {}

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
            "arrows": "to",
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

    def generate_html(self, warning_msg):
        return render_template(
            "network_graph.html",
            nodes=list(self.node_map.values()),
            edges=self.edges,
            cluster_data=self.cluster_data,
            active_edges=self.active_edges,
            legend=self.legend,
            warning_msg=warning_msg,
        )
