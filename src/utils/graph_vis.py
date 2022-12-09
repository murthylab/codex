from collections import defaultdict

from flask import render_template, url_for

from src.data.brain_regions import neuropil_description, REGIONS
from src.utils.formatting import shorten_and_concat_labels, truncate

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
UNSPECIFIED_COLOR = "#fafafa"


def cap(connection_table, center_ids, nodes_limit):
    node_to_syn_count = {n: 0 for n in center_ids}
    for r in connection_table:
        if r[0] in node_to_syn_count:
            node_to_syn_count[r[0]] += r[3]
        if r[1] in node_to_syn_count:
            node_to_syn_count[r[1]] += r[3]
    center_ids = [
        t[0]
        for t in sorted(node_to_syn_count.items(), key=lambda p: -p[1])[:nodes_limit]
    ]
    connection_table = [
        r for r in connection_table if (r[0] in center_ids or r[1] in center_ids)
    ]
    return connection_table, center_ids


def make_graph_html(connection_table, neuron_data_fetcher, center_ids, nodes_limit):
    """
    connection_table has 4 columns: pre root id, post root id, neuropil, syn count
    neuron_data_fetcher is a lambda that returns neuron metadata given it's id
    center_ids is the ids of the neurons that are being inspected
    """
    center_ids = center_ids or []
    connection_table = [
        r for r in connection_table if r[2] in REGIONS
    ]  # exclude unknown region connections

    if len(center_ids) > nodes_limit:
        warning_msg = f"Top {nodes_limit} cells out of {len(center_ids)}"
        connection_table, center_ids = cap(
            connection_table=connection_table,
            center_ids=center_ids,
            nodes_limit=nodes_limit,
        )
    else:
        warning_msg = None

    def node_size(ndata):
        return 10 if ndata["root_id"] in center_ids else 5

    def pil_size():
        return 5

    def node_mass(node_id):
        if node_id == "neuropil":
            return 5
        else:
            return 3 if node_id in center_ids else 1

    def node_shape(ndata):
        return "ellipse" if ndata["root_id"] in center_ids else "dot"

    def node_position(ndata):
        return None, None

    def node_color(ndata):
        return nt_color(ndata["nt_type"])

    def node_clusterable(node_id):
        return node_id in center_ids

    def node_label(nd):
        if nd["root_id"] in center_ids or nodes_limit < 10:
            labels = sorted(nd["tag"], key=lambda x: len(x))
            lbl = labels[0] if labels else nd["name"]
            return truncate(lbl, 15)
        else:
            return " "

    def node_title(nd):
        rid = nd["root_id"]
        name = nd["name"]
        class_and_annotations = nd["class"]
        if nd["tag"]:
            tags_str = shorten_and_concat_labels(nd["tag"])
            class_and_annotations += f"<br>{tags_str}"

        prefix = "queried cell" if rid in center_ids else "connected cell"
        cell_detail_url = url_for("app.cell_details", root_id=rid)
        thumbnail_url = url_for("base.skeleton_thumbnail_url", root_id=rid)
        return (
            f'<a href="{cell_detail_url}" target="_parent">{name}</a> [{prefix}]<br><small>{rid}'
            f"</small><br><small>{class_and_annotations}</small><br>"
            f'<a href="{cell_detail_url}" target="_parent">'
            f'<img src="{thumbnail_url}" width="200px" height="150px;" border="0px;"></a>'
        )

    def edge_title(num):
        return f"{num} synapses"

    def nt_color(nt_type):
        return NT_COLORS.get(nt_type.lower(), UNSPECIFIED_COLOR)

    net = Network()

    cell_to_pil_counts = defaultdict(int)
    pil_to_cell_counts = defaultdict(int)
    for r in connection_table:
        pil_name = r[2]
        if not pil_name or pil_name == "None":
            pil_name = "Neuropil NA"
        cell_to_pil_counts[(r[0], pil_name)] += r[3]
        pil_to_cell_counts[(pil_name, r[1])] += r[3]

    added_cell_nodes = set()

    def add_cell_node(nid):
        if nid not in added_cell_nodes:
            nd = neuron_data_fetcher(nid)
            x, y = node_position(nd)
            net.add_node(
                name=nd["root_id"],
                label=node_label(nd),
                title=node_title(nd),
                color=node_color(nd),
                shape=node_shape(nd),
                size=node_size(nd),
                mass=node_mass(nd["root_id"]),
                x=x,
                y=y,
                cluster_inputs=node_clusterable(nd["root_id"]),
                cluster_outputs=node_clusterable(nd["root_id"]),
            )
            added_cell_nodes.add(nid)
            net.add_legend(nd["nt_type"].upper(), color=nt_color(nd["nt_type"]))

    added_pil_nodes = set()

    def add_pil_node(pil, is_input):
        node_name = f"{pil}_{'in' if is_input else 'out'}"
        if node_name not in added_pil_nodes:
            title = f"Neuropil {pil}<br><small>{neuropil_description(pil)}</small>"
            net.add_node(
                name=node_name,
                label=pil,
                title=title,
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

    # add the most significant
    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[
        : 2 * nodes_limit
    ]:
        add_cell_node(k[0])
        pnid = add_pil_node(k[1], is_input=k[0] not in center_ids)
        net.add_edge(
            source=k[0],
            target=pnid,
            weak=k[0] not in center_ids,
            label=str(v),
            title=edge_title(v),
        )
    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[
        : 2 * nodes_limit
    ]:
        add_cell_node(k[1])
        pnid = add_pil_node(k[0], is_input=k[1] in center_ids)
        net.add_edge(
            source=pnid,
            target=k[1],
            weak=k[1] not in center_ids,
            label=str(v),
            title=edge_title(v),
        )

    return net.generate_html(warning_msg=warning_msg)


class Network(object):
    def __init__(self, edge_physics=True, node_physics=False):
        self.edges = []
        self.node_map = {}
        self.legend = []
        self.edge_physics = edge_physics
        self.node_physics = node_physics
        self.cluster_data = {}
        self.active_edges = {}

    def add_node(
        self, name, size, mass, label, shape, color, title=None, x=None, y=None, cluster_inputs=False, cluster_outputs=False
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

    def add_edge(self, source, target, weak, label, title):
        source = str(source)
        target = str(target)
        assert source in self.node_map, f"non existent node '{str(source)}'"
        assert target in self.node_map, f"non existent node '{str(target)}'"

        edge = {
                "id": source + "_to_" + target,
                "from": source,
                "to": target,
                "physics": self.edge_physics,
                "label": label,
                "title": title,
                "arrows": "to",
                "width": 1 if weak else 2,
                "dashes": False,
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
