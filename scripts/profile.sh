#!/usr/bin/env sh
python3 -m cProfile -o profile -m pytest tests/unit/test_neuron_data.py -k find_similar_cells
python3 -m src.utils.print_profiling_data
