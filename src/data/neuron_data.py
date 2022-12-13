from collections import defaultdict
from functools import lru_cache
from random import choice

from src.data.brain_regions import neuropil_hemisphere, REGIONS
from src.data.catalog import (
    get_neurons_file_columns,
    get_similar_cells_file_columns,
    get_labels_file_columns,
    get_coordinates_file_columns,
    get_classes_file_columns,
    get_connections_file_columns,
)
from src.data.neuron_collections import NEURON_COLLECTIONS
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.search_index import SearchIndex
from src.data.structured_search_filters import (
    make_structured_terms_predicate,
    apply_chaining_rule,
    parse_search_query,
)
from src.configuration import MIN_SYN_COUNT
from src.utils.formatting import compact_tag, nanometer_to_flywire_coordinates
from src.utils.logging import log

# Keywords will be matched against these attributes
NEURON_SEARCH_LABEL_ATTRIBUTES = [
    "root_id",
    "name",
    "group",
    "nt_type",
    "classes",
    "hemisphere_fingerprint",
]

NEURON_DATA_ATTRIBUTES = {
    "ach_avg": float,
    "class": str,
    "classes": list,
    "da_avg": float,
    "gaba_avg": float,
    "glut_avg": float,
    "group": str,
    "hemisphere_fingerprint": str,
    "input_cells": int,
    "input_neuropils": list,
    "input_synapses": int,
    "name": str,
    "nt_type": str,
    "nt_type_score": float,
    "oct_avg": float,
    "output_cells": int,
    "output_neuropils": list,
    "output_synapses": int,
    "position": list,
    "root_id": int,
    "ser_avg": float,
    "similar_root_id_scores": list,
    "similar_root_ids": list,
    "supervoxel_id": list,
    "symmetrical_root_id_scores": list,
    "symmetrical_root_ids": list,
    "tag": list,
}


class NeuronDB(object):
    def __init__(
        self,
        neuron_file_rows,
        connection_rows,
        label_rows,
        labels_file_timestamp,
        coordinate_rows,
        classification_rows,
        similar_cell_rows,
    ):
        self.neuron_data = {}
        self.label_data = {}
        self.labels_file_timestamp = labels_file_timestamp

        log(f"App initialization processing neuron data..")
        column_index = {}
        for i, r in enumerate(neuron_file_rows):
            if i == 0:
                assert r == get_neurons_file_columns()
                column_index = {c: i for i, c in enumerate(r)}
                continue

            def _get_value(col, split=False, to_type=None):
                def convert_type(v):
                    return to_type(v) if to_type else v

                val = r[column_index[col]]
                if split:
                    return [convert_type(v) for v in val.split(",")] if val else []
                else:
                    return convert_type(val) if val else ""

            root_id = _get_value("root_id", to_type=int)
            assert root_id not in self.neuron_data
            self.neuron_data[root_id] = {
                "root_id": root_id,
                "name": _get_value("name"),
                "group": _get_value("group"),
                "nt_type": _get_value("nt_type").upper(),
                "nt_type_score": _get_value("nt_type_score", to_type=float),
                "gaba_avg": _get_value("gaba_avg", to_type=float),
                "ach_avg": _get_value("ach_avg", to_type=float),
                "glut_avg": _get_value("glut_avg", to_type=float),
                "oct_avg": _get_value("oct_avg", to_type=float),
                "ser_avg": _get_value("ser_avg", to_type=float),
                "da_avg": _get_value("da_avg", to_type=float),
                # clean
                "classes": [],
                "tag": [],
                "position": [],
                "supervoxel_id": [],
                "input_neuropils": [],
                "output_neuropils": [],
                "similar_root_ids": [],
                "similar_root_id_scores": [],
                "symmetrical_root_ids": [],
                "symmetrical_root_id_scores": [],
            }

        log(f"App initialization processing similar cells data..")
        column_index = {}
        for i, r in enumerate(similar_cell_rows):
            if i == 0:
                assert sorted(r) == sorted(get_similar_cells_file_columns())
                column_index = {c: i for i, c in enumerate(r)}
                continue

            def _get_value(col, split=False, to_type=None):
                def convert_type(v):
                    return to_type(v) if to_type else v

                val = r[column_index[col]]
                if split:
                    return [convert_type(v) for v in val.split(",")] if val else []
                else:
                    return convert_type(val) if val else ""

            root_id = _get_value("root_id", to_type=int)

            self.neuron_data[root_id].update(
                {
                    "similar_root_ids": _get_value(
                        "similar_root_ids", split=True, to_type=int
                    ),
                    "similar_root_id_scores": _get_value(
                        "similar_root_id_scores", split=True, to_type=float
                    ),
                    "symmetrical_root_ids": _get_value(
                        "symmetrical_root_ids", split=True, to_type=int
                    ),
                    "symmetrical_root_id_scores": _get_value(
                        "symmetrical_root_id_scores", split=True, to_type=float
                    ),
                }
            )

        log(f"App initialization processing label data..")
        labels_file_columns = get_labels_file_columns()
        rid_col_idx = labels_file_columns.index("root_id")
        tag_col_idx = labels_file_columns.index("tag")
        not_found_rids = set()
        not_found_tags = defaultdict(int)
        for i, r in enumerate(label_rows or []):
            if i == 0:
                # check header
                assert r == labels_file_columns
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
            label_dict = NeuronDB._row_to_dict(
                columns=labels_file_columns,
                row=r,
                exclude={"root_id"},
                to_int={"user_id", "supervoxel_id", "tag_id"},
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

        log(f"App initialization processing coordinates data..")
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

        log(f"App initialization processing classification data..")
        classes_file_columns = get_classes_file_columns()
        rid_col_idx = classes_file_columns.index("root_id")
        cls_col_idx = classes_file_columns.index("class")
        not_found_rids = set()
        all_classes = set()
        for i, r in enumerate(classification_rows or []):
            if i == 0:
                # check header
                assert r == classes_file_columns
                continue
            rid = int(r[rid_col_idx])
            if rid not in self.neuron_data:
                not_found_rids.add(rid)
                continue
            cl = r[cls_col_idx]
            if cl not in self.neuron_data[rid]["classes"]:
                all_classes.add(cl)
                self.neuron_data[rid]["classes"].append(cl)
        len([nd for nd in self.neuron_data.values() if not nd["classes"]])
        log(
            f"App initialization classes loaded for all root ids."
            f"not found rids: {len(not_found_rids)}, "
            f"max list val: {max([len(nd['classes']) for nd in self.neuron_data.values()])}, "
            f"classes: {all_classes}"
        )

        log(f"App initialization loading connections..")
        self.connection_rows = []
        input_neuropils = defaultdict(set)
        output_neuropils = defaultdict(set)
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
            assert neuropil == "NONE" or neuropil in REGIONS.keys()
            if neuropil != "NONE":
                input_neuropils[to_node].add(neuropil)
                output_neuropils[from_node].add(neuropil)
            input_synapses[to_node] += syn_count
            output_synapses[from_node] += syn_count
            self.connection_rows.append(
                [from_node, to_node, neuropil, syn_count, nt_type]
            )

        log(f"App initialization augmenting..")
        for rid, nd in self.neuron_data.items():
            nd["input_neuropils"] = sorted(input_neuropils[rid])
            nd["output_neuropils"] = sorted(output_neuropils[rid])
            nd["input_synapses"] = input_synapses[rid]
            nd["output_synapses"] = output_synapses[rid]
            nd["hemisphere_fingerprint"] = NeuronDB.hemisphere_fingerprint(
                nd["input_neuropils"], nd["output_neuropils"]
            )
            nd["class"] = ", ".join([c for c in nd["classes"]])
            nd["input_cells"] = len(self.input_sets()[rid])
            nd["output_cells"] = len(self.output_sets()[rid])

        log(f"App initialization building search index..")

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
        except:
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
                connections_loader=self.connections_by_region,
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
    def _row_to_dict(columns, row, exclude, to_int):
        res = {}
        for i, c in enumerate(columns):
            if not exclude or c not in exclude:
                if not to_int or c not in to_int:
                    res[c] = row[i]
                else:
                    res[c] = int(row[i])
        return res
