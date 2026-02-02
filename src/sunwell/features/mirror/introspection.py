"""Core introspection capabilities for RFC-015 Mirror Neurons.

Provides tools to examine Sunwell's own source code, lens configuration,
simulacrum state, and execution history.
"""


import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.tools.execution import ToolExecutor


def _get_sunwell_source_root() -> Path:
    """Get the root directory containing Sunwell's source code.

    This auto-resolves to where `src/sunwell/` lives, regardless of
    the current working directory. Works for both development installs
    and installed packages.
    """
    import sunwell
    # sunwell.__file__ = .../src/sunwell/__init__.py
    # We need .../src/sunwell's parent's parent = ...
    return Path(sunwell.__file__).parent.parent.parent


@dataclass(slots=True)
class SourceIntrospector:
    """Read and analyze Sunwell's own source code.

    Example:
        >>> introspector = SourceIntrospector()
        >>> source = introspector.get_module_source("sunwell.tools.executor")
        >>> symbol = introspector.find_symbol("sunwell.tools.executor", "ToolExecutor")

    Source root is auto-detected from the installed package location.
    """

    _source_root: Path = field(init=False)

    def __post_init__(self) -> None:
        """Auto-resolve the actual Sunwell source root."""
        self._source_root = _get_sunwell_source_root()

    def get_module_source(self, module_path: str) -> str:
        """Get source code for a module.

        Args:
            module_path: Dotted module path (e.g., 'sunwell.tools.executor')

        Returns:
            Source code as string

        Raises:
            FileNotFoundError: If module doesn't exist
        """
        # Convert module path to file path
        parts = module_path.replace("sunwell.", "").split(".")
        file_path = self._source_root / "src" / "sunwell" / "/".join(parts)

        # Try .py extension
        if not file_path.suffix:
            file_path = file_path.with_suffix(".py")

        # Check for __init__.py in directory
        if not file_path.exists():
            dir_path = self._source_root / "src" / "sunwell" / "/".join(parts)
            if dir_path.is_dir():
                file_path = dir_path / "__init__.py"

        if not file_path.exists():
            raise FileNotFoundError(f"Module not found: {module_path}")

        return file_path.read_text()

    def find_symbol(self, module_path: str, symbol: str) -> dict[str, Any]:
        """Find a specific symbol (class, function, constant) in a module.

        Args:
            module_path: Dotted module path
            symbol: Name of class, function, or constant

        Returns:
            Dict with 'source', 'start_line', 'end_line', 'docstring', 'type'

        Raises:
            ValueError: If symbol not found
        """
        source = self.get_module_source(module_path)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == symbol:
                return {
                    "type": "class",
                    "source": ast.get_source_segment(source, node),
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": [
                        n.name for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                }
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
                return {
                    "type": "function",
                    "source": ast.get_source_segment(source, node),
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                }

        raise ValueError(f"Symbol '{symbol}' not found in {module_path}")

    def get_module_structure(self, module_path: str) -> dict[str, Any]:
        """Get structure of a module: classes, functions, imports.

        Args:
            module_path: Dotted module path

        Returns:
            Dict with 'classes', 'functions', 'imports' lists
        """
        source = self.get_module_source(module_path)
        tree = ast.parse(source)

        structure: dict[str, list] = {
            "classes": [],
            "functions": [],
            "imports": [],
        }

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                structure["classes"].append({
                    "name": node.name,
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                    "line": node.lineno,
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                structure["functions"].append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "line": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
            elif isinstance(node, ast.Import):
                structure["imports"].extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    structure["imports"].append(f"{module}.{alias.name}")

        return structure

    def list_modules(self) -> list[str]:
        """List all available Sunwell modules.

        Returns:
            List of dotted module paths
        """
        sunwell_src = self._source_root / "src" / "sunwell"
        modules = []

        for path in sunwell_src.rglob("*.py"):
            if "__pycache__" in str(path):
                continue

            relative = path.relative_to(sunwell_src)
            parts = list(relative.parts)

            # Handle __init__.py
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
                if not parts:
                    continue
            else:
                parts[-1] = parts[-1].replace(".py", "")

            module_path = "sunwell." + ".".join(parts)
            modules.append(module_path)

        return sorted(modules)


# === Lens Introspection Functions ===


def lens_get_heuristics(lens: Any) -> list[dict[str, Any]]:
    """Get all heuristics from a lens.

    Args:
        lens: Loaded lens object

    Returns:
        List of heuristic dicts with name, rule, always, never
    """
    if not lens or not hasattr(lens, "heuristics"):
        return []

    return [
        {
            "name": getattr(h, "name", "unknown"),
            "rule": getattr(h, "rule", ""),
            "always": getattr(h, "always", []),
            "never": getattr(h, "never", []),
        }
        for h in lens.heuristics
    ]


def lens_get_validators(lens: Any) -> list[dict[str, Any]]:
    """Get all validators from a lens.

    Args:
        lens: Loaded lens object

    Returns:
        List of validator dicts with name, type, severity
    """
    if not lens or not hasattr(lens, "validators"):
        return []

    return [
        {
            "name": getattr(v, "name", "unknown"),
            "type": getattr(v, "type", "heuristic"),
            "severity": getattr(v, "severity", "warning"),
        }
        for v in lens.validators
    ]


def lens_get_personas(lens: Any) -> list[dict[str, Any]]:
    """Get all personas from a lens.

    Args:
        lens: Loaded lens object

    Returns:
        List of persona dicts with name, background, goals, friction_points
    """
    if not lens or not hasattr(lens, "personas"):
        return []

    return [
        {
            "name": getattr(p, "name", "unknown"),
            "background": getattr(p, "background", ""),
            "goals": getattr(p, "goals", []),
            "friction_points": getattr(p, "friction_points", []),
        }
        for p in lens.personas
    ]


def lens_get_framework(lens: Any) -> dict[str, Any] | None:
    """Get framework configuration from a lens.

    Args:
        lens: Loaded lens object

    Returns:
        Framework dict or None if not defined
    """
    if not lens or not hasattr(lens, "framework"):
        return None

    framework = lens.framework
    return {
        "name": getattr(framework, "name", "unknown"),
        "categories": [
            {
                "name": getattr(c, "name", ""),
                "purpose": getattr(c, "purpose", ""),
            }
            for c in getattr(framework, "categories", [])
        ],
    }


def lens_get_all(lens: Any) -> dict[str, Any]:
    """Get all lens components.

    Args:
        lens: Loaded lens object

    Returns:
        Dict with heuristics, validators, personas, framework
    """
    return {
        "heuristics": lens_get_heuristics(lens),
        "validators": lens_get_validators(lens),
        "personas": lens_get_personas(lens),
        "framework": lens_get_framework(lens),
    }


# === Simulacrum Introspection Functions ===


def simulacrum_get_learnings(simulacrum: Any) -> list[dict[str, Any]]:
    """Get all learnings from simulacrum.

    Args:
        simulacrum: Simulacrum manager instance

    Returns:
        List of learning dicts
    """
    if not simulacrum:
        return []

    # Try different simulacrum interfaces
    if hasattr(simulacrum, "get_learnings"):
        return simulacrum.get_learnings()
    elif hasattr(simulacrum, "learnings"):
        return list(simulacrum.learnings)

    return []


def simulacrum_get_dead_ends(simulacrum: Any) -> list[dict[str, Any]]:
    """Get all dead ends (approaches that didn't work).

    Args:
        simulacrum: Simulacrum manager instance

    Returns:
        List of dead end dicts
    """
    if not simulacrum:
        return []

    if hasattr(simulacrum, "get_dead_ends"):
        return simulacrum.get_dead_ends()
    elif hasattr(simulacrum, "dead_ends"):
        return list(simulacrum.dead_ends)

    return []


def simulacrum_get_focus(simulacrum: Any) -> dict[str, Any] | None:
    """Get current focus state.

    Args:
        simulacrum: Simulacrum manager instance

    Returns:
        Focus dict or None
    """
    if not simulacrum:
        return None

    if hasattr(simulacrum, "get_focus"):
        return simulacrum.get_focus()
    elif hasattr(simulacrum, "focus"):
        return simulacrum.focus

    return None


def simulacrum_get_context(simulacrum: Any, limit: int = 10) -> list[dict[str, Any]]:
    """Get recent conversation context.

    Args:
        simulacrum: Simulacrum manager instance
        limit: Maximum number of turns to return

    Returns:
        List of conversation turn dicts
    """
    if not simulacrum:
        return []

    if hasattr(simulacrum, "get_recent_context"):
        return simulacrum.get_recent_context(limit)
    elif hasattr(simulacrum, "context"):
        ctx = list(simulacrum.context)
        return ctx[-limit:] if len(ctx) > limit else ctx

    return []


def simulacrum_get_all(simulacrum: Any) -> dict[str, Any]:
    """Get all simulacrum state.

    Args:
        simulacrum: Simulacrum manager instance

    Returns:
        Dict with learnings, dead_ends, focus, context
    """
    return {
        "learnings": simulacrum_get_learnings(simulacrum),
        "dead_ends": simulacrum_get_dead_ends(simulacrum),
        "focus": simulacrum_get_focus(simulacrum),
        "context_summary": f"{len(simulacrum_get_context(simulacrum))} turns",
    }


# === Execution Introspection Functions ===


def execution_get_recent_tool_calls(
    executor: ToolExecutor,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get recent tool calls from the executor's audit log.

    Args:
        executor: ToolExecutor instance
        limit: Maximum number of entries

    Returns:
        List of tool call dicts
    """
    entries = executor.get_audit_log()[-limit:]
    return [e.to_dict() for e in entries]


def execution_get_errors(
    executor: ToolExecutor,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get recent errors from execution history.

    Args:
        executor: ToolExecutor instance
        limit: Maximum number of errors

    Returns:
        List of error dicts
    """
    entries = executor.get_audit_log()
    errors = [e for e in entries if not e.success][-limit:]
    return [e.to_dict() for e in errors]


def execution_get_error_summary(executor: ToolExecutor) -> dict[str, Any]:
    """Summarize errors from execution history.

    Args:
        executor: ToolExecutor instance

    Returns:
        Dict with total_errors, by_type, recent_errors
    """
    entries = executor.get_audit_log()
    errors = [e for e in entries if not e.success]

    by_type: dict[str, int] = {}
    for e in errors:
        error_type = (e.error or "Unknown").split(":")[0]
        by_type[error_type] = by_type.get(error_type, 0) + 1

    return {
        "total_errors": len(errors),
        "by_type": by_type,
        "recent_errors": [e.to_dict() for e in errors[-5:]],
    }


def execution_get_stats(executor: ToolExecutor) -> dict[str, Any]:
    """Get execution statistics.

    Args:
        executor: ToolExecutor instance

    Returns:
        Execution stats dict
    """
    return executor.get_stats()
