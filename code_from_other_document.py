
import logging
from markdownify import markdownify as md
import os
import re
import rdflib
from rdflib import Graph, URIRef, Namespace
import json
from pyld import jsonld
##############################################################
# Actions/tools related to the web (unauthenticated).
##############################################################



# Define namespaces
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
DBO   = Namespace("http://dbpedia.org/ontology/")
DBR   = Namespace("http://dbpedia.org/resource/")
DBC   = Namespace("http://dbpedia.org/resource/Category:")
DCT   = Namespace("http://purl.org/dc/terms/")
FOAF  = Namespace("http://xmlns.com/foaf/0.1/")
SKOS  = Namespace("http://www.w3.org/2004/02/skos/core#")
OWL   = Namespace("http://www.w3.org/2002/07/owl#")
SCHEMA = Namespace("http://schema.org/")
DUL   = Namespace("http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#")
WIKIDATA = Namespace("http://www.wikidata.org/entity/")

# Define allowed predicates (forward and reverse)
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


# Define namespaces for prefix handling
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

# Turtle Terser Version
def turtle_terser_version(graph: str) -> str:
    """
    Convert a turtle graph to its terser version.
    
    Args:
        graph: A string representing the turtle graph.
    """
    # In-memory mapping for caching URI transformations within this function call
    mapping = {}
    
    def _apply_namespace_transformation(uri: str, prefix: str, local_name: str, is_predicate: bool = False) -> str:
        """Helper function to apply namespace-specific transformations."""
        if prefix == "dbc":  # Category
            return f"Category of {local_name}"
        elif prefix == "dbt":  # Template
            return f"Template for {local_name}"
        elif prefix == "dbo":  # Ontology
            # For predicates, use "has" prefix; for subjects/objects, just use local name
            if is_predicate:
                return f"has {local_name}"
            else:
                return local_name
        elif prefix == "dbr":  # Resource
            # Check for special cases within dbr
            if "Category:" in uri:
                return f"Category of {local_name.replace('Category:', '')}"
            elif "Template:" in uri:
                return f"Template for {local_name.replace('Template:', '')}"
            elif "Property:" in uri:
                return f"Property of {local_name.replace('Property:', '')}"
            elif "Class:" in uri:
                return f"has class {local_name.replace('Class:', '')}"
            else:
                return local_name
        else:
            # For other namespaces, just use the local name
            return local_name
    
    def _apply_legacy_transformation(uri: str, is_predicate: bool = False) -> str:
        """Apply legacy hardcoded patterns for backward compatibility."""
        if "dbpedia.org/resource/Category:" in uri:
            return uri.replace("http://dbpedia.org/resource/Category:", "Category of ")
        elif "dbpedia.org/resource/Template:" in uri:
            return uri.replace("http://dbpedia.org/resource/Template:", "Template for ")
        elif "dbpedia.org/resource/Property:" in uri:
            return uri.replace("http://dbpedia.org/resource/Property:", "Property of ")
        elif "dbpedia.org/ontology/" in uri:
            # For predicates, use "has" prefix; for subjects/objects, just remove namespace
            if is_predicate:
                return uri.replace("http://dbpedia.org/ontology/", "has ")
            else:
                return uri.replace("http://dbpedia.org/ontology/", "")
        elif "dbpedia.org/resource/Class:" in uri:
            return uri.replace("http://dbpedia.org/resource/Class:", "has class ")
        elif "dbpedia.org/resource/" in uri:
            return uri.replace("http://dbpedia.org/resource/", "")
        else:
            return uri
        
    def add_mapping_subject_object(uri: str) -> str:
        """Add mapping for subject or object URIs."""
        if uri in mapping:
            return mapping[uri]
        
        # Try to match against known namespaces
        uri_replacement = None
        for prefix, namespace in NAMESPACES.items():
            if uri.startswith(namespace):
                local_name = uri[len(namespace):]
                uri_replacement = _apply_namespace_transformation(uri, prefix, local_name, is_predicate=False)
                break
        
        # If no namespace matched, try legacy hardcoded patterns
        if uri_replacement is None:
            uri_replacement = _apply_legacy_transformation(uri, is_predicate=False)
        
        # Replace underscores with spaces
        uri_replacement = uri_replacement.replace("_", " ")
        mapping[uri] = uri_replacement
        return uri_replacement
    
    def add_mapping_predicate(uri: str) -> str:
        """Add mapping for predicate URIs."""
        if uri in mapping:
            return mapping[uri]
        
        # Try to match against known namespaces
        uri_replacement = None
        for prefix, namespace in NAMESPACES.items():
            if uri.startswith(namespace):
                local_name = uri[len(namespace):]
                uri_replacement = _apply_namespace_transformation(uri, prefix, local_name, is_predicate=True)
                break
        
        # If no namespace matched, try legacy hardcoded patterns
        if uri_replacement is None:
            uri_replacement = _apply_legacy_transformation(uri, is_predicate=True)
        
        # Replace underscores with spaces
        uri_replacement = uri_replacement.replace("_", " ")
        mapping[uri] = uri_replacement
        return uri_replacement
    
    terser_turtle = ""
    for s, p, o in g.triples((None, None, None)):
        # Use separate functions for predicates vs subjects/objects
        subject = mapping.get(str(s)) if str(s) in mapping else add_mapping_subject_object(str(s))
        predicate = mapping.get(str(p)) if str(p) in mapping else add_mapping_predicate(str(p))
        object_val = mapping.get(str(o)) if str(o) in mapping else add_mapping_subject_object(str(o))
        terser_turtle += f"[{subject}]({str(s)}) [{predicate}]({str(p)}) [{object_val}]({str(o)})\n"
    
    return terser_turtle

7,8

# A dictionary containing all uris that have been transformed before 
URI_DICTIONARY = {}

def add_uri(key, uri):
    if key not in URI_DICTIONARY:
        URI_DICTIONARY[key] = uri
        
def get_uri(key):
    return URI_DICTIONARY.get(key, "")

def is_allowed_uri(uri_ref) -> bool:
    """
    Check if a URI is from dbpedia.org or wikipedia.org domains.
    """
    if not isinstance(uri_ref, URIRef):
        return False
    
    uri_str = str(uri_ref)
    return 'dbpedia.org' in uri_str or 'wikipedia.org' in uri_str

def initialize_graph() -> rdflib.Graph:
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


def prune_graph_by_in_and_outgoing_resources(g, target_uris, result_graph) -> Graph:
    g_res = initialize_graph()
    # Iterate over all triples in the graph
    for subject, predicate, obj in g:
        # Check if subject matches target URI and predicate is allowed
        # Also ensure the object URI is from dbpedia or wikipedia
        if subject in target_uris and predicate in ALLOWED_PREDICATES:
            if isinstance(obj, URIRef) and is_allowed_uri(obj):
                g_res.add((subject, predicate, obj))
            elif not isinstance(obj, URIRef):
                # Allow non-URI objects (literals, blank nodes)
                g_res.add((subject, predicate, obj))
        
        # Check if object matches target URI and predicate is allowed (reverse relationships)
        # Also ensure the subject URI is from dbpedia or wikipedia
        if obj in target_uris and predicate in ALLOWED_PREDICATES:
            if isinstance(subject, URIRef) and is_allowed_uri(subject):
                g_res.add((subject, predicate, obj))
    return g_res


def prune_graph_by_outgoing_resources_only(g, target_uris, result_graph) -> Graph:
    g_res = initialize_graph()
    for subject, predicate, obj in g:
        if subject not in target_uris and predicate in ALLOWED_PREDICATES:
            continue
        g_res.add((subject, predicate, obj))
    return g_res


def remove_white_spaces(serialized_graph: str) -> str:
    """ Removes unnecessary white spaces and new lines. """
    cleaned = re.sub(r'\s+', ' ', serialized_graph).strip()
    return cleaned

def get_compact_turtle(result_graph: Graph) -> str:
    serialized_graph = result_graph.serialize(format="turtle")
    return remove_white_spaces(serialized_graph)

def get_terser_turtle(result_graph: Graph) -> str:
    turtle_terser = turtle_terser_version(result_graph)
    return turtle_terser


def get_compact_json_ld(g: Graph) -> str:
    data = json.loads(g.serialize(format='json-ld', indent=4))

    # 3. Load your context
    context = {
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
    "isPrimaryTopicOf": { "@id": "http://xmlns.com/foaf/0.1/isPrimaryTopicOf", "@type": "@id" },
    "hypernym": { "@id": "http://purl.org/linguistics/gold/hypernym", "@type": "@id" },
    "homepage": { "@id": "http://xmlns.com/foaf/0.1/homepage", "@type": "@id" },
    "sameAs": { "@id": "http://www.w3.org/2002/07/owl#sameAs", "@type": "@id" },
    "wasDerivedFrom": { "@id": "http://www.w3.org/ns/prov#wasDerivedFrom", "@type": "@id" },
    "broader": { "@id": "http://www.w3.org/2004/02/skos/core#broader", "@type": "@id" },
    "narrower": { "@id": "http://www.w3.org/2004/02/skos/core#narrower", "@type": "@id" },
    "related": { "@id": "http://www.w3.org/2004/02/skos/core#related", "@type": "@id" },
    "website": { "@id": "http://dbpedia.org/property/website", "@type": "@id" },
    "wikiPageExternalLink": { "@id": "http://dbpedia.org/ontology/wikiPageExternalLink", "@type": "@id" },
    "wikiPageWikiLink": { "@id": "http://dbpedia.org/ontology/wikiPageWikiLink", "@type": "@id" },
    "subject": { "@id": "http://purl.org/dc/terms/subject", "@type": "@id" },
    "wikiPageUsesTemplate": { "@id": "http://dbpedia.org/property/wikiPageUsesTemplate", "@type": "@id" },
    "label": { "@id": "http://www.w3.org/2000/01/rdf-schema#label" },
    "description": { "@id": "http://dbpedia.org/ontology/description" }
}

    

    # 4. Compact the data
    compacted = jsonld.compact(data, context)

    # 5. Pretty print
    return json.dumps(compacted, indent=2, ensure_ascii=False)

def get_json_ld(result_graph: Graph) -> str:
    return result_graph.serialize(format='json-ld', indent=4)

def get_turtle(result_graph) -> str:
    """
    Filter RDF graph by iterating over all triples and keeping only those
    that match the URI (as subject or object) and have allowed predicates.
    Only keeps triples where URIs are from dbpedia.org or wikipedia.org domains.
    """
    return result_graph.serialize(format="turtle")
  

  
def get_rdf_representation(resource_representation: str, uri: str) -> str:
    configured_rdf_representation = os.environ.get("RDF_REPRESENTATION")
    selected_pruning_method = os.environ.get("PRUNING_METHOD")
    
    if configured_rdf_representation == "html":
        return md(resource_representation)
    
    # Create Graph
    g = Graph()
    g.parse(data=resource_representation, format="turtle")
    
    # Create both HTTP and HTTPS versions of the URI
    http_uri = URIRef(uri.replace('https://', 'http://'))
    https_uri = URIRef(uri.replace('http://', 'https://'))
    target_uris = {http_uri, https_uri}
    
    # Create a new graph for filtered results
    result_graph = initialize_graph()
    
    
    

    logging.info(f"Used pruning method: {selected_pruning_method}")    
    if selected_pruning_method == "unpruned":
        result_graph += g
    elif selected_pruning_method == "outgoing-only":
        result_graph = prune_graph_by_outgoing_resources_only(g, target_uris, result_graph)
    elif selected_pruning_method == "in-and-outgoing":
        result_graph = prune_graph_by_in_and_outgoing_resources(g, target_uris, result_graph)
    else:
        raise NameError
    
    logging.info(f"Used rdf representation: {configured_rdf_representation}")
    if configured_rdf_representation == "json-ld":
        return get_json_ld(result_graph)
    elif configured_rdf_representation == "turtle":
        return get_turtle(result_graph)
    elif configured_rdf_representation == "turtle-compact":
        return get_compact_turtle(result_graph)
    elif configured_rdf_representation == "turtle-terser":
        return get_terser_turtle(result_graph)
    elif configured_rdf_representation == "json-ld-compact":
        return get_compact_json_ld(result_graph)
    else:
        raise NameError
    


def modify_uri(uri: str) -> str:
    if os.environ.get("REPRESENTATION_FORMAT") == "rdf":
        if os.environ.get("RDF_REPRESENTATION") == "html":
            return f"https://dbpedia.org/page/{uri.split('/')[-1]}"
        else:
            # Call dbpedia instead of wikipedia
            return f"http://dbpedia.org/data/{uri.split('/')[-1]}.ttl"
    
    
    elif os.environ.get("REPRESENTATION_FORMAT") == "wikitext":
        # Call wikitext instead of wikipedia
        return f"https://en.wikipedia.org/api/rest_v1/page/html/{uri.split('/')[-1]}"
    elif os.environ.get("REPRESENTATION_FORMAT") == "html":
        return uri
    else:
        return uri

def get_dbpedia_resource_uri(uri: str) -> str:
    return f"http://dbpedia.org/resource/{uri.split('/')[-1]}"

def get_representation(resource_representation: str, uri: str) -> str:
    selected_representation_format = os.environ.get("REPRESENTATION_FORMAT")
    selected_context_format = os.environ.get("CONTEXT")
    
    logging.info(f"Used RDF representation {selected_representation_format}: {selected_context_format}")
    if selected_representation_format == "rdf":
        if selected_context_format == "raw":
            return resource_representation
        elif selected_context_format == "modified":
            return get_rdf_representation(resource_representation, get_dbpedia_resource_uri(uri))
        
    elif selected_representation_format == "wikitext":
        if selected_context_format == "raw":
            return resource_representation
        elif selected_context_format == "modified":
            return md(resource_representation)
    elif selected_representation_format == "html":
        if selected_context_format == "raw":
            return resource_representation
        elif selected_context_format == "modified":
            return md(resource_representation)
    else:
        return resource_representation

async def get(uri: str) -> tuple[str, list]:
    """
    Dereference (a la CBD or deref) a URI.
    """
    message = ""
    warnings = []

    status_code = -1
    content_type = None

    modified_context = os.environ.get("MODIFY_CONTEXT")
    rdf_representation = os.environ.get("RDF_REPRESENTATION")
    print(f"RDF representation: {rdf_representation}")
    print(f"Modified context: {modified_context}")
    print(f"URI: {uri}")
    
    try:
        
        logging.info(f"Use modified context {modified_context} {type(modified_context)}")
        if modified_context == "true":
            modified_uri = modify_uri(uri)
            logging.info(f"Modified uri from {uri} to {modified_uri}")
        else:
            modified_uri = uri
            
        if rdf_representation == "html":
            content_types = """
                    text/html,
                    application/xhtml+xml,
                    application/xml;q=0.9

            """
        else:
            content_types = """
                    text/turtle;q=1,
                    application/ld+json;q=0.99,
                    application/rdf+xml;q=0.99,
                    application/n-triples;q=0.99,
                    application/activity+json;q=0.99,
                    application/hal+json;q=0.975,
                    application/json;q=0.95,
                    application/atom+xml;q=0.9,
                    application/xml;q=0.85
            """
        response = await get(modified_uri, content_types=content_types)

        # message, graph = await asyncio.wait_for(asyncio.to_thread(web.deref, uri), timeout=TIMEOUT_DEREF)

        message = f"Status code `{status_code}`, content type `{content_type}`.\n"

        if response.content is None:
            message += f"No content for `deref('{uri}')`."
        else:
            # html_content = content
            if modified_context == "true":
                modified_content = get_representation(response.content, uri)
            else:
                modified_content = response.content
            message += f"The description of `{uri}` is as follows.\n\n{escape.escape_code(modified_content)}"


    return message, warnings
