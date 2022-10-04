# CoDE - Connectome Data Explorer for FlyWire

## Description
Flask web app for finding and analyzing neurons/cells proofread by the FlyWire community (see flywire.ai).

## Run locally
```
conda create -n code python=3.9
conda activate code
pip install -r requirements.txt
./run_dev.sh
```
Navigate to [localhost:5000](http://localhost:5000)


## Downloading and packaging static data
### Compile raw data from cloud (set version and access tokens within)
```
python3 -m src.etl_compile_data
```
### Pickle downloaded data
```
python3 -m src.etl_pickle_data
```

## Test
`python3 -m pytest`

## Profile
```python3 -m cProfile -o profile -m pytest tests/test_neuron_data.py -k test_augmentation_loading```
Then load the generated `profile` file:
```
import pstats
p = pstats.Stats('profile')
p.strip_dirs()
p.sort_stats('cumtime')
p.print_stats(50)
```

## Deploy
First make sure to update the most recent commit SHA in `about.html` template.
Then:
```
./deploy.sh
```

## Internal endpoints
1. [Cloud Run](https://code-yjsmm7mp3q-ue.a.run.app)