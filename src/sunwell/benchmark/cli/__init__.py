"""Benchmark CLI commands (RFC-018).

Provides CLI interface for the benchmark framework:
- sunwell benchmark run - Run benchmark suite
- sunwell benchmark compare - Compare two versions
- sunwell benchmark report - Generate report from results
"""

from sunwell.benchmark.cli.commands import benchmark

__all__ = ["benchmark"]
