import csv
import gzip
import io
from functools import lru_cache
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
