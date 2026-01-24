"""ExecutionManager for backlog-driven goal execution (RFC-094).

Single entry point for all goal execution (CLI, Studio, autonomous).
Uses IncrementalExecutor for hash-based change detection and caching.

RFC-105: Enhanced with hierarchical DAG context for skip decisions.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from sunwell.agent.events import AgentEvent, EventType
from sunwell.backlog.goals import Goal, GoalResult, GoalScope
from sunwell.backlog.manager import BacklogManager
from sunwell.execution.context import BacklogContext
from sunwell.incremental import ExecutionCache, IncrementalExecutor, IncrementalResult
from sunwell.naaru.persistence import hash_goal

if TYPE_CHECKING:
    from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of goal execution."""

    success: bool
    goal_id: str
    artifacts_created: tuple[str, ...]
    artifacts_failed: tuple[str, ...]
    artifacts_skipped: tuple[str, ...] = ()
    error: str | None = None
    duration_ms: int = 0
    learnings_count: int = 0


@dataclass(frozen=True, slots=True)
class DagContext:
    """RFC-105: Context from hierarchical DAG for planning.
    
    Provides information about previous goals and artifacts
    to inform skip decisions and reuse existing work.
    """

    total_goals: int = 0
    completed_goals: int = 0
    total_artifacts: int = 0
    previous_goals: tuple[str, ...] = ()
    previous_artifacts: frozenset[str] = frozenset()
    learnings: tuple[str, ...] = ()


class EventEmitter(Protocol):
    """Protocol for event emission."""

    def emit(self, event: AgentEvent) -> None:
        """Emit an event."""
        ...


class ExecutionManager:
    """Single entry point for all goal execution.

    Owns the backlog and ensures consistent state updates.
    All CLI commands and Studio go through this.

    Features:
    - IncrementalExecutor integration (hash-based skip)
    - Backlog lifecycle management (claim/complete/fail)
    - Event emission for UI updates
    - Learnings extraction
    - Goal→artifact tracking
    """

    def __init__(
        self,
        root: Path,
        emitter: EventEmitter | None = None,
        cache_path: Path | None = None,
    ):
        self.root = root
        self.emitter = emitter
        self.backlog = BacklogManager(root)

        # Initialize execution cache
        self._cache_path = cache_path or (root / ".sunwell" / "cache" / "execution.db")
        self._cache: ExecutionCache | None = None

    @property
    def cache(self) -> ExecutionCache:
        """Lazy-load execution cache."""
        if self._cache is None:
            self._cache = ExecutionCache(self._cache_path)
        return self._cache

    async def run_goal(
        self,
        goal: str,
        planner: Any,
        executor: Any,
        *,
        goal_id: str | None = None,
        context: dict[str, Any] | None = None,
        force: bool = False,
        verbose: bool = False,
    ) -> ExecutionResult:
        """Execute a goal with full backlog lifecycle and incremental caching.

        1. Create/find goal in backlog
        2. Claim it (prevents duplicate execution)
        3. Discover artifact graph
        4. Execute with IncrementalExecutor (skip unchanged)
        5. Record goal→artifacts mapping
        6. Extract learnings
        7. Mark complete/failed in backlog
        8. Emit events for UI
        """
        start_time = datetime.now()

        # 1. Ensure goal exists in backlog
        goal_obj = await self._ensure_goal(goal, goal_id)
        gid = goal_obj.id

        # 2. Claim goal (atomic - fails if already claimed)
        claimed = await self.backlog.claim_goal(gid, worker_id=None)
        if not claimed:
            return ExecutionResult(
                success=False,
                goal_id=gid,
                artifacts_created=(),
                artifacts_failed=(),
                error=f"Goal {gid} already being executed",
            )

        self._emit(EventType.BACKLOG_GOAL_STARTED, {
            "goal_id": gid,
            "title": goal_obj.title,
        })

        try:
            # 3. Build backlog context for planner
            backlog_context = await self._build_context()

            # RFC-105: Load hierarchical DAG context
            dag_context = self._load_dag_context()

            # 4. Discover artifact graph
            self._emit(EventType.PLAN_START, {"goal": goal})

            plan_context = context or {}
            plan_context["cwd"] = str(self.root)

            # RFC-105: Add DAG context to planning context
            plan_context["dag"] = {
                "total_goals": dag_context.total_goals,
                "completed_goals": dag_context.completed_goals,
                "total_artifacts": dag_context.total_artifacts,
                "previous_goals": dag_context.previous_goals,
                "previous_artifacts": list(dag_context.previous_artifacts),
                "learnings": dag_context.learnings,
            }

            graph = await self._discover_graph(planner, goal, plan_context, backlog_context)

            self._emit(EventType.PLAN_WINNER, {
                "tasks": len(graph),
                "artifact_count": len(graph),
            })

            # 5. Execute with IncrementalExecutor
            result = await self._execute_incremental(
                graph=graph,
                planner=planner,
                tool_executor=executor,
                force=force,
                verbose=verbose,
            )

            # 6. Record goal→artifacts mapping
            self.cache.record_goal_execution(
                gid,
                list(graph),
                execution_time_ms=result.duration_ms,
            )

            # 7. Extract learnings
            learnings_count = await self._extract_learnings(result, graph)

            # 8. Update backlog based on result
            duration_s = (datetime.now() - start_time).total_seconds()
            exec_result = ExecutionResult(
                success=len(result.failed) == 0,
                goal_id=gid,
                artifacts_created=tuple(result.completed.keys()),
                artifacts_failed=tuple(result.failed.keys()),
                artifacts_skipped=tuple(result.skipped.keys()),
                duration_ms=result.duration_ms,
                learnings_count=learnings_count,
            )

            if result.completed or result.skipped:
                # Some success - mark complete
                await self.backlog.complete_goal(
                    gid,
                    GoalResult(
                        success=len(result.failed) == 0,
                        summary=f"Created {len(result.completed)}, skipped {len(result.skipped)}, failed {len(result.failed)}",
                        artifacts_created=list(result.completed.keys()),
                        files_changed=len(result.completed),
                        duration_seconds=duration_s,
                    ),
                )
                self._emit(EventType.BACKLOG_GOAL_COMPLETED, {
                    "goal_id": gid,
                    "artifacts": list(result.completed.keys()),
                    "skipped": list(result.skipped.keys()),
                    "failed": list(result.failed.keys()),
                    "partial": len(result.failed) > 0,
                    "learnings_count": learnings_count,
                })
            else:
                # Total failure - no artifacts created or cached
                error_msg = f"All {len(result.failed)} artifacts failed"
                await self.backlog.mark_failed(gid, error_msg)
                self._emit(EventType.BACKLOG_GOAL_FAILED, {
                    "goal_id": gid,
                    "error": error_msg,
                })
                exec_result = ExecutionResult(
                    success=False,
                    goal_id=gid,
                    artifacts_created=(),
                    artifacts_failed=tuple(result.failed.keys()),
                    error=error_msg,
                    duration_ms=result.duration_ms,
                )

            self._emit(EventType.COMPLETE, {
                "tasks_completed": len(result.completed) + len(result.skipped),
                "tasks_failed": len(result.failed),
                "duration_s": duration_s,
                "learnings_count": learnings_count,
            })

            return exec_result

        except Exception as e:
            await self.backlog.mark_failed(gid, str(e))
            self._emit(EventType.BACKLOG_GOAL_FAILED, {
                "goal_id": gid,
                "error": str(e),
            })
            self._emit(EventType.ERROR, {"message": str(e)})
            raise
        finally:
            # Always unclaim on exit
            await self.backlog.unclaim_goal(gid)

    async def _build_context(self) -> BacklogContext:
        """Build context for planner from current backlog state."""
        pending = await self.backlog.get_pending_goals()
        completed_artifacts = await self.backlog.get_completed_artifacts()

        return BacklogContext(
            existing_goals=tuple(pending),
            completed_artifacts=frozenset(completed_artifacts),
            in_progress=self.backlog.backlog.in_progress,
        )

    def _load_dag_context(self) -> DagContext:
        """RFC-105: Load DAG context from hierarchical index.
        
        Reads .sunwell/dag/index.json for fast access to previous
        goals and artifacts for skip decisions.
        """
        index_path = self.root / ".sunwell" / "dag" / "index.json"

        if not index_path.exists():
            return DagContext()

        try:
            data = json.loads(index_path.read_text())

            # Extract goal titles for context
            goals = data.get("goals", [])
            previous_goals = tuple(g.get("title", "") for g in goals if g.get("status") == "complete")

            # Extract artifact IDs
            artifacts = data.get("recentArtifacts", [])
            previous_artifacts = frozenset(a.get("id", "") for a in artifacts)

            # Extract learnings from goal files
            learnings: list[str] = []
            goals_dir = self.root / ".sunwell" / "dag" / "goals"
            if goals_dir.exists():
                for goal_file in goals_dir.glob("*.json"):
                    try:
                        goal_data = json.loads(goal_file.read_text())
                        learnings.extend(goal_data.get("learnings", []))
                    except (json.JSONDecodeError, OSError):
                        continue

            summary = data.get("summary", {})
            return DagContext(
                total_goals=summary.get("totalGoals", 0),
                completed_goals=summary.get("completedGoals", 0),
                total_artifacts=summary.get("totalArtifacts", 0),
                previous_goals=previous_goals,
                previous_artifacts=previous_artifacts,
                learnings=tuple(learnings[:20]),  # Limit to recent learnings
            )
        except (json.JSONDecodeError, OSError) as e:
            # Log but don't fail - DAG context is optional
            import logging
            logging.debug("RFC-105: Could not load DAG index: %s", e)
            return DagContext()

    async def _ensure_goal(self, goal: str, goal_id: str | None) -> Goal:
        """Create goal in backlog if not exists."""
        gid = goal_id or hash_goal(goal)

        # Check if already exists
        existing = self.backlog.backlog.goals.get(gid)
        if existing:
            return existing

        # Create new goal
        new_goal = Goal(
            id=gid,
            title=goal[:100],
            description=goal,
            source_signals=(),
            priority=1.0,
            estimated_complexity="moderate",
            requires=frozenset(),
            category="user",
            auto_approvable=True,
            scope=GoalScope(max_files=50, max_lines_changed=5000),
        )
        await self.backlog.add_external_goal(new_goal)
        self._emit(EventType.BACKLOG_GOAL_ADDED, {
            "goal_id": gid,
            "title": new_goal.title,
        })
        return new_goal

    async def _discover_graph(
        self,
        planner: Any,
        goal: str,
        context: dict[str, Any],
        backlog: BacklogContext,
    ) -> ArtifactGraph:
        """Discover artifact graph from planner."""
        # Artifact-first planner (preferred)
        if hasattr(planner, "discover_graph"):
            return await planner.discover_graph(goal, context)

        # Task-based planner with backlog support
        if hasattr(planner, "plan"):
            import inspect
            sig = inspect.signature(planner.plan)
            if "backlog" in sig.parameters:
                return await planner.plan([goal], context=context, backlog=backlog)
            return await planner.plan([goal], context=context)

        msg = f"Planner {type(planner).__name__} has no plan() or discover_graph()"
        raise TypeError(msg)

    async def _execute_incremental(
        self,
        graph: ArtifactGraph,
        planner: Any,
        tool_executor: Any,
        force: bool,
        verbose: bool,
    ) -> IncrementalResult:
        """Execute using IncrementalExecutor with caching."""
        # Create executor
        executor = IncrementalExecutor(
            graph=graph,
            cache=self.cache,
            event_callback=self._event_callback,
            project_root=self.root,
            trace_enabled=verbose,
        )

        # Convert force flag
        force_artifacts = set(graph) if force else None

        # Preview what will execute
        plan = executor.plan_execution(force_rerun=force_artifacts)

        if plan.to_skip and not force:
            self._emit(EventType.LOG, {
                "message": f"📊 Incremental: {len(plan.to_skip)} cached, {len(plan.to_execute)} to execute",
            })

            if not plan.to_execute:
                # Everything cached - return early
                return IncrementalResult(
                    completed={},
                    failed={},
                    skipped={aid: plan.decisions[aid].cached_result for aid in plan.to_skip},
                    run_id="cached",
                )

        # Create artifact function
        async def create_artifact(spec: ArtifactSpec) -> str:
            return await self._create_artifact(spec, planner, tool_executor)

        # Execute
        return await executor.execute(
            create_fn=create_artifact,
            force_rerun=force_artifacts,
            on_progress=lambda msg: self._emit(EventType.LOG, {"message": msg}) if verbose else None,
        )

    async def _create_artifact(
        self,
        spec: ArtifactSpec,
        planner: Any,
        tool_executor: Any,
    ) -> str:
        """Create a single artifact."""
        from sunwell.models.protocol import ToolCall

        self._emit(EventType.TASK_START, {
            "task_id": spec.id,
            "description": spec.description,
        })

        start_time = datetime.now()

        try:
            # Generate content
            content = await planner.create_artifact(spec, {})

            # Write to disk
            if spec.produces_file and content:
                write_call = ToolCall(
                    id=f"write_{spec.id}",
                    name="write_file",
                    arguments={"path": spec.produces_file, "content": content},
                )
                result = await tool_executor.execute(write_call)

                if not result.success:
                    self._emit(EventType.TASK_FAILED, {
                        "task_id": spec.id,
                        "error": result.output,
                    })
                    raise RuntimeError(f"Failed to write {spec.produces_file}: {result.output}")

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._emit(EventType.TASK_COMPLETE, {
                "task_id": spec.id,
                "duration_ms": duration_ms,
                "file": spec.produces_file,
            })

            return content or ""

        except Exception as e:
            self._emit(EventType.TASK_FAILED, {
                "task_id": spec.id,
                "error": str(e),
            })
            raise

    async def _extract_learnings(
        self,
        result: IncrementalResult,
        graph: ArtifactGraph,
    ) -> int:
        """Extract learnings from execution result."""
        try:
            from sunwell.simulacrum.extractors.extractor import auto_extract_learnings
        except ImportError:
            return 0

        import json
        import uuid

        learnings = []
        intel_path = self.root / ".sunwell" / "intelligence"
        intel_path.mkdir(parents=True, exist_ok=True)

        for artifact_id in result.completed:
            artifact = graph.get(artifact_id)
            if not artifact:
                continue

            content = ""
            artifact_result = result.completed.get(artifact_id)
            if artifact_result and artifact_result.get("content"):
                content = artifact_result["content"]
            elif artifact.description:
                content = artifact.description

            if not content:
                continue

            try:
                extracted = auto_extract_learnings(content, min_confidence=0.6)
                for fact, category, confidence in extracted[:3]:
                    learning = {
                        "id": f"learn-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
                        "fact": fact,
                        "category": category,
                        "confidence": confidence,
                        "source_file": artifact_id,
                        "created_at": datetime.now().isoformat(),
                    }
                    learnings.append(learning)

                    self._emit(EventType.MEMORY_LEARNING, {
                        "fact": fact,
                        "category": category,
                        "confidence": confidence,
                        "source": artifact_id,
                    })
            except Exception:
                continue

        if learnings:
            learnings_file = intel_path / "learnings.jsonl"
            with open(learnings_file, "a") as f:
                for learning in learnings:
                    f.write(json.dumps(learning) + "\n")

        return len(learnings)

    def _event_callback(self, event_type: str, **kwargs: Any) -> None:
        """Callback for IncrementalExecutor events."""
        try:
            et = EventType(event_type)
            self._emit(et, kwargs)
        except ValueError:
            # Unknown event type - skip
            pass

    def _emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Emit event via configured emitter."""
        if self.emitter is None:
            return

        event = AgentEvent(event_type, data)
        self.emitter.emit(event)
