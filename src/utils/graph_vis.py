from collections import defaultdict

from flask import render_template, url_for

from src.data.brain_regions import neuropil_description

MAX_NODES = 30

NEUROPIL_COLOR = "#97c2fc"
NT_COLORS = {
    "ach": "#ff9999",
    "gaba": "#99ff99",
    "glut": "#9999ff",
    "oct": "#ffff99",
    "ser": "#ff99ff",
    "da": "#99ffff",
}
UNSPECIFIED_COLOR = "#fafafa"


def make_graph_html(connection_table, neuron_data_fetcher, center_ids=None):
    """
    connection_table has 4 columns: pre root id, post root id, neuropil, syn count
    neuron_data_fetcher is a lambda that returns neuron metadata given it's id
    center_ids is the ids of the neurons that are being inspected
    """
    center_ids = center_ids or []

    def node_size(ndata):
        return 20 if ndata["root_id"] in center_ids else 10

    def node_mass(node_id):
        if node_id == "neuropil":
            return 5
        elif node_id == "supernode":
            return 10
        else:
            return 200 if node_id in center_ids else 1

    def node_shape(ndata):
        return "elipse" if ndata["root_id"] in center_ids else "dot"

    def node_position(ndata):
        if ndata["root_id"] in center_ids:
            idx = center_ids.index(ndata["root_id"])
            return 0, 50 * idx
        return None, None

    def node_color(ndata):
        return nt_color(ndata["nt_type"])

    def node_title(nd):
        rid = nd["root_id"]
        name = nd["name"]
        class_and_annotations = nd["class"]
        if nd["annotations"]:
            class_and_annotations += f'<br>{nd["annotations"]}'

        prefix = "selected cell" if rid in center_ids else "connected cell"
        cell_detail_url = url_for("app.cell_details", root_id=rid)
        thumbnail_url = url_for("base.skeleton_thumbnail_url", root_id=rid)
        return (
            f'<a href="{cell_detail_url}" target="_parent">{name}</a><br>({prefix})<br><small>{rid}'
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
                label=f"{nd['name']}",
                title=node_title(nd),
                color=node_color(nd),
                shape=node_shape(nd),
                size=node_size(nd),
                mass=node_mass(nd["root_id"]),
                x=x,
                y=y,
            )
            added_cell_nodes.add(nid)
            net.add_legend(nd["nt_type"].upper(), color=nt_color(nd["nt_type"]))

    added_pil_nodes = set()

    def add_pil_node(pil, is_input):
        nid = f"{pil}_{'in' if is_input else 'out'}"
        if nid not in added_pil_nodes:
            title = f"Neuropil {pil}<br><small>{neuropil_description(pil)}</small>"
            net.add_node(
                name=nid,
                label=f"{pil} ({'in' if is_input else 'out'})",
                title=title,
                shape="box",
                size=20,
                mass=node_mass("neuropil"),
                color=NEUROPIL_COLOR,
            )
            added_pil_nodes.add(nid)
            net.add_legend("Neuropil", color=NEUROPIL_COLOR)
        return nid

    # add the most significant connections first
    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[:MAX_NODES]:
        add_cell_node(k[0])
        pnid = add_pil_node(k[1], is_input=k[0] not in center_ids)
        net.add_edge(
            source=k[0], target=pnid, value=v, label=str(v), title=edge_title(v)
        )
    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[:MAX_NODES]:
        add_cell_node(k[1])
        pnid = add_pil_node(k[0], is_input=k[1] in center_ids)
        net.add_edge(
            source=pnid, target=k[1], value=v, label=str(v), title=edge_title(v)
        )

    # bundle any remaining connections (to prevent too large graphs)
    def add_super_cell_node():
        scid = "other_cells"
        if scid not in added_cell_nodes:
            net.add_node(
                name=scid,
                label=f"Other Cells",
                color="#fafafa",
                shape="database",
                size=40,
                mass=node_mass("supernode"),
            )
            added_cell_nodes.add(scid)
        return scid

    def add_super_pil_node():
        spid = "other_neuropils"
        if spid not in added_pil_nodes:
            net.add_node(
                name=spid,
                label=f"Other Neuropils",
                color="#fafafa",
                shape="database",
                size="40",
                mass=node_mass("supernode"),
            )
            added_pil_nodes.add(spid)
        return spid

    # also apply limit on bundled nodes/edges (scaling issues)
    added_super_edge_pairs = set()

    def add_super_edge(f, t, v):
        if (f, t) not in added_super_edge_pairs:
            net.add_edge(source=f, target=t, value=v, label=str(v), title=edge_title(v))
            added_super_edge_pairs.add((f, t))

    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[
        MAX_NODES : 2 * MAX_NODES
    ]:
        if k[0] in added_cell_nodes:
            if k[1] in added_pil_nodes:
                add_super_edge(k[0], k[1], v)
            else:
                sp = add_super_pil_node()
                add_super_edge(k[0], sp, v)
        else:
            if k[1] in added_pil_nodes:
                sc = add_super_cell_node()
                add_super_edge(sc, k[1], v)
            else:
                sc = add_super_cell_node()
                sp = add_super_pil_node()
                add_super_edge(sc, sp, v)

    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[
        MAX_NODES : 2 * MAX_NODES
    ]:
        if k[1] in added_cell_nodes:
            if k[0] in added_pil_nodes:
                add_super_edge(k[0], k[1], v)
            else:
                sp = add_super_pil_node()
                add_super_edge(sp, k[1], v)
        else:
            if k[0] in added_pil_nodes:
                sc = add_super_cell_node()
                add_super_edge(k[0], sc, v)
            else:
                sc = add_super_cell_node()
                sp = add_super_pil_node()
                add_super_edge(sp, sc, v)

    if len(cell_to_pil_counts) > MAX_NODES:
        warning_msg = f"Showing top {MAX_NODES} cells out of {len(cell_to_pil_counts)}"
    else:
        warning_msg = None
    return net.generate_html(warning_msg=warning_msg)


class Network(object):
    def __init__(self, edge_physics=True, node_physics=False):
        self.edges = []
        self.node_map = {}
        self.legend = []
        self.edge_physics = edge_physics
        self.node_physics = node_physics

    def add_node(
        self, name, size, mass, label, shape, color, title=None, x=None, y=None
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

    def add_edge(self, source, target, value, label, title):
        source = str(source)
        target = str(target)
        assert source in self.node_map, f"non existent node '{str(source)}'"
        assert target in self.node_map, f"non existent node '{str(target)}'"

        self.edges.append(
            {
                "from": source,
                "to": target,
                "value": value,
                "physics": self.edge_physics,
                "label": label,
                "title": title,
                "arrows": "to",
            }
        )

    def add_legend(self, label, color):
        legend_entry = {"label": label, "color": color}
        if legend_entry not in self.legend:
            self.legend.append(legend_entry)

    def generate_html(self, warning_msg):
        return render_template(
            "network_graph.html",
            nodes=list(self.node_map.values()),
            edges=self.edges,
            legend=self.legend,
            warning_msg=warning_msg,
        )
