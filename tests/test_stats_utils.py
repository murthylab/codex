import os

from src.utils import stats
from unittest import TestCase

from src.data.local_data_loader import unpickle_neuron_db, DATA_ROOT_PATH

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
        }, stats._format_for_display({
            'd1': {'a': 6555},
            'd2': {'b': None, 'c': 0.55}
        }))

    def test_compile_data(self):
        # empty data
        caption, data_stats, data_charts = stats.compile_data(
            data={}, search_query='test_query_1', case_sensitive=0, match_words=1, data_version='447')
        self.assertEqual("Stats for search query: 'test_query_1', match words, data version: 447", caption)
        self.assertEqual({'': {'- Classified': '0', '- Annotated': '0', 'Cells': '0'}}, data_stats)
        self.assertEqual({}, data_charts)

        # actual data
        neuron_db = unpickle_neuron_db('447', data_root_path=TEST_DATA_ROOT_PATH)
        caption, data_stats, data_charts = stats.compile_data(
            data=list(neuron_db.neuron_data.values()), search_query='test_query_2', case_sensitive=1, match_words=0,
            data_version='447')
        self.assertEqual("Stats for search query: 'test_query_2', case sensitive, data version: 447", caption)
        self.assertEqual({'': {'- Classified': '68,375', '- Annotated': '33,009', 'Cells': '68,375'},
                          'Top Classes': {'Ascending': '2,224',
                                          'Central Brain': '32,797',
                                          'Optic Lobe': '19,815',
                                          'Sensory': '4,752',
                                          'Visual Projection': '7,456'},
                          'Top Annotations': {'Kenyon_Cell_L': '2,586',
                                              'Kenyon_Cell_L*': '1,242',
                                              'Putative AN; Part of comprehensive neck connective tracing; contact Connectomics Group Cambridge for more detailed information on descending/ascending neurons': '2,227',
                                              'antennal lobe olfactory and thermo/hygrosensory receptor neuron (ALRN)': '1,916',
                                              'putative fru': '1,130'}}, data_stats)
        self.assertEqual({'Input/Output hemispheres': [['Output regions', 'Count'],
                                                       ['Left/Left', 24163],
                                                       ['Left/Mid', 30],
                                                       ['Left/Mix', 1361],
                                                       ['Left/None', 839],
                                                       ['Left/Right', 141],
                                                       ['Mid/Left', 77],
                                                       ['Mid/Mid', 4116],
                                                       ['Mid/Mix', 427],
                                                       ['Mid/None', 515],
                                                       ['Mid/Right', 83],
                                                       ['Mix/Left', 903],
                                                       ['Mix/Mid', 1133],
                                                       ['Mix/Mix', 7993],
                                                       ['Mix/None', 240],
                                                       ['Mix/Right', 879],
                                                       ['None/Left', 765],
                                                       ['None/Mid', 984],
                                                       ['None/Mix', 706],
                                                       ['None/Right', 870],
                                                       ['Right/Left', 144],
                                                       ['Right/Mid', 23],
                                                       ['Right/Mix', 1314],
                                                       ['Right/None', 737],
                                                       ['Right/Right', 18190],
                                                       ['Unknown', 1742]],
                          'Neurotransmitter Types': [['Type', 'Count'],
                                                     ['ACH', 39110],
                                                     ['DA', 5722],
                                                     ['GABA', 9888],
                                                     ['GLUT', 11865],
                                                     ['OCT', 121],
                                                     ['SER', 1415],
                                                     ['Unknown', 254]],
                          'Num. Assigned Neuron Classes': [['Num Classes', 'Count'], ['1', 68375]]}, data_charts)
