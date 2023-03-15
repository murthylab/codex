# Prerequisites:
# pip install google-cloud-logging
# <download codex dev secret json to secrets>
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
    max_results = 1000
    client = logging.Client()

    def get_logs(log_type, date_str):
        return client.logging_api.list_entries(
            resource_names=["projects/murthy-lab-sleap"],
            filter_="resource.type = cloud_run_revision "
            "resource.labels.service_name = codex "
            "resource.labels.location = us-east1 "
            f'timestamp < "{date_str}T23:59:59.0Z" '
            f'timestamp > "{date_str}T00:00:00.0Z" '
            '"@" '
            f'"{LOG_TYPES[log_type]}"',
            max_results=max_results,
        )

    for lt in LOG_TYPES.keys():
        for date_str in ["2023-03-01", "2022-12-10", "2023-02-01", "2023-01-10"]:
            print(f"===============\nFetching logs of type {lt} for {date_str}..")
            log_lines = [["instance", "timestamp", "payload"]]
            for result in get_logs(log_type=lt, date_str=date_str):
                log_data = result.to_api_repr()
                instance_id = log_data["labels"]["instanceId"]
                timestamp = log_data["timestamp"]
                payload = log_data["textPayload"]
                log_lines.append([instance_id, timestamp, payload])
            print(f"Fetched {len(log_lines) - 1}. Saving..")
            write_csv(
                filename=f"logs/{date_str}_{lt}_{len(log_lines) - 1}_logs.csv",
                rows=log_lines,
            )
