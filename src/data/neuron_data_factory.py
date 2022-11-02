from src.data.local_data_loader import unpickle_neuron_db, DATA_ROOT_PATH
from src.data.versions import DATA_SNAPSHOT_VERSIONS, LATEST_DATA_SNAPSHOT_VERSION


class NeuronDataFactory(object):
    def __init__(self, data_root_path=DATA_ROOT_PATH, preload_latest=True):
        self._data_root_path = data_root_path
        self._available_versions = DATA_SNAPSHOT_VERSIONS
        self._version_to_data = {}
        if preload_latest:
            self.get()

    def get(self, version=None):
        version = version or LATEST_DATA_SNAPSHOT_VERSION
        if version not in self._version_to_data:
            self._version_to_data[version] = unpickle_neuron_db(
                version, data_root_path=self._data_root_path
            )
        return self._version_to_data[version]

    def available_versions(self):
        return list(self._available_versions)

    def loaded_versions(self):
        return list(self._version_to_data.keys())
