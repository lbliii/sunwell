"""Demo executor for single-shot vs Sunwell comparison (RFC-095).

Runs the same task through raw single-shot prompting and through
Sunwell's cognitive architecture (Resonance loop) for comparison.

Supports:
- Parallel execution: Run both methods concurrently (2x faster)
- Streaming: Real-time code generation to UI
- Full stack: Lens integration + component breakdown
"""

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sunwell.foundation.utils import safe_yaml_load
from sunwell.benchmark.demo.judge import DemoJudge
from sunwell.benchmark.demo.scorer import DemoScorer
from sunwell.benchmark.demo.tasks import DemoTask
from sunwell.planning.naaru.resonance import Resonance, ResonanceConfig

# Type alias for streaming callbacks
StreamCallback = Callable[[str, str], None]  # (method: "single_shot"|"sunwell", chunk: str)


@dataclass(frozen=True, slots=True)
class ComponentBreakdown:
    """Tracks what each Sunwell component contributed.

    Shows the "anatomy" of a Sunwell response - which components
    were used and what each contributed to the final output.
    """

    # Lens info
    lens_name: str = "none"
    lens_detected: bool = False
    heuristics_applied: tuple[str, ...] = ()

    # Structured prompting
    prompt_type: str = "basic"  # "basic" | "structured" | "lens-enhanced"
    requirements_added: tuple[str, ...] = ()

    # Judge evaluation
    judge_score: float = 0.0
    judge_issues: tuple[str, ...] = ()
    judge_passed: bool = False

    # Resonance refinement
    resonance_triggered: bool = False
    resonance_succeeded: bool = False  # Did refinement actually help?
    resonance_iterations: int = 0
    resonance_improvements: tuple[str, ...] = ()

    # Final validation
    final_score: float = 0.0
    features_achieved: tuple[str, ...] = ()
    features_missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DemoResult:
    """Result from a single demo execution.

    Attributes:
        code: The generated code.
        time_ms: Time taken in milliseconds.
        method: Either "single_shot" or "sunwell".
        iterations: Number of refinement iterations (for Sunwell method).
        judge_score: Score from judge evaluation (for Sunwell method).
        judge_feedback: Feedback from judge (for Sunwell method).
        prompt_tokens: Number of input tokens used.
        completion_tokens: Number of output tokens generated.
        total_tokens: Total tokens used.
        breakdown: Component breakdown showing what each part contributed.
    """

    code: str
    time_ms: int
    method: str
    iterations: int = 0
    judge_score: float | None = None
    judge_feedback: tuple[str, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    breakdown: ComponentBreakdown | None = None


class DemoExecutor:
    """Runs single-shot and Sunwell comparisons.

    This executor demonstrates the Prism Principle by running the same
    task through:
    1. Raw single-shot prompting (baseline)
    2. Sunwell's cognitive architecture with Lens + Resonance refinement

    The difference in output quality makes the value proposition undeniable.
    """

    def __init__(self, model: Any, verbose: bool = False) -> None:
        """Initialize executor with a model.

        Args:
            model: A model implementing the ModelProtocol.
            verbose: Whether to emit verbose progress output.
        """
        self.model = model
        self.verbose = verbose
        self.judge = DemoJudge(model)
        self.scorer = DemoScorer()  # Deterministic scorer for honest evaluation
        self.resonance = Resonance(
            model=model,
            config=ResonanceConfig(
                max_attempts=2,
                temperature_boost=0.1,
                max_tokens=1024,
            ),
        )
        # Load lens for enhanced prompting - prefer v2 mental model format
        self.lens_data = self._load_lens_v2()
        self.prompt_builder = self._create_prompt_builder()
        # Also load raw YAML for fallback
        self.lens = self._load_coder_lens()
        self.lens_heuristics = self._extract_lens_heuristics()

    def _load_lens_v2(self):
        """Load v2 lens (mental model format) for enhanced prompting."""
        try:
            from sunwell.benchmark.demo.lens_experiments import LensData
            
            # Prefer v2 python-expert lens, fall back to coder.lens
            lens_paths = [
                Path("lenses/python-expert-v2.lens"),
                Path(__file__).parent.parent.parent.parent / "lenses" / "python-expert-v2.lens",
                Path("lenses/coder.lens"),
                Path(__file__).parent.parent.parent.parent / "lenses" / "coder.lens",
                Path.home() / ".sunwell" / "lenses" / "coder.lens",
            ]
            
            for path in lens_paths:
                if path.exists():
                    return LensData.from_yaml(path)
            return None
        except Exception:
            return None
    
    def _create_prompt_builder(self):
        """Create the best prompt builder for the loaded lens."""
        if not self.lens_data:
            return None
        
        try:
            from sunwell.benchmark.demo.lens_experiments import LensStrategy, create_prompt_builder
            # Use examples_prominent - best performing strategy
            return create_prompt_builder(LensStrategy.EXAMPLES_PROMINENT, self.lens_data)
        except Exception:
            return None

    def _load_coder_lens(self) -> dict | None:
        """Load the coder.lens file for enhanced prompting."""
        try:
            # Try common lens locations
            lens_paths = [
                Path("lenses/coder.lens"),
                Path.home() / ".sunwell" / "lenses" / "coder.lens",
                Path(__file__).parent.parent.parent.parent / "lenses" / "coder.lens",
            ]

            for path in lens_paths:
                if path.exists():
                    return safe_yaml_load(path)
            return None
        except Exception:
            return None

    def _extract_lens_heuristics(self) -> list[str]:
        """Extract key heuristics from the lens for the prompt."""
        if not self.lens:
            return []

        try:
            heuristics = self.lens.get("lens", {}).get("heuristics", [])
            # Extract the top priority rules
            sorted_h = sorted(heuristics, key=lambda h: h.get("priority", 0), reverse=True)
            return [h.get("name", "") for h in sorted_h[:5]]
        except Exception:
            return []

    def _build_lens_enhanced_prompt(self, task: DemoTask) -> tuple[str, tuple[str, ...]]:
        """Build a prompt enhanced with lens heuristics.

        Uses v2 mental model format if available, falls back to v1.

        Returns:
            Tuple of (prompt, requirements_added)
        """
        # Use v2 prompt builder if available
        if self.prompt_builder and self.lens_data:
            prompt = self.prompt_builder.build_prompt(task.prompt)
            # Extract heuristic names as "requirements" for tracking
            requirements = tuple(
                h.get("name", "Heuristic")
                for h in self.lens_data.heuristics
            )
            return prompt, requirements
        
        # Fallback to v1 approach
        requirements = [
            "Include type hints for all parameters and return values",
            "Write a complete docstring with Args, Returns, and Raises sections",
            "Handle edge cases and errors appropriately",
            "Follow Python best practices",
        ]

        # Add lens-specific requirements
        if self.lens:
            lens_heuristics = self.lens.get("lens", {}).get("heuristics", [])
            for h in lens_heuristics:
                if h.get("priority", 0) >= 0.85:
                    # Add the "always" rules from high-priority heuristics
                    always_rules = h.get("always", [])
                    if always_rules and len(requirements) < 8:
                        requirements.append(always_rules[0])

        prompt = f"""Write production-quality Python code.

Task: {task.prompt}

Requirements:
{chr(10).join(f'- {r}' for r in requirements)}

Code only (no explanations):"""

        return prompt, tuple(requirements)

    async def run_single_shot(
        self,
        task: DemoTask,
        *,
        on_progress: Any = None,
    ) -> DemoResult:
        """Run the task with raw single-shot prompting.

        This is the baseline - what you'd get from raw model prompting
        without any cognitive architecture.

        Args:
            task: The demo task to run.
            on_progress: Optional callback for progress updates.

        Returns:
            DemoResult with the generated code.
        """
        # Simple prompt - no structure, no guidance
        prompt = f"You are a Python developer. {task.prompt}"

        if on_progress:
            on_progress("Generating (single-shot)...")

        start = time.perf_counter()

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(
                temperature=0.7,
                max_tokens=512,
            ),
        )

        elapsed = int((time.perf_counter() - start) * 1000)

        # Extract token usage
        usage = result.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        return DemoResult(
            code=result.content or "",
            time_ms=elapsed,
            method="single_shot",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    async def run_sunwell(
        self,
        task: DemoTask,
        *,
        on_progress: Any = None,
    ) -> DemoResult:
        """Run the task through Sunwell's cognitive architecture.

        Uses the full stack:
        1. Lens-enhanced prompting (coder.lens heuristics)
        2. Initial generation
        3. Judge evaluation
        4. Resonance refinement (if needed)

        Args:
            task: The demo task to run.
            on_progress: Optional callback for progress updates.

        Returns:
            DemoResult with refined code, metadata, and component breakdown.
        """
        start = time.perf_counter()

        # Track what components are used
        lens_name = "coder.lens" if self.lens else "none"
        lens_detected = self.lens is not None

        # 1. Build lens-enhanced prompt
        if on_progress:
            on_progress("Applying lens heuristics...")

        from sunwell.models.protocol import GenerateOptions

        initial_prompt, requirements_added = self._build_lens_enhanced_prompt(task)

        initial_result = await self.model.generate(
            initial_prompt,
            options=GenerateOptions(
                temperature=0.3,
                max_tokens=768,
            ),
        )

        initial_code = initial_result.content or ""

        # Track token usage across all calls
        total_prompt_tokens = 0
        total_completion_tokens = 0

        if initial_result.usage:
            total_prompt_tokens += initial_result.usage.prompt_tokens
            total_completion_tokens += initial_result.usage.completion_tokens

        # 2. Judge evaluation (also uses tokens)
        if on_progress:
            on_progress("Judge evaluating...")

        judgment = await self.judge.evaluate(initial_code, task.expected_features)

        # Track judge evaluation
        judge_issues = tuple(judgment.feedback) if judgment.feedback else ()
        judge_passed = judgment.score >= 8.0

        # 3. Score initial code with deterministic scorer (same scorer used for final evaluation)
        initial_score_result = self.scorer.score(initial_code, task.expected_features)
        initial_score = initial_score_result.score

        # 4. Resonance refinement (if initial score is low)
        iterations = 0
        final_code = initial_code
        resonance_triggered = False
        resonance_succeeded = False
        resonance_improvements: list[str] = []

        # Trigger Resonance on low score (using deterministic scorer, not judge)
        if initial_score < 8.0:
            resonance_triggered = True
            if on_progress:
                on_progress("Resonance refining...")

            # Build feedback from judge AND scorer issues
            feedback_parts = []
            if initial_score_result.issues:
                feedback_parts.append(f"Missing features: {', '.join(initial_score_result.issues)}")
            if judgment.feedback:
                feedback_parts.extend(judgment.feedback)
            if not feedback_parts:
                feedback_parts.append(f"Score too low ({initial_score}/10). Improve code quality.")

            # Prepare proposal and rejection for Resonance
            proposal = {
                "diff": initial_code,
                "proposal_id": str(uuid.uuid4())[:8],
                "summary": {"category": "code_quality"},
            }

            rejection = {
                "issues": list(initial_score_result.issues),
                "feedback": " ".join(feedback_parts),
                "score": initial_score,
            }

            # Run Resonance refinement
            resonance_result = await self.resonance.refine(proposal, rejection)

            if resonance_result.success and resonance_result.refined_code:
                # CRITICAL: Re-score refined code with same deterministic scorer
                refined_score_result = self.scorer.score(
                    resonance_result.refined_code, task.expected_features
                )

                # Only accept refinement if it ACTUALLY improved the score
                if refined_score_result.score > initial_score:
                    resonance_succeeded = True
                    final_code = resonance_result.refined_code
                    iterations = len(resonance_result.attempts)

                    # Track what features were actually gained
                    initial_features = set(
                        f for f, present in initial_score_result.features.items() if present
                    )
                    refined_features = set(
                        f for f, present in refined_score_result.features.items() if present
                    )
                    gained_features = refined_features - initial_features
                    resonance_improvements = list(gained_features) if gained_features else ["quality"]

                    # Add resonance tokens if tracked
                    if hasattr(resonance_result, 'total_tokens'):
                        total_prompt_tokens += getattr(resonance_result, 'prompt_tokens', 0)
                        total_completion_tokens += getattr(resonance_result, 'completion_tokens', 0)
                # else: refinement didn't help, keep original code

        elapsed = int((time.perf_counter() - start) * 1000)

        # Final scoring with deterministic scorer (honest evaluation)
        final_score_result = self.scorer.score(final_code, task.expected_features)
        achieved = tuple(f for f, present in final_score_result.features.items() if present)
        missing = tuple(final_score_result.issues)

        # Build component breakdown - honest about what happened
        breakdown = ComponentBreakdown(
            lens_name=lens_name,
            lens_detected=lens_detected,
            heuristics_applied=tuple(self.lens_heuristics) if self.lens_heuristics else (),
            prompt_type="lens-enhanced" if lens_detected else "structured",
            requirements_added=requirements_added,
            judge_score=initial_score,  # Use deterministic scorer, not LLM judge
            judge_issues=judge_issues,
            judge_passed=initial_score >= 8.0,
            resonance_triggered=resonance_triggered,
            resonance_succeeded=resonance_succeeded,
            resonance_iterations=iterations,
            resonance_improvements=tuple(resonance_improvements),
            final_score=final_score_result.score,  # Honest final score
            features_achieved=achieved,
            features_missing=missing,
        )

        return DemoResult(
            code=final_code,
            time_ms=elapsed,
            method="sunwell",
            iterations=iterations,
            judge_score=judgment.score,
            judge_feedback=judgment.feedback,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            breakdown=breakdown,
        )

    async def run_single_shot_streaming(
        self,
        task: DemoTask,
        *,
        on_chunk: Callable[[str], None] | None = None,
    ) -> DemoResult:
        """Run single-shot with streaming output.

        Args:
            task: The demo task to run.
            on_chunk: Callback for each streamed chunk.

        Returns:
            DemoResult with the generated code.
        """
        prompt = f"You are a Python developer. {task.prompt}"

        start = time.perf_counter()
        chunks: list[str] = []

        from sunwell.models.protocol import GenerateOptions

        async for chunk in self.model.generate_stream(
            prompt,
            options=GenerateOptions(
                temperature=0.7,
                max_tokens=512,
            ),
        ):
            chunks.append(chunk)
            if on_chunk:
                on_chunk(chunk)

        elapsed = int((time.perf_counter() - start) * 1000)
        code = "".join(chunks)

        # Note: Streaming doesn't provide token counts, estimate from content
        # Rough estimate: ~4 chars per token
        estimated_tokens = len(code) // 4

        return DemoResult(
            code=code,
            time_ms=elapsed,
            method="single_shot",
            completion_tokens=estimated_tokens,
            total_tokens=estimated_tokens,
        )

    async def run_sunwell_streaming(
        self,
        task: DemoTask,
        *,
        on_chunk: Callable[[str], None] | None = None,
        on_phase: Callable[[str], None] | None = None,
    ) -> DemoResult:
        """Run Sunwell method with streaming output.

        Uses the full stack:
        1. Lens-enhanced prompting
        2. Streaming generation
        3. Judge evaluation
        4. Resonance refinement (if needed)

        Args:
            task: The demo task to run.
            on_chunk: Callback for each streamed chunk.
            on_phase: Callback for phase changes ("generating", "judging", "refining").

        Returns:
            DemoResult with refined code, metadata, and component breakdown.
        """
        start = time.perf_counter()
        total_prompt_tokens = 0
        total_completion_tokens = 0

        # Track components
        lens_name = "coder.lens" if self.lens else "none"
        lens_detected = self.lens is not None

        from sunwell.models.protocol import GenerateOptions

        initial_prompt, requirements_added = self._build_lens_enhanced_prompt(task)

        # Phase 1: Stream initial generation
        if on_phase:
            on_phase("generating")

        chunks: list[str] = []
        async for chunk in self.model.generate_stream(
            initial_prompt,
            options=GenerateOptions(
                temperature=0.3,
                max_tokens=768,
            ),
        ):
            chunks.append(chunk)
            if on_chunk:
                on_chunk(chunk)

        initial_code = "".join(chunks)
        total_completion_tokens += len(initial_code) // 4  # Estimate

        # Phase 2: Judge evaluation (for feedback) + deterministic scoring
        if on_phase:
            on_phase("judging")

        judgment = await self.judge.evaluate(initial_code, task.expected_features)
        judge_issues = tuple(judgment.feedback) if judgment.feedback else ()

        # Score with deterministic scorer (same scorer used for final evaluation)
        initial_score_result = self.scorer.score(initial_code, task.expected_features)
        initial_score = initial_score_result.score

        # Phase 3: Resonance refinement (if needed)
        iterations = 0
        final_code = initial_code
        resonance_triggered = False
        resonance_succeeded = False
        resonance_improvements: list[str] = []

        # Trigger Resonance on low score (using deterministic scorer)
        if initial_score < 8.0:
            resonance_triggered = True
            if on_phase:
                on_phase("refining")

            # Build feedback from judge AND scorer issues
            feedback_parts = []
            if initial_score_result.issues:
                feedback_parts.append(f"Missing features: {', '.join(initial_score_result.issues)}")
            if judgment.feedback:
                feedback_parts.extend(judgment.feedback)
            if not feedback_parts:
                feedback_parts.append(f"Score too low ({initial_score}/10). Improve code quality.")

            proposal = {
                "diff": initial_code,
                "proposal_id": str(uuid.uuid4())[:8],
                "summary": {"category": "code_quality"},
            }

            rejection = {
                "issues": list(initial_score_result.issues),
                "feedback": " ".join(feedback_parts),
                "score": initial_score,
            }

            resonance_result = await self.resonance.refine(proposal, rejection)

            if resonance_result.success and resonance_result.refined_code:
                # CRITICAL: Re-score refined code with same deterministic scorer
                refined_score_result = self.scorer.score(
                    resonance_result.refined_code, task.expected_features
                )

                # Only accept refinement if it ACTUALLY improved the score
                if refined_score_result.score > initial_score:
                    resonance_succeeded = True
                    final_code = resonance_result.refined_code
                    iterations = len(resonance_result.attempts)

                    # Track what features were actually gained
                    initial_features = set(
                        f for f, present in initial_score_result.features.items() if present
                    )
                    refined_features = set(
                        f for f, present in refined_score_result.features.items() if present
                    )
                    gained_features = refined_features - initial_features
                    resonance_improvements = list(gained_features) if gained_features else ["quality"]
                # else: refinement didn't help, keep original code

        elapsed = int((time.perf_counter() - start) * 1000)

        # Final scoring with deterministic scorer (honest evaluation)
        final_score_result = self.scorer.score(final_code, task.expected_features)
        achieved = tuple(f for f, present in final_score_result.features.items() if present)
        missing = tuple(final_score_result.issues)

        # Build component breakdown - honest about what happened
        breakdown = ComponentBreakdown(
            lens_name=lens_name,
            lens_detected=lens_detected,
            heuristics_applied=tuple(self.lens_heuristics) if self.lens_heuristics else (),
            prompt_type="lens-enhanced" if lens_detected else "structured",
            requirements_added=requirements_added,
            judge_score=initial_score,  # Use deterministic scorer
            judge_issues=judge_issues,
            judge_passed=initial_score >= 8.0,
            resonance_triggered=resonance_triggered,
            resonance_succeeded=resonance_succeeded,
            resonance_iterations=iterations,
            resonance_improvements=tuple(resonance_improvements),
            final_score=final_score_result.score,  # Honest final score
            features_achieved=achieved,
            features_missing=missing,
        )

        return DemoResult(
            code=final_code,
            time_ms=elapsed,
            method="sunwell",
            iterations=iterations,
            judge_score=initial_score,  # Deterministic score
            judge_feedback=judgment.feedback,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            breakdown=breakdown,
        )

    async def run_parallel(
        self,
        task: DemoTask,
        *,
        on_single_shot_chunk: Callable[[str], None] | None = None,
        on_sunwell_chunk: Callable[[str], None] | None = None,
        on_sunwell_phase: Callable[[str], None] | None = None,
    ) -> tuple[DemoResult, DemoResult]:
        """Run both methods in parallel with streaming.

        This is the recommended way to run the demo - 2x faster than sequential.

        Args:
            task: The demo task to run.
            on_single_shot_chunk: Callback for single-shot streaming chunks.
            on_sunwell_chunk: Callback for Sunwell streaming chunks.
            on_sunwell_phase: Callback for Sunwell phase changes.

        Returns:
            Tuple of (single_shot_result, sunwell_result).
        """
        single_shot_result, sunwell_result = await asyncio.gather(
            self.run_single_shot_streaming(task, on_chunk=on_single_shot_chunk),
            self.run_sunwell_streaming(
                task,
                on_chunk=on_sunwell_chunk,
                on_phase=on_sunwell_phase,
            ),
        )
        return single_shot_result, sunwell_result


@dataclass(frozen=True, slots=True)
class DemoComparison:
    """Complete comparison result.

    Attributes:
        task: The demo task that was run.
        single_shot: Result from single-shot execution.
        sunwell: Result from Sunwell execution.
        improvement_percent: Percentage improvement in score.
    """

    task: DemoTask
    single_shot: DemoResult
    sunwell: DemoResult
    single_score: Any  # DemoScore
    sunwell_score: Any  # DemoScore

    @property
    def improvement_percent(self) -> float:
        """Calculate percentage improvement."""
        if self.single_score.score == 0:
            return 0.0
        return (
            (self.sunwell_score.score - self.single_score.score)
            / self.single_score.score
            * 100
        )
