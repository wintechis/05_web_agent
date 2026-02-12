"""CLI for generating Wikipedia/DBpedia path-finding challenges."""

import argparse
import logging

from benchmark.application.wikipedia_challenge_generator import (
    DEFAULT_DBPEDIA_OUTPUT,
    DEFAULT_LIMIT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_WIKIPEDIA_OUTPUT,
    DISTANCE,
    ENFORCE_EXACT_DISTANCE,
    GenerateChallengeUseCase,
    NUMBER_OF_CHALLENGES,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate wikipedia/dbpedia challenges."
    )
    parser.add_argument("--distance", type=int, default=DISTANCE)
    parser.add_argument(
        "--number-of-challenges",
        type=int,
        default=NUMBER_OF_CHALLENGES,
    )
    parser.add_argument("--default-limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--enforce-exact-distance",
        action=argparse.BooleanOptionalAction,
        default=ENFORCE_EXACT_DISTANCE,
    )
    parser.add_argument("--log-level", type=str, default=DEFAULT_LOG_LEVEL)
    parser.add_argument(
        "--wikipedia-output",
        type=str,
        default=DEFAULT_WIKIPEDIA_OUTPUT,
    )
    parser.add_argument(
        "--dbpedia-output",
        type=str,
        default=DEFAULT_DBPEDIA_OUTPUT,
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper())

    use_case = GenerateChallengeUseCase()
    use_case.run(
        distance=args.distance,
        number_of_challenges=args.number_of_challenges,
        default_limit=args.default_limit,
        enforce_exact_distance=args.enforce_exact_distance,
        wikipedia_output=args.wikipedia_output,
        dbpedia_output=args.dbpedia_output,
    )


if __name__ == "__main__":
    main()
