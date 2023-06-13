import os

from flask import Flask

from src.blueprints.api import api
from src.blueprints.app import app
from src.blueprints.base import base
from src.data.neuron_data_factory import NeuronDataFactory
from src.utils.logging import log

log("App initialization started")
codex = Flask(__name__)

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
