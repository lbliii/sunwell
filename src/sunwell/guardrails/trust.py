"""Trust Zone Evaluation for Autonomy Guardrails (RFC-048).

Evaluates paths against trust zones to determine risk overrides.
"""


from fnmatch import fnmatch
from pathlib import Path

from sunwell.guardrails.classifier import DEFAULT_TRUST_ZONES
from sunwell.guardrails.types import ActionRisk, TrustZone


class TrustZoneEvaluator:
    """Evaluate paths against trust zones.

    Trust zones provide path-based risk overrides. For example,
    files in tests/ are always SAFE, while files in auth/ are DANGEROUS.
    """

    def __init__(
        self,
        custom_zones: tuple[TrustZone, ...] = (),
        include_defaults: bool = True,
    ):
        """Initialize evaluator.

        Args:
            custom_zones: Custom trust zones (evaluated first)
            include_defaults: Whether to include default zones
        """
        self.zones: tuple[TrustZone, ...] = custom_zones
        if include_defaults:
            self.zones = custom_zones + DEFAULT_TRUST_ZONES

    def evaluate(self, path: str | Path) -> TrustZoneMatch | None:
        """Evaluate a path against trust zones.

        Args:
            path: Path to evaluate

        Returns:
            TrustZoneMatch if a zone matches, None otherwise
        """
        path_str = str(path)

        for zone in self.zones:
            if self._matches_pattern(path_str, zone.pattern):
                return TrustZoneMatch(
                    path=path_str,
                    zone=zone,
                    risk_override=zone.risk_override,
                    allowed_in_autonomous=zone.allowed_in_autonomous,
                )

        return None

    def evaluate_all(self, paths: list[str | Path]) -> dict[str, TrustZoneMatch | None]:
        """Evaluate multiple paths.

        Args:
            paths: Paths to evaluate

        Returns:
            Dictionary mapping path to match result
        """
        return {str(p): self.evaluate(p) for p in paths}

    def is_safe_path(self, path: str | Path) -> bool:
        """Check if path is in a SAFE zone.

        Args:
            path: Path to check

        Returns:
            True if path matches a SAFE zone
        """
        match = self.evaluate(path)
        return match is not None and match.risk_override == ActionRisk.SAFE

    def is_forbidden_path(self, path: str | Path) -> bool:
        """Check if path is in a FORBIDDEN zone.

        Args:
            path: Path to check

        Returns:
            True if path matches a FORBIDDEN zone
        """
        match = self.evaluate(path)
        return match is not None and match.risk_override == ActionRisk.FORBIDDEN

    def is_allowed_in_autonomous(self, path: str | Path) -> bool:
        """Check if path can be modified in autonomous mode.

        Args:
            path: Path to check

        Returns:
            True if path is allowed in autonomous mode
        """
        match = self.evaluate(path)
        # No match = allowed (default behavior)
        if match is None:
            return True
        return match.allowed_in_autonomous

    def get_blocked_paths(self, paths: list[str | Path]) -> list[str]:
        """Get paths that are blocked in autonomous mode.

        Args:
            paths: Paths to check

        Returns:
            List of paths that are blocked
        """
        blocked = []
        for path in paths:
            if not self.is_allowed_in_autonomous(path):
                blocked.append(str(path))
        return blocked

    def summarize_paths(self, paths: list[str | Path]) -> dict:
        """Summarize trust zone evaluation for multiple paths.

        Args:
            paths: Paths to summarize

        Returns:
            Summary dictionary with counts by risk level
        """
        results = self.evaluate_all(paths)

        summary = {
            "total": len(paths),
            "by_risk": {
                "safe": 0,
                "moderate": 0,
                "dangerous": 0,
                "forbidden": 0,
                "unclassified": 0,
            },
            "blocked_in_autonomous": 0,
            "blocked_paths": [],
        }

        for path, match in results.items():
            if match is None:
                summary["by_risk"]["unclassified"] += 1
            elif match.risk_override == ActionRisk.SAFE:
                summary["by_risk"]["safe"] += 1
            elif match.risk_override == ActionRisk.MODERATE:
                summary["by_risk"]["moderate"] += 1
            elif match.risk_override == ActionRisk.DANGEROUS:
                summary["by_risk"]["dangerous"] += 1
            elif match.risk_override == ActionRisk.FORBIDDEN:
                summary["by_risk"]["forbidden"] += 1

            if match and not match.allowed_in_autonomous:
                summary["blocked_in_autonomous"] += 1
                summary["blocked_paths"].append(path)

        return summary

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a glob pattern.

        Handles various pattern formats:
        - Simple: "*.py"
        - Directory: "tests/**"
        - Nested: "**/auth/**"
        """
        # Direct match
        if fnmatch(path, pattern):
            return True

        # Try with ** prefix for nested matching
        if not pattern.startswith("**") and fnmatch(path, f"**/{pattern}"):
            return True

        # Check if pattern matches any path component
        path_parts = Path(path).parts
        for i in range(len(path_parts)):
            partial = "/".join(path_parts[i:])
            if fnmatch(partial, pattern):
                return True

        return False


class TrustZoneMatch:
    """Result of a trust zone evaluation."""

    def __init__(
        self,
        path: str,
        zone: TrustZone,
        risk_override: ActionRisk | None,
        allowed_in_autonomous: bool,
    ):
        """Initialize match result.

        Args:
            path: The matched path
            zone: The matching zone
            risk_override: Risk level override
            allowed_in_autonomous: Whether allowed in autonomous mode
        """
        self.path = path
        self.zone = zone
        self.risk_override = risk_override
        self.allowed_in_autonomous = allowed_in_autonomous

    def __repr__(self) -> str:
        return (
            f"TrustZoneMatch(path={self.path!r}, "
            f"risk={self.risk_override}, "
            f"autonomous={self.allowed_in_autonomous})"
        )
