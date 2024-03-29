from codex.data.vocabulary import STOP_WORDS
from codex import logger

from codex.utils.parsing import tokenize, edit_distance


class SearchIndex(object):
    def __init__(self, texts_labels_id_tuples):
        self.CS_label_to_row_id = {}
        self.ci_label_to_row_id = {}
        self.CS_token_to_row_id = {}
        self.ci_token_to_row_id = {}
        self.lc_labels = {}

        logger.debug("App initialization creating search index")
        for text_list, label_list, i in texts_labels_id_tuples:
            for txt in text_list:
                self.add_to_index(txt, i, self.CS_label_to_row_id)
                self.add_to_index(txt.lower(), i, self.ci_label_to_row_id)

                tokens = tokenize(txt)
                for t in tokens:
                    self.add_to_index(t, i, self.CS_token_to_row_id)
                    self.add_to_index(t.lower(), i, self.ci_token_to_row_id)

            for lc_label in [str(t).lower() for t in label_list]:
                self.add_to_index(lc_label, i, self.lc_labels)

        logger.debug(
            f"Search index created: {len(self.CS_token_to_row_id)=} {len(self.ci_token_to_row_id)=}"
            f" {len(self.CS_label_to_row_id)=} {len(self.ci_label_to_row_id)=}"
        )

    @staticmethod
    def add_to_index(t, rid, index_dict):
        st = index_dict.get(t, set())
        if not st:
            index_dict[t] = st
        st.add(rid)

    def _search_inner(self, term, case_sensitive=False, word_match=False):
        matching_doc_ids_ranked = []
        matching_doc_ids_set = set()

        def collect(ids):
            if ids:
                new_ids = ids - matching_doc_ids_set
                matching_doc_ids_ranked.extend(new_ids)
                matching_doc_ids_set.update(new_ids)

        term_lower = term.lower()

        # match whole words
        if case_sensitive:
            collect(self.CS_token_to_row_id.get(term))
        else:
            collect(self.ci_token_to_row_id.get(term_lower))

        # match labels (labels are lowercase by default - optimization because there's too many)
        collect(self.lc_labels.get(term_lower))

        if not word_match:
            # match prefixes
            if case_sensitive:
                for k, v in self.CS_token_to_row_id.items():
                    if k.startswith(term):
                        collect(v)
            else:
                for k, v in self.ci_token_to_row_id.items():
                    if k.startswith(term_lower):
                        collect(v)

            # lastly, try to match substrings
            if case_sensitive:
                for k, v in self.CS_label_to_row_id.items():
                    if term in k:
                        collect(v)
            else:
                for k, v in self.ci_label_to_row_id.items():
                    if term_lower in k:
                        collect(v)

        return matching_doc_ids_ranked, matching_doc_ids_set

    def search(self, term, case_sensitive=False, word_match=False):
        if not term or term == "*":
            return list(self.all_doc_ids())

        matching_doc_ids_ranked, matching_doc_ids_set = self._search_inner(
            term=term.replace('"', ""),
            case_sensitive=case_sensitive,
            word_match=word_match,
        )

        # try breaking the search term into tokens. run search for each token and collect resulting doc ids.
        # then append them in this order: first those docs that contain all the terms, then those that do not contain
        # all the terms (ranking)
        if not (term.startswith('"') and term.endswith('"') and len(term) > 1):
            tokens = tokenize(term)
            if len(tokens) > 1 or (
                len(tokens) == 1 and tokens[0] != term
            ):  # 2nd cond if tokenization changes the term
                logger.debug(f"Tokenized search term {term} into {tokens}")
                doc_ids_ranked_lst = []
                doc_ids_set_lst = []
                for tk in tokens:
                    (
                        tk_matching_doc_ids_ranked,
                        tk_matching_doc_ids_set,
                    ) = self._search_inner(
                        term=tk, case_sensitive=case_sensitive, word_match=word_match
                    )
                    doc_ids_ranked_lst.append(tk_matching_doc_ids_ranked)
                    doc_ids_set_lst.append(tk_matching_doc_ids_set)
                intersection_all = set.intersection(*doc_ids_set_lst)
                # append new docs that match all tokens first
                for lst in doc_ids_ranked_lst:
                    for doc_id in lst:
                        if (
                            doc_id in intersection_all
                            and doc_id not in matching_doc_ids_set
                        ):
                            matching_doc_ids_set.add(doc_id)
                            matching_doc_ids_ranked.append(doc_id)
                # lastly append new docs that match some of the tokens
                for lst in doc_ids_ranked_lst:
                    for doc_id in lst:
                        if doc_id not in matching_doc_ids_set:
                            matching_doc_ids_set.add(doc_id)
                            matching_doc_ids_ranked.append(doc_id)

        return matching_doc_ids_ranked

    def closest_token(self, term, case_sensitive, limited_ids_set=None):
        term = term.strip()
        if case_sensitive:
            indx = self.CS_token_to_row_id
        else:
            indx = self.ci_token_to_row_id
            term = term.lower()
        key_set = set(
            indx.keys()
            if not limited_ids_set
            else [k for k, i in indx.items() if not i.isdisjoint(limited_ids_set)]
        )

        # exclude_stopwords
        if case_sensitive:
            key_set = set([k for k in key_set if k.lower() not in STOP_WORDS])
        else:
            key_set -= STOP_WORDS

        # make deterministic (if few minimums)
        key_set = sorted(key_set)

        closest = min(key_set, key=lambda x: edit_distance(x, term))
        return closest, edit_distance(closest, term)

    def all_doc_ids(self):
        res_set = set()
        res_list = []
        # collect ids of neurons with labels first, then the rest
        for indx in [self.CS_label_to_row_id, self.lc_labels]:
            for ids in indx.values():
                for rid in ids:
                    if rid not in res_set:
                        res_set.add(rid)
                        res_list.append(rid)
        return res_list
