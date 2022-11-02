from unittest import TestCase
import os

from src.data.local_data_loader import DATA_ROOT_PATH, unpickle_all_neuron_db_versions, \
    load_neuron_db
from src.data.neuron_data_factory import NeuronDataFactory

# for IDE test
from src.data.versions import DATA_SNAPSHOT_VERSIONS, LATEST_DATA_SNAPSHOT_VERSION

TEST_DATA_ROOT_PATH = os.getcwd().replace('tests/integration', DATA_ROOT_PATH)
# for pytest
if not TEST_DATA_ROOT_PATH.endswith(DATA_ROOT_PATH):
    TEST_DATA_ROOT_PATH += f'/{DATA_ROOT_PATH}'


class NeuronDataTest(TestCase):
    def setUp(self):
        self.neuron_dbs = unpickle_all_neuron_db_versions(data_root_path=TEST_DATA_ROOT_PATH)

    def test_data_load_equals_pickled_db(self):
        versions = DATA_SNAPSHOT_VERSIONS
        loaded_neuron_dbs = {v: load_neuron_db(version=v, data_root_path=TEST_DATA_ROOT_PATH) for v in versions}

        # check that all versions loaded
        for v in versions:
            self.assertIsNotNone(loaded_neuron_dbs[v])
            self.assertEqual(set(loaded_neuron_dbs[v].neuron_data.keys()),
                             set(loaded_neuron_dbs[v].search_index.all_doc_ids()))
            self.assertEqual(set(loaded_neuron_dbs[v].neuron_data.keys()),
                             set(self.neuron_dbs[v].neuron_data.keys()))
            for rid, nd in loaded_neuron_dbs[v].neuron_data.items():
                self.assertEqual(nd, self.neuron_dbs[v].get_neuron_data(rid))

        # check the same for data factory
        neuron_data_factory = NeuronDataFactory(data_root_path=TEST_DATA_ROOT_PATH)
        for v in versions:
            self.assertEqual(set(neuron_data_factory.get(v).neuron_data.keys()),
                             set(neuron_data_factory.get(v).search_index.all_doc_ids()))
            self.assertEqual(set(neuron_data_factory.get(v).neuron_data.keys()),
                             set(self.neuron_dbs[v].neuron_data.keys()))
            for rid, nd in neuron_data_factory.get(v).neuron_data.items():
                self.assertEqual(nd, self.neuron_dbs[v].get_neuron_data(rid))
