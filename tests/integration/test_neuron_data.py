from unittest import TestCase

from src.data.local_data_loader import unpickle_all_neuron_db_versions, load_neuron_db
from src.data.neuron_data_factory import NeuronDataFactory

from src.data.versions import DATA_SNAPSHOT_VERSIONS
from tests import TEST_DATA_ROOT_PATH
from collections import defaultdict


class NeuronDataTest(TestCase):
    def setUp(self):
        # this allows to temporarily disable some checks when updating the schema of data files. should be kept empty
        # after the updates are tested and complete
        self.exclude_keys = {
            "user_id",
            "inherited_tag_root_id",
            "inherited_tag_score",
            "inherited_tag_mirrored",
        }
        self.neuron_dbs = unpickle_all_neuron_db_versions(
            data_root_path=TEST_DATA_ROOT_PATH
        )

    def test_data_load_equals_pickled_db(self):
        versions = DATA_SNAPSHOT_VERSIONS
        loaded_neuron_dbs = {
            v: load_neuron_db(version=v, data_root_path=TEST_DATA_ROOT_PATH)
            for v in versions
        }

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
                    else:
                        if val != ndp[k]:
                            diff_keys[k] += 1
                            diff_vals[f"{k}: {val} vs {ndp[k]}"] += 1
            self.assertEqual(
                0,
                len(diff_keys),
                f"Diff keys not empty: {diff_keys}\n\n {len(diff_vals)}\n\n {diff_vals=}",
            )
            # compare optional output sets (adjacency)
            self.assertEqual(tested.connection_rows, golden.connection_rows)
            if tested.input_sets():
                connected_cells = set(tested.input_sets().keys()).union(
                    set(tested.output_sets().keys())
                )
                not_connected_cells = set(tested.neuron_data.keys()) - connected_cells
                self.assertGreater(2000, len(not_connected_cells))

            # compare optional label data
            self.assertEqual(tested.label_data, golden.label_data)

        # check that all versions loaded
        for v in versions:
            compare_neuron_dbs(tested=loaded_neuron_dbs[v], golden=self.neuron_dbs[v])

        # check the same for data factory
        neuron_data_factory = NeuronDataFactory(data_root_path=TEST_DATA_ROOT_PATH)
        for v in versions:
            compare_neuron_dbs(
                tested=neuron_data_factory.get(v), golden=self.neuron_dbs[v]
            )

    # this is a helper test to not forget clean up excluded keys once schema has updated
    def test_no_keys_excluded(self):
        self.assertEqual(self.exclude_keys, {})
