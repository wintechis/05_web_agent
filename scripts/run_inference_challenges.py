#!/usr/bin/env python3
"""Run inference over all challenges (challenges/dbpedia, challenges/wikipedia) for each (experiment, model) pair.

Uses run_inference_hydra.py with datasource=challenges. Each experiment writes to its own output subtree
out/challenges_run/<experiment>/<dataset>/<model_slug>/ so results are not overwritten across experiments.
Experiments and models are discovered from config/experiment/*.yaml and config/model/*.yaml; experiments
can be blacklisted, models are whitelisted (if --models is empty, all models run).

Usage:
  python scripts/run_inference_challenges.py
  python scripts/run_inference_challenges.py --models qwen3_coder_30b,llama_3_3_70b
  python scripts/run_inference_challenges.py --experiment-blacklist compression_dbpedia_html --dry-run
  EXPERIMENT_BLACKLIST=exp1,exp2 python scripts/run_inference_challenges.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Project root: parent of scripts/
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CONFIG_EXPERIMENT_DIR = PROJECT_ROOT / "config" / "experiment"
CONFIG_MODEL_DIR = PROJECT_ROOT / "config" / "model"
HYDRA_ENTRY = "run_inference_hydra.py"
CHALLENGES_INPUT_PREFIX = "challenges_tiny"
CHALLENGES_OUTPUT_PREFIX = "out/challenges_run"
DATASOURCE_CHALLENGES = "challenges"
DATASET_KEY = "dataset"
VALID_DATASETS = ("dbpedia", "wikipedia")


def _discover_config_stems(config_dir: Path) -> list[str]:
    """Return sorted list of YAML file stems in config_dir (e.g. experiment or model names)."""
    if not config_dir.is_dir():
        return []
    stems = [p.stem for p in config_dir.glob("*.yaml")]
    return sorted(stems)


def _parse_list(value: str | None) -> set[str]:
    """Parse comma-separated string into set of non-empty stripped names."""
    if not value or not value.strip():
        return set()
    return {s.strip() for s in value.split(",") if s.strip()}


def _experiment_dataset(experiment_name: str) -> str:
    """Return dataset (dbpedia or wikipedia) for the given experiment from its config YAML."""
    path = CONFIG_EXPERIMENT_DIR / f"{experiment_name}.yaml"
    if not path.is_file():
        raise ValueError(f"Experiment config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    dataset = (data or {}).get(DATASET_KEY)
    if dataset not in VALID_DATASETS:
        raise ValueError(f"Experiment {experiment_name} has invalid or missing dataset: {dataset!r}")
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run inference on challenges/dbpedia and challenges/wikipedia for each (experiment, model) pair."
    )
    parser.add_argument(
        "--experiment-blacklist",
        type=str,
        default=os.getenv("EXPERIMENT_BLACKLIST", ""),
        help="Comma-separated experiment names to skip (default: env EXPERIMENT_BLACKLIST).",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help="Comma-separated model names to run; if empty, run all models.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print (experiment, model) pairs that would be run.",
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        metavar="OVERRIDE",
        help="Extra Hydra overrides (e.g. input_folder=path). Can be repeated.",
    )
    args = parser.parse_args()

    experiments = _discover_config_stems(CONFIG_EXPERIMENT_DIR)
    models = _discover_config_stems(CONFIG_MODEL_DIR)
    if not experiments:
        print("No experiments found in config/experiment/.", file=sys.stderr)
        return 1
    if not models:
        print("No models found in config/model/.", file=sys.stderr)
        return 1

    blacklist = _parse_list(args.experiment_blacklist)
    experiments_filtered = [e for e in experiments if e not in blacklist]
    if blacklist:
        print(f"Experiment blacklist: {sorted(blacklist)}", file=sys.stderr)

    models_requested = _parse_list(args.models)
    models_filtered = [m for m in models if m in models_requested] if models_requested else models

    pairs: list[tuple[str, str]] = []
    for exp in experiments_filtered:
        for model in models_filtered:
            pairs.append((exp, model))

    if not pairs:
        print("No (experiment, model) pairs to run.", file=sys.stderr)
        return 0

    if args.dry_run:
        for exp, model in pairs:
            try:
                dataset = _experiment_dataset(exp)
                out = f"{CHALLENGES_OUTPUT_PREFIX}/{exp}/{dataset}/<model_slug>"
            except (ValueError, OSError) as e:
                out = f"(error: {e})"
            print(f"  experiment={exp} model={model} -> {out}")
        print(f"Total: {len(pairs)} pairs.", file=sys.stderr)
        return 0

    failed: list[tuple[str, str, str]] = []
    for exp, model in pairs:
        try:
            dataset = _experiment_dataset(exp)
        except (ValueError, OSError) as e:
            failed.append((exp, model, str(e)))
            print(f"  Failed to get dataset for {exp}: {e}", file=sys.stderr)
            continue
        input_folder = f"{CHALLENGES_INPUT_PREFIX}/{dataset}"
        output_folder = f"{CHALLENGES_OUTPUT_PREFIX}/{exp}/{dataset}"
        print(f"Running experiment={exp} model={model} -> {output_folder}/<model>/ ...")
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / HYDRA_ENTRY),
            f"datasource={DATASOURCE_CHALLENGES}",
            f"experiment={exp}",
            f"model={model}",
            f"input_folder={input_folder}",
            f"output_folder={output_folder}",
            *args.extra,
        ]
        try:
            subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
        except subprocess.CalledProcessError as e:
            failed.append((exp, model, str(e)))
            print(f"  Failed: {e}", file=sys.stderr)

    if failed:
        print(f"\n{len(failed)} run(s) failed:", file=sys.stderr)
        for exp, model, err in failed:
            print(f"  experiment={exp} model={model}: {err}", file=sys.stderr)
        return 1
    print(f"All {len(pairs)} runs finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
