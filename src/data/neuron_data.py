from collections import defaultdict
from functools import lru_cache
from random import choice

from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.search_index import SearchIndex
from src.data.structured_search_filters import (
    make_structured_terms_predicate,
    apply_chaining_rule,
    parse_search_query,
)
from src.configuration import MIN_SYN_COUNT, MIN_NBLAST_SCORE_SIMILARITY
from src.utils.formatting import (
    truncate,
    display,
)
from src.utils.logging import log

# Keywords will be matched against these attributes
NEURON_SEARCH_LABEL_ATTRIBUTES = [
    "root_id",
    "name",
    "group",
    "nt_type",
    "super_class",
    "class",
    "sub_class",
    "cell_type",
    "flow",
    "hemibrain_type",
    "hemilineage",
    "nerve",
    "side",
    "cluster",
]


class NeuronDB(object):
    def __init__(
        self,
        neuron_attributes,
        neuron_connection_rows,
        label_data,
        labels_file_timestamp,
        grouped_synapse_counts,
        reciprocal_connections,
    ):
        self.neuron_data = neuron_attributes
        self.connection_rows = neuron_connection_rows
        self.label_data = label_data
        self.labels_file_timestamp = labels_file_timestamp
        self.grouped_synapse_counts = grouped_synapse_counts
        self.reciprocal_connections = reciprocal_connections

        log("App initialization building search index..")

        def searchable_labels(ndata):
            labels = []
            for c in NEURON_SEARCH_LABEL_ATTRIBUTES:
                val = ndata[c]
                if val:
                    if isinstance(val, list):
                        labels += val
                    else:
                        labels.append(val)
            return labels

        self.search_index = SearchIndex(
            [
                (nd["label"], searchable_labels(nd), k)
                for k, nd in self.neuron_data.items()
            ]
        )

    def input_sets(self, min_syn_count=5):
        return self.input_output_partner_sets(min_syn_count)[0]

    def output_sets(self, min_syn_count=5):
        return self.input_output_partner_sets(min_syn_count)[1]

    @lru_cache
    def input_output_partner_sets(self, min_syn_count=MIN_SYN_COUNT):
        ins = defaultdict(set)
        outs = defaultdict(set)
        for r in self.connection_rows:
            if not min_syn_count or r[3] >= min_syn_count:
                ins[r[1]].add(r[0])
                outs[r[0]].add(r[1])
        return ins, outs

    @lru_cache
    def input_output_neuropil_sets(self, min_syn_count=MIN_SYN_COUNT):
        ins = defaultdict(set)
        outs = defaultdict(set)
        for r in self.connection_rows:
            if not min_syn_count or r[3] >= min_syn_count:
                ins[r[1]].add(r[2])
                outs[r[0]].add(r[2])
        return ins, outs

    def connections(self, ids, min_syn_count=MIN_SYN_COUNT, nt_type=None):
        idset = set(ids)
        cons = []
        if self.connection_rows:  # avail in mem cache
            cons = [r for r in self.connection_rows if (r[0] in idset or r[1] in idset)]
        if min_syn_count:
            cons = [r for r in cons if r[3] >= min_syn_count]
        if nt_type:
            nt_type = nt_type.upper()
            if nt_type not in NEURO_TRANSMITTER_NAMES:
                raise ValueError(
                    f"Unknown NT type: {nt_type}, must be one of {NEURO_TRANSMITTER_NAMES}"
                )
            cons = [r for r in cons if r[2] == nt_type]
        return cons

    def connections_by_region(
        self, cell_id, by_neuropil=False, min_syn_count=5, nt_type=None
    ):
        try:
            cell_id = int(cell_id)
        except ValueError:
            raise ValueError(f"'{cell_id}' is not a valid cell ID")
        table = self.connections(
            ids=[cell_id], min_syn_count=min_syn_count, nt_type=nt_type
        )
        if by_neuropil:
            downstream = defaultdict(list)
            upstream = defaultdict(list)
        else:
            downstream = []
            upstream = []
        for r in table or []:
            if r[0] == cell_id:
                if by_neuropil:
                    downstream[r[2]].append(r[1])
                else:
                    downstream.append(r[1])
            else:
                assert r[1] == cell_id
                if by_neuropil:
                    upstream[r[2]].append(r[0])
                else:
                    upstream.append(r[0])
        return downstream, upstream

    def random_cell_id(self):
        return choice(list(self.neuron_data.keys()))

    def num_cells(self):
        return len(self.neuron_data)

    @lru_cache
    def num_synapses(self):
        return sum([r[3] for r in self.connection_rows])

    @lru_cache
    def num_labels(self):
        return sum([len(nd["label"]) for nd in self.neuron_data.values()])

    @lru_cache
    def unique_values(self, attr_name):
        vals = set()
        for nd in self.neuron_data.values():
            if nd[attr_name]:
                if isinstance(nd[attr_name], list):
                    vals |= set(nd[attr_name])
                else:
                    vals.add(nd[attr_name])
        return sorted(vals)

    @lru_cache
    def categories(self, top_values=10):
        counts_dict = defaultdict(lambda: defaultdict(int))
        category_names = {
            "Super Classes": "super_class",
            "Hemilineages": "hemilineage",
            "Flows": "flow",
            "Classes": "class",
            "Sub Classes": "sub_class",
            "Cell Types": "cell_type",
            "Hemibrain Types": "hemibrain_type",
            "Community Identifications": "label",
            "Cell Body Sides": "side",
            "Nerve Types": "nerve",
            "Max In/Out Neuropil Groups": "group",
        }
        for nd in self.neuron_data.values():
            for v in category_names.values():
                val = nd[v]
                if not val:
                    continue
                if isinstance(val, list):
                    for c in val:
                        counts_dict[v][c] += 1
                else:
                    counts_dict[v][val] += 1

        def _caption(name, length):
            if length > top_values:
                return f"{name} (top {top_values} values out of {display(length)})"
            elif length > 10:
                return f"{name} ({display(length)} values)"
            else:
                return name

        def _sorted_counts(d):
            lst_all = sorted([(k, v) for k, v in d.items() if k], key=lambda p: -p[1])
            return lst_all[:top_values]

        return [
            {
                "caption": _caption(ck, len(counts_dict[cv])),
                "key": cv,
                "counts": _sorted_counts(counts_dict[cv]),
            }
            for ck, cv in category_names.items()
            if cv
        ]

    # Returns value ranges for all attributes with not too many different values. Used for advanced search dropdowns.
    @lru_cache
    def dynamic_ranges(self):
        res = {}
        for dct in self.categories(top_values=20):
            if len(dct["counts"]) < 20:
                res[f"data_{dct['key']}_range"] = [p[0] for p in dct["counts"]]
        return res

    def is_in_dataset(self, root_id):
        root_id = int(root_id)
        return root_id in self.neuron_data

    def get_neuron_data(self, root_id):
        root_id = int(root_id)
        nd = self.neuron_data.get(root_id)
        if not nd:
            log(f"No data exists for {root_id} in {len(self.neuron_data)} records")
            nd = {}
        return nd

    def get_neuron_caption(self, root_id):
        nd = self.get_neuron_data(root_id)
        labels = sorted(nd["label"], key=lambda x: len(x))
        lbl = labels[0] if labels else nd["name"]
        return truncate(lbl, 15)

    def get_similar_cells(
        self,
        root_id,
        as_dict_with_scores=False,
        min_score=MIN_NBLAST_SCORE_SIMILARITY,
        top_k=99999,
    ):
        scores = (
            [
                (rid, score)
                for rid, score in self.get_neuron_data(root_id)[
                    "similar_cell_scores"
                ].items()
                if score >= min_score
            ]
            if self.get_neuron_data(root_id).get("similar_cell_scores")
            else []
        )
        scores = sorted(scores, key=lambda p: -p[1])[:top_k]
        if as_dict_with_scores:
            return {p[0]: p[1] for p in scores}
        else:
            return [p[0] for p in scores]

    def get_label_data(self, root_id):
        root_id = int(root_id)
        return self.label_data.get(root_id)

    def all_label_data(self):
        return list(self.label_data.values())

    def labels_ingestion_timestamp(self):
        return self.labels_file_timestamp

    @lru_cache
    def search(self, search_query, case_sensitive=False, word_match=False):
        if not search_query:
            return sorted(
                self.neuron_data.keys(),
                key=lambda rid: self.neuron_data[rid]["area_nm"],
                reverse=True,
            )

        # The basic search query term can be either "free form" or "structured".
        # - Free form is when user types in a keyword, or a sentence, and the goal is to find all items that match
        #   (w.r.t any of their searchable attributes).
        # - Structured is something like 'label == olfactory' or 'nt_type != GABA' etc.
        #
        # These basic terms can be chained with one of the chaining rules: '&&' (and), '||' (or).
        # For example, 'label == olfactory && nt_type != GABA' should match items where label is olfactory and NT type
        # is other than GABA. Similarly, 'JON || nt_type == GABA' should find anything that matches JON (free form) or
        # has NT equal to GABA (structured).
        #
        # For chained search queries, we execute all 'free form' parts separately, and we combine one predicate for the
        # 'structured' parts to be evaluated once on every item. This is an optimization, because free form queries are
        # index lookups (and quick), while structured queries are evaluated in a linear scan. Then we combine the
        # collected results with the chaining rule (intersection for '&&' / union for '||').

        chaining_rule, free_form_terms, structured_terms = parse_search_query(
            search_query
        )
        log(
            f"Processing search query: '{chaining_rule=}' '{free_form_terms=}' '{structured_terms=}'"
        )
        term_search_results = [
            self.search_index.search(
                term=term, case_sensitive=case_sensitive, word_match=word_match
            )
            for term in free_form_terms
        ]
        if structured_terms:
            predicate = make_structured_terms_predicate(
                chaining_rule=chaining_rule,
                structured_terms=structured_terms,
                input_sets=self.input_sets(),
                output_sets=self.output_sets(),
                connections_loader=self.connections_by_region,
                similar_cells_loader=self.get_similar_cells,
                case_sensitive=case_sensitive,
            )
            term_search_results.append(
                [k for k, v in self.neuron_data.items() if predicate(v)]
            )

        return apply_chaining_rule(
            chaining_rule=chaining_rule, term_search_results=term_search_results
        )

    def closest_token(self, query, case_sensitive, limited_ids_set=None):
        query = query.strip()
        if not query or query.isnumeric():  # do not suggest number/id close matches
            return None, None
        chaining_rule, free_form_terms, structured_terms = parse_search_query(query)
        if chaining_rule or structured_terms:  # do not suggest for structured queries
            return None, None
        return self.search_index.closest_token(
            term=query, case_sensitive=case_sensitive, limited_ids_set=limited_ids_set
        )

    def multi_val_attrs(self, ids):
        # Given list of cell ids, returns the attrs for which the set of values in these cells is >1
        # This is used for deciding when to allow "include / exclude" filters.

        attr_vals = defaultdict(set)
        candidate_attr_names = {
            "super_class",
            "class",
            "sub_class",
            "hemilineage",
            "flow",
            "side",
            "nt_type",
            "nerve",
        }
        multi_val_attr_names = set()

        for cell_id in ids:
            nd = self.neuron_data[cell_id]
            for attr_name in candidate_attr_names:
                attr_vals[attr_name].add(nd[attr_name])
                if len(attr_vals[attr_name]) > 1:
                    multi_val_attr_names.add(attr_name)
            candidate_attr_names -= multi_val_attr_names
            if not candidate_attr_names:
                break

        return multi_val_attr_names

    def non_uniform_labels(self, page_ids, all_ids):
        # Returns the labels for cells in page_ids such that some cells from all_ids have them while others don't.
        # This is used for deciding when to allow "include / exclude" filters.
        page_labels = set()
        for cell_id in page_ids:
            for lbl in self.neuron_data[cell_id]["label"]:
                page_labels.add(lbl)
        non_uniform_set = set()
        for i, cell_id in enumerate(all_ids):
            lbl_set = set(self.neuron_data[cell_id]["label"])
            non_uniform_set |= page_labels - lbl_set
            if len(non_uniform_set) == len(page_labels):
                break
        return non_uniform_set
