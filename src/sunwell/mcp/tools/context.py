"""MCP context packaging tools for external agent workers.

When an external agent claims a goal, they need enough context to execute
independently. This module packages relevant information:
- Goal description and constraints
- Relevant file contents (from knowledge index)
- Dependency artifacts (what upstream goals produced)
- Scope limits (max files, forbidden paths)
- Lens context (expertise/heuristics for this domain)

Inspired by: "Workers are unaware of the larger system. They don't
communicate with any other planners or workers."
(Cursor self-driving codebases research, Feb 2026)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Maximum file content to include in context (to avoid huge payloads)
MAX_FILE_PREVIEW_CHARS = 2000
MAX_FILES_IN_CONTEXT = 10


def register_context_tools(mcp: FastMCP, workspace_dir: str | None = None) -> None:
    """Register context packaging tools for MCP workers.

    Args:
        mcp: FastMCP server instance
        workspace_dir: Optional workspace directory
    """

    def _get_workspace() -> Path:
        """Resolve workspace directory."""
        if workspace_dir:
            return Path(workspace_dir)
        return Path.cwd()

    @mcp.tool()
    def sunwell_get_goal_context(goal_id: str) -> str:
        """
        Get full execution context for a claimed goal.

        Returns everything an external agent needs to execute a goal
        independently: description, relevant files, dependency info,
        scope limits, and expertise guidance.

        Call this after claiming a goal with sunwell_claim_goal().

        Args:
            goal_id: ID of the goal to get context for

        Returns:
            JSON with comprehensive goal context including:
            - goal: Full goal details
            - relevant_files: File contents relevant to the goal
            - dependencies: What upstream goals produced
            - scope: Constraints on what can be modified
            - expertise: Domain-specific guidance
            - instructions: Step-by-step execution guidance
        """
        try:
            from sunwell.features.backlog.manager import BacklogManager

            workspace = _get_workspace()
            manager = BacklogManager(root=workspace)

            goal = manager.backlog.goals.get(goal_id)
            if goal is None:
                return json.dumps({
                    "error": f"Goal '{goal_id}' not found",
                }, indent=2)

            # Build context package
            context: dict = {
                "goal": {
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "category": goal.category,
                    "task_type": goal.task_type,
                    "estimated_complexity": goal.estimated_complexity,
                    "requires": list(goal.requires),
                    "produces": list(goal.produces),
                },
                "scope": {
                    "max_files": goal.scope.max_files,
                    "max_lines_changed": goal.scope.max_lines_changed,
                    "allowed_paths": [
                        str(p) for p in goal.scope.allowed_paths
                    ] if goal.scope.allowed_paths else [],
                    "forbidden_paths": [
                        str(p) for p in goal.scope.forbidden_paths
                    ] if goal.scope.forbidden_paths else [],
                },
                "relevant_files": _gather_relevant_files(
                    workspace, goal
                ),
                "dependencies": _gather_dependency_context(
                    manager, goal
                ),
                "expertise": _gather_expertise(workspace, goal),
                "instructions": _build_execution_instructions(goal),
            }

            return json.dumps(context, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


def _gather_relevant_files(workspace: Path, goal) -> list[dict]:
    """Gather file contents relevant to the goal.

    Uses the goal's scope and description to identify relevant files.

    Args:
        workspace: Workspace root
        goal: The goal to find files for

    Returns:
        List of file info dicts with path and preview content
    """
    files: list[dict] = []

    # 1. Check scope allowed_paths
    if goal.scope.allowed_paths:
        for path in goal.scope.allowed_paths:
            full_path = workspace / path if not Path(path).is_absolute() else Path(path)
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text(errors="ignore")
                    files.append({
                        "path": str(path),
                        "content": content[:MAX_FILE_PREVIEW_CHARS],
                        "truncated": len(content) > MAX_FILE_PREVIEW_CHARS,
                        "total_lines": content.count("\n") + 1,
                        "source": "scope_allowed",
                    })
                except OSError:
                    pass

            if len(files) >= MAX_FILES_IN_CONTEXT:
                break

    # 2. Look for files matching goal keywords in description
    if len(files) < MAX_FILES_IN_CONTEXT:
        keywords = _extract_file_hints(goal.description)
        for keyword in keywords[:5]:
            # Simple glob for matching files
            for match in workspace.rglob(f"*{keyword}*"):
                if match.is_file() and match.suffix in (".py", ".ts", ".js", ".go", ".rs"):
                    # Skip hidden/excluded directories
                    parts = match.relative_to(workspace).parts
                    if any(p.startswith(".") or p in ("__pycache__", "node_modules") for p in parts):
                        continue

                    rel_path = str(match.relative_to(workspace))
                    if any(f["path"] == rel_path for f in files):
                        continue  # Already included

                    try:
                        content = match.read_text(errors="ignore")
                        files.append({
                            "path": rel_path,
                            "content": content[:MAX_FILE_PREVIEW_CHARS],
                            "truncated": len(content) > MAX_FILE_PREVIEW_CHARS,
                            "total_lines": content.count("\n") + 1,
                            "source": "keyword_match",
                        })
                    except OSError:
                        pass

                    if len(files) >= MAX_FILES_IN_CONTEXT:
                        break

    return files


def _gather_dependency_context(manager, goal) -> dict:
    """Gather context about what upstream goals produced.

    Args:
        manager: BacklogManager instance
        goal: The goal to check dependencies for

    Returns:
        Dict with dependency information
    """
    dependencies: dict = {
        "required_goal_ids": list(goal.requires),
        "completed_dependencies": [],
        "pending_dependencies": [],
    }

    for dep_id in goal.requires:
        dep_goal = manager.backlog.goals.get(dep_id)
        if dep_goal is None:
            dependencies["pending_dependencies"].append({
                "id": dep_id,
                "status": "not_found",
            })
            continue

        is_completed = dep_id in manager.backlog.completed
        entry = {
            "id": dep_id,
            "title": dep_goal.title,
            "status": "completed" if is_completed else "pending",
            "produces": list(dep_goal.produces),
        }

        if is_completed:
            dependencies["completed_dependencies"].append(entry)
        else:
            dependencies["pending_dependencies"].append(entry)

    dependencies["all_deps_met"] = len(dependencies["pending_dependencies"]) == 0

    return dependencies


def _gather_expertise(workspace: Path, goal) -> dict:
    """Gather domain-specific expertise for the goal.

    Tries to load relevant lens context based on the goal's category.

    Args:
        workspace: Workspace root
        goal: The goal to find expertise for

    Returns:
        Dict with expertise guidance
    """
    expertise: dict = {
        "category": goal.category,
        "guidance": [],
    }

    # Map categories to general guidance
    category_guidance = {
        "fix": [
            "Reproduce the issue first before fixing",
            "Add a regression test alongside the fix",
            "Minimize the scope of changes",
        ],
        "improve": [
            "Preserve existing behavior while enhancing",
            "Consider backward compatibility",
            "Measure improvement where possible",
        ],
        "add": [
            "Follow existing project conventions",
            "Add tests for new functionality",
            "Document public APIs",
        ],
        "refactor": [
            "Ensure all existing tests pass before and after",
            "Make atomic changes that can be independently verified",
            "Don't change behavior -- only structure",
        ],
        "test": [
            "Cover edge cases and error paths",
            "Use descriptive test names",
            "Follow existing test patterns in the project",
        ],
        "document": [
            "Write for the target audience, not yourself",
            "Include code examples where helpful",
            "Keep documentation close to the code it describes",
        ],
        "security": [
            "Follow OWASP guidelines for the relevant category",
            "Don't just fix the symptom -- address the root cause",
            "Add security-specific tests",
        ],
        "performance": [
            "Profile before optimizing -- measure don't guess",
            "Consider trade-offs (memory vs. CPU, readability vs. speed)",
            "Add benchmarks alongside optimizations",
        ],
    }

    guidance = category_guidance.get(goal.category, [])
    expertise["guidance"] = guidance

    # Try to detect project type for additional context
    if (workspace / "pyproject.toml").exists():
        expertise["project_type"] = "python"
        expertise["guidance"].append("Follow PEP 8 and type hint all new code")
    elif (workspace / "package.json").exists():
        expertise["project_type"] = "javascript"
    elif (workspace / "Cargo.toml").exists():
        expertise["project_type"] = "rust"

    return expertise


def _build_execution_instructions(goal) -> str:
    """Build step-by-step execution instructions for the goal.

    Args:
        goal: The goal to build instructions for

    Returns:
        Formatted instructions string
    """
    lines = [
        f"## Execute: {goal.title}",
        "",
        goal.description,
        "",
        "### Constraints",
        f"- Maximum files to modify: {goal.scope.max_files}",
        f"- Maximum lines changed: {goal.scope.max_lines_changed}",
    ]

    if goal.scope.forbidden_paths:
        lines.append(f"- Do NOT modify: {', '.join(str(p) for p in goal.scope.forbidden_paths)}")

    lines.extend([
        "",
        "### When Done",
        "Call `sunwell_submit_handoff()` with:",
        "- success: true/false",
        "- summary: Brief description of what you did",
        "- files_changed: Comma-separated list of modified files",
        "- findings: Things you discovered (comma-separated)",
        "- concerns: Risks or issues to flag (comma-separated)",
        "- suggestions: Ideas for follow-up work (comma-separated)",
        "",
        "### If You Cannot Complete",
        "Call `sunwell_release_goal()` to release the claim.",
    ])

    return "\n".join(lines)


def _extract_file_hints(description: str) -> list[str]:
    """Extract potential file/module names from a goal description.

    Simple heuristic: look for words that could be file paths or module names.

    Args:
        description: Goal description text

    Returns:
        List of potential file name keywords
    """
    import re

    hints: list[str] = []

    # Look for quoted paths
    quoted = re.findall(r'["`\']([\w/._-]+)["`\']', description)
    hints.extend(quoted)

    # Look for dotted module names (e.g., auth.middleware)
    dotted = re.findall(r'\b(\w+\.\w+(?:\.\w+)*)\b', description)
    for d in dotted:
        if not d[0].isdigit():  # Skip version numbers
            hints.append(d.replace(".", "/"))

    # Look for snake_case identifiers that might be filenames
    snake = re.findall(r'\b([a-z][a-z_]+(?:_[a-z]+)+)\b', description)
    hints.extend(snake[:3])

    return list(dict.fromkeys(hints))[:10]  # Deduplicate, cap at 10
