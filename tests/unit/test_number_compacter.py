from unittest import TestCase

from codex.utils.number_compacter import number_to_compact_repr, compact_repr_to_number

TEST_CASES = {
    0: "0",
    1: "1",
    10: "A",
    36: "a",
    62: "10",
    3843: "zz",
    238327: "zzz",
    14776335: "zzzz",
}
TEST_CASES.update({-k: f"-{v}" for k, v in TEST_CASES.items() if k})


class CompacterTest(TestCase):
    def test_number_to_compact_repr(self):
        for k, v in TEST_CASES.items():
            self.assertEqual(v, number_to_compact_repr(k))

    def test_compact_repr_to_number(self):
        for k, v in TEST_CASES.items():
            self.assertEqual(k, compact_repr_to_number(v))

    def test_equivalence(self):
        for i in range(30):
            num = pow(3, i)
            self.assertEqual(num, compact_repr_to_number(number_to_compact_repr(num)))
            self.assertEqual(-num, compact_repr_to_number(number_to_compact_repr(-num)))
