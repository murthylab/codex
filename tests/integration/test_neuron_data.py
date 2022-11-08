from unittest import TestCase

from src.data.local_data_loader import unpickle_all_neuron_db_versions, \
    load_neuron_db
from src.data.neuron_data_factory import NeuronDataFactory

from src.data.versions import DATA_SNAPSHOT_VERSIONS
from tests import TEST_DATA_ROOT_PATH
from collections import defaultdict


class NeuronDataTest(TestCase):
    def setUp(self):
        self.neuron_dbs = unpickle_all_neuron_db_versions(data_root_path=TEST_DATA_ROOT_PATH)

    def test_data_load_equals_pickled_db(self):
        versions = DATA_SNAPSHOT_VERSIONS
        loaded_neuron_dbs = {v: load_neuron_db(version=v, data_root_path=TEST_DATA_ROOT_PATH) for v in versions}

        def isnan(vl):
            return vl != vl

        def compare_neuron_dbs(tested, golden):
            self.assertIsNotNone(tested)
            self.assertEqual(set(tested.neuron_data.keys()),
                             set(tested.search_index.all_doc_ids()))
            self.assertEqual(set(tested.neuron_data.keys()),
                             set(golden.neuron_data.keys()))

            diff_keys = defaultdict(int)
            for rid, nd in tested.neuron_data.items():
                ndp = golden.get_neuron_data(rid)
                self.assertEqual(set(nd.keys()), set(ndp.keys()))
                for k, val in nd.items():
                    if isnan(val):
                        if not isnan(ndp[k]):
                            diff_keys[k] += 1
                    else:
                        if val != ndp[k]:
                            diff_keys[k] += 1
            self.assertEqual(0, len(diff_keys), f"Diff keys not empty: {diff_keys}")

        # check that all versions loaded
        for v in versions:
            compare_neuron_dbs(tested=loaded_neuron_dbs[v], golden=self.neuron_dbs[v])

        # check the same for data factory
        neuron_data_factory = NeuronDataFactory(data_root_path=TEST_DATA_ROOT_PATH)
        for v in versions:
            compare_neuron_dbs(tested=neuron_data_factory.get(v), golden=self.neuron_dbs[v])
