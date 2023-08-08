import os
import re

# for IDE test
from src.configuration import APP_ENVIRONMENT
from src.data.local_data_loader import DATA_ROOT_PATH
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.versions import TESTING_DATA_SNAPSHOT_VERSION

TEST_DATA_ROOT_PATH = re.sub(r"tests.*", DATA_ROOT_PATH, os.getcwd())
# for pytest
if not TEST_DATA_ROOT_PATH.endswith(DATA_ROOT_PATH):
    TEST_DATA_ROOT_PATH += f"/{DATA_ROOT_PATH}"

_TEST_NEURON_DATA_FACTORY = NeuronDataFactory(data_root_path=TEST_DATA_ROOT_PATH)


def get_testing_neuron_db(version=TESTING_DATA_SNAPSHOT_VERSION):
    return _TEST_NEURON_DATA_FACTORY.get(version=version)


assert APP_ENVIRONMENT == "DEV"

# Helper for inspecting cell lists in dev server
def log_dev_url_for_root_ids(caption, root_ids, prod=False):
    assert len(root_ids) <= 100
    burl = "https://codex.flywire.ai" if prod else "http://localhost:5000"
    print(
        f"{caption}: {burl}/app/search?filter_string="
        f"{'%2C+'.join([str(rid) for rid in root_ids])}&page_size=100"
    )
