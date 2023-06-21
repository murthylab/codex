from collections import defaultdict
from functools import lru_cache
from random import choice

from src.data.connections import Connections
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.optic_lobe_cell_types import (
    COLUMNAR_CELL_TYPE_GROUPS,
    COLUMNAR_CELL_SUPER_CLASSES,
    feasible_candidate,
)
from src.data.search_index import SearchIndex
from src.data.structured_search_filters import (
    make_structured_terms_predicate,
    apply_chaining_rule,
    parse_search_query,
    OP_IN,
)
from src.configuration import MIN_NBLAST_SCORE_SIMILARITY
from src.data.svd import Svd
from src.utils.formatting import (
    display,
    percentage,
)
from src.utils.logging import log

# Keywords will be matched against these attributes
from src.utils.stats import jaccard_weighted, jaccard_binary

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
    "morphology_cluster",
    "connectivity_cluster",
]


class NeuronDB(object):
    def __init__(
        self,
        neuron_attributes,
        neuron_connection_rows,
        label_data,
        labels_file_timestamp,
        grouped_synapse_counts,
        grouped_connection_counts,
        grouped_reciprocal_connection_counts,
        svd_rows,
    ):
        self.neuron_data = neuron_attributes
        self.connections_ = Connections(neuron_connection_rows)
        self.label_data = label_data
        self.grouped_synapse_counts = grouped_synapse_counts
        self.grouped_connection_counts = grouped_connection_counts
        self.grouped_reciprocal_connection_counts = grouped_reciprocal_connection_counts
        self.meta_data = {"labels_file_timestamp": labels_file_timestamp}
        self.svd = Svd(svd_rows)

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

        self._create_markers()

    def input_sets(self, min_syn_count=0):
        return self.input_output_partner_sets(min_syn_count)[0]

    def output_sets(self, min_syn_count=0):
        return self.input_output_partner_sets(min_syn_count)[1]

    @lru_cache
    def input_output_partner_sets(self, min_syn_count=0):
        ins, outs = self.input_output_partners_with_synapse_counts(
            min_syn_count=min_syn_count
        )
        ins = {k: set(v.keys()) for k, v in ins.items()}
        outs = {k: set(v.keys()) for k, v in outs.items()}
        return ins, outs

    @lru_cache
    def input_output_partners_with_synapse_counts(self, min_syn_count=0):
        ins, outs = self.connections_.input_output_synapse_counts()
        if min_syn_count:

            def apply_syn_threshold(syn_counts):
                return {
                    rid_: cnt
                    for rid_, cnt in syn_counts.items()
                    if cnt >= min_syn_count
                }

            ins = {k: apply_syn_threshold(v) for k, v in ins.items()}
            outs = {k: apply_syn_threshold(v) for k, v in outs.items()}

        for rid in self.neuron_data.keys():
            if rid not in ins:
                ins[rid] = {}
            if rid not in outs:
                outs[rid] = {}
        return ins, outs

    @lru_cache
    def cell_connections(self, cell_id):
        return list(self.connections_.rows_for_cell(cell_id))

    def connections(self, ids, induced=False, min_syn_count=0, nt_type=None):
        if nt_type and nt_type not in NEURO_TRANSMITTER_NAMES:
            raise ValueError(
                f"Unknown NT type: {nt_type}, must be one of {NEURO_TRANSMITTER_NAMES}"
            )
        if induced:
            return list(
                self.connections_.rows_between_sets(
                    ids, ids, min_syn_count=min_syn_count, nt_type=nt_type
                )
            )
        else:
            return list(
                self.connections_.rows_for_set(
                    ids, min_syn_count=min_syn_count, nt_type=nt_type
                )
            )

    @lru_cache
    def connections_up_down(self, cell_id, by_neuropil=False):
        try:
            cell_id = int(cell_id)
        except ValueError:
            raise ValueError(f"'{cell_id}' is not a valid cell ID")
        table = self.cell_connections(cell_id)
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

    def num_synapses(self):
        return self.connections_.num_synapses()

    def num_connections(self):
        return self.connections_.num_connections()

    @lru_cache
    def num_labels(self):
        return sum([len(nd["label"]) for nd in self.neuron_data.values()])

    @lru_cache
    def num_typed_or_identified_cells(self):
        return len(
            [
                nd
                for nd in self.neuron_data.values()
                if any([nd[attr] for attr in ["label", "cell_type", "hemibrain_type"]])
            ]
        )

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
    def categories(self, top_values, exclude_internal_markers, for_attr_name=None):
        value_counts_dict = defaultdict(lambda: defaultdict(int))
        assigned_to_num_cells_dict = defaultdict(int)
        category_attr_names = {
            "Neurotransmitter Type": "nt_type",
            "Flow": "flow",
            "Super Class": "super_class",
            "Class": "class",
            "Sub Class": "sub_class",
            "Cell Type": "cell_type",
            "Hemibrain Type": "hemibrain_type",
            "Hemilineage": "hemilineage",
            "Nerve": "nerve",
            "Cell Body Side": "side",
            "Community Identification Label": "label",
            "Connectivity Labels": "marker",
            "Max In/Out Neuropil": "group",
            "Morphology cluster": "morphology_cluster",
            "Connectivity cluster": "connectivity_cluster",
        }
        for nd in self.neuron_data.values():
            for v in category_attr_names.values():
                if for_attr_name and v != for_attr_name:
                    continue
                val = nd[v]
                if not val:
                    continue

                if isinstance(val, list):
                    assigned = False
                    for c in val:
                        if (
                            v == "marker" and exclude_internal_markers and ":" in c
                        ):  # skip temporary OL tagging markers
                            continue
                        else:
                            assigned = True
                            value_counts_dict[v][c] += 1
                else:
                    assigned = True
                    value_counts_dict[v][val] += 1

                if assigned:
                    assigned_to_num_cells_dict[v] += 1

        def _caption(name, assigned_to_count, values_count):

            caption = (
                f"<b>{name}</b><small style='color: teal'>"
                f"<br>- Assigned to {display(assigned_to_count)} cells / {percentage(assigned_to_count, self.num_cells())}"
                f"<br>- {display(values_count)} unique values"
            )
            if values_count > top_values:
                caption += f". Showing top {top_values}</small> <b>&#8594;</b>"
            else:
                caption += "</small>"
            return caption

        def _sorted_counts(d):
            lst_all = sorted([(k, v) for k, v in d.items() if k], key=lambda p: -p[1])
            return lst_all[:top_values]

        return [
            {
                "caption": _caption(
                    ck, assigned_to_num_cells_dict[cv], len(value_counts_dict[cv])
                ),
                "key": cv,
                "counts": _sorted_counts(value_counts_dict[cv]),
            }
            for ck, cv in category_attr_names.items()
            if value_counts_dict[cv]
        ]

    # Returns value ranges for all attributes with not too many different values. Used for advanced search dropdowns.
    @lru_cache
    def dynamic_ranges(self, range_cardinality_cap=40):
        res = {}
        for dct in self.categories(
            top_values=range_cardinality_cap, exclude_internal_markers=False
        ):
            if len(dct["counts"]) < range_cardinality_cap:
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

    @lru_cache
    def get_similar_shape_cells(
        self,
        root_id,
        include_self,
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
        if include_self:
            scores.append((root_id, 10))
        scores = sorted(scores, key=lambda p: -p[1])[:top_k]
        return {p[0]: p[1] for p in scores}

    @lru_cache
    def get_similar_connectivity_cells(
        self,
        root_id,
        include_upstream=True,
        include_downstream=True,
        weighted=False,
        with_same_attributes=None,
        include_score_threshold=0.2,
        min_score_threshold=0.1,
        min_score_limit=20,
    ):
        if not self.is_in_dataset(root_id):
            raise ValueError(
                f"{root_id} is not a valid cell ID or not included in this data snapshot."
            )
        if weighted:
            ins, outs = self.input_output_partners_with_synapse_counts()
            jaccard_score = jaccard_weighted
            upstream_filter_attr_name = "input_synapses"
            downstream_filter_attr_name = "output_synapses"
        else:
            ins, outs = self.input_output_partner_sets()
            jaccard_score = jaccard_binary
            upstream_filter_attr_name = "input_cells"
            downstream_filter_attr_name = "output_cells"

        def calc_range_for_threshold(attr_name):
            val = self.get_neuron_data(root_id)[attr_name]
            return val * min_score_threshold, val / min_score_threshold

        upstream_filter_range = calc_range_for_threshold(upstream_filter_attr_name)
        downstream_filter_range = calc_range_for_threshold(downstream_filter_attr_name)

        if with_same_attributes:
            match_attributes = {
                attr: self.neuron_data[root_id][attr]
                for attr in with_same_attributes.split(",")
            }
        else:
            match_attributes = None

        def calc_similarity_score(r, nd):
            # optimization filters
            if include_upstream and not (
                upstream_filter_range[0]
                <= nd[upstream_filter_attr_name]
                <= upstream_filter_range[1]
            ):
                return 0
            if include_downstream and not (
                downstream_filter_range[0]
                <= nd[downstream_filter_attr_name]
                <= downstream_filter_range[1]
            ):
                return 0
            if match_attributes and not all(
                [nd[attr] == val for attr, val in match_attributes.items()]
            ):
                return 0

            combined_score, num_scores = 0, 0
            if include_upstream:
                combined_score += jaccard_score(ins[root_id], ins[r])
                num_scores += 1
            if include_downstream:
                combined_score += jaccard_score(outs[root_id], outs[r])
                num_scores += 1
            return combined_score / num_scores

        scores = []
        for rid, ndata in self.neuron_data.items():
            score = calc_similarity_score(rid, ndata)
            if score >= min_score_threshold:
                scores.append((rid, score))
        scores = sorted(scores, key=lambda p: -p[1])
        res = {}
        for p in scores:
            if p[1] >= include_score_threshold or len(res) < min_score_limit:
                res[p[0]] = p[1]
            else:
                break
        return res

    @lru_cache
    def get_similar_spectral_cells(
        self,
        root_id,
        projected_to_root_id=None,
        include_upstream=True,
        include_downstream=True,
        limit=100,
    ):
        if projected_to_root_id:
            v1 = self.svd.get_vec_copy(
                root_id, up=include_upstream, down=include_downstream
            )
            v2 = self.svd.get_vec_copy(
                projected_to_root_id, up=include_upstream, down=include_downstream
            )
            if not v1 or not v2:
                return {}
            vec = []
            for i, v1v in enumerate(v1):
                vec.append(v2[i] + (v2[i] - v1v))
            norm = self.svd.calculate_norm(vec)
            scores = self.svd.vec_score_pairs_sorted(
                vec=vec, norm=norm, up=include_upstream, down=include_downstream
            )
        else:
            scores = self.svd.rid_score_pairs_sorted(
                rid=root_id, up=include_upstream, down=include_downstream
            )
        res = {}
        for p in scores[:limit]:
            res[p[0]] = p[1]
        return res

    def get_label_data(self, root_id):
        root_id = int(root_id)
        return self.label_data.get(root_id)

    def label_data_for_ids(self, ids):
        return [self.label_data[r] for r in ids]

    def cell_ids_with_label_data(self):
        return list(self.label_data.keys())

    def labels_ingestion_timestamp(self):
        return self.meta_data["labels_file_timestamp"]

    @lru_cache
    def search(self, search_query, case_sensitive=False, word_match=False):
        if not search_query:
            return sorted(
                self.neuron_data.keys(),
                key=lambda rid: self.neuron_data[rid]["input_cells"]
                + self.neuron_data[rid]["output_cells"],
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
                input_sets_getter=self.input_sets,
                output_sets_getter=self.output_sets,
                connections_loader=self.connections_up_down,
                similar_cells_loader=self.get_similar_shape_cells,
                similar_connectivity_loader=self.get_similar_connectivity_cells,
                similar_spectral_loader=self.get_similar_spectral_cells,
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

    def _create_markers(self):
        # Add markers for special cells (as per FlyWire flagship paper)
        special_cells = self._identify_special_cells()
        for tp, lst in special_cells.items():
            for rid in lst:
                self.neuron_data[rid]["marker"].append(tp)

        # Add tagging candidate markers for columnar cells in the Optic Lobe
        for (
            cst_type,
            tagged_and_candidate_rids,
        ) in self._collect_columnar_cell_tagging_candidates().items():
            tagged_left_count = len(
                [
                    rid
                    for rid in tagged_and_candidate_rids[0]
                    if self.neuron_data[rid]["side"] == "left"
                ]
            )
            tagged_right_count = len(
                [
                    rid
                    for rid in tagged_and_candidate_rids[0]
                    if self.neuron_data[rid]["side"] == "right"
                ]
            )
            candidate_left_count = len(
                [
                    rid
                    for rid in tagged_and_candidate_rids[1]
                    if self.neuron_data[rid]["side"] == "left"
                ]
            )
            candidate_right_count = len(
                [
                    rid
                    for rid in tagged_and_candidate_rids[1]
                    if self.neuron_data[rid]["side"] == "right"
                ]
            )
            self.meta_data[f"{cst_type}_tagged_count_left"] = tagged_left_count
            self.meta_data[f"{cst_type}_tagged_count_right"] = tagged_right_count
            self.meta_data[f"{cst_type}_candidate_count_left"] = candidate_left_count
            self.meta_data[f"{cst_type}_candidate_count_right"] = candidate_right_count
            for rid in tagged_and_candidate_rids[0]:
                self.neuron_data[rid]["marker"].append(f"columnar:{cst_type}")
            for rid in tagged_and_candidate_rids[1]:
                self.neuron_data[rid]["marker"].append(f"columnar_candidate:{cst_type}")

    def _identify_special_cells(self):
        ins, outs = self.input_output_partner_sets()
        rich_club = {
            rid
            for rid in self.neuron_data.keys()
            if len(ins[rid]) + len(outs[rid]) >= 37
        }
        broadcasters = {
            rid
            for rid in rich_club
            if self.neuron_data[rid]["flow"] == "intrinsic"
            and len(outs[rid]) >= 5 * len(ins[rid])
        }
        integrators = {
            rid
            for rid in rich_club
            if self.neuron_data[rid]["flow"] == "intrinsic"
            and len(ins[rid]) >= 5 * len(outs[rid])
        }
        reciprocals = {
            rid for rid in self.neuron_data.keys() if not ins[rid].isdisjoint(outs[rid])
        }
        return {
            "rich_club": rich_club,
            "broadcaster": broadcasters,
            "integrator": integrators,
            "reciprocal": reciprocals,
        }

    def _collect_columnar_cell_tagging_candidates(self):
        # identify optic lobe columnar cell tagging candidates
        all_annotated_columnar_neurons = set()
        type_to_annotated_neuron_sets = defaultdict(set)

        # first use the "cell_type" attribute to infer correctly tagged cells
        for rid, ndata in self.neuron_data.items():
            for ct in ndata["cell_type"]:
                if ct in COLUMNAR_CELL_TYPE_GROUPS:
                    assert rid not in all_annotated_columnar_neurons
                    type_to_annotated_neuron_sets[ct].add(rid)
                    all_annotated_columnar_neurons.add(rid)

        # then use the community labels to infer more tagged cells
        for type_group_name, types in COLUMNAR_CELL_TYPE_GROUPS.items():
            for t in types:
                type_to_annotated_neuron_sets[type_group_name] |= (
                    set(
                        self.search(
                            f"{t} && super_class {OP_IN} {','.join(COLUMNAR_CELL_SUPER_CLASSES)}",
                            word_match=True,
                        )
                    )
                    - all_annotated_columnar_neurons
                )
                all_annotated_columnar_neurons |= type_to_annotated_neuron_sets[
                    type_group_name
                ]

        def similar_unannotated_cells(type_group, cells):
            candidates = set()
            for c in cells:
                candidates |= set(
                    self.get_similar_shape_cells(c, include_self=False).keys()
                )
            candidates = set(
                [
                    rid
                    for rid in candidates
                    if self.neuron_data[rid]["super_class"]
                    in COLUMNAR_CELL_SUPER_CLASSES
                ]
            )
            candidates -= all_annotated_columnar_neurons
            return set(
                [
                    c
                    for c in candidates
                    if feasible_candidate(
                        type_group=type_group,
                        output_neuropils=self.neuron_data[c]["output_neuropils"],
                    )
                ]
            )

        return {
            t: (v, similar_unannotated_cells(t, v))
            for t, v in type_to_annotated_neuron_sets.items()
        }
