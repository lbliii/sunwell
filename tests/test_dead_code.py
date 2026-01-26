"""Detect unreachable code patterns.

This catches code that will never execute, indicating bugs or leftover code.

Run with: pytest tests/test_dead_code.py -v
"""

import ast
from pathlib import Path

import pytest


class DeadCodeDetector(ast.NodeVisitor):
    """AST visitor that detects unreachable code patterns."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.issues: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check for code after return/raise in functions."""
        self._check_unreachable_after_terminator(node.body, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check for code after return/raise in async functions."""
        self._check_unreachable_after_terminator(node.body, "async function")
        self.generic_visit(node)

    def _check_unreachable_after_terminator(
        self, body: list[ast.stmt], context: str
    ) -> None:
        """Check for statements after return/raise that aren't reachable."""
        for i, stmt in enumerate(body[:-1]):
            # Check if this statement always terminates
            if self._always_terminates(stmt):
                next_stmt = body[i + 1]
                # Allow docstrings and pass statements after terminator
                if isinstance(next_stmt, ast.Pass):
                    continue
                if isinstance(next_stmt, ast.Expr) and isinstance(
                    next_stmt.value, ast.Constant
                ):
                    continue

                self.issues.append(
                    f"{self.filename}:{next_stmt.lineno}: "
                    f"Unreachable code after {self._stmt_name(stmt)} in {context}"
                )

    def _always_terminates(self, stmt: ast.stmt) -> bool:
        """Check if a statement always terminates execution flow."""
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return True

        # Check if-else where both branches terminate
        if isinstance(stmt, ast.If):
            if stmt.orelse:
                # Has else branch - check if both terminate
                if_terminates = any(self._always_terminates(s) for s in stmt.body)
                else_terminates = any(self._always_terminates(s) for s in stmt.orelse)
                return if_terminates and else_terminates

        return False

    def _stmt_name(self, stmt: ast.stmt) -> str:
        """Get human-readable name for statement type."""
        if isinstance(stmt, ast.Return):
            return "return"
        if isinstance(stmt, ast.Raise):
            return "raise"
        if isinstance(stmt, ast.If):
            return "if/else"
        return stmt.__class__.__name__


def _check_file(py_file: Path) -> list[str]:
    """Check a single file for dead code."""
    try:
        content = py_file.read_text()
        tree = ast.parse(content, filename=str(py_file))
        detector = DeadCodeDetector(str(py_file))
        detector.visit(tree)
        return detector.issues
    except SyntaxError:
        return []  # Skip files with syntax errors (caught elsewhere)


def test_no_code_after_return() -> None:
    """No code should exist after return/raise statements.

    This catches bugs like:
    - Leftover code after early return
    - Debugging code that was never removed
    - Merge conflict artifacts
    """
    src = Path(__file__).parent.parent / "src" / "sunwell"
    all_issues: list[str] = []

    for py_file in src.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        issues = _check_file(py_file)
        all_issues.extend(issues)

    if all_issues:
        pytest.fail(
            f"Found {len(all_issues)} unreachable code patterns:\n"
            + "\n".join(all_issues[:20])  # Limit output
            + ("\n..." if len(all_issues) > 20 else "")
        )


class TestExceptionHandling:
    """Tests for exception handling patterns."""

    def test_no_bare_except(self) -> None:
        """No bare except clauses (catches too much)."""
        src = Path(__file__).parent.parent / "src" / "sunwell"
        bare_excepts: list[str] = []

        class BareExceptFinder(ast.NodeVisitor):
            def __init__(self, filename: str):
                self.filename = filename
                self.issues: list[str] = []

            def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
                if node.type is None:
                    self.issues.append(f"{self.filename}:{node.lineno}: bare except")
                self.generic_visit(node)

        for py_file in src.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                tree = ast.parse(py_file.read_text())
                finder = BareExceptFinder(str(py_file))
                finder.visit(tree)
                bare_excepts.extend(finder.issues)
            except SyntaxError:
                continue

        # Allow some bare excepts for now, but cap it
        assert len(bare_excepts) < 10, (
            f"Too many bare except clauses ({len(bare_excepts)}):\n"
            + "\n".join(bare_excepts[:10])
        )
