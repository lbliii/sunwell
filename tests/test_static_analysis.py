"""Run static analysis as part of test suite.

This catches pyflakes errors that would cause runtime failures:
- F821: Undefined names
- F822: Undefined __all__ exports
- F811: Redefinition of unused names

Run with: pytest tests/test_static_analysis.py -v
"""

import subprocess
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"


def _run_ruff(select: str, extra_args: list[str] | None = None) -> tuple[int, str]:
    """Run ruff with given selection and return (exit_code, output)."""
    cmd = ["ruff", "check", str(SRC_DIR), f"--select={select}", "--quiet"]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def test_no_undefined_names() -> None:
    """No F821 (undefined name) errors.

    These would cause NameError at runtime.
    """
    code, output = _run_ruff("F821")
    assert code == 0, f"Undefined names found (F821):\n{output}"


def test_no_undefined_all_exports() -> None:
    """No F822 (undefined __all__ export) errors.

    These would cause ImportError when doing `from module import *`.
    """
    code, output = _run_ruff("F822")
    assert code == 0, f"Undefined __all__ exports found (F822):\n{output}"


def test_no_redefinitions() -> None:
    """No F811 (redefinition of unused name) errors.

    These indicate copy-paste errors or merge conflicts.
    """
    code, output = _run_ruff("F811")
    assert code == 0, f"Redefinitions found (F811):\n{output}"


def test_no_syntax_errors() -> None:
    """Verify all Python files have valid syntax.

    This would prevent modules from loading at all.
    """
    import ast
    from pathlib import Path

    errors: list[str] = []
    src = Path(__file__).parent.parent / "src" / "sunwell"

    for py_file in src.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            ast.parse(py_file.read_text())
        except SyntaxError as e:
            errors.append(f"{py_file}:{e.lineno}: {e.msg}")

    assert not errors, f"Syntax errors found:\n" + "\n".join(errors)


@pytest.mark.slow
def test_all_pyflakes_errors() -> None:
    """No pyflakes (F) errors at all.

    This is a comprehensive check for all F-class errors.
    """
    code, output = _run_ruff("F")
    assert code == 0, f"Pyflakes errors found:\n{output}"


class TestImportOrder:
    """Tests for import hygiene."""

    def test_no_star_imports_in_non_init(self) -> None:
        """No wildcard imports outside of __init__.py.

        F403: `from module import *` used; unable to detect undefined names
        """
        # Only check non-init files
        code, output = _run_ruff("F403", ["--exclude", "*/__init__.py"])
        # Allow in __init__.py for re-exports, but not elsewhere
        if code != 0 and "__init__.py" not in output:
            pytest.fail(f"Star imports in non-__init__ files:\n{output}")


class TestUnusedCode:
    """Tests for unused code detection."""

    @pytest.mark.slow
    def test_unused_variables_count(self) -> None:
        """Track unused variable count (F841).

        We don't fail on these but track the count to prevent regression.
        """
        code, output = _run_ruff("F841")
        if code != 0:
            count = output.count("F841")
            # Set a threshold - fail if it grows too much
            assert count < 20, f"Too many unused variables ({count}):\n{output}"
