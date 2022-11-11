from src.data.structured_search_filters import (
    OPERATOR_METADATA,
    SEARCH_TERM_BINARY_OPERATORS,
    SEARCH_TERM_UNARY_OPERATORS,
    STRUCTURED_SEARCH_ATTRIBUTES,
)
from src.data.brain_regions import REGIONS


def get_advanced_search_data():
    operators = SEARCH_TERM_BINARY_OPERATORS + SEARCH_TERM_UNARY_OPERATORS
    operator_types = {}
    for op in SEARCH_TERM_BINARY_OPERATORS:
        operator_types[op] = (
            "binary_region" if "stream_region" in op else "binary_attribute"
        )
    for op in SEARCH_TERM_UNARY_OPERATORS:
        operator_types[op] = "unary_stream" if "stream" in op else "unary_attribute"
    hemispheres = ["Left", "Right", "Center"]
    regions = list(REGIONS.keys())
    regions.sort()
    return {
        "operators": operators,
        "operator_types": operator_types,
        "operator_metadata": OPERATOR_METADATA,
        "attributes": STRUCTURED_SEARCH_ATTRIBUTES,
        "hemispheres": hemispheres,
        "regions": regions,
    }
