import datetime
import json
import os
import socket
import uuid
from multiprocessing import Process

import requests
from flask import session, request
from user_agents import parse as parse_ua

APP_ENVIRONMENT = str(os.environ.get("APP_ENVIRONMENT", "PROD"))

proc_id = str(uuid.uuid4())[-4:] + f"-{APP_ENVIRONMENT[:1]}"
host_name = socket.gethostname()

startup_time = datetime.datetime.now()


def uptime(millis=True):
    ut = str(datetime.datetime.now() - startup_time)

    # remove leading zeroes and colons
    for i, c in enumerate(ut):
        if c not in [":", "0"]:
            ut = ut[i:]
            break

    parts = ut.split(".")
    if millis:
        return f"{parts[0]}.{parts[1][:2]}"
    else:
        return parts[0]


SLKHKACT = os.environ.get("HK_ACTIVITY")
SLCKHKHB = os.environ.get("HK_DEV")
SLCKHKSOS = os.environ.get("HK_HELP")


def user_agent():
    try:
        return str(parse_ua(str(request.user_agent)))
    except:
        return ""


def _is_smoke_test_request():
    try:
        return request.args.get("smoke_test", "") == os.environ["SMOKE_TEST_KEY"]
    except:
        return False


def _fetch_user_name():
    try:
        return session["id_info"]["name"]
    except:
        return None


def _fetch_user_email():
    try:
        return session["id_info"]["email"]
    except:
        return None


def _fetch_client_info():
    try:
        ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
        return f"<https://ipinfo.io/{ip_addr}|{user_agent()}"
    except:
        return None


def log(msg):
    msg = f"{proc_id} > {uptime()} > {msg}"
    if "localhost" != host_name:
        msg = f"{host_name} > {msg}"

    client_info = _fetch_client_info()
    if client_info:
        msg = f"{client_info} > {msg}"

    user_info = _fetch_user_email()
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
            data=json.dumps({
                "username": username or "unknown",
                "icon_emoji": ":large_green_circle:" if access_granted else ":large_yellow_circle:",
                "text": text,
                "unfurl_links": False
            }),
            headers={"Content-Type": "application/json"},
        )
        for hk in hks
        if hk
    ]
    log(f"SLK post response(s): {res}")


def post_to_slk(text, hk=None):
    real_user_activity = APP_ENVIRONMENT != "DEV" and not _is_smoke_test_request()
    username = _fetch_user_name()
    access_granted = "data_access_token" in session
    Process(
        target=_post_to_slk, args=(username, access_granted, text, real_user_activity, hk), daemon=True
    ).start()


def log_activity(msg):
    msg = log(f":eyes: > {msg}")
    post_to_slk(msg)


def log_error(msg):
    msg = log(f":warning: > {msg}")
    post_to_slk(msg, hk=SLCKHKSOS)


def log_user_help(msg):
    msg = log(f":sos: > {msg}")
    post_to_slk(msg, hk=SLCKHKSOS)


def format_link(url, tag="link"):
    return f"<{url}|{tag}>"
