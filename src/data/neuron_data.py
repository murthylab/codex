from functools import lru_cache
from random import choice

from src.data.brain_regions import match_to_neuropil, lookup_neuropil_set
from src.data.gcs_data_loader import load_connections_for_root_id
from src.data.neuron_collections import NEURON_COLLECTIONS
from src.data.neurotransmitters import lookup_nt_type
from src.data.search_index import SearchIndex
from src.utils.logging import log

# Expected column in static FlyWire data CSV file
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

# Structured search operators
OP_EQUAL = "{equal}"
OP_NOT_EQUAL = "{not equal}"
OP_IN = "{in}"
OP_NOT_IN = "{not in}"
OP_HAS = "{has}"
OP_NOT = "{not}"
OP_UPSTREAM = "{upstream}"
OP_DOWNSTREAM = "{downstream}"
OP_UPSTREAM_REGION = "{upstream_region}"
OP_DOWNSTREAM_REGION = "{downstream_region}"
OP_AND = "{and}"
OP_OR = "{or}"

OPERATOR_METADATA = {
    # user facing op: (alternative shorthand, description)
    OP_EQUAL: ("==", "Binary, LHS attribute of the cell and RHS value are equal"),
    OP_NOT_EQUAL: (
        "!=",
        "Binary, LHS attribute of the cell and RHS value are not equal",
    ),
    OP_IN: (
        "<<",
        "Binary, LHS attribute of the cell equals one of the comma-separated values on RHS",
    ),
    OP_NOT_IN: (
        "!<",
        "Binary, LHS attribute of the cell is not equal to any of the comma-separated values on RHS",
    ),
    OP_HAS: ("$$", "Unary, attribute of the cell has value (not empty)"),
    OP_NOT: ("!$", "Unary, attribute of the cell has no value (empty)"),
    OP_UPSTREAM: ("^^", "Unary, matches cells upstream of specified Cell ID)"),
    OP_DOWNSTREAM: ("!^", "Unary, matches cells downstream of specified Cell ID)"),
    OP_UPSTREAM_REGION: (
        "^R",
        "Binary, matches cells upstream of RHS, with synapses in LHS region, where region "
        "is either hemisphere (left/right/center) or neuropil (e.g. GNG).",
    ),
    OP_DOWNSTREAM_REGION: (
        "!R",
        "Binary, matches cells downstream of RHS, with synapses in LHS region, where region "
        "is either hemisphere (left/right/center) or neuropil (e.g. GNG).",
    ),
    OP_AND: ("&&", "N-ary, all terms are true"),
    OP_OR: ("||", "N-ary, at least one of the terms is true"),
}

SEARCH_TERM_BINARY_OPERATORS = [
    OP_EQUAL,  # equals
    OP_NOT_EQUAL,  # not equal to
    OP_IN,  # one of the values on rhs (rhs is comma separated list)
    OP_NOT_IN,  # none of the values on rhs (rhs is comma separated list)
    OP_UPSTREAM_REGION,  # upstream to RHS in LHS region
    OP_DOWNSTREAM_REGION,  # downstream to RHS in LHS region
]
SEARCH_TERM_UNARY_OPERATORS = [
    OP_HAS,  # exists / has value
    OP_NOT,  # does not exist / has no value
    OP_DOWNSTREAM,  # match downstream connections
    OP_UPSTREAM,  # match upstream connections
]
SEARCH_CHAINING_OPERATORS = [
    OP_AND,  # and / conjunction
    OP_OR,  # or / disjunction
]
STRUCTURED_SEARCH_ATTRIBUTES = {
    # user facing attr: (internal attr, conversion - optional, description)
    "id": (
        "root_id",
        lambda x: int(x),
        "ID of the cell. Unique across data versions, "
        "but might get replaced if affected by proofreading.",
    ),
    "name": (
        "name",
        None,
        "Automatically assigned name (based on properties of the cell). Unique across data "
        "versions, but might get replaced if affected by proofreading.",
    ),
    "group": (
        "group",
        None,
        "Automatically assigned group name (based on properties of the cell).",
    ),
    "class": (
        "classes",
        None,
        "Cell typing attribute. Indicates function or other property of the cell. Each cell can "
        "belong to zero or more classes.",
    ),
    "label": (
        "tag",
        None,
        "Human readable label assigned during cell identification process. Each cell can have zero "
        "or more labels.",
    ),
    "nt": (
        "nt_type",
        lambda x: lookup_nt_type(x),
        "Neuro-transmitter type. One of ACH, GABA, GLUT, SER, OCT, DA.",
    ),
    "input_neuropil": (
        "input_neuropils",
        lambda x: match_to_neuropil(x),
        "Brain region / neuropil with upstream synaptic connections.",
    ),
    "output_neuropil": (
        "output_neuropils",
        lambda x: match_to_neuropil(x),
        "Brain region / neuropil with downstream synaptic connections.",
    ),
    "io_hemisphere": ("hemisphere_fingerprint", None, "Input / Output Hemispheres"),
}


class NeuronDB(object):
    def __init__(self, data_file_rows):
        self.neuron_data = {}
        self.rids_of_neurons_with_inherited_tags = []

        for i, r in enumerate(data_file_rows):
            if not i:
                # check header
                assert r == DATA_FILE_COLUMNS
                continue
            root_id = self._get_value(r, "root_id", to_type=int)

            def _compact_tag(anno_tag):
                # TODO: get rid of this
                return anno_tag.replace(
                    "; Part of comprehensive neck connective tracing; contact Connectomics Group Cambridge "
                    "for more detailed information on descending/ascending neurons",
                    "",
                )

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
                "tag": [_compact_tag(t) for t in self._get_value(r, "tag", split=True)],
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
            }

        log(f"App initialization augmenting..")
        # augment
        for nd in self.neuron_data.values():
            if nd["inherited_tag_root_id"]:
                assert nd["tag"] or nd["classes"]
                self.rids_of_neurons_with_inherited_tags.append(nd["root_id"])
            nd["annotations"] = "&nbsp; <b>&#x2022;</b> &nbsp;".join(
                [self._trim_long_tokens(t) for t in nd["tag"]]
            )
            nd["hemisphere_fingerprint"] = NeuronDB.hemisphere_fingerprint(
                nd["input_neuropils"], nd["output_neuropils"]
            )
            nd["class"] = ", ".join([c for c in nd["classes"]])

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

        # For now limit to most common categories.
        # TODO: find a better way to resolve page loading slowness for huge lists
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
                "caption": _caption("Annotations", len(labels)),
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

    @staticmethod
    def hemisphere_fingerprint(input_pils, output_pils):
        def fp(pils):
            if pils:
                left = any([p.endswith("_L") for p in pils])
                center = any([not (p.endswith("_L") or p.endswith("_R")) for p in pils])
                right = any([p.endswith("_R") for p in pils])
                if len([v for v in [left, center, right] if v]) > 1:
                    return "Mix"
                elif left:
                    return "Left"
                elif center:
                    return "Mid"
                elif right:
                    return "Right"
                else:
                    return "?"

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

        chaining_rule, free_form_terms, structured_terms = NeuronDB.parse_search_query(
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
            predicate = NeuronDB._make_structured_terms_predicate(
                chaining_rule=chaining_rule, structured_terms=structured_terms
            )
            term_search_results.append(
                [k for k, v in self.neuron_data.items() if predicate(v)]
            )

        return NeuronDB._apply_chaining_rule(
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
        chaining_rule, free_form_terms, structured_terms = NeuronDB.parse_search_query(
            query
        )
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

    # Private helpers

    @staticmethod
    def _make_equality_predicate(lhs, rhs):
        lhs = lhs.lower()
        if lhs not in STRUCTURED_SEARCH_ATTRIBUTES:
            NeuronDB._raise_unsupported_attr_for_structured_search(lhs)

        attr_key = STRUCTURED_SEARCH_ATTRIBUTES[lhs][0]
        # if conversion fails, default to false predicate
        try:
            conversion_func = STRUCTURED_SEARCH_ATTRIBUTES[lhs][1]
            if conversion_func:
                rhs = conversion_func(rhs)
        except:
            return lambda x: False

        def eq_checker(x):
            val = x.get(attr_key)
            if isinstance(val, list):
                return rhs in val
            else:
                return rhs == val

        return lambda nd: eq_checker(nd)

    @staticmethod
    def _make_has_predicate(rhs):
        rhs = rhs.lower()
        if rhs not in STRUCTURED_SEARCH_ATTRIBUTES:
            NeuronDB._raise_unsupported_attr_for_structured_search(rhs)

        attr_key = STRUCTURED_SEARCH_ATTRIBUTES[rhs][0]
        return lambda nd: nd.get(attr_key)

    @staticmethod
    def _raise_unsupported_attr_for_structured_search(attr_name):
        raise ValueError(
            f"Structured query by attribute <b>{attr_name}</b> is not supported. Possible solutions:"
            f"<br>- look for typos in <b>{attr_name}</b>, or try searching by one of the supported "
            f"attribute: {', '.join(STRUCTURED_SEARCH_ATTRIBUTES.keys())} (read more about advanced "
            f"search on the FAQ page)."
            f"<br>- if this was not meant to be a structured query, wrap it in double quotes to force "
            f"free form search"
        )

    @staticmethod
    def _make_predicate(structured_term):
        if structured_term["op"] == OP_EQUAL:
            return NeuronDB._make_equality_predicate(
                lhs=structured_term["lhs"], rhs=structured_term["rhs"]
            )
        elif structured_term["op"] == OP_NOT_EQUAL:
            eqp = NeuronDB._make_equality_predicate(
                lhs=structured_term["lhs"], rhs=structured_term["rhs"]
            )
            return lambda x: not eqp(x)
        elif structured_term["op"] == OP_HAS:
            hp = NeuronDB._make_has_predicate(rhs=structured_term["rhs"])
            return lambda x: hp(x)
        elif structured_term["op"] == OP_NOT:
            hp = NeuronDB._make_has_predicate(rhs=structured_term["rhs"])
            return lambda x: not hp(x)
        elif structured_term["op"] in [OP_IN, OP_NOT_IN]:
            rhs_items = [item.strip() for item in structured_term["rhs"].split(",")]
            predicates = [
                NeuronDB._make_equality_predicate(lhs=structured_term["lhs"], rhs=i)
                for i in rhs_items
            ]
            if structured_term["op"] == OP_IN:
                return lambda x: any([p(x) for p in predicates])
            else:
                return lambda x: not any([p(x) for p in predicates])
        elif structured_term["op"] in [OP_DOWNSTREAM, OP_UPSTREAM]:
            downstream, upstream = load_connections_for_root_id(
                structured_term["rhs"], by_neuropil=False
            )
            target_rid_set = (
                set(downstream)
                if structured_term["op"] == OP_DOWNSTREAM
                else set(upstream)
            )
            return lambda x: x["root_id"] in target_rid_set
        elif structured_term["op"] in [OP_DOWNSTREAM_REGION, OP_UPSTREAM_REGION]:
            downstream, upstream = load_connections_for_root_id(
                structured_term["rhs"], by_neuropil=True
            )
            region_neuropil_set = lookup_neuropil_set(structured_term["lhs"])
            target_rid_set = set()
            for k, v in (
                downstream
                if structured_term["op"] == OP_DOWNSTREAM_REGION
                else upstream
            ).items():
                if k in region_neuropil_set:
                    target_rid_set |= set(v)
            return lambda x: x["root_id"] in target_rid_set
        else:
            raise ValueError(f"Unsupported query operator {structured_term['op']}")

    @staticmethod
    def _make_structured_terms_predicate(chaining_rule, structured_terms):
        predicates = [
            NeuronDB._make_predicate(structured_term=t) for t in structured_terms
        ]
        if len(structured_terms) == 1:
            return predicates[0]
        elif chaining_rule == OP_AND:
            return lambda x: all([p(x) for p in predicates])
        elif chaining_rule == OP_OR:
            return lambda x: any([p(x) for p in predicates])
        else:
            raise ValueError(f"Unsupported chaining rule {chaining_rule}")

    @staticmethod
    def _apply_chaining_rule(chaining_rule, term_search_results):
        if len(term_search_results) == 1:
            return term_search_results[0]
        elif chaining_rule == OP_AND:
            return list(set.intersection(*[set(r) for r in term_search_results]))
        elif chaining_rule == OP_OR:
            return list(set.union(*[set(r) for r in term_search_results]))
        else:
            raise ValueError(f"Unsupported chaining rule {chaining_rule}")

    @staticmethod
    def _extract_search_operators(term, ops=None):
        if not (term.startswith('"') and term.endswith('"')):
            ops = (
                ops
                or SEARCH_TERM_BINARY_OPERATORS
                + SEARCH_TERM_UNARY_OPERATORS
                + SEARCH_CHAINING_OPERATORS
            )
            ops_shorthands = [OPERATOR_METADATA[op][0] for op in ops]
            return [
                op
                for i, op in enumerate(ops)
                if (op in term or ops_shorthands[i] in term)
            ]
        else:
            return []

    @staticmethod
    def _parse_search_terms(terms):
        free_form = []
        structured = []
        for term in terms:
            search_operators = NeuronDB._extract_search_operators(term)
            if len(search_operators) == 1:
                op = search_operators[0]
                parts = NeuronDB._extract_operands(text=term, op=op)
                if len(parts) == 2:
                    if op in SEARCH_TERM_BINARY_OPERATORS:
                        if all(parts):
                            structured.append(
                                {"op": op, "lhs": parts[0], "rhs": parts[1]}
                            )
                            continue
                    elif op in SEARCH_TERM_UNARY_OPERATORS:
                        if not parts[0] and parts[1]:
                            structured.append({"op": op, "rhs": parts[1]})
                            continue

            free_form.append(term)
        return free_form, structured

    @staticmethod
    def _parse_chained_search_query(search_query):
        if search_query and not (
            search_query.startswith('"') and search_query.endswith('"')
        ):
            search_operators = NeuronDB._extract_search_operators(
                search_query, SEARCH_CHAINING_OPERATORS
            )
            if len(search_operators) == 1:
                parts = NeuronDB._extract_operands(
                    text=search_query, op=search_operators[0]
                )
                if len(parts) >= 2 and all(parts):
                    return search_operators[0], parts
        return None, [search_query]

    @staticmethod
    def _extract_operands(text, op):
        parts = [p.strip() for p in text.split(op)]
        # try shorthand if op not found in text
        if len(parts) == 1:
            parts = [p.strip() for p in text.split(OPERATOR_METADATA[op][0])]
        return parts

    @staticmethod
    def parse_search_query(search_query):
        chaining_rule, terms = NeuronDB._parse_chained_search_query(search_query)
        free_form, structured = NeuronDB._parse_search_terms(terms)
        return chaining_rule, free_form, structured

    @staticmethod
    def _get_value(row, col, split=False, to_type=None):
        def convert_type(v):
            return to_type(v) if to_type else v

        val = row[COLUMN_INDEX[col]]
        if split:
            return [convert_type(v) for v in val.split(",")] if val else []
        else:
            return convert_type(val) if val else ""

    @staticmethod
    def _trim_long_tokens(text, limit=50):
        def trim(token):
            if len(token) > limit:
                token = token[: limit - 5] + "..."
            return token

        if text and len(text) > limit:
            return " ".join([trim(t) for t in text.split()])
        return text
