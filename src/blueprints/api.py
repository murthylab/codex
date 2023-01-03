from flask import Blueprint, render_template, request, session
from werkzeug.utils import redirect

from src.blueprints.base import request_wrapper, require_data_access, render_error
from src.data.versions import (
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
    LATEST_DATA_SNAPSHOT_VERSION,
)
from src.utils.cookies import fetch_user_name
from src.utils.logging import log_activity, log_user_help, log_error

api = Blueprint("api", __name__, url_prefix="/api")

DOWNLOADABLE_PRODUCTS = {
    "neurons": "Cell / neuron features",
    "connections": "Connectivity table",
    "labels": "Labels (free form annotations)",
    "coordinates": "Marked neuron coordinates",
    "neuropil_synapse_table": "Neurons input/output synapse and partner counts in each neuropil",
}


@api.route("/")
@request_wrapper
@require_data_access
def index():
    log_activity(f"Rendering API")
    return render_error(
        message=f"Programmatic access coming soon.", title="Coming soon"
    )


@api.route("/download")
@request_wrapper
@require_data_access
def download():
    data_version = request.args.get("data_version", LATEST_DATA_SNAPSHOT_VERSION)
    data_product = request.args.get("data_product")
    if data_version not in DATA_SNAPSHOT_VERSION_DESCRIPTIONS:
        return render_error(
            message=f"Download data version not recognized: '{data_version}'"
        )

    if data_product:
        log_user_help(f"API: downloading '{data_product}' for version '{data_version}'")
        if data_product not in DOWNLOADABLE_PRODUCTS:
            return render_error(
                message=f"Download resource not recognized: '{data_product}'"
            )
        return redirect(
            f"https://storage.googleapis.com/flywire-data/codex/data/{data_version}/{data_product}.csv.gz"
        )
    else:
        log_user_help(f"API: rendering download page")
        return render_template(
            "download.html",
            data_version=data_version or LATEST_DATA_SNAPSHOT_VERSION,
            data_product=data_product or list(DOWNLOADABLE_PRODUCTS.keys())[0],
            data_versions=list(DATA_SNAPSHOT_VERSION_DESCRIPTIONS.keys()),
            data_products=DOWNLOADABLE_PRODUCTS,
            user_name=fetch_user_name(session),
        )
