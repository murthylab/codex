import csv
import gzip
import io
from collections import defaultdict
from functools import lru_cache, partial
from multiprocessing import Pool

import requests

from src.utils.logging import log_error, log

GCS_BASE_URL = "https://storage.googleapis.com"
FLYWIRE_DATA_BUCKET = "flywire-data"
FILE_EXTENSION = "csv.gz"

DEFAULT_POOL_SIZE = 1  # TODO: this should be set to 'cpu_count()' once caching works for multiprocess execution


def load_csv_content_from_compressed_object_on_gcs(
    gcs_blob, gcs_bucket=FLYWIRE_DATA_BUCKET
):
    obj_url = f"{GCS_BASE_URL}/{gcs_bucket}/{gcs_blob}.{FILE_EXTENSION}"
    try:
        web_response = requests.get(obj_url, timeout=3, stream=True)
        gz_file = web_response.content
        f = io.BytesIO(gz_file)
        with gzip.GzipFile(fileobj=f) as fh:
            reader = csv.reader(io.TextIOWrapper(fh, "utf8"))
            return [row for row in reader]
    except:
        log(f"Could not download from GCS: {obj_url}")
        return None  # This is not an error necessarily. Data might not exist for certain objects.


"""
NBLAST Scores are stored in single-row zipped CSV files. If concatenated, they form a giant matrix with forward NBLAST
scores for pairs of neurons. Each neuron has a row, that starts with it's own root ID, followed by NBLAST scores from
itself to all the other neurons. There's one special row `header.csv.gz` that contains the columns - Root IDs of all
the neurons in the matrix.
"""
NBLAST_SCORE_OBJECTS_PREFIX = "nblast-scores"


@lru_cache
def load_nblast_scores_header():
    try:
        header_row = load_csv_content_from_compressed_object_on_gcs(
            f"{NBLAST_SCORE_OBJECTS_PREFIX}/header"
        )[0]
        # First item in the header is empty (because each row starts with the 'from' Root ID).
        return [int(rid) for rid in header_row[1:]]
    except Exception as e:
        log_error(f"Exception while loading NBLAST scores header: {e}")


@lru_cache
def load_nblast_scores_for_root_id(
    root_id, with_ids=True, sort_highest_score=False, limit=None
):
    scores = load_csv_content_from_compressed_object_on_gcs(
        f"{NBLAST_SCORE_OBJECTS_PREFIX}/{root_id}"
    )
    if scores:
        try:
            scores = scores[0]  # one row CSV
            assert str(scores[0]) == str(root_id)
            if with_ids:
                header = load_nblast_scores_header()
                assert len(scores) == len(header) + 1
                result = [(rid, float(scores[i + 1])) for i, rid in enumerate(header)]
                if sort_highest_score:
                    result.sort(key=lambda x: x[1], reverse=True)
            else:
                result = [float(s) for s in scores[1:]]
                if sort_highest_score:
                    result.sort(reverse=True)

            return result[:limit] if limit else result
        except Exception as e:
            log_error(f"Exception while loading NBLAST scores for {root_id}: {e}")


def load_nblast_scores_for_root_ids(root_ids, pool_size=DEFAULT_POOL_SIZE):
    # dedupe input
    root_ids = list(set(root_ids))

    log(f"Loading nblast scores for {root_ids} with {pool_size} workers")

    if pool_size > 1:
        pool = Pool(pool_size)
        results = pool.map(load_nblast_scores_for_root_id, root_ids)
        pool.close()
        pool.join()
    else:
        results = [load_nblast_scores_for_root_id(rid) for rid in root_ids]

    log(
        f"Loaded {len(results)} nblast scores for {root_ids} with {pool_size} workers. "
        f"Unsuccessful: {len([r for r in results if not r])}"
    )

    return {p[0]: p[1] for p in zip(root_ids, results)}


"""
Connection tables are stored as CSV files, one for each neuron. A CSV file for neuron A (named 'A.csv.gz')
contains #inputs + #outputs rows, each containing 5 columns: from root id, to root id, neuropil, synapse count, NT type.
And in each row, either 'fromm root id' or 'to root id' value equals to A.
"""
CONNECTION_TABLES_PREFIX = "connection-tables"


@lru_cache
def load_connection_table_for_root_id(root_id):
    table = load_csv_content_from_compressed_object_on_gcs(
        f"{CONNECTION_TABLES_PREFIX}/{root_id}"
    )
    if table:
        try:
            return [[int(r[0]), int(r[1]), r[2], int(r[3]), r[4]] for r in table]
        except Exception as e:
            log_error(f"Exception while loading connection table for {root_id}: {e}")


def load_connections_for_root_id(root_id, by_neuropil, min_syn_cnt=5):
    root_id = int(root_id)
    table = load_connection_table_for_root_id(root_id)
    if by_neuropil:
        downstream = defaultdict(list)
        upstream = defaultdict(list)
    else:
        downstream = []
        upstream = []
    for r in table:
        if r[3] < min_syn_cnt:
            continue
        if r[0] == root_id:
            if by_neuropil:
                downstream[r[2]].append(r[1])
            else:
                downstream.append(r[1])
        else:
            assert r[1] == root_id
            if by_neuropil:
                upstream[r[2]].append(r[0])
            else:
                upstream.append(r[0])
    return downstream, upstream


def load_connection_table_for_root_ids(root_ids, pool_size=DEFAULT_POOL_SIZE):
    # dedupe input
    root_ids = list(set(root_ids))

    log(f"Loading connection tables for {root_ids} with {pool_size} workers")

    if pool_size > 1:
        pool = Pool(pool_size)
        tables = pool.map(load_connection_table_for_root_id, root_ids)
        pool.close()
        pool.join()
    else:
        tables = [load_connection_table_for_root_id(rid) for rid in root_ids]

    log(
        f"Loaded {len(tables)} connection tables for {root_ids} with {pool_size} workers. "
        f"Unsuccessful: {len([r for r in tables if not r])}"
    )

    # concatenate all tables
    result = []
    for table in [t for t in tables if t]:
        result += table

    # dedupe rows as connection tables can be intersecting
    result = set(tuple(i) for i in result)
    result = [list(t) for t in result]

    log(
        f"Loaded {len(result)} rows of connections for {root_ids} with {pool_size} workers."
    )
    return result


"""
Precomputed distances are stored in single-row zipped CSV files. If concatenated, they form a giant matrix with shortest
path distances for pairs of neurons. Each neuron has a row, that contains the shortest path lengths from
itself to all the other neurons. There's one special row `targets.csv.gz` that contains the columns - Root IDs of all
the neurons in the matrix. Values are integers, representing length of shortest path, and equal to '-1' if there's no
path (i.e. when 'to neuron' is not reachable from 'from neuron').
"""
PRECOMPUTED_DISTANCES_PREFIX = "447/precomputed_distances"


def precomputed_distance_path(nt_type, min_syn_cnt, obj):
    return f"{PRECOMPUTED_DISTANCES_PREFIX}/nt_type={nt_type}/min_syn_cnt={min_syn_cnt}/{obj}"


@lru_cache
def load_precomputed_distances_targets(nt_type, min_syn_cnt):
    try:
        header_csv = load_csv_content_from_compressed_object_on_gcs(
            precomputed_distance_path(
                nt_type=nt_type, min_syn_cnt=min_syn_cnt, obj="targets"
            )
        )
        return [int(rid) for rid in header_csv[0]]
    except Exception as e:
        log_error(f"Exception while loading precomputed distance header: {e}")


@lru_cache
def load_precomputed_distances_for_root_id(root_id, nt_type, min_syn_cnt):
    try:
        distances = load_csv_content_from_compressed_object_on_gcs(
            precomputed_distance_path(
                nt_type=nt_type, min_syn_cnt=min_syn_cnt, obj=root_id
            )
        )
        if distances:
            return [int(s) for s in distances[0]]  # one row CSV
    except Exception as e:
        log_error(
            f"Exception while loading distances for {root_id=} {nt_type=} {min_syn_cnt=}: {e}"
        )


def load_precomputed_distances_for_root_ids(
    root_ids, nt_type, min_syn_cnt, whole_rows, pool_size=DEFAULT_POOL_SIZE
):
    # dedupe input
    root_ids = sorted(list(set(root_ids)))

    targets = load_precomputed_distances_targets(
        nt_type=nt_type, min_syn_cnt=min_syn_cnt
    )
    column_idx = {t: i for i, t in enumerate(targets)}

    log(f"Loading precomputed distances for {root_ids} with {pool_size} workers")

    download_func = partial(
        load_precomputed_distances_for_root_id, nt_type=nt_type, min_syn_cnt=min_syn_cnt
    )
    if pool_size > 1:
        pool = Pool(pool_size)
        results = pool.map(download_func, root_ids)
        pool.close()
        pool.join()
    else:
        results = [download_func(rid) for rid in root_ids]

    log(
        f"Loaded {len(results)} precomputed distances for {root_ids} with {pool_size} workers. "
        f"Unsuccessful: {len([r for r in results if not r])}"
    )

    def project_to_found_root_ids(row):
        if whole_rows:
            return row
        else:
            return [row[column_idx[rid]] for rid in root_ids if rid in column_idx]

    table = [["from \\ to"] + project_to_found_root_ids(targets)]
    for p in zip(root_ids, results):
        if p[1]:
            table.append([p[0]] + project_to_found_root_ids(p[1]))
    return table
