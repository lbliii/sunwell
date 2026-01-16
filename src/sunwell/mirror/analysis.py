"""Analysis capabilities for RFC-015 Mirror Neurons.

Provides pattern detection, failure analysis, and behavior diagnostics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class PatternAnalyzer:
    """Analyze patterns in Sunwell's behavior.
    
    Detects trends in tool usage, latency, error rates,
    and common execution sequences.
    """
    
    def analyze_tool_usage(
        self,
        audit_log: list[Any],
        scope: str = "session",
    ) -> dict[str, Any]:
        """Analyze tool usage patterns.
        
        Args:
            audit_log: List of audit log entries
            scope: Time scope ('session', 'day', 'week', 'all')
            
        Returns:
            Dict with tool_counts, success_rates, common_sequences
        """
        entries = self._filter_by_scope(audit_log, scope)
        
        if not entries:
            return {
                "tool_counts": {},
                "success_rates": {},
                "common_sequences": [],
                "total_calls": 0,
            }
        
        # Count tool usage
        tool_counts = Counter(e.tool_name for e in entries)
        
        # Calculate success rates
        success_rates: dict[str, float] = {}
        for tool in tool_counts:
            tool_entries = [e for e in entries if e.tool_name == tool]
            successes = sum(1 for e in tool_entries if e.success)
            success_rates[tool] = round(
                successes / len(tool_entries) if tool_entries else 0,
                2,
            )
        
        # Find common sequences
        sequences = self._find_sequences(entries)
        
        return {
            "tool_counts": dict(tool_counts),
            "success_rates": success_rates,
            "common_sequences": sequences,
            "total_calls": len(entries),
        }
    
    def analyze_latency(
        self,
        audit_log: list[Any],
        scope: str = "session",
    ) -> dict[str, Any]:
        """Analyze latency patterns.
        
        Args:
            audit_log: List of audit log entries
            scope: Time scope ('session', 'day', 'week', 'all')
            
        Returns:
            Dict with overall and per-tool latency stats
        """
        entries = self._filter_by_scope(audit_log, scope)
        
        if not entries:
            return {"message": "No data available"}
        
        times = [e.execution_time_ms for e in entries]
        
        by_tool: dict[str, dict[str, float]] = {}
        for tool in set(e.tool_name for e in entries):
            tool_times = [
                e.execution_time_ms for e in entries if e.tool_name == tool
            ]
            by_tool[tool] = {
                "avg_ms": round(sum(tool_times) / len(tool_times), 1),
                "max_ms": max(tool_times),
                "min_ms": min(tool_times),
                "count": len(tool_times),
            }
        
        # Calculate overall stats
        sorted_times = sorted(times)
        p95_idx = int(len(sorted_times) * 0.95)
        
        return {
            "overall": {
                "avg_ms": round(sum(times) / len(times), 1),
                "max_ms": max(times),
                "min_ms": min(times),
                "p95_ms": sorted_times[p95_idx] if len(times) > 20 else max(times),
                "total_calls": len(times),
            },
            "by_tool": by_tool,
        }
    
    def analyze_errors(
        self,
        audit_log: list[Any],
        scope: str = "session",
    ) -> dict[str, Any]:
        """Analyze error patterns.
        
        Args:
            audit_log: List of audit log entries
            scope: Time scope
            
        Returns:
            Dict with error counts, rates, and categories
        """
        entries = self._filter_by_scope(audit_log, scope)
        
        if not entries:
            return {"message": "No data available"}
        
        errors = [e for e in entries if not e.success]
        total = len(entries)
        
        # Categorize errors
        by_category: dict[str, int] = {}
        for e in errors:
            category = self._categorize_error(e.error or "Unknown")
            by_category[category] = by_category.get(category, 0) + 1
        
        # Error rate by tool
        error_rate_by_tool: dict[str, float] = {}
        for tool in set(e.tool_name for e in entries):
            tool_entries = [e for e in entries if e.tool_name == tool]
            tool_errors = sum(1 for e in tool_entries if not e.success)
            error_rate_by_tool[tool] = round(
                tool_errors / len(tool_entries) if tool_entries else 0,
                2,
            )
        
        return {
            "total_errors": len(errors),
            "error_rate": round(len(errors) / total if total else 0, 2),
            "by_category": by_category,
            "error_rate_by_tool": error_rate_by_tool,
        }
    
    def _filter_by_scope(self, entries: list[Any], scope: str) -> list[Any]:
        """Filter entries by time scope."""
        if scope == "session" or scope == "all":
            return entries
        
        now = datetime.now()
        if scope == "day":
            cutoff = now - timedelta(days=1)
        elif scope == "week":
            cutoff = now - timedelta(weeks=1)
        else:
            return entries
        
        return [e for e in entries if e.timestamp > cutoff]
    
    def _find_sequences(
        self,
        entries: list[Any],
        min_count: int = 2,
    ) -> list[dict[str, Any]]:
        """Find common tool call sequences (bigrams)."""
        if len(entries) < 2:
            return []
        
        # Build bigrams
        bigrams: list[tuple[str, str]] = []
        for i in range(len(entries) - 1):
            bigrams.append((entries[i].tool_name, entries[i + 1].tool_name))
        
        # Count bigrams
        bigram_counts = Counter(bigrams)
        
        # Return common sequences
        return [
            {"sequence": list(seq), "count": count}
            for seq, count in bigram_counts.most_common(5)
            if count >= min_count
        ]
    
    def _categorize_error(self, error: str) -> str:
        """Categorize an error message."""
        error_lower = error.lower()
        
        if "permission" in error_lower or "denied" in error_lower:
            return "permission"
        elif "not found" in error_lower or "no such" in error_lower:
            return "not_found"
        elif "timeout" in error_lower:
            return "timeout"
        elif "rate limit" in error_lower:
            return "rate_limit"
        elif "connection" in error_lower or "network" in error_lower:
            return "network"
        else:
            return "other"


@dataclass
class FailureAnalyzer:
    """Analyze failures and suggest fixes.
    
    Maps error patterns to root causes and provides
    actionable suggestions for resolution.
    """
    
    # Known failure patterns with suggestions
    known_patterns: dict[str, dict[str, str]] = None
    
    def __post_init__(self) -> None:
        """Initialize known patterns."""
        self.known_patterns = {
            "Permission denied": {
                "category": "security",
                "suggestion": "Check trust level. Current operation requires elevated permissions.",
                "fix_hint": "Use --trust-level workspace or shell flag",
            },
            "Rate limit exceeded": {
                "category": "throttling",
                "suggestion": "Wait before retrying. Consider batching operations.",
                "fix_hint": "Reduce tool call frequency or increase rate limits in policy",
            },
            "Not found": {
                "category": "file_system",
                "suggestion": "Verify path exists. Check for typos or wrong workspace.",
                "fix_hint": "Use list_files to verify path, check workspace root",
            },
            "Timeout": {
                "category": "performance",
                "suggestion": "Operation took too long. Consider breaking into smaller steps.",
                "fix_hint": "Increase timeout or simplify the operation",
            },
            "Connection": {
                "category": "network",
                "suggestion": "Network connectivity issue. Check internet connection.",
                "fix_hint": "Verify network access, check API keys for web tools",
            },
            "Invalid JSON": {
                "category": "parsing",
                "suggestion": "Tool arguments were malformed.",
                "fix_hint": "Check argument types match tool schema",
            },
        }
    
    def analyze(self, error_message: str) -> dict[str, Any]:
        """Analyze an error and provide suggestions.
        
        Args:
            error_message: The error message to analyze
            
        Returns:
            Dict with matched_pattern, category, suggestion, confidence
        """
        for pattern, info in self.known_patterns.items():
            if pattern.lower() in error_message.lower():
                return {
                    "matched_pattern": pattern,
                    "category": info["category"],
                    "suggestion": info["suggestion"],
                    "fix_hint": info.get("fix_hint", ""),
                    "confidence": 0.9,
                }
        
        return {
            "matched_pattern": None,
            "category": "unknown",
            "suggestion": "No known pattern matched. Consider reporting this error.",
            "fix_hint": "Check the full error message for clues",
            "confidence": 0.3,
        }
    
    def summarize_failures(self, audit_log: list[Any]) -> dict[str, Any]:
        """Summarize all failures with analysis.
        
        Args:
            audit_log: List of audit log entries
            
        Returns:
            Dict with total_failures, by_category, analyzed_details
        """
        failures = [e for e in audit_log if not e.success]
        
        analyzed = []
        for failure in failures:
            analysis = self.analyze(failure.error or "")
            analyzed.append({
                "tool": failure.tool_name,
                "error": failure.error,
                "analysis": analysis,
                "timestamp": failure.timestamp.isoformat(),
            })
        
        # Group by category
        by_category: dict[str, int] = {}
        for item in analyzed:
            cat = item["analysis"]["category"]
            by_category[cat] = by_category.get(cat, 0) + 1
        
        # Find most common issues
        most_common = sorted(
            by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        return {
            "total_failures": len(failures),
            "by_category": by_category,
            "most_common": most_common[:3] if most_common else [],
            "details": analyzed[-10:],  # Last 10 failures
            "recommendations": self._generate_recommendations(by_category),
        }
    
    def _generate_recommendations(
        self,
        by_category: dict[str, int],
    ) -> list[str]:
        """Generate recommendations based on failure patterns."""
        recommendations = []
        
        if by_category.get("permission", 0) > 2:
            recommendations.append(
                "Multiple permission errors detected. Consider reviewing trust level settings."
            )
        
        if by_category.get("rate_limit", 0) > 1:
            recommendations.append(
                "Rate limiting is active. Consider batching tool calls or increasing limits."
            )
        
        if by_category.get("not_found", 0) > 3:
            recommendations.append(
                "Many 'not found' errors. Verify workspace root and file paths."
            )
        
        if by_category.get("timeout", 0) > 2:
            recommendations.append(
                "Timeout issues detected. Consider increasing timeout values or simplifying operations."
            )
        
        return recommendations
