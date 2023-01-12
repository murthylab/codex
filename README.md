# Codex - Connectome Data Explorer for FlyWire

![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kaikue/a442efe7b753f00d0f7a1cfceff87f61/raw/codex_badge_coverage.json)
![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kaikue/a442efe7b753f00d0f7a1cfceff87f61/raw/codex_badge_tests.json)

## Description
Flask web app for finding and analyzing neurons/cells proofread by the
FlyWire community (see flywire.ai). See [demo clips](https://codex.flywire.ai/demo_clip).

## Service URLs
[prod](https://codex.flywire.ai) / [staging (may take few secs to load)](https://codex-staging.flywire.ai)

## Run service locally
```
conda create -n codex python=3.9
conda activate codex
pip install -r requirements.txt
./run_local.sh
```
Navigate to [localhost:5000](http://localhost:5000)


## Testing before posting a PR or merging
### Manual UI testing (Required)
run service locally and click around in all pages
### Unit tests & code coverage (Required)
Note: If running for the first time, first run `pip install -r requirements_dev.txt`

`python3 tests/run_unit_tests_with_coverage.py`
### Integration/perf tests (Optional, requires setup)
`python3 -m pytest tests/integration`

`python3 tests/run_unit_tests_with_coverage.py i` will run unit tests, integration tests, and coverage for both.


## Linting / code formatting
```
pip install git+https://github.com/psf/black && black src
```

## Profiling
```python3 -m cProfile -o profile -m pytest tests/unit/test_neuron_data.py -k test_augmentation_loading```
Then print the generated `profile` file:
```
python3 -m src.utils.print_profiling_data
```

## Downloading and packaging static data
### Compile raw data from cloud (set version and access tokens within)
```
python3 -m src.etl.compile_data
```
### Pickle downloaded data
```
python3 -m src.etl.pickle_data
```


## Deploy
### Staging
[codex-staging.flywire.ai](https://codex-staging.flywire.ai)
#### Auto-deployed from the main branch
```
./deploy-staging.sh
```
### Prod
[codex.flywire.ai](https://codex.flywire.ai)
```
./deploy.sh
```

### Latest revision URL:
[latest---codex-yjsmm7mp3q-ue.a.run.app](https://latest---codex-yjsmm7mp3q-ue.a.run.app/)
