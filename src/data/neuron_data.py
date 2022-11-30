from collections import defaultdict
from functools import lru_cache
from random import choice

from src.data.brain_regions import neuropil_hemisphere, REGIONS
from src.data.gcs_data_loader import load_connection_table_for_root_ids
from src.data.neuron_collections import NEURON_COLLECTIONS
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.search_index import SearchIndex
from src.data.structured_search_filters import (
    make_structured_terms_predicate,
    apply_chaining_rule,
    parse_search_query,
)
from src.configuration import MIN_SYN_COUNT
from src.utils.formatting import compact_tag
from src.utils.logging import log

# Expected columns in static FlyWire data CSV file
DATA_FILE_COLUMNS = [
    "root_id",
    "name",
    "group",
    "nt_type",
    "classes",
    "similar_root_ids",
    "similar_root_id_scores",
    "symmetrical_root_ids",
    "symmetrical_root_id_scores",
    "input_neuropils",
    "output_neuropils",
    "supervoxel_id",
    "tag",
    "inherited_tag_root_id",
    "inherited_tag_score",
    "inherited_tag_mirrored",
    "user_id",
    "position",
    "closest_nblast_root_ids",
    "closest_nblast_scores",
    "gaba_avg",
    "ach_avg",
    "glut_avg",
    "oct_avg",
    "ser_avg",
    "da_avg",
]

# Expected columns in static labels data CSV file
LABEL_FILE_COLUMNS = [
    "root_id",
    "tag",
    "user_id",
    "position",
    "supervoxel_id",
    "user_name",
    "user_affiliation",
]

# Keywords will be matched against these attributes
NEURON_SEARCH_LABEL_ATTRIBUTES = [
    "root_id",
    "name",
    "group",
    "nt_type",
    "classes",
    "hemisphere_fingerprint",
]

COLUMN_INDEX = {c: i for i, c in enumerate(DATA_FILE_COLUMNS)}


def _row_to_dict(columns, row, exclude):
    res = {}
    for i, c in enumerate(columns):
        if not exclude or c not in exclude:
            res[c] = row[i]
    return res


class NeuronDB(object):
    def __init__(self, data_file_rows, connection_rows, label_rows):
        self.neuron_data = {}
        self.rids_of_neurons_with_inherited_tags = []
        self.label_data = {}

        for i, r in enumerate(data_file_rows):
            if i == 0:
                # check header
                assert r == DATA_FILE_COLUMNS
                continue
            root_id = self._get_value(r, "root_id", to_type=int)

            self.neuron_data[root_id] = {
                "root_id": root_id,
                "name": self._get_value(r, "name"),
                "group": self._get_value(r, "group"),
                "nt_type": self._get_value(r, "nt_type").upper(),
                "classes": self._get_value(r, "classes", split=True),
                "similar_root_ids": self._get_value(
                    r, "similar_root_ids", split=True, to_type=int
                ),
                "similar_root_id_scores": self._get_value(
                    r, "similar_root_id_scores", split=True, to_type=float
                ),
                "symmetrical_root_ids": self._get_value(
                    r, "symmetrical_root_ids", split=True, to_type=int
                ),
                "symmetrical_root_id_scores": self._get_value(
                    r, "symmetrical_root_id_scores", split=True, to_type=float
                ),
                "input_neuropils": self._get_value(r, "input_neuropils", split=True),
                "output_neuropils": self._get_value(r, "output_neuropils", split=True),
                "supervoxel_id": self._get_value(
                    r, "supervoxel_id", split=True, to_type=int
                ),
                "inherited_tag_root_id": self._get_value(
                    r, "inherited_tag_root_id", to_type=int
                ),
                "inherited_tag_score": self._get_value(
                    r, "inherited_tag_score", to_type=float
                ),
                "inherited_tag_mirrored": self._get_value(
                    r, "inherited_tag_mirrored", to_type=int
                ),
                "user_id": self._get_value(r, "user_id", split=True),
                "position": self._get_value(r, "position", split=True),
                "gaba_avg": self._get_value(r, "gaba_avg", to_type=float),
                "ach_avg": self._get_value(r, "ach_avg", to_type=float),
                "glut_avg": self._get_value(r, "glut_avg", to_type=float),
                "oct_avg": self._get_value(r, "oct_avg", to_type=float),
                "ser_avg": self._get_value(r, "ser_avg", to_type=float),
                "da_avg": self._get_value(r, "da_avg", to_type=float),
                "tag": [],
            }

        log(f"App initialization processing label data..")
        rid_col_idx = LABEL_FILE_COLUMNS.index("root_id")
        tag_col_idx = LABEL_FILE_COLUMNS.index("tag")
        not_found_rids = set()
        not_found_tags = defaultdict(int)
        for i, r in enumerate(label_rows or []):
            if i == 0:
                # check header
                assert r == LABEL_FILE_COLUMNS
                continue
            rid = int(r[rid_col_idx])
            if rid not in self.neuron_data:
                not_found_rids.add(rid)
                not_found_tags[r[tag_col_idx]] += 1
                continue
            label_data_list = self.label_data.get(rid)
            if not label_data_list:
                label_data_list = []
                self.label_data[rid] = label_data_list
            label_dict = _row_to_dict(
                columns=LABEL_FILE_COLUMNS, row=r, exclude={"root_id"}
            )
            label_data_list.append(label_dict)
            ctag = compact_tag(label_dict["tag"])
            if ctag and ctag not in self.neuron_data[rid]["tag"]:
                self.neuron_data[rid]["tag"].append(compact_tag(ctag))
        log(
            f"App initialization labels loaded for {len(self.label_data)} root ids, "
            f"not found rids: {len(not_found_rids)}"
        )
        if not_found_tags:
            log("Top 10 not found tags:")
            for p in sorted(not_found_tags.items(), key=lambda x: -x[1])[:10]:
                log(f"  {p}")

        log(f"App initialization augmenting..")
        # augment
        for nd in self.neuron_data.values():
            if nd["inherited_tag_root_id"]:
                self.rids_of_neurons_with_inherited_tags.append(nd["root_id"])
            nd["hemisphere_fingerprint"] = NeuronDB.hemisphere_fingerprint(
                nd["input_neuropils"], nd["output_neuropils"]
            )
            nd["class"] = ", ".join([c for c in nd["classes"]])
            nt_score_key = f'{nd["nt_type"].lower()}_avg'
            nd["nt_type_score"] = nd.get(nt_score_key, "")

        log(f"App initialization sorting..")

        # init search index
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
                (nd["tag"], searchable_labels(nd), k)
                for k, nd in self.neuron_data.items()
            ]
        )

        log(f"App initialization loading connections..")
        self.connection_rows = []
        for r in connection_rows or []:
            from_node, to_node, neuropil, syn_count, nt_type = (
                int(r[0]),
                int(r[1]),
                r[2].upper(),
                int(r[3]),
                r[4].upper(),
            )
            assert from_node in self.neuron_data and to_node in self.neuron_data
            assert syn_count >= MIN_SYN_COUNT
            assert nt_type in NEURO_TRANSMITTER_NAMES
            assert neuropil == "NONE" or neuropil in REGIONS.keys()
            self.connection_rows.append(
                [from_node, to_node, neuropil, syn_count, nt_type]
            )

        # augment ndata with in/out partner counts
        in_sets = self.input_sets()
        out_sets = self.output_sets()
        for rid, nd in self.neuron_data.items():
            nd["input_cells"] = len(in_sets[rid]) or "-"
            nd["output_cells"] = len(out_sets[rid]) or "-"

    def input_sets(self, min_syn_count=5):
        return self.input_output_sets(min_syn_count)[0]

    def output_sets(self, min_syn_count=5):
        return self.input_output_sets(min_syn_count)[1]

    @lru_cache
    def input_output_sets(self, min_syn_count=5):
        ins = defaultdict(set)
        outs = defaultdict(set)
        for r in self.connection_rows:
            if r[3] >= min_syn_count:
                ins[r[1]].add(r[0])
                outs[r[0]].add(r[1])
        return ins, outs

    def connections(self, ids, min_syn_count=5, nt_type=None):
        idset = set(ids)
        if self.connection_rows:  # avail in mem cache
            cons = [r for r in self.connection_rows if (r[0] in idset or r[1] in idset)]
        else:  # fetch from cloud
            cons = load_connection_table_for_root_ids(ids)
        if min_syn_count:
            cons = [r for r in cons if r[3] >= min_syn_count]
        if nt_type:
            nt_type = nt_type.upper()
            if nt_type != "ALL":
                cons = [r for r in cons if r[2] == nt_type]
        return cons

    @lru_cache
    def neuropils(self):
        res = set()
        for nd in self.neuron_data.values():
            for p in nd["input_neuropils"]:
                res.add(p)
            for p in nd["output_neuropils"]:
                res.add(p)
        return sorted(list([p for p in res if p]))

    def random_cell_id(self):
        return choice(list(self.neuron_data.keys()))

    def num_cells(self):
        return len(self.neuron_data)

    @lru_cache
    def num_synapses(self):
        # TODO: implement this once synapse data is loaded
        return 19351447

    @lru_cache
    def num_annotations(self):
        return sum(
            [len(nd["tag"]) + len(nd["classes"]) for nd in self.neuron_data.values()]
        )

    @lru_cache
    def classes(self):
        res = set()
        for nd in self.neuron_data.values():
            for p in nd["classes"]:
                res.add(p)
        return sorted(list([p for p in res if p]))

    @lru_cache
    def categories(self):
        classes = {}
        labels = {}
        groups = {}
        input_neuropils = {}
        output_neuropils = {}
        for nd in self.neuron_data.values():
            for c in nd.get("classes", []):
                classes[c] = classes.get(c, 0) + 1
            for c in nd.get("tag", []):
                labels[c] = labels.get(c, 0) + 1
            group = nd.get("group")
            if group:
                groups[group] = groups.get(group, 0) + 1
            for c in nd.get("input_neuropils", []):
                input_neuropils[c] = input_neuropils.get(c, 0) + 1
            for c in nd.get("output_neuropils", []):
                output_neuropils[c] = output_neuropils.get(c, 0) + 1

        # Limit to most common categories.
        CATEGORY_LIMIT = 100

        def _caption(name, length):
            if length > CATEGORY_LIMIT:
                return f"{name} (showing top {CATEGORY_LIMIT} out of {length})"
            elif length > 10:
                return f"{name} ({length})"
            else:
                return name

        def _sorted_counts(d):
            lst_all = sorted([(k, v) for k, v in d.items()], key=lambda p: -p[1])
            return lst_all[:CATEGORY_LIMIT]

        return [
            {
                "caption": _caption("Classes", len(classes)),
                "key": "class",
                "counts": _sorted_counts(classes),
            },
            {
                # curated neuron lists (not a neuron attribute)
                "caption": "Collections",
                "key": "collection",
                "counts": [(k, len(v)) for k, v in NEURON_COLLECTIONS.items()],
            },
            {
                "caption": _caption("Labels", len(labels)),
                "key": "label",
                "counts": _sorted_counts(labels),
            },
            {
                "caption": _caption("Input Neuropils", len(input_neuropils)),
                "key": "input_neuropil",
                "counts": _sorted_counts(input_neuropils),
            },
            {
                "caption": _caption("Output Neuropils", len(output_neuropils)),
                "key": "output_neuropil",
                "counts": _sorted_counts(output_neuropils),
            },
            {
                "caption": _caption("Max In/Out Neuropil Groups", len(groups)),
                "key": "group",
                "counts": _sorted_counts(groups),
            },
        ]

    def get_neuron_data(self, root_id):
        root_id = int(root_id)
        nd = self.neuron_data.get(root_id)
        if not nd:
            log(f"No data exists for {root_id} in {len(self.neuron_data)} records")
            nd = {}
        return nd

    def get_label_data(self, root_id):
        root_id = int(root_id)
        return self.label_data.get(root_id)

    @staticmethod
    def hemisphere_fingerprint(input_pils, output_pils):
        def fp(pils):
            if pils:
                hemispheres = set([neuropil_hemisphere(p) for p in pils])
                if len(hemispheres) > 1:
                    return "Mix"
                else:
                    return hemispheres.pop()

        if input_pils or output_pils:
            return f"{fp(input_pils)}/{fp(output_pils)}"
        else:
            return ""

    @lru_cache
    def search(self, search_query, case_sensitive=False, word_match=False):
        # TODO: Find a more elegant solution for curated collections
        def _intersect(rid_list):
            return [rid for rid in rid_list if rid in self.neuron_data]

        if search_query.startswith("collection == "):
            return _intersect(
                NEURON_COLLECTIONS[search_query.replace("collection == ", "")]
            )
        if not search_query:
            res = _intersect(NEURON_COLLECTIONS["Dominating Set"])
            res += list(set(self.neuron_data.keys()) - set(res))
            assert set(res) == set(self.neuron_data.keys())
            return res

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
                case_sensitive=case_sensitive,
            )
            term_search_results.append(
                [k for k, v in self.neuron_data.items() if predicate(v)]
            )

        return apply_chaining_rule(
            chaining_rule=chaining_rule, term_search_results=term_search_results
        )

    @lru_cache
    def search_in_neurons_with_inherited_labels(
        self, search_term, case_sensitive=False, word_match=False
    ):
        if search_term:
            matching_doc_ids_set = set(
                self.search(
                    search_query=search_term,
                    case_sensitive=case_sensitive,
                    word_match=word_match,
                )
            )
            return [
                p
                for p in self.rids_of_neurons_with_inherited_tags
                if p in matching_doc_ids_set
            ]
        else:
            return self.rids_of_neurons_with_inherited_tags

    def closest_token(self, query, case_sensitive, limited_ids_set=None):
        query = query.strip()
        if not query or query.isnumeric():  # do not suggest number/id close matches
            return None
        chaining_rule, free_form_terms, structured_terms = parse_search_query(query)
        if chaining_rule or structured_terms:  # do not suggest for structured queries
            return None
        return self.search_index.closest_token(
            term=query, case_sensitive=case_sensitive, limited_ids_set=limited_ids_set
        )

    def closest_token_from_inherited_tags(self, term, case_sensitive):
        return self.closest_token(
            term,
            case_sensitive=case_sensitive,
            limited_ids_set=set(self.rids_of_neurons_with_inherited_tags),
        )

    def multi_val_attrs(self, ids):
        # Given list of cell ids, returns the attrs for which the set of values in these cells is >1
        # This is used for deciding when to allow "include / exclude" filters.

        attr_vals = defaultdict(set)
        candidate_attr_names = {"class", "nt_type"}
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

    # Private helpers

    @staticmethod
    def _get_value(row, col, split=False, to_type=None):
        def convert_type(v):
            return to_type(v) if to_type else v

        val = row[COLUMN_INDEX[col]]
        if split:
            return [convert_type(v) for v in val.split(",")] if val else []
        else:
            return convert_type(val) if val else ""
