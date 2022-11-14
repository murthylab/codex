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

STRUCTURED_SEARCH_ATTRIBUTES = {
    # user facing attr: (neuron attr getter, conversion - optional, description, restricted_values)
    "label": (
        lambda nd: nd["tag"],
        None,
        "Human readable label assigned during cell identification process. Each cell can have zero or more labels.",
        None,
    ),
    "nt": (
        lambda nd: nd["nt_type"],
        lambda x: lookup_nt_type(x),
        "Neuro-transmitter type",
        NEURO_TRANSMITTER_NAMES,
    ),
    "input_neuropil": (
        lambda nd: nd["input_neuropils"],
        lambda x: match_to_neuropil(x),
        "Brain region / neuropil with upstream synaptic connections.",
        list(REGIONS.keys()),
    ),
    "output_neuropil": (
        lambda nd: nd["output_neuropils"],
        lambda x: match_to_neuropil(x),
        "Brain region / neuropil with downstream synaptic connections.",
        list(REGIONS.keys()),
    ),
    "input_hemisphere": (
        lambda nd: [neuropil_hemisphere(p) for p in nd["input_neuropils"]],
        None,
        "Brain hemisphere / side with upstream synaptic connections.",
        HEMISPHERES,
    ),
    "output_hemisphere": (
        lambda nd: [neuropil_hemisphere(p) for p in nd["output_neuropils"]],
        None,
        "Brain hemisphere / side with downstream synaptic connections.",
        HEMISPHERES,
    ),
    "class": (
        lambda nd: nd["classes"],
        None,
        "Cell typing attribute. Indicates function or other property of the cell. Each cell can "
        "belong to zero or more classes.",
        None,
    ),
    "group": (
        lambda nd: nd["group"],
        None,
        "Automatically assigned group name (based on properties of the cell).",
        None,
    ),
    "name": (
        lambda nd: nd["name"],
        None,
        "Automatically assigned name (based on properties of the cell). Unique across data "
        "versions, but might get replaced if affected by proofreading.",
        None,
    ),
    "id": (
        lambda nd: nd["root_id"],
        lambda x: int(x),
        "ID of the cell. Unique across data versions, "
        "but might get replaced if affected by proofreading.",
        None,
    ),
}


# Operator types
TYPE_BINARY_ATTRIBUTE = "binary_attribute"
TYPE_BINARY_REGION = "binary_region"
TYPE_BINARY_TWOIDS = "binary_twoids"
TYPE_UNARY_ATTRIBUTE = "unary_attribute"
TYPE_UNARY_STREAM = "unary_stream"
TYPE_NARY = "nary"

# Structured search operators
OP_EQUAL = "{equal}"
OP_NOT_EQUAL = "{not equal}"
OP_STARTS_WITH = "{starts_with}"
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

OPERATOR_METADATA = {
    # user facing op: (alternative shorthand, description, type, lhs_restricted_values, rhs_testricted_values)
    OP_EQUAL: (
        "==",
        "Binary, LHS attribute of the cell and RHS value are equal",
        TYPE_BINARY_ATTRIBUTE,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
        None,
    ),
    OP_NOT_EQUAL: (
        "!=",
        "Binary, LHS attribute of the cell and RHS value are not equal",
        TYPE_BINARY_ATTRIBUTE,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
        None,
    ),
    OP_STARTS_WITH: (
        "^*",
        "Binary, LHS attribute of the cell starts with RHS value (e.g., label {starts_with} LC",
        TYPE_BINARY_ATTRIBUTE,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
        None,
    ),
    OP_IN: (
        "<<",
        "Binary, LHS attribute of the cell equals one of the comma-separated values on RHS",
        TYPE_BINARY_ATTRIBUTE,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
        None,
    ),
    OP_NOT_IN: (
        "!<",
        "Binary, LHS attribute of the cell is not equal to any of the comma-separated values on RHS",
        TYPE_BINARY_ATTRIBUTE,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
        None,
    ),
    OP_HAS: (
        "$$",
        "Unary, attribute of the cell has value (not empty)",
        TYPE_UNARY_ATTRIBUTE,
        lambda x: x is None or len(x) == 0,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
    ),
    OP_NOT: (
        "!$",
        "Unary, attribute of the cell has no value (empty)",
        TYPE_UNARY_ATTRIBUTE,
        lambda x: x is None or len(x) == 0,
        list(STRUCTURED_SEARCH_ATTRIBUTES.keys()),
    ),
    OP_UPSTREAM: (
        "^^",
        "Unary, matches cells upstream of specified Cell ID)",
        TYPE_UNARY_STREAM,
        lambda x: x is None or len(x) == 0,
        None,
    ),
    OP_DOWNSTREAM: (
        "!^",
        "Unary, matches cells downstream of specified Cell ID)",
        TYPE_UNARY_STREAM,
        lambda x: x is None or len(x) == 0,
        None,
    ),
    OP_UPSTREAM_REGION: (
        "^R",
        "Binary, matches cells upstream of RHS, with synapses in LHS region, where region "
        "is either hemisphere (left/right/center) or neuropil (e.g. GNG).",
        TYPE_BINARY_REGION,
        HEMISPHERES + list(REGIONS.keys()),
        None,
    ),
    OP_DOWNSTREAM_REGION: (
        "!R",
        "Binary, matches cells downstream of RHS, with synapses in LHS region, where region "
        "is either hemisphere (left/right/center) or neuropil (e.g. GNG).",
        TYPE_BINARY_REGION,
        HEMISPHERES + list(REGIONS.keys()),
        None,
    ),
    OP_PATHWAYS: (
        "->",
        "Binary, match all cells along shortest-path pathways from LHS to RHS",
        TYPE_BINARY_TWOIDS,
        None,
        None,
    ),
    OP_AND: ("&&", "N-ary, all terms are true", TYPE_NARY, None, None),
    OP_OR: ("||", "N-ary, at least one of the terms is true", TYPE_NARY, None, None),
}

SEARCH_TERM_BINARY_OPERATORS = [
    OP_EQUAL,  # equals
    OP_NOT_EQUAL,  # not equal to
    OP_STARTS_WITH,  # starts with
    OP_IN,  # one of the values on rhs (rhs is comma separated list)
    OP_NOT_IN,  # none of the values on rhs (rhs is comma separated list)
    OP_UPSTREAM_REGION,  # upstream to RHS in LHS region
    OP_DOWNSTREAM_REGION,  # downstream to RHS in LHS region
    OP_PATHWAYS,  # pathways from LHS to RHS
]
SEARCH_TERM_UNARY_OPERATORS = [
    OP_HAS,  # exists / has value
    OP_NOT,  # does not exist / has no value
    OP_DOWNSTREAM,  # match downstream connections
    OP_UPSTREAM,  # match upstream connections
]
SEARCH_CHAINING_OPERATORS = [
    OP_AND,  # and / conjunction
    OP_OR,  # or / disjunction
]


def _make_comparison_predicate(lhs, rhs, op):
    lhs = lhs.lower()
    if lhs not in STRUCTURED_SEARCH_ATTRIBUTES:
        _raise_unsupported_attr_for_structured_search(lhs)

    # attempt conversion
    try:
        conversion_func = STRUCTURED_SEARCH_ATTRIBUTES[lhs][1]
        if conversion_func:
            rhs = conversion_func(rhs)
    except:
        _raise_invalid_value_for_structured_search(
            attr_name=lhs, value=rhs, valid_values=STRUCTURED_SEARCH_ATTRIBUTES[lhs][3]
        )

    def op_checker(val):
        if isinstance(val, list):
            if op == OP_EQUAL:
                return rhs in val
            elif op == OP_NOT_EQUAL:
                return rhs not in val
            elif op == OP_STARTS_WITH:
                return any([str(v).startswith(str(rhs)) for v in val])
        else:
            if op == OP_EQUAL:
                return rhs == val
            elif op == OP_NOT_EQUAL:
                return rhs != val
            elif op == OP_STARTS_WITH:
                return str(val).startswith(str(rhs))

        raise ValueError(f"Unsupported comparison operand: {op}")

    return lambda nd: op_checker(STRUCTURED_SEARCH_ATTRIBUTES[lhs][0](nd))


def _make_has_predicate(rhs):
    rhs = rhs.lower()
    if rhs not in STRUCTURED_SEARCH_ATTRIBUTES:
        _raise_unsupported_attr_for_structured_search(rhs)
    return lambda nd: STRUCTURED_SEARCH_ATTRIBUTES[rhs][0](nd)


def _raise_unsupported_attr_for_structured_search(attr_name):
    raise_malformed_structured_search_query(
        f"Structured query by attribute <b>{attr_name}</b> is not supported. Possible solutions:"
        f"<br>- look for typos in <b>{attr_name}</b>, or try searching by one of the supported "
        f"attribute: {', '.join(STRUCTURED_SEARCH_ATTRIBUTES.keys())}"
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


def _make_predicate(structured_term, input_sets, output_sets):
    if structured_term["op"] in [OP_EQUAL, OP_NOT_EQUAL, OP_STARTS_WITH]:
        return _make_comparison_predicate(
            lhs=structured_term["lhs"],
            rhs=structured_term["rhs"],
            op=structured_term["op"],
        )
    elif structured_term["op"] == OP_HAS:
        hp = _make_has_predicate(rhs=structured_term["rhs"])
        return lambda x: hp(x)
    elif structured_term["op"] == OP_NOT:
        hp = _make_has_predicate(rhs=structured_term["rhs"])
        return lambda x: not hp(x)
    elif structured_term["op"] in [OP_IN, OP_NOT_IN]:
        rhs_items = [item.strip() for item in structured_term["rhs"].split(",")]
        predicates = [
            _make_comparison_predicate(lhs=structured_term["lhs"], rhs=i, op=OP_EQUAL)
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
    chaining_rule, structured_terms, input_sets, output_sets
):
    predicates = [
        _make_predicate(
            structured_term=t, input_sets=input_sets, output_sets=output_sets
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
        ops = (
            ops
            or SEARCH_TERM_BINARY_OPERATORS
            + SEARCH_TERM_UNARY_OPERATORS
            + SEARCH_CHAINING_OPERATORS
        )
        ops_shorthands = [OPERATOR_METADATA[op][0] for op in ops]
        return [
            op for i, op in enumerate(ops) if (op in term or ops_shorthands[i] in term)
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
                if op in SEARCH_TERM_BINARY_OPERATORS:
                    if all(parts):
                        structured.append({"op": op, "lhs": parts[0], "rhs": parts[1]})
                        continue
                elif op in SEARCH_TERM_UNARY_OPERATORS:
                    if not parts[0] and parts[1]:
                        structured.append({"op": op, "rhs": parts[1]})
                        continue
        raise_malformed_structured_search_query()

    return free_form, structured


def _parse_chained_search_query(search_query):
    if search_query and not (
        search_query.startswith('"') and search_query.endswith('"')
    ):
        search_operators = _extract_search_operators(
            search_query, SEARCH_CHAINING_OPERATORS
        )
        if len(search_operators) == 1:
            parts = _extract_operands(text=search_query, op=search_operators[0])
            if len(parts) >= 2 and all(parts):
                return search_operators[0], parts
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
    parts = [p.strip() for p in text.split(op)]
    # try shorthand if op not found in text
    if len(parts) == 1:
        parts = [p.strip() for p in text.split(OPERATOR_METADATA[op][0])]
    return parts


def parse_search_query(search_query):
    chaining_rule, terms = _parse_chained_search_query(search_query)
    free_form, structured = _parse_search_terms(terms)
    return chaining_rule, free_form, structured


def get_advanced_search_data():
    operators = SEARCH_TERM_BINARY_OPERATORS + SEARCH_TERM_UNARY_OPERATORS
    operator_types = {}
    for op in operators:
        operator_types[op] = OPERATOR_METADATA[op][2]
    return {
        "operators": operators,
        "operator_types": operator_types,
        "operator_metadata": OPERATOR_METADATA,
        "attributes": STRUCTURED_SEARCH_ATTRIBUTES,
        "hemispheres": HEMISPHERES,
        "regions": list(REGIONS.keys()),
    }
