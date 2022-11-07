def synapse_table_to_csv_string(table):
    table = [["From", "To", "Neuropil", "Synapses", "Neuro Transmitter"]] + table
    return "\n".join([",".join([str(r) for r in row]) for row in table])


def neuron_json(ndata):
    return {
        attrib: ndata[attrib]
        for attrib in ["name", "nt_type", "root_id", "classes"]
        if ndata[attrib]
    }


def synapse_json(synapse_table_row):
    return {
        "from": synapse_table_row[0],
        "to": synapse_table_row[1],
        "neuropil": synapse_table_row[2],
        "synapses": synapse_table_row[3],
        "nt_type": synapse_table_row[4],
    }


def synapse_table_to_json_dict(table, neuron_data_fetcher, meta_data):
    network_dict = {}
    node_set = set([r[0] for r in table]).union(set([r[1] for r in table]))
    network_dict["nodes"] = {
        rid: neuron_json(neuron_data_fetcher(rid)) for rid in sorted(node_set)
    }
    network_dict["edges"] = [synapse_json(r) for r in table]
    return {"meta": meta_data, "network": network_dict} if meta_data else network_dict
