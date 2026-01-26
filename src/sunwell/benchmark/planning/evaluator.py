"""Planning Quality Evaluation Framework.

Measures how well Sunwell (or any planner) creates execution plans.

Key insight: Planning quality is a leading indicator of execution quality.
Good plans → easier execution → fewer wasted tokens → better outcomes.

Metrics:
- Coverage: Did the plan include all required artifacts?
- Coherence: Are dependencies logically ordered?
- Tech Alignment: Did it pick up the right tech stack?
- Granularity: Right level of task decomposition?
- Speed: How fast was planning?

Usage:
    evaluator = PlanningEvaluator.from_task("benchmark/tasks/planning/rfc043-phase1.yaml")
    result = evaluator.evaluate("benchmark/results/rfc043-phase1-plan.json")
    print(result.report())
"""


import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sunwell.foundation.utils import safe_yaml_load


@dataclass(frozen=True, slots=True)
class ArtifactMatch:
    """Match between expected and actual artifact."""

    expected_id: str
    actual_id: str | None
    confidence: float  # 0-1
    matched_files: tuple[str, ...] = ()
    reasoning: str = ""


@dataclass(frozen=True, slots=True)
class PlanningEvaluationResult:
    """Complete evaluation result for a plan.
    
    Note: Named PlanningEvaluationResult to distinguish from
    benchmark.types.EvaluationResult which is for judge evaluations.
    """

    task_id: str
    plan_file: str

    # Scores (0-100 each)
    coverage_score: float
    coherence_score: float
    tech_alignment_score: float
    granularity_score: float
    speed_score: float

    # Weighted total
    total_score: float

    # Details (immutable mappings)
    coverage_details: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    coherence_details: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    tech_details: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    # Timing
    planning_time_ms: float | None = None
    eval_time_ms: float = 0

    def report(self) -> str:
        """Generate human-readable report."""
        lines = [
            f"# Planning Evaluation: {self.task_id}",
            f"Plan: {self.plan_file}",
            "",
            "## Scores",
            f"  Coverage:       {self.coverage_score:5.1f}/100 (weight: 40%)",
            f"  Coherence:      {self.coherence_score:5.1f}/100 (weight: 25%)",
            f"  Tech Alignment: {self.tech_alignment_score:5.1f}/100 (weight: 20%)",
            f"  Granularity:    {self.granularity_score:5.1f}/100 (weight: 10%)",
            f"  Speed:          {self.speed_score:5.1f}/100 (weight: 5%)",
            "",
            f"  **TOTAL: {self.total_score:.1f}/100**",
            "",
        ]

        # Coverage details
        if self.coverage_details:
            lines.append("## Coverage Details")
            matched = self.coverage_details.get("matched", [])
            missing = self.coverage_details.get("missing", [])
            extra = self.coverage_details.get("extra", [])

            lines.append(f"  Matched: {len(matched)}/{len(matched) + len(missing)}")
            if matched:
                for m in matched:
                    lines.append(f"    ✓ {m['expected']} → {m['actual']}")
            if missing:
                lines.append(f"  Missing ({len(missing)}):")
                for m in missing:
                    lines.append(f"    ✗ {m}")
            if extra:
                lines.append(f"  Extra artifacts ({len(extra)}): {', '.join(extra)}")
            lines.append("")

        # Tech details
        if self.tech_details:
            lines.append("## Tech Alignment")
            correct = self.tech_details.get("correct_tech", [])
            wrong = self.tech_details.get("wrong_tech", [])
            if correct:
                lines.append(f"  ✓ Correct: {', '.join(correct)}")
            if wrong:
                lines.append(f"  ✗ Wrong: {', '.join(wrong)}")
            lines.append("")

        # Timing
        if self.planning_time_ms:
            lines.append(f"Planning time: {self.planning_time_ms:.0f}ms")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "plan_file": self.plan_file,
            "scores": {
                "coverage": self.coverage_score,
                "coherence": self.coherence_score,
                "tech_alignment": self.tech_alignment_score,
                "granularity": self.granularity_score,
                "speed": self.speed_score,
                "total": self.total_score,
            },
            "details": {
                "coverage": dict(self.coverage_details),
                "coherence": dict(self.coherence_details),
                "tech": dict(self.tech_details),
            },
            "timing": {
                "planning_ms": self.planning_time_ms,
                "eval_ms": self.eval_time_ms,
            },
        }


@dataclass(slots=True)
class PlanningEvaluator:
    """Evaluates plan quality against a benchmark task."""

    task: dict[str, Any]
    """The benchmark task specification."""

    # Weights from task or defaults
    weights: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_task(cls, task_path: str | Path) -> PlanningEvaluator:
        """Load evaluator from task YAML file."""
        path = Path(task_path)
        task = safe_yaml_load(path)

        # Extract weights
        grading = task.get("grading", {})
        weights = {
            "coverage": grading.get("coverage", {}).get("weight", 40) / 100,
            "coherence": grading.get("coherence", {}).get("weight", 25) / 100,
            "tech_alignment": grading.get("tech_alignment", {}).get("weight", 20) / 100,
            "granularity": grading.get("granularity", {}).get("weight", 10) / 100,
            "speed": grading.get("speed", {}).get("weight", 5) / 100,
        }

        return cls(task=task, weights=weights)

    def evaluate(self, plan_path: str | Path) -> PlanningEvaluationResult:
        """Evaluate a plan against the task specification."""
        start = time.perf_counter()

        path = Path(plan_path)
        with open(path) as f:
            plan = json.load(f)

        # Run each evaluation
        coverage_score, coverage_details = self._eval_coverage(plan)
        coherence_score, coherence_details = self._eval_coherence(plan)
        tech_score, tech_details = self._eval_tech_alignment(plan)
        granularity_score, _ = self._eval_granularity(plan)
        speed_score, _ = self._eval_speed(plan)

        # Weighted total
        total = (
            coverage_score * self.weights["coverage"]
            + coherence_score * self.weights["coherence"]
            + tech_score * self.weights["tech_alignment"]
            + granularity_score * self.weights["granularity"]
            + speed_score * self.weights["speed"]
        )

        eval_time = (time.perf_counter() - start) * 1000

        # Validate task has required 'id' field
        task_id = self.task.get("id")
        if task_id is None:
            raise ValueError("Task YAML must contain 'id' field")

        return PlanningEvaluationResult(
            task_id=task_id,
            plan_file=str(path),
            coverage_score=coverage_score,
            coherence_score=coherence_score,
            tech_alignment_score=tech_score,
            granularity_score=granularity_score,
            speed_score=speed_score,
            total_score=total,
            coverage_details=MappingProxyType(coverage_details),
            coherence_details=MappingProxyType(coherence_details),
            tech_details=MappingProxyType(tech_details),
            eval_time_ms=eval_time,
        )

    def _eval_coverage(self, plan: dict) -> tuple[float, dict]:
        """Evaluate artifact coverage (0-100)."""
        expected = self.task.get("expected_artifacts", {})
        required = expected.get("required", [])

        if not required:
            return 100.0, {}

        plan_artifacts = plan.get("artifacts", [])
        plan_files: set[str] = set()
        for a in plan_artifacts:
            if a.get("produces_file"):
                plan_files.add(a["produces_file"].lower())

        matched = []
        missing = []

        for req in required:
            req_id = req["id"]
            req_desc = req.get("description", "").lower()
            req_files = [f.lower() for f in req.get("files", [])]

            # Try to match by ID similarity
            best_match = None
            best_score = 0

            for pa in plan_artifacts:
                pa_id = pa.get("id")
                if not pa_id:
                    continue  # Skip artifacts without ID
                pa_id_lower = pa_id.lower()
                pa_desc = pa.get("description", "").lower()
                pa_file = (pa.get("produces_file") or "").lower()

                score = 0

                # ID similarity
                if req_id.lower() in pa_id_lower or pa_id_lower in req_id.lower():
                    score += 0.4

                # Description keyword overlap
                req_words = set(req_desc.split())
                pa_words = set(pa_desc.split())
                overlap = len(req_words & pa_words) / max(len(req_words), 1)
                score += overlap * 0.3

                # File match
                for rf in req_files:
                    if rf in pa_file or pa_file in rf:
                        score += 0.3
                        break

                if score > best_score:
                    best_score = score
                    best_match = pa_id

            if best_score >= 0.3:  # Threshold for match
                matched.append({"expected": req_id, "actual": best_match, "score": best_score})
            else:
                missing.append(req_id)

        # Extra artifacts (not necessarily bad)
        expected_ids = {r.get("id", "").lower() for r in required}
        extra = [
            a.get("id", "<unknown>")
            for a in plan_artifacts
            if a.get("id", "").lower() not in expected_ids
        ]

        coverage = len(matched) / len(required) * 100

        return coverage, {
            "matched": matched,
            "missing": missing,
            "extra": extra,
            "required_count": len(required),
            "matched_count": len(matched),
        }

    def _eval_coherence(self, plan: dict) -> tuple[float, dict]:
        """Evaluate dependency coherence (0-100)."""
        artifacts = plan.get("artifacts", [])
        waves = plan.get("waves", [])

        if not artifacts or not waves:
            return 50.0, {"error": "No artifacts or waves"}

        # Check: artifacts in earlier waves shouldn't depend on later waves
        artifact_waves: dict[str, int] = {}
        for a in artifacts:
            a_id = a.get("id")
            if a_id:
                artifact_waves[a_id] = a.get("wave", 0)

        violations = []
        for a in artifacts:
            a_id = a.get("id", "<unknown>")
            a_wave = a.get("wave", 0)
            for req in a.get("requires", []):
                req_wave = artifact_waves.get(req, 0)
                if req_wave > a_wave:
                    violations.append(f"{a_id} (wave {a_wave}) requires {req} (wave {req_wave})")

        if violations:
            score = max(0, 100 - len(violations) * 25)
            return score, {"violations": violations}

        # Check: no orphan dependencies (requiring non-existent artifacts)
        all_ids = {a.get("id") for a in artifacts if a.get("id")}
        orphans = []
        for a in artifacts:
            a_id = a.get("id", "<unknown>")
            for req in a.get("requires", []):
                if req not in all_ids:
                    orphans.append(f"{a_id} requires missing {req}")

        if orphans:
            score = max(0, 100 - len(orphans) * 20)
            return score, {"orphan_dependencies": orphans}

        return 100.0, {"valid": True}

    def _eval_tech_alignment(self, plan: dict) -> tuple[float, dict]:
        """Evaluate tech stack alignment (0-100)."""
        goal = self.task.get("goal", "").lower()
        artifacts = plan.get("artifacts", [])

        # Extract expected tech from goal
        expected_tech = []
        tech_keywords = {
            "tauri": ["tauri", "rust", ".rs", "cargo"],
            "svelte": ["svelte", ".svelte"],
            "react": ["react", ".jsx", ".tsx"],
            "flask": ["flask", "flask.py", "from flask"],
            "fastapi": ["fastapi", "uvicorn"],
        }

        for tech, keywords in tech_keywords.items():
            if any(kw in goal for kw in keywords):
                expected_tech.append(tech)

        if not expected_tech:
            return 100.0, {"note": "No specific tech required"}

        # Check what tech the plan uses
        plan_text = json.dumps(artifacts).lower()
        found_tech = []
        wrong_tech = []

        for tech, keywords in tech_keywords.items():
            if any(kw in plan_text for kw in keywords):
                if tech in expected_tech:
                    found_tech.append(tech)
                elif tech not in expected_tech and expected_tech:
                    # Check if it's a conflicting tech
                    conflicts = {
                        "flask": ["tauri", "svelte", "react"],
                        "fastapi": ["tauri", "svelte", "react"],
                        "react": ["svelte"],
                        "svelte": ["react"],
                    }
                    if tech in conflicts and any(e in conflicts[tech] for e in expected_tech):
                        wrong_tech.append(tech)

        # Score (expected_tech is guaranteed non-empty here due to early return above)
        correct_ratio = len(found_tech) / len(expected_tech)
        penalty = len(wrong_tech) * 25
        score = max(0, correct_ratio * 100 - penalty)

        return score, {
            "expected_tech": expected_tech,
            "correct_tech": found_tech,
            "wrong_tech": wrong_tech,
        }

    def _eval_granularity(self, plan: dict) -> tuple[float, dict]:
        """Evaluate task decomposition granularity (0-100).
        
        Scoring uses smooth transitions to avoid cliff effects:
        - Sweet spot: 5-15 artifacts → 100
        - Acceptable: 3-4 or 16-20 artifacts → 70-90 (linear ramp)
        - Edge cases: <3 or >25 → 40-60
        """
        artifacts = plan.get("artifacts", [])
        waves = plan.get("waves", [])

        if not artifacts:
            return 0.0, {}

        n_artifacts = len(artifacts)
        n_waves = len(waves)

        # Smooth scoring with linear ramps instead of cliffs
        if 5 <= n_artifacts <= 15:
            # Sweet spot
            score = 100.0
        elif n_artifacts < 3:
            # Too coarse
            score = 40.0
        elif n_artifacts < 5:
            # Ramp from 70 (at 3) to 100 (at 5)
            score = 70.0 + (n_artifacts - 3) * 15.0  # 70 → 85 → 100
        elif n_artifacts <= 20:
            # Ramp from 100 (at 15) to 70 (at 20)
            score = 100.0 - (n_artifacts - 15) * 6.0  # 100 → 94 → 88 → 82 → 76 → 70
        elif n_artifacts <= 25:
            # Ramp from 70 (at 20) to 60 (at 25)
            score = 70.0 - (n_artifacts - 20) * 2.0
        else:
            # Too fine
            score = 60.0

        # Parallelization bonus: more waves with good width = better
        if n_waves > 0:
            avg_width = n_artifacts / n_waves
            if 2 <= avg_width <= 4:
                score = min(100.0, score + 10.0)

        return score, {"artifacts": n_artifacts, "waves": n_waves}

    def _eval_speed(self, plan: dict) -> tuple[float, dict]:
        """Evaluate planning speed (0-100)."""
        # We don't have timing in the plan file currently
        # This would need to be added during planning
        stats = plan.get("statistics", {})

        # Estimate based on artifact count (rough proxy)
        n_artifacts = stats.get("total_artifacts", len(plan.get("artifacts", [])))

        # Assume ~3s per artifact for planning
        estimated_time = n_artifacts * 3

        if estimated_time < 15:
            return 100.0, {"estimated_seconds": estimated_time}
        elif estimated_time < 30:
            return 80.0, {"estimated_seconds": estimated_time}
        elif estimated_time < 60:
            return 60.0, {"estimated_seconds": estimated_time}
        else:
            return 40.0, {"estimated_seconds": estimated_time}


# =============================================================================
# CLI Integration
# =============================================================================


def evaluate_plan(task_path: str, plan_path: str) -> PlanningEvaluationResult:
    """Convenience function for CLI."""
    evaluator = PlanningEvaluator.from_task(task_path)
    return evaluator.evaluate(plan_path)
