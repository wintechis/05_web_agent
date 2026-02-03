import logging
from urllib.parse import unquote
from typing import Any, Dict, List

import httpx
import SPARQLWrapper

DEFAULT_LIMIT = 2
DISTANCE = 2
NUMBER_OF_CHALLENGES = 10

from dataclasses import dataclass
from clients import http_client
from typing import Tuple, Optional
import yaml
from functools import lru_cache

LOGGER = logging.getLogger(__name__)

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

    def build_non_adjacent_filter(
        node_left: str,
        node_right: str,
    ) -> str:
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
) -> Dict[str, Any]:
    query = _build_redirect_query(n=n, wikipedia_page=wikipedia_page)
    LOGGER.debug("DBPedia redirect query: %s", query)
    sparql = SPARQLWrapper.SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    results = sparql.query().convert()
    
    LOGGER.debug("DBPedia redirect results: %s", results)
    wikipedia_pages = []
    for result in results.get("results", {}).get("bindings", []):
        if f"page{n}" in result:
            page_url = result[f"page{n}"].get("value", None)
            if not page_url:
                continue
            #wikipedia_pages.append(WikipediaPage(url=httpx.URL(page_url)))
        if "derivedFrom" in result:
            derived_from = result["derivedFrom"].get("value", None)
            if not derived_from:
                continue
            wikipedia_pages.append(WikipediaPage(url=httpx.URL(derived_from)))
    return wikipedia_pages


def find_wiki_path(source, target) -> WikipediaPath:
    url = "https://api.sixdegreesofwikipedia.com/paths"
    payload = {
        "source": source,
        "target": target
    }
    
    LOGGER.info("Finding path with payload: %s", payload)
    
    
    response = http_client.post(url, json=payload, timeout=30)
    LOGGER.debug("Six Degrees response: %s", response.text)
    data = response.json()
    
    # This returns a list of all shortest paths found
    paths = data.get("paths", [])
    identifiers = data.get("pages", {})

    res = []
    minimal_length_path = None
    
    if len(paths) == 0:
        LOGGER.info("No paths found for %s -> %s", source, target)
        return []
    
    for path in paths:
        if len(path) < DISTANCE + 1:
            return []
        if minimal_length_path is None or len(path) < len(minimal_length_path):
            minimal_length_path = path
        
    wikipedia_pages = [WikipediaPage(url=httpx.URL(identifiers[str(page)].get("url", ""))) for page in minimal_length_path]
    wikipedia_path = WikipediaPath(path=wikipedia_pages, length=len(wikipedia_pages))
    res.append(wikipedia_path)
    return res


@lru_cache(maxsize=10000)
def get_reversed_neighborhood_size(end_uri):
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
def get_in_degree(uri):
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
def get_out_degree(uri):
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
        


def data_statistics(uri: str) -> Tuple[int, int, int]:
    reversed_neighborhood_size = get_reversed_neighborhood_size(uri)
    in_degree = get_in_degree(uri)
    out_degree = get_out_degree(uri)
    return reversed_neighborhood_size, in_degree, out_degree


def _serialize_statistics(
    statistics: Optional[Tuple[int, int, int]],
) -> Optional[Dict[str, int]]:
    if statistics is None:
        return None
    return {
        "reversed_neighborhood_size": statistics[0],
        "in_degree": statistics[1],
        "out_degree": statistics[2]
    }
 
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    all_paths = []
    attempts = 0
    while len(all_paths) < NUMBER_OF_CHALLENGES:
        attempts += 1
        LOGGER.info("Challenge generation attempt %s", attempts)
        start_uri = find_random_wikipedia_page()
        end_uris = get_n_steps_away_from_random_wikipedia_page(
            n=DISTANCE,
            wikipedia_page=start_uri.dbpedia_url(),
        )
        
        for end_uri in end_uris:
            start_to_end_path = find_wiki_path(start_uri.wikipedia_title(), end_uri.wikipedia_title())
            end_to_start_path = find_wiki_path(end_uri.wikipedia_title(), start_uri.wikipedia_title())
            paths = start_to_end_path + end_to_start_path
            valid_paths = []
            for wikipedia_path in paths:
                if len(wikipedia_path.path) < DISTANCE + 1:
                    LOGGER.warning("Path too short: %s", wikipedia_path.path)
                    continue
                
                valid_paths.append(wikipedia_path)

            if len(valid_paths) != len(paths):
                LOGGER.warning("Invalid paths: %s", valid_paths)
                # drop the paths
                continue
            all_paths.extend(valid_paths)
            if len(all_paths) >= NUMBER_OF_CHALLENGES:
                break
        
    LOGGER.info("Found %s paths", len(all_paths))
    
    # Validate that the paths are of the expexted lenght
    
    for path in all_paths:
        path.start_uri_statistics = data_statistics(path.path[0].dbpedia_url())
        path.end_uri_statistics = data_statistics(path.path[-1].dbpedia_url())
        path.statistics = (
            path.start_uri_statistics[0] + path.end_uri_statistics[0],
            path.start_uri_statistics[1] + path.end_uri_statistics[1],
            path.start_uri_statistics[2] + path.end_uri_statistics[2]
        )
        LOGGER.info(
            "Path: %s, Length: %s, Statistics: %s",
            path.path,
            path.length,
            path.statistics,
        )

    
    def _write_challenge_yaml(
        file_name: str,
        dataset_prefix: str,
        uri_builder,
    ) -> None:
        with open(file_name, "w", encoding="utf-8") as f:
            res = {
                "dataset": {
                    "id": "",
                    "prefix": dataset_prefix,
                },
                "questions": [],
            }
            for path in all_paths:
                start_uri = uri_builder(path.path[0])
                end_uri = uri_builder(path.path[-1])
                res["questions"].append(
                    {
                        "id": path.path[0].wikipedia_title()
                        + "_"
                        + path.path[-1].wikipedia_title(),
                        "question": {
                            "en": (
                                "Task: Find a path between the start URI "
                                f"{start_uri} and end URI {end_uri}. "
                                "Return all URIs of the path, including the start "
                                "and end URIs, in the following format: "
                                "<answer> <uri1> <uri2> <uri3> <uri4> </answer>"
                            )
                        },
                        "path": [uri_builder(page) for page in path.path],
                        "statistics": {
                            "start_uri_statistics": path.start_uri_statistics,
                            "end_uri_statistics": path.end_uri_statistics,
                            "statistics": path.statistics,
                        },
                    }
                )
            for question in res["questions"]:
                stats = question.get("statistics", {})
                stats["start_uri_statistics"] = _serialize_statistics(
                    stats.get("start_uri_statistics")
                )
                stats["end_uri_statistics"] = _serialize_statistics(
                    stats.get("end_uri_statistics")
                )
                stats["statistics"] = _serialize_statistics(stats.get("statistics"))
            yaml.safe_dump(res, f, default_flow_style=False, allow_unicode=True)

    _write_challenge_yaml(
        "wikipedia_challenge.yaml",
        "wikipedia-challenge",
        lambda page: page.wikipedia_url(),
    )
    _write_challenge_yaml(
        "dbpedia_challenge.yaml",
        "dbpedia-challenge",
        lambda page: page.dbpedia_url(),
    )
        