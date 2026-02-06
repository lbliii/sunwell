#!/usr/bin/env python3
"""Find unwired/incomplete code in the Sunwell codebase.

This script detects:
1. Dead code - Functions/classes defined but never called (via vulture)
2. Stub implementations - pass, ..., raise NotImplementedError
3. TODO/FIXME markers - Incomplete work indicators
4. Orphan exports - Things exported in __init__.py but never imported elsewhere
5. Empty modules - Files with only imports and no implementation
6. No-op fallbacks - Optional callbacks that silently return mock results when None

Usage:
    python scripts/find_unwired.py [--category CATEGORY] [--min-confidence N]
    
Categories:
    all       - Run all checks (default)
    dead      - Dead code only (requires vulture)
    stubs     - Stub implementations only
    todos     - TODO/FIXME markers only
    exports   - Orphan exports only
    empty     - Empty modules only
    noop      - No-op/mock fallbacks only
"""

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Finding:
    """A single finding from the unwired code analysis."""

    file: Path
    line: int
    category: str
    description: str
    confidence: int  # 0-100
    code_snippet: str = ""

    def __str__(self) -> str:
        confidence_indicator = "🟢" if self.confidence >= 90 else "🟡" if self.confidence >= 70 else "🟠"
        return f"{self.file}:{self.line} [{self.category}] {confidence_indicator} {self.confidence}%\n  {self.description}"


def get_project_root() -> Path:
    """Find the project root (contains src/sunwell)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "src" / "sunwell").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


def find_stubs(src_dir: Path) -> list[Finding]:
    """Find stub implementations (pass, ..., NotImplementedError)."""
    findings = []
    
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        
        lines = content.splitlines()
        
        for node in ast.walk(tree):
            # Check for functions/methods with stub bodies
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                
                # Skip if docstring only followed by stub
                if len(body) >= 1:
                    first_stmt = body[0] if len(body) == 1 else body[1] if (
                        len(body) == 2 and isinstance(body[0], ast.Expr) and 
                        isinstance(body[0].value, ast.Constant)
                    ) else None
                    
                    actual_body = body[1:] if (
                        len(body) >= 2 and isinstance(body[0], ast.Expr) and 
                        isinstance(body[0].value, ast.Constant)
                    ) else body
                    
                    # Check for pass statement
                    if len(actual_body) == 1 and isinstance(actual_body[0], ast.Pass):
                        line_content = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                        findings.append(Finding(
                            file=py_file.relative_to(src_dir.parent.parent),
                            line=node.lineno,
                            category="stub",
                            description=f"Function '{node.name}' has empty body (pass)",
                            confidence=95,
                            code_snippet=line_content.strip(),
                        ))
                    
                    # Check for ellipsis
                    elif len(actual_body) == 1 and isinstance(actual_body[0], ast.Expr):
                        if isinstance(actual_body[0].value, ast.Constant) and actual_body[0].value.value is ...:
                            line_content = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                            findings.append(Finding(
                                file=py_file.relative_to(src_dir.parent.parent),
                                line=node.lineno,
                                category="stub",
                                description=f"Function '{node.name}' has ellipsis body (...)",
                                confidence=95,
                                code_snippet=line_content.strip(),
                            ))
                    
                    # Check for NotImplementedError
                    elif len(actual_body) == 1 and isinstance(actual_body[0], ast.Raise):
                        raise_stmt = actual_body[0]
                        if raise_stmt.exc and isinstance(raise_stmt.exc, ast.Call):
                            if isinstance(raise_stmt.exc.func, ast.Name) and raise_stmt.exc.func.id == "NotImplementedError":
                                line_content = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                                findings.append(Finding(
                                    file=py_file.relative_to(src_dir.parent.parent),
                                    line=node.lineno,
                                    category="stub",
                                    description=f"Function '{node.name}' raises NotImplementedError",
                                    confidence=100,
                                    code_snippet=line_content.strip(),
                                ))
    
    return findings


def find_todos(src_dir: Path) -> list[Finding]:
    """Find TODO/FIXME/XXX markers indicating incomplete work."""
    findings = []
    patterns = [
        (r"#\s*TODO[:\s](.+)", "TODO", 80),
        (r"#\s*FIXME[:\s](.+)", "FIXME", 90),
        (r"#\s*XXX[:\s](.+)", "XXX", 85),
        (r"#\s*HACK[:\s](.+)", "HACK", 75),
        (r"#\s*WIP[:\s](.+)", "WIP", 95),
    ]
    
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        
        for lineno, line in enumerate(content.splitlines(), 1):
            for pattern, marker, confidence in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    findings.append(Finding(
                        file=py_file.relative_to(src_dir.parent.parent),
                        line=lineno,
                        category="todo",
                        description=f"{marker}: {match.group(1).strip()}",
                        confidence=confidence,
                        code_snippet=line.strip(),
                    ))
    
    return findings


def find_orphan_exports(src_dir: Path) -> list[Finding]:
    """Find symbols exported in __init__.py but never imported elsewhere."""
    findings = []
    
    # First pass: collect all exports from __init__.py files
    exports: dict[str, tuple[Path, int]] = {}  # symbol -> (file, line)
    
    for init_file in src_dir.rglob("__init__.py"):
        try:
            content = init_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(init_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        
        # Check __all__ if defined
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    module_path = init_file.parent.relative_to(src_dir)
                                    full_name = f"sunwell.{str(module_path).replace('/', '.')}.{elt.value}"
                                    exports[full_name] = (init_file, node.lineno)
    
    # Second pass: find all imports across the codebase
    all_imports: set[str] = set()
    
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("sunwell"):
                    for alias in node.names:
                        all_imports.add(f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sunwell"):
                        all_imports.add(alias.name)
    
    # Find orphans
    for export_name, (file, line) in exports.items():
        # Check if this export is ever imported
        short_name = export_name.split(".")[-1]
        if not any(export_name in imp or imp.endswith(f".{short_name}") for imp in all_imports):
            # Additional check: is it used in tests?
            test_imports: set[str] = set()
            test_dir = src_dir.parent.parent / "tests"
            if test_dir.exists():
                for test_file in test_dir.rglob("*.py"):
                    try:
                        test_content = test_file.read_text(encoding="utf-8")
                        test_tree = ast.parse(test_content)
                        for node in ast.walk(test_tree):
                            if isinstance(node, ast.ImportFrom) and node.module:
                                for alias in node.names:
                                    test_imports.add(f"{node.module}.{alias.name}")
                    except (SyntaxError, UnicodeDecodeError):
                        continue
            
            if not any(export_name in imp or imp.endswith(f".{short_name}") for imp in test_imports):
                findings.append(Finding(
                    file=file.relative_to(src_dir.parent.parent),
                    line=line,
                    category="orphan_export",
                    description=f"'{short_name}' exported but never imported",
                    confidence=70,  # Lower confidence - might be public API
                ))
    
    return findings


def find_empty_modules(src_dir: Path) -> list[Finding]:
    """Find modules with only imports and no implementation."""
    findings = []
    
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        
        # Count meaningful nodes
        has_implementation = False
        
        for node in ast.iter_child_nodes(tree):
            # Skip imports, docstrings, and __all__
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # docstring
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("__all__", "__version__"):
                        continue
            
            # Check for actual implementation
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                has_implementation = True
                break
            # Also count non-trivial assignments
            if isinstance(node, ast.Assign):
                has_implementation = True
                break
        
        if not has_implementation and len(content.strip()) > 0:
            # Only report if file has some content
            line_count = len([l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")])
            if line_count > 2:  # More than just imports
                findings.append(Finding(
                    file=py_file.relative_to(src_dir.parent.parent),
                    line=1,
                    category="empty_module",
                    description="Module has imports but no implementation",
                    confidence=60,
                ))
    
    return findings


def find_noop_fallbacks(src_dir: Path) -> list[Finding]:
    """Find optional callbacks that silently return mock/no-op results when None.
    
    This detects the pattern:
        if self._callback is None:
            return MockResult(success=True)  # Silent no-op!
    
    This pattern caused the parallel executor bug where tasks completed
    in 0ms without doing any work because no executor callback was provided.
    """
    findings = []
    
    # Keywords that suggest a mock/no-op return value
    mock_indicators = {
        "mock", "noop", "no-op", "dummy", "fake", "stub", 
        "success=true", "completed", "no executor", "no callback",
        "not provided", "not set", "not configured",
    }
    
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        
        lines = content.splitlines()
        
        class NoopFallbackVisitor(ast.NodeVisitor):
            def __init__(self):
                self.findings = []
                self.current_class = None
                self.optional_attrs: set[str] = set()
            
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                old_class = self.current_class
                old_attrs = self.optional_attrs.copy()
                self.current_class = node.name
                self.optional_attrs = set()
                
                # Find __init__ and look for optional callback attributes
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        self._scan_init_for_optional_callbacks(item)
                
                self.generic_visit(node)
                self.current_class = old_class
                self.optional_attrs = old_attrs
            
            def _scan_init_for_optional_callbacks(self, init_node: ast.FunctionDef) -> None:
                """Find optional callback parameters in __init__."""
                for arg in init_node.args.args + init_node.args.kwonlyargs:
                    # Check for Callable | None or Optional[Callable] annotations
                    if arg.annotation:
                        ann_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else ""
                        if "Callable" in ann_str and ("None" in ann_str or "Optional" in ann_str):
                            self.optional_attrs.add(f"_{arg.arg}")
                            self.optional_attrs.add(f"self._{arg.arg}")
                
                # Also check for assignments like self._callback = callback
                for stmt in ast.walk(init_node):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                if target.value.id == "self" and target.attr.startswith("_"):
                                    # Check if assigned from a parameter with "callback", "executor", "handler" etc
                                    if isinstance(stmt.value, ast.Name):
                                        param_name = stmt.value.id.lower()
                                        if any(kw in param_name for kw in ["callback", "executor", "handler", "func", "fn"]):
                                            self.optional_attrs.add(target.attr)
                                            self.optional_attrs.add(f"self.{target.attr}")
            
            def visit_If(self, node: ast.If) -> None:
                """Check for 'if callback is None: return/assign mock' patterns."""
                # Pattern: if self._something is None:
                if isinstance(node.test, ast.Compare):
                    if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Is):
                        if len(node.test.comparators) == 1:
                            comparator = node.test.comparators[0]
                            if isinstance(comparator, ast.Constant) and comparator.value is None:
                                # Check what's being compared
                                left = node.test.left
                                attr_name = None
                                
                                if isinstance(left, ast.Attribute):
                                    if isinstance(left.value, ast.Name) and left.value.id == "self":
                                        attr_name = f"self.{left.attr}"
                                elif isinstance(left, ast.Name):
                                    attr_name = left.id
                                
                                if attr_name:
                                    # Check if name suggests a callback/executor
                                    callback_keywords = ["callback", "executor", "handler", "func", "fn", "hook"]
                                    is_callback_check = (
                                        any(kw in attr_name.lower() for kw in callback_keywords) or
                                        attr_name in self.optional_attrs
                                    )
                                    
                                    if is_callback_check:
                                        # Check body for mock patterns (return or assignment)
                                        self._check_mock_body(node, attr_name)
                
                self.generic_visit(node)
            
            def _check_mock_body(self, if_node: ast.If, attr_name: str) -> None:
                """Check if an if-body contains mock/no-op patterns."""
                # Collect all lines in the if body for context
                body_lines: list[str] = []
                for stmt in if_node.body:
                    if stmt.lineno <= len(lines):
                        body_lines.append(lines[stmt.lineno - 1].lower())
                
                # Also check comments above/in the if block
                if if_node.lineno <= len(lines):
                    # Check line before and the if line itself
                    for offset in range(-1, 3):
                        check_line = if_node.lineno + offset
                        if 0 < check_line <= len(lines):
                            body_lines.append(lines[check_line - 1].lower())
                
                body_text = " ".join(body_lines)
                
                # Check for mock indicators in comments or strings
                if any(ind in body_text for ind in mock_indicators):
                    # Found a mock pattern!
                    self.findings.append(Finding(
                        file=py_file.relative_to(src_dir.parent.parent),
                        line=if_node.lineno,
                        category="noop_fallback",
                        description=f"'{attr_name}' has mock/no-op fallback when None",
                        confidence=90,
                        code_snippet=lines[if_node.lineno - 1].strip() if if_node.lineno <= len(lines) else "",
                    ))
                    return
                
                # Check for return or assignment with success=True
                for stmt in if_node.body:
                    value_node = None
                    if isinstance(stmt, ast.Return) and stmt.value:
                        value_node = stmt.value
                    elif isinstance(stmt, ast.Assign) and stmt.value:
                        value_node = stmt.value
                    
                    if value_node and hasattr(ast, 'unparse'):
                        value_code = ast.unparse(value_node)
                        if "success=True" in value_code:
                            self.findings.append(Finding(
                                file=py_file.relative_to(src_dir.parent.parent),
                                line=if_node.lineno,
                                category="noop_fallback",
                                description=f"'{attr_name}' creates success result when None (silent no-op)",
                                confidence=95,
                                code_snippet=lines[if_node.lineno - 1].strip() if if_node.lineno <= len(lines) else "",
                            ))
                            return
        
        visitor = NoopFallbackVisitor()
        visitor.visit(tree)
        findings.extend(visitor.findings)
    
    return findings


def run_vulture(src_dir: Path, min_confidence: int = 60) -> list[Finding]:
    """Run vulture to find dead code."""
    findings = []
    
    try:
        result = subprocess.run(
            ["vulture", str(src_dir), f"--min-confidence={min_confidence}"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("⚠️  vulture not installed. Run: pip install vulture", file=sys.stderr)
        return findings
    
    # Parse vulture output
    for line in result.stdout.splitlines():
        # Format: path:line: message (confidence%)
        match = re.match(r"(.+):(\d+): (.+) \((\d+)% confidence\)", line)
        if match:
            file_path = Path(match.group(1))
            lineno = int(match.group(2))
            message = match.group(3)
            confidence = int(match.group(4))
            
            try:
                rel_path = file_path.relative_to(src_dir.parent.parent)
            except ValueError:
                rel_path = file_path
            
            findings.append(Finding(
                file=rel_path,
                line=lineno,
                category="dead_code",
                description=message,
                confidence=confidence,
            ))
    
    return findings


def print_findings(findings: list[Finding], category: str | None = None) -> None:
    """Print findings grouped by category."""
    if category:
        findings = [f for f in findings if f.category == category]
    
    if not findings:
        print("✅ No issues found!")
        return
    
    # Group by category
    by_category: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_category[f.category].append(f)
    
    category_names = {
        "dead_code": "🪦 Dead Code",
        "stub": "🚧 Stub Implementations",
        "todo": "📝 TODO/FIXME Markers",
        "orphan_export": "🔗 Orphan Exports",
        "empty_module": "📭 Empty Modules",
        "noop_fallback": "🔌 No-op Fallbacks (unwired callbacks)",
    }
    
    total = len(findings)
    high_confidence = len([f for f in findings if f.confidence >= 90])
    
    print(f"\n{'═' * 70}")
    print(f"  UNWIRED CODE REPORT")
    print(f"  Found {total} issues ({high_confidence} high confidence)")
    print(f"{'═' * 70}\n")
    
    for cat, cat_findings in sorted(by_category.items()):
        cat_findings.sort(key=lambda f: (-f.confidence, str(f.file), f.line))
        print(f"\n{category_names.get(cat, cat)} ({len(cat_findings)} items)")
        print("─" * 60)
        for f in cat_findings[:50]:  # Limit output
            print(f)
        if len(cat_findings) > 50:
            print(f"  ... and {len(cat_findings) - 50} more")
    
    print(f"\n{'═' * 70}")
    print("Confidence: 🟢 ≥90%  🟡 70-89%  🟠 <70%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find unwired/incomplete code")
    parser.add_argument(
        "--category", "-c",
        choices=["all", "dead", "stubs", "todos", "exports", "empty", "noop"],
        default="all",
        help="Category to check (default: all)",
    )
    parser.add_argument(
        "--min-confidence", "-m",
        type=int,
        default=60,
        help="Minimum confidence threshold (default: 60)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()
    
    project_root = get_project_root()
    src_dir = project_root / "src" / "sunwell"
    
    print(f"🔍 Scanning {src_dir}...")
    
    findings: list[Finding] = []
    
    if args.category in ("all", "dead"):
        print("  Running vulture (dead code)...")
        findings.extend(run_vulture(src_dir, args.min_confidence))
    
    if args.category in ("all", "stubs"):
        print("  Finding stubs...")
        findings.extend(find_stubs(src_dir))
    
    if args.category in ("all", "todos"):
        print("  Finding TODOs...")
        findings.extend(find_todos(src_dir))
    
    if args.category in ("all", "exports"):
        print("  Finding orphan exports...")
        findings.extend(find_orphan_exports(src_dir))
    
    if args.category in ("all", "empty"):
        print("  Finding empty modules...")
        findings.extend(find_empty_modules(src_dir))
    
    if args.category in ("all", "noop"):
        print("  Finding no-op fallbacks...")
        findings.extend(find_noop_fallbacks(src_dir))
    
    # Filter by confidence
    findings = [f for f in findings if f.confidence >= args.min_confidence]
    
    if args.json:
        import json
        print(json.dumps([{
            "file": str(f.file),
            "line": f.line,
            "category": f.category,
            "description": f.description,
            "confidence": f.confidence,
        } for f in findings], indent=2))
    else:
        print_findings(findings)


if __name__ == "__main__":
    main()
