#! /bin/bash
curl 'https://api.braincircuits.io/app/neuron2line/submission?project=fruitfly_fafb_flywire&submission=160c26fe-c4fd-4500-971d-2e1f232e34b5' \
    -H 'Authorization: Bearer PLrh9E-XqFr9_0XrnE5ljn2XMsAnJTSerwK1nff0y-k' \
    --compressed | jq
