#!/usr/bin/env python3
"""Evaluate each benchmark result YAML in out/ for wikipedia and dbpedia.

Discovers *-challenge.yaml files under out/datasets_*/dbpedia and out/datasets_*/wikipedia,
runs benchmark.cli.run_evaluation on each, and writes evaluation.yaml in the same folder.

Usage:
  python scripts/evaluate_out_datasets.py
  python scripts/evaluate_out_datasets.py --out-dir out
  python scripts/evaluate_out_datasets.py --dry-run
  python scripts/evaluate_out_datasets.py --datasource datasets_05 --dataset dbpedia
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Project root: parent of scripts/
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CHALLENGE_SUFFIX = "-challenge.yaml"
EVALUATION_SUFFIX = "-evaluation.yaml"
DATASET_NAMES = ("dbpedia", "wikipedia")


def _discover_result_yamls(
    out_dir: Path,
    *,
    datasource_filter: str | None = None,
    dataset_filter: str | None = None,
) -> list[Path]:
    """Find *-challenge.yaml files under out_dir for dbpedia and wikipedia (exclude traces/)."""
    out_dir = out_dir.resolve()
    if not out_dir.is_dir():
        return []

    result_paths: list[Path] = []
    for top in out_dir.iterdir():
        if not top.is_dir():
            continue
        if datasource_filter is not None and top.name != datasource_filter:
            continue
        for dataset_dir in top.iterdir():
            if not dataset_dir.is_dir():
                continue
            if dataset_dir.name not in DATASET_NAMES:
                continue
            if dataset_filter is not None and dataset_dir.name != dataset_filter:
                continue
            for model_dir in dataset_dir.iterdir():
                if not model_dir.is_dir() or model_dir.name == "traces":
                    continue
                for path in model_dir.iterdir():
                    if path.suffix in (".yaml", ".yml") and path.name.endswith(CHALLENGE_SUFFIX):
                        result_paths.append(path.resolve())
    return sorted(result_paths)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate benchmark result YAMLs in out/ (wikipedia and dbpedia) and save evaluation.yaml per folder."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("out"),
        help="Root directory containing datasets_*/dbpedia and datasets_*/wikipedia (default: out).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print which result files would be evaluated and where evaluation would be written.",
    )
    parser.add_argument(
        "--datasource",
        default=None,
        help="Limit to one datasource folder (e.g. datasets_02, datasets_05).",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        choices=list(DATASET_NAMES),
        help="Limit to one dataset (dbpedia or wikipedia).",
    )
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else PROJECT_ROOT / args.out_dir
    result_paths = _discover_result_yamls(
        out_dir,
        datasource_filter=args.datasource,
        dataset_filter=args.dataset,
    )

    if not result_paths:
        print("No result YAML files found.", file=sys.stderr)
        return 0

    if args.dry_run:
        for p in result_paths:
            out_path = p.parent / f"{p.stem}{EVALUATION_SUFFIX}"
            print(f"  {p} -> {out_path}")
        return 0

    failed: list[tuple[Path, str]] = []
    for result_path in result_paths:
        output_path = result_path.parent / f"{result_path.stem}{EVALUATION_SUFFIX}"
        print(f"Evaluating: {result_path} -> {output_path}")
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "benchmark.cli.run_evaluation",
                    str(result_path),
                    "--output",
                    str(output_path),
                ],
                check=True,
                cwd=str(PROJECT_ROOT),
            )
        except subprocess.CalledProcessError as e:
            failed.append((result_path, str(e)))
            print(f"  Failed: {e}", file=sys.stderr)

    if failed:
        print(f"\n{len(failed)} evaluation(s) failed:", file=sys.stderr)
        for path, err in failed:
            print(f"  {path}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
