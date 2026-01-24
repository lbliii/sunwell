# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Permission diff utilities for security analysis (RFC-089).

Compares permission scopes between:
- Two lens versions
- Skill updates
- Policy changes

Outputs human-readable diffs and risk impact assessment.
"""


from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sunwell.security.analyzer import PermissionAnalyzer, PermissionScope, RiskAssessment

if TYPE_CHECKING:
    from sunwell.skills.types import Skill


# =============================================================================
# DIFF TYPES
# =============================================================================


class ChangeType(Enum):
    """Type of permission change."""

    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class PermissionChange:
    """A single permission change."""

    category: str
    """Permission category (filesystem_read, network_allow, etc.)."""

    value: str
    """The permission value that changed."""

    change_type: ChangeType
    """Type of change."""

    risk_impact: str | None = None
    """Risk impact of this change (if assessed)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "category": self.category,
            "value": self.value,
            "change_type": self.change_type.value,
            "risk_impact": self.risk_impact,
        }


@dataclass
class PermissionDiff:
    """Complete diff between two permission scopes."""

    old_scope: PermissionScope
    """Original permission scope."""

    new_scope: PermissionScope
    """New permission scope."""

    changes: list[PermissionChange] = field(default_factory=list)
    """List of individual changes."""

    old_risk: RiskAssessment | None = None
    """Risk assessment of old scope."""

    new_risk: RiskAssessment | None = None
    """Risk assessment of new scope."""

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return len([c for c in self.changes if c.change_type != ChangeType.UNCHANGED]) > 0

    @property
    def added(self) -> list[PermissionChange]:
        """Get added permissions."""
        return [c for c in self.changes if c.change_type == ChangeType.ADDED]

    @property
    def removed(self) -> list[PermissionChange]:
        """Get removed permissions."""
        return [c for c in self.changes if c.change_type == ChangeType.REMOVED]

    @property
    def risk_increased(self) -> bool:
        """Check if risk level increased."""
        if not self.old_risk or not self.new_risk:
            return False
        return self.new_risk.score > self.old_risk.score

    @property
    def risk_delta(self) -> float:
        """Get change in risk score."""
        if not self.old_risk or not self.new_risk:
            return 0.0
        return self.new_risk.score - self.old_risk.score

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "has_changes": self.has_changes,
            "added_count": len(self.added),
            "removed_count": len(self.removed),
            "changes": [c.to_dict() for c in self.changes],
            "old_risk": self.old_risk.to_dict() if self.old_risk else None,
            "new_risk": self.new_risk.to_dict() if self.new_risk else None,
            "risk_increased": self.risk_increased,
            "risk_delta": self.risk_delta,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = ["## Permission Diff Report", ""]

        if not self.has_changes:
            lines.append("**No permission changes detected.**")
            return "\n".join(lines)

        # Summary
        lines.append(f"**Added**: {len(self.added)} | **Removed**: {len(self.removed)}")

        if self.risk_increased:
            lines.append(f"**⚠️ Risk Increased**: {self.risk_delta:+.0%}")
        elif self.risk_delta < 0:
            lines.append(f"**✅ Risk Decreased**: {self.risk_delta:+.0%}")

        lines.append("")

        # Added permissions
        if self.added:
            lines.append("### ➕ Added Permissions")
            lines.append("")
            for change in self.added:
                impact = f" ({change.risk_impact})" if change.risk_impact else ""
                lines.append(f"- `{change.category}`: `{change.value}`{impact}")
            lines.append("")

        # Removed permissions
        if self.removed:
            lines.append("### ➖ Removed Permissions")
            lines.append("")
            for change in self.removed:
                lines.append(f"- `{change.category}`: `{change.value}`")
            lines.append("")

        # Risk comparison
        if self.old_risk and self.new_risk:
            lines.append("### Risk Comparison")
            lines.append("")
            lines.append("| Metric | Before | After |")
            lines.append("|--------|--------|-------|")
            lines.append(f"| Level | {self.old_risk.level} | {self.new_risk.level} |")
            lines.append(f"| Score | {self.old_risk.score:.0%} | {self.new_risk.score:.0%} |")

            if self.new_risk.flags:
                lines.append("")
                lines.append("**New Risk Flags:**")
                for flag in self.new_risk.flags:
                    if not self.old_risk or flag not in self.old_risk.flags:
                        lines.append(f"- ⚠️ {flag}")

        return "\n".join(lines)


# =============================================================================
# DIFF CALCULATOR
# =============================================================================


class PermissionDiffCalculator:
    """Calculates differences between permission scopes."""

    def __init__(self, analyzer: PermissionAnalyzer | None = None):
        """Initialize calculator.

        Args:
            analyzer: Permission analyzer for risk assessment (optional)
        """
        self._analyzer = analyzer or PermissionAnalyzer()

    def diff_scopes(
        self,
        old_scope: PermissionScope,
        new_scope: PermissionScope,
        assess_risk: bool = True,
    ) -> PermissionDiff:
        """Calculate diff between two permission scopes.

        Args:
            old_scope: Original permissions
            new_scope: New permissions
            assess_risk: Whether to compute risk assessment

        Returns:
            PermissionDiff with all changes
        """
        changes: list[PermissionChange] = []

        # Compare each permission category
        categories = [
            ("filesystem_read", old_scope.filesystem_read, new_scope.filesystem_read),
            ("filesystem_write", old_scope.filesystem_write, new_scope.filesystem_write),
            ("network_allow", old_scope.network_allow, new_scope.network_allow),
            ("network_deny", old_scope.network_deny, new_scope.network_deny),
            ("shell_allow", old_scope.shell_allow, new_scope.shell_allow),
            ("shell_deny", old_scope.shell_deny, new_scope.shell_deny),
            ("env_read", old_scope.env_read, new_scope.env_read),
            ("env_write", old_scope.env_write, new_scope.env_write),
        ]

        for category, old_set, new_set in categories:
            # Added
            for value in new_set - old_set:
                risk_impact = self._assess_change_risk(category, value, ChangeType.ADDED)
                changes.append(
                    PermissionChange(
                        category=category,
                        value=value,
                        change_type=ChangeType.ADDED,
                        risk_impact=risk_impact,
                    )
                )

            # Removed
            for value in old_set - new_set:
                changes.append(
                    PermissionChange(
                        category=category,
                        value=value,
                        change_type=ChangeType.REMOVED,
                    )
                )

        # Compute risk assessments
        old_risk = None
        new_risk = None

        if assess_risk:
            old_flags = self._analyzer._check_risks_deterministic(
                type("MockSkill", (), {"name": "old", "permissions": old_scope})(),
                old_scope,
            )
            new_flags = self._analyzer._check_risks_deterministic(
                type("MockSkill", (), {"name": "new", "permissions": new_scope})(),
                new_scope,
            )
            old_risk = self._analyzer._compute_risk(old_scope, old_flags)
            new_risk = self._analyzer._compute_risk(new_scope, new_flags)

        return PermissionDiff(
            old_scope=old_scope,
            new_scope=new_scope,
            changes=changes,
            old_risk=old_risk,
            new_risk=new_risk,
        )

    def diff_skills(
        self,
        old_skill: Skill,
        new_skill: Skill,
        assess_risk: bool = True,
    ) -> PermissionDiff:
        """Calculate diff between two skill versions.

        Args:
            old_skill: Original skill
            new_skill: Updated skill
            assess_risk: Whether to compute risk assessment

        Returns:
            PermissionDiff with all changes
        """
        old_scope = self._extract_scope(old_skill)
        new_scope = self._extract_scope(new_skill)
        return self.diff_scopes(old_scope, new_scope, assess_risk)

    def _extract_scope(self, skill: Skill) -> PermissionScope:
        """Extract permission scope from skill."""
        permissions = getattr(skill, "permissions", None)
        if permissions is None:
            return PermissionScope()

        if isinstance(permissions, PermissionScope):
            return permissions

        if isinstance(permissions, dict):
            return PermissionScope.from_dict(permissions)

        return PermissionScope()

    def _assess_change_risk(
        self,
        category: str,
        value: str,
        change_type: ChangeType,
    ) -> str | None:
        """Assess risk impact of a single permission change.

        Args:
            category: Permission category
            value: Permission value
            change_type: Type of change

        Returns:
            Risk impact description or None
        """
        if change_type == ChangeType.REMOVED:
            return None  # Removals reduce risk

        # High-risk patterns
        high_risk_patterns = {
            "filesystem_read": ["~/.ssh/*", "~/.aws/*", "**/.env*", "**/secrets*"],
            "filesystem_write": ["/etc/*", "/usr/*", "/**"],
            "shell_allow": ["rm -rf", "dd if=", "ssh ", "scp "],
            "network_allow": ["*:*", "0.0.0.0:*"],
        }

        patterns = high_risk_patterns.get(category, [])
        from fnmatch import fnmatch

        for pattern in patterns:
            if fnmatch(value, pattern) or value.startswith(pattern.replace("*", "")):
                return "HIGH RISK"

        # Medium-risk patterns
        if category in ("shell_allow", "network_allow"):
            return "MODERATE"

        if category == "filesystem_write":
            return "ELEVATED"

        return None


# =============================================================================
# BATCH DIFF
# =============================================================================


def diff_lens_permissions(
    old_skills: list[Skill],
    new_skills: list[Skill],
) -> PermissionDiff:
    """Compare total permissions between two lens versions.

    Args:
        old_skills: Skills from old lens
        new_skills: Skills from new lens

    Returns:
        PermissionDiff of total permissions
    """
    # Aggregate permissions from each lens
    old_total = PermissionScope()
    new_total = PermissionScope()

    calculator = PermissionDiffCalculator()

    for skill in old_skills:
        scope = calculator._extract_scope(skill)
        old_total = old_total.merge_with(scope)

    for skill in new_skills:
        scope = calculator._extract_scope(skill)
        new_total = new_total.merge_with(scope)

    return calculator.diff_scopes(old_total, new_total)


def diff_skill_by_name(
    old_skills: list[Skill],
    new_skills: list[Skill],
) -> dict[str, PermissionDiff]:
    """Compare permissions for matching skills by name.

    Args:
        old_skills: Skills from old version
        new_skills: Skills from new version

    Returns:
        Dict of skill name to PermissionDiff
    """
    calculator = PermissionDiffCalculator()
    diffs: dict[str, PermissionDiff] = {}

    old_by_name = {s.name: s for s in old_skills}
    new_by_name = {s.name: s for s in new_skills}

    # Skills in both versions
    for name in old_by_name.keys() & new_by_name.keys():
        diff = calculator.diff_skills(old_by_name[name], new_by_name[name])
        if diff.has_changes:
            diffs[name] = diff

    # New skills
    for name in new_by_name.keys() - old_by_name.keys():
        scope = calculator._extract_scope(new_by_name[name])
        if not scope.is_empty():
            diffs[name] = calculator.diff_scopes(PermissionScope(), scope)

    # Removed skills (optional - might want to track these)
    for name in old_by_name.keys() - new_by_name.keys():
        scope = calculator._extract_scope(old_by_name[name])
        if not scope.is_empty():
            diffs[f"{name} (REMOVED)"] = calculator.diff_scopes(scope, PermissionScope())

    return diffs
