"""Tests for MetricsCalculator: TSR, PO, CSR, PPM."""

import pytest
from unittest.mock import patch
from benchmark.domain.metrics import MetricsCalculator
from benchmark.domain.models import EvaluationMetrics, Path, TaskEntry


def _entry(task_id: str, gold: list[str], predicted: list[str]) -> TaskEntry:
    return TaskEntry(
        task_id=task_id,
        question_text="",
        gold_path=Path(uris=tuple(gold)),
        predicted_path=Path(uris=tuple(predicted)),
    )


def _make_calculator(all_edges_valid: bool = True) -> MetricsCalculator:
    """Create a MetricsCalculator that stubs out HTTP edge validation."""
    calc = MetricsCalculator()
    # Replace the real EdgeValidator with one whose result is controlled
    calc._edge_validator.validate_edges = lambda path: [all_edges_valid] * max(len(path) - 1, 0)
    calc._edge_validator.valid_edges_in_path = lambda path: (
        [{"from": path[i], "to": path[i + 1]} for i in range(len(path) - 1)] if all_edges_valid else []
    )
    return calc


GOLD = ["https://en.wikipedia.org/wiki/A", "https://en.wikipedia.org/wiki/B",
        "https://en.wikipedia.org/wiki/C", "https://en.wikipedia.org/wiki/D"]


class TestTSR:
    """True Success Rate: predicted ends at target AND all edges valid."""

    def test_success_when_exact_gold_path(self):
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, GOLD)
        metrics, _ = calc.compute([entry])
        assert metrics.tsr == 1.0

    def test_success_when_longer_but_valid_and_reaches_target(self):
        detour = GOLD[:1] + ["https://en.wikipedia.org/wiki/X"] + GOLD[1:]
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, detour)
        metrics, _ = calc.compute([entry])
        assert metrics.tsr == 1.0

    def test_failure_when_wrong_last_uri(self):
        wrong_end = GOLD[:-1] + ["https://en.wikipedia.org/wiki/WRONG"]
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, wrong_end)
        metrics, _ = calc.compute([entry])
        assert metrics.tsr == 0.0

    def test_failure_when_invalid_edges(self):
        calc = _make_calculator(all_edges_valid=False)
        entry = _entry("t1", GOLD, GOLD)
        metrics, _ = calc.compute([entry])
        assert metrics.tsr == 0.0

    def test_failure_when_empty_predicted(self):
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, [])
        metrics, _ = calc.compute([entry])
        assert metrics.tsr == 0.0

    def test_tsr_partial_success(self):
        gold2 = ["https://en.wikipedia.org/wiki/X", "https://en.wikipedia.org/wiki/Y"]
        calc = _make_calculator(all_edges_valid=True)
        entries = [
            _entry("t1", GOLD, GOLD),       # success
            _entry("t2", gold2, []),         # failure (empty)
        ]
        metrics, _ = calc.compute(entries)
        assert metrics.tsr == pytest.approx(0.5)


class TestPO:
    """Path Optimality: gold_length / predicted_length (Bug 2 fix)."""

    def test_po_is_1_for_optimal_path(self):
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, GOLD)
        metrics, _ = calc.compute([entry])
        assert metrics.po == pytest.approx(1.0)

    def test_po_is_less_than_1_for_longer_predicted(self):
        """Regression: before fix, po_sum used predicted/gold (> 1), not gold/predicted (≤ 1)."""
        # Insert an extra detour node but still end at the correct target
        detour = [GOLD[0], "https://en.wikipedia.org/wiki/X"] + GOLD[1:]  # 5 nodes, ends at GOLD[-1]
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, detour)
        metrics, _ = calc.compute([entry])
        assert metrics.po == pytest.approx(len(GOLD) / len(detour))
        assert metrics.po < 1.0, "PO must be < 1 when predicted is longer than gold"

    def test_po_is_0_when_no_successes(self):
        calc = _make_calculator(all_edges_valid=False)
        entry = _entry("t1", GOLD, GOLD)
        metrics, _ = calc.compute([entry])
        assert metrics.po == 0.0


class TestPPM:
    """Path Prefix Match: ratio of gold edges matched in common prefix."""

    def test_ppm_is_1_for_identical_paths(self):
        calc = _make_calculator(all_edges_valid=True)
        entry = _entry("t1", GOLD, GOLD)
        metrics, _ = calc.compute([entry])
        assert metrics.ppm == pytest.approx(1.0)

    def test_ppm_is_0_when_first_node_differs(self):
        calc = _make_calculator(all_edges_valid=True)
        predicted = ["https://en.wikipedia.org/wiki/X"] + GOLD[1:]
        entry = _entry("t1", GOLD, predicted)
        metrics, _ = calc.compute([entry])
        assert metrics.ppm == pytest.approx(0.0)

    def test_ppm_partial_prefix_match(self):
        calc = _make_calculator(all_edges_valid=True)
        predicted = GOLD[:2] + ["https://en.wikipedia.org/wiki/X", GOLD[-1]]
        entry = _entry("t1", GOLD, predicted)
        metrics, _ = calc.compute([entry])
        gold_edges = len(GOLD) - 1
        matched_edges = 1  # only A->B matches
        assert metrics.ppm == pytest.approx(matched_edges / gold_edges)


class TestCSR:
    def test_csr_all_claimed(self):
        calc = _make_calculator()
        entries = [_entry(str(i), GOLD, GOLD) for i in range(5)]
        metrics, _ = calc.compute(entries)
        assert metrics.csr == 1.0

    def test_csr_none_claimed(self):
        calc = _make_calculator()
        entries = [_entry(str(i), GOLD, []) for i in range(5)]
        metrics, _ = calc.compute(entries)
        assert metrics.csr == 0.0

    def test_empty_task_list(self):
        calc = _make_calculator()
        metrics, results = calc.compute([])
        assert metrics == EvaluationMetrics(csr=0.0, tsr=0.0, po=0.0, ppm=0.0)
        assert results == []
