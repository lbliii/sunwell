"""Project detection for workspace context building."""

import json
from pathlib import Path

# Project type detection patterns
PROJECT_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "requirements.txt", "Pipfile"),
    "node": ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"),
    "rust": ("Cargo.toml",),
    "go": ("go.mod",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "ruby": ("Gemfile",),
    "php": ("composer.json",),
    "dotnet": ("*.csproj", "*.sln"),
    "svelte": ("svelte.config.js", "svelte.config.ts"),
    "react": ("next.config.js", "next.config.ts", "vite.config.ts"),
    "tauri": ("tauri.conf.json",),
}

# Key files to always include in context (if they exist)
KEY_FILES = (
    "README.md", "README.rst", "README.txt", "README",
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "Makefile", "justfile",
    ".env.example",
)

# Entry point patterns by project type
ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "python": ("src/*/cli.py", "src/*/__main__.py", "main.py", "app.py", "cli.py"),
    "node": ("src/index.ts", "src/index.js", "index.ts", "index.js", "src/main.ts"),
    "rust": ("src/main.rs", "src/lib.rs"),
    "go": ("main.go", "cmd/*/main.go"),
}


class ProjectDetector:
    """Detects project type, framework, and key files."""

    @staticmethod
    def detect_project_type(cwd: Path) -> tuple[str, str | None]:
        """Detect project type from marker files.

        Args:
            cwd: Current working directory

        Returns:
            Tuple of (project_type, framework) e.g. ("python", "FastAPI")
        """
        for ptype, markers in PROJECT_MARKERS.items():
            for marker in markers:
                if "*" in marker:
                    if list(cwd.glob(marker)):
                        return ptype, None
                elif (cwd / marker).exists():
                    # Try to detect framework
                    framework = ProjectDetector._detect_framework(cwd, ptype)
                    return ptype, framework
        return "unknown", None

    @staticmethod
    def _detect_framework(cwd: Path, ptype: str) -> str | None:
        """Detect framework from config files.

        Args:
            cwd: Current working directory
            ptype: Project type

        Returns:
            Framework name or None
        """
        if ptype == "python":
            pyproject = cwd / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text()
                if "fastapi" in content.lower():
                    return "FastAPI"
                if "django" in content.lower():
                    return "Django"
                if "flask" in content.lower():
                    return "Flask"
                if "click" in content.lower():
                    return "CLI (Click)"
        elif ptype == "node":
            pkg = cwd / "package.json"
            if pkg.exists():
                try:
                    data = json.loads(pkg.read_text())
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if "next" in deps:
                        return "Next.js"
                    if "svelte" in deps or "@sveltejs/kit" in deps:
                        return "SvelteKit"
                    if "react" in deps:
                        return "React"
                    if "vue" in deps:
                        return "Vue"
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def is_project_directory(cwd: Path) -> bool:
        """Check if cwd looks like a project directory.

        Args:
            cwd: Current working directory

        Returns:
            True if looks like a project
        """
        # Has any project marker
        for markers in PROJECT_MARKERS.values():
            for marker in markers:
                if "*" in marker:
                    if list(cwd.glob(marker)):
                        return True
                elif (cwd / marker).exists():
                    return True

        # Has .git directory
        if (cwd / ".git").is_dir():
            return True

        # Has common project files
        if (cwd / "README.md").exists() or (cwd / "Makefile").exists():
            return True

        return False

    @staticmethod
    def find_key_files(cwd: Path) -> list[tuple[str, str]]:
        """Find key files and return (path, first_lines) tuples.

        Args:
            cwd: Current working directory

        Returns:
            List of (filename, preview) tuples
        """
        found = []
        for name in KEY_FILES:
            path = cwd / name
            if path.exists() and path.is_file():
                try:
                    content = path.read_text()
                    # Get first meaningful lines (skip empty)
                    lines = [l for l in content.split("\n") if l.strip()][:5]
                    preview = "\n".join(lines)
                    if len(preview) > 300:
                        preview = preview[:300] + "..."
                    found.append((name, preview))
                except (OSError, UnicodeDecodeError):
                    found.append((name, "(binary or unreadable)"))
        return found

    @staticmethod
    def find_entry_points(cwd: Path, ptype: str) -> list[str]:
        """Find likely entry point files.

        Args:
            cwd: Current working directory
            ptype: Project type

        Returns:
            List of entry point file paths (relative to cwd)
        """
        patterns = ENTRY_POINTS.get(ptype, ())
        found = []
        for pattern in patterns:
            matches = list(cwd.glob(pattern))
            found.extend(str(m.relative_to(cwd)) for m in matches[:3])
        return found[:5]  # Limit to 5 entry points

    @staticmethod
    def build_directory_tree(cwd: Path, max_files: int = 40, max_depth: int = 3) -> str:
        """Build a compact directory tree.

        Args:
            cwd: Current working directory
            max_files: Maximum files to include
            max_depth: Maximum directory depth

        Returns:
            Directory tree as string
        """
        ignore_patterns = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
            ".egg-info", ".tox", ".coverage", "htmlcov", ".next", ".svelte-kit",
            "target", ".cargo",
        }

        lines = []
        file_count = 0

        for root, dirs, files in cwd.walk():
            dirs[:] = [d for d in sorted(dirs)
                       if d not in ignore_patterns and not d.startswith(".")]

            rel_root = root.relative_to(cwd)
            depth = len(rel_root.parts)

            if depth > max_depth:
                continue

            indent = "  " * depth
            if depth > 0:
                lines.append(f"{indent}{rel_root.name}/")

            for f in sorted(files)[:15]:
                if f.startswith(".") and f not in {".env.example", ".gitignore"}:
                    continue
                lines.append(f"{indent}  {f}")
                file_count += 1
                if file_count >= max_files:
                    lines.append(f"{indent}  ...")
                    return "\n".join(lines)

        return "\n".join(lines)
