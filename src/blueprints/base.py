import os
import time
import traceback
from functools import wraps
from random import randint

from flask import (
    render_template,
    request,
    redirect,
    session,
    url_for,
    send_from_directory,
    Blueprint,
    jsonify,
)
from google.auth.transport import requests
from google.oauth2 import id_token
from requests import get as get_request

from src.configuration import (
    BUILD_GIT_SHA,
    BUILD_TIMESTAMP,
    GOOGLE_CLIENT_ID,
    SUPPORT_EMAIL,
)
from src.data.faq_qa_kb import FAQ_QA_KB
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
)
from src.utils.auth import extract_access_token
from src.utils.cookies import (
    store_flywire_data_access,
    is_user_authenticated,
    fetch_user_email,
    is_granted_data_access,
    fetch_user_name,
    fetch_user_picture,
    delete_cookies,
    store_user_info,
    fetch_flywire_token,
)
from src.utils.formatting import truncate
from src.utils.logging import (
    log,
    log_activity,
    log_error,
    log_user_help,
    format_link,
    uptime,
    host_name,
    proc_id,
    _is_smoke_test_request,
    APP_ENVIRONMENT,
    log_warning,
)
from src.utils.thumbnails import url_for_skeleton

base = Blueprint("base", __name__)

num_requests_processed = 0
num_request_errors = 0
total_request_serving_time_millis = 0.0


def current_milli_time():
    return round(time.time() * 1000)


def request_wrapper(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        global num_requests_processed
        global num_request_errors
        global total_request_serving_time_millis
        start_millis = current_milli_time()
        num_requests_processed += 1
        log_verbose = False

        signature = (
            f"func: {func.__name__} endpoint: {request.endpoint} url: {request.url}"
        )
        log_lines = ["\n", f"########### Processing {signature}"]
        if request.args:
            log_lines.extend([f"### Arg {k}: {v}" for k, v in request.args.items()])
        if request.form:
            log_lines.extend([f"### Form {k}: {v}" for k, v in request.form.items()])
        if log_verbose:
            log_lines.append(f"### Headers: {request.headers}")
            log_lines.append(f"### Environ: {request.environ}")
        log_lines.extend([f"############# Finished {signature}", "\n"])
        log("\n".join(log_lines))

        for previous_domains in [
            "flywireindex.pniapps.org",
            "code.pniapps.org",
            "codex.pniapps.org",
        ]:
            if previous_domains in request.url:
                new_url = request.url.replace(previous_domains, "codex.flywire.ai")
                log_activity(f"Redirecting base URL from  {request.url}: {new_url}")
                return redirect(new_url)

        if not is_user_authenticated(session) and not _is_smoke_test_request():
            if request.endpoint not in ["base.login", "base.logout"]:
                return render_auth_page(redirect_to=request.url)
        elif log_verbose:
            log(f"Executing authenticated request for: {fetch_user_email(session)}")

        # if we got here, this could be authenticated or non-authenticated request
        try:
            exec_res = func(*args, **kwargs)
            total_request_serving_time_millis += current_milli_time() - start_millis
            return exec_res
        except Exception as e:
            traceback.print_exc()
            log_error(f"Exception when executing {signature}: {e}")
            num_request_errors += 1
            return render_error(f"{e}\n")

    return wrap


# TODO: get rid of this once data is published
def require_data_access(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        if not is_granted_data_access(session) and not _is_smoke_test_request():
            if request.endpoint not in [
                "base.login",
                "base.logout",
                "base.data_access_token",
            ]:
                return redirect(
                    url_for("base.data_access_token", redirect_to=request.url)
                )
        return func(*args, **kwargs)

    return wrap


OBSOLETE_ROUTE_DESTINATIONS = {
    "stats": "app/stats",
    "explore": "app/explore",
    "annotation_search": "app/search",
    "download_search_results": "app/download_search_results",
    "search_results_flywire_url": "app/search_results_flywire_url",
    "flywire_url": "app/flywire_url",
    "neuron_info": "app/cell_details",
    "app/neuron_info": "app/cell_details",
}


@base.route("/wip")
@request_wrapper
def wip():
    log_activity("Rendering WIP notice")
    return render_error(
        message="Both the data and the app are a work in progress. Estimated completion time is Feb 2023.",
        title="Codex - current status",
    )


@base.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(base.root_path, "../../static"), "favicon.ico"
    )


@base.route("/background_image")
def background_image():
    return asset(filename=f"bgd{randint(1, 6)}.png")


@base.route("/asset/<path:filename>")
def asset(filename):
    return send_from_directory(
        os.path.join(base.root_path, "../../static/assets"), filename
    )


@base.route("/styles/<path:filename>")
def styles(filename):
    return send_from_directory(
        os.path.join(base.root_path, "../../static/styles"), filename
    )


@base.route("/error", methods=["GET", "POST"])
@request_wrapper
def error():
    log_activity("Loading Error page")
    message = request.args.get("message", "Unexpected error")
    title = request.args.get("title", "Request failed")
    back_button = request.args.get("back_button", 1, type=int)
    message_sent = False
    if request.method == "POST":
        msg = request.form.get("user_message")
        log_user_help(
            f"From Error page with title {title} and message {message}: {msg}"
        )
        message_sent = True
    return render_template(
        "error.html",
        message=message,
        title=title,
        back_button=back_button,
        message_sent=message_sent,
        user_email=fetch_user_email(session, default_to="email missing"),
    )


def warning_with_redirect(title, message, redirect_url, redirect_button_text):
    log_warning(
        f"Loading warning with redirect page with '{message}' to {format_link(redirect_url)}"
    )
    return render_template(
        "warning_with_redirect.html",
        title=title,
        message=message,
        redirect_url=redirect_url,
        redirect_button_text=redirect_button_text,
    )


@base.route("/about_codex", methods=["GET", "POST"])
@request_wrapper
def about_codex():
    log_activity("Loading About Codex page")
    message_sent = False
    if request.method == "POST":
        msg = request.form.get("user_message")
        if msg:
            log_user_help(f"From About Codex page: {msg}")
            message_sent = True
    return render_template(
        "about_codex.html",
        message_sent=message_sent,
        build_git_sha=BUILD_GIT_SHA,
        build_timestamp=BUILD_TIMESTAMP,
        instance_environment=APP_ENVIRONMENT,
        instance_host_name=host_name,
        instance_proc_id=proc_id,
        instance_uptime=uptime(millis=False),
        instance_num_requests=num_requests_processed,
        instance_error_rate=f'{float(f"{num_request_errors / max(1, num_requests_processed):.1g}"):g}',
        instance_mean_response_time=round(
            total_request_serving_time_millis / max(1, num_requests_processed)
        )
        / 1000,
    )


@base.route("/about_flywire", methods=["GET", "POST"])
@request_wrapper
def about_flywire():
    log_activity("Loading About FlyWire Dataset page")
    return render_template(
        "about_flywire.html",
    )


@base.route("/account", methods=["GET"])
@request_wrapper
def account():
    log_activity("Loading Account page")
    return render_template(
        "account.html",
        user_email=fetch_user_email(session),
        user_name=fetch_user_name(session),
        user_picture=fetch_user_picture(session),
    )


@base.route("/faq", methods=["GET", "POST"])
@request_wrapper
def faq():
    log_activity("Loading FAQ page")
    message_sent = False
    if request.method == "POST":
        msg = request.form.get("user_message")
        if msg:
            log_user_help(f"From FAQ page: {msg}")
            message_sent = True
    return render_template(
        "faq.html",
        faq_dict=FAQ_QA_KB,
        user_email=fetch_user_email(session),
        message_sent=message_sent,
    )


@base.route("/feedback_note", methods=["POST"])
@request_wrapper
def feedback_note():
    note = request.json.get("note")
    log_user_help(f"Submitting feedback: {note}")
    return jsonify({"message": "note received"})


@base.route("/", defaults={"path": ""})
@base.route("/<path:path>")
@request_wrapper
def index(path):
    if path:
        log_activity(f"Handling catch all with {path=}")
        destination_route = OBSOLETE_ROUTE_DESTINATIONS.get(path)
        if destination_route:
            destination_url = request.url.replace(f"/{path}", f"/{destination_route}")
            log_activity(
                f"Destination route for {path}: {destination_route}. Redirecting to {destination_url}"
            )
            message = (
                f"The URL you pointed to has permanently moved to "
                f"<a href=\"{destination_url}\">{destination_url.replace('http://', '')}</a> </br>Please "
                f"update your bookmark(s) accordingly."
            )
            return render_error(message=message, title="Use updated URL", back_button=0)
        else:
            if not any([bt in path for bt in ["favicon", "robots"]]):
                log_error(f"No destination found for {path=}, redirecting to home page")
            return redirect("/")
    elif request.args.get("filter_string"):
        log_activity("Searching from home page")
        return redirect(
            url_for("app.search", filter_string=request.args.get("filter_string"))
        )
    else:
        data_version = request.args.get("data_version", DEFAULT_DATA_SNAPSHOT_VERSION)
        log_activity(f"Loading home page for {data_version=}")
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
                "asset_filename": "card-network.jpg",
                "url": "app.connectivity",
            },
            {
                "header": "Pathways",
                "body": "Analyse shortest-paths between pairs of neurons",
                "asset_filename": "card-pathways.png",
                "url": "app.path_length",
            },
            {
                "header": "NBLAST",
                "body": "Pairwise morphological similarity scores for sets of neurons",
                "asset_filename": "card-nblast.jpg",
                "url": "app.nblast",
            },
            {
                "header": "Download Data",
                "body": "Export raw data for analysis with other tools / programs",
                "asset_filename": "card-data.png",
                "url": "api.download",
            },
        ]
        neuron_db = NeuronDataFactory.instance().get(version=data_version)
        return render_template(
            "index.html",
            card_data=card_data,
            data_version_infos=sorted(
                DATA_SNAPSHOT_VERSION_DESCRIPTIONS.values(), reverse=True
            ),
            num_cells="{:,}".format(neuron_db.num_cells()),
            num_synapses="{:,}".format(neuron_db.num_synapses()),
            num_labels="{:,}".format(neuron_db.num_labels()),
            default_version=DEFAULT_DATA_SNAPSHOT_VERSION,
        )


def render_auth_page(redirect_to="/"):
    log_activity(f"Rendering auth page with redirect to {redirect_to}")
    return render_template(
        "auth.html",
        client_id=GOOGLE_CLIENT_ID,
        support_email=SUPPORT_EMAIL,
        redirect_to=redirect_to,
    )


@base.route("/login", methods=["GET", "POST"])
@request_wrapper
def login():
    if request.method == "POST":
        try:
            log(f"Attempting to login: {request.form}")
            id_info = id_token.verify_oauth2_token(
                request.form["credential"], requests.Request(), GOOGLE_CLIENT_ID
            )
            # ID token is valid. Save it to session and redirect to home page.
            log_activity(f"Logged in: {id_info}")
            session.permanent = True
            store_user_info(session, id_info=id_info)
            return redirect(request.args.get("redirect_to", "/"))
        except ValueError:
            log_activity(f"Invalid token provided upon login: {request.form}")
            return render_error("Login failed.")
    else:
        return render_auth_page()


@base.route("/data_access_token", methods=["GET", "POST"])
@request_wrapper
def data_access_token():
    log_activity("Loading data access token form")
    if request.method == "POST":
        access_token = extract_access_token(request.form.get("access_token", ""))
        url = resp = access_payload = None
        try:
            url = f"https://globalv1.flywire-daf.com/auth/api/v1/user/cache?middle_auth_token={access_token}"
            resp = get_request(url=url)
            access_payload = resp.json()
            log(f"Auth payload: {access_payload}")
        except Exception as e:
            log_error(
                f"Could not parse auth response: {access_token=} {url=} {resp=} {e=}"
            )

        if access_payload and "view" in access_payload.get("permissions_v2", {}).get(
            "fafb", {}
        ):
            log_activity(f"Data access granted: {access_payload}")
            store_flywire_data_access(
                session, access_token=access_token, access_payload=access_payload
            )
            return redirect(request.args.get("redirect_to", "/"))
        else:
            log_activity(f"Data access denied: {access_payload}")
            message = (
                "The provided token does not grant access to FlyWire data. If you have been granted access in "
                "the past, make sure you obtain the token using the same account (go back and try again). To "
                'request access visit <a href="https://join.flywire.ai" target="_blank">this page</a>.'
            )
            return render_error(message=message)
    else:
        return render_template(
            "data_access_token.html", redirect_to=request.args.get("redirect_to", "/")
        )


@base.route("/logout", methods=["GET", "POST"])
@request_wrapper
def logout():
    log_activity("Logging out")
    delete_cookies(session)
    return render_auth_page()


@base.route("/auth_token", methods=["GET"])
@request_wrapper
def auth_token():
    log_activity("Showing auth token")
    token = fetch_flywire_token(session)
    return render_info(title="Your auth token (don't share)", message=token)


def render_error(
    message="No details available.", title="Something went wrong", back_button=1
):
    log_error(f"Rendering error: {message=} {title=}")
    return redirect(f"/error?message={message}&title={title}&back_button={back_button}")


def render_info(title="Info", message="Operation complete."):
    log_activity(f"Rendering info: {message}")
    return render_template("info.html", title=title, message=message)


@base.route("/todo_list", methods=["GET"])
def todo_list():
    log_activity("Loading todo list")
    return redirect(
        "https://docs.google.com/document/d/1iPtT9teD9i2k2YN7XrKjeY9UwPo7s9CNFWtmCkRelkg/edit?usp=sharing"
    )


@base.route("/demo_clip", methods=["GET"])
def demo_clip():
    log_activity("Loading demo clips")
    return redirect("https://www.youtube.com/@flywireprinceton4189/search?query=codex")


def activity_suffix(filter_string, data_version):
    return (f"for '{truncate(filter_string, 50)}'" if filter_string else "") + (
        f" (v{data_version})" if data_version != DEFAULT_DATA_SNAPSHOT_VERSION else ""
    )


@base.route("/skeleton_thumbnail_url")
@request_wrapper
def skeleton_thumbnail_url():
    cell_or_neuropil = request.args.get("cell_or_neuropil")
    animated = request.args.get("animated", type=bool, default=False)
    log_request = request.args.get("log_request", default=1, type=int)
    url = url_for_skeleton(cell_or_neuropil=cell_or_neuropil, animated=animated)
    if log_request:
        log_activity(
            f"Fetching skeleton URL for {cell_or_neuropil}: {format_link(url)}"
        )
    return redirect(url, code=302)
