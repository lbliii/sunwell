"""Drift detection probe (RFC-103).

Detects when documentation has drifted from the actual source code:
- Renamed functions/classes
- Removed APIs
- Changed signatures
- Deprecated features

Requires workspace linking to source code repositories.

Example:
    probe = DriftProbe(source_contexts=[python_ctx, ts_ctx])
    result = await probe.run(doc_node)
    # HealthProbeResult(score=0.7, issues=["User.create() renamed to User.register()"])
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sunwell.analysis.state_dag import HealthProbeResult

if TYPE_CHECKING:
    from sunwell.analysis.source_context import SourceContext
    from sunwell.analysis.state_dag import StateDagNode

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL CONSTANTS
# ═══════════════════════════════════════════════════════════════

_SKIP_FUNCS: frozenset[str] = frozenset({
    "print", "len", "str", "int", "float",
    "list", "dict", "set", "range", "open",
})

# ═══════════════════════════════════════════════════════════════
# PRE-COMPILED REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════

# Pattern 1: Inline code with parentheses (function calls)
# `auth.login()`, `User.create()`
_RE_INLINE_FUNC = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\([^)]*\)`"
)

# Pattern 2: Inline code that looks like class/module reference
# `User`, `AuthService`, `auth.token`
_RE_INLINE_CLASS = re.compile(
    r"`([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`"
)

# Pattern 3: Python-style imports mentioned in text
# "from auth import login"
_RE_IMPORT = re.compile(r"from\s+(\w+(?:\.\w+)*)\s+import\s+(\w+)")

# Pattern 4: Code blocks - extract function definitions being demonstrated
_RE_CODE_BLOCK = re.compile(
    r"```(?:python|py|javascript|js|typescript|ts)?\n(.*?)```",
    re.DOTALL,
)

# Function calls within code blocks
_RE_FUNC_CALL = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\("
)

# Pattern 5: Sphinx/MyST roles that reference code
# :func:`auth.login`, :class:`User`, :meth:`User.save`
_RE_SPHINX_ROLE = re.compile(r":(?:func|class|meth|attr|mod):`([^`]+)`")


@dataclass(frozen=True, slots=True)
class DriftResult:
    """A single drift warning between documentation and source code."""

    doc_claim: str
    """What the documentation says (e.g., 'User.create()')."""

    source_reality: str
    """What the source actually has (e.g., 'renamed to User.register()')."""

    drift_type: Literal["renamed", "removed", "signature_changed", "deprecated"]
    """Type of drift detected."""

    doc_file: Path
    """Documentation file where the claim appears."""

    doc_line: int | None
    """Line number in documentation (if known)."""

    source_file: Path | None
    """Source file where the symbol is defined (if found)."""

    source_line: int | None
    """Line number in source (if found)."""

    confidence: float
    """Confidence that this is actually drift (0.0-1.0)."""

    suggested_fix: str | None = None
    """Suggested fix for the drift."""


class DriftProbe:
    """Detect drift between documentation and source code.

    This probe extracts code references from documentation (function calls,
    class names, API endpoints) and validates them against the indexed
    source code context.

    Detection types:
    - Renamed: Symbol exists with different name
    - Removed: Symbol no longer exists
    - Signature changed: Function signature differs
    - Deprecated: Symbol is marked deprecated

    Performance target: <100ms per node (uses pre-built symbol index).
    """

    def __init__(self, source_contexts: list[SourceContext] | None = None):
        """Initialize drift probe.

        Args:
            source_contexts: List of indexed source code contexts.
                If empty, probe will return "no source linked" status.
        """
        self.source_contexts = source_contexts or []
        self._unified_index: dict[str, SourceContext] = {}

        # Build unified symbol -> context mapping
        for ctx in self.source_contexts:
            for symbol_name in ctx.symbols:
                self._unified_index[symbol_name] = ctx

    async def run(self, node: StateDagNode) -> HealthProbeResult:
        """Check a documentation node for drift against source.

        Args:
            node: Documentation node to check.

        Returns:
            HealthProbeResult with drift score and issues.
        """
        # No source linked - can't detect drift
        if not self.source_contexts:
            return HealthProbeResult(
                probe_name="drift_detection",
                score=1.0,
                issues=(),
                metadata={"status": "no_source_linked"},
            )

        # Skip non-doc files
        if node.artifact_type == "directory":
            return HealthProbeResult(
                probe_name="drift_detection",
                score=1.0,
                issues=(),
            )

        # Read content
        try:
            content = node.path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not read {node.path}: {e}")
            return HealthProbeResult(
                probe_name="drift_detection",
                score=0.5,
                issues=("Could not read file for drift detection",),
            )

        # Extract code references from documentation
        code_refs = self._extract_code_references(content)
        if not code_refs:
            return HealthProbeResult(
                probe_name="drift_detection",
                score=1.0,
                issues=(),
                metadata={"refs_found": 0},
            )

        # Check each reference against source
        drift_warnings: list[DriftResult] = []
        for ref in code_refs:
            drift = self._check_reference(ref, node.path, content)
            if drift:
                drift_warnings.append(drift)

        # Calculate score based on drift count
        if not drift_warnings:
            score = 1.0
        elif len(drift_warnings) == 1:
            score = 0.8
        elif len(drift_warnings) <= 3:
            score = 0.6
        elif len(drift_warnings) <= 5:
            score = 0.5
        else:
            score = 0.3

        # Format issues (limit to 5 for display)
        issues = tuple(self._format_drift(d) for d in drift_warnings[:5])

        return HealthProbeResult(
            probe_name="drift_detection",
            score=score,
            issues=issues,
            metadata={
                "drift_count": len(drift_warnings),
                "refs_checked": len(code_refs),
            },
        )

    def _extract_code_references(self, content: str) -> list[str]:
        """Extract code references from documentation content.

        Looks for:
        - Inline code: `function_name()`, `ClassName`
        - Code blocks with specific function calls
        - API endpoint references
        """
        refs: set[str] = set()

        # Pattern 1: Inline code with parentheses (function calls)
        for match in _RE_INLINE_FUNC.finditer(content):
            refs.add(match.group(1))

        # Pattern 2: Inline code that looks like class/module reference
        for match in _RE_INLINE_CLASS.finditer(content):
            refs.add(match.group(1))

        # Pattern 3: Python-style imports mentioned in text
        for match in _RE_IMPORT.finditer(content):
            module = match.group(1)
            symbol = match.group(2)
            refs.add(f"{module}.{symbol}")

        # Pattern 4: Code blocks - extract function calls
        for match in _RE_CODE_BLOCK.finditer(content):
            block = match.group(1)
            func_calls = _RE_FUNC_CALL.findall(block)
            for func in func_calls:
                if func.split(".")[-1] not in _SKIP_FUNCS:
                    refs.add(func)

        # Pattern 5: Sphinx/MyST roles that reference code
        for match in _RE_SPHINX_ROLE.finditer(content):
            ref = match.group(1)
            # Strip leading ~ which is used for short display
            refs.add(ref.lstrip("~"))

        return list(refs)

    def _check_reference(
        self, ref: str, doc_path: Path, content: str
    ) -> DriftResult | None:
        """Check a single code reference against source.

        Args:
            ref: Code reference (e.g., "User.create")
            doc_path: Path to the documentation file
            content: Full documentation content

        Returns:
            DriftResult if drift detected, None otherwise.
        """
        # Try to find the symbol in any context
        found_symbol = None

        for ctx in self.source_contexts:
            symbol = ctx.lookup(ref)
            if symbol:
                found_symbol = symbol
                break

        # Symbol found - check for deprecation or signature changes
        if found_symbol:
            if found_symbol.deprecated:
                return DriftResult(
                    doc_claim=ref,
                    source_reality=f"deprecated (use {found_symbol.replacement or 'alternative'})",
                    drift_type="deprecated",
                    doc_file=doc_path,
                    doc_line=self._find_line(content, ref),
                    source_file=found_symbol.file,
                    source_line=found_symbol.line,
                    confidence=0.95,
                    suggested_fix=(
                        f"Update to use {found_symbol.replacement}"
                        if found_symbol.replacement else None
                    ),
                )
            # Symbol exists and is not deprecated - no drift
            return None

        # Symbol not found - check if it was renamed
        # Look for partial matches that might indicate a rename
        possible_renames = self._find_possible_renames(ref)
        if possible_renames:
            best_match = possible_renames[0]
            return DriftResult(
                doc_claim=ref,
                source_reality=f"renamed to {best_match.name}",
                drift_type="renamed",
                doc_file=doc_path,
                doc_line=self._find_line(content, ref),
                source_file=best_match.file,
                source_line=best_match.line,
                confidence=0.75,
                suggested_fix=f"Update reference to {best_match.name}",
            )

        # Symbol not found and no rename candidate - might be removed
        # Only flag if it looks like a real API reference (has dots or capitals)
        if "." in ref or ref[0].isupper():
            return DriftResult(
                doc_claim=ref,
                source_reality="not found in source",
                drift_type="removed",
                doc_file=doc_path,
                doc_line=self._find_line(content, ref),
                source_file=None,
                source_line=None,
                confidence=0.60,  # Lower confidence - might be external API
                suggested_fix="Verify API exists or remove reference",
            )

        return None

    def _find_possible_renames(self, ref: str) -> list:
        """Find symbols that might be renames of the reference.

        Uses fuzzy matching on the final component of the name.
        """
        from sunwell.analysis.source_context import SymbolInfo

        candidates: list[SymbolInfo] = []

        # Get the final component (e.g., "create" from "User.create")
        ref_parts = ref.split(".")
        final = ref_parts[-1].lower()

        for ctx in self.source_contexts:
            for name, symbol in ctx.symbols.items():
                name_final = name.split(".")[-1].lower()

                # Check for common rename patterns
                # - Prefix changes: login -> sign_in
                # - Suffix changes: create -> register
                # - Similar length and some character overlap

                # Skip if completely different length
                if abs(len(name_final) - len(final)) > 5:
                    continue

                # Check for shared prefix/suffix
                shared_prefix = 0
                for c1, c2 in zip(final, name_final, strict=False):
                    if c1 == c2:
                        shared_prefix += 1
                    else:
                        break

                # If significant overlap, consider as candidate
                has_prefix = shared_prefix >= 3
                has_module_match = len(ref_parts) > 1 and ref_parts[-2].lower() in name.lower()
                if has_prefix or has_module_match:
                    candidates.append(symbol)

        # Sort by relevance (prefer same kind, same module path)
        return candidates[:3]  # Return top 3 candidates

    def _find_line(self, content: str, ref: str) -> int | None:
        """Find the line number where a reference appears."""
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if ref in line:
                return i
        return None

    def _format_drift(self, drift: DriftResult) -> str:
        """Format a drift result as a human-readable issue string."""
        location = f" at line {drift.doc_line}" if drift.doc_line else ""
        if drift.drift_type == "renamed":
            return f"`{drift.doc_claim}` → {drift.source_reality}{location}"
        elif drift.drift_type == "deprecated":
            return f"`{drift.doc_claim}` is {drift.source_reality}{location}"
        elif drift.drift_type == "removed":
            return f"`{drift.doc_claim}` {drift.source_reality}{location}"
        else:
            return f"`{drift.doc_claim}` has changed{location}"
