"""Reliability detection for agent execution.

This module provides tools for detecting when agent execution
may have failed silently or produced unreliable results.

Key detectors:
- Tool calling reliability (hallucination detection)
- Model capability mismatches
- Execution anomalies
"""

from sunwell.agent.reliability.tool_detector import (
    ToolFailureType,
    ToolReliabilityResult,
    detect_blocked_tool_pattern,
    detect_tool_failure,
)

__all__ = [
    "ToolFailureType",
    "ToolReliabilityResult",
    "detect_tool_failure",
    "detect_blocked_tool_pattern",
]
