def extract_markers(neuron_data, markers_type):
    prefix = f"{markers_type}:"
    res = []
    for mrk in neuron_data["marker"]:
        if mrk.startswith(prefix):
            res.append(mrk[len(prefix) :])
    return res
