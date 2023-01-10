from collections import defaultdict
from functools import lru_cache

from flask import url_for

from src.data.brain_regions import neuropil_hemisphere, NEUROPIL_DESCRIPTIONS
from src.data.neurotransmitters import lookup_nt_type_name, NEURO_TRANSMITTER_NAMES
from src.data.structured_search_filters import OP_UPSTREAM, OP_DOWNSTREAM, OP_SIMILAR
from src.utils import nglui
from src.utils import stats as stats_utils
from src.utils.formatting import concat_labels, nanometer_to_flywire_coordinates
from src.utils.graph_algos import reachable_node_counts


@lru_cache
def cached_cell_details(
    cell_names_or_id, root_id, neuron_db, data_version, min_syn_cnt, reachability_stats
):
    nd = neuron_db.get_neuron_data(root_id=root_id)
    labels_data = neuron_db.get_label_data(root_id=root_id)
    labels = sorted(set([ld["label"] for ld in labels_data or []]))
    unames = sorted(
        set(
            [
                f'<small>{ld["user_name"]}, {ld["user_affiliation"]}</small>'
                for ld in labels_data or []
            ]
        )
    )
    cell_attributes = {
        "Name": nd["name"],
        "FlyWire Root ID": f'{root_id}<br><small><a href="{nglui.url_for_root_ids([root_id], version=data_version, point_to_proofreading_flywire=True)}">Open in FlyWire <i class="fa-solid fa-up-right-from-square"></i> </a></small>',
        "Partners<br><small>Synapses</small>": "{:,}".format(nd["input_cells"])
        + " in, "
        + "{:,}".format(nd["output_cells"])
        + " out<br><small>"
        + "{:,}".format(nd["input_synapses"])
        + " in, "
        + "{:,}".format(nd["output_synapses"])
        + " out</small>",
        "Classification": nd["class"],
        f'Labels<br><span style="font-size: 9px; color: purple;">Updated {neuron_db.labels_ingestion_timestamp()}</span>': concat_labels(
            labels
        ),
        "NT Type": nd["nt_type"]
        + f' ({lookup_nt_type_name(nd["nt_type"])})'
        + "<br><small>predictions "
        + ", ".join(
            [f"{k}: {nd[f'{k.lower()}_avg']}" for k in sorted(NEURO_TRANSMITTER_NAMES)]
        )
        + "</small>",
        f"Label contributors": concat_labels(unames),
    }

    related_cells = {}

    def insert_neuron_list_links(key, ids, icon, search_endpoint=None):
        if ids:
            ids = set(ids)
            comma_separated_root_ids = ", ".join([str(rid) for rid in ids])
            if not search_endpoint:
                search_endpoint = (
                    f"search?filter_string=id << {comma_separated_root_ids}"
                )
            search_link = f'<a class="btn btn-link" href="{search_endpoint}" target="_blank">{icon}&nbsp; {len(ids)} {key}</a>'
            ngl_url = url_for("app.flywire_url", root_ids=[root_id] + list(ids))
            nglui_link = (
                f'<a class="btn btn-outline-primary btn-sm" href="{ngl_url}"'
                f' target="_blank"><i class="fa-solid fa-cube"></i></a>'
            )
            related_cells[search_link] = nglui_link

    connectivity_table = neuron_db.connections(ids=[root_id], min_syn_count=min_syn_cnt)

    if connectivity_table:
        input_neuropil_synapse_count = defaultdict(int)
        output_neuropil_synapse_count = defaultdict(int)
        input_nt_type_count = defaultdict(int)
        downstream = []
        upstream = []
        for r in connectivity_table:
            if r[0] == root_id:
                downstream.append(r[1])
                output_neuropil_synapse_count[r[2]] += r[3]
            else:
                assert r[1] == root_id
                upstream.append(r[0])
                input_neuropil_synapse_count[r[2]] += r[3]
                input_nt_type_count[r[4].upper()] += r[3]

        # dedupe
        downstream = sorted(set(downstream))
        upstream = sorted(set(upstream))

        insert_neuron_list_links(
            "input cells (upstream) with 5+ synapses",
            upstream,
            '<i class="fa-solid fa-arrow-up"></i>',
            search_endpoint=url_for(
                "app.search", filter_string=f"{OP_UPSTREAM} {root_id}"
            ),
        )
        insert_neuron_list_links(
            "output cells (downstream) with 5+ synapses",
            downstream,
            '<i class="fa-solid fa-arrow-down"></i>',
            search_endpoint=url_for(
                "app.search", filter_string=f"{OP_DOWNSTREAM} {root_id}"
            ),
        )

        charts = {}

        def hemisphere_counts(neuropil_counts):
            res = defaultdict(int)
            for k, v in neuropil_counts.items():
                res[neuropil_hemisphere(k)] += v
            return res

        charts["Input / Output Synapses"] = stats_utils.make_chart_from_counts(
            chart_type="donut",
            key_title="Cell",
            val_title="Count",
            counts_dict={
                "Inputs": sum(input_neuropil_synapse_count.values()),
                "Outputs": sum(output_neuropil_synapse_count.values()),
            },
            search_filter="input_output",
        )

        if input_neuropil_synapse_count:
            charts["Input Synapse Neuropils"] = stats_utils.make_chart_from_counts(
                chart_type="bar",
                key_title="Neuropil",
                val_title="Synapse count",
                counts_dict=input_neuropil_synapse_count,
                descriptions_dict=NEUROPIL_DESCRIPTIONS,
                sort_by_freq=True,
                search_filter="input_neuropils",
            )
            charts["Input Synapse Hemisphere"] = stats_utils.make_chart_from_counts(
                chart_type="donut",
                key_title="Hemisphere",
                val_title="Synapse count",
                counts_dict=hemisphere_counts(input_neuropil_synapse_count),
                search_filter="input_hemisphere",
            )

        if input_nt_type_count:
            charts[
                "Input Synapse Neurotransmitters"
            ] = stats_utils.make_chart_from_counts(
                chart_type="donut",
                key_title="Neurotransmitter Type",
                val_title="Synapse count",
                counts_dict=input_nt_type_count,
                search_filter="input_nt_type",
            )

        if output_neuropil_synapse_count:
            charts["Output Synapse Neuropils"] = stats_utils.make_chart_from_counts(
                chart_type="bar",
                key_title="Neuropil",
                val_title="Synapse count",
                counts_dict=output_neuropil_synapse_count,
                descriptions_dict=NEUROPIL_DESCRIPTIONS,
                sort_by_freq=True,
                search_filter="output_neuropils",
            )
            charts["Output Synapse Hemisphere"] = stats_utils.make_chart_from_counts(
                chart_type="donut",
                key_title="Hemisphere",
                val_title="Synapse count",
                counts_dict=hemisphere_counts(output_neuropil_synapse_count),
                search_filter="output_hemisphere",
            )
    else:
        charts = {}

    insert_neuron_list_links(
        "cells with similar morphology (NBLAST based)",
        neuron_db.get_similar_cells(root_id),
        '<i class="fa-regular fa-clone"></i>',
        search_endpoint=url_for("app.search", filter_string=f"{OP_SIMILAR} {root_id}"),
    )

    # reachability analysis link
    if connectivity_table and not reachability_stats:
        rurl = url_for(
            "app.cell_details",
            cell_names_or_id=cell_names_or_id,
            min_syn_cnt=min_syn_cnt,
            data_version=data_version,
            reachability_stats=1,
        )
        hlink = (
            f'<a class="btn btn-link" onclick="loading(event);" href="{rurl}"><i class="fa-solid fa-gears"></i> &nbsp; Run downstream / '
            f"upstream reachability analysis and reload</a>"
        )
        related_cells[hlink] = ""

    # remove empty items
    cell_attributes = {k: v for k, v in cell_attributes.items() if v}

    cell_extra_data = {}
    if neuron_db.connection_rows and reachability_stats:
        ins, outs = neuron_db.input_output_partner_sets()

        reachable_counts = reachable_node_counts(
            sources={root_id},
            neighbor_sets=outs,
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            cell_extra_data["Downstream Reachable Cells (5+ syn)"] = reachable_counts
        reachable_counts = reachable_node_counts(
            sources={root_id},
            neighbor_sets=ins,
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            cell_extra_data["Upstream Reachable Cells (5+ syn)"] = reachable_counts

    if nd["position"]:
        cell_extra_data["Marked coordinates and Supervoxel IDs"] = {
            f"nm: {c}<br>fw: {nanometer_to_flywire_coordinates(c)}": s
            for c, s in zip(nd["position"], nd["supervoxel_id"])
        }

    return dict(
        cell_names_or_id=cell_names_or_id or nd["name"],
        cell_id=root_id,
        data_version=data_version,
        cell_coordinates=nd["position"][0] if nd["position"] else "",
        cell_attributes=cell_attributes,
        cell_extra_data=cell_extra_data,
        related_cells=related_cells,
        charts=charts,
        load_connections=1 if connectivity_table and len(connectivity_table) > 1 else 0,
    )
