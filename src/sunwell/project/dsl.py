"""Constraint DSL parser for schema validation (RFC-035).

This module provides a simple domain-specific language for expressing
constraints across artifacts. The DSL supports:

- FOR x IN collection: Iteration over artifacts
- WHERE condition: Filtering
- ASSERT condition: The actual check

Example:
    ```
    FOR character IN artifacts.characters
    FOR scene_a, scene_b IN artifacts.scenes
    WHERE character IN scene_a.characters_present
      AND character IN scene_b.characters_present
      AND scene_a.timeline_position == scene_b.timeline_position
    ASSERT scene_a.location == scene_b.location
    ```

Security note: This DSL is data, not code. It provides a sandboxed way
to express constraints without arbitrary code execution.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ForClause:
    """A FOR iteration clause in the DSL.

    Examples:
        FOR character IN artifacts.characters
        FOR scene_a, scene_b IN artifacts.scenes
    """

    variables: tuple[str, ...]  # Variable names (e.g., ("character",) or ("scene_a", "scene_b"))
    collection: str  # Collection path (e.g., "artifacts.characters")


@dataclass(frozen=True, slots=True)
class ParsedRule:
    """A parsed constraint rule ready for execution.

    Contains the structured representation of a constraint DSL rule.
    """

    for_clauses: tuple[ForClause, ...]
    where_clause: str | None
    assert_clause: str
    raw_rule: str = ""


class ConstraintDSL:
    """Parser for the constraint DSL.

    The DSL grammar:
        rule := for_clause+ [where_clause] assert_clause
        for_clause := "FOR" var_list "IN" collection
        var_list := var | var "," var_list
        where_clause := "WHERE" condition
        assert_clause := "ASSERT" condition
        collection := "artifacts." type_name
        condition := comparison (("AND" | "OR") comparison)*
        comparison := expr "==" expr | expr "!=" expr | expr "IN" expr
    """

    # Regex patterns for parsing
    FOR_PATTERN = re.compile(
        r"FOR\s+(\w+(?:\s*,\s*\w+)*)\s+IN\s+([\w.]+)",
        re.IGNORECASE,
    )
    WHERE_PATTERN = re.compile(r"WHERE\s+(.+?)(?=ASSERT)", re.IGNORECASE | re.DOTALL)
    ASSERT_PATTERN = re.compile(r"ASSERT\s+(.+)", re.IGNORECASE | re.DOTALL)

    def parse(self, rule: str) -> ParsedRule:
        """Parse a constraint DSL rule.

        Args:
            rule: The DSL rule string

        Returns:
            ParsedRule ready for execution

        Raises:
            ValueError: If rule is malformed
        """
        rule = rule.strip()

        # Parse FOR clauses
        for_clauses = self._parse_for_clauses(rule)
        if not for_clauses:
            raise ValueError(f"Rule must have at least one FOR clause: {rule[:100]}")

        # Parse WHERE clause (optional)
        where_clause = self._parse_where_clause(rule)

        # Parse ASSERT clause (required)
        assert_clause = self._parse_assert_clause(rule)
        if not assert_clause:
            raise ValueError(f"Rule must have an ASSERT clause: {rule[:100]}")

        return ParsedRule(
            for_clauses=for_clauses,
            where_clause=where_clause,
            assert_clause=assert_clause,
            raw_rule=rule,
        )

    def _parse_for_clauses(self, rule: str) -> tuple[ForClause, ...]:
        """Extract all FOR clauses from the rule."""
        matches = self.FOR_PATTERN.findall(rule)

        clauses = []
        for vars_str, collection in matches:
            # Parse variable list (can be "x" or "x, y, z")
            variables = tuple(v.strip() for v in vars_str.split(","))
            clauses.append(ForClause(variables=variables, collection=collection))

        return tuple(clauses)

    def _parse_where_clause(self, rule: str) -> str | None:
        """Extract the WHERE clause if present."""
        match = self.WHERE_PATTERN.search(rule)
        if match:
            return match.group(1).strip()
        return None

    def _parse_assert_clause(self, rule: str) -> str | None:
        """Extract the ASSERT clause."""
        match = self.ASSERT_PATTERN.search(rule)
        if match:
            return match.group(1).strip()
        return None


@dataclass
class ConstraintEvaluator:
    """Evaluates parsed constraint rules against artifacts.

    This class provides a safe evaluation environment for constraint
    expressions without arbitrary code execution.
    """

    def evaluate_condition(
        self,
        condition: str,
        bindings: dict[str, Any],
    ) -> bool:
        """Evaluate a condition expression with variable bindings.

        Supports:
        - Equality: a == b, a != b
        - Membership: a IN b
        - Boolean: AND, OR
        - Field access: artifact.field

        Args:
            condition: The condition expression
            bindings: Variable bindings (name → value)

        Returns:
            True if condition is satisfied
        """
        condition = condition.strip()

        # Handle AND/OR (simple left-to-right, no precedence)
        if " AND " in condition.upper():
            parts = re.split(r"\s+AND\s+", condition, flags=re.IGNORECASE)
            return all(self.evaluate_condition(p, bindings) for p in parts)

        if " OR " in condition.upper():
            parts = re.split(r"\s+OR\s+", condition, flags=re.IGNORECASE)
            return any(self.evaluate_condition(p, bindings) for p in parts)

        # Handle comparisons
        if "==" in condition:
            left, right = condition.split("==", 1)
            return self._resolve_value(left.strip(), bindings) == self._resolve_value(
                right.strip(), bindings
            )

        if "!=" in condition:
            left, right = condition.split("!=", 1)
            return self._resolve_value(left.strip(), bindings) != self._resolve_value(
                right.strip(), bindings
            )

        # Handle IN membership
        if " IN " in condition.upper():
            match = re.match(r"(.+?)\s+IN\s+(.+)", condition, re.IGNORECASE)
            if match:
                item = self._resolve_value(match.group(1).strip(), bindings)
                collection = self._resolve_value(match.group(2).strip(), bindings)
                if collection is None:
                    return False
                return item in collection

        # Handle bare boolean
        value = self._resolve_value(condition, bindings)
        return bool(value)

    def _resolve_value(self, expr: str, bindings: dict[str, Any]) -> Any:
        """Resolve an expression to a value.

        Handles:
        - Variable references: var_name
        - Field access: var_name.field
        - Literal strings: "string" or 'string'
        - Literal numbers: 123, 123.45
        """
        expr = expr.strip()

        # Literal string
        if (expr.startswith('"') and expr.endswith('"')) or (
            expr.startswith("'") and expr.endswith("'")
        ):
            return expr[1:-1]

        # Literal number
        if re.match(r"^-?\d+\.?\d*$", expr):
            if "." in expr:
                return float(expr)
            return int(expr)

        # Field access (var.field or var.field.subfield)
        if "." in expr:
            parts = expr.split(".")
            value = bindings.get(parts[0])
            for part in parts[1:]:
                if value is None:
                    return None
                if isinstance(value, dict):
                    value = value.get(part)
                elif hasattr(value, part):
                    value = getattr(value, part)
                elif hasattr(value, "__getitem__"):
                    try:
                        value = value[part]
                    except (KeyError, TypeError):
                        return None
                else:
                    return None
            return value

        # Variable reference
        return bindings.get(expr)

    def enumerate_bindings(
        self,
        for_clauses: tuple[ForClause, ...],
        artifacts: dict[str, list[dict[str, Any]]],
    ):
        """Enumerate all possible variable bindings from FOR clauses.

        Yields all combinations of variable assignments.

        Args:
            for_clauses: The FOR clauses to process
            artifacts: Artifact collections (type_name → list of artifacts)

        Yields:
            Dict mapping variable names to artifact values
        """
        if not for_clauses:
            yield {}
            return

        first_clause = for_clauses[0]
        rest_clauses = for_clauses[1:]

        # Get collection
        # Handle "artifacts.type" format
        collection_path = first_clause.collection
        if collection_path.startswith("artifacts."):
            artifact_type = collection_path[len("artifacts."):]
            collection = artifacts.get(artifact_type, [])
        else:
            collection = artifacts.get(collection_path, [])

        # Single variable: iterate over collection
        if len(first_clause.variables) == 1:
            var_name = first_clause.variables[0]
            for item in collection:
                for rest_bindings in self.enumerate_bindings(rest_clauses, artifacts):
                    yield {var_name: item, **rest_bindings}

        # Multiple variables: iterate over all pairs/tuples
        else:
            import itertools

            # Generate all combinations
            for combo in itertools.product(collection, repeat=len(first_clause.variables)):
                bindings = dict(zip(first_clause.variables, combo, strict=True))
                for rest_bindings in self.enumerate_bindings(rest_clauses, artifacts):
                    yield {**bindings, **rest_bindings}
