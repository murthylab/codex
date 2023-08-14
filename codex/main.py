import os

from flask import Flask, request, redirect, url_for

from codex.blueprints.app import app
from codex.blueprints.base import base
from codex.data.neuron_data_factory import NeuronDataFactory
from codex.configuration import RedirectHomeError
from codex import logger
import logging

# Set logger level
logger.setLevel(logging.DEBUG)

# Create console handler and set its level to DEBUG
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Add the console handler to the logger
logger.addHandler(ch)

logger.debug("App initialization started")
codex = Flask(__name__)


@app.before_request
def before_request():
    logger.info(f"APP: Processing request to {request.url}")


@codex.errorhandler(RedirectHomeError)
def handle_redirect_home_error(e):
    logger.error(f"Redirecting home due to exception: {e}")
    return redirect(url_for("base.index"))


@codex.errorhandler(404)
def page_not_found(e):
    logger.error(f"404: {e}")
    return redirect(url_for("base.page_not_found"))


# TODO more handlers for other errors

codex.secret_key = os.environ["FLASK_SECRET_KEY"]
codex.config["PERMANENT_SESSION_LIFETIME"] = 12 * 31 * 24 * 60 * 60  # 12 months
codex.register_blueprint(
    base
)  # Common endpoints, mostly static pages, assets and other resources
codex.register_blueprint(
    app
)  # Web application (search/stats/cell details, other tools)

print(
    f"App initialization complete. Loaded data versions {NeuronDataFactory.instance().loaded_versions()}"
)

if __name__ == "__main__":
    codex.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
