"""Signature extractor for L1 lightweight indexing.

Extracts only public APIs, exports, and type definitions.
Used for cross-project awareness without full indexing overhead.

L1 indexing is ~10x lighter than L2 full indexing because it:
- Only indexes function/class signatures (not bodies)
- Only indexes public APIs (not private/internal)
- Skips documentation and prose files
- Uses smaller chunks
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from sunwell.knowledge.workspace.indexer import CodeChunk

__all__ = [
    "SignatureExtractor",
    "Signature",
    "extract_signatures",
]


@dataclass(frozen=True, slots=True)
class Signature:
    """An extracted public API signature.

    Lighter than CodeChunk - just the signature text and metadata.
    """

    name: str
    """Name of the function/class/constant."""

    kind: str
    """Type: function, class, constant, type, export."""

    signature: str
    """The signature text (without body)."""

    file_path: Path
    """Source file path."""

    line: int
    """Line number."""

    docstring: str | None = None
    """First line of docstring if present."""

    def to_chunk(self) -> CodeChunk:
        """Convert to CodeChunk for embedding."""
        content = self.signature
        if self.docstring:
            content = f"{content}\n    '''{self.docstring}'''"

        return CodeChunk(
            file_path=self.file_path,
            start_line=self.line,
            end_line=self.line + self.signature.count("\n"),
            content=content,
            chunk_type=self.kind,
            name=self.name,
        )


class SignatureExtractor:
    """Extracts public signatures from source files.

    Supports:
    - Python: functions, classes, constants, type aliases
    - TypeScript/JavaScript: functions, classes, exports, types
    - Go: functions, types, constants
    - Rust: pub fn, pub struct, pub enum, pub const
    """

    def extract(self, file_path: Path) -> list[Signature]:
        """Extract signatures from a file.

        Args:
            file_path: Path to source file.

        Returns:
            List of extracted signatures.
        """
        suffix = file_path.suffix.lower()

        if suffix == ".py":
            return self._extract_python(file_path)
        elif suffix in (".ts", ".tsx", ".js", ".jsx"):
            return self._extract_typescript(file_path)
        elif suffix == ".go":
            return self._extract_go(file_path)
        elif suffix == ".rs":
            return self._extract_rust(file_path)
        else:
            return []

    def _extract_python(self, file_path: Path) -> list[Signature]:
        """Extract signatures from Python file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError, OSError):
            return []

        signatures: list[Signature] = []
        lines = content.split("\n")

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Only public functions (no underscore prefix)
                if not node.name.startswith("_"):
                    sig = self._python_function_signature(node, lines, file_path)
                    if sig:
                        signatures.append(sig)

            elif isinstance(node, ast.ClassDef):
                # Only public classes
                if not node.name.startswith("_"):
                    sig = self._python_class_signature(node, lines, file_path)
                    if sig:
                        signatures.append(sig)

            elif isinstance(node, ast.Assign):
                # Module-level constants (UPPER_CASE)
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        sig = self._python_constant_signature(target, node, lines, file_path)
                        if sig:
                            signatures.append(sig)

            elif isinstance(node, ast.AnnAssign):
                # Type aliases (TypeAlias or annotated assignments)
                if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
                    sig = self._python_type_alias_signature(node, lines, file_path)
                    if sig:
                        signatures.append(sig)

        return signatures

    def _python_function_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], file_path: Path
    ) -> Signature | None:
        """Extract Python function signature."""
        # Build signature from AST
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        # Add *args and **kwargs
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        # Return type
        returns = ""
        if node.returns:
            returns = f" -> {ast.unparse(node.returns)}"

        async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        signature = f"{async_prefix}def {node.name}({', '.join(args)}){returns}:"

        # Get docstring (first line only)
        docstring = ast.get_docstring(node)
        if docstring:
            docstring = docstring.split("\n")[0].strip()

        return Signature(
            name=node.name,
            kind="function",
            signature=signature,
            file_path=file_path,
            line=node.lineno,
            docstring=docstring,
        )

    def _python_class_signature(
        self, node: ast.ClassDef, lines: list[str], file_path: Path
    ) -> Signature | None:
        """Extract Python class signature."""
        # Build class definition line
        bases = [ast.unparse(b) for b in node.bases]
        keywords = [f"{kw.arg}={ast.unparse(kw.value)}" for kw in node.keywords]
        all_bases = bases + keywords

        if all_bases:
            signature = f"class {node.name}({', '.join(all_bases)}):"
        else:
            signature = f"class {node.name}:"

        # Add public method signatures
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                if not item.name.startswith("_") or item.name in ("__init__", "__call__"):
                    method_sig = self._python_function_signature(item, lines, file_path)
                    if method_sig:
                        methods.append(f"    {method_sig.signature}")

        if methods:
            signature = signature + "\n" + "\n".join(methods[:5])  # Limit to 5 methods

        # Get docstring
        docstring = ast.get_docstring(node)
        if docstring:
            docstring = docstring.split("\n")[0].strip()

        return Signature(
            name=node.name,
            kind="class",
            signature=signature,
            file_path=file_path,
            line=node.lineno,
            docstring=docstring,
        )

    def _python_constant_signature(
        self, target: ast.Name, node: ast.Assign, lines: list[str], file_path: Path
    ) -> Signature | None:
        """Extract Python constant signature."""
        try:
            value_repr = ast.unparse(node.value)
            # Truncate long values
            if len(value_repr) > 50:
                value_repr = value_repr[:47] + "..."
            signature = f"{target.id} = {value_repr}"
        except Exception:
            signature = f"{target.id} = ..."

        return Signature(
            name=target.id,
            kind="constant",
            signature=signature,
            file_path=file_path,
            line=node.lineno,
        )

    def _python_type_alias_signature(
        self, node: ast.AnnAssign, lines: list[str], file_path: Path
    ) -> Signature | None:
        """Extract Python type alias signature."""
        if not isinstance(node.target, ast.Name):
            return None

        try:
            ann_repr = ast.unparse(node.annotation)
            signature = f"{node.target.id}: {ann_repr}"
            if node.value:
                value_repr = ast.unparse(node.value)
                if len(value_repr) > 50:
                    value_repr = value_repr[:47] + "..."
                signature += f" = {value_repr}"
        except Exception:
            return None

        return Signature(
            name=node.target.id,
            kind="type",
            signature=signature,
            file_path=file_path,
            line=node.lineno,
        )

    def _extract_typescript(self, file_path: Path) -> list[Signature]:
        """Extract signatures from TypeScript/JavaScript file.

        Uses regex-based extraction (no full parser needed for signatures).
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []

        signatures: list[Signature] = []
        lines = content.split("\n")

        # Patterns for exports
        patterns = [
            # export function name(...)
            (r"^export\s+(async\s+)?function\s+(\w+)\s*\([^)]*\)", "function"),
            # export class Name
            (r"^export\s+class\s+(\w+)", "class"),
            # export const NAME =
            (r"^export\s+const\s+([A-Z_][A-Z0-9_]*)\s*=", "constant"),
            # export type Name =
            (r"^export\s+type\s+(\w+)\s*=", "type"),
            # export interface Name
            (r"^export\s+interface\s+(\w+)", "type"),
            # export default function
            (r"^export\s+default\s+(async\s+)?function\s+(\w+)?", "function"),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()
            for pattern, kind in patterns:
                match = re.match(pattern, stripped)
                if match:
                    # Extract name from appropriate group
                    groups = match.groups()
                    name = next((g for g in groups if g and not g.startswith("async")), "default")

                    # Find the full signature (up to opening brace or newline)
                    sig_line = stripped
                    if "{" in sig_line:
                        sig_line = sig_line[:sig_line.index("{")] + " { ... }"

                    signatures.append(Signature(
                        name=name or "default",
                        kind=kind,
                        signature=sig_line,
                        file_path=file_path,
                        line=i + 1,
                    ))
                    break

        return signatures

    def _extract_go(self, file_path: Path) -> list[Signature]:
        """Extract signatures from Go file."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []

        signatures: list[Signature] = []
        lines = content.split("\n")

        # Patterns for public Go symbols (capitalized names are exported)
        patterns = [
            # func Name(...)
            (r"^func\s+([A-Z]\w*)\s*\([^)]*\)", "function"),
            # func (receiver) Name(...)
            (r"^func\s+\([^)]+\)\s*([A-Z]\w*)\s*\([^)]*\)", "function"),
            # type Name struct/interface
            (r"^type\s+([A-Z]\w*)\s+(struct|interface)", "type"),
            # const Name =
            (r"^const\s+([A-Z]\w*)\s*=", "constant"),
            # var Name =
            (r"^var\s+([A-Z]\w*)\s+", "constant"),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()
            for pattern, kind in patterns:
                match = re.match(pattern, stripped)
                if match:
                    name = match.group(1)

                    # Find the full signature
                    sig_line = stripped
                    if "{" in sig_line:
                        sig_line = sig_line[:sig_line.index("{")] + " { ... }"

                    signatures.append(Signature(
                        name=name,
                        kind=kind,
                        signature=sig_line,
                        file_path=file_path,
                        line=i + 1,
                    ))
                    break

        return signatures

    def _extract_rust(self, file_path: Path) -> list[Signature]:
        """Extract signatures from Rust file."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []

        signatures: list[Signature] = []
        lines = content.split("\n")

        # Patterns for pub items
        patterns = [
            # pub fn name(...)
            (r"^pub\s+(async\s+)?fn\s+(\w+)", "function"),
            # pub struct Name
            (r"^pub\s+struct\s+(\w+)", "type"),
            # pub enum Name
            (r"^pub\s+enum\s+(\w+)", "type"),
            # pub type Name
            (r"^pub\s+type\s+(\w+)", "type"),
            # pub const NAME
            (r"^pub\s+const\s+([A-Z_][A-Z0-9_]*)", "constant"),
            # pub trait Name
            (r"^pub\s+trait\s+(\w+)", "type"),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()
            for pattern, kind in patterns:
                match = re.match(pattern, stripped)
                if match:
                    # Get the name (skip async group if present)
                    groups = [g for g in match.groups() if g and not g.startswith("async")]
                    name = groups[0] if groups else "unknown"

                    # Find the full signature
                    sig_line = stripped
                    if "{" in sig_line:
                        sig_line = sig_line[:sig_line.index("{")] + " { ... }"

                    signatures.append(Signature(
                        name=name,
                        kind=kind,
                        signature=sig_line,
                        file_path=file_path,
                        line=i + 1,
                    ))
                    break

        return signatures


def extract_signatures(file_path: Path) -> list[Signature]:
    """Extract public signatures from a file.

    Convenience function using default SignatureExtractor.

    Args:
        file_path: Path to source file.

    Returns:
        List of extracted signatures.
    """
    return SignatureExtractor().extract(file_path)
