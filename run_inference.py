import argparse
import os
from typing import Any, Iterable

import yaml
from opentelemetry import trace

from agents import vanilla_web_agent
from clients import openai_inference_model
from telemetry import DEFAULT_TRACE_DIR, TRACE_DIR_ENV, init_tracing

OUTPUT_KEY = "benchmark"
QUESTIONS_KEY = "questions"
QUESTION_TEXT_KEY = "question"
GOLD_STANDARD_KEY = "gold_standard_answer"
PATH_KEY = "path"
MODEL_KEY = "model"
PREDICTED_KEY = "predicted_answer"
TRACE_FILE_KEY = "trace_file"
MAX_AGENT_STEPS_ENV = "MAX_AGENT_STEPS"
DEFAULT_MAX_AGENT_STEPS = 10


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML format in {path}")
    return data


def _dump_yaml(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def _iter_yaml_files(input_dir: str) -> Iterable[str]:
    for entry in sorted(os.listdir(input_dir)):
        if entry.endswith((".yaml", ".yml")):
            full_path = os.path.join(input_dir, entry)
            if os.path.isfile(full_path):
                yield full_path


def _normalize_answer(answer: Any) -> str:
    if answer is None:
        return ""
    if isinstance(answer, list):
        return "\n".join(str(item) for item in answer)
    return str(answer)



def _model_id() -> str:
    model_id = getattr(openai_inference_model, "model_id", None)
    return str(model_id) if model_id else "unknown"


def _trace_file_for_id(trace_dir: str, trace_id: str) -> str:
    return os.path.join(trace_dir, f"{trace_id}.jsonl")


def _max_agent_steps() -> int:
    raw_value = os.getenv(MAX_AGENT_STEPS_ENV, "")
    if not raw_value:
        return DEFAULT_MAX_AGENT_STEPS
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return DEFAULT_MAX_AGENT_STEPS


def _run_agent(question_text: str) -> Any:
    max_steps = _max_agent_steps()
    if max_steps > 0:
        try:
            return vanilla_web_agent.run(question_text, max_steps=max_steps)
        except TypeError:
            return vanilla_web_agent.run(question_text)
    return vanilla_web_agent.run(question_text)


def _run_question(question_text: str, trace_dir: str) -> tuple[str, str]:
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


def _run_benchmark_file(
    input_path: str,
    output_dir: str,
    trace_dir: str,
) -> None:
    data = _load_yaml(input_path)
    questions = data.get(QUESTIONS_KEY, [])
    if not isinstance(questions, list):
        raise ValueError(f"Missing '{QUESTIONS_KEY}' list in {input_path}")

    output_entries: list[dict[str, Any]] = []
    for entry in questions:
        if not isinstance(entry, dict):
            continue
        question_block = entry.get(QUESTION_TEXT_KEY, {})
        question_text = (
            question_block.get("en")
            if isinstance(question_block, dict)
            else str(question_block)
        )
        predicted_answer, trace_file = _run_question(question_text, trace_dir)
        output_entries.append(
            {
                "id": entry.get("id"),
                QUESTION_TEXT_KEY: question_block,
                GOLD_STANDARD_KEY: entry,
                MODEL_KEY: _model_id(),
                PREDICTED_KEY: predicted_answer,
                TRACE_FILE_KEY: trace_file,
            }
        )

    output_data = {OUTPUT_KEY: output_entries}
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, os.path.basename(input_path))
    _dump_yaml(output_path, output_data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run benchmark questions and store YAML outputs."
    )
    parser.add_argument("input_folder", help="Folder with benchmark YAML files.")
    parser.add_argument("output_folder", help="Folder to store YAML results.")
    parser.add_argument(
        "--trace-dir",
        default=None,
        help="Folder to store per-trace JSONL files.",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_folder)
    output_dir = os.path.abspath(args.output_folder)
    trace_dir = (
        os.path.abspath(args.trace_dir)
        if args.trace_dir
        else os.path.abspath(os.getenv(TRACE_DIR_ENV, DEFAULT_TRACE_DIR))
    )
    
    # Changes the trace directory for the whole run
    os.environ[TRACE_DIR_ENV] = trace_dir
    init_tracing()

    yaml_files = list(_iter_yaml_files(input_dir))
    if not yaml_files:
        raise ValueError(f"No YAML files found in {input_dir}")

    for input_path in yaml_files:
        _run_benchmark_file(input_path, output_dir, trace_dir)


if __name__ == "__main__":
    main()