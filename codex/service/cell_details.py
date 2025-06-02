from collections import defaultdict
from functools import lru_cache

from flask import url_for

from codex.configuration import MIN_SYN_THRESHOLD
from codex.data.brain_regions import neuropil_hemisphere, NEUROPIL_DESCRIPTIONS
from codex.data.neurotransmitters import lookup_nt_type_name, NEURO_TRANSMITTER_NAMES
from codex.data.structured_search_filters import (
    OP_UPSTREAM,
    OP_DOWNSTREAM,
    OP_RECIPROCAL,
    OP_SIMILAR_SHAPE,
    OP_SIMILAR_CONNECTIVITY_UPSTREAM,
    OP_SIMILAR_CONNECTIVITY_DOWNSTREAM,
    OP_SIMILAR_CONNECTIVITY,
)
from codex.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
from codex.utils import nglui
from codex.utils import stats as stats_utils
from codex.utils.formatting import (
    concat_labels,
    nanometer_to_flywire_coordinates,
    nanos_to_formatted_micros,
    display,
)
from codex.utils.graph_algos import reachable_node_counts


def connectivity_tag_links(root_id, connectivity_tag):
    if connectivity_tag == "3_cycle_participant":
        return url_for(
            "app.motifs",
            queryA=root_id,
            enabledAB="on",
            regionAB="Any",
            ntTypeAB="Any",
            minSynapseCountAB=1,
            enabledBC="on",
            regionBC="Any",
            ntTypeBC="Any",
            minSynapseCountBC=1,
            enabledCA="on",
            regionCA="Any",
            ntTypeCA="Any",
            minSynapseCountCA=1,
        )
    elif connectivity_tag == "reciprocal":
        return url_for(
            "app.connectivity",
            cell_names_or_ids=str(root_id) + " {or} {reciprocal} " + str(root_id),
        )
    else:
        return None


@lru_cache
def cached_cell_details(
    cell_names_or_id, root_id, neuron_db, data_version, reachability_stats
):
    nd = neuron_db.get_neuron_data(root_id=root_id)
    pos = (
        nanometer_to_flywire_coordinates(nd["position"][0]) if nd["position"] else None
    )
    fw_url = nglui.url_for_root_ids(
        root_ids=[root_id],
        version=data_version or DEFAULT_DATA_SNAPSHOT_VERSION,
        point_to="flywire_public",
        position=pos,
    )
    cell_attributes = {
        "Name": nd["name"],
        "FlyWire Root ID": f"{root_id}<br><small>"
        f'<a href="{fw_url}" target="_blank">Open in FlyWire editor <i class="fa-solid fa-up-right-from-square"></i> </a><br>'
        f'<a href="cell_coordinates/{root_id}?data_version={data_version}" target="_blank">Supervoxel IDs and Coordinates <i class="fa-solid fa-up-right-from-square"></i> </a>'
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
        "Classification<br><small>"
        '<a href="" data-toggle="modal" data-target="#cellAnnotationsModal">'
        'info & credits <i class="fa-solid fa-up-right-from-square"></i></a></small>': concat_labels(
            [
                f"{display(cl)}: <b>{', '.join([str(v) for v in nd[cl]]) if isinstance(nd[cl], list) else nd[cl]}</b>"
                for cl in [
                    "side",
                    "nerve",
                    "flow",
                    "super_class",
                    "class",
                    "sub_class",
                    "cell_type",
                    "hemilineage",
                ]
                if nd[cl]
            ]
        ),
        "Connectivity Tags<br><small>"
        '<a href="" data-toggle="modal" data-target="#connectivityTagsModal">'
        'info & credits <i class="fa-solid fa-up-right-from-square"></i></a></small>': concat_labels(
            nd["connectivity_tag"],
            linker=lambda con_tag: connectivity_tag_links(root_id, con_tag),
        ),
        "Community Labels<br><small>"
        f'<a href="{url_for("app.labeling_log", root_id=root_id)}" target="_blank">'
        'info & credits <i class="fa-solid fa-up-right-from-square"></i></a></small>': concat_labels(
            nd["label"]
        ),
    }

    related_cells = []
    further_analysis = []

    def insert_related_cell_links(key, num_neurons, icon, search_endpoint):
        if num_neurons:
            related_cells.append(
                f'<a class="btn btn-link" href="{search_endpoint}" target="_blank">{icon}&nbsp; {display(num_neurons)} {key}</a>'
            )

    def insert_further_analysis_links(key, icon, search_endpoint):
        further_analysis.append(
            f'<a class="btn btn-link" href="{search_endpoint}" target="_blank">{icon}&nbsp; {key}</a>'
        )

    connectivity_table = neuron_db.cell_connections(root_id)

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

        insert_related_cell_links(
            f"input cells (upstream) with {MIN_SYN_THRESHOLD}+ synapses",
            nd["input_cells"],
            '<i class="fa-solid fa-arrow-up"></i>',
            search_endpoint=url_for(
                "app.search", filter_string=f"{OP_UPSTREAM} {root_id}"
            ),
        )
        insert_related_cell_links(
            f"output cells (downstream) with {MIN_SYN_THRESHOLD}+ synapses",
            nd["output_cells"],
            '<i class="fa-solid fa-arrow-down"></i>',
            search_endpoint=url_for(
                "app.search", filter_string=f"{OP_DOWNSTREAM} {root_id}"
            ),
        )
        if "reciprocal" in nd["connectivity_tag"]:
            up, dn = neuron_db.connections_up_down(root_id)
            reciprocal_count = len(set(up).intersection(dn))
            insert_related_cell_links(
                f"reciprocal cells (both up- and downstream) with {MIN_SYN_THRESHOLD}+ synapses",
                reciprocal_count,
                '<i class="fa-solid fa-arrow-right-arrow-left"></i>',
                search_endpoint=url_for(
                    "app.search", filter_string=f"{OP_RECIPROCAL} {root_id}"
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
            charts["Input Synapse Neurotransmitters"] = (
                stats_utils.make_chart_from_counts(
                    chart_type="donut",
                    key_title="Neurotransmitter Type",
                    val_title="Synapse count",
                    counts_dict=input_nt_type_count,
                    search_filter="input_nt_type",
                )
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

    insert_related_cell_links(
        "cells with similar morphology (NBLAST based)",
        len(neuron_db.get_similar_shape_cells(root_id, include_self=False)),
        '<i class="fa-regular fa-clone"></i>',
        search_endpoint=url_for(
            "app.search", filter_string=f"{OP_SIMILAR_SHAPE} {root_id}"
        ),
    )

    insert_further_analysis_links(
        "Find cells with similar partners up- and downstream",
        '<i class="fa-solid fa-arrow-down-up-across-line"></i>',
        search_endpoint=url_for(
            "app.search",
            filter_string=f"{OP_SIMILAR_CONNECTIVITY} {root_id}",
        ),
    )

    insert_further_analysis_links(
        "Find cells with similar partners upstream",
        '<i class="fa-solid fa-arrows-up-to-line"></i>',
        search_endpoint=url_for(
            "app.search",
            filter_string=f"{OP_SIMILAR_CONNECTIVITY_UPSTREAM} {root_id}",
        ),
    )

    insert_further_analysis_links(
        "Find cells with similar partners downstream",
        '<i class="fa-solid fa-arrows-down-to-line"></i>',
        search_endpoint=url_for(
            "app.search",
            filter_string=f"{OP_SIMILAR_CONNECTIVITY_DOWNSTREAM} {root_id}",
        ),
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
        further_analysis.append(hlink)

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
            cell_extra_data[f"Upstream Reachable Cells ({MIN_SYN_THRESHOLD}+ syn)"] = (
                reachable_counts
            )

    return dict(
        cell_names_or_id=cell_names_or_id or nd["name"],
        cell_id=root_id,
        data_version=data_version,
        cell_coordinates=nd["position"][0] if nd["position"] else "",
        cell_attributes=cell_attributes,
        cell_annotations=cell_annotations,
        cell_extra_data=cell_extra_data,
        related_cells=related_cells,
        further_analysis=further_analysis,
        charts=charts,
        load_connections=1 if connectivity_table and len(connectivity_table) > 1 else 0,
    )
