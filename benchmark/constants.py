"""Shared constants for benchmark YAML format and regex patterns."""

import re

# YAML structure keys
BENCHMARK_KEY = "benchmark"
QUESTIONS_KEY = "questions"
QUESTION_KEY = "question"
GOLD_STANDARD_KEY = "gold_standard_answer"
PREDICTED_KEY = "predicted_answer"
TASK_STATE_KEY = "task_state"
PATH_KEY = "path"
METRICS_KEY = "metrics"
TASKS_KEY = "tasks"
PREFIX_VALID_EDGES_KEY = "prefix_valid_edges"
MODEL_KEY = "model"
TRACE_FILE_KEY = "trace_file"

# Regex patterns for URI extraction
ANSWER_URI_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
QUESTION_URI_PATTERN = re.compile(
    r"start URI\s+(?P<start>\S+)\s+and end URI\s+(?P<end>\S+)",
    re.IGNORECASE | re.DOTALL,
)

# Labels
PREFIX_MATCH_LABEL = "Path Prefix Match (PPM)"

# Environment variables
MAX_AGENT_STEPS_ENV = "MAX_AGENT_STEPS"
DEFAULT_MAX_AGENT_STEPS = 10
