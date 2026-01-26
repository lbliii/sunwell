"""Verify __all__ exports actually exist.

This catches F822 errors where __all__ references undefined names.

Run with: pytest tests/test_all_exports.py -v
"""

import importlib
from pathlib import Path

import pytest


def _find_modules_with_all() -> list[str]:
    """Find all modules that define __all__."""
    src = Path(__file__).parent.parent / "src" / "sunwell"
    modules_with_all: list[str] = []

    for py_file in src.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text()
            if "__all__" in content:
                # Convert to module name
                relative = py_file.relative_to(src.parent)
                if py_file.name == "__init__.py":
                    module = str(relative.parent).replace("/", ".")
                else:
                    module = str(relative.with_suffix("")).replace("/", ".")
                modules_with_all.append(module)
        except Exception:
            continue

    return sorted(modules_with_all)


MODULES_WITH_ALL = _find_modules_with_all()


@pytest.mark.parametrize("module_name", MODULES_WITH_ALL)
def test_all_exports_exist(module_name: str) -> None:
    """Everything in __all__ should actually be defined in the module.

    This catches cases like:
    - Typos in __all__ entries
    - Removed classes still listed in __all__
    - Renamed exports not updated in __all__
    """
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        pytest.skip(f"Could not import {module_name}: {e}")
        return

    if not hasattr(module, "__all__"):
        pytest.skip(f"{module_name} has no __all__")
        return

    missing: list[str] = []
    for name in module.__all__:
        if not hasattr(module, name):
            missing.append(name)

    if missing:
        pytest.fail(
            f"{module_name}.__all__ contains undefined names: {missing}\n"
            f"Either define these or remove them from __all__"
        )


def test_no_duplicate_all_entries() -> None:
    """__all__ should not have duplicate entries."""
    src = Path(__file__).parent.parent / "src" / "sunwell"
    duplicates: list[str] = []

    for py_file in src.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            module_name = str(py_file.relative_to(src.parent)).replace("/", ".").replace(".py", "")
            module = importlib.import_module(module_name.replace(".__init__", ""))

            if hasattr(module, "__all__"):
                all_list = module.__all__
                if len(all_list) != len(set(all_list)):
                    seen: set[str] = set()
                    for item in all_list:
                        if item in seen:
                            duplicates.append(f"{module_name}: {item}")
                        seen.add(item)
        except Exception:
            continue

    if duplicates:
        pytest.fail(f"Duplicate __all__ entries found:\n" + "\n".join(duplicates))
