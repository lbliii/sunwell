"""Observability module for tool execution.

Provides:
- Metrics: Counters, histograms, gauges for tool execution
- Exporters: OpenTelemetry/Prometheus export
- Hooks: Pre/post execution hooks for instrumentation
"""

from sunwell.tools.observability.hooks import (
    ExecutionHook,
    HookManager,
    create_metrics_hook,
    create_logging_hook,
)
from sunwell.tools.observability.metrics import (
    MetricsCollector,
    ToolMetrics,
    get_metrics_collector,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "ToolMetrics",
    "get_metrics_collector",
    # Hooks
    "ExecutionHook",
    "HookManager",
    "create_metrics_hook",
    "create_logging_hook",
]
