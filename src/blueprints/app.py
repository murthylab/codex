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

from src.blueprints.base import (
    request_wrapper,
    require_data_access,
    activity_suffix,
    render_error,
    warning_with_redirect,
)
from src.configuration import MIN_SYN_COUNT, MAX_NEURONS_FOR_DOWNLOAD
from src.data.brain_regions import (
    REGIONS,
    NEUROPIL_DESCRIPTIONS,
    REGIONS_JSON,
)
from src.data.faq_qa_kb import FAQ_QA_KB
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.structured_search_filters import (
    OP_PATHWAYS,
    parse_search_query,
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
from src.service.synapse import synapse_density_cached
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
    trim_long_tokens,
)
from src.utils.graph_algos import distance_matrix
from src.utils.logging import (
    log_activity,
    format_link,
    user_agent,
    log,
    log_user_help,
    log_warning,
    log_error,
)
from src.utils.nglui import can_be_flywire_root_id
from src.utils.pathway_vis import pathway_chart_data_rows
from src.utils.prm import cell_identification_url
from src.utils.thumbnails import url_for_skeleton
from src.data.structured_search_filters import get_advanced_search_data
from src.data.braincircuits import neuron2line

app = Blueprint("app", __name__, url_prefix="/app")


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
    log_activity("Loading Leaderboard")
    return render_template("leaderboard.html", data_stats=leaderboard_cached())


@app.route("/explore")
@request_wrapper
@require_data_access
def explore():
    log_activity("Loading Explore page")
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    return render_template(
        "categories.html",
        data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
        data_version=data_version,
        key="class",
        categories=NeuronDataFactory.instance().get(data_version).categories(),
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
            url_for_skeleton(nd["root_id"], animated=False),
            url_for_skeleton(nd["root_id"], animated=True),
        )
        for nd in display_data
    }
    highlighted_labels = {}
    for nd in display_data:
        # Only highlight free-form search tokens (and not structured search attributes)
        psq = parse_search_query(filter_string)
        search_terms = psq[1] + [stq["rhs"] for stq in psq[2] or []]
        highlighted_label_list = highlight_annotations(
            search_terms, [trim_long_tokens(t) for t in nd["label"]]
        )
        for t, highlighted_label in enumerate(highlighted_label_list):
            highlighted_labels[nd["label"][t]] = highlighted_label

    return render_template(
        template_name_or_list=template_name,
        display_data=display_data,
        highlighted_labels=highlighted_labels,
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
    ua = (user_agent() or "").lower()
    if "chrome" in ua or "firefox" in ua:
        return redirect(ngl_url, code=302)
    else:
        return warning_with_redirect(
            title="Browser not supported",
            message="Neuroglancer (3D neuron rendering) is not supported on your browser. Use Chrome or Firefox.",
            redirect_url=ngl_url,
            redirect_button_text="Proceed anyway",
        )


@app.route("/cell_details", methods=["GET", "POST"])
@request_wrapper
@require_data_access
def cell_details():
    min_syn_cnt = request.args.get("min_syn_cnt", 5, type=int)
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
        min_syn_cnt=min_syn_cnt,
        reachability_stats=reachability_stats,
    )
    log_activity(
        f"Generated neuron info for {root_id} with {len(dct['cell_attributes']) + len(dct['related_cells'])} items"
    )
    return render_template("cell_details.html", **dct)


@app.route("/pathways")
@request_wrapper
@require_data_access
def pathways():
    source = request.args.get("source_cell_id", type=int)
    target = request.args.get("target_cell_id", type=int)
    min_syn_count = request.args.get("min_syn_count", type=int, default=MIN_SYN_COUNT)
    min_syn_count = max(min_syn_count, MIN_SYN_COUNT)
    log_activity(f"Rendering pathways from {source} to {target} with {min_syn_count=}")
    neuron_db = NeuronDataFactory.instance().get()
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
        neuron_db = NeuronDataFactory.instance().get()
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
        fname = "path_lengths.csv"
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
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
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
        neuron_db = NeuronDataFactory.instance().get(data_version)
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
            root_ids=root_ids,
            contable=contable,
            data_version=data_version,
            group_regions=group_regions,
            reduce=reduce,
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
                max_cap=max_cap,
                network_html=network_html,
                info_text=None,
                sample_input=None,
                message=message,
                data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
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
            data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
            data_version=data_version,
            reduce=reduce,
            group_regions=group_regions,
            hide_weights=hide_weights,
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
    data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
    normalized = request.args.get("normalized", type=int, default=0)
    directed = request.args.get("directed", type=int, default=0)
    group_by = request.args.get("group_by")
    log_activity(
        f"Rendering synapse_density page with {data_version=} {normalized=} {directed=} {group_by=}"
    )

    dct = synapse_density_cached(
        data_version=data_version,
        normalized=normalized,
        directed=directed,
        group_by=group_by,
    )

    return render_template("synapse_density.html", **dct)


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
