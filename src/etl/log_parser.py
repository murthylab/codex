# Prerequisites:
# pip install google-cloud-logging
# <download codex dev secret json to secrets/>
# export GOOGLE_APPLICATION_CREDENTIALS=static/secrets/codex_dev_gcp_secret.json
from google.cloud import logging

from src.data.local_data_loader import write_csv

LOG_TYPES = {
    "activity": ":eyes:",
    "error": ":exclamation:",
    "warning": ":warning:",
    "feedback": ":sos:",
}

if __name__ == "__main__":
    client = logging.Client()

    def get_logs(log_type, max_results=10):
        return client.logging_api.list_entries(
            resource_names=["projects/murthy-lab-sleap"],
            filter_="resource.type = cloud_run_revision "
            "resource.labels.service_name = codex "
            "resource.labels.location = us-east1 "
            '"@" '
            f'"{LOG_TYPES[log_type]}"',
            max_results=max_results,
        )

    def extract_activity_log(res):
        parts = str(res).split("payload=")
        return f"Meta: {parts[0]}\nPayload: {parts[1]}\n"

    for lt in LOG_TYPES.keys():
        print(f"===============\n Logs of type {lt}:")
        log_lines = []
        for result in get_logs(log_type=lt, max_results=2000):
            log_lines.append(extract_activity_log(result))
        print(f"Fetched {len(log_lines)}")
        write_csv(filename=f"logs/{lt}_logs.csv", rows=log_lines)
