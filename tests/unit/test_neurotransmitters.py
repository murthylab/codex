from unittest import TestCase
from src.data.neurotransmitters import lookup_nt_type, NEURO_TRANSMITTER_NAMES


class NtTest(TestCase):
    def test_lookup_nt_type(self):
        for nt in NEURO_TRANSMITTER_NAMES.keys():
            self.assertEqual(nt, lookup_nt_type(nt.lower()))
            self.assertEqual(nt, lookup_nt_type(nt.lower()))
        self.assertEqual("bogus", lookup_nt_type("bogus"))
        self.assertEqual("DA", lookup_nt_type("DOPA"))
        self.assertEqual("DA", lookup_nt_type("Dopamine"))
        self.assertEqual("DA", lookup_nt_type("dopamine"))
