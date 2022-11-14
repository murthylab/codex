# Keep in sync with [public doc](https://codex.flywire.ai/todo_list)

## Search / cell lists
1. select with checkboxes what is shown in 3d interactive image, so that its easy to compare morphologies by eye

## Labels / data quality
1. labels lineage with history/credits
1. some names have ‘*’ on them, clarify what they mean
1. import Hemibrain and other labels/annotations
1. show label status: pending, reviewed, synced to main DB

## Connectivity / network view
1. it could be helpful to have the option to decide how many connections will be shown, including "all" inputs or outputs
1. clickable neuropils

## Pathways / NBLAST tables
1. after nblast, people might want to look at a subset (but more than 2 neurons) together. Perhaps a checkbox to select ids to copy would be useful?
1. origin / target textboxes instead of just one with set of cells
1. And in path length, people might want to know e.g. if the path length is 3, which cells are in the middle, and what’s 
   the synapse count for those connections. Might be good to make the path length numbers clickable for this info?

## General TODO:
1. use synapse position partition into smaller cubes (instead neuropils) for similarity metric
1. inspect diff from best match to 2nd best match to identify quality
1. provide forward vs symmetric nblast scores
1. internal/external version mapping
1. multi-threaded table loading
1. account history
1. make caching work in remote data loader with multiprocessing
1. input/output combined piechart in cell details page
1. programmatic access with user tokens
1. user starred cells
1. look up previous cell root ids by coordinates
1. save search when you switch tabs
 
