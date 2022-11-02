from flask import Blueprint

from src.blueprints.base import request_wrapper, require_data_access, render_error
from src.utils.logging import log_activity

api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/")
@request_wrapper
@require_data_access
def index():
    log_activity(f"Rendering API")
    return render_error(
        message=f"Programmatic access coming soon.", title="Coming soon"
    )
