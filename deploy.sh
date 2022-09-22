TIMESTAMP=$(date)
GIT_SHA=$(git log | head -1 | cut -d " " -f 2)

pip install pytest && \
python3 -m pytest && \
gcloud run deploy --source . \
        --set-env-vars "BUILD_GIT_SHA=${GIT_SHA}" \
        --set-env-vars "BUILD_TIMESTAMP=${TIMESTAMP}" \
        --region us-east1 \
        --allow-unauthenticated \
        --min-instances 1 \
        --cpu 4 \
        --memory 4G \
        flywire-index && \
echo "Running post deploy smoke tests. Make sure env variable SMOKE_TEST_PROD_KEY is set to match the value stored in secret manager (GCP) in order to bypass auth" && \
for i in $(seq 1 5); do curl "https://code.pniapps.org/app/search?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Cell ID" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 5); do curl "https://code.pniapps.org/app/explore?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Classes" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done && \
for i in $(seq 1 5); do curl "https://code.pniapps.org/app/stats?smoke_test=$SMOKE_TEST_PROD_KEY" | grep "Cells" || echo -e "\033[1;31m FAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED\nFAILED  \033[0m"; done