"""Unified Naaru Pipeline - Composable Multi-Perspective Intelligence (RFC-033).

This module implements the unified architecture that composes three layers:
1. Diversity Layer - Generate multiple perspectives
2. Selection Layer - Choose the best candidate
3. Refinement Layer - Optionally improve the result

Each layer offers multiple strategies with different cost/quality tradeoffs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from sunwell.naaru.diversity import (
    Candidate,
    diversity_harmonic,
    diversity_none,
    diversity_rotation,
    diversity_sampling,
)
from sunwell.naaru.refinement import (
    RefinementResult,
    refine_full,
    refine_none,
    refine_tiered,
)
from sunwell.naaru.selection import (
    select_heuristic,
    select_judge,
    select_passthrough,
    select_voting,
)

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.types.config import NaaruConfig


@dataclass(frozen=True, slots=True)
class TaskAnalysis:
    """Analysis of a task to inform strategy selection."""
    
    is_deterministic: bool
    """Has clear "correct" answer."""
    
    is_creative: bool
    """Benefits from diverse perspectives."""
    
    is_high_stakes: bool
    """Errors are costly."""
    
    complexity: Literal["simple", "moderate", "complex"]
    """Task complexity level."""
    
    @classmethod
    async def analyze(
        cls,
        task: str,
        model: ModelProtocol | None = None,
    ) -> TaskAnalysis:
        """Analyze task to inform strategy selection.
        
        Uses a lightweight model (defaults to router model if available,
        otherwise falls back to keyword-based classification).
        
        Args:
            task: The task description
            model: Optional model for LLM-based analysis
            
        Returns:
            TaskAnalysis with task characteristics
        """
        if model is None:
            # Fallback to keyword-based classification
            return cls._classify_by_keywords(task)
        
        # Use tiny model to classify task
        try:
            result = await model.generate(
                f"""Classify this task:
TASK: {task[:500]}

OUTPUT (JSON):
{{"deterministic": true/false, "creative": true/false, "high_stakes": true/false, "complexity": "simple/moderate/complex"}}
""",
            )
            
            import json
            import re
            
            text = result.text.strip()
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return cls(
                    is_deterministic=bool(data.get("deterministic", False)),
                    is_creative=bool(data.get("creative", False)),
                    is_high_stakes=bool(data.get("high_stakes", False)),
                    complexity=data.get("complexity", "moderate"),
                )
        except Exception:
            # Fallback to keyword classification on error
            pass
        
        return cls._classify_by_keywords(task)
    
    @classmethod
    def _classify_by_keywords(cls, task: str) -> TaskAnalysis:
        """Fallback keyword-based classification."""
        task_lower = task.lower()
        
        is_deterministic = (
            "correct" in task_lower
            or "validate" in task_lower
            or "check" in task_lower
            or "verify" in task_lower
        )
        
        is_creative = (
            "creative" in task_lower
            or "write" in task_lower
            or "design" in task_lower
            or "brainstorm" in task_lower
        )
        
        is_high_stakes = (
            "security" in task_lower
            or "critical" in task_lower
            or "production" in task_lower
            or "important" in task_lower
        )
        
        word_count = len(task.split())
        if word_count > 100:
            complexity = "complex"
        elif word_count > 50:
            complexity = "moderate"
        else:
            complexity = "simple"
        
        return cls(
            is_deterministic=is_deterministic,
            is_creative=is_creative,
            is_high_stakes=is_high_stakes,
            complexity=complexity,
        )


def select_strategies(
    analysis: TaskAnalysis,
    budget: str,
) -> tuple[str, str, str]:
    """Select diversity, selection, and refinement strategies.
    
    Args:
        analysis: Task analysis
        budget: Cost budget ("minimal", "normal", "quality")
        
    Returns:
        Tuple of (diversity_strategy, selection_strategy, refinement_strategy)
    """
    # Budget overrides
    if budget == "minimal":
        return ("none", "passthrough", "none")
    
    if budget == "quality":
        return ("harmonic", "voting", "full")
    
    # Task-based selection (normal budget)
    if analysis.is_deterministic and analysis.complexity == "simple":
        return ("none", "passthrough", "none")
    
    if analysis.is_creative:
        if analysis.is_high_stakes:
            return ("harmonic", "voting", "tiered")
        else:
            return ("sampling", "heuristic", "none")
    
    if analysis.is_high_stakes:
        return ("rotation", "passthrough", "full")
    
    # Default: cheap diversity
    return ("sampling", "heuristic", "tiered")


@dataclass(frozen=True, slots=True)
class UnifiedResult:
    """Result from unified Naaru pipeline."""
    
    text: str
    """Final output text."""
    
    diversity_strategy: str
    """Diversity strategy used."""
    
    selection_strategy: str
    """Selection strategy used."""
    
    refinement_strategy: str
    """Refinement strategy used."""
    
    candidates: list[Candidate]
    """All candidates from diversity layer."""
    
    selected: Candidate
    """Selected candidate."""
    
    refinement: RefinementResult
    """Refinement result."""
    
    total_tokens: int
    """Total tokens used."""
    
    task_analysis: TaskAnalysis | None = None
    """Task analysis (if auto mode was used)."""


async def unified_pipeline(
    model: ModelProtocol,
    prompt: str,
    config: NaaruConfig,
    judge_model: ModelProtocol | None = None,
    task_type: str | None = None,
) -> UnifiedResult:
    """Execute unified Naaru pipeline with three composable layers.
    
    Args:
        model: Model for generation
        prompt: Input prompt
        config: Naaru configuration
        judge_model: Model for judging (if None, uses model)
        task_type: Task type hint ("code", "creative", "analysis", "auto")
        
    Returns:
        UnifiedResult with final output and metadata
    """
    if judge_model is None:
        judge_model = model
    
    # Determine strategies (auto mode or explicit)
    diversity_strategy = config.diversity
    selection_strategy = config.selection
    refinement_strategy = config.refinement
    
    task_analysis: TaskAnalysis | None = None
    
    # Auto mode: analyze task and select strategies
    if (
        diversity_strategy == "auto"
        or selection_strategy == "auto"
        or refinement_strategy == "auto"
    ):
        task_analysis = await TaskAnalysis.analyze(prompt, model)
        auto_diversity, auto_selection, auto_refinement = select_strategies(
            task_analysis, config.cost_budget
        )
        
        if diversity_strategy == "auto":
            diversity_strategy = auto_diversity
        if selection_strategy == "auto":
            selection_strategy = auto_selection
        if refinement_strategy == "auto":
            refinement_strategy = auto_refinement
    
    # Layer 1: Diversity
    candidates: list[Candidate]
    
    if diversity_strategy == "none":
        candidates = await diversity_none(model, prompt)
    elif diversity_strategy == "sampling":
        temps = config.diversity_temps[: config.diversity_count]
        candidates = await diversity_sampling(model, prompt, temps=temps)
    elif diversity_strategy == "rotation":
        candidates = await diversity_rotation(model, prompt)
    elif diversity_strategy == "harmonic":
        candidates = await diversity_harmonic(model, prompt)
    else:
        raise ValueError(f"Unknown diversity strategy: {diversity_strategy}")
    
    # Layer 2: Selection
    selected: Candidate
    
    if selection_strategy == "passthrough":
        selected = select_passthrough(candidates)
    elif selection_strategy == "heuristic":
        task_type_hint = task_type or config.task_type
        if task_type_hint == "auto":
            if task_analysis:
                # Infer from analysis
                if task_analysis.is_creative:
                    task_type_hint = "creative"
                elif "code" in prompt.lower():
                    task_type_hint = "code"
                else:
                    task_type_hint = "analysis"
            else:
                # Fallback: infer from prompt
                prompt_lower = prompt.lower()
                if "code" in prompt_lower or "function" in prompt_lower or "class" in prompt_lower:
                    task_type_hint = "code"
                elif "write" in prompt_lower or "creative" in prompt_lower:
                    task_type_hint = "creative"
                else:
                    task_type_hint = "general"
        selected = select_heuristic(candidates, task_type_hint)
    elif selection_strategy == "voting":
        selected = await select_voting(model, candidates, prompt)
    elif selection_strategy == "judge":
        selected = await select_judge(judge_model, candidates)
    else:
        raise ValueError(f"Unknown selection strategy: {selection_strategy}")
    
    # Layer 3: Refinement
    refinement: RefinementResult
    
    if refinement_strategy == "none":
        refinement = await refine_none(selected, prompt)
    elif refinement_strategy == "tiered":
        refinement = await refine_tiered(
            selected, prompt, model, judge_model, config.purity_threshold
        )
    elif refinement_strategy == "full":
        refinement = await refine_full(
            selected,
            prompt,
            model,
            judge_model,
            config.refinement_max_attempts,
            config.purity_threshold,
        )
    else:
        raise ValueError(f"Unknown refinement strategy: {refinement_strategy}")
    
    # Calculate total tokens
    total_tokens = sum(c.tokens for c in candidates) + refinement.tokens
    
    return UnifiedResult(
        text=refinement.text,
        diversity_strategy=diversity_strategy,
        selection_strategy=selection_strategy,
        refinement_strategy=refinement_strategy,
        candidates=candidates,
        selected=selected,
        refinement=refinement,
        total_tokens=total_tokens,
        task_analysis=task_analysis,
    )


# Preset configurations (RFC-033)
def create_minimal_config() -> NaaruConfig:
    """Minimal cost: single generation, no frills."""
    from sunwell.types.config import NaaruConfig
    
    return NaaruConfig(
        diversity="none",
        selection="passthrough",
        refinement="none",
        cost_budget="minimal",
    )


def create_cheap_diversity_config() -> NaaruConfig:
    """Cheap diversity: sampling + heuristic."""
    from sunwell.types.config import NaaruConfig
    
    return NaaruConfig(
        diversity="sampling",
        selection="heuristic",
        refinement="none",
        cost_budget="normal",
    )


def create_balanced_config() -> NaaruConfig:
    """Balanced: rotation + heuristic + tiered."""
    from sunwell.types.config import NaaruConfig
    
    return NaaruConfig(
        diversity="rotation",
        selection="passthrough",  # Rotation integrates perspectives
        refinement="tiered",
        cost_budget="normal",
    )


def create_quality_config() -> NaaruConfig:
    """Quality: harmonic + voting + full."""
    from sunwell.types.config import NaaruConfig
    
    return NaaruConfig(
        diversity="harmonic",
        selection="voting",
        refinement="full",
        cost_budget="quality",
    )


def create_auto_config() -> NaaruConfig:
    """Auto: Naaru decides everything."""
    from sunwell.types.config import NaaruConfig
    
    return NaaruConfig(
        diversity="auto",
        selection="auto",
        refinement="auto",
        cost_budget="normal",
    )
