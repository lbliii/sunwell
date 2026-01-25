"""Model-aware task routing for RFC-015.

Routes tasks to optimal models based on:
1. Lens configuration preferences
2. Historical performance data
3. Task category classification
"""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.mirror.model_tracker import ModelPerformanceTracker


# Default task category mappings for tool classification
TASK_CATEGORY_MAP: dict[str, str] = {
    # Introspection tools
    "introspect_source": "introspection",
    "introspect_lens": "introspection",
    "introspect_simulacrum": "introspection",
    "introspect_execution": "introspection",

    # Analysis tools
    "analyze_patterns": "analysis",
    "analyze_failures": "analysis",
    "analyze_model_performance": "analysis",

    # Code operations
    "write_file": "code_generation",
    "propose_improvement": "deep_reasoning",
    "propose_model_routing": "deep_reasoning",

    # Quick operations
    "read_file": "quick_analysis",
    "list_files": "quick_analysis",
    "search_files": "quick_analysis",
    "search_memory": "quick_analysis",

    # Memory operations
    "recall_user_info": "quick_analysis",
    "find_related": "quick_analysis",
    "add_learning": "quick_analysis",

    # Proposal management
    "list_proposals": "quick_analysis",
    "get_proposal": "quick_analysis",
    "submit_proposal": "quick_analysis",
    "approve_proposal": "deep_reasoning",
    "apply_proposal": "deep_reasoning",
    "rollback_proposal": "deep_reasoning",
}


@dataclass(slots=True)
class ModelRoutingConfig:
    """Configuration for model routing from a lens.

    Parsed from lens model_routing section:

    ```yaml
    model_routing:
      enabled: true
      preferences:
        introspection:
          model: "claude-3-5-sonnet"
          rationale: "Strong at code analysis"
        code_generation:
          model: "claude-3-5-sonnet"
        quick_analysis:
          model: "gpt-4o-mini"
          rationale: "Fast and cheap"
    ```
    """

    enabled: bool = False
    preferences: dict[str, dict[str, str]] = field(default_factory=dict)
    privacy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ModelRoutingConfig:
        """Create from lens configuration dict."""
        if not data:
            return cls()

        return cls(
            enabled=data.get("enabled", False),
            preferences=data.get("preferences", {}),
            privacy=data.get("privacy", {}),
        )

    def get_model_for_category(self, category: str) -> str | None:
        """Get preferred model for a task category.

        Returns None if no preference set or routing disabled.
        """
        if not self.enabled:
            return None

        pref = self.preferences.get(category)
        if pref:
            model = pref.get("model")
            if model and model != "session":
                return model

        # Check default
        default = self.preferences.get("default", {})
        if default:
            model = default.get("model")
            if model and model != "session":
                return model

        return None

    def should_keep_local(self, category: str) -> bool:
        """Check if a category should be routed to local models only."""
        keep_local = self.privacy.get("keep_local", [])
        return category in keep_local

    def is_local_only(self) -> bool:
        """Check if routing is restricted to local models."""
        return self.privacy.get("local_only", False)


@dataclass(slots=True)
class ModelRouter:
    """Routes tasks to optimal models based on lens config and performance.

    Priority order for model selection:
    1. Lens explicit preference for task category
    2. Performance-based selection (if enough data)
    3. Session default model

    Example:
        >>> router = ModelRouter(
        ...     lens_config={"model_routing": {"enabled": True, ...}},
        ...     session_model="gpt-4o",
        ... )
        >>> model = router.select_model("introspect_source")
    """

    lens_config: dict[str, Any] | None = None
    performance_tracker: ModelPerformanceTracker | None = None
    session_model: str = "session"
    available_models: dict[str, str] = field(default_factory=dict)

    # Parsed routing config (initialized in __post_init__)
    _routing_config: ModelRoutingConfig = field(init=False)

    def __post_init__(self) -> None:
        """Parse lens config into routing config."""
        routing_data = None
        if self.lens_config:
            routing_data = self.lens_config.get("model_routing")
        self._routing_config = ModelRoutingConfig.from_dict(routing_data)

    def select_model(self, tool_name: str) -> str:
        """Select optimal model for a tool call.

        Args:
            tool_name: Name of the tool being called

        Returns:
            Model identifier to use
        """
        task_category = self.classify_task(tool_name)

        # Check privacy constraints first
        if self._routing_config.is_local_only():
            # Return a local model or session default
            local = self._get_local_model()
            if local:
                return local
            return self.session_model

        if self._routing_config.should_keep_local(task_category):
            local = self._get_local_model()
            if local:
                return local

        # 1. Check lens config preferences
        lens_model = self._routing_config.get_model_for_category(task_category)
        if lens_model:
            return lens_model

        # 2. Performance-based selection
        if self.performance_tracker:
            best = self.performance_tracker.get_best_model(task_category)
            if best:
                return best

        # 3. Fall back to session default
        return self.session_model

    def classify_task(self, tool_name: str) -> str:
        """Classify a tool into a task category.

        Args:
            tool_name: Name of the tool

        Returns:
            Task category string
        """
        return TASK_CATEGORY_MAP.get(tool_name, "default")

    def get_routing_info(self) -> dict[str, Any]:
        """Get current routing configuration for debugging.

        Returns:
            Dict with session_model, lens_routing_enabled, preferences,
            performance_based status
        """
        return {
            "session_model": self.session_model,
            "lens_routing_enabled": self._routing_config.enabled,
            "preferences": self._routing_config.preferences,
            "performance_based": self.performance_tracker is not None,
            "privacy": self._routing_config.privacy,
        }

    def get_category_recommendation(self, task_category: str) -> dict[str, Any]:
        """Get recommendation for a specific task category.

        Args:
            task_category: The task category

        Returns:
            Dict with recommended model and reasoning
        """
        result: dict[str, Any] = {
            "category": task_category,
            "recommended_model": None,
            "reason": None,
            "alternatives": [],
        }

        # Check lens preference
        lens_model = self._routing_config.get_model_for_category(task_category)
        if lens_model:
            result["recommended_model"] = lens_model
            result["reason"] = "lens_preference"
            pref = self._routing_config.preferences.get(task_category, {})
            result["rationale"] = pref.get("rationale", "Configured in lens")
            return result

        # Check performance data
        if self.performance_tracker:
            best = self.performance_tracker.get_best_model(task_category)
            if best:
                result["recommended_model"] = best
                result["reason"] = "performance_data"
                stats = self.performance_tracker.get_stats(best, task_category)
                result["rationale"] = (
                    f"Best performing: {stats['success_rate']:.0%} success, "
                    f"{stats['edit_rate']:.0%} edit rate"
                )

                # Get alternatives
                comparisons = self.performance_tracker.compare_models(task_category)
                result["alternatives"] = comparisons[:3]
                return result

        # Default
        result["recommended_model"] = self.session_model
        result["reason"] = "session_default"
        result["rationale"] = "No preference or performance data available"
        return result

    def _get_local_model(self) -> str | None:
        """Get a local model from available models."""
        # Look for ollama or local models
        for name, provider in self.available_models.items():
            if provider in ("ollama", "local"):
                return name
        return None


def get_all_task_categories() -> list[str]:
    """Get all defined task categories.

    Returns:
        List of unique task category names
    """
    return list(set(TASK_CATEGORY_MAP.values()))


def get_tools_for_category(category: str) -> list[str]:
    """Get all tools mapped to a category.

    Args:
        category: Task category name

    Returns:
        List of tool names
    """
    return [
        tool for tool, cat in TASK_CATEGORY_MAP.items()
        if cat == category
    ]
