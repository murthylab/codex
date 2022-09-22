from collections import defaultdict

from pyvis.network import Network

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
        return f"<a href=\"neuron_info?root_id={rid}\" target=\"_blank\">{rid}</a>"

    def edge_title(row):
        return f'{row[2]}'

    def edge_size(row):
        return pow(row[3], 1/2)

    net = Network(height='100%', width='100%', directed=True)
    #net.force_atlas_2based()

    cell_to_pil_counts = defaultdict(int)
    pil_to_cell_counts = defaultdict(int)
    for r in connection_table:
        cell_to_pil_counts[(r[0], r[2])] += r[3]
        pil_to_cell_counts[(r[2], r[1])] += r[3]

    added_cell_nodes = set()

    def add_cell_node(nid):
        if nid not in added_cell_nodes:
            nd = neuron_data_fetcher(nid)
            net.add_node(
                nd['root_id'],
                label=f"{nd['kind']}",
                title=node_title(nd),
                physics=node_physics,
                color=node_color(nd),
                shape=node_shape(nd),
                size=node_size(nd)
            )
            added_cell_nodes.add(k[0])

    added_pil_nodes = set()

    def add_pil_node(pil):
        if pil not in added_pil_nodes:
            net.add_node(
                pil,
                label=f"{pil}",
                title=f"Neuropil {pil}",
                physics=node_physics,
                shape='box',
                size=20
            )
            added_pil_nodes.add(pil)

    # add the most significant connections first
    max_nodes = 50
    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[:max_nodes]:
        add_cell_node(k[0])
        add_pil_node(k[1])
        net.add_edge(k[0], k[1], value=v, physics=edge_physics)
    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[:max_nodes]:
        add_cell_node(k[1])
        add_pil_node(k[0])
        net.add_edge(k[0], k[1], value=v, physics=edge_physics)

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
    for k, v in sorted(cell_to_pil_counts.items(), key=lambda x: -x[1])[max_nodes:2*max_nodes]:
        if k[0] in added_cell_nodes:
            if k[1] in added_pil_nodes:
                net.add_edge(k[0], k[1], value=v, physics=edge_physics)
            else:
                sp = add_super_pil_node()
                net.add_edge(k[0], sp, value=v, physics=edge_physics)
        else:
            if k[1] in added_pil_nodes:
                sc = add_super_cell_node()
                net.add_edge(sc, k[1], value=v, physics=edge_physics)
            else:
                sc = add_super_cell_node()
                sp = add_super_pil_node()
                net.add_edge(sc, sp, value=v, physics=edge_physics)

    for k, v in sorted(pil_to_cell_counts.items(), key=lambda x: -x[1])[max_nodes:2*max_nodes]:
        if k[1] in added_cell_nodes:
            if k[0] in added_pil_nodes:
                net.add_edge(k[0], k[1], value=v, physics=edge_physics)
            else:
                sp = add_super_pil_node()
                net.add_edge(sp, k[1], value=v, physics=edge_physics)
        else:
            if k[0] in added_pil_nodes:
                sc = add_super_cell_node()
                net.add_edge(k[0], sc, value=v, physics=edge_physics)
            else:
                sc = add_super_cell_node()
                sp = add_super_pil_node()
                net.add_edge(sp, sc, value=v, physics=edge_physics)

    return net.generate_html()
