#!/usr/bin/env sh
python3 -m black . && python3 -m ruff --fix .
