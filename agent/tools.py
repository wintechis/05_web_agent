import asyncio
import json
import os
import time
import markdownify
import httpx
from pydantic import BaseModel

from pi_agent.types import AgentTool, AgentToolResult
from pi_ai.types import TextContent

from agent.clients import http_client

GET_MAX_RETRIES = 3
GET_RETRY_DELAY_SECONDS = 1.0
from agent.resource_transform import (
    get_accept_header_when_modify_context,
    get_modify_context,
    get_representation,
    modify_uri,
)


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
    """Internal synchronous function to fetch and process URL. Retries on transient transport errors."""
    fetch_url = modify_uri(url) if get_modify_context() else url
    headers = (
        {"Accept": get_accept_header_when_modify_context(fetch_url)}
        if get_modify_context()
        else None
    )
    last_exc: Exception | None = None

    for attempt in range(GET_MAX_RETRIES):
        try:
            if headers is not None:
                response = http_client.get(fetch_url, headers=headers)
            else:
                response = http_client.get(fetch_url)
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < GET_MAX_RETRIES - 1:
                time.sleep(GET_RETRY_DELAY_SECONDS)
                continue
            return Response(
                text=f"Request failed after {GET_MAX_RETRIES} attempts: {exc!s}. Please try again or use another URL.",
                url=url,
                status_code=None,
            )

        error_response = _http_error_response(response, url)
        if error_response is not None:
            return error_response

        if get_modify_context():
            text = get_representation(response.text, url)
        else:
            content_type = response.headers.get("Content-Type")
            if content_type == "application/sparql-results+json":
                text = response.text
            elif content_type == "text/html":
                text = process_html(response.text)
            else:
                text = response.text

        return Response(
            text=text,
            url=url,
            status_code=response.status_code,
        )

    return Response(
        text=f"Request failed after {GET_MAX_RETRIES} attempts: {last_exc!s}. Please try again or use another URL.",
        url=url,
        status_code=None,
    )


def _inputs_to_parameters(inputs: dict) -> dict:
    """Convert smolagents-style inputs to JSON Schema parameters."""
    required = [k for k, v in inputs.items() if not v.get("nullable")]
    properties: dict = {}
    for k, v in inputs.items():
        prop = {"type": v["type"], "description": v.get("description", "")}
        if v.get("nullable"):
            prop["nullable"] = True
        if "items" in v:
            prop["items"] = v["items"]
        if "enum" in v:
            prop["enum"] = list(v["enum"])
        properties[k] = prop
    return {"type": "object", "properties": properties, "required": required}


async def _execute_get(tool_call_id: str, args: dict, cancel_event: asyncio.Event | None, on_update: None) -> AgentToolResult:
    url = (args.get("url") or "").strip()
    result = await asyncio.to_thread(_get, url)
    text = f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"
    return AgentToolResult(content=[TextContent(type="text", text=text)], details=None)


GET_TOOL_INPUTS = {
    "url": {
        "type": "string",
        "description": "The URL to fetch and the resource content.",
    }
}

GETTool = AgentTool(
    name="get",
    label="get",
    description="Fetches a URL and returns the resource content. Takes a URL as input and returns the the URL with the resource content.",
    parameters=_inputs_to_parameters(GET_TOOL_INPUTS),
    execute=_execute_get,
)


def _post(url: str, json_body: str | None = None) -> Response:
    """Internal synchronous function to POST to a URL and return the response."""
    response = None
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
            status_code=response.status_code if response is not None else None,
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


async def _execute_post(tool_call_id: str, args: dict, cancel_event: asyncio.Event | None, on_update: None) -> AgentToolResult:
    url = (args.get("url") or "").strip()
    json_body = (args.get("json_body") or "").strip() or None
    result = await asyncio.to_thread(_post, url, json_body)
    text = f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"
    return AgentToolResult(content=[TextContent(type="text", text=text)], details=None)


POST_TOOL_INPUTS = {
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

POSTTool = AgentTool(
    name="post",
    label="post",
    description=(
        "Sends a POST request to a URL. Use for submitting forms or sending JSON payloads. "
        "Takes URL as input; optionally provide json_body as a JSON string to send in the request body."
    ),
    parameters=_inputs_to_parameters(POST_TOOL_INPUTS),
    execute=_execute_post,
)


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


async def _execute_put(tool_call_id: str, args: dict, cancel_event: asyncio.Event | None, on_update: None) -> AgentToolResult:
    url = (args.get("url") or "").strip()
    text_body = (args.get("text_body") or "").strip() or None
    result = await asyncio.to_thread(_put, url, text_body)
    text = f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"
    return AgentToolResult(content=[TextContent(type="text", text=text)], details=None)


PUT_TOOL_INPUTS = {
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

PUTTool = AgentTool(
    name="put",
    label="put",
    description=(
        "Sends a PUT request to a URL. Use for replacing or updating resources. "
        "Takes URL and text_body as input; sends the body with Content-Type: text/plain."
    ),
    parameters=_inputs_to_parameters(PUT_TOOL_INPUTS),
    execute=_execute_put,
)


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


async def _execute_post_rdf(tool_call_id: str, args: dict, cancel_event: asyncio.Event | None, on_update: None) -> AgentToolResult:
    url = (args.get("url") or "").strip()
    data_binary = (args.get("data_binary") or "").strip()
    result = await asyncio.to_thread(_post_rdf, url, data_binary)
    text = f"URL: {result.url}\n\nStatus Code: {result.status_code}\n\nContent:\n{result.text}"
    return AgentToolResult(content=[TextContent(type="text", text=text)], details=None)


POST_RDF_TOOL_INPUTS = {
    "url": {
        "type": "string",
        "description": "The URL to send the RDF data to.",
    },
    "data_binary": {
        "type": "string",
        "description": "RDF data as a string (Turtle, N-Triples, RDF/XML, TriG, N3, or JSON-LD).",
    },
}

POSTRdfTool = AgentTool(
    name="post_rdf",
    label="post_rdf",
    description=(
        "Sends RDF data to a URL via POST. Accepts RDF in various formats (Turtle, "
        "N-Triples, RDF/XML, TriG, N3, JSON-LD). Use for updating RDF stores or "
        "submitting RDF payloads."
    ),
    parameters=_inputs_to_parameters(POST_RDF_TOOL_INPUTS),
    execute=_execute_post_rdf,
)


# Allowed values for LLM-reported task state (structured final answer).
TASK_STATE_VALUES = ("completed", "partial", "failed")


def _forward_final_answer(urls: list[str] | None = None, task_state: str | None = None) -> dict:
    """Synchronous logic for structured final answer (path validation, normalisation)."""
    if urls is None:
        urls = []
    elif isinstance(urls, str):
        urls = [urls]
    elif not isinstance(urls, list):
        urls = [str(urls)] if urls else []
    else:
        urls = [str(u) for u in urls]
    state = (task_state if task_state in TASK_STATE_VALUES else "unclear") or "unclear"

    if os.getenv("PATH_VALIDATION", "").strip().lower() in ("true", "1", "yes") and len(urls) >= 2:
        from benchmark.domain.edge_validator import EdgeValidator

        valid_edges = EdgeValidator().validate_edges(urls)
        invalid = [
            f"{urls[i]} -> {urls[i + 1]}"
            for i, ok in enumerate(valid_edges)
            if not ok
        ]
        if invalid:
            raise ValueError(
                f"Path validation failed: the following edges are not valid links: "
                + "; ".join(invalid)
                + ". Please correct your path and try again."
            )

    return {"urls": urls, "task_state": state}


async def _execute_final_answer(tool_call_id: str, args: dict, cancel_event: asyncio.Event | None, on_update: None) -> AgentToolResult:
    urls = args.get("urls")
    task_state = args.get("task_state")
    result_dict = await asyncio.to_thread(_forward_final_answer, urls, task_state)
    text = json.dumps(result_dict, ensure_ascii=False)
    return AgentToolResult(content=[TextContent(type="text", text=text)], details=result_dict)


FINAL_ANSWER_TOOL_INPUTS = {
    "urls": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of URLs that form the answer. Use empty list if none.",
        "nullable": True,
    },
    "task_state": {
        "type": "string",
        "description": "State of the task: completed (goal achieved), partial (some progress, goal not fully met), failed (goal not achieved).",
        "enum": list(TASK_STATE_VALUES),
        "nullable": True,
    },
}

StructuredFinalAnswerTool = AgentTool(
    name="final_answer",
    label="final_answer",
    description=(
        "Call this when you are done with the task. Provide the list of URLs that answer the user's question "
        "and the task state (completed, partial, failed)."
    ),
    parameters=_inputs_to_parameters(FINAL_ANSWER_TOOL_INPUTS),
    execute=_execute_final_answer,
)
