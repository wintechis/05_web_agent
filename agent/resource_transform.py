"""Resource transformation variants for the GET tool (URI rewriting, RDF pruning, serialization)."""

import json
import logging
import os
import re
from rdflib import Graph, Namespace, URIRef
from pyld import jsonld
from markdownify import markdownify as md

from crn import graph_to_crn, html_to_crn, serialize

logger = logging.getLogger(__name__)

# Config: env keys and defaults
ENV_MODIFY_CONTEXT = "MODIFY_CONTEXT"
ENV_REPRESENTATION_FORMAT = "REPRESENTATION_FORMAT"
ENV_CONTEXT = "CONTEXT"
ENV_RDF_REPRESENTATION = "RDF_REPRESENTATION"
ENV_PRUNING_METHOD = "PRUNING_METHOD"

DEFAULT_REPRESENTATION_FORMAT = "wikitext"
DEFAULT_CONTEXT = "modified"
DEFAULT_RDF_REPRESENTATION = "html"
DEFAULT_PRUNING_METHOD = "unpruned"

REPRESENTATION_FORMATS = ("rdf", "wikitext", "html", "crn")
CONTEXT_VALUES = ("raw", "modified")
RDF_REPRESENTATIONS = ("html", "json-ld", "turtle", "turtle-compact", "turtle-terser", "json-ld-compact")
PRUNING_METHODS = ("unpruned", "outgoing-only", "in-and-outgoing")

# Namespaces
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
DBO = Namespace("http://dbpedia.org/ontology/")
DBR = Namespace("http://dbpedia.org/resource/")
DBC = Namespace("http://dbpedia.org/resource/Category:")
DCT = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
SCHEMA = Namespace("http://schema.org/")
DUL = Namespace("http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#")
WIKIDATA = Namespace("http://www.wikidata.org/entity/")

ALLOWED_PREDICATES = {
    RDF.type,
    DBO.type,
    DCT.subject,
    DBO.wikiPageWikiLink,
    FOAF.isPrimaryTopicOf,
    SKOS.closeMatch,
    SKOS.broadMatch,
    SKOS.exactMatch,
    SKOS.relatedMatch,
    RDFS.label,
}

NAMESPACES = {
    "foaf": "http://xmlns.com/foaf/0.1/",
    "wikipedia-en": "http://en.wikipedia.org/wiki/",
    "dbr": "http://dbpedia.org/resource/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "wikidata": "http://www.wikidata.org/entity/",
    "dbo": "http://dbpedia.org/ontology/",
    "schema": "http://schema.org/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "dul": "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#",
    "yago-res": "http://yago-knowledge.org/resource/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "prov": "http://www.w3.org/ns/prov#",
    "dct": "http://purl.org/dc/terms/",
    "dbc": "http://dbpedia.org/resource/Category:",
    "dbp": "http://dbpedia.org/property/",
    "dbd": "http://dbpedia.org/datatype/",
    "dbt": "http://dbpedia.org/resource/Template:",
    "gold": "http://purl.org/linguistics/gold/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}

JSON_LD_CONTEXT = {
    "foaf": "http://xmlns.com/foaf/0.1/",
    "wikipedia-en": "http://en.wikipedia.org/wiki/",
    "dbr": "http://dbpedia.org/resource/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "wikidata": "http://www.wikidata.org/entity/",
    "dbo": "http://dbpedia.org/ontology/",
    "schema": "http://schema.org/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "dul": "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#",
    "yago-res": "http://yago-knowledge.org/resource/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "prov": "http://www.w3.org/ns/prov#",
    "dct": "http://purl.org/dc/terms/",
    "dbc": "http://dbpedia.org/resource/Category:",
    "dbp": "http://dbpedia.org/property/",
    "dbd": "http://dbpedia.org/datatype/",
    "dbt": "http://dbpedia.org/resource/Template:",
    "gold": "http://purl.org/linguistics/gold/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "isPrimaryTopicOf": {"@id": "http://xmlns.com/foaf/0.1/isPrimaryTopicOf", "@type": "@id"},
    "hypernym": {"@id": "http://purl.org/linguistics/gold/hypernym", "@type": "@id"},
    "homepage": {"@id": "http://xmlns.com/foaf/0.1/homepage", "@type": "@id"},
    "sameAs": {"@id": "http://www.w3.org/2002/07/owl#sameAs", "@type": "@id"},
    "wasDerivedFrom": {"@id": "http://www.w3.org/ns/prov#wasDerivedFrom", "@type": "@id"},
    "broader": {"@id": "http://www.w3.org/2004/02/skos/core#broader", "@type": "@id"},
    "narrower": {"@id": "http://www.w3.org/2004/02/skos/core#narrower", "@type": "@id"},
    "related": {"@id": "http://www.w3.org/2004/02/skos/core#related", "@type": "@id"},
    "website": {"@id": "http://dbpedia.org/property/website", "@type": "@id"},
    "wikiPageExternalLink": {"@id": "http://dbpedia.org/ontology/wikiPageExternalLink", "@type": "@id"},
    "wikiPageWikiLink": {"@id": "http://dbpedia.org/ontology/wikiPageWikiLink", "@type": "@id"},
    "subject": {"@id": "http://purl.org/dc/terms/subject", "@type": "@id"},
    "wikiPageUsesTemplate": {"@id": "http://dbpedia.org/property/wikiPageUsesTemplate", "@type": "@id"},
    "label": {"@id": "http://www.w3.org/2000/01/rdf-schema#label"},
    "description": {"@id": "http://dbpedia.org/ontology/description"},
}


def get_modify_context() -> bool:
    """Return True if MODIFY_CONTEXT env is enabled (e.g. 'true')."""
    val = os.environ.get(ENV_MODIFY_CONTEXT, "").strip().lower()
    return val in ("true", "1", "yes")


def get_representation_format() -> str:
    """Return REPRESENTATION_FORMAT from env; default wikitext."""
    val = os.environ.get(ENV_REPRESENTATION_FORMAT, DEFAULT_REPRESENTATION_FORMAT).strip().lower()
    if val not in REPRESENTATION_FORMATS:
        raise ValueError(
            f"Invalid {ENV_REPRESENTATION_FORMAT}={val!r}; allowed: {REPRESENTATION_FORMATS}"
        )
    return val


def get_context() -> str:
    """Return CONTEXT from env; default modified."""
    val = os.environ.get(ENV_CONTEXT, DEFAULT_CONTEXT).strip().lower()
    if val not in CONTEXT_VALUES:
        raise ValueError(f"Invalid {ENV_CONTEXT}={val!r}; allowed: {CONTEXT_VALUES}")
    return val


def get_rdf_representation_env() -> str:
    """Return RDF_REPRESENTATION from env; default html."""
    val = os.environ.get(ENV_RDF_REPRESENTATION, DEFAULT_RDF_REPRESENTATION).strip().lower()
    if val not in RDF_REPRESENTATIONS:
        raise ValueError(
            f"Invalid {ENV_RDF_REPRESENTATION}={val!r}; allowed: {RDF_REPRESENTATIONS}"
        )
    return val


def get_pruning_method() -> str:
    """Return PRUNING_METHOD from env; default unpruned."""
    val = os.environ.get(ENV_PRUNING_METHOD, DEFAULT_PRUNING_METHOD).strip().lower()
    if val not in PRUNING_METHODS:
        raise ValueError(f"Invalid {ENV_PRUNING_METHOD}={val!r}; allowed: {PRUNING_METHODS}")
    return val


def get_dbpedia_resource_uri(uri: str) -> str:
    """Return DBpedia resource URI for the given URI (local name from path)."""
    return f"http://dbpedia.org/resource/{uri.split('/')[-1]}"


# Regex patterns for normalizing DBpedia URL variants to canonical resource URIs.
# Matches: http(s)://dbpedia.org/data/<local>[.<ext>]
_DBPEDIA_DATA_RE = re.compile(r"https?://dbpedia\.org/data/([^.]+)(\.\w+)?$")
# Matches: http(s)://dbpedia.org/page/<local>
_DBPEDIA_PAGE_RE = re.compile(r"https?://dbpedia\.org/page/(.+)$")


def _normalize_dbpedia_uri(uri: str) -> str:
    """Normalize DBpedia URL variants back to canonical resource URI.

    Handles:
      http://dbpedia.org/data/X.ttl    → http://dbpedia.org/resource/X
      http://dbpedia.org/data/X.json   → http://dbpedia.org/resource/X
      https://dbpedia.org/page/X       → http://dbpedia.org/resource/X
    Canonical http://dbpedia.org/resource/X is returned unchanged.
    """
    m = _DBPEDIA_DATA_RE.match(uri)
    if m:
        return f"http://dbpedia.org/resource/{m.group(1)}"
    m = _DBPEDIA_PAGE_RE.match(uri)
    if m:
        return f"http://dbpedia.org/resource/{m.group(1)}"
    return uri


def modify_uri(uri: str) -> str:
    """Return the URL to fetch based on REPRESENTATION_FORMAT and RDF_REPRESENTATION."""
    fmt = get_representation_format()
    if fmt == "rdf":
        uri = _normalize_dbpedia_uri(uri)
        rdf_repr = get_rdf_representation_env()
        local = uri.split("/")[-1]
        if rdf_repr == "html":
            return f"https://dbpedia.org/page/{local}"
        return f"http://dbpedia.org/data/{local}.ttl"
    if fmt == "crn":
        if "dbpedia.org" in uri:
            uri = _normalize_dbpedia_uri(uri)
            local = uri.split("/")[-1]
            return f"http://dbpedia.org/data/{local}.ttl"
        if "wikipedia.org" in uri:
            local = uri.split("/")[-1]
            return f"https://en.wikipedia.org/api/rest_v1/page/html/{local}"
        return uri
    if fmt == "wikitext":
        local = uri.split("/")[-1]
        return f"https://en.wikipedia.org/api/rest_v1/page/html/{local}"
    if fmt == "html":
        return uri
    return uri


def _accept_header_for_rdf_representation() -> str:
    """Return Accept header value when MODIFY_CONTEXT is true."""
    if get_rdf_representation_env() == "html":
        return "text/html, application/xhtml+xml, application/xml;q=0.9"
    return (
        "text/turtle;q=1, application/ld+json;q=0.99, application/rdf+xml;q=0.99, "
        "application/n-triples;q=0.99, application/activity+json;q=0.99, "
        "application/hal+json;q=0.975, application/json;q=0.95, application/atom+xml;q=0.9, "
        "application/xml;q=0.85"
    )


def get_accept_header_when_modify_context(fetch_url: str | None = None) -> str:
    """Return the Accept header to use for the GET request when MODIFY_CONTEXT is true.
    When REPRESENTATION_FORMAT is crn, fetch_url is used to choose Turtle (DBpedia) or HTML (Wikipedia).
    """
    fmt = get_representation_format()
    if fmt == "crn" and fetch_url:
        if "dbpedia.org" in fetch_url:
            return (
                "text/turtle;q=1, application/ld+json;q=0.99, application/rdf+xml;q=0.99, "
                "application/n-triples;q=0.99, application/activity+json;q=0.99, "
                "application/hal+json;q=0.975, application/json;q=0.95, application/atom+xml;q=0.9, "
                "application/xml;q=0.85"
            )
        if "wikipedia.org" in fetch_url:
            return "text/html, application/xhtml+xml, application/xml;q=0.9"
    return _accept_header_for_rdf_representation()


def is_allowed_uri(uri_ref: URIRef) -> bool:
    """Return True if the URI is from dbpedia.org or wikipedia.org."""
    if not isinstance(uri_ref, URIRef):
        return False
    uri_str = str(uri_ref)
    return "dbpedia.org" in uri_str or "wikipedia.org" in uri_str


def initialize_graph() -> Graph:
    """Create and bind namespaces for the result graph."""
    g = Graph()
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    g.bind("dbo", DBO)
    g.bind("dbr", DBR)
    g.bind("dbc", DBC)
    g.bind("dct", DCT)
    g.bind("foaf", FOAF)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.bind("schema", SCHEMA)
    g.bind("dul", DUL)
    g.bind("wd", WIKIDATA)
    return g


def prune_graph_by_in_and_outgoing_resources(
    g: Graph, target_uris: set, result_graph: Graph
) -> Graph:
    """Keep triples where subject or object is in target_uris and predicate is allowed."""
    g_res = initialize_graph()
    for subject, predicate, obj in g:
        if subject in target_uris and predicate in ALLOWED_PREDICATES:
            if isinstance(obj, URIRef) and is_allowed_uri(obj):
                g_res.add((subject, predicate, obj))
            elif not isinstance(obj, URIRef):
                g_res.add((subject, predicate, obj))
        if obj in target_uris and predicate in ALLOWED_PREDICATES:
            if isinstance(subject, URIRef) and is_allowed_uri(subject):
                g_res.add((subject, predicate, obj))
    return g_res


def prune_graph_by_outgoing_resources_only(
    g: Graph, target_uris: set, result_graph: Graph
) -> Graph:
    """Keep triples where subject is in target_uris (outgoing only)."""
    g_res = initialize_graph()
    for subject, predicate, obj in g:
        if subject not in target_uris and predicate in ALLOWED_PREDICATES:
            continue
        g_res.add((subject, predicate, obj))
    return g_res


def remove_white_spaces(serialized_graph: str) -> str:
    """Remove unnecessary whitespace and newlines."""
    return re.sub(r"\s+", " ", serialized_graph).strip()


def turtle_terser_version(g: Graph) -> str:
    """Convert an RDF graph to a human-readable terser turtle-style string."""
    mapping: dict[str, str] = {}

    def _apply_namespace_transformation(
        uri: str, prefix: str, local_name: str, is_predicate: bool = False
    ) -> str:
        if prefix == "dbc":
            return f"Category of {local_name}"
        if prefix == "dbt":
            return f"Template for {local_name}"
        if prefix == "dbo":
            return f"has {local_name}" if is_predicate else local_name
        if prefix == "dbr":
            if "Category:" in uri:
                return f"Category of {local_name.replace('Category:', '')}"
            if "Template:" in uri:
                return f"Template for {local_name.replace('Template:', '')}"
            if "Property:" in uri:
                return f"Property of {local_name.replace('Property:', '')}"
            if "Class:" in uri:
                return f"has class {local_name.replace('Class:', '')}"
            return local_name
        return local_name

    def _apply_legacy_transformation(uri: str, is_predicate: bool = False) -> str:
        if "dbpedia.org/resource/Category:" in uri:
            return uri.replace("http://dbpedia.org/resource/Category:", "Category of ")
        if "dbpedia.org/resource/Template:" in uri:
            return uri.replace("http://dbpedia.org/resource/Template:", "Template for ")
        if "dbpedia.org/resource/Property:" in uri:
            return uri.replace("http://dbpedia.org/resource/Property:", "Property of ")
        if "dbpedia.org/ontology/" in uri:
            return (
                uri.replace("http://dbpedia.org/ontology/", "has ")
                if is_predicate
                else uri.replace("http://dbpedia.org/ontology/", "")
            )
        if "dbpedia.org/resource/Class:" in uri:
            return uri.replace("http://dbpedia.org/resource/Class:", "has class ")
        if "dbpedia.org/resource/" in uri:
            return uri.replace("http://dbpedia.org/resource/", "")
        return uri

    def add_mapping_subject_object(uri: str) -> str:
        if uri in mapping:
            return mapping[uri]
        uri_replacement = None
        for prefix, namespace in NAMESPACES.items():
            if uri.startswith(namespace):
                local_name = uri[len(namespace) :]
                uri_replacement = _apply_namespace_transformation(
                    uri, prefix, local_name, is_predicate=False
                )
                break
        if uri_replacement is None:
            uri_replacement = _apply_legacy_transformation(uri, is_predicate=False)
        uri_replacement = uri_replacement.replace("_", " ")
        mapping[uri] = uri_replacement
        return uri_replacement

    def add_mapping_predicate(uri: str) -> str:
        if uri in mapping:
            return mapping[uri]
        uri_replacement = None
        for prefix, namespace in NAMESPACES.items():
            if uri.startswith(namespace):
                local_name = uri[len(namespace) :]
                uri_replacement = _apply_namespace_transformation(
                    uri, prefix, local_name, is_predicate=True
                )
                break
        if uri_replacement is None:
            uri_replacement = _apply_legacy_transformation(uri, is_predicate=True)
        uri_replacement = uri_replacement.replace("_", " ")
        mapping[uri] = uri_replacement
        return uri_replacement

    def format_term(label: str, term: object, uri_seen: set[str]) -> str:
        """Format one term: [label](uri) the first time uri appears, else [label]."""
        uri_str = str(term)
        if uri_str in uri_seen:
            return f"[{label}]"
        uri_seen.add(uri_str)
        return f"[{label}]({uri_str})"

    lines: list[str] = []
    uri_seen: set[str] = set()
    for s, p, o in g.triples((None, None, None)):
        subject = mapping.get(str(s)) or add_mapping_subject_object(str(s))
        predicate = mapping.get(str(p)) or add_mapping_predicate(str(p))
        object_val = mapping.get(str(o)) or add_mapping_subject_object(str(o))
        subj_str = format_term(subject, s, uri_seen)
        pred_str = format_term(predicate, p, uri_seen)
        obj_str = format_term(object_val, o, uri_seen)
        lines.append(f"{subj_str} {pred_str} {obj_str}\n")
    return "".join(lines)


def get_compact_turtle(result_graph: Graph) -> str:
    """Serialize graph to turtle and collapse whitespace."""
    return remove_white_spaces(result_graph.serialize(format="turtle"))


def get_terser_turtle(result_graph: Graph) -> str:
    """Serialize graph to human-readable terser format."""
    return turtle_terser_version(result_graph)


def get_compact_json_ld(g: Graph) -> str:
    """Serialize graph to JSON-LD and compact with context."""
    data = json.loads(g.serialize(format="json-ld", indent=4))
    compacted = jsonld.compact(data, JSON_LD_CONTEXT)
    return json.dumps(compacted, indent=2, ensure_ascii=False)


def get_json_ld(result_graph: Graph) -> str:
    """Serialize graph to JSON-LD."""
    return result_graph.serialize(format="json-ld", indent=4)


def get_turtle(result_graph: Graph) -> str:
    """Serialize graph to turtle."""
    return result_graph.serialize(format="turtle")


def get_rdf_representation(resource_representation: str, uri: str) -> str:
    """Transform RDF body: optionally prune and serialize per RDF_REPRESENTATION."""
    configured_rdf = get_rdf_representation_env()
    pruning = get_pruning_method()

    if configured_rdf == "html":
        return md(resource_representation)

    g = Graph()
    g.parse(data=resource_representation, format="turtle")

    http_uri = URIRef(uri.replace("https://", "http://"))
    https_uri = URIRef(uri.replace("http://", "https://"))
    target_uris = {http_uri, https_uri}

    # Semantic Noise Cleaning
    result_graph = initialize_graph()
    logger.info("Used pruning method: %s", pruning)
    if pruning == "unpruned":
        result_graph += g
    elif pruning == "outgoing-only":
        result_graph = prune_graph_by_outgoing_resources_only(g, target_uris, result_graph)
    elif pruning == "in-and-outgoing":
        result_graph = prune_graph_by_in_and_outgoing_resources(g, target_uris, result_graph)
    else:
        raise ValueError(f"Unknown {ENV_PRUNING_METHOD}={pruning!r}; allowed: {PRUNING_METHODS}")

    logger.info("Used RDF representation: %s", configured_rdf)
    if configured_rdf == "json-ld":
        return get_json_ld(result_graph)
    if configured_rdf == "turtle":
        return get_turtle(result_graph)
    # if configured_rdf == "turtle-compact":
    #     return get_compact_turtle(result_graph)
    if configured_rdf == "turtle-terser":
        return get_terser_turtle(result_graph)
    if configured_rdf == "json-ld-compact":
        return get_compact_json_ld(result_graph)
    raise ValueError(
        f"Unknown {ENV_RDF_REPRESENTATION}={configured_rdf!r}; allowed: {RDF_REPRESENTATIONS}"
    )


def _get_pruned_graph_for_uri(turtle_text: str, resource_uri: str) -> Graph:
    """Parse Turtle and return graph pruned per PRUNING_METHOD for the given resource URI."""
    g = Graph()
    g.parse(data=turtle_text, format="turtle")
    http_uri = URIRef(resource_uri.replace("https://", "http://"))
    https_uri = URIRef(resource_uri.replace("http://", "https://"))
    target_uris = {http_uri, https_uri}
    pruning = get_pruning_method()
    result_graph = initialize_graph()
    if pruning == "unpruned":
        result_graph += g
    elif pruning == "outgoing-only":
        result_graph = prune_graph_by_outgoing_resources_only(g, target_uris, result_graph)
    elif pruning == "in-and-outgoing":
        result_graph = prune_graph_by_in_and_outgoing_resources(g, target_uris, result_graph)
    else:
        raise ValueError(f"Unknown {ENV_PRUNING_METHOD}={pruning!r}; allowed: {PRUNING_METHODS}")
    return result_graph


def get_representation(resource_representation: str, uri: str) -> str:
    """Transform response body per REPRESENTATION_FORMAT and CONTEXT."""
    fmt = get_representation_format()
    ctx = get_context()
    logger.debug("Used representation format: %s, context: %s", fmt, ctx)

    if fmt == "rdf":
        if ctx == "raw":
            return resource_representation
        if ctx == "modified":
            return get_rdf_representation(
                resource_representation, get_dbpedia_resource_uri(uri)
            )
    if fmt == "wikitext":
        if ctx == "raw":
            return resource_representation
        if ctx == "modified":
            return md(resource_representation)
    if fmt == "html":
        if ctx == "raw":
            return resource_representation
        if ctx == "modified":
            return md(resource_representation)
    if fmt == "crn":
        if ctx == "raw":
            return resource_representation
        if ctx == "modified":
            if "dbpedia.org" in uri:
                resource_uri = get_dbpedia_resource_uri(uri)
                g = _get_pruned_graph_for_uri(resource_representation, resource_uri)
                doc = graph_to_crn(g, resource_uri)
                return serialize(doc)
            if "wikipedia.org" in uri:
                doc = html_to_crn(resource_representation, uri)
                return serialize(doc)
            return resource_representation
    return resource_representation
