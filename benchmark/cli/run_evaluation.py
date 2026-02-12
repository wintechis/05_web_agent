"""CLI for evaluating benchmark results."""

import argparse
import os

from benchmark.application.evaluation import RunEvaluationUseCase


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate benchmark results and report metrics."
    )
    parser.add_argument(
        "results_file",
        help="Path to a results YAML file (e.g. benchmark/experiments/01/wikipedia.yaml).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write evaluation metrics as YAML.",
    )
    args = parser.parse_args()

    results_path = os.path.abspath(args.results_file)
    use_case = RunEvaluationUseCase()
    use_case.run(results_path, output_path=args.output)


if __name__ == "__main__":
    main()
