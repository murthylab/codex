from collections import defaultdict
from unittest import TestCase

from src.data.local_data_loader import write_csv
from src.utils.markers import extract_at_most_one_marker
from tests import get_testing_neuron_db


class SandboxTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def test_ben_mala_paper_data(self):
        def neuron_type(nd):
            def fetch():
                olr_type = extract_at_most_one_marker(nd, "olr_type")
                if olr_type:
                    return olr_type
                if nd["cell_type"]:
                    return nd["cell_type"][0]
                if nd["hemibrain_type"]:
                    return nd["hemibrain_type"][0]

            tp = fetch()
            if tp and not any(
                [tp.startswith(prefix) for prefix in ["5", "?", "Unknown"]]
            ):
                return tp

        paper_types_set = set(
            [
                t.strip()
                for t in "LC4, LC6, LC9, LC10a, LC10ad, LC10bc, LC10d, LC11, LC12, LC13, LC15, LC16, LC17, LC18, LC20, LC21, LC22, LC24, LC25, LC26, LC31, LPLC1, LPLC2".split(
                    ","
                )
            ]
        )
        neuron_types = {}
        type_counts = defaultdict(int)
        for rid, ndata in self.neuron_db.neuron_data.items():
            nt = neuron_type(ndata)
            if not nt:
                continue
            neuron_types[rid] = nt
            type_counts[nt] += 1

        syn_counts = defaultdict(lambda: defaultdict(int))
        syn_table_types = set()

        def is_lc_type(tp):
            return tp in paper_types_set or (
                tp.startswith("LC") and not tp.startswith("LCN")
            )

        for r in self.neuron_db.connections_.all_rows():
            tp_from, tp_to = neuron_types.get(r[0]), neuron_types.get(r[1])
            if tp_from and tp_to:
                if is_lc_type(tp_from) or is_lc_type(tp_to):
                    syn_counts[tp_from][tp_to] += r[3]
                    syn_table_types.add(tp_from)
                    syn_table_types.add(tp_to)

        lc_types = set(tp for tp in syn_table_types if is_lc_type(tp))
        print(f"New LC types: {', '.join(sorted(lc_types - paper_types_set))}")
        print(f"Not found LC types: {', '.join(sorted(paper_types_set - lc_types))}")

        relevant_type_counts = {
            k: v for k, v in type_counts.items() if k in syn_table_types
        }
        write_csv(
            rows=sorted(
                [[k, v] for k, v in relevant_type_counts.items()], key=lambda r: r[0]
            ),
            filename="../../static/experimental_data/mala_ben/type_neuron_counts.csv",
        )

        syn_table_types = sorted(syn_table_types)
        syn_table = [["from type", "to type", "synapses"]]
        for tp_from in syn_table_types:
            for tp_to in syn_table_types:
                syn_count = syn_counts[tp_from][tp_to]
                if syn_count:
                    syn_table.append([tp_from, tp_to, syn_count])
        write_csv(
            rows=syn_table,
            filename="../../static/experimental_data/mala_ben/synapse_counts.csv",
        )
