# Codex - Connectome Data Explorer for FlyWire

[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kaikue/a442efe7b753f00d0f7a1cfceff87f61/raw/codex_badge_coverage.json)](https://github.com/murthylab/codex/actions)
[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kaikue/a442efe7b753f00d0f7a1cfceff87f61/raw/codex_badge_tests.json)](https://github.com/murthylab/codex/actions)

## Description

[Codex](https://codex.flywire.ai) is a web application for exploring and analyzing neurons and
annotations from the
[FlyWire Whole Brain Connectome](https://flywire.ai).

## Setup

Python 3.9 or later is required.

We recommend using an environment manager such as [Poetry](https://python-poetry.org/):

```sh
poetry install
poetry shell
```

### Download and initialize the FlyWire connectome data (initially or upon version updates)
```bash
./scripts/init_data.sh
```

## Run service locally

```bash
./scripts/run_local.sh
```

To run in [Flask debug mode](https://flask.palletsprojects.com/en/2.2.x/debugging/#the-built-in-debugger)

```sh
./scripts/run_local_dev.sh
```

Navigate to [localhost:5000](http://localhost:5000)

## Testing before posting a PR or merging (please fork - do not create branches in the main repo)

### Manual UI testing (Required)

Run service locally and click around in all pages

### Unit tests & code coverage (Required)

```sh
./scripts/run_unit_tests.sh
```

## Linting / code formatting

```sh
./scripts/lint.sh
```
