import os

from flask import Flask

from src.blueprints.api import api
from src.blueprints.app import app
from src.blueprints.base import neuron_data_factory, base
from src.utils.logging import log

log("App initialization started")
codex = Flask(__name__)
codex.secret_key = os.environ['FLASK_SECRET_KEY']
codex.config['PERMANENT_SESSION_LIFETIME'] = 12 * 31 * 24 * 60 * 60  # 12 months
codex.register_blueprint(base)
codex.register_blueprint(api)
codex.register_blueprint(app)
log(f"App initialization complete. Loaded data versions {neuron_data_factory.loaded_versions()}")

if __name__ == "__main__":
    codex.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
