import csv
import gzip
import pickle

from src.data.neuron_data import NeuronDB
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS
from src.utils.logging import log, log_error

DATA_ROOT_PATH = 'static/data'
NEURON_DATA_FILE_NAME = 'neuron_data.csv.gz'
NEURON_DB_PICKLE_FILE_NAME = 'neuron_db.pickle.gz'


def data_file_path_for_version(version, data_root_path=DATA_ROOT_PATH):
    return f'{data_root_path}/{version}'


def load_neuron_db(data_root_path=DATA_ROOT_PATH, version=None):
    if version is None:
        version = LATEST_DATA_SNAPSHOT_VERSION
    data_file_path = data_file_path_for_version(version=version, data_root_path=data_root_path)
    log(f"App initialization loading data from {data_file_path}...")
    rows = read_csv(f'{data_file_path}/{NEURON_DATA_FILE_NAME}')
    log(f"App initialization loaded {len(rows)} items from {data_file_path}.")
    neuron_db = NeuronDB(rows)
    # free mem
    del rows
    return neuron_db


def unpickle_neuron_db(version, data_root_path=DATA_ROOT_PATH):
    try:
        pf = f'{data_file_path_for_version(version=version, data_root_path=data_root_path)}/{NEURON_DB_PICKLE_FILE_NAME}'
        with gzip.open(pf, 'rb') as handle:
            db = pickle.load(handle)
            log(f"App initialization pickle loaded for version {version}")
            return db
    except Exception as e:
        log_error(f"Failed to load DB for data version {version}: {e}")
        return None


def unpickle_all_neuron_db_versions(data_root_path=DATA_ROOT_PATH):
    return {v: unpickle_neuron_db(version=v, data_root_path=data_root_path)
            for v in DATA_SNAPSHOT_VERSIONS}


def load_and_pickle_all_neuron_db_versions(data_root_path=DATA_ROOT_PATH):
    for v in DATA_SNAPSHOT_VERSIONS:
        try:
            db = load_neuron_db(version=v, data_root_path=data_root_path)
            pf = f'{data_file_path_for_version(version=v, data_root_path=data_root_path)}/{NEURON_DB_PICKLE_FILE_NAME}'
            with gzip.open(pf, 'wb') as handle:
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
