#!/usr/bin/env python3
"""Magnetic Search Experiment - Multi-Language Support.

Tests whether intent-driven extraction ("query shapes the pattern") finds
relevant code more efficiently than progressive file reading or grep.

The metaphor: instead of sifting through sand grain by grain, we stick a
magnet into the barrel and attract only the iron filings.

Supports:
- Python (via ast module)
- JavaScript/TypeScript (via tree-sitter, optional)
- Markdown/plain text (via heading structure)

Usage:
    python scripts/magnetic_search_experiment.py
"""

from __future__ import annotations

import ast
import re
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

# Try to import tree-sitter for JS/TS support
try:
    import tree_sitter_javascript as ts_js
    import tree_sitter_typescript as ts_ts
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


# =============================================================================
# Intent Classification
# =============================================================================


class Intent(Enum):
    """Query intent categories that determine extraction strategy."""

    DEFINITION = auto()  # "where is X defined", "find X class/function"
    USAGE = auto()  # "where is X used/called", "what calls X"
    STRUCTURE = auto()  # "what methods does X have", "what's in X"
    CONTRACT = auto()  # "what does X expect/return", "signature of X"
    FLOW = auto()  # "how does X connect to Y" (stretch goal)
    UNKNOWN = auto()  # Fallback


@dataclass(frozen=True, slots=True)
class ClassifiedQuery:
    """Result of intent classification."""

    intent: Intent
    entities: tuple[str, ...]
    confidence: float  # 0.0 - 1.0
    raw_query: str


class IntentClassifier:
    """Classify queries into intent categories using rule-based patterns.

    The classifier extracts:
    1. The intent type (what kind of search)
    2. Entity names (what to search for)
    """

    # Patterns for each intent type (order matters - first match wins)
    INTENT_PATTERNS: list[tuple[Intent, re.Pattern[str], float]] = [
        # DEFINITION patterns
        (Intent.DEFINITION, re.compile(r"where\s+is\s+(\w+)\s+defined", re.I), 0.95),
        (Intent.DEFINITION, re.compile(r"find\s+(?:the\s+)?(\w+)\s+(?:class|function|def)", re.I), 0.9),
        (Intent.DEFINITION, re.compile(r"(?:class|function|def)\s+(\w+)", re.I), 0.85),
        (Intent.DEFINITION, re.compile(r"definition\s+of\s+(\w+)", re.I), 0.9),
        (Intent.DEFINITION, re.compile(r"locate\s+(\w+)", re.I), 0.7),
        # USAGE patterns
        (Intent.USAGE, re.compile(r"where\s+is\s+(\w+)\s+(?:used|called)", re.I), 0.95),
        (Intent.USAGE, re.compile(r"what\s+(?:calls|uses)\s+(\w+)", re.I), 0.9),
        (Intent.USAGE, re.compile(r"(?:usages?|calls?)\s+(?:of|to)\s+(\w+)", re.I), 0.85),
        (Intent.USAGE, re.compile(r"find\s+(?:all\s+)?(?:usages?|calls?)\s+(?:of|to)\s+(\w+)", re.I), 0.9),
        # STRUCTURE patterns
        (Intent.STRUCTURE, re.compile(r"what\s+methods?\s+does\s+(\w+)\s+have", re.I), 0.95),
        (Intent.STRUCTURE, re.compile(r"what(?:'s| is)\s+in\s+(\w+)", re.I), 0.85),
        (Intent.STRUCTURE, re.compile(r"(?:structure|outline|skeleton)\s+of\s+(\w+)", re.I), 0.9),
        (Intent.STRUCTURE, re.compile(r"list\s+(?:the\s+)?methods?\s+(?:of|in)\s+(\w+)", re.I), 0.9),
        (Intent.STRUCTURE, re.compile(r"(\w+)\s+(?:class|module)\s+structure", re.I), 0.85),
        # CONTRACT patterns
        (Intent.CONTRACT, re.compile(r"what\s+does\s+(\w+)\s+(?:expect|return|take)", re.I), 0.95),
        (Intent.CONTRACT, re.compile(r"signature\s+of\s+(\w+)", re.I), 0.95),
        (Intent.CONTRACT, re.compile(r"(?:parameters?|args?|arguments?)\s+(?:of|for)\s+(\w+)", re.I), 0.9),
        (Intent.CONTRACT, re.compile(r"(?:return\s+type|returns?)\s+(?:of|from)\s+(\w+)", re.I), 0.9),
        (Intent.CONTRACT, re.compile(r"how\s+(?:to\s+)?(?:call|use)\s+(\w+)", re.I), 0.8),
        # FLOW patterns (stretch goal)
        (Intent.FLOW, re.compile(r"how\s+does\s+(\w+)\s+(?:connect|flow|reach)\s+(?:to\s+)?(\w+)", re.I), 0.9),
        (Intent.FLOW, re.compile(r"(?:path|flow)\s+from\s+(\w+)\s+to\s+(\w+)", re.I), 0.9),
    ]

    # Fallback entity extraction for UNKNOWN intent
    ENTITY_PATTERN = re.compile(r"\b([A-Z][a-zA-Z0-9_]+)\b")  # CamelCase names

    def classify(self, query: str) -> ClassifiedQuery:
        """Classify a query into intent + entities.

        Args:
            query: Natural language search query.

        Returns:
            ClassifiedQuery with intent type and extracted entities.
        """
        query = query.strip()

        # Try each pattern in order
        for intent, pattern, confidence in self.INTENT_PATTERNS:
            match = pattern.search(query)
            if match:
                entities = tuple(g for g in match.groups() if g)
                return ClassifiedQuery(
                    intent=intent,
                    entities=entities,
                    confidence=confidence,
                    raw_query=query,
                )

        # Fallback: extract CamelCase names and return UNKNOWN
        entities = tuple(set(self.ENTITY_PATTERN.findall(query)))
        return ClassifiedQuery(
            intent=Intent.UNKNOWN,
            entities=entities,
            confidence=0.3,
            raw_query=query,
        )


# =============================================================================
# Pattern Generation
# =============================================================================


@dataclass(frozen=True, slots=True)
class ExtractionPattern:
    """Pattern that defines what to extract from code."""

    intent: Intent
    entities: tuple[str, ...]

    # AST node types to look for
    node_types: tuple[type[ast.AST], ...] = ()

    # Name matching strategy
    name_matcher: str | None = None  # Regex pattern for name matching

    # What to extract
    extract_body: bool = True  # Include function/class body
    extract_docstring: bool = True  # Include docstring
    extract_signature: bool = True  # Include signature
    context_lines: int = 0  # Lines of context around matches


class PatternGenerator:
    """Generate extraction patterns from classified queries.

    Converts (intent, entities) into concrete AST extraction patterns.
    """

    def generate(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Generate an extraction pattern from a classified query.

        Args:
            classified: The classified query with intent and entities.

        Returns:
            ExtractionPattern defining what to extract.
        """
        match classified.intent:
            case Intent.DEFINITION:
                return self._definition_pattern(classified)
            case Intent.USAGE:
                return self._usage_pattern(classified)
            case Intent.STRUCTURE:
                return self._structure_pattern(classified)
            case Intent.CONTRACT:
                return self._contract_pattern(classified)
            case Intent.FLOW:
                return self._flow_pattern(classified)
            case Intent.UNKNOWN:
                return self._fallback_pattern(classified)

    def _definition_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Pattern for finding definitions."""
        return ExtractionPattern(
            intent=Intent.DEFINITION,
            entities=classified.entities,
            node_types=(ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=True,
            extract_docstring=True,
            extract_signature=True,
        )

    def _usage_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Pattern for finding usages/call sites."""
        return ExtractionPattern(
            intent=Intent.USAGE,
            entities=classified.entities,
            node_types=(ast.Call, ast.Attribute, ast.Name),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=False,  # Just the call site
            extract_docstring=False,
            extract_signature=False,
            context_lines=3,  # Show context around usages
        )

    def _structure_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Pattern for extracting class/module structure (skeleton)."""
        return ExtractionPattern(
            intent=Intent.STRUCTURE,
            entities=classified.entities,
            node_types=(ast.ClassDef,),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=False,  # Skeleton only - no method bodies
            extract_docstring=True,
            extract_signature=True,
        )

    def _contract_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Pattern for extracting function contracts (signature + docstring)."""
        return ExtractionPattern(
            intent=Intent.CONTRACT,
            entities=classified.entities,
            node_types=(ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=False,  # No body
            extract_docstring=True,
            extract_signature=True,
        )

    def _flow_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Pattern for flow tracing (stretch goal)."""
        # For now, treat as usage search for first entity
        return ExtractionPattern(
            intent=Intent.FLOW,
            entities=classified.entities,
            node_types=(ast.Call, ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=True,
            extract_docstring=True,
            extract_signature=True,
        )

    def _fallback_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Fallback pattern for unknown intent."""
        return ExtractionPattern(
            intent=Intent.UNKNOWN,
            entities=classified.entities,
            node_types=(ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=True,
            extract_docstring=True,
            extract_signature=True,
        )

    def _entity_regex(self, entities: tuple[str, ...]) -> str:
        """Build regex pattern that matches any entity (case-insensitive)."""
        if not entities:
            return r".*"
        escaped = [re.escape(e) for e in entities]
        return r"(?i)(?:" + "|".join(escaped) + ")"


# =============================================================================
# Structural Extraction
# =============================================================================


@dataclass(frozen=True, slots=True)
class CodeFragment:
    """A fragment of code extracted by magnetic search."""

    file_path: Path
    start_line: int
    end_line: int
    content: str
    fragment_type: str  # "class", "function", "call_site", etc.
    name: str | None = None
    docstring: str | None = None
    signature: str | None = None


@dataclass(slots=True)
class ExtractionResult:
    """Result of magnetic extraction."""

    fragments: list[CodeFragment] = field(default_factory=list)
    files_parsed: int = 0
    total_file_lines: int = 0
    parse_time_ms: float = 0.0


# =============================================================================
# Language Extractor Protocol & Registry
# =============================================================================


@runtime_checkable
class LanguageExtractor(Protocol):
    """Protocol for language-specific extractors.

    Each extractor handles a specific file type and knows how to:
    - Parse the file's structure
    - Extract definitions, usages, structure, and contracts
    """

    def can_handle(self, file_path: Path) -> bool:
        """Return True if this extractor handles this file type."""
        ...

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching code fragments from a file."""
        ...


class ExtractorRegistry:
    """Registry that maps file types to extractors.

    Auto-selects the appropriate extractor based on file extension.
    """

    def __init__(self) -> None:
        self._extractors: list[LanguageExtractor] = []

    def register(self, extractor: LanguageExtractor) -> None:
        """Register an extractor."""
        self._extractors.append(extractor)

    def get_extractor(self, file_path: Path) -> LanguageExtractor | None:
        """Get the appropriate extractor for a file."""
        for extractor in self._extractors:
            if extractor.can_handle(file_path):
                return extractor
        return None

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract from a file using the appropriate extractor."""
        extractor = self.get_extractor(file_path)
        if extractor is None:
            return ExtractionResult()  # Unknown file type
        return extractor.extract(file_path, pattern)

    def extract_multi(
        self,
        file_paths: list[Path],
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract from multiple files."""
        combined = ExtractionResult()
        for path in file_paths:
            result = self.extract(path, pattern)
            combined.fragments.extend(result.fragments)
            combined.files_parsed += result.files_parsed
            combined.total_file_lines += result.total_file_lines
            combined.parse_time_ms += result.parse_time_ms
        return combined


# =============================================================================
# Python Extractor (using ast module)
# =============================================================================


class PythonExtractor:
    """Extract code fragments from Python files using ast module.

    Instead of reading full files, parses to AST and extracts only
    the nodes that match the pattern - like a magnet attracting iron.
    """

    EXTENSIONS = {".py", ".pyi"}

    def __init__(self) -> None:
        self._ast_cache: dict[Path, ast.Module | None] = {}

    def can_handle(self, file_path: Path) -> bool:
        """Return True for Python files."""
        return file_path.suffix.lower() in self.EXTENSIONS

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching code fragments from a Python file.

        Args:
            file_path: Path to Python file.
            pattern: Extraction pattern defining what to find.

        Returns:
            ExtractionResult with matching fragments.
        """
        result = ExtractionResult()
        start_time = time.perf_counter()

        # Parse file (cached)
        tree = self._parse_file(file_path)
        if tree is None:
            return result

        result.files_parsed = 1

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return result

        lines = content.split("\n")
        result.total_file_lines = len(lines)

        # Extract based on intent
        match pattern.intent:
            case Intent.DEFINITION | Intent.UNKNOWN:
                result.fragments = self._extract_definitions(tree, lines, file_path, pattern)
            case Intent.USAGE:
                result.fragments = self._extract_usages(tree, lines, file_path, pattern)
            case Intent.STRUCTURE:
                result.fragments = self._extract_structure(tree, lines, file_path, pattern)
            case Intent.CONTRACT:
                result.fragments = self._extract_contracts(tree, lines, file_path, pattern)
            case Intent.FLOW:
                result.fragments = self._extract_flow(tree, lines, file_path, pattern)

        result.parse_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _parse_file(self, file_path: Path) -> ast.Module | None:
        """Parse a Python file to AST (cached)."""
        if file_path in self._ast_cache:
            return self._ast_cache[file_path]

        try:
            content = file_path.read_text()
            tree = ast.parse(content, filename=str(file_path))
            self._ast_cache[file_path] = tree
            return tree
        except (SyntaxError, OSError, UnicodeDecodeError):
            self._ast_cache[file_path] = None
            return None

    def _extract_definitions(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract class and function definitions."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check name match
                if name_re and not name_re.search(node.name):
                    continue

                fragment = self._node_to_fragment(node, lines, file_path, pattern)
                if fragment:
                    fragments.append(fragment)

        return fragments

    def _extract_usages(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract call sites and references."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None
        seen_lines: set[int] = set()  # Avoid duplicates

        for node in ast.walk(tree):
            # Check function calls
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if name_re and call_name and name_re.search(call_name):
                    if node.lineno not in seen_lines:
                        seen_lines.add(node.lineno)
                        fragment = self._call_to_fragment(
                            node, lines, file_path, call_name, pattern.context_lines
                        )
                        if fragment:
                            fragments.append(fragment)

            # Check attribute access (X.method)
            elif isinstance(node, ast.Attribute):
                if name_re and name_re.search(node.attr):
                    if node.lineno not in seen_lines:
                        seen_lines.add(node.lineno)
                        fragment = self._attr_to_fragment(
                            node, lines, file_path, pattern.context_lines
                        )
                        if fragment:
                            fragments.append(fragment)

        return fragments

    def _extract_structure(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract class skeleton (signatures only, no bodies)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if name_re and not name_re.search(node.name):
                    continue

                skeleton = self._class_skeleton(node, lines)
                skeleton_lines = len(skeleton.split("\n"))
                fragments.append(
                    CodeFragment(
                        file_path=file_path,
                        start_line=node.lineno,
                        # Use skeleton line count, not original class size
                        end_line=node.lineno + skeleton_lines - 1,
                        content=skeleton,
                        fragment_type="class_skeleton",
                        name=node.name,
                        docstring=ast.get_docstring(node),
                        signature=f"class {node.name}",
                    )
                )

        return fragments

    def _extract_contracts(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract function contracts (signature + docstring only)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if name_re and not name_re.search(node.name):
                    continue

                signature = self._extract_signature(node, lines)
                docstring = ast.get_docstring(node)

                # Build contract content
                parts = [signature]
                if docstring:
                    parts.append(f'    """{docstring}"""')

                fragments.append(
                    CodeFragment(
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=node.lineno + (5 if docstring else 1),
                        content="\n".join(parts),
                        fragment_type="contract",
                        name=node.name,
                        docstring=docstring,
                        signature=signature,
                    )
                )

        return fragments

    def _extract_flow(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract flow-related code (combination of definitions and usages)."""
        # For now, combine definitions and usages
        defs = self._extract_definitions(tree, lines, file_path, pattern)
        usages = self._extract_usages(tree, lines, file_path, pattern)
        return defs + usages

    def _node_to_fragment(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> CodeFragment | None:
        """Convert an AST node to a CodeFragment."""
        start_line = node.lineno

        # Include decorators
        if hasattr(node, "decorator_list") and node.decorator_list:
            for dec in node.decorator_list:
                start_line = min(start_line, dec.lineno)

        end_line = node.end_lineno or node.lineno

        # Extract content based on pattern
        if pattern.extract_body:
            content = "\n".join(lines[start_line - 1 : end_line])
        else:
            # Just signature + docstring
            content = self._extract_signature(node, lines)
            docstring = ast.get_docstring(node)
            if pattern.extract_docstring and docstring:
                indent = "    " if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
                content += f'\n{indent}"""{docstring}"""'

        fragment_type = "class" if isinstance(node, ast.ClassDef) else "function"

        return CodeFragment(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            fragment_type=fragment_type,
            name=node.name,
            docstring=ast.get_docstring(node),
            signature=self._extract_signature(node, lines),
        )

    def _call_to_fragment(
        self,
        node: ast.Call,
        lines: list[str],
        file_path: Path,
        call_name: str,
        context_lines: int,
    ) -> CodeFragment:
        """Convert a Call node to a fragment with context."""
        start = max(0, node.lineno - 1 - context_lines)
        end = min(len(lines), (node.end_lineno or node.lineno) + context_lines)
        content = "\n".join(lines[start:end])

        return CodeFragment(
            file_path=file_path,
            start_line=start + 1,
            end_line=end,
            content=content,
            fragment_type="call_site",
            name=call_name,
        )

    def _attr_to_fragment(
        self,
        node: ast.Attribute,
        lines: list[str],
        file_path: Path,
        context_lines: int,
    ) -> CodeFragment:
        """Convert an Attribute node to a fragment with context."""
        start = max(0, node.lineno - 1 - context_lines)
        end = min(len(lines), (node.end_lineno or node.lineno) + context_lines)
        content = "\n".join(lines[start:end])

        return CodeFragment(
            file_path=file_path,
            start_line=start + 1,
            end_line=end,
            content=content,
            fragment_type="attribute_ref",
            name=node.attr,
        )

    def _class_skeleton(self, node: ast.ClassDef, lines: list[str]) -> str:
        """Extract class skeleton - signatures only, no bodies."""
        parts: list[str] = []

        # Class definition line
        parts.append(lines[node.lineno - 1])

        # Docstring
        docstring = ast.get_docstring(node)
        if docstring:
            parts.append(f'    """{docstring}"""')

        # Method signatures
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._extract_signature(item, lines)
                parts.append(f"    {sig}")
                parts.append("        ...")

        return "\n".join(parts)

    def _extract_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        lines: list[str],
    ) -> str:
        """Extract signature from source lines."""
        if isinstance(node, ast.ClassDef):
            return lines[node.lineno - 1].strip()

        # For functions, handle multi-line signatures
        sig_lines: list[str] = []
        for i in range(node.lineno - 1, min(node.lineno + 10, len(lines))):
            line = lines[i]
            sig_lines.append(line)
            if line.rstrip().endswith(":"):
                break

        return "\n".join(sig_lines).strip()

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the name being called."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None


# =============================================================================
# Tree-Sitter Extractor (JavaScript/TypeScript)
# =============================================================================


class TreeSitterExtractor:
    """Extract code fragments from JS/TS files using tree-sitter.

    Requires tree-sitter and language grammars to be installed.
    Falls back gracefully if not available.
    """

    EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

    def __init__(self) -> None:
        self._parser_cache: dict[str, "Parser"] = {}
        self._available = TREE_SITTER_AVAILABLE

    def can_handle(self, file_path: Path) -> bool:
        """Return True for JS/TS files if tree-sitter is available."""
        if not self._available:
            return False
        return file_path.suffix.lower() in self.EXTENSIONS

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching code fragments from a JS/TS file."""
        if not self._available:
            return ExtractionResult()

        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return result

        lines = content.split("\n")
        result.total_file_lines = len(lines)
        result.files_parsed = 1

        # Get parser for this file type
        parser = self._get_parser(file_path.suffix.lower())
        if parser is None:
            return result

        # Parse the file
        tree = parser.parse(content.encode())

        # Extract based on intent
        match pattern.intent:
            case Intent.DEFINITION | Intent.UNKNOWN:
                result.fragments = self._extract_definitions(
                    tree.root_node, content, lines, file_path, pattern
                )
            case Intent.USAGE:
                result.fragments = self._extract_usages(
                    tree.root_node, content, lines, file_path, pattern
                )
            case Intent.STRUCTURE:
                result.fragments = self._extract_structure(
                    tree.root_node, content, lines, file_path, pattern
                )
            case Intent.CONTRACT:
                result.fragments = self._extract_contracts(
                    tree.root_node, content, lines, file_path, pattern
                )
            case Intent.FLOW:
                # Combine definitions and usages for flow
                result.fragments = self._extract_definitions(
                    tree.root_node, content, lines, file_path, pattern
                ) + self._extract_usages(
                    tree.root_node, content, lines, file_path, pattern
                )

        result.parse_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _get_parser(self, suffix: str) -> "Parser | None":
        """Get or create a parser for the given file type."""
        if suffix in self._parser_cache:
            return self._parser_cache[suffix]

        if not TREE_SITTER_AVAILABLE:
            return None

        try:
            parser = Parser()
            if suffix in {".ts", ".tsx"}:
                if suffix == ".tsx":
                    lang = Language(ts_ts.language_tsx())
                else:
                    lang = Language(ts_ts.language_typescript())
            else:
                lang = Language(ts_js.language())
            parser.language = lang
            self._parser_cache[suffix] = parser
            return parser
        except Exception:
            return None

    def _extract_definitions(
        self,
        root_node: "tree_sitter.Node",
        content: str,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract function and class definitions."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        # Node types for definitions
        def_types = {
            "function_declaration",
            "class_declaration",
            "method_definition",
            "arrow_function",
            "function_expression",
        }

        def walk(node: "tree_sitter.Node") -> None:
            if node.type in def_types:
                name = self._get_node_name(node)
                if name and (name_re is None or name_re.search(name)):
                    fragment = self._node_to_fragment(node, content, lines, file_path, name)
                    if fragment:
                        fragments.append(fragment)

            for child in node.children:
                walk(child)

        walk(root_node)
        return fragments

    def _extract_usages(
        self,
        root_node: "tree_sitter.Node",
        content: str,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract call sites."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None
        seen_lines: set[int] = set()

        def walk(node: "tree_sitter.Node") -> None:
            if node.type == "call_expression":
                # Get function name from call
                func_node = node.child_by_field_name("function")
                if func_node:
                    name = self._get_identifier_text(func_node, content)
                    if name and (name_re is None or name_re.search(name)):
                        line = node.start_point[0] + 1
                        if line not in seen_lines:
                            seen_lines.add(line)
                            fragment = self._call_to_fragment(
                                node, content, lines, file_path, name, pattern.context_lines
                            )
                            if fragment:
                                fragments.append(fragment)

            for child in node.children:
                walk(child)

        walk(root_node)
        return fragments

    def _extract_structure(
        self,
        root_node: "tree_sitter.Node",
        content: str,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract class skeleton (method signatures only)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        def walk(node: "tree_sitter.Node") -> None:
            if node.type == "class_declaration":
                name = self._get_node_name(node)
                if name and (name_re is None or name_re.search(name)):
                    skeleton = self._class_skeleton(node, content, lines)
                    skeleton_lines = len(skeleton.split("\n"))
                    fragments.append(
                        CodeFragment(
                            file_path=file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.start_point[0] + skeleton_lines,
                            content=skeleton,
                            fragment_type="class_skeleton",
                            name=name,
                            signature=f"class {name}",
                        )
                    )

            for child in node.children:
                walk(child)

        walk(root_node)
        return fragments

    def _extract_contracts(
        self,
        root_node: "tree_sitter.Node",
        content: str,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract function signatures (with JSDoc if present)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        func_types = {"function_declaration", "method_definition", "arrow_function"}

        def walk(node: "tree_sitter.Node") -> None:
            if node.type in func_types:
                name = self._get_node_name(node)
                if name and (name_re is None or name_re.search(name)):
                    # Get signature line
                    start_line = node.start_point[0]
                    sig = lines[start_line] if start_line < len(lines) else ""

                    # Look for JSDoc comment before
                    jsdoc = self._get_jsdoc(node, content, lines)

                    contract = sig
                    if jsdoc:
                        contract = jsdoc + "\n" + sig

                    fragments.append(
                        CodeFragment(
                            file_path=file_path,
                            start_line=start_line + 1,
                            end_line=start_line + len(contract.split("\n")),
                            content=contract,
                            fragment_type="contract",
                            name=name,
                            signature=sig.strip(),
                            docstring=jsdoc,
                        )
                    )

            for child in node.children:
                walk(child)

        walk(root_node)
        return fragments

    def _get_node_name(self, node: "tree_sitter.Node") -> str | None:
        """Get the name of a definition node."""
        # Try name field first
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode() if name_node.text else None

        # For arrow functions, look at parent assignment
        if node.type == "arrow_function":
            parent = node.parent
            if parent and parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return name_node.text.decode() if name_node.text else None

        return None

    def _get_identifier_text(self, node: "tree_sitter.Node", content: str) -> str | None:
        """Get text from an identifier or member expression."""
        if node.type == "identifier":
            return node.text.decode() if node.text else None
        if node.type == "member_expression":
            prop = node.child_by_field_name("property")
            if prop:
                return prop.text.decode() if prop.text else None
        return None

    def _node_to_fragment(
        self,
        node: "tree_sitter.Node",
        content: str,
        lines: list[str],
        file_path: Path,
        name: str,
    ) -> CodeFragment:
        """Convert a tree-sitter node to a CodeFragment."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        fragment_content = "\n".join(lines[start_line : end_line + 1])

        fragment_type = "function"
        if node.type == "class_declaration":
            fragment_type = "class"

        return CodeFragment(
            file_path=file_path,
            start_line=start_line + 1,
            end_line=end_line + 1,
            content=fragment_content,
            fragment_type=fragment_type,
            name=name,
        )

    def _call_to_fragment(
        self,
        node: "tree_sitter.Node",
        content: str,
        lines: list[str],
        file_path: Path,
        name: str,
        context_lines: int,
    ) -> CodeFragment:
        """Convert a call node to a fragment with context."""
        start = max(0, node.start_point[0] - context_lines)
        end = min(len(lines), node.end_point[0] + context_lines + 1)
        fragment_content = "\n".join(lines[start:end])

        return CodeFragment(
            file_path=file_path,
            start_line=start + 1,
            end_line=end,
            content=fragment_content,
            fragment_type="call_site",
            name=name,
        )

    def _class_skeleton(
        self,
        node: "tree_sitter.Node",
        content: str,
        lines: list[str],
    ) -> str:
        """Extract class skeleton - signatures only."""
        parts: list[str] = []

        # Class declaration line
        start_line = node.start_point[0]
        parts.append(lines[start_line] if start_line < len(lines) else "")

        # Find class body and extract method signatures
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    method_line = child.start_point[0]
                    if method_line < len(lines):
                        sig = lines[method_line].strip()
                        # Just take until opening brace
                        brace_idx = sig.find("{")
                        if brace_idx > 0:
                            sig = sig[:brace_idx].strip()
                        parts.append(f"  {sig} {{ ... }}")

        return "\n".join(parts)

    def _get_jsdoc(
        self,
        node: "tree_sitter.Node",
        content: str,
        lines: list[str],
    ) -> str | None:
        """Get JSDoc comment before a node."""
        # Look at previous sibling or check lines before
        start_line = node.start_point[0]
        if start_line > 0:
            prev_line = lines[start_line - 1].strip()
            if prev_line.endswith("*/"):
                # Found end of JSDoc, find start
                jsdoc_lines = []
                for i in range(start_line - 1, max(0, start_line - 20), -1):
                    jsdoc_lines.insert(0, lines[i])
                    if lines[i].strip().startswith("/**"):
                        return "\n".join(jsdoc_lines)
        return None


# =============================================================================
# Markdown Extractor (Plain Text / Documentation)
# =============================================================================


class MarkdownExtractor:
    """Extract structure from Markdown files.

    Uses heading hierarchy as the structural skeleton:
    - Headings = function/class names
    - First paragraph under heading = docstring/signature
    - Section content = body
    """

    EXTENSIONS = {".md", ".markdown", ".txt", ".rst"}

    # Regex patterns for Markdown structure
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")

    def can_handle(self, file_path: Path) -> bool:
        """Return True for Markdown and text files."""
        return file_path.suffix.lower() in self.EXTENSIONS

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching fragments from a Markdown file."""
        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return result

        lines = content.split("\n")
        result.total_file_lines = len(lines)
        result.files_parsed = 1

        # Parse headings into a structure
        sections = self._parse_sections(content, lines)

        # Extract based on intent
        match pattern.intent:
            case Intent.DEFINITION | Intent.UNKNOWN:
                result.fragments = self._extract_definitions(
                    sections, lines, file_path, pattern
                )
            case Intent.USAGE:
                result.fragments = self._extract_mentions(
                    content, lines, file_path, pattern
                )
            case Intent.STRUCTURE:
                result.fragments = self._extract_outline(
                    sections, lines, file_path, pattern
                )
            case Intent.CONTRACT:
                result.fragments = self._extract_summaries(
                    sections, lines, file_path, pattern
                )
            case Intent.FLOW:
                # For flow, show related sections
                result.fragments = self._extract_definitions(
                    sections, lines, file_path, pattern
                )

        result.parse_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _parse_sections(
        self,
        content: str,
        lines: list[str],
    ) -> list[dict]:
        """Parse content into sections based on headings."""
        sections: list[dict] = []

        for match in self.HEADING_PATTERN.finditer(content):
            level = len(match.group(1))
            title = match.group(2).strip()
            start_pos = match.start()

            # Find line number
            line_num = content[:start_pos].count("\n") + 1

            sections.append({
                "level": level,
                "title": title,
                "line": line_num,
                "start_pos": start_pos,
            })

        # Calculate end positions
        for i, section in enumerate(sections):
            if i + 1 < len(sections):
                section["end_line"] = sections[i + 1]["line"] - 1
            else:
                section["end_line"] = len(lines)

        return sections

    def _extract_definitions(
        self,
        sections: list[dict],
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Find sections where entity is defined (heading match)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for section in sections:
            title = section["title"]
            if name_re is None or name_re.search(title):
                start = section["line"]
                end = section["end_line"]
                content = "\n".join(lines[start - 1 : end])

                fragments.append(
                    CodeFragment(
                        file_path=file_path,
                        start_line=start,
                        end_line=end,
                        content=content,
                        fragment_type="section",
                        name=title,
                        signature=f"{'#' * section['level']} {title}",
                    )
                )

        return fragments

    def _extract_mentions(
        self,
        content: str,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Find all mentions of entity in the document."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        if name_re is None:
            return fragments

        seen_lines: set[int] = set()
        context = pattern.context_lines or 2

        for i, line in enumerate(lines):
            if name_re.search(line):
                if i not in seen_lines:
                    seen_lines.add(i)
                    start = max(0, i - context)
                    end = min(len(lines), i + context + 1)
                    fragment_content = "\n".join(lines[start:end])

                    fragments.append(
                        CodeFragment(
                            file_path=file_path,
                            start_line=start + 1,
                            end_line=end,
                            content=fragment_content,
                            fragment_type="mention",
                            name=pattern.entities[0] if pattern.entities else None,
                        )
                    )

        return fragments

    def _extract_outline(
        self,
        sections: list[dict],
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract heading hierarchy as outline/TOC."""
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        # Build outline
        outline_lines: list[str] = []
        for section in sections:
            indent = "  " * (section["level"] - 1)
            outline_lines.append(f"{indent}- {section['title']}")

        outline = "\n".join(outline_lines)

        # If searching for specific entity, filter to matching section
        if name_re:
            for section in sections:
                if name_re.search(section["title"]):
                    return [
                        CodeFragment(
                            file_path=file_path,
                            start_line=1,
                            end_line=len(outline_lines),
                            content=outline,
                            fragment_type="outline",
                            name=section["title"],
                            signature="Document Outline",
                        )
                    ]

        # Return full outline
        return [
            CodeFragment(
                file_path=file_path,
                start_line=1,
                end_line=len(outline_lines),
                content=outline,
                fragment_type="outline",
                name=file_path.stem,
                signature="Document Outline",
            )
        ] if outline_lines else []

    def _extract_summaries(
        self,
        sections: list[dict],
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract heading + first paragraph (topic sentence) for each section."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for section in sections:
            title = section["title"]
            if name_re and not name_re.search(title):
                continue

            start = section["line"]
            end = min(section["end_line"], start + 5)  # Just first few lines

            # Get content and find first paragraph
            section_lines = lines[start - 1 : end]
            summary_lines: list[str] = [section_lines[0]]  # Heading

            # Find first non-empty paragraph
            in_para = False
            for line in section_lines[1:]:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    summary_lines.append(line)
                    in_para = True
                elif in_para and not stripped:
                    break  # End of first paragraph

            content = "\n".join(summary_lines)

            fragments.append(
                CodeFragment(
                    file_path=file_path,
                    start_line=start,
                    end_line=start + len(summary_lines) - 1,
                    content=content,
                    fragment_type="summary",
                    name=title,
                    signature=f"{'#' * section['level']} {title}",
                )
            )

        return fragments


# =============================================================================
# Baselines for Comparison
# =============================================================================


@dataclass(slots=True)
class BaselineResult:
    """Result from a baseline search method."""

    content: str
    lines_examined: int
    lines_returned: int
    time_ms: float
    method: str


def baseline_full_read(file_path: Path, entity: str) -> BaselineResult:
    """Baseline 1: Read the full file."""
    start = time.perf_counter()

    try:
        content = file_path.read_text()
        lines = content.split("\n")
    except (OSError, UnicodeDecodeError):
        return BaselineResult("", 0, 0, 0.0, "full_read")

    elapsed = (time.perf_counter() - start) * 1000

    return BaselineResult(
        content=content,
        lines_examined=len(lines),
        lines_returned=len(lines),
        time_ms=elapsed,
        method="full_read",
    )


def baseline_grep(file_path: Path, entity: str, context: int = 5) -> BaselineResult:
    """Baseline 2: Grep for entity with context."""
    start = time.perf_counter()

    try:
        result = subprocess.run(
            ["grep", "-n", "-i", f"-C{context}", entity, str(file_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        content = result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        content = ""

    elapsed = (time.perf_counter() - start) * 1000

    try:
        total_lines = len(file_path.read_text().split("\n"))
    except (OSError, UnicodeDecodeError):
        total_lines = 0

    return BaselineResult(
        content=content,
        lines_examined=total_lines,  # Grep examines all lines
        lines_returned=len(content.split("\n")) if content else 0,
        time_ms=elapsed,
        method="grep",
    )


# =============================================================================
# Experiment Runner
# =============================================================================


@dataclass(slots=True)
class ExperimentResult:
    """Complete result of an experiment."""

    query: str
    classified: ClassifiedQuery
    pattern: ExtractionPattern

    # Magnetic results
    magnetic_fragments: list[CodeFragment]
    magnetic_lines_returned: int
    magnetic_time_ms: float
    files_parsed: int

    # Baseline results
    baseline_full_read: BaselineResult | None = None
    baseline_grep: BaselineResult | None = None

    # Metrics
    information_density: float = 0.0  # (lines relevant) / (lines returned)
    compression_ratio: float = 0.0  # (original lines) / (magnetic lines)

    def calculate_metrics(self, total_file_lines: int) -> None:
        """Calculate derived metrics."""
        if self.magnetic_lines_returned > 0:
            # For now, assume all returned lines are relevant (optimistic)
            self.information_density = 1.0  # Magnetic returns only matches

        if total_file_lines > 0 and self.magnetic_lines_returned > 0:
            self.compression_ratio = total_file_lines / self.magnetic_lines_returned


def create_default_registry() -> ExtractorRegistry:
    """Create registry with all available extractors."""
    registry = ExtractorRegistry()
    registry.register(PythonExtractor())
    registry.register(TreeSitterExtractor())
    registry.register(MarkdownExtractor())
    return registry


def run_experiment(
    query: str,
    search_scope: list[Path],
    run_baselines: bool = True,
    registry: ExtractorRegistry | None = None,
) -> ExperimentResult:
    """Run the magnetic search experiment.

    Args:
        query: Natural language search query.
        search_scope: Files to search in.
        run_baselines: Whether to run baseline comparisons.
        registry: Extractor registry (created if not provided).

    Returns:
        ExperimentResult with all metrics.
    """
    # Classify query
    classifier = IntentClassifier()
    classified = classifier.classify(query)

    # Generate pattern
    generator = PatternGenerator()
    pattern = generator.generate(classified)

    # Run magnetic extraction using registry
    if registry is None:
        registry = create_default_registry()
    extraction = registry.extract_multi(search_scope, pattern)

    # Count lines in results
    magnetic_lines = sum(
        f.end_line - f.start_line + 1 for f in extraction.fragments
    )

    result = ExperimentResult(
        query=query,
        classified=classified,
        pattern=pattern,
        magnetic_fragments=extraction.fragments,
        magnetic_lines_returned=magnetic_lines,
        magnetic_time_ms=extraction.parse_time_ms,
        files_parsed=extraction.files_parsed,
    )

    # Run baselines if requested
    if run_baselines and search_scope and classified.entities:
        entity = classified.entities[0]
        first_file = search_scope[0]

        result.baseline_full_read = baseline_full_read(first_file, entity)
        result.baseline_grep = baseline_grep(first_file, entity)

    # Calculate metrics
    result.calculate_metrics(extraction.total_file_lines)

    return result


def format_result(result: ExperimentResult) -> str:
    """Format experiment result for display."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"Query: {result.query}")
    lines.append(f"Intent: {result.classified.intent.name} (confidence: {result.classified.confidence:.0%})")
    lines.append(f"Entities: {result.classified.entities}")
    lines.append("-" * 70)

    # Magnetic results
    lines.append("\n[MAGNETIC SEARCH]")
    lines.append(f"  Fragments found: {len(result.magnetic_fragments)}")
    lines.append(f"  Lines returned: {result.magnetic_lines_returned}")
    lines.append(f"  Files parsed: {result.files_parsed}")
    lines.append(f"  Time: {result.magnetic_time_ms:.1f}ms")
    lines.append(f"  Compression ratio: {result.compression_ratio:.1f}x")

    # Show fragments
    for i, frag in enumerate(result.magnetic_fragments[:5], 1):  # Show first 5
        lines.append(f"\n  Fragment {i} ({frag.fragment_type}): {frag.name}")
        lines.append(f"    Location: {frag.file_path.name}:{frag.start_line}-{frag.end_line}")
        preview = frag.content[:200] + "..." if len(frag.content) > 200 else frag.content
        for line in preview.split("\n")[:5]:
            lines.append(f"    | {line}")

    # Baseline comparisons
    if result.baseline_full_read:
        bl = result.baseline_full_read
        lines.append("\n[BASELINE: FULL READ]")
        lines.append(f"  Lines returned: {bl.lines_returned}")
        lines.append(f"  Time: {bl.time_ms:.1f}ms")

    if result.baseline_grep:
        bl = result.baseline_grep
        lines.append("\n[BASELINE: GREP]")
        lines.append(f"  Lines examined: {bl.lines_examined}")
        lines.append(f"  Lines returned: {bl.lines_returned}")
        lines.append(f"  Time: {bl.time_ms:.1f}ms")

    # Summary
    lines.append("\n[SUMMARY]")
    if result.baseline_full_read and result.magnetic_lines_returned > 0:
        reduction = (
            1 - result.magnetic_lines_returned / result.baseline_full_read.lines_returned
        ) * 100
        lines.append(f"  Line reduction vs full read: {reduction:.0f}%")

    lines.append("=" * 70)
    return "\n".join(lines)


# =============================================================================
# Main: Run Test Cases
# =============================================================================


def find_files(directory: Path, pattern: str, extensions: set[str] | None = None) -> list[Path]:
    """Find files matching a pattern in path or filename.

    Args:
        directory: Directory to search in.
        pattern: Pattern to match against path.
        extensions: File extensions to include (e.g., {".py", ".js"}). None = all.

    Returns:
        List of matching file paths.
    """
    results: list[Path] = []
    pattern_lower = pattern.lower()
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if extensions and path.suffix.lower() not in extensions:
            continue
        # Match against full path (relative to directory) or filename
        relative = str(path.relative_to(directory)).lower()
        if pattern_lower in relative:
            results.append(path)
    return results


def find_python_files(directory: Path, pattern: str) -> list[Path]:
    """Find Python files matching a pattern in path or filename."""
    return find_files(directory, pattern, {".py", ".pyi"})


def ensure_test_data(script_dir: Path) -> Path:
    """Ensure test data files exist for multi-language testing."""
    test_data_dir = script_dir / "test_data"
    test_data_dir.mkdir(exist_ok=True)

    # Create JavaScript test file
    js_file = test_data_dir / "example.js"
    if not js_file.exists():
        js_file.write_text('''// Test file for magnetic search experiment
/**
 * Service for managing user operations.
 * @class
 */
class UserService {
    /**
     * Create a UserService.
     * @param {Database} db - The database connection.
     */
    constructor(db) {
        this.db = db;
    }

    /**
     * Get a user by ID.
     * @param {string} id - The user ID.
     * @returns {Promise<User>} The user object.
     */
    async getUser(id) {
        return this.db.find(id);
    }

    /**
     * Create a new user.
     * @param {Object} data - The user data.
     * @returns {Promise<User>} The created user.
     */
    async createUser(data) {
        return this.db.insert(data);
    }

    /**
     * Delete a user.
     * @param {string} id - The user ID.
     */
    async deleteUser(id) {
        return this.db.delete(id);
    }
}

/**
 * Validate an email address.
 * @param {string} email - The email to validate.
 * @returns {boolean} True if valid.
 */
function validateEmail(email) {
    return email.includes('@') && email.includes('.');
}

/**
 * Format a user's display name.
 */
const formatDisplayName = (user) => {
    return `${user.firstName} ${user.lastName}`;
};

// Usage example
const service = new UserService(database);
const user = await service.getUser('123');
const isValid = validateEmail(user.email);
''')

    # Create TypeScript test file
    ts_file = test_data_dir / "example.ts"
    if not ts_file.exists():
        ts_file.write_text('''// TypeScript test file for magnetic search
interface User {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
}

interface Database {
    find(id: string): Promise<User>;
    insert(data: Partial<User>): Promise<User>;
    delete(id: string): Promise<void>;
}

/**
 * Authentication service for handling user auth.
 */
class AuthService {
    private tokenStore: Map<string, string> = new Map();

    constructor(private userService: UserService) {}

    /**
     * Authenticate a user with credentials.
     */
    async login(email: string, password: string): Promise<string> {
        const user = await this.userService.findByEmail(email);
        if (!user) throw new Error('User not found');
        const token = this.generateToken(user);
        this.tokenStore.set(user.id, token);
        return token;
    }

    /**
     * Log out a user.
     */
    async logout(userId: string): Promise<void> {
        this.tokenStore.delete(userId);
    }

    private generateToken(user: User): string {
        return `token_${user.id}_${Date.now()}`;
    }
}

// Arrow function with types
const hashPassword = async (password: string): Promise<string> => {
    return `hashed_${password}`;
};
''')

    # Create Markdown test file
    md_file = test_data_dir / "example.md"
    if not md_file.exists():
        md_file.write_text('''# Authentication System

This document explains how the authentication system works in our application.

## Overview

The authentication system provides secure user login and session management.
It supports multiple authentication methods including password-based and OAuth2.

## Login Flow

Users authenticate via the `/api/login` endpoint. The process involves:

1. User submits credentials (email + password)
2. Server validates credentials against the database
3. On success, a JWT token is generated
4. Token is returned to the client

### Password Validation

Passwords must meet the following requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one number

### Token Generation

Tokens are generated using the HS256 algorithm with a secret key.
Each token contains the user ID and expiration timestamp.

## Session Management

Sessions are stored in Redis with a 24-hour TTL (time to live).

### Session Structure

Each session contains:
- User ID
- Creation timestamp
- Last activity timestamp
- IP address

### Token Refresh

When tokens expire, the client can request a refresh using the `/api/refresh` endpoint.
The refresh token has a longer validity period (7 days).

## Security Considerations

- All passwords are hashed using bcrypt
- Rate limiting is applied to login endpoints
- Failed login attempts are logged for security monitoring

## API Reference

### POST /api/login

Authenticate a user and return a token.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "secretpassword"
}
```

**Response:**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresIn": 3600
}
```

### POST /api/logout

Invalidate the current session.

### POST /api/refresh

Get a new access token using the refresh token.
''')

    return test_data_dir


def main() -> None:
    """Run the magnetic search experiment."""
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / "src" / "sunwell"

    # Ensure test data exists
    test_data_dir = ensure_test_data(script_dir)

    print("=" * 70)
    print("MAGNETIC SEARCH EXPERIMENT - MULTI-LANGUAGE")
    print("Testing intent-driven extraction vs progressive file reading")
    print("Supports: Python, JavaScript/TypeScript, Markdown")
    print("=" * 70)

    # Check tree-sitter availability
    if TREE_SITTER_AVAILABLE:
        print("\n[INFO] Tree-sitter available: JS/TS extraction enabled")
    else:
        print("\n[INFO] Tree-sitter not available: JS/TS extraction disabled")
        print("       Install with: pip install tree-sitter tree-sitter-javascript tree-sitter-typescript")

    # Create shared registry
    registry = create_default_registry()

    # =========================================================================
    # PYTHON TEST CASES
    # =========================================================================
    print("\n" + "=" * 70)
    print("PYTHON TEST CASES")
    print("=" * 70)

    python_test_cases: list[tuple[str, str]] = [
        ("where is BindingManager defined", "binding"),
        ("what methods does UnifiedChatLoop have", "unified"),
        ("where is _execute_tool_calls called", "loop"),
        ("what does create expect", "binding/manager"),
    ]

    python_results: list[ExperimentResult] = []

    if src_dir.exists():
        for query, file_pattern in python_test_cases:
            print(f"\nRunning: {query}")
            print("-" * 50)

            matching_files = find_python_files(src_dir, file_pattern)
            if not matching_files:
                print(f"  No files found matching '{file_pattern}'")
                continue

            print(f"  Searching in {len(matching_files)} file(s)")
            result = run_experiment(query, matching_files[:10], registry=registry)
            python_results.append(result)
            print(format_result(result))
    else:
        print(f"\n[SKIP] Source directory not found: {src_dir}")

    # =========================================================================
    # JAVASCRIPT/TYPESCRIPT TEST CASES
    # =========================================================================
    print("\n" + "=" * 70)
    print("JAVASCRIPT/TYPESCRIPT TEST CASES")
    print("=" * 70)

    js_test_cases: list[tuple[str, list[Path]]] = [
        ("what methods does UserService have", [test_data_dir / "example.js"]),
        ("where is validateEmail defined", [test_data_dir / "example.js"]),
        ("what methods does AuthService have", [test_data_dir / "example.ts"]),
        ("where is login called", [test_data_dir / "example.js", test_data_dir / "example.ts"]),
    ]

    js_results: list[ExperimentResult] = []

    if TREE_SITTER_AVAILABLE:
        for query, files in js_test_cases:
            existing_files = [f for f in files if f.exists()]
            if not existing_files:
                print(f"\n[SKIP] {query} - no test files found")
                continue

            print(f"\nRunning: {query}")
            print("-" * 50)
            print(f"  Searching in {len(existing_files)} file(s)")

            result = run_experiment(query, existing_files, registry=registry)
            js_results.append(result)
            print(format_result(result))
    else:
        print("\n[SKIP] Tree-sitter not available - skipping JS/TS tests")

    # =========================================================================
    # MARKDOWN TEST CASES
    # =========================================================================
    print("\n" + "=" * 70)
    print("MARKDOWN TEST CASES")
    print("=" * 70)

    md_test_cases: list[tuple[str, list[Path]]] = [
        ("structure of Authentication System", [test_data_dir / "example.md"]),
        ("what is Session Management", [test_data_dir / "example.md"]),
        ("where is Token mentioned", [test_data_dir / "example.md"]),
        ("what does Login Flow expect", [test_data_dir / "example.md"]),
    ]

    md_results: list[ExperimentResult] = []

    for query, files in md_test_cases:
        existing_files = [f for f in files if f.exists()]
        if not existing_files:
            print(f"\n[SKIP] {query} - no test files found")
            continue

        print(f"\nRunning: {query}")
        print("-" * 50)
        print(f"  Searching in {len(existing_files)} file(s)")

        result = run_experiment(query, existing_files, registry=registry)
        md_results.append(result)
        print(format_result(result))

    # =========================================================================
    # OVERALL SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    all_results = python_results + js_results + md_results

    if not all_results:
        print("No results to summarize.")
        return

    total_magnetic_lines = sum(r.magnetic_lines_returned for r in all_results)
    total_baseline_lines = sum(
        r.baseline_full_read.lines_returned
        for r in all_results
        if r.baseline_full_read
    )
    total_fragments = sum(len(r.magnetic_fragments) for r in all_results)

    print(f"\nPython queries: {len(python_results)}")
    print(f"JS/TS queries: {len(js_results)}")
    print(f"Markdown queries: {len(md_results)}")
    print(f"Total queries: {len(all_results)}")
    print(f"Total fragments extracted: {total_fragments}")
    print(f"Total magnetic lines: {total_magnetic_lines}")
    print(f"Total baseline (full read) lines: {total_baseline_lines}")

    if total_baseline_lines > 0:
        overall_reduction = (1 - total_magnetic_lines / total_baseline_lines) * 100
        print(f"Overall line reduction: {overall_reduction:.0f}%")

    print("\nConclusion: ", end="")
    if total_baseline_lines > 0 and total_magnetic_lines < total_baseline_lines / 2:
        print("Magnetic search achieves significant compression across all file types!")
    elif total_magnetic_lines < total_baseline_lines:
        print("Magnetic search shows improvement over full reads.")
    else:
        print("More tuning needed.")


if __name__ == "__main__":
    main()
