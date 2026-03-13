"""Compact Resource Notation (CRN) domain model.

All types are immutable. API expects/returns Unicode str (UTF-8 decoded).
"""

from dataclasses import dataclass, field
from typing import Any


# Default namespace for plain property keys when converting CRN to RDF (Resolved #1).
CRN_PROPERTY_NS = "http://purl.org/crn/property#"


@dataclass(frozen=True)
class PropertyEntry:
    """A single property: key, value, and optional language tag (spec 6.5, Resolved #4)."""

    key: str
    value: str
    lang: str | None = None


@dataclass(frozen=True)
class LinkEntry:
    """A link: id, relationship, label, and uri_ref (prefixed or <full>)."""

    id: int
    relationship: str
    label: str
    uri_ref: str


@dataclass(frozen=True)
class FormEntry:
    """A form: fid, method, label, uri_ref, and parameters (name, type_str)."""

    fid: str
    method: str
    label: str
    uri_ref: str
    parameters: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass
class CRNDocument:
    """CRN document: header (required @resource) and optional sections in fixed order."""

    resource: str
    label: str | None = None
    source: str | None = None
    type: tuple[str, ...] = field(default_factory=tuple)
    prefixes: dict[str, str] = field(default_factory=dict)
    content: str | None = None
    properties: tuple[PropertyEntry, ...] = field(default_factory=tuple)
    links: tuple[LinkEntry, ...] = field(default_factory=tuple)
    forms: tuple[FormEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.resource.strip():
            raise ValueError("resource (@resource) is required and must be non-empty")
        # Normalize to tuple for immutable types
        if isinstance(self.type, list):
            object.__setattr__(self, "type", tuple(self.type))
        if isinstance(self.properties, list):
            object.__setattr__(self, "properties", tuple(self.properties))
        if isinstance(self.links, list):
            object.__setattr__(self, "links", tuple(self.links))
        if isinstance(self.forms, list):
            object.__setattr__(self, "forms", tuple(self.forms))
