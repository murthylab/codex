import csv
import gzip
import io
from functools import lru_cache

import requests

from src.utils.logging import log

GCS_BASE_URL = "https://storage.googleapis.com"
FLYWIRE_DATA_BUCKET = "flywire-data"
FILE_EXTENSION = "csv.gz"


@lru_cache
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
    except Exception as e:
        log(f"Could not download from GCS: {obj_url}, error: {e}")
        return None  # This is not an error necessarily. Data might not exist for certain objects.
