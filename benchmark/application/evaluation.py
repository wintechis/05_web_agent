"""RunEvaluationUseCase: load results, compute metrics, optionally persist."""

import os
from typing import Any

from loguru import logger

from benchmark.constants import METRICS_KEY, PREFIX_VALID_EDGES_KEY, TASKS_KEY
from benchmark.domain.metrics import MetricsCalculator
from benchmark.domain.models import EvaluationMetrics, Path, TaskEntry, TaskResult
from benchmark.domain.path_parser import (
    parse_gold_path,
    parse_predicted,
    parse_question_text,
)
from benchmark.infrastructure.yaml_io import dump_yaml, iter_entries, load_yaml


class RunEvaluationUseCase:
    """Evaluate benchmark results and optionally persist metrics."""

    def __init__(self) -> None:
        self._metrics_calculator = MetricsCalculator()

    def run(self, results_path: str, output_path: str | None = None) -> None:
        """Load results, compute metrics, print to stdout. Optionally write YAML to output_path."""
        abs_path = os.path.abspath(results_path)
        logger.info("Evaluating results file: {}", abs_path)

        data = load_yaml(abs_path)
        entries = iter_entries(data)
        logger.info("Loaded {} entries", len(entries))

        task_entries = self._entries_to_task_entries(entries)
        metrics, task_results = self._metrics_calculator.compute(task_entries)

        self._print_metrics(metrics)

        if output_path:
            self._persist_output(output_path, metrics, task_results)

    def _entries_to_task_entries(
        self, entries: list[dict[str, Any]]
    ) -> list[TaskEntry]:
        """Convert raw YAML entries to TaskEntry domain objects."""
        result: list[TaskEntry] = []
        for entry in entries:
            gold_uris = parse_gold_path(entry)
            predicted_uris = parse_predicted(entry)
            task_entry = TaskEntry(
                task_id=entry.get("id", "unknown"),
                question_text=parse_question_text(entry),
                gold_path=Path(uris=tuple(gold_uris)),
                predicted_path=Path(uris=tuple(predicted_uris)),
            )
            result.append(task_entry)
        return result

    def _print_metrics(self, metrics: EvaluationMetrics) -> None:
        """Print metrics to stdout."""
        from benchmark.constants import PREFIX_MATCH_LABEL

        print(f"Claimed Success Rate (CSR): {metrics.csr:.4f}")
        print(f"True Success Rate (TSR): {metrics.tsr:.4f}")
        print(f"Path Optimality (PO): {metrics.po:.4f}")
        print(f"{PREFIX_MATCH_LABEL}: {metrics.ppm:.4f}")

    def _persist_output(
        self, output_path: str, metrics: EvaluationMetrics, task_results: list[TaskResult]
    ) -> None:
        """Write metrics and task details to YAML."""
        abs_output = os.path.abspath(output_path)
        task_details = [
            {
                "id": r.task_id,
                "predicted_length": r.predicted_length,
                "valid": r.valid_edges,
                "success": r.success,
                "start_uri": r.start_uri,
                "target_uri": r.target_uri,
                "prefix_ratio": r.prefix_ratio,
                PREFIX_VALID_EDGES_KEY: r.prefix_valid_edges,
            }
            for r in task_results
        ]
        output_data = {
            METRICS_KEY: {
                "csr": metrics.csr,
                "tsr": metrics.tsr,
                "po": metrics.po,
                "ppm": metrics.ppm,
            },
            TASKS_KEY: task_details,
        }
        dump_yaml(abs_output, output_data)
        logger.info("Wrote evaluation results to {}", abs_output)
