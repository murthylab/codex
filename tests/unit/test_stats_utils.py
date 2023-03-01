from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
from src.utils import stats
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    def test_format_for_display(self):
        self.assertEqual(
            {"d1": {"a": "6,555"}, "d2": {"b": None, "c": 0.55}},
            stats.format_for_display({"d1": {"a": 6555}, "d2": {"b": None, "c": 0.55}}),
        )

    def test_compile_data(self):
        # empty data
        caption, data_stats, data_charts = stats.compile_data(
            neuron_data={},
            label_data={},
            search_query="test_query_1",
            case_sensitive=0,
            match_words=1,
            data_version=DEFAULT_DATA_SNAPSHOT_VERSION,
        )
        self.assertEqual(
            f"Stats for search query: 'test_query_1', match words, data version: {DEFAULT_DATA_SNAPSHOT_VERSION}",
            caption,
        )
        self.assertEqual(
            {
                "": {
                    "- Avg. area": "NA",
                    "- Avg. length": "NA",
                    "- Avg. volume": "NA",
                    "- Classified": "0",
                    "- With label(s)": "0",
                    "Cells": "0",
                }
            },
            data_stats,
        )
        self.assertEqual({}, data_charts)

        # actual data
        neuron_db = unpickle_neuron_db(
            DEFAULT_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )
        caption, data_stats, data_charts = stats.compile_data(
            neuron_data=list(neuron_db.neuron_data.values()),
            label_data=list(neuron_db.label_data.values()),
            search_query="test_query_2",
            case_sensitive=1,
            match_words=0,
            data_version=DEFAULT_DATA_SNAPSHOT_VERSION,
        )
        self.assertEqual(
            f"Stats for search query: 'test_query_2', case sensitive, data version: {DEFAULT_DATA_SNAPSHOT_VERSION}",
            caption,
        )
        self.assertEqual(
            {"", "Top Labels"},
            set(data_stats.keys()),
        )
        self.assertEqual(
            [
                # TODO: revive once cell type data is available "Cell Type",
                "Class",
                "Flow",
                "Nerve",
                "Neurotransmitter Types",
                "Soma Side",
                "Sub Class",
                "Super Class",
                "Top Input Regions",
                "Top Output Regions",
            ],
            sorted(data_charts.keys()),
        )
        self.assertEqual(
            [5, 5, 5, 5, 5, 5, 5, 5, 5],
            [len(data_charts[k]) for k in sorted(data_charts.keys())],
        )
