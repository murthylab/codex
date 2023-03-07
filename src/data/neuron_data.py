from collections import defaultdict
from functools import lru_cache
from random import choice

from src.data.brain_regions import neuropil_hemisphere, REGIONS
from src.data.catalog import (
    get_neurons_file_columns,
    get_labels_file_columns,
    get_coordinates_file_columns,
    get_connections_file_columns,
    get_nblast_file_columns,
    get_classification_file_columns,
    get_cell_stats_file_columns,
)
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.search_index import SearchIndex
from src.data.structured_search_filters import (
    make_structured_terms_predicate,
    apply_chaining_rule,
    parse_search_query,
)
from src.configuration import MIN_SYN_COUNT, MIN_NBLAST_SCORE_SIMILARITY
from src.utils.formatting import (
    compact_label,
    nanometer_to_flywire_coordinates,
    truncate,
    make_web_safe,
    display,
)
from src.utils.logging import log

NEURON_DATA_ATTRIBUTE_TYPES = {
    # auto assigned based on most prominent input and output neuropils
    "group": str,
    # group + running id (to make unique)
    "name": str,
    # FlyWire identifiers. Root IDs change with every edit -> not stable across data snapshots.
    "root_id": int,
    "supervoxel_id": list,
    # community identification labels
    "label": list,
    # nblast-based similarity. Cell ids + 1-digit scores, mapping all negative to 0 and multiplying by 10,
    # e.g.: 0.14 -> 1, 0.28 -> 3, -0.5 -> 0)
    "similar_cell_scores": dict,
    # neurotransmitter type info with prediction confidence scores
    "nt_type": str,
    "nt_type_score": float,
    "ach_avg": float,
    "gaba_avg": float,
    "glut_avg": float,
    "ser_avg": float,
    "oct_avg": float,
    "da_avg": float,
    # hierarchical annotations & classification
    "flow": str,
    "super_class": str,
    "class": str,
    "sub_class": str,
    "cell_type": str,
    "hemibrain_type": str,
    "hemilineage": str,
    "nerve": str,
    "side": str,
    # I/O counts + regions
    "input_cells": int,
    "input_synapses": int,
    "input_neuropils": list,
    "output_cells": int,
    "output_synapses": int,
    "output_neuropils": list,
    # Left/Center/Right X In/Out
    "hemisphere_fingerprint": str,
    # Marked coordinates by FlyWire community
    "position": list,
    # Cell size measurements
    "length_nm": int,
    "area_nm": int,
    "size_nm": int,
}

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
]


class NeuronDB(object):
    def __init__(
        self,
        neuron_file_rows,
        classification_rows,
        cell_stats_rows,
        connection_rows,
        label_rows,
        labels_file_timestamp,
        coordinate_rows,
        nblast_rows,
    ):
        self.neuron_data = {}
        self.label_data = {}
        self.labels_file_timestamp = labels_file_timestamp

        def _get_value(row, column_index, attr_name):
            attr_val = make_web_safe(row[column_index[attr_name]])
            attr_type = NEURON_DATA_ATTRIBUTE_TYPES[attr_name]
            return attr_type(attr_val) if attr_val else attr_type()

        log("App initialization processing neuron data..")
        assert neuron_file_rows[0] == get_neurons_file_columns()
        neurons_column_index = {c: i for i, c in enumerate(neuron_file_rows[0])}
        for i, r in enumerate(neuron_file_rows[1:]):
            root_id = _get_value(r, neurons_column_index, "root_id")
            assert root_id not in self.neuron_data
            self.neuron_data[root_id] = {"root_id": root_id}
            self.neuron_data[root_id].update(
                {
                    attr_name: _get_value(r, neurons_column_index, attr_name)
                    if attr_name in neurons_column_index
                    else attr_type()
                    for attr_name, attr_type in NEURON_DATA_ATTRIBUTE_TYPES.items()
                }
            )

        log(
            f"App initialization processing classification data with {len(classification_rows)} rows.."
        )
        not_found_classified_root_ids = 0
        assert classification_rows[0] == get_classification_file_columns()
        classification_column_index = {
            c: i for i, c in enumerate(classification_rows[0])
        }
        for i, r in enumerate(classification_rows[1:]):
            root_id = _get_value(r, classification_column_index, "root_id")
            if root_id not in self.neuron_data:
                not_found_classified_root_ids += 1
                continue
            self.neuron_data[root_id].update(
                {
                    attr_name: _get_value(r, classification_column_index, attr_name)
                    for attr_name in get_classification_file_columns()[1:]
                }
            )
        log(
            f"App initialization: {not_found_classified_root_ids} classified ids not found in set of neurons"
        )

        if cell_stats_rows:
            log(
                f"App initialization processing cell stats data with {len(cell_stats_rows)} rows.."
            )
            not_found_stats_root_ids = 0
            assert cell_stats_rows[0] == get_cell_stats_file_columns()
            cell_stats_column_index = {c: i for i, c in enumerate(cell_stats_rows[0])}
            for i, r in enumerate(cell_stats_rows[1:]):
                root_id = _get_value(r, cell_stats_column_index, "root_id")
                if root_id not in self.neuron_data:
                    not_found_stats_root_ids += 1
                    continue
                self.neuron_data[root_id].update(
                    {
                        attr_name: _get_value(r, cell_stats_column_index, attr_name)
                        for attr_name in get_cell_stats_file_columns()[1:]
                    }
                )
            log(
                f"App initialization: {not_found_stats_root_ids} stats root ids not found in set of neurons"
            )

        log("App initialization processing label data..")
        labels_file_columns = get_labels_file_columns()
        rid_col_idx = labels_file_columns.index("root_id")
        label_col_idx = labels_file_columns.index("label")
        not_found_rids = set()
        not_found_labels = defaultdict(int)

        def label_row_to_dict(row):
            res = {}
            for col_i, col_name in enumerate(labels_file_columns):
                if col_name == "root_id":
                    continue
                elif col_name in {"user_id", "supervoxel_id", "label_id"}:
                    res[col_name] = int(row[col_i])
                elif col_name == "label":
                    res[col_name] = make_web_safe(compact_label(row[col_i]))
                else:
                    res[col_name] = row[col_i]
            return res

        for i, r in enumerate(label_rows or []):
            if i == 0:
                # check header
                assert r == labels_file_columns
                continue
            rid = int(r[rid_col_idx])
            if rid not in self.neuron_data:
                not_found_rids.add(rid)
                not_found_labels[r[label_col_idx]] += 1
                continue
            label_data_list = self.label_data.get(rid)
            if not label_data_list:
                label_data_list = []
                self.label_data[rid] = label_data_list
            label_dict = label_row_to_dict(r)
            label_data_list.append(label_dict)
            if (
                label_dict["label"]
                and label_dict["label"] not in self.neuron_data[rid]["label"]
            ):
                self.neuron_data[rid]["label"].append(label_dict["label"])
        log(
            f"App initialization labels loaded for {len(self.label_data)} root ids, "
            f"not found rids: {len(not_found_rids)}"
        )
        if not_found_labels:
            log("Top 10 not found labels:")
            for p in sorted(not_found_labels.items(), key=lambda x: -x[1])[:10]:
                log(f"  {p}")

        log("App initialization processing coordinates data..")
        coordinates_file_columns = get_coordinates_file_columns()
        rid_col_idx = coordinates_file_columns.index("root_id")
        pos_col_idx = coordinates_file_columns.index("position")
        vox_col_idx = coordinates_file_columns.index("supervoxel_id")
        not_found_rids = set()
        for i, r in enumerate(coordinate_rows or []):
            if i == 0:
                # check header
                assert r == coordinates_file_columns
                continue
            rid = int(r[rid_col_idx])
            if rid not in self.neuron_data:
                not_found_rids.add(rid)
                continue
            pos = r[pos_col_idx]
            vox = int(r[vox_col_idx])
            if (
                vox not in self.neuron_data[rid]["supervoxel_id"]
                or pos not in self.neuron_data[rid]["position"]
            ):
                self.neuron_data[rid]["position"].append(pos)
                self.neuron_data[rid]["supervoxel_id"].append(vox)
                fw_x, fw_y, fw_z = nanometer_to_flywire_coordinates(pos)
                assert fw_x and fw_y and fw_z
        for nd in self.neuron_data.values():
            assert len(nd["position"]) == len(nd["supervoxel_id"])
        log(
            f"App initialization coordinates loaded for "
            f"{len([nd for nd in self.neuron_data.values() if nd['position']])} root ids, supervoxel ids loaded for "
            f"{len([nd for nd in self.neuron_data.values() if nd['supervoxel_id']])} root ids, "
            f"not found rids: {len(not_found_rids)}, max list val: {max([(len(nd['position']), nd['root_id']) for nd in self.neuron_data.values()])}"
        )

        log("App initialization loading connections..")
        self.connection_rows = []
        input_neuropils = defaultdict(set)
        output_neuropils = defaultdict(set)
        input_cells = defaultdict(set)
        output_cells = defaultdict(set)
        input_synapses = defaultdict(int)
        output_synapses = defaultdict(int)
        for i, r in enumerate(connection_rows or []):
            if i == 0:
                assert r == get_connections_file_columns()
                continue
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
            assert neuropil in REGIONS
            input_cells[to_node].add(from_node)
            output_cells[from_node].add(to_node)
            input_neuropils[to_node].add(neuropil)
            output_neuropils[from_node].add(neuropil)
            input_synapses[to_node] += syn_count
            output_synapses[from_node] += syn_count
            self.connection_rows.append(
                [from_node, to_node, neuropil, syn_count, nt_type]
            )

        log("App initialization processing NBLAST data..")
        nblast_file_columns = get_nblast_file_columns()
        rid_col_idx = nblast_file_columns.index("root_id")
        scores_col_idx = nblast_file_columns.index("scores")
        not_found_rids = set()
        for i, r in enumerate(nblast_rows or []):
            if i == 0:
                # check header
                assert r == nblast_file_columns
                continue
            from_rid = int(r[rid_col_idx])
            if from_rid not in self.neuron_data:
                not_found_rids.add(from_rid)
                continue
            assert not self.neuron_data[from_rid]["similar_cell_scores"]
            scores_dict = {}
            if r[scores_col_idx]:
                for score_pair in r[scores_col_idx].split(";"):
                    vals = score_pair.split(":")
                    to_rid = int(vals[0])
                    if to_rid in self.neuron_data:
                        score = int(vals[1])
                        assert 0 < score < 10
                        if score >= MIN_NBLAST_SCORE_SIMILARITY:
                            scores_dict[to_rid] = score
                    else:
                        not_found_rids.add(to_rid)
            self.neuron_data[from_rid]["similar_cell_scores"] = scores_dict
        for nd in self.neuron_data.values():
            if "similar_cell_scores" not in nd:
                nd["similar_cell_scores"] = {}
        log(
            f"App initialization NBLAST scores loaded for all root ids. "
            f"Not found rids: {len(not_found_rids)}, "
            f"max list val: {max([0] + [len(nd['similar_cell_scores']) for nd in self.neuron_data.values() if nd['similar_cell_scores']])}, "
            f"neruons with similar cells: {len([1 for nd in self.neuron_data.values() if nd['similar_cell_scores']])}"
        )

        log("App initialization augmenting..")
        for rid, nd in self.neuron_data.items():
            nd["input_neuropils"] = sorted(input_neuropils[rid])
            nd["output_neuropils"] = sorted(output_neuropils[rid])
            nd["input_synapses"] = input_synapses[rid]
            nd["output_synapses"] = output_synapses[rid]
            nd["hemisphere_fingerprint"] = NeuronDB.hemisphere_fingerprint(
                nd["input_neuropils"], nd["output_neuropils"]
            )
            nd["input_cells"] = len(input_cells[rid])
            nd["output_cells"] = len(output_cells[rid])

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
        return sorted(
            set([nd[attr_name] for nd in self.neuron_data.values() if nd[attr_name]])
        )

    @lru_cache
    def categories(self, top_values=10):
        counts_dict = defaultdict(lambda: defaultdict(int))
        category_names = {
            "Identification Labels": "label",
            "Flows": "flow",
            "Super Classes": "super_class",
            "Classes": "class",
            "Sub Classes": "sub_class",
            "Cell Types": "cell_type",
            "Hemibrain Types": "hemibrain_type",
            "Hemilineages": "hemilineage",
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
            "cell_type",
            "hemibrain_type",
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
