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
    _match_list_of_neuropils,
    STRUCTURED_SEARCH_ATTRIBUTES,
    closest_attribute_by_name,
    _search_attribute_by_name,
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

            def mock_con_loader(cell_id=None, by_neuropil=None):
                if by_neuropil:
                    return {}, {}
                else:
                    return [], []

            def mock_list_loader(
                cell_id=None,
                root_id=None,
                projected_to_root_id=None,
                limit=0,
                include_self=True,
                include_upstream=False,
                include_downstream=False,
                weighted=False,
            ):
                return []

            def mock_dict_loader(
                cell_id=None,
                root_id=None,
                projected_to_root_id=None,
                limit=0,
                include_self=True,
                include_upstream=False,
                include_downstream=False,
                weighted=False,
            ):
                return {}

            self.assertIsNotNone(
                _make_predicate(
                    st,
                    mock_con_loader,
                    mock_con_loader,
                    connections_loader=mock_con_loader,
                    similar_cells_loader=mock_list_loader,
                    similar_connectivity_loader=mock_list_loader,
                    similar_spectral_loader=mock_dict_loader,
                    case_sensitive=False,
                )
            )
            self.assertIsNotNone(
                _make_predicate(
                    st,
                    mock_con_loader,
                    mock_con_loader,
                    connections_loader=mock_con_loader,
                    similar_cells_loader=mock_list_loader,
                    similar_connectivity_loader=mock_list_loader,
                    similar_spectral_loader=mock_dict_loader,
                    case_sensitive=True,
                )
            )

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
            parse_search_query("foo {not_equal} bar"),
            (None, [], [{"op": "{not_equal}", "lhs": "foo", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query("foo != bar"),
            (None, [], [{"op": "{not_equal}", "lhs": "foo", "rhs": "bar"}]),
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
            ("{and}", ["other"], [{"op": "{not_equal}", "lhs": "foo", "rhs": "bar"}]),
        )
        self.assertEqual(
            parse_search_query("other || foo {not_equal} bar"),
            ("{or}", ["other"], [{"op": "{not_equal}", "lhs": "foo", "rhs": "bar"}]),
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

    def test_match_list_of_neuropils(self):
        self.assertEqual(
            {"AME_L", "ME_L", "ME_R", "AME_R"}, _match_list_of_neuropils("medulla")
        )

    def test_attributes_consistency(self):
        names_and_alternative_names = []
        for so in STRUCTURED_SEARCH_ATTRIBUTES:
            names_and_alternative_names.append(so.name)
            names_and_alternative_names.extend(so.alternative_names)
            self.assertTrue(so.value_range is None or isinstance(so.value_range, list))
        self.assertEqual(
            len(names_and_alternative_names), len(set(names_and_alternative_names))
        )

        seps = ["-", "_", " "]
        for n in names_and_alternative_names:
            self.assertEqual(n, n.lower())
            for s1 in seps:
                for s2 in seps:
                    if s1 == s2:
                        continue
                    if s1 in n:
                        self.assertFalse(s2 in n, f"Mixed {s1} and {s2} in {n}")
                        altname = n.replace(s1, s2)
                        self.assertTrue(
                            altname in names_and_alternative_names,
                            f"{n} but not {altname}",
                        )

        for a in STRUCTURED_SEARCH_ATTRIBUTES:
            for n in a.alternative_names + [a.name]:
                score, attr = closest_attribute_by_name(n)
                self.assertEqual(0, score)
                self.assertEqual(attr, a)

        score, attr = closest_attribute_by_name("Input Hemisphere")
        self.assertEqual(0, score)
        self.assertEqual("input_hemisphere", attr.name)

        score, attr = closest_attribute_by_name("ID")
        self.assertEqual(0, score)
        self.assertEqual("root_id", attr.name)

        score, attr = closest_attribute_by_name("tags")
        self.assertEqual(1, score)
        self.assertEqual("label", attr.name)

        score, attr = closest_attribute_by_name("flowing")
        self.assertEqual(3, score)
        self.assertEqual("flow", attr.name)

    def test_attributes_lookup(self):
        for a in STRUCTURED_SEARCH_ATTRIBUTES:
            for n in a.alternative_names + [a.name]:
                self.assertEqual(a, _search_attribute_by_name(n))
                self.assertEqual(a, _search_attribute_by_name(n.upper()))
