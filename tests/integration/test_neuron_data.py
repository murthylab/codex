from unittest import TestCase
from pympler import asizeof
from src.data.local_data_loader import (
    load_neuron_db,
    unpickle_neuron_db,
)
from src.data.neuron_data_initializer import NEURON_DATA_ATTRIBUTE_TYPES

from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION
from tests import TEST_DATA_ROOT_PATH, TEST_NEURON_DATA_FACTORY
from collections import defaultdict


class NeuronDataTest(TestCase):
    def setUp(self):
        # this allows to temporarily disable some checks when updating the schema of data files. should be kept empty
        # after the updates are tested and complete
        self.exclude_keys = set([])

    def test_content(self):
        loaded_db = unpickle_neuron_db(
            version=DEFAULT_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )
        self.assertEqual(
            sorted(
                [
                    "connection_rows",
                    "grouped_synapse_counts",
                    "label_data",
                    "labels_file_timestamp",
                    "neuron_data",
                    "reciprocal_connections",
                    "search_index",
                ]
            ),
            sorted(loaded_db.__dict__.keys()),
        )

        expected_sizes = {
            "connection_rows": "762 M",
            "label_data": "59 M",
            "labels_file_timestamp": "64 B",
            "neuron_data": "419 M",
            "search_index": "189 M",
            "reciprocal_connections": "46 M",
            "grouped_synapse_counts": "112 K",
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
            "connection_rows": approx_size(loaded_db.connection_rows),
            "neuron_data": approx_size(loaded_db.neuron_data),
            "search_index": approx_size(loaded_db.search_index),
            "label_data": approx_size(loaded_db.label_data),
            "labels_file_timestamp": approx_size(loaded_db.labels_file_timestamp),
            "reciprocal_connections": approx_size(loaded_db.reciprocal_connections),
            "grouped_synapse_counts": approx_size(loaded_db.grouped_synapse_counts),
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
                    :1000
                ],
            )
            # compare optional output sets (adjacency)
            self.assertEqual(len(tested.connection_rows), len(golden.connection_rows))
            for r1, r2 in zip(
                sorted(tested.connection_rows), sorted(golden.connection_rows)
            ):
                self.assertEqual(r1, r2)
            if tested.input_sets():
                connected_cells = set(tested.input_sets().keys()).union(
                    set(tested.output_sets().keys())
                )
                not_connected_cells = set(tested.neuron_data.keys()) - connected_cells
                self.assertGreater(2000, len(not_connected_cells))

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
            factory_db = TEST_NEURON_DATA_FACTORY.get(version=v)
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
