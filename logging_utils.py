import requests
import datetime
import uuid
import base64
import json
from multiprocessing import Process
import os
import socket
from flask import session, request

DEV_LOGGING = str(os.environ.get('PROD_MODE')) != '1'

proc_id = str(uuid.uuid4())[-4:] + ('-D' if DEV_LOGGING else '-P')
host_name = socket.gethostname()

startup_time = datetime.datetime.now()
def uptime(millis=True):
    ut = datetime.datetime.now() - startup_time
    return ut if millis else str(ut).split('.')[0]


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
        user_agent = request.user_agent
        return f'{ip_addr} {user_agent}'
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

def _post_to_slk(text, real_user_activity, hk):
    if not hk:
        hk = SLKHKACT if real_user_activity else SLCKHKHB # dedicated hook for test/dev/heartbit query logs
    res = requests.post(hk, data=json.dumps({"text": text}), headers={'Content-Type': 'application/json'})
    log(f"SLK post response: {res}")

def post_to_slk(text, hk=None):
    real_user_activity = not DEV_LOGGING and not _is_smoke_test_request()
    Process(target=_post_to_slk, args=(text, real_user_activity, hk), daemon=True).start()


def log_activity(msg):
    msg = log(f'ACTIVITY > {msg}')
    post_to_slk(msg)


def log_error(msg):
    msg = log(f'ERROR > {msg}')
    post_to_slk(msg, hk=SLCKHKSOS)


def log_user_help(msg):
    msg = log(f'HELP > {msg}')
    post_to_slk(msg, hk=SLCKHKSOS)


def format_link(url, tag='link'):
    return f'<{url}|{tag}>'
