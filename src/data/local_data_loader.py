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
NEURON_FILE_NAME = "neurons.csv.gz"
CONNECTIONS_FILE_NAME = "connections.csv.gz"
LABELS_FILE_NAME = "labels.csv.gz"
COORDINATES_FILE_NAME = "coordinates.csv.gz"
CLASSIFICATIONS_FILE_NAME = "classification.csv.gz"
SIMILAR_CELLS_FILE_NAME = "similar_cells.csv.gz"

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

    def _read_data(filename, with_timestamp=False):
        if os.path.exists(f"{data_file_path}/{filename}"):
            rows = read_csv(f"{data_file_path}/{CLASSIFICATIONS_FILE_NAME}")
        else:
            rows = []
        if with_timestamp:
            if rows:
                ts = os.path.getmtime(f"{data_file_path}/{filename}")
                return rows, datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            else:
                return rows, "?"
        else:
            return rows

    neuron_rows = _read_data(NEURON_FILE_NAME)
    connection_rows = _read_data(CONNECTIONS_FILE_NAME)
    label_rows, labels_file_timestamp = _read_data(LABELS_FILE_NAME, with_timestamp=True)
    coordinate_rows = _read_data(COORDINATES_FILE_NAME)
    classification_rows = _read_data(CLASSIFICATIONS_FILE_NAME)
    similar_cell_rows = _read_data(SIMILAR_CELLS_FILE_NAME)

    log(
        f"App initialization loaded {len(neuron_rows)} neurons from {data_file_path} with:"
        f"   {len(connection_rows)} connection rows\n"
        f"   {len(label_rows)} label rows ({labels_file_timestamp})\n"
        f"   {len(coordinate_rows)} coordinate rows\n"
        f"   {len(classification_rows)} classification rows\n"
        f"   {len(similar_cell_rows)} similar cell rows\n"
    )
    neuron_db = NeuronDB(
        neuron_file_rows=neuron_rows,
        connection_rows=connection_rows,
        label_rows=label_rows,
        labels_file_timestamp=labels_file_timestamp,
        coordinate_rows=coordinate_rows,
        classification_rows=classification_rows,
        similar_cell_rows=similar_cell_rows,
    )
    # free mem
    del neuron_rows
    del connection_rows
    del label_rows
    del coordinate_rows
    del classification_rows
    del similar_cell_rows
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
        db = load_neuron_db(version=v, data_root_path=data_root_path)
        pf = f"{data_file_path_for_version(version=v, data_root_path=data_root_path)}/{NEURON_DB_PICKLE_FILE_NAME}"
        with gzip.open(pf, "wb") as handle:
            pickle.dump(db, handle, protocol=pickle.HIGHEST_PROTOCOL)


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
