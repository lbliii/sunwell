# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Security sandbox benchmark suite (RFC-089).

Measures performance overhead of security features:
- Permission analysis latency
- Sandbox setup time
- Monitoring overhead per token
- Audit log write latency

Results help tune configurations and identify bottlenecks.
"""


import json
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.security.analyzer import PermissionAnalyzer, PermissionScope
from sunwell.security.audit import LocalAuditLog
from sunwell.security.monitor import SecurityMonitor
from sunwell.security.sandbox import PermissionAwareSandboxConfig, SecureSandbox
from sunwell.skills.types import TrustLevel

# =============================================================================
# BENCHMARK RESULTS
# =============================================================================


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    """Benchmark name."""

    iterations: int
    """Number of iterations run."""

    mean_ms: float
    """Mean latency in milliseconds."""

    std_ms: float
    """Standard deviation in milliseconds."""

    min_ms: float
    """Minimum latency in milliseconds."""

    max_ms: float
    """Maximum latency in milliseconds."""

    p50_ms: float
    """50th percentile (median) latency."""

    p95_ms: float
    """95th percentile latency."""

    p99_ms: float
    """99th percentile latency."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When benchmark was run."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional benchmark metadata."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 3),
            "std_ms": round(self.std_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkSuite:
    """Complete benchmark suite results."""

    results: list[BenchmarkResult] = field(default_factory=list)
    """Individual benchmark results."""

    platform: str = ""
    """Platform identifier."""

    python_version: str = ""
    """Python version."""

    total_duration_s: float = 0.0
    """Total benchmark duration in seconds."""

    def __post_init__(self) -> None:
        import platform
        import sys

        self.platform = f"{platform.system()} {platform.release()}"
        self.python_version = sys.version.split()[0]

    def add(self, result: BenchmarkResult) -> None:
        """Add a benchmark result."""
        self.results.append(result)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "platform": self.platform,
            "python_version": self.python_version,
            "total_duration_s": round(self.total_duration_s, 2),
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Security Benchmark Results",
            "",
            f"**Platform**: {self.platform}",
            f"**Python**: {self.python_version}",
            f"**Total Duration**: {self.total_duration_s:.2f}s",
            "",
            "## Results",
            "",
            "| Benchmark | Mean (ms) | P95 (ms) | P99 (ms) | Iterations |",
            "|-----------|-----------|----------|----------|------------|",
        ]

        for r in self.results:
            lines.append(
                f"| {r.name} | {r.mean_ms:.3f} | {r.p95_ms:.3f} | {r.p99_ms:.3f} | {r.iterations} |"
            )

        return "\n".join(lines)


# =============================================================================
# BENCHMARK FUNCTIONS
# =============================================================================


def _compute_stats(latencies_ms: list[float]) -> dict[str, float]:
    """Compute statistics from latency samples."""
    if not latencies_ms:
        return {"mean": 0, "std": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}

    sorted_latencies = sorted(latencies_ms)
    n = len(sorted_latencies)

    return {
        "mean": statistics.mean(latencies_ms),
        "std": statistics.stdev(latencies_ms) if n > 1 else 0,
        "min": sorted_latencies[0],
        "max": sorted_latencies[-1],
        "p50": sorted_latencies[n // 2],
        "p95": sorted_latencies[int(n * 0.95)] if n >= 20 else sorted_latencies[-1],
        "p99": sorted_latencies[int(n * 0.99)] if n >= 100 else sorted_latencies[-1],
    }


def benchmark_permission_analysis(iterations: int = 100) -> BenchmarkResult:
    """Benchmark permission analysis latency.

    Measures time to analyze a typical skill's permissions and compute risk.

    Args:
        iterations: Number of iterations to run

    Returns:
        BenchmarkResult with latency statistics
    """
    analyzer = PermissionAnalyzer()

    # Create a typical permission scope
    scope = PermissionScope(
        filesystem_read=frozenset(["./src/**", "./config/*", "~/.config/app/*"]),
        filesystem_write=frozenset(["./output/*", "./logs/*"]),
        network_allow=frozenset(["localhost:3000", "api.internal:8080"]),
        shell_allow=frozenset(["pytest", "python", "pip install"]),
        env_read=frozenset(["API_KEY", "DATABASE_URL", "LOG_LEVEL"]),
    )

    latencies_ms: list[float] = []

    for _ in range(iterations):
        start = time.perf_counter()

        # Simulate skill analysis
        flags = analyzer._check_risks_deterministic(
            type("MockSkill", (), {"name": "test", "permissions": scope})(),
            scope,
        )
        analyzer._compute_risk(scope, flags)

        elapsed = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed)

    stats = _compute_stats(latencies_ms)

    return BenchmarkResult(
        name="permission_analysis",
        iterations=iterations,
        mean_ms=stats["mean"],
        std_ms=stats["std"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        metadata={
            "permissions_count": (
                len(scope.filesystem_read)
                + len(scope.filesystem_write)
                + len(scope.network_allow)
                + len(scope.shell_allow)
            )
        },
    )


def benchmark_sandbox_setup(iterations: int = 50) -> BenchmarkResult:
    """Benchmark sandbox initialization time.

    Measures time to create and configure a SecureSandbox.

    Args:
        iterations: Number of iterations to run

    Returns:
        BenchmarkResult with latency statistics
    """
    scope = PermissionScope(
        filesystem_read=frozenset(["./src/**"]),
        filesystem_write=frozenset(["./output/*"]),
        network_allow=frozenset(["localhost:3000"]),
    )

    latencies_ms: list[float] = []

    for _ in range(iterations):
        start = time.perf_counter()

        config = PermissionAwareSandboxConfig(
            permissions=scope,
            base_trust=TrustLevel.SANDBOXED,
            max_memory_mb=512,
            max_cpu_seconds=60,
        )
        sandbox = SecureSandbox(config)
        sandbox.cleanup()

        elapsed = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed)

    stats = _compute_stats(latencies_ms)

    return BenchmarkResult(
        name="sandbox_setup",
        iterations=iterations,
        mean_ms=stats["mean"],
        std_ms=stats["std"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        metadata={"isolation_backend": config.isolation_backend},
    )


def benchmark_monitoring_overhead(iterations: int = 100) -> BenchmarkResult:
    """Benchmark security monitoring overhead per chunk.

    Measures time to scan output chunks for security violations.

    Args:
        iterations: Number of iterations to run

    Returns:
        BenchmarkResult with latency statistics
    """
    monitor = SecurityMonitor()
    scope = PermissionScope()

    # Typical output chunks of varying sizes
    chunks = [
        "Processing file: src/main.py\n" * 10,  # ~300 chars
        "Result: " + "a" * 500,  # ~500 chars
        '{"data": "' + "x" * 1000 + '"}',  # ~1000 chars
        "Error: " + "stack trace\n" * 50,  # ~800 chars
    ]

    latencies_ms: list[float] = []

    for _ in range(iterations):
        for chunk in chunks:
            start = time.perf_counter()

            monitor.classify_output_deterministic(chunk, scope)

            elapsed = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed)

    stats = _compute_stats(latencies_ms)

    avg_chunk_size = sum(len(c) for c in chunks) // len(chunks)

    return BenchmarkResult(
        name="monitoring_overhead",
        iterations=iterations * len(chunks),
        mean_ms=stats["mean"],
        std_ms=stats["std"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        metadata={
            "chunk_count": len(chunks),
            "avg_chunk_size": avg_chunk_size,
            "ms_per_kb": stats["mean"] / (avg_chunk_size / 1000) if avg_chunk_size else 0,
        },
    )


def benchmark_credential_scanning(iterations: int = 100) -> BenchmarkResult:
    """Benchmark credential scanning performance.

    Measures time to scan content for credential leaks.

    Args:
        iterations: Number of iterations to run

    Returns:
        BenchmarkResult with latency statistics
    """
    analyzer = PermissionAnalyzer()

    # Content with various credential patterns to detect
    content_samples = [
        # Clean content
        "This is normal output with no credentials.",
        # AWS key
        "Found key: AKIAIOSFODNN7EXAMPLE",
        # GitHub token
        "Token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        # Private key header
        "-----BEGIN RSA PRIVATE KEY-----\nMIIE...",
        # Generic secret
        'password = "supersecret123"',
        # Multiple patterns
        "API_KEY=sk_test_xxxxx\nAWS_SECRET=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ]

    latencies_ms: list[float] = []

    for _ in range(iterations):
        for content in content_samples:
            start = time.perf_counter()

            analyzer.scan_for_credentials(content)

            elapsed = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed)

    stats = _compute_stats(latencies_ms)

    return BenchmarkResult(
        name="credential_scanning",
        iterations=iterations * len(content_samples),
        mean_ms=stats["mean"],
        std_ms=stats["std"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        metadata={
            "sample_count": len(content_samples),
            "patterns_checked": len(analyzer.CREDENTIAL_PATTERNS),
        },
    )


def benchmark_audit_write(iterations: int = 100) -> BenchmarkResult:
    """Benchmark audit log write latency.

    Measures time to append entries to the audit log.

    Args:
        iterations: Number of iterations to run

    Returns:
        BenchmarkResult with latency statistics
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = Path(tmpdir) / "audit.log"
        key = b"benchmark-test-key"
        backend = LocalAuditLog(audit_path, key)

        latencies_ms: list[float] = []

        for i in range(iterations):
            start = time.perf_counter()

            backend.append(
                backend._create_entry(
                    skill_name=f"skill_{i}",
                    action="execute",
                    dag_id=f"dag_{i % 10}",
                    permissions_json="{}",
                    details=f"Iteration {i} of benchmark",
                )
            )

            elapsed = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed)

        stats = _compute_stats(latencies_ms)

        final_size = audit_path.stat().st_size if audit_path.exists() else 0

    return BenchmarkResult(
        name="audit_write",
        iterations=iterations,
        mean_ms=stats["mean"],
        std_ms=stats["std"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        metadata={
            "final_log_size_kb": final_size / 1024,
            "bytes_per_entry": final_size / iterations if iterations else 0,
        },
    )


def benchmark_risk_computation(iterations: int = 500) -> BenchmarkResult:
    """Benchmark risk computation performance.

    Measures time to compute risk from flags and permissions.

    Args:
        iterations: Number of iterations to run

    Returns:
        BenchmarkResult with latency statistics
    """
    analyzer = PermissionAnalyzer()

    scope = PermissionScope(
        filesystem_write=frozenset(["./a", "./b", "./c", "./d", "./e"]),
        shell_allow=frozenset(["cmd1", "cmd2", "cmd3"]),
        network_allow=frozenset(["host1:80", "host2:443"]),
    )

    flags = [
        "CREDENTIAL_ACCESS: skill reads ~/.aws/credentials",
        "EXTERNAL_NETWORK: skill connects to api.example.com",
        "DANGEROUS_COMMAND: skill allows 'rm -rf'",
    ]

    latencies_ms: list[float] = []

    for _ in range(iterations):
        start = time.perf_counter()

        analyzer._compute_risk(scope, flags)

        elapsed = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed)

    stats = _compute_stats(latencies_ms)

    return BenchmarkResult(
        name="risk_computation",
        iterations=iterations,
        mean_ms=stats["mean"],
        std_ms=stats["std"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        metadata={
            "flag_count": len(flags),
            "permission_count": (
                len(scope.filesystem_write)
                + len(scope.shell_allow)
                + len(scope.network_allow)
            ),
        },
    )


# =============================================================================
# SUITE RUNNER
# =============================================================================


def run_benchmark_suite(
    iterations: int = 100,
    include_slow: bool = True,
) -> BenchmarkSuite:
    """Run the complete security benchmark suite.

    Args:
        iterations: Base iteration count (some benchmarks scale this)
        include_slow: Include slower benchmarks

    Returns:
        BenchmarkSuite with all results
    """
    suite = BenchmarkSuite()
    start_time = time.time()

    # Fast benchmarks
    suite.add(benchmark_risk_computation(iterations * 5))
    suite.add(benchmark_credential_scanning(iterations))
    suite.add(benchmark_permission_analysis(iterations))
    suite.add(benchmark_monitoring_overhead(iterations))

    if include_slow:
        # Slower benchmarks (involve I/O or system calls)
        suite.add(benchmark_sandbox_setup(iterations // 2))
        suite.add(benchmark_audit_write(iterations))

    suite.total_duration_s = time.time() - start_time

    return suite


# =============================================================================
# CLI INTEGRATION
# =============================================================================


def run_benchmarks_cli(output: Path | None = None, json_output: bool = False) -> None:
    """Run benchmarks from CLI.

    Args:
        output: Path to write results
        json_output: Output as JSON instead of markdown
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    console.print("[bold]Running Security Benchmark Suite...[/bold]\n")

    suite = run_benchmark_suite()

    if json_output:
        result = suite.to_json()
        if output:
            output.write_text(result)
            console.print(f"[green]Results written to {output}[/green]")
        else:
            console.print(result)
        return

    # Display results as table
    table = Table(title="Security Benchmark Results")
    table.add_column("Benchmark", style="cyan")
    table.add_column("Mean (ms)", justify="right")
    table.add_column("P95 (ms)", justify="right")
    table.add_column("P99 (ms)", justify="right")
    table.add_column("Iterations", justify="right")

    for r in suite.results:
        table.add_row(
            r.name,
            f"{r.mean_ms:.3f}",
            f"{r.p95_ms:.3f}",
            f"{r.p99_ms:.3f}",
            str(r.iterations),
        )

    console.print(table)
    console.print(f"\n[dim]Total duration: {suite.total_duration_s:.2f}s[/dim]")

    if output:
        output.write_text(suite.to_markdown())
        console.print(f"[green]Markdown report written to {output}[/green]")
