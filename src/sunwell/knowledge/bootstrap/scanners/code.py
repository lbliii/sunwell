"""Code Scanner — RFC-050.

Analyze code patterns without execution: naming, types, docstrings.
"""


import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sunwell.bootstrap.types import (
    CodeEvidence,
    DocstringStyle,
    ImportPatterns,
    ModuleStructure,
    NamingPatterns,
    TestPatterns,
    TypeHintUsage,
)


@dataclass(frozen=True, slots=True)
class ParsedFile:
    """Parsed Python file with extracted names."""

    path: Path
    function_names: tuple[str, ...]
    class_names: tuple[str, ...]
    constant_names: tuple[str, ...]
    private_names: tuple[str, ...]
    docstrings: tuple[str, ...]
    has_type_hints: bool
    uses_modern_types: bool
    import_lines: tuple[str, ...]


class CodeScanner:
    """Analyze code patterns without execution."""

    # Directories to skip
    SKIP_DIRS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        ".env",
        "node_modules",
        "vendor",
        "dist",
        "build",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }

    def __init__(
        self,
        root: Path,
        include_globs: list[str] | None = None,
        max_files: int = 500,
    ):
        """Initialize code scanner.

        Args:
            root: Project root directory
            include_globs: Glob patterns for files to include
            max_files: Maximum number of files to scan
        """
        self.root = Path(root)
        self.include_globs = include_globs or ["**/*.py"]
        self.max_files = max_files

    async def scan(self) -> CodeEvidence:
        """Scan codebase and extract patterns."""
        files = self._collect_files()
        parsed = self._parse_files(files)

        return CodeEvidence(
            naming_patterns=self._analyze_naming(parsed),
            import_patterns=self._analyze_imports(parsed),
            type_hint_usage=self._analyze_type_hints(parsed),
            docstring_style=self._analyze_docstrings(parsed),
            module_structure=self._analyze_structure(files, parsed),
            test_patterns=self._analyze_tests(parsed),
        )

    def _collect_files(self) -> list[Path]:
        """Collect Python files to analyze."""
        files: list[Path] = []

        for pattern in self.include_globs:
            for file_path in self.root.glob(pattern):
                if not file_path.is_file():
                    continue

                # Skip excluded directories
                if any(part in self.SKIP_DIRS for part in file_path.parts):
                    continue

                files.append(file_path)

                if len(files) >= self.max_files:
                    break

        return files

    def _parse_files(self, files: list[Path]) -> list[ParsedFile]:
        """Parse all files and extract names."""
        parsed: list[ParsedFile] = []

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content)

                function_names: list[str] = []
                class_names: list[str] = []
                constant_names: list[str] = []
                private_names: list[str] = []
                docstrings: list[str] = []
                has_type_hints = False
                uses_modern_types = False
                import_lines: list[str] = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                        function_names.append(node.name)
                        if node.name.startswith("_"):
                            private_names.append(node.name)

                        # Check for type hints
                        if node.returns or any(arg.annotation for arg in node.args.args):
                            has_type_hints = True

                        # Check for docstring
                        if (node.body and isinstance(node.body[0], ast.Expr) and
                                isinstance(node.body[0].value, ast.Constant) and
                                isinstance(node.body[0].value.value, str)):
                            docstrings.append(node.body[0].value.value)

                    elif isinstance(node, ast.ClassDef):
                        class_names.append(node.name)

                        # Check class docstring
                        if (node.body and isinstance(node.body[0], ast.Expr) and
                                isinstance(node.body[0].value, ast.Constant) and
                                isinstance(node.body[0].value.value, str)):
                            docstrings.append(node.body[0].value.value)

                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                name = target.id
                                if name.isupper() and "_" in name:
                                    constant_names.append(name)

                    elif isinstance(node, ast.Import | ast.ImportFrom):
                        import_lines.append(ast.unparse(node))

                    # Check for modern type syntax (list[] vs List[])
                    elif isinstance(node, ast.Subscript):
                        is_builtin = (
                            isinstance(node.value, ast.Name) and
                            node.value.id in ("list", "dict", "set", "tuple")
                        )
                        if is_builtin:
                            uses_modern_types = True

                    # Check for union syntax (X | Y)
                    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                        uses_modern_types = True

                parsed.append(ParsedFile(
                    path=file_path,
                    function_names=tuple(function_names),
                    class_names=tuple(class_names),
                    constant_names=tuple(constant_names),
                    private_names=tuple(private_names),
                    docstrings=tuple(docstrings),
                    has_type_hints=has_type_hints,
                    uses_modern_types=uses_modern_types,
                    import_lines=tuple(import_lines),
                ))

            except (SyntaxError, UnicodeDecodeError, OSError):
                # Skip files that can't be parsed
                continue

        return parsed

    def _analyze_naming(self, parsed: list[ParsedFile]) -> NamingPatterns:
        """Analyze naming conventions across codebase."""
        function_names: list[str] = []
        class_names: list[str] = []
        constant_names: list[str] = []
        private_names: list[str] = []

        for file in parsed:
            function_names.extend(file.function_names)
            class_names.extend(file.class_names)
            constant_names.extend(file.constant_names)
            private_names.extend(file.private_names)

        return NamingPatterns(
            function_style=self._classify_style(function_names, "function"),
            function_samples=len(function_names),
            class_style=self._classify_style(class_names, "class"),
            class_samples=len(class_names),
            constant_style=self._classify_style(constant_names, "constant"),
            constant_samples=len(constant_names),
            private_prefix=self._classify_private(private_names),
            private_samples=len(private_names),
        )

    def _classify_style(
        self,
        names: list[str],
        name_type: str,
    ) -> Literal["snake_case", "camelCase", "PascalCase", "UPPER_SNAKE", "mixed"]:
        """Classify naming style from samples."""
        if not names:
            return "mixed"

        snake = sum(1 for n in names if self._is_snake_case(n))
        camel = sum(1 for n in names if self._is_camel_case(n))
        pascal = sum(1 for n in names if self._is_pascal_case(n))
        upper = sum(1 for n in names if self._is_upper_snake(n))

        total = len(names)
        threshold = 0.7

        if snake / total > threshold:
            return "snake_case"
        elif camel / total > threshold:
            return "camelCase"
        elif pascal / total > threshold:
            return "PascalCase"
        elif upper / total > threshold:
            return "UPPER_SNAKE"
        else:
            return "mixed"

    def _is_snake_case(self, name: str) -> bool:
        """Check if name is snake_case."""
        if not name or name.startswith("_"):
            name = name.lstrip("_")
        if not name:
            return False
        return bool(re.match(r"^[a-z][a-z0-9_]*$", name))

    def _is_camel_case(self, name: str) -> bool:
        """Check if name is camelCase."""
        if not name:
            return False
        return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", name)) and any(c.isupper() for c in name)

    def _is_pascal_case(self, name: str) -> bool:
        """Check if name is PascalCase."""
        if not name:
            return False
        return bool(re.match(r"^[A-Z][a-zA-Z0-9]*$", name))

    def _is_upper_snake(self, name: str) -> bool:
        """Check if name is UPPER_SNAKE_CASE."""
        if not name:
            return False
        return bool(re.match(r"^[A-Z][A-Z0-9_]*$", name)) and "_" in name

    def _classify_private(
        self,
        names: list[str],
    ) -> Literal["_", "__", "none", "mixed"]:
        """Classify private naming convention."""
        if not names:
            return "none"

        single = sum(1 for n in names if n.startswith("_") and not n.startswith("__"))
        double = sum(1 for n in names if n.startswith("__") and not n.startswith("___"))

        total = len(names)
        threshold = 0.7

        if single / total > threshold:
            return "_"
        elif double / total > threshold:
            return "__"
        else:
            return "mixed"

    def _analyze_imports(self, parsed: list[ParsedFile]) -> ImportPatterns:
        """Analyze import organization style."""
        absolute_count = 0
        relative_count = 0
        files_with_imports = 0

        for file in parsed:
            if not file.import_lines:
                continue

            files_with_imports += 1

            for imp in file.import_lines:
                if "from ." in imp:
                    relative_count += 1
                else:
                    absolute_count += 1

        total = absolute_count + relative_count
        if total == 0:
            return ImportPatterns(
                style="absolute",
                groups_stdlib=False,
                groups_third_party=False,
                samples=0,
            )

        threshold = 0.7
        if absolute_count / total > threshold:
            style = "absolute"
        elif relative_count / total > threshold:
            style = "relative"
        else:
            style = "mixed"

        return ImportPatterns(
            style=style,
            groups_stdlib=True,  # Would need more analysis
            groups_third_party=True,
            samples=files_with_imports,
        )

    def _analyze_type_hints(self, parsed: list[ParsedFile]) -> TypeHintUsage:
        """Analyze type annotation prevalence."""
        files_with_hints = sum(1 for f in parsed if f.has_type_hints)
        files_total = len(parsed)
        uses_modern = any(f.uses_modern_types for f in parsed)

        if files_total == 0:
            return TypeHintUsage(
                level="none",
                functions_with_hints=0,
                functions_total=0,
                uses_modern_syntax=False,
            )

        ratio = files_with_hints / files_total

        if ratio >= 0.8:
            level = "comprehensive"
        elif ratio >= 0.5:
            level = "public_only"
        elif ratio >= 0.1:
            level = "minimal"
        else:
            level = "none"

        # Count functions (approximation based on parsed files)
        functions_with_hints = sum(1 for f in parsed if f.has_type_hints)
        functions_total = sum(len(f.function_names) for f in parsed)

        return TypeHintUsage(
            level=level,
            functions_with_hints=functions_with_hints,
            functions_total=functions_total,
            uses_modern_syntax=uses_modern,
        )

    def _analyze_docstrings(self, parsed: list[ParsedFile]) -> DocstringStyle:
        """Detect docstring format from samples."""
        all_docstrings: list[str] = []
        for file in parsed:
            all_docstrings.extend(file.docstrings)

        if not all_docstrings:
            return DocstringStyle(style="none", samples=0, consistency=1.0)

        google_count = sum(1 for d in all_docstrings if self._is_google_docstring(d))
        numpy_count = sum(1 for d in all_docstrings if self._is_numpy_docstring(d))
        sphinx_count = sum(1 for d in all_docstrings if self._is_sphinx_docstring(d))

        total = len(all_docstrings)

        if google_count / total > 0.5:
            return DocstringStyle(
                style="google",
                samples=total,
                consistency=google_count / total,
            )
        elif numpy_count / total > 0.5:
            return DocstringStyle(
                style="numpy",
                samples=total,
                consistency=numpy_count / total,
            )
        elif sphinx_count / total > 0.5:
            return DocstringStyle(
                style="sphinx",
                samples=total,
                consistency=sphinx_count / total,
            )
        else:
            return DocstringStyle(
                style="mixed",
                samples=total,
                consistency=0.0,
            )

    def _is_google_docstring(self, docstring: str) -> bool:
        """Check if docstring follows Google style."""
        patterns = ["Args:", "Returns:", "Raises:", "Yields:", "Attributes:"]
        return any(p in docstring for p in patterns)

    def _is_numpy_docstring(self, docstring: str) -> bool:
        """Check if docstring follows NumPy style."""
        patterns = ["Parameters\n", "Returns\n", "Raises\n", "----------"]
        return any(p in docstring for p in patterns)

    def _is_sphinx_docstring(self, docstring: str) -> bool:
        """Check if docstring follows Sphinx style."""
        patterns = [":param ", ":return:", ":returns:", ":raises:", ":type "]
        return any(p in docstring for p in patterns)

    def _analyze_structure(
        self,
        files: list[Path],
        parsed: list[ParsedFile],
    ) -> ModuleStructure:
        """Analyze directory organization patterns."""
        has_src_layout = any("src" in f.parts for f in files)
        has_tests_dir = any("tests" in f.parts or "test" in f.parts for f in files)

        # Try to detect package name
        package_name = None
        if has_src_layout:
            src_dir = self.root / "src"
            if src_dir.exists():
                subdirs = [d for d in src_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
                if len(subdirs) == 1:
                    package_name = subdirs[0].name
        else:
            # Look for pyproject.toml to get package name
            pyproject = self.root / "pyproject.toml"
            if pyproject.exists():
                try:
                    content = pyproject.read_text()
                    match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        package_name = match.group(1).replace("-", "_")
                except OSError:
                    pass

        # Collect modules
        modules = set()
        for f in files:
            # Get module path relative to root
            try:
                rel = f.relative_to(self.root)
                if rel.parts:
                    modules.add(rel.parts[0])
            except ValueError:
                pass

        # Collect all function and class names
        all_functions: list[str] = []
        all_classes: list[str] = []
        for p in parsed:
            all_functions.extend(p.function_names)
            all_classes.extend(p.class_names)

        return ModuleStructure(
            has_src_layout=has_src_layout,
            has_tests_dir=has_tests_dir,
            package_name=package_name,
            modules=tuple(sorted(modules)),
            functions=tuple(all_functions),
            classes=tuple(all_classes),
        )

    def _analyze_tests(self, parsed: list[ParsedFile]) -> TestPatterns:
        """Analyze testing conventions and patterns."""
        test_files = [p for p in parsed if "test" in p.path.name.lower()]
        test_functions = sum(
            1 for p in test_files for f in p.function_names if f.startswith("test_")
        )

        uses_fixtures = False
        uses_mocks = False

        for p in test_files:
            for imp in p.import_lines:
                if "pytest" in imp:
                    uses_fixtures = True
                if "mock" in imp.lower() or "patch" in imp:
                    uses_mocks = True

        framework: Literal["pytest", "unittest", "nose", "none"] = "none"
        for p in test_files:
            for imp in p.import_lines:
                if "pytest" in imp:
                    framework = "pytest"
                    break
                elif "unittest" in imp:
                    framework = "unittest"

        return TestPatterns(
            framework=framework,
            uses_fixtures=uses_fixtures,
            uses_mocks=uses_mocks,
            test_count=test_functions,
        )
