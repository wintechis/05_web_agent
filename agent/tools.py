import json
import markdownify
import httpx
from pydantic import BaseModel
from smolagents import Tool

from agent.clients import http_client


class Response(BaseModel):
    text: str
    url: str
    status_code: int | None = None


def markdownify_text(text: str) -> str:
    return markdownify.markdownify(text)


def modify_header(httpx_client: httpx.Client, headers: dict[str, str]) -> httpx.Client:
    return httpx_client.with_headers(headers)

def get_query(url: str) -> str:
    query = """
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT (COUNT(DISTINCT ?neighbor) AS ?outDegree)
    WHERE {
        <{url}> dbo:wikiPageWikiLink ?neighbor .
    }
    """
    
    query = query.replace("{url}", url)
    return query

def get_with_sparql(url: str, query: str) -> Response:
    http_client = modify_header(http_client, {"Accept": "application/sparql-results+json"})
    response = http_client.get(url, params={"query": query})
    return Response(
        text=response.text,
        url=url,
        status_code=response.status_code,
    )


def process_html(text: str) -> str:
    return markdownify_text(text)


def _http_error_response(response: httpx.Response, url: str) -> Response | None:
    """Return a Response for HTTP error/redirect status codes, or None if 2xx."""
    if 300 <= response.status_code < 400:
        return Response(
            text=f"Redirected to {response.headers.get('Location')}",
            url=url,
            status_code=response.status_code,
        )
    if 400 <= response.status_code < 500:
        return Response(
            text=f"Client error: {response.status_code}, {response.text}",
            url=url,
            status_code=response.status_code,
        )
    if 500 <= response.status_code < 600:
        return Response(
            text=f"Server error: {response.status_code}, {response.text}",
            url=url,
            status_code=response.status_code,
        )
    return None


def _get(url: str) -> Response:
    """Internal synchronous function to fetch and process URL."""
    response = http_client.get(url)

    error_response = _http_error_response(response, url)
    if error_response is not None:
        return error_response

    content_type = response.headers.get("Content-Type")
    if content_type == "application/sparql-results+json":
        text = response.text
    if content_type == "text/html":
        text = process_html(response.text)
    else:
        text = response.text
    

    return Response(
        text=text,
        url=url,
        status_code=response.status_code,
    )


class GETTool(Tool):
    """Tool to fetch and convert web resources."""

    name = "get"
    description = "Fetches a URL and returns the resource content. Takes a URL as input and returns the the URL with the resource content."
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to fetch and the resource content.",
        }
    }
    output_type = "string"

    def forward(self, url: str) -> str:
        """Synchronous function to fetch URL and return markdown content."""
        result = _get(url)
        return f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"


def _post(url: str, json_body: str | None = None) -> Response:
    """Internal synchronous function to POST to a URL and return the response."""
    try:
        if json_body:
            body = json.loads(json_body)
            response = http_client.post(url, json=body)
        else:
            response = http_client.post(url)
    except json.JSONDecodeError:
        return Response(
            text=f"Invalid JSON body: {json_body}",
            url=url,
            status_code=response.status_code,
        )

    error_response = _http_error_response(response, url)
    if error_response is not None:
        return error_response

    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text = process_html(response.text)
    else:
        text = response.text

    return Response(text=text, url=url, status_code=response.status_code)


class POSTTool(Tool):
    """Tool to send a POST request to a URL and return the response content."""

    name = "post"
    description = (
        "Sends a POST request to a URL. Use for submitting forms or sending JSON payloads. "
        "Takes URL as input; optionally provide json_body as a JSON string to send in the request body."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to send the POST request to.",
        },
        "json_body": {
            "type": "string",
            "description": "Optional JSON string to send as request body (e.g. '{\"key\": \"value\"}').",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(self, url: str, json_body: str = "") -> str:
        """Synchronous function to POST to URL and return response content."""
        result = _post(url, json_body=json_body.strip() or None)
        return f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"


def _put(url: str, text_body: str | None = None) -> Response:
    """Internal synchronous function to PUT to a URL and return the response."""
    if text_body:
        response = http_client.put(
            url,
            content=text_body.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
    else:
        response = http_client.put(url)

    error_response = _http_error_response(response, url)
    if error_response is not None:
        return error_response

    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text = process_html(response.text)
    else:
        text = response.text

    return Response(text=text, url=url, status_code=response.status_code)


class PUTTool(Tool):
    """Tool to send a PUT request to a URL with a text body."""

    name = "put"
    description = (
        "Sends a PUT request to a URL. Use for replacing or updating resources. "
        "Takes URL and text_body as input; sends the body with Content-Type: text/plain."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to send the PUT request to.",
        },
        "text_body": {
            "type": "string",
            "description": "Text to send as request body (plain text).",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(self, url: str, text_body: str = "") -> str:
        """Synchronous function to PUT to URL and return response content."""
        result = _put(url, text_body=text_body.strip() or None)
        return f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"


RDF_FORMATS = (
    "TURTLE",
    "N_TRIPLES",
    "N_QUADS",
    "TRIG",
    "N3",
    "RDF_XML",
    "JSON_LD",
)


def _parse_rdf_to_turtle(data_binary: str) -> tuple[str, str] | tuple[None, str]:
    """
    Parse RDF from string, validate it, and serialize to Turtle.
    Returns (turtle_str, "") on success, or (None, error_message) on failure.
    """
    from pyoxigraph import RdfFormat, parse, serialize

    data_bytes = data_binary.encode("utf-8") if isinstance(data_binary, str) else data_binary

    last_error: str | None = None
    for fmt_name in RDF_FORMATS:
        fmt = getattr(RdfFormat, fmt_name, None)
        if fmt is None:
            continue
        try:
            quads = list(parse(input=data_bytes, format=fmt))
            if not quads:
                return None, "Parsed RDF is empty"
            turtle_bytes = serialize(quads, format=RdfFormat.TURTLE)
            return turtle_bytes.decode("utf-8"), ""
        except (SyntaxError, ValueError, OSError) as e:
            last_error = str(e)
            continue

    err_suffix = f" Last error: {last_error}" if last_error else ""
    return None, (
        f"Invalid RDF: could not parse as any supported format "
        f"(Turtle, N-Triples, RDF/XML, TriG, N3, JSON-LD).{err_suffix}"
    )


def _post_rdf(url: str, data_binary: str) -> Response:
    """Parse RDF from data_binary, encode as Turtle, POST to url."""
    turtle_str, error = _parse_rdf_to_turtle(data_binary)
    if error:
        return Response(text=error, url=url, status_code=None)

    headers = {"Content-Type": "text/turtle; charset=utf-8"}
    response = http_client.post(url, content=turtle_str.encode("utf-8"), headers=headers)

    error_response = _http_error_response(response, url)
    if error_response is not None:
        return error_response

    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text = process_html(response.text)
    else:
        text = response.text

    return Response(text=text, url=url, status_code=response.status_code)


class POSTRdfTool(Tool):
    """
    Tool to POST RDF data to a URL. Validates input as RDF, converts to Turtle,
    and sends with Content-Type: text/turtle.
    """

    name = "post_rdf"
    description = (
        "Sends RDF data to a URL via POST. Accepts RDF in various formats (Turtle, "
        "N-Triples, RDF/XML, TriG, N3, JSON-LD). Use for updating RDF stores or "
        "submitting RDF payloads."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to send the RDF data to.",
        },
        "data_binary": {
            "type": "string",
            "description": "RDF data as a string (Turtle, N-Triples, RDF/XML, TriG, N3, or JSON-LD).",
        },
    }
    output_type = "string"

    def forward(self, url: str, data_binary: str) -> str:
        """Parse RDF, validate, convert to Turtle, POST to URL."""
        result = _post_rdf(url, data_binary.strip())
        return f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"
