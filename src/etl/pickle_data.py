import sys

from src.data.local_data_loader import load_and_pickle_neuron_db_versions
from src.data.versions import DATA_SNAPSHOT_VERSIONS, DEFAULT_DATA_SNAPSHOT_VERSION

if __name__ == "__main__":
    versions_ = DATA_SNAPSHOT_VERSIONS
    if len(sys.argv) > 1:
        if len(sys.argv) == 2 and sys.argv[1] == "-default_version_only":
            versions_ = [DEFAULT_DATA_SNAPSHOT_VERSION]
        else:
            print(f"Unrecognized args: {sys.argv[1:]}")
            exit(1)

    load_and_pickle_neuron_db_versions(versions=versions_)
