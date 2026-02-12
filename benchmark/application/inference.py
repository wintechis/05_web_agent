"""RunInferenceUseCase: load challenges, run agent per question, store results."""

import os
from typing import Any

from opentelemetry import trace

from agent.agents import vanilla_web_agent
from benchmark.constants import (
    BENCHMARK_KEY,
    DEFAULT_MAX_AGENT_STEPS,
    GOLD_STANDARD_KEY,
    MAX_AGENT_STEPS_ENV,
    MODEL_KEY,
    PREDICTED_KEY,
    QUESTION_KEY,
    QUESTIONS_KEY,
    TRACE_FILE_KEY,
)
from benchmark.infrastructure.yaml_io import dump_yaml, iter_yaml_files, load_yaml
from agent.clients import openai_inference_model
from agent.telemetry import DEFAULT_TRACE_DIR, TRACE_DIR_ENV, init_tracing


def _normalize_answer(answer: Any) -> str:
    """Convert agent answer to string for storage."""
    if answer is None:
        return ""
    if isinstance(answer, list):
        return "\n".join(str(item) for item in answer)
    return str(answer)


def _model_id() -> str:
    """Get current model identifier from clients."""
    model_id = getattr(openai_inference_model, "model_id", None)
    return str(model_id) if model_id else "unknown"


def _trace_file_for_id(trace_dir: str, trace_id: str) -> str:
    """Build trace file path for trace ID."""
    return os.path.join(trace_dir, f"{trace_id}.jsonl")


def _max_agent_steps() -> int:
    """Parse MAX_AGENT_STEPS from env, default to DEFAULT_MAX_AGENT_STEPS."""
    raw_value = os.getenv(MAX_AGENT_STEPS_ENV, "")
    if not raw_value:
        return DEFAULT_MAX_AGENT_STEPS
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return DEFAULT_MAX_AGENT_STEPS


def _run_agent(question_text: str) -> Any:
    """Invoke vanilla web agent with optional max_steps."""
    max_steps = _max_agent_steps()
    if max_steps > 0:
        try:
            return vanilla_web_agent.run(question_text, max_steps=max_steps)
        except TypeError:
            return vanilla_web_agent.run(question_text)
    return vanilla_web_agent.run(question_text)


def _run_question(question_text: str, trace_dir: str) -> tuple[str, str]:
    """Run agent for one question, return (normalized_answer, trace_file_path)."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("inference_run") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        trace_file = _trace_file_for_id(trace_dir, trace_id)
        try:
            answer = _run_agent(question_text)
        except Exception as exc:
            print(f"Agent error: {exc}")
            return "", trace_file
    print(f"Answer: {answer}")
    return _normalize_answer(answer), trace_file


class RunInferenceUseCase:
    """Run benchmark inference: load challenges, execute agent, persist results."""

    def run(
        self,
        input_dir: str,
        output_dir: str,
        trace_dir: str | None = None,
    ) -> None:
        """
        Process all YAML files in input_dir, run agent per question, write to output_dir.
        If trace_dir is None, use TRACE_DIR_ENV or DEFAULT_TRACE_DIR.
        """
        abs_input = os.path.abspath(input_dir)
        abs_output = os.path.abspath(output_dir)
        abs_trace = (
            os.path.abspath(trace_dir)
            if trace_dir
            else os.path.abspath(os.getenv(TRACE_DIR_ENV, DEFAULT_TRACE_DIR))
        )

        os.environ[TRACE_DIR_ENV] = abs_trace
        init_tracing()

        yaml_files = list(iter_yaml_files(abs_input))
        if not yaml_files:
            raise ValueError(f"No YAML files found in {abs_input}")

        for input_path in yaml_files:
            self._run_benchmark_file(input_path, abs_output, abs_trace)

    def _run_benchmark_file(
        self, input_path: str, output_dir: str, trace_dir: str
    ) -> None:
        """Process single YAML file and write results."""
        data = load_yaml(input_path)
        questions = data.get(QUESTIONS_KEY, [])
        if not isinstance(questions, list):
            raise ValueError(f"Missing '{QUESTIONS_KEY}' list in {input_path}")

        output_entries: list[dict[str, Any]] = []
        for entry in questions:
            if not isinstance(entry, dict):
                continue
            question_block = entry.get(QUESTION_KEY, {})
            question_text = (
                question_block.get("en")
                if isinstance(question_block, dict)
                else str(question_block)
            )
            predicted_answer, trace_file = _run_question(question_text, trace_dir)
            output_entries.append(
                {
                    "id": entry.get("id"),
                    QUESTION_KEY: question_block,
                    GOLD_STANDARD_KEY: entry,
                    MODEL_KEY: _model_id(),
                    PREDICTED_KEY: predicted_answer,
                    TRACE_FILE_KEY: trace_file,
                }
            )

        output_data = {BENCHMARK_KEY: output_entries}
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, os.path.basename(input_path))
        dump_yaml(output_path, output_data)
