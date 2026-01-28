"""Contract verifier implementing tiered Protocol compliance checking.

Uses a three-tier approach for verification:
1. AST Analysis - Fast structural checks
2. Static Type Check - mypy verification
3. LLM Verification - Semantic analysis (fallback)
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.planning.naaru.verification.ast_checker import (
    check_implementation_satisfies,
    extract_protocol_methods,
    find_implementing_class,
)
from sunwell.planning.naaru.verification.type_checker import (
    check_protocol_compliance,
    run_mypy_check,
)
from sunwell.planning.naaru.verification.types import (
    ContractVerificationResult,
    MethodMismatch,
    TierResult,
    VerificationStatus,
    VerificationTier,
)

if TYPE_CHECKING:
    from sunwell.llm.types import ModelProtocol


@dataclass(slots=True)
class ContractVerifier:
    """Verify implementations satisfy their Protocol contracts.

    Uses a tiered verification approach:
    1. **AST Analysis** (instant): Parse and check method signatures
    2. **Static Type Check** (fast): Run mypy for full type checking
    3. **LLM Verification** (fallback): Semantic check for edge cases

    Each tier is only run if needed (pass continues, fail tries next tier).

    Example:
        >>> verifier = ContractVerifier(workspace=Path("."))
        >>> result = await verifier.verify(
        ...     implementation_file=Path("src/service.py"),
        ...     contract_file=Path("src/protocols.py"),
        ...     protocol_name="ServiceProtocol",
        ... )
        >>> if result.passed:
        ...     print("Contract satisfied!")
    """

    workspace: Path
    """Workspace root directory."""

    model: "ModelProtocol | None" = None
    """LLM model for semantic verification (Tier 3 fallback)."""

    skip_llm: bool = False
    """If True, skip LLM verification even when model is available."""

    mypy_timeout: float = 30.0
    """Timeout for mypy type checking in seconds."""

    _tier_results: list[TierResult] = field(default_factory=list, init=False)

    async def verify(
        self,
        implementation_file: Path,
        contract_file: Path,
        protocol_name: str,
        impl_class_name: str | None = None,
    ) -> ContractVerificationResult:
        """Run tiered verification to check Protocol compliance.

        Args:
            implementation_file: Path to the implementation file
            contract_file: Path to the Protocol definition file
            protocol_name: Name of the Protocol class
            impl_class_name: Name of implementing class (auto-detected if None)

        Returns:
            ContractVerificationResult with status and details
        """
        self._tier_results = []

        # Resolve paths relative to workspace
        impl_path = self._resolve_path(implementation_file)
        contract_path = self._resolve_path(contract_file)

        # Validate files exist
        if not impl_path.exists():
            return self._error_result(
                protocol_name,
                impl_path,
                contract_path,
                f"Implementation file not found: {impl_path}",
            )

        if not contract_path.exists():
            return self._error_result(
                protocol_name,
                impl_path,
                contract_path,
                f"Contract file not found: {contract_path}",
            )

        # Read source files
        try:
            impl_source = impl_path.read_text(encoding="utf-8")
            contract_source = contract_path.read_text(encoding="utf-8")
        except OSError as e:
            return self._error_result(
                protocol_name,
                impl_path,
                contract_path,
                f"Failed to read files: {e}",
            )

        # Auto-detect implementation class if not specified
        if impl_class_name is None:
            impl_class_name = find_implementing_class(impl_source, protocol_name)
            if impl_class_name is None:
                return self._error_result(
                    protocol_name,
                    impl_path,
                    contract_path,
                    f"Could not find class implementing {protocol_name}",
                )

        # Tier 1: AST Analysis
        tier1_result = self._run_ast_check(
            impl_source, contract_source, protocol_name, impl_class_name
        )
        self._tier_results.append(tier1_result)

        if tier1_result.passed:
            # AST check passed - continue to type check for full verification
            pass
        elif tier1_result.mismatches:
            # AST found definitive mismatches - fail fast
            return ContractVerificationResult(
                status=VerificationStatus.FAILED,
                protocol_name=protocol_name,
                implementation_file=str(impl_path),
                contract_file=str(contract_path),
                tier_results=tuple(self._tier_results),
                final_tier=VerificationTier.AST,
            )

        # Tier 2: Static Type Check
        tier2_result = await self._run_type_check(
            impl_path, contract_path, protocol_name, impl_class_name
        )
        self._tier_results.append(tier2_result)

        if tier2_result.passed:
            # Full type check passed - verified!
            return ContractVerificationResult(
                status=VerificationStatus.PASSED,
                protocol_name=protocol_name,
                implementation_file=str(impl_path),
                contract_file=str(contract_path),
                tier_results=tuple(self._tier_results),
                final_tier=VerificationTier.TYPE_CHECK,
            )

        # Tier 3: LLM Verification (if available and not skipped)
        if self.model is not None and not self.skip_llm:
            tier3_result = await self._run_llm_check(
                impl_source,
                contract_source,
                protocol_name,
                impl_class_name,
                tier2_result.mismatches,
            )
            self._tier_results.append(tier3_result)

            if tier3_result.passed:
                return ContractVerificationResult(
                    status=VerificationStatus.PASSED,
                    protocol_name=protocol_name,
                    implementation_file=str(impl_path),
                    contract_file=str(contract_path),
                    tier_results=tuple(self._tier_results),
                    final_tier=VerificationTier.LLM,
                )

        # All tiers exhausted - verification failed
        return ContractVerificationResult(
            status=VerificationStatus.FAILED,
            protocol_name=protocol_name,
            implementation_file=str(impl_path),
            contract_file=str(contract_path),
            tier_results=tuple(self._tier_results),
            final_tier=self._tier_results[-1].tier if self._tier_results else None,
        )

    def _resolve_path(self, path: Path) -> Path:
        """Resolve a path relative to workspace if not absolute."""
        if path.is_absolute():
            return path
        return self.workspace / path

    def _error_result(
        self,
        protocol_name: str,
        impl_path: Path,
        contract_path: Path,
        error_message: str,
    ) -> ContractVerificationResult:
        """Create an error result."""
        return ContractVerificationResult(
            status=VerificationStatus.ERROR,
            protocol_name=protocol_name,
            implementation_file=str(impl_path),
            contract_file=str(contract_path),
            tier_results=tuple(self._tier_results),
            error_message=error_message,
        )

    def _run_ast_check(
        self,
        impl_source: str,
        contract_source: str,
        protocol_name: str,
        impl_class_name: str,
    ) -> TierResult:
        """Run Tier 1: AST-based structural verification."""
        start_time = time.perf_counter()

        try:
            # Extract required methods from Protocol
            required_methods = extract_protocol_methods(contract_source, protocol_name)

            if not required_methods:
                return TierResult(
                    tier=VerificationTier.AST,
                    passed=True,
                    message="Protocol has no required methods",
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                )

            # Check implementation
            mismatches = check_implementation_satisfies(
                impl_source, impl_class_name, required_methods
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            if not mismatches:
                return TierResult(
                    tier=VerificationTier.AST,
                    passed=True,
                    message=f"All {len(required_methods)} methods found with matching signatures",
                    duration_ms=duration_ms,
                )

            return TierResult(
                tier=VerificationTier.AST,
                passed=False,
                message=f"Found {len(mismatches)} signature mismatch(es)",
                mismatches=tuple(
                    MethodMismatch(
                        method_name=m.method_name,
                        issue=m.issue,
                        expected=m.expected,
                        actual=m.actual,
                    )
                    for m in mismatches
                ),
                duration_ms=duration_ms,
            )

        except ValueError as e:
            return TierResult(
                tier=VerificationTier.AST,
                passed=False,
                message=f"AST analysis failed: {e}",
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )

    async def _run_type_check(
        self,
        impl_path: Path,
        contract_path: Path,
        protocol_name: str,
        impl_class_name: str,
    ) -> TierResult:
        """Run Tier 2: Static type checking with mypy."""
        start_time = time.perf_counter()

        try:
            result = await check_protocol_compliance(
                implementation_file=impl_path,
                protocol_file=contract_path,
                protocol_name=protocol_name,
                impl_class_name=impl_class_name,
                timeout_seconds=self.mypy_timeout,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            if result.passed:
                return TierResult(
                    tier=VerificationTier.TYPE_CHECK,
                    passed=True,
                    message="mypy type check passed",
                    duration_ms=duration_ms,
                )

            # Filter out import-not-found errors - they're not Protocol compliance issues
            # These occur when files are in temp directories without proper package structure
            compliance_errors = [
                e for e in result.errors
                if "import-not-found" not in e
                and "Cannot find implementation or library stub" not in e
            ]

            if not compliance_errors:
                # All errors were import-related - consider this passed
                # since AST already verified the structural contract
                return TierResult(
                    tier=VerificationTier.TYPE_CHECK,
                    passed=True,
                    message="mypy passed (import errors ignored)",
                    duration_ms=duration_ms,
                )

            # Convert errors to mismatches
            mismatches = tuple(
                MethodMismatch(
                    method_name="<type-error>",
                    issue=error,
                )
                for error in compliance_errors
            )

            return TierResult(
                tier=VerificationTier.TYPE_CHECK,
                passed=False,
                message=f"mypy found {len(compliance_errors)} type error(s)",
                mismatches=mismatches,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return TierResult(
                tier=VerificationTier.TYPE_CHECK,
                passed=False,
                message=f"Type check failed: {e}",
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )

    async def _run_llm_check(
        self,
        impl_source: str,
        contract_source: str,
        protocol_name: str,
        impl_class_name: str,
        prior_mismatches: tuple[MethodMismatch, ...],
    ) -> TierResult:
        """Run Tier 3: LLM-based semantic verification."""
        start_time = time.perf_counter()

        if self.model is None:
            return TierResult(
                tier=VerificationTier.LLM,
                passed=False,
                message="No LLM model available for semantic verification",
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )

        try:
            # Build prompt for LLM verification
            prompt = self._build_llm_prompt(
                impl_source,
                contract_source,
                protocol_name,
                impl_class_name,
                prior_mismatches,
            )

            # Call LLM
            response = await self.model.generate(prompt)
            response_text = response.content.lower() if response.content else ""

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Parse LLM response
            if "satisfies" in response_text or "compatible" in response_text:
                if "does not satisfy" in response_text or "not compatible" in response_text:
                    return TierResult(
                        tier=VerificationTier.LLM,
                        passed=False,
                        message="LLM determined implementation does not satisfy protocol",
                        duration_ms=duration_ms,
                    )
                return TierResult(
                    tier=VerificationTier.LLM,
                    passed=True,
                    message="LLM verified implementation satisfies protocol",
                    duration_ms=duration_ms,
                )

            return TierResult(
                tier=VerificationTier.LLM,
                passed=False,
                message="LLM verification inconclusive",
                duration_ms=duration_ms,
            )

        except Exception as e:
            return TierResult(
                tier=VerificationTier.LLM,
                passed=False,
                message=f"LLM verification failed: {e}",
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )

    def _build_llm_prompt(
        self,
        impl_source: str,
        contract_source: str,
        protocol_name: str,
        impl_class_name: str,
        prior_mismatches: tuple[MethodMismatch, ...],
    ) -> str:
        """Build prompt for LLM verification."""
        mismatch_text = ""
        if prior_mismatches:
            mismatch_text = "\n\nPrior analysis found these potential issues:\n"
            for m in prior_mismatches:
                mismatch_text += f"- {m.method_name}: {m.issue}"
                if m.expected:
                    mismatch_text += f" (expected: {m.expected})"
                if m.actual:
                    mismatch_text += f" (actual: {m.actual})"
                mismatch_text += "\n"

        return f"""Analyze whether the class `{impl_class_name}` satisfies the Protocol `{protocol_name}`.

## Protocol Definition
```python
{contract_source}
```

## Implementation
```python
{impl_source}
```
{mismatch_text}
Answer ONLY with one of:
- "SATISFIES: The implementation satisfies the protocol" (if compatible)
- "DOES NOT SATISFY: <reason>" (if not compatible)

Focus on:
1. All required methods are implemented
2. Method signatures are compatible (parameters and return types)
3. Async/sync consistency"""


async def verify_contracts_batch(
    verifier: ContractVerifier,
    contracts: list[tuple[Path, Path, str, str | None]],
) -> list[ContractVerificationResult]:
    """Verify multiple contracts in sequence.

    Args:
        verifier: ContractVerifier instance
        contracts: List of (impl_file, contract_file, protocol_name, impl_class_name)

    Returns:
        List of verification results in same order
    """
    results = []
    for impl_file, contract_file, protocol_name, impl_class in contracts:
        result = await verifier.verify(
            implementation_file=impl_file,
            contract_file=contract_file,
            protocol_name=protocol_name,
            impl_class_name=impl_class,
        )
        results.append(result)
    return results
