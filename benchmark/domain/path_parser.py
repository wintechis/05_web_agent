"""Parse paths from YAML dict formats (gold standard, predicted)."""

from typing import Any

from benchmark.constants import (
    ANSWER_URI_PATTERN,
    GOLD_STANDARD_KEY,
    PATH_KEY,
    PREDICTED_KEY,
    QUESTION_KEY,
)


def strip_answer_wrapper(text: str) -> str:
    """Remove <answer> and </answer> tags from text."""
    return text.replace("<answer>", " ").replace("</answer>", " ")


def extract_uris(text: str) -> list[str]:
    """Extract HTTP(S) URIs from text, stripping answer wrapper and trailing punctuation."""
    if not text:
        return []
    cleaned = strip_answer_wrapper(text)
    return [match.group(0).rstrip(".,)") for match in ANSWER_URI_PATTERN.finditer(cleaned)]


def parse_predicted(entry: dict[str, Any]) -> list[str]:
    """Parse predicted answer from entry. Handles list or string format."""
    predicted = entry.get(PREDICTED_KEY, "")
    if isinstance(predicted, list):
        return [str(item) for item in predicted if str(item).strip()]
    return extract_uris(str(predicted))


def parse_gold_path(entry: dict[str, Any]) -> list[str]:
    """Parse gold standard path from entry. Handles dict, list, or string format."""
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


def parse_question_text(entry: dict[str, Any]) -> str:
    """Parse question text from entry. Handles dict with 'en' key or plain string."""
    question_block = entry.get(QUESTION_KEY, "")
    if isinstance(question_block, dict):
        return str(question_block.get("en", ""))
    return str(question_block)
