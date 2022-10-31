TIMESTAMP=$(date)
GIT_SHA=$(git log | head -1 | cut -d " " -f 2)

gcloud run deploy --source . \
        --set-env-vars "BUILD_GIT_SHA=${GIT_SHA}" \
        --set-env-vars "BUILD_TIMESTAMP=${TIMESTAMP}" \
        --region us-east1 \
        --allow-unauthenticated \
        codex-staging
