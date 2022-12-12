from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION
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
            data_version=LATEST_DATA_SNAPSHOT_VERSION,
        )
        self.assertEqual(
            f"Stats for search query: 'test_query_1', match words, data version: {LATEST_DATA_SNAPSHOT_VERSION}",
            caption,
        )
        self.assertEqual(
            {"": {"- Classified": "0", "- Labeled": "0", "Cells": "0"}}, data_stats
        )
        self.assertEqual({}, data_charts)

        # actual data
        neuron_db = unpickle_neuron_db(
            LATEST_DATA_SNAPSHOT_VERSION, data_root_path=TEST_DATA_ROOT_PATH
        )
        caption, data_stats, data_charts = stats.compile_data(
            neuron_data=list(neuron_db.neuron_data.values()),
            label_data=list(neuron_db.label_data.values()),
            search_query="test_query_2",
            case_sensitive=1,
            match_words=0,
            data_version=LATEST_DATA_SNAPSHOT_VERSION,
        )
        self.assertEqual(
            f"Stats for search query: 'test_query_2', case sensitive, data version: {LATEST_DATA_SNAPSHOT_VERSION}",
            caption,
        )
        self.assertEqual(
            {
                "": 3,
                "Top Labelers (all time)": 5,
                "Top Labelers (last 500)": 5,
                "Top Labels": 5,
            },
            {k: len(v) for k, v in data_stats.items()},
        )
        self.assertEqual(
            [
                "Classes",
                "Neurotransmitter types",
                "Num cells with inputs/outputs in hemispheres",
                "Top input regions",
                "Top output regions",
            ],
            sorted(data_charts.keys()),
        )
        self.assertEqual(
            [5, 5, 5, 5, 5], [len(data_charts[k]) for k in sorted(data_charts.keys())]
        )
