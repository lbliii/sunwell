"""Configuration for Autonomy Guardrails (RFC-048).

Loads guardrail configuration from pyproject.toml or sunwell.yaml.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.guardrails.types import (
    ActionRisk,
    ScopeLimits,
    TrustLevel,
    TrustZone,
    VerificationThresholds,
)


@dataclass
class GuardrailConfig:
    """Configuration for guardrail system.

    Can be loaded from:
    - pyproject.toml [tool.sunwell.guardrails]
    - sunwell.yaml guardrails section
    - Programmatic configuration
    """

    # Overall trust level
    trust_level: TrustLevel = TrustLevel.GUARDED
    """Trust level for autonomous operation."""

    # Scope limits
    scope: ScopeLimits = field(default_factory=ScopeLimits)
    """Scope limits configuration."""

    # Verification thresholds
    verification: VerificationThresholds = field(
        default_factory=VerificationThresholds
    )
    """Verification confidence thresholds."""

    # Trust zones (extend defaults)
    trust_zones: tuple[TrustZone, ...] = ()
    """Additional trust zones (merged with defaults)."""

    # Auto-approve policy
    auto_approve_categories: frozenset[str] = frozenset({"fix", "test", "document"})
    """Categories that can be auto-approved."""

    auto_approve_complexity: frozenset[str] = frozenset({"trivial", "simple"})
    """Complexity levels that can be auto-approved."""

    # Recovery settings
    require_clean_start: bool = True
    """Require clean git state to start autonomous session."""

    commit_after_each_goal: bool = True
    """Create git commit after each goal completes."""

    auto_tag_sessions: bool = True
    """Automatically tag session start for rollback."""

    # RFC-049: External integration settings
    trusted_external_sources: frozenset[str] = frozenset({"github", "gitlab"})
    """Sources trusted for external event processing."""


def load_config(project_root: Path | None = None) -> GuardrailConfig:
    """Load guardrail configuration from project files.

    Looks for configuration in order:
    1. pyproject.toml [tool.sunwell.guardrails]
    2. sunwell.yaml guardrails section
    3. Default configuration

    Args:
        project_root: Project root directory (defaults to cwd)

    Returns:
        GuardrailConfig instance
    """
    if project_root is None:
        project_root = Path.cwd()

    # Try pyproject.toml
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.exists():
        config = _load_from_pyproject(pyproject_path)
        if config:
            return config

    # Try sunwell.yaml
    yaml_path = project_root / "sunwell.yaml"
    if yaml_path.exists():
        config = _load_from_yaml(yaml_path)
        if config:
            return config

    # Default config
    return GuardrailConfig()


def _load_from_pyproject(path: Path) -> GuardrailConfig | None:
    """Load config from pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return None

    try:
        content = path.read_text()
        data = tomllib.loads(content)

        guardrails_config = (
            data.get("tool", {}).get("sunwell", {}).get("guardrails", {})
        )

        if not guardrails_config:
            return None

        return _parse_config(guardrails_config)

    except Exception:
        return None


def _load_from_yaml(path: Path) -> GuardrailConfig | None:
    """Load config from sunwell.yaml."""
    try:
        import yaml
    except ImportError:
        return None

    try:
        content = path.read_text()
        data = yaml.safe_load(content)

        guardrails_config = data.get("guardrails", {})

        if not guardrails_config:
            return None

        return _parse_config(guardrails_config)

    except Exception:
        return None


def _parse_config(data: dict[str, Any]) -> GuardrailConfig:
    """Parse configuration dictionary into GuardrailConfig."""
    # Parse trust level
    trust_level = TrustLevel.GUARDED
    if "trust_level" in data:
        trust_level = TrustLevel(data["trust_level"])

    # Parse scope limits
    scope = ScopeLimits()
    if "scope" in data:
        scope_data = data["scope"]
        scope = ScopeLimits(
            max_files_per_goal=scope_data.get("max_files_per_goal", 10),
            max_lines_changed_per_goal=scope_data.get("max_lines_per_goal", 500),
            max_duration_per_goal_minutes=scope_data.get(
                "max_duration_per_goal_minutes", 30
            ),
            max_goals_per_session=scope_data.get("max_goals_per_session", 20),
            max_files_per_session=scope_data.get("max_files_per_session", 50),
            max_lines_per_session=scope_data.get("max_lines_per_session", 2000),
            max_duration_per_session_hours=scope_data.get(
                "max_duration_per_session_hours", 8
            ),
            require_tests_for_source_changes=scope_data.get(
                "require_tests_for_source", True
            ),
            require_git_clean_start=scope_data.get("require_clean_start", True),
            commit_after_each_goal=scope_data.get("commit_after_each_goal", True),
        )

    # Parse verification thresholds
    verification = VerificationThresholds()
    if "verification" in data:
        ver_data = data["verification"]
        verification = VerificationThresholds(
            safe_threshold=ver_data.get("safe_threshold", 0.70),
            moderate_threshold=ver_data.get("moderate_threshold", 0.85),
        )

    # Parse trust zones
    trust_zones: list[TrustZone] = []
    if "trust_zones" in data:
        for zone_data in data["trust_zones"]:
            risk_override = None
            if "risk_override" in zone_data:
                risk_override = ActionRisk(zone_data["risk_override"])

            trust_zones.append(
                TrustZone(
                    pattern=zone_data["pattern"],
                    risk_override=risk_override,
                    allowed_in_autonomous=zone_data.get("allowed_in_autonomous", True),
                    reason=zone_data.get("reason", ""),
                )
            )

    # Parse auto-approve settings
    auto_approve_categories = frozenset({"fix", "test", "document"})
    auto_approve_complexity = frozenset({"trivial", "simple"})

    if "auto_approve" in data:
        auto_data = data["auto_approve"]
        if "categories" in auto_data:
            auto_approve_categories = frozenset(auto_data["categories"])
        if "complexity" in auto_data:
            auto_approve_complexity = frozenset(auto_data["complexity"])

    # Parse recovery settings
    recovery_data = data.get("recovery", {})

    return GuardrailConfig(
        trust_level=trust_level,
        scope=scope,
        verification=verification,
        trust_zones=tuple(trust_zones),
        auto_approve_categories=auto_approve_categories,
        auto_approve_complexity=auto_approve_complexity,
        require_clean_start=recovery_data.get("require_clean_start", True),
        commit_after_each_goal=recovery_data.get("commit_after_each_goal", True),
        auto_tag_sessions=recovery_data.get("auto_tag_sessions", True),
    )


def save_config(config: GuardrailConfig, path: Path) -> None:
    """Save configuration to a YAML file.

    Args:
        config: Configuration to save
        path: Path to save to
    """
    try:
        import yaml
    except ImportError as err:
        raise ImportError("PyYAML required to save configuration") from err

    data = {
        "guardrails": {
            "trust_level": config.trust_level.value,
            "scope": {
                "max_files_per_goal": config.scope.max_files_per_goal,
                "max_lines_per_goal": config.scope.max_lines_changed_per_goal,
                "max_duration_per_goal_minutes": config.scope.max_duration_per_goal_minutes,
                "max_goals_per_session": config.scope.max_goals_per_session,
                "max_files_per_session": config.scope.max_files_per_session,
                "max_lines_per_session": config.scope.max_lines_per_session,
                "max_duration_per_session_hours": config.scope.max_duration_per_session_hours,
                "require_tests_for_source": config.scope.require_tests_for_source_changes,
            },
            "verification": {
                "safe_threshold": config.verification.safe_threshold,
                "moderate_threshold": config.verification.moderate_threshold,
            },
            "trust_zones": [
                {
                    "pattern": z.pattern,
                    "risk_override": z.risk_override.value if z.risk_override else None,
                    "allowed_in_autonomous": z.allowed_in_autonomous,
                    "reason": z.reason,
                }
                for z in config.trust_zones
            ],
            "auto_approve": {
                "categories": list(config.auto_approve_categories),
                "complexity": list(config.auto_approve_complexity),
            },
            "recovery": {
                "require_clean_start": config.require_clean_start,
                "commit_after_each_goal": config.commit_after_each_goal,
                "auto_tag_sessions": config.auto_tag_sessions,
            },
        }
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
