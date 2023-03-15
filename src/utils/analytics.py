import json

from google.cloud import bigquery

from src.configuration import APP_ENVIRONMENT
from src.utils.logging import log_error

__client = None
__requests_table = None

_DATASET_NAME = "CODEX"
_REQUESTS_TABLE_NAME = f"{APP_ENVIRONMENT}_REQUESTS"

# !! Try to avoid changing this schema. Use 'extra_data' JSON for adding more attributes in future.
# If changing the schema is necessary, it will require creating a new BQ table (e.g. <env>_REQUESTS_V2).
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


def _client():
    global __client
    if __client is None:
        __client = bigquery.Client()
    return __client

def _requests_table():
    global __requests_table
    if __requests_table is None:
        client = _client()
        dataset_ref = client.create_dataset(dataset=_DATASET_NAME, exists_ok=True)
        table_id = f"{dataset_ref.project}.{_DATASET_NAME}.{_REQUESTS_TABLE_NAME}"
        schema = [bigquery.SchemaField(p[0], p[1]) for p in _REQUESTS_TABLE_SCHEMA]
        __requests_table = client.create_table(
            table=bigquery.Table(table_id, schema=schema), exists_ok=True
        )

    return __requests_table


def report_request(request_ctx):
    def _convert(val, datatype):
        if datatype == "JSON":
            return json.dumps(val)
        return val

    try:
        row = tuple(
            [_convert(request_ctx.get(p[0]), p[1]) for p in _REQUESTS_TABLE_SCHEMA]
        )
        errors = _client().insert_rows(_requests_table(), [row])
        if errors:
            log_error(
                f"Analytics record insertion failed. Errors: {errors}, row: {row}"
            )
    except Exception as e:
        if APP_ENVIRONMENT != "DEV":
            log_error(f"Analytics reporting crashed: {e}")
