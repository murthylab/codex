import os
from random import randint

from flask import (
    Blueprint,
    redirect,
    request,
    send_from_directory,
    url_for,
)
from jinja2 import Environment, PackageLoader, select_autoescape

from codex.configuration import (
    MIN_SYN_THRESHOLD,
)
from codex.data.faq_qa_kb import FAQ_QA_KB
from codex.data.neuron_data_factory import NeuronDataFactory
from codex.data.versions import (
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from codex.utils.formatting import (
    display,
    nanos_to_formatted_micros,
    percentage,
    truncate,
)
from codex.utils.thumbnails import url_for_skeleton
from codex import logger


def format_link(url, tag="link"):
    return f"<{url}|{tag}>"


tabs = [
    ["explore", "Explore", "app"],
    ["search", "Search", "app"],
    ["stats", "Stats", "app"],
    ["cell_details", "Cell Info", "app"],
    ["connectivity", "Network", "app"],
    ["path_length", "Pathways", "app"],
    ["neuropils", "Neuropils", "app"],
    ["heatmaps", "Heatmaps", "app"],
    ["motifs", "Motifs", "app"],
    ["about_codex", "About", "base"],
]

dropdown_items = [
    ["about_flywire", "base.about_flywire", "FlyWire Info & Credits"],
    ["faq", "base.faq", "FAQ"],
]
more_tabs = [item[0] for item in dropdown_items]


jinja_env = Environment(
    loader=PackageLoader("codex"),
    autoescape=select_autoescape(["html", "xml"]),
)
jinja_env.globals["url_for"] = url_for
jinja_env.globals["display"] = display
jinja_env.globals["nanos_to_formatted_micros"] = nanos_to_formatted_micros
jinja_env.globals["tabs"] = tabs
jinja_env.globals["dropdown_items"] = dropdown_items
jinja_env.globals["more_tabs"] = more_tabs
jinja_env.globals["request"] = request

# This flag disables the UI for features that won't work in the open source version of Codex
jinja_env.globals["is_oss"] = True


def render_template(template_name_or_list, **context):
    return jinja_env.get_template(template_name_or_list).render(**context)


base = Blueprint("base", __name__)


@base.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(base.root_path, "../static"), "favicon.ico")


@base.route("/background_image")
def background_image():
    return asset(filename=f"bgd{randint(1, 6)}.png")


@base.route("/asset/<path:filename>")
def asset(filename):
    return send_from_directory(
        os.path.join(base.root_path, "../static/assets"), filename
    )


@base.route("/styles/<path:filename>")
def styles(filename):
    return send_from_directory(
        os.path.join(base.root_path, "../static/styles"), filename
    )


@base.route("/js/<path:filename>")
def js(filename):
    return send_from_directory(os.path.join(base.root_path, "../static/js"), filename)


@base.route("/error", methods=["GET", "POST"])
def error():
    message = request.args.get("message", "Unexpected error")
    title = request.args.get("title", "Request failed")
    logger.info(f"Loading Error page with {title=} and {message=}")
    back_button = request.args.get("back_button", 1, type=int)
    message_sent = False
    return render_template(
        "error.html",
        message=message,
        title=title,
        back_button=back_button,
        message_sent=message_sent,
    )


def warning_with_redirect(title, message, redirect_url, redirect_button_text):
    logger.warning(
        f"Loading warning with redirect page with '{message}' to {format_link(redirect_url)}"
    )
    return render_template(
        "warning_with_redirect.html",
        title=title,
        message=message,
        redirect_url=redirect_url,
        redirect_button_text=redirect_button_text,
    )


@base.route("/about_flywire", methods=["GET", "POST"])
def about_flywire():
    logger.info("Loading FlyWire Credits page")
    return render_template(
        "about_flywire.html",
    )


@base.route("/faq", methods=["GET", "POST"])
def faq():
    logger.info("Loading FAQ page")
    message_sent = False
    return render_template(
        "faq.html",
        faq_dict=FAQ_QA_KB,
        message_sent=message_sent,
    )


@base.route("/", defaults={"path": ""})
def index(path):
    if request.args.get("filter_string"):
        logger.info("Searching from home page")
        return redirect(
            url_for("app.search", filter_string=request.args.get("filter_string"))
        )
    else:
        data_version = request.args.get("data_version", "")
        logger.info(f"Loading home page for {data_version=}")
        card_data = [
            {
                "header": "Search",
                "body": "Find neurons using free-form or structured queries",
                "asset_filename": "card-search.jpg",
                "url": "app.search",
            },
            {
                "header": "Stats",
                "body": "See statistics and charts for various attributes of all or subset of neurons in the dataset",
                "asset_filename": "card-stats.jpg",
                "url": "app.stats",
            },
            {
                "header": "Explore",
                "body": "Browse cell types, labels, and groupings of the neurons in the dataset",
                "asset_filename": "card-explore.jpg",
                "url": "app.explore",
            },
            {
                "header": "Cell Details",
                "body": "Information about individual cells, their connectivity, similar/twin "
                "cells, 3D rendering and annotations",
                "asset_filename": "card-cell-details.png",
                "url": "app.cell_details",
            },
            {
                "header": "Neuropils",
                "body": "Visualize and query connections in specific brain regions",
                "asset_filename": "neuropils.gif",
                "url": "app.neuropils",
            },
            {
                "header": "Network Graphs",
                "body": "Visualize connectivity of neurons and their synaptic links",
                "asset_filename": "card-network.png",
                "url": "app.connectivity",
            },
            {
                "header": "Pathways",
                "body": "Analyse shortest-paths between pairs of neurons",
                "asset_filename": "card-pathways.png",
                "url": "app.path_length",
            },
        ]

        neuron_db = NeuronDataFactory.instance().get(version=data_version)
        return render_template(
            "index.html",
            card_data=card_data,
            data_version_infos=sorted(
                DATA_SNAPSHOT_VERSION_DESCRIPTIONS.values(), reverse=True
            ),
            num_cells=display(neuron_db.num_cells()),
            num_synapses=display(neuron_db.num_synapses()),
            num_connections=display(neuron_db.num_connections()),
            num_typed_or_identified_cells=display(
                neuron_db.num_typed_or_identified_cells()
            ),
            percent_typed_or_identified_cells=percentage(
                neuron_db.num_typed_or_identified_cells(), neuron_db.num_cells()
            ),
            default_version=DEFAULT_DATA_SNAPSHOT_VERSION,
            min_syn_threshold=MIN_SYN_THRESHOLD,
        )


def render_error(
    message="No details available.", title="Something went wrong", back_button=1
):
    logger.error(f"Redirecting to error page: {message=} {title=}")
    return redirect(f"/error?message={message}&title={title}&back_button={back_button}")


def render_info(title="Info", message="Operation complete.", back_button=1):
    logger.info(f"Rendering info: {truncate(message, 100, include_length=True)}")
    return render_template(
        "info.html", title=title, message=message, back_button=back_button
    )


@base.route("/todo_list", methods=["GET"])
def todo_list():
    logger.info("Loading todo list")
    return redirect(
        "https://docs.google.com/document/d/1iPtT9teD9i2k2YN7XrKjeY9UwPo7s9CNFWtmCkRelkg/edit?usp=sharing"
    )


@base.route("/announcement", methods=["GET"])
def announcement():
    logger.info("Loading announcement")
    return redirect(
        "https://docs.google.com/document/d/1MoCj36XdjSUrSfhx00Zn0RF5PwL27iRXLz15BufZRO0/edit?usp=sharing"
    )


@base.route("/demo_clip", methods=["GET"])
def demo_clip():
    logger.info("Loading demo clips")
    return redirect("https://www.youtube.com/@flywireprinceton4189/search?query=codex")


def activity_suffix(filter_string, data_version):
    return (f"for '{truncate(filter_string, 50)}'" if filter_string else "") + (
        f" (v{data_version})"
        if data_version and data_version != DEFAULT_DATA_SNAPSHOT_VERSION
        else ""
    )


@base.route("/skeleton_thumbnail_url")
def skeleton_thumbnail_url():
    cell_or_neuropil = request.args.get("cell_or_neuropil")
    file_type = request.args.get("file_type", type=str, default="png")
    log_request = request.args.get("log_request", default=1, type=int)
    url = url_for_skeleton(cell_or_neuropil=cell_or_neuropil, file_type=file_type)
    if log_request:
        logger.info(f"Fetching skeleton URL for {cell_or_neuropil}: {format_link(url)}")
    return redirect(url, code=302)


@base.route("/flywire_homepage")
def flywire_homepage():
    logger.info("Redirecting to homepage.")
    return redirect("https://flywire.ai", code=302)


@base.route("/about_codex", methods=["GET", "POST"])
def about_codex():
    logger.info("Loading About Codex page")
    message_sent = False
    return render_template("about_codex.html", message_sent=message_sent)


@base.route("/404")
def page_not_found():
    return render_error("Page not found", "404")
