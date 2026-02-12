import argparse
import os
import re
from functools import lru_cache
from typing import Any, Iterable

import yaml
from loguru import logger

from uri_contains import uri_contains

ANSWER_URI_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
QUESTION_URI_PATTERN = re.compile(
    r"start URI\s+(?P<start>\S+)\s+and end URI\s+(?P<end>\S+)",
    re.IGNORECASE | re.DOTALL,
)
BENCHMARK_KEY = "benchmark"
QUESTIONS_KEY = "questions"
QUESTION_KEY = "question"
GOLD_STANDARD_KEY = "gold_standard_answer"
PREDICTED_KEY = "predicted_answer"
PATH_KEY = "path"
PREFIX_MATCH_LABEL = "Path Prefix Match (PPM)"
METRICS_KEY = "metrics"
TASKS_KEY = "tasks"
PREFIX_VALID_EDGES_KEY = "prefix_valid_edges"


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML format in {path}")
    return data


def _dump_yaml(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def _iter_entries(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    if BENCHMARK_KEY in data and isinstance(data[BENCHMARK_KEY], list):
        return [entry for entry in data[BENCHMARK_KEY] if isinstance(entry, dict)]
    if QUESTIONS_KEY in data and isinstance(data[QUESTIONS_KEY], list):
        return [entry for entry in data[QUESTIONS_KEY] if isinstance(entry, dict)]
    return []


def _strip_answer_wrapper(text: str) -> str:
    cleaned = text.replace("<answer>", " ").replace("</answer>", " ")
    return cleaned


def _extract_uris(text: str) -> list[str]:
    if not text:
        return []
    cleaned = _strip_answer_wrapper(text)
    return [match.group(0).rstrip(".,)") for match in ANSWER_URI_PATTERN.finditer(cleaned)]


def _parse_predicted(entry: dict[str, Any]) -> list[str]:
    predicted = entry.get(PREDICTED_KEY, "")
    if isinstance(predicted, list):
        return [str(item) for item in predicted if str(item).strip()]
    return _extract_uris(str(predicted))


def _parse_gold_path(entry: dict[str, Any]) -> list[str]:
    gold = entry.get(GOLD_STANDARD_KEY, "")
    if isinstance(gold, dict):
        gold = gold.get(PATH_KEY, "")
    if isinstance(gold, list):
        return [str(item) for item in gold if str(item).strip()]
    if isinstance(gold, str):
        lines = [line.strip() for line in gold.splitlines() if line.strip()]
        if lines:
            return lines
    return []


def _parse_question_text(entry: dict[str, Any]) -> str:
    question_block = entry.get(QUESTION_KEY, "")
    if isinstance(question_block, dict):
        return str(question_block.get("en", ""))
    return str(question_block)


def _parse_start_target(gold_path: list[str]) -> tuple[str | None, str | None]:
    match = QUESTION_URI_PATTERN.search(question_text)
    if match:
        return match.group("start"), match.group("end")
    if gold_path:
        return gold_path[0], gold_path[-1]
    return None, None


@lru_cache(maxsize=4096)
def _edge_exists(container_uri: str, candidate_uri: str) -> bool:
    return uri_contains(container_uri, candidate_uri)


def valid_edges(path: list[str], start_uri: str | None) -> bool:
    return [_edge_exists(path[index], path[index + 1]) for index in range(len(path) - 1)]


def _path_length(path: list[str]) -> int:
    return len(path)


def _common_prefix_ratio(predicted: list[str], gold: list[str]) -> float:
    if len(gold) <= 1:
        return 0.0
    match_len = 0
    for predicted_uri, gold_uri in zip(predicted, gold):
        if predicted_uri != gold_uri:
            break
        match_len += 1
    matched_edges = max(match_len - 1, 0)
    gold_edges = len(gold) - 1
    return matched_edges / gold_edges if gold_edges > 0 else 0.0


def _common_prefix(predicted: list[str], gold: list[str]) -> list[str]:
    prefix: list[str] = []
    for predicted_uri, gold_uri in zip(predicted, gold):
        if predicted_uri != gold_uri:
            break
        prefix.append(predicted_uri)
    return prefix


def _valid_edges_in_prefix(prefix_path: list[str]) -> list[dict[str, str]]:
    valid_edges: list[dict[str, str]] = []
    for index in range(len(prefix_path) - 1):
        from_uri = prefix_path[index]
        to_uri = prefix_path[index + 1]
        if _edge_exists(from_uri, to_uri):
            valid_edges.append({"from": from_uri, "to": to_uri})
    return valid_edges


def _compute_metrics(entries: Iterable[dict[str, Any]]) -> tuple[float, float, float, float, list[dict[str, Any]]]:
    tasks = list(entries)
    total = len(tasks)
    if total == 0:
        return 0.0, 0.0, 0.0, 0.0, []

    claimed = 0
    success = 0
    po_sum = 0.0
    prefix_sum = 0.0
    task_details: list[dict[str, Any]] = []

    for entry in tasks:
        task_id = entry.get("id", "unknown")
        gold_path = _parse_gold_path(entry)
        question_text = _parse_question_text(entry)
        predicted_path = _parse_predicted(entry)
        start_uri, target_uri = gold_path[0], gold_path[-1]

        if predicted_path:
            claimed += 1

        valid_edges_list = valid_edges(predicted_path, start_uri)
        

        is_success = (
            all(valid_edges_list)
            and target_uri is not None
            and predicted_path
            and predicted_path[-1] == target_uri
        )
        
        prefix_path = _common_prefix(predicted_path, gold_path)
        prefix_ratio = _common_prefix_ratio(predicted_path, gold_path)
        prefix_valid_edges = _valid_edges_in_prefix(prefix_path)
        prefix_sum += prefix_ratio
        logger.info(
            "task_id={} predicted_len={} valid={} success={} start_uri={} target_uri={} prefix_ratio={:.3f}",
            task_id,
            len(predicted_path),
            all(valid_edges_list),
            is_success,
            start_uri,
            target_uri,
            prefix_ratio,
        )
        task_details.append(
            {
                "id": task_id,
                "predicted_length": len(predicted_path),
                "valid": all(valid_edges_list),
                "success": is_success,
                "start_uri": start_uri,
                "target_uri": target_uri,
                "prefix_ratio": prefix_ratio,
                PREFIX_VALID_EDGES_KEY: prefix_valid_edges,
            }
        )
        if is_success:
            success += 1
            shortest = _path_length(gold_path) if gold_path else 0
            predicted_len = _path_length(valid_edges_list) if valid_edges_list else 0
            if shortest > 0:
                po_sum += predicted_len / shortest

    csr = claimed / total
    tsr = success / total
    po = po_sum / success if success > 0 else 0.0
    ppm = prefix_sum / total
    return csr, tsr, po, ppm, task_details


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate benchmark results and report metrics."
    )
    parser.add_argument(
        "results_file",
        help="Path to a results YAML file (e.g. benchmark/experiments/01/wikipedia.yaml).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write evaluation metrics as YAML.",
    )
    args = parser.parse_args()

    results_path = os.path.abspath(args.results_file)
    logger.info("Evaluating results file: {}", results_path)
    data = _load_yaml(results_path)
    entries = _iter_entries(data)
    logger.info("Loaded {} entries", len(entries))
    csr, tsr, po, ppm, task_details = _compute_metrics(entries)

    print(f"Claimed Success Rate (CSR): {csr:.4f}")
    print(f"True Success Rate (TSR): {tsr:.4f}")
    print(f"Path Optimality (PO): {po:.4f}")
    print(f"{PREFIX_MATCH_LABEL}: {ppm:.4f}")

    if args.output:
        output_path = os.path.abspath(args.output)
        output_data = {
            METRICS_KEY: {
                "csr": csr,
                "tsr": tsr,
                "po": po,
                "ppm": ppm,
            },
            TASKS_KEY: task_details,
        }
        _dump_yaml(output_path, output_data)
        logger.info("Wrote evaluation results to {}", output_path)


if __name__ == "__main__":
    main()