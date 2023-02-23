#!/usr/bin/env sh
python3 -m cProfile -o profile -m pytest tests/unit/test_neuron_data.py -k test_augmentation_loading
python3 -m src.utils.print_profiling_data
