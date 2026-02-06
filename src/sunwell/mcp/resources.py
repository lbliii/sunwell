"""MCP Resource definitions for Sunwell.

Resources are read-only data endpoints that expose Sunwell's configuration,
lens registry, memory state, and reference content to MCP clients.

Resource URIs:
- sunwell://map                       - Capabilities overview and routing guide
- sunwell://config                    - Current configuration summary
- sunwell://status                    - System health and stats
- sunwell://lenses                    - Dynamic lens list
- sunwell://lenses/registry           - Full registry with shortcuts and overrides
- sunwell://shortcuts                 - Dynamic shortcut map
- sunwell://projects                  - Known projects with metadata
- sunwell://briefing                  - Current rolling briefing
- sunwell://learnings                 - Recent learnings from past sessions
- sunwell://deadends                  - Known dead ends and failed approaches
- sunwell://constraints               - Active constraints and guardrails
- sunwell://goals                     - Current active goals
- sunwell://goals/blocked             - Blocked goals with reasons
- sunwell://reference/domains         - Available domains and capabilities
- sunwell://reference/tools           - Available tool catalog
- sunwell://reference/validators      - Available validators by domain
- sunwell://reference/models          - Available models and strengths
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_resources(mcp: FastMCP, workspace: str | None = None, lenses_dir: str | None = None) -> None:
    """Register all Sunwell resources with the MCP server.

    Args:
        mcp: FastMCP server instance
        workspace: Optional workspace root path
        lenses_dir: Optional path to lenses directory
    """

    def _resolve_workspace() -> Path:
        if workspace:
            return Path(workspace).expanduser().resolve()
        return Path.cwd()

    # =========================================================================
    # Core Resources
    # =========================================================================

    @mcp.resource("sunwell://map")
    def map_resource() -> str:
        """Sunwell capabilities overview and routing guide. Start here."""
        return """# Sunwell MCP Server

Sunwell provides domain intelligence through an MCP interface. It exposes
lenses (professional expertise), memory (persistent learnings), knowledge
(codebase intelligence), planning (intent routing), and execution (agent pipeline).

## Quick Start

1. **Get the briefing**: `sunwell://briefing` or `sunwell_briefing()` — instant project context
2. **Search the codebase**: `sunwell_search("how does auth work?")` — semantic search
3. **Get expertise**: `sunwell_lens("coder")` — inject professional perspective
4. **Classify intent**: `sunwell_classify("add dark mode toggle")` — understand complexity
5. **Check learnings**: `sunwell_recall("caching strategy")` — leverage past insights

## Tool Categories

### Lens System (expertise injection)
- `sunwell_lens(name)` — Get lens as injectable expertise
- `sunwell_list(format)` — List available lenses
- `sunwell_route(command)` — Route shortcuts to lenses
- `sunwell_shortcuts()` — List all shortcuts

### Knowledge (codebase intelligence)
- `sunwell_search(query)` — Semantic search across indexed codebase
- `sunwell_ask(question)` — Synthesized answer with source refs
- `sunwell_codebase(aspect)` — Call graphs, hot paths, patterns
- `sunwell_workspace()` — List known projects

### Memory (persistent context)
- `sunwell_briefing()` — Rolling briefing (mission, status, hazards)
- `sunwell_recall(query, scope)` — Query learnings, dead ends, constraints
- `sunwell_lineage(file_path)` — Artifact provenance and dependencies
- `sunwell_session()` — Session history and metrics

### Planning (intelligence routing)
- `sunwell_plan(goal)` — Execution plan without executing
- `sunwell_classify(input)` — Intent, complexity, lens recommendation
- `sunwell_reason(question)` — Reasoned decision with confidence

### Backlog (autonomous goals)
- `sunwell_goals(status)` — List goals from DAG
- `sunwell_goal(goal_id)` — Goal details with dependencies
- `sunwell_suggest_goal(signal)` — Generate goals from observation

### Mirror (self-introspection)
- `sunwell_mirror(aspect)` — Learnings, patterns, dead ends
- `sunwell_team(query, scope)` — Team decisions, ownership, patterns

### Execution (agent pipeline)
- `sunwell_execute(goal)` — Run full agent pipeline
- `sunwell_validate(file_path)` — Run validators
- `sunwell_complete(goal)` — Report completion to update memory

### Delegation (model routing)
- `sunwell_delegate(task)` — Smart model recommendation

## Resources

Use resources for static/semi-static context that you pull in as needed:
- `sunwell://briefing` — Current rolling briefing
- `sunwell://learnings` — Accumulated insights
- `sunwell://deadends` — Known failed approaches
- `sunwell://goals` — Active backlog
- `sunwell://reference/domains` — Domain capabilities
- `sunwell://reference/tools` — Tool catalog
"""

    @mcp.resource("sunwell://config")
    def config_resource() -> str:
        """Current Sunwell configuration summary."""
        try:
            from sunwell.foundation.config import get_config

            config = get_config()
            return json.dumps(
                {
                    "verbose": config.verbose,
                    "debug": config.debug,
                    "model": {
                        "default": getattr(config.model, "default", None),
                    } if hasattr(config, "model") else {},
                    "embedding": {
                        "provider": getattr(config.embedding, "provider", None),
                    } if hasattr(config, "embedding") else {},
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("sunwell://status")
    def status_resource() -> str:
        """System health: memory stats, model availability."""
        try:
            ws = _resolve_workspace()
            status: dict = {"workspace": str(ws)}

            # Memory stats
            try:
                from sunwell.memory.facade import PersistentMemory

                memory = PersistentMemory.load(ws)
                status["memory"] = {
                    "learnings": memory.learning_count,
                    "decisions": memory.decision_count,
                    "failures": memory.failure_count,
                    "has_simulacrum": memory.simulacrum is not None,
                    "has_team": memory.team is not None,
                }
            except Exception:
                status["memory"] = {"available": False}

            # Model availability
            try:
                from sunwell.models.registry.registry import get_registry

                registry = get_registry()
                status["models"] = {
                    "registered": registry.list_registered(),
                }
            except Exception:
                status["models"] = {"available": False}

            # Briefing
            try:
                from sunwell.memory.briefing import Briefing

                briefing = Briefing.load(ws)
                status["briefing"] = {
                    "available": briefing is not None,
                    "status": briefing.status.value if briefing and hasattr(briefing.status, "value") else None,
                    "mission": briefing.mission if briefing else None,
                }
            except Exception:
                status["briefing"] = {"available": False}

            return json.dumps(status, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # Lens Resources
    # =========================================================================

    @mcp.resource("sunwell://lenses")
    def lenses_resource() -> str:
        """Dynamic lens list from all layers."""
        try:
            from sunwell.foundation.registry.layered import LayeredLensRegistry

            if lenses_dir:
                registry = LayeredLensRegistry.build(
                    local_dir=Path(lenses_dir),
                    installed_dir=Path.home() / ".sunwell" / "lenses",
                    builtin_dir=Path(__file__).parent.parent / "lenses",
                )
            else:
                registry = LayeredLensRegistry.from_discovery()

            lenses = []
            for entry in registry.all_entries():
                lenses.append({
                    "name": entry.lens.metadata.name,
                    "domain": entry.lens.metadata.domain,
                    "layer": entry.layer,
                    "description": entry.lens.metadata.description,
                })

            return json.dumps({"lenses": lenses, "total": len(lenses)}, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("sunwell://lenses/registry")
    def lenses_registry_resource() -> str:
        """Full lens registry with shortcuts, overrides, and collisions."""
        try:
            from sunwell.foundation.registry.layered import LayeredLensRegistry

            if lenses_dir:
                registry = LayeredLensRegistry.build(
                    local_dir=Path(lenses_dir),
                    installed_dir=Path.home() / ".sunwell" / "lenses",
                    builtin_dir=Path(__file__).parent.parent / "lenses",
                )
            else:
                registry = LayeredLensRegistry.from_discovery()

            summary = registry.summary()
            overrides = []
            for lens_name, winner, overridden in registry.get_overrides():
                overrides.append({
                    "lens": lens_name,
                    "winner_layer": winner.layer,
                    "overridden_layers": [e.layer for e in overridden],
                })

            collisions = {}
            for shortcut, entries in registry.get_collisions().items():
                collisions[shortcut] = [
                    {"lens": e.lens.metadata.name, "layer": e.layer}
                    for e in entries
                ]

            return json.dumps(
                {
                    "summary": summary,
                    "shortcuts": dict(registry.shortcuts),
                    "overrides": overrides,
                    "collisions": collisions,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("sunwell://shortcuts")
    def shortcuts_resource() -> str:
        """Dynamic shortcut map across all lenses."""
        try:
            from sunwell.foundation.registry.layered import LayeredLensRegistry

            if lenses_dir:
                registry = LayeredLensRegistry.build(
                    local_dir=Path(lenses_dir),
                    installed_dir=Path.home() / ".sunwell" / "lenses",
                    builtin_dir=Path(__file__).parent.parent / "lenses",
                )
            else:
                registry = LayeredLensRegistry.from_discovery()

            return json.dumps(dict(registry.shortcuts), indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # Knowledge Resources
    # =========================================================================

    @mcp.resource("sunwell://projects")
    def projects_resource() -> str:
        """Known projects with metadata."""
        try:
            from sunwell.knowledge.workspace import WorkspaceRegistry

            reg = WorkspaceRegistry()
            projects = []
            for ws_entry in reg.list_workspaces():
                for proj in ws_entry.projects:
                    projects.append({
                        "id": proj.id,
                        "path": str(proj.path),
                        "role": proj.role.value if hasattr(proj.role, "value") else str(proj.role),
                        "is_primary": proj.is_primary,
                    })

            return json.dumps({"projects": projects, "total": len(projects)}, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e), "projects": []})

    # =========================================================================
    # Memory Resources
    # =========================================================================

    @mcp.resource("sunwell://briefing")
    def briefing_resource() -> str:
        """Current rolling briefing — the single most useful context blob."""
        try:
            from sunwell.memory.briefing import Briefing

            ws = _resolve_workspace()
            briefing = Briefing.load(ws)
            if not briefing:
                return json.dumps({"status": "no_briefing", "message": "No briefing found."})

            return briefing.to_prompt()
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("sunwell://learnings")
    def learnings_resource() -> str:
        """Recent learnings extracted from past sessions."""
        try:
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace()
            memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return json.dumps({"learnings": [], "message": "No simulacrum store available."})

            try:
                dag = memory.simulacrum.get_dag()
                all_learnings = dag.get_learnings()
                return json.dumps(
                    {
                        "learnings": [
                            {
                                "fact": l.fact if hasattr(l, "fact") else str(l),
                                "category": getattr(l, "category", None),
                                "confidence": getattr(l, "confidence", None),
                                "use_count": getattr(l, "use_count", 0),
                            }
                            for l in all_learnings[:50]
                        ],
                        "total": len(all_learnings),
                    },
                    indent=2,
                    default=str,
                )
            except Exception as e:
                return json.dumps({"error": str(e), "learnings": []})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("sunwell://deadends")
    def deadends_resource() -> str:
        """Known dead ends and failed approaches — avoid repeating mistakes."""
        try:
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace()
            memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return json.dumps({"dead_ends": [], "message": "No simulacrum store available."})

            dead_ends = memory.simulacrum.get_dead_ends()
            return json.dumps(
                {
                    "dead_ends": [str(de) for de in dead_ends[:30]],
                    "total": len(dead_ends),
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("sunwell://constraints")
    def constraints_resource() -> str:
        """Active constraints and guardrails from memory."""
        try:
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace()
            memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return json.dumps({"constraints": [], "message": "No simulacrum store available."})

            try:
                dag = memory.simulacrum.get_dag()
                all_learnings = dag.get_learnings()
                constraints = [
                    {
                        "fact": l.fact if hasattr(l, "fact") else str(l),
                        "confidence": getattr(l, "confidence", None),
                    }
                    for l in all_learnings
                    if getattr(l, "category", None) == "constraint"
                ]
                return json.dumps(
                    {"constraints": constraints, "total": len(constraints)},
                    indent=2,
                    default=str,
                )
            except Exception as e:
                return json.dumps({"error": str(e), "constraints": []})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # Backlog Resources
    # =========================================================================

    @mcp.resource("sunwell://goals")
    def goals_resource() -> str:
        """Current active goals from the backlog DAG."""
        import asyncio

        try:
            from sunwell.features.backlog.manager import BacklogManager

            ws = _resolve_workspace()
            manager = BacklogManager(root=ws)

            loop = asyncio.new_event_loop()
            try:
                backlog = loop.run_until_complete(manager.refresh())
            finally:
                loop.close()

            active = []
            for goal_id, goal in backlog.goals.items():
                if goal_id not in backlog.completed:
                    active.append({
                        "id": goal.id,
                        "title": goal.title,
                        "priority": goal.priority,
                        "category": goal.category,
                        "goal_type": getattr(goal, "goal_type", "task"),
                        "in_progress": goal_id == backlog.in_progress,
                        "blocked": goal_id in backlog.blocked,
                    })

            active.sort(key=lambda g: g.get("priority", 0), reverse=True)
            return json.dumps({"goals": active, "total": len(active)}, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e), "goals": []})

    @mcp.resource("sunwell://goals/blocked")
    def goals_blocked_resource() -> str:
        """Blocked goals with reasons."""
        import asyncio

        try:
            from sunwell.features.backlog.manager import BacklogManager

            ws = _resolve_workspace()
            manager = BacklogManager(root=ws)

            loop = asyncio.new_event_loop()
            try:
                backlog = loop.run_until_complete(manager.refresh())
            finally:
                loop.close()

            blocked = []
            for goal_id, reason in backlog.blocked.items():
                goal = backlog.goals.get(goal_id)
                if goal:
                    blocked.append({
                        "id": goal.id,
                        "title": goal.title,
                        "reason": reason,
                        "requires": list(goal.requires),
                    })

            return json.dumps({"blocked_goals": blocked, "total": len(blocked)}, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e), "blocked_goals": []})

    # =========================================================================
    # Reference Resources
    # =========================================================================

    @mcp.resource("sunwell://reference/domains")
    def domains_reference() -> str:
        """Available domains and their capabilities."""
        return json.dumps(
            {
                "domains": [
                    {
                        "name": "code",
                        "type": "CODE",
                        "description": "Software development, debugging, refactoring",
                        "validators": ["syntax", "lint", "type", "test"],
                        "tools": ["read_file", "write_file", "edit_file", "git_*", "run_command"],
                        "keywords": ["implement", "refactor", "debug", "api", "function", "class", "test", "bug"],
                    },
                    {
                        "name": "research",
                        "type": "RESEARCH",
                        "description": "Investigation, summarization, evidence gathering",
                        "validators": ["sources", "coherence"],
                        "tools": ["web_search", "summarize", "extract_claims"],
                        "keywords": ["research", "investigate", "summarize", "sources", "evidence", "find"],
                    },
                    {
                        "name": "writing",
                        "type": "WRITING",
                        "description": "Documentation, technical writing, content creation",
                        "validators": [],
                        "tools": ["read_file", "write_file", "edit_file"],
                        "keywords": ["write", "document", "explain", "describe", "readme"],
                    },
                    {
                        "name": "data",
                        "type": "DATA",
                        "description": "Data analysis, processing, transformation",
                        "validators": [],
                        "tools": ["read_file", "run_command"],
                        "keywords": ["data", "analysis", "analytics", "csv", "json", "transform"],
                    },
                    {
                        "name": "general",
                        "type": "GENERAL",
                        "description": "Fallback for unclassified tasks",
                        "validators": [],
                        "tools": ["read_file", "write_file"],
                        "keywords": [],
                    },
                ],
            },
            indent=2,
        )

    @mcp.resource("sunwell://reference/tools")
    def tools_reference() -> str:
        """Available tool catalog with trust levels."""
        return json.dumps(
            {
                "tool_categories": {
                    "file_operations": {
                        "tools": ["read_file", "write_file", "edit_file", "patch_file", "delete_file", "copy_file", "rename_file", "find_files", "search_files", "list_files"],
                        "trust": "WORKSPACE",
                    },
                    "git_operations": {
                        "tools": ["git_status", "git_add", "git_commit", "git_diff", "git_log", "git_show", "git_blame", "git_branch", "git_checkout", "git_merge"],
                        "trust": "WORKSPACE",
                    },
                    "shell": {
                        "tools": ["run_command", "mkdir"],
                        "trust": "FULL_WRITE",
                    },
                    "environment": {
                        "tools": ["get_env", "list_env"],
                        "trust": "READ_ONLY",
                    },
                    "undo": {
                        "tools": ["undo_file", "restore_file", "list_backups"],
                        "trust": "WORKSPACE",
                    },
                    "research": {
                        "tools": ["github_research"],
                        "trust": "READ_ONLY",
                    },
                },
                "trust_levels": {
                    "NONE": "No access",
                    "READ_ONLY": "Can only read",
                    "SAFE_WRITE": "Can write with restrictions",
                    "FULL_WRITE": "Full write access",
                },
                "profiles": {
                    "MINIMAL": "Essential tools only",
                    "STANDARD": "Common development tools",
                    "DEVELOPER": "Full development toolkit",
                    "FULL": "All tools including shell",
                },
            },
            indent=2,
        )

    @mcp.resource("sunwell://reference/validators")
    def validators_reference() -> str:
        """Available validators organized by domain."""
        return json.dumps(
            {
                "code": {
                    "syntax": {"description": "Check syntax validity", "blocking": True},
                    "lint": {"description": "Run linting checks", "blocking": False},
                    "type": {"description": "Type checking", "blocking": False},
                    "test": {"description": "Run related tests", "blocking": True},
                },
                "research": {
                    "sources": {"description": "Check claims are backed by sources", "blocking": True},
                    "coherence": {"description": "Check argument coherence", "blocking": False},
                },
                "lens_provided": {
                    "deterministic": {"description": "Script-based, reproducible checks"},
                    "heuristic": {"description": "AI-based judgment calls"},
                    "schema": {"description": "Lens-provided artifact validation (RFC-035)"},
                },
            },
            indent=2,
        )

    @mcp.resource("sunwell://reference/models")
    def models_reference() -> str:
        """Available models and their strengths."""
        try:
            from sunwell.models.registry.registry import DEFAULT_ALIASES, get_registry

            registry = get_registry()
            registered = registry.list_registered()

            return json.dumps(
                {
                    "registered_models": registered,
                    "default_aliases": DEFAULT_ALIASES,
                    "tiers": {
                        "smart": {
                            "description": "High intelligence, higher cost",
                            "good_for": ["complex reasoning", "architecture", "debugging", "planning"],
                            "aliases": ["anthropic-smart", "openai-smart", "ollama-smart"],
                        },
                        "cheap": {
                            "description": "Fast and affordable",
                            "good_for": ["formatting", "simple edits", "classification", "renaming"],
                            "aliases": ["anthropic-cheap", "openai-cheap", "ollama-cheap"],
                        },
                    },
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})
