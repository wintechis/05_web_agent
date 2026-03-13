"""Tests for CRN serializer and round-trip."""

import pytest
from crn import parse, serialize
from crn.model import CRNDocument, LinkEntry, PropertyEntry


def test_serialize_minimal():
    doc = CRNDocument(resource="http://example.org/X")
    out = serialize(doc)
    assert "@resource <http://example.org/X>" in out
    assert "== content ==" not in out


def test_serialize_with_label_and_content():
    doc = CRNDocument(
        resource="http://ex.org/X",
        label='Say "hello"',
        content="Paragraph one.\n\nParagraph two.",
    )
    out = serialize(doc)
    assert "@label " in out
    assert "\\\"" in out or "hello" in out
    assert "== content ==" in out
    assert "Paragraph one." in out


def test_round_trip_minimal():
    crn = "@resource <http://example.org/Thing>\n"
    doc = parse(crn)
    out = serialize(doc)
    doc2 = parse(out)
    assert doc2.resource == doc.resource


def test_round_trip_with_links():
    crn = """@resource <http://ex.org/X>
@label "X"

== content ==
See [1].

== links ==
[1] href "First" <http://ex.org/First>
"""
    doc = parse(crn)
    out = serialize(doc)
    doc2 = parse(out)
    assert doc2.resource == doc.resource
    assert doc2.label == doc.label
    assert len(doc2.links) == 1
    assert doc2.links[0].label == "First"


def test_round_trip_properties_with_lang():
    doc = CRNDocument(
        resource="http://ex.org/X",
        properties=(
            PropertyEntry("label", "Hello", "en"),
            PropertyEntry("label", "Hallo", "de"),
        ),
    )
    out = serialize(doc)
    doc2 = parse(out)
    assert len(doc2.properties) == 2
    assert doc2.properties[0].lang == "en" and doc2.properties[0].value == "Hello"


def test_round_trip_with_forms():
    from crn.model import FormEntry
    crn = """@resource <http://ex.org/X>
== content ==
Use the form.
== links ==
[1] href "Back" <http://ex.org/>
== forms ==
[f1] GET "Search" <http://ex.org/search> {q: text}
"""
    doc = parse(crn)
    out = serialize(doc)
    doc2 = parse(out)
    assert len(doc2.forms) == 1
    assert doc2.forms[0].fid == "f1" and doc2.forms[0].label == "Search"
    assert doc2.forms[0].parameters == (("q", "text"),)


def test_round_trip_spec_example_snippet():
    """Round-trip a CRN snippet similar to spec 13.2 (DBpedia Berlin)."""
    crn = """@resource <http://dbpedia.org/resource/Berlin>
@label "Berlin"
@source text/turtle
@type dbo:City, dbo:PopulatedPlace
@prefix dbr: <http://dbpedia.org/resource/>
@prefix dbo: <http://dbpedia.org/ontology/>

== content ==
Berlin is the capital and largest city of Germany [1].

== properties ==
dbo:populationTotal: 3748148
dbo:areaTotal: 891.7 km²

== links ==
[1] dbo:country "Germany" dbr:Germany
"""
    doc = parse(crn)
    out = serialize(doc)
    doc2 = parse(out)
    assert doc2.resource == doc.resource
    assert doc2.label == doc.label
    assert len(doc2.type) == 2
    assert "capital" in (doc2.content or "")
    assert len(doc2.properties) == 2
    assert any(p.value == "3748148" for p in doc2.properties)
    assert len(doc2.links) == 1 and doc2.links[0].label == "Germany"
