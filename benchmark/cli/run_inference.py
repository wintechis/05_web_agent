"""CLI for running benchmark inference."""

import argparse
import os

from benchmark.application.inference import RunInferenceUseCase
from agent.telemetry import TRACE_DIR_ENV


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run benchmark questions and store YAML outputs."
    )
    parser.add_argument("input_folder", help="Folder with benchmark YAML files.")
    parser.add_argument("output_folder", help="Folder to store YAML results.")
    parser.add_argument(
        "--trace-dir",
        default=None,
        help="Folder to store per-trace JSONL files. Default: output_folder/traces.",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_folder)
    output_dir = os.path.abspath(args.output_folder)
    default_trace_dir = os.path.join(output_dir, "traces")
    trace_dir = (
        os.path.abspath(args.trace_dir)
        if args.trace_dir
        else os.path.abspath(os.getenv(TRACE_DIR_ENV, default_trace_dir))
    )

    use_case = RunInferenceUseCase()
    use_case.run(input_dir=input_dir, output_dir=output_dir, trace_dir=trace_dir)


if __name__ == "__main__":
    main()
