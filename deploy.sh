opt=$1
TIMESTAMP=$(date)
GIT_SHA=$(git log | head -1 | cut -d " " -f 2)

pip install pytest | grep -v 'already satisfied'

set -e
set -o pipefail

if [ "$opt" = "-nt" ]; then
   echo "!!! Skipping ALL tests !!!"
elif [ "$opt" = "-ni" ]; then
   echo "! Skipping integration tests !"
   python3 -m pytest tests/unit -x
else
   echo "Running tests.."
   python3 -m pytest tests/integration -x
   python3 -m pytest tests/unit -x
fi

gcloud run deploy --source . \
        --set-env-vars "APP_ENVIRONMENT=PROD" \
        --set-env-vars "BUILD_GIT_SHA=${GIT_SHA}" \
        --set-env-vars "BUILD_TIMESTAMP=${TIMESTAMP}" \
        --region us-east1 \
        --allow-unauthenticated \
        --min-instances 2 \
        --cpu 2 \
        --memory 8G \
        codex && \
echo "Running post deploy smoke tests. Make sure env variable SMOKE_TEST_PROD_KEY is set to match the value stored in secret manager (GCP) in order to bypass auth" && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/search?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/cell_details?root_id=720575940638460998&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/download_search_results?filter_string=rr&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/explore?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/stats?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "scending" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/connectivity?cell_names_or_ids=__sample_cells__&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "drawGraph" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/path_length?source_cell_names_or_ids=__sample_cells__&target_cell_names_or_ids=__sample_cells__&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "from" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
echo "Done."