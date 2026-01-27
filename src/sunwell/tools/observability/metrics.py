"""Metrics collection for tool execution.

Provides lightweight, thread-safe metrics for monitoring tool performance:
- Counters: tool_calls_total, tool_errors_total
- Histograms: tool_latency_seconds
- Gauges: active_tool_calls

Metrics can be exported to various backends via exporters.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolMetrics:
    """Snapshot of metrics for a single tool."""

    tool_name: str
    call_count: int
    error_count: int
    success_rate: float
    total_latency_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


@dataclass
class MetricsCollector:
    """Thread-safe metrics collector for tool execution.

    Collects:
    - Call counts (success/failure)
    - Latency distributions
    - Bytes written (for file tools)
    - Rate limit hits

    Example:
        collector = MetricsCollector()

        # Record a tool call
        collector.record_call("write_file", success=True, latency_ms=45)

        # Get metrics
        metrics = collector.get_tool_metrics("write_file")
        print(f"Avg latency: {metrics.avg_latency_ms}ms")

        # Export all metrics
        all_metrics = collector.export_all()
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    # Per-tool counters
    _call_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int), init=False)
    _error_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int), init=False)

    # Per-tool latency samples (keep last N for percentile calculation)
    _latencies: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list), init=False)
    _max_latency_samples: int = 1000

    # Global counters
    _total_calls: int = field(default=0, init=False)
    _total_errors: int = field(default=0, init=False)
    _total_bytes_written: int = field(default=0, init=False)
    _rate_limit_hits: int = field(default=0, init=False)

    # Timing
    _start_time: float = field(default_factory=time.time, init=False)

    def record_call(
        self,
        tool_name: str,
        *,
        success: bool,
        latency_ms: float,
        bytes_written: int = 0,
    ) -> None:
        """Record a tool call.

        Args:
            tool_name: Name of the tool called
            success: Whether the call succeeded
            latency_ms: Execution time in milliseconds
            bytes_written: Bytes written (for file tools)
        """
        with self._lock:
            self._call_counts[tool_name] += 1
            self._total_calls += 1

            if not success:
                self._error_counts[tool_name] += 1
                self._total_errors += 1

            # Record latency sample
            latencies = self._latencies[tool_name]
            latencies.append(latency_ms)

            # Prune old samples if needed
            if len(latencies) > self._max_latency_samples:
                self._latencies[tool_name] = latencies[-self._max_latency_samples:]

            # Track bytes written
            if bytes_written > 0:
                self._total_bytes_written += bytes_written

    def record_rate_limit_hit(self) -> None:
        """Record a rate limit hit."""
        with self._lock:
            self._rate_limit_hits += 1

    def get_tool_metrics(self, tool_name: str) -> ToolMetrics | None:
        """Get metrics for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolMetrics or None if no data
        """
        with self._lock:
            if tool_name not in self._call_counts:
                return None

            call_count = self._call_counts[tool_name]
            error_count = self._error_counts[tool_name]
            latencies = self._latencies[tool_name]

            if not latencies:
                return ToolMetrics(
                    tool_name=tool_name,
                    call_count=call_count,
                    error_count=error_count,
                    success_rate=1.0 if error_count == 0 else (call_count - error_count) / call_count,
                    total_latency_ms=0,
                    avg_latency_ms=0,
                    min_latency_ms=0,
                    max_latency_ms=0,
                    p50_latency_ms=0,
                    p95_latency_ms=0,
                    p99_latency_ms=0,
                )

            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)

            return ToolMetrics(
                tool_name=tool_name,
                call_count=call_count,
                error_count=error_count,
                success_rate=(call_count - error_count) / call_count if call_count > 0 else 1.0,
                total_latency_ms=sum(latencies),
                avg_latency_ms=sum(latencies) / n,
                min_latency_ms=sorted_latencies[0],
                max_latency_ms=sorted_latencies[-1],
                p50_latency_ms=sorted_latencies[int(n * 0.50)],
                p95_latency_ms=sorted_latencies[int(n * 0.95)] if n > 20 else sorted_latencies[-1],
                p99_latency_ms=sorted_latencies[int(n * 0.99)] if n > 100 else sorted_latencies[-1],
            )

    def get_all_tool_names(self) -> list[str]:
        """Get names of all tools with recorded metrics."""
        with self._lock:
            return list(self._call_counts.keys())

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics.

        Returns:
            Dict with summary statistics
        """
        with self._lock:
            uptime_seconds = time.time() - self._start_time
            calls_per_minute = (self._total_calls / uptime_seconds) * 60 if uptime_seconds > 0 else 0

            return {
                "uptime_seconds": uptime_seconds,
                "total_calls": self._total_calls,
                "total_errors": self._total_errors,
                "error_rate": self._total_errors / self._total_calls if self._total_calls > 0 else 0,
                "calls_per_minute": calls_per_minute,
                "total_bytes_written": self._total_bytes_written,
                "rate_limit_hits": self._rate_limit_hits,
                "tools_used": len(self._call_counts),
            }

    def export_all(self) -> dict[str, Any]:
        """Export all metrics as a dictionary.

        Returns:
            Dict with summary and per-tool metrics
        """
        summary = self.get_summary()
        tools = {}

        for tool_name in self.get_all_tool_names():
            metrics = self.get_tool_metrics(tool_name)
            if metrics:
                tools[tool_name] = {
                    "call_count": metrics.call_count,
                    "error_count": metrics.error_count,
                    "success_rate": metrics.success_rate,
                    "avg_latency_ms": metrics.avg_latency_ms,
                    "p50_latency_ms": metrics.p50_latency_ms,
                    "p95_latency_ms": metrics.p95_latency_ms,
                    "p99_latency_ms": metrics.p99_latency_ms,
                }

        return {
            "summary": summary,
            "tools": tools,
        }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []

        # Helper to format a metric line
        def metric(name: str, value: float, labels: dict[str, str] | None = None) -> str:
            if labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                return f"{name}{{{label_str}}} {value}"
            return f"{name} {value}"

        summary = self.get_summary()

        # Global metrics
        lines.append("# HELP sunwell_tool_calls_total Total number of tool calls")
        lines.append("# TYPE sunwell_tool_calls_total counter")
        lines.append(metric("sunwell_tool_calls_total", summary["total_calls"]))

        lines.append("# HELP sunwell_tool_errors_total Total number of tool errors")
        lines.append("# TYPE sunwell_tool_errors_total counter")
        lines.append(metric("sunwell_tool_errors_total", summary["total_errors"]))

        lines.append("# HELP sunwell_bytes_written_total Total bytes written by file tools")
        lines.append("# TYPE sunwell_bytes_written_total counter")
        lines.append(metric("sunwell_bytes_written_total", summary["total_bytes_written"]))

        lines.append("# HELP sunwell_rate_limit_hits_total Total rate limit hits")
        lines.append("# TYPE sunwell_rate_limit_hits_total counter")
        lines.append(metric("sunwell_rate_limit_hits_total", summary["rate_limit_hits"]))

        # Per-tool metrics
        lines.append("# HELP sunwell_tool_call_count Number of calls per tool")
        lines.append("# TYPE sunwell_tool_call_count counter")
        for tool_name in self.get_all_tool_names():
            metrics = self.get_tool_metrics(tool_name)
            if metrics:
                lines.append(metric("sunwell_tool_call_count", metrics.call_count, {"tool": tool_name}))

        lines.append("# HELP sunwell_tool_latency_seconds Tool execution latency")
        lines.append("# TYPE sunwell_tool_latency_seconds summary")
        for tool_name in self.get_all_tool_names():
            metrics = self.get_tool_metrics(tool_name)
            if metrics:
                labels = {"tool": tool_name}
                lines.append(metric("sunwell_tool_latency_seconds", metrics.avg_latency_ms / 1000, {**labels, "quantile": "0.5"}))
                lines.append(metric("sunwell_tool_latency_seconds", metrics.p95_latency_ms / 1000, {**labels, "quantile": "0.95"}))
                lines.append(metric("sunwell_tool_latency_seconds", metrics.p99_latency_ms / 1000, {**labels, "quantile": "0.99"}))
                lines.append(metric("sunwell_tool_latency_seconds_sum", metrics.total_latency_ms / 1000, labels))
                lines.append(metric("sunwell_tool_latency_seconds_count", metrics.call_count, labels))

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._call_counts.clear()
            self._error_counts.clear()
            self._latencies.clear()
            self._total_calls = 0
            self._total_errors = 0
            self._total_bytes_written = 0
            self._rate_limit_hits = 0
            self._start_time = time.time()


# Global metrics collector (singleton)
_global_collector: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector.

    Returns:
        The global MetricsCollector instance
    """
    global _global_collector
    if _global_collector is None:
        with _collector_lock:
            if _global_collector is None:
                _global_collector = MetricsCollector()
    return _global_collector
