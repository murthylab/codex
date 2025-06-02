import csv
import gc
import gzip
import os
import pickle
from datetime import datetime, UTC

from codex.data.neuron_data_initializer import (
    initialize_neuron_data,
    NEURON_DATA_ATTRIBUTE_TYPES,
)
from codex.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS
from codex.utils.networking import download

from codex import logger

DATA_ROOT_PATH = "static/data"
NEURON_FILE_NAME = "neurons.csv.gz"
CLASSIFICATION_FILE_NAME = "classification.csv.gz"
CONSOLIDATED_CELL_TYPES_FILE_NAME = "consolidated_cell_types.csv.gz"
CELL_STATS_ROWS = "cell_stats.csv.gz"
CONNECTIONS_FILE_NAME = "connections.csv.gz"
LABELS_FILE_NAME = "labels.csv.gz"
COORDINATES_FILE_NAME = "coordinates.csv.gz"
NBLAST_FILE_NAME = "nblast.csv.gz"
CONNECTIVITY_TAGS_FILE_NAME = "connectivity_tags.csv.gz"


NEURON_DB_PICKLE_FILE_NAME = "neuron_db.pickle.gz"

GCS_PICKLE_URL_TEMPLATE = "https://storage.googleapis.com/flywire-data/codex/data/fafb/{version}/neuron_db.pickle.gz"
GCS_RAW_DATA_URL_TEMPLATE = (
    "https://storage.googleapis.com/flywire-data/codex/data/fafb/{version}/{filename}"
)


def data_file_path_for_version(version, data_root_path=DATA_ROOT_PATH):
    return f"{data_root_path}/{version}"


def load_neuron_db(data_root_path=DATA_ROOT_PATH, version=None):
    if version is None:
        version = DEFAULT_DATA_SNAPSHOT_VERSION
    data_file_path = data_file_path_for_version(
        version=version, data_root_path=data_root_path
    )
    print(f" loading data from {data_file_path}...")

    def _read_data(filename, with_timestamp=False):
        fname = f"{data_file_path}/{filename}"
        if not os.path.exists(fname):
            print(f" downloading raw data file {filename} for version {version}..")
            ok = download(
                url=GCS_RAW_DATA_URL_TEMPLATE.format(
                    version=version, filename=filename
                ),
                dest_folder=data_file_path,
            )
            if not ok:
                print(
                    f"WARNING: Raw data file {filename} for version {version} could not be downloaded"
                )

        if os.path.exists(fname):
            rows = read_csv(fname)
            if with_timestamp:
                return rows, datetime.fromtimestamp(
                    os.path.getmtime(fname), UTC
                ).strftime("%Y-%m-%d")
            else:
                return rows
        else:
            if with_timestamp:
                return [], "?"
            else:
                return []

    neuron_rows = _read_data(NEURON_FILE_NAME)
    classification_rows = _read_data(CLASSIFICATION_FILE_NAME)
    cell_type_rows = _read_data(CONSOLIDATED_CELL_TYPES_FILE_NAME)
    cell_stats_rows = _read_data(CELL_STATS_ROWS)
    connection_rows = _read_data(CONNECTIONS_FILE_NAME)
    label_rows, labels_file_timestamp = _read_data(
        LABELS_FILE_NAME, with_timestamp=True
    )
    coordinate_rows = _read_data(COORDINATES_FILE_NAME)
    nblast_rows = _read_data(NBLAST_FILE_NAME)
    connectivity_tag_rows = _read_data(CONNECTIVITY_TAGS_FILE_NAME)

    print(
        f" loading data from {data_file_path}:\n"
        f"   {len(neuron_rows)} neuron rows\n"
        f"   {len(connection_rows)} connection rows\n"
        f"   {len(label_rows)} label rows ({labels_file_timestamp})\n"
        f"   {len(coordinate_rows)} coordinate rows\n"
        f"   {len(nblast_rows)} nblast rows\n"
    )
    neuron_db = initialize_neuron_data(
        neuron_file_rows=neuron_rows,
        classification_rows=classification_rows,
        cell_type_rows=cell_type_rows,
        cell_stats_rows=cell_stats_rows,
        connection_rows=connection_rows,
        label_rows=label_rows,
        labels_file_timestamp=labels_file_timestamp,
        coordinate_rows=coordinate_rows,
        nblast_rows=nblast_rows,
        connectivity_tag_rows=connectivity_tag_rows,
    )
    # free mem
    del neuron_rows
    del connection_rows
    del label_rows
    del coordinate_rows
    del cell_type_rows
    return neuron_db


def unpickle_neuron_db(version, data_root_path=DATA_ROOT_PATH):
    try:
        fldr = data_file_path_for_version(
            version=version, data_root_path=data_root_path
        )
        pf = f"{fldr}/{NEURON_DB_PICKLE_FILE_NAME}"
        if not os.path.isfile(pf):
            print(f" downloading pickle for version {version}")
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
            # For the default data version, we want to make sure the data schema of the sourcecode is consistent with
            # the pre-pickled data file.
            if version == DEFAULT_DATA_SNAPSHOT_VERSION:
                for nd in db.neuron_data.values():
                    if NEURON_DATA_ATTRIBUTE_TYPES != {
                        k: type(v) for k, v in nd.items()
                    }:
                        logger.error(
                            f"Failed to load data {version=}.\nPickled data file is inconsistent with source. "
                            f"If running a local server, delete cached pickle files in the data folder and try again."
                        )
                        exit(1)
            gc.enable()
            print(f" pickle loaded for version {version}")
            return db
    except Exception as e:
        logger.error(f"Failed to load DB for data version {version}: {e}")
        return None


def unpickle_all_neuron_db_versions(data_root_path=DATA_ROOT_PATH):
    return {
        v: unpickle_neuron_db(version=v, data_root_path=data_root_path)
        for v in DATA_SNAPSHOT_VERSIONS
    }


def load_and_pickle_neuron_db_versions(
    data_root_path=DATA_ROOT_PATH, versions=DATA_SNAPSHOT_VERSIONS
):
    for v in versions:
        print(f"Loading data for version {v}..")
        db = load_neuron_db(version=v, data_root_path=data_root_path)
        pf = f"{data_file_path_for_version(version=v, data_root_path=data_root_path)}/{NEURON_DB_PICKLE_FILE_NAME}"
        print(f" writing pickle to {pf}..")
        with gzip.open(pf, "wb") as handle:
            pickle.dump(db, handle, protocol=pickle.HIGHEST_PROTOCOL)
        print("Done.")


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


if __name__ == "__main__":
    load_and_pickle_neuron_db_versions(versions=[DEFAULT_DATA_SNAPSHOT_VERSION])
