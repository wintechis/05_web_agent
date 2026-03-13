"""Convert RDF (rdflib Graph or Turtle string) to CRN document (spec 11.2). Link order: by relationship (Resolved #5)."""

from collections import defaultdict
from rdflib import Graph, URIRef, Literal, BNode, Namespace
from rdflib.namespace import RDF, RDFS

from crn.model import CRNDocument, PropertyEntry, LinkEntry
from crn.uri import local_name_from_uri

RDFS_COMMENT = RDFS.comment
DBO_ABSTRACT = Namespace("http://dbpedia.org/ontology/").abstract

# Namespaces commonly used for content and types.
CONTENT_PREDICATES = (RDFS_COMMENT, DBO_ABSTRACT)


def _uri_to_ref(uri: str, prefixes: dict[str, str]) -> str:
    """Return prefixed form if base matches a prefix, else <full>."""
    for pname, base in prefixes.items():
        base = base.rstrip("#/")
        if uri.startswith(base + "/") or uri.startswith(base + "#"):
            local = uri[len(base) + 1 :] if uri[len(base)] in ("/", "#") else uri[len(base) :]
            return f"{pname}:{local}"
    return f"<{uri}>"


def _pick_prefixes(graph: Graph, target_uri: URIRef, uri_counts: dict[str, int]) -> dict[str, str]:
    """Choose prefixes for bases that appear 3+ times (spec 4.5). Return short -> base."""
    bases: dict[str, list[str]] = defaultdict(list)
    for uri in uri_counts:
        if uri_counts[uri] < 3:
            continue
        # Find base: strip fragment or last path segment
        if "#" in uri:
            base = uri.split("#")[0] + "#"
        else:
            base = uri.rsplit("/", 1)[0] + "/"
        bases[base].append(uri)
    # Assign short prefix (1-4 chars)
    known = {"dbr", "dbo", "rdf", "rdfs", "foaf", "dct", "skos", "owl", "xsd"}
    prefixes: dict[str, str] = {}
    for base in sorted(bases.keys(), key=lambda b: -sum(uri_counts[u] for u in bases[b])):
        cand = base.replace("http://", "").replace("https://", "").replace(".org/", "").replace(".org", "")
        cand = "".join(c for c in cand if c.isalnum())[:4].lower()
        if not cand:
            cand = "ns"
        while cand in known or cand in prefixes:
            cand = cand + "x" if cand[-1] != "x" else cand[:-1] + "y"
        known.add(cand)
        prefixes[cand] = base
    return prefixes


def graph_to_crn(graph: Graph, resource_uri: str) -> CRNDocument:
    """Build CRNDocument from rdflib Graph for the given subject resource_uri (absolute)."""
    if isinstance(resource_uri, URIRef):
        subject = resource_uri
        resource_str = str(resource_uri)
    else:
        resource_str = resource_uri.strip()
        subject = URIRef(resource_str)

    # Count URI occurrences for prefix heuristic
    uri_counts: dict[str, int] = defaultdict(int)
    for s, p, o in graph:
        for node in (s, p, o):
            if isinstance(node, URIRef):
                uri_counts[str(node)] += 1
    prefixes = _pick_prefixes(graph, subject, uri_counts)

    label_val: str | None = None
    for _, _, o in graph.triples((subject, RDFS.label, None)):
        if isinstance(o, Literal):
            label_val = str(o)
            break

    types: list[str] = []
    for _, _, o in graph.triples((subject, RDF.type, None)):
        if isinstance(o, URIRef):
            types.append(_uri_to_ref(str(o), prefixes))

    content_val: str | None = None
    for p in CONTENT_PREDICATES:
        for _, _, o in graph.triples((subject, p, None)):
            if isinstance(o, Literal):
                content_val = str(o)
                break
        if content_val is not None:
            break

    properties: list[PropertyEntry] = []
    link_triples: list[tuple[URIRef, URIRef]] = []  # (predicate, object)

    for _, p, o in graph.triples((subject, None, None)):
        if p in (RDF.type, RDFS.label):
            continue
        if p in CONTENT_PREDICATES:
            continue
        if isinstance(o, Literal):
            key = _uri_to_ref(str(p), prefixes)
            properties.append(PropertyEntry(key=key, value=str(o), lang=None))
        elif isinstance(o, BNode):
            for _, p2, o2 in graph.triples((o, None, None)):
                if isinstance(o2, Literal):
                    k1 = _uri_to_ref(str(p), prefixes).replace(":", "_")
                    k2 = _uri_to_ref(str(p2), prefixes).replace(":", "_")
                    properties.append(PropertyEntry(key=f"{k1}.{k2}", value=str(o2), lang=None))
        elif isinstance(o, URIRef):
            link_triples.append((p, o))

    # Link labels: rdfs:label of object if in graph, else local name
    def label_for(obj: URIRef) -> str:
        for _, _, lit in graph.triples((obj, RDFS.label, None)):
            if isinstance(lit, Literal):
                return str(lit)
        return local_name_from_uri(str(obj))

    # Resolved #5: order links by relationship type (predicate), then by object
    link_triples.sort(key=lambda x: (str(x[0]), str(x[1])))
    links = []
    for idx, (pred, obj) in enumerate(link_triples, start=1):
        rel_ref = _uri_to_ref(str(pred), prefixes)
        obj_ref = _uri_to_ref(str(obj), prefixes)
        links.append(LinkEntry(id=idx, relationship=rel_ref, label=label_for(obj), uri_ref=obj_ref))

    return CRNDocument(
        resource=resource_str,
        label=label_val,
        source="text/turtle",
        type=tuple(types),
        prefixes=prefixes,
        content=content_val,
        properties=tuple(properties),
        links=tuple(links),
        forms=(),
    )


def turtle_to_crn(turtle_text: str, resource_uri: str) -> CRNDocument:
    """Parse Turtle string into a Graph and return graph_to_crn(g, resource_uri)."""
    g = Graph()
    g.parse(data=turtle_text, format="turtle")
    return graph_to_crn(g, resource_uri)
