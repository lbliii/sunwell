"""SessionContext — All session state in one object (RFC-MEMORY).

SessionContext consolidates all session-related state:
- Project detection (from cli/helpers.py, inlined)
- Briefing loading (from Agent._load_briefing, moved)
- Goal and execution state
- Prompt formatting

This replaces RunRequest as THE input contract for Agent.run().

Example:
    >>> session = SessionContext.build(workspace, "add auth", RunOptions())
    >>> memory = PersistentMemory.load(workspace)
    >>> async for event in agent.run(session, memory):
    ...     print(event)
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sunwell.agent.utils.request import RunOptions
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.briefing import Briefing
    from sunwell.planning.naaru.types import Task


class SpawnDepthExceededError(Exception):
    """Raised when spawn depth limit is exceeded."""

    def __init__(self, depth: int, max_depth: int = 3) -> None:
        self.depth = depth
        self.max_depth = max_depth
        super().__init__(f"Spawn depth {depth} exceeds maximum {max_depth}")


@dataclass(slots=True)
class SessionContext:
    """Everything about THIS execution.

    Consolidates:
    - Project detection (from cli/helpers.py)
    - Briefing loading (from Agent._load_briefing)
    - Goal and execution state
    - Prompt formatting

    SessionContext is disposable after each run, unlike PersistentMemory
    which persists across sessions.
    """

    # === IDENTITY ===
    session_id: str
    """Unique session identifier."""

    cwd: Path
    """Working directory for this session."""

    goal: str
    """Natural language goal (shortcuts already expanded)."""

    # === WORKSPACE (from build_workspace_context) ===
    project_name: str
    """Name of the project (directory name)."""

    project_type: str
    """Detected project type: python, javascript, go, rust, unknown."""

    framework: str | None
    """Detected framework: fastapi, flask, react, etc."""

    key_files: list[tuple[str, str]]
    """List of (filename, preview) tuples for key project files."""

    entry_points: list[str]
    """List of entry point files."""

    directory_tree: str
    """Directory tree string for context."""

    # === BRIEFING (from previous session) ===
    briefing: Briefing | None = None
    """Rolling handoff note from previous session."""

    # === OPTIONS ===
    trust: str = "workspace"
    """Tool trust level: 'read_only', 'workspace', or 'shell'."""

    timeout: int = 300
    """Maximum execution time in seconds."""

    model_name: str = "default"
    """Model identifier."""

    lens: Lens | None = None
    """Active lens for expertise injection."""

    options: RunOptions | None = None
    """Full execution options (RFC-137: includes delegation config)."""

    # === WORKSPACE CONTEXT (multi-project architecture) ===
    workspace_id: str | None = None
    """Workspace container ID for multi-project context."""

    project_id: str | None = None
    """Project ID within the workspace (if workspace_id is set)."""

    # === SUBAGENT COORDINATION (Agentic Infrastructure Upgrade) ===
    parent_session_id: str | None = None
    """Parent session ID if this is a subagent. None for root sessions."""

    spawn_depth: int = 0
    """Nesting depth (0 = root session, 1 = first-level subagent, etc.)."""

    cleanup_policy: Literal["delete", "keep"] = "keep"
    """What to do with session state after completion.
    
    - 'delete': Remove session artifacts after completion (for ephemeral subagents)
    - 'keep': Preserve session artifacts (default, for debugging/resumption)
    """

    # === EXECUTION STATE (updated during run) ===
    tasks: list[Task] = field(default_factory=list)
    """Tasks in the current plan."""

    current_task: Task | None = None
    """Currently executing task."""

    artifacts_created: list[str] = field(default_factory=list)
    """Paths of artifacts created during execution."""

    files_modified: list[str] = field(default_factory=list)
    """Paths of files modified during execution."""

    # === METADATA ===
    started_at: datetime = field(default_factory=datetime.now)
    """When this session started."""

    # === BUILD ===
    @classmethod
    def build(
        cls,
        cwd: Path,
        goal: str,
        options: RunOptions | None = None,
        lens: Lens | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> SessionContext:
        """Build session context from workspace.

        Detects project type and framework, finds key files with previews,
        builds directory tree, and loads briefing from previous session.

        Args:
            cwd: Working directory
            goal: Natural language goal
            options: Execution options (or defaults)
            lens: Explicit lens or None for auto-selection
            workspace_id: Optional workspace container ID for multi-project context
            project_id: Optional project ID within the workspace

        Returns:
            SessionContext ready for Agent.run()
        """
        cwd = Path(cwd).resolve()

        # Set defaults if options not provided
        if options is None:
            from sunwell.agent.utils.request import RunOptions
            options = RunOptions()

        # Detect project type and framework
        project_type, framework = _detect_project_type(cwd)

        # Find key files with previews
        key_files = _find_key_files(cwd)

        # Find entry points
        entry_points = _find_entry_points(cwd, project_type)

        # Build directory tree
        directory_tree = _build_directory_tree(cwd)

        # Load briefing from previous session
        briefing = _load_briefing(cwd)

        return cls(
            session_id=_generate_session_id(),
            cwd=cwd,
            goal=goal,
            project_name=cwd.name,
            project_type=project_type,
            framework=framework,
            key_files=key_files,
            entry_points=entry_points,
            directory_tree=directory_tree,
            briefing=briefing,
            trust=options.trust,
            timeout=options.timeout_seconds,
            model_name="default",  # Resolved later
            lens=lens,
            options=options,  # RFC-137: Full options for delegation config
            workspace_id=workspace_id,
            project_id=project_id or cwd.name,
        )

    @classmethod
    def spawn_child(
        cls,
        parent: SessionContext,
        task: str,
        cleanup: Literal["delete", "keep"] = "delete",
        max_depth: int = 3,
    ) -> SessionContext:
        """Spawn a child session for a subagent.

        Creates a new session that inherits workspace context from parent
        but has its own session_id and tracks its relationship to parent.

        Args:
            parent: Parent session to spawn from
            task: Goal/task for the child session
            cleanup: Cleanup policy for child session artifacts
            max_depth: Maximum allowed nesting depth

        Returns:
            New SessionContext for the subagent

        Raises:
            SpawnDepthExceededError: If parent.spawn_depth >= max_depth
        """
        if parent.spawn_depth >= max_depth:
            raise SpawnDepthExceededError(parent.spawn_depth, max_depth)

        return cls(
            session_id=_generate_session_id(),
            cwd=parent.cwd,
            goal=task,
            project_name=parent.project_name,
            project_type=parent.project_type,
            framework=parent.framework,
            key_files=parent.key_files,
            entry_points=parent.entry_points,
            directory_tree=parent.directory_tree,
            briefing=parent.briefing,
            trust=parent.trust,
            timeout=parent.timeout,
            model_name=parent.model_name,
            lens=parent.lens,
            options=parent.options,
            workspace_id=parent.workspace_id,
            project_id=parent.project_id,
            parent_session_id=parent.session_id,
            spawn_depth=parent.spawn_depth + 1,
            cleanup_policy=cleanup,
        )

    @property
    def is_subagent(self) -> bool:
        """True if this is a child session (has a parent)."""
        return self.parent_session_id is not None

    @property
    def is_root(self) -> bool:
        """True if this is a root session (no parent)."""
        return self.parent_session_id is None

    # === PROMPTS ===

    def to_planning_prompt(self) -> str:
        """Format session context for planning prompt.

        Includes workspace info, briefing, and any prefetched context.
        """
        lines = [
            "## Workspace Context",
            "",
            f"**Project**: `{self.project_name}` ({self.cwd})",
        ]

        # Project type badge
        if self.project_type != "unknown":
            type_line = f"**Type**: {self.project_type.title()}"
            if self.framework:
                type_line += f" ({self.framework})"
            lines.append(type_line)

        lines.append("")

        # Key files with preview
        if self.key_files:
            lines.append("### Key Files")
            for name, preview in self.key_files[:3]:  # Limit to 3
                lines.append(f"\n**{name}**:")
                lines.append("```")
                lines.append(preview)
                lines.append("```")
            lines.append("")

        # Entry points
        if self.entry_points:
            lines.append(
                f"**Entry points**: {', '.join(f'`{e}`' for e in self.entry_points)}"
            )
            lines.append("")

        # Directory tree
        if self.directory_tree:
            lines.append("### Structure")
            lines.append("```")
            lines.append(self.directory_tree)
            lines.append("```")

        lines.append("")
        lines.append("You can reference files by their relative paths.")

        # Add briefing if available
        if self.briefing:
            lines.append("")
            lines.append(self.briefing.to_prompt())

        return "\n".join(lines)

    def to_task_prompt(self, task: Task) -> str:
        """Format context for task execution.

        Args:
            task: The task being executed

        Returns:
            Formatted prompt string with task-specific context
        """
        lines = [
            f"## Task: {task.description}",
            "",
            f"**Mode**: {task.mode.value if hasattr(task.mode, 'value') else task.mode}",
        ]

        if task.target_path:
            lines.append(f"**Target**: `{task.target_path}`")

        if task.depends_on:
            lines.append(f"**Dependencies**: {', '.join(task.depends_on)}")

        lines.append("")
        lines.append(f"**Project**: {self.project_type}")
        if self.framework:
            lines.append(f"**Framework**: {self.framework}")

        # Add hazards from briefing
        if self.briefing and self.briefing.hazards:
            lines.append("")
            lines.append("**Hazards to avoid:**")
            for h in self.briefing.hazards:
                lines.append(f"- ⚠️ {h}")

        return "\n".join(lines)

    # === BRIEFING ===

    def save_briefing(self) -> None:
        """Save updated briefing for next session."""
        from sunwell.memory.briefing import (
            BriefingStatus,
            ExecutionSummary,
            compress_briefing,
        )

        # Determine status
        completed_ids = [
            c.id for c in self.tasks if hasattr(c, "completed") and c.completed
        ]
        all_done = self.tasks and all(t.id in completed_ids for t in self.tasks)
        status = BriefingStatus.COMPLETE if all_done else BriefingStatus.IN_PROGRESS

        # Build execution summary
        completed_count = len([t for t in self.tasks if hasattr(t, "completed") and t.completed])
        next_action = (
            None if status == BriefingStatus.COMPLETE
            else "Continue from previous session"
        )
        summary = ExecutionSummary(
            last_action=f"Worked on: {self.goal[:100]}",
            next_action=next_action,
            modified_files=tuple(self.files_modified[:10]),
            tasks_completed=completed_count,
            gates_passed=0,
            new_learnings=(),
        )

        # Compress and save
        new_briefing = compress_briefing(
            old_briefing=self.briefing,
            summary=summary,
            new_status=status,
        )
        new_briefing.save(self.cwd)

    # === UTILITIES ===

    def summary(self) -> dict[str, Any]:
        """Generate summary dict for completion event."""
        result = {
            "session_id": self.session_id,
            "goal": self.goal[:100],
            "project_type": self.project_type,
            "framework": self.framework,
            "tasks_total": len(self.tasks),
            "artifacts_created": len(self.artifacts_created),
            "files_modified": len(self.files_modified),
        }
        # Include subagent info if applicable
        if self.is_subagent:
            result["parent_session_id"] = self.parent_session_id
            result["spawn_depth"] = self.spawn_depth
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/UI consumption."""
        return {
            "session_id": self.session_id,
            "cwd": str(self.cwd),
            "goal": self.goal,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "framework": self.framework,
            "key_files": self.key_files,
            "entry_points": self.entry_points,
            "has_briefing": self.briefing is not None,
            "trust": self.trust,
            "timeout": self.timeout,
            "started_at": self.started_at.isoformat(),
            # Subagent coordination
            "parent_session_id": self.parent_session_id,
            "spawn_depth": self.spawn_depth,
            "cleanup_policy": self.cleanup_policy,
            "is_subagent": self.is_subagent,
        }


# =============================================================================
# Helper Functions (inlined from cli/helpers.py)
# =============================================================================


def _generate_session_id() -> str:
    """Generate unique session ID."""
    return uuid.uuid4().hex[:16]


def _detect_python_framework(cwd: Path) -> str | None:
    """Detect Python framework from dependencies, not file names.
    
    Checks pyproject.toml and requirements.txt for actual framework imports.
    """
    framework_deps = {
        "django": "django",
        "flask": "flask",
        "fastapi": "fastapi",
        "starlette": "starlette",
        "tornado": "tornado",
    }

    # Check pyproject.toml dependencies
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(errors="ignore").lower()
            for framework, dep in framework_deps.items():
                if f'"{dep}"' in content or f"'{dep}'" in content or f"{dep} =" in content:
                    return framework
        except OSError:
            pass

    # Check requirements.txt
    for req_file in ["requirements.txt", "requirements/base.txt"]:
        req_path = cwd / req_file
        if req_path.exists():
            try:
                content = req_path.read_text(errors="ignore").lower()
                for framework, dep in framework_deps.items():
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith(dep) and (len(line) == len(dep) or line[len(dep)] in "=<>~["):
                            return framework
            except OSError:
                pass

    # Fallback: Check manage.py for Django
    if (cwd / "manage.py").exists():
        return "django"

    # Fallback: Check main.py/app.py for framework imports
    for entry in ["main.py", "app.py"]:
        entry_path = cwd / entry
        if entry_path.exists():
            try:
                content = entry_path.read_text(errors="ignore")[:2000]
                if "from fastapi" in content or "import fastapi" in content:
                    return "fastapi"
                if "from flask" in content or "import flask" in content:
                    return "flask"
            except OSError:
                pass

    return None


def _detect_project_type(cwd: Path) -> tuple[str, str | None]:
    """Detect project type and framework from directory contents."""
    ptype = "unknown"
    framework = None

    # Python indicators
    if (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
        ptype = "python"
        framework = _detect_python_framework(cwd)

    # JavaScript/TypeScript indicators
    elif (cwd / "package.json").exists():
        ptype = "javascript"
        try:
            pkg = json.loads((cwd / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "react" in deps:
                framework = "react"
            elif "vue" in deps:
                framework = "vue"
            elif "next" in deps:
                framework = "next.js"
            elif "svelte" in deps:
                framework = "svelte"
            elif "express" in deps:
                framework = "express"
        except (json.JSONDecodeError, OSError):
            pass

    # Go indicators
    elif (cwd / "go.mod").exists():
        ptype = "go"

    # Rust indicators
    elif (cwd / "Cargo.toml").exists():
        ptype = "rust"

    return ptype, framework


def _find_key_files(cwd: Path) -> list[tuple[str, str]]:
    """Find and preview key project files."""
    key_files: list[tuple[str, str]] = []

    # Priority files to check
    candidates = [
        "README.md",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        ".sunwell/project.toml",
    ]

    for filename in candidates:
        filepath = cwd / filename
        if filepath.exists():
            try:
                content = filepath.read_text(errors="ignore")
                # Preview first 500 chars
                preview = content[:500]
                if len(content) > 500:
                    preview += "\n... (truncated)"
                key_files.append((filename, preview))
            except OSError:
                pass

        if len(key_files) >= 3:
            break

    return key_files


def _find_entry_points(cwd: Path, ptype: str) -> list[str]:
    """Find likely entry point files based on project type."""
    entry_points: list[str] = []

    if ptype == "python":
        candidates = ["main.py", "app.py", "run.py", "__main__.py", "cli.py"]
        for c in candidates:
            if (cwd / c).exists():
                entry_points.append(c)
        # Check src/ directory
        src = cwd / "src"
        if src.exists():
            for c in candidates:
                if (src / c).exists():
                    entry_points.append(f"src/{c}")

    elif ptype == "javascript":
        candidates = ["index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts"]
        for c in candidates:
            if (cwd / c).exists():
                entry_points.append(c)
        # Check src/ directory
        src = cwd / "src"
        if src.exists():
            for c in candidates:
                if (src / c).exists():
                    entry_points.append(f"src/{c}")

    return entry_points[:5]  # Limit


def _build_directory_tree(cwd: Path, max_depth: int = 3, max_items: int = 50) -> str:
    """Build a simple directory tree string."""
    lines: list[str] = []
    count = 0

    # Directories to skip
    skip_dirs = {
        ".git", ".sunwell", "__pycache__", "node_modules", ".venv", "venv",
        "dist", "build", ".next", ".svelte-kit", "target", ".pytest_cache",
    }

    def walk(path: Path, prefix: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= max_items:
            return

        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return

        # Filter and limit
        dirs = [i for i in items if i.is_dir() and i.name not in skip_dirs]
        files = [i for i in items if i.is_file() and not i.name.startswith(".")]

        visible = dirs[:10] + files[:15]  # Limit per level

        for i, item in enumerate(visible):
            if count >= max_items:
                lines.append(f"{prefix}... (truncated)")
                return

            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if item.is_dir():
                lines.append(f"{prefix}{connector}{item.name}/")
                count += 1
                walk(item, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{item.name}")
                count += 1

    lines.append(f"{cwd.name}/")
    walk(cwd, "", 1)

    return "\n".join(lines)


def _load_briefing(cwd: Path) -> Briefing | None:
    """Load briefing from previous session."""
    try:
        from sunwell.memory.briefing import Briefing
        return Briefing.load(cwd)
    except Exception:
        return None


def workspace_id(path: Path) -> str:
    """Generate stable workspace ID from path.

    Uses blake2b hash of resolved path for:
    - Stability (same path = same ID)
    - Privacy (ID doesn't leak path)
    - Uniqueness (no collisions)

    Examples:
        >>> workspace_id(Path("/Users/me/myproject"))
        'a1b2c3d4e5f6g7h8'
    """
    resolved = str(Path(path).resolve())
    return hashlib.blake2b(resolved.encode(), digest_size=8).hexdigest()
