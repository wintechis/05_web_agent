"""Edge validation: check if consecutive URIs in a path are valid (linked)."""

from functools import lru_cache

from benchmark.infrastructure.uri_contains import uri_contains


@lru_cache(maxsize=4096)
def _edge_exists(container_uri: str, candidate_uri: str) -> bool:
    """Check if container_uri page contains link to candidate_uri. Cached for performance."""
    return uri_contains(container_uri, candidate_uri)


class EdgeValidator:
    """Validates that consecutive URIs in a path are connected (candidate reachable from container)."""

    def validate_edges(self, path: list[str]) -> list[bool]:
        """Return list of bools: True if edge (path[i] -> path[i+1]) is valid."""
        if len(path) <= 1:
            return []
        return [
            _edge_exists(path[index], path[index + 1])
            for index in range(len(path) - 1)
        ]

    def all_edges_valid(self, path: list[str]) -> bool:
        """Return True if all consecutive edges in path are valid."""
        return all(self.validate_edges(path))

    def valid_edges_in_path(self, path: list[str]) -> list[dict[str, str]]:
        """Return list of valid edges as {'from': uri, 'to': uri} dicts."""
        result: list[dict[str, str]] = []
        for index in range(len(path) - 1):
            from_uri = path[index]
            to_uri = path[index + 1]
            if _edge_exists(from_uri, to_uri):
                result.append({"from": from_uri, "to": to_uri})
        return result
