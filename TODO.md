## Search / cell lists
1. filters / sorting options for search page
1. expandable "actions" buttons instead of menu behind rocket
1. could be nice to be able to select with checkboxes what is shown in 3d interactive image, so that its easy to compare morphologies by eye
1. could be helpful to be able to group chosen cells together and make such graphs for them as well (for example, if there are 3 cells that I know are
   part of the same group, being able to pool that info would be great--- Im spending time doing such things for a plot for our paper)

## Labels / data quality
1. label lineage with history/credits
1. And some names have ‘*’ on them. It’s not very clear to me what they mean?
1. Import hemibrain labels, and others from seatable
1. label suggestion status: pending, approved, synced to main DB

## Labeling / annotations
1. labeling a set of cells at once
1. modify label before assigning
1. for the "labeling suggestions" part -- my guess is that these are neurons that have been tentatively identified but need confirmation? if this is the case 
   id suggest 1) adding some instructions, 2) before allowing a user to accept/reject things, to validate somehow that they are a user that can do so 
   (the way we had the flywire training before being allowed to actually make changes in the dataset)-- i was tempted to click around and click 
   "accept" to see what happens, but didnt because i wasnt sure if this would change something in the dataset or what it was doing
1. I also wonder how viable it is to put a neuroglancer window in Labelling Suggestions , because it’s time consuming to
   compare many cells when you have to load a neuroglancer link for every pair of neruons
1. And perhaps labelling suggestions could also allow you to put multiple pairs at the same time into a neuroglancer window quickly

## Explanations / definitions / tooltips
1. it's unclear to some what the "nblast" tab is displaying and what we can do with it
1. info on how cells are named could be helpful
1. info on neurotransmitter thresholds-- and what exactly does % input synapse neurotransmitters mean? what confidence thresholds were used? specifically, i am unsure if these percentages mean "out of 100 synapses, 34 were cholinergic and 66 were glut" or whether it means "for 100 synapses, on average, each synapse was 34% likely to be cholinergic and  66% likely to be glut"
1. need definition for "I/O Side"
1. path length: when i clicked on this, there were a handful of neuron numbers charted, not sure why that page starts with those specific neurons
1. show warning for non-chrome browsers in skeletons / general

## Connectivity / network view
1. on the connectivity maps:
   1. it could be helpful to numerically write the number of connections (not just have the arrow be different thicknesses)-- and to be able to export this info
   1. it could be helpful to have the option to decide how many connections will be shown, including "all" inputs or outputs. currently one cell that 
      i searched shows the top 2 connected cells (and their inputs) and the top 1 output, but if i wanted to see the top 5/10/all, would be helpful to have this feature 
      a way to then manually  group these connections could be nice (based on user knowledge)
1. BUG: One small thing, when I hover over some connectivity info, 2 things appear and disappear together and overlap, like in the screenshot
1. clickable neuropils
1. larger graph / expandable view
1. legend for nodes in graphs

## Pathways / NBLAST tables
1. loved the Path length tool - asked how to see 1. what cells are in between and 2. cells in FW
1. And after nblast, people might want to look at a subset (but more than 2 neurons) together. Perhaps a checkbox to select ids to copy would be useful?
1. origin / target textboxes instead of just one with set of cells
1. And might also be good to include some meta information of neurons in the nblast page
1. And in path length, people might want to know e.g. if the path length is 3, which cells are in the middle, and what’s 
   the synapse count for those connections. Might be good to make the path length numbers clickable for this info?
1. show graph in path lengths

## General TODO:
1. use synapse position partition into smaller cubes (instead neuropils) for similarity metric
1. inspect diff from best match to 2nd best match to identify quality
1. forward / symmetric nblast scores
1. internal/external version mapping
1. table loading - share code
1. account history
1. make caching work in remote data loader with multiprocessing
1. input/output combined piechart in cell details page
1. firestore DB for storing labels and user info
1. programmatic access with user tokens
1. user starred cells
1. look up previous cell root ids by coordinates
1. Save search when you switch tabs
1. rename repo and service names to codex
 
