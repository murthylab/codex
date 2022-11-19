from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db
from src.utils import stats
from tests import TEST_DATA_ROOT_PATH


class Test(TestCase):
    def test_format_for_display(self):
        self.assertEqual(
            {"d1": {"a": "6,555"}, "d2": {"b": None, "c": 0.55}},
            stats._format_for_display(
                {"d1": {"a": 6555}, "d2": {"b": None, "c": 0.55}}
            ),
        )

    def test_compile_data(self):
        # empty data
        caption, data_stats, data_charts = stats.compile_data(
            data={},
            search_query="test_query_1",
            case_sensitive=0,
            match_words=1,
            data_version="447",
        )
        self.assertEqual(
            "Stats for search query: 'test_query_1', match words, data version: 447",
            caption,
        )
        self.assertEqual(
            {"": {"- Classified": "0", "- Annotated": "0", "Cells": "0"}}, data_stats
        )
        self.assertEqual({}, data_charts)

        # actual data
        neuron_db = unpickle_neuron_db("447", data_root_path=TEST_DATA_ROOT_PATH)
        caption, data_stats, data_charts = stats.compile_data(
            data=list(neuron_db.neuron_data.values()),
            search_query="test_query_2",
            case_sensitive=1,
            match_words=0,
            data_version="447",
        )
        self.assertEqual(
            "Stats for search query: 'test_query_2', case sensitive, data version: 447",
            caption,
        )
        self.assertEqual(
            {
                "": {
                    "- Classified": "68,375",
                    "- Annotated": "33,009",
                    "Cells": "68,375",
                },
                "Top Classes": {
                    "Ascending": "2,224",
                    "Central Brain": "32,797",
                    "Optic Lobe": "19,815",
                    "Sensory": "4,752",
                    "Visual Projection": "7,456",
                },
                "Top Annotations": {
                    "Kenyon_Cell_L": "2,586",
                    "Kenyon_Cell_L*": "1,242",
                    "Putative AN": "2,227",
                    "antennal lobe olfactory and thermo/hygrosensory receptor neuron (ALRN)": "1,916",
                    "putative fru": "1,130",
                },
            },
            data_stats,
        )
        self.assertEqual(
            [
                "Num cells with inputs/outputs in hemispheres",
                "Num cells with neurotransmitter types",
                "Top input regions",
                "Top output regions",
            ],
            sorted(data_charts.keys()),
        )
        self.assertEqual(
            [5, 5, 5, 5], [len(data_charts[k]) for k in sorted(data_charts.keys())]
        )
