## General TODO:
1. use synapse position partition into smaller cubes (instead neuropils) for similarity metric
1. inspect diff from best match to 2nd best match to identify quality
1. instead of rocket, do dropdown quick menu that expands if there's space
1. path length links to DFS result showing paths
1. single neuron nblast and path lengths (showing top something)
1. forward / symmetric nblast scores
1. internal/external version mapping
1. table loading - share code
1. suggestions for class propagation
1. account history
1. get rid of NBLAST / path tabs
1. clickable neuropils
1. larger graph on neuron info
1. legend for nodes in graphs
1. make caching work in remote data loader with multiprocessing
1. input/output combined piechart in cell details page
1. firestore DB for storing labels and user info
1. page load spinner
1. programatic access with user tokens
1. user starred cells
1. look up previous cell root ids by coordinates
1. import hemibrain labels
1. label suggestion status: pending, approved, synced to main DB
1. dedicated cell detail page (+ tab)
1. homepage cards + stats
1. show graph in path lengths
1. skeleton thumbnails

## User feedback (Jie)
1. - TODO: I’m note sure how familiar you are with seatable, but they have a feature that allows you to filter the db on
values from multiple columns. I attach a screenshot. I think that would be useful, in addition to the free search box.
   - UNSURE: After searching I like the rocket button that allows you to load all in flywire, but the option to load all
neurons in flywire could be made more obvious;
   - DONE: similarly, it would be nice to have a button to copy all the root ids at once, from the search results.
   - TODO: in addition, for stats, perhaps it would be nice to display stats for any collection of ids the user chooses.
   - TODO[explain in FAQ]: I’m not sure what the definition is for ‘kind’? Perhaps would be good to define it
   - For adding labels, if it’s also intended for this interface, it would be nice to be able to assign a label to a
collection of ids easily.
   - UNSURE: In the neuroglancer view of ids, it would be nice to have the default view as frontal (we are used to
here. But from the few Princeton presentations I’ve seen you seem to prefer the ventral view? I’m not sure what’s
standard, and it’s up to you)
   - UNSURE: Not sure if you want a way to assign credit/references to the labels somehow. perhaps: hovering on
the label shows you the group/person who gave the name. Now people seem to add credits to the labels which messes
up the data a bit
   - TODO[pick and modify label before assigning]: Approving in ‘labelling suggestions’ seem to assign all labels
from one neuron to another. Is there a way to only assign some labels?
   - And some questions:
   - TODO[explain in FAQ]: are the ids always up to date? do the labels sync in real time with our seatable data? 
   - DONE: may I ask how those labelling suggestions are generated?

## User feedback (Edna)
Thanks for making this cool tool! Took a quick look and here are some comments (top is i think quicker things, bottom is feature suggestions)
Hope this helps and lmk if there's anything else specific you'd like me to comment on!
1. it's unclear to me what the "nblast" tab is displaying and what we can do with it
1. in faq: info on how the connected  cells are named could be helpful
1. info on neurotransmitter thresholds-- and what exactly does % input synapse neurotransmitters mean? what confidence thresholds were used?
specifically, i am unsure if these percentages mean "out of 100 synapses, 34 were cholinergic and 66 were glut" or whether it means "for 100 synapses, on average, each synapse was 34% likely to be cholinergic and  66% likely to be glut"
1. need definition for "I/O Side"
1. path length: when i clicked on this, there were a handful of neuron numbers charted, not sure why that page starts with those specific neurons
1. under stats: unsure what "top labels" means
1. for the "labeling suggestions" part -- my guess is that these are neurons that have been tentatively identified but need confirmation? if this is the case id suggest 1) adding some instructions, 2) before allowing a user to accept/reject things, to validate somehow that they are a user that can do so (the way we had the flywire training before being allowed to actually make changes in the dataset)-- i was tempted to click around and click "accept" to see what happens, but didnt because i wasnt sure if this would change something in the dataset or what it was doing
### useful potential additions:
1. on the connectivity maps:
   1. it could be helpful to numerically write the number of connections (not just have the arrow be different thicknesses)-- and to be able to export this info
   1. it could be helpful to have the option to decide how many connections will be shown, including "all" inputs or outputs. currently one cell that i searched shows the top 2 connected cells (and their inputs) and the top 1 output, but if i wanted to see the top 5/10/all, would be helpful to have this feature
a way to then manually  group these connections could be nice (based on user knowledge)
1. the skeleton (within the 3d brain) feature is really nice.
1. could be nice to be able to select a second, third, etc neuron skeleton to display in the same 3d interactive image, so that its easy to compare morphologies by eye (hemibrain has this, but the interface is super annoying-- here the interface is great but is lacking this feature)
1. a feature to change the type of graph could be nice as well as to download the graph (for example, if instead of a pie graph we wanted to change it to bar).
1. similar to points above, perhaps a mechanism to then make that graph for >1 neuron, enabling an easy statistical comparison
1. could be helpful to be able to group chosen cells together and make such graphs for them as well (for example, if there are 3 cells that I know are part of the same group, being able to pool that info would be great--- Im spending time doing such things for a plot for our paper)

## User feedback (Tjalda)
1. loved the Path length tool - asked how to see 1. what cells are in between and 2. cells in FW
1. She said she would want to see any cells in FW but if results are too many then maybe a way to have checkboxes to choose which cells to show. I think though going through SVG would be better.
1. FlyWire crashes frequently for most of our users and they are constantly refreshing, and when they do so it reorders their meshes and recolors them. I know this isn't related to CoDE but just wanted to relay in case the opportunity to fix it comes up. this seems to be the biggest complaint of all our users
