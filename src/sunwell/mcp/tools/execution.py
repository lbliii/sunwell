"""MCP execution tools for Sunwell.

Provides tools for running goals through the agent pipeline,
running validators, and reporting task completion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_execution_tools(mcp: FastMCP, workspace: str | None = None) -> None:
    """Register execution-related tools.

    Args:
        mcp: FastMCP server instance
        workspace: Optional workspace root path
    """

    def _resolve_workspace(project: str | None = None) -> Path:
        if project:
            p = Path(project).expanduser().resolve()
            if p.exists():
                return p
        if workspace:
            return Path(workspace).expanduser().resolve()
        return Path.cwd()

    @mcp.tool()
    def sunwell_execute(
        goal: str,
        project: str | None = None,
        lens: str | None = None,
        dry_run: bool = False,
    ) -> str:
        """
        Execute a goal through Sunwell's full agent pipeline.

        Runs the complete ORIENT -> SIGNAL -> LENS -> PLAN -> EXECUTE ->
        VALIDATE -> FIX -> LEARN pipeline. The agent will decompose the goal,
        select appropriate tools, execute tasks, validate results, and
        extract learnings.

        Set dry_run=True to get the plan without executing it.

        WARNING: This tool can modify files. Use with appropriate trust level.

        Args:
            goal: The goal to execute (natural language)
            project: Optional project path
            lens: Optional lens name to use (e.g., "coder", "tech-writer")
            dry_run: If True, only plan without executing (default: False)

        Returns:
            JSON with execution results including tasks completed,
            files modified, and validation results
        """
        import asyncio

        try:
            from sunwell.agent.context.session import SessionContext
            from sunwell.agent.core.agent import Agent
            from sunwell.memory.facade import PersistentMemory
            from sunwell.models.registry.registry import resolve_model

            ws = _resolve_workspace(project)
            model = resolve_model("default")
            if not model:
                return json.dumps(
                    {"error": "No model available for execution"},
                    indent=2,
                )

            memory = PersistentMemory.load(ws)
            agent = Agent(model=model)

            # Dry run - just plan
            if dry_run:
                loop = asyncio.new_event_loop()
                try:
                    plan = loop.run_until_complete(agent.plan_only(goal, memory=memory))
                finally:
                    loop.close()

                tasks = []
                if plan.task_graph and hasattr(plan.task_graph, "tasks"):
                    tasks = [
                        {
                            "id": getattr(t, "id", None),
                            "title": getattr(t, "title", str(t)),
                        }
                        for t in plan.task_graph.tasks
                    ]

                return json.dumps(
                    {
                        "mode": "dry_run",
                        "goal": goal,
                        "tasks": tasks,
                        "estimated_seconds": plan.estimated_seconds,
                    },
                    indent=2,
                    default=str,
                )

            # Full execution
            # Build session context
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

            # Collect events from execution
            events_summary: list[dict] = []
            files_modified: list[str] = []
            tasks_completed = 0
            tasks_failed = 0
            validation_passed = True

            loop = asyncio.new_event_loop()
            try:

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

                loop.run_until_complete(run_and_collect())
            finally:
                loop.close()

            files_modified = list(session.files_modified)

            return json.dumps(
                {
                    "mode": "executed",
                    "goal": goal,
                    "tasks_completed": tasks_completed,
                    "tasks_failed": tasks_failed,
                    "validation_passed": validation_passed,
                    "files_modified": files_modified,
                    "artifacts_created": list(session.artifacts_created),
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "goal": goal}, indent=2)

    @mcp.tool()
    def sunwell_validate(
        file_path: str,
        project: str | None = None,
        validators: list[str] | None = None,
        domain: str | None = None,
    ) -> str:
        """
        Run validators against a file or artifact.

        Runs Sunwell's validation system against a file. Can run specific
        validators or auto-detect based on domain (code, research, etc.).

        Available validators (code domain):
        - "syntax": Check Python syntax validity
        - "lint": Run linting checks
        - "type": Type checking
        - "test": Run related tests

        Available validators (research domain):
        - "sources": Check claims are backed by sources
        - "coherence": Check argument coherence

        Args:
            file_path: Path to the file to validate (relative to project or absolute)
            project: Optional project path
            validators: Optional list of specific validators to run
            domain: Optional domain hint for auto-detection (code, research)

        Returns:
            JSON with validation results including pass/fail, errors, and details
        """
        try:
            ws = _resolve_workspace(project)

            # Resolve file path
            fp = Path(file_path)
            if not fp.is_absolute():
                fp = ws / fp

            if not fp.exists():
                return json.dumps(
                    {"error": f"File not found: {fp}", "file_path": file_path},
                    indent=2,
                )

            content = fp.read_text()

            # Auto-detect domain if not specified
            if not domain:
                if fp.suffix in (".py", ".js", ".ts", ".rs", ".go", ".java", ".cpp", ".c"):
                    domain = "code"
                elif fp.suffix in (".md", ".rst", ".txt"):
                    domain = "research"
                else:
                    domain = "code"

            results: list[dict] = []

            if domain == "code":
                # Run code validators
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
                        results.append({
                            "validator": name,
                            "status": "skipped",
                            "reason": f"Validator '{name}' not available",
                        })
                        continue

                    try:
                        import asyncio

                        validator = available[name]
                        loop = asyncio.new_event_loop()
                        try:
                            vr = loop.run_until_complete(
                                validator.validate(
                                    {"path": str(fp), "content": content},
                                    {"cwd": str(ws)},
                                )
                            )
                        finally:
                            loop.close()

                        results.append({
                            "validator": name,
                            "passed": getattr(vr, "passed", None),
                            "severity": str(getattr(vr, "severity", "unknown")),
                            "message": getattr(vr, "message", None),
                            "details": getattr(vr, "details", {}),
                        })
                    except Exception as e:
                        results.append({
                            "validator": name,
                            "status": "error",
                            "error": str(e),
                        })

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
                        results.append({
                            "validator": name,
                            "status": "skipped",
                            "reason": f"Validator '{name}' not available",
                        })
                        continue

                    try:
                        import asyncio

                        validator = available[name]
                        loop = asyncio.new_event_loop()
                        try:
                            vr = loop.run_until_complete(
                                validator.validate(
                                    {"path": str(fp), "content": content},
                                    {"cwd": str(ws)},
                                )
                            )
                        finally:
                            loop.close()

                        results.append({
                            "validator": name,
                            "passed": getattr(vr, "passed", None),
                            "message": getattr(vr, "message", None),
                        })
                    except Exception as e:
                        results.append({
                            "validator": name,
                            "status": "error",
                            "error": str(e),
                        })

            all_passed = all(
                r.get("passed", True)
                for r in results
                if r.get("status") != "skipped"
            )

            return json.dumps(
                {
                    "file_path": file_path,
                    "domain": domain,
                    "all_passed": all_passed,
                    "results": results,
                    "total_validators": len(results),
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "file_path": file_path}, indent=2)

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

        Inspired by DORI's completion tracking pattern.

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
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace(project)
            memory = PersistentMemory.load(ws)

            modified = [f.strip() for f in files_modified.split(",") if f.strip()]
            reviewed = [f.strip() for f in files_reviewed.split(",") if f.strip()]

            recorded: dict = {
                "goal": goal,
                "success": success,
                "files_modified": modified,
                "files_reviewed": reviewed,
                "workspace": str(ws),
            }

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
                sync_result = memory.sync()
                recorded["synced"] = True
            except Exception as e:
                recorded["sync_error"] = str(e)

            return json.dumps(recorded, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
