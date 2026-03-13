"""Parse CRN text to CRNDocument. Input is Unicode str (UTF-8 decoded). Unknown escapes: literal backslash + char (Resolved #11)."""

import re
from crn.model import CRNDocument, PropertyEntry, LinkEntry, FormEntry

# Section delimiters (order fixed per spec).
SECTION_CONTENT = "== content =="
SECTION_PROPERTIES = "== properties =="
SECTION_LINKS = "== links =="
SECTION_FORMS = "== forms =="
SECTION_DELIMITERS = (SECTION_CONTENT, SECTION_PROPERTIES, SECTION_LINKS, SECTION_FORMS)

# Header: @resource <uri>, @label "...", @source x, @type a, b, @prefix p: <base>
RESOURCE_RE = re.compile(r"^@resource\s+<([^>]+)>")
LABEL_RE = re.compile(r'^@label\s+"((?:[^"\\]|\\.)*)"')
SOURCE_RE = re.compile(r"^@source\s+(.+)$")
TYPE_RE = re.compile(r"^@type\s+(.+)$")
PREFIX_RE = re.compile(r"^@prefix\s+([a-zA-Z0-9]+):\s+<([^>]+)>")

# Link line: [id] relationship "label" uri-ref
LINK_LINE_RE = re.compile(
    r'^\s*\[(\d+)\]\s+(\S+)\s+"((?:[^"\\]|\\.)*)"\s+(\S+(?:\s+\S+)*)\s*$'
)
# Form line: [fid] METHOD "label" uri-ref {params}
FORM_LINE_RE = re.compile(
    r'^\s*\[(f\d+)\]\s+(GET|POST|PUT|DELETE)\s+"((?:[^"\\]|\\.)*)"\s+(\S+)\s+\{(.+)\}\s*$'
)
# Property key (lang): key or key (lang)
KEY_LANG_RE = re.compile(r"^(.+?)\s+\(([a-zA-Z\-]+)\)\s*$")


class CRNParseError(ValueError):
    """Raised when CRN text is invalid (missing @resource, wrong order, invalid [id] refs)."""

    pass


def _unescape_content(s: str) -> str:
    """Unescape \\", \\[, \\], \\\\. Unknown \\X -> literal \\ + X (Resolved #11)."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == '"':
                out.append('"')
            elif n == "[":
                out.append("[")
            elif n == "]":
                out.append("]")
            elif n == "\\":
                out.append("\\")
            else:
                out.append("\\")
                out.append(n)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _unescape_quoted(s: str) -> str:
    """Unescape only \\" and \\\\ inside a quoted string."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == '"' or n == "\\":
                out.append(n)
            else:
                out.append("\\")
                out.append(n)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _parse_header(lines: list[str]) -> tuple[dict[str, str], int]:
    """Parse header lines; return (header dict with resource, label, source, type, prefixes), next index."""
    resource: str | None = None
    label: str | None = None
    source: str | None = None
    type_str: str | None = None
    prefixes: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("=="):
            break
        if not line.startswith("@"):
            i += 1
            continue
        if line.startswith("@resource"):
            m = RESOURCE_RE.match(line)
            if not m:
                raise CRNParseError(f"Invalid @resource line: {line!r}")
            resource = m.group(1).strip()
        elif line.startswith("@label"):
            m = LABEL_RE.match(line)
            if m:
                label = _unescape_quoted(m.group(1))
        elif line.startswith("@source"):
            m = SOURCE_RE.match(line)
            if m:
                source = m.group(1).strip()
        elif line.startswith("@type"):
            m = TYPE_RE.match(line)
            if m:
                type_str = m.group(1).strip()
        elif line.startswith("@prefix"):
            m = PREFIX_RE.match(line)
            if m:
                prefixes[m.group(1)] = m.group(2).strip()
        i += 1
    if resource is None:
        raise CRNParseError("Missing required @resource")
    type_list = [t.strip() for t in type_str.split(",")] if type_str else []
    out: dict[str, str | list[str] | dict[str, str]] = {"resource": resource, "type_list": type_list, "prefixes": prefixes}
    if label is not None:
        out["label"] = label
    if source is not None:
        out["source"] = source
    return out, i


def _section_body(lines: list[str], start: int, end_markers: tuple[str, ...]) -> tuple[str, int]:
    """Collect body until next section or EOF. Return (body text, next index)."""
    parts: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        for m in end_markers:
            if line.strip() == m:
                return "\n".join(parts).rstrip(), i
        parts.append(line)
        i += 1
    return "\n".join(parts).rstrip(), i


def _parse_property_line(line: str) -> PropertyEntry:
    """Parse 'key: value' or 'key (lang): value' into PropertyEntry."""
    if ": " not in line:
        return PropertyEntry(key=line.strip(), value="", lang=None)
    idx = line.index(": ")
    left = line[:idx].strip()
    value = line[idx + 2 :].strip()
    m = KEY_LANG_RE.match(left)
    if m:
        key = m.group(1).strip()
        lang = m.group(2).strip()
        return PropertyEntry(key=key, value=value, lang=lang)
    return PropertyEntry(key=left, value=value, lang=None)


def _parse_links_body(body: str) -> list[LinkEntry]:
    """Parse links section body into list of LinkEntry."""
    entries: list[LinkEntry] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        m = LINK_LINE_RE.match(line)
        if not m:
            continue
        link_id = int(m.group(1))
        rel = m.group(2)
        label = _unescape_quoted(m.group(3))
        uri_ref = m.group(4).strip()
        entries.append(LinkEntry(id=link_id, relationship=rel, label=label, uri_ref=uri_ref))
    return entries


def _parse_form_params(params_str: str) -> tuple[tuple[str, str], ...]:
    """Parse {name: type, name2: type2} into ((name, type), ...)."""
    params_str = params_str.strip()
    if not params_str:
        return ()
    result: list[tuple[str, str]] = []
    for part in params_str.split(","):
        part = part.strip()
        if ": " in part:
            idx = part.index(": ")
            name = part[:idx].strip()
            typ = part[idx + 2 :].strip()
            result.append((name, typ))
    return tuple(result)


def _parse_forms_body(body: str) -> list[FormEntry]:
    """Parse forms section body into list of FormEntry."""
    entries: list[FormEntry] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        m = FORM_LINE_RE.match(line)
        if not m:
            continue
        fid = m.group(1)
        method = m.group(2)
        label = _unescape_quoted(m.group(3))
        uri_ref = m.group(4).strip()
        params = _parse_form_params(m.group(5))
        entries.append(
            FormEntry(fid=fid, method=method, label=label, uri_ref=uri_ref, parameters=params)
        )
    return entries


def _content_ref_ids(content: str) -> list[int]:
    """Return list of [id] references in content, in order of appearance."""
    refs: list[int] = []
    # Match [number] but not \[number\]
    pattern = re.compile(r"(?<!\\)\[(\d+)\]")
    for m in pattern.finditer(content):
        refs.append(int(m.group(1)))
    return refs


def parse(text: str) -> CRNDocument:
    """Parse CRN text to CRNDocument. Input must be Unicode str. Validates [id] refs (Resolved #8)."""
    if not isinstance(text, str):
        raise TypeError("CRN parser expects Unicode str; decode from UTF-8 if you have bytes")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header_data, i = _parse_header(lines)
    resource = header_data["resource"]
    label = header_data.get("label")
    source = header_data.get("source")
    type_list = header_data.get("type_list", [])
    prefixes = header_data.get("prefixes", {})

    content: str | None = None
    properties: list[PropertyEntry] = []
    links: list[LinkEntry] = []
    forms: list[FormEntry] = []
    seen_sections: list[str] = []

    while i < len(lines):
        line = lines[i].strip()
        if line == SECTION_CONTENT:
            if SECTION_CONTENT in seen_sections:
                raise CRNParseError("Section == content == must appear at most once")
            if seen_sections:
                raise CRNParseError("Sections must appear in order: content, properties, links, forms")
            seen_sections.append(SECTION_CONTENT)
            i += 1
            body, i = _section_body(lines, i, SECTION_DELIMITERS)
            content = _unescape_content(body).strip() if body.strip() else None
        elif line == SECTION_PROPERTIES:
            if SECTION_PROPERTIES in seen_sections:
                raise CRNParseError("Section == properties == must appear at most once")
            if SECTION_LINKS in seen_sections or SECTION_FORMS in seen_sections:
                raise CRNParseError("Sections must appear in order: content, properties, links, forms")
            seen_sections.append(SECTION_PROPERTIES)
            i += 1
            body, i = _section_body(lines, i, SECTION_DELIMITERS)
            for ln in body.splitlines():
                ln = ln.strip()
                if ln:
                    properties.append(_parse_property_line(ln))
        elif line == SECTION_LINKS:
            if SECTION_LINKS in seen_sections:
                raise CRNParseError("Section == links == must appear at most once")
            if SECTION_FORMS in seen_sections:
                raise CRNParseError("Sections must appear in order: content, properties, links, forms")
            seen_sections.append(SECTION_LINKS)
            i += 1
            body, i = _section_body(lines, i, SECTION_DELIMITERS)
            links = _parse_links_body(body)
        elif line == SECTION_FORMS:
            if SECTION_FORMS in seen_sections:
                raise CRNParseError("Section == forms == must appear at most once")
            seen_sections.append(SECTION_FORMS)
            i += 1
            body, i = _section_body(lines, i, SECTION_DELIMITERS)
            forms = _parse_forms_body(body)
        else:
            i += 1

    link_ids = {le.id for le in links}
    if content:
        ref_ids = _content_ref_ids(content)
        for rid in ref_ids:
            if rid not in link_ids:
                raise CRNParseError(
                    f"Content references [id]={rid} but links section has no such entry"
                )

    return CRNDocument(
        resource=resource,
        label=label,
        source=source,
        type=tuple(type_list),
        prefixes=prefixes,
        content=content or None,
        properties=tuple(properties),
        links=tuple(links),
        forms=tuple(forms),
    )
