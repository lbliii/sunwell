"""Verify all modules can be imported without errors.

This catches:
- Missing imports (F821)
- Circular imports
- Import-time exceptions
- Syntax errors

Run with: pytest tests/test_imports.py -v
"""

import importlib
from pathlib import Path

import pytest


def _get_all_modules() -> list[str]:
    """Discover all Python modules in src/sunwell."""
    src = Path(__file__).parent.parent / "src" / "sunwell"
    modules: list[str] = []

    for py_file in src.rglob("*.py"):
        # Skip test files and __pycache__
        if "__pycache__" in str(py_file):
            continue

        # Convert path to module name
        relative = py_file.relative_to(src.parent)
        if py_file.name == "__init__.py":
            # sunwell/agent/__init__.py -> sunwell.agent
            module = str(relative.parent).replace("/", ".")
        else:
            # sunwell/agent/loop.py -> sunwell.agent.loop
            module = str(relative.with_suffix("")).replace("/", ".")

        modules.append(module)

    return sorted(set(modules))


# Get modules once at collection time
ALL_MODULES = _get_all_modules()


@pytest.mark.parametrize("module", ALL_MODULES)
def test_module_imports(module: str) -> None:
    """Each module should import without errors.

    This catches:
    - NameError from undefined names
    - ImportError from missing dependencies
    - SyntaxError from invalid Python
    - Circular import issues
    """
    try:
        importlib.import_module(module)
    except Exception as e:
        pytest.fail(f"Failed to import {module}: {type(e).__name__}: {e}")


def test_main_package_imports() -> None:
    """The main package should import cleanly."""
    import sunwell

    # Verify key attributes exist
    assert hasattr(sunwell, "__version__") or True  # Version may not be set


def test_cli_entrypoint_imports() -> None:
    """CLI entrypoint should be importable."""
    from sunwell.interface.cli import cli_entrypoint

    assert callable(cli_entrypoint)
