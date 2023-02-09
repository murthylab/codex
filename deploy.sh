TIMESTAMP=$(date)
GIT_SHA=$(git log | head -1 | cut -d " " -f 2)

pip install pytest && \
python3 -m pytest tests/unit -x && \
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
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/connectivity?cell_names_or_ids=720575940628289103&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "drawGraph" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/path_length?with_sample_input=1&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "from" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://latest---codex-yjsmm7mp3q-ue.a.run.app/app/nblast?with_sample_input=1&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "from" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
echo "Done."