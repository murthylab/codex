import os

import stats_utils
from unittest import TestCase

from local_data_loader import unpickle_neuron_db, DATA_ROOT_PATH

# for IDE test
TEST_DATA_ROOT_PATH = os.getcwd().replace('tests', DATA_ROOT_PATH)
# for pytest
if not TEST_DATA_ROOT_PATH.endswith(DATA_ROOT_PATH):
    TEST_DATA_ROOT_PATH += f'/{DATA_ROOT_PATH}'


class Test(TestCase):
    def test_format_for_display(self):
        self.assertEqual({
            'd1': {'a': '6,555'},
            'd2': {'b': None, 'c': 0.55}
        }, stats_utils._format_for_display({
            'd1': {'a': 6555},
            'd2': {'b': None, 'c': 0.55}
        }))

    def test_compile_data(self):
        # empty data
        caption, data_stats, data_charts = stats_utils.compile_data(
            data={}, search_query='test_query_1', case_sensitive=0, match_words=1, data_version='447')
        self.assertEqual("Stats for search query: 'test_query_1', match words, data version: 447", caption)
        self.assertEqual({'': {'- Classified': '0', '- Labeled': '0', 'Cells': '0'}}, data_stats)
        self.assertEqual({}, data_charts)

        # actual data
        neuron_db = unpickle_neuron_db('447', data_root_path=TEST_DATA_ROOT_PATH)
        caption, data_stats, data_charts = stats_utils.compile_data(
            data=list(neuron_db.neuron_data.values()), search_query='test_query_2', case_sensitive=1, match_words=0,
            data_version='447')
        self.assertEqual("Stats for search query: 'test_query_2', case sensitive, data version: 447", caption)
        self.assertEqual({'': {'- Classified': '18,486', '- Labeled': '35,285', 'Cells': '68,375'},
                          'Top Classes': {'ALRN': '1,916',
                                          'LN': '1,381',
                                          'descending': '3,236',
                                          'fru*': '1,636',
                                          'optic_lobe_input': '4,690'},
                          'Top Labels': {'Kenyon_Cell_L': '1,785',
                                         'Kenyon_Cell_L*': '1,611',
                                         'Putative AN; Part of comprehensive neck connective tracing; contact Connectomics Group Cambridge for more detailed information on descending/ascending neurons': '2,130',
                                         'putative fru*': '1,637',
                                         'sensory*': '1,643'}}, data_stats)
        self.assertEqual({'In regions (L-eft, C-enter, R-ight, 0-none)': [['Input regions', 'Count'],
                                                                          ['0', 3325],
                                                                          ['C', 5218],
                                                                          ['CR', 2262],
                                                                          ['L', 26534],
                                                                          ['LC', 2427],
                                                                          ['LCR', 1571],
                                                                          ['LR', 4888],
                                                                          ['R', 20408],
                                                                          ['Unknown', 1742]],
                          'Neurotransmitter Types': [['Type', 'Count'],
                                                     ['ACH', 39110],
                                                     ['DA', 5722],
                                                     ['GABA', 9888],
                                                     ['GLUT', 11865],
                                                     ['OCT', 121],
                                                     ['SER', 1415],
                                                     ['Unknown', 254]],
                          'Num. Assigned Neuron Classes': [['Num Classes', 'Count'],
                                                           ['0', 49889],
                                                           ['1', 13771],
                                                           ['2', 3817],
                                                           ['3', 781],
                                                           ['4', 82],
                                                           ['5', 24],
                                                           ['6', 11]],
                          'Out regions (L-eft, C-enter, R-ight, 0-none)': [['Output regions', 'Count'],
                                                                           ['0', 2331],
                                                                           ['C', 6286],
                                                                           ['CR', 1811],
                                                                           ['L', 26052],
                                                                           ['LC', 1915],
                                                                           ['LCR', 1213],
                                                                           ['LR', 6862],
                                                                           ['R', 20163],
                                                                           ['Unknown', 1742]]}, data_charts)
