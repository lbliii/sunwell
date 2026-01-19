"""Constraint validators for schema validation (RFC-035).

This module provides the ConstraintValidator that executes constraint DSL
rules against project artifacts to catch inconsistencies.

Example:
    ```python
    validator = ConstraintValidator()
    violations = validator.validate(
        rule="FOR c IN artifacts.characters ASSERT c.name != ''",
        artifacts={"characters": [{"name": "John"}, {"name": ""}]},
    )
    # violations contains one entry for the empty name
    ```
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.project.dsl import ConstraintDSL, ConstraintEvaluator, ParsedRule

if TYPE_CHECKING:
    from sunwell.project.schema import ValidatorConfig


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    """A violation of a constraint rule.

    Contains details about what failed and which artifacts were involved.
    """

    rule_name: str
    description: str
    message: str
    severity: str = "error"
    bindings: dict[str, Any] = field(default_factory=dict)  # type: ignore[arg-type]
    artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "rule_name": self.rule_name,
            "description": self.description,
            "message": self.message,
            "severity": self.severity,
            "bindings": {k: str(v) for k, v in self.bindings.items()},
            "artifact_ids": list(self.artifact_ids),
        }


@dataclass
class ConstraintValidator:
    """Executes constraint DSL rules against project artifacts.

    The validator parses rules written in the constraint DSL and
    evaluates them against loaded artifacts. It returns a list of
    violations for any constraints that fail.

    Example:
        >>> validator = ConstraintValidator()
        >>> rule = '''
        ... FOR character IN artifacts.characters
        ... FOR scene IN artifacts.scenes
        ... WHERE character.id IN scene.characters_present
        ... ASSERT scene.timeline_position != None
        ... '''
        >>> violations = validator.validate(
        ...     rule=rule,
        ...     artifacts=artifacts,
        ...     rule_name="timeline_consistency",
        ... )
    """

    dsl: ConstraintDSL = field(default_factory=ConstraintDSL)
    evaluator: ConstraintEvaluator = field(default_factory=ConstraintEvaluator)

    def validate(
        self,
        rule: str,
        artifacts: dict[str, list[dict[str, Any]]],
        rule_name: str = "unnamed",
        description: str = "",
        severity: str = "error",
    ) -> list[ConstraintViolation]:
        """Execute a constraint rule against loaded artifacts.

        The DSL supports:
        - FOR x IN collection: iteration
        - WHERE condition: filtering
        - ASSERT condition: the actual check

        Args:
            rule: The constraint DSL rule
            artifacts: Artifact collections (type_name → list of artifacts)
            rule_name: Name for error reporting
            description: Human description of what's checked
            severity: error, warning, or info

        Returns:
            List of violations (empty = valid)
        """
        # Parse the rule
        try:
            parsed = self.dsl.parse(rule)
        except ValueError as e:
            # Rule itself is malformed
            return [
                ConstraintViolation(
                    rule_name=rule_name,
                    description=description,
                    message=f"Invalid rule syntax: {e}",
                    severity="error",
                )
            ]

        return self.validate_parsed(
            parsed=parsed,
            artifacts=artifacts,
            rule_name=rule_name,
            description=description,
            severity=severity,
        )

    def validate_parsed(
        self,
        parsed: ParsedRule,
        artifacts: dict[str, list[dict[str, Any]]],
        rule_name: str = "unnamed",
        description: str = "",
        severity: str = "error",
    ) -> list[ConstraintViolation]:
        """Execute a pre-parsed constraint rule.

        Args:
            parsed: The parsed rule
            artifacts: Artifact collections
            rule_name: Name for error reporting
            description: Human description
            severity: error, warning, or info

        Returns:
            List of violations
        """
        violations = []

        # Enumerate all variable bindings
        for bindings in self.evaluator.enumerate_bindings(parsed.for_clauses, artifacts):
            # Check WHERE clause if present (SIM102: combined if)
            if parsed.where_clause and not self.evaluator.evaluate_condition(
                parsed.where_clause, bindings
            ):
                continue  # Filtered out by WHERE

            # Check ASSERT clause
            if not self.evaluator.evaluate_condition(parsed.assert_clause, bindings):
                # Collect artifact IDs from bindings
                artifact_ids = []
                for value in bindings.values():
                    if isinstance(value, dict) and "id" in value:
                        artifact_ids.append(value["id"])

                violations.append(
                    ConstraintViolation(
                        rule_name=rule_name,
                        description=description,
                        message=self._make_violation_message(parsed, bindings),
                        severity=severity,
                        bindings=dict(bindings),
                        artifact_ids=tuple(artifact_ids),
                    )
                )

        return violations

    def _make_violation_message(
        self,
        parsed: ParsedRule,
        bindings: dict[str, Any],
    ) -> str:
        """Generate a human-readable violation message."""
        # Build a readable summary of the failing bindings
        binding_strs = []
        for name, value in bindings.items():
            if isinstance(value, dict):
                if "id" in value:
                    binding_strs.append(f"{name}={value['id']}")
                elif "name" in value:
                    binding_strs.append(f"{name}='{value['name']}'")
                else:
                    binding_strs.append(f"{name}={{...}}")
            else:
                binding_strs.append(f"{name}={value}")

        return f"ASSERT failed: {parsed.assert_clause} (with {', '.join(binding_strs)})"


@dataclass
class SchemaValidationRunner:
    """Runs all validators defined in a project schema.

    This class coordinates running both constraint validators and
    LLM-based validators, aggregating results.
    """

    constraint_validator: ConstraintValidator = field(default_factory=ConstraintValidator)

    def run_all(
        self,
        validators: tuple[ValidatorConfig, ...],
        artifacts: dict[str, list[dict[str, Any]]],
    ) -> list[ConstraintViolation]:
        """Run all validators against artifacts.

        Args:
            validators: Validator configurations from schema
            artifacts: Loaded artifacts by type

        Returns:
            List of all violations
        """
        all_violations: list[ConstraintViolation] = []

        for validator in validators:
            if validator.method == "constraint":
                violations = self.constraint_validator.validate(
                    rule=validator.rule,
                    artifacts=artifacts,
                    rule_name=validator.name,
                    description=validator.description,
                    severity=validator.severity,
                )
                all_violations.extend(violations)
            elif validator.method == "llm":
                # LLM validators would integrate with existing HeuristicValidator
                # For now, skip (placeholder for future implementation)
                pass

        return all_violations

    def filter_by_severity(
        self,
        violations: list[ConstraintViolation],
        min_severity: str = "warning",
    ) -> list[ConstraintViolation]:
        """Filter violations by minimum severity.

        Args:
            violations: List of violations
            min_severity: Minimum severity to include (error > warning > info)

        Returns:
            Filtered list
        """
        severity_order = {"error": 0, "warning": 1, "info": 2}
        min_level = severity_order.get(min_severity, 1)

        return [
            v for v in violations
            if severity_order.get(v.severity, 1) <= min_level
        ]

    def format_report(
        self,
        violations: list[ConstraintViolation],
        schema_name: str = "Project",
    ) -> str:
        """Format violations as a human-readable report.

        Args:
            violations: List of violations
            schema_name: Name of the schema for the header

        Returns:
            Formatted report string
        """
        if not violations:
            return f"✅ All validators passed for {schema_name}"

        lines = [
            "═" * 60,
            f"📋 Validation Report: {schema_name}",
            "═" * 60,
            "",
        ]

        # Group by severity
        errors = [v for v in violations if v.severity == "error"]
        warnings = [v for v in violations if v.severity == "warning"]
        infos = [v for v in violations if v.severity == "info"]

        if errors:
            lines.append(f"❌ Errors ({len(errors)}):")
            for v in errors:
                lines.append(f"  • [{v.rule_name}] {v.message}")
            lines.append("")

        if warnings:
            lines.append(f"⚠️ Warnings ({len(warnings)}):")
            for v in warnings:
                lines.append(f"  • [{v.rule_name}] {v.message}")
            lines.append("")

        if infos:
            lines.append(f"ℹ️ Info ({len(infos)}):")
            for v in infos:
                lines.append(f"  • [{v.rule_name}] {v.message}")
            lines.append("")

        lines.append("═" * 60)

        return "\n".join(lines)
