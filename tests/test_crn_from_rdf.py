"""Tests for RDF → CRN (graph_to_crn, turtle_to_crn)."""

import pytest
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

from crn import graph_to_crn, turtle_to_crn

DBO = Namespace("http://dbpedia.org/ontology/")
DBR = Namespace("http://dbpedia.org/resource/")


def test_graph_to_crn_minimal():
    g = Graph()
    subject = URIRef("http://dbpedia.org/resource/Berlin")
    g.add((subject, RDF.type, DBO.City))
    g.add((subject, RDFS.label, Literal("Berlin")))
    doc = graph_to_crn(g, "http://dbpedia.org/resource/Berlin")
    assert doc.resource == "http://dbpedia.org/resource/Berlin"
    assert doc.label == "Berlin"
    assert any("City" in t for t in doc.type)


def test_graph_to_crn_with_content_and_links():
    g = Graph()
    subject = DBR.Berlin
    g.add((subject, RDFS.label, Literal("Berlin")))
    g.add((subject, DBO.abstract, Literal("Berlin is the capital of Germany.")))
    g.add((subject, DBO.country, DBR.Germany))
    g.add((DBR.Germany, RDFS.label, Literal("Germany")))
    doc = graph_to_crn(g, str(subject))
    assert doc.content is not None
    assert "Germany" in doc.content or "capital" in doc.content
    assert len(doc.links) >= 1
    assert any(l.uri_ref for l in doc.links)
