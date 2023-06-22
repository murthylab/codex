import os
import uuid
import socket

MIN_SYN_THRESHOLD = 5
MIN_NBLAST_SCORE_SIMILARITY = 4
MAX_NEURONS_FOR_DOWNLOAD = 100
MAX_NODES_FOR_PATHWAY_ANALYSIS = 10

DOWNLOADABLE_FILE_EXTENSION = ".csv.gz"
DOWNLOADABLE_FILE_FORMAT = "compressed CSV file (gzip)"
# take care of various working directories (tests, local app, cloud app, update scripts)
APP_ROOT = os.getenv("APP_HOME", "codex").replace("/", "")
DOWNLOADABLE_FILES_METADATA_FILE = f"{os.getcwd().split(APP_ROOT)[0]}/{APP_ROOT}/src/data/downloadable_files_metadata.json"
DOWNLOADABLE_CSV_TITLES_AND_DESCRIPTIONS = {
    "neurons": "Cell name, group and NT type predictions. "
    "For every cell in the dataset, specifies auto-generated name and group (based on primary input and output "
    "neuropils) as well as the predicted NT type  of the cell along with the prediction scores for individual "
    "NT types.",
    "classification": "Classification / hierarchical annotations. "
    "Soma side, Nerve Type and hierarchical classification for each cell in the dataset. Annotated by the Jefferis"
    ' Lab (<a href="" data-toggle="modal" data-target="#cellAnnotationsModal">additional info</a>)',
    "cell_stats": "Cell size measurements. "
    "Specifies the surface area, cable length and size/volume for each cell in the dataset. Nanometer units.",
    "morphology_clusters": "Clustering / grouping of cells based on their morphology. Cells assigned to same cluster "
    "should be similar in shape. The clustering is done with community detection algorithm on a network induced by "
    "pairwise NBLAST scores. First number in the cluster name is a serial index, the second "
    "number is it's size.",
    "connectivity_clusters": "Clustering / grouping of cells based on their connectivity vectors. "
    "Cells assigned to same cluster should have similar partners up/downstream. The clustering is done with "
    "community detection algorithm on a network induced by "
    "input/output vector Jaccard similarity scores. First number in the cluster name is a "
    "serial index, the second "
    "number is it's size.",
    "connections": "Synaptic connectivity table. "
    "One row for every connected pair of cells broken by neuropil (region). First and second columns contain the "
    "FlyWire Root IDs of the connected pair ('pre/from' and 'post/to' respectively), the third column contains the "
    "neuropil abbreviation, the fourth contains the number of synapses (aggregated across all connection sites of "
    "the respective pair and neuropil), and the fifth column contains the predicted NT type for the synapses.",
    "labels": "Identification tags (labeled by FlyWire community). "
    "Community identification labels with additional information including the author and their affiliation. "
    "One cell might contain zero or more identification labels.",
    "coordinates": "Marked neuron coordinates. "
    "FlyWire Supervoxel IDs and position coordinates for cells in the dataset. One cell might have zero or more "
    "marked coordinates and supervoxel IDs.",
    "neuropil_synapse_table": "In-out synapse & partner counts by neuropil. "
    "For every cell and neuropil (region), contains the number of input and output synapses, as well as the "
    "number of input and output partners the cell has in that neuropil. One row for each cell with the first "
    "column containing the FlyWire Root ID of the cell, followed by a column for every combination of neuropil X "
    "input/output X synapse/partner. Note: this resource is a convenience, it can be derived from the connectivity "
    "table.",
}
DOWNLOADABLE_ARCHIVE_FILES = {
    "skeleton_swc_files": {
        "description": "Gzipped archive of all Skeleton files in SWC format.",
        "file_url": "https://storage.googleapis.com/flywire-data/codex/skeleton_swcs/flywire_skeleton_swcs.tar.gz",
        "file_format": "gzipped tar file",
        "file_size": 329000000,
        "content": {},
    },
    "synapse_coordinates": {
        "description": "Individual synapse coordinates (x, y, z in nanometers). Typically synapse locations are "
        "bounded within a 3D bounding box, for compactness this table only provides coordinates of "
        "a single point in the detected bounding box. Also for compactness, empty pre/post id "
        "columns should be inferred by looking up in the table at the last non-empty value "
        "respectively. Contact flywire@princeton.ai if you need access to more accurate synapse coordinates.",
        "file_url": "https://storage.googleapis.com/flywire-data/codex/data/630/synapse_coordinates.csv.gz",
        "file_format": DOWNLOADABLE_FILE_FORMAT,
        "file_size": 281523733,
        "version": "630",
        "content": {
            "# rows": "32,970,606 (+ header)",
            "# columns": "5",
            "col 1 - pre_root_id": "121,327 unique values in 121,327 rows, empty in 32,849,279 rows",
            "col 2 - post_root_id": "119,687 unique values in 2,612,073 rows, empty in 30,358,533 rows",
            "col 3 - x": "181,181 unique values of type INT in range [97,920 .. 891,008]",
            "col 4 - y": "80,815 unique values of type INT in range [65,152 .. 406,664]",
            "col 5 - z": "6,700 unique values of type INT in range [3,200 .. 271,760]",
        },
    },
}

GOOGLE_CLIENT_ID = (
    "356707763910-l9ovf7f2at2vc23f3u2j356aokr4eb99.apps.googleusercontent.com"
)

ADMIN_DASHBOARD_URLS = {
    "trends": "https://lookerstudio.google.com/reporting/28c81476-62f4-454e-8be2-3feb473e5568",
    "details": "https://lookerstudio.google.com/reporting/980e9b4f-1bd7-41e5-90a1-0e7c443d3fa9",
}

SUPPORT_EMAIL = "arie@princeton.edu"

# TODO: check all places that fetch Cave token before disabling
REQUIRE_FLYWIRE_CAVE_TOKEN = True

BUILD_GIT_SHA = os.environ.get("BUILD_GIT_SHA", "na")
BUILD_TIMESTAMP = os.environ.get("BUILD_TIMESTAMP", "na")
APP_ENVIRONMENT = str(os.environ.get("APP_ENVIRONMENT", "DEV"))

proc_id = str(uuid.uuid4())[-4:] + f"-{APP_ENVIRONMENT[:1]}"
host_name = socket.gethostname()


class RedirectHomeError(ValueError):
    def __init__(self, msg):
        super().__init__(msg)
