from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES

SYN_COUNT_MULTIPLIER = 8
NT_TO_ID = {nt: i for i, nt in enumerate(sorted(NEURO_TRANSMITTER_NAMES.keys()))}
ID_TO_NT = {v: k for k, v in NT_TO_ID.items()}


class Connections(object):
    def __init__(self, connection_rows):
        rids_set = set()
        for r in connection_rows:
            rids_set.add(int(r[0]))
            rids_set.add(int(r[1]))
        self.rids_list = sorted(rids_set)
        self.rid_to_idx = {rid: i for i, rid in enumerate(self.rids_list)}
        self.compact_connections_representation = {}
        self.synapse_count = 0
        for r in connection_rows:
            from_rid, to_rid = self.rid_to_idx[int(r[0])], self.rid_to_idx[int(r[1])]
            pil, syn_cnt, nt_type = r[2], int(r[3]), r[4]
            pil_dict = self.compact_connections_representation.setdefault(pil, {})
            from_dict = pil_dict.setdefault(from_rid, {})
            from_dict[to_rid] = SYN_COUNT_MULTIPLIER * syn_cnt + NT_TO_ID[nt_type]
            self.synapse_count += syn_cnt

    def rows(self, cell_id=None):
        for pil, pil_dict in self.compact_connections_representation.items():
            for from_id, from_dict in pil_dict.items():
                from_rid = self.rids_list[from_id]
                for to_id, syn_cnt_and_nt_type in from_dict.items():
                    to_rid = self.rids_list[to_id]
                    if cell_id and not (cell_id == from_rid or cell_id == to_rid):
                        continue
                    syn_cnt, nt_type_idx = divmod(
                        syn_cnt_and_nt_type, SYN_COUNT_MULTIPLIER
                    )
                    nt_type = ID_TO_NT[nt_type_idx]
                    yield [
                        from_rid,
                        to_rid,
                        pil,
                        syn_cnt,
                        nt_type,
                    ]

    def num_synapses(self):
        return self.synapse_count
