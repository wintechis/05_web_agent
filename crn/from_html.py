"""Convert HTML to CRN document (spec 11.1). Main content: first <main>, else first <article>, else <body> (Resolved #6)."""

import re
from bs4 import BeautifulSoup

from crn.model import CRNDocument, PropertyEntry, LinkEntry, FormEntry
from crn.uri import resolve_relative

# Section delimiters for consistency
SECTION_CONTENT = "== content =="
SECTION_LINKS = "== links =="
SECTION_FORMS = "== forms =="


def _main_content_container(soup: BeautifulSoup):
    """Return the main content element: first <main>, else first <article>, else <body> (Resolved #6)."""
    main = soup.find("main")
    if main is not None:
        return main
    article = soup.find("article")
    if article is not None:
        return article
    body = soup.find("body")
    if body is not None:
        return body
    return soup


def _text_with_link_refs(container, base_url: str) -> tuple[str, list[LinkEntry]]:
    """Walk container, collect text and replace <a href> with [id]. Return (content_text, links)."""
    links: list[LinkEntry] = []
    id_counter = [0]

    def walk(el):
        if getattr(el, "name", None) in ("style", "script"):
            return ""
        if el.name == "a" and el.get("href"):
            href = el.get("href", "").strip()
            if not href or href.startswith("#"):
                return ""
            abs_url = resolve_relative(href, base_url)
            id_counter[0] += 1
            lid = id_counter[0]
            label = (el.get_text(strip=True) or abs_url.split("/")[-1] or "link").replace("_", " ")
            links.append(LinkEntry(id=lid, relationship="href", label=label, uri_ref=f"<{abs_url}>"))
            return f"[{lid}]"
        if hasattr(el, "children"):
            return "".join(walk(c) for c in el.children)
        if isinstance(el, str):
            return el
        return ""

    text = walk(container)
    # Normalize whitespace and paragraph breaks
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text, links


def _all_links_outside_main(soup: BeautifulSoup, main_el, base_url: str) -> list[LinkEntry]:
    """Find <a href> outside main content; return as link entries (no [id] in content)."""
    main_link_ids = {id(a) for a in main_el.find_all("a", href=True)} if main_el else set()
    seen = set()
    result: list[LinkEntry] = []
    for a in soup.find_all("a", href=True):
        if id(a) in main_link_ids:
            continue
        href = a.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        abs_url = resolve_relative(href, base_url)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        label = (a.get_text(strip=True) or abs_url.split("/")[-1] or "link").replace("_", " ")
        result.append(
            LinkEntry(id=len(result) + 1, relationship="href", label=label, uri_ref=f"<{abs_url}>")
        )
    return result


def _properties_from_dl(soup: BeautifulSoup) -> list[PropertyEntry]:
    """Extract key-value from <dl><dt>key</dt><dd>value</dd></dl>."""
    props: list[PropertyEntry] = []
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for i, dt in enumerate(dts):
            key = dt.get_text(strip=True)
            value = dds[i].get_text(strip=True) if i < len(dds) else ""
            if key:
                props.append(PropertyEntry(key=key, value=value, lang=None))
    return props


def _properties_from_tables(soup: BeautifulSoup) -> list[PropertyEntry]:
    """Extract key-value from <table> with two columns."""
    props: list[PropertyEntry] = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key:
                    props.append(PropertyEntry(key=key, value=value, lang=None))
    return props


def _forms_from_html(soup: BeautifulSoup, base_url: str) -> list[FormEntry]:
    """Extract <form> into FormEntry list."""
    forms: list[FormEntry] = []
    for idx, form in enumerate(soup.find_all("form"), start=1):
        method = (form.get("method") or "GET").upper()
        action = form.get("action", "").strip()
        action_url = resolve_relative(action, base_url) if action else base_url
        label = form.get("aria-label") or f"Form {idx}"
        params: list[tuple[str, str]] = []
        for inp in form.find_all(["input", "select", "textarea"]):
            name = inp.get("name")
            if not name:
                continue
            if inp.name == "input":
                typ = inp.get("type", "text").lower()
                if typ == "hidden":
                    val = inp.get("value", "")
                    params.append((name, f"hidden({val})"))
                elif typ in ("text", "search", "email"):
                    params.append((name, "text"))
                elif typ == "number":
                    params.append((name, "number"))
                elif typ == "url":
                    params.append((name, "uri"))
                else:
                    params.append((name, "text"))
            elif inp.name == "select":
                opts = inp.find_all("option")
                if opts:
                    vals = [o.get("value") or o.get_text(strip=True) for o in opts]
                    params.append((name, f"select({'|'.join(vals)})"))
                else:
                    params.append((name, "text"))
            else:
                params.append((name, "text"))
        forms.append(
            FormEntry(
                fid=f"f{idx}",
                method=method,
                label=label,
                uri_ref=f"<{action_url}>",
                parameters=tuple(params),
            )
        )
    return forms


def html_to_crn(html_text: str, resource_uri: str) -> CRNDocument:
    """Build CRNDocument from HTML string. resource_uri is the page URL (used for @resource and resolving relative links)."""
    soup = BeautifulSoup(html_text, "html.parser")
    base_url = resource_uri.strip()
    main_el = _main_content_container(soup)
    content_text, content_links = _text_with_link_refs(main_el, base_url)
    other_links = _all_links_outside_main(soup, main_el, base_url)
    # Merge links: content_links first (they have [id] in content), then others with new ids
    all_links = list(content_links)
    start_id = len(all_links) + 1
    for i, le in enumerate(other_links):
        all_links.append(LinkEntry(id=start_id + i, relationship=le.relationship, label=le.label, uri_ref=le.uri_ref))
    label = None
    if soup.title and soup.title.string:
        label = soup.title.get_text(strip=True)
    if not label and soup.find("h1"):
        label = soup.find("h1").get_text(strip=True)
    props = _properties_from_dl(soup) + _properties_from_tables(soup)
    forms = _forms_from_html(soup, base_url)
    return CRNDocument(
        resource=base_url,
        label=label,
        source="text/html",
        type=(),
        prefixes={},
        content=content_text if content_text.strip() else None,
        properties=tuple(props),
        links=tuple(all_links),
        forms=tuple(forms),
    )
