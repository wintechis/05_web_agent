"""Tests for HTML → CRN (html_to_crn)."""

import pytest
from crn import html_to_crn


def test_html_to_crn_minimal():
    html = """<!DOCTYPE html><html><head><title>Page</title></head><body><p>Hello.</p></body></html>"""
    doc = html_to_crn(html, "https://example.org/page")
    assert doc.resource == "https://example.org/page"
    assert doc.label == "Page"
    assert doc.content is not None
    assert "Hello" in doc.content


def test_html_to_crn_main_precedence():
    html = """
    <html><head><title>T</title></head><body>
    <main><p>In main.</p></main>
    <article><p>In article.</p></article>
    </body></html>
    """
    doc = html_to_crn(html, "https://ex.org/")
    assert "In main" in (doc.content or "")


def test_html_to_crn_link_in_content():
    html = """
    <html><head><title>T</title></head><body>
    <p>See <a href="/wiki/Germany">Germany</a>.</p>
    </body></html>
    """
    doc = html_to_crn(html, "https://example.org/page")
    assert doc.content is not None
    assert "[1]" in doc.content
    assert len(doc.links) >= 1
    assert doc.links[0].label == "Germany"


def test_html_to_crn_form():
    html = """
    <html><body>
    <form method="GET" action="/search">
    <input type="text" name="q">
    <input type="hidden" name="lang" value="en">
    </form>
    </body></html>
    """
    doc = html_to_crn(html, "https://ex.org/")
    assert len(doc.forms) == 1
    assert doc.forms[0].method == "GET"
    assert "search" in doc.forms[0].uri_ref
    assert any(n == "q" for n, _ in doc.forms[0].parameters)
    assert any("hidden" in t for _, t in doc.forms[0].parameters)
