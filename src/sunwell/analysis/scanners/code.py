"""Code/software-specific scanner for State DAG (RFC-100).

Scans software projects (Python, JavaScript, Rust, etc.) to build
a State DAG with:
- Nodes: Modules, packages, source files
- Edges: Import relationships, dependencies
- Health probes: Test coverage, lint issues, complexity
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from sunwell.analysis.state_dag import (
    HealthProbeResult,
    StateDagEdge,
    StateDagNode,
)

logger = logging.getLogger(__name__)


class CodeScanner:
    """Scanner for software/code projects.

    Supports:
    - Python (pyproject.toml, setup.py, requirements.txt)
    - JavaScript/TypeScript (package.json, tsconfig.json)
    - Rust (Cargo.toml)
    - Go (go.mod)

    Health probes:
    - test_coverage: Has tests, coverage percentage
    - lint_issues: Ruff/ESLint issues
    - complexity: Cyclomatic complexity
    - freshness: Last modified date
    """

    def __init__(self) -> None:
        """Initialize the code scanner."""
        self._import_cache: dict[str, set[str]] = {}

    async def scan_nodes(self, root: Path) -> list[StateDagNode]:
        """Scan software project for nodes.

        Discovers:
        - Python modules (.py files)
        - JavaScript/TypeScript modules (.js, .ts, .jsx, .tsx)
        - Rust modules (.rs)
        - Go modules (.go)
        - Package directories (__init__.py, package.json)

        Args:
            root: Project root directory

        Returns:
            List of StateDagNode for each artifact
        """
        nodes: list[StateDagNode] = []

        # Detect project type
        project_type = self._detect_project_type(root)
        logger.info(f"Detected project type: {project_type}")

        # Get source extensions based on project type
        extensions = self._get_extensions(project_type)

        # Find all source files
        for ext in extensions:
            for path in root.glob(f"**/*{ext}"):
                if self._should_skip(path):
                    continue

                node = await self._create_node(path, root, project_type)
                nodes.append(node)

        # Add package/module directory nodes
        nodes.extend(await self._create_package_nodes(root, project_type))

        logger.info(f"CodeScanner found {len(nodes)} nodes")
        return nodes

    async def extract_edges(
        self, root: Path, nodes: list[StateDagNode]
    ) -> list[StateDagEdge]:
        """Extract edges between code nodes.

        Extracts:
        - Import relationships
        - Package dependencies

        Args:
            root: Project root directory
            nodes: Already discovered nodes

        Returns:
            List of StateDagEdge representing relationships
        """
        edges: list[StateDagEdge] = []
        node_ids = {n.id for n in nodes}

        # Build module name to node ID mapping
        module_to_node = self._build_module_mapping(nodes, root)

        for node in nodes:
            if node.artifact_type in ("directory", "package"):
                continue

            imports = await self._extract_imports(node.path, root)

            for imp in imports:
                # Try to resolve import to a node
                target_id = self._resolve_import(imp, module_to_node, root)
                if target_id and target_id in node_ids and target_id != node.id:
                    edges.append(
                        StateDagEdge(
                            source=node.id,
                            target=target_id,
                            edge_type="import",
                        )
                    )

        logger.info(f"CodeScanner extracted {len(edges)} edges")
        return edges

    async def run_health_probes(
        self,
        root: Path,
        nodes: list[StateDagNode],
        source_contexts: list | None = None,
    ) -> dict[str, list[HealthProbeResult]]:
        """Run health probes on all nodes.

        Probes:
        - has_tests: Does this module have corresponding tests?
        - lint_clean: Any ruff/ESLint issues?
        - freshness: How recently was it updated?
        - complexity: Is it too complex?

        Args:
            root: Project root directory
            nodes: All discovered nodes
            source_contexts: Optional list of SourceContext (unused by CodeScanner)

        Returns:
            Dict mapping node ID to list of health probe results
        """
        del source_contexts  # Unused by CodeScanner
        results: dict[str, list[HealthProbeResult]] = {}

        # Run project-level lint check once
        lint_issues = await self._run_lint_check(root)

        # Find test files for test coverage check
        test_modules = self._find_test_modules(root)

        for node in nodes:
            probes: list[HealthProbeResult] = []

            if node.artifact_type not in ("directory", "package"):
                # Test coverage probe
                test_result = self._probe_has_tests(node, test_modules, root)
                probes.append(test_result)

                # Lint probe
                lint_result = self._probe_lint(node, lint_issues, root)
                probes.append(lint_result)

                # Freshness probe
                freshness_result = self._probe_freshness(node)
                probes.append(freshness_result)

                # Size/complexity probe
                size_result = self._probe_size(node)
                probes.append(size_result)

            results[node.id] = probes

        return results

    def _detect_project_type(self, root: Path) -> str:
        """Detect the primary language/framework of the project."""
        markers = {
            "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
            "javascript": ["package.json", "tsconfig.json", "jsconfig.json"],
            "rust": ["Cargo.toml"],
            "go": ["go.mod"],
        }

        for lang, files in markers.items():
            for marker in files:
                if (root / marker).exists():
                    return lang

        # Fallback: count files by extension
        counts: dict[str, int] = {}
        ext_to_lang = [
            (".py", "python"), (".js", "javascript"), (".ts", "javascript"),
            (".rs", "rust"), (".go", "go"),
        ]
        for ext, lang in ext_to_lang:
            counts[lang] = counts.get(lang, 0) + len(list(root.glob(f"**/*{ext}")))

        return max(counts, key=lambda k: counts[k]) if counts else "unknown"

    def _get_extensions(self, project_type: str) -> list[str]:
        """Get file extensions for a project type."""
        extensions = {
            "python": [".py"],
            "javascript": [".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
            "rust": [".rs"],
            "go": [".go"],
            "unknown": [".py", ".js", ".ts"],
        }
        return extensions.get(project_type, extensions["unknown"])

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped during scanning."""
        skip_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".tox",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "htmlcov",
            "target",  # Rust
            ".next",  # Next.js
            ".nuxt",  # Nuxt.js
            "coverage",
            ".coverage",
            "egg-info",
            ".cursor",  # Cursor IDE
            ".idea",  # JetBrains
            ".vscode",  # VS Code
        }
        skip_prefixes = (".venv", "venv", ".env", "env")
        parts = path.parts
        for part in parts:
            if part in skip_dirs or part.endswith(".egg-info"):
                return True
            if any(part.startswith(prefix) for prefix in skip_prefixes):
                return True
        return False

    async def _create_node(
        self, path: Path, root: Path, project_type: str
    ) -> StateDagNode:
        """Create a StateDagNode for a source file."""
        rel_path = path.relative_to(root)
        node_id = str(rel_path).replace("/", "-").replace("\\", "-").replace(".", "-")

        # Get file stats
        stat = path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime)

        # Count lines
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            line_count = len(content.splitlines())
        except Exception:
            line_count = 0

        # Determine title from module name
        title = self._get_module_title(path, project_type)

        # Determine artifact type
        artifact_type = self._get_artifact_type(path, project_type)

        return StateDagNode(
            id=node_id,
            path=path,
            artifact_type=artifact_type,
            title=title,
            health_score=1.0,  # Will be updated by health probes
            health_probes=(),
            last_modified=last_modified,
            line_count=line_count,
            metadata={"project_type": project_type},
        )

    async def _create_package_nodes(
        self, root: Path, project_type: str
    ) -> list[StateDagNode]:
        """Create nodes for packages/modules."""
        package_nodes: list[StateDagNode] = []

        if project_type == "python":
            # Find all __init__.py files (Python packages)
            for init_file in root.glob("**/__init__.py"):
                if self._should_skip(init_file):
                    continue

                pkg_dir = init_file.parent
                rel_path = pkg_dir.relative_to(root)
                node_id = f"pkg-{str(rel_path).replace('/', '-').replace('\\', '-')}"

                # Count modules in package
                py_files = len(list(pkg_dir.glob("*.py"))) - 1  # Exclude __init__.py

                package_nodes.append(
                    StateDagNode(
                        id=node_id,
                        path=pkg_dir,
                        artifact_type="package",
                        title=pkg_dir.name,
                        health_score=1.0,
                        health_probes=(),
                        metadata={"module_count": py_files},
                    )
                )

        return package_nodes

    def _get_module_title(self, path: Path, project_type: str) -> str:
        """Get a human-readable title for a module."""
        stem = path.stem

        # Special cases
        if stem == "__init__":
            return f"{path.parent.name} (package)"
        if stem == "__main__":
            return f"{path.parent.name} (main)"

        # Convert snake_case to Title Case
        return stem.replace("_", " ").title()

    def _get_artifact_type(self, path: Path, project_type: str) -> str:
        """Determine the artifact type for a file."""
        stem = path.stem
        parts = path.parts

        # Test files
        if "test" in stem or "tests" in parts or "_test" in stem or "test_" in stem:
            return "test"

        # Config files
        if stem in ("config", "settings", "conf", "configuration"):
            return "config"

        # Entry points
        if stem in ("main", "__main__", "cli", "app", "index"):
            return "entry"

        # Model/Type definitions
        if stem in ("types", "models", "schemas", "interfaces"):
            return "types"

        return "module"

    def _build_module_mapping(
        self, nodes: list[StateDagNode], root: Path
    ) -> dict[str, str]:
        """Build mapping from module names to node IDs."""
        mapping: dict[str, str] = {}

        for node in nodes:
            if node.artifact_type in ("directory", "package"):
                continue

            # Python module: path relative to root as dotted module
            rel = node.path.relative_to(root)
            parts = list(rel.parts)
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__":
                parts = parts[:-1]

            module_name = ".".join(parts)
            mapping[module_name] = node.id

            # Also map the filename directly
            mapping[node.path.stem] = node.id

        return mapping

    async def _extract_imports(self, path: Path, root: Path) -> list[str]:
        """Extract imports from a source file."""
        suffix = path.suffix.lower()

        if suffix == ".py":
            return self._extract_python_imports(path)
        elif suffix in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"):
            return self._extract_js_imports(path)
        elif suffix == ".rs":
            return self._extract_rust_imports(path)
        elif suffix == ".go":
            return self._extract_go_imports(path)

        return []

    def _extract_python_imports(self, path: Path) -> list[str]:
        """Extract imports from a Python file using AST."""
        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception:
            return []

        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])

        return imports

    def _extract_js_imports(self, path: Path) -> list[str]:
        """Extract imports from a JavaScript/TypeScript file."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        imports: list[str] = []

        # ES6 imports: import ... from 'module'
        es6_pattern = r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"
        imports.extend(re.findall(es6_pattern, content))

        # CommonJS: require('module')
        cjs_pattern = r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
        imports.extend(re.findall(cjs_pattern, content))

        # Filter to local imports (starting with . or /)
        local_imports = [imp for imp in imports if imp.startswith((".", "/"))]

        return local_imports

    def _extract_rust_imports(self, path: Path) -> list[str]:
        """Extract imports from a Rust file."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        imports: list[str] = []

        # use statements: use crate::module or use super::module
        use_pattern = r"use\s+(crate|super|self)::([^;{]+)"
        for match in re.finditer(use_pattern, content):
            path_part = match.group(2).split("::")[0].strip()
            imports.append(path_part)

        # mod statements: mod module;
        mod_pattern = r"mod\s+(\w+)\s*;"
        imports.extend(re.findall(mod_pattern, content))

        return imports

    def _extract_go_imports(self, path: Path) -> list[str]:
        """Extract imports from a Go file."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        imports: list[str] = []

        # import "package" or import ( ... )
        import_block = re.search(r"import\s*\(([^)]+)\)", content, re.DOTALL)
        if import_block:
            for line in import_block.group(1).split("\n"):
                match = re.search(r'"([^"]+)"', line)
                if match:
                    imports.append(match.group(1))

        single_imports = re.findall(r'import\s+"([^"]+)"', content)
        imports.extend(single_imports)

        return imports

    def _resolve_import(
        self, imp: str, module_to_node: dict[str, str], root: Path
    ) -> str | None:
        """Resolve an import to a node ID."""
        # Direct match
        if imp in module_to_node:
            return module_to_node[imp]

        # Try first part of dotted import
        first_part = imp.split(".")[0]
        if first_part in module_to_node:
            return module_to_node[first_part]

        # Try relative path resolution
        if imp.startswith("."):
            clean_imp = imp.lstrip("./")
            if clean_imp in module_to_node:
                return module_to_node[clean_imp]

        return None

    async def _run_lint_check(self, root: Path) -> dict[Path, list[str]]:
        """Run linter and collect issues by file."""
        issues: dict[Path, list[str]] = {}

        # Try ruff for Python projects
        if (root / "pyproject.toml").exists() or any(root.glob("**/*.py")):
            try:
                result = subprocess.run(
                    ["ruff", "check", "--output-format=json", str(root)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.stdout:
                    import json
                    lint_output = json.loads(result.stdout)
                    for issue in lint_output:
                        file_path = Path(issue.get("filename", ""))
                        if file_path not in issues:
                            issues[file_path] = []
                        issues[file_path].append(
                            f"{issue.get('code', 'E')}: {issue.get('message', '')}"
                        )
            except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
                pass

        return issues

    def _find_test_modules(self, root: Path) -> set[str]:
        """Find all test modules in the project."""
        test_modules: set[str] = set()

        for path in root.glob("**/*.py"):
            if self._should_skip(path):
                continue

            stem = path.stem
            if "test" in stem.lower() or "tests" in path.parts:
                # Map test file to its corresponding module
                # test_foo.py -> foo
                # foo_test.py -> foo
                if stem.startswith("test_"):
                    test_modules.add(stem[5:])
                elif stem.endswith("_test"):
                    test_modules.add(stem[:-5])
                elif stem.startswith("tests_"):
                    test_modules.add(stem[6:])
                else:
                    test_modules.add(stem)

        return test_modules

    def _probe_has_tests(
        self, node: StateDagNode, test_modules: set[str], root: Path
    ) -> HealthProbeResult:
        """Check if a module has corresponding tests."""
        # Test files don't need their own tests
        if node.artifact_type == "test":
            return HealthProbeResult(
                probe_name="has_tests",
                score=1.0,
                issues=(),
            )

        # Config files don't need tests
        if node.artifact_type == "config":
            return HealthProbeResult(
                probe_name="has_tests",
                score=1.0,
                issues=(),
            )

        module_name = node.path.stem

        # __init__.py doesn't need dedicated tests
        if module_name == "__init__":
            return HealthProbeResult(
                probe_name="has_tests",
                score=1.0,
                issues=(),
            )

        if module_name in test_modules:
            return HealthProbeResult(
                probe_name="has_tests",
                score=1.0,
                issues=(),
            )

        # No tests found
        return HealthProbeResult(
            probe_name="has_tests",
            score=0.5,
            issues=(f"No tests found for {module_name}",),
        )

    def _probe_lint(
        self, node: StateDagNode, lint_issues: dict[Path, list[str]], root: Path
    ) -> HealthProbeResult:
        """Check lint status for a file."""
        file_issues = lint_issues.get(node.path, [])

        if not file_issues:
            return HealthProbeResult(
                probe_name="lint_clean",
                score=1.0,
                issues=(),
            )

        issue_count = len(file_issues)
        if issue_count <= 3:
            return HealthProbeResult(
                probe_name="lint_clean",
                score=0.8,
                issues=tuple(file_issues[:3]),
            )
        elif issue_count <= 10:
            return HealthProbeResult(
                probe_name="lint_clean",
                score=0.6,
                issues=tuple(file_issues[:5]),
                metadata={"total_issues": issue_count},
            )
        else:
            return HealthProbeResult(
                probe_name="lint_clean",
                score=0.3,
                issues=tuple(file_issues[:5]),
                metadata={"total_issues": issue_count},
            )

    def _probe_freshness(self, node: StateDagNode) -> HealthProbeResult:
        """Check if a file is stale."""
        if not node.last_modified:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.5,
                issues=("Could not determine last modified date",),
            )

        days_old = (datetime.now() - node.last_modified).days

        if days_old <= 30:
            return HealthProbeResult(
                probe_name="freshness",
                score=1.0,
                issues=(),
                metadata={"days_old": days_old},
            )
        elif days_old <= 90:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.9,
                issues=(),
                metadata={"days_old": days_old},
            )
        elif days_old <= 180:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.7,
                issues=(),
                metadata={"days_old": days_old},
            )
        else:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.6,
                issues=(f"File not updated in {days_old} days",),
                metadata={"days_old": days_old},
            )

    def _probe_size(self, node: StateDagNode) -> HealthProbeResult:
        """Check if file size/complexity is appropriate."""
        if not node.line_count:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.5,
                issues=("Could not determine file size",),
            )

        lines = node.line_count

        if lines <= 500:
            return HealthProbeResult(
                probe_name="size_check",
                score=1.0,
                issues=(),
                metadata={"line_count": lines},
            )
        elif lines <= 1000:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.8,
                issues=("File is getting large - consider refactoring",),
                metadata={"line_count": lines},
            )
        elif lines <= 2000:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.5,
                issues=(f"File is large ({lines} lines) - should be split",),
                metadata={"line_count": lines},
            )
        else:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.3,
                issues=(f"File is very large ({lines} lines) - needs refactoring",),
                metadata={"line_count": lines},
            )
