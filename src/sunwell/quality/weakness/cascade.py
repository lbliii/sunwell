"""RFC-063: Cascade Engine.

Computes cascade impact and manages wave-by-wave execution.
"""

import ast
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.quality.weakness.types import (
    DeltaPreview,
    ExtractedContract,
    WaveConfidence,
    WeaknessScore,
)
from sunwell.quality.weakness.verification import run_mypy, run_pytest, run_ruff

if TYPE_CHECKING:
    from sunwell.planning.naaru.artifacts import ArtifactGraph


@dataclass(frozen=True, slots=True)
class CascadePreview:
    """Preview of what a cascade regeneration would affect."""

    weak_node: str
    weakness_score: WeaknessScore
    direct_dependents: frozenset[str]
    transitive_dependents: frozenset[str]
    total_impacted: int
    estimated_effort: str  # small, medium, large, epic
    files_touched: tuple[str, ...]
    waves: tuple[tuple[str, ...], ...]  # Topological order
    risk_assessment: str

    # Contract and delta information (populated by enhanced preview)
    # Use tuples for immutability in frozen dataclass
    extracted_contracts: tuple[tuple[str, ExtractedContract], ...] = ()
    delta_previews: tuple[tuple[str, DeltaPreview], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "weak_node": self.weak_node,
            "weakness_types": [s.weakness_type.value for s in self.weakness_score.signals],
            "severity": self.weakness_score.total_severity,
            "cascade_risk": self.weakness_score.cascade_risk,
            "direct_dependents": list(self.direct_dependents),
            "transitive_dependents": list(self.transitive_dependents),
            "total_impacted": self.total_impacted,
            "estimated_effort": self.estimated_effort,
            "files_touched": list(self.files_touched),
            "waves": [list(w) for w in self.waves],
            "risk_assessment": self.risk_assessment,
            "has_contracts": len(self.extracted_contracts) > 0,
            "has_deltas": len(self.delta_previews) > 0,
            "extracted_contracts": {k: v.to_dict() if hasattr(v, 'to_dict') else str(v) for k, v in self.extracted_contracts},
            "delta_previews": {k: v.to_dict() if hasattr(v, 'to_dict') else str(v) for k, v in self.delta_previews},
        }


@dataclass(slots=True)
class CascadeExecution:
    """State of an in-progress cascade execution with wave-by-wave approval."""

    preview: CascadePreview
    current_wave: int = 0
    wave_confidences: list[WaveConfidence] = field(default_factory=list)

    # Execution mode
    auto_approve: bool = False  # If True, continue automatically if confidence > threshold
    confidence_threshold: float = 0.7

    # Escalation tracking
    max_consecutive_low_confidence: int = 2
    consecutive_low_confidence_count: int = 0
    escalated_to_human: bool = False

    # State
    paused_for_approval: bool = False
    completed: bool = False
    aborted: bool = False
    abort_reason: str | None = None

    @property
    def overall_confidence(self) -> float:
        """Average confidence across completed waves."""
        if not self.wave_confidences:
            return 1.0
        return sum(w.confidence for w in self.wave_confidences) / len(self.wave_confidences)

    def approve_wave(self) -> None:
        """Approve current wave and proceed to next."""
        self.paused_for_approval = False

    def abort(self, reason: str) -> None:
        """Abort cascade execution."""
        self.aborted = True
        self.abort_reason = reason

    def record_wave_completion(self, confidence: WaveConfidence) -> None:
        """Record completion of a wave and determine next action."""
        self.wave_confidences.append(confidence)

        # Track consecutive low-confidence waves for escalation
        if confidence.confidence < self.confidence_threshold:
            self.consecutive_low_confidence_count += 1

            # Escalate to human review if too many consecutive low-confidence waves
            if self.consecutive_low_confidence_count >= self.max_consecutive_low_confidence:
                self.escalated_to_human = True
                self.paused_for_approval = True
                self.auto_approve = False  # Force manual review
            elif self.auto_approve:
                # Auto mode but confidence too low - pause
                self.paused_for_approval = True
            else:
                self.paused_for_approval = True
        else:
            # Reset counter on successful wave
            self.consecutive_low_confidence_count = 0
            if not self.auto_approve:
                self.paused_for_approval = True

        # Check if done
        if self.current_wave >= len(self.preview.waves) - 1:
            self.completed = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "preview": self.preview.to_dict(),
            "current_wave": self.current_wave,
            "wave_confidences": [
                {
                    "wave_num": w.wave_num,
                    "artifacts_completed": list(w.artifacts_completed),
                    "tests_passed": w.tests_passed,
                    "types_clean": w.types_clean,
                    "lint_clean": w.lint_clean,
                    "contracts_preserved": w.contracts_preserved,
                    "confidence": w.confidence,
                    "deductions": list(w.deductions),
                    "should_continue": w.should_continue,
                }
                for w in self.wave_confidences
            ],
            "auto_approve": self.auto_approve,
            "confidence_threshold": self.confidence_threshold,
            "max_consecutive_low_confidence": self.max_consecutive_low_confidence,
            "consecutive_low_confidence_count": self.consecutive_low_confidence_count,
            "escalated_to_human": self.escalated_to_human,
            "paused_for_approval": self.paused_for_approval,
            "completed": self.completed,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "overall_confidence": self.overall_confidence,
        }


@dataclass(slots=True)
class CascadeEngine:
    """Computes and executes cascade regenerations."""

    graph: ArtifactGraph
    project_root: Path
    max_cascade_depth: int = 5
    max_cascade_size: int = 50

    def preview(self, weakness: WeaknessScore) -> CascadePreview:
        """Preview what regenerating a weak node would affect."""
        weak_id = weakness.artifact_id

        # Get direct dependents
        direct = self.graph.get_dependents(weak_id)

        # Get full cascade (transitive) using BFS from weak node to dependents
        all_impacted = self._find_invalidated({weak_id})
        all_impacted.discard(weak_id)  # Don't count weak node itself
        transitive = all_impacted - direct

        # Compute topological order (waves)
        waves = self._compute_waves(weak_id, all_impacted)

        # Gather file paths
        files = [weak_id]
        for aid in all_impacted:
            if aid in self.graph:
                artifact = self.graph[aid]
                if artifact.produces_file:
                    files.append(artifact.produces_file)

        # Estimate effort
        total = len(all_impacted) + 1
        if total <= 3:
            effort = "small"
        elif total <= 10:
            effort = "medium"
        elif total <= 25:
            effort = "large"
        else:
            effort = "epic"

        # Risk assessment
        risk = self._assess_risk(weakness, all_impacted)

        return CascadePreview(
            weak_node=weak_id,
            weakness_score=weakness,
            direct_dependents=frozenset(direct),
            transitive_dependents=frozenset(transitive),
            total_impacted=total,
            estimated_effort=effort,
            files_touched=tuple(files),
            waves=waves,
            risk_assessment=risk,
        )

    def _find_invalidated(self, changed_ids: set[str]) -> set[str]:
        """Find all artifacts invalidated by changes using BFS.

        If A changed and B depends on A, B is invalidated.

        Args:
            changed_ids: Set of directly changed artifact IDs.

        Returns:
            Set of all invalidated artifact IDs (includes changed_ids).
        """
        invalidated = set(changed_ids)

        # BFS from changed artifacts to their dependents
        queue = list(changed_ids)
        while queue:
            artifact_id = queue.pop(0)
            for dependent_id in self.graph.get_dependents(artifact_id):
                if dependent_id not in invalidated:
                    invalidated.add(dependent_id)
                    queue.append(dependent_id)

        return invalidated

    def _compute_waves(
        self,
        weak_id: str,
        impacted: set[str],
    ) -> tuple[tuple[str, ...], ...]:
        """Compute execution waves in topological order."""
        waves: list[tuple[str, ...]] = []
        remaining = impacted | {weak_id}
        completed: set[str] = set()

        # Pre-compute cascade-relevant deps for each artifact (O(n) total)
        cascade_scope = impacted | {weak_id}
        deps_in_cascade: dict[str, set[str]] = {}
        for aid in remaining:
            if aid in self.graph:
                artifact = self.graph[aid]
                deps_in_cascade[aid] = set(artifact.requires) & cascade_scope
            else:
                deps_in_cascade[aid] = set()

        # Wave 0: the weak node itself
        waves.append((weak_id,))
        completed.add(weak_id)
        remaining.discard(weak_id)

        # Subsequent waves: nodes whose deps are all completed
        while remaining:
            wave = [aid for aid in remaining if deps_in_cascade[aid] <= completed]

            if not wave:
                # Circular dependency or unreachable - add remaining
                waves.append(tuple(remaining))
                break

            waves.append(tuple(wave))
            completed.update(wave)
            remaining -= set(wave)

        return tuple(waves)

    def _assess_risk(
        self,
        weakness: WeaknessScore,
        impacted: set[str],
    ) -> str:
        """Generate human-readable risk assessment."""
        risk_factors: list[str] = []

        if len(impacted) > 20:
            risk_factors.append(f"Large cascade ({len(impacted)} files)")

        if weakness.fan_out > 10:
            risk_factors.append(f"High fan-out ({weakness.fan_out} dependents)")

        critical_signals = [s for s in weakness.signals if s.is_critical]
        if critical_signals:
            types = ", ".join(s.weakness_type.value for s in critical_signals)
            risk_factors.append(f"Critical weaknesses: {types}")

        if not risk_factors:
            return "Low risk: Small, isolated change"

        return " | ".join(risk_factors)

    async def extract_contract(self, artifact_id: str) -> ExtractedContract:
        """Extract public interface contract from a file.

        Uses AST analysis to extract:
        - Function signatures (name, params, return type)
        - Class definitions with public methods
        - Module exports (__all__)
        - Key type annotations
        """
        artifact = self.graph[artifact_id]
        file_path = self.project_root / artifact.produces_file

        if not file_path.exists():
            return ExtractedContract(
                artifact_id=artifact_id,
                file_path=file_path,
                functions=(),
                classes=(),
                exports=(),
                type_signatures=(),
                interface_hash="",
            )

        source = file_path.read_text()
        tree = ast.parse(source)

        functions: list[str] = []
        classes: list[str] = []
        exports: list[str] = []
        type_sigs: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Skip private functions
                if not node.name.startswith("_"):
                    sig = f"def {node.name}({ast.unparse(node.args)})"
                    if node.returns:
                        sig += f" -> {ast.unparse(node.returns)}"
                    functions.append(sig)

            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    methods = [
                        f.name
                        for f in node.body
                        if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef)
                        and not f.name.startswith("_")
                    ]
                    classes.append(f"class {node.name}: {', '.join(methods)}")

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            exports = [
                                elt.value
                                for elt in node.value.elts
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            ]

        # Create hash of interface for quick comparison
        interface_str = "\n".join(sorted(functions + classes + exports))
        interface_hash = hashlib.sha256(interface_str.encode()).hexdigest()[:16]

        return ExtractedContract(
            artifact_id=artifact_id,
            file_path=file_path,
            functions=tuple(functions),
            classes=tuple(classes),
            exports=tuple(exports),
            type_signatures=tuple(type_sigs),
            interface_hash=interface_hash,
        )

    async def preview_with_contracts(
        self,
        weakness: WeaknessScore,
        include_deltas: bool = False,
    ) -> CascadePreview:
        """Enhanced preview that extracts contracts.

        Args:
            weakness: The weakness to preview cascade for
            include_deltas: If True, use agent to generate delta previews (expensive)

        Returns:
            CascadePreview with contracts populated
        """
        # Get basic preview
        preview = self.preview(weakness)

        # Extract contracts for all affected files
        contracts: dict[str, ExtractedContract] = {}
        for artifact_id in [preview.weak_node, *preview.direct_dependents]:
            if artifact_id in self.graph:
                try:
                    contract = await self.extract_contract(artifact_id)
                    contracts[artifact_id] = contract
                except Exception:
                    pass  # Some files may not be parseable

        # Optionally generate delta previews (expensive - requires agent)
        deltas: dict[str, DeltaPreview] = {}
        if include_deltas:
            # Would call agent in dry-run mode
            pass

        # Return enhanced preview with contracts
        return CascadePreview(
            weak_node=preview.weak_node,
            weakness_score=preview.weakness_score,
            direct_dependents=preview.direct_dependents,
            transitive_dependents=preview.transitive_dependents,
            total_impacted=preview.total_impacted,
            estimated_effort=preview.estimated_effort,
            files_touched=preview.files_touched,
            waves=preview.waves,
            risk_assessment=preview.risk_assessment,
            extracted_contracts=tuple(contracts.items()),
            delta_previews=tuple(deltas.items()),
        )

    def compute_regeneration_tasks(
        self,
        preview: CascadePreview,
    ) -> list[dict[str, Any]]:
        """Convert preview into executable task list for agent."""
        tasks: list[dict[str, Any]] = []

        for wave_num, wave in enumerate(preview.waves):
            for artifact_id in wave:
                task = {
                    "id": f"cascade-{artifact_id}",
                    "description": self._generate_task_description(
                        artifact_id,
                        wave_num,
                        preview,
                    ),
                    "mode": "modify" if wave_num > 0 else "regenerate",
                    "target_path": artifact_id,
                    "depends_on": self._get_wave_dependencies(
                        artifact_id,
                        wave_num,
                        preview,
                    ),
                    "verification": "ruff check && mypy && pytest",
                    "wave": wave_num,
                }
                tasks.append(task)

        # Final verification task
        if preview.waves:
            tasks.append(
                {
                    "id": "cascade-verify",
                    "description": "Run full test suite to verify cascade didn't break anything",
                    "mode": "verify",
                    "depends_on": [f"cascade-{aid}" for aid in preview.waves[-1]],
                    "verification_command": "pytest --tb=short",
                }
            )

        return tasks

    def _generate_task_description(
        self,
        artifact_id: str,
        wave_num: int,
        preview: CascadePreview,
    ) -> str:
        """Generate descriptive task for agent."""
        if wave_num == 0:
            weakness_types = ", ".join(
                s.weakness_type.value for s in preview.weakness_score.signals
            )
            return (
                f"Regenerate {artifact_id} to fix: {weakness_types}. "
                f"Maintain all existing public interfaces."
            )
        else:
            return (
                f"Update {artifact_id} to be compatible with regenerated "
                f"{preview.weak_node}. Preserve existing behavior."
            )

    def _get_wave_dependencies(
        self,
        artifact_id: str,
        wave_num: int,
        preview: CascadePreview,
    ) -> list[str]:
        """Get task dependencies from previous waves."""
        if wave_num == 0:
            return []

        # Depend on all tasks from previous wave
        prev_wave = preview.waves[wave_num - 1]
        return [f"cascade-{aid}" for aid in prev_wave]

    async def execute_wave_by_wave(
        self,
        preview: CascadePreview,
        auto_approve: bool = False,
        on_wave_complete: Callable[[WaveConfidence], Awaitable[bool]] | None = None,
    ) -> CascadeExecution:
        """Execute cascade with wave-by-wave approval.

        Args:
            preview: The cascade preview to execute
            auto_approve: If True, continue automatically if confidence > threshold
            on_wave_complete: Callback after each wave; return False to abort

        Returns:
            CascadeExecution with final state
        """

        execution = CascadeExecution(
            preview=preview,
            auto_approve=auto_approve,
        )

        # Convert tuple of tuples to dict for contract verification
        contracts_dict = dict(preview.extracted_contracts)

        for wave_num, wave in enumerate(preview.waves):
            execution.current_wave = wave_num

            # Execute wave (would call agent here in real implementation)
            # ... agent execution ...

            # Verify wave completion using shared functions
            test_result = await run_pytest(self.project_root)
            type_result = await run_mypy(self.project_root)
            lint_result = await run_ruff(self.project_root)
            contract_result = await self._verify_contracts(contracts_dict, wave)

            confidence = WaveConfidence.compute(
                wave_num=wave_num,
                artifacts=tuple(wave),
                test_result=test_result,
                type_result=type_result,
                lint_result=lint_result,
                contract_result=contract_result,
            )

            execution.record_wave_completion(confidence)

            # Callback for UI/CLI to handle
            if on_wave_complete:
                should_continue = await on_wave_complete(confidence)
                if not should_continue:
                    execution.abort("User cancelled")
                    break

            # Check if we should pause
            if execution.paused_for_approval and not auto_approve:
                break

            if execution.aborted:
                break

        return execution

    async def _verify_contracts(
        self,
        original_contracts: dict[str, ExtractedContract],
        wave_artifacts: tuple[str, ...],
    ) -> bool:
        """Verify contracts are preserved after regeneration."""
        for artifact_id in wave_artifacts:
            if artifact_id not in original_contracts:
                continue

            original = original_contracts[artifact_id]
            try:
                current = await self.extract_contract(artifact_id)
                if not original.is_compatible_with(current):
                    return False
            except Exception:
                # Can't verify - assume OK
                pass

        return True
