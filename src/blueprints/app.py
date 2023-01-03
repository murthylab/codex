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
    warning_with_redirect,
)
from src.configuration import MIN_SYN_COUNT
from src.data import gcs_data_loader
from src.data.brain_regions import (
    neuropil_hemisphere,
    REGIONS,
    NEUROPIL_DESCRIPTIONS,
    REGIONS_JSON,
)
from src.data.faq_qa_kb import FAQ_QA_KB
from src.data.structured_search_filters import (
    OP_DOWNSTREAM,
    OP_UPSTREAM,
    OP_PATHWAYS,
    parse_search_query,
    OP_SIMILAR,
)
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES, lookup_nt_type_name
from src.data.sorting import sort_search_results, SORT_BY_OPTIONS
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION
from src.utils import nglui, stats as stats_utils
from src.utils.cookies import fetch_flywire_user_id
from src.utils.formatting import (
    synapse_table_to_csv_string,
    synapse_table_to_json_dict,
    highlight_annotations,
    concat_labels,
    trim_long_tokens,
    nanometer_to_flywire_coordinates,
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
    log_warning,
)
from src.utils.nglui import can_be_flywire_root_id
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
        log_warning(
            f"No stats {activity_suffix(filter_string, data_version)}, sending hint '{hint}'"
        )

    return render_template(
        "stats.html",
        data_stats=data_stats,
        data_charts=data_charts,
        num_items=num_items,
        searched_for_root_id=can_be_flywire_root_id(filter_string),
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
        hint, edist = neuron_db.closest_token(
            filter_string, case_sensitive=case_sensitive
        )
        log_warning(
            f"No stats results for {filter_string}. Sending hint '{hint}' {edist=}"
        )

    neuron_data = [neuron_db.get_neuron_data(i) for i in filtered_root_id_list]
    label_data = [neuron_db.get_label_data(i) for i in filtered_root_id_list]
    caption, data_stats, data_charts = stats_utils.compile_data(
        neuron_data=neuron_data,
        label_data=label_data,
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


@app.route("/leaderboard")
@request_wrapper
@require_data_access
def leaderboard():
    log_activity(f"Loading Leaderboard")
    return render_template("leaderboard.html", data_stats=_leaderboard_cached())


@lru_cache
def _leaderboard_cached():
    res = {}
    stats_utils.fill_in_leaderboard_data(
        label_data=neuron_data_factory.get().all_label_data(),
        top_n=20,
        include_lab_leaderboard=True,
        destination=res,
    )
    return stats_utils.format_for_display(res)


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
    sort_by,
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
    highlighted_tags = {}
    for nd in display_data:
        # Only highlight free-form search tokens (and not structured search attributes)
        psq = parse_search_query(filter_string)
        search_terms = psq[1] + [stq["rhs"] for stq in psq[2] or []]
        highlighted_tag_list = highlight_annotations(
            search_terms, [trim_long_tokens(t) for t in nd["tag"]]
        )
        for t, highlighted_tag in enumerate(highlighted_tag_list):
            highlighted_tags[nd["tag"][t]] = highlighted_tag

    return render_template(
        template_name_or_list=template_name,
        display_data=display_data,
        highlighted_tags=highlighted_tags,
        skeleton_thumbnail_urls=skeleton_thumbnail_urls,
        # If num results is small enough to pass to browser, pass it to allow copying root IDs to clipboard.
        # Otherwise it will be available as downloadable file.
        root_ids_str=",".join([str(ddi) for ddi in filtered_root_id_list])
        if len(filtered_root_id_list) <= MAX_NEURONS_FOR_DOWNLOAD
        else [],
        num_items=num_items,
        searched_for_root_id=can_be_flywire_root_id(filter_string),
        pagination_info=pagination_info,
        filter_string=filter_string,
        hint=hint,
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        extra_data=extra_data,
        sort_by=sort_by,
        sort_by_options=SORT_BY_OPTIONS,
        advanced_search_data=get_advanced_search_data(current_query=filter_string),
        multi_val_attrs=neuron_db.multi_val_attrs(filtered_root_id_list),
        non_uniform_labels=neuron_db.non_uniform_labels(
            page_ids=display_data_ids, all_ids=filtered_root_id_list
        ),
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
    sort_by = request.args.get("sort_by")
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
            f"Loaded {len(filtered_root_id_list)} search results for page {page_number} "
            f"{activity_suffix(filter_string, data_version)}"
        )
        filtered_root_id_list, extra_data = sort_search_results(
            query=filter_string,
            ids=filtered_root_id_list,
            output_sets=neuron_db.output_sets(),
            label_count_getter=lambda x: len(neuron_db.get_neuron_data(x)["tag"]),
            synapse_neuropil_count_getter=lambda x: len(
                neuron_db.get_neuron_data(x)["input_neuropils"]
            )
            + len(neuron_db.get_neuron_data(x)["output_neuropils"]),
            size_getter=lambda x: neuron_db.get_neuron_data(x)["size_nm"],
            partner_count_getter=lambda x: len(neuron_db.output_sets()[x])
            + len(neuron_db.input_sets()[x]),
            similarity_scores_getter=lambda x: neuron_db.get_similar_cells(
                x, as_dict_with_scores=True
            ),
            connections_getter=lambda x: neuron_db.connections(ids=[x]),
            sort_by=sort_by,
        )
    else:
        hint, edist = neuron_db.closest_token(
            filter_string, case_sensitive=case_sensitive
        )
        log_warning(f"No results for '{filter_string}', sending hint '{hint}' {edist=}")

    return render_neuron_list(
        data_version=data_version,
        template_name="search.html",
        filtered_root_id_list=filtered_root_id_list,
        filter_string=filter_string,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        page_number=page_number,
        sort_by=sort_by,
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
        "tag",
        "name",
        "nt_type",
        "class",
        "input_synapses",
        "output_synapses",
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

    url = nglui.url_for_random_sample(
        filtered_root_id_list,
        version=data_version,
        sample_size=MAX_NEURONS_FOR_DOWNLOAD,
    )
    log_activity(
        f"Redirecting results {activity_suffix(filter_string, data_version)} to FlyWire {format_link(url)}"
    )
    return ngl_redirect_with_browser_check(ngl_url=url)


@app.route("/flywire_url")
@request_wrapper
def flywire_url():
    root_ids = [int(rid) for rid in request.args.getlist("root_ids")]
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    log_request = request.args.get("log_request", default=1, type=int)
    proofreading_url = request.args.get("proofreading_url", default=0, type=int)
    url = nglui.url_for_root_ids(
        root_ids, version=data_version, point_to_proofreading_flywire=proofreading_url
    )
    if log_request:
        log_activity(
            f"Redirecting for {root_ids} to FlyWire {format_link(url)}, {proofreading_url=}"
        )
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
    min_syn_cnt = request.args.get("min_syn_cnt", 5, type=int)
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    reachability_stats = request.args.get("reachability_stats", 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    if request.method == "POST":
        annotation_text = request.form.get("annotation_text")
        annotation_coordinates = request.form.get("annotation_coordinates")
        annotation_cell_id = request.form.get("annotation_cell_id")
        if not annotation_coordinates:
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
    cell_names_or_id = request.args.get("cell_names_or_id")
    if not cell_names_or_id:
        cell_names_or_id = request.args.get("root_id")
    if cell_names_or_id:
        if cell_names_or_id == "{random_cell}":
            log_activity(f"Generated random cell detail page")
            root_id = neuron_db.random_cell_id()
            cell_names_or_id = f"name == {neuron_db.get_neuron_data(root_id)['name']}"
        else:
            log_activity(
                f"Generating cell detail page from search: '{cell_names_or_id}"
            )
            root_ids = neuron_db.search(search_query=cell_names_or_id)
            if len(root_ids) == 1:
                root_id = root_ids[0]
            else:
                return redirect(url_for("app.search", filter_string=cell_names_or_id))

    if root_id is None:
        log_activity(f"Generated empty cell detail page")
        return render_template("cell_details.html")
    log(f"Generating neuron info {activity_suffix(root_id, data_version)}")
    return _cached_cell_details(
        cell_names_or_id=cell_names_or_id,
        root_id=root_id,
        neuron_db=neuron_db,
        data_version=data_version,
        min_syn_cnt=min_syn_cnt,
        reachability_stats=reachability_stats,
    )


@lru_cache
def _cached_cell_details(
    cell_names_or_id, root_id, neuron_db, data_version, min_syn_cnt, reachability_stats
):
    nd = neuron_db.get_neuron_data(root_id=root_id)
    labels_data = neuron_db.get_label_data(root_id=root_id)
    tags = sorted(set([ld["tag"] for ld in labels_data or []]))
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
            tags
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
        ins, outs = neuron_db.input_output_sets()

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

    log_activity(
        f"Generated neuron info for {root_id} with {len(cell_attributes) + len(related_cells)} items"
    )

    return render_template(
        "cell_details.html",
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


@app.route("/nblast")
@request_wrapper
@require_data_access
def nblast():
    sample_input = (
        "720575940634139799, 720575940626843194, 720575940631740497, 720575940608893891"
    )
    source_cell_names_or_ids = request.args.get("source_cell_names_or_ids", "")
    target_cell_names_or_ids = request.args.get("target_cell_names_or_ids", "")
    if not source_cell_names_or_ids and not target_cell_names_or_ids:
        if request.args.get("with_sample_input", type=int, default=0):
            source_cell_names_or_ids = target_cell_names_or_ids = sample_input
        else:
            source_cell_names_or_ids = target_cell_names_or_ids = ""

    download = request.args.get("download", 0, type=int)
    log_activity(
        f"Generating NBLAST table for '{source_cell_names_or_ids}' -> '{target_cell_names_or_ids}' {download=}"
    )
    message = None

    if source_cell_names_or_ids or target_cell_names_or_ids:
        neuron_db = neuron_data_factory.get()
        root_ids = set()
        if source_cell_names_or_ids:
            root_ids |= set(neuron_db.search(search_query=source_cell_names_or_ids))
        if (
            target_cell_names_or_ids
            and target_cell_names_or_ids != source_cell_names_or_ids
        ):
            root_ids |= set(neuron_db.search(search_query=target_cell_names_or_ids))
        root_ids = sorted(root_ids)
        if not root_ids:
            return render_error(
                title="No matching cells found",
                message=f"Could not find any cells matching '{source_cell_names_or_ids} -> {target_cell_names_or_ids}'",
            )
        elif len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
            message = (
                f"{len(root_ids)} cells match your query. "
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
    log_activity(f"Rendering pathways from {source} to {target} with {min_syn_count=}")
    neuron_db = neuron_data_factory.get()
    for rid in [source, target]:
        if not neuron_db.is_in_dataset(rid):
            return render_error(
                message=f"Cell {rid} is not in the dataset.", title="Cell not found"
            )

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
    sample_input = "720575940626843194, 720575940631740497, 720575940608893891"
    source_cell_names_or_ids = request.args.get("source_cell_names_or_ids", "")
    target_cell_names_or_ids = request.args.get("target_cell_names_or_ids", "")
    min_syn_count = request.args.get("min_syn_count", type=int, default=MIN_SYN_COUNT)
    min_syn_count = max(min_syn_count, MIN_SYN_COUNT)

    if not source_cell_names_or_ids and not target_cell_names_or_ids:
        if request.args.get("with_sample_input", type=int, default=0):
            source_cell_names_or_ids = target_cell_names_or_ids = sample_input
        else:
            source_cell_names_or_ids = target_cell_names_or_ids = ""

    download = request.args.get("download", 0, type=int)
    log_activity(
        f"Generating path lengths table for '{source_cell_names_or_ids}' -> '{target_cell_names_or_ids}' {download=}"
    )
    message = None

    if source_cell_names_or_ids or target_cell_names_or_ids:
        neuron_db = neuron_data_factory.get()
        root_ids = set()
        if source_cell_names_or_ids:
            root_ids |= set(neuron_db.search(search_query=source_cell_names_or_ids))
        if (
            target_cell_names_or_ids
            and target_cell_names_or_ids != source_cell_names_or_ids
        ):
            root_ids |= set(neuron_db.search(search_query=target_cell_names_or_ids))
        root_ids = sorted(root_ids)
        if not root_ids:
            return render_error(
                title="No matching cells found",
                message=f"Could not find any cells matching '{source_cell_names_or_ids} -> {target_cell_names_or_ids}'",
            )
        elif len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
            message = (
                f"{len(root_ids)} cells match your query. "
                f"Fetching pathways for the first {MAX_NEURONS_FOR_DOWNLOAD // 2} matches."
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
            neuron_db=neuron_db,
            min_syn_count=min_syn_count,
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
    sample_input = "720575940626843194, 720575940631740497, 720575940608893891"
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    nt_type = request.args.get("nt_type", None)
    min_syn_cnt = request.args.get("min_syn_cnt", 5, type=int)
    connections_cap = request.args.get("cap", 20, type=int)
    reduce = request.args.get("reduce", 0, type=int)
    group_regions = request.args.get("group_regions", 0, type=int)
    hide_weights = request.args.get("hide_weights", 0, type=int)
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
        log_activity(
            (f"Downloading {download}" if download else "Generating")
            + " network for '{cell_names_or_ids}'"
        )

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

        contable = neuron_db.connections(
            ids=root_ids, nt_type=nt_type, min_syn_count=min_syn_cnt
        )
        if len(contable) <= 1:
            return render_error(
                f"Connections for {min_syn_cnt=}, {nt_type=} and Cell IDs {root_ids} are unavailable."
            )
        max_cap = min(len(contable), 200)
        if log_request:
            log_activity(
                f"Generated connections table for {len(root_ids)} cells with {connections_cap=}, {download=} {min_syn_cnt=} {nt_type=}"
            )
        if download:
            if len(contable) > 100000:
                return render_error(
                    message=f"The network generetad for your query is too large to download ({len(contable)} connections). Please refine the query and try again.",
                    title="Selected network is too large for download",
                )
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

        if not group_regions:  # exclude unknown region connections
            connection_table = [list(r) for r in contable if r[2] in REGIONS]
        else:
            connection_table = contable
        if reduce:

            def node_projection(nd):
                return f"{nd['class']}".replace(" neuron", "").replace("_", " ")

            projection_sets = defaultdict(set)
            for rid, nd in neuron_db.neuron_data.items():
                projection_sets[node_projection(nd)].add(rid)
            projection_set_fractions = {
                k: round(100 * len(v) / len(neuron_db.neuron_data))
                for k, v in projection_sets.items()
            }
            projections = {
                rid: f"{node_projection(nd)} {projection_set_fractions[node_projection(nd)]}%"
                for rid, nd in neuron_db.neuron_data.items()
            }

            def pil_projection(pil):
                return neuropil_hemisphere(pil)

            def project_row(row):
                return [
                    projections[row[0]],
                    projections[row[1]],
                    pil_projection(row[2]),
                ] + row[3:]

            connection_table = [project_row(r) for r in connection_table]
            name_getter = lambda x: f"Class {x}"
            caption_getter = lambda x: x
            tag_getter = None
            class_getter = None
            nt_type_getter = None
            size_getter = lambda x: 1 + int(x.replace("%", "").split()[-1])
            center_ids = list(
                set([r[0] for r in connection_table]).union(
                    [r[1] for r in connection_table]
                )
            )
        else:
            name_getter = lambda x: neuron_db.get_neuron_data(x)["name"]
            caption_getter = lambda x: neuron_db.get_neuron_caption(x)
            tag_getter = lambda x: neuron_db.get_neuron_data(x)["tag"]
            class_getter = lambda x: neuron_db.get_neuron_data(x)["class"]
            nt_type_getter = lambda x: neuron_db.get_neuron_data(x)["nt_type"]
            size_getter = lambda x: 1
            center_ids = root_ids

        network_html = make_graph_html(
            connection_table=connection_table,
            center_ids=center_ids,
            connections_cap=connections_cap,
            name_getter=name_getter,
            caption_getter=caption_getter,
            tag_getter=tag_getter,
            class_getter=class_getter,
            nt_type_getter=nt_type_getter,
            size_getter=size_getter,
            group_regions=group_regions,
            show_edge_weights=not hide_weights,
            show_warnings=log_request,
        )
        if headless:
            return network_html
        else:
            return render_template(
                "connectivity.html",
                cell_names_or_ids=cell_names_or_ids,
                min_syn_cnt=min_syn_cnt,
                nt_type=nt_type,
                cap=connections_cap,
                max_cap=max_cap,
                network_html=network_html,
                info_text=None,
                sample_input=None,
                message=message,
                data_versions=neuron_data_factory.available_versions(),
                data_version=data_version,
                reduce=reduce,
                group_regions=group_regions,
                hide_weights=hide_weights,
            )
    else:
        con_doc = FAQ_QA_KB["connectivity"]
        return render_template(
            "connectivity.html",
            cell_names_or_ids=cell_names_or_ids,
            min_syn_cnt=min_syn_cnt,
            nt_type=nt_type,
            cap=1,
            max_cap=1,
            network_html=None,
            info_text="With this tool you can specify one or more cells and visualize their connectivity network.<br>"
            f"{con_doc['a']}",
            sample_input=sample_input,
            message=None,
            data_versions=neuron_data_factory.available_versions(),
            data_version=data_version,
            reduce=reduce,
            group_regions=group_regions,
            hide_weights=hide_weights,
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


@app.route("/flywire_neuropil_url")
@request_wrapper
def flywire_neuropil_url():
    selected = request.args.get("selected")
    segment_ids = [REGIONS[r][0] for r in selected.split(",") if r in REGIONS]
    url = nglui.url_for_neuropils(segment_ids)
    return ngl_redirect_with_browser_check(ngl_url=url)


@app.route("/neuropils")
@request_wrapper
@require_data_access
def neuropils():
    landing = False
    selected = request.args.get("selected")
    log_activity(f"Rendering neuropils page with {selected=}")
    if selected:
        selected = selected.strip(",")
        selected_ids = [r for r in selected.split(",") if r]
        if len(selected_ids) > 1:
            caption = ", ".join([NEUROPIL_DESCRIPTIONS[r] for r in selected_ids])
        else:
            caption = NEUROPIL_DESCRIPTIONS[selected_ids[0]]
        selected = ",".join(selected_ids)
    else:
        selected = ",".join(REGIONS.keys())
        landing = True
        caption = "All neuropils"

    return render_template(
        "neuropils.html",
        selected=selected,
        REGIONS_JSON=REGIONS_JSON,
        caption=caption,
        landing=landing,
    )


@app.route("/synapse_density")
@request_wrapper
@require_data_access
def synapse_density():
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    normalized = request.args.get("normalized", type=int, default=0)
    directed = request.args.get("directed", type=int, default=0)
    group_by = request.args.get("group_by")
    log_activity(
        f"Rendering synapse_density page with {data_version=} {normalized=} {directed=} {group_by=}"
    )
    return _synapse_density_cached(
        data_version=data_version,
        normalized=normalized,
        directed=directed,
        group_by=group_by,
    )


@lru_cache
def _synapse_density_cached(data_version, normalized, directed, group_by):
    neuron_db = neuron_data_factory.get(data_version)

    num_cells = len(neuron_db.neuron_data)
    group_to_rids = defaultdict(set)
    rid_to_class = {}

    def class_group_name(nd):
        return (
            nd["class"]
            .lower()
            .replace(" neuron", "")
            .replace("ending", "")
            .replace("ection", "")
            .replace("optic", "opt")
            .replace("central", "centr")
            .replace("bilateral", "bi")
            .replace("visual", "vis")
            .replace("_", " ")
            .capitalize()
        )

    def nt_type_group_name(nd):
        return NEURO_TRANSMITTER_NAMES.get(nd["nt_type"], "unknown").capitalize()

    group_by_options = {
        "Neuron Class": class_group_name,
        "NT Type": nt_type_group_name,
    }
    if not group_by:
        group_by = list(group_by_options.keys())[0]
    group_func = group_by_options[group_by]

    all_groups = "All"
    for v in neuron_db.neuron_data.values():
        cl = group_func(v)
        rid = v["root_id"]
        group_to_rids[cl].add(rid)
        group_to_rids[all_groups].add(rid)
        rid_to_class[rid] = cl

    tot_syn_cnt = 0
    group_to_group_syn_cnt = defaultdict(int)

    def update_syn_counts(cf, ct, syn):
        group_to_group_syn_cnt[f"{cf}:{ct}"] += syn
        group_to_group_syn_cnt[f"{all_groups}:{ct}"] += syn
        group_to_group_syn_cnt[f"{cf}:{all_groups}"] += syn
        group_to_group_syn_cnt[f"{all_groups}:{all_groups}"] += syn

    for r in neuron_db.connection_rows:
        assert r[0] != r[1]
        clfrom = rid_to_class[r[0]]
        clto = rid_to_class[r[1]]
        tot_syn_cnt += r[3]
        update_syn_counts(clfrom, clto, r[3])
        if not directed:
            update_syn_counts(clto, clfrom, r[3])
    if not directed:  # reverse double counting
        group_to_group_syn_cnt = {
            k: round(v / 2) for k, v in group_to_group_syn_cnt.items()
        }

    tot_density = tot_syn_cnt / (num_cells * (num_cells - 1))
    group_to_group_density = {}
    for k, v in group_to_group_syn_cnt.items():
        if normalized:
            parts = k.split(":")
            sizefrom = (
                len(group_to_rids[parts[0]]) if parts[0] != all_groups else num_cells
            )
            sizeto = (
                len(group_to_rids[parts[1]]) if parts[1] != all_groups else num_cells
            )
            density = v / (sizefrom * sizeto)
            density /= tot_density
        else:
            density = v
        group_to_group_density[k] = density

    def heatmap_color(value, min_value, mid_value, max_value):
        cold_color = "#AAAAAA"
        hot_color = "#00FF00"
        if value <= mid_value:
            color = cold_color
            offset = math.sqrt((mid_value - value) / (mid_value - min_value))
        else:
            color = hot_color
            offset = math.sqrt((value - mid_value) / (max_value - mid_value))

        opacity = round(max(0, min(99, offset * 100)))
        return f"{color}{opacity}"

    classes = sorted(group_to_rids.keys(), key=lambda x: -len(group_to_rids[x]))

    def class_caption(cln):
        return f"<b>{cln}</b>&nbsp;<small>{round(100 * len(group_to_rids[cln]) / num_cells)}%</small>"

    def density_caption(d):
        if normalized:
            pct_diff = round(100 * (density - 1))
            if pct_diff == 0:
                return "+0% (baseline)"
            return ("+" if pct_diff >= 0 else "") + "{:,}".format(pct_diff) + "%"
        else:
            pct = round(100 * d / tot_syn_cnt)
            return "{:,}".format(d) + f"<br><small>{pct}%</small>"

    table = [["from \\ to"] + [class_caption(c) for c in classes]]
    min_density = min(group_to_group_density.values())
    max_density = max(group_to_group_density.values())
    mid_density = 1 if normalized else tot_syn_cnt / len(group_to_group_density)
    for c1 in classes:
        row = [(class_caption(c1), 0)]
        for c2 in classes:
            density = group_to_group_density.get(f"{c1}:{c2}", 0)
            row.append(
                (
                    density_caption(density),
                    heatmap_color(
                        value=density,
                        min_value=min_density,
                        mid_value=mid_density,
                        max_value=max_density,
                    ),
                )
            )
        table.append(row)

    return render_template(
        "synapse_density.html",
        table=table,
        total_density=tot_density,
        directed=directed,
        normalized=normalized,
        group_by=group_by,
        group_by_options=list(group_by_options.keys()),
    )
