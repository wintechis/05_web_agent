"""Generate Wikipedia/DBpedia path-finding challenges via SPARQL and Six Degrees API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Optional, Tuple
from urllib.parse import unquote

import httpx
import SPARQLWrapper
import yaml

from agent.clients import http_client

LOGGER = logging.getLogger(__name__)

DEFAULT_LIMIT = 4
DISTANCE = 3
NUMBER_OF_CHALLENGES = 200
ENFORCE_EXACT_DISTANCE = True
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_WIKIPEDIA_OUTPUT = "wikipedia_challenge_5.yaml"
DEFAULT_DBPEDIA_OUTPUT = "dbpedia_challenge_5.yaml"


@dataclass
class WikipediaPage:
    url: httpx.URL

    def name(self) -> str:
        return unquote(self.url.path.split("/")[-1])

    def dbpedia_url(self) -> str:
        return f"http://dbpedia.org/resource/{self.name()}"

    def wikipedia_url(self) -> str:
        return f"https://en.wikipedia.org/wiki/{self.name()}"

    def wikipedia_title(self) -> str:
        return self.name().replace("_", " ")


@dataclass
class WikipediaPath:
    path: List[WikipediaPage]
    length: int
    start_uri_statistics: Optional[Tuple[int, int, int]] = None
    end_uri_statistics: Optional[Tuple[int, int, int]] = None
    statistics: Optional[Tuple[int, int, int]] = None


def find_random_wikipedia_page() -> WikipediaPage:
    r = http_client.get("https://en.wikipedia.org/wiki/Special:Random", follow_redirects=True)
    LOGGER.debug("Random wikipedia response: %s", r.text)
    return WikipediaPage(url=r.url)


def _build_redirect_query(n: int, wikipedia_page: str, limit: int = DEFAULT_LIMIT) -> str:
    if n <= 0:
        raise ValueError("n must be greater than 0")

    page_vars = [f"?page{index}" for index in range(1, n + 1)]
    select_clause = " ".join(page_vars)
    path_nodes = [f"<{wikipedia_page}>"] + page_vars

    def build_triples(previous: str, remaining: List[str]) -> List[str]:
        if not remaining:
            return []
        head, *tail = remaining
        return [f"    {previous} dbo:wikiPageWikiLink {head} ."] + build_triples(head, tail)

    def build_non_adjacent_filter(node_left: str, node_right: str) -> str:
        return (
            "    FILTER NOT EXISTS { "
            f"{node_left} dbo:wikiPageWikiLink {node_right} . "
            f"{node_right} dbo:wikiPageWikiLink {node_left} . "
            "}"
        )

    def build_filters(nodes: List[str]) -> List[str]:
        filters: List[str] = []
        for left_index, left_node in enumerate(nodes):
            for right_index, right_node in enumerate(nodes):
                if right_index <= left_index + 1:
                    continue
                filters.append(build_non_adjacent_filter(left_node, right_node))
        return filters

    triples_block = "\n".join(build_triples(f"<{wikipedia_page}>", page_vars))
    last_page_var = page_vars[-1]
    derived_from_triple = f"    {last_page_var} prov:wasDerivedFrom ?derivedFrom ."
    filters_block = "\n".join(build_filters(path_nodes))
    return f""" PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT {select_clause} ?derivedFrom WHERE {{
{triples_block}
{derived_from_triple}
{filters_block}
}}
LIMIT {limit}
    """


def get_n_steps_away_from_random_wikipedia_page(
    n: int,
    wikipedia_page: str,
    limit: int = DEFAULT_LIMIT,
) -> List[WikipediaPage]:
    query = _build_redirect_query(n=n, wikipedia_page=wikipedia_page, limit=limit)
    LOGGER.debug("DBPedia redirect query: %s", query)
    sparql = SPARQLWrapper.SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    results = sparql.query().convert()

    LOGGER.debug("DBPedia redirect results: %s", results)
    wikipedia_pages: List[WikipediaPage] = []
    for result in results.get("results", {}).get("bindings", []):
        if f"page{n}" in result:
            page_url = result[f"page{n}"].get("value", None)
            if not page_url:
                continue
        if "derivedFrom" in result:
            derived_from = result["derivedFrom"].get("value", None)
            if not derived_from:
                continue
            wikipedia_pages.append(WikipediaPage(url=httpx.URL(derived_from)))
    return wikipedia_pages


# Timeout for Six Degrees API (path finding can be slow for large distance)
SIX_DEGREES_REQUEST_TIMEOUT = 60.0


def find_wiki_path(
    source: str,
    target: str,
    distance: int = DISTANCE,
) -> List[WikipediaPath]:
    url = "https://api.sixdegreesofwikipedia.com/paths"
    payload = {"source": source, "target": target}

    LOGGER.info("Finding path with payload: %s", payload)

    try:
        response = http_client.post(url, json=payload, timeout=SIX_DEGREES_REQUEST_TIMEOUT)
    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as e:
        LOGGER.warning(
            "Six Degrees API timeout or connection error for %s -> %s: %s",
            source,
            target,
            e,
        )
        return []
    except httpx.HTTPError as e:
        LOGGER.warning(
            "Six Degrees API request failed for %s -> %s: %s",
            source,
            target,
            e,
        )
        return []

    LOGGER.debug("Six Degrees response: %s", response.text)

    if not response.is_success:
        LOGGER.warning(
            "Six Degrees API error: %s %s for %s -> %s",
            response.status_code,
            response.reason_phrase or "",
            source,
            target,
        )
        return []

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        LOGGER.warning(
            "Six Degrees API returned non-JSON (e.g. 502 body) for %s -> %s: %s",
            source,
            target,
            e,
        )
        return []

    paths = data.get("paths", [])
    identifiers = data.get("pages", {})

    res: List[WikipediaPath] = []
    minimal_length_path = None

    if len(paths) == 0:
        LOGGER.info("No paths found for %s -> %s", source, target)
        return []

    for path in paths:
        if len(path) < distance + 1:
            return []
        if minimal_length_path is None or len(path) < len(minimal_length_path):
            minimal_length_path = path

    wikipedia_pages = [
        WikipediaPage(url=httpx.URL(identifiers[str(page)].get("url", "")))
        for page in minimal_length_path
    ]
    wikipedia_path = WikipediaPath(path=wikipedia_pages, length=len(wikipedia_pages))
    res.append(wikipedia_path)
    return res


@lru_cache(maxsize=10000)
def get_reversed_neighborhood_size(end_uri: str) -> Optional[int]:
    sparql = SPARQLWrapper.SPARQLWrapper("https://dbpedia.org/sparql")
    query = """
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT (COUNT(DISTINCT ?neighbor) AS ?reversedNeighborhoodSize)
    WHERE {
        ?neighbor (^dbo:wikiPageWikiLink){0,2} <{end_uri}> .
    }
    """
    query = query.replace("{end_uri}", end_uri)
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQLWrapper.JSON)

    try:
        results = sparql.query().convert()
        for r in results["results"]["bindings"]:
            return int(results["results"]["bindings"][0]["reversedNeighborhoodSize"]["value"])
    except Exception:
        LOGGER.exception("Failed to compute reversed neighborhood size for %s", end_uri)
        return None


@lru_cache(maxsize=10000)
def get_in_degree(uri: str) -> Optional[int]:
    sparql = SPARQLWrapper.SPARQLWrapper("https://dbpedia.org/sparql")
    query = """
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT (COUNT(DISTINCT ?neighbor) AS ?inDegree)
    WHERE {
        ?neighbor dbo:wikiPageWikiLink <{uri}> .
    }
    """
    query = query.replace("{uri}", uri)
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    try:
        results = sparql.query().convert()
        for r in results["results"]["bindings"]:
            return int(r["inDegree"]["value"])
    except Exception:
        LOGGER.exception("Failed to compute in degree for %s", uri)
        return None


@lru_cache(maxsize=10000)
def get_out_degree(uri: str) -> Optional[int]:
    sparql = SPARQLWrapper.SPARQLWrapper("https://dbpedia.org/sparql")
    query = """
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT (COUNT(DISTINCT ?neighbor) AS ?outDegree)
    WHERE {
        <{uri}> dbo:wikiPageWikiLink ?neighbor .
    }
    """
    query = query.replace("{uri}", uri)
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    try:
        results = sparql.query().convert()
        for r in results["results"]["bindings"]:
            return int(r["outDegree"]["value"])
    except Exception:
        LOGGER.exception("Failed to compute out degree for %s", uri)
        return None


def data_statistics(uri: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    reversed_neighborhood_size = get_reversed_neighborhood_size(uri)
    in_degree = get_in_degree(uri)
    out_degree = get_out_degree(uri)
    return reversed_neighborhood_size, in_degree, out_degree


def _serialize_statistics(
    statistics: Optional[Tuple[int, int, int]],
) -> Optional[dict]:
    if statistics is None:
        return None
    return {
        "reversed_neighborhood_size": statistics[0],
        "in_degree": statistics[1],
        "out_degree": statistics[2],
    }


def _write_challenge_yaml(
    file_name: str,
    dataset_prefix: str,
    all_paths: List[WikipediaPath],
    uri_builder: Callable[[WikipediaPage], str],
) -> None:
    res: dict = {
        "dataset": {"id": "", "prefix": dataset_prefix},
        "questions": [],
    }
    for path in all_paths:
        start_stats = path.start_uri_statistics
        end_stats = path.end_uri_statistics
        combined_stats = path.statistics
        res["questions"].append(
            {
                "id": path.path[0].wikipedia_title() + "_" + path.path[-1].wikipedia_title(),
                "question": {
                    "en": (
                        "Task: Find a path between the start URI "
                        f"{uri_builder(path.path[0])} and end URI {uri_builder(path.path[-1])}. "
                        "Return all URIs of the path, including the start "
                        "and end URIs, in the following format: "
                        "<answer> <uri1> <uri2> <uri3> <uri4> </answer>"
                    )
                },
                "path": [uri_builder(page) for page in path.path],
                "statistics": {
                    "start_uri_statistics": _serialize_statistics(start_stats),
                    "end_uri_statistics": _serialize_statistics(end_stats),
                    "statistics": _serialize_statistics(combined_stats),
                },
            }
        )
    with open(file_name, "w", encoding="utf-8") as f:
        yaml.safe_dump(res, f, default_flow_style=False, allow_unicode=True)


class GenerateChallengeUseCase:
    """Generate Wikipedia/DBpedia path-finding challenges."""

    def run(
        self,
        *,
        distance: int = DISTANCE,
        number_of_challenges: int = NUMBER_OF_CHALLENGES,
        default_limit: int = DEFAULT_LIMIT,
        enforce_exact_distance: bool = ENFORCE_EXACT_DISTANCE,
        wikipedia_output: str = DEFAULT_WIKIPEDIA_OUTPUT,
        dbpedia_output: str = DEFAULT_DBPEDIA_OUTPUT,
    ) -> None:
        all_paths: List[WikipediaPath] = []
        attempts = 0

        while len(all_paths) < number_of_challenges:
            attempts += 1
            LOGGER.info("Challenge generation attempt %s", attempts)
            start_uri = find_random_wikipedia_page()
            end_uris = get_n_steps_away_from_random_wikipedia_page(
                n=distance,
                wikipedia_page=start_uri.dbpedia_url(),
                limit=default_limit,
            )

            for end_uri in end_uris:
                start_to_end_path = find_wiki_path(
                    start_uri.wikipedia_title(),
                    end_uri.wikipedia_title(),
                    distance=distance,
                )
                end_to_start_path = find_wiki_path(
                    end_uri.wikipedia_title(),
                    start_uri.wikipedia_title(),
                    distance=distance,
                )
                paths = start_to_end_path + end_to_start_path
                valid_paths: List[WikipediaPath] = []
                for wikipedia_path in paths:
                    if len(wikipedia_path.path) < distance + 1:
                        LOGGER.warning("Path too short: %s", wikipedia_path.path)
                        continue
                    valid_paths.append(wikipedia_path)

                if len(valid_paths) != len(paths):
                    LOGGER.warning("Invalid paths: %s", valid_paths)
                    continue

                if enforce_exact_distance:
                    valid_paths = [
                        path for path in valid_paths if len(path.path) == distance + 1
                    ]

                all_paths.extend(valid_paths)
                if len(all_paths) >= number_of_challenges:
                    break

        LOGGER.info("Found %s paths", len(all_paths))

        for path in all_paths:
            path.start_uri_statistics = data_statistics(path.path[0].dbpedia_url())
            path.end_uri_statistics = data_statistics(path.path[-1].dbpedia_url())
            path.statistics = (
                (path.start_uri_statistics[0] or 0) + (path.end_uri_statistics[0] or 0),
                (path.start_uri_statistics[1] or 0) + (path.end_uri_statistics[1] or 0),
                (path.start_uri_statistics[2] or 0) + (path.end_uri_statistics[2] or 0),
            )
            LOGGER.info(
                "Path: %s, Length: %s, Statistics: %s",
                path.path,
                path.length,
                path.statistics,
            )

        _write_challenge_yaml(
            wikipedia_output,
            "wikipedia-challenge",
            all_paths,
            lambda page: page.wikipedia_url(),
        )
        _write_challenge_yaml(
            dbpedia_output,
            "dbpedia-challenge",
            all_paths,
            lambda page: page.dbpedia_url(),
        )
