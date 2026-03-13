"""Serialize CRNDocument to CRN text. Output is Unicode str (LF). Escape only \" \\ [ ] (spec 10.3)."""

from crn.model import CRNDocument, PropertyEntry, LinkEntry, FormEntry


def _escape_content(s: str) -> str:
    """Escape only \\ " [ ] for content/labels (spec 10.3)."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("[", "\\[").replace("]", "\\]")


def _format_uri_ref(uri_ref: str) -> str:
    """Format uri_ref for output: if it contains : and no spaces, use as-is; else wrap in <> if needed."""
    uri_ref = uri_ref.strip()
    if uri_ref.startswith("<") and uri_ref.endswith(">"):
        return uri_ref
    if " " in uri_ref or uri_ref.startswith("<"):
        if not uri_ref.startswith("<"):
            return f"<{uri_ref}>"
    return uri_ref


def serialize(doc: CRNDocument) -> str:
    """Serialize CRN document to text. Returns Unicode str with LF line endings."""
    lines: list[str] = []
    lines.append(f"@resource <{doc.resource.strip()}>")
    if doc.label is not None:
        lines.append(f'@label "{_escape_content(doc.label)}"')
    if doc.source is not None:
        lines.append(f"@source {doc.source}")
    type_attrs = getattr(doc, "type", ())
    if type_attrs:
        lines.append("@type " + ", ".join(type_attrs))
    for prefix_name, base in sorted(doc.prefixes.items()):
        base = base.strip()
        if not (base.startswith("<") and base.endswith(">")):
            base = f"<{base}>"
        lines.append(f"@prefix {prefix_name}: {base}")
    if doc.content is not None and doc.content.strip():
        lines.append("")
        lines.append("== content ==")
        lines.append(_escape_content(doc.content))
    if doc.properties:
        lines.append("")
        lines.append("== properties ==")
        for p in doc.properties:
            if p.lang:
                lines.append(f"{p.key} ({p.lang}): {p.value}")
            else:
                lines.append(f"{p.key}: {p.value}")
    if doc.links:
        lines.append("")
        lines.append("== links ==")
        for link in doc.links:
            uri = _format_uri_ref(link.uri_ref)
            lines.append(f'[{link.id}] {link.relationship} "{_escape_content(link.label)}" {uri}')
    if doc.forms:
        lines.append("")
        lines.append("== forms ==")
        for form in doc.forms:
            params_str = ", ".join(f"{n}: {t}" for n, t in form.parameters)
            uri = _format_uri_ref(form.uri_ref)
            lines.append(f'[{form.fid}] {form.method} "{_escape_content(form.label)}" {uri} {{{params_str}}}')
    return "\n".join(lines).strip() + "\n"
