#!/usr/bin/env python3
"""Import linter — enforces architectural layer direction.

Scans every .py file under src/sunwell/ and reports violations where
a lower-layer module imports from a higher-layer module.

Layer map (lower number = lower layer):
  0: contracts
  1: foundation
  2: models, knowledge, memory
  3: agent, planning, tools, domains, features, awareness, core
  4: interface, mcp

Rule: A module may only import from its own layer or a lower layer.

Usage:
  python scripts/check_layer_imports.py              # error mode (exit 1 on violations)
  python scripts/check_layer_imports.py --warn       # warn mode (exit 0 always)
  python scripts/check_layer_imports.py --count-exempt  # just count layer-exempt comments
  python scripts/check_layer_imports.py --ratchet    # fail if exempt count increased

Exempt imports:
  Add ``# layer-exempt: <reason>`` on the import line to suppress a violation.
  The linter counts exemptions and reports the total — this count should only
  decrease over time (ratchet).

Ratchet:
  The file .layer-exempt-count stores the last-known exempt count. Running
  with --ratchet will fail if the current count exceeds the stored baseline.
  After reducing exemptions, update the baseline by running without --ratchet.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# =============================================================================
# Layer definitions
# =============================================================================

LAYER_MAP: dict[str, int] = {
    "contracts": 0,
    "foundation": 1,
    "models": 2,
    "knowledge": 2,
    "memory": 2,
    "agent": 3,
    "planning": 3,
    "tools": 3,
    "domains": 3,
    "features": 3,
    "awareness": 3,
    "core": 3,
    "interface": 4,
    "mcp": 4,
}

# Modules that are NOT part of the layer system (skip them)
SKIP_MODULES = {"benchmark", "scripts"}


# =============================================================================
# Helpers
# =============================================================================


def _get_layer(module_path: str) -> int | None:
    """Get the layer number for a module path like 'sunwell.agent.events'.

    Returns None if the module is not part of the layer map.
    """
    parts = module_path.split(".")
    if len(parts) < 2 or parts[0] != "sunwell":
        return None
    top_module = parts[1]
    if top_module in SKIP_MODULES:
        return None
    return LAYER_MAP.get(top_module)


def _get_file_layer(file_path: Path, src_root: Path) -> int | None:
    """Get the layer for a source file based on its path."""
    try:
        rel = file_path.relative_to(src_root / "sunwell")
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    top_module = parts[0]
    if top_module in SKIP_MODULES:
        return None
    return LAYER_MAP.get(top_module)


def _is_exempt(source_lines: list[str], lineno: int) -> bool:
    """Check if the import on ``lineno`` (1-based) has a layer-exempt comment."""
    if 1 <= lineno <= len(source_lines):
        return "layer-exempt:" in source_lines[lineno - 1]
    return False


# =============================================================================
# AST-based import extraction
# =============================================================================


def _extract_imports(tree: ast.Module) -> list[tuple[int, str, bool]]:
    """Extract all sunwell imports from an AST.

    Returns list of (lineno, module_path, is_type_checking).
    """
    imports: list[tuple[int, str, bool]] = []

    # Find TYPE_CHECKING blocks
    type_checking_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            # Match: if TYPE_CHECKING:
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                start = node.lineno
                end = max(
                    getattr(child, "end_lineno", start)
                    for child in ast.walk(node)
                    if hasattr(child, "end_lineno")
                )
                type_checking_ranges.append((start, end))

    def _in_type_checking(lineno: int) -> bool:
        return any(start <= lineno <= end for start, end in type_checking_ranges)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("sunwell."):
                    imports.append(
                        (node.lineno, alias.name, _in_type_checking(node.lineno))
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("sunwell."):
                imports.append(
                    (node.lineno, node.module, _in_type_checking(node.lineno))
                )

    return imports


# =============================================================================
# Violation detection
# =============================================================================


class Violation:
    """A single layer violation."""

    def __init__(
        self,
        file: Path,
        lineno: int,
        from_layer: int,
        to_layer: int,
        import_module: str,
        is_type_checking: bool,
    ):
        self.file = file
        self.lineno = lineno
        self.from_layer = from_layer
        self.to_layer = to_layer
        self.import_module = import_module
        self.is_type_checking = is_type_checking

    def __str__(self) -> str:
        tc = " (TYPE_CHECKING)" if self.is_type_checking else ""
        return (
            f"  {self.file}:{self.lineno}: "
            f"L{self.from_layer} imports from L{self.to_layer}{tc} — "
            f"{self.import_module}"
        )


def check_file(
    file_path: Path,
    src_root: Path,
) -> tuple[list[Violation], int]:
    """Check a single file for layer violations.

    Returns (violations, exempt_count).
    """
    file_layer = _get_file_layer(file_path, src_root)
    if file_layer is None:
        return [], 0

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], 0

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return [], 0

    source_lines = source.splitlines()
    imports = _extract_imports(tree)

    violations: list[Violation] = []
    exempt_count = 0

    for lineno, module_path, is_tc in imports:
        target_layer = _get_layer(module_path)
        if target_layer is None:
            continue

        # Violation: importing from a higher layer
        if target_layer > file_layer:
            if _is_exempt(source_lines, lineno):
                exempt_count += 1
            else:
                violations.append(
                    Violation(
                        file=file_path,
                        lineno=lineno,
                        from_layer=file_layer,
                        to_layer=target_layer,
                        import_module=module_path,
                        is_type_checking=is_tc,
                    )
                )

    return violations, exempt_count


# =============================================================================
# Main
# =============================================================================


def _ratchet_file(src_root: Path) -> Path:
    """Return path to the ratchet baseline file."""
    return src_root.parent / ".layer-exempt-count"


def main() -> int:
    """Run the layer import linter.

    Returns:
        0 if no violations (or --warn mode), 1 if violations found.
    """
    warn_mode = "--warn" in sys.argv
    count_exempt_only = "--count-exempt" in sys.argv
    ratchet_mode = "--ratchet" in sys.argv
    update_baseline = "--update-baseline" in sys.argv

    # Find src root
    script_dir = Path(__file__).resolve().parent
    src_root = script_dir.parent / "src"
    if not (src_root / "sunwell").is_dir():
        # Try relative to cwd
        src_root = Path.cwd() / "src"
    if not (src_root / "sunwell").is_dir():
        print("ERROR: Cannot find src/sunwell/ directory", file=sys.stderr)
        return 1

    # Collect all .py files
    py_files = sorted((src_root / "sunwell").rglob("*.py"))

    all_violations: list[Violation] = []
    total_exempt = 0

    for py_file in py_files:
        violations, exempt_count = check_file(py_file, src_root)
        all_violations.extend(violations)
        total_exempt += exempt_count

    # Report
    if count_exempt_only:
        print(f"Layer-exempt count: {total_exempt}")
        return 0

    if all_violations:
        print(f"\n{'='*60}")
        print(f"Layer import violations: {len(all_violations)}")
        print(f"{'='*60}\n")
        for v in all_violations:
            print(v)
        print()

    if total_exempt > 0:
        print(f"Layer-exempt imports (tracked debt): {total_exempt}")

    # Ratchet check
    ratchet_path = _ratchet_file(src_root)
    if update_baseline:
        ratchet_path.write_text(str(total_exempt))
        print(f"Updated baseline: {total_exempt}")

    if ratchet_mode and ratchet_path.exists():
        baseline = int(ratchet_path.read_text().strip())
        if total_exempt > baseline:
            print(
                f"\n[RATCHET FAIL] Exempt count increased: {total_exempt} > {baseline} (baseline)"
            )
            print(f"Remove exemptions or update baseline with: python {__file__} --update-baseline")
            return 1
        if total_exempt < baseline:
            print(f"\n[RATCHET OK] Exempt count decreased: {total_exempt} < {baseline}")
            print(f"Update baseline with: python {__file__} --update-baseline")

    if not all_violations:
        print(f"No layer violations found ({len(py_files)} files checked)")
        return 0

    if warn_mode:
        print(f"\n[WARN] {len(all_violations)} violations (warn mode, not failing)")
        return 0

    print(f"\n[ERROR] {len(all_violations)} violations found. Fix or add # layer-exempt: <reason>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
