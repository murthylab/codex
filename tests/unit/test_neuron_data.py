from unittest import TestCase

from src.data.brain_regions import REGIONS
from src.data.neuron_data import *
from src.data.local_data_loader import unpickle_all_neuron_db_versions

# for IDE test
from src.data.versions import DATA_SNAPSHOT_VERSIONS, LATEST_DATA_SNAPSHOT_VERSION
from tests import TEST_DATA_ROOT_PATH


class NeuronDataTest(TestCase):

    def setUp(self):
        versions = DATA_SNAPSHOT_VERSIONS
        self.neuron_dbs = unpickle_all_neuron_db_versions(data_root_path=TEST_DATA_ROOT_PATH)
        # check that all versions loaded
        for v in versions:
            self.assertIsNotNone(self.neuron_dbs[v])
            self.assertEqual(set(self.neuron_dbs[v].neuron_data.keys()),
                             set(self.neuron_dbs[v].search_index.all_doc_ids()))
        self.neuron_db = self.neuron_dbs[LATEST_DATA_SNAPSHOT_VERSION]

    def test_index_data(self):
        assert 60000 < len(self.neuron_db.neuron_data)

        def check_min_values_present(attrib, lower_bound):
            num_present = len([1 for nd in self.neuron_db.neuron_data.values() if nd[attrib]])
            self.assertGreaterEqual(num_present, lower_bound)

        check_min_values_present('name', 66812)
        check_min_values_present('nt_type', 68121)
        check_min_values_present('hemisphere_fingerprint', 66633)
        check_min_values_present('classes', 10782)
        check_min_values_present('similar_root_ids', 66633)
        check_min_values_present('similar_root_id_scores', 66633)
        check_min_values_present('symmetrical_root_ids', 66633)
        check_min_values_present('symmetrical_root_id_scores', 66633)
        check_min_values_present('input_neuropils', 63308)
        check_min_values_present('output_neuropils', 64302)
        check_min_values_present('supervoxel_id', 22155)
        check_min_values_present('tag', 30026)
        check_min_values_present('inherited_tag_root_id', 2871)
        check_min_values_present('inherited_tag_score', 2871)
        check_min_values_present('user_id', 23155)
        check_min_values_present('position', 23155)

    def test_annotations(self):
        neurons_with_tags = [n for n in self.neuron_db.neuron_data.values() if n['tag']]
        self.assertGreater(len(neurons_with_tags), 25000)

        neurons_with_annotations = [n for n in self.neuron_db.neuron_data.values() if n['annotations']]
        self.assertEqual(len(neurons_with_tags), len(neurons_with_annotations))

        neurons_with_inherited_labels = [n for n in neurons_with_annotations if "*" in n['annotations']]
        self.assertGreater(len(neurons_with_inherited_labels), 2800)

        for n in self.neuron_db.neuron_data.values():
            for col in [
                'classes', 'similar_root_ids', 'symmetrical_root_ids', 'input_neuropils', 'output_neuropils',
                'supervoxel_id', 'tag', 'user_id', 'position'
            ]:
                self.assertEqual(len(set(n[col])), len(n[col]))

        # closest term search
        self.assertEqual(self.neuron_db.closest_token('blobe', case_sensitive=False), 'lobe')
        self.assertEqual(self.neuron_db.closest_token('blobe', case_sensitive=True), 'lobe')
        self.assertEqual(self.neuron_db.closest_token('BLOBE', case_sensitive=True), 'LB3')

        self.assertEqual(self.neuron_db.closest_token_from_inherited_tags('blobe', case_sensitive=False), 'lobe')

    def test_search(self):
        # search results
        self.assertGreater(len(self.neuron_db.search('da')), 6000)
        self.assertEqual(len(self.neuron_db.search('dadadeadbeef')), 0)

        # structured search
        gaba_rids = self.neuron_db.search('nt == gaba')
        self.assertGreater(len(gaba_rids), 1000)
        self.assertEqual(len(self.neuron_db.neuron_data), len(gaba_rids) + len(self.neuron_db.search('nt != gaba')))
        for rid in gaba_rids:
            self.assertEqual('GABA', self.neuron_db.get_neuron_data(rid)['nt_type'])

        ach_rids = self.neuron_db.search('nt == ACH')
        self.assertGreater(len(ach_rids), 1000)
        self.assertEqual(len(self.neuron_db.neuron_data), len(ach_rids) + len(self.neuron_db.search('nt != ACH')))
        for rid in ach_rids:
            self.assertEqual('ACH', self.neuron_db.get_neuron_data(rid)['nt_type'])

        gaba_and_ach_rids = self.neuron_db.search('nt == ACH && nt == gaba')
        self.assertEqual(0, len(gaba_and_ach_rids))

        gaba_or_ach_rids = self.neuron_db.search('nt == ACH || nt == gaba')
        self.assertEqual(len(ach_rids) + len(gaba_rids), len(gaba_or_ach_rids))

        ids_with_name = self.neuron_db.search('{has} name')
        ids_without_name = self.neuron_db.search('{not} name')
        self.assertEqual(len(self.neuron_db.neuron_data), len(ids_with_name))
        self.assertEqual(0, len(ids_without_name))

        ids_with_class = self.neuron_db.search('$$ class')
        ids_without_class = self.neuron_db.search('!$ class')
        self.assertEqual(len(self.neuron_db.neuron_data), len(ids_with_class) + len(ids_without_class))
        self.assertEqual(set(ids_with_class),
                         set([nd['root_id'] for nd in self.neuron_db.neuron_data.values() if nd['classes']]))

        hundred_root_ids = list(self.neuron_db.neuron_data.keys())[:100]
        root_id_search_explicit = self.neuron_db.search(' || '.join([f'id == {rid}' for rid in hundred_root_ids]))
        self.assertEqual(set(root_id_search_explicit), set(hundred_root_ids))
        root_id_search_membership = self.neuron_db.search(
            f"id << {','.join([str(rid) for rid in hundred_root_ids])}")
        self.assertEqual(set(root_id_search_explicit), set(root_id_search_membership))
        self.assertEqual(len(self.neuron_db.neuron_data), len(hundred_root_ids) + len(
            self.neuron_db.search(' && '.join([f'id != {rid}' for rid in hundred_root_ids]))))
        self.assertEqual(len(self.neuron_db.neuron_data), len(hundred_root_ids) + len(
            self.neuron_db.search(f"id !< {','.join([str(rid) for rid in hundred_root_ids])}")))

        self.assertLess(len(self.neuron_db.search('gaba && nt != gaba')), 700)

        self.assertEqual(2, len(self.neuron_db.search('720575940624284903 720575940625504714')))
        self.assertEqual(2, len(self.neuron_db.search('720575940624284903,720575940625504714')))
        self.assertEqual(2, len(self.neuron_db.search('720575940624284903, 720575940625504714')))

    def test_downstream_upstream_queries(self):
        downstream = self.neuron_db.search('{downstream} 720575940629495808')
        self.assertEqual(55, len(downstream))

        upstream = self.neuron_db.search('{upstream} 720575940629495808')
        self.assertEqual(18, len(upstream))

    def test_structured_query_parsing(self):
        # free form
        self.assertEqual(NeuronDB._parse_search_query('foo'), (None, ['foo'], []))
        self.assertEqual(NeuronDB._parse_search_query('foo bar'), (None, ['foo bar'], []))

        # structured
        self.assertEqual(NeuronDB._parse_search_query('foo {equal} bar'),
                         (None, [], [{'op': '{equal}', 'lhs': 'foo', 'rhs': 'bar'}]))
        self.assertEqual(NeuronDB._parse_search_query('foo == bar'),
                         (None, [], [{'op': '{equal}', 'lhs': 'foo', 'rhs': 'bar'}]))

        self.assertEqual(NeuronDB._parse_search_query('foo {not equal} bar'),
                         (None, [], [{'op': '{not equal}', 'lhs': 'foo', 'rhs': 'bar'}]))
        self.assertEqual(NeuronDB._parse_search_query('foo != bar'),
                         (None, [], [{'op': '{not equal}', 'lhs': 'foo', 'rhs': 'bar'}]))
        self.assertEqual(NeuronDB._parse_search_query(' {has} bar'),
                         (None, [], [{'op': '{has}', 'rhs': 'bar'}]))
        self.assertEqual(NeuronDB._parse_search_query(' !$ bar'),
                         (None, [], [{'op': '{not}', 'rhs': 'bar'}]))

        # false cases
        self.assertEqual(NeuronDB._parse_search_query('== foo == bar'),
                         (None, ['== foo == bar'], []))
        self.assertEqual(NeuronDB._parse_search_query('=='),
                         (None, ['=='], []))
        self.assertEqual(NeuronDB._parse_search_query('foo == !='),
                         (None, ['foo == !='], []))
        self.assertEqual(NeuronDB._parse_search_query('foo {has} bar'),
                         (None, ['foo {has} bar'], []))
        self.assertEqual(NeuronDB._parse_search_query(' {!$} bar'),
                         (None, [' {!$} bar'], []))

        # combos
        self.assertEqual(NeuronDB._parse_search_query('foo != bar && other'),
                         ('{and}', ['other'], [{'op': '{not equal}', 'lhs': 'foo', 'rhs': 'bar'}]))
        self.assertEqual(NeuronDB._parse_search_query('other || foo {not equal} bar'),
                         ('{or}', ['other'], [{'op': '{not equal}', 'lhs': 'foo', 'rhs': 'bar'}]))

        # and/or mix not allowed
        self.assertEqual(NeuronDB._parse_search_query('other {or} foo != bar && third'),
                         (None, ['other {or} foo != bar && third'], []))

        # another false case
        self.assertEqual(NeuronDB._parse_search_query('|| other || foo != bar'),
                         (None, ['|| other || foo != bar'], []))

        # structured search should not be triggered if the query is wrapped in quotes
        self.assertEqual(NeuronDB._parse_search_query('"foo == bar"'), (None, ['"foo == bar"'], []))

    def test_structured_query_operators(self):
        op_keys = set(OPERATOR_METADATA.keys())
        self.assertTrue(all(op_keys))
        self.assertEqual(len(op_keys), len(OPERATOR_METADATA))
        self.assertEqual(len(SEARCH_CHAINING_OPERATORS + SEARCH_TERM_BINARY_OPERATORS + SEARCH_TERM_UNARY_OPERATORS),
                         len(OPERATOR_METADATA))

        op_shorthands = set([p[0] for p in OPERATOR_METADATA.values()])
        self.assertTrue(all(op_shorthands))
        self.assertEqual(len(op_shorthands), len(OPERATOR_METADATA))
        self.assertTrue(op_keys.isdisjoint(op_shorthands))

        # Check descriptions are present and unique
        descs = set([p[1] for p in OPERATOR_METADATA.values()])
        self.assertTrue(all(descs))
        self.assertEqual(len(descs), len(OPERATOR_METADATA))

        # check that operators or their shorthands are not substrings of each other
        all_ops = op_shorthands.union(op_keys)
        for op1 in all_ops:
            for op2 in all_ops:
                self.assertTrue(op1 == op2 or op1 not in op2)

    def test_neuropils(self):
        expected_list = [
            'AL_L', 'AL_R', 'AME_L', 'AME_R', 'AMMC_L', 'AMMC_R', 'AOTU_L', 'AOTU_R', 'ATL_L', 'ATL_R', 'AVLP_L',
            'AVLP_R', 'BU_L', 'BU_R', 'CAN_L', 'CAN_R', 'CRE_L', 'CRE_R', 'EB', 'EPA_L', 'EPA_R', 'FB', 'FLA_L',
            'FLA_R', 'GA_L', 'GA_R', 'GNG', 'GOR_L', 'GOR_R', 'IB_L', 'IB_R', 'ICL_L', 'ICL_R', 'IPS_L', 'IPS_R',
            'LAL_L', 'LAL_R', 'LH_L', 'LH_R', 'LOP_L', 'LOP_R', 'LO_L', 'LO_R', 'MB_CA_L', 'MB_CA_R', 'MB_ML_L',
            'MB_ML_R', 'MB_PED_L', 'MB_PED_R', 'MB_VL_L', 'MB_VL_R', 'ME_L', 'ME_R', 'NO', 'PB', 'PLP_L', 'PLP_R',
            'PRW', 'PVLP_L', 'PVLP_R', 'SAD', 'SCL_L', 'SCL_R', 'SIP_L', 'SIP_R', 'SLP_L', 'SLP_R', 'SMP_L', 'SMP_R',
            'SPS_L', 'SPS_R', 'VES_L', 'VES_R', 'WED_L', 'WED_R']
        self.assertEqual(set(expected_list), set(REGIONS.keys()))
        self.assertEqual(expected_list, self.neuron_db.neuropils())

    def test_classes(self):
        expected_list = ['Ascending',
                         'Central Brain',
                         'Descending',
                         'Optic Lobe',
                         'Sensory',
                         'Visual Projection']
        self.assertEqual(expected_list, self.neuron_db.classes())

    def test_hemisphere_fingerprint(self):
        self.assertEqual('Left/Right', NeuronDB.hemisphere_fingerprint(
            ['AMMC_L', 'IPS_L'], ['IPS_R']))
        self.assertEqual('Mix/Mix', NeuronDB.hemisphere_fingerprint(
            ['AMMC_L', 'GNG', 'IPS_L', 'IPS_R', 'SAD'], ['GNG', 'IPS_R', 'SAD']))
        self.assertEqual('None/Mix', NeuronDB.hemisphere_fingerprint(
            [], ['GNG', 'IPS_R', 'SAD']))
        self.assertEqual('', NeuronDB.hemisphere_fingerprint(
            [], []))

    def test_get_neuron_data(self):
        self.assertGreater(len(self.neuron_db.get_neuron_data(root_id=720575940624056624)), 5)
        self.assertGreater(len(self.neuron_db.get_neuron_data(root_id='720575940624056624')), 5)

    def test_augmentation_loading(self):
        self.assertGreater(len(self.neuron_db.search_in_neurons_with_inherited_labels('')), 2800)
        self.assertGreater(len(self.neuron_db.search_in_neurons_with_inherited_labels('da')), 500)
