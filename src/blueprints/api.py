from flask import Blueprint, render_template, request, session
from werkzeug.utils import redirect

from src.blueprints.base import request_wrapper, render_error
from src.data.download_catalog import DOWNLOAD_CATALOG
from src.data.versions import (
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from src.utils.cookies import fetch_user_name
from src.utils.formatting import display
from src.utils.logging import log_user_help

api = Blueprint("api", __name__, url_prefix="/api")


@api.context_processor
def jinja_utils():
    return dict(display=display)


@api.route("/download")
@request_wrapper
def download():
    data_version = request.args.get("data_version", "")
    if not data_version:  # empty form - initial load
        agree_chk = 0
        data_version = DEFAULT_DATA_SNAPSHOT_VERSION
    else:
        agree_chk = 1
    if data_version not in DOWNLOAD_CATALOG:
        return render_error(
            title="Unknown data version",
            message=f"Download data version not recognized: '{data_version}'",
        )

    data_product = request.args.get("data_product")
    if data_product:
        log_user_help(f"API: downloading '{data_product}' for version '{data_version}'")
        if data_product not in DOWNLOAD_CATALOG[data_version]:
            return render_error(
                title="Unknown resource",
                message=f"Download resource not recognized: '{data_product}'",
            )
        return redirect(DOWNLOAD_CATALOG[data_version][data_product].file_url)
    else:
        log_user_help("API: rendering download page")
        return render_template(
            "download.html",
            agree_chk=agree_chk,
            data_version=data_version,
            data_product=list(DOWNLOAD_CATALOG[data_version].keys())[0],
            data_versions=DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
            download_catalog=DOWNLOAD_CATALOG[data_version],
            user_name=fetch_user_name(session),
        )
