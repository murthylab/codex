# Codex - Connectome Data Explorer for FlyWire

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
### Unit tests (Required)
You may need to first run `pip install pytest`

`python3 -m pytest tests/unit`
### Integration/perf tests (Optional, requires setup)
`python3 -m pytest tests/integration`


## Linting / code formatting
```
pip install git+https://github.com/psf/black && black src
```

## Profiling
```python3 -m cProfile -o profile -m pytest tests/unit/test_neuron_data.py -k test_augmentation_loading```
Then load the generated `profile` file:
```
import pstats
p = pstats.Stats('profile')
p.strip_dirs()
p.sort_stats('cumtime')
p.print_stats(50)
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
