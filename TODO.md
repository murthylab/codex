## General TODO:
1. use synapse position partition into smaller cubes (instead neuropils) for similarity metric
1. inspect diff from best match to 2nd best match to identify quality
1. assign 'kinds' based on similarity clusters instead most prominent input/output neuropil
   1. kinds -> unique names
1. integrate conviz
1. downstream / upstream connectivity
1. instead of rocket, do dropdown quick menu that expands if there's space
1. path length links to DFS result showing paths
1. single neuron nblast and path lengths (showing top something)
1. forward / symmetric nblast scores
1. internal/external version mapping
1. table loading - share code
1. suggestions for class propagation
1. account history
1. streamline activity logs


## User feedback
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
