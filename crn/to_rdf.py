"""Convert CRN document to RDF Turtle (spec 11.4). Plain keys -> crn: (Resolved #1). Content predicate configurable (Resolved #2)."""

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

from crn.model import CRNDocument, CRN_PROPERTY_NS
from crn.uri import expand_uri

RDFS_COMMENT = str(RDFS.comment)
CRN_NS = Namespace(CRN_PROPERTY_NS)


def _key_to_uri(key: str, prefixes: dict[str, str]) -> str:
    """Return full URI for key. If key is prefixed (e.g. dbo:population), expand; if <full>, use as-is; else crn:key (Resolved #1)."""
    key = key.strip()
    if key.startswith("<") and key.endswith(">"):
        return key[1:-1]
    if ":" in key:
        prefix_part = key.split(":", 1)[0]
        if prefix_part in prefixes:
            return expand_uri(key, prefixes)
    # Plain key -> crn namespace
    safe = key.replace(" ", "_").replace(".", "_")
    return CRN_PROPERTY_NS + safe


def crn_to_turtle(
    doc: CRNDocument,
    content_predicate: str = RDFS_COMMENT,
) -> str:
    """Serialize CRNDocument to Turtle. content_predicate defaults to rdfs:comment (Resolved #2)."""
    g = Graph()
    subject = URIRef(doc.resource)
    prefixes_used = dict(doc.prefixes)
    g.bind("crn", CRN_NS)
    for pname, base in doc.prefixes.items():
        g.bind(pname, base)

    if doc.label is not None:
        g.add((subject, RDFS.label, Literal(doc.label)))
    for t in getattr(doc, "type", ()) or ():
        type_uri = expand_uri(t, doc.prefixes) if ":" in t else t
        if not type_uri.startswith("http"):
            type_uri = expand_uri(t, doc.prefixes)
        g.add((subject, RDF.type, URIRef(type_uri)))
    if doc.content is not None and doc.content.strip():
        g.add((subject, URIRef(content_predicate), Literal(doc.content)))
    for prop in doc.properties:
        pred_uri = _key_to_uri(prop.key, doc.prefixes)
        if prop.lang:
            g.add((subject, URIRef(pred_uri), Literal(prop.value, lang=prop.lang)))
        else:
            g.add((subject, URIRef(pred_uri), Literal(prop.value)))
    for link in doc.links:
        pred_uri = expand_uri(link.relationship, doc.prefixes)
        obj_uri = expand_uri(link.uri_ref, doc.prefixes)
        g.add((subject, URIRef(pred_uri), URIRef(obj_uri)))
    return g.serialize(format="turtle")


def crn_to_graph(doc: CRNDocument, content_predicate: str = RDFS_COMMENT) -> Graph:
    """Build rdflib Graph from CRNDocument. Same options as crn_to_turtle."""
    g = Graph()
    subject = URIRef(doc.resource)
    g.bind("crn", CRN_NS)
    for pname, base in doc.prefixes.items():
        g.bind(pname, base)
    if doc.label is not None:
        g.add((subject, RDFS.label, Literal(doc.label)))
    for t in getattr(doc, "type", ()) or ():
        type_uri = expand_uri(t, doc.prefixes) if ":" in t else t
        if not type_uri.startswith("http"):
            type_uri = expand_uri(t, doc.prefixes)
        g.add((subject, RDF.type, URIRef(type_uri)))
    if doc.content is not None and doc.content.strip():
        g.add((subject, URIRef(content_predicate), Literal(doc.content)))
    for prop in doc.properties:
        pred_uri = _key_to_uri(prop.key, doc.prefixes)
        if prop.lang:
            g.add((subject, URIRef(pred_uri), Literal(prop.value, lang=prop.lang)))
        else:
            g.add((subject, URIRef(pred_uri), Literal(prop.value)))
    for link in doc.links:
        pred_uri = expand_uri(link.relationship, doc.prefixes)
        obj_uri = expand_uri(link.uri_ref, doc.prefixes)
        g.add((subject, URIRef(pred_uri), URIRef(obj_uri)))
    return g
