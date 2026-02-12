"""Thin wrapper delegating to benchmark CLI. Preserves backward compatibility."""

from benchmark.cli.run_evaluation import main

if __name__ == "__main__":
    main()
