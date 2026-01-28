"""Behavioral assertions for journey testing.

Checks observable outcomes against expectations, allowing for
ranges and patterns rather than exact matches.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.benchmark.journeys.recorder import EventRecorder
from sunwell.benchmark.journeys.types import (
    Expectation,
    FileExpectation,
    SignalExpectation,
    ToolExpectation,
)


@dataclass(frozen=True, slots=True)
class AssertionResult:
    """Result of a single assertion check."""

    passed: bool
    """Whether the assertion passed."""

    message: str
    """Human-readable description of the result."""

    category: str = "general"
    """Category: intent, signals, tools, files, output."""

    expected: Any = None
    """What was expected."""

    actual: Any = None
    """What was found."""


@dataclass(slots=True)
class AssertionReport:
    """Complete assertion report for a journey or turn."""

    results: list[AssertionResult] = field(default_factory=list)
    """All assertion results."""

    @property
    def passed(self) -> bool:
        """True if all assertions passed."""
        return all(r.passed for r in self.results)

    @property
    def failed_count(self) -> int:
        """Number of failed assertions."""
        return sum(1 for r in self.results if not r.passed)

    @property
    def passed_count(self) -> int:
        """Number of passed assertions."""
        return sum(1 for r in self.results if r.passed)

    def add(self, result: AssertionResult) -> None:
        """Add an assertion result."""
        self.results.append(result)

    def merge(self, other: "AssertionReport") -> None:
        """Merge another report into this one."""
        self.results.extend(other.results)

    def failures(self) -> list[AssertionResult]:
        """Get all failed assertions."""
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        """Get a summary string."""
        total = len(self.results)
        passed = self.passed_count
        return f"{passed}/{total} assertions passed"


class BehavioralAssertions:
    """Check observable outcomes against expectations.

    Supports flexible matching:
    - Intent: exact match or one of alternatives
    - Signals: exact match or range (tuple)
    - Tools: tool was called, args contain patterns
    - Files: file exists, content contains patterns
    - Output: contains patterns (case-insensitive)

    Example:
        >>> assertions = BehavioralAssertions()
        >>> report = assertions.check_all(recorder, expectation)
        >>> assert report.passed
    """

    def check_all(
        self,
        recorder: EventRecorder,
        expectation: Expectation,
        workspace: Path | None = None,
    ) -> AssertionReport:
        """Run all assertions for an expectation.

        Args:
            recorder: EventRecorder with captured events.
            expectation: Expected behaviors.
            workspace: Workspace path for file checks.

        Returns:
            AssertionReport with all results.
        """
        report = AssertionReport()

        # Intent check
        if expectation.intent:
            report.add(self.check_intent(recorder, expectation.intent))

        # Signals check
        if expectation.signals:
            report.merge(self.check_signals(recorder, expectation.signals))

        # Tools called check
        for tool_exp in expectation.tools_called:
            report.add(self.check_tool_called(recorder, tool_exp))

        # Tools called any (at least one)
        if expectation.tools_called_any:
            report.add(self.check_tools_called_any(recorder, expectation.tools_called_any))

        # Minimum tool calls check
        if expectation.tools_called_min > 0:
            report.add(self.check_tools_called_min(recorder, expectation.tools_called_min))

        # Tools NOT called check
        for tool_name in expectation.tools_not_called:
            report.add(self.check_tool_not_called(recorder, tool_name))

        # Files created check
        for file_exp in expectation.files_created:
            report.add(self.check_file_created(recorder, file_exp, workspace))

        # Files modified check
        for file_exp in expectation.files_modified:
            report.add(self.check_file_modified(recorder, file_exp, workspace))

        # Output contains check
        if expectation.output_contains:
            report.add(self.check_output_contains(recorder, expectation.output_contains))

        # Output matches (regex) check
        if expectation.output_matches:
            report.add(self.check_output_matches(recorder, expectation.output_matches))

        # Output NOT contains check
        if expectation.output_not_contains:
            report.add(self.check_output_not_contains(recorder, expectation.output_not_contains))

        # Routing strategy check
        if expectation.routing_strategy:
            report.add(self.check_routing_strategy(recorder, expectation.routing_strategy))

        # Validation must pass check
        if expectation.validation_must_pass:
            report.add(self.check_validation_passed(recorder))

        # No reliability issues check
        if expectation.no_reliability_issues:
            report.add(self.check_no_reliability_issues(recorder))

        # Token budget check
        if expectation.max_tokens is not None:
            report.add(self.check_token_budget(recorder, expectation.max_tokens))

        return report

    def check_intent(
        self,
        recorder: EventRecorder,
        expected: str | tuple[str, ...],
    ) -> AssertionResult:
        """Check intent classification matches expected.

        Args:
            recorder: EventRecorder with captured events.
            expected: Expected intent or tuple of acceptable intents.
        """
        actual = recorder.intent

        # Normalize to tuple for comparison
        if isinstance(expected, str):
            expected_set = {expected.upper()}
        else:
            expected_set = {e.upper() for e in expected}

        actual_upper = (actual or "NONE").upper()
        passed = actual_upper in expected_set

        return AssertionResult(
            passed=passed,
            message=f"Intent: expected {expected}, got {actual}",
            category="intent",
            expected=expected,
            actual=actual,
        )

    def _check_signal_value(
        self,
        signal_name: str,
        expected: tuple[str, ...] | str,
        actual: Any,
    ) -> AssertionResult:
        """Check a single signal value against expected (supports tuples)."""
        if isinstance(expected, tuple):
            passed = actual in expected
            exp_str = f"one of {expected}"
        else:
            passed = actual == expected
            exp_str = expected

        return AssertionResult(
            passed=passed,
            message=f"Signal {signal_name}: expected {exp_str}, got {actual}",
            category="signals",
            expected=expected,
            actual=actual,
        )

    def check_signals(
        self,
        recorder: EventRecorder,
        expected: SignalExpectation,
    ) -> AssertionReport:
        """Check extracted signals match expected.

        Args:
            recorder: EventRecorder with captured events.
            expected: Expected signal values.
        """
        report = AssertionReport()

        # Check each signal field if specified (all support tuples now)
        if expected.needs_tools is not None:
            actual = recorder.get_signal("needs_tools")
            report.add(self._check_signal_value("needs_tools", expected.needs_tools, actual))

        if expected.complexity is not None:
            actual = recorder.get_signal("complexity")
            report.add(self._check_signal_value("complexity", expected.complexity, actual))

        if expected.is_ambiguous is not None:
            actual = recorder.get_signal("is_ambiguous")
            report.add(self._check_signal_value("is_ambiguous", expected.is_ambiguous, actual))

        if expected.is_dangerous is not None:
            actual = recorder.get_signal("is_dangerous")
            report.add(self._check_signal_value("is_dangerous", expected.is_dangerous, actual))

        if expected.is_epic is not None:
            actual = recorder.get_signal("is_epic")
            report.add(self._check_signal_value("is_epic", expected.is_epic, actual))

        if expected.domain is not None:
            actual = recorder.get_signal("domain")
            report.add(self._check_signal_value("domain", expected.domain, actual))

        return report

    def check_tool_called(
        self,
        recorder: EventRecorder,
        expected: ToolExpectation,
    ) -> AssertionResult:
        """Check that a tool was called with expected args.

        Args:
            recorder: EventRecorder with captured events.
            expected: Expected tool call.
        """
        # First check if tool was called at all
        if not recorder.has_tool_call(expected.name):
            return AssertionResult(
                passed=False,
                message=f"Tool {expected.name} was NOT called",
                category="tools",
                expected=expected.name,
                actual=None,
            )

        # If no args expected, we're done
        if not expected.args_contain:
            return AssertionResult(
                passed=True,
                message=f"Tool {expected.name} was called",
                category="tools",
                expected=expected.name,
                actual=expected.name,
            )

        # Check args
        if recorder.tool_call_args_match(expected.name, expected.args_contain):
            return AssertionResult(
                passed=True,
                message=f"Tool {expected.name} called with matching args",
                category="tools",
                expected=expected.args_contain,
                actual="matched",
            )

        # Get actual args for reporting
        calls = recorder.get_tool_calls(expected.name)
        actual_args = [tc.arguments for tc in calls]

        return AssertionResult(
            passed=False,
            message=f"Tool {expected.name} called but args don't match: expected {expected.args_contain}",
            category="tools",
            expected=expected.args_contain,
            actual=actual_args,
        )

    def check_tool_not_called(
        self,
        recorder: EventRecorder,
        tool_name: str,
    ) -> AssertionResult:
        """Check that a tool was NOT called.

        Args:
            recorder: EventRecorder with captured events.
            tool_name: Tool that should not have been called.
        """
        if recorder.has_tool_call(tool_name):
            calls = recorder.get_tool_calls(tool_name)
            return AssertionResult(
                passed=False,
                message=f"Tool {tool_name} was called {len(calls)} time(s) but should NOT be",
                category="tools",
                expected=f"NOT {tool_name}",
                actual=f"{tool_name} called",
            )

        return AssertionResult(
            passed=True,
            message=f"Tool {tool_name} was correctly NOT called",
            category="tools",
            expected=f"NOT {tool_name}",
            actual="not called",
        )

    def check_file_created(
        self,
        recorder: EventRecorder,
        expected: FileExpectation,
        workspace: Path | None = None,
    ) -> AssertionResult:
        """Check that a file was created.

        Args:
            recorder: EventRecorder with captured events.
            expected: Expected file.
            workspace: Workspace path for resolving relative paths.
        """
        # Check via recorder first (from tool calls)
        found_in_recorder = False
        if expected.pattern:
            found_in_recorder = recorder.has_file_change(pattern=expected.pattern)
        elif expected.path:
            found_in_recorder = recorder.has_file_change(path=expected.path)

        # Also check filesystem if workspace provided
        found_on_disk = False
        if workspace:
            if expected.pattern:
                found_on_disk = len(list(workspace.glob(expected.pattern))) > 0
            elif expected.path:
                found_on_disk = (workspace / expected.path).exists()

        found = found_in_recorder or found_on_disk

        if not found:
            identifier = expected.pattern or expected.path
            return AssertionResult(
                passed=False,
                message=f"File {identifier} was NOT created",
                category="files",
                expected=identifier,
                actual=None,
            )

        # Check content if specified
        if expected.contains:
            content_found = False
            identifier = expected.pattern or expected.path or ""

            # Try to get content from recorder
            for fc in recorder.file_changes:
                if expected.path and fc.path == expected.path:
                    if fc.content and all(c.lower() in fc.content.lower() for c in expected.contains):
                        content_found = True
                        break
                elif expected.pattern and fnmatch.fnmatch(fc.path, expected.pattern):
                    if fc.content and all(c.lower() in fc.content.lower() for c in expected.contains):
                        content_found = True
                        break

            # Try filesystem if not found in recorder
            if not content_found and workspace:
                if expected.path:
                    file_path = workspace / expected.path
                    if file_path.exists():
                        content = file_path.read_text()
                        content_found = all(c.lower() in content.lower() for c in expected.contains)
                elif expected.pattern:
                    for fp in workspace.glob(expected.pattern):
                        content = fp.read_text()
                        if all(c.lower() in content.lower() for c in expected.contains):
                            content_found = True
                            break

            if not content_found:
                return AssertionResult(
                    passed=False,
                    message=f"File {identifier} created but missing content: {expected.contains}",
                    category="files",
                    expected=expected.contains,
                    actual="content not matched",
                )

        identifier = expected.pattern or expected.path
        return AssertionResult(
            passed=True,
            message=f"File {identifier} was created with expected content",
            category="files",
            expected=identifier,
            actual="created",
        )

    def check_file_modified(
        self,
        recorder: EventRecorder,
        expected: FileExpectation,
        workspace: Path | None = None,
    ) -> AssertionResult:
        """Check that a file was modified.

        Same logic as created, but semantically different.
        """
        # Reuse created logic - for our purposes they're the same check
        result = self.check_file_created(recorder, expected, workspace)

        # Adjust message
        identifier = expected.pattern or expected.path
        if result.passed:
            return AssertionResult(
                passed=True,
                message=f"File {identifier} was modified with expected content",
                category="files",
                expected=identifier,
                actual="modified",
            )
        else:
            return AssertionResult(
                passed=False,
                message=result.message.replace("created", "modified"),
                category="files",
                expected=result.expected,
                actual=result.actual,
            )

    def check_output_contains(
        self,
        recorder: EventRecorder,
        patterns: tuple[str, ...],
    ) -> AssertionResult:
        """Check that output contains all patterns.

        Args:
            recorder: EventRecorder with captured events.
            patterns: Patterns that must all be present (case-insensitive).
        """
        output = recorder.all_output.lower()
        missing = [p for p in patterns if p.lower() not in output]

        if missing:
            return AssertionResult(
                passed=False,
                message=f"Output missing patterns: {missing}",
                category="output",
                expected=patterns,
                actual=f"missing {missing}",
            )

        return AssertionResult(
            passed=True,
            message=f"Output contains all {len(patterns)} expected patterns",
            category="output",
            expected=patterns,
            actual="all present",
        )

    def check_output_not_contains(
        self,
        recorder: EventRecorder,
        patterns: tuple[str, ...],
    ) -> AssertionResult:
        """Check that output does NOT contain any patterns.

        Args:
            recorder: EventRecorder with captured events.
            patterns: Patterns that must NOT be present.
        """
        output = recorder.all_output.lower()
        found = [p for p in patterns if p.lower() in output]

        if found:
            return AssertionResult(
                passed=False,
                message=f"Output incorrectly contains: {found}",
                category="output",
                expected=f"NOT {patterns}",
                actual=f"found {found}",
            )

        return AssertionResult(
            passed=True,
            message=f"Output correctly excludes {len(patterns)} patterns",
            category="output",
            expected=f"NOT {patterns}",
            actual="none found",
        )

    def check_output_matches(
        self,
        recorder: EventRecorder,
        patterns: tuple[str, ...],
    ) -> AssertionResult:
        """Check that output matches all regex patterns.

        Args:
            recorder: EventRecorder with captured events.
            patterns: Regex patterns that must all match.
        """
        output = recorder.all_output
        failed: list[str] = []

        for pattern in patterns:
            try:
                if not re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
                    failed.append(pattern)
            except re.error as e:
                return AssertionResult(
                    passed=False,
                    message=f"Invalid regex pattern '{pattern}': {e}",
                    category="output",
                    expected=patterns,
                    actual=f"regex error: {e}",
                )

        if failed:
            return AssertionResult(
                passed=False,
                message=f"Output failed to match patterns: {failed}",
                category="output",
                expected=patterns,
                actual=f"failed to match {failed}",
            )

        return AssertionResult(
            passed=True,
            message=f"Output matches all {len(patterns)} regex patterns",
            category="output",
            expected=patterns,
            actual="all matched",
        )

    def check_tools_called_any(
        self,
        recorder: EventRecorder,
        tool_names: tuple[str, ...],
    ) -> AssertionResult:
        """Check that at least ONE of the tools was called.

        Args:
            recorder: EventRecorder with captured events.
            tool_names: Tools where at least one must be called.
        """
        called = [name for name in tool_names if recorder.has_tool_call(name)]

        if called:
            return AssertionResult(
                passed=True,
                message=f"At least one tool called: {called}",
                category="tools",
                expected=f"any of {tool_names}",
                actual=f"called {called}",
            )

        return AssertionResult(
            passed=False,
            message=f"None of the expected tools were called: {tool_names}",
            category="tools",
            expected=f"any of {tool_names}",
            actual="none called",
        )

    def check_tools_called_min(
        self,
        recorder: EventRecorder,
        min_count: int,
    ) -> AssertionResult:
        """Check that at least N total tool calls were made.

        Args:
            recorder: EventRecorder with captured events.
            min_count: Minimum number of tool calls expected.
        """
        actual_count = len(recorder.tool_calls)

        if actual_count >= min_count:
            return AssertionResult(
                passed=True,
                message=f"Made {actual_count} tool calls (min: {min_count})",
                category="tools",
                expected=f">= {min_count}",
                actual=actual_count,
            )

        return AssertionResult(
            passed=False,
            message=f"Only {actual_count} tool calls made (expected >= {min_count})",
            category="tools",
            expected=f">= {min_count}",
            actual=actual_count,
        )

    # =========================================================================
    # New Observability Assertions
    # =========================================================================

    def check_routing_strategy(
        self,
        recorder: EventRecorder,
        expected: str | tuple[str, ...],
    ) -> AssertionResult:
        """Check that the routing strategy matches expected.

        Args:
            recorder: EventRecorder with captured events.
            expected: Expected strategy or tuple of acceptable strategies.
        """
        actual = recorder.routing_strategy

        if isinstance(expected, str):
            expected_set = {expected.lower()}
        else:
            expected_set = {e.lower() for e in expected}

        actual_lower = (actual or "none").lower()
        passed = actual_lower in expected_set

        return AssertionResult(
            passed=passed,
            message=f"Routing strategy: expected {expected}, got {actual}",
            category="routing",
            expected=expected,
            actual=actual,
        )

    def check_validation_passed(
        self,
        recorder: EventRecorder,
        gate_type: str | None = None,
    ) -> AssertionResult:
        """Check that validation gates passed.

        Args:
            recorder: EventRecorder with captured events.
            gate_type: Optional specific gate type to check.
        """
        passed = recorder.validation_passed(gate_type)

        if passed:
            gate_desc = f" ({gate_type})" if gate_type else ""
            return AssertionResult(
                passed=True,
                message=f"All validation gates{gate_desc} passed",
                category="validation",
                expected="pass",
                actual="passed",
            )

        # Get failed validations for reporting
        all_validations = recorder.all_validations
        failed = [v for v in all_validations if not v.passed]
        if gate_type:
            failed = [v for v in failed if v.gate_type == gate_type]

        failed_info = [(v.gate_id, v.gate_type) for v in failed]

        return AssertionResult(
            passed=False,
            message=f"Validation failed: {failed_info}",
            category="validation",
            expected="pass",
            actual=f"failed: {failed_info}",
        )

    def check_no_reliability_issues(
        self,
        recorder: EventRecorder,
    ) -> AssertionResult:
        """Check that no reliability issues were detected.

        Args:
            recorder: EventRecorder with captured events.
        """
        issues = recorder.all_reliability_issues

        if not issues:
            return AssertionResult(
                passed=True,
                message="No reliability issues detected",
                category="reliability",
                expected="no issues",
                actual="none",
            )

        issue_info = [(r.failure_type, r.confidence) for r in issues]

        return AssertionResult(
            passed=False,
            message=f"Reliability issues detected: {issue_info}",
            category="reliability",
            expected="no issues",
            actual=issue_info,
        )

    def check_token_budget(
        self,
        recorder: EventRecorder,
        max_tokens: int,
    ) -> AssertionResult:
        """Check that token usage is within budget.

        Args:
            recorder: EventRecorder with captured events.
            max_tokens: Maximum token budget.
        """
        actual = recorder.total_tokens

        if actual <= max_tokens:
            return AssertionResult(
                passed=True,
                message=f"Token usage {actual} within budget {max_tokens}",
                category="tokens",
                expected=f"<= {max_tokens}",
                actual=actual,
            )

        return AssertionResult(
            passed=False,
            message=f"Token usage {actual} exceeds budget {max_tokens}",
            category="tokens",
            expected=f"<= {max_tokens}",
            actual=actual,
        )
