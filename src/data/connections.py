from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES

SYN_COUNT_MULTIPLIER = 8
NT_TO_ID = {nt: i for i, nt in enumerate(sorted(NEURO_TRANSMITTER_NAMES.keys()))}
ID_TO_NT = {v: k for k, v in NT_TO_ID.items()}


class Connections(object):
    def __init__(self, connection_rows):
        rids_set = set()
        connection_set = set()
        for r in connection_rows:
            rids_set.add(int(r[0]))
            rids_set.add(int(r[1]))
        self.rids_list = sorted(rids_set)
        self.rid_to_idx = {rid: i for i, rid in enumerate(self.rids_list)}
        self.rid_to_pils = {rid: set() for rid in self.rids_list}
        self.compact_connections_representation = {}
        self.synapse_count = 0
        for r in connection_rows:
            from_rid, to_rid = int(r[0]), int(r[1])
            from_rid_idx, to_rid_idx = (
                self.rid_to_idx[from_rid],
                self.rid_to_idx[to_rid],
            )
            pil, syn_cnt, nt_type = r[2], int(r[3]), r[4]
            self.synapse_count += syn_cnt
            self.rid_to_pils[from_rid].add(pil)
            self.rid_to_pils[to_rid].add(pil)
            pil_dict = self.compact_connections_representation.setdefault(pil, {})
            from_dict = pil_dict.setdefault(from_rid_idx, {})
            from_dict[to_rid_idx] = SYN_COUNT_MULTIPLIER * syn_cnt + NT_TO_ID[nt_type]
            connection_set.add(len(rids_set) * from_rid_idx + to_rid)
        self.connection_count = len(connection_set)

    def all_rows(self, min_syn_count=None):
        return self._rows_from_predicates(
            syn_cnt_predicate=(lambda x: x >= min_syn_count) if min_syn_count else None
        )

    def rows_for_cell(self, rid):
        if rid not in self.rid_to_pils:
            return []
        return self._rows_from_predicates(
            rids_predicate=lambda x, y: rid == x or rid == y,
            pils_predicate=lambda pil: pil in self.rid_to_pils[rid],
        )

    def rows_for_set(self, rids, min_syn_count=None, nt_type=None):
        rids_set = set(rids)
        return self._rows_from_predicates(
            rids_predicate=lambda x, y: x in rids_set or y in rids_set,
            syn_cnt_predicate=(lambda x: x >= min_syn_count) if min_syn_count else None,
            nt_type_predicate=(lambda x: x == nt_type) if nt_type else None,
        )

    def rows_between_sets(
        self, source_rids, target_rids, min_syn_count=None, nt_type=None
    ):
        source_rids_set = set(source_rids)
        target_rids_set = set(target_rids)
        return self._rows_from_predicates(
            rids_predicate=lambda x, y: x in source_rids_set and y in target_rids_set,
            syn_cnt_predicate=(lambda x: x >= min_syn_count) if min_syn_count else None,
            nt_type_predicate=(lambda x: x == nt_type) if nt_type else None,
        )

    def _rows_from_predicates(
        self,
        rids_predicate=None,
        pils_predicate=None,
        syn_cnt_predicate=None,
        nt_type_predicate=None,
    ):
        for pil, pil_dict in self.compact_connections_representation.items():
            if pils_predicate and not pils_predicate(pil):
                continue
            for from_id, from_dict in pil_dict.items():
                from_rid = self.rids_list[from_id]
                for to_id, syn_cnt_and_nt_type in from_dict.items():
                    to_rid = self.rids_list[to_id]
                    if rids_predicate and not rids_predicate(from_rid, to_rid):
                        continue
                    syn_cnt, nt_type_idx = divmod(
                        syn_cnt_and_nt_type, SYN_COUNT_MULTIPLIER
                    )
                    if syn_cnt_predicate and not syn_cnt_predicate(syn_cnt):
                        continue
                    nt_type = ID_TO_NT[nt_type_idx]
                    if nt_type_predicate and not nt_type_predicate(nt_type):
                        continue
                    yield (
                        from_rid,
                        to_rid,
                        pil,
                        syn_cnt,
                        nt_type,
                    )

    def num_synapses(self):
        return self.synapse_count

    def num_connections(self):
        return self.connection_count
