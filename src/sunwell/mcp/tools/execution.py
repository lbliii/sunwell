"""MCP execution tools for Sunwell.

Provides tools for running goals through the agent pipeline,
running validators, and reporting task completion.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import (
    DEFAULT_FORMAT,
    mcp_json,
    omit_empty,
    resolve_format,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.mcp.runtime import MCPRuntime


def register_execution_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register execution-related tools.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and async bridging
    """

    @mcp.tool()
    def sunwell_execute(
        goal: str,
        project: str | None = None,
        lens: str | None = None,
        dry_run: bool = False,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Execute a goal through Sunwell's full agent pipeline.

        Runs the complete ORIENT -> SIGNAL -> LENS -> PLAN -> EXECUTE ->
        VALIDATE -> FIX -> LEARN pipeline.

        Set dry_run=True to get the plan without executing it.

        WARNING: This tool can modify files. Use with appropriate trust level.

        Args:
            goal: The goal to execute (natural language)
            project: Optional project path
            lens: Optional lens name to use (e.g., "coder", "tech-writer")
            dry_run: If True, only plan without executing (default: False)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with execution results
        """
        fmt = resolve_format(format)

        try:
            from sunwell.agent.context.session import SessionContext
            from sunwell.agent.core.agent import Agent
            from sunwell.memory.facade import PersistentMemory
            from sunwell.models.registry.registry import resolve_model

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            model = resolve_model("default")
            if not model:
                return mcp_json({"error": "No model available for execution"}, fmt)

            memory = runtime.memory if runtime else PersistentMemory.load(ws)
            agent = Agent(model=model)

            if not runtime:
                return mcp_json({"error": "Runtime not available for async execution"}, fmt)

            # Dry run - just plan
            if dry_run:
                plan = runtime.run(agent.plan_only(goal, memory=memory))

                tasks = []
                if plan.task_graph and hasattr(plan.task_graph, "tasks"):
                    tasks = [
                        omit_empty({
                            "id": getattr(t, "id", None),
                            "title": getattr(t, "title", str(t)),
                        })
                        for t in plan.task_graph.tasks
                    ]

                return mcp_json(omit_empty({
                    "mode": "dry_run",
                    "goal": goal,
                    "tasks": tasks,
                    "estimated_seconds": plan.estimated_seconds,
                }), fmt)

            # Full execution
            lens_obj = None
            if lens:
                try:
                    from sunwell.foundation.schema.loader import LensLoader
                    from sunwell.planning.naaru.expertise.discovery import LensDiscovery

                    discovery = LensDiscovery()
                    loader = LensLoader()
                    for sp in discovery.search_paths:
                        if not sp.exists():
                            continue
                        for ext in (".lens", ".lens.yaml"):
                            path = sp / f"{lens}{ext}"
                            if path.exists():
                                lens_obj = loader.load(path)
                                break
                        if lens_obj:
                            break
                except Exception:
                    pass

            session = SessionContext.build(
                cwd=ws,
                goal=goal,
                lens=lens_obj,
            )

            tasks_completed = 0
            tasks_failed = 0
            validation_passed = True

            async def run_and_collect():
                nonlocal tasks_completed, tasks_failed, validation_passed
                async for event in agent.run(session, memory):
                    event_type = type(event).__name__
                    if event_type in ("TaskComplete", "TASK_COMPLETE"):
                        tasks_completed += 1
                    elif event_type in ("TaskFailed", "TASK_FAILED"):
                        tasks_failed += 1
                    elif event_type in ("ValidationFailed", "VALIDATION_FAILED"):
                        validation_passed = False

            runtime.run(run_and_collect())

            data = omit_empty({
                "mode": "executed",
                "goal": goal,
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
                "validation_passed": validation_passed,
                "files_modified": list(session.files_modified),
                "artifacts_created": list(session.artifacts_created),
            })

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e), "goal": goal}, fmt)

    @mcp.tool()
    def sunwell_validate(
        file_path: str,
        project: str | None = None,
        validators: list[str] | None = None,
        domain: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Run validators against a file or artifact.

        Formats:
        - "summary": pass/fail verdict only (~50 tokens)
        - "compact": per-validator pass/fail with messages (default)
        - "full": everything including details and severity

        Args:
            file_path: Path to the file to validate
            project: Optional project path
            validators: Optional list of specific validators to run
            domain: Optional domain hint (code, research)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with validation results
        """
        fmt = resolve_format(format)

        try:
            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()

            fp = Path(file_path)
            if not fp.is_absolute():
                fp = ws / fp

            if not fp.exists():
                return mcp_json({"error": f"File not found: {fp}"}, fmt)

            content = fp.read_text()

            if not domain:
                if fp.suffix in (".py", ".js", ".ts", ".rs", ".go", ".java", ".cpp", ".c"):
                    domain = "code"
                elif fp.suffix in (".md", ".rst", ".txt"):
                    domain = "research"
                else:
                    domain = "code"

            results: list[dict] = []

            if domain == "code":
                available = {}
                try:
                    from sunwell.domains.code.validators import (
                        LintValidator,
                        SyntaxValidator,
                        TypeValidator,
                    )

                    available = {
                        "syntax": SyntaxValidator(),
                        "lint": LintValidator(),
                        "type": TypeValidator(),
                    }
                except ImportError:
                    pass

                to_run = validators or list(available.keys())
                for name in to_run:
                    if name not in available:
                        results.append({"validator": name, "status": "skipped"})
                        continue

                    try:
                        validator = available[name]
                        if runtime:
                            vr = runtime.run(
                                validator.validate(
                                    {"path": str(fp), "content": content},
                                    {"cwd": str(ws)},
                                )
                            )
                        else:
                            continue

                        entry: dict = {
                            "validator": name,
                            "passed": getattr(vr, "passed", None),
                        }
                        if fmt != "summary":
                            entry["message"] = getattr(vr, "message", None)
                        if fmt == "full":
                            entry["severity"] = str(getattr(vr, "severity", "unknown"))
                            entry["details"] = getattr(vr, "details", {})
                        results.append(omit_empty(entry))
                    except Exception as e:
                        results.append({"validator": name, "status": "error", "error": str(e)})

            elif domain == "research":
                available = {}
                try:
                    from sunwell.domains.research.validators import (
                        CoherenceValidator,
                        SourceValidator,
                    )

                    available = {
                        "sources": SourceValidator(),
                        "coherence": CoherenceValidator(),
                    }
                except ImportError:
                    pass

                to_run = validators or list(available.keys())
                for name in to_run:
                    if name not in available:
                        results.append({"validator": name, "status": "skipped"})
                        continue

                    try:
                        validator = available[name]
                        if runtime:
                            vr = runtime.run(
                                validator.validate(
                                    {"path": str(fp), "content": content},
                                    {"cwd": str(ws)},
                                )
                            )
                        else:
                            continue

                        entry = {"validator": name, "passed": getattr(vr, "passed", None)}
                        if fmt != "summary":
                            entry["message"] = getattr(vr, "message", None)
                        results.append(omit_empty(entry))
                    except Exception as e:
                        results.append({"validator": name, "status": "error", "error": str(e)})

            all_passed = all(
                r.get("passed", True)
                for r in results
                if r.get("status") != "skipped"
            )

            if fmt == "summary":
                return mcp_json({"file_path": file_path, "all_passed": all_passed}, fmt)

            return mcp_json(omit_empty({
                "file_path": file_path,
                "domain": domain,
                "all_passed": all_passed,
                "results": results,
                "total_validators": len(results),
            }), fmt)
        except Exception as e:
            return mcp_json({"error": str(e), "file_path": file_path}, fmt)

    @mcp.tool()
    def sunwell_complete(
        goal: str,
        files_modified: str = "",
        files_reviewed: str = "",
        learnings: str | None = None,
        success: bool = True,
        project: str | None = None,
    ) -> str:
        """
        Report task completion back to Sunwell.

        Call this after completing a task to let Sunwell update its memory.
        This enables Sunwell to learn from what happened, track which files
        were touched, and maintain accurate session history.

        Args:
            goal: What was accomplished
            files_modified: Comma-separated paths of files that were edited
            files_reviewed: Comma-separated paths of files that were only reviewed
            learnings: Optional learnings to record (free text)
            success: Whether the task completed successfully (default: True)
            project: Optional project path

        Returns:
            JSON confirmation with recorded completion data
        """
        try:
            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            modified = [f.strip() for f in files_modified.split(",") if f.strip()]
            reviewed = [f.strip() for f in files_reviewed.split(",") if f.strip()]

            recorded: dict = omit_empty({
                "goal": goal,
                "success": success,
                "files_modified": modified,
                "files_reviewed": reviewed,
            })

            # Record learnings if provided
            if learnings and memory.simulacrum:
                try:
                    memory.add_learning(learnings)
                    recorded["learning_recorded"] = True
                except Exception as e:
                    recorded["learning_error"] = str(e)

            # Update lineage for modified files
            if modified:
                try:
                    from sunwell.memory.lineage.store import LineageStore

                    lineage = LineageStore(ws)
                    for fp in modified:
                        lineage.record_edit(
                            path=fp,
                            goal_id=None,
                            task_id=None,
                            lines_added=0,
                            lines_removed=0,
                            source="external",
                            session_id=None,
                        )
                    recorded["lineage_updated"] = True
                except Exception as e:
                    recorded["lineage_error"] = str(e)

            # Sync memory to disk
            try:
                memory.sync()
                recorded["synced"] = True
            except Exception as e:
                recorded["sync_error"] = str(e)

            return mcp_json(recorded, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")
