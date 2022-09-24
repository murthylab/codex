from collections import defaultdict

import stats_utils
from graph_vis import make_graph_html
from neuron_data_factory import NeuronDataFactory
import nglui_utils
import gcs_data_loader
from logging_utils import log, log_activity, log_error, log_user_help, format_link, _is_smoke_test_request, uptime, \
    host_name, proc_id
from faq_qa_kb import FAQ_QA_KB
from search_index import tokenize
import math
import re
import os
import traceback
from functools import wraps, lru_cache
from flask import Flask, render_template, request, redirect, Response, session, url_for
from google.oauth2 import id_token
from google.auth.transport import requests

log("App initialization started")
app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']

GOOGLE_CLIENT_ID = "356707763910-l9ovf7f2at2vc23f3u2j356aokr4eb99.apps.googleusercontent.com"
SUPPORT_EMAIL = "arie@princeton.edu"

BUILD_GIT_SHA = os.environ.get('BUILD_GIT_SHA', 'na')
BUILD_TIMESTAMP = os.environ.get('BUILD_TIMESTAMP', 'na')

MAX_NEURONS_FOR_DOWNLOAD = 50

neuron_data_factory = NeuronDataFactory(preload_latest=os.environ.get('SKIP_NEURON_DB_LOAD') != 'true')

log(f"App initialization loaded data versions {neuron_data_factory.loaded_versions()}")

num_requests_processed = 0


def request_wrapper(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        global num_requests_processed
        num_requests_processed += 1
        signature = f'func: {func.__name__} endpoint: {request.endpoint} url: {request.url}'
        log(f'>>>>>>> {signature}'
            f' || >>> Args:\n{request.args}'
            f' || >>> Headers:\n{request.headers}'
            f' || >>> Environ:\n{request.environ}'
            f' || >>> Form:\n{request.form}'
            f' || <<<<<<< {signature}\n')

        if 'flywireindex.pniapps.org' in request.url:
            new_url = request.url.replace('flywireindex.pniapps.org', 'code.pniapps.org')
            log_activity(f"Redirecting base URL from  {request.url}: {new_url}")
            return redirect(new_url)
        if 'id_info' not in session and not _is_smoke_test_request():
            if request.endpoint not in ['login', 'logout']:
                return render_auth_page(redirect_to=request.url)
        else:
            log(f"Executing authenticated request for: {session.get('id_info')}")
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            log_error(f"Exception when executing {signature}: {e}")
            return render_error(f'{e}\n')

    return wrap


OBSOLETE_ROUTE_DESTINATIONS = {
    'stats': 'app/stats',
    'explore': 'app/explore',
    'annotation_search': 'app/search',
    'annotation_augmentations': 'app/labeling_suggestions',
    'download_search_results': 'app/download_search_results',
    'search_results_flywire_url': 'app/search_results_flywire_url',
    'flywire_url': 'app/flywire_url',
    'neuron_info': 'app/neuron_info'
}

log("App initialization complete.")


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@request_wrapper
def index(path):
    if path:
        log_activity(f"Handling catch all with {path=}")
        destination_route = OBSOLETE_ROUTE_DESTINATIONS.get(path)
        if destination_route:
            destination_url = request.url.replace(f'/{path}', f'/{destination_route}')
            log_activity(f"Destination route for {path}: {destination_route}. Redirecting to {destination_url}")
            message = f"The URL you pointed to has permanently moved to " \
                      f"<a href=\"{destination_url}\">{destination_url.replace('http://', '')}</a> </br>Please " \
                      f"update your bookmark(s) accordingly."
            return render_error(message=message, title="Use updated URL", back_button=0)
        else:
            if 'favicon.ico' != path:
                log_error(f"No destination found for {path=}, redirecting to home page")
            return redirect('/')
    else:
        log_activity(f"Loading home page")
        return render_template("index.html")


def render_auth_page(redirect_to='/'):
    log_activity(f"Rendering auth page with redirect to {redirect_to}")
    return render_template("auth.html", client_id=GOOGLE_CLIENT_ID, support_email=SUPPORT_EMAIL,
                           redirect_to=redirect_to)


@app.route('/login', methods=['GET', 'POST'])
@request_wrapper
def login():
    if request.method == 'POST':
        try:
            log(f'Attempting to login: {request.form}')
            id_info = id_token.verify_oauth2_token(request.form['credential'], requests.Request(), GOOGLE_CLIENT_ID)
            # ID token is valid. Save it to session and redirect to home page.
            log_activity(f"Logged in: {id_info}")
            session['id_info'] = id_info
            return redirect(request.args.get('redirect_to', '/'))
        except ValueError:
            log_activity(f'Invalid token provided upon login: {request.form}')
            return render_error(f'Login failed.')
    else:
        return render_auth_page()


@app.route('/logout', methods=['GET', 'POST'])
@request_wrapper
def logout():
    log_activity(f"Logging out")
    if 'id_info' in session:
        del session['id_info']
    return render_auth_page()


def render_error(message='No details available.', title='Something went wrong', back_button=1):
    log_error(f"Rendering error: {message=} {title=}")
    return redirect(f'/error?message={message}&title={title}&back_button={back_button}')


def render_info(message='Operation complete.'):
    log_activity(f"Rendering info: {message}")
    return render_template("info.html", message=f'{message}')

def activity_suffix(filter_string, data_version):
    return (f"for '{filter_string}'" if filter_string else '') + \
           (f' (v{data_version})' if data_version != neuron_data_factory.latest_data_version() else '')

@app.route('/app/stats')
@request_wrapper
def stats():
    filter_string = request.args.get('filter_string', '')
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    case_sensitive = request.args.get('case_sensitive', 0, type=int)
    whole_word = request.args.get('whole_word', 0, type=int)

    log_activity(f"Generating stats {activity_suffix(filter_string, data_version)}")
    num_items, hint, caption, data_stats, data_charts = _stats_cached(
        filter_string=filter_string, data_version=data_version, case_sensitive=case_sensitive, whole_word=whole_word
    )
    if num_items:
        log_activity(
            f"Stats got {num_items} results {activity_suffix(filter_string, data_version)}"
        )
    else:
        log_activity(f"No stats {activity_suffix(filter_string, data_version)}, sending hint '{hint}'")

    return render_template(
        "stats.html",
        caption=caption,
        data_stats=data_stats,
        data_charts=data_charts,
        num_items=num_items,
        filter_string=filter_string,
        hint=hint,
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word
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
        data, search_query=filter_string, case_sensitive=case_sensitive, match_words=whole_word,
        data_version=data_version
    )
    return len(filtered_root_id_list), hint, caption, data_stats, data_charts


@app.route('/error', methods=['GET', 'POST'])
@request_wrapper
def error():
    log_activity(f"Loading Error page")
    message = request.args.get('message', 'Unexpected error')
    title = request.args.get('title', 'Request failed')
    back_button = request.args.get('back_button', 1, type=int)
    message_sent = False
    if request.method == 'POST':
        msg = request.form.get('user_message')
        log_user_help(f'From Error page with title {title} and message {message}: {msg}')
        message_sent = True
    return render_template("error.html", message=message, title=title,
                           back_button=back_button,
                           message_sent=message_sent,
                           user_email=session.get('id_info', {}).get('email', 'email missing'), )


@app.route('/about', methods=['GET', 'POST'])
@request_wrapper
def about():
    log_activity(f"Loading About page")
    message_sent = False
    if request.method == 'POST':
        msg = request.form.get('user_message')
        if msg:
            log_user_help(f'From About page: {msg}')
            message_sent = True
    return render_template("about.html",
                           user_email=session['id_info']['email'],
                           user_name=session['id_info']['name'],
                           user_picture=session['id_info']['picture'],
                           message_sent=message_sent,
                           build_git_sha=BUILD_GIT_SHA,
                           build_timestamp=BUILD_TIMESTAMP,
                           instance_host_name=host_name,
                           instance_proc_id=proc_id,
                           instance_uptime=uptime(millis=False),
                           instance_num_requests=num_requests_processed)


@app.route('/faq', methods=['GET', 'POST'])
@request_wrapper
def faq():
    log_activity(f"Loading FAQ page")
    message_sent = False
    if request.method == 'POST':
        msg = request.form.get('user_message')
        if msg:
            log_user_help(f'From FAQ page: {msg}')
            message_sent = True
    return render_template("faq.html",
                           faq_dict=FAQ_QA_KB,
                           user_email=session['id_info']['email'],
                           message_sent=message_sent)


@app.route('/app/explore')
@request_wrapper
def explore():
    log_activity(f"Loading Explore page")
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    return render_template(
        "categories.html",
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        key='class',
        categories=neuron_data_factory.get(data_version).categories())


def render_neuron_list(data_version, template_name, filtered_root_id_list, filter_string, case_sensitive, whole_word,
                       page_number, hint):
    neuron_db = neuron_data_factory.get(data_version)
    num_items = len(filtered_root_id_list)

    if num_items > 20:
        num_pages = math.ceil(num_items / 20)
        page_number = max(page_number, 1)
        page_number = min(page_number, num_pages)
        pagination_info = [
            {'label': 'Prev', 'number': page_number - 1, 'status': ('disabled' if page_number == 1 else '')}
        ]
        for i in [-3, -2, -1, 0, 1, 2, 3]:
            page_idx = page_number + i
            if 1 <= page_idx <= num_pages:
                pagination_info.append(
                    {
                        'label': page_idx,
                        'number': page_idx,
                        'status': ('active' if page_number == page_idx else '')
                    }
                )
        pagination_info.append(
            {'label': 'Next', 'number': page_number + 1, 'status': ('disabled' if page_number == num_pages else '')}
        )
        display_data_ids = filtered_root_id_list[(page_number - 1) * 20:page_number * 20]
    else:
        pagination_info = []
        display_data_ids = filtered_root_id_list

    display_data = [neuron_db.get_neuron_data(i) for i in display_data_ids]

    return render_template(
        template_name_or_list=template_name,
        display_data=display_data,
        # If num results is small enough to pass to browser, pass it to allow copying root IDs to clipboard.
        # Otherwise it will be available as downloadable file.
        root_ids_str=','.join([str(ddi) for ddi in filtered_root_id_list]) if len(
            filtered_root_id_list) <= MAX_NEURONS_FOR_DOWNLOAD else [],
        num_items=num_items,
        pagination_info=pagination_info,
        filter_string=filter_string,
        hint=hint,
        data_versions=neuron_data_factory.available_versions(),
        data_version=data_version,
        case_sensitive=case_sensitive,
        whole_word=whole_word
    )


@app.route('/app/search', methods=['GET'])
@request_wrapper
def search():
    filter_string = request.args.get('filter_string', '')
    page_number = int(request.args.get('page_number', 1))
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    case_sensitive = request.args.get('case_sensitive', 0, type=int)
    whole_word = request.args.get('whole_word', 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)
    hint = None

    log_activity(f"Loading search page {page_number} {activity_suffix(filter_string, data_version)}")
    filtered_root_id_list = neuron_db.search(
        filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    if filtered_root_id_list:
        log_activity(f"Got {len(filtered_root_id_list)} search results {activity_suffix(filter_string, data_version)}")
    else:
        hint = neuron_db.closest_token(filter_string, case_sensitive=case_sensitive)
        log_error(f"No results for '{filter_string}', sending hint '{hint}'")

    return render_neuron_list(
        data_version=data_version,
        template_name='search.html',
        filtered_root_id_list=filtered_root_id_list,
        filter_string=filter_string,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        page_number=page_number,
        hint=hint
    )


@app.route('/app/labeling_suggestions')
@request_wrapper
def labeling_suggestions():
    filter_string = request.args.get('filter_string', '')
    page_number = int(request.args.get('page_number', 1))
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    case_sensitive = request.args.get('case_sensitive', 0, type=int)
    whole_word = request.args.get('whole_word', 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    hint = None

    log_activity(f"Loading labeling suggestions page {page_number} {activity_suffix(filter_string, data_version)}")
    filtered_root_id_list = neuron_db.search_in_neurons_with_inherited_labels(filter_string)

    if filtered_root_id_list:
        log_activity(f"Got {len(filtered_root_id_list)} labeling suggestions {activity_suffix(filter_string, data_version)}")
    else:
        hint = neuron_db.closest_token_from_inherited_tags(filter_string, case_sensitive=case_sensitive)
        log_activity(f"No labeling suggestion results {activity_suffix(filter_string, data_version)}, sending hint '{hint}'")

    return render_neuron_list(
        data_version=data_version,
        template_name='labeling_suggestions.html',
        filtered_root_id_list=filtered_root_id_list,
        filter_string=filter_string,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        page_number=page_number,
        hint=hint
    )


@app.route('/app/accept_label_suggestion')
@request_wrapper
def accept_label_suggestion():
    from_root_id = request.args.get('from_root_id')
    to_root_id = request.args.get('to_root_id')
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    neuron_db = neuron_data_factory.get(data_version)

    from_neuron = neuron_db.get_neuron_data(from_root_id)
    to_neuron = neuron_db.get_neuron_data(to_root_id)

    log_activity(f"Accepting label suggestion from\n{from_root_id}: {from_neuron}\nto\n{to_root_id}: {to_neuron}")

    if not from_neuron or not to_neuron:
        return render_error(f"Neurons for Cell IDs {from_root_id} and/or {to_root_id} not found.")

    return render_info(f"Label(s) <b> {from_neuron['annotations']} </b> assigned to Cell ID <b> {to_root_id} </b>")


@app.route('/app/reject_label_suggestion')
@request_wrapper
def reject_label_suggestion():
    from_root_id = request.args.get('from_root_id')
    to_root_id = request.args.get('to_root_id')
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    neuron_db = neuron_data_factory.get(data_version)

    from_neuron = neuron_db.get_neuron_data(from_root_id)
    to_neuron = neuron_db.get_neuron_data(to_root_id)

    log_activity(f"Rejecting label suggestion from\n{from_root_id}: {from_neuron}\nto\n{to_root_id}: {to_neuron}")

    if not from_neuron or not to_neuron:
        return render_error(f"Neurons for Cell IDs {from_root_id} and/or {to_root_id} not found.")

    return render_info(f"Label suggestion rejected.")


@app.route("/app/download_search_results")
@request_wrapper
def download_search_results():
    filter_string = request.args.get('filter_string', '')
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    case_sensitive = request.args.get('case_sensitive', 0, type=int)
    whole_word = request.args.get('whole_word', 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    log_activity(f"Downloading search results {activity_suffix(filter_string, data_version)}")
    filtered_root_id_list = neuron_db.search(
        search_query=filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    log_activity(
        f"For download got {len(filtered_root_id_list)} results {activity_suffix(filter_string, data_version)}"
    )

    cols = ['root_id', 'annotations', 'kind', 'nt_type', 'class', 'hemisphere_fingerprint']
    data = [cols]
    for i in filtered_root_id_list:
        data.append([str(neuron_db.get_neuron_data(i)[c]).replace(',', ';') for c in cols])

    fname = f"search_results_{re.sub('[^0-9a-zA-Z]+', '_', filter_string)}.csv"
    return Response(
        "\n".join([",".join(r) for r in data]),
        mimetype="text/csv",
        headers={
            "Content-disposition": f"attachment; filename={fname}"
        }
    )


@app.route("/app/root_ids_from_search_results")
@request_wrapper
def root_ids_from_search_results():
    filter_string = request.args.get('filter_string', '')
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    case_sensitive = request.args.get('case_sensitive', 0, type=int)
    whole_word = request.args.get('whole_word', 0, type=int)
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
        headers={
            "Content-disposition": f"attachment; filename={fname}"
        }
    )


@app.route('/app/search_results_flywire_url')
@request_wrapper
def search_results_flywire_url():
    filter_string = request.args.get('filter_string', '')
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    case_sensitive = request.args.get('case_sensitive', 0, type=int)
    whole_word = request.args.get('whole_word', 0, type=int)
    neuron_db = neuron_data_factory.get(data_version)

    log_activity(f"Generating URL search results {activity_suffix(filter_string, data_version)}")
    filtered_root_id_list = neuron_db.search(
        filter_string, case_sensitive=case_sensitive, word_match=whole_word
    )
    log_activity(
        f"For URLs got {len(filtered_root_id_list)} results {activity_suffix(filter_string, data_version)}"
    )

    url = nglui_utils.url_for_random_sample(filtered_root_id_list, MAX_NEURONS_FOR_DOWNLOAD)
    log_activity(f"Redirecting results {activity_suffix(filter_string, data_version)} to FlyWire {format_link(url)}")
    return redirect(url, code=302)


@app.route('/app/flywire_url')
@request_wrapper
def flywire_url():
    root_ids = [int(request.args.get('root_id'))]
    extra_root_id = request.args.get('extra_root_id')
    if extra_root_id:
        root_ids.append(int(extra_root_id))
    url = nglui_utils.url_for_root_ids(root_ids)
    log_activity(f"Redirecting for {root_ids} to FlyWire {format_link(url)}")
    return redirect(url, code=302)


@app.route('/app/neuron_info')
@request_wrapper
def neuron_info():
    root_id = int(request.args.get('root_id'))
    min_syn_cnt = request.args.get('min_syn_cnt', 5, type=int)
    data_version = request.args.get('data_version', neuron_data_factory.latest_data_version())
    neuron_db = neuron_data_factory.get(data_version)
    log_activity(f"Generating neuron info {activity_suffix(root_id, data_version)}")
    nd = neuron_db.get_neuron_data(root_id=root_id)
    combined_neuron_info = {
        'Type': nd['nt_type'],
        'Classification': nd['class'],
        #'Labels & Coordinates': '<br>'.join(nd['tag'] + nd['position']),
        'Labels': '<br>'.join(nd['tag']),
    }

    def insert_neuron_list_links(key, ids, search_endpoint=None):
        if ids:
            ids = set(ids)
            comma_separated_root_ids = ', '.join([str(rid) for rid in ids])
            if not search_endpoint:
                search_endpoint = f'search?filter_string=id << {comma_separated_root_ids}'
            search_link = f'<a class="btn btn-link" href="{search_endpoint}" target="_blank">{len(ids)} {key}</a>'
            nglui_link = f'<a class="btn btn-info btn-sm" href="{nglui_utils.url_for_root_ids([root_id] + list(ids))}"' \
                         f' target="_blank">FlyWire</a>'
            combined_neuron_info[search_link] = nglui_link

    connectivity = gcs_data_loader.load_connection_table_for_root_id(root_id)
    if connectivity and min_syn_cnt:
        connectivity = [r for r in connectivity if r[3] >= min_syn_cnt]
    if connectivity:
        input_neuropil_synapse_count = defaultdict(int)
        output_neuropil_synapse_count = defaultdict(int)
        input_nt_type_count = defaultdict(int)
        downstream = []
        upstream = []
        for r in connectivity:
            if r[0] == root_id:
                downstream.append(r[1])
                output_neuropil_synapse_count[r[2]] += r[3]
            else:
                assert r[1] == root_id
                upstream.append(r[0])
                input_neuropil_synapse_count[r[2]] += r[3]
                input_nt_type_count[r[4].upper()] += r[3]

        insert_neuron_list_links('input cells (upstream)', upstream,
                                 search_endpoint='search?filter_string={upstream}' + str(root_id))
        insert_neuron_list_links('output cells (downstream)', downstream,
                                 search_endpoint='search?filter_string={downstream}' + str(root_id))

        charts = {}

        def hemisphere_counts(neuropil_counts):
            res = defaultdict(int)
            for k, v in neuropil_counts.items():
                res['Left' if k.upper().endswith('_L') else ('Right' if k.upper().endswith('_R') else 'Center')] += v
            return res

        charts['Inputs / Outputs'] = stats_utils.make_donut_chart_from_counts(
            key_title='Cell', val_title='Count', counts_dict={'Inputs': len(upstream), 'Outputs': len(downstream)}
        )

        if input_neuropil_synapse_count:
            charts['Input Synapse Neuropils'] = stats_utils.make_donut_chart_from_counts(
                key_title='Neuropil', val_title='Synapse count', counts_dict=input_neuropil_synapse_count
            )
            charts['Input Synapse Hemisphere'] = stats_utils.make_donut_chart_from_counts(
                key_title='Hemisphere', val_title='Synapse count', counts_dict=hemisphere_counts(input_neuropil_synapse_count)
            )

        if input_nt_type_count:
            charts['Input Synapse Neurotransmitters'] = stats_utils.make_donut_chart_from_counts(
                key_title='Neurotransmitter Type', val_title='Synapse count', counts_dict=input_nt_type_count
            )

        if output_neuropil_synapse_count:
            charts['Output Synapse Neuropils'] = stats_utils.make_donut_chart_from_counts(
                key_title='Neuropil', val_title='Synapse count', counts_dict=output_neuropil_synapse_count
            )
            charts['Output Synapse Hemisphere'] = stats_utils.make_donut_chart_from_counts(
                key_title='Hemisphere', val_title='Synapse count', counts_dict=hemisphere_counts(output_neuropil_synapse_count)
            )
    else:
        charts = {}

    top_nblast_matches = [i[0] for i in (
                gcs_data_loader.load_nblast_scores_for_root_id(root_id, sort_highest_score=True, limit=10) or []) if
                          i[1] > 0.4 and i[0] != root_id]
    insert_neuron_list_links('cells with similar morphology (NBLAST based)', top_nblast_matches)

    similar_root_ids = [i[0] for i in zip(nd['similar_root_ids'], nd['similar_root_id_scores']) if
                        i[1] > 12 and i[0] != root_id]
    insert_neuron_list_links('cells with similar neuropil projection', similar_root_ids)

    symmetrical_root_ids = [i[0] for i in zip(nd['symmetrical_root_ids'], nd['symmetrical_root_id_scores']) if
                            i[1] > 12 and i[0] != root_id]
    insert_neuron_list_links('cells with similar neuropil projection in opposite hemisphere', symmetrical_root_ids)

    # remove empty items
    combined_neuron_info = {k: v for k, v in combined_neuron_info.items() if v}

    log_activity(f"Generated neuron info for {root_id} with {len(combined_neuron_info)} items")
    return render_template(
        "neuron_info.html",
        caption=f"{nd['kind']}",
        subcaption=f"{root_id}",
        id=root_id,
        neuron_info=combined_neuron_info,
        charts=charts,
        load_connections=1 if connectivity and len(connectivity) > 1 else 0
    )


@app.route('/app/nblast')
@request_wrapper
def nblast():
    root_ids = request.args.get('root_ids', '')
    download = request.args.get('download', 0, type=int)
    log_activity(f"Generating NBLAST table for '{root_ids}' {download=}")
    try:
        root_ids = [int(root_id) for root_id in tokenize(root_ids)]
    except Exception as e:
        return render_error(f"Could not extract valid Cell IDs from {root_ids}: {e}")

    if len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
        return render_error(f"NBLAST scores can be fetched for up to {MAX_NEURONS_FOR_DOWNLOAD} cells at a time.")
    elif len(root_ids) == 1:
        return render_error(message=f"Please provide at least 2 Cell IDs.", title="List is too short")

    empty = ''

    if root_ids:
        if download:
            nblast_scores = [['from \ to'] + root_ids]
        else:
            nblast_scores = [['from \ to'] + [f'({i + 1})' for i, rid in enumerate(root_ids)]]
        column_index = {r: i for i, r in enumerate(gcs_data_loader.load_nblast_scores_header())}
        columns = [column_index.get(rid, -1) for rid in root_ids]
        all_scores = gcs_data_loader.load_nblast_scores_for_root_ids(root_ids)
        for i, rid in enumerate(root_ids):
            scores = all_scores.get(rid)

            if download:
                nblast_scores.append(
                    [rid] + ([(scores[c][1] if j != i else empty) for j, c in enumerate(columns)] if scores else [
                                                                                                                     empty] * len(
                        columns)))
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
                    return f'<a target="_blank" {style} href="search?filter_string=id << {rid},{root_ids[idx]}">{score}</a> ' \
                           f'<a target="_blank" href="search_results_flywire_url?filter_string=id << {rid},{root_ids[idx]}">&#10132;</a>'

                scores_row = [score_with_link(i, c) for i, c in enumerate(columns)] if scores else [empty] * len(
                    columns)
                nblast_scores.append([f'<b>({i + 1})</b> {rid}'] + scores_row)

        if all([all([v == empty for v in row[1:]]) for row in nblast_scores[1:]]):
            return render_error(f"NBLAST scores for Cell IDs {root_ids} are not available. Currently NBLAST scores "
                                f"are available for the central brain cells only (which is around 60% of the dataset).")

        log_activity(f"Generated NBLAST table for {root_ids} {download=}")
    else:
        nblast_scores = []

    if download:
        fname = f"nblast_scores.csv"
        return Response(
            "\n".join([",".join([str(r) for r in row]) for row in nblast_scores]),
            mimetype="text/csv",
            headers={
                "Content-disposition": f"attachment; filename={fname}"
            }
        )
    else:
        nblast_doc = FAQ_QA_KB['nblast']
        return render_template(
            "distance_table.html",
            root_ids=', '.join([str(r) for r in root_ids]),
            distance_table=nblast_scores,
            download_url=url_for('nblast', download=1, root_ids=','.join([str(r) for r in root_ids])),
            info_title=nblast_doc['q'],
            info_text=nblast_doc['a'],
            sample_root_ids="720575940628063479,720575940645542276,720575940626822533,720575940609037432,720575940628445399"
        )


@app.route('/app/path_length')
@request_wrapper
def path_length():
    root_ids = request.args.get('root_ids', '')
    nt_type = request.args.get('nt_type', 'all')
    min_syn_cnt = request.args.get('min_syn_cnt', 5, type=int)
    download = request.args.get('download', 0, type=int)
    log_activity(f"Generating Path Length table for '{root_ids}' {download=} {min_syn_cnt=} {nt_type=}")
    try:
        root_ids = [int(root_id) for root_id in tokenize(root_ids)]
    except Exception as e:
        return render_error(f"Could not extract valid Cell IDs from {root_ids}: {e}")

    if len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
        return render_error(f"Path lengths can be fetched for up to {MAX_NEURONS_FOR_DOWNLOAD} cells at a time.")
    elif len(root_ids) == 1:
        return render_error(f"Please provide at least 2 Cell IDs.", title="List is too short")

    if root_ids:
        distance_matrix = gcs_data_loader.load_precomputed_distances_for_root_ids(root_ids, nt_type=nt_type,
                                                                                  min_syn_cnt=min_syn_cnt,
                                                                                  whole_rows=False)
        if len(distance_matrix) <= 1:
            return render_error(f"Path lengths for Cell IDs {root_ids} are not available.")
        log_activity(f"Generated path lengths table for {root_ids} {download=} {min_syn_cnt=} {nt_type=}")
    else:
        distance_matrix = []

    if download:
        fname = f"path_lengths.csv"
        return Response(
            "\n".join([",".join([str(r) for r in row]) for row in distance_matrix]),
            mimetype="text/csv",
            headers={
                "Content-disposition": f"attachment; filename={fname}"
            }
        )
    else:
        paths_doc = FAQ_QA_KB['paths']
        return render_template(
            "distance_table.html",
            root_ids=', '.join([str(r) for r in root_ids]),
            min_syn_cnt=min_syn_cnt,
            nt_type=nt_type,
            distance_table=distance_matrix,
            download_url=url_for('path_length', download=1, root_ids=','.join([str(r) for r in root_ids]),
                                 nt_type=nt_type, min_syn_cnt=min_syn_cnt),
            info_title=paths_doc['q'],
            info_text=paths_doc['a'],
            sample_root_ids="720575940626822533, 720575940632905663, 720575940604373932, 720575940628289103"
        )


@app.route('/app/connections')
@request_wrapper
def connections():
    root_ids = request.args.get('root_ids', '')
    nt_type = request.args.get('nt_type', 'all')
    min_syn_cnt = request.args.get('min_syn_cnt', 5, type=int)
    download = request.args.get('download', 0, type=int)
    neuron_db = neuron_data_factory.get()
    log_activity(f"Generating connection table for '{root_ids}' {download=} {min_syn_cnt=} {nt_type=}")
    try:
        root_ids = [int(root_id) for root_id in tokenize(root_ids)]
    except Exception as e:
        return render_error(f"Could not extract valid Cell IDs from {root_ids}: {e}")

    if len(root_ids) > MAX_NEURONS_FOR_DOWNLOAD:
        return render_error(f"Connections can be fetched for up to {MAX_NEURONS_FOR_DOWNLOAD} cells at a time.")

    if root_ids:
        contable = gcs_data_loader.load_connection_table_for_root_ids(root_ids)
        nt_type = nt_type.upper()
        if nt_type and nt_type != 'ALL':
            contable = [r for r in contable if r[4].upper() == nt_type]
        if min_syn_cnt:
            contable = [r for r in contable if r[3] >= min_syn_cnt]
        if len(contable) <= 1:
            return render_error(f"Connections for {min_syn_cnt=}, {nt_type=} and Cell IDs {root_ids} are unavailable.")
        matrix = [['From', 'To', 'Neuropil', 'Synapses', 'Neuro Transmitter']] + contable
        log_activity(f"Generated connections table for {root_ids} {download=} {min_syn_cnt=} {nt_type=}")
    else:
        matrix = []

    if download:
        fname = f"connections.csv"
        return Response(
            "\n".join([",".join([str(r) for r in row]) for row in matrix]),
            mimetype="text/csv",
            headers={
                "Content-disposition": f"attachment; filename={fname}"
            }
        )
    else:
        return make_graph_html(connection_table=matrix[1:],
                               neuron_data_fetcher=lambda nid: neuron_db.get_neuron_data(nid),
                               center_id=root_ids[0] if len(root_ids) == 1 else None)


@app.route('/app/activity_log')
@request_wrapper
def activity_log():
    log_activity(f"Rendering Activity Log ")
    return render_error(
        message=f'Activity log feature coming soon. It will list a history of recent searches / queries with '
                f'links to results.', title="Coming soon")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
