import csv
import gc
import gzip
import os
import pickle
from datetime import datetime

from src.data.neuron_data import NeuronDB
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS
from src.utils.logging import log, log_error
from src.utils.networking import download

DATA_ROOT_PATH = "static/data"
NEURON_DATA_FILE_NAME = "neuron_data.csv.gz"
CONNECTIONS_FILE_NAME = "connections_5syn.csv.gz"
LABELS_FILE_NAME = "labels.csv.gz"
COORDINATES_FILE_NAME = "coordinates.csv.gz"
NEURON_DB_PICKLE_FILE_NAME = "neuron_db.pickle.gz"

GCS_PICKLE_URL_TEMPLATE = "https://storage.googleapis.com/flywire-data/codex/data/{version}/neuron_db.pickle.gz"


def data_file_path_for_version(version, data_root_path=DATA_ROOT_PATH):
    return f"{data_root_path}/{version}"


def load_neuron_db(data_root_path=DATA_ROOT_PATH, version=None):
    if version is None:
        version = LATEST_DATA_SNAPSHOT_VERSION
    data_file_path = data_file_path_for_version(
        version=version, data_root_path=data_root_path
    )
    log(f"App initialization loading data from {data_file_path}...")
    neuron_data_rows = read_csv(f"{data_file_path}/{NEURON_DATA_FILE_NAME}")
    if os.path.exists(f"{data_file_path}/{CONNECTIONS_FILE_NAME}"):
        connection_rows = read_csv(f"{data_file_path}/{CONNECTIONS_FILE_NAME}")
    else:
        connection_rows = []

    if os.path.exists(f"{data_file_path}/{LABELS_FILE_NAME}"):
        label_rows = read_csv(f"{data_file_path}/{LABELS_FILE_NAME}")
        labels_file_timestamp = os.path.getmtime(f"{data_file_path}/{LABELS_FILE_NAME}")
        labels_file_timestamp = datetime.utcfromtimestamp(
            labels_file_timestamp
        ).strftime("%Y-%m-%d")
        log(f"Labels file timestamp: {labels_file_timestamp}")
    else:
        label_rows = []
        labels_file_timestamp = "?"

    if os.path.exists(f"{data_file_path}/{COORDINATES_FILE_NAME}"):
        coordinate_rows = read_csv(f"{data_file_path}/{COORDINATES_FILE_NAME}")
    else:
        coordinate_rows = []

    log(
        f"App initialization loaded {len(neuron_data_rows)} items from {data_file_path}, "
        f"{len(connection_rows)} connection rows, "
        f"{len(label_rows)} label rows, "
        f"{len(coordinate_rows)} coordinate rows."
    )
    neuron_db = NeuronDB(
        data_file_rows=neuron_data_rows,
        connection_rows=connection_rows,
        label_rows=label_rows,
        labels_file_timestamp=labels_file_timestamp,
        coordinate_rows=coordinate_rows,
    )
    # free mem
    del neuron_data_rows
    del connection_rows
    return neuron_db


def unpickle_neuron_db(version, data_root_path=DATA_ROOT_PATH):
    try:
        fldr = data_file_path_for_version(
            version=version, data_root_path=data_root_path
        )
        pf = f"{fldr}/{NEURON_DB_PICKLE_FILE_NAME}"
        if not os.path.isfile(pf):
            log(f"App initialization downloading pickle for version {version}")
            ok = download(
                url=GCS_PICKLE_URL_TEMPLATE.format(version=version), dest_folder=fldr
            )
            if not ok:
                raise RuntimeError(
                    f"Failed to download data file for {version=} and {data_root_path=}"
                )
        with gzip.open(pf, "rb") as handle:
            gc.disable()
            db = pickle.load(handle)
            gc.enable()
            log(f"App initialization pickle loaded for version {version}")
            return db
    except Exception as e:
        log_error(f"Failed to load DB for data version {version}: {e}")
        return None


def unpickle_all_neuron_db_versions(data_root_path=DATA_ROOT_PATH):
    return {
        v: unpickle_neuron_db(version=v, data_root_path=data_root_path)
        for v in DATA_SNAPSHOT_VERSIONS
    }


def load_and_pickle_all_neuron_db_versions(data_root_path=DATA_ROOT_PATH):
    for v in DATA_SNAPSHOT_VERSIONS:
        try:
            db = load_neuron_db(version=v, data_root_path=data_root_path)
            pf = f"{data_file_path_for_version(version=v, data_root_path=data_root_path)}/{NEURON_DB_PICKLE_FILE_NAME}"
            with gzip.open(pf, "wb") as handle:
                pickle.dump(db, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            log_error(f"Failed to load and pickle DB for data version {v}: {e}")


# generic CSV file reader with settings
def read_csv(filename, num_rows=None, column_idx=None):
    def col_reader(row):
        return row[column_idx]

    def row_reader(row):
        return row

    def read_from(rdr):
        if num_rows is None and column_idx is None:
            return [r for r in rdr]
        else:
            if num_rows is None:
                return [r[column_idx] for r in rdr]
            reader_func = col_reader if column_idx is not None else row_reader
            res = []
            for r in rdr:
                res.append(reader_func(r))
                if len(res) == num_rows:
                    break
            return res

    if filename.lower().endswith(".gz"):
        with gzip.open(filename, "rt") as f:
            reader = csv.reader(f, delimiter=",", quotechar='"')
            return read_from(reader)
    else:
        with open(filename) as fp:
            reader = csv.reader(fp, delimiter=",", quotechar='"')
            return read_from(reader)


def write_csv(filename, rows, compress=False):
    if compress:
        if not filename.lower().endswith(".gz"):
            filename = filename + ".gz"
        with gzip.open(filename, "wt") as f:
            csv.writer(f, delimiter=",").writerows(rows)
    else:
        with open(filename, "wt") as fp:
            csv.writer(fp, delimiter=",").writerows(rows)
