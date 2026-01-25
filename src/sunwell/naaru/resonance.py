"""Resonance - Feedback Loop for Iterative Refinement.

The Resonance component implements a feedback loop that refines rejected proposals
based on judge feedback. This is key to quality improvement with local models.

Architecture:
```
    Proposal
        │
        ▼
    ┌─────────────┐
    │   Judge     │
    └──────┬──────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
 [Approved]   [Rejected]
                  │
                  ▼
           ┌──────────────┐
           │  Resonance   │
           │  (Feedback)  │
           └──────┬───────┘
                  │
                  ▼
           [Refined Proposal]
                  │
                  ▼
            Back to Judge
            (max N attempts)
```

The name "Resonance" comes from the Naaru lore - they resonate with power,
amplifying and refining through harmonics.

Example:
    >>> from sunwell.naaru.resonance import Resonance, ResonanceConfig
    >>> resonance = Resonance(model=my_model, config=ResonanceConfig(max_attempts=2))
    >>> refined = await resonance.refine(proposal, rejection)
"""


import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GenerativeModel(Protocol):
    """Protocol for models that can generate text."""

    async def generate(self, prompt: str, **kwargs) -> Any:
        """Generate text from a prompt."""
        ...


@dataclass(frozen=True, slots=True)
class ResonanceConfig:
    """Configuration for the Resonance feedback loop.

    Attributes:
        max_attempts: Maximum refinement attempts before final rejection (default: 2)
        temperature_boost: Temperature increase for creative refinement (default: 0.1)
        max_tokens: Maximum tokens for refined output (default: 768)
        feedback_format: How to format feedback for the model
        preserve_working_code: Don't refine if original code is syntactically correct
    """

    max_attempts: int = 2
    temperature_boost: float = 0.1
    max_tokens: int = 768
    feedback_format: str = "bullet"  # "bullet" | "prose" | "structured"
    preserve_working_code: bool = False


@dataclass(frozen=True, slots=True)
class RefinementAttempt:
    """Record of a single refinement attempt."""

    attempt_number: int
    original_proposal_id: str
    refined_proposal_id: str
    feedback_used: tuple[str, ...]
    tokens_used: int = 0
    success: bool = False


@dataclass(frozen=True, slots=True)
class ResonanceResult:
    """Result from a resonance refinement session."""

    refined_code: str
    refined_proposal_id: str
    original_proposal_id: str
    attempts: tuple[RefinementAttempt, ...]
    total_tokens: int
    success: bool
    final_feedback: str = ""


@dataclass(slots=True)
class Resonance:
    """Feedback loop that refines rejected proposals.

    The Resonance component takes rejected proposals and judge feedback,
    then generates improved versions that address the specific issues.

    Like the Naaru's resonance, it amplifies quality through iteration.

    Example:
        >>> resonance = Resonance(model=llm, config=ResonanceConfig(max_attempts=2))
        >>>
        >>> # After a rejection from the judge
        >>> result = await resonance.refine(
        ...     proposal={"diff": "def foo(): pass", "proposal_id": "abc123"},
        ...     rejection={"issues": ["No docstring", "Missing type hints"]},
        ... )
        >>>
        >>> if result.success:
        ...     print(f"Refined in {len(result.attempts)} attempts")
        ...     print(result.refined_code)
    """

    model: Any  # GenerativeModel
    config: ResonanceConfig = field(default_factory=ResonanceConfig)

    # Statistics
    _stats: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._stats = {
            "refinements_attempted": 0,
            "refinements_successful": 0,
            "total_tokens": 0,
            "avg_attempts_to_success": 0.0,
        }

    async def refine(
        self,
        proposal: dict,
        rejection: dict,
        attempt: int = 1,
    ) -> ResonanceResult:
        """Refine a rejected proposal based on feedback.

        Args:
            proposal: The rejected proposal dict with 'diff' and 'proposal_id'
            rejection: The rejection dict with 'issues', 'feedback', 'score'
            attempt: Current attempt number (for recursive calls)

        Returns:
            ResonanceResult with the refined code and metadata
        """
        original_code = proposal.get("diff", proposal.get("code", ""))
        original_id = proposal.get("proposal_id", f"unknown_{uuid.uuid4().hex[:8]}")

        # Extract feedback
        issues = rejection.get("issues", [])
        feedback = rejection.get("feedback", rejection.get("reason", ""))
        rejection.get("score", 0.0)
        category = proposal.get("summary", {}).get("category", "code_quality")

        # Track attempts
        attempts: list[RefinementAttempt] = []
        current_code = original_code
        current_id = original_id
        total_tokens = 0

        for attempt_num in range(1, self.config.max_attempts + 1):
            self._stats["refinements_attempted"] += 1

            # Build refinement prompt
            prompt = self._build_refinement_prompt(
                code=current_code,
                issues=issues,
                feedback=feedback,
                category=category,
                attempt=attempt_num,
            )

            try:
                # Generate refined code
                from sunwell.models.protocol import GenerateOptions

                temperature = min(0.3 + (self.config.temperature_boost * attempt_num), 0.7)

                result = await self.model.generate(
                    prompt,
                    options=GenerateOptions(
                        temperature=temperature,
                        max_tokens=self.config.max_tokens,
                    ),
                )

                refined_code = result.content or ""
                tokens_used = result.usage.total_tokens if result.usage else 0
                total_tokens += tokens_used

                # Create new proposal ID
                refined_id = f"{original_id}_r{attempt_num}"

                # Record attempt
                attempt_record = RefinementAttempt(
                    attempt_number=attempt_num,
                    original_proposal_id=current_id,
                    refined_proposal_id=refined_id,
                    feedback_used=issues[:5] if issues else [feedback[:100]],
                    tokens_used=tokens_used,
                    success=True,  # We got a response
                )
                attempts.append(attempt_record)

                # Update for next iteration if needed
                current_code = refined_code
                current_id = refined_id

            except Exception:
                attempt_record = RefinementAttempt(
                    attempt_number=attempt_num,
                    original_proposal_id=current_id,
                    refined_proposal_id=f"{original_id}_r{attempt_num}_failed",
                    feedback_used=issues[:5] if issues else [feedback[:100]],
                    tokens_used=0,
                    success=False,
                )
                attempts.append(attempt_record)

                # Don't continue if generation failed
                break

        # Update stats
        self._stats["total_tokens"] += total_tokens
        if attempts and attempts[-1].success:
            self._stats["refinements_successful"] += 1

        return ResonanceResult(
            refined_code=current_code,
            refined_proposal_id=current_id,
            original_proposal_id=original_id,
            attempts=attempts,
            total_tokens=total_tokens,
            success=len(attempts) > 0 and attempts[-1].success,
            final_feedback=f"Refined {len(attempts)} times. Issues addressed: {', '.join(issues[:3])}",
        )

    def _build_refinement_prompt(
        self,
        code: str,
        issues: list[str],
        feedback: str,
        category: str,
        attempt: int,
    ) -> str:
        """Build the refinement prompt based on configuration."""

        # Format issues based on config
        if self.config.feedback_format == "bullet":
            issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else feedback
        elif self.config.feedback_format == "structured":
            issues_text = "ISSUES:\n" + "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues))
            if feedback:
                issues_text += f"\n\nJUDGE FEEDBACK:\n{feedback}"
        else:  # prose
            issues_text = ". ".join(issues) if issues else feedback

        # Category-specific guidance
        category_guidance = {
            "error_handling": "Ensure all exceptions are caught with specific types, include helpful error messages, and handle cleanup.",
            "testing": "Write comprehensive tests covering edge cases, use pytest fixtures, and include assertions for all behaviors.",
            "documentation": "Include complete docstrings with Args, Returns, Raises sections and usage examples.",
            "code_quality": "Follow PEP 8, use type hints, write Pythonic code with clear variable names.",
        }

        guidance = category_guidance.get(category, "Write clean, correct, production-ready code.")

        # Build prompt
        prompt = f"""The following code was rejected by quality review. This is refinement attempt {attempt}/{self.config.max_attempts}.

ORIGINAL CODE:
```python
{code}
```

ISSUES TO FIX:
{issues_text}

GUIDANCE FOR {category.upper()}:
{guidance}

Write an IMPROVED version that fixes ALL the issues above.
Keep the same core functionality but address every quality concern.

Requirements:
1. Fix every issue listed above
2. Maintain the original intent
3. Follow Python best practices
4. Include docstrings and type hints

Code only, no explanations:"""

        return prompt

    async def refine_with_validation(
        self,
        proposal: dict,
        rejection: dict,
        validator: Any,
    ) -> tuple[ResonanceResult, dict | None]:
        """Refine and validate in a loop until success or max attempts.

        This is the full feedback loop:
        1. Refine the proposal
        2. Validate the refined proposal
        3. If rejected, refine again with new feedback
        4. Repeat until approved or max attempts reached

        Args:
            proposal: The original rejected proposal
            rejection: The initial rejection with feedback
            validator: Validator with a validate(proposal) method

        Returns:
            Tuple of (ResonanceResult, final_validation_result or None)
        """
        current_proposal = proposal
        current_rejection = rejection
        all_attempts = []
        total_tokens = 0

        for loop_num in range(self.config.max_attempts):
            # Refine based on current feedback
            result = await self.refine(
                proposal=current_proposal,
                rejection=current_rejection,
                attempt=1,  # Single attempt per loop
            )

            all_attempts.extend(result.attempts)
            total_tokens += result.total_tokens

            if not result.success:
                break

            # Create proposal from refined code
            refined_proposal = {
                **proposal,
                "diff": result.refined_code,
                "proposal_id": result.refined_proposal_id,
                "refinement_attempt": loop_num + 1,
            }

            # Validate
            validation = await validator.validate(refined_proposal)

            if validation.get("valid", False) or validation.score >= 6.0:
                # Success!
                return (
                    ResonanceResult(
                        refined_code=result.refined_code,
                        refined_proposal_id=result.refined_proposal_id,
                        original_proposal_id=proposal.get("proposal_id", "unknown"),
                        attempts=all_attempts,
                        total_tokens=total_tokens,
                        success=True,
                        final_feedback="Approved after refinement",
                    ),
                    validation,
                )

            # Update for next loop
            current_proposal = refined_proposal
            current_rejection = {
                "issues": validation.get("issues", []),
                "feedback": validation.get("reason", ""),
                "score": validation.get("score", 0),
            }

        # Max attempts reached without approval
        return (
            ResonanceResult(
                refined_code=result.refined_code if result else proposal.get("diff", ""),
                refined_proposal_id=result.refined_proposal_id if result else proposal.get("proposal_id", ""),
                original_proposal_id=proposal.get("proposal_id", "unknown"),
                attempts=all_attempts,
                total_tokens=total_tokens,
                success=False,
                final_feedback="Max refinement attempts reached",
            ),
            None,
        )

    def get_stats(self) -> dict:
        """Get resonance statistics."""
        stats = dict(self._stats)

        if stats["refinements_successful"] > 0:
            # Calculate average attempts to success (simplified)
            stats["success_rate"] = stats["refinements_successful"] / max(1, stats["refinements_attempted"])
        else:
            stats["success_rate"] = 0.0

        return stats


# =============================================================================
# Integration with Naaru
# =============================================================================


async def create_resonance_handler(
    model: Any,
    config: ResonanceConfig | None = None,
) -> Resonance:
    """Create a Resonance handler for use with Naaru.

    Example:
        >>> resonance = await create_resonance_handler(
        ...     model=OllamaModel("gemma3:1b"),
        ...     config=ResonanceConfig(max_attempts=2),
        ... )
    """
    return Resonance(
        model=model,
        config=config or ResonanceConfig(),
    )


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate the Resonance feedback loop."""
    print("=" * 60)
    print("Resonance Feedback Loop Demo")
    print("=" * 60)

    # Mock model for demo
    class MockModel:
        async def generate(self, prompt, options=None):
            class MockResult:
                content = '''def example(x: int) -> int:
    """Example function with proper docstring.

    Args:
        x: Input value

    Returns:
        Doubled input value
    """
    if x is None:
        raise ValueError("x cannot be None")
    return x * 2'''

                class usage:
                    total_tokens = 100

            return MockResult()

    resonance = Resonance(
        model=MockModel(),
        config=ResonanceConfig(max_attempts=2),
    )

    # Simulate a rejection
    proposal = {
        "proposal_id": "test_001",
        "diff": "def example(x): return x * 2",
        "summary": {"category": "code_quality"},
    }

    rejection = {
        "issues": [
            "Missing docstring",
            "No type hints",
            "No error handling for None input",
        ],
        "feedback": "Code quality too low",
        "score": 4.0,
    }

    print("\n📋 Original Proposal:")
    print(f"   ID: {proposal['proposal_id']}")
    print(f"   Code: {proposal['diff']}")

    print("\n❌ Rejection:")
    print(f"   Score: {rejection['score']}/10")
    print(f"   Issues: {', '.join(rejection['issues'])}")

    # Refine
    result = await resonance.refine(proposal, rejection)

    print("\n✨ Resonance Result:")
    print(f"   Success: {result.success}")
    print(f"   Attempts: {len(result.attempts)}")
    print(f"   Tokens used: {result.total_tokens}")
    print(f"   New ID: {result.refined_proposal_id}")
    print("\n📝 Refined Code:")
    print(result.refined_code)

    print("\n📊 Stats:")
    stats = resonance.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
