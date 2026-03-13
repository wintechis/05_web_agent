"""Tests for CRN → HTML (crn_to_html)."""

import pytest
from crn import parse, crn_to_html
from crn.model import CRNDocument, FormEntry, PropertyEntry


def test_crn_to_html_minimal():
    doc = CRNDocument(resource="http://example.org/X", label="Example")
    html = crn_to_html(doc)
    assert "<link rel=\"canonical\"" in html or "canonical" in html
    assert "<title>Example</title>" in html
    assert "<h1>Example</h1>" in html


def test_crn_to_html_content_with_link_ref():
    crn = """@resource <http://ex.org/X>
@label "X"
== content ==
See [1] here.
== links ==
[1] href "Target" <http://ex.org/Target>
"""
    doc = parse(crn)
    html = crn_to_html(doc)
    assert "<a href=" in html
    assert "Target" in html
    assert "See " in html


def test_crn_to_html_properties_as_dl():
    doc = CRNDocument(
        resource="http://ex.org/X",
        properties=(PropertyEntry("key", "value", None),),
    )
    html = crn_to_html(doc)
    assert "<dl>" in html
    assert "key" in html and "value" in html


def test_crn_to_html_form_hidden_and_text():
    doc = CRNDocument(
        resource="http://ex.org/X",
        forms=(
            FormEntry(
                fid="f1",
                method="GET",
                label="Search",
                uri_ref="<http://ex.org/search>",
                parameters=(("q", "text"), ("lang", "hidden(en)")),
            ),
        ),
    )
    html = crn_to_html(doc)
    assert 'type="hidden"' in html
    assert 'type="text"' in html or 'name="q"' in html
    assert "Search" in html


def test_crn_to_html_form_select_and_number():
    doc = CRNDocument(
        resource="http://ex.org/X",
        forms=(
            FormEntry(
                fid="f1",
                method="GET",
                label="Choose",
                uri_ref="<http://ex.org/form>",
                parameters=(("x", "select(a|b|c)"), ("n", "number")),
            ),
        ),
    )
    html = crn_to_html(doc)
    assert "<select" in html
    assert "number" in html or 'type="number"' in html
    assert "option" in html.lower()
