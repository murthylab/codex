import datetime
import json
import os
from multiprocessing import Process

import requests
from flask import session, request, has_request_context
from user_agents import parse as parse_ua

from src.configuration import proc_id, host_name, APP_ENVIRONMENT
from src.utils.cookies import fetch_user_name, fetch_user_email, is_granted_data_access

startup_time = datetime.datetime.now()


def uptime(millis=True):
    ut = str(datetime.datetime.now() - startup_time)

    # remove leading zeroes and colons
    for i, c in enumerate(ut):
        if c not in [":", "0"]:
            ut = ut[i:]
            break

    parts = ut.split(".")
    if millis and len(parts) > 1:
        return f"{parts[0]}.{parts[1][:2]}"
    else:
        return parts[0]


SLKHKACT = os.environ.get("HK_ACTIVITY")
SLCKHKHB = os.environ.get("HK_DEV")
SLCKHKSOS = os.environ.get("HK_HELP")


def user_agent():
    try:
        return str(parse_ua(str(request.user_agent)))
    except Exception:
        return ""


def _is_smoke_test_request():
    try:
        return request.args.get("smoke_test", "") == os.environ.get("SMOKE_TEST_KEY")
    except Exception:
        return False


def _fetch_client_info():
    try:
        ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
        return f"<https://ipinfo.io/{ip_addr}|{user_agent()}>"
    except Exception:
        return None


def with_url_link(txt):
    try:
        format_link(request.url, txt)
    except Exception:
        return txt


def log(msg):
    msg = f"{proc_id} > {uptime()} > {msg}"
    if "localhost" != host_name:
        msg = f"{host_name} > {msg}"

    client_info = _fetch_client_info()
    if client_info:
        msg = f"{client_info} > {msg}"

    user_info = fetch_user_email(session)
    if user_info:
        msg = f"{user_info} > {msg}"
    print(msg)
    return msg


def _post_to_slk(username, access_granted, text, real_user_activity, extra_hk):
    if any(
        [
            bot in text
            for bot in [
                "Slackbot-LinkExpanding",
                "Spider",
                "FullStoryBot",
                "Googlebot",
                "AhrefsBot",
                "Other / Other / Other",
            ]
        ]
    ):
        log(f"Skipping SLK post from bots: {text}")
        return

    hks = [
        SLKHKACT if real_user_activity else SLCKHKHB
    ]  # default or hook for test/dev/heartbit query logs
    if extra_hk:
        hks.append(extra_hk)  # additional channels (optional)
    res = [
        requests.post(
            hk,
            data=json.dumps(
                {
                    "username": username or "unknown",
                    "icon_emoji": ":large_green_circle:"
                    if access_granted
                    else ":large_yellow_circle:",
                    "text": text,
                    "unfurl_links": False,
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        for hk in hks
        if hk
    ]
    log(f"SLK post response(s): {res}")


def post_to_slk(text, hk=None):
    real_user_activity = APP_ENVIRONMENT != "DEV" and not _is_smoke_test_request()
    if has_request_context():
        username = fetch_user_name(session)
        access_granted = is_granted_data_access(session)
    else:
        username = access_granted = None
    Process(
        target=_post_to_slk,
        args=(username, access_granted, text, real_user_activity, hk),
        daemon=True,
    ).start()


def log_activity(msg):
    msg = log(f":eyes: {with_url_link('go')} > {msg}")
    post_to_slk(msg)


def log_warning(msg):
    msg = log(f":warning: > {msg}")
    post_to_slk(msg)


def log_error(msg):
    msg = log(f":exclamation: > {msg}")
    post_to_slk(msg, hk=SLCKHKSOS)


def log_user_help(msg):
    msg = log(f":sos: > {msg}")
    post_to_slk(msg, hk=SLCKHKSOS)


def format_link(url, tag="link"):
    return f"<{url}|{tag}>"
