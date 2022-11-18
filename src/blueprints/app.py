import json
import math
import re
from collections import defaultdict
from datetime import datetime
from functools import lru_cache

from flask import (
    render_template,
    request,
    redirect,
    Response,
    url_for,
    Blueprint,
    session,
)

from src.blueprints.base import (
    request_wrapper,
    require_data_access,
    neuron_data_factory,
    activity_suffix,
    MAX_NEURONS_FOR_DOWNLOAD,
    render_error,
    render_info,
    warning_with_redirect,
)
from src.configuration import MIN_SYN_COUNT
from src.data import gcs_data_loader
from src.data.brain_regions import neuropil_hemisphere
from src.data.faq_qa_kb import FAQ_QA_KB
from src.data.structured_search_filters import (
    OP_DOWNSTREAM,
    OP_UPSTREAM,
    OP_PATHWAYS,
    parse_search_query,
)
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES, lookup_nt_type_name
from src.data.sorting import sort_search_results
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION
from src.utils import nglui, stats as stats_utils
from src.utils.cookies import fetch_flywire_user_id
from src.utils.formatting import (
    synapse_table_to_csv_string,
    synapse_table_to_json_dict,
    highlight_annotations,
)
from src.utils.graph_algos import reachable_node_counts, distance_matrix
from src.utils.graph_vis import make_graph_html
from src.utils.logging import (
    log_activity,
    log_error,
    format_link,
    user_agent,
    log,
    log_user_help,
)
from src.utils.pathway_vis import pathway_chart_data_rows
from src.utils.prm import cell_identification_url
from src.utils.thumbnails import url_for_skeleton
from src.data.structured_search_filters import get_advanced_search_data

app = Blueprint("app", __name__, url_prefix="/app")


@app.route("/stats")
@request_wrapper
@require_data_access
def stats():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)

    log_activity(f"Generating stats {activity_suffix(filter_string, data_version)}")
    filtered_root_id_list, num_items, hint, data_stats, data_charts = _stats_cached(
        filter_string=filter_string,
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
    )
    if num_items:
        log_activity(
            f"Stats got {num_items} results {activity_suffix(filter_string, data_version)}"
        )
    else:
        log_activity(
            f"No stats {activity_suffix(filter_string, data_version)}, sending hint '{hint}'"
        )

    return render_template(
        "stats.html",
        data_stats=data_stats,
        data_charts=data_charts,
        num_items=num_items,
        # If num results is small enough to pass to browser, pass it to allow copying root IDs to clipboard.
        # Otherwise it will be available as downloadable file.
        root_ids_str=",".join([str(ddi) for ddi in filtered_root_id_list])
        if len(filtered_root_id_list) <= MAX_NEURONS_FOR_DOWNLOAD
        else [],
        filter_string=filter_string,
        hint=hint,
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        advanced_search_data=get_advanced_search_data(current_query=filter_string),
    )


@lru_cache
def _stats_cached(filter_string, data_version, case_sensitive, whole_word):
    neuron_db = neuron_data_factory.get(data_version)
    filtered_root_id_list = neuron_db.search(
        search_query=filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    if filtered_root_id_list:
        hint = None
    else:
        hint = neuron_db.closest_token(filter_string, case_sensitive=case_sensitive)
        log_error(f"No stats results for {filter_string}. Sending hint '{hint}'")

    data = [neuron_db.get_neuron_data(i) for i in filtered_root_id_list]
    caption, data_stats, data_charts = stats_utils.compile_data(
        data,
        search_query=filter_string,
        case_sensitive=case_sensitive,
        match_words=whole_word,
        data_version=data_version,
    )
    if neuron_db.connection_rows:
        reachable_counts = reachable_node_counts(
            sources=filtered_root_id_list,
            neighbor_sets=neuron_db.output_sets(),
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            data_stats["Downstream Reachable Cells (5+ syn)"] = reachable_counts
        reachable_counts = reachable_node_counts(
            sources=filtered_root_id_list,
            neighbor_sets=neuron_db.input_sets(),
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            data_stats["Upstream Reachable Cells (5+ syn)"] = reachable_counts
    return (
        filtered_root_id_list,
        len(filtered_root_id_list),
        hint,
        data_stats,
        data_charts,
    )


@app.route("/explore")
@request_wrapper
@require_data_access
def explore():
    log_activity(f"Loading Explore page")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    return render_template(
        "categories.html",
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        key="class",
        categories=neuron_data_factory.get(data_version).categories(),
    )


def render_neuron_list(
    data_version,
    template_name,
    filtered_root_id_list,
    filter_string,
    case_sensitive,
    whole_word,
    page_number,
    hint,
    extra_data,
):
    neuron_db = neuron_data_factory.get(data_version)
    num_items = len(filtered_root_id_list)

    if num_items > 20:
        num_pages = math.ceil(num_items / 20)
        page_number = max(page_number, 1)
        page_number = min(page_number, num_pages)
        pagination_info = [
            {
                "label": "Prev",
                "number": page_number - 1,
                "status": ("disabled" if page_number == 1 else ""),
            }
        ]
        for i in [-3, -2, -1, 0, 1, 2, 3]:
            page_idx = page_number + i
            if 1 <= page_idx <= num_pages:
                pagination_info.append(
                    {
                        "label": page_idx,
                        "number": page_idx,
                        "status": ("active" if page_number == page_idx else ""),
                    }
                )
        pagination_info.append(
            {
                "label": "Next",
                "number": page_number + 1,
                "status": ("disabled" if page_number == num_pages else ""),
            }
        )
        display_data_ids = filtered_root_id_list[
            (page_number - 1) * 20 : page_number * 20
        ]
    else:
        pagination_info = []
        display_data_ids = filtered_root_id_list

    display_data = [neuron_db.get_neuron_data(i) for i in display_data_ids]
    skeleton_thumbnail_urls = {
        nd["root_id"]: url_for_skeleton(nd["root_id"], data_version=data_version)
        for nd in display_data
    }
    for nd in display_data:
        if nd["inherited_tag_root_id"]:
            skeleton_thumbnail_urls[nd["inherited_tag_root_id"]] = url_for_skeleton(
                nd["inherited_tag_root_id"], data_version=data_version
            )

        # Only highlight free-form search tokens (and not structured search attributes)
        nd["colored_annotations"] = highlight_annotations(
            parse_search_query(filter_string)[1], nd["tag"]
        )

    return render_template(
        template_name_or_list=template_name,
        display_data=display_data,
        skeleton_thumbnail_urls=skeleton_thumbnail_urls,
        # If num results is small enough to pass to browser, pass it to allow copying root IDs to clipboard.
        # Otherwise it will be available as downloadable file.
        root_ids_str=",".join([str(ddi) for ddi in filtered_root_id_list])
        if len(filtered_root_id_list) <= MAX_NEURONS_FOR_DOWNLOAD
        else [],
        num_items=num_items,
        pagination_info=pagination_info,
        filter_string=filter_string,
        hint=hint,
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        extra_data=extra_data,
        advanced_search_data=get_advanced_search_data(current_query=filter_string),
    )


@app.route("/search", methods=["GET"])
@request_wrapper
@require_data_access
def search():
    filter_string = request.args.get("filter_string", "")
    page_number = int(request.args.get("page_number", 1))
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)
    hint = None
    extra_data = None
    log(
        f"Loading search page {page_number} {activity_suffix(filter_string, data_version)}"
    )
    filtered_root_id_list = neuron_db.search(
        filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    if filtered_root_id_list:
        log_activity(
            f"Loaded {len(filtered_root_id_list)} search results for page {page_number} {activity_suffix(filter_string, data_version)}"
        )
        filtered_root_id_list, extra_data = sort_search_results(
            query=filter_string,
            ids=filtered_root_id_list,
            output_sets=neuron_db.output_sets(),
        )
    else:
        hint = neuron_db.closest_token(filter_string, case_sensitive=case_sensitive)
        log_error(f"No results for '{filter_string}', sending hint '{hint}'")

    return render_neuron_list(
        data_version=data_version,
        template_name="search.html",
        filtered_root_id_list=filtered_root_id_list,
        filter_string=filter_string,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        page_number=page_number,
        hint=hint,
        extra_data=extra_data,
    )


@app.route("/download_search_results")
@request_wrapper
@require_data_access
def download_search_results():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    log_activity(
        f"Downloading search results {activity_suffix(filter_string, data_version)}"
    )
    filtered_root_id_list = neuron_db.search(
        search_query=filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    log_activity(
        f"For download got {len(filtered_root_id_list)} results {activity_suffix(filter_string, data_version)}"
    )

    cols = [
        "root_id",
        "annotations",
        "name",
        "nt_type",
        "class",
        "hemisphere_fingerprint",
    ]
    data = [cols]
    for i in filtered_root_id_list:
        data.append(
            [str(neuron_db.get_neuron_data(i)[c]).replace(",", ";") for c in cols]
        )

    fname = f"search_results_{re.sub('[^0-9a-zA-Z]+', '_', filter_string)}.csv"
    return Response(
        "\n".join([",".join(r) for r in data]),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={fname}"},
    )


@app.route("/root_ids_from_search_results")
@request_wrapper
@require_data_access
def root_ids_from_search_results():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    log_activity(f"Listing Cell IDs {activity_suffix(filter_string, data_version)}")
    filtered_root_id_list = neuron_db.search(
        search_query=filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    log_activity(
        f"For list cell ids got {len(filtered_root_id_list)} results {activity_suffix(filter_string, data_version)}"
    )
    fname = f"root_ids_{re.sub('[^0-9a-zA-Z]+', '_', filter_string)}.txt"
    return Response(
        ",".join([str(rid) for rid in filtered_root_id_list]),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={fname}"},
    )


@app.route("/search_results_flywire_url")
@request_wrapper
@require_data_access
def search_results_flywire_url():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    log_activity(
        f"Generating URL search results {activity_suffix(filter_string, data_version)}"
    )
    filtered_root_id_list = neuron_db.search(
        filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    log_activity(
        f"For URLs got {len(filtered_root_id_list)} results {activity_suffix(filter_string, data_version)}"
    )

    url = nglui.url_for_random_sample(filtered_root_id_list, MAX_NEURONS_FOR_DOWNLOAD)
    log_activity(
        f"Redirecting results {activity_suffix(filter_string, data_version)} to FlyWire {format_link(url)}"
    )
    return ngl_redirect_with_browser_check(ngl_url=url)


@app.route("/labeling_suggestions")
@request_wrapper
@require_data_access
def labeling_suggestions():
    filter_string = request.args.get("filter_string", "")
    page_number = int(request.args.get("page_number", 1))
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    hint = None

    log_activity(
        f"Loading labeling suggestions page {page_number} {activity_suffix(filter_string, data_version)}"
    )
    filtered_root_id_list = neuron_db.search_in_neurons_with_inherited_labels(
        filter_string
    )

    if filtered_root_id_list:
        log_activity(
            f"Got {len(filtered_root_id_list)} labeling suggestions {activity_suffix(filter_string, data_version)}"
        )
    else:
        hint = neuron_db.closest_token_from_inherited_tags(
            filter_string, case_sensitive=case_sensitive
        )
        log_activity(
            f"No labeling suggestion results {activity_suffix(filter_string, data_version)}, sending hint '{hint}'"
        )

    return render_neuron_list(
        data_version=data_version,
        template_name="labeling_suggestions.html",
        filtered_root_id_list=filtered_root_id_list,
        filter_string=filter_string,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        page_number=page_number,
        hint=hint,
        extra_data=None,
    )


@app.route("/accept_label_suggestion")
@request_wrapper
@require_data_access
def accept_label_suggestion():
    from_root_id = request.args.get("from_root_id")
    to_root_id = request.args.get("to_root_id")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    neuron_db = neuron_data_factory.get(data_version)

    from_neuron = neuron_db.get_neuron_data(from_root_id)
    to_neuron = neuron_db.get_neuron_data(to_root_id)

    log_activity(
        f"Accepting label suggestion from\n{from_root_id}: {from_neuron}\nto\n{to_root_id}: {to_neuron}"
    )

    if not from_neuron or not to_neuron:
        return render_error(
            f"Neurons for Cell IDs {from_root_id} and/or {to_root_id} not found."
        )

    return render_info(
        f"Label(s) <b> {from_neuron['annotations']} </b> assigned to Cell ID <b> {to_root_id} </b>"
    )


@app.route("/reject_label_suggestion")
@request_wrapper
@require_data_access
def reject_label_suggestion():
    from_root_id = request.args.get("from_root_id")
    to_root_id = request.args.get("to_root_id")
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    neuron_db = neuron_data_factory.get(data_version)

    from_neuron = neuron_db.get_neuron_data(from_root_id)
    to_neuron = neuron_db.get_neuron_data(to_root_id)

    log_activity(
        f"Rejecting label suggestion from\n{from_root_id}: {from_neuron}\nto\n{to_root_id}: {to_neuron}"
    )

    if not from_neuron or not to_neuron:
        return render_error(
            f"Neurons for Cell IDs {from_root_id} and/or {to_root_id} not found."
        )

    return render_info(f"Label suggestion rejected.")


@app.route("/flywire_url")
@request_wrapper
def flywire_url():
    root_ids = [int(rid) for rid in request.args.getlist("root_ids")]
    log_request = request.args.get("log_request", default=1, type=int)
    url = nglui.url_for_root_ids(root_ids)
    if log_request:
        log_activity(f"Redirecting for {root_ids} to FlyWire {format_link(url)}")
    return ngl_redirect_with_browser_check(ngl_url=url)


def ngl_redirect_with_browser_check(ngl_url):
    ua = (user_agent() or "").lower()
    if "chrome" in ua or "firefox" in ua:
        return redirect(ngl_url, code=302)
    else:
        return warning_with_redirect(
            title="Browser not supported",
            message=f"Neuroglancer (3D neuron rendering) is not supported on your browser. Use Chrome or Firefox.",
            redirect_url=ngl_url,
            redirect_button_text="Proceed anyway",
        )


@app.route("/cell_details", methods=["GET", "POST"])
@request_wrapper
@require_data_access
def cell_details():
    if request.method == "POST":
        annotation_text = request.form.get("annotation_text")
        annotation_coordinates = request.form.get("annotation_coordinates")
        annotation_cell_id = request.form.get("annotation_cell_id")
        if not annotation_coordinates:
            neuron_db = neuron_data_factory.get()
            ndata = neuron_db.get_neuron_data(annotation_cell_id)
            annotation_coordinates = ndata["position"][0] if ndata["position"] else None
        fw_user_id = fetch_flywire_user_id(session)
        log_user_help(
            f"Submitting annotation '{annotation_text}' for cell {annotation_cell_id} "
            f"with user id {fw_user_id} and coordinates {annotation_coordinates}"
        )
        return redirect(
            cell_identification_url(
                cell_id=annotation_cell_id,
                user_id=fw_user_id,
                coordinates=annotation_coordinates,
                annotation=annotation_text,
            )
        )

    root_id = None
    cell_names_or_id = None
    if "root_id" in request.args:
        root_id = int(request.args.get("root_id"))
    else:
        cell_names_or_id = request.args.get("cell_names_or_id")
        if cell_names_or_id:
            neuron_db = neuron_data_factory.get()
            if cell_names_or_id == "{random_cell}":
                log_activity(f"Generated random cell detail page")
                root_id = neuron_db.random_cell_id()
                cell_names_or_id = (
                    f"name == {neuron_db.get_neuron_data(root_id)['name']}"
                )
            else:
                log_activity(
                    f"Generating cell detail page from search: '{cell_names_or_id}"
                )
                root_ids = neuron_db.search(search_query=cell_names_or_id)
                if len(root_ids) == 1:
                    root_id = root_ids[0]
                else:
                    return redirect(
                        url_for("app.search", filter_string=cell_names_or_id)
                    )

    if root_id is None:
        log_activity(f"Generated empty cell detail page")
        return render_template("cell_details.html")

    min_syn_cnt = request.args.get("min_syn_cnt", 5, type=int)
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    neuron_db = neuron_data_factory.get(data_version)
    log(f"Generating neuron info {activity_suffix(root_id, data_version)}")
    nd = neuron_db.get_neuron_data(root_id=root_id)
    cell_attributes = {
        "Name": nd["name"],
        "FlyWire Root ID": root_id,
        "Annotations": "&nbsp; <b>&#x2022;</b> &nbsp;".join(nd["tag"]),
        "NT Type": nd["nt_type"]
        + f' ({lookup_nt_type_name(nd["nt_type"])})'
        + "<br><small>predictions "
        + ", ".join(
            [f"{k}: {nd[f'{k.lower()}_avg']}" for k in sorted(NEURO_TRANSMITTER_NAMES)]
        )
        + "</small>",
        "Classification": nd["class"],
        "Position": "<br>".join(nd["position"]),
    }

    related_cells = {}

    def insert_neuron_list_links(key, ids, search_endpoint=None):
        if ids:
            ids = set(ids)
            comma_separated_root_ids = ", ".join([str(rid) for rid in ids])
            if not search_endpoint:
                search_endpoint = (
                    f"search?filter_string=id << {comma_separated_root_ids}"
                )
            search_link = f'<a class="btn btn-link" href="{search_endpoint}" target="_blank">{len(ids)} {key}</a>'
            ngl_url = url_for("app.flywire_url", root_ids=[root_id] + list(ids))
            nglui_link = (
                f'<a class="btn btn-outline-primary btn-sm" href="{ngl_url}"'
                f' target="_blank"><i class="fa-solid fa-cube"></i></a>'
            )
            related_cells[search_link] = nglui_link

    connectivity_table = gcs_data_loader.load_connection_table_for_root_id(
        root_id, min_syn_count=min_syn_cnt
    )
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
            search_endpoint=url_for(
                "app.search", filter_string=f"{OP_UPSTREAM} {root_id}"
            ),
        )
        insert_neuron_list_links(
            "output cells (downstream) with 5+ synapses",
            downstream,
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

    top_nblast_matches = [
        i[0]
        for i in (
            gcs_data_loader.load_nblast_scores_for_root_id(
                root_id, sort_highest_score=True, limit=10
            )
            or []
        )
        if i[1] > 0.4 and i[0] != root_id
    ]
    insert_neuron_list_links(
        "cells with similar morphology (NBLAST based)", top_nblast_matches
    )

    similar_root_ids = [
        i[0]
        for i in zip(nd["similar_root_ids"], nd["similar_root_id_scores"])
        if i[1] > 12 and i[0] != root_id
    ]
    insert_neuron_list_links("cells with similar neuropil projection", similar_root_ids)

    symmetrical_root_ids = [
        i[0]
        for i in zip(nd["symmetrical_root_ids"], nd["symmetrical_root_id_scores"])
        if i[1] > 12 and i[0] != root_id
    ]
    insert_neuron_list_links(
        "cells with similar neuropil projection in opposite hemisphere",
        symmetrical_root_ids,
    )

    # remove empty items
    cell_attributes = {k: v for k, v in cell_attributes.items() if v}
    related_cells = {k: v for k, v in related_cells.items() if v}

    cell_extra_data = {}
    if neuron_db.connection_rows:
        reachable_counts = reachable_node_counts(
            sources={root_id},
            neighbor_sets=neuron_db.output_sets(),
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            cell_extra_data["Downstream Reachable Cells (5+ syn)"] = reachable_counts
        reachable_counts = reachable_node_counts(
            sources={root_id},
            neighbor_sets=neuron_db.input_sets(),
            total_count=neuron_db.num_cells(),
        )
        if reachable_counts:
            cell_extra_data["Upstream Reachable Cells (5+ syn)"] = reachable_counts

    log_activity(
        f"Generated neuron info for {root_id} with {len(cell_attributes) + len(related_cells)} items"
    )
    return render_template(
        "cell_details.html",
        cell_names_or_id=cell_names_or_id or nd["name"],
        cell_id=root_id,
        cell_coordinates=nd["position"][0] if nd["position"] else "",
        cell_attributes=cell_attributes,
        cell_extra_data=cell_extra_data,
        related_cells=related_cells,
        charts=charts,
        load_connections=1 if connectivity_table and len(connectivity_table) > 1 else 0,
    )


@app.route("/nblast")
@request_wrapper
@require_data_access
def nblast():
    sample_input = "720575940628063479, 720575940645542276, 720575940626822533, 720575940609037432, 720575940628445399"
    source_cell_names_or_ids = request.args.get("source_cell_names_or_ids", "")
    target_cell_names_or_ids = request.args.get("target_cell_names_or_ids", "")
    if not source_cell_names_or_ids and not target_cell_names_or_ids:
        if request.args.get("with_sample_input", type=int, default=0):
            cell_names_or_ids = sample_input
        else:
            cell_names_or_ids = None
    else:
        cell_names_or_ids = " ".join(
            [q for q in [source_cell_names_or_ids, target_cell_names_or_ids] if q]
        )

    download = request.args.get("download", 0, type=int)
    log_activity(f"Generating NBLAST table for '{cell_names_or_ids}' {download=}")
    message = None

    if cell_names_or_ids:
        neuron_db = neuron_data_factory.get()
        root_ids = neuron_db.search(search_query=cell_names_or_ids)
        if not root_ids:
            return render_error(
                title="No matching cells found",
                message=f"Could not find any cells matching '{cell_names_or_ids}'",
            )
        elif len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
            message = (
                f"{len(root_ids)} cells match '{cell_names_or_ids}'. "
                f"Fetching NBLAST scores for the first {MAX_NEURONS_FOR_DOWNLOAD // 2} matches."
            )
            root_ids = root_ids[: MAX_NEURONS_FOR_DOWNLOAD // 2]
        elif len(root_ids) == 1:
            return render_error(
                message=f"Only one match found in the data: {root_ids}. Need 2 or more cells for pairwise NBLAST score(s).",
                title="Cell list is too short",
            )

        data = [neuron_db.get_neuron_data(i) for i in root_ids]
        empty = ""
        cell_names_and_ids = [f"{n['name']} {n['root_id']}" for n in data]
        if download:
            nblast_scores = [["from \\ to"] + cell_names_and_ids]
        else:
            nblast_scores = [
                ["from \\ to"]
                + [f"({i + 1})" for i, rid in enumerate(cell_names_and_ids)]
            ]
        column_index = {
            r: i for i, r in enumerate(gcs_data_loader.load_nblast_scores_header())
        }
        columns = [column_index.get(rid, -1) for rid in root_ids]
        all_scores = gcs_data_loader.load_nblast_scores_for_root_ids(root_ids)
        for i, rid in enumerate(root_ids):
            scores = all_scores.get(rid)
            if download:
                nblast_scores.append(
                    [cell_names_and_ids[i]]
                    + (
                        [
                            (scores[c][1] if j != i else empty)
                            for j, c in enumerate(columns)
                        ]
                        if scores
                        else [empty] * len(columns)
                    )
                )
            else:

                def score_with_link(idx, col):
                    if col < 0 or i == idx:
                        return empty
                    score = scores[col][1]
                    if score < -0.4:
                        bgd = "red"
                    elif score < 0.3:
                        bgd = "orange"
                    else:
                        bgd = "green"
                    style = f'style="color:{bgd};"' if bgd else empty
                    return (
                        f"<strong><span {style}>{score}</span><br></strong><small>"
                        f'<a target="_blank" href="search_results_flywire_url?filter_string=id << {rid},{root_ids[idx]}"><i class="fa-solid fa-cube"></i></a> &nbsp;'
                        f'<a target="_blank" href="search?filter_string=id << {rid},{root_ids[idx]}"><i class="fa-solid fa-list"></i></a></small>'
                    )

                scores_row = (
                    [score_with_link(i, c) for i, c in enumerate(columns)]
                    if scores
                    else [empty] * len(columns)
                )
                nblast_scores.append(
                    [f"<b>({i + 1})</b><br>{data[i]['name']}<br><small>{rid}</small>"]
                    + scores_row
                )

        if all([all([v == empty for v in row[1:]]) for row in nblast_scores[1:]]):
            return render_error(
                f"NBLAST scores for Cells IDs {root_ids} are not available. Currently NBLAST scores "
                f"are available for the central brain cells only (which is around 60% of the dataset)."
            )

        log_activity(f"Generated NBLAST table for {root_ids} {download=}")
    else:
        root_ids = []
        nblast_scores = []

    if download:
        fname = f"nblast_scores.csv"
        return Response(
            "\n".join([",".join([str(r) for r in row]) for row in nblast_scores]),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={fname}"},
        )
    else:
        nblast_doc = FAQ_QA_KB["nblast"]
        return render_template(
            "distance_table.html",
            source_cell_names_or_ids=source_cell_names_or_ids,
            target_cell_names_or_ids=target_cell_names_or_ids,
            distance_table=nblast_scores,
            download_url=url_for(
                "app.nblast",
                download=1,
                source_cell_names_or_ids=source_cell_names_or_ids,
                target_cell_names_or_ids=target_cell_names_or_ids,
            ),
            info_text="With this tool you can specify one "
            "or more source cells + one or more target cells, and get a matrix of NBLAST scores for all "
            "source/target pairs.<br>"
            f"{nblast_doc['a']}",
            sample_input=sample_input,
            message=message,
        )


@app.route("/pathways")
@request_wrapper
@require_data_access
def pathways():
    source = request.args.get("source_cell_id", type=int)
    target = request.args.get("target_cell_id", type=int)
    min_syn_count = request.args.get("min_syn_count", type=int, default=MIN_SYN_COUNT)
    min_syn_count = max(min_syn_count, MIN_SYN_COUNT)
    log_activity(
        f"Rendering pathways from {source} to {target} with {min_syn_count=}"
    )
    neuron_db = neuron_data_factory.get()
    plen, data_rows = pathway_chart_data_rows(
        source=source,
        target=target,
        neuron_db=neuron_db,
        min_syn_count=min_syn_count,
    )

    def cell_link(rid):
        cell_details_url = url_for("app.cell_details", root_id=rid)
        cell_name = neuron_db.get_neuron_data(rid)["name"]
        return f'<a href="{cell_details_url}">{cell_name}</a>'

    if not data_rows:
        caption = f"There are no pathways from {cell_link(source)} to {cell_link(target)} with minimum synapse threshold "
    else:
        caption = (
            f"Shortest paths from {cell_link(source)} to "
            f"{cell_link(target)} have length {plen} for minimum synapse threshold "
        )

    return render_template(
        "pathways.html",
        data_rows=data_rows,
        caption=caption,
        min_syn_count=min_syn_count,
        source_cell_id=source,
        target_cell_id=target,
        list_url=url_for("app.search", filter_string=f"{source} {OP_PATHWAYS} {target}")
        if min_syn_count == MIN_SYN_COUNT
        else "",
    )


@app.route("/path_length")
@request_wrapper
@require_data_access
def path_length():
    sample_input = (
        "720575940626822533, 720575940632905663, 720575940604373932, 720575940628289103"
    )
    source_cell_names_or_ids = request.args.get("source_cell_names_or_ids", "")
    target_cell_names_or_ids = request.args.get("target_cell_names_or_ids", "")
    min_syn_count = request.args.get("min_syn_count", type=int, default=MIN_SYN_COUNT)
    min_syn_count = max(min_syn_count, MIN_SYN_COUNT)

    if not source_cell_names_or_ids and not target_cell_names_or_ids:
        if request.args.get("with_sample_input", type=int, default=0):
            cell_names_or_ids = sample_input
        else:
            cell_names_or_ids = None
    else:
        cell_names_or_ids = " ".join(
            [q for q in [source_cell_names_or_ids, target_cell_names_or_ids] if q]
        )

    download = request.args.get("download", 0, type=int)
    log_activity(f"Generating path lengths table for '{cell_names_or_ids}' {download=}")
    message = None
    neuron_db = neuron_data_factory.get()

    if cell_names_or_ids:
        root_ids = neuron_db.search(search_query=cell_names_or_ids)
        if not root_ids:
            return render_error(
                title="No matching cells found",
                message=f"Could not find any cells matching '{cell_names_or_ids}'",
            )
        elif len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
            message = (
                f"{len(root_ids)} cells match '{cell_names_or_ids}'. "
                f"Fetching path lengths for the first {MAX_NEURONS_FOR_DOWNLOAD // 2} matches."
            )
            root_ids = root_ids[: MAX_NEURONS_FOR_DOWNLOAD // 2]
        elif len(root_ids) == 1:
            return render_error(
                message=f"Only one match found in the data: {root_ids}. Need 2 or more cells for pairwise pathway(s).",
                title="Cell list is too short",
            )

        matrix = distance_matrix(
            sources=root_ids,
            targets=root_ids,
            neighbor_sets=neuron_db.output_sets(min_syn_count=min_syn_count),
        )
        if len(matrix) <= 1:
            return render_error(
                f"Path lengths for Cell IDs {root_ids} are not available."
            )
        log_activity(f"Generated path lengths table for {root_ids} {download=}")
    else:
        matrix = []

    if download:
        fname = f"path_lengths.csv"
        return Response(
            "\n".join([",".join([str(r) for r in row]) for row in matrix]),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={fname}"},
        )
    else:
        if matrix:
            # format matrix with cell info/hyperlinks and pathway hyperlinks
            for i, r in enumerate(matrix[1:]):
                from_root_id = int(r[0])
                for j, val in enumerate(r):
                    if j == 0:
                        r[
                            j
                        ] = f'<a href="{url_for("app.search", filter_string="id == " + str(from_root_id))}">{neuron_db.get_neuron_data(from_root_id)["name"]}</a><br><small>{from_root_id}</small>'
                    elif val > 0:
                        to_root_id = int(matrix[0][j])
                        if min_syn_count == MIN_SYN_COUNT:
                            q = f"{from_root_id} {OP_PATHWAYS} {to_root_id}"
                            slink = f'<a href="{url_for("app.search", filter_string=q)}" target="_blank" ><i class="fa-solid fa-list"></i></a>'
                        else:
                            slink = ""  # search by pathways is only available for default threshold
                        plink = f'<a href="{url_for("app.pathways", source_cell_id=from_root_id, target_cell_id=to_root_id, min_syn_count=min_syn_count)}" target="_blank" ><i class="fa-solid fa-route"></i></a>'
                        r[j] = f"{val} hops <br> <small>{plink} &nbsp; {slink}</small>"
                    elif val == 0:
                        r[j] = ""
                    elif val == -1:
                        r[j] = '<span style="color:grey">no path</span>'

            for j, val in enumerate(matrix[0]):
                if j > 0:
                    matrix[0][
                        j
                    ] = f'<a href="{url_for("app.search", filter_string="id == " + str(val))}">{neuron_db.get_neuron_data(int(val))["name"]}</a><br><small>{val}</small>'

        paths_doc = FAQ_QA_KB["paths"]
        return render_template(
            "distance_table.html",
            source_cell_names_or_ids=source_cell_names_or_ids,
            target_cell_names_or_ids=target_cell_names_or_ids,
            collect_min_syn_count=True,
            min_syn_count=min_syn_count,
            distance_table=matrix,
            download_url=url_for(
                "app.path_length",
                download=1,
                source_cell_names_or_ids=source_cell_names_or_ids,
                target_cell_names_or_ids=target_cell_names_or_ids,
            ),
            info_text="With this tool you can specify one "
            "or more source cells + one or more target cells, set a minimum synapse threshold per connection,"
            " and get a matrix with shortest path lengths for all source/target pairs. From there, you can inspect / "
            "visualize "
            "the pathways between any pair of cells in detail.<br>"
            f"{paths_doc['a']}",
            sample_input=sample_input,
            message=message,
        )


@app.route("/connectivity")
@request_wrapper
@require_data_access
def connectivity():
    sample_input = (
        "720575940626822533, 720575940632905663, 720575940604373932, 720575940628289103"
    )
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    nt_type = request.args.get("nt_type", "all")
    min_syn_cnt = request.args.get("min_syn_cnt", 5, type=int)
    cell_names_or_ids = request.args.get("cell_names_or_ids", "")
    if (
        request.args.get("with_sample_input", type=int, default=0)
        and not cell_names_or_ids
    ):
        cell_names_or_ids = sample_input
    download = request.args.get("download")
    # headless network view (no search box / nav bar etc.)
    headless = request.args.get("headless", default=0, type=int)
    log_request = request.args.get(
        "log_request", default=0 if headless else 1, type=int
    )
    if log_request:
        log_activity(f"Generating network for '{cell_names_or_ids}' {download=}")

    root_ids = []
    message = None

    if cell_names_or_ids:
        neuron_db = neuron_data_factory.get(data_version)
        root_ids = neuron_db.search(search_query=cell_names_or_ids)
        if not root_ids:
            return render_error(
                title="No matching cells found",
                message=f"Could not find any cells matching '{cell_names_or_ids}'",
            )
        elif len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
            message = (
                f"Too many ({len(root_ids)}) cells match '{cell_names_or_ids}'. "
                f"Generating connectivity network for the first {MAX_NEURONS_FOR_DOWNLOAD // 2} matches."
            )
            root_ids = root_ids[: MAX_NEURONS_FOR_DOWNLOAD // 2]

        contable = gcs_data_loader.load_connection_table_for_root_ids(root_ids)
        nt_type = nt_type.upper()
        if nt_type and nt_type != "ALL":
            contable = [r for r in contable if r[4].upper() == nt_type]
        if min_syn_cnt:
            contable = [r for r in contable if r[3] >= min_syn_cnt]
        if len(contable) <= 1:
            return render_error(
                f"Connections for {min_syn_cnt=}, {nt_type=} and Cell IDs {root_ids} are unavailable."
            )
        if log_request:
            log_activity(
                f"Generated connections table for {root_ids} {download=} {min_syn_cnt=} {nt_type=}"
            )
        if download:
            if download.lower() == "json":
                return Response(
                    json.dumps(
                        synapse_table_to_json_dict(
                            table=contable,
                            neuron_data_fetcher=lambda rid: neuron_db.get_neuron_data(
                                rid
                            ),
                            meta_data={
                                "generated": str(datetime.now()),
                                "data_version": data_version,
                                "query": cell_names_or_ids,
                                "min_syn_cnt": min_syn_cnt,
                                "nt_types": nt_type,
                                "url": str(request.url),
                            },
                        ),
                        indent=4,
                    ),
                    mimetype="application/json",
                    headers={
                        "Content-disposition": f"attachment; filename=connections.json"
                    },
                )
            else:
                return Response(
                    synapse_table_to_csv_string(contable),
                    mimetype="text/csv",
                    headers={
                        "Content-disposition": f"attachment; filename=connections.csv"
                    },
                )

        network_html = make_graph_html(
            connection_table=contable,
            neuron_data_fetcher=lambda nid: neuron_db.get_neuron_data(nid),
            center_ids=root_ids,
        )
        if headless:
            return network_html
        else:
            return render_template(
                "connectivity.html",
                cell_names_or_ids=cell_names_or_ids,
                min_syn_cnt=min_syn_cnt,
                nt_type=nt_type,
                network_html=network_html,
                info_text=None,
                sample_input=None,
                message=message,
            )
    else:
        con_doc = FAQ_QA_KB["connectivity"]
        return render_template(
            "connectivity.html",
            cell_names_or_ids=cell_names_or_ids,
            min_syn_cnt=min_syn_cnt,
            nt_type=nt_type,
            network_html=None,
            info_text="With this tool you can specify one or more cells and visualize their connectivity network.<br>"
            f"{con_doc['a']}",
            sample_input=sample_input,
            message=None,
        )


@app.route("/activity_log")
@request_wrapper
def activity_log():
    log_activity(f"Rendering Activity Log")
    return render_error(
        message=f"Activity log feature coming soon. It will list a history of recent searches / queries with "
        f"links to results.",
        title="Coming soon",
    )
