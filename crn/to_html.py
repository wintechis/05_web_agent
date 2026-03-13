"""Convert CRN document to HTML (spec 11.3). Full form type mapping (Resolved #7)."""

import re
from html import escape

from crn.model import CRNDocument
from crn.uri import expand_uri


def _escape(s: str) -> str:
    """Escape HTML entities."""
    return escape(s, quote=True)


def _form_param_to_html(name: str, type_str: str) -> str:
    """Return HTML for one form parameter (Resolved #7)."""
    type_str = type_str.strip().lower()
    if type_str.startswith("hidden("):
        m = re.match(r"hidden\s*\(\s*(.*)\s*\)", type_str, re.I)
        val = m.group(1).strip() if m else ""
        return f'<input type="hidden" name="{_escape(name)}" value="{_escape(val)}">'
    if type_str == "number":
        return f'<input type="number" name="{_escape(name)}">'
    if type_str == "uri":
        return f'<input type="url" name="{_escape(name)}">'
    if type_str.startswith("select("):
        m = re.match(r"select\s*\(\s*(.*)\s*\)", type_str, re.I)
        opts = [o.strip() for o in (m.group(1).split("|") if m else [])]
        parts = [f'<select name="{_escape(name)}">']
        for o in opts:
            parts.append(f"<option value=\"{_escape(o)}\">{_escape(o)}</option>")
        parts.append("</select>")
        return "\n".join(parts)
    return f'<input type="text" name="{_escape(name)}">'


def crn_to_html(doc: CRNDocument) -> str:
    """Serialize CRNDocument to a minimal HTML document."""
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head>")
    parts.append(f'<meta charset="UTF-8">')
    parts.append(f'<link rel="canonical" href="{_escape(doc.resource)}">')
    title = _escape(doc.label) if doc.label else "Untitled"
    parts.append(f"<title>{title}</title>")
    parts.append("</head><body>")
    parts.append(f"<h1>{title}</h1>")
    if doc.content is not None and doc.content.strip():
        link_by_id = {link.id: link for link in doc.links}
        paragraphs = doc.content.split("\n\n")
        parts.append("<article>")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # Split by [id] so we can escape text and inject <a> for refs
            segments = re.split(r"(?<!\\)\[(\d+)\]", para)
            p_parts: list[str] = []
            for i, seg in enumerate(segments):
                if i % 2 == 0:
                    p_parts.append(_escape(seg.replace("\n", " ")))
                else:
                    lid = int(seg)
                    link = link_by_id.get(lid)
                    if link:
                        uri = expand_uri(link.uri_ref, doc.prefixes)
                        p_parts.append(f'<a href="{_escape(uri)}">{_escape(link.label)}</a>')
                    else:
                        p_parts.append(_escape(f"[{lid}]"))
            parts.append("<p>" + "".join(p_parts) + "</p>")
        parts.append("</article>")
    if doc.properties:
        parts.append("<dl>")
        for p in doc.properties:
            key_display = f"{p.key} ({p.lang})" if p.lang else p.key
            parts.append(f"<dt>{_escape(key_display)}</dt>")
            parts.append(f"<dd>{_escape(p.value)}</dd>")
        parts.append("</dl>")
    # Links not referenced in content
    if doc.content:
        ref_ids = set(re.findall(r"(?<!\\)\[(\d+)\]", doc.content))
    else:
        ref_ids = set()
    unreferenced = [l for l in doc.links if l.id not in ref_ids]
    if unreferenced:
        parts.append("<nav><ul>")
        for link in unreferenced:
            uri = expand_uri(link.uri_ref, doc.prefixes)
            parts.append(f'<li><a href="{_escape(uri)}">{_escape(link.label)}</a></li>')
        parts.append("</ul></nav>")
    for form in doc.forms:
        action = expand_uri(form.uri_ref, doc.prefixes)
        parts.append(f'<form method="{_escape(form.method)}" action="{_escape(action)}">')
        for name, type_str in form.parameters:
            parts.append(_form_param_to_html(name, type_str))
        parts.append(f'<button type="submit">{_escape(form.label)}</button>')
        parts.append("</form>")
    parts.append("</body></html>")
    return "\n".join(parts)
