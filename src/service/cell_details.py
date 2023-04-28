from collections import defaultdict
from functools import lru_cache

from flask import url_for

from src.configuration import MIN_SYN_THRESHOLD
from src.data.brain_regions import neuropil_hemisphere, NEUROPIL_DESCRIPTIONS
from src.data.neurotransmitters import lookup_nt_type_name, NEURO_TRANSMITTER_NAMES
from src.data.structured_search_filters import OP_UPSTREAM, OP_DOWNSTREAM, OP_SIMILAR
from src.utils import nglui
from src.utils import stats as stats_utils
from src.utils.formatting import (
    concat_labels,
    nanometer_to_flywire_coordinates,
    nanos_to_formatted_micros,
    display,
)
from src.utils.graph_algos import reachable_node_counts


@lru_cache
def cached_cell_details(
    cell_names_or_id, root_id, neuron_db, data_version, reachability_stats
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
    pos = (
        nanometer_to_flywire_coordinates(nd["position"][0]) if nd["position"] else None
    )
    cell_attributes = {
        "Name": nd["name"],
        "FlyWire Root ID": f"{root_id}<br><small>"
        f'<a href="{nglui.url_for_root_ids([root_id], version=data_version, point_to_proofreading_flywire=True, position=pos)}" target="_blank">Open in FlyWire <i class="fa-solid fa-up-right-from-square"></i> </a><br>'
        f'<a href="cell_coordinates/{data_version}/{root_id}" target="_blank">Supervoxel IDs and Coordinates <i class="fa-solid fa-up-right-from-square"></i> </a>'
        "</small>",
        "Partners<br><small>Synapses</small>": '<a href="'
        + url_for("app.search", filter_string=f"{OP_UPSTREAM} {root_id}")
        + f'" target="_blank"><i class="fa-solid fa-arrow-up"></i> {display(nd["input_cells"])} in</a>'
        + f' &#183; <a href="{url_for("app.search", filter_string=f"{OP_DOWNSTREAM} {root_id}")}'
        + f'" target="_blank">{display(nd["output_cells"])} out <i class="fa-solid fa-arrow-down"></i></a>'
        + f'<br><small><i class="fa-solid fa-arrow-up"></i> {display(nd["input_synapses"])} in &#183; '
        + f'{display(nd["output_synapses"])} out <i class="fa-solid fa-arrow-down"></i></small>',
        "NT Type": nd["nt_type"]
        + f' ({lookup_nt_type_name(nd["nt_type"])})<br><small>predictions '
        + ", ".join(
            [f"{k}: {nd[f'{k.lower()}_avg']}" for k in sorted(NEURO_TRANSMITTER_NAMES)]
        )
        + "</small>",
        "Size": "<small>"
        + "<br>".join(
            [
                f"{cl[0]}: <b>{nanos_to_formatted_micros(nd[cl[1]], cl[2])}</b>"
                for cl in [
                    ("Length", "length_nm", 1),
                    ("Area", "area_nm", 2),
                    ("Volume", "size_nm", 3),
                ]
                if nd[cl[1]]
            ]
        )
        + "</small>",
    }

    cell_annotations = {
        "Classification": concat_labels(
            [
                f"{display(cl)}: <b>{nd[cl]}</b>"
                for cl in [
                    "side",
                    "nerve",
                    "flow",
                    "super_class",
                    "class",
                    "sub_class",
                    "cell_type",
                    "hemibrain_type",
                    "hemilineage",
                ]
                if nd[cl]
            ]
        ),
        "Identification Labels": concat_labels(labels),
        "Label contributors": concat_labels(unames),
        "Last DB sync": concat_labels(
            [f'<b style="color: green">{neuron_db.labels_ingestion_timestamp()}</b>']
        ),
    }

    related_cells = []

    def insert_neuron_list_links(key, num_neurons, icon, search_endpoint):
        if num_neurons:
            related_cells.append(
                f'<a class="btn btn-link" href="{search_endpoint}" target="_blank">{icon}&nbsp; {display(num_neurons)} {key}</a>'
            )

    connectivity_table = neuron_db.connections(ids=[root_id])

    if connectivity_table:
        input_neuropil_synapse_count = defaultdict(int)
        output_neuropil_synapse_count = defaultdict(int)
        input_nt_type_count = defaultdict(int)
        for r in connectivity_table:
            if r[0] == root_id:
                output_neuropil_synapse_count[r[2]] += r[3]
            else:
                assert r[1] == root_id
                input_neuropil_synapse_count[r[2]] += r[3]
                input_nt_type_count[r[4].upper()] += r[3]

        insert_neuron_list_links(
            f"input cells (upstream) with {MIN_SYN_THRESHOLD}+ synapses",
            nd["input_cells"],
            '<i class="fa-solid fa-arrow-up"></i>',
            search_endpoint=url_for(
                "app.search", filter_string=f"{OP_UPSTREAM} {root_id}"
            ),
        )
        insert_neuron_list_links(
            f"output cells (downstream) with {MIN_SYN_THRESHOLD}+ synapses",
            nd["output_cells"],
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
        len(neuron_db.get_similar_cells(root_id)),
        '<i class="fa-regular fa-clone"></i>',
        search_endpoint=url_for("app.search", filter_string=f"{OP_SIMILAR} {root_id}"),
    )

    # reachability analysis link
    if connectivity_table and not reachability_stats:
        rurl = url_for(
            "app.cell_details",
            cell_names_or_id=cell_names_or_id,
            data_version=data_version,
            reachability_stats=1,
        )
        hlink = (
            f'<a class="btn btn-link" onclick="loading(event);" href="{rurl}"><i class="fa-solid fa-gears"></i> &nbsp; '
            "Run reachability analysis and reload</a>"
        )
        related_cells.append(hlink)

    # remove empty items
    cell_attributes = {k: v for k, v in cell_attributes.items() if v}
    cell_annotations = {k: v for k, v in cell_annotations.items() if v}

    cell_extra_data = {}
    if reachability_stats:
        ins, outs = neuron_db.input_output_partner_sets()

        reachable_counts = reachable_node_counts(
            sources={root_id},
            neighbor_sets=outs,
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            cell_extra_data[
                f"Downstream Reachable Cells ({MIN_SYN_THRESHOLD}+ syn)"
            ] = reachable_counts
        reachable_counts = reachable_node_counts(
            sources={root_id},
            neighbor_sets=ins,
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            cell_extra_data[
                f"Upstream Reachable Cells ({MIN_SYN_THRESHOLD}+ syn)"
            ] = reachable_counts

    return dict(
        cell_names_or_id=cell_names_or_id or nd["name"],
        cell_id=root_id,
        data_version=data_version,
        cell_coordinates=nd["position"][0] if nd["position"] else "",
        cell_attributes=cell_attributes,
        cell_annotations=cell_annotations,
        cell_extra_data=cell_extra_data,
        related_cells=related_cells,
        charts=charts,
        load_connections=1 if connectivity_table and len(connectivity_table) > 1 else 0,
    )
