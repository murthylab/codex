#! /bin/bash
curl 'https://api.braincircuits.io/app/neuron2line/result/matching?project=fruitfly_fafb_flywire&job=fb0e1a89-2aa2-444e-9756-b2a55d68e759' \
    -H 'Authorization: Bearer PLrh9E-XqFr9_0XrnE5ljn2XMsAnJTSerwK1nff0y-k' \
    --compressed | jq
