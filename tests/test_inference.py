"""Tests for _extract_answer_and_task_state (Bug 1 fix: structured answer preserves URL list)."""

import pytest
from benchmark.application.inference import _extract_answer_and_task_state, _normalize_answer


class TestExtractAnswerAndTaskState:
    """The primary bug: StructuredFinalAnswerTool returns a dict, which was previously
    str()-ified, corrupting URLs with trailing quotes when regex-extracted later.
    After the fix, the urls list is returned directly."""

    def test_structured_answer_returns_url_list(self):
        answer = {"urls": ["https://en.wikipedia.org/wiki/A", "https://en.wikipedia.org/wiki/B"], "task_state": "completed"}
        predicted, task_state = _extract_answer_and_task_state(answer)
        assert predicted == ["https://en.wikipedia.org/wiki/A", "https://en.wikipedia.org/wiki/B"]
        assert task_state == "completed"

    def test_structured_answer_url_list_has_no_trailing_quotes(self):
        """Regression: before fix, URLs had trailing ' from Python dict repr."""
        answer = {"urls": ["https://en.wikipedia.org/wiki/Target"], "task_state": "completed"}
        predicted, _ = _extract_answer_and_task_state(answer)
        assert predicted == ["https://en.wikipedia.org/wiki/Target"]
        assert not predicted[0].endswith("'"), "URL must not have a trailing quote"
        assert not predicted[0].endswith('"'), "URL must not have a trailing double-quote"

    def test_structured_answer_extracts_task_state(self):
        for state in ("completed", "partial", "failed", "unclear"):
            answer = {"urls": [], "task_state": state}
            _, task_state = _extract_answer_and_task_state(answer)
            assert task_state == state

    def test_structured_answer_empty_urls(self):
        answer = {"urls": [], "task_state": "failed"}
        predicted, task_state = _extract_answer_and_task_state(answer)
        assert predicted == []
        assert task_state == "failed"

    def test_structured_answer_none_urls(self):
        answer = {"urls": None, "task_state": "unclear"}
        predicted, task_state = _extract_answer_and_task_state(answer)
        assert predicted == []

    def test_string_answer_falls_back_to_normalize(self):
        answer = "https://en.wikipedia.org/wiki/Paris"
        predicted, task_state = _extract_answer_and_task_state(answer)
        assert predicted == "https://en.wikipedia.org/wiki/Paris"
        assert task_state is None

    def test_none_answer(self):
        predicted, task_state = _extract_answer_and_task_state(None)
        assert predicted == ""
        assert task_state is None

    def test_dict_without_urls_key_uses_str_fallback(self):
        answer = {"task_state": "failed"}
        predicted, task_state = _extract_answer_and_task_state(answer)
        assert task_state == "failed"
        # No urls key → string fallback
        assert isinstance(predicted, str)
