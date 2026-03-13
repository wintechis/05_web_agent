"""Compact Resource Notation (CRN) — token-efficient, LLM-readable resource format.

API is Unicode str only (decode from UTF-8 if you have bytes).
See crn-specification.md and .cursor/plans for design decisions.
"""

from crn.model import (
    CRNDocument,
    CRN_PROPERTY_NS,
    FormEntry,
    LinkEntry,
    PropertyEntry,
)
from crn.parser import CRNParseError, parse
from crn.serializer import serialize
from crn.uri import expand_uri, local_name_from_uri, resolve_relative, uri_equals
from crn.from_rdf import graph_to_crn, turtle_to_crn
from crn.from_html import html_to_crn
from crn.to_rdf import crn_to_graph, crn_to_turtle
from crn.to_html import crn_to_html

__all__ = [
    "CRNDocument",
    "CRNParseError",
    "CRN_PROPERTY_NS",
    "FormEntry",
    "LinkEntry",
    "PropertyEntry",
    "crn_to_graph",
    "crn_to_html",
    "crn_to_turtle",
    "expand_uri",
    "graph_to_crn",
    "html_to_crn",
    "local_name_from_uri",
    "parse",
    "resolve_relative",
    "serialize",
    "turtle_to_crn",
    "uri_equals",
]
