import json
import os

from google.cloud import bigquery

from src.utils.logging import log_error

client = bigquery.Client()

_DATASET_NAME = "CODEX"
_DATASET_REF = client.create_dataset(dataset=_DATASET_NAME, exists_ok=True)
_REQUESTS_TABLE_NAME = f"{os.environ.get('APP_ENVIRONMENT')}_REQUESTS"
_REQUESTS_TABLE_ID = f"{_DATASET_REF.project}.{_DATASET_NAME}.{_REQUESTS_TABLE_NAME}"
_REQUESTS_TABLE_SCHEMA = [
    ("timestamp", "DATETIME"),
    ("func_name", "STRING"),
    ("endpoint", "STRING"),
    ("method", "STRING"),
    ("url", "STRING"),
    ("user_email", "STRING"),
    ("user_name", "STRING"),
    ("user_id", "STRING"),
    ("user_affiliation", "STRING"),
    ("data_access_granted", "BOOL"),
    ("auth_bypass", "BOOL"),
    ("ip_addr", "STRING"),
    ("user_agent", "STRING"),
    ("args", "JSON"),
    ("form", "JSON"),
    ("env", "STRING"),
    ("headers", "STRING"),
    ("exception", "STRING"),
    ("elapsed_time_millis", "INTEGER"),
    ("extra_data", "JSON"),
]

schema = [bigquery.SchemaField(p[0], p[1]) for p in _REQUESTS_TABLE_SCHEMA]
table = client.create_table(
    table=bigquery.Table(_REQUESTS_TABLE_ID, schema=schema), exists_ok=True
)


def report_request(request_ctx):
    def _convert(val, datatype):
        if datatype == "JSON":
            return json.dumps(val)
        return val

    try:
        row = tuple(
            [_convert(request_ctx.get(p[0]), p[1]) for p in _REQUESTS_TABLE_SCHEMA]
        )
        errors = client.insert_rows(table, [row])
        if errors:
            log_error(
                f"Analytics record insertion failed. Errors: {errors}, row: {row}"
            )
    except Exception as e:
        log_error(f"Analytics reporting crashed: {e}")
