"""Auto-configuration for advanced features (RFC-015, RFC-020).

Automatically enables features based on context:
- Mirror Neurons: For complex/long sessions
- Model Routing: When multiple models are configured
- Smart Mode: When model costs vary significantly
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AutoFeatures:
    """Auto-detected feature flags."""

    mirror_enabled: bool = False
    """Enable Mirror Neurons for self-introspection."""

    model_routing_enabled: bool = False
    """Enable Model-Aware Task Routing."""

    smart_enabled: bool = False
    """Enable Adaptive Model Selection."""

    reason: str = ""
    """Why these features were enabled/disabled."""


def detect_auto_features(
    workspace_root: Path,
    session_length: int = 0,
    goal_complexity: str = "unknown",
    explicit_mirror: bool | None = None,
    explicit_routing: bool | None = None,
    explicit_smart: bool | None = None,
) -> AutoFeatures:
    """Detect which features should be auto-enabled.

    Features are auto-enabled based on:
    - Mirror: Long sessions (>10 messages), complex goals, or agentic tasks
    - Routing: Multiple models configured with different capabilities
    - Smart: Models with varying costs configured

    Args:
        workspace_root: Project root directory.
        session_length: Number of messages in current session.
        goal_complexity: Goal complexity hint ('simple', 'medium', 'complex').
        explicit_mirror: User explicitly set --mirror or --no-mirror.
        explicit_routing: User explicitly set --model-routing.
        explicit_smart: User explicitly set --smart.

    Returns:
        AutoFeatures with detected settings.
    """
    reasons: list[str] = []

    # Check if user explicitly set flags
    if explicit_mirror is not None:
        mirror = explicit_mirror
        reasons.append(f"mirror={'on' if mirror else 'off'} (explicit)")
    else:
        mirror = _should_enable_mirror(session_length, goal_complexity)
        if mirror:
            reasons.append("mirror=on (auto: complex/long session)")

    if explicit_routing is not None:
        routing = explicit_routing
        reasons.append(f"routing={'on' if routing else 'off'} (explicit)")
    else:
        routing = _should_enable_routing(workspace_root)
        if routing:
            reasons.append("routing=on (auto: multiple models)")

    if explicit_smart is not None:
        smart = explicit_smart
        reasons.append(f"smart={'on' if smart else 'off'} (explicit)")
    else:
        smart = _should_enable_smart(workspace_root)
        if smart:
            reasons.append("smart=on (auto: cost variance)")

    return AutoFeatures(
        mirror_enabled=mirror,
        model_routing_enabled=routing,
        smart_enabled=smart,
        reason="; ".join(reasons) if reasons else "defaults",
    )


def _should_enable_mirror(session_length: int, goal_complexity: str) -> bool:
    """Determine if Mirror Neurons should be auto-enabled.

    Mirror helps with:
    - Self-correction during complex tasks
    - Detecting when stuck in loops
    - Reflecting on reasoning quality

    Args:
        session_length: Number of messages so far.
        goal_complexity: 'simple', 'medium', or 'complex'.

    Returns:
        True if mirror should be enabled.
    """
    # Enable for long sessions (agent might get stuck)
    if session_length >= 10:
        return True

    # Enable for complex goals
    if goal_complexity == "complex":
        return True

    return False


def _should_enable_routing(workspace_root: Path) -> bool:
    """Determine if Model Routing should be auto-enabled.

    Routing helps when you have:
    - A fast/cheap model for simple tasks
    - A powerful model for complex reasoning

    Args:
        workspace_root: Project root directory.

    Returns:
        True if routing should be enabled.
    """
    try:
        from sunwell.foundation.config import get_config

        config = get_config()

        # Check if router is configured
        if hasattr(config, "router") and config.router:
            router_cfg = config.router
            # Router needs at least 2 different models
            if hasattr(router_cfg, "models") and len(getattr(router_cfg, "models", [])) >= 2:
                return True

        # Check for multiple providers configured
        providers_configured = 0
        if hasattr(config, "openai") and config.openai:
            providers_configured += 1
        if hasattr(config, "anthropic") and config.anthropic:
            providers_configured += 1
        if hasattr(config, "ollama") and config.ollama:
            providers_configured += 1

        # Enable if 2+ providers available
        if providers_configured >= 2:
            return True

    except Exception as e:
        logger.debug("Could not check routing config: %s", e)

    return False


def _should_enable_smart(workspace_root: Path) -> bool:
    """Determine if Smart Mode (Adaptive Model Selection) should be enabled.

    Smart mode optimizes cost by:
    - Using cheaper models for simple queries
    - Reserving expensive models for complex reasoning

    Args:
        workspace_root: Project root directory.

    Returns:
        True if smart mode should be enabled.
    """
    try:
        from sunwell.foundation.config import get_config

        config = get_config()

        # Check if there are models with different cost tiers
        # For now, enable if both Anthropic and OpenAI are configured
        # (they have different pricing)
        has_anthropic = hasattr(config, "anthropic") and config.anthropic
        has_openai = hasattr(config, "openai") and config.openai

        if has_anthropic and has_openai:
            return True

        # Check for Ollama (free local) + cloud provider
        has_ollama = hasattr(config, "ollama") and config.ollama
        if has_ollama and (has_anthropic or has_openai):
            return True

    except Exception as e:
        logger.debug("Could not check smart config: %s", e)

    return False


def estimate_goal_complexity(goal: str) -> str:
    """Estimate complexity of a goal from its description.

    Args:
        goal: Goal description.

    Returns:
        'simple', 'medium', or 'complex'.
    """
    goal_lower = goal.lower()

    # Complex indicators
    complex_signals = [
        "refactor",
        "architect",
        "design",
        "integrate",
        "migrate",
        "optimize",
        "performance",
        "security",
        "authentication",
        "database",
        "api",
        "full stack",
        "end to end",
        "complete",
        "comprehensive",
    ]

    # Simple indicators
    simple_signals = [
        "fix typo",
        "rename",
        "add comment",
        "update readme",
        "change color",
        "simple",
        "quick",
        "small",
    ]

    complex_count = sum(1 for s in complex_signals if s in goal_lower)
    simple_count = sum(1 for s in simple_signals if s in goal_lower)

    if complex_count >= 2 or len(goal) > 200:
        return "complex"
    elif simple_count >= 1 or len(goal) < 50:
        return "simple"
    else:
        return "medium"
