#! /bin/bash
curl 'https://api.braincircuits.io/app/neuron2line?project=fruitfly_fafb_flywire' \
    -H 'Authorization: Bearer PLrh9E-XqFr9_0XrnE5ljn2XMsAnJTSerwK1nff0y-k' \
    -H 'Content-Type: application/json' \
    --data-raw '{"segment_ids":"720575940624967305","email":"rmorey@princeton.edu","template_space":"JRC2018_BRAIN_UNISEX","target_library":"fruitfly_brain_FlyLight_Annotator_Gen1_MCFO","matching_method":"colormip","caveToken":"2b479ecfb87e457f4f863055db38918f"}' \
    --compressed | jq
