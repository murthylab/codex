from collections import defaultdict
from unittest import TestCase
import networkx as nx
import matplotlib.pyplot as plt

from src.configuration import TYPE_PREDICATES_METADATA
from src.data.visual_neuron_types import (
    VISUAL_NEURON_TYPE_TO_MEGA_TYPE,
    VISUAL_NEURON_MEGA_TYPE_TO_TYPES,
)
from src.utils.formatting import display
from src.utils.markers import extract_at_most_one_marker
from tests import get_testing_neuron_db

OLR_REGIONS = {
    "LA_R": "Lamina",
    "ME_R": "Medulla",
    "AME_R": "Acc. Medulla",
    "LO_R": "Lobula",
    "LOP_R": "Lobula Plate",
}

MEGA_TYPES = sorted(VISUAL_NEURON_MEGA_TYPE_TO_TYPES.keys())
types_cm = plt.get_cmap("tab20")
TYPE_COLORS = [types_cm(1.0 * i / len(MEGA_TYPES)) for i in range(len(MEGA_TYPES))]

OLR_REGIONS_KEYS = list(OLR_REGIONS.keys())
regions_cm = plt.get_cmap("Dark2")
REGION_COLORS = [
    regions_cm(1.0 * i / len(OLR_REGIONS_KEYS)) for i in range(len(OLR_REGIONS_KEYS))
]


def region_color(region):
    idx = OLR_REGIONS_KEYS.index(region)
    assert idx >= 0
    return REGION_COLORS[idx]


def type_color(tp):
    mtype = VISUAL_NEURON_TYPE_TO_MEGA_TYPE[tp]
    idx = MEGA_TYPES.index(mtype)
    return TYPE_COLORS[idx]


def to_percent(frac):
    return f"{round(frac * 100)}%"


def plot_file_name(plot_index, name):
    return f"../../static/experimental_data/ol_catalog_assets/{plot_index}_fig_{name.replace(' ', '')}.png"


class CatalogAssets(TestCase):
    @staticmethod
    def collect_data():
        neuron_db = get_testing_neuron_db()
        rid_to_ol_type = {}
        ol_type_to_list = defaultdict(list)
        for rid, nd in neuron_db.neuron_data.items():
            mrk = extract_at_most_one_marker(nd, "olr_type")
            if mrk and "unknown" not in mrk.lower():
                rid_to_ol_type[rid] = mrk
                ol_type_to_list[mrk].append(rid)

        ol_type_to_pil_inputs = defaultdict(lambda: defaultdict(int))
        ol_type_to_pil_outputs = defaultdict(lambda: defaultdict(int))

        ol_type_to_type_inputs = defaultdict(lambda: defaultdict(int))
        ol_type_to_type_outputs = defaultdict(lambda: defaultdict(int))

        for r in neuron_db.connections_.all_rows():
            tp = rid_to_ol_type.get(r[0])
            if tp:
                if r[2] != "UNASGD":
                    ol_type_to_pil_outputs[tp][r[2]] += r[3]
                tp_other = rid_to_ol_type.get(r[1])
                if tp_other:
                    ol_type_to_type_outputs[tp][tp_other] += 1
            tp = rid_to_ol_type.get(r[1])
            if tp:
                if r[2] != "UNASGD":
                    ol_type_to_pil_inputs[tp][r[2]] += r[3]
                tp_other = rid_to_ol_type.get(r[0])
                if tp_other:
                    ol_type_to_type_inputs[tp][tp_other] += 1

        def avg_counts(dct, num_cells, rounded):
            res = {
                k: (round(v / num_cells) if rounded else v / num_cells)
                for k, v in dct.items()
            }
            return {k: v for k, v in res.items() if v}

        result = {}

        ins, outs = neuron_db.input_output_partners_with_synapse_counts()
        for tp, rids in ol_type_to_list.items():
            avg_in_degree = round(sum([len(ins[rid]) for rid in rids]) / len(rids))
            avg_out_degree = round(sum([len(outs[rid]) for rid in rids]) / len(rids))
            avg_in_synapses = round(
                sum([sum(ins[rid].values()) for rid in rids]) / len(rids)
            )
            avg_out_synapses = round(
                sum([sum(outs[rid].values()) for rid in rids]) / len(rids)
            )

            result[tp] = {
                "num_cells": len(rids),
                "avg_length_nm": round(
                    sum([neuron_db.neuron_data[rid]["length_nm"] for rid in rids])
                    / len(rids)
                ),
                "avg_area_nm": round(
                    sum([neuron_db.neuron_data[rid]["area_nm"] for rid in rids])
                    / len(rids)
                ),
                "avg_volume_nm": round(
                    sum([neuron_db.neuron_data[rid]["size_nm"] for rid in rids])
                    / len(rids)
                ),
                "avg_in_degree": avg_in_degree,
                "avg_out_degree": avg_out_degree,
                "avg_in_synapses": avg_in_synapses,
                "avg_out_synapses": avg_out_synapses,
                "avg_in_synapses_by_region": avg_counts(
                    ol_type_to_pil_inputs[tp], len(rids), rounded=True
                ),
                "avg_out_synapses_by_region": avg_counts(
                    ol_type_to_pil_outputs[tp], len(rids), rounded=True
                ),
                "avg_in_partners_by_type": avg_counts(
                    ol_type_to_type_inputs[tp], len(rids), rounded=False
                ),
                "avg_out_partners_by_type": avg_counts(
                    ol_type_to_type_outputs[tp], len(rids), rounded=False
                ),
            }

        # print(json.dumps(result, indent=2))
        return result

    @staticmethod
    def add_network(subplot, top_nodes, mid_nodes, bottom_nodes, precision, recall):
        graph = nx.DiGraph()
        node_names = []
        for n in top_nodes + mid_nodes + bottom_nodes:
            graph.add_node(n)
            node_names.append(n)
        for n1 in top_nodes:
            for n2 in mid_nodes:
                graph.add_edge(n1, n2)
        for n1 in mid_nodes:
            for n2 in bottom_nodes:
                graph.add_edge(n1, n2)

        positions = {}

        def calc_node_positions(nodes, layer):
            space = round(100 / max(len(nodes), 1))
            for i, n in enumerate(nodes):
                positions[n] = (round((i + 1 / 2) * space), layer)

        calc_node_positions(top_nodes, 2)
        calc_node_positions(mid_nodes, 1)
        calc_node_positions(bottom_nodes, 0)

        nx.draw(
            graph,
            with_labels=True,
            font_size=18,
            font_weight="bold",
            pos=positions,
            node_shape="",
            # node_color=[type_color(nn.replace(" ", "")) for nn in node_names],
            node_size=[len(nn) ** 2 * 100 for nn in node_names],
            ax=subplot,
        )
        subplot.set_title(
            f"Connectivity Predicate [precision: {precision}, recall: {recall}]",
            fontsize=24,
        )

    @staticmethod
    def add_barchart(subplot, title, ylabel, data, colorizer, sort_by_key):
        # first trim to top 10, then sort by key
        data = sorted(data, key=lambda x: -x[1])[:6]
        if sort_by_key:
            data = sorted(data, key=lambda x: x[0])
        bars = [d[2] for d in data]
        counts = [d[1] for d in data]
        bar_labels = [d[0] for d in data]
        bar_colors = [colorizer(bar) for bar in bar_labels]

        subplot.bar(bars, counts, label=bar_labels, color=bar_colors)

        subplot.set_ylabel(ylabel, fontsize=18)
        subplot.set_title(title, fontsize=24)
        subplot.tick_params(axis="x", labelrotation=75, labelsize=16)
        subplot.tick_params(axis="y", labelsize=16)

    @staticmethod
    def add_table(subplot, title, subtitle, data_dict):
        # Data for the table
        data = [[k, display(v)] for k, v in data_dict.items()]

        # Set titles for the figure and the subplot respectively
        subplot.set_title(
            f"{title}\n{subtitle}", fontsize=28, fontweight="bold", color="purple"
        )

        # Hide axes
        subplot.axis("off")

        # Plot the table
        table = subplot.table(
            cellText=data,
            colLabels=None,
            cellLoc="left",
            loc="center",
            edges="open",
        )

        # adjust 2nd col to the right
        for key, cell in table._cells.items():
            cell.PAD = 0.03  # Adjust padding to move text to the right for the second column (optional)
            if key[1] == 1:  # Align the text in the second column to the right
                cell._text.set_horizontalalignment("right")

        # Customize the table
        table.auto_set_font_size(False)
        table.set_fontsize(26)

        # Adjust table layout
        table.scale(1, 2.5)

    def test_make_catalog_figures(self):
        meta_data = CatalogAssets.collect_data()
        types_by_name = sorted(meta_data.keys())
        last_mega_type = None
        plot_idx = 0
        for k in types_by_name:
            v = TYPE_PREDICATES_METADATA.get(k)
            if not v or v["f_score"] < 0.6:
                continue

            plot_idx += 1

            if VISUAL_NEURON_TYPE_TO_MEGA_TYPE[k] != last_mega_type:
                last_mega_type = VISUAL_NEURON_TYPE_TO_MEGA_TYPE[k]
                fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(32, 20))
                CatalogAssets.add_table(
                    subplot=ax[0][0],
                    title=last_mega_type,
                    subtitle="",
                    data_dict={
                        "Types": len(VISUAL_NEURON_MEGA_TYPE_TO_TYPES[last_mega_type]),
                        "Cells": "TODO",
                    },
                )
                plt.savefig(plot_file_name(plot_index=plot_idx, name=last_mega_type))
                plt.close(fig)
                plot_idx += 1

            fig, ax = plt.subplots(nrows=2, ncols=3, figsize=(32, 20))
            plt.subplots_adjust(wspace=0.5, hspace=0.5)

            CatalogAssets.add_network(
                subplot=ax[1][0],
                top_nodes=[f"  {nn}   " for nn in v["predicate_input_types"]],
                mid_nodes=[f"   {k}   "],
                bottom_nodes=[f"   {nn}  " for nn in v["predicate_output_types"]],
                precision=to_percent(v["precision"]),
                recall=to_percent(v["recall"]),
            )

            table_data_dict = {
                f'{display(meta_data[k]["num_cells"])} CELLS': "",
                "": "",
                "AVG. STATS": "",
                " in degree": meta_data[k]["avg_in_degree"],
                " out degree": meta_data[k]["avg_out_degree"],
                " in synapses": meta_data[k]["avg_in_synapses"],
                " out synapses": meta_data[k]["avg_out_synapses"],
                " cable len (µm)": meta_data[k]["avg_length_nm"] // 1000,
                " surface (µm^2)": meta_data[k]["avg_area_nm"] // 1000000,
                " volume (µm^3)": meta_data[k]["avg_volume_nm"] // 1000000000,
            }
            CatalogAssets.add_table(
                subplot=ax[0][0],
                title=k,
                subtitle=VISUAL_NEURON_TYPE_TO_MEGA_TYPE[k],
                data_dict=table_data_dict,
            )
            CatalogAssets.add_barchart(
                subplot=ax[0][1],
                title="Input Brain Regions",
                ylabel="avg. num synapses",
                data=[
                    (
                        rgn,
                        meta_data[k]["avg_in_synapses_by_region"].get(rgn, 0),
                        rgn_name,
                    )
                    for rgn, rgn_name in OLR_REGIONS.items()
                ],
                colorizer=region_color,
                sort_by_key=True,
            )
            CatalogAssets.add_barchart(
                subplot=ax[0][2],
                title="Output Brain Regions",
                ylabel="avg. num synapses",
                data=[
                    (
                        rgn,
                        meta_data[k]["avg_out_synapses_by_region"].get(rgn, 0),
                        rgn_name,
                    )
                    for rgn, rgn_name in OLR_REGIONS.items()
                ],
                colorizer=region_color,
                sort_by_key=True,
            )
            CatalogAssets.add_barchart(
                subplot=ax[1][1],
                title="Upstream Partner Types",
                ylabel="avg. num cells",
                data=[
                    (kk, vv, kk)
                    for kk, vv in meta_data[k]["avg_in_partners_by_type"].items()
                ],
                colorizer=type_color,
                sort_by_key=False,
            )
            CatalogAssets.add_barchart(
                subplot=ax[1][2],
                title="Downstream Partner Types",
                ylabel="avg. num cells",
                data=[
                    (kk, vv, kk)
                    for kk, vv in meta_data[k]["avg_out_partners_by_type"].items()
                ],
                colorizer=type_color,
                sort_by_key=False,
            )
            plt.savefig(plot_file_name(plot_index=plot_idx, name=k))
            plt.close(fig)
