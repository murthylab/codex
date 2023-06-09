from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import TESTING_DATA_SNAPSHOT_VERSION
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

    def test_clean_and_reduce_labels(self):
        for nd in self.neuron_db.neuron_data.values():
            for lbl in nd["label"]:
                self.assertFalse(lbl.lower().startswith("putative"), lbl)
