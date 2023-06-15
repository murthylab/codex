#!/usr/bin/env sh

opt=$1

set -e
set -o pipefail

if [ "$opt" = "-fast" ]; then
   echo "!!! Ingesting just labels and only for the default version !!!"
   python3 -m src.etl.compile_data -default_version_only
   python3 -m src.etl.pickle_data -default_version_only
   python3 -m src.etl.update_download_catalog -labels_in_default_version_only
   python3 -m pytest tests/unit -x
else
   echo "Running full ingestion pipeline.."
   python3 -m src.etl.compile_data
   python3 -m src.etl.pickle_data
   python3 -m src.etl.update_download_catalog
   python3 -m pytest tests/unit -x
   python3 -m pytest tests/integration -x
fi


gsutil -m rsync -r -x ".*.DS_Store|.*bkp.csv.gz" static/data gs://flywire-data/codex/data