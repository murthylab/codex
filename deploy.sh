TIMESTAMP=$(date)
GIT_SHA=$(git log | head -1 | cut -d " " -f 2)

pip install pytest && \
python3 -m pytest tests/integration -x && \
python3 -m pytest tests/unit -x && \
gcloud run deploy --source . \
        --set-env-vars "APP_ENVIRONMENT=PROD" \
        --set-env-vars "BUILD_GIT_SHA=${GIT_SHA}" \
        --set-env-vars "BUILD_TIMESTAMP=${TIMESTAMP}" \
        --region us-east1 \
        --allow-unauthenticated \
        --min-instances 1 \
        --cpu 4 \
        --memory 4G \
        codex && \
echo "Running post deploy smoke tests. Make sure env variable SMOKE_TEST_PROD_KEY is set to match the value stored in secret manager (GCP) in order to bypass auth" && \
for i in $(seq 1 3); do curl "https://codex.flywire.ai/app/search?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://codex.flywire.ai/app/search?filter_string=rr&download=1&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://codex.flywire.ai/app/explore?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Class" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://codex.flywire.ai/app/stats?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Ascending" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://codex.flywire.ai/app/path_length?with_sample_input=1&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "from" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 3); do curl "https://codex.flywire.ai/app/nblast?with_sample_input=1&smoke_test=$SMOKE_TEST_PROD_KEY" | grep "from" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
echo "Done."