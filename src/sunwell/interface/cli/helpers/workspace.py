"""Workspace context building for CLI commands.

RFC-126: Build workspace context for agent orientation.
"""

import json
from pathlib import Path


def build_workspace_context(
    cwd: Path | None = None,
    use_cache: bool = True,
) -> dict[str, str | list[tuple[str, str]] | list[str]]:
    """Build workspace context dict for agent orientation.

    Returns a dict with:
    - path: Workspace path
    - name: Project name
    - type: Detected project type (python, javascript, etc.)
    - framework: Detected framework (fastapi, flask, react, etc.)
    - key_files: List of (filename, preview) tuples
    - entry_points: List of entry point files
    - tree: Directory tree string

    Args:
        cwd: Working directory (defaults to Path.cwd())
        use_cache: Whether to use cached context from .sunwell/context.json
    """
    if cwd is None:
        cwd = Path.cwd()

    cache_path = cwd / ".sunwell" / "context.json"

    # Try cache first
    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            # Validate cache has expected keys
            if cached.get("path") and cached.get("name"):
                return cached
        except (json.JSONDecodeError, OSError):
            pass  # Cache invalid, rebuild

    # Detect project type and framework
    ptype, framework = _detect_project_type(cwd)

    # Find key files
    key_files = _find_key_files(cwd)

    # Find entry points
    entry_points = _find_entry_points(cwd, ptype) if ptype != "unknown" else []

    # Build directory tree
    tree = _build_directory_tree(cwd)

    context = {
        "path": str(cwd),
        "name": cwd.name,
        "type": ptype,
        "framework": framework,
        "key_files": [(k, v) for k, v in key_files],
        "entry_points": entry_points,
        "tree": tree,
    }

    # Cache for next time
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(context, indent=2))
    except OSError:
        pass  # Non-fatal

    return context


def format_workspace_context(
    ctx: dict[str, str | list[tuple[str, str]] | list[str]],
) -> str:
    """Format context dict into markdown for system prompt / agent context."""
    lines = [
        "## Workspace Context",
        "",
        f"**Project**: `{ctx['name']}` ({ctx['path']})",
    ]

    # Project type badge
    ptype = ctx.get("type", "unknown")
    framework = ctx.get("framework")
    if ptype != "unknown":
        type_line = f"**Type**: {ptype.title()}"
        if framework:
            type_line += f" ({framework})"
        lines.append(type_line)

    lines.append("")

    # Key files with preview
    key_files = ctx.get("key_files", [])
    if key_files:
        lines.append("### Key Files")
        for name, preview in key_files[:3]:  # Limit to 3 for prompt size
            lines.append(f"\n**{name}**:")
            lines.append("```")
            lines.append(preview)
            lines.append("```")
        lines.append("")

    # Entry points
    entry_points = ctx.get("entry_points", [])
    if entry_points:
        lines.append(f"**Entry points**: {', '.join(f'`{e}`' for e in entry_points)}")
        lines.append("")

    # Directory tree
    tree = ctx.get("tree", "")
    if tree:
        lines.append("### Structure")
        lines.append("```")
        lines.append(tree)
        lines.append("```")

    lines.append("")
    lines.append("You can reference files by their relative paths.")

    return "\n".join(lines)


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
        "bottle": "bottle",
        "pyramid": "pyramid",
    }

    # Check pyproject.toml dependencies
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(errors="ignore").lower()
            for framework, dep in framework_deps.items():
                # Look for dependency declarations like: flask = "..." or "flask"
                if f'"{dep}"' in content or f"'{dep}'" in content or f"{dep} =" in content:
                    return framework
        except OSError:
            pass

    # Check requirements.txt
    for req_file in ["requirements.txt", "requirements/base.txt", "requirements/main.txt"]:
        req_path = cwd / req_file
        if req_path.exists():
            try:
                content = req_path.read_text(errors="ignore").lower()
                for framework, dep in framework_deps.items():
                    # Match lines starting with the dep name (handles flask==1.0, flask>=2.0, etc.)
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith(dep) and (len(line) == len(dep) or line[len(dep)] in "=<>~["):
                            return framework
            except OSError:
                pass

    # Fallback: Check manage.py for Django
    if (cwd / "manage.py").exists():
        return "django"

    # Fallback: Check main.py for FastAPI import
    main_py = cwd / "main.py"
    if main_py.exists():
        try:
            content = main_py.read_text(errors="ignore")[:2000]
            if "from fastapi" in content or "import fastapi" in content:
                return "fastapi"
            if "from flask" in content or "import flask" in content:
                return "flask"
        except OSError:
            pass

    return None


def _detect_project_type(cwd: Path) -> tuple[str, str | None]:
    """Detect project type and framework from directory contents.

    .. deprecated::
        For language detection only, use
        `sunwell.planning.naaru.expertise.language.detect_language` instead.
        This function is kept for framework detection compatibility.
    """
    import warnings

    warnings.warn(
        "Use sunwell.planning.naaru.expertise.language.detect_language for language detection. "
        "_detect_project_type is kept for framework detection.",
        DeprecationWarning,
        stacklevel=2,
    )
    ptype = "unknown"
    framework = None

    # Python indicators
    if (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
        ptype = "python"
        # Framework detection - check dependencies, not file names
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
        ".git",
        ".sunwell",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        ".svelte-kit",
        "target",
        ".pytest_cache",
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
