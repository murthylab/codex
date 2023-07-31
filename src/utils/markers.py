def extract_markers(neuron_data, markers_type):
    prefix = f"{markers_type}:"
    res = []
    for mrk in neuron_data["marker"]:
        if mrk.startswith(prefix):
            res.append(mrk[len(prefix) :])
    return res


def extract_at_most_one_marker(neuron_data, markers_type):
    markers = extract_markers(neuron_data, markers_type)
    if len(markers) == 1:
        return markers[0]
    if len(markers) > 1:
        raise ValueError(
            f"Found {len(markers)} markers of type {markers_type} for {neuron_data['root_id']}: {markers}"
        )
