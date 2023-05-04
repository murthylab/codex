from unittest import TestCase
from unittest.mock import patch

from src.data.local_data_loader import (
    unpickle_neuron_db,
)
from src.data.versions import (
    TESTING_DATA_SNAPSHOT_VERSION,
)
from src.service.network import compile_network_html
from tests import TEST_DATA_ROOT_PATH


class ConnectivityTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = unpickle_neuron_db(
            version=TESTING_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )

    def test_full_network_generation(self):
        query = "*"

        rids = self.neuron_db.search(query)
        self.assertEqual(set(rids), set(self.neuron_db.neuron_data.keys()))

        contable = self.neuron_db.connections(
            ids=rids,
            nt_type=None,
            induced=True,
            min_syn_count=None,
        )
        self.assertEqual(3794615, len(contable))

        with patch("src.utils.graph_vis.render_template") as mocked:
            network_html = compile_network_html(
                center_ids=rids,
                contable=contable,
                neuron_db=self.neuron_db,
                show_regions=False,
                group_by_attribute_name="side",
                split_groups_by_side=False,
                connections_cap=50,
                hide_weights=False,
                log_request=False,
            )
            self.assertEqual(1, mocked.call_count)
            self.assertTrue("render_template" in str(network_html))

            with patch("src.utils.graph_vis.url_for") as mocked_url_for:
                network_html = compile_network_html(
                    center_ids=rids,
                    contable=contable,
                    neuron_db=self.neuron_db,
                    show_regions=False,
                    group_by_attribute_name=None,
                    split_groups_by_side=False,
                    connections_cap=50,
                    hide_weights=False,
                    log_request=False,
                )
                self.assertEqual(138, mocked_url_for.call_count)
                self.assertTrue("render_template" in str(network_html))
