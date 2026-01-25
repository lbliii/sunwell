"""Deep Verification Module (RFC-047).

Semantic correctness verification for generated code.
Ensures code does the right thing, not just that it runs.

Components:
- SpecificationExtractor: Extract what code should do from contracts, docstrings, signatures
- TestGenerator: Generate behavioral tests from specifications
- BehavioralExecutor: Execute tests in isolated sandbox
- MultiPerspectiveAnalyzer: Multiple LLM personas analyze correctness
- ConfidenceTriangulator: Cross-check signals for final confidence
- DeepVerifier: Orchestrator that ties everything together

Usage:
    from sunwell.quality.verification import DeepVerifier, create_verifier

    # Create verifier with desired level
    verifier = create_verifier(model, cwd, level="standard")

    # Stream verification events
    async for event in verifier.verify(artifact_spec, content):
        print(f"{event.stage}: {event.message}")
        if event.stage == "complete":
            result = event.data["result"]
            print(f"Passed: {result.passed}, Confidence: {result.confidence:.0%}")

    # Or quick verification
    result = await verifier.verify_quick(artifact_spec, content)

Integration:
- RFC-042 (Adaptive Agent): Adds SEMANTIC gate after syntactic gates
- RFC-046 (Autonomous Backlog): Uses confidence for auto-approval
"""

# Types
# Components
from sunwell.quality.verification.analyzer import MultiPerspectiveAnalyzer
from sunwell.quality.verification.executor import BehavioralExecutor
from sunwell.quality.verification.extractor import SpecificationExtractor
from sunwell.quality.verification.generator import TestGenerator
from sunwell.quality.verification.triangulator import ConfidenceTriangulator
from sunwell.quality.verification.types import (
    QUICK_CONFIG,
    STANDARD_CONFIG,
    THOROUGH_CONFIG,
    BehavioralExecutionResult,
    DeepVerificationConfig,
    DeepVerificationResult,
    GeneratedTest,
    InputSpec,
    OutputSpec,
    PerspectiveResult,
    SemanticIssue,
    Specification,
    TestExecutionResult,
    VerificationEvent,
)
from sunwell.quality.verification.verifier import DeepVerifier, create_verifier

__all__ = [
    # Main verifier
    "DeepVerifier",
    "create_verifier",
    # Components (for advanced use)
    "SpecificationExtractor",
    "TestGenerator",
    "BehavioralExecutor",
    "MultiPerspectiveAnalyzer",
    "ConfidenceTriangulator",
    # Result types
    "DeepVerificationResult",
    "VerificationEvent",
    "BehavioralExecutionResult",
    "TestExecutionResult",
    "PerspectiveResult",
    "SemanticIssue",
    # Spec types
    "Specification",
    "InputSpec",
    "OutputSpec",
    "GeneratedTest",
    # Config
    "DeepVerificationConfig",
    "QUICK_CONFIG",
    "STANDARD_CONFIG",
    "THOROUGH_CONFIG",
]
