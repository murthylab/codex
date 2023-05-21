import os
import datetime
from flask import request, session
from user_agents import parse as parse_ua

from src.configuration import APP_ENVIRONMENT
from src.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
from src.utils.cookies import (
    fetch_user_email,
    fetch_user_name,
    fetch_flywire_user_id,
    fetch_flywire_user_affiliation,
    is_granted_data_access,
)


def ip_addr():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def user_agent():
    try:
        return str(parse_ua(str(request.user_agent)))
    except Exception:
        return ""


def should_bypass_auth():
    try:
        is_smoke_test = request.args.get("smoke_test", "") == os.environ.get(
            "SMOKE_TEST_KEY"
        )
        is_auth_bypass = (
            os.environ.get("BYPASS_AUTH") and os.environ.get("APP_ENVIRONMENT") == "DEV"
        )
    except Exception:
        return False
    return bool(is_smoke_test or is_auth_bypass)


def build_request_context(func_name, verbose=False):
    return {
        "timestamp": datetime.datetime.now(),
        "func_name": str(func_name),
        "endpoint": str(request.endpoint),
        "method": str(request.method),
        "url": str(request.url),
        "user_email": str(fetch_user_email(session)),
        "user_name": str(fetch_user_name(session)),
        "user_id": str(fetch_flywire_user_id(session)),
        "user_affiliation": str(fetch_flywire_user_affiliation(session)),
        "data_access_granted": str(is_granted_data_access(session)),
        "auth_bypass": str(should_bypass_auth()),
        "ip_addr": str(ip_addr()),
        "user_agent": str(user_agent()),
        "args": {str(k): str(v) for k, v in request.args.items()}
        if request.args
        else {},
        "form": {str(k): str(v) for k, v in request.form.items()}
        if request.form
        else {},
        "env": f'{APP_ENVIRONMENT}:{request.args.get("data_version", f"{DEFAULT_DATA_SNAPSHOT_VERSION}-defaulted")}',
        "headers": str(request.headers) if verbose else "",
        "elapsed_time_millis": 0,
        "exception": "",
        "extra_data": {},  # placeholder attr/column for additional metadata in the future
    }


def set_elapsed_time(ctx, elapsed_time_millis):
    ctx["elapsed_time_millis"] = elapsed_time_millis


def set_exception(ctx, e):
    ctx["exception"] = str(e)
