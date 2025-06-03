# Codex - Connectome Data Explorer for FlyWire

![Tests Passing](https://img.shields.io/badge/tests-passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-67%25-yellowgreen)

## Description

[Codex](https://codex.flywire.ai) is a web application for exploring and analyzing neurons and
annotations from the
[FlyWire Whole Brain Connectome](https://flywire.ai).

## Setup

Python 3.9 or later is required.

We recommend using an environment manager such as [Poetry](https://python-poetry.org/):

```sh
poetry install
```

### Download and initialize the FlyWire connectome data (initially or upon version updates)
```bash
poetry run ./scripts/make_data.sh
```

## Run service locally

```bash
poetry run ./scripts/run_local.sh
```

To run in [Flask debug mode](https://flask.palletsprojects.com/en/2.2.x/debugging/#the-built-in-debugger)

```sh
poetry run ./scripts/run_local_dev.sh
```

Navigate to [localhost:5000](http://localhost:5000)

## Testing before posting a PR or merging (please fork - do not create branches in the main repo)

### Manual UI testing (Required)

Run service locally and click around in all pages

### Unit tests & code coverage (Required)

```sh
poetry run ./scripts/run_unit_tests.sh
```
If test status or coverage percentage change, update the static badges above

## Linting / code formatting

```sh
poetry run ./scripts/lint.sh
```
