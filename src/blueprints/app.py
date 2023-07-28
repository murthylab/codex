import json
import re
from collections import defaultdict
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
    TYPE_PREDICATES_METADATA,
)
from src.data.brain_regions import (
    REGIONS,
    NEUROPIL_DESCRIPTIONS,
    REGIONS_JSON,
)
from src.data.faq_qa_kb import FAQ_QA_KB
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.neuron_data_initializer import NETWORK_GROUP_BY_ATTRIBUTES
from src.data.structured_search_filters import (
    OP_PATHWAYS,
    parse_search_query,
)
from src.data.sorting import sort_search_results, SORT_BY_OPTIONS
from src.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
)
from src.data.visual_neuron_types import (
    VISUAL_NEURON_MEGA_TYPE_TO_TYPES,
    VISUAL_NEURON_TYPES,
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
    log,
    log_warning,
    log_error,
)
from src.utils.formatting import can_be_flywire_root_id
from src.utils.markers import extract_markers
from src.utils.parsing import tokenize
from src.utils.pathway_vis import pathway_chart_data_rows
from src.utils.prm import cell_identification_url
from src.utils.thumbnails import url_for_skeleton
from src.data.structured_search_filters import get_advanced_search_data
from src.data.braincircuits import neuron2line
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.service.motif_search import MotifSearchQuery

app = Blueprint("app", __name__, url_prefix="/app")


@app.context_processor
def jinja_utils():
    return dict(display=display, nanos_to_formatted_micros=nanos_to_formatted_micros)


@app.route("/stats")
@request_wrapper
def stats():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", "")
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)

    log_activity(f"Generating stats {activity_suffix(filter_string, data_version)}")
    (filtered_root_id_list, num_items, hint, data_stats, data_charts,) = stats_cached(
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
        advanced_search_data=get_advanced_search_data(current_query=filter_string),
    )


@app.route("/leaderboard")
@request_wrapper
def leaderboard():
    query = request.args.get("filter_string", "")
    user_filter = request.args.get("user_filter", "")
    lab_filter = request.args.get("lab_filter", "")

    log_activity(f"Loading Leaderboard, {query=} {user_filter=} {lab_filter=}")
    labeled_cells_caption, leaderboard_data = leaderboard_cached(
        query=query,
        user_filter=user_filter,
        lab_filter=lab_filter,
        data_version=DEFAULT_DATA_SNAPSHOT_VERSION,
    )
    return render_template(
        "leaderboard.html",
        labeled_cells_caption=labeled_cells_caption,
        data_stats=leaderboard_data,
        filter_string=query,
        user_filter=user_filter,
        lab_filter=lab_filter,
    )


@app.route("/explore")
@request_wrapper
def explore():
    log_activity("Loading Explore page")
    data_version = request.args.get("data_version", "")
    top_values = request.args.get("top_values", type=int, default=6)
    for_attr_name = request.args.get("for_attr_name", "")
    return render_template(
        "explore.html",
        data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
        data_version=data_version,
        top_values=top_values,
        categories=NeuronDataFactory.instance()
        .get(data_version)
        .categories(
            top_values=top_values,
            for_attr_name=for_attr_name,
        ),
    )


def render_neuron_list(
    data_version,
    template_name,
    sorted_search_result_root_ids,
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
        items_list=sorted_search_result_root_ids,
        page_number=page_number,
        page_size=page_size,
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
    links = {}
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
            "connectivity_tag",
        ]:
            if nd[attr_name]:
                if isinstance(nd[attr_name], list):
                    terms_to_annotate |= set(nd[attr_name])
                else:
                    terms_to_annotate.add(nd[attr_name])
        highlighted_terms.update(highlight_annotations(search_terms, terms_to_annotate))
        links[nd["root_id"]] = neuron_db.get_links(nd["root_id"])

    return render_template(
        template_name_or_list=template_name,
        display_data=display_data,
        highlighted_terms=highlighted_terms,
        links=links,
        skeleton_thumbnail_urls=skeleton_thumbnail_urls,
        # If num results is small enough to pass to browser, pass it to allow copying root IDs to clipboard.
        # Otherwise it will be available as downloadable file.
        root_ids_str=",".join([str(ddi) for ddi in sorted_search_result_root_ids])
        if len(sorted_search_result_root_ids) <= MAX_NEURONS_FOR_DOWNLOAD
        else [],
        num_items=len(sorted_search_result_root_ids),
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
        advanced_search_data=get_advanced_search_data(current_query=filter_string),
        multi_val_attrs=neuron_db.multi_val_attrs(sorted_search_result_root_ids),
        non_uniform_labels=neuron_db.non_uniform_values(
            list_attr_key="label",
            page_ids=page_ids,
            all_ids=sorted_search_result_root_ids,
        ),
        non_uniform_cell_types=neuron_db.non_uniform_values(
            list_attr_key="cell_type",
            page_ids=page_ids,
            all_ids=sorted_search_result_root_ids,
        ),
        non_uniform_hemibrain_types=neuron_db.non_uniform_values(
            list_attr_key="hemibrain_type",
            page_ids=page_ids,
            all_ids=sorted_search_result_root_ids,
        ),
    )


def _search_and_sort():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", "")
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    sort_by = request.args.get("sort_by")
    neuron_db = NeuronDataFactory.instance().get(data_version)
    filtered_root_id_list = neuron_db.search(
        filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    return sort_search_results(
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
        similar_embedding_cells_getter=neuron_db.get_similar_embedding_cells,
        connections_getter=lambda x: neuron_db.cell_connections(x),
        sort_by=sort_by,
    )


@app.route("/search", methods=["GET"])
@request_wrapper
def search():
    filter_string = request.args.get("filter_string", "")
    page_number = int(request.args.get("page_number", 1))
    page_size = int(request.args.get("page_size", DEFAULT_PAGE_SIZE))
    data_version = request.args.get("data_version", "")
    case_sensitive = request.args.get("case_sensitive", 0, type=int)
    whole_word = request.args.get("whole_word", 0, type=int)
    sort_by = request.args.get("sort_by")

    hint = None
    log(
        f"Loading search page {page_number} {activity_suffix(filter_string, data_version)}"
    )
    sorted_search_result_root_ids, extra_data = _search_and_sort()
    if sorted_search_result_root_ids:
        if len(sorted_search_result_root_ids) == 1:
            if filter_string == str(sorted_search_result_root_ids[0]):
                log_activity("Single cell match, redirecting to cell details")
                return redirect(
                    url_for(
                        "app.cell_details",
                        root_id=sorted_search_result_root_ids[0],
                        data_version=data_version,
                    )
                )

        log_activity(
            f"Loaded {len(sorted_search_result_root_ids)} search results for page {page_number} "
            f"{activity_suffix(filter_string, data_version)}"
        )
    else:
        neuron_db = NeuronDataFactory.instance().get(data_version)
        hint, edist = neuron_db.closest_token(
            filter_string, case_sensitive=case_sensitive
        )
        log_warning(f"No results for '{filter_string}', sending hint '{hint}' {edist=}")

    return render_neuron_list(
        data_version=data_version,
        template_name="search.html",
        sorted_search_result_root_ids=sorted_search_result_root_ids,
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
def download_search_results():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", "")
    neuron_db = NeuronDataFactory.instance().get(data_version)

    log_activity(
        f"Downloading search results {activity_suffix(filter_string, data_version)}"
    )
    sorted_search_result_root_ids, extra_data = _search_and_sort()
    log_activity(
        f"For download got {len(sorted_search_result_root_ids)} results {activity_suffix(filter_string, data_version)}"
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
        "connectivity_tag",
        "side",
        "input_synapses",
        "output_synapses",
        "morphology_cluster",
        "connectivity_cluster",
    ]
    data = [cols]
    for i in sorted_search_result_root_ids:
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
def root_ids_from_search_results():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", "")

    log_activity(f"Listing Cell IDs {activity_suffix(filter_string, data_version)}")
    sorted_search_result_root_ids, extra_data = _search_and_sort()
    log_activity(
        f"For list cell ids got {len(sorted_search_result_root_ids)} results {activity_suffix(filter_string, data_version)}"
    )
    fname = f"root_ids_{re.sub('[^0-9a-zA-Z]+', '_', filter_string)}.txt"
    return Response(
        ",".join([str(rid) for rid in sorted_search_result_root_ids]),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={fname}"},
    )


@app.route("/search_results_flywire_url")
@request_wrapper
def search_results_flywire_url():
    filter_string = request.args.get("filter_string", "")
    data_version = request.args.get("data_version", "")
    request.args.get("case_sensitive", 0, type=int)
    request.args.get("whole_word", 0, type=int)
    NeuronDataFactory.instance().get(data_version)

    log_activity(
        f"Generating URL search results {activity_suffix(filter_string, data_version)}"
    )
    sorted_search_result_root_ids, extra_data = _search_and_sort()
    log_activity(
        f"For URLs got {len(sorted_search_result_root_ids)} results {activity_suffix(filter_string, data_version)}"
    )

    url = nglui.url_for_random_sample(
        sorted_search_result_root_ids,
        version=data_version or DEFAULT_DATA_SNAPSHOT_VERSION,
        sample_size=MAX_NEURONS_FOR_DOWNLOAD,
    )
    log_activity(
        f"Redirecting {len(sorted_search_result_root_ids)} results {activity_suffix(filter_string, data_version)} to FlyWire"
    )
    return ngl_redirect_with_client_check(ngl_url=url)


@app.route("/optic_lobe_catalog")
@request_wrapper
@require_data_access
def optic_lobe_catalog():
    log_activity("Loading optic lobe catalog")
    neuron_db = NeuronDataFactory.instance().get()
    olr_type_lists = {t: [] for t in VISUAL_NEURON_TYPES}
    non_olr_type_lists = {t: [] for t in VISUAL_NEURON_TYPES}
    predicted_olr_type_lists = {t: [] for t in VISUAL_NEURON_TYPES}
    for rid, nd in neuron_db.neuron_data.items():
        for mrk in nd["marker"]:
            if mrk.startswith("olr_type:"):
                olt = mrk.split(":")[1]
                olr_type_lists[olt].append(rid)
            elif mrk.startswith("not_in_olr_type:"):
                olt = mrk.split(":")[1]
                non_olr_type_lists[olt].append(rid)
            elif mrk.startswith("predicted_olr_type:"):
                olt = mrk.split(":")[1]
                predicted_olr_type_lists[olt].append(rid)

    types_data = {}
    types_with_predicates = []
    for mt, tl in VISUAL_NEURON_MEGA_TYPE_TO_TYPES.items():
        types_list = []
        for t in tl:
            olr_query = f"marker == olr_type:{t}"
            non_olr_query = f"marker == not_in_olr_type:{t}"
            predicted_olr_query = "marker {starts_with} predicted_olr_type:" + f"{t}:"
            dct = {
                "name": t,
                "olr_count": len(olr_type_lists[t]),
                "olr_search_url": url_for("app.search", filter_string=olr_query),
                "olr_ngl_url": url_for(
                    "app.search_results_flywire_url", filter_string=olr_query
                ),
                "predicted_olr_count": len(predicted_olr_type_lists[t]),
                "predicted_olr_search_url": url_for(
                    "app.search", filter_string=predicted_olr_query
                ),
                "predicted_olr_ngl_url": url_for(
                    "app.search_results_flywire_url",
                    filter_string=predicted_olr_query,
                ),
                "non_olr_count": len(non_olr_type_lists[t]),
                "non_olr_search_url": url_for(
                    "app.search", filter_string=non_olr_query
                ),
                "non_olr_ngl_url": url_for(
                    "app.search_results_flywire_url", filter_string=non_olr_query
                ),
            }
            if (
                t in TYPE_PREDICATES_METADATA
                and float(TYPE_PREDICATES_METADATA[t]["f_score"]) >= 0.6
            ):
                types_with_predicates.append(t)
                dct.update(
                    {
                        "predicate": True,
                        "predicate_input_types": TYPE_PREDICATES_METADATA[t][
                            "predicate_input_types"
                        ],
                        "predicate_output_types": TYPE_PREDICATES_METADATA[t][
                            "predicate_output_types"
                        ],
                        "predicate_precision": TYPE_PREDICATES_METADATA[t]["precision"],
                        "predicate_recall": TYPE_PREDICATES_METADATA[t]["recall"],
                        "predicate_f_score": TYPE_PREDICATES_METADATA[t]["f_score"],
                        "predicate_true_positives_count": len(
                            TYPE_PREDICATES_METADATA[t]["true_positives"]
                        ),
                        "predicate_false_positives_count": len(
                            TYPE_PREDICATES_METADATA[t]["false_positives"]
                        ),
                        "predicate_false_negatives_count": len(
                            TYPE_PREDICATES_METADATA[t]["false_negatives"]
                        ),
                    }
                )
            else:
                dct["predicate"] = False
            types_list.append(dct)

        if mt == "Unknown":
            all_predicted = set()
            for v in predicted_olr_type_lists.values():
                all_predicted |= set(v)
            unpredicted_count = len(
                [
                    rid
                    for rid in olr_type_lists["Unknown-labeled"]
                    + olr_type_lists["Unknown-not-labeled"]
                    if rid not in all_predicted
                ]
            )
            unpredicted_query = (
                "marker {contains} olr_type:unknown && marker {not_contains} predicted"
            )
            types_list.append(
                {
                    "name": "Unknown and have no predictions (new type candidates)",
                    "olr_count": unpredicted_count,
                    "olr_search_url": url_for(
                        "app.search", filter_string=unpredicted_query
                    ),
                    "olr_ngl_url": url_for(
                        "app.search_results_flywire_url",
                        filter_string=unpredicted_query,
                    ),
                }
            )

            for t, lst in sorted(
                predicted_olr_type_lists.items(), key=lambda x: -len(x[1])
            ):
                if not predicted_olr_type_lists[t]:
                    continue
                predicted_olr_query = (
                    "marker {starts_with} predicted_olr_type:" + f"{t}:"
                )
                types_list.append(
                    {
                        "name": f"Unknown predicted to be {t}",
                        "olr_count": len(predicted_olr_type_lists[t]),
                        "olr_search_url": url_for(
                            "app.search", filter_string=predicted_olr_query
                        ),
                        "olr_ngl_url": url_for(
                            "app.search_results_flywire_url",
                            filter_string=predicted_olr_query,
                        ),
                    }
                )

        types_data[mt] = types_list

    def total_length(dct, with_percentage=False, exclude_unknown=False):
        totlen = 0
        for k, v in dct.items():
            if exclude_unknown and k.startswith("Unknown"):
                continue
            totlen += len(v)

        if with_percentage:
            return f"{display(totlen)} ({percentage(totlen, sum([len(v) for v in olr_type_lists.values()]))})"
        else:
            return display(totlen)

    meta_data = {
        "Progress": [
            f"{total_length(olr_type_lists, True, True)} neurons in the right optic lobe have been typed (per catalog)",
        ],
        "TODO breakdown": [
            f"{display(len(olr_type_lists['Unknown-not-labeled']))} of the untyped neurons in the right optic lobe have no labels",
            f"{len(olr_type_lists['Unknown-labeled'])} of the untyped neurons in the right optic lobe have unidentified labels",
            f"{total_length(predicted_olr_type_lists)} of the untyped neurons in the right optic lobe have predictions",
        ],
        "Types": [
            f"{len([k for k, v in olr_type_lists.items() if v and 'Unknown' not in k])} types from the catalog have matches in the right optic lobe",
            f"{len([k for k, v in olr_type_lists.items() if not v and 'Unknown' not in k])} types from the catalog have <b>no</b> matches in the right optic lobe",
            f"{total_length(non_olr_type_lists)} neurons <b>outside</b> the right optic lobe have types from the catalog",
        ],
        "Connectivity predicates": [
            f"{len(types_with_predicates)} types have connectivity predicates with high precision/recall",
        ],
        "Target set update suggestions": [
            '<a href="search?filter_string=olr_false_positives:5&sort_by=-partners&page_size=100", target="_blank">REMOVE: neurons without any synapses in OLR or with >5% of synapses outside OLR</a>',
            '<a href="search?filter_string=olr_false_negatives&sort_by=-partners&page_size=100", target="_blank">ADD: sensory neurons with all their synapses in OLR</a>',
        ],
    }
    return render_template(
        "optic_lobe_catalog.html",
        meta_data=meta_data,
        types_data=types_data,
    )


@app.route("/count_visual_cell_types", methods=["GET", "POST"])
@request_wrapper
@require_data_access
def count_visual_cell_types():
    log_activity("Counting visual cell types")
    msg = "This tool summarizes visual types for sets of cells"

    if request.method == "POST":
        neuron_db = NeuronDataFactory.instance().get()
        cell_ids = request.form.get("cell_ids")
        cell_ids = neuron_db.search(cell_ids)
        counts = defaultdict(int)
        for cell_id in cell_ids:
            try:
                cell = neuron_db.neuron_data[int(cell_id)]
                mrks = extract_markers(cell, "olr_type") + extract_markers(
                    cell, "not_in_olr_type"
                )
                if mrks:
                    if not len(mrks) == 1:
                        raise ValueError(
                            f"Multiple types assigned to {cell_id}: {mrks}"
                        )
                    counts[mrks[0]] += 1
                else:
                    counts["Has no visual type assigned"] += 1
            except Exception:
                counts["Invalid Cell ID"] += 1
        if counts:
            msg = "<br>".join(
                [
                    f"{p[1]} ({percentage(p[1], len(cell_ids))}):  {p[0]}"
                    for p in sorted(counts.items(), key=lambda x: -x[1])
                ]
            )
            log_activity(f"Counting visual cell types for {len(cell_ids)} cells: {msg}")
    return render_template(
        "many_cells_form.html",
        title="Count Visual Cell Types",
        message=msg,
    )


@app.route("/find_similar_cells", methods=["GET", "POST"])
@request_wrapper
@require_data_access
def find_similar_cells():
    log_activity("Finding similar cells")
    msg = "This tool finds cells that have similar connectivity to <b>any</b> of the specified cells."

    if request.method == "POST":
        neuron_db = NeuronDataFactory.instance().get()
        cell_ids = request.form.get("cell_ids")
        cell_ids = tokenize(cell_ids) if cell_ids else []
        invalid_cell_ids = []
        for cell_id in cell_ids:
            try:
                neuron_db.neuron_data[int(cell_id)]
            except Exception as e:
                print(f"Exception: {e}")
                invalid_cell_ids.append(cell_id)

        max_input_size = 150
        if invalid_cell_ids:
            msg = (
                f'<i style="color:red" class="fa-solid fa-triangle-exclamation"></i> Invalid Cell IDs (not found in v{DEFAULT_DATA_SNAPSHOT_VERSION}): '
                + ", ".join(invalid_cell_ids)
            )
            log_activity(msg)
        elif len(cell_ids) > max_input_size:
            msg = f'<i style="color:red" class="fa-solid fa-triangle-exclamation"></i> Too many Cell IDs ({len(cell_ids)}), reduce to {max_input_size} or less'
            log_activity(msg)
        else:
            cell_ids = set([int(cid) for cid in cell_ids])
            similar_cell_scores = {}
            for cell_id in cell_ids:
                dct = neuron_db.get_similar_connectivity_cells(
                    cell_id, with_same_attributes="side,super_class"
                )
                for k, v in dct.items():
                    if k in cell_ids:
                        continue
                    if k not in similar_cell_scores or v > similar_cell_scores[k]:
                        similar_cell_scores[k] = v

            if similar_cell_scores:
                top_k = 600
                top_matches = sorted(similar_cell_scores.items(), key=lambda p: -p[1])[
                    :top_k
                ]
                flat_list_of_ids = ",".join([str(m[0]) for m in top_matches])
                msg = f"<a href='search?filter_string={flat_list_of_ids}'>Show matches in Codex -></a>"
                msg += f"<br><br>Flat list of matched cell IDs:<br>{flat_list_of_ids}"
                msg += "<br><br>Individual cell IDs with match scores:<br>" + "<br>".join(
                    [
                        f"<a href='search?filter_string={m[0]}'>{m[0]}</a>: {str(m[1])[:5]}"
                        for m in top_matches
                    ]
                )
                log_activity(
                    f"Found {len(similar_cell_scores)} similar cells, showing up to top {top_k}"
                )
            else:
                msg = "No similar cells found"
                log_activity(f"No similar cells found for {cell_ids}")
    return render_template(
        "many_cells_form.html",
        title="Find Similar Cells",
        message=msg,
    )


@app.route("/find_unlabeled_cells", methods=["GET", "POST"])
@request_wrapper
@require_data_access
def find_unlabeled_cells():
    log_activity("Finding unlabeled cells")
    msg = "This tool finds unlabeled cells. Just provide a list of cell IDs and it'll print out the unlabeled subset."

    if request.method == "POST":
        neuron_db = NeuronDataFactory.instance().get()
        cell_ids = request.form.get("cell_ids")
        cell_ids = tokenize(cell_ids) if cell_ids else []
        cell_ids = set(cell_ids)
        invalid_cell_ids = []
        unlabeled_cell_ids = []
        for cell_id in cell_ids:
            try:
                nd = neuron_db.neuron_data[int(cell_id)]
                if not nd["label"]:
                    unlabeled_cell_ids.append(cell_id)
            except Exception:
                invalid_cell_ids.append(cell_id)
        if unlabeled_cell_ids:
            msg = "Unlabeled cells:<br>" + ", ".join(unlabeled_cell_ids)
        else:
            msg = "No Unlabeled cells found"
        if invalid_cell_ids:
            msg += "<br><br>Invalid cells:<br>" + ", ".join(invalid_cell_ids)

        log_activity(
            f"Found {len(unlabeled_cell_ids)} unlabeled cells out of {len(cell_ids)}"
        )
    return render_template(
        "many_cells_form.html",
        title="Find Unlabeled Cells",
        message=msg,
    )


@app.route("/flywire_url")
@request_wrapper
def flywire_url():
    root_ids = [int(rid) for rid in request.args.getlist("root_ids")]
    data_version = request.args.get("data_version", "")
    log_request = request.args.get("log_request", default=1, type=int)
    point_to = request.args.get("point_to")
    show_side_panel = request.args.get("show_side_panel", type=int, default=None)

    url = nglui.url_for_root_ids(
        root_ids,
        version=data_version or DEFAULT_DATA_SNAPSHOT_VERSION,
        point_to=point_to,
        show_side_panel=show_side_panel,
    )
    if log_request:
        log_activity(
            f"Redirecting for {len(root_ids)} root ids to FlyWire, {point_to=}"
        )
    return ngl_redirect_with_client_check(ngl_url=url)


def ngl_redirect_with_client_check(ngl_url):
    ua = parse_ua(str(request.user_agent))
    # iOS (iPhone/iPad) does not render brain meshes or neuropils
    if "iOS" in ua.get_os():
        return warning_with_redirect(
            title="Device not supported",
            message="Neuroglancer (3D neuron rendering) may not be supported on your mobile iOS device. "
            "Compatible platforms: Mac / PC / Android",
            redirect_url=ngl_url,
            redirect_button_text="Proceed anyway",
        )

    min_supported = {
        "Chrome": 51,
        "Edge": 51,
        "Firefox": 46,
        "Safari": 15,
        "Opera": 95,
    }
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


@app.route("/cell_coordinates/<path:cell_id>")
@request_wrapper
def cell_coordinates(cell_id):
    data_version = request.args.get("data_version", "")
    log_activity(f"Loading coordinates for cell {cell_id}, {data_version=}")
    neuron_db = NeuronDataFactory.instance().get(data_version)
    nd = neuron_db.get_neuron_data(cell_id)
    return f"<h2>Supervoxel IDs and coordinates for {cell_id}</h2>" + "<br>".join(
        [
            f"Supervoxel ID: {s}, nanometer coordinates: {c}, FlyWire coordinates: {nanometer_to_flywire_coordinates(c)}"
            for c, s in zip(nd["position"], nd["supervoxel_id"])
        ]
    )


@app.route("/annotate_cell", methods=["GET"])
@request_wrapper
@require_data_access
def annotate_cell():
    annotation_cell_id = request.args.get("annotation_cell_id", "")
    annotation_text = request.args.get("annotation_text", "")
    annotation_coordinates = request.args.get("annotation_coordinates", "")

    fw_user_id = fetch_flywire_user_id(session, required=True)
    log_activity(
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


@app.route("/cell_details", methods=["GET", "POST"])
@request_wrapper
def cell_details():
    data_version = request.args.get("data_version", "")
    reachability_stats = request.args.get("reachability_stats", 0, type=int)
    neuron_db = NeuronDataFactory.instance().get(data_version)

    if request.method == "POST":
        data_version = request.args.get("data_version", "")
        neuron_db = NeuronDataFactory.instance().get(data_version)
        annotation_text = request.form.get("annotation_text")
        annotation_coordinates = request.form.get("annotation_coordinates")
        annotation_cell_id = request.form.get("annotation_cell_id")
        if not annotation_coordinates:
            ndata = neuron_db.get_neuron_data(annotation_cell_id)
            annotation_coordinates = ndata["position"][0] if ndata["position"] else None
        return redirect(
            url_for(
                "app.annotate_cell",
                annotation_cell_id=annotation_cell_id,
                annotation_text=annotation_text,
                annotation_coordinates=annotation_coordinates,
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
def pathways():
    source = request.args.get("source_cell_id", type=int)
    target = request.args.get("target_cell_id", type=int)
    min_syn_count = request.args.get("min_syn_count", type=int, default=0)
    log_activity(f"Rendering pathways from {source} to {target} with {min_syn_count=}")
    data_version = request.args.get("data_version", "")
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
def path_length():
    source_cell_names_or_ids = request.args.get("source_cell_names_or_ids", "")
    target_cell_names_or_ids = request.args.get("target_cell_names_or_ids", "")
    data_version = request.args.get("data_version", "")
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
def connectivity():
    data_version = request.args.get("data_version", "")
    nt_type = request.args.get("nt_type", None)
    min_syn_cnt = request.args.get("min_syn_cnt", default=0, type=int)
    connections_cap = request.args.get("cap", default=50, type=int)
    group_by = request.args.get("group_by", default="")
    show_regions = request.args.get("show_regions", default=0, type=int)
    include_partners = request.args.get("include_partners", default=0, type=int)
    hide_weights = request.args.get("hide_weights", default=0, type=int)
    cell_names_or_ids = request.args.get("cell_names_or_ids", "")
    # This flag labels the list of cells with "A, B, C, .." in the order they're specified. Used for mapping motif node
    # names to cell names.
    label_abc = request.args.get("label_abc", type=bool)
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
        node_labels = None
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
            if label_abc:
                if not len(root_ids) == 3:
                    raise ValueError(
                        f"Unexpected flag {label_abc=} for {len(root_ids)} matching root IDs"
                    )
                node_labels = {
                    root_ids[i]: ltr for i, ltr in enumerate(["A", "B", "C"])
                }

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
                                "data_version": data_version
                                or DEFAULT_DATA_SNAPSHOT_VERSION,
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
            node_labels=node_labels,
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
    return ngl_redirect_with_client_check(ngl_url=url)


@app.route("/neuropils")
@request_wrapper
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
def heatmaps():
    data_version = request.args.get("data_version", "")
    group_by = request.args.get("group_by")
    count_type = request.args.get("count_type")
    log_activity(f"Rendering heatmaps page with {data_version=} {group_by=}")

    dct = heatmap_data(
        neuron_db=NeuronDataFactory.instance().get(data_version),
        group_by=group_by,
        count_type=count_type,
    )
    dct["data_version"] = data_version

    return render_template("heatmaps.html", **dct)


@app.route("/matching_lines")
@request_wrapper
def matching_lines():
    segment_id = request.args.get("segment_id")
    target_library = request.args.get("target_library")
    email = fetch_user_email(session)
    log_activity(f"Calling BrainCircuits API with {segment_id=} {target_library=}")
    try:
        result = neuron2line([segment_id], target_library, email)
        log_activity(f"BrainCircuits API call returned {result=}")
        return render_info(
            title="Submission complete",
            message=f"The results will be sent to your email address: {email}",
        )
    except requests.HTTPError as e:
        log_error(
            f"BrainCircuits API call failed with {e=}. Did you set BRAINCIRCUITS_TOKEN?"
        )
    except Exception as e:
        log_error(f"BrainCircuits API call failed with error: {e=}")

    return render_error(
        "There was an error submitting the request.<br>Please try again later."
    )


@app.route("/labeling_log")
@request_wrapper
def labeling_log():
    root_id = request.args.get("root_id")
    log_activity(f"Loading labling log for {root_id}")
    root_id = int(root_id)
    neuron_db = NeuronDataFactory.instance().get()
    nd = neuron_db.get_neuron_data(root_id)
    if not nd:
        return render_error(
            f"Neuron with ID {root_id} not found in v{DEFAULT_DATA_SNAPSHOT_VERSION} data snapshot."
        )

    labels_data = neuron_db.get_label_data(root_id=root_id)
    labeling_log = [
        f'<small><b>{ld["label"]}</b> - labeled by {ld["user_name"]}'
        + (f' from {ld["user_affiliation"]}' if ld["user_affiliation"] else "")
        + f' on {ld["date_created"]}</small>'
        for ld in sorted(
            labels_data or [], key=lambda x: x["date_created"], reverse=True
        )
    ]

    def format_log(labels):
        return "<br>".join([f"&nbsp; <b>&#x2022;</b> &nbsp; {t}" for t in labels])

    return render_info(
        title=f"Labeling Info & Credits<br><small style='color:teal'>&nbsp;  &nbsp;  &nbsp; {nd['name']}  &#x2022;  {nd['root_id']}</small>",
        message=format_log(labeling_log)
        + f"<br><br>Last synced: <b>{neuron_db.labels_ingestion_timestamp()}</b>",
        back_button=0,
    )


@app.route("/my_labels")
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


@app.route("/motifs/", methods=["GET", "POST"])
@request_wrapper
def motifs():
    log_activity(f"Loading motifs search with {request.args}")
    search_results = []

    if request.args:
        motifs_query = MotifSearchQuery.from_form_query(
            request.args, NeuronDataFactory.instance()
        )
        search_results = motifs_query.search()
        log_activity(
            f"Motif search with {motifs_query} found {len(search_results)} matches"
        )
        query = request.args
        show_explainer = False
    else:
        # make a default state so that hitting search finds results (empty query will err)
        query = dict(
            enabledAB=True,
            minSynapseCountAB=1,
            enabledBA=True,
            minSynapseCountBA=1,
            enabledAC=True,
            minSynapseCountAC=1,
            enabledCA=True,
            minSynapseCountCA=1,
            enabledBC=True,
            minSynapseCountBC=1,
            enabledCB=True,
            minSynapseCountCB=1,
        )
        show_explainer = True

    return render_template(
        "motif_search.html",
        regions=list(REGIONS.keys()),
        NEURO_TRANSMITTER_NAMES=NEURO_TRANSMITTER_NAMES,
        query=query,
        results=search_results,
        show_explainer=show_explainer,
    )
