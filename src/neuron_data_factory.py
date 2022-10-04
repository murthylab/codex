from src.local_data_loader import available_data_versions, latest_data_version, unpickle_neuron_db, DATA_ROOT_PATH

class NeuronDataFactory(object):
    def __init__(self, data_root_path=DATA_ROOT_PATH, preload_latest=True):
        self._data_root_path = data_root_path
        self._available_versions = available_data_versions(data_root_path=self._data_root_path)
        self._latest_version = latest_data_version(data_root_path=self._data_root_path)
        self._version_to_data = {}
        if preload_latest:
            self.get()

    def get(self, version=None):
        version = version or self._latest_version
        if version not in self._version_to_data:
            self._version_to_data[version] = unpickle_neuron_db(version, data_root_path=self._data_root_path)
        return self._version_to_data[version]

    def latest_data_version(self):
        return self._latest_version

    def available_versions(self):
        return list(self._available_versions)

    def loaded_versions(self):
        return list(self._version_to_data.keys())
