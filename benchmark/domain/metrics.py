"""Metrics computation: CSR, TSR, PO, PPM for benchmark evaluation."""

from typing import Iterable

from loguru import logger

from benchmark.domain.edge_validator import EdgeValidator
from benchmark.domain.models import EvaluationMetrics, Path, TaskEntry, TaskResult


def _common_prefix_ratio(predicted: list[str], gold: list[str]) -> float:
    """Ratio of matched edges in common prefix to total gold edges."""
    if len(gold) <= 1:
        return 0.0
    match_len = 0
    for pred_uri, gold_uri in zip(predicted, gold):
        if pred_uri != gold_uri:
            break
        match_len += 1
    matched_edges = max(match_len - 1, 0)
    gold_edges = len(gold) - 1
    return matched_edges / gold_edges if gold_edges > 0 else 0.0


def _common_prefix(predicted: list[str], gold: list[str]) -> list[str]:
    """Longest common prefix of predicted and gold paths."""
    prefix: list[str] = []
    for pred_uri, gold_uri in zip(predicted, gold):
        if pred_uri != gold_uri:
            break
        prefix.append(pred_uri)
    return prefix


class MetricsCalculator:
    """Computes evaluation metrics from task entries."""

    def __init__(self, edge_validator: EdgeValidator | None = None) -> None:
        self._edge_validator = edge_validator or EdgeValidator()

    def compute(
        self, tasks: Iterable[TaskEntry]
    ) -> tuple[EvaluationMetrics, list[TaskResult]]:
        """Compute CSR, TSR, PO, PPM and per-task results."""
        task_list = list(tasks)
        total = len(task_list)
        if total == 0:
            return (
                EvaluationMetrics(csr=0.0, tsr=0.0, po=0.0, ppm=0.0),
                [],
            )

        claimed = 0
        success = 0
        po_sum = 0.0
        prefix_sum = 0.0
        task_results: list[TaskResult] = []

        for entry in task_list:
            gold = list(entry.gold_path.uris)
            predicted = list(entry.predicted_path.uris)
            target_uri = entry.target_uri

            if predicted:
                claimed += 1

            valid_edges_list = self._edge_validator.validate_edges(predicted)
            all_valid = all(valid_edges_list)

            is_success = (
                all_valid
                and target_uri is not None
                and predicted
                and predicted[-1] == target_uri
            )

            prefix_path = _common_prefix(predicted, gold)
            prefix_ratio = _common_prefix_ratio(predicted, gold)
            prefix_valid_edges = self._edge_validator.valid_edges_in_path(prefix_path)
            prefix_sum += prefix_ratio

            logger.info(
                "task_id={} predicted_len={} valid={} success={} start_uri={} target_uri={} prefix_ratio={:.3f}",
                entry.task_id,
                len(predicted),
                all_valid,
                is_success,
                entry.start_uri,
                target_uri,
                prefix_ratio,
            )

            task_results.append(
                TaskResult(
                    task_id=entry.task_id,
                    predicted_length=len(predicted),
                    valid_edges=all_valid,
                    success=is_success,
                    start_uri=entry.start_uri,
                    target_uri=target_uri,
                    prefix_ratio=prefix_ratio,
                    prefix_valid_edges=prefix_valid_edges,
                )
            )

            if is_success:
                success += 1
                shortest = len(gold) if gold else 0
                predicted_len = len(predicted)
                if shortest > 0:
                    po_sum += predicted_len / shortest

        csr = claimed / total
        tsr = success / total
        po = po_sum / success if success > 0 else 0.0
        ppm = prefix_sum / total

        metrics = EvaluationMetrics(csr=csr, tsr=tsr, po=po, ppm=ppm)
        return metrics, task_results
