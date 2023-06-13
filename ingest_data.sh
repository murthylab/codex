#!/usr/bin/env sh
python3 -m src.etl.compile_data && \
python3 -m src.etl.pickle_data && \
python3 -m src.etl.update_download_catalog && \
python3 -m pytest tests/unit -x && \
python3 -m pytest tests/integration -x && \
gsutil -m rsync -r -x ".*.DS_Store|.*bkp.csv.gz" static/data gs://flywire-data/codex/data