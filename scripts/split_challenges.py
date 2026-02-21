#!/usr/bin/env python3
"""Split wikipedia_challenge.yaml and dbpedia_challenge.yaml into n equal-sized files.

Preserves the same structure (dataset + questions). Questions are split by index so
wikipedia part k and dbpedia part k contain the same challenge items.

Usage:
  python scripts/split_challenges.py --n 4
  python scripts/split_challenges.py --n 5 --wikipedia path/to/wikipedia_challenge.yaml --dbpedia path/to/dbpedia_challenge.yaml --output-dir out/splits
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


QUESTIONS_KEY = "questions"
DATASET_KEY = "dataset"


def load_challenge(path: Path) -> tuple[dict, list]:
    """Load challenge YAML; return (full data dict, questions list)."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML: {path}")
    questions = data.get(QUESTIONS_KEY)
    if not isinstance(questions, list):
        raise ValueError(f"No '{QUESTIONS_KEY}' list in {path}")
    return data, questions


def split_list(items: list, n: int) -> list[list]:
    """Split items into n roughly equal chunks (last chunk may be smaller)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    total = len(items)
    if total == 0:
        return [[]] * n
    chunk_size = total // n
    remainder = total % n
    chunks: list[list] = []
    start = 0
    for i in range(n):
        size = chunk_size + (1 if i < remainder else 0)
        chunks.append(items[start : start + size])
        start += size
    return chunks


def write_challenge(path: Path, data_template: dict, questions_chunk: list) -> None:
    """Write a challenge YAML with the same top-level keys but only questions_chunk."""
    out = {k: v for k, v in data_template.items() if k != QUESTIONS_KEY}
    out[QUESTIONS_KEY] = questions_chunk
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(out, f, sort_keys=False, default_flow_style=False, allow_unicode=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split wikipedia and dbpedia challenge YAMLs into n equal-sized parts.",
    )
    parser.add_argument(
        "-n",
        "--num-splits",
        type=int,
        required=True,
        metavar="N",
        help="Number of equal-sized splits (e.g. 4 → part 1..4).",
    )
    parser.add_argument(
        "--wikipedia",
        type=Path,
        default=Path("wikipedia_challenge.yaml"),
        help="Path to wikipedia_challenge.yaml (default: wikipedia_challenge.yaml).",
    )
    parser.add_argument(
        "--dbpedia",
        type=Path,
        default=Path("dbpedia_challenge.yaml"),
        help="Path to dbpedia_challenge.yaml (default: dbpedia_challenge.yaml).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for output files (default: same dir as inputs).",
    )
    parser.add_argument(
        "--per-dataset-dirs",
        action="store_true",
        help="Write wikipedia splits to <output-dir>/wikipedia and dbpedia to <output-dir>/dbpedia.",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="",
        help="Optional prefix for output filenames (e.g. 'split_' → split_wikipedia_challenge_1.yaml).",
    )
    args = parser.parse_args()

    if args.num_splits < 1:
        print("Error: --num-splits must be >= 1", file=sys.stderr)
        return 1

    if args.per_dataset_dirs and args.output_dir is None:
        args.output_dir = Path("challenges")
    out_dir = args.output_dir or args.wikipedia.parent
    prefix = args.output_prefix
    wiki_out_dir = out_dir / "wikipedia" if args.per_dataset_dirs else out_dir
    dbp_out_dir = out_dir / "dbpedia" if args.per_dataset_dirs else out_dir

    try:
        wiki_data, wiki_questions = load_challenge(args.wikipedia)
        dbp_data, dbp_questions = load_challenge(args.dbpedia)
    except (OSError, ValueError) as e:
        print(f"Error loading challenges: {e}", file=sys.stderr)
        return 1

    if len(wiki_questions) != len(dbp_questions):
        print(
            f"Warning: wikipedia has {len(wiki_questions)} questions, dbpedia has {len(dbp_questions)}; "
            "splits will be aligned by index.",
            file=sys.stderr,
        )

    n = min(args.num_splits, len(wiki_questions), len(dbp_questions)) or 1
    if n < args.num_splits:
        print(f"Warning: using n={n} splits (fewer than requested).", file=sys.stderr)

    wiki_chunks = split_list(wiki_questions, n)
    dbp_chunks = split_list(dbp_questions, n)

    for i in range(n):
        part = i + 1
        wiki_path = wiki_out_dir / f"{prefix}wikipedia_challenge_{part}_of_{n}.yaml"
        dbp_path = dbp_out_dir / f"{prefix}dbpedia_challenge_{part}_of_{n}.yaml"
        write_challenge(wiki_path, wiki_data, wiki_chunks[i])
        write_challenge(dbp_path, dbp_data, dbp_chunks[i])
        print(f"Wrote {wiki_path} ({len(wiki_chunks[i])} questions), {dbp_path} ({len(dbp_chunks[i])} questions).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
