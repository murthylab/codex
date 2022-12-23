from unittest import TestCase

from src.data.local_data_loader import (
    load_neuron_db,
    unpickle_neuron_db,
)
from src.data.neuron_data import NEURON_DATA_ATTRIBUTES
from src.data.neuron_data_factory import NeuronDataFactory

from src.data.versions import DATA_SNAPSHOT_VERSIONS
from tests import TEST_DATA_ROOT_PATH
from collections import defaultdict


class NeuronDataTest(TestCase):
    def setUp(self):
        # this allows to temporarily disable some checks when updating the schema of data files. should be kept empty
        # after the updates are tested and complete
        self.exclude_keys = set([])

    def test_data_load_equals_pickled_db(self):
        def isnan(vl):
            return vl != vl

        def compare_neuron_dbs(tested, golden):
            self.assertIsNotNone(tested)
            self.assertEqual(
                set(tested.neuron_data.keys()), set(tested.search_index.all_doc_ids())
            )
            self.assertEqual(
                set(tested.neuron_data.keys()), set(golden.neuron_data.keys())
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
            neuron_data_factory = NeuronDataFactory(
                data_root_path=TEST_DATA_ROOT_PATH, preload_latest=False
            )
            factory_db = neuron_data_factory.get(v)
            compare_neuron_dbs(tested=factory_db, golden=unpickled_db)

            # check neuron attributes
            for nd in unpickled_db.neuron_data.values():
                attribs = {k: type(v) for k, v in nd.items()}
                self.assertEqual(
                    NEURON_DATA_ATTRIBUTES, attribs, f"Mismatch in types for {nd}"
                )

            del unpickled_db
            del factory_db
            print(f"Done testing version {v}")

    # this is a helper test to not forget clean up excluded keys once schema has updated
    def test_no_keys_excluded(self):
        self.assertEqual(0, len(self.exclude_keys))
