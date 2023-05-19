from unittest import TestCase
from pympler import asizeof

from src.data.brain_regions import REGIONS
from src.data.connections import Connections
from src.data.local_data_loader import (
    load_neuron_db,
    unpickle_neuron_db,
    unpickle_all_neuron_db_versions,
    read_csv,
)
from src.data.neuron_data_initializer import NEURON_DATA_ATTRIBUTE_TYPES

from src.data.versions import (
    DATA_SNAPSHOT_VERSIONS,
    TESTING_DATA_SNAPSHOT_VERSION,
)
from tests import TEST_DATA_ROOT_PATH, get_testing_neuron_db
from collections import defaultdict


class NeuronDataTest(TestCase):
    def setUp(self):
        # this allows to temporarily disable some checks when updating the schema of data files. should be kept empty
        # after the updates are tested and complete
        self.exclude_keys = set([])
        self.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

    def test_content(self):
        self.assertEqual(
            sorted(
                [
                    "label_data",
                    "meta_data",
                    "neuron_data",
                    "connections_",
                    "grouped_synapse_counts",
                    "grouped_connection_counts",
                    "grouped_reciprocal_connection_counts",
                    "search_index",
                ]
            ),
            sorted(self.neuron_db.__dict__.keys()),
        )

        expected_sizes = {
            "connections_": "410 M",
            "neuron_data": "549 M",
            "search_index": "235 M",
            "label_data": "87 M",
            "meta_data": "17 K",
            "grouped_synapse_counts": "108 K",
            "grouped_connection_counts": "111 K",
            "grouped_reciprocal_connection_counts": "69 K",
        }

        def approx_size(ob):
            sz_bytes = asizeof.asizeof(ob)
            num_digs = len(str(sz_bytes))
            if num_digs > 9:
                return f"{round(sz_bytes / 1000000000)} G"
            elif num_digs > 6:
                return f"{round(sz_bytes / 1000000)} M"
            elif num_digs > 3:
                return f"{round(sz_bytes / 1000)} K"
            else:
                return f"{sz_bytes} B"

        actual_sizes = {
            "connections_": approx_size(self.neuron_db.connections_),
            "neuron_data": approx_size(self.neuron_db.neuron_data),
            "search_index": approx_size(self.neuron_db.search_index),
            "label_data": approx_size(self.neuron_db.label_data),
            "meta_data": approx_size(self.neuron_db.meta_data),
            "grouped_synapse_counts": approx_size(
                self.neuron_db.grouped_synapse_counts
            ),
            "grouped_connection_counts": approx_size(
                self.neuron_db.grouped_connection_counts
            ),
            "grouped_reciprocal_connection_counts": approx_size(
                self.neuron_db.grouped_reciprocal_connection_counts
            ),
        }

        def compare_approx_sizes(exp, act):
            if exp.keys() != act.keys():
                return False
            for k, ve in exp.items():
                va = act[k]
                ve_vals = ve.split(" ")
                va_vals = va.split(" ")
                if ve_vals[1] != va_vals[1] or not (
                    0.8 * int(ve_vals[0]) <= int(va_vals[0]) <= 1.2 * int(ve_vals[0])
                ):
                    print(f"Mismatch: {exp=} {act=}")
                    return False
            return True

        self.assertTrue(
            compare_approx_sizes(expected_sizes, actual_sizes),
            "Unexpected DB size, makes sure it's not outdated. To update: rm -r static/data/* then run the service.",
        )

    def test_data_load_equals_pickled_db(self):
        def isnan(vl):
            return vl != vl

        def compare_neuron_dbs(tested, golden):
            self.assertIsNotNone(tested)
            self.assertEqual(
                set(tested.neuron_data.keys()), set(tested.search_index.all_doc_ids())
            )
            self.assertEqual(
                set(tested.neuron_data.keys()),
                set(golden.neuron_data.keys()),
                f"Left minus right: {len(set(tested.neuron_data.keys()) - set(golden.neuron_data.keys()))}, "
                f"Right minus left: {len(set(golden.neuron_data.keys()) - set(tested.neuron_data.keys()))}",
            )

            diff_keys = defaultdict(int)
            diff_vals = defaultdict(int)
            diff_rids = set()
            for rid, nd in tested.neuron_data.items():
                ndp = golden.get_neuron_data(rid)
                self.assertEqual(
                    set(nd.keys()) - self.exclude_keys,
                    set(ndp.keys()) - self.exclude_keys,
                )
                for k, val in nd.items():
                    if k in self.exclude_keys:
                        continue
                    if isnan(val):
                        if not isnan(ndp[k]):
                            diff_keys[k] += 1
                            diff_rids.add(rid)
                    else:
                        if val != ndp[k]:
                            diff_keys[k] += 1
                            diff_vals[f"{k}: {val} vs {ndp[k]}"] += 1
                            diff_rids.add(rid)
            if diff_rids:
                print(f"Diff RIDs {len(diff_rids)}: {sorted(diff_rids)[:100]}")
            self.assertEqual(
                0,
                len(diff_keys),
                f"Diff keys not empty: {diff_keys=}\n\n {len(diff_vals)=}\n\n {diff_vals=}"[
                    :100
                ],
            )
            # compare optional output sets (adjacency)
            for r1, r2 in zip(
                tested.connections_.all_rows(), golden.connections_.all_rows()
            ):
                self.assertEqual(r1, r2)
            if tested.input_sets():
                connected_cells = set(tested.input_sets().keys()).union(
                    set(tested.output_sets().keys())
                )
                not_connected_cells = set(tested.neuron_data.keys()) - connected_cells
                self.assertGreater(4000, len(not_connected_cells))

            # compare optional label data
            self.assertEqual(tested.label_data, golden.label_data)

        # check that all versions loaded
        for v in DATA_SNAPSHOT_VERSIONS:
            print(f"Testing version {v}...")
            unpickled_db = unpickle_neuron_db(
                version=v, data_root_path=TEST_DATA_ROOT_PATH
            )
            loaded_db = load_neuron_db(version=v, data_root_path=TEST_DATA_ROOT_PATH)
            compare_neuron_dbs(tested=loaded_db, golden=unpickled_db)
            del loaded_db

            # check the same for data factory
            factory_db = get_testing_neuron_db(version=v)
            compare_neuron_dbs(tested=factory_db, golden=unpickled_db)

            # check neuron attributes
            expected_attribs = {
                k: v
                for k, v in NEURON_DATA_ATTRIBUTE_TYPES.items()
                if k not in self.exclude_keys
            }
            for nd in unpickled_db.neuron_data.values():
                attribs = {
                    k: type(v) for k, v in nd.items() if k not in self.exclude_keys
                }
                self.assertEqual(
                    expected_attribs, attribs, f"Mismatch in types for {nd}"
                )

            del unpickled_db
            del factory_db
            print(f"Done testing version {v}")

    # this is a helper test to not forget clean up excluded keys once schema has updated
    def test_no_keys_excluded(self):
        self.assertEqual(0, len(self.exclude_keys))

    def test_input_output_counts(self):
        input_partners = defaultdict(set)
        input_synapses = defaultdict(int)
        input_neuropils = defaultdict(set)
        output_partners = defaultdict(set)
        output_synapses = defaultdict(int)
        output_neuropils = defaultdict(set)

        for r in self.neuron_db.connections_.all_rows():
            input_partners[r[1]].add(r[0])
            input_synapses[r[1]] += r[3]
            input_neuropils[r[1]].add(r[2])
            output_partners[r[0]].add(r[1])
            output_synapses[r[0]] += r[3]
            output_neuropils[r[0]].add(r[2])

        for rid, nd in self.neuron_db.neuron_data.items():
            self.assertEqual(nd["input_cells"], len(input_partners[rid]))
            self.assertEqual(nd["input_synapses"], input_synapses[rid])
            self.assertEqual(set(nd["input_neuropils"]), input_neuropils[rid])
            self.assertEqual(nd["output_cells"], len(output_partners[rid]))
            self.assertEqual(nd["output_synapses"], output_synapses[rid])
            self.assertEqual(set(nd["output_neuropils"]), output_neuropils[rid])

    def test_loading(self):
        # check that all versions loaded
        neuron_dbs = unpickle_all_neuron_db_versions(data_root_path=TEST_DATA_ROOT_PATH)
        for v in DATA_SNAPSHOT_VERSIONS:
            self.assertIsNotNone(neuron_dbs[v])
            self.assertEqual(
                set(neuron_dbs[v].neuron_data.keys()),
                set(neuron_dbs[v].search_index.all_doc_ids()),
            )

    def test_neuropils(self):
        input_neuropils = defaultdict(set)
        output_neuropils = defaultdict(set)
        for r in self.neuron_db.connections_.all_rows():
            self.assertTrue(r[2] in REGIONS)
            input_neuropils[r[1]].add(r[2])
            output_neuropils[r[0]].add(r[2])
        for nd in self.neuron_db.neuron_data.values():
            self.assertEqual(
                sorted(input_neuropils[nd["root_id"]]), sorted(nd["input_neuropils"])
            )
            self.assertEqual(
                sorted(output_neuropils[nd["root_id"]]), sorted(nd["output_neuropils"])
            )

    def test_connections_representation(self):
        con_rows = [
            (int(r[0]), int(r[1]), r[2], int(r[3]), r[4])
            for r in read_csv(
                f"{TEST_DATA_ROOT_PATH}/{TESTING_DATA_SNAPSHOT_VERSION}/connections.csv.gz"
            )[1:]
        ]
        cons = Connections(con_rows[:1000])
        self.assertEqual(sorted(con_rows[:1000]), sorted(cons.all_rows()))
        cons = Connections(con_rows)
        for r in zip(cons.all_rows(), self.neuron_db.connections_.all_rows()):
            self.assertEqual(r[0], r[1])
