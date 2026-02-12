"""YAML load/dump and entry iteration for benchmark data."""

import os
from typing import Any, Iterable

import yaml

from benchmark.constants import BENCHMARK_KEY, QUESTIONS_KEY


def load_yaml(path: str) -> dict[str, Any]:
    """Load YAML file and return dict. Raises ValueError if not a dict."""
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML format in {path}")
    return data


def dump_yaml(path: str, data: dict[str, Any]) -> None:
    """Write dict to YAML file."""
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def iter_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract entries from YAML dict, normalizing 'benchmark' or 'questions' keys."""
    if BENCHMARK_KEY in data and isinstance(data[BENCHMARK_KEY], list):
        return [entry for entry in data[BENCHMARK_KEY] if isinstance(entry, dict)]
    if QUESTIONS_KEY in data and isinstance(data[QUESTIONS_KEY], list):
        return [entry for entry in data[QUESTIONS_KEY] if isinstance(entry, dict)]
    return []


def iter_yaml_files(input_dir: str) -> Iterable[str]:
    """Yield full paths to YAML files in directory, sorted by name."""
    for entry in sorted(os.listdir(input_dir)):
        if entry.endswith((".yaml", ".yml")):
            full_path = os.path.join(input_dir, entry)
            if os.path.isfile(full_path):
                yield full_path
