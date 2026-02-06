"""MCP Resource definitions for Sunwell.

Resources are read-only data endpoints that expose Sunwell's configuration,
lens registry, memory state, and reference content to MCP clients.

Resource URIs:
- sunwell://map                       - Capabilities overview and routing guide
- sunwell://config                    - Current configuration summary
- sunwell://status                    - System health and stats
- sunwell://lenses                    - Dynamic lens list
- sunwell://lenses/minimal            - Names and domains only (low token)
- sunwell://lenses/registry           - Full registry with shortcuts and overrides
- sunwell://shortcuts                 - Dynamic shortcut map
- sunwell://projects                  - Known projects with metadata
- sunwell://briefing                  - Current rolling briefing (full prompt)
- sunwell://briefing/summary          - Mission + status + hazards only (low token)
- sunwell://learnings                 - Recent learnings from past sessions
- sunwell://learnings/summary         - Count + top-5 most-used (low token)
- sunwell://deadends                  - Known dead ends and failed approaches
- sunwell://constraints               - Active constraints and guardrails
- sunwell://goals                     - Current active goals
- sunwell://goals/summary             - Counts by status only (low token)
- sunwell://goals/blocked             - Blocked goals with reasons
- sunwell://reference/domains         - Available domains and capabilities
- sunwell://reference/tools           - Available tool catalog
- sunwell://reference/validators      - Available validators by domain
- sunwell://reference/models          - Available models and strengths
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import mcp_json, omit_empty, truncate

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.mcp.runtime import MCPRuntime


def register_resources(
    mcp: FastMCP,
    runtime: MCPRuntime | None = None,
    lenses_dir: str | None = None,
) -> None:
    """Register all Sunwell resources with the MCP server.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and subsystem access
        lenses_dir: Optional path to lenses directory
    """

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

## Format Tiers

Most tools accept a `format` parameter:
- **summary**: Minimal output — counts, IDs, status only. Use when scanning.
- **compact** (default): Core fields with truncated text. Use for regular work.
- **full**: Everything untruncated. Use only when you need the complete payload.

## Thin Mode

Tools returning large injectable content support `include_context=False`:
- `sunwell_lens(name, include_context=False)` — metadata only (~200 tokens vs 5-15k)
- `sunwell_route(command, include_context=False)` — routing only, no context

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

## Resources (summary tiers for low-token access)

| Full resource           | Summary resource              | Use case                    |
|-------------------------|-------------------------------|-----------------------------|
| `sunwell://briefing`    | `sunwell://briefing/summary`  | Quick status check          |
| `sunwell://learnings`   | `sunwell://learnings/summary` | Learning count + top-5      |
| `sunwell://goals`       | `sunwell://goals/summary`     | Goal counts by status       |
| `sunwell://lenses`      | `sunwell://lenses/minimal`    | Just names and domains      |
"""

    @mcp.resource("sunwell://config")
    def config_resource() -> str:
        """Current Sunwell configuration summary."""
        try:
            from sunwell.foundation.config import get_config

            config = get_config()
            return mcp_json(omit_empty({
                "verbose": config.verbose,
                "debug": config.debug,
                "model": {
                    "default": getattr(config.model, "default", None),
                } if hasattr(config, "model") else None,
                "embedding": {
                    "provider": getattr(config.embedding, "provider", None),
                } if hasattr(config, "embedding") else None,
            }), "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://status")
    def status_resource() -> str:
        """System health: memory stats, model availability."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            status: dict = {"workspace": str(ws)}

            # Memory stats — use runtime cache
            memory = runtime.memory if runtime else None
            if memory is not None:
                status["memory"] = {
                    "learnings": memory.learning_count,
                    "decisions": memory.decision_count,
                    "failures": memory.failure_count,
                    "has_simulacrum": memory.simulacrum is not None,
                    "has_team": memory.team is not None,
                }
            else:
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
                status["models"] = {"registered": registry.list_registered()}
            except Exception:
                status["models"] = {"available": False}

            # Briefing
            try:
                from sunwell.memory.briefing import Briefing

                briefing = Briefing.load(ws)
                status["briefing"] = omit_empty({
                    "available": briefing is not None,
                    "status": briefing.status.value if briefing and hasattr(briefing.status, "value") else None,
                    "mission": truncate(briefing.mission, 120) if briefing else None,
                })
            except Exception:
                status["briefing"] = {"available": False}

            return mcp_json(status, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

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
                lenses.append(omit_empty({
                    "name": entry.lens.metadata.name,
                    "domain": entry.lens.metadata.domain,
                    "layer": entry.layer,
                    "description": truncate(entry.lens.metadata.description, 120),
                }))

            return mcp_json({"lenses": lenses, "total": len(lenses)}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://lenses/minimal")
    def lenses_minimal_resource() -> str:
        """Lens names and domains only — lowest token cost."""
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

            lenses = [
                {"name": e.lens.metadata.name, "domain": e.lens.metadata.domain}
                for e in registry.all_entries()
            ]

            return mcp_json({"lenses": lenses, "total": len(lenses)}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

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

            return mcp_json(omit_empty({
                "summary": summary,
                "shortcuts": dict(registry.shortcuts),
                "overrides": overrides if overrides else None,
                "collisions": collisions if collisions else None,
            }), "full")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

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

            return mcp_json(dict(registry.shortcuts), "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

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
                    projects.append(omit_empty({
                        "id": proj.id,
                        "path": str(proj.path),
                        "role": proj.role.value if hasattr(proj.role, "value") else str(proj.role),
                        "is_primary": proj.is_primary,
                    }))

            return mcp_json({"projects": projects, "total": len(projects)}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e), "projects": []}, "compact")

    # =========================================================================
    # Memory Resources
    # =========================================================================

    @mcp.resource("sunwell://briefing")
    def briefing_resource() -> str:
        """Current rolling briefing — the single most useful context blob (full prompt)."""
        try:
            from sunwell.memory.briefing import Briefing

            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            briefing = Briefing.load(ws)
            if not briefing:
                return mcp_json({"status": "no_briefing", "message": "No briefing found."}, "compact")

            return briefing.to_prompt()
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://briefing/summary")
    def briefing_summary_resource() -> str:
        """Briefing summary — mission + status + hazards only (low token)."""
        try:
            from sunwell.memory.briefing import Briefing

            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            briefing = Briefing.load(ws)
            if not briefing:
                return mcp_json({"status": "no_briefing"}, "compact")

            return mcp_json(omit_empty({
                "mission": truncate(briefing.mission, 120),
                "status": briefing.status.value if hasattr(briefing.status, "value") else str(briefing.status),
                "next_action": truncate(briefing.next_action, 120),
                "hazards": list(briefing.hazards),
                "suggested_lens": briefing.suggested_lens,
                "complexity_estimate": briefing.complexity_estimate,
            }), "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://learnings")
    def learnings_resource() -> str:
        """Recent learnings extracted from past sessions (full)."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return mcp_json({"learnings": [], "message": "No simulacrum store available."}, "compact")

            try:
                dag = memory.simulacrum.get_dag()
                all_learnings = dag.get_learnings()
                return mcp_json({
                    "learnings": [
                        omit_empty({
                            "fact": l.fact if hasattr(l, "fact") else str(l),
                            "category": getattr(l, "category", None),
                            "confidence": getattr(l, "confidence", None),
                            "use_count": getattr(l, "use_count", 0),
                        })
                        for l in all_learnings[:50]
                    ],
                    "total": len(all_learnings),
                }, "full")
            except Exception as e:
                return mcp_json({"error": str(e), "learnings": []}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://learnings/summary")
    def learnings_summary_resource() -> str:
        """Learning count + top-5 most-used (low token)."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return mcp_json({"total": 0}, "compact")

            try:
                dag = memory.simulacrum.get_dag()
                all_learnings = dag.get_learnings()
                # Sort by use_count descending for top-5
                sorted_learnings = sorted(
                    all_learnings,
                    key=lambda l: getattr(l, "use_count", 0),
                    reverse=True,
                )
                return mcp_json({
                    "total": len(all_learnings),
                    "top_5": [
                        truncate(l.fact if hasattr(l, "fact") else str(l), 120)
                        for l in sorted_learnings[:5]
                    ],
                }, "compact")
            except Exception as e:
                return mcp_json({"error": str(e), "total": 0}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://deadends")
    def deadends_resource() -> str:
        """Known dead ends and failed approaches — avoid repeating mistakes."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return mcp_json({"dead_ends": [], "message": "No simulacrum store available."}, "compact")

            dead_ends = memory.simulacrum.get_dead_ends()
            return mcp_json({
                "dead_ends": [str(de) for de in dead_ends[:30]],
                "total": len(dead_ends),
            }, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://constraints")
    def constraints_resource() -> str:
        """Active constraints and guardrails from memory."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            if not memory.simulacrum:
                return mcp_json({"constraints": [], "message": "No simulacrum store available."}, "compact")

            try:
                dag = memory.simulacrum.get_dag()
                all_learnings = dag.get_learnings()
                constraints = [
                    omit_empty({
                        "fact": l.fact if hasattr(l, "fact") else str(l),
                        "confidence": getattr(l, "confidence", None),
                    })
                    for l in all_learnings
                    if getattr(l, "category", None) == "constraint"
                ]
                return mcp_json({"constraints": constraints, "total": len(constraints)}, "compact")
            except Exception as e:
                return mcp_json({"error": str(e), "constraints": []}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    # =========================================================================
    # Backlog Resources
    # =========================================================================

    @mcp.resource("sunwell://goals")
    def goals_resource() -> str:
        """Current active goals from the backlog DAG."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()

            # Use runtime-cached backlog or create fresh
            manager = runtime.backlog if runtime else None
            if manager is None:
                from sunwell.features.backlog.manager import BacklogManager
                manager = BacklogManager(root=ws)

            if runtime:
                backlog = runtime.run(manager.refresh())
            else:
                backlog = manager.backlog

            active = []
            for goal_id, goal in backlog.goals.items():
                if goal_id not in backlog.completed:
                    active.append(omit_empty({
                        "id": goal.id,
                        "title": goal.title,
                        "priority": goal.priority,
                        "category": goal.category,
                        "goal_type": getattr(goal, "goal_type", "task"),
                        "in_progress": goal_id == backlog.in_progress,
                        "blocked": goal_id in backlog.blocked,
                    }))

            active.sort(key=lambda g: g.get("priority", 0), reverse=True)
            return mcp_json({"goals": active, "total": len(active)}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e), "goals": []}, "compact")

    @mcp.resource("sunwell://goals/summary")
    def goals_summary_resource() -> str:
        """Goal counts by status only (low token)."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()

            manager = runtime.backlog if runtime else None
            if manager is None:
                from sunwell.features.backlog.manager import BacklogManager
                manager = BacklogManager(root=ws)

            if runtime:
                backlog = runtime.run(manager.refresh())
            else:
                backlog = manager.backlog

            total = len(backlog.goals)
            completed = len(backlog.completed)
            blocked = len(backlog.blocked)
            pending = total - completed - blocked

            return mcp_json({
                "total": total,
                "completed": completed,
                "blocked": blocked,
                "pending": pending,
                "in_progress": backlog.in_progress is not None,
            }, "compact")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

    @mcp.resource("sunwell://goals/blocked")
    def goals_blocked_resource() -> str:
        """Blocked goals with reasons."""
        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()

            manager = runtime.backlog if runtime else None
            if manager is None:
                from sunwell.features.backlog.manager import BacklogManager
                manager = BacklogManager(root=ws)

            if runtime:
                backlog = runtime.run(manager.refresh())
            else:
                backlog = manager.backlog

            blocked = []
            for goal_id, reason in backlog.blocked.items():
                goal = backlog.goals.get(goal_id)
                if goal:
                    blocked.append(omit_empty({
                        "id": goal.id,
                        "title": goal.title,
                        "reason": reason,
                        "requires": list(goal.requires),
                    }))

            return mcp_json({"blocked_goals": blocked, "total": len(blocked)}, "compact")
        except Exception as e:
            return mcp_json({"error": str(e), "blocked_goals": []}, "compact")

    # =========================================================================
    # Reference Resources
    # =========================================================================

    @mcp.resource("sunwell://reference/domains")
    def domains_reference() -> str:
        """Available domains and their capabilities."""
        return mcp_json({
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
        }, "full")

    @mcp.resource("sunwell://reference/tools")
    def tools_reference() -> str:
        """Available tool catalog with trust levels."""
        return mcp_json({
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
        }, "full")

    @mcp.resource("sunwell://reference/validators")
    def validators_reference() -> str:
        """Available validators organized by domain."""
        return mcp_json({
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
        }, "full")

    @mcp.resource("sunwell://reference/models")
    def models_reference() -> str:
        """Available models and their strengths."""
        try:
            from sunwell.models.registry.registry import DEFAULT_ALIASES, get_registry

            registry = get_registry()
            registered = registry.list_registered()

            return mcp_json({
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
            }, "full")
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")
