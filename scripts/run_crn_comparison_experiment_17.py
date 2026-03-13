#!/usr/bin/env python3
"""Run CRN vs baseline on experiment 17 dataset and compare benchmark results.

Uses datasource=experiment_17 (evaluation/experiments/17 questions). Runs four
inference jobs with distinct output folders, then evaluates each and prints
a comparison table.

Usage:
  # Use a model your API allows (e.g. qwen3_5_35b)
  python scripts/run_crn_comparison_experiment_17.py --model qwen3_5_35b

  # Dry-run: only print commands
  python scripts/run_crn_comparison_experiment_17.py --model qwen3_5_35b --dry-run

Requires: OPENAI_API_KEY (and OPENAI_BASE_URL if needed) in .env.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
OUT_BASE = ROOT / "out" / "experiment_17"
MODEL_SLUG = {"qwen3_coder_30b": "qwen3-coder-30b-a3b-instruct", "qwen3_5_35b": "Qwen_Qwen3.5-35B-A3B-FP8"}


def _model_slug(model_key: str) -> str:
    """Infer output subfolder from model config name (Hydra uses openai_model_id with / replaced)."""
    if model_key in MODEL_SLUG:
        return MODEL_SLUG[model_key]
    return model_key.replace("/", "_").replace(".", "_").strip() or "unknown"


def run_cmd(cmd: list[str], dry_run: bool) -> bool:
    if dry_run:
        print("Would run:", " ".join(cmd))
        return True
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser(description="CRN vs baseline on experiment 17 dataset")
    ap.add_argument("--model", default="qwen3_5_35b", help="Hydra model config name (default: qwen3_5_35b)")
    ap.add_argument("--dry-run", action="store_true", help="Only print commands, do not run")
    ap.add_argument("--max-steps", type=int, default=10, help="MAX_AGENT_STEPS (default: 10)")
    args = ap.parse_args()
    model_slug = _model_slug(args.model)
    env = os.environ.copy()
    env["MAX_AGENT_STEPS"] = str(args.max_steps)

    # Pass both input_folder and output_folder so Hydra uses them (otherwise it uses datasource defaults)
    input_base = "evaluation/experiments/17/questions"
    jobs = [
        ("DBpedia baseline (semantic_outgoing_turtle)", "semantic_outgoing_turtle", "dbpedia", "dbpedia_baseline"),
        ("DBpedia CRN", "crn_dbpedia", "dbpedia", "dbpedia_crn"),
        ("Wikipedia baseline (semantic_wikipedia_html_wikitext)", "semantic_wikipedia_html_wikitext", "wikipedia", "wikipedia_baseline"),
        ("Wikipedia CRN", "crn_wikipedia", "wikipedia", "wikipedia_crn"),
    ]
    ok = True
    for label, experiment, dataset, out_suffix in jobs:
        out_dir = OUT_BASE / out_suffix / model_slug
        input_dir = f"{input_base}/{dataset}"
        cmd = [
            sys.executable,
            "run_inference_hydra.py",
            "datasource=experiment_17",
            f"experiment={experiment}",
            f"model={args.model}",
            f"input_folder={input_dir}",
            f"output_folder=out/experiment_17/{out_suffix}",
        ]
        print(f"\n--- {label} ---")
        if not run_cmd(cmd, args.dry_run):
            ok = False
            if not args.dry_run:
                print("Inference failed, stopping.")
                sys.exit(1)

    if args.dry_run:
        print("\nDry-run: would run evaluation on each result and print comparison.")
        return

    # Run evaluation on each result and load metrics
    metrics_key = "metrics"
    try:
        import yaml
    except ImportError:
        yaml = None
    results: list[tuple[str, str, dict]] = []  # (label, results_path, metrics_dict)
    for label, _exp, dataset, out_suffix in jobs:
        out_dir = OUT_BASE / out_suffix / model_slug
        if dataset == "dbpedia":
            result_file = out_dir / "dbpedia-challenge.yaml"
        else:
            result_file = out_dir / "wikipedia-challenge.yaml"
        if not result_file.exists():
            print(f"Missing result file: {result_file}")
            ok = False
            continue
        metrics_file = result_file.parent / "metrics.yaml"
        subprocess.run(
            [sys.executable, "-m", "benchmark.cli.run_evaluation", str(result_file), "--output", str(metrics_file)],
            cwd=ROOT,
            capture_output=True,
        )
        if metrics_file.exists() and yaml:
            with open(metrics_file) as f:
                data = yaml.safe_load(f)
            metrics = data.get(metrics_key, data) if isinstance(data, dict) else {}
            results.append((label, str(result_file), metrics))
        else:
            results.append((label, str(result_file), {}))

    if not results:
        print("No metrics to compare.")
        sys.exit(1)

    # Comparison table
    print("\n" + "=" * 80)
    print("BENCHMARK COMPARISON (experiment 17 dataset)")
    print("=" * 80)
    header = f"{'Experiment':<50} {'CSR':>8} {'TSR':>8} {'PO':>8} {'PPM':>8}"
    print(header)
    print("-" * 80)
    for label, _path, m in results:
        csr = m.get("csr", 0)
        tsr = m.get("tsr", 0)
        po = m.get("po", 0)
        ppm = m.get("ppm", 0)
        print(f"{label:<50} {csr:>8.4f} {tsr:>8.4f} {po:>8.4f} {ppm:>8.4f}")
    print("=" * 80)
    print("CSR = Claimed Success Rate, TSR = True Success Rate, PO = Path Optimality, PPM = Path Prefix Match")


if __name__ == "__main__":
    main()
