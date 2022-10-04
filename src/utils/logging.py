import requests
import datetime
import uuid
import base64
import json
import os
import socket
from multiprocessing import Process
from flask import session, request
from user_agents import parse as parse_ua

DEV_LOGGING = str(os.environ.get('PROD_MODE')) != '1'

proc_id = str(uuid.uuid4())[-4:] + ('-D' if DEV_LOGGING else '-P')
host_name = socket.gethostname()

startup_time = datetime.datetime.now()
def uptime(millis=True):
    ut = str(datetime.datetime.now() - startup_time)

    # remove leading zeroes and colons
    for i, c in enumerate(ut):
        if c not in [':', '0']:
            ut = ut[i:]
            break

    parts = ut.split('.')
    if millis:
        return f'{parts[0]}.{parts[1][:2]}'
    else:
        return parts[0]

def b64e(s):
    return base64.b64encode(s.encode()).decode()


def b64d(s):
    return base64.b64decode(s).decode()


SLKHKACT = b64d('aHR0cHM6Ly9ob29rcy5zbGFjay5jb20vc2VydmljZXMvVDNHMjcwUEx'
                'NL0IwM005RDVBVkUyL0VEM1R5YU9tbm9xbDQxV3NFVHlkazlkdg==')
SLCKHKHB = b64d('aHR0cHM6Ly9ob29rcy5zbGFjay5jb20vc2VydmljZXMvVDNHMjcwUEx'
                'NL0IwM1M3Rk02MVFYLzJwMDhRYUFNUjFlWDI0cjZ6UnZkNkpGNw==')
SLCKHKSOS = b64d('aHR0cHM6Ly9ob29rcy5zbGFjay5jb20vc2VydmljZXMvVDNHMjcwUEx'
                 'NL0IwNDFMTjlWREZBL1kzeEVXeGZSVkttejZoQVR6UHU5ajBvcg==')

def _is_smoke_test_request():
    try:
        return request.args.get('smoke_test', '') == os.environ['SMOKE_TEST_KEY']
    except:
        return False


def _fetch_user_info():
    try:
        return session['id_info']['email']
    except:
        return None

def _fetch_client_info():
    try:
        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = str(parse_ua(str(request.user_agent)))
        return f'<https://ipinfo.io/{ip_addr}|{user_agent}'
    except:
        return None


def log(msg):
    msg = f"{proc_id} > {uptime()} > {msg}"
    if 'localhost' != host_name:
        msg = f"{host_name} > {msg}"

    client_info = _fetch_client_info()
    if client_info:
        msg = f"{client_info} > {msg}"

    user_info = _fetch_user_info()
    if user_info:
        msg = f"{user_info} > {msg}"
    print(msg)
    return msg

def _post_to_slk(text, real_user_activity, extra_hk):
    if 'Slackbot-LinkExpanding' in text:
        log(f"Skipping SLK post from bots: {text}")
        return

    hks = [SLKHKACT if real_user_activity else SLCKHKHB]  # default or hook for test/dev/heartbit query logs
    if extra_hk:
        hks.append(extra_hk)  # additional channels (optional)
    res = [requests.post(hk,
                         data=json.dumps({"text": text, "unfurl_links": False}),
                         headers={'Content-Type': 'application/json'})
           for hk in hks]
    log(f"SLK post response(s): {res}")

def post_to_slk(text, hk=None):
    real_user_activity = not DEV_LOGGING and not _is_smoke_test_request()
    Process(target=_post_to_slk, args=(text, real_user_activity, hk), daemon=True).start()


def log_activity(msg):
    msg = log(f':eyes: > {msg}')
    post_to_slk(msg)


def log_error(msg):
    msg = log(f':warning: > {msg}')
    post_to_slk(msg, hk=SLCKHKSOS)


def log_user_help(msg):
    msg = log(f':sos: > {msg}')
    post_to_slk(msg, hk=SLCKHKSOS)


def format_link(url, tag='link'):
    return f'<{url}|{tag}>'
