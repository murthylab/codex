from unittest import TestCase
from src.data.neurotransmitters import lookup_nt_type
from src.etl.compile_data import NT_TYPES


class NtTest(TestCase):
    def test_lookup_nt_type(self):
        for nt in NT_TYPES:
            self.assertEqual(nt.upper(), lookup_nt_type(nt))
            self.assertEqual(nt.upper(), lookup_nt_type(nt.lower()))
        self.assertEqual('bogus', lookup_nt_type('bogus'))
        self.assertEqual('DA', lookup_nt_type('DOPA'))
        self.assertEqual('DA', lookup_nt_type('Dopamine'))
        self.assertEqual('DA', lookup_nt_type('dopamine'))