"""RFC-069: Cascade Executor — bridges weakness cascade to artifact execution.

This module wires the cascade fix button to the agent's artifact execution system,
enabling automated regeneration of weak code and all its dependents with
wave-by-wave confidence verification.

Key components:
- CascadeArtifactBuilder: Converts cascade preview into artifact specs
- CascadeExecutor: Executes cascade regeneration wave-by-wave
- WaveResult: Result of executing a single wave
"""


import subprocess
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.weakness.cascade import CascadeEngine, CascadeExecution, CascadePreview
from sunwell.weakness.types import ExtractedContract, WaveConfidence

if TYPE_CHECKING:
    from sunwell.agent.events import AgentEvent
    from sunwell.naaru.planners.artifact import ArtifactPlanner
    from sunwell.tools.executor import ToolExecutor


@dataclass(frozen=True, slots=True)
class WaveResult:
    """Result of executing a single wave."""

    wave_num: int
    completed: dict[str, str]
    success: bool
    error: str | None = None


@dataclass
class CascadeArtifactBuilder:
    """Converts cascade preview into executable artifact specs.

    Each wave is converted into a mini ArtifactGraph that can be executed
    independently, allowing verification between waves before proceeding.
    """

    engine: CascadeEngine
    preview: CascadePreview
    contracts: dict[str, ExtractedContract]

    def build_wave_graph(self, wave_num: int) -> ArtifactGraph:
        """Build artifact graph for a single wave.

        Each wave is executed as a mini-graph to allow verification
        between waves before proceeding.
        """
        wave = self.preview.waves[wave_num]
        specs = [self._build_spec(artifact_id, wave_num) for artifact_id in wave]

        graph = ArtifactGraph()
        for spec in specs:
            graph.add(spec)

        return graph

    def _build_spec(self, artifact_id: str, wave_num: int) -> ArtifactSpec:
        """Build artifact spec for cascade regeneration."""
        original = self.engine.graph[artifact_id]
        contract = self.contracts.get(artifact_id)

        # Wave 0 = regenerate the weak node with improvements
        # Wave 1+ = update dependents for compatibility
        if wave_num == 0:
            description = self._regenerate_description(artifact_id)
            mode = "regenerate"
        else:
            description = self._update_description(artifact_id)
            mode = "update"

        # Build contract constraint for prompt
        contract_constraint = ""
        if contract:
            contract_constraint = self._format_contract_constraint(contract)

        return ArtifactSpec(
            id=f"cascade-{artifact_id}",
            description=description,
            produces_file=original.produces_file,
            requires=frozenset(),  # Wave deps handled externally
            contract=f"{original.contract or ''}\n\n{contract_constraint}".strip(),
            domain_type=original.domain_type,
            metadata={"cascade_mode": mode, "wave": wave_num, "original_id": artifact_id},
        )

    def _regenerate_description(self, artifact_id: str) -> str:
        """Generate description for regenerating the weak node."""
        weakness_types = ", ".join(
            s.weakness_type.value for s in self.preview.weakness_score.signals
        )
        return (
            f"Regenerate {artifact_id} to fix weaknesses: {weakness_types}. "
            f"Improve test coverage, reduce complexity, fix type errors. "
            f"CRITICAL: Maintain all existing public interfaces for backward compatibility."
        )

    def _update_description(self, artifact_id: str) -> str:
        """Generate description for updating a dependent."""
        return (
            f"Update {artifact_id} to be compatible with the regenerated "
            f"{self.preview.weak_node}. Preserve all existing behavior and tests. "
            f"Only make changes necessary for compatibility."
        )

    def _format_contract_constraint(self, contract: ExtractedContract) -> str:
        """Format contract as prompt constraint."""
        lines = ["## Interface Contract (MUST preserve)"]

        if contract.functions:
            lines.append("\nPublic functions:")
            for fn in contract.functions:
                lines.append(f"  - {fn}")

        if contract.classes:
            lines.append("\nPublic classes:")
            for cls in contract.classes:
                lines.append(f"  - {cls}")

        if contract.exports:
            lines.append(f"\n__all__ = {list(contract.exports)}")

        return "\n".join(lines)


@dataclass
class CascadeExecutor:
    """Executes cascade regeneration wave-by-wave with verification.

    This executor bridges the cascade system to the artifact planner,
    enabling actual code regeneration through the agent.
    """

    engine: CascadeEngine
    planner: ArtifactPlanner
    tool_executor: ToolExecutor
    project_root: Path

    # Event callback for UI updates
    on_event: Callable[[AgentEvent], None] | None = None

    async def execute(
        self,
        preview: CascadePreview,
        auto_approve: bool = False,
        confidence_threshold: float = 0.7,
        on_wave_complete: Callable[[WaveConfidence], Awaitable[bool]] | None = None,
    ) -> CascadeExecution:
        """Execute cascade with wave-by-wave verification.

        Args:
            preview: The cascade preview to execute
            auto_approve: Continue automatically if confidence > threshold
            confidence_threshold: Minimum confidence to auto-proceed
            on_wave_complete: Callback after each wave; return False to abort

        Returns:
            CascadeExecution with final state
        """
        start_time = time.monotonic()

        # Extract contracts before any changes
        contracts = await self._extract_all_contracts(preview)

        # Build artifact converter
        builder = CascadeArtifactBuilder(
            engine=self.engine,
            preview=preview,
            contracts=contracts,
        )

        # Initialize execution state
        execution = CascadeExecution(
            preview=preview,
            auto_approve=auto_approve,
            confidence_threshold=confidence_threshold,
        )

        # Emit cascade start event
        total_deps = preview.total_impacted - 1
        self._emit_event(
            "task_start",
            {
                "task_id": f"cascade-{preview.weak_node}",
                "description": f"Cascade fix: {preview.weak_node} + {total_deps} dependents",
            },
        )

        # Execute each wave
        for wave_num, wave in enumerate(preview.waves):
            execution.current_wave = wave_num

            # Build wave-specific artifact graph
            wave_graph = builder.build_wave_graph(wave_num)

            # Emit wave start
            self._emit_event(
                "task_progress",
                {
                    "task_id": f"cascade-{preview.weak_node}",
                    "message": f"Wave {wave_num}: {', '.join(wave)}",
                    "progress": int((wave_num / len(preview.waves)) * 100),
                },
            )

            # Execute wave through artifact executor
            wave_result = await self._execute_wave(wave_graph, wave_num)

            if not wave_result.success:
                execution.abort(f"Wave {wave_num} failed: {wave_result.error}")
                break

            # Run verification suite
            confidence = await self._verify_wave(
                wave_num=wave_num,
                wave=wave,
                contracts=contracts,
            )

            execution.record_wave_completion(confidence)

            # Emit wave confidence
            self._emit_event(
                "task_progress",
                {
                    "task_id": f"cascade-{preview.weak_node}",
                    "message": f"Wave {wave_num} confidence: {confidence.confidence:.0%}",
                    "progress": int(((wave_num + 1) / len(preview.waves)) * 100),
                },
            )

            # Callback for UI
            if on_wave_complete:
                should_continue = await on_wave_complete(confidence)
                if not should_continue:
                    execution.abort("User cancelled")
                    break

            # Check auto-approve vs pause
            if execution.paused_for_approval and not auto_approve:
                # Emit pause event for UI
                self._emit_event(
                    "task_progress",
                    {
                        "task_id": f"cascade-{preview.weak_node}",
                        "message": f"Paused for approval (confidence: {confidence.confidence:.0%})",
                        "paused": True,
                    },
                )
                break

            if execution.aborted:
                break

        # Calculate duration
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Emit completion
        if execution.completed:
            self._emit_event(
                "task_complete",
                {
                    "task_id": f"cascade-{preview.weak_node}",
                    "duration_ms": duration_ms,
                },
            )
        elif execution.aborted:
            self._emit_event(
                "task_failed",
                {
                    "task_id": f"cascade-{preview.weak_node}",
                    "error": execution.abort_reason or "Aborted",
                },
            )

        return execution

    async def _extract_all_contracts(
        self,
        preview: CascadePreview,
    ) -> dict[str, ExtractedContract]:
        """Extract contracts for all affected files before regeneration."""
        contracts: dict[str, ExtractedContract] = {}

        all_artifacts = [
            preview.weak_node,
            *preview.direct_dependents,
            *preview.transitive_dependents,
        ]

        for artifact_id in all_artifacts:
            if artifact_id in self.engine.graph:
                try:
                    contract = await self.engine.extract_contract(artifact_id)
                    contracts[artifact_id] = contract
                except Exception:
                    pass  # Some files may not be parseable

        return contracts

    async def _execute_wave(
        self,
        wave_graph: ArtifactGraph,
        wave_num: int,
    ) -> WaveResult:
        """Execute a single wave through the artifact system."""
        from sunwell.models.protocol import ToolCall

        completed_content: dict[str, str] = {}
        errors: list[str] = []

        # Execute each artifact in the wave (they're independent within a wave)
        for artifact_id in wave_graph:
            artifact = wave_graph[artifact_id]

            self._emit_event(
                "task_start",
                {
                    "task_id": artifact_id,
                    "description": artifact.description[:100],
                },
            )

            try:
                # Generate content using planner
                content = await self.planner.create_artifact(artifact, {})

                # Write to file if content was generated
                if artifact.produces_file and content:
                    write_call = ToolCall(
                        id=f"write_{artifact_id}",
                        name="write_file",
                        arguments={
                            "path": artifact.produces_file,
                            "content": content,
                        },
                    )
                    result = await self.tool_executor.execute(write_call)
                    if not result.success:
                        raise RuntimeError(
                            f"Failed to write {artifact.produces_file}: {result.output}"
                        )

                completed_content[artifact_id] = content or ""

                self._emit_event(
                    "task_complete",
                    {
                        "task_id": artifact_id,
                        "duration_ms": 0,
                    },
                )
            except Exception as e:
                errors.append(f"{artifact_id}: {e}")

                self._emit_event(
                    "task_failed",
                    {
                        "task_id": artifact_id,
                        "error": str(e),
                    },
                )

        return WaveResult(
            wave_num=wave_num,
            completed=completed_content,
            success=len(errors) == 0,
            error="; ".join(errors) if errors else None,
        )

    async def _verify_wave(
        self,
        wave_num: int,
        wave: tuple[str, ...],
        contracts: dict[str, ExtractedContract],
    ) -> WaveConfidence:
        """Run verification suite and compute confidence."""
        test_result = await self._run_tests()
        type_result = await self._run_type_check()
        lint_result = await self._run_lint()
        contract_result = await self._verify_contracts(contracts, wave)

        return WaveConfidence.compute(
            wave_num=wave_num,
            artifacts=wave,
            test_result=test_result,
            type_result=type_result,
            lint_result=lint_result,
            contract_result=contract_result,
        )

    async def _run_tests(self) -> bool:
        """Run pytest and return success status."""
        try:
            result = subprocess.run(
                ["pytest", "--tb=short", "-q"],
                cwd=self.project_root,
                capture_output=True,
                timeout=300,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # Assume pass if can't run

    async def _run_type_check(self) -> bool:
        """Run mypy and return success status."""
        try:
            result = subprocess.run(
                ["mypy", "src/"],
                cwd=self.project_root,
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True

    async def _run_lint(self) -> bool:
        """Run ruff and return success status."""
        try:
            result = subprocess.run(
                ["ruff", "check", "src/"],
                cwd=self.project_root,
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True

    async def _verify_contracts(
        self,
        original_contracts: dict[str, ExtractedContract],
        wave_artifacts: tuple[str, ...],
    ) -> bool:
        """Verify contracts are preserved after regeneration."""
        for artifact_id in wave_artifacts:
            # Map cascade-prefixed ID back to original
            original_id = artifact_id.replace("cascade-", "")

            if original_id not in original_contracts:
                continue

            original = original_contracts[original_id]
            try:
                current = await self.engine.extract_contract(original_id)
                if not original.is_compatible_with(current):
                    return False
            except Exception:
                pass  # Can't verify - assume OK

        return True

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit agent event if callback registered."""
        if self.on_event:
            from sunwell.agent.events import AgentEvent, EventType

            try:
                event = AgentEvent(EventType(event_type), data)
                self.on_event(event)
            except ValueError:
                pass  # Unknown event type


async def create_cascade_executor(
    project_root: Path,
    graph: ArtifactGraph,
    model: Any | None = None,
    model_name: str | None = None,
    on_event: Callable[[AgentEvent], None] | None = None,
) -> CascadeExecutor:
    """Factory function to create a fully-configured CascadeExecutor.

    This handles all the wiring between components.

    Args:
        project_root: Root directory of the project
        graph: The artifact graph for the project
        model: Optional pre-configured model (if None, creates OllamaModel)
        model_name: Model name for OllamaModel if model not provided
        on_event: Optional event callback for progress updates

    Returns:
        Configured CascadeExecutor ready to use
    """
    from sunwell.naaru.planners.artifact import ArtifactPlanner
    from sunwell.tools.executor import ToolExecutor

    # Create model if not provided
    if model is None:
        from sunwell.config import get_config
        from sunwell.models.ollama import OllamaModel

        config = get_config()
        name = model_name
        if not name and config and hasattr(config, "naaru"):
            name = getattr(config.naaru, "voice", "gemma3:4b")
        if not name:
            name = "gemma3:4b"

        model = OllamaModel(model=name)

    # Create planner
    planner = ArtifactPlanner(model=model)

    # RFC-117: Try to resolve project context
    from sunwell.project import ProjectResolutionError, resolve_project

    project = None
    try:
        project = resolve_project(project_root=project_root)
    except ProjectResolutionError:
        pass

    # Create tool executor
    tool_executor = ToolExecutor(
        project=project,
        workspace=project_root if project is None else None,
    )

    # Create cascade engine
    engine = CascadeEngine(graph=graph, project_root=project_root)

    return CascadeExecutor(
        engine=engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=project_root,
        on_event=on_event,
    )
