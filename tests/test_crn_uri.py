"""Tests for CRN URI expansion, equality, local name."""

import pytest
from crn.uri import expand_uri, local_name_from_uri, resolve_relative, uri_equals

PREFIXES = {
    "dbr": "http://dbpedia.org/resource/",
    "dbo": "http://dbpedia.org/ontology/",
}


class TestExpandUri:
    def test_full_uri_angle_brackets(self):
        assert expand_uri("<http://example.org/foo>", PREFIXES) == "http://example.org/foo"

    def test_prefixed_uri(self):
        assert expand_uri("dbr:Berlin", PREFIXES) == "http://dbpedia.org/resource/Berlin"

    def test_prefixed_uri_with_special_local(self):
        assert "Spree" in expand_uri("dbr:Spree_(river)", PREFIXES)

    def test_unknown_prefix_returned_as_is(self):
        assert expand_uri("ex:Something", PREFIXES) == "ex:Something"


class TestResolveRelative:
    def test_absolute_unchanged(self):
        assert resolve_relative("http://example.org/a", "http://example.org/") == "http://example.org/a"

    def test_relative_to_base(self):
        assert resolve_relative("bar", "http://example.org/foo/") == "http://example.org/foo/bar"


class TestUriEquals:
    def test_same_expanded(self):
        assert uri_equals("dbr:Berlin", "<http://dbpedia.org/resource/Berlin>", PREFIXES)

    def test_different_false(self):
        assert not uri_equals("dbr:Berlin", "dbr:Paris", PREFIXES)


class TestLocalName:
    def test_fragment(self):
        assert local_name_from_uri("http://example.org/ns#label") == "label"

    def test_path_segment(self):
        assert local_name_from_uri("http://dbpedia.org/resource/Berlin") == "Berlin"

    def test_underscores_to_spaces(self):
        assert local_name_from_uri("http://ex.org/Kai_Wegner") == "Kai Wegner"
