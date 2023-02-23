# Codex - Connectome Data Explorer for FlyWire

[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kaikue/a442efe7b753f00d0f7a1cfceff87f61/raw/codex_badge_coverage.json)](https://github.com/murthylab/codex/actions)
[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kaikue/a442efe7b753f00d0f7a1cfceff87f61/raw/codex_badge_tests.json)](https://github.com/murthylab/codex/actions)

## Description

Flask web app for finding and analyzing neurons/cells proofread by the
FlyWire community (see flywire.ai). See [demo clips](https://codex.flywire.ai/demo_clip).

## Service URLs

[prod](https://codex.flywire.ai) / [staging (may take few secs to load)](https://codex-staging.flywire.ai)

## Setup

Python 3.9 or later is required.

We recommend using an environment manager such as [Conda](https://conda.io):

```sh
conda create -n codex python=3.9
conda activate codex
./setup.sh
```

Or [Poetry](https://python-poetry.org/):

```sh
poetry install
poetry shell
```

To bypass Google login and preload your Cave Token during development, create a `.env` file like so:

```env
BYPASS_AUTH=1
CAVE_TOKEN=<your token>
```

## Run service locally

```bash
./run_local.sh
```

To run in [Flask debug mode](https://flask.palletsprojects.com/en/2.2.x/debugging/#the-built-in-debugger)

```sh
./run_local_dev.sh
```

Navigate to [localhost:5000](http://localhost:5000)

## Testing before posting a PR or merging

### Manual UI testing (Required)

Run service locally and click around in all pages

### Unit tests & code coverage (Required)

```sh
./run_unit_tests.sh
```

### Integration/perf tests (Optional, requires setup)

```sh
./run_integration_tests.sh
```

### Run unit tests, integration tests, and coverage for both

```sh
./run_tests.sh
```

## Linting / code formatting

```sh
./lint.sh
```

## Profiling

```sh
./profile.sh
```

## Downloading and packaging static data

### Compile raw data from cloud (set version and access tokens within)

```sh
python3 -m src.etl.compile_data
```

### Pickle downloaded data

```shs
python3 -m src.etl.pickle_data
```

## Deploy

### Staging

[codex-staging.flywire.ai](https://codex-staging.flywire.ai)

#### Auto-deployed from the main branch

```sh
./deploy-staging.sh
```

### Prod

[codex.flywire.ai](https://codex.flywire.ai)

```sh
./deploy.sh
```

### Latest revision URL:

[latest---codex-yjsmm7mp3q-ue.a.run.app](https://latest---codex-yjsmm7mp3q-ue.a.run.app/)
