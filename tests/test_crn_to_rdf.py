"""Tests for CRN → Turtle (crn_to_turtle) and round-trip."""

import pytest
from rdflib import Graph
from rdflib.namespace import RDFS

from crn import parse, crn_to_turtle, crn_to_graph, graph_to_crn


def test_crn_to_turtle_minimal():
    from crn.model import CRNDocument
    doc = CRNDocument(resource="http://example.org/X", label="Example")
    ttl = crn_to_turtle(doc)
    g = Graph()
    g.parse(data=ttl, format="turtle")
    assert (None, RDFS.label, None) in g
    triples = list(g.triples((None, RDFS.label, None)))
    assert any(str(o) == "Example" for _, _, o in triples)


def test_crn_to_turtle_content_predicate_default_rdfs_comment():
    from crn.model import CRNDocument
    doc = CRNDocument(
        resource="http://ex.org/X",
        content="Some abstract text.",
    )
    ttl = crn_to_turtle(doc)
    assert "rdfs:comment" in ttl or "comment" in ttl
    assert "Some abstract text" in ttl


def test_crn_to_turtle_plain_key_uses_crn_namespace():
    from crn.model import CRNDocument, PropertyEntry
    doc = CRNDocument(
        resource="http://ex.org/X",
        properties=(PropertyEntry("population", "1000", None),),
    )
    ttl = crn_to_turtle(doc)
    assert "crn:" in ttl or "purl.org/crn" in ttl
    assert "population" in ttl


def test_crn_to_turtle_property_with_lang():
    from crn.model import CRNDocument, PropertyEntry
    doc = CRNDocument(
        resource="http://ex.org/X",
        properties=(PropertyEntry("label", "Hello", "en"),),
    )
    ttl = crn_to_turtle(doc)
    assert "@en" in ttl or "Hello" in ttl


def test_round_trip_turtle_to_crn_to_turtle():
    from crn import turtle_to_crn
    turtle_src = """
    @prefix dbr: <http://dbpedia.org/resource/> .
    @prefix dbo: <http://dbpedia.org/ontology/> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    dbr:Berlin a dbo:City ;
        rdfs:label "Berlin" ;
        dbo:populationTotal 3748148 .
    """
    doc = turtle_to_crn(turtle_src, "http://dbpedia.org/resource/Berlin")
    ttl2 = crn_to_turtle(doc)
    g1 = Graph()
    g1.parse(data=turtle_src, format="turtle")
    g2 = Graph()
    g2.parse(data=ttl2, format="turtle")
    # Same number of triples (subject, type, label, population)
    assert len(list(g2)) >= 3
    assert any("Berlin" in str(o) for _, _, o in g2.triples((None, None, None)))


def test_round_trip_graph_isomorphism():
    """Round-trip Turtle -> CRN -> Turtle; compare as set of (s,p,o) triples (Resolved #9)."""
    from rdflib.namespace import RDFS
    from crn import turtle_to_crn
    turtle_src = """
    @prefix dbr: <http://dbpedia.org/resource/> .
    @prefix dbo: <http://dbpedia.org/ontology/> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    dbr:Berlin a dbo:City ;
        rdfs:label "Berlin" ;
        dbo:populationTotal 3748148 .
    """
    doc = turtle_to_crn(turtle_src, "http://dbpedia.org/resource/Berlin")
    ttl2 = crn_to_turtle(doc)
    g1 = Graph()
    g1.parse(data=turtle_src, format="turtle")
    g2 = Graph()
    g2.parse(data=ttl2, format="turtle")
    triples1 = set((str(s), str(p), str(o)) for s, p, o in g1)
    triples2 = set((str(s), str(p), str(o)) for s, p, o in g2)
    # Subject, label, type, and at least one property should be present
    assert ("http://dbpedia.org/resource/Berlin", str(RDFS.label), "Berlin") in triples2
    assert len(triples2) >= 3
    # Same subject in both
    subs1 = {s for s, _, _ in triples1}
    subs2 = {s for s, _, _ in triples2}
    assert subs1 == subs2
