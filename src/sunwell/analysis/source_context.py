"""Source code context for drift detection (RFC-103).

Provides symbol indexing for linked source code repositories,
enabling drift detection between documentation and source.

Example:
    ctx = await SourceContext.build(Path("~/acme-core"))
    symbol = ctx.lookup("auth.login")
    # SymbolInfo(name="login", kind="function", deprecated=True, replacement="sign_in")
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Information about a symbol in source code."""

    name: str
    """Fully qualified name (e.g., 'auth.login', 'User.create')."""

    kind: Literal["function", "class", "method", "constant", "variable", "module"]
    """Type of symbol."""

    file: Path
    """File where the symbol is defined."""

    line: int
    """Line number of the definition."""

    signature: str | None = None
    """Function/method signature (e.g., 'login(username: str, password: str) -> Token')."""

    docstring: str | None = None
    """First line of docstring if available."""

    deprecated: bool = False
    """Whether the symbol is marked as deprecated."""

    replacement: str | None = None
    """Suggested replacement if deprecated."""


@dataclass
class SourceContext:
    """Indexed source code context for drift detection.

    Provides fast symbol lookup for validating documentation claims
    against actual source code. Uses AST parsing for Python and
    regex-based extraction for other languages.

    Performance target: <2s for 10k line project.
    """

    root: Path
    """Source code root directory."""

    language: str
    """Primary language (python, typescript, go, rust)."""

    symbols: dict[str, SymbolInfo]
    """All indexed symbols, keyed by fully qualified name."""

    indexed_at: datetime = field(default_factory=datetime.now)
    """When the index was built."""

    file_count: int = 0
    """Number of files indexed."""

    symbol_count: int = 0
    """Total number of symbols indexed."""

    @classmethod
    async def build(cls, root: Path, language: str | None = None) -> SourceContext:
        """Index source code for drift detection.

        Args:
            root: Source code root directory.
            language: Language override (auto-detected if not provided).

        Returns:
            SourceContext with indexed symbols.

        Target: <2s for 10k line project.
        """
        root = Path(root).expanduser().resolve()

        # Auto-detect language
        if not language:
            language = _detect_language(root)

        logger.info(f"Indexing {language} source at {root}")

        # Index based on language
        if language == "python":
            symbols, file_count = await _index_python(root)
        elif language == "typescript":
            symbols, file_count = await _index_typescript(root)
        else:
            # Fallback to basic extraction
            symbols, file_count = await _index_generic(root, language)

        return cls(
            root=root,
            language=language,
            symbols=symbols,
            file_count=file_count,
            symbol_count=len(symbols),
        )

    def lookup(self, name: str) -> SymbolInfo | None:
        """Look up a symbol by name.

        Supports:
        - Exact match: "auth.login"
        - Partial match: "login" (finds first match)
        - Method lookup: "User.create"

        Args:
            name: Symbol name to look up.

        Returns:
            SymbolInfo if found, None otherwise.
        """
        # Exact match
        if name in self.symbols:
            return self.symbols[name]

        # Try with normalized case
        name_lower = name.lower()
        for key, symbol in self.symbols.items():
            if key.lower() == name_lower:
                return symbol

        # Partial match (symbol name without module prefix)
        for key, symbol in self.symbols.items():
            if key.endswith(f".{name}") or key.split(".")[-1] == name:
                return symbol

        return None

    def search(self, pattern: str) -> list[SymbolInfo]:
        """Search for symbols matching a pattern.

        Args:
            pattern: Regex pattern to match against symbol names.

        Returns:
            List of matching SymbolInfo.
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Treat as literal string if invalid regex
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        return [s for name, s in self.symbols.items() if regex.search(name)]

    def find_deprecated(self) -> list[SymbolInfo]:
        """Find all deprecated symbols."""
        return [s for s in self.symbols.values() if s.deprecated]


def _detect_language(root: Path) -> str:
    """Detect primary language of a source directory."""
    markers = [
        ("pyproject.toml", "python"),
        ("setup.py", "python"),
        ("package.json", "typescript"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
    ]
    for marker, lang in markers:
        if (root / marker).exists():
            return lang
    return "unknown"


async def _index_python(root: Path) -> tuple[dict[str, SymbolInfo], int]:
    """Index Python source using AST parsing.

    Extracts:
    - Functions and their signatures
    - Classes and their methods
    - Module-level constants
    - Deprecation markers from decorators and docstrings
    """
    symbols: dict[str, SymbolInfo] = {}
    file_count = 0

    # Skip directories that shouldn't be indexed
    skip_dirs = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        ".tox",
        "node_modules",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
    }

    for py_file in root.glob("**/*.py"):
        # Skip files in excluded directories
        if any(skip in py_file.parts for skip in skip_dirs):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(py_file))
            file_count += 1

            # Calculate module name from path
            rel_path = py_file.relative_to(root)
            if rel_path.name == "__init__.py":
                module_name = ".".join(rel_path.parent.parts)
            else:
                module_name = ".".join(rel_path.with_suffix("").parts)

            # Add module itself as a symbol
            if module_name:
                symbols[module_name] = SymbolInfo(
                    name=module_name,
                    kind="module",
                    file=py_file,
                    line=1,
                )

            # Extract symbols from AST
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    symbol = _extract_function(node, module_name, py_file)
                    if symbol:
                        symbols[symbol.name] = symbol

                elif isinstance(node, ast.ClassDef):
                    class_symbol = _extract_class(node, module_name, py_file)
                    if class_symbol:
                        symbols[class_symbol.name] = class_symbol

                    # Extract methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                            method_symbol = _extract_function(
                                item,
                                f"{module_name}.{node.name}" if module_name else node.name,
                                py_file,
                            )
                            if method_symbol:
                                # Mark as method
                                symbols[method_symbol.name] = SymbolInfo(
                                    name=method_symbol.name,
                                    kind="method",
                                    file=method_symbol.file,
                                    line=method_symbol.line,
                                    signature=method_symbol.signature,
                                    docstring=method_symbol.docstring,
                                    deprecated=method_symbol.deprecated,
                                    replacement=method_symbol.replacement,
                                )

                elif isinstance(node, ast.Assign):
                    # Module-level constants (UPPER_CASE names)
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            const_name = f"{module_name}.{target.id}" if module_name else target.id
                            symbols[const_name] = SymbolInfo(
                                name=const_name,
                                kind="constant",
                                file=py_file,
                                line=node.lineno,
                            )

        except SyntaxError as e:
            logger.debug(f"Syntax error in {py_file}: {e}")
        except Exception as e:
            logger.debug(f"Error indexing {py_file}: {e}")

    logger.info(f"Indexed {len(symbols)} Python symbols from {file_count} files")
    return symbols, file_count


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module_name: str,
    file: Path,
) -> SymbolInfo | None:
    """Extract function information from AST node."""
    # Skip private methods (start with _)
    if node.name.startswith("_") and not node.name.startswith("__"):
        return None

    full_name = f"{module_name}.{node.name}" if module_name else node.name

    # Build signature
    signature = _build_signature(node)

    # Get docstring
    docstring = ast.get_docstring(node)
    if docstring:
        # Just first line
        docstring = docstring.split("\n")[0].strip()

    # Check for deprecation
    deprecated, replacement = _check_deprecation(node, docstring)

    return SymbolInfo(
        name=full_name,
        kind="function",
        file=file,
        line=node.lineno,
        signature=signature,
        docstring=docstring,
        deprecated=deprecated,
        replacement=replacement,
    )


def _extract_class(node: ast.ClassDef, module_name: str, file: Path) -> SymbolInfo | None:
    """Extract class information from AST node."""
    # Skip private classes
    if node.name.startswith("_"):
        return None

    full_name = f"{module_name}.{node.name}" if module_name else node.name

    # Get docstring
    docstring = ast.get_docstring(node)
    if docstring:
        docstring = docstring.split("\n")[0].strip()

    # Check for deprecation
    deprecated, replacement = _check_deprecation(node, docstring)

    return SymbolInfo(
        name=full_name,
        kind="class",
        file=file,
        line=node.lineno,
        docstring=docstring,
        deprecated=deprecated,
        replacement=replacement,
    )


def _build_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build function signature string from AST."""
    parts = []

    # Positional args
    for arg in node.args.args:
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f": {ast.unparse(arg.annotation)}"
        parts.append(arg_str)

    # *args
    if node.args.vararg:
        arg_str = f"*{node.args.vararg.arg}"
        if node.args.vararg.annotation:
            arg_str += f": {ast.unparse(node.args.vararg.annotation)}"
        parts.append(arg_str)

    # **kwargs
    if node.args.kwarg:
        arg_str = f"**{node.args.kwarg.arg}"
        if node.args.kwarg.annotation:
            arg_str += f": {ast.unparse(node.args.kwarg.annotation)}"
        parts.append(arg_str)

    sig = f"{node.name}({', '.join(parts)})"

    # Return type
    if node.returns:
        sig += f" -> {ast.unparse(node.returns)}"

    return sig


def _check_deprecation(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    docstring: str | None,
) -> tuple[bool, str | None]:
    """Check if a symbol is deprecated."""
    deprecated = False
    replacement = None

    # Check decorators
    for decorator in node.decorator_list:
        dec_name = ""
        if isinstance(decorator, ast.Name):
            dec_name = decorator.id
        elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
            dec_name = decorator.func.id
        elif isinstance(decorator, ast.Attribute):
            dec_name = decorator.attr

        if dec_name.lower() in ("deprecated", "deprecate", "deprecation_warning"):
            deprecated = True
            # Try to extract replacement from decorator args
            if isinstance(decorator, ast.Call) and decorator.args:
                first_arg = decorator.args[0]
                if isinstance(first_arg, ast.Constant):
                    replacement = str(first_arg.value)
            break

    # Check docstring for deprecation markers
    if docstring:
        doc_lower = docstring.lower()
        if "deprecated" in doc_lower or ".. deprecated::" in doc_lower:
            deprecated = True
            # Try to extract replacement
            match = re.search(r"use\s+[`']?(\w+)[`']?\s+instead", doc_lower)
            if match:
                replacement = match.group(1)

    return deprecated, replacement


async def _index_typescript(root: Path) -> tuple[dict[str, SymbolInfo], int]:
    """Index TypeScript source using regex-based extraction.

    Extracts:
    - Exported functions
    - Exported classes
    - Exported interfaces
    - Type definitions
    """
    symbols: dict[str, SymbolInfo] = {}
    file_count = 0

    skip_dirs = {"node_modules", ".git", "dist", "build", "coverage"}

    # TypeScript patterns
    function_pattern = re.compile(
        r"export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*([^{]+))?",
        re.MULTILINE,
    )
    class_pattern = re.compile(r"export\s+class\s+(\w+)", re.MULTILINE)
    interface_pattern = re.compile(r"export\s+interface\s+(\w+)", re.MULTILINE)
    type_pattern = re.compile(r"export\s+type\s+(\w+)", re.MULTILINE)
    const_pattern = re.compile(r"export\s+const\s+(\w+)\s*[:=]", re.MULTILINE)

    for ts_file in root.glob("**/*.ts"):
        if any(skip in ts_file.parts for skip in skip_dirs):
            continue

        try:
            content = ts_file.read_text(encoding="utf-8", errors="ignore")
            file_count += 1

            # Calculate module name
            rel_path = ts_file.relative_to(root)
            if rel_path.name == "index.ts":
                module_name = "/".join(rel_path.parent.parts)
            else:
                module_name = "/".join(rel_path.with_suffix("").parts)

            # Extract functions
            for match in function_pattern.finditer(content):
                name = match.group(1)
                params = match.group(2)
                return_type = match.group(3).strip() if match.group(3) else None

                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                signature = f"{name}({params})"
                if return_type:
                    signature += f": {return_type}"

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="function",
                    file=ts_file,
                    line=line,
                    signature=signature,
                )

            # Extract classes
            for match in class_pattern.finditer(content):
                name = match.group(1)
                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="class",
                    file=ts_file,
                    line=line,
                )

            # Extract interfaces and types
            for match in interface_pattern.finditer(content):
                name = match.group(1)
                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="class",  # Treat as class for simplicity
                    file=ts_file,
                    line=line,
                )

            for match in type_pattern.finditer(content):
                name = match.group(1)
                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="class",
                    file=ts_file,
                    line=line,
                )

            # Extract constants
            for match in const_pattern.finditer(content):
                name = match.group(1)
                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="constant",
                    file=ts_file,
                    line=line,
                )

        except Exception as e:
            logger.debug(f"Error indexing {ts_file}: {e}")

    # Also index .tsx files
    for tsx_file in root.glob("**/*.tsx"):
        if any(skip in tsx_file.parts for skip in skip_dirs):
            continue

        try:
            content = tsx_file.read_text(encoding="utf-8", errors="ignore")
            file_count += 1

            rel_path = tsx_file.relative_to(root)
            module_name = "/".join(rel_path.with_suffix("").parts)

            # Same patterns for TSX
            for match in function_pattern.finditer(content):
                name = match.group(1)
                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="function",
                    file=tsx_file,
                    line=line,
                )

        except Exception as e:
            logger.debug(f"Error indexing {tsx_file}: {e}")

    logger.info(f"Indexed {len(symbols)} TypeScript symbols from {file_count} files")
    return symbols, file_count


async def _index_generic(root: Path, language: str) -> tuple[dict[str, SymbolInfo], int]:
    """Generic regex-based indexing for other languages.

    Basic extraction of:
    - Function definitions
    - Class definitions
    """
    symbols: dict[str, SymbolInfo] = {}
    file_count = 0

    # Language-specific patterns
    patterns = {
        "go": {
            "ext": "*.go",
            "func": re.compile(r"func\s+(?:\(.*?\)\s+)?(\w+)\s*\(", re.MULTILINE),
            "type": re.compile(r"type\s+(\w+)\s+(?:struct|interface)", re.MULTILINE),
        },
        "rust": {
            "ext": "*.rs",
            "func": re.compile(r"(?:pub\s+)?fn\s+(\w+)\s*[<(]", re.MULTILINE),
            "type": re.compile(r"(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)", re.MULTILINE),
        },
    }

    lang_patterns = patterns.get(language)
    if not lang_patterns:
        logger.warning(f"No patterns for language: {language}")
        return symbols, file_count

    skip_dirs = {".git", "target", "vendor", "node_modules"}

    for file in root.glob(f"**/{lang_patterns['ext']}"):
        if any(skip in file.parts for skip in skip_dirs):
            continue

        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
            file_count += 1

            rel_path = file.relative_to(root)
            module_name = "/".join(rel_path.with_suffix("").parts)

            # Extract functions
            for match in lang_patterns["func"].finditer(content):
                name = match.group(1)
                if name.startswith("_") or name == "main":
                    continue

                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="function",
                    file=file,
                    line=line,
                )

            # Extract types
            for match in lang_patterns["type"].finditer(content):
                name = match.group(1)
                if name.startswith("_"):
                    continue

                full_name = f"{module_name}/{name}" if module_name else name
                line = content[: match.start()].count("\n") + 1

                symbols[full_name] = SymbolInfo(
                    name=full_name,
                    kind="class",
                    file=file,
                    line=line,
                )

        except Exception as e:
            logger.debug(f"Error indexing {file}: {e}")

    logger.info(f"Indexed {len(symbols)} {language} symbols from {file_count} files")
    return symbols, file_count
