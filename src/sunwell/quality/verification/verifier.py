"""Deep Verifier Orchestrator for RFC-047.

Ties all verification components together.
"""


import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.verification.analyzer import MultiPerspectiveAnalyzer
from sunwell.verification.executor import BehavioralExecutor
from sunwell.verification.extractor import SpecificationExtractor
from sunwell.verification.generator import TestGenerator
from sunwell.verification.triangulator import ConfidenceTriangulator
from sunwell.verification.types import (
    QUICK_CONFIG,
    STANDARD_CONFIG,
    THOROUGH_CONFIG,
    DeepVerificationConfig,
    DeepVerificationResult,
    VerificationEvent,
)

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.artifacts import ArtifactSpec


class DeepVerifier:
    """Orchestrates deep semantic verification.

    Integration with RFC-042 (Adaptive Agent):
    - DeepVerifier runs AFTER syntactic gates pass
    - If DeepVerifier fails, triggers Compound Eye for fix
    - Confidence feeds into technique selection

    Integration with RFC-046 (Autonomous Backlog):
    - auto_approvable goals require DeepVerifier pass
    - DeepVerifier confidence determines goal completion
    """

    def __init__(
        self,
        model: ModelProtocol,
        cwd: Path,
        config: DeepVerificationConfig | None = None,
    ):
        self.model = model
        self.cwd = cwd
        self.config = config or STANDARD_CONFIG

        # Components
        self.spec_extractor = SpecificationExtractor(model)
        self.test_generator = TestGenerator(model)
        self.executor = BehavioralExecutor(
            cwd,
            timeout_per_test=self.config.test_timeout_s,
            total_timeout=self.config.total_timeout_s,
        )
        self.analyzer = MultiPerspectiveAnalyzer(model)
        self.triangulator = ConfidenceTriangulator()

    async def verify(
        self,
        artifact: ArtifactSpec,
        content: str,
        existing_code: str | None = None,
        existing_tests: str | None = None,
    ) -> AsyncIterator[VerificationEvent]:
        """Verify an artifact with streaming events.

        Args:
            artifact: The artifact specification
            content: Generated content to verify
            existing_code: Previous version (for regression detection)
            existing_tests: Existing tests (for spec mining)

        Yields:
            VerificationEvent for each stage
        """
        start = time.monotonic()

        yield VerificationEvent(
            stage="start",
            message="Starting deep verification",
            data={"level": self.config.level},
        )

        # Stage 1: Extract specification
        yield VerificationEvent(
            stage="spec_extraction",
            message="Extracting specification from contract, docstrings, and signatures",
        )

        spec = await self.spec_extractor.extract(artifact, content, existing_tests)

        yield VerificationEvent(
            stage="spec_extracted",
            message=f"Specification extracted (confidence: {spec.confidence:.0%})",
            data={
                "source": spec.source,
                "confidence": spec.confidence,
                "edge_cases": len(spec.edge_cases),
                "invariants": len(spec.invariants),
            },
        )

        # Stage 2: Generate tests (if configured)
        tests = []
        if self.config.max_tests > 0:
            yield VerificationEvent(
                stage="test_generation",
                message=f"Generating up to {self.config.max_tests} behavioral tests",
            )

            tests = await self.test_generator.generate(
                artifact,
                content,
                spec,
                max_tests=self.config.max_tests,
            )

            yield VerificationEvent(
                stage="tests_generated",
                message=f"Generated {len(tests)} tests",
                data={
                    "count": len(tests),
                    "categories": self._count_test_categories(tests),
                },
            )

        # Stage 3: Execute tests (if we have any)
        execution_results = None
        if tests:
            yield VerificationEvent(
                stage="test_execution",
                message=f"Executing {len(tests)} behavioral tests",
            )

            execution_results = await self.executor.execute(content, tests)

            yield VerificationEvent(
                stage="tests_executed",
                message=f"Tests completed: {execution_results.passed}/{execution_results.total_tests} passed",
                data={
                    "passed": execution_results.passed,
                    "failed": execution_results.failed,
                    "errors": execution_results.errors,
                    "pass_rate": execution_results.pass_rate,
                },
            )

        # Stage 4: Multi-perspective analysis
        yield VerificationEvent(
            stage="analysis",
            message=f"Running {len(self.config.perspectives)} perspective analysis",
        )

        perspectives = await self.analyzer.analyze(
            artifact, content, spec, execution_results, existing_code
        )

        yield VerificationEvent(
            stage="analyzed",
            message=f"Analysis complete: {sum(1 for p in perspectives if p.verdict == 'correct')}/{len(perspectives)} perspectives positive",
            data={
                "perspectives": len(perspectives),
                "verdicts": {p.perspective: p.verdict for p in perspectives},
            },
        )

        # Stage 5: Triangulate
        yield VerificationEvent(
            stage="triangulation",
            message="Computing final confidence via triangulation",
        )

        result = self.triangulator.triangulate(
            spec, execution_results, perspectives, tests
        )

        # Add timing
        duration = int((time.monotonic() - start) * 1000)
        result = DeepVerificationResult(
            passed=result.passed,
            confidence=result.confidence,
            issues=result.issues,
            generated_tests=result.generated_tests,
            test_results=result.test_results,
            perspective_results=result.perspective_results,
            recommendations=result.recommendations,
            duration_ms=duration,
        )

        yield VerificationEvent(
            stage="complete",
            message=f"Verification {'PASSED' if result.passed else 'FAILED'} (confidence: {result.confidence:.0%})",
            data={"result": result},
        )

    async def verify_quick(
        self,
        artifact: ArtifactSpec,
        content: str,
    ) -> DeepVerificationResult:
        """Quick verification without streaming.

        Useful for integration with existing validation cascade.
        """
        result = None
        async for event in self.verify(artifact, content):
            if event.stage == "complete":
                result = event.data.get("result")

        if result is None:
            # Should not happen, but provide fallback
            return DeepVerificationResult(
                passed=False,
                confidence=0.0,
                issues=(),
                generated_tests=(),
                test_results=None,
                perspective_results=(),
                recommendations=("Verification failed to complete",),
                duration_ms=0,
            )

        return result

    def _count_test_categories(self, tests: list) -> dict[str, int]:
        """Count tests by category."""
        counts: dict[str, int] = {}
        for test in tests:
            category = test.category
            counts[category] = counts.get(category, 0) + 1
        return counts


# Factory functions for different verification levels
def create_verifier(
    model: ModelProtocol,
    cwd: Path,
    level: str = "standard",
) -> DeepVerifier:
    """Create a DeepVerifier with the specified level.

    Args:
        model: The model to use for LLM calls
        cwd: Working directory for test execution
        level: One of "quick", "standard", "thorough"

    Returns:
        Configured DeepVerifier
    """
    configs = {
        "quick": QUICK_CONFIG,
        "standard": STANDARD_CONFIG,
        "thorough": THOROUGH_CONFIG,
    }

    config = configs.get(level, STANDARD_CONFIG)
    return DeepVerifier(model, cwd, config)
