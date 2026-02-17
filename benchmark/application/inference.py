"""RunInferenceUseCase: load challenges, run agent per question, store results."""

import os
from typing import Any

from loguru import logger
from opentelemetry import trace

from agent.agents import get_vanilla_web_agent
from agent.clients import get_openai_inference_model
from agent.telemetry import DEFAULT_TRACE_DIR, TRACE_DIR_ENV, init_tracing
from benchmark.constants import (
    BENCHMARK_KEY,
    DEFAULT_MAX_AGENT_STEPS,
    GOLD_STANDARD_KEY,
    MAX_AGENT_STEPS_ENV,
    MODEL_KEY,
    PREDICTED_KEY,
    QUESTION_KEY,
    TASK_STATE_KEY,
    TRACE_FILE_KEY,
)
from benchmark.infrastructure.yaml_io import dump_yaml, iter_entries, iter_yaml_files, load_yaml


def _normalize_answer(answer: Any, include_task_state_in_text: bool = False) -> str:
    """Convert agent answer (list, dict with urls, or string) to string for storage."""
    if answer is None:
        return ""
    return str(answer)


def _extract_answer_and_task_state(answer: Any) -> tuple[str, str | None]:
    """Extract predicted answer string (complete response) and optional task_state from agent result."""
    # Include task_state in predicted_answer so the stored string is the full agent response
    predicted = _normalize_answer(answer, include_task_state_in_text=True)
    task_state = None
    if isinstance(answer, dict) and "task_state" in answer:
        task_state = answer.get("task_state")
        if task_state is not None:
            task_state = str(task_state).strip() or None
    return predicted, task_state


def _model_id() -> str:
    """Get current model identifier from clients."""
    model = get_openai_inference_model()
    model_id = getattr(model, "model_id", None)
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


def _print_inference_config_overview(
    input_dir: str, output_dir: str, trace_dir: str
) -> None:
    """Print configuration overview at the start of a run (paths + env-driven settings)."""
    model_id = getattr(get_openai_inference_model(), "model_id", None) or "unknown"
    max_steps = _max_agent_steps()
    modify_ctx = os.getenv("MODIFY_CONTEXT", "").strip().lower() in ("true", "1", "yes")
    repr_fmt = os.getenv("REPRESENTATION_FORMAT", "wikitext").strip().lower()
    context = os.getenv("CONTEXT", "modified").strip().lower()
    rdf_repr = os.getenv("RDF_REPRESENTATION", "html").strip().lower()
    pruning = os.getenv("PRUNING_METHOD", "unpruned").strip().lower()
    ctx_comp = os.getenv("CONTEXT_COMPRESSION", "").strip().lower() in ("true", "1", "yes")
    max_tokens = os.getenv("MAX_TOKEN_FOR_MODEL", "120000").strip()
    temperature = os.getenv("OPENAI_TEMPERATURE", "").strip() or "(not set)"
    top_p = os.getenv("OPENAI_TOP_P", "").strip() or "(not set)"
    seed = os.getenv("OPENAI_SEED", "").strip() or "(not set)"

    lines = [
        "========== Inference run: configuration overview ==========",
        "Paths:",
        f"  input_dir   = {input_dir}",
        f"  output_dir  = {output_dir}",
        f"  trace_dir   = {trace_dir}",
        "Agent / steps:",
        f"  model_id    = {model_id}",
        f"  MAX_AGENT_STEPS = {max_steps}",
        "Determinism (model sampling):",
        f"  OPENAI_TEMPERATURE = {temperature}",
        f"  OPENAI_TOP_P      = {top_p}",
        f"  OPENAI_SEED       = {seed}",
        "Resource transformation (GET tool):",
        f"  MODIFY_CONTEXT       = {modify_ctx}",
        f"  REPRESENTATION_FORMAT = {repr_fmt}",
        f"  CONTEXT              = {context}",
        f"  RDF_REPRESENTATION   = {rdf_repr}",
        f"  PRUNING_METHOD       = {pruning}",
        "Context compression:",
        f"  CONTEXT_COMPRESSION  = {ctx_comp}",
        f"  MAX_TOKEN_FOR_MODEL  = {max_tokens}",
        "============================================================",
    ]
    print("\n".join(lines))


def _run_agent(question_text: str) -> Any:
    """Invoke vanilla web agent with optional max_steps (uses current OPENAI_MODEL_ID)."""
    agent = get_vanilla_web_agent()
    max_steps = _max_agent_steps()
    if max_steps > 0:
        try:
            return agent.run(question_text, max_steps=max_steps)
        except TypeError:
            return agent.run(question_text)
    return agent.run(question_text)


# Maximum length for error text stored as predicted answer (avoid huge YAML)
_MAX_ERROR_AS_ANSWER_LEN = 2000


def _run_question(question_text: str, trace_dir: str) -> tuple[str, str, str | None]:
    """Run agent for one question, return (normalized_answer, trace_file_path, task_state or None)."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("inference_run") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        trace_file = _trace_file_for_id(trace_dir, trace_id)
        try:
            answer = _run_agent(question_text)
        except Exception as exc:
            print(f"Agent error: {exc}")
            err_msg = str(exc).strip()
            if len(err_msg) > _MAX_ERROR_AS_ANSWER_LEN:
                err_msg = err_msg[:_MAX_ERROR_AS_ANSWER_LEN] + "..."
            return f"Error: {err_msg}", trace_file, "failed"
    print(f"Answer: {answer}")
    predicted, task_state = _extract_answer_and_task_state(answer)
    return predicted, trace_file, task_state


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

        _print_inference_config_overview(abs_input, abs_output, abs_trace)

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
        entries = iter_entries(data)
        if not entries:
            logger.warning(
                "No benchmark/questions entries in %s; expected top-level 'benchmark' or 'questions' list",
                input_path,
            )

        output_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            question_block = entry.get(QUESTION_KEY, {})
            question_text = (
                question_block.get("en")
                if isinstance(question_block, dict)
                else str(question_block)
            )
            predicted_answer, trace_file, task_state = _run_question(question_text, trace_dir)
            entry_dict: dict[str, Any] = {
                "id": entry.get("id"),
                QUESTION_KEY: question_block,
                GOLD_STANDARD_KEY: entry,
                MODEL_KEY: _model_id(),
                PREDICTED_KEY: predicted_answer,
                TRACE_FILE_KEY: trace_file,
            }
            if task_state is not None:
                entry_dict[TASK_STATE_KEY] = task_state
            output_entries.append(entry_dict)

        output_data = {BENCHMARK_KEY: output_entries}
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, os.path.basename(input_path))
        dump_yaml(output_path, output_data)
