from typing import Iterable

from src.data.brain_regions import (
    match_to_neuropil,
    lookup_neuropil_set,
    REGIONS,
    HEMISPHERES,
    neuropil_hemisphere,
)
from src.data.gcs_data_loader import load_connections_for_root_id
from src.data.neurotransmitters import lookup_nt_type, NEURO_TRANSMITTER_NAMES
from src.utils.graph_algos import pathways


class SearchAttribute(object):
    def __init__(self, name, value_getter, convertor, description, value_range):
        self.name = name
        self.value_getter = value_getter
        self.convertor = convertor
        self.description = description
        self.value_range = list(value_range) if value_range is not None else None


STRUCTURED_SEARCH_ATTRIBUTES = [
    SearchAttribute(
        name="label",
        value_getter=lambda nd: nd["tag"],
        convertor=None,
        description="Human readable label assigned during cell identification process. Each cell can have zero or more labels.",
        value_range=None,
    ),
    SearchAttribute(
        name="nt",
        value_getter=lambda nd: nd["nt_type"],
        convertor=lambda x: lookup_nt_type(x),
        description="Neuro-transmitter type",
        value_range=NEURO_TRANSMITTER_NAMES,
    ),
    SearchAttribute(
        name="input_neuropil",
        value_getter=lambda nd: nd["input_neuropils"],
        convertor=lambda x: match_to_neuropil(x),
        description="Brain region / neuropil with upstream synaptic connections.",
        value_range=REGIONS.keys(),
    ),
    SearchAttribute(
        name="output_neuropil",
        value_getter=lambda nd: nd["output_neuropils"],
        convertor=lambda x: match_to_neuropil(x),
        description="Brain region / neuropil with downstream synaptic connections.",
        value_range=REGIONS.keys(),
    ),
    SearchAttribute(
        name="input_hemisphere",
        value_getter=lambda nd: [neuropil_hemisphere(p) for p in nd["input_neuropils"]],
        convertor=None,
        description="Brain hemisphere / side with upstream synaptic connections.",
        value_range=HEMISPHERES,
    ),
    SearchAttribute(
        name="output_hemisphere",
        value_getter=lambda nd: [
            neuropil_hemisphere(p) for p in nd["output_neuropils"]
        ],
        convertor=None,
        description="Brain hemisphere / side with downstream synaptic connections.",
        value_range=HEMISPHERES,
    ),
    SearchAttribute(
        name="class",
        value_getter=lambda nd: nd["classes"],
        convertor=None,
        description="Cell typing attribute. Indicates function or other property of the cell. Each cell can belong to zero or more classes.",
        value_range=None,
    ),
    SearchAttribute(
        name="group",
        value_getter=lambda nd: nd["group"],
        convertor=None,
        description="Automatically assigned group name (based on properties of the cell).",
        value_range=None,
    ),
    SearchAttribute(
        name="name",
        value_getter=lambda nd: nd["name"],
        convertor=None,
        description="Automatically assigned name (based on properties of the cell). Unique across data versions, but might get replaced if affected by proofreading.",
        value_range=None,
    ),
    SearchAttribute(
        name="id",
        value_getter=lambda nd: nd["root_id"],
        convertor=lambda x: int(x),
        description="ID of the cell. Unique across data versions, but might get replaced if affected by proofreading.",
        value_range=None,
    ),
]

SEARCH_ATTRIBUTE_NAMES = [a.name for a in STRUCTURED_SEARCH_ATTRIBUTES]


# Structured search operators
OP_EQUAL = "{equal}"
OP_NOT_EQUAL = "{not equal}"
OP_STARTS_WITH = "{starts_with}"
OP_CONTAINS = "{contains}"
OP_IN = "{in}"
OP_NOT_IN = "{not in}"
OP_HAS = "{has}"
OP_NOT = "{not}"
OP_UPSTREAM = "{upstream}"
OP_DOWNSTREAM = "{downstream}"
OP_UPSTREAM_REGION = "{upstream_region}"
OP_DOWNSTREAM_REGION = "{downstream_region}"
OP_PATHWAYS = "{pathways}"
OP_AND = "{and}"
OP_OR = "{or}"

# Operator types
TYPE_BINARY_OP = "binary_operator"
TYPE_UNARY_OP = "unary_operator"
TYPE_NARY_OP = "nary_operator"


class SearchOperator(object):
    def __init__(self, name, shorthand, op_type, description):
        if type(self) is SearchOperator:
            raise Exception(
                "SearchOperator is an abstract class and cannot be instantiated directly"
            )
        self.name = name
        self.shorthand = shorthand
        self.op_type = op_type
        self.description = description


class BinarySearchOperator(SearchOperator):
    def __init__(
        self,
        name,
        shorthand,
        description,
        lhs_description,
        lhs_range,
        rhs_description,
        rhs_range,
    ):
        super().__init__(
            name=name,
            shorthand=shorthand,
            op_type=TYPE_BINARY_OP,
            description=description,
        )
        self.lhs_description = lhs_description
        self.lhs_range = lhs_range
        self.rhs_description = rhs_description
        self.rhs_range = rhs_range


class UnarySearchOperator(SearchOperator):
    def __init__(self, name, shorthand, description, rhs_description, rhs_range):
        super().__init__(
            name=name,
            shorthand=shorthand,
            op_type=TYPE_UNARY_OP,
            description=description,
        )
        self.rhs_description = rhs_description
        self.rhs_range = rhs_range


class NarySearchOperator(SearchOperator):
    def __init__(self, name, shorthand, description):
        super().__init__(
            name=name,
            shorthand=shorthand,
            op_type=TYPE_NARY_OP,
            description=description,
        )


STRUCTURED_SEARCH_OPERATORS = [
    BinarySearchOperator(
        name=OP_EQUAL,
        shorthand="==",
        description="Binary, LHS attribute of the cell and RHS value are equal",
        lhs_description="Attribute",
        lhs_range=SEARCH_ATTRIBUTE_NAMES,
        rhs_description="Value",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_NOT_EQUAL,
        shorthand="!=",
        description="Binary, LHS attribute of the cell and RHS value are not equal",
        lhs_description="Attribute",
        lhs_range=SEARCH_ATTRIBUTE_NAMES,
        rhs_description="Value",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_STARTS_WITH,
        shorthand="^*",
        description="Binary, LHS attribute of the cell starts with RHS value (e.g., label {starts_with} LC",
        lhs_description="Attribute",
        lhs_range=SEARCH_ATTRIBUTE_NAMES,
        rhs_description="Prefix",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_CONTAINS,
        shorthand=">>",
        description="Binary, LHS attribute of the cell contains RHS value (e.g., label {contains} dsx",
        lhs_description="Attribute",
        lhs_range=SEARCH_ATTRIBUTE_NAMES,
        rhs_description="Substring",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_IN,
        shorthand="<<",
        description="Binary, LHS attribute of the cell equals one of the comma-separated values on RHS",
        lhs_description="Attribute",
        lhs_range=SEARCH_ATTRIBUTE_NAMES,
        rhs_description="Values",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_NOT_IN,
        shorthand="!<",
        description="Binary, LHS attribute of the cell is not equal to any of the comma-separated values on RHS",
        lhs_description="Attribute",
        lhs_range=SEARCH_ATTRIBUTE_NAMES,
        rhs_description="Values",
        rhs_range=None,
    ),
    UnarySearchOperator(
        name=OP_HAS,
        shorthand="$$",
        description="Unary, attribute of the cell has value (not empty)",
        rhs_description="Attribute",
        rhs_range=SEARCH_ATTRIBUTE_NAMES,
    ),
    UnarySearchOperator(
        name=OP_NOT,
        shorthand="!$",
        description="Unary, attribute of the cell has no value (empty)",
        rhs_description="Attribute",
        rhs_range=SEARCH_ATTRIBUTE_NAMES,
    ),
    UnarySearchOperator(
        name=OP_UPSTREAM,
        shorthand="^^",
        description="Unary, matches cells upstream of specified Cell ID)",
        rhs_description="Cell ID",
        rhs_range=None,
    ),
    UnarySearchOperator(
        name=OP_DOWNSTREAM,
        shorthand="!^",
        description="Unary, matches cells downstream of specified Cell ID)",
        rhs_description="Cell ID",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_UPSTREAM_REGION,
        shorthand="^R",
        description="Binary, matches cells upstream of RHS, with synapses in LHS region, where region is either hemisphere (left/right/center) or neuropil (e.g. GNG).",
        lhs_description="Region or Side",
        lhs_range=HEMISPHERES + list(REGIONS.keys()),
        rhs_description="Cell ID",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_DOWNSTREAM_REGION,
        shorthand="!R",
        description="Binary, matches cells downstream of RHS, with synapses in LHS region, where region is either hemisphere (left/right/center) or neuropil (e.g. GNG).",
        lhs_description="Region or Side",
        lhs_range=HEMISPHERES + list(REGIONS.keys()),
        rhs_description="Cell ID",
        rhs_range=None,
    ),
    BinarySearchOperator(
        name=OP_PATHWAYS,
        shorthand="->",
        description="Binary, match all cells along shortest-path pathways from LHS to RHS",
        lhs_description="Source Cell ID",
        lhs_range=None,
        rhs_description="Target Cell ID",
        rhs_range=None,
    ),
    NarySearchOperator(
        name=OP_AND, shorthand="&&", description="N-ary, all terms are true"
    ),
    NarySearchOperator(
        name=OP_OR,
        shorthand="||",
        description="N-ary, at least one of the terms is true",
    ),
]

STRUCTURED_SEARCH_BINARY_OPERATORS = [
    op for op in STRUCTURED_SEARCH_OPERATORS if op.op_type == TYPE_BINARY_OP
]
STRUCTURED_SEARCH_UNARY_OPERATORS = [
    op for op in STRUCTURED_SEARCH_OPERATORS if op.op_type == TYPE_UNARY_OP
]
STRUCTURED_SEARCH_NARY_OPERATORS = [
    op for op in STRUCTURED_SEARCH_OPERATORS if op.op_type == TYPE_NARY_OP
]


def _raise_unsupported_attr_for_structured_search(attr_name):
    raise_malformed_structured_search_query(
        f"Structured query by attribute <b>{attr_name}</b> is not supported. Possible solutions:"
        f"<br>- look for typos in <b>{attr_name}</b>, or try searching by one of the supported "
        f"attribute: {', '.join(SEARCH_ATTRIBUTE_NAMES)}"
    )


def _raise_invalid_value_for_structured_search(attr_name, value, valid_values):
    msg = f"'{value}' is not a valid value for  <b>{attr_name}</b>."
    if valid_values:
        msg += (
            " Valid values are:<ul>"
            + "".join([f"<li>{v}</li>" for v in valid_values])
            + "</ul>"
        )
    raise_malformed_structured_search_query(msg)


def raise_malformed_structured_search_query(msg="Malformed structured search query"):
    raise ValueError(
        f"{msg}<br>See info about structured search on the FAQ page, "
        f"or wrap your query in double quotes to run a free form search."
    )


def _search_attribute_by_name(name):
    matches = [sa for sa in STRUCTURED_SEARCH_ATTRIBUTES if sa.name == name]
    if len(matches) != 1:
        raise_malformed_structured_search_query(
            f"Attribute name '{name}' is not recognized"
        )
    return matches[0]


def _search_operator_by_name(name):
    matches = [so for so in STRUCTURED_SEARCH_OPERATORS if so.name == name]
    if len(matches) != 1:
        raise_malformed_structured_search_query(f"Operator '{name}' is not recognized")
    return matches[0]


def _make_comparison_predicate(lhs, rhs, op, case_sensitive):
    lhs = lhs.lower()
    search_attr = _search_attribute_by_name(lhs)

    # attempt conversion
    try:
        conversion_func = search_attr.convertor
        if conversion_func:
            rhs = conversion_func(rhs)
    except:
        _raise_invalid_value_for_structured_search(
            attr_name=lhs, value=rhs, valid_values=search_attr.value_range
        )

    def op_checker(val):
        str_rhs = str(rhs)
        if not case_sensitive:
            str_rhs = str_rhs.lower()

        def str_op_checker(str_val):
            if not case_sensitive:
                str_val = str_val.lower()

            if op == OP_EQUAL:
                return str_rhs == str_val
            elif op == OP_STARTS_WITH:
                return str_val.startswith(str_rhs)
            elif op == OP_CONTAINS:
                return str_rhs in str_val
            raise ValueError(f"Unsupported comparison operand: {op}")

        if isinstance(val, list):
            return any([str_op_checker(str(v)) for v in val])
        else:
            return str_op_checker(str(val))

    return lambda nd: op_checker(search_attr.value_getter(nd))


def _make_has_predicate(rhs):
    rhs = rhs.lower()
    search_attr = _search_attribute_by_name(rhs)
    return lambda nd: search_attr.value_getter(nd)


def _make_predicate(structured_term, input_sets, output_sets, case_sensitive):
    if structured_term["op"] in [OP_EQUAL, OP_STARTS_WITH, OP_CONTAINS]:
        return _make_comparison_predicate(
            lhs=structured_term["lhs"],
            rhs=structured_term["rhs"],
            op=structured_term["op"],
            case_sensitive=case_sensitive,
        )
    elif structured_term["op"] == OP_NOT_EQUAL:
        eq_p = _make_comparison_predicate(
            lhs=structured_term["lhs"],
            rhs=structured_term["rhs"],
            op=OP_EQUAL,
            case_sensitive=case_sensitive,
        )
        return lambda x: not eq_p(x)
    elif structured_term["op"] == OP_HAS:
        hp = _make_has_predicate(rhs=structured_term["rhs"])
        return lambda x: hp(x)
    elif structured_term["op"] == OP_NOT:
        hp = _make_has_predicate(rhs=structured_term["rhs"])
        return lambda x: not hp(x)
    elif structured_term["op"] in [OP_IN, OP_NOT_IN]:
        rhs_items = [item.strip() for item in structured_term["rhs"].split(",")]
        predicates = [
            _make_comparison_predicate(
                lhs=structured_term["lhs"],
                rhs=i,
                op=OP_EQUAL,
                case_sensitive=case_sensitive,
            )
            for i in rhs_items
        ]
        if structured_term["op"] == OP_IN:
            return lambda x: any([p(x) for p in predicates])
        else:
            return lambda x: not any([p(x) for p in predicates])
    elif structured_term["op"] in [OP_DOWNSTREAM, OP_UPSTREAM]:
        downstream, upstream = load_connections_for_root_id(
            structured_term["rhs"], by_neuropil=False
        )
        target_rid_set = (
            set(downstream) if structured_term["op"] == OP_DOWNSTREAM else set(upstream)
        )
        return lambda x: x["root_id"] in target_rid_set
    elif structured_term["op"] in [OP_DOWNSTREAM_REGION, OP_UPSTREAM_REGION]:
        downstream, upstream = load_connections_for_root_id(
            structured_term["rhs"], by_neuropil=True
        )
        region_neuropil_set = lookup_neuropil_set(structured_term["lhs"])
        target_rid_set = set()
        for k, v in (
            downstream if structured_term["op"] == OP_DOWNSTREAM_REGION else upstream
        ).items():
            if k in region_neuropil_set:
                target_rid_set |= set(v)
        return lambda x: x["root_id"] in target_rid_set
    elif structured_term["op"] == OP_PATHWAYS:
        pathway_distance_map = pathways(
            source=structured_term["lhs"],
            target=structured_term["rhs"],
            input_sets=input_sets,
            output_sets=output_sets,
        )
        pathway_distance_map = pathway_distance_map or {}
        return lambda x: x["root_id"] in pathway_distance_map
    elif structured_term["op"] == OP_AND:
        return structured_term["lhs"] and structured_term["rhs"]
    elif structured_term["op"] == OP_OR:
        return structured_term["lhs"] or structured_term["rhs"]
    else:
        raise ValueError(f"Unsupported query operator {structured_term['op']}")


def make_structured_terms_predicate(
    chaining_rule, structured_terms, input_sets, output_sets, case_sensitive
):
    predicates = [
        _make_predicate(
            structured_term=t,
            input_sets=input_sets,
            output_sets=output_sets,
            case_sensitive=case_sensitive,
        )
        for t in structured_terms
    ]
    if len(structured_terms) == 1:
        return predicates[0]
    elif chaining_rule == OP_AND:
        return lambda x: all([p(x) for p in predicates])
    elif chaining_rule == OP_OR:
        return lambda x: any([p(x) for p in predicates])
    else:
        raise ValueError(f"Unsupported chaining rule {chaining_rule}")


def apply_chaining_rule(chaining_rule, term_search_results):
    if len(term_search_results) == 1:
        return term_search_results[0]
    elif chaining_rule == OP_AND:
        return list(set.intersection(*[set(r) for r in term_search_results]))
    elif chaining_rule == OP_OR:
        return list(set.union(*[set(r) for r in term_search_results]))
    else:
        raise ValueError(f"Unsupported chaining rule {chaining_rule}")


def _extract_search_operators(term, ops=None):
    if not (term.startswith('"') and term.endswith('"')):
        ops = ops or STRUCTURED_SEARCH_OPERATORS
        ops_shorthands = [op.shorthand for op in ops]
        return [
            op
            for i, op in enumerate(ops)
            if (op.name in term or ops_shorthands[i] in term)
        ]
    else:
        return []


def _parse_search_terms(terms):
    free_form = []
    structured = []
    for term in terms:
        search_operators = _extract_search_operators(term)
        if not search_operators:
            free_form.append(term)
            continue
        elif len(search_operators) == 1:
            op = search_operators[0]
            parts = _extract_operands(text=term, op=op)
            if len(parts) == 2:
                if op.op_type == TYPE_BINARY_OP:
                    if all(parts):
                        structured.append(
                            {"op": op.name, "lhs": parts[0], "rhs": parts[1]}
                        )
                        continue
                elif op.op_type == TYPE_UNARY_OP:
                    if not parts[0] and parts[1]:
                        structured.append({"op": op.name, "rhs": parts[1]})
                        continue
        raise_malformed_structured_search_query()

    return free_form, structured


def _parse_chained_search_query(search_query):
    if search_query and not (
        search_query.startswith('"') and search_query.endswith('"')
    ):
        search_operators = _extract_search_operators(
            search_query, STRUCTURED_SEARCH_NARY_OPERATORS
        )
        if len(search_operators) == 1:
            parts = _extract_operands(text=search_query, op=search_operators[0])
            if len(parts) >= 2 and all(parts):
                return search_operators[0].name, parts
            else:
                raise_malformed_structured_search_query(
                    f"Malformed {search_operators[0]} query"
                )
        elif len(search_operators) > 1:
            raise_malformed_structured_search_query(
                f"Mixing operators {search_operators} not supported"
            )
    return None, [search_query]


def _extract_operands(text, op):
    parts = [p.strip() for p in text.split(op.name)]
    # try shorthand if op not found in text
    if len(parts) == 1:
        parts = [p.strip() for p in text.split(op.shorthand)]
    return parts


def parse_search_query(search_query):
    chaining_rule, terms = _parse_chained_search_query(search_query)
    free_form, structured = _parse_search_terms(terms)
    return chaining_rule, free_form, structured


def get_advanced_search_data(current_query):
    def clean(dct):
        clean_dict = {}
        for k, v in dct.items():
            if v == SEARCH_ATTRIBUTE_NAMES:
                clean_dict[k] = "attributes"
            elif v is not None and any([isinstance(v, t) for t in [str, Iterable]]):
                clean_dict[k] = v
        return clean_dict

    current_query = parse_search_query(current_query)
    res = {
        "operators": {
            op.name: clean(op.__dict__)
            for op in STRUCTURED_SEARCH_BINARY_OPERATORS
            + STRUCTURED_SEARCH_UNARY_OPERATORS
        },
        "attributes": {
            sa.name: clean(sa.__dict__) for sa in STRUCTURED_SEARCH_ATTRIBUTES
        },
        "current_query": {"chaining": current_query[0], "terms": current_query[2]},
    }
    return res
