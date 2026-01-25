"""RFC-063: Weakness Analyzer, RFC-077: FastClassifier Integration.

Analyzes codebase for weak points using static analysis tools:
- coverage.py for test coverage
- radon for cyclomatic complexity
- ruff for lint errors
- mypy for type errors
- git for staleness detection

RFC-077 adds LLM-based severity prioritization for context-aware ranking.

All tools are optional - graceful degradation if missing.
"""


import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.weakness.types import (
    WeaknessScore,
    WeaknessSignal,
    WeaknessType,
    _freeze_evidence,
)

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.artifacts import ArtifactGraph


@dataclass(slots=True)
class WeaknessAnalyzer:
    """Analyzes codebase for weak points using DAG structure."""

    graph: ArtifactGraph
    project_root: Path

    # Thresholds (configurable)
    coverage_threshold: float = 0.5
    complexity_threshold: int = 10
    staleness_months: int = 6

    # Tool availability cache
    _tool_available: dict[str, bool] = field(default_factory=dict)

    def _check_tool(self, tool: str) -> bool:
        """Check if a tool is available."""
        if tool not in self._tool_available:
            try:
                result = subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    timeout=5,
                )
                self._tool_available[tool] = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self._tool_available[tool] = False
        return self._tool_available[tool]

    async def scan(self) -> list[WeaknessScore]:
        """Scan codebase for weaknesses, returning scored artifacts."""
        # Run analysis tools in parallel (they're I/O bound)
        coverage_map = await self._analyze_coverage()
        complexity_map = await self._analyze_complexity()
        lint_map = await self._analyze_lint()
        staleness_map = await self._analyze_staleness()
        type_errors = await self._analyze_types()

        scores: list[WeaknessScore] = []

        for artifact_id in self.graph:
            artifact = self.graph[artifact_id]

            # Skip artifacts without output files
            if not artifact.produces_file:
                continue

            # Skip non-Python files for now
            file_path = Path(artifact.produces_file)
            if file_path.suffix not in (".py", ".pyi"):
                continue

            signals: list[WeaknessSignal] = []

            # Check coverage
            if artifact_id in coverage_map:
                cov = coverage_map[artifact_id]
                if cov < self.coverage_threshold:
                    signals.append(
                        WeaknessSignal(
                            artifact_id=artifact_id,
                            file_path=file_path,
                            weakness_type=WeaknessType.LOW_COVERAGE,
                            severity=(self.coverage_threshold - cov) / self.coverage_threshold,
                            evidence=_freeze_evidence(
                                {"coverage": cov, "threshold": self.coverage_threshold}
                            ),
                        )
                    )

            # Check complexity
            if artifact_id in complexity_map:
                complexity = complexity_map[artifact_id]
                if complexity > self.complexity_threshold:
                    signals.append(
                        WeaknessSignal(
                            artifact_id=artifact_id,
                            file_path=file_path,
                            weakness_type=WeaknessType.HIGH_COMPLEXITY,
                            severity=min(1.0, (complexity - self.complexity_threshold) / 10),
                            evidence=_freeze_evidence({
                                "complexity": complexity,
                                "threshold": self.complexity_threshold,
                            }),
                        )
                    )

            # Check lint errors
            if artifact_id in lint_map and lint_map[artifact_id] > 0:
                signals.append(
                    WeaknessSignal(
                        artifact_id=artifact_id,
                        file_path=file_path,
                        weakness_type=WeaknessType.LINT_ERRORS,
                        severity=min(1.0, lint_map[artifact_id] / 10),
                        evidence=_freeze_evidence({"error_count": lint_map[artifact_id]}),
                    )
                )

            # Check staleness (requires all three: stale + low coverage + high fan_out)
            if artifact_id in staleness_map:
                months_stale = staleness_map[artifact_id]
                fan_out = self.graph.fan_out(artifact_id)
                coverage = coverage_map.get(artifact_id, 1.0)
                is_stale = months_stale > self.staleness_months
                is_low_coverage = coverage < self.coverage_threshold
                is_high_fanout = fan_out > 3

                if is_stale and is_low_coverage and is_high_fanout:
                    signals.append(
                        WeaknessSignal(
                            artifact_id=artifact_id,
                            file_path=file_path,
                            weakness_type=WeaknessType.STALE_CODE,
                            severity=min(1.0, (months_stale / 12) * (fan_out / 10)),
                            evidence=_freeze_evidence({
                                "months_stale": months_stale,
                                "fan_out": fan_out,
                                "coverage": coverage,
                            }),
                        )
                    )

            # Check type errors
            if artifact_id in type_errors:
                signals.append(
                    WeaknessSignal(
                        artifact_id=artifact_id,
                        file_path=file_path,
                        weakness_type=WeaknessType.MISSING_TYPES,
                        severity=min(1.0, type_errors[artifact_id] / 5),
                        evidence=_freeze_evidence({"type_errors": type_errors[artifact_id]}),
                    )
                )

            if signals:
                scores.append(
                    WeaknessScore(
                        artifact_id=artifact_id,
                        file_path=file_path,
                        signals=tuple(signals),
                        fan_out=self.graph.fan_out(artifact_id),
                        depth=self.graph.depth(artifact_id),
                    )
                )

        # Sort by total severity (highest first)
        return sorted(scores, key=lambda s: s.total_severity, reverse=True)

    async def _analyze_coverage(self) -> dict[str, float]:
        """Get test coverage per file using coverage.py."""
        if not self._check_tool("coverage"):
            return {}

        try:
            result = subprocess.run(
                ["coverage", "json", "-o", "-"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                return {
                    self._file_to_artifact(f): info["summary"]["percent_covered"] / 100
                    for f, info in data.get("files", {}).items()
                }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
            pass
        return {}

    async def _analyze_complexity(self) -> dict[str, int]:
        """Get cyclomatic complexity per file using radon."""
        if not self._check_tool("radon"):
            return {}

        try:
            src_dir = self.project_root / "src"
            if not src_dir.exists():
                src_dir = self.project_root

            result = subprocess.run(
                ["radon", "cc", "-j", str(src_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                complexity_map: dict[str, int] = {}
                for file_path, funcs in data.items():
                    if funcs:
                        max_complexity = max((f["complexity"] for f in funcs), default=0)
                        complexity_map[self._file_to_artifact(file_path)] = max_complexity
                return complexity_map
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
            pass
        return {}

    async def _analyze_lint(self) -> dict[str, int]:
        """Get lint error count per file using ruff."""
        if not self._check_tool("ruff"):
            return {}

        try:
            src_dir = self.project_root / "src"
            if not src_dir.exists():
                src_dir = self.project_root

            result = subprocess.run(
                ["ruff", "check", "--output-format=json", str(src_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # Ruff returns non-zero if there are errors, but still outputs JSON
            if result.stdout:
                data = json.loads(result.stdout)
                error_counts: dict[str, int] = {}
                for error in data:
                    file_path = error.get("filename", "")
                    artifact_id = self._file_to_artifact(file_path)
                    error_counts[artifact_id] = error_counts.get(artifact_id, 0) + 1
                return error_counts
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
            pass
        return {}

    async def _analyze_staleness(self) -> dict[str, int]:
        """Get months since last commit per file using git."""
        try:
            src_dir = self.project_root / "src"
            if not src_dir.exists():
                src_dir = self.project_root

            # Get list of Python files
            result = subprocess.run(
                ["git", "ls-files", "*.py"],
                cwd=src_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {}

            staleness: dict[str, int] = {}
            now = datetime.now(UTC)

            for file_path in result.stdout.strip().split("\n"):
                if not file_path:
                    continue

                # Get last commit date for this file
                log_result = subprocess.run(
                    ["git", "log", "-1", "--format=%ct", "--", file_path],
                    cwd=src_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if log_result.returncode == 0 and log_result.stdout.strip():
                    timestamp = int(log_result.stdout.strip())
                    last_modified = datetime.fromtimestamp(timestamp, tz=UTC)
                    months = (now - last_modified).days // 30
                    staleness[self._file_to_artifact(file_path)] = months

            return staleness
        except (subprocess.TimeoutExpired, ValueError):
            pass
        return {}

    async def _analyze_types(self) -> dict[str, int]:
        """Get type error count per file from mypy."""
        if not self._check_tool("mypy"):
            return {}

        try:
            src_dir = self.project_root / "src"
            if not src_dir.exists():
                src_dir = self.project_root

            result = subprocess.run(
                [
                    "mypy",
                    "--no-error-summary",
                    "--show-error-codes",
                    str(src_dir),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            # Parse mypy output: "path/file.py:10: error: Message [code]"
            error_counts: dict[str, int] = {}
            for line in result.stdout.splitlines():
                if ": error:" in line:
                    file_path = line.split(":")[0]
                    artifact_id = self._file_to_artifact(file_path)
                    error_counts[artifact_id] = error_counts.get(artifact_id, 0) + 1
            return error_counts
        except subprocess.TimeoutExpired:
            pass
        return {}

    def _file_to_artifact(self, file_path: str) -> str:
        """Convert file path to artifact ID."""
        try:
            rel = Path(file_path).relative_to(self.project_root)
            return str(rel)
        except ValueError:
            return file_path


# =============================================================================
# Smart Weakness Analyzer (RFC-077)
# =============================================================================


@dataclass(slots=True)
class SmartWeaknessAnalyzer(WeaknessAnalyzer):
    """Weakness analyzer with LLM-based severity prioritization (RFC-077).

    Uses FastClassifier to provide context-aware severity assessment
    beyond static thresholds.

    Example:
        analyzer = SmartWeaknessAnalyzer(
            graph=artifact_graph,
            project_root=Path("."),
            model=small_model,
        )
        scores = await analyzer.scan_smart()
        # Scores are ranked by LLM-assessed severity, not just metrics
    """

    model: ModelProtocol | None = None
    """Small model for severity assessment (llama3.2:3b recommended)."""

    _classifier: Any = field(default=None, repr=False)

    async def _get_classifier(self) -> Any:
        """Lazy-load FastClassifier."""
        if self._classifier is None and self.model is not None:
            from sunwell.reasoning import FastClassifier

            self._classifier = FastClassifier(model=self.model)
        return self._classifier

    async def scan_smart(self) -> list[WeaknessScore]:
        """Scan with LLM-enhanced severity assessment.

        Strategy:
        1. Run standard scan (static analysis)
        2. For top N weaknesses, get LLM severity assessment
        3. Re-rank based on LLM severity

        Returns:
            List of WeaknessScores ranked by LLM-assessed severity
        """
        # Standard scan first
        scores = await self.scan()

        classifier = await self._get_classifier()
        if classifier is None or not scores:
            return scores  # No model, use static results

        # Assess top 20 weaknesses with LLM (batching would be better)
        top_n = min(20, len(scores))
        assessed_scores: list[tuple[WeaknessScore, str]] = []

        for score in scores[:top_n]:
            try:
                severity = await self._assess_severity(classifier, score)
                assessed_scores.append((score, severity))
            except Exception:
                # LLM failed, use "medium" as default
                assessed_scores.append((score, "medium"))

        # Sort by LLM severity (critical > high > medium > low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        assessed_scores.sort(key=lambda x: (severity_order.get(x[1], 2), -x[0].total_severity))

        # Rebuild list: assessed scores first, then remaining
        result = [s[0] for s in assessed_scores]
        result.extend(scores[top_n:])

        return result

    async def _assess_severity(
        self, classifier: Any, score: WeaknessScore
    ) -> str:
        """Get LLM severity assessment for a weakness."""
        # Build context from weakness signals
        signals_desc = []
        for signal in score.signals[:3]:  # Top 3 signals
            signals_desc.append(
                f"- {signal.weakness_type.value}: severity={signal.severity:.2f}"
            )

        context = f"""File: {score.file_path}
Fan-out (dependencies): {score.fan_out}
Depth in dependency graph: {score.depth}
Total severity score: {score.total_severity:.2f}

Weakness signals:
{chr(10).join(signals_desc)}"""

        return await classifier.severity(
            signal_type="weakness_cluster",
            content=context,
            file_path=str(score.file_path),
        )

    async def prioritize_for_goal(
        self, goal: str, top_n: int = 10
    ) -> list[WeaknessScore]:
        """Prioritize weaknesses based on a specific goal (RFC-077).

        Uses LLM to determine which weaknesses are most relevant to a goal.

        Args:
            goal: The user's goal (e.g., "improve test coverage for auth")
            top_n: Number of weaknesses to return

        Returns:
            Weaknesses most relevant to the goal
        """
        scores = await self.scan()

        classifier = await self._get_classifier()
        if classifier is None:
            return scores[:top_n]

        # Score relevance to goal
        relevant: list[tuple[WeaknessScore, bool]] = []

        for score in scores[:30]:  # Check top 30
            try:
                is_relevant = await classifier.yes_no(
                    f"Is this weakness relevant to the goal: '{goal}'?\n\n"
                    f"File: {score.file_path}\n"
                    f"Weakness types: {', '.join(s.weakness_type.value for s in score.signals)}"
                )
                relevant.append((score, is_relevant))
            except Exception:
                relevant.append((score, False))

        # Sort: relevant first, then by severity
        relevant.sort(key=lambda x: (not x[1], -x[0].total_severity))

        return [s[0] for s in relevant[:top_n]]
