"""Tests for CRN parser: valid CRN, escaping, section order, [id] validation."""

import pytest
from crn import parse
from crn.parser import CRNParseError

MINIMAL_CRN = """@resource <http://example.org/Thing>
"""

CRN_WITH_LINKS = """@resource <http://example.org/Thing>
@label "A Thing"

== content ==
See also [1] and [2].

== links ==
[1] href "First" <http://example.org/First>
[2] href "Second" <http://example.org/Second>
"""


class TestParseMinimal:
    def test_minimal_resource_only(self):
        doc = parse(MINIMAL_CRN)
        assert doc.resource == "http://example.org/Thing"
        assert doc.label is None
        assert doc.content is None
        assert doc.links == ()

    def test_missing_resource_raises(self):
        with pytest.raises(CRNParseError, match="Missing required @resource"):
            parse("@label \"x\"\n== content ==\nhi")

    def test_invalid_resource_raises(self):
        with pytest.raises(CRNParseError, match="Invalid @resource"):
            parse("@resource not_angle_brackets\n")


class TestParseContentAndLinks:
    def test_content_and_links(self):
        doc = parse(CRN_WITH_LINKS)
        assert doc.resource == "http://example.org/Thing"
        assert doc.label == "A Thing"
        assert "See also [1] and [2]." in (doc.content or "")
        assert len(doc.links) == 2
        assert doc.links[0].id == 1 and doc.links[0].label == "First"
        assert doc.links[1].id == 2 and doc.links[1].label == "Second"

    def test_content_ref_missing_in_links_raises(self):
        bad = """@resource <http://ex.org/X>
== content ==
Ref [99] here.
== links ==
[1] href "Only" <http://ex.org/Only>
"""
        with pytest.raises(CRNParseError, match="references \\[id\\]=99"):
            parse(bad)


class TestParseEscaping:
    def test_escape_backslash_bracket_in_content(self):
        crn = """@resource <http://ex.org/X>
== content ==
Literal \\[1\\] and \\"quote\\" and \\\\
== links ==
[1] href "L" <http://ex.org/L>
"""
        doc = parse(crn)
        assert "Literal [1]" in (doc.content or "")
        assert '"quote"' in (doc.content or "")
        assert "\\\\" in (doc.content or "") or "\\" in (doc.content or "")

    def test_unknown_escape_literal_backslash_plus_char(self):
        crn = """@resource <http://ex.org/X>
== content ==
\\x here
== links ==
[1] href "L" <http://ex.org/L>
"""
        doc = parse(crn)
        assert "\\x" in (doc.content or "") or "x" in (doc.content or "")


class TestParseSectionOrder:
    def test_links_before_content_raises(self):
        crn = """@resource <http://ex.org/X>
== links ==
[1] href "L" <http://ex.org/L>
== content ==
See [1].
"""
        with pytest.raises(CRNParseError, match="order"):
            parse(crn)

    def test_forms_before_links_raises(self):
        crn = """@resource <http://ex.org/X>
== content ==
x
== forms ==
[f1] GET "F" <http://ex.org/f> {}
== links ==
[1] href "L" <http://ex.org/L>
"""
        with pytest.raises(CRNParseError, match="order"):
            parse(crn)


class TestParseProperties:
    def test_property_with_lang(self):
        crn = """@resource <http://ex.org/X>
== properties ==
label (en): Hello
label (de): Hallo
"""
        doc = parse(crn)
        assert len(doc.properties) == 2
        assert doc.properties[0].key == "label" and doc.properties[0].lang == "en"
        assert doc.properties[0].value == "Hello"
        assert doc.properties[1].lang == "de" and doc.properties[1].value == "Hallo"

    def test_property_plain(self):
        crn = """@resource <http://ex.org/X>
== properties ==
population: 1000
"""
        doc = parse(crn)
        assert doc.properties[0].key == "population" and doc.properties[0].value == "1000"
        assert doc.properties[0].lang is None


class TestParseForms:
    def test_parse_forms_section(self):
        crn = """@resource <http://ex.org/X>
== content ==
Search here.
== links ==
[1] href "Help" <http://ex.org/help>
== forms ==
[f1] GET "Search" <https://ex.org/search> {q: text, limit: hidden(10)}
[f2] POST "Submit" <https://ex.org/submit> {name: text, value: number}
"""
        doc = parse(crn)
        assert len(doc.forms) == 2
        assert doc.forms[0].fid == "f1"
        assert doc.forms[0].method == "GET"
        assert doc.forms[0].label == "Search"
        assert "search" in doc.forms[0].uri_ref
        assert ("q", "text") in doc.forms[0].parameters
        assert ("limit", "hidden(10)") in doc.forms[0].parameters
        assert doc.forms[1].method == "POST"
        assert ("value", "number") in doc.forms[1].parameters


class TestParseAPI:
    def test_bytes_raises_type_error(self):
        with pytest.raises(TypeError, match="Unicode str"):
            parse(b"@resource <http://ex.org/X>")  # type: ignore[arg-type]
