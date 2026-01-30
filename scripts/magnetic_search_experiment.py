#!/usr/bin/env python3
"""Magnetic Search Experiment.

Tests whether intent-driven extraction ("query shapes the pattern") finds
relevant code more efficiently than progressive file reading or grep.

The metaphor: instead of sifting through sand grain by grain, we stick a
magnet into the barrel and attract only the iron filings.

Usage:
    python scripts/magnetic_search_experiment.py
"""

from __future__ import annotations

import ast
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


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


class MagneticExtractor:
    """Extract code fragments using magnetic patterns.

    Instead of reading full files, parses to AST and extracts only
    the nodes that match the pattern - like a magnet attracting iron.
    """

    def __init__(self) -> None:
        self._ast_cache: dict[Path, ast.Module | None] = {}

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching code fragments from a file.

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


def run_experiment(
    query: str,
    search_scope: list[Path],
    run_baselines: bool = True,
) -> ExperimentResult:
    """Run the magnetic search experiment.

    Args:
        query: Natural language search query.
        search_scope: Files to search in.
        run_baselines: Whether to run baseline comparisons.

    Returns:
        ExperimentResult with all metrics.
    """
    # Classify query
    classifier = IntentClassifier()
    classified = classifier.classify(query)

    # Generate pattern
    generator = PatternGenerator()
    pattern = generator.generate(classified)

    # Run magnetic extraction
    extractor = MagneticExtractor()
    extraction = extractor.extract_multi(search_scope, pattern)

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


def find_python_files(directory: Path, pattern: str) -> list[Path]:
    """Find Python files matching a pattern in path or filename."""
    results: list[Path] = []
    pattern_lower = pattern.lower()
    for path in directory.rglob("*.py"):
        # Match against full path (relative to directory) or filename
        relative = str(path.relative_to(directory)).lower()
        if pattern_lower in relative:
            results.append(path)
    return results


def main() -> None:
    """Run the magnetic search experiment."""
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / "src" / "sunwell"

    if not src_dir.exists():
        print(f"Error: Source directory not found: {src_dir}")
        return

    print("=" * 70)
    print("MAGNETIC SEARCH EXPERIMENT")
    print("Testing intent-driven extraction vs progressive file reading")
    print("=" * 70)
    print()

    # Test cases from the plan (with corrected file patterns)
    test_cases: list[tuple[str, str | None]] = [
        # Definition: find class in path containing "binding"
        ("where is BindingManager defined", "binding"),
        # Structure: extract class skeleton
        ("what methods does UnifiedChatLoop have", "unified"),
        # Usage: find call sites (need to search in agent/core where calls happen)
        ("where is _execute_tool_calls called", "loop"),
        # Contract: extract function signature + docstring (use actual method name)
        ("what does create expect", "binding/manager"),
        # Definition: find executor class
        ("where is ToolExecutor defined", "executor"),
    ]

    results: list[ExperimentResult] = []

    for query, file_pattern in test_cases:
        print(f"\nRunning: {query}")
        print("-" * 50)

        # Find relevant files
        matching_files = find_python_files(src_dir, file_pattern)
        if not matching_files:
            print(f"  No files found matching '{file_pattern}'")
            continue

        print(f"  Searching in {len(matching_files)} file(s)")

        # Run experiment
        result = run_experiment(query, matching_files[:10])  # Limit to 10 files
        results.append(result)

        # Print results
        print(format_result(result))

    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    total_magnetic_lines = sum(r.magnetic_lines_returned for r in results)
    total_baseline_lines = sum(
        r.baseline_full_read.lines_returned
        for r in results
        if r.baseline_full_read
    )
    total_fragments = sum(len(r.magnetic_fragments) for r in results)

    print(f"Total queries: {len(results)}")
    print(f"Total fragments extracted: {total_fragments}")
    print(f"Total magnetic lines: {total_magnetic_lines}")
    print(f"Total baseline (full read) lines: {total_baseline_lines}")

    if total_baseline_lines > 0:
        overall_reduction = (1 - total_magnetic_lines / total_baseline_lines) * 100
        print(f"Overall line reduction: {overall_reduction:.0f}%")

    print("\nConclusion: ", end="")
    if total_baseline_lines > 0 and total_magnetic_lines < total_baseline_lines / 2:
        print("Magnetic search achieves significant compression!")
    elif total_magnetic_lines < total_baseline_lines:
        print("Magnetic search shows improvement over full reads.")
    else:
        print("More tuning needed.")


if __name__ == "__main__":
    main()
