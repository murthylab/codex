from typing import Iterable
from unittest import TestCase

from src.data.structured_search_filters import (
    _make_predicate,
    parse_search_query,
    STRUCTURED_SEARCH_UNARY_OPERATORS,
    STRUCTURED_SEARCH_NARY_OPERATORS,
    STRUCTURED_SEARCH_BINARY_OPERATORS,
    STRUCTURED_SEARCH_OPERATORS,
    TYPE_BINARY_OP,
    TYPE_UNARY_OP,
    TYPE_NARY_OP,
    BinarySearchOperator,
    UnarySearchOperator,
    NarySearchOperator,
)


class Test(TestCase):
    def test_make_predicate(self):
        for op in STRUCTURED_SEARCH_OPERATORS:

            def some_value(restricted_values):
                if restricted_values is None:
                    return "123"
                elif isinstance(restricted_values, Iterable):
                    return restricted_values[0]
                else:
                    return ""

            if op.op_type == TYPE_BINARY_OP:
                self.assertTrue(type(op) == BinarySearchOperator)
                st = {
                    "lhs": some_value(op.lhs_range),
                    "rhs": some_value(op.rhs_range),
                    "op": op.name,
                }
            elif op.op_type == TYPE_UNARY_OP:
                self.assertTrue(type(op) == UnarySearchOperator)
                st = {"lhs": None, "rhs": some_value(op.rhs_range), "op": op.name}
            elif op.op_type == TYPE_NARY_OP:
                self.assertTrue(type(op) == NarySearchOperator)
                st = {"lhs": some_value(None), "rhs": some_value(None), "op": op.name}
            else:
                self.fail(f"Unknown op type: {op}")
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
        op_names_set = set([op.name for op in STRUCTURED_SEARCH_OPERATORS])
        self.assertTrue(all(op_names_set))
        self.assertEqual(len(op_names_set), len(STRUCTURED_SEARCH_OPERATORS))
        self.assertEqual(
            len(
                STRUCTURED_SEARCH_NARY_OPERATORS
                + STRUCTURED_SEARCH_BINARY_OPERATORS
                + STRUCTURED_SEARCH_UNARY_OPERATORS
            ),
            len(STRUCTURED_SEARCH_OPERATORS),
        )

        op_shorthands = set([op.shorthand for op in STRUCTURED_SEARCH_OPERATORS])
        self.assertTrue(all(op_shorthands))
        self.assertEqual(len(op_shorthands), len(STRUCTURED_SEARCH_OPERATORS))
        self.assertTrue(op_names_set.isdisjoint(op_shorthands))

        # Check descriptions are present and unique
        op_descriptions = set([op.description for op in STRUCTURED_SEARCH_OPERATORS])
        self.assertTrue(all(op_descriptions))
        self.assertEqual(len(op_descriptions), len(STRUCTURED_SEARCH_OPERATORS))

        # check that operators or their shorthands are not substrings of each other
        all_ops = op_shorthands.union(op_names_set)
        for op1 in all_ops:
            for op2 in all_ops:
                self.assertTrue(op1 == op2 or op1 not in op2)
