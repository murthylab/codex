from src.data.local_data_loader import unpickle_neuron_db, DATA_ROOT_PATH
from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION
from src.utils.logging import log

# Singleton
_instance = None


class NeuronDataFactory(object):
    def __init__(self, data_root_path=DATA_ROOT_PATH, preload_latest=True):
        log(f"Initializing NeuronDataFactory with {data_root_path=}...")
        # enforce singleton for app (allow for tests)
        if data_root_path == DATA_ROOT_PATH:
            global _instance
            assert _instance is None
            _instance = self

        self._data_root_path = data_root_path
        self._version_to_data = {}
        if preload_latest:
            log("App Initialization: preloading latest version")
            self.get()

    def get(self, version=None):
        version = version or DEFAULT_DATA_SNAPSHOT_VERSION
        if version not in self._version_to_data:
            self._version_to_data[version] = unpickle_neuron_db(
                version, data_root_path=self._data_root_path
            )
        return self._version_to_data[version]

    def loaded_versions(self):
        return list(self._version_to_data.keys())

    @classmethod
    def instance(cls):
        global _instance
        if _instance is None:
            _instance = NeuronDataFactory()
        return _instance
