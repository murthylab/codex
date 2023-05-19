import json
import re
from datetime import datetime
import requests


from flask import (
    render_template,
    request,
    redirect,
    Response,
    url_for,
    Blueprint,
    session,
)
from user_agents import parse as parse_ua

from src.blueprints.base import (
    request_wrapper,
    require_data_access,
    activity_suffix,
    render_error,
    warning_with_redirect,
    render_info,
)
from src.configuration import (
    MAX_NEURONS_FOR_DOWNLOAD,
    MIN_SYN_THRESHOLD,
    MAX_NODES_FOR_PATHWAY_ANALYSIS,
)
from src.data.brain_regions import (
    REGIONS,
    NEUROPIL_DESCRIPTIONS,
    REGIONS_JSON,
)
from src.data.faq_qa_kb import FAQ_QA_KB
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.neuron_data_initializer import NETWORK_GROUP_BY_ATTRIBUTES
from src.data.optic_lobe_cell_types import (
    COLUMNAR_CELL_TYPE_GROUPS,
    COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR,
    COLUMNAR_CELL_SUPER_CLASSES,
)
from src.data.structured_search_filters import (
    OP_PATHWAYS,
    parse_search_query,
    OP_IN,
)
from src.data.sorting import sort_search_results, SORT_BY_OPTIONS
from src.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
)
from src.service.cell_details import cached_cell_details
from src.service.network import compile_network_html
from src.service.search import pagination_data, DEFAULT_PAGE_SIZE
from src.service.stats import stats_cached, leaderboard_cached
from src.service.heatmaps import heatmap_data
from src.utils import nglui
from src.utils.cookies import (
    fetch_flywire_user_id,
    fetch_user_email,
    fetch_flywire_token,
)
from src.utils.formatting import (
    synapse_table_to_csv_string,
    synapse_table_to_json_dict,
    highlight_annotations,
    nanos_to_formatted_micros,
    nanometer_to_flywire_coordinates,
    display,
    percentage,
)
from src.utils.graph_algos import distance_matrix
from src.utils.logging import (
    log_activity,
    format_link,
    log,
    log_user_help,
    log_warning,
    log_error,
)
from src.utils.formatting import can_be_flywire_root_id
from src.utils.pathway_vis import pathway_chart_data_rows
from src.utils.prm import cell_identification_url
from src.utils.thumbnails import url_for_skeleton
from src.data.structured_search_filters import get_advanced_search_data
from src.data.braincircuits import neuron2line

app = Blueprint("app", __name__, url_prefix="/app")


@app.context_processor
def jinja_utils():
    return dict(display=display, nanos_to_formatted_micros=nanos_to_formatted_micros)


@app.route("/stats")
@request_wrapper
@require_data_access
def stats():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)

    log_activity(f"Generating stats {activity_suffix(filter_string, data_version)}")
    (
        filtered_root_id_list,
        num_items,
        hint,
        data_stats,
        data_charts,
        dynamic_ranges,
    ) = stats_cached(
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
        data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        advanced_search_data=get_advanced_search_data(
            current_query=filter_string, dynamic_ranges=dynamic_ranges
        ),
    )


@app.route("/leaderboard")
@request_wrapper
@require_data_access
def leaderboard():
    query = request.args.get("filter_string", "")
    log_activity("Loading Leaderboard" + (f", query: {query}" if query else ""))
    labeled_cells_caption, leaderboard_data = leaderboard_cached(
        query=query, data_version=DEFAULT_DATA_SNAPSHOT_VERSION
    )
    return render_template(
        "leaderboard.html",
        labeled_cells_caption=labeled_cells_caption,
        data_stats=leaderboard_data,
        filter_string=query,
    )


@app.route("/explore")
@request_wrapper
@require_data_access
def explore():
    log_activity("Loading Explore page")
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    top_values = request.args.get("top_values", type=int, default=15)
    return render_template(
        "explore.html",
        data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
        data_version=data_version,
        top_values=top_values,
        categories=NeuronDataFactory.instance()
        .get(data_version)
        .categories(top_values=top_values),
    )


def render_neuron_list(
    data_version,
    template_name,
    filtered_root_id_list,
    filter_string,
    case_sensitive,
    whole_word,
    page_number,
    page_size,
    sort_by,
    hint,
    extra_data,
):
    neuron_db = NeuronDataFactory.instance().get(data_version)
    pagination_info, page_ids, page_size, page_size_options = pagination_data(
        items_list=filtered_root_id_list, page_number=page_number, page_size=page_size
    )

    display_data = [neuron_db.get_neuron_data(i) for i in page_ids]
    skeleton_thumbnail_urls = {
        nd["root_id"]: (
            url_for_skeleton(nd["root_id"], file_type="png"),
            url_for_skeleton(nd["root_id"], file_type="gif"),
        )
        for nd in display_data
    }
    highlighted_terms = {}
    for nd in display_data:
        # Only highlight from free-form search tokens (and not structured search attributes)
        psq = parse_search_query(filter_string)
        search_terms = psq[1] + [stq["rhs"] for stq in psq[2] or []]
        # highlight all displayed annotations
        terms_to_annotate = set()
        for attr_name in [
            "root_id",
            "label",
            "side",
            "flow",
            "super_class",
            "class",
            "sub_class",
            "cell_type",
            "hemibrain_type",
            "hemilineage",
            "nt_type",
            "nerve",
        ]:
            if nd[attr_name]:
                if isinstance(nd[attr_name], list):
                    terms_to_annotate |= set(nd[attr_name])
                else:
                    terms_to_annotate.add(nd[attr_name])
        highlighted_terms.update(highlight_annotations(search_terms, terms_to_annotate))

    return render_template(
        template_name_or_list=template_name,
        display_data=display_data,
        highlighted_terms=highlighted_terms,
        skeleton_thumbnail_urls=skeleton_thumbnail_urls,
        # If num results is small enough to pass to browser, pass it to allow copying root IDs to clipboard.
        # Otherwise it will be available as downloadable file.
        root_ids_str=",".join([str(ddi) for ddi in filtered_root_id_list])
        if len(filtered_root_id_list) <= MAX_NEURONS_FOR_DOWNLOAD
        else [],
        num_items=len(filtered_root_id_list),
        searched_for_root_id=can_be_flywire_root_id(filter_string),
        pagination_info=pagination_info,
        page_size=page_size,
        page_size_options=page_size_options,
        filter_string=filter_string,
        hint=hint,
        data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        extra_data=extra_data,
        sort_by=sort_by,
        sort_by_options=SORT_BY_OPTIONS,
        advanced_search_data=get_advanced_search_data(
            current_query=filter_string, dynamic_ranges=neuron_db.dynamic_ranges()
        ),
        multi_val_attrs=neuron_db.multi_val_attrs(filtered_root_id_list),
        non_uniform_labels=neuron_db.non_uniform_labels(
            page_ids=page_ids, all_ids=filtered_root_id_list
        ),
    )


@app.route("/search", methods=["GET"])
@request_wrapper
@require_data_access
def search():
    filter_string = request.args.get("filter_string", "")
    page_number = int(request.args.get("page_number", 1))
    page_size = int(request.args.get("page_size", DEFAULT_PAGE_SIZE))
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    sort_by = request.args.get("sort_by")
    neuron_db = NeuronDataFactory.instance().get(data_version)
    hint = None
    extra_data = None
    log(
        f"Loading search page {page_number} {activity_suffix(filter_string, data_version)}"
    )
    filtered_root_id_list = neuron_db.search(
        filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    if filtered_root_id_list:
        if len(filtered_root_id_list) == 1:
            if filter_string == str(filtered_root_id_list[0]):
                log_activity("Single cell match, redirecting to cell details")
                return redirect(
                    url_for(
                        "app.cell_details",
                        root_id=filtered_root_id_list[0],
                        data_version=data_version,
                    )
                )

        log_activity(
            f"Loaded {len(filtered_root_id_list)} search results for page {page_number} "
            f"{activity_suffix(filter_string, data_version)}"
        )
        filtered_root_id_list, extra_data = sort_search_results(
            query=filter_string,
            ids=filtered_root_id_list,
            output_sets=neuron_db.output_sets(),
            label_count_getter=lambda x: len(neuron_db.get_neuron_data(x)["label"]),
            nt_type_getter=lambda x: neuron_db.get_neuron_data(x)["nt_type"],
            morphology_cluster_getter=lambda x: neuron_db.get_neuron_data(x)[
                "morphology_cluster"
            ],
            synapse_neuropil_count_getter=lambda x: len(
                neuron_db.get_neuron_data(x)["input_neuropils"]
            )
            + len(neuron_db.get_neuron_data(x)["output_neuropils"]),
            size_getter=lambda x: neuron_db.get_neuron_data(x)["size_nm"],
            partner_count_getter=lambda x: len(neuron_db.output_sets()[x])
            + len(neuron_db.input_sets()[x]),
            similar_shape_cells_getter=neuron_db.get_similar_shape_cells,
            similar_connectivity_cells_getter=neuron_db.get_similar_connectivity_cells,
            connections_getter=lambda x: neuron_db.cell_connections(x),
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
        page_size=page_size,
        sort_by=sort_by,
        hint=hint,
        extra_data=extra_data,
    )


@app.route("/download_search_results")
@request_wrapper
@require_data_access
def download_search_results():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = NeuronDataFactory.instance().get(data_version)

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
        "label",
        "name",
        "nt_type",
        "flow",
        "super_class",
        "class",
        "sub_class",
        "cell_type",
        "hemibrain_type",
        "hemilineage",
        "nerve",
        "side",
        "input_synapses",
        "output_synapses",
        "hemisphere_fingerprint",
        "morphology_cluster",
        "connectivity_cluster",
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
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = NeuronDataFactory.instance().get(data_version)

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
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    neuron_db = NeuronDataFactory.instance().get(data_version)

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


@app.route("/optic_lobe_tagging")
@request_wrapper
@require_data_access
def optic_lobe_tagging():
    log_activity("Loading optic lobe tags page")
    examples_for = request.args.get("examples_for")
    candidates_for = request.args.get("candidates_for")
    side = request.args.get("side")

    def check_known_type(tp):
        if tp not in COLUMNAR_CELL_TYPE_GROUPS:
            raise ValueError(
                f"Type '{tp} is not a valid optic lobe type. Pick one of {COLUMNAR_CELL_TYPE_GROUPS}"
            )

    if examples_for:
        check_known_type(examples_for)
        query = f"marker == {examples_for}"
        if side:
            query += f" && side == {side}"
        return redirect(url_for("app.search", filter_string=query, whole_word=1))
    elif candidates_for:
        check_known_type(candidates_for)
        query = f"marker == candidate:{candidates_for}"
        if side:
            query += f" && side == {side}"
        return redirect(url_for("app.search", filter_string=query))
    else:
        neuron_db = NeuronDataFactory.instance().get()

        def make_data(t):
            def with_percentage(c, tot):
                return f"{c} ({percentage(int(c), int(tot))})"

            return {
                "type_name": t,
                "image_url": url_for("base.asset", filename=f"columnar_cells/{t}.jpg"),
                "goal_count_left": COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR[t]["left"],
                "goal_count_right": COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR[t]["right"],
                "tagged_count_left": with_percentage(
                    neuron_db.meta_data[f"{t}_tagged_count_left"],
                    COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR[t]["left"],
                ),
                "tagged_count_right": with_percentage(
                    neuron_db.meta_data[f"{t}_tagged_count_right"],
                    COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR[t]["right"],
                ),
                "candidate_count_left": neuron_db.meta_data[
                    f"{t}_candidate_count_left"
                ],
                "candidate_count_right": neuron_db.meta_data[
                    f"{t}_candidate_count_right"
                ],
                "examples_url_left": url_for(
                    "app.optic_lobe_tagging", examples_for=t, side="left"
                ),
                "examples_url_right": url_for(
                    "app.optic_lobe_tagging", examples_for=t, side="right"
                ),
                "candidates_url_left": url_for(
                    "app.optic_lobe_tagging", candidates_for=t, side="left"
                ),
                "candidates_url_right": url_for(
                    "app.optic_lobe_tagging", candidates_for=t, side="right"
                ),
            }

        ol_type_data = [make_data(t) for t in COLUMNAR_CELL_TYPE_GROUPS]
        total_goal_count, total_tagged_count = 0, 0
        for t, q in COLUMNAR_CELL_TYPE_TARGET_QUANTITIES_LR.items():
            total_goal_count += q["left"] + q["right"]
            total_tagged_count += (
                neuron_db.meta_data[f"{t}_tagged_count_left"]
                + neuron_db.meta_data[f"{t}_tagged_count_right"]
            )
        total_tagged_percent = percentage(total_tagged_count, total_goal_count)

        return render_template(
            "optic_lobe_tagging.html",
            ol_type_data=ol_type_data,
            total_goal_count=display(total_goal_count),
            total_tagged_count=display(total_tagged_count),
            total_tagged_percent=total_tagged_percent,
            leaderboard_url=url_for(
                "app.leaderboard",
                filter_string=f"super_class {OP_IN} {','.join(COLUMNAR_CELL_SUPER_CLASSES)}",
            ),
        )


@app.route("/flywire_url")
@request_wrapper
def flywire_url():
    root_ids = [int(rid) for rid in request.args.getlist("root_ids")]
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
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
    min_supported = {
        "Chrome": 51,
        "Edge": 51,
        "Firefox": 46,
        "Safari": 15,
        "Opera": 95,
    }
    ua = parse_ua(str(request.user_agent))
    # browser_family can contain other parts, e.g. "Mobile Safari", or "Chrome Mobile". Use substring match.
    browser = None
    bfl = ua.browser.family.lower()
    for k in min_supported.keys():
        if k.lower() in bfl:
            browser = k
            break
    if browser in min_supported and ua.browser.version[0] >= min_supported[browser]:
        return redirect(ngl_url, code=302)
    else:
        supported = ", ".join(
            [f"{browser} >= {version}" for browser, version in min_supported.items()]
        )
        return warning_with_redirect(
            title="Browser not supported",
            message=f"Neuroglancer (3D neuron rendering) may not be supported on your browser {ua.get_browser()}. Try: {supported}",
            redirect_url=ngl_url,
            redirect_button_text="Proceed anyway",
        )


@app.route("/cell_coordinates/<path:data_version>/<path:cell_id>")
@request_wrapper
@require_data_access
def cell_coordinates(data_version, cell_id):
    log_activity(
        f"Loading coordinates for cell {cell_id} from data version {data_version}"
    )
    neuron_db = NeuronDataFactory.instance().get(data_version)
    nd = neuron_db.get_neuron_data(cell_id)
    return f"<h2>Supervoxel IDs and coordinates for {cell_id}</h2>" + "<br>".join(
        [
            f"Supervoxel ID: {s}, nanometer coordinates: {c}, FlyWire coordinates: {nanometer_to_flywire_coordinates(c)}"
            for c, s in zip(nd["position"], nd["supervoxel_id"])
        ]
    )


@app.route("/cell_details", methods=["GET", "POST"])
@request_wrapper
@require_data_access
def cell_details():
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    reachability_stats = request.args.get("reachability_stats", 0, type=int)
    neuron_db = NeuronDataFactory.instance().get(data_version)

    if request.method == "POST":
        annotation_text = request.form.get("annotation_text")
        annotation_coordinates = request.form.get("annotation_coordinates")
        annotation_cell_id = request.form.get("annotation_cell_id")
        if not annotation_coordinates:
            ndata = neuron_db.get_neuron_data(annotation_cell_id)
            annotation_coordinates = ndata["position"][0] if ndata["position"] else None
        fw_user_id = fetch_flywire_user_id(session, required=True)
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
            log_activity("Generated random cell detail page")
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
        log_activity("Generated empty cell detail page")
        return render_template("cell_details.html")
    log(f"Generating neuron info {activity_suffix(root_id, data_version)}")
    dct = cached_cell_details(
        cell_names_or_id=cell_names_or_id,
        root_id=root_id,
        neuron_db=neuron_db,
        data_version=data_version,
        reachability_stats=reachability_stats,
    )
    dct["min_syn_threshold"] = MIN_SYN_THRESHOLD
    log_activity(
        f"Generated neuron info for {root_id} with {len(dct['cell_attributes']) + len(dct['cell_annotations']) + len(dct['related_cells'])} items"
    )
    return render_template("cell_details.html", **dct)


@app.route("/pathways")
@request_wrapper
@require_data_access
def pathways():
    source = request.args.get("source_cell_id", type=int)
    target = request.args.get("target_cell_id", type=int)
    min_syn_count = request.args.get("min_syn_count", type=int, default=0)
    log_activity(f"Rendering pathways from {source} to {target} with {min_syn_count=}")
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    neuron_db = NeuronDataFactory.instance().get(version=data_version)
    for rid in [source, target]:
        if not neuron_db.is_in_dataset(rid):
            return render_error(
                message=f"Cell {rid} is not in the dataset.", title="Cell not found"
            )
    root_ids = [source, target]

    layers, data_rows = pathway_chart_data_rows(
        source=source,
        target=target,
        neuron_db=neuron_db,
        min_syn_count=min_syn_count,
    )
    cons = []
    for data_row in data_rows:
        cons.append([data_row[0], data_row[1], "", data_row[2], ""])
    return compile_network_html(
        center_ids=root_ids,
        contable=cons,
        neuron_db=neuron_db,
        show_regions=0,
        connections_cap=0,
        hide_weights=0,
        log_request=True,
        layers=layers,
        page_title="Pathways",
    )


@app.route("/path_length")
@request_wrapper
@require_data_access
def path_length():
    source_cell_names_or_ids = request.args.get("source_cell_names_or_ids", "")
    target_cell_names_or_ids = request.args.get("target_cell_names_or_ids", "")
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    min_syn_count = request.args.get("min_syn_count", type=int, default=0)
    download = request.args.get("download", 0, type=int)

    messages = []

    if source_cell_names_or_ids and target_cell_names_or_ids:
        neuron_db = NeuronDataFactory.instance().get(data_version)

        if source_cell_names_or_ids == target_cell_names_or_ids == "__sample_cells__":
            root_ids_src = neuron_db.search(search_query="gustatory")[:3]
            root_ids_target = neuron_db.search(search_query="motor")[:5]
            source_cell_names_or_ids = ", ".join([str(rid) for rid in root_ids_src])
            target_cell_names_or_ids = ", ".join([str(rid) for rid in root_ids_target])
            log_activity("Generating path lengths table for sample cells")
        else:
            root_ids_src = neuron_db.search(search_query=source_cell_names_or_ids)
            root_ids_target = neuron_db.search(search_query=target_cell_names_or_ids)
            log_activity(
                f"Generating path lengths table for '{source_cell_names_or_ids}' -> '{target_cell_names_or_ids}' "
                f"with {min_syn_count=} and {download=}"
            )
        if not root_ids_src:
            return render_error(
                title="No matching source cells",
                message=f"Could not find any cells matching '{source_cell_names_or_ids}'",
            )
        if not root_ids_target:
            return render_error(
                title="No matching target cells",
                message=f"Could not find any cells matching '{target_cell_names_or_ids}'",
            )

        if len(root_ids_src) > MAX_NODES_FOR_PATHWAY_ANALYSIS:
            messages.append(
                f"{display(len(root_ids_src))} source cells match your query. "
                f"Fetching pathways for the first {MAX_NODES_FOR_PATHWAY_ANALYSIS} sources."
            )
            root_ids_src = root_ids_src[:MAX_NODES_FOR_PATHWAY_ANALYSIS]
        if len(root_ids_target) > MAX_NODES_FOR_PATHWAY_ANALYSIS:
            messages.append(
                f"{display(len(root_ids_target))} target cells match your query. "
                f"Fetching pathways for the first {MAX_NODES_FOR_PATHWAY_ANALYSIS} targets."
            )
            root_ids_target = root_ids_target[:MAX_NODES_FOR_PATHWAY_ANALYSIS]

        matrix = distance_matrix(
            sources=root_ids_src,
            targets=root_ids_target,
            neuron_db=neuron_db,
            min_syn_count=min_syn_count,
        )
        log_activity(
            f"Generated path lengths table of length {len(matrix)}. "
            f"{len(root_ids_src)=}, {len(root_ids_target)=}, {min_syn_count=}, {download=}"
        )
        if len(matrix) <= 1:
            log_error(
                f"No paths found from {source_cell_names_or_ids} to {target_cell_names_or_ids} with synapse "
                f"threshold {min_syn_count}."
            )
    else:
        matrix = []
        if source_cell_names_or_ids or target_cell_names_or_ids:
            messages.append("Please specify both source and target cell queries.")

    if matrix:
        if download:
            fname = "path_lengths.csv"
            return Response(
                "\n".join([",".join([str(r) for r in row]) for row in matrix]),
                mimetype="text/csv",
                headers={"Content-disposition": f"attachment; filename={fname}"},
            )
        else:
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
                        if not min_syn_count:
                            q = f"{from_root_id} {OP_PATHWAYS} {to_root_id}"
                            slink = f'<a href="{url_for("app.search", filter_string=q)}" target="_blank" ><i class="fa-solid fa-list"></i> View cells as list</a>'
                        else:
                            slink = ""  # search by pathways is only available for default threshold
                        plink = f'<a href="{url_for("app.pathways", source_cell_id=from_root_id, target_cell_id=to_root_id, min_syn_count=min_syn_count)}" target="_blank" ><i class="fa-solid fa-route"></i> View Pathways chart</a>'
                        r[j] = f"{val} hops <br> <small>{plink} <br> {slink}</small>"
                    elif val == 0:
                        r[j] = ""
                    elif val == -1:
                        r[j] = '<span style="color:grey">no path</span>'

            for j, val in enumerate(matrix[0]):
                if j > 0:
                    matrix[0][
                        j
                    ] = f'<a href="{url_for("app.search", filter_string="id == " + str(val))}">{neuron_db.get_neuron_data(int(val))["name"]}</a><br><small>{val}</small>'

    info_text = (
        "With this tool you can specify one or more source cells + one or more target cells, set a "
        "minimum synapse threshold per connection, and get a matrix with shortest path lengths for all "
        "source/target pairs. From there, you can inspect / visualize the pathways between any pair of "
        f"cells in detail.<br>{FAQ_QA_KB['paths']['a']}"
    )

    return render_template(
        "path_lengths.html",
        source_cell_names_or_ids=source_cell_names_or_ids,
        target_cell_names_or_ids=target_cell_names_or_ids,
        collect_min_syn_count=True,
        min_syn_count=min_syn_count,
        matrix=matrix,
        download_url=url_for(
            "app.path_length",
            download=1,
            source_cell_names_or_ids=source_cell_names_or_ids,
            target_cell_names_or_ids=target_cell_names_or_ids,
        ),
        info_text=info_text,
        messages=messages,
    )


@app.route("/connectivity")
@request_wrapper
@require_data_access
def connectivity():
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    nt_type = request.args.get("nt_type", None)
    min_syn_cnt = request.args.get("min_syn_cnt", default=0, type=int)
    connections_cap = request.args.get("cap", default=50, type=int)
    group_by = request.args.get("group_by", default="")
    show_regions = request.args.get("show_regions", default=0, type=int)
    include_partners = request.args.get("include_partners", default=0, type=int)
    hide_weights = request.args.get("hide_weights", default=0, type=int)
    cell_names_or_ids = request.args.get("cell_names_or_ids", "")
    download = request.args.get("download")
    # headless network view (no search box / nav bar etc.)
    headless = request.args.get("headless", default=0, type=int)
    log_request = request.args.get(
        "log_request", default=0 if headless else 1, type=int
    )

    message = None

    group_by_options = {"": "Individual Cells"}
    group_by_options.update({k: display(k) for k in NETWORK_GROUP_BY_ATTRIBUTES})
    group_by_options.update(
        {
            f"{k}_and_side": f"{display(k)} & side"
            for k in NETWORK_GROUP_BY_ATTRIBUTES
            if k != "side"
        }
    )
    if group_by.endswith("_and_side"):
        group_by_attribute_name = group_by[: -len("_and_side")]
        split_groups_by_side = True
    else:
        group_by_attribute_name = group_by
        split_groups_by_side = False

    if not cell_names_or_ids:
        con_doc = FAQ_QA_KB["connectivity"]
        return render_template(
            "connectivity.html",
            cell_names_or_ids=cell_names_or_ids,
            min_syn_cnt=min_syn_cnt,
            nt_type=nt_type,
            network_html=None,
            info_text="With this tool you can specify one or more cells and visualize their connectivity network.<br>"
            f"{con_doc['a']}",
            message=None,
            data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
            group_by_options=group_by_options,
            group_by=group_by,
            data_version=data_version,
            show_regions=show_regions,
            hide_weights=hide_weights,
            num_matches=0,
        )
    else:
        neuron_db = NeuronDataFactory.instance().get(data_version)
        if cell_names_or_ids == "__sample_cells__":
            root_ids = [
                720575940623725972,
                720575940630057979,
                720575940633300148,
                720575940644300323,
                720575940640176848,
                720575940627796298,
            ]
            root_ids = [r for r in root_ids if neuron_db.is_in_dataset(r)]
            cell_names_or_ids = ", ".join([str(rid) for rid in root_ids])
            log_activity("Generating connectivity network for sample cells")
        else:
            root_ids = neuron_db.search(search_query=cell_names_or_ids)
            if log_request:
                log_activity(
                    ("Downloading " if download else "Generating ")
                    + f"network for '{cell_names_or_ids}'"
                )

        if not root_ids:
            return render_error(
                title="No matching cells found",
                message=f"Could not find any cells matching '{cell_names_or_ids}'",
            )
        elif len(root_ids) == 1:
            # if only one match found, show some connections to it's partners (instead of lonely point)
            include_partners = True

        if len(root_ids) == 1 and not nt_type and not min_syn_cnt:
            # this simplest case (also used in cell details page) can be handled more efficiently
            contable = neuron_db.cell_connections(root_ids[0])
        else:
            contable = neuron_db.connections(
                ids=root_ids,
                nt_type=nt_type,
                induced=include_partners == 0,
                min_syn_count=min_syn_cnt,
            )
        if log_request:
            log_activity(
                f"Generated connections table for {len(root_ids)} cells with {connections_cap=}, {download=} {min_syn_cnt=} {nt_type=}"
            )
        if download:
            if len(contable) > 100000:
                return render_error(
                    message=f"The network generatad for your query is too large to download ({len(contable)} connections). Please refine the query and try again.",
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
                        "Content-disposition": "attachment; filename=connections.json"
                    },
                )
            else:
                return Response(
                    synapse_table_to_csv_string(contable),
                    mimetype="text/csv",
                    headers={
                        "Content-disposition": "attachment; filename=connections.csv"
                    },
                )

        network_html = compile_network_html(
            center_ids=root_ids,
            contable=contable,
            neuron_db=neuron_db,
            show_regions=show_regions,
            group_by_attribute_name=group_by_attribute_name,
            split_groups_by_side=split_groups_by_side,
            connections_cap=connections_cap,
            hide_weights=hide_weights,
            log_request=log_request,
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
                max_cap=200,
                network_html=network_html,
                info_text=None,
                message=message,
                data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
                data_version=data_version,
                group_by_options=group_by_options,
                group_by=group_by,
                show_regions=show_regions,
                include_partners=include_partners,
                hide_weights=hide_weights,
                num_matches=len(root_ids),
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
        caption = display(caption)
        selected = ",".join(selected_ids)
    else:
        selected = ",".join(REGIONS.keys())
        landing = True
        caption = '<i class="fa-solid fa-arrow-down"></i> use links to select regions <i class="fa-solid fa-arrow-down"></i>'

    return render_template(
        "neuropils.html",
        selected=selected,
        REGIONS_JSON=REGIONS_JSON,
        caption=caption,
        landing=landing,
    )


@app.route("/heatmaps")
@request_wrapper
@require_data_access
def heatmaps():
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    group_by = request.args.get("group_by")
    count_type = request.args.get("count_type")
    log_activity(f"Rendering heatmaps page with {data_version=} {group_by=}")

    dct = heatmap_data(
        neuron_db=NeuronDataFactory.instance().get(data_version),
        group_by=group_by,
        count_type=count_type,
    )

    return render_template("heatmaps.html", **dct)


@app.route("/matching_lines/")
@request_wrapper
@require_data_access
def matching_lines():
    segment_id = request.args.get("segment_id")
    target_library = request.args.get("target_library")
    email = fetch_user_email(session)
    cave_token = fetch_flywire_token(session)
    log_activity(f"Calling BrainCircuits API with {segment_id=} {target_library=}")
    result = None
    try:
        result = neuron2line([segment_id], target_library, email, cave_token)
        log_activity(f"BrainCircuits API call returned {result=}")
    except requests.HTTPError as e:
        log_error(
            f"BrainCircuits API call failed with {e=}. Did you set BRAINCIRCUITS_TOKEN?"
        )
        return {
            "error": "BrainCircuits API call failed. Did you set BRAINCIRCUITS_TOKEN?"
        }, e.response.status_code
    except Exception as e:
        log_error(f"BrainCircuits API call failed with error: {e=}")
        return {"error": str(e)}, 500
    result["email"] = email
    return result


@app.route("/my_labels/")
@request_wrapper
@require_data_access
def my_labels():
    log_activity("Fetching my labeled cells")
    neuron_db = NeuronDataFactory.instance().get()
    user_id = fetch_flywire_user_id(session, required=True)
    rids = []
    for rid in neuron_db.cell_ids_with_label_data():
        for ld_dict in neuron_db.get_label_data(rid):
            if ld_dict["user_id"] == user_id:
                rids.append(rid)
                break
    if not rids:
        return render_error(
            title="Not found",
            message=f"The current data snapshot does not contain any cells labeled by user ID {user_id} ({fetch_user_email(session)})",
        )
    else:
        rids_str = ", ".join([str(r) for r in rids])
        if len(rids_str) <= 1000:
            return redirect(url_for("app.search", filter_string=rids_str))
        else:
            return render_info(
                title=f"Cells labeled by user ID {user_id} ({fetch_user_email(session)})",
                message=f"{rids_str}",
            )
