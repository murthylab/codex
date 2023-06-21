import os
from time import sleep

from flask import Flask, make_response, render_template, session
from flask_limiter import Limiter, RequestLimit
from flask_limiter.util import get_remote_address

from src.blueprints.api import api
from src.blueprints.app import app
from src.blueprints.base import base
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.cookies import fetch_user_email
from src.utils.logging import log, log_error

log("App initialization started")
codex = Flask(__name__)


def limit_exceeded_responder(request_limit: RequestLimit):
    sleep(3)
    log_error(f"Rate limited: {request_limit.limit}")
    return make_response(
        render_template(
            "error.html",
            message="Too many requests issued in a short period of time. This mechanism is in place "
            "to prevent scripts/hacks overloading the service. Limits are generous enough "
            "to not impact human interaction - if you believe this is not the "
            "case please send us a message below and we'll check what happened.",
            title="Rate limited",
            back_button=True,
            message_sent=False,
            user_email=fetch_user_email(session, default_to="email missing"),
        ),
        429,
    )


limiter = Limiter(
    get_remote_address,
    app=codex,
    default_limits=["3000 per day", "1000 per hour", "100 per minute", "3 per second"],
    storage_uri="memory://",
    on_breach=limit_exceeded_responder,
)


if os.environ.get("CODEX_ENABLE_PROFILING", ""):
    from werkzeug.middleware.profiler import ProfilerMiddleware

    codex.wsgi_app = ProfilerMiddleware(codex.wsgi_app)

codex.secret_key = os.environ["FLASK_SECRET_KEY"]
codex.config["PERMANENT_SESSION_LIFETIME"] = 12 * 31 * 24 * 60 * 60  # 12 months
codex.register_blueprint(
    base
)  # Common endpoints, mostly static pages, assets and other resources
codex.register_blueprint(api)  # Programmatic API
codex.register_blueprint(
    app
)  # Web application (search/stats/cell details, other tools)
log(
    f"App initialization complete. Loaded data versions {NeuronDataFactory.instance().loaded_versions()}"
)

if __name__ == "__main__":
    codex.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
