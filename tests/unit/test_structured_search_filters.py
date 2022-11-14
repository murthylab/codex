from collections import Iterable
from unittest import TestCase

from src.data.structured_search_filters import (
    _make_predicate,
    OPERATOR_METADATA,
    parse_search_query,
    SEARCH_TERM_UNARY_OPERATORS,
    SEARCH_CHAINING_OPERATORS,
    SEARCH_TERM_BINARY_OPERATORS,
)


class Test(TestCase):
    def test_make_predicate(self):
        for op, meta in OPERATOR_METADATA.items():

            def some_value(restricted_values):
                if restricted_values is None:
                    return "123"
                elif isinstance(restricted_values, Iterable):
                    return restricted_values[0]
                else:
                    return ""

            st = {"lhs": some_value(meta[3]), "rhs": some_value(meta[4]), "op": op}
            self.assertIsNotNone(_make_predicate(st, {}, {}))

    def test_structured_query_parsing(self):
        # free form
        self.assertEqual(parse_search_query("foo"), (None, ["foo"], []))
        self.assertEqual(parse_search_query("foo bar"), (None, ["foo bar"], []))

        # structured
        self.assertEqual(
            parse_search_query("foo {equal} bar"),
            (None, [], [{"op": "{equal}", "lhs": "foo", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query("foo == bar"),
            (None, [], [{"op": "{equal}", "lhs": "foo", "rhs": "bar"}]),
        )

        self.assertEqual(
            parse_search_query("foo {not equal} bar"),
            (None, [], [{"op": "{not equal}", "lhs": "foo", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query("foo != bar"),
            (None, [], [{"op": "{not equal}", "lhs": "foo", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query(" {has} bar"),
            (None, [], [{"op": "{has}", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query(" !$ bar"),
            (None, [], [{"op": "{not}", "rhs": "bar"}]),
        )

        # false cases
        with self.assertRaises(ValueError):
            parse_search_query("== foo == bar")
        with self.assertRaises(ValueError):
            parse_search_query("==")
        with self.assertRaises(ValueError):
            parse_search_query("foo == !=")
        with self.assertRaises(ValueError):
            parse_search_query("foo {has} bar")
        with self.assertRaises(ValueError):
            parse_search_query(" {!$} bar")

        # combos
        self.assertEqual(
            parse_search_query("foo != bar && other"),
            ("{and}", ["other"], [{"op": "{not equal}", "lhs": "foo", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query("other || foo {not equal} bar"),
            ("{or}", ["other"], [{"op": "{not equal}", "lhs": "foo", "rhs": "bar"}]),
        )

        # and/or mix not allowed
        with self.assertRaises(ValueError):
            parse_search_query("other {or} foo != bar && third")

        # another false case
        with self.assertRaises(ValueError):
            parse_search_query("|| other || foo != bar")

        # structured search should not be triggered if the query is wrapped in quotes
        self.assertEqual(
            parse_search_query('"foo == bar"'), (None, ['"foo == bar"'], [])
        )

    def test_structured_query_operators(self):
        op_keys = set(OPERATOR_METADATA.keys())
        self.assertTrue(all(op_keys))
        self.assertEqual(len(op_keys), len(OPERATOR_METADATA))
        self.assertEqual(
            len(
                SEARCH_CHAINING_OPERATORS
                + SEARCH_TERM_BINARY_OPERATORS
                + SEARCH_TERM_UNARY_OPERATORS
            ),
            len(OPERATOR_METADATA),
        )

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
