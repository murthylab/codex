#!/usr/bin/env sh

export FLASK_APP=codex.main && \
export FLASK_SECRET_KEY=dev_dummy_key && \
export APP_ENVIRONMENT=DEV && \
BUILD_GIT_SHA=dummy_git_sha && \
export BUILD_GIT_SHA && \
BUILD_TIMESTAMP="$(date)" &&\
export BUILD_TIMESTAMP && \
flask run