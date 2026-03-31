"""Observability module for tool execution.

Provides:
- Metrics: Counters, histograms, gauges for tool execution
- Exporters: OpenTelemetry/Prometheus export
- Hooks: Pre/post execution hooks for instrumentation
"""

from sunwell.tools.observability.events import (
    log_generate_tool_surface_tokens,
    log_tool_collision,
    log_tool_deferred,
    log_tool_materialized,
    log_tool_surface_assembled,
)
from sunwell.tools.observability.hooks import (
    ExecutionHook,
    HookManager,
    create_logging_hook,
    create_metrics_hook,
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
    # Surface / lifecycle logging
    "log_tool_surface_assembled",
    "log_tool_collision",
    "log_tool_deferred",
    "log_tool_materialized",
    "log_generate_tool_surface_tokens",
    # Hooks
    "ExecutionHook",
    "HookManager",
    "create_metrics_hook",
    "create_logging_hook",
]
