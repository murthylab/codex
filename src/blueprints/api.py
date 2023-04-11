from collections import namedtuple

from flask import Blueprint, render_template, request, session
from werkzeug.utils import redirect

from src.blueprints.base import request_wrapper, require_data_access, render_error
from src.data.versions import (
    DATA_SNAPSHOT_VERSION_DESCRIPTIONS,
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from src.utils.cookies import fetch_user_name
from src.utils.formatting import display
from src.utils.logging import log_user_help

api = Blueprint("api", __name__, url_prefix="/api")


DOWNLOADABLE_FILE_EXTENSION = ".csv.gz"
DOWNLOADABLE_FILE_FORMAT = "compressed CSV file (gzip)"
DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS = {
    "neurons": (
        "Cell name, group and NT type predictions",
        "For every cell in the dataset, specifies auto-generated name and group (based on primary input and output "
        "neuropils) as well as the predicted NT type  of the cell along with the prediction scores for individual "
        "NT types.",
    ),
    "classification": (
        "Classification / hierarchical annotations",
        "Soma side, Nerve Type and hierarchical classification for each cell in the dataset. Annotated by the Jefferis"
        ' Lab - more details <a href="about_classification">here</a>',
    ),
    "cell_stats": (
        "Cell size measurements",
        "Specifies the surface area, cable length and size/volume for each cell in the dataset. Nanometer units.",
    ),
    "morphology_clusters": (
        "Morphology clusters",
        "Clustering / grouping of cells based on their morphology. Cells assigned to same cluster should be similar in "
        "shape.",
    ),
    "connections": (
        "Connectivity table",
        "One row for every connected pair of cells broken by neuropil (region). First and second columns contain the "
        "FlyWire Root IDs of the connected pair ('pre/from' and 'post/to' respectively), the third column contains the "
        "neuropil abbreviation, the fourth contains the number of synapses (aggregated across all connection sites of "
        "the respective pair and neuropil), and the fifth column contains the predicted NT type for the synapses.",
    ),
    "labels": (
        "Identification tags (labeled by FlyWire community)",
        "Community identification labels with additional information including the author and their affiliation. "
        "One cell might contain zero or more identification labels.",
    ),
    "coordinates": (
        "Marked neuron coordinates",
        "FlyWire Supervoxel IDs and position coordinates for cells in the dataset. One cell might have zero or more "
        "marked coordinates and supervoxel IDs.",
    ),
    "neuropil_synapse_table": (
        "In-out synapse & partner counts by neuropil",
        "For every cell and neuropil (region), contains the number of input and output synapses, as well as the "
        "number of input and output partners the cell has in that neuropil. One row for each cell with the first "
        "column containing the FlyWire Root ID of the cell, followed by a column for every combination of neuropil X "
        "input/output X synapse/partner.",
    ),
}

DOWNLOADABLE_FILE_SIZES = {
    "526": {
        "cell_stats.csv.gz": "1,952,932 bytes",
        "classification.csv.gz": "584,952 bytes",
        "connections.csv.gz": "27,426,837 bytes",
        "coordinates.csv.gz": "3,624,667 bytes",
        "labels.csv.gz": "2,536,462 bytes",
        "neurons.csv.gz": "1,679,896 bytes",
        "neuropil_synapse_table.csv.gz": "2,531,010 bytes",
    },
    "571": {
        "cell_stats.csv.gz": "2,257,920 bytes",
        "classification.csv.gz": "808,205 bytes",
        "connections.csv.gz": "32,220,716 bytes",
        "coordinates.csv.gz": "3,945,113 bytes",
        "labels.csv.gz": "2,536,852 bytes",
        "morphology_clusters.csv.gz": "206,854 bytes",
        "neurons.csv.gz": "1,926,110 bytes",
        "neuropil_synapse_table.csv.gz": "2,866,446 bytes",
    },
}

DOWNLOADABLE_FILE_CONTENTS = {
    "571": {
        "neurons.csv.gz": {
            "# rows": "117,605 (+ header)",
            "# columns": "11",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: name": "all rows contain unique values",
            "column  3: group": "1,524 unique values",
            "column  4: nt_type": "6 unique values in 106,983 rows, empty in remaining 10,622 rows",
            "column  5: nt_type_score": "73 unique values of type float",
            "column  6: da_avg": "100 unique values of type float",
            "column  7: ser_avg": "102 unique values of type float",
            "column  8: gaba_avg": "102 unique values of type float",
            "column  9: glut_avg": "102 unique values of type float",
            "column  10: ach_avg": "102 unique values of type float",
            "column  11: oct_avg": "69 unique values of type float",
        },
        "classification.csv.gz": {
            "# rows": "123,303 (+ header)",
            "# columns": "10",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: flow": "3 unique values in 123,143 rows, empty in remaining 160 rows",
            "column  3: super_class": "10 unique values in 123,160 rows, empty in remaining 143 rows",
            "column  4: class": "34 unique values in 92,138 rows, empty in remaining 31,165 rows",
            "column  5: sub_class": "15 unique values in 3,474 rows, empty in remaining 119,829 rows",
            "column  6: cell_type": "1,031 unique values in 10,466 rows, empty in remaining 112,837 rows",
            "column  7: hemibrain_type": "2,782 unique values in 25,475 rows, empty in remaining 97,828 rows",
            "column  8: hemilineage": "178 unique values in 29,615 rows, empty in remaining 93,688 rows",
            "column  9: side": "4 unique values in 123,301 rows, empty in remaining 2 rows",
            "column  10: nerve": "8 unique values in 9,590 rows, empty in remaining 113,713 rows",
        },
        "cell_stats.csv.gz": {
            "# rows": "120,145 (+ header)",
            "# columns": "4",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: length_nm": "112,149 unique values of type int",
            "column  3: area_nm": "119,800 unique values of type int",
            "column  4: size_nm": "119,724 unique values of type int",
        },
        "morphology_clusters.csv.gz": {
            "# rows": "34,249 (+ header)",
            "# columns": "2",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: cluster": "4,252 unique values",
        },
        "connections.csv.gz": {
            "# rows": "2,502,864 (+ header)",
            "# columns": "5",
            "column  1: pre_root_id": "114,220 unique values of type int",
            "column  2: post_root_id": "114,094 unique values of type int",
            "column  3: neuropil": "75 unique values",
            "column  4: syn_count": "522 unique values of type int",
            "column  5: nt_type": "6 unique values",
        },
        "labels.csv.gz": {
            "# rows": "91,649 (+ header)",
            "# columns": "8",
            "column  1: root_id": "58,601 unique values of type int",
            "column  2: label": "6,205 unique values",
            "column  3: user_id": "122 unique values of type int",
            "column  4: position": "70,255 unique values",
            "column  5: supervoxel_id": "69,481 unique values of type int",
            "column  6: label_id": "all rows contain unique values of type int",
            "column  7: user_name": "119 unique values in 90,997 rows, empty in remaining 652 rows",
            "column  8: user_affiliation": "47 unique values in 90,935 rows, empty in remaining 714 rows",
        },
        "coordinates.csv.gz": {
            "# rows": "179,104 (+ header)",
            "# columns": "3",
            "column  1: root_id": "121,825 unique values of type int",
            "column  2: position": "169,473 unique values",
            "column  3: supervoxel_id": "167,584 unique values of type int",
        },
        "neuropil_synapse_table.csv.gz": {
            "# rows": "117,605 (+ header)",
            "# columns": "301",
        },
    },
    "526": {
        "neurons.csv.gz": {
            "# rows": "101,498 (+ header)",
            "# columns": "11",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: name": "all rows contain unique values",
            "column  3: group": "1,524 unique values",
            "column  4: nt_type": "6 unique values in 92,451 rows, empty in remaining 9,047 rows",
            "column  5: nt_type_score": "73 unique values of type float",
            "column  6: da_avg": "100 unique values of type float",
            "column  7: ser_avg": "102 unique values of type float",
            "column  8: gaba_avg": "102 unique values of type float",
            "column  9: glut_avg": "102 unique values of type float",
            "column  10: ach_avg": "102 unique values of type float",
            "column  11: oct_avg": "70 unique values of type float",
        },
        "classification.csv.gz": {
            "# rows": "103,615 (+ header)",
            "# columns": "10",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: flow": "3 unique values in 103,468 rows, empty in remaining 147 rows",
            "column  3: super_class": "9 unique values in 103,467 rows, empty in remaining 148 rows",
            "column  4: class": "6 unique values in 5,389 rows, empty in remaining 98,226 rows",
            "column  5: sub_class": "all empty",
            "column  6: cell_type": "all empty",
            "column  7: hemibrain_type": "all empty",
            "column  8: hemilineage": "all empty",
            "column  9: side": "4 unique values in 103,609 rows, empty in remaining 6 rows",
            "column  10: nerve": "8 unique values in 9,218 rows, empty in remaining 94,397 rows",
        },
        "cell_stats.csv.gz": {
            "# rows": "103,731 (+ header)",
            "# columns": "4",
            "column  1: root_id": "all rows contain unique values of type int",
            "column  2: length_nm": "97,681 unique values of type int",
            "column  3: area_nm": "103,495 unique values of type int",
            "column  4: size_nm": "103,474 unique values of type int",
        },
        "connections.csv.gz": {
            "# rows": "2,119,440 (+ header)",
            "# columns": "5",
            "column  1: pre_root_id": "98,543 unique values of type int",
            "column  2: post_root_id": "97,968 unique values of type int",
            "column  3: neuropil": "75 unique values",
            "column  4: syn_count": "514 unique values of type int",
            "column  5: nt_type": "6 unique values",
        },
        "labels.csv.gz": {
            "# rows": "91,649 (+ header)",
            "# columns": "8",
            "column  1: root_id": "58,479 unique values of type int",
            "column  2: label": "6,205 unique values",
            "column  3: user_id": "122 unique values of type int",
            "column  4: position": "70,255 unique values",
            "column  5: supervoxel_id": "69,481 unique values of type int",
            "column  6: label_id": "all rows contain unique values of type int",
            "column  7: user_name": "119 unique values in 90,997 rows, empty in remaining 652 rows",
            "column  8: user_affiliation": "47 unique values in 90,935 rows, empty in remaining 714 rows",
        },
        "coordinates.csv.gz": {
            "# rows": "165,334 (+ header)",
            "# columns": "3",
            "column  1: root_id": "113,288 unique values of type int",
            "column  2: position": "155,969 unique values",
            "column  3: supervoxel_id": "154,296 unique values of type int",
        },
        "neuropil_synapse_table.csv.gz": {
            "# rows": "101,498 (+ header)",
            "# columns": "301",
        },
    },
}

DownloadableProduct = namedtuple(
    "Product", "title description file_name file_format file_size file_content"
)

DOWNLOAD_CATALOG = {}
for version, assets in DOWNLOADABLE_FILE_CONTENTS.items():
    DOWNLOAD_CATALOG[version] = {}
    for fname, content in assets.items():
        product = fname.replace(DOWNLOADABLE_FILE_EXTENSION, "")
        DOWNLOAD_CATALOG[version][product] = DownloadableProduct(
            title=DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS[product][0],
            description=DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS[product][1],
            file_name=fname,
            file_format=DOWNLOADABLE_FILE_FORMAT,
            file_size=DOWNLOADABLE_FILE_SIZES[version][fname],
            file_content=content,
        )


@api.context_processor
def jinja_utils():
    return dict(display=display)


@api.route("/download")
@request_wrapper
@require_data_access
def download():
    data_version = request.args.get("data_version")
    if not data_version:  # empty form - initial load
        agree_chk = 0
        data_version = DEFAULT_DATA_SNAPSHOT_VERSION
    else:
        agree_chk = 1
    if data_version not in DOWNLOAD_CATALOG:
        return render_error(
            message=f"Download data version not recognized: '{data_version}'"
        )

    data_product = request.args.get("data_product")
    if data_product:
        log_user_help(f"API: downloading '{data_product}' for version '{data_version}'")
        if data_product not in DOWNLOAD_CATALOG[data_version]:
            return render_error(
                message=f"Download resource not recognized: '{data_product}'"
            )
        return redirect(
            f"https://storage.googleapis.com/flywire-data/codex/data/{data_version}/"
            f"{DOWNLOAD_CATALOG[data_version][data_product].file_name}"
        )
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
