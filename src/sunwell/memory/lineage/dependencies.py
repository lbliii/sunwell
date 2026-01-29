"""Dependency detection for lineage tracking (RFC-121).

Detects imports in source files and maintains the dependency graph.
Supports Python, TypeScript, and JavaScript.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.memory.lineage.store import LineageStore

# ─────────────────────────────────────────────────────────────────
# Import Patterns by Language
# ─────────────────────────────────────────────────────────────────

IMPORT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "python": [
        # import module
        re.compile(r"^import\s+([\w.]+)", re.MULTILINE),
        # from module import ...
        re.compile(r"^from\s+([\w.]+)\s+import", re.MULTILINE),
    ],
    "typescript": [
        # import ... from "path"
        re.compile(r"import\s+.*from\s+['\"]([^'\"]+)['\"]"),
        # import "path"
        re.compile(r"import\s+['\"]([^'\"]+)['\"]"),
        # require("path")
        re.compile(r"require\(['\"]([^'\"]+)['\"]\)"),
        # export ... from "path"
        re.compile(r"export\s+.*from\s+['\"]([^'\"]+)['\"]"),
        # dynamic import("path")
        re.compile(r"import\(['\"]([^'\"]+)['\"]\)"),
    ],
    "javascript": [
        # import ... from "path"
        re.compile(r"import\s+.*from\s+['\"]([^'\"]+)['\"]"),
        # require("path")
        re.compile(r"require\(['\"]([^'\"]+)['\"]\)"),
        # export ... from "path"
        re.compile(r"export\s+.*from\s+['\"]([^'\"]+)['\"]"),
        # dynamic import("path")
        re.compile(r"import\(['\"]([^'\"]+)['\"]\)"),
    ],
    "go": [
        # "package/path" within import block
        re.compile(r'^\s*"([^"]+)"', re.MULTILINE),
    ],
}

EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
}

# Standard library modules (skip these)
PYTHON_STDLIB = frozenset([
    "abc", "aifc", "argparse", "array", "ast", "asyncio", "atexit",
    "base64", "bdb", "binascii", "bisect", "builtins", "bz2",
    "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code",
    "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "cProfile", "crypt", "csv", "ctypes", "curses",
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest", "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools", "gc", "getopt", "getpass",
    "gettext", "glob", "graphlib", "grp", "gzip", "hashlib", "heapq",
    "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
    "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue",
    "quopri", "random", "re", "readline", "reprlib", "resource",
    "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
    "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib",
    "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "ssl",
    "stat", "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap",
    "threading", "time", "timeit", "tkinter", "token", "tokenize",
    "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
    "types", "typing", "typing_extensions", "unicodedata", "unittest",
    "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml",
    "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib", "_thread",
])


# ─────────────────────────────────────────────────────────────────
# Import Detection
# ─────────────────────────────────────────────────────────────────


def detect_language(path: Path) -> str | None:
    """Detect language from file extension.

    .. deprecated::
        Use `sunwell.planning.naaru.expertise.language.language_from_extension`
        for file extension-based detection, or `detect_language` for
        comprehensive goal+project detection.

    Args:
        path: File path

    Returns:
        Language identifier or None if unknown
    """
    import warnings

    warnings.warn(
        "Use sunwell.planning.naaru.expertise.language.language_from_extension instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return EXTENSION_TO_LANG.get(path.suffix.lower())


def detect_imports(path: Path, content: str) -> list[str]:
    """Detect imports in a file.

    Returns list of resolved import paths (relative to project root).
    Only resolves local/relative imports; skips stdlib and third-party.

    Args:
        path: File path
        content: File content

    Returns:
        List of resolved import paths
    """
    lang = detect_language(path)
    if not lang:
        return []

    patterns = IMPORT_PATTERNS.get(lang, [])

    raw_imports: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(content):
            raw_imports.append(match.group(1))

    return _resolve_imports(path, raw_imports, lang)


def _resolve_imports(
    file_path: Path,
    imports: list[str],
    lang: str,
) -> list[str]:
    """Resolve imports to project-relative paths.

    Args:
        file_path: File containing the imports
        imports: Raw import strings
        lang: Language identifier

    Returns:
        List of resolved paths (relative to project root)
    """
    seen: set[str] = set()
    resolved: list[str] = []
    base_dir = file_path.parent

    for imp in imports:
        resolved_path = _resolve_single_import(base_dir, imp, lang)
        if resolved_path and resolved_path not in seen:
            seen.add(resolved_path)
            resolved.append(resolved_path)

    return resolved


def _resolve_single_import(
    base_dir: Path,
    imp: str,
    lang: str,
) -> str | None:
    """Resolve a single import to a path.

    Returns None for stdlib/third-party imports.

    Args:
        base_dir: Directory of the importing file
        imp: Import string
        lang: Language identifier

    Returns:
        Resolved path or None
    """
    if lang == "python":
        return _resolve_python_import(base_dir, imp)
    elif lang in ("typescript", "javascript"):
        return _resolve_ts_import(base_dir, imp)
    elif lang == "go":
        return _resolve_go_import(imp)
    return None


def _resolve_python_import(base_dir: Path, imp: str) -> str | None:
    """Resolve Python import.

    Args:
        base_dir: Directory of importing file
        imp: Import string (e.g., "sunwell.core.models" or ".base")

    Returns:
        Resolved path or None for stdlib/third-party
    """
    # Check if it's stdlib
    top_module = imp.split(".")[0].lstrip(".")
    if top_module in PYTHON_STDLIB:
        return None

    # Relative import (starts with .)
    if imp.startswith("."):
        levels = len(imp) - len(imp.lstrip("."))
        remaining = imp.lstrip(".")

        # Go up directories based on level
        target = base_dir
        for _ in range(levels - 1):
            target = target.parent

        if remaining:
            parts = remaining.split(".")
            target = target / "/".join(parts)

        # Try .py extension
        py_path = target.with_suffix(".py")
        if py_path.exists():
            return str(py_path)

        # Try __init__.py in directory
        init_path = target / "__init__.py"
        if init_path.exists():
            return str(init_path)

        # Return as-is (might not exist yet)
        return str(target.with_suffix(".py"))

    # Absolute import - check if it starts with known project prefixes
    # These are common source roots
    if imp.startswith(("src.", "sunwell.", "app.", "lib.")):
        parts = imp.split(".")
        target = Path("/".join(parts))

        # Return with .py extension
        return str(target.with_suffix(".py"))

    # Skip third-party (no . prefix, not stdlib, doesn't match known patterns)
    return None


def _resolve_ts_import(base_dir: Path, imp: str) -> str | None:
    """Resolve TypeScript/JavaScript import.

    Args:
        base_dir: Directory of importing file
        imp: Import string (e.g., "./utils" or "../config")

    Returns:
        Resolved path or None for third-party
    """
    # Only resolve relative imports
    if not imp.startswith("."):
        return None

    # Resolve relative path
    target = (base_dir / imp).resolve()

    # Try various extensions
    extensions = [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]
    for ext in extensions:
        candidate = Path(str(target) + ext)
        if candidate.exists():
            return str(candidate)

    # Return as-is with .ts extension
    return str(target) + ".ts"


def _resolve_go_import(imp: str) -> str | None:
    """Resolve Go import.

    Only resolves local imports (not full module paths).

    Args:
        imp: Import string

    Returns:
        Resolved path or None for external
    """
    # Go imports are full module paths - skip external ones
    # Only local relative imports start with .
    if not imp.startswith("."):
        return None
    return imp


# ─────────────────────────────────────────────────────────────────
# Dependency Graph Updates
# ─────────────────────────────────────────────────────────────────


def update_dependency_graph(store: LineageStore, path: str, content: str) -> None:
    """Update import/imported_by relationships after file change.

    Args:
        store: LineageStore to update
        path: File path that changed
        content: New file content
    """
    lineage = store.get_by_path(path)
    if not lineage:
        return

    new_imports = detect_imports(Path(path), content)
    old_imports = set(lineage.imports)
    new_imports_set = set(new_imports)

    # Remove this file from old imports' imported_by
    for removed in old_imports - new_imports_set:
        store.remove_imported_by(removed, path)

    # Add this file to new imports' imported_by
    for added in new_imports_set - old_imports:
        store.add_imported_by(added, path)

    # Update this file's imports
    store.update_imports(path, list(new_imports_set))


def get_impact_analysis(store: LineageStore, path: str) -> dict:
    """Analyze impact of modifying/deleting a file.

    Args:
        store: LineageStore to query
        path: File path to analyze

    Returns:
        Dict with affected_files, affected_goals, depth info
    """
    lineage = store.get_by_path(path)
    if not lineage:
        return {
            "path": path,
            "affected_files": [],
            "affected_goals": set(),
            "max_depth": 0,
        }

    # BFS to find all files that directly or transitively depend on this file
    affected: set[str] = set()
    goals: set[str] = set()
    queue: list[tuple[str, int]] = [(path, 0)]
    visited: set[str] = set()
    max_depth = 0

    while queue:
        current, depth = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        max_depth = max(max_depth, depth)

        current_lineage = store.get_by_path(current)
        if not current_lineage:
            continue

        # Collect goals
        if current_lineage.created_by_goal:
            goals.add(current_lineage.created_by_goal)
        for edit in current_lineage.edits:
            if edit.goal_id:
                goals.add(edit.goal_id)

        # Add files that import this one
        for importer in current_lineage.imported_by:
            if importer not in visited:
                affected.add(importer)
                queue.append((importer, depth + 1))

    return {
        "path": path,
        "affected_files": sorted(affected),
        "affected_goals": goals,
        "max_depth": max_depth,
    }
