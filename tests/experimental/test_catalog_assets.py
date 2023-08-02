import json
from collections import defaultdict
from unittest import TestCase
import networkx as nx
import matplotlib.pyplot as plt

from src.configuration import TYPE_PREDICATES_METADATA
from src.data.brain_regions import REGIONS
from src.data.visual_neuron_types import (
    VISUAL_NEURON_TYPE_TO_MEGA_TYPE,
    VISUAL_NEURON_TYPES,
)
from src.utils.formatting import display
from src.utils.markers import extract_at_most_one_marker
from tests import get_testing_neuron_db


def region_color(region):
    return f"C{REGIONS[region][0]}"


def type_color(tp):
    return f"C{VISUAL_NEURON_TYPES.index(tp)}"


def to_percent(frac):
    return f"{round(frac * 100)}%"


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

        print(json.dumps(result, indent=2))
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
            node_color=[type_color(nn.replace(" ", "")) for nn in node_names],
            pos=positions,
            node_shape="o",
            node_size=[len(nn) ** 2 * 60 for nn in node_names],
            ax=subplot,
        )
        subplot.set_title(
            f"Connectivity Predicate [precision: {precision}, recall: {recall}]", y=-0.1
        )

    @staticmethod
    def add_barchart(subplot, title, ylabel, legend, data, colorizer):
        # first trim to top 10, then sort by key
        data = sorted(data, key=lambda x: -x[1])[:10]
        data = sorted(data, key=lambda x: x[0])
        bars = [d[0] for d in data]
        counts = [d[1] for d in data]
        bar_labels = [d[2] for d in data]
        bar_colors = [colorizer(bar) for bar in bars]

        subplot.bar(bars, counts, label=bar_labels, color=bar_colors)

        subplot.set_ylabel(ylabel)
        subplot.set_title(title)
        if legend:
            subplot.legend(title=legend)

    @staticmethod
    def add_table(subplot, title, subtitle, data_dict):
        # Data for the table
        data = [[k, display(v)] for k, v in data_dict.items()]

        # Set titles for the figure and the subplot respectively
        subplot.set_title(
            f"{title}\n\n{subtitle}", fontsize=18, fontweight="bold", color="purple"
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
        table.set_fontsize(16)

        # Adjust table layout
        table.scale(1, 2.5)

    def test_make_catalog_figures(self):
        meta_data = CatalogAssets.collect_data()
        types_by_size = sorted(
            meta_data.keys(), key=lambda x: -meta_data[x]["num_cells"]
        )
        for k in types_by_size:
            v = TYPE_PREDICATES_METADATA.get(k)
            if not v or v["f_score"] < 0.6:
                continue

            fig, ax = plt.subplots(nrows=2, ncols=3, figsize=(32, 20))

            CatalogAssets.add_network(
                subplot=ax[1][2],
                top_nodes=[f"  {nn}   " for nn in v["predicate_input_types"]],
                mid_nodes=[f"   {k}   "],
                bottom_nodes=[f"   {nn}  " for nn in v["predicate_output_types"]],
                precision=to_percent(v["precision"]),
                recall=to_percent(v["recall"]),
            )

            table_data_dict = {
                "Avg. in degree": meta_data[k]["avg_in_degree"],
                "Avg. out degree": meta_data[k]["avg_out_degree"],
                "Avg. in synapses": meta_data[k]["avg_in_synapses"],
                "Avg. out synapses": meta_data[k]["avg_out_synapses"],
                "Avg. cable length (nm)": meta_data[k]["avg_length_nm"],
                "Avg. surface area (nm^2)": meta_data[k]["avg_area_nm"],
                "Avg. volume (nm^3)": meta_data[k]["avg_volume_nm"],
            }
            CatalogAssets.add_table(
                subplot=ax[0][0],
                title=f"{k} ({VISUAL_NEURON_TYPE_TO_MEGA_TYPE[k]})",
                subtitle=f'{display(meta_data[k]["num_cells"])} cells',
                data_dict=table_data_dict,
            )
            CatalogAssets.add_barchart(
                subplot=ax[0][1],
                title="Input Brain Regions",
                ylabel="avg. num synapses",
                legend="Regions",
                data=[
                    (k, v, REGIONS[k][1])
                    for k, v in meta_data[k]["avg_in_synapses_by_region"].items()
                ],
                colorizer=region_color,
            )
            CatalogAssets.add_barchart(
                subplot=ax[0][2],
                title="Output Brain Regions",
                ylabel="avg. num synapses",
                legend="Regions",
                data=[
                    (k, v, REGIONS[k][1])
                    for k, v in meta_data[k]["avg_out_synapses_by_region"].items()
                ],
                colorizer=region_color,
            )
            CatalogAssets.add_barchart(
                subplot=ax[1][0],
                title="Upstream Partner Types",
                ylabel="avg. num cells",
                legend=None,
                data=[
                    (k, v, None)
                    for k, v in meta_data[k]["avg_in_partners_by_type"].items()
                ],
                colorizer=type_color,
            )
            CatalogAssets.add_barchart(
                subplot=ax[1][1],
                title="Downstream Partner Types",
                ylabel="avg. num cells",
                legend=None,
                data=[
                    (k, v, None)
                    for k, v in meta_data[k]["avg_out_partners_by_type"].items()
                ],
                colorizer=type_color,
            )

            plt.savefig(f"../../static/experimental_data/catalog_assets/fig_{k}.png")
            plt.close(fig)
