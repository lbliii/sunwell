"""Contract verification for Protocol compliance.

This package provides tools to verify that implementations satisfy their
declared Protocol contracts using a tiered approach:

1. **AST Analysis** (instant, free): Parse both files, check method signatures exist
2. **Static Type Check** (fast, subprocess): Run mypy on implementation file
3. **LLM Verification** (slower, fallback): Semantic check if structural checks fail

Example:
    >>> from sunwell.planning.naaru.verification import ContractVerifier
    >>> verifier = ContractVerifier(workspace=Path("."))
    >>> result = await verifier.verify(
    ...     implementation_file=Path("src/user_service.py"),
    ...     contract_file=Path("src/protocols/user.py"),
    ...     protocol_name="UserProtocol",
    ... )
    >>> if result.passed:
    ...     print("Implementation satisfies contract!")
"""

from sunwell.planning.naaru.verification.ast_checker import (
    check_implementation_satisfies,
    extract_class_methods,
    extract_protocol_info,
    extract_protocol_methods,
    find_implementing_class,
    verify_protocol_from_files,
)
from sunwell.planning.naaru.verification.contract_verifier import (
    ContractVerifier,
    verify_contracts_batch,
)
from sunwell.planning.naaru.verification.type_checker import (
    check_protocol_compliance,
    parse_protocol_errors,
    run_mypy_check,
)
from sunwell.planning.naaru.verification.types import (
    ContractVerificationResult,
    MethodMismatch,
    MethodSignature,
    ProtocolInfo,
    TierResult,
    TypeCheckResult,
    VerificationStatus,
    VerificationTier,
)

__all__ = [
    # Main verifier
    "ContractVerifier",
    "verify_contracts_batch",
    # AST checker
    "check_implementation_satisfies",
    "extract_class_methods",
    "extract_protocol_info",
    "extract_protocol_methods",
    "find_implementing_class",
    "verify_protocol_from_files",
    # Type checker
    "check_protocol_compliance",
    "parse_protocol_errors",
    "run_mypy_check",
    # Types
    "ContractVerificationResult",
    "MethodMismatch",
    "MethodSignature",
    "ProtocolInfo",
    "TierResult",
    "TypeCheckResult",
    "VerificationStatus",
    "VerificationTier",
]
