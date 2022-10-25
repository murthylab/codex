from collections import defaultdict
from flask import render_template

def make_graph_html(connection_table, neuron_data_fetcher, center_id=None):
    edge_physics = True
    node_physics = True

    def node_size(ndata):
        return 10

    def node_shape(ndata):
        if ndata['root_id'] == center_id:
            return 'circle'
        return 'dot'

    def node_color(ndata):
        return {
            'ach': '#aa0000',
            'gaba': '#00aa00',
            'glut': '#0000aa',
            'oct': '#aaaa00',
            'ser': '#aa00aa',
            'da': '#00aaaa'
        }.get(ndata['nt_type'].lower(), '#fafafa')

    def node_title(nd):
        rid = nd['root_id']
        return f"<a href=\"cell_details?root_id={rid}\">{rid}</a>"

    def edge_title(row):
        return f'{row[2]}'

    def edge_size(row):
        return pow(row[3], 1/2)

    net = Network()

    cell_to_pil_counts = defaultdict(int)
    pil_to_cell_counts = defaultdict(int)
    for r in connection_table:
        pil_name = r[2]
        if not pil_name or pil_name == 'None':
            pil_name = 'Neuropil NA'
        cell_to_pil_counts[(r[0], pil_name)] += r[3]
        pil_to_cell_counts[(pil_name, r[1])] += r[3]

    added_cell_nodes = set()

    def add_cell_node(nid):
        if nid not in added_cell_nodes:
            nd = neuron_data_fetcher(nid)
            net.add_node(
                nd['root_id'],
                label=f"{nd['name']}",
                title=node_title(nd),
                physics=node_physics,
                color=node_color(nd),
                shape=node_shape(nd),
                size=node_size(nd)
            )
            added_cell_nodes.add(k[0])
            net.add_legend(nd["nt_type"].upper(), color=node_color(nd))

    added_pil_nodes = set()

    def add_pil_node(pil, is_input):
        nid = f"{pil}_{'in' if is_input else 'out'}"
        if nid not in added_pil_nodes:
            net.add_node(
                nid,
                label=f"{pil} ({'in' if is_input else 'out'})",
                title=f"{'Inputs from' if is_input else 'Outputs to'} neuropil {pil}",
                physics=node_physics,
                shape='box',
                size=20
            )
            added_pil_nodes.add(nid)
            net.add_legend("Neuropil")
        return nid

    # add the most significant connections first
    max_nodes = 30
    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[:max_nodes]:
        add_cell_node(k[0])
        pnid = add_pil_node(k[1], is_input=k[0] != center_id)
        net.add_edge(k[0], pnid, value=v, physics=edge_physics)
    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[:max_nodes]:
        add_cell_node(k[1])
        pnid = add_pil_node(k[0], is_input=k[1] == center_id)
        net.add_edge(pnid, k[1], value=v, physics=edge_physics)

    # bundle any remaining connections (to prevent too large graphs)
    def add_super_cell_node():
        scid = 'other_cells'
        if scid not in added_cell_nodes:
            net.add_node(
                scid,
                label=f"Other Cells",
                physics=node_physics,
                color="#fafafa",
                shape='database',
                size=40
            )
            added_cell_nodes.add(scid)
        return scid

    def add_super_pil_node():
        spid = 'other_neuropils'
        if spid not in added_pil_nodes:
            net.add_node(
                spid,
                label=f"Other Neuropils",
                physics=node_physics,
                color='#fafafa',
                shape='database',
                size='40'
            )
            added_pil_nodes.add(spid)
        return spid

    # also apply limit on bundled nodes/edges (scaling issues)
    added_super_edge_pairs = set()

    def add_super_edge(f, t, v):
        if (f, t) not in added_super_edge_pairs:
            net.add_edge(f, t, value=v, physics=edge_physics)
            added_super_edge_pairs.add((f, t))

    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[max_nodes:2*max_nodes]:
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

    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[max_nodes:2*max_nodes]:
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

    return net.generate_html()

class Network(object):
    # based on https://pyvis.readthedocs.io/en/latest/_modules/pyvis/network.html
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.node_ids = []
        self.node_map = {}
        self.legend = {}

    def add_node(self, n_id, label=None, shape="dot", color="#97c2fc", **options):
        assert isinstance(n_id, str) or isinstance(n_id, int)
        if label:
            node_label = label
        else:
            node_label = n_id
        if n_id not in self.node_ids:
            if "group" in options:
                n = Node(n_id, shape, label=node_label, **options)
            else:
                n = Node(n_id, shape, label=node_label, color=color, **options)
            self.nodes.append(n.options)
            self.node_ids.append(n_id)
            self.node_map[n_id] = n.options

    def add_edge(self, source, to, **options):
        # verify nodes exist
        assert source in self.node_ids, \
            "non existent node '" + str(source) + "'"

        assert to in self.node_ids, \
            "non existent node '" + str(to) + "'"

        e = Edge(source, to, True, **options)
        self.edges.append(e.options)
    
    def add_legend(self, label, color="#97c2fc"):
        self.legend[label] = color

    def generate_html(self):
        return render_template("network_graph.html", nodes=self.nodes, edges=self.edges, legend=self.legend)

class Node(object):
    # based on https://github.com/WestHealth/pyvis/blob/master/pyvis/node.py
    def __init__(self, n_id, shape, label, font_color=False, **opts):
        self.options = opts
        self.options["id"] = n_id
        self.options["label"] = label
        self.options["shape"] = shape
        if font_color:
            self.options["font"] = dict(color=font_color)

class Edge(object):
    # based on https://github.com/WestHealth/pyvis/blob/master/pyvis/edge.py
    def __init__(self, source, dest, directed=False, **options):
        self.options = options
        self.options["from"] = source
        self.options["to"] = dest
        if directed:
            if "arrows" not in self.options:
                self.options["arrows"] = "to"
