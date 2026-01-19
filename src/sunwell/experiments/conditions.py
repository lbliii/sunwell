"""Vortex Conditions — Adaptive Primitive Selection.

The hypothesis: Like storms that strengthen in warm water and weaken
over land, the vortex should adapt based on sensed conditions.

Favorable conditions (amplify vortex):
- Medium difficulty (not trivial, not impossible)
- Ambiguous inputs (multiple valid perspectives)
- Multi-step reasoning (benefits from decomposition)
- Model at edge of capability (primitives help most)

Unfavorable conditions (dampen/skip vortex):
- Trivial tasks (single model is fine)
- Pure factual lookups (no perspective needed)
- All perspectives fail equally (need bigger model, not more small ones)
- Very high agreement (consensus is clear, dialectic is waste)

This module provides:
1. Condition sensors (detect favorable/unfavorable)
2. Adaptive router (choose primitive combination)
3. Resource optimizer (minimize cost for expected quality)

Example:
    >>> from sunwell.experiments.conditions import (
    ...     sense_conditions,
    ...     adaptive_solve,
    ... )
    >>>
    >>> conditions = await sense_conditions(task, model)
    >>> print(f"Favorability: {conditions.favorability:.0%}")
    >>> print(f"Recommended: {conditions.recommended_primitives}")
    >>>
    >>> # Adaptive solve uses conditions automatically
    >>> result = await adaptive_solve(task, model)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Condition Types
# =============================================================================


class VortexIntensity(Enum):
    """How much vortex machinery to apply."""

    NONE = "none"              # Single model only
    LIGHT = "light"            # Quick interference check
    MODERATE = "moderate"      # Interference + maybe dialectic
    FULL = "full"              # Full vortex pipeline
    ESCALATE = "escalate"      # Need larger model, not more primitives


class ConditionType(Enum):
    """Types of conditions that affect vortex strength."""

    # Favorable (warm water)
    AMBIGUOUS = "ambiguous"          # Multiple valid interpretations
    MULTI_STEP = "multi_step"        # Benefits from decomposition
    EDGE_CAPABILITY = "edge"         # At model's capability boundary

    # Unfavorable (cold water)
    TRIVIAL = "trivial"              # Too easy
    IMPOSSIBLE = "impossible"        # Too hard for this model
    FACTUAL = "factual"              # Pure lookup, no reasoning
    CONSENSUS_CLEAR = "consensus"    # All perspectives agree


@dataclass(frozen=True, slots=True)
class VortexConditions:
    """Sensed conditions for adaptive vortex control."""

    task: str
    """The task being evaluated."""

    # Core metrics
    difficulty: float
    """Estimated difficulty (0.0 = trivial, 1.0 = impossible)."""

    ambiguity: float
    """How ambiguous/multi-perspective (0.0 = clear, 1.0 = very ambiguous)."""

    decomposability: float
    """How well it decomposes into subtasks (0.0 = atomic, 1.0 = highly decomposable)."""

    agreement: float
    """Initial agreement from quick interference probe (0.0 = none, 1.0 = consensus)."""

    # Derived
    favorability: float
    """Overall favorability for vortex (0.0 = skip, 1.0 = full vortex)."""

    recommended_intensity: VortexIntensity
    """Recommended vortex intensity."""

    recommended_primitives: tuple[str, ...]
    """Which primitives to use."""

    conditions_detected: tuple[ConditionType, ...]
    """Specific conditions that were detected."""

    reasoning: str
    """Explanation of the recommendation."""


@dataclass(frozen=True, slots=True)
class AdaptiveResult:
    """Result from adaptive vortex execution."""

    task: str
    response: str
    quality: float
    confidence: float

    # What was used
    intensity_used: VortexIntensity
    primitives_used: tuple[str, ...]
    conditions: VortexConditions

    # Cost
    model_calls: int
    latency_ms: float

    # Comparison to baseline
    would_single_model_work: bool
    efficiency_gain: float  # Quality per model call vs full vortex


# =============================================================================
# Condition Sensing
# =============================================================================


async def sense_conditions(
    task: str,
    model: ModelProtocol,
    quick_probe: bool = True,
) -> VortexConditions:
    """Sense conditions to determine vortex intensity.

    Args:
        task: The task to evaluate
        model: Model for probing
        quick_probe: If True, run minimal probes. If False, more thorough.

    Returns:
        VortexConditions with recommendations
    """
    # Parallel probes
    difficulty_task = _probe_difficulty(task, model)
    ambiguity_task = _probe_ambiguity(task, model)
    decomp_task = _probe_decomposability(task, model)

    if quick_probe:
        # Quick: Just check agreement with 2 perspectives
        agreement_task = _quick_agreement_probe(task, model)
    else:
        # Thorough: Full interference scan
        agreement_task = _full_agreement_probe(task, model)

    difficulty, ambiguity, decomp, agreement = await asyncio.gather(
        difficulty_task, ambiguity_task, decomp_task, agreement_task
    )

    # Detect specific conditions
    conditions = _detect_conditions(difficulty, ambiguity, decomp, agreement)

    # Calculate favorability and recommendation
    favorability, intensity, primitives, reasoning = _calculate_recommendation(
        difficulty, ambiguity, decomp, agreement, conditions
    )

    return VortexConditions(
        task=task,
        difficulty=difficulty,
        ambiguity=ambiguity,
        decomposability=decomp,
        agreement=agreement,
        favorability=favorability,
        recommended_intensity=intensity,
        recommended_primitives=primitives,
        conditions_detected=tuple(conditions),
        reasoning=reasoning,
    )


async def _probe_difficulty(task: str, model: ModelProtocol) -> float:
    """Probe task difficulty using model self-assessment."""
    prompt = f"""Rate the difficulty of this task for a small AI model.

Task: {task}

Rate 0.0 (trivial, any model can do it) to 1.0 (very hard, needs expert reasoning).
Consider: complexity, required knowledge, ambiguity.

Respond with ONLY a number between 0.0 and 1.0."""

    result = await model.generate(prompt)
    response = result.content if hasattr(result, "content") else str(result)

    return _extract_float(response, default=0.5)


async def _probe_ambiguity(task: str, model: ModelProtocol) -> float:
    """Probe how ambiguous/multi-perspective the task is."""
    prompt = f"""Does this task have multiple valid interpretations or perspectives?

Task: {task}

Rate 0.0 (single clear answer) to 1.0 (highly ambiguous, many valid views).
Consider: Is there room for debate? Could experts disagree?

Respond with ONLY a number between 0.0 and 1.0."""

    result = await model.generate(prompt)
    response = result.content if hasattr(result, "content") else str(result)

    return _extract_float(response, default=0.5)


async def _probe_decomposability(task: str, model: ModelProtocol) -> float:
    """Probe how well the task decomposes into subtasks."""
    prompt = f"""Can this task be broken into multiple subtasks?

Task: {task}

Rate 0.0 (atomic, single action) to 1.0 (clearly multi-step).
Consider: Are there distinct phases? Can parts be done independently?

Respond with ONLY a number between 0.0 and 1.0."""

    result = await model.generate(prompt)
    response = result.content if hasattr(result, "content") else str(result)

    return _extract_float(response, default=0.5)


async def _quick_agreement_probe(task: str, model: ModelProtocol) -> float:
    """Quick probe: Run 2 perspectives and check agreement."""
    perspectives = [
        f"As a careful analyst: {task}",
        f"As a skeptic looking for issues: {task}",
    ]

    results = await asyncio.gather(*[
        model.generate(p) for p in perspectives
    ])

    responses = [
        r.content if hasattr(r, "content") else str(r)
        for r in results
    ]

    # Simple similarity check
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, responses[0].lower(), responses[1].lower()).ratio()

    return similarity


async def _full_agreement_probe(task: str, model: ModelProtocol) -> float:
    """Full probe: Run interference scan."""
    from sunwell.experiments.interference import interference_scan

    result = await interference_scan(task, model, n_perspectives=3)
    return result.agreement_score


def _detect_conditions(
    difficulty: float,
    ambiguity: float,
    decomp: float,
    agreement: float,
) -> list[ConditionType]:
    """Detect specific conditions from metrics."""
    conditions = []

    # Favorable conditions
    if ambiguity > 0.6:
        conditions.append(ConditionType.AMBIGUOUS)
    if decomp > 0.6:
        conditions.append(ConditionType.MULTI_STEP)
    if 0.3 < difficulty < 0.7:
        conditions.append(ConditionType.EDGE_CAPABILITY)

    # Unfavorable conditions
    if difficulty < 0.2:
        conditions.append(ConditionType.TRIVIAL)
    if difficulty > 0.9:
        conditions.append(ConditionType.IMPOSSIBLE)
    if ambiguity < 0.2 and decomp < 0.2:
        conditions.append(ConditionType.FACTUAL)
    if agreement > 0.8:
        conditions.append(ConditionType.CONSENSUS_CLEAR)

    return conditions


def _calculate_recommendation(
    difficulty: float,
    ambiguity: float,
    decomp: float,
    agreement: float,
    conditions: list[ConditionType],
) -> tuple[float, VortexIntensity, tuple[str, ...], str]:
    """Calculate favorability and recommendations."""

    # Check for clear unfavorable conditions first
    if ConditionType.TRIVIAL in conditions:
        return (
            0.1,
            VortexIntensity.NONE,
            ("single_model",),
            "Task is trivial - single model sufficient, vortex is wasteful",
        )

    if ConditionType.IMPOSSIBLE in conditions:
        return (
            0.1,
            VortexIntensity.ESCALATE,
            ("escalate_to_larger_model",),
            "Task exceeds model capability - need larger model, not more primitives",
        )

    if ConditionType.CONSENSUS_CLEAR in conditions and ConditionType.FACTUAL in conditions:
        return (
            0.2,
            VortexIntensity.NONE,
            ("single_model",),
            "Clear factual answer with high agreement - vortex unnecessary",
        )

    # Calculate favorability for favorable conditions
    favorability = 0.5  # Base
    primitives = ["single_model"]
    reasons = []

    # Ambiguity increases favorability (dialectic helps)
    if ambiguity > 0.4:
        favorability += 0.2
        primitives.append("dialectic")
        reasons.append("ambiguity benefits from thesis/antithesis")

    # Low agreement increases favorability (interference is informative)
    if agreement < 0.6:
        favorability += 0.2
        primitives.append("interference")
        reasons.append("low agreement indicates uncertainty")

    # Decomposability increases favorability (gradient helps)
    if decomp > 0.5:
        favorability += 0.15
        primitives.append("gradient")
        reasons.append("multi-step benefits from decomposition")

    # Edge capability is the sweet spot
    if ConditionType.EDGE_CAPABILITY in conditions:
        favorability += 0.15
        reasons.append("at capability edge - primitives help most here")

    # Determine intensity
    if favorability < 0.3:
        intensity = VortexIntensity.NONE
    elif favorability < 0.5:
        intensity = VortexIntensity.LIGHT
    elif favorability < 0.7:
        intensity = VortexIntensity.MODERATE
    else:
        intensity = VortexIntensity.FULL

    reasoning = "; ".join(reasons) if reasons else "moderate conditions"

    return favorability, intensity, tuple(primitives), reasoning


def _extract_float(response: str, default: float = 0.5) -> float:
    """Extract a float from model response."""
    import re

    # Find first float in response
    match = re.search(r"(\d+\.?\d*)", response)
    if match:
        try:
            value = float(match.group(1))
            return min(1.0, max(0.0, value))
        except ValueError:
            pass

    return default


# =============================================================================
# Adaptive Execution
# =============================================================================


async def adaptive_solve(
    task: str,
    model: ModelProtocol,
    force_intensity: VortexIntensity | None = None,
) -> AdaptiveResult:
    """Solve task with adaptive vortex intensity.

    Senses conditions and applies appropriate level of vortex machinery.

    Args:
        task: The task to solve
        model: Model to use
        force_intensity: Override sensed conditions (for testing)

    Returns:
        AdaptiveResult with response and metadata
    """
    from sunwell.experiments.dialectic import dialectic_decide
    from sunwell.experiments.interference import interference_scan, should_escalate

    start = time.perf_counter()
    model_calls = 0

    # Sense conditions (4 model calls for probing)
    conditions = await sense_conditions(task, model, quick_probe=True)
    model_calls += 4

    intensity = force_intensity or conditions.recommended_intensity
    primitives_used = []

    # Execute based on intensity
    if intensity == VortexIntensity.NONE:
        # Single model only
        result = await model.generate(task)
        response = result.content if hasattr(result, "content") else str(result)
        model_calls += 1
        primitives_used = ["single_model"]
        confidence = 0.7  # Default confidence for single model

    elif intensity == VortexIntensity.LIGHT:
        # Quick interference check
        interference = await interference_scan(task, model, n_perspectives=3)
        model_calls += 3
        response = interference.consensus_answer or ""
        confidence = interference.agreement_score
        primitives_used = ["interference"]

    elif intensity == VortexIntensity.MODERATE:
        # Interference + conditional dialectic
        interference = await interference_scan(task, model, n_perspectives=3)
        model_calls += 3
        primitives_used = ["interference"]

        if should_escalate(interference, threshold=0.6):
            dialectic = await dialectic_decide(task, model=model)
            model_calls += 3  # thesis, antithesis, synthesis
            response = dialectic.synthesis
            confidence = 0.8
            primitives_used.append("dialectic")
        else:
            response = interference.consensus_answer or ""
            confidence = interference.agreement_score

    elif intensity == VortexIntensity.FULL:
        # Full vortex pipeline
        from sunwell.experiments.vortex import _run_vortex

        # Use internal vortex function
        vortex_result = await _run_vortex(task, model, model)
        response = vortex_result.response
        confidence = vortex_result.confidence
        model_calls += 15  # Approximate
        primitives_used = ["interference", "dialectic", "gradient", "resonance"]

    else:  # ESCALATE
        # Return with escalation recommendation
        result = await model.generate(task)
        response = result.content if hasattr(result, "content") else str(result)
        model_calls += 1
        response = f"[ESCALATION RECOMMENDED]\n\n{response}"
        confidence = 0.3
        primitives_used = ["single_model", "escalation_flag"]

    latency = (time.perf_counter() - start) * 1000

    # Calculate efficiency
    # Would single model have worked? (heuristic: high agreement + not trivial)
    would_single_work = (
        conditions.agreement > 0.8 and
        conditions.difficulty < 0.5
    )

    # Efficiency = quality per model call
    baseline_calls = 1  # Single model
    if intensity == VortexIntensity.NONE:
        efficiency_gain = 1.0  # Same as baseline
    else:
        # Higher quality but more calls
        quality_ratio = confidence / 0.7  # vs baseline confidence
        call_ratio = baseline_calls / model_calls
        efficiency_gain = quality_ratio * call_ratio

    return AdaptiveResult(
        task=task,
        response=response,
        quality=confidence,  # Using confidence as quality proxy
        confidence=confidence,
        intensity_used=intensity,
        primitives_used=tuple(primitives_used),
        conditions=conditions,
        model_calls=model_calls,
        latency_ms=latency,
        would_single_model_work=would_single_work,
        efficiency_gain=efficiency_gain,
    )


# =============================================================================
# Condition Monitoring (Real-time)
# =============================================================================


@dataclass
class ConditionMonitor:
    """Real-time monitoring of vortex conditions.

    Like weather monitoring for storm prediction.
    Tracks metrics over time to detect condition changes.
    """

    history: list[VortexConditions] = field(default_factory=list)
    """Historical condition readings."""

    window_size: int = 10
    """Number of recent readings to consider."""

    def record(self, conditions: VortexConditions) -> None:
        """Record new condition reading."""
        self.history.append(conditions)
        # Keep only recent history
        if len(self.history) > self.window_size * 2:
            self.history = self.history[-self.window_size:]

    def trend(self) -> dict[str, float]:
        """Calculate trends in conditions."""
        if len(self.history) < 2:
            return {"favorability": 0.0, "difficulty": 0.0, "agreement": 0.0}

        recent = self.history[-self.window_size:]

        # Calculate slopes
        fav_trend = recent[-1].favorability - recent[0].favorability
        diff_trend = recent[-1].difficulty - recent[0].difficulty
        agree_trend = recent[-1].agreement - recent[0].agreement

        return {
            "favorability": fav_trend / len(recent),
            "difficulty": diff_trend / len(recent),
            "agreement": agree_trend / len(recent),
        }

    def is_strengthening(self) -> bool:
        """Are conditions becoming more favorable for vortex?"""
        trends = self.trend()
        return trends["favorability"] > 0.05

    def is_weakening(self) -> bool:
        """Are conditions becoming less favorable?"""
        trends = self.trend()
        return trends["favorability"] < -0.05

    def recommended_adjustment(self) -> str:
        """Recommend intensity adjustment based on trends."""
        if self.is_strengthening():
            return "increase_intensity"
        elif self.is_weakening():
            return "decrease_intensity"
        else:
            return "maintain"


# =============================================================================
# Utility Functions
# =============================================================================


def format_conditions_report(conditions: VortexConditions) -> str:
    """Format conditions as human-readable report."""
    intensity_emoji = {
        VortexIntensity.NONE: "💤",
        VortexIntensity.LIGHT: "🌤️",
        VortexIntensity.MODERATE: "⛅",
        VortexIntensity.FULL: "🌀",
        VortexIntensity.ESCALATE: "⚠️",
    }

    lines = [
        f"Task: {conditions.task[:60]}...",
        "",
        "=== SENSED CONDITIONS ===",
        f"Difficulty:      {conditions.difficulty:.0%}",
        f"Ambiguity:       {conditions.ambiguity:.0%}",
        f"Decomposability: {conditions.decomposability:.0%}",
        f"Agreement:       {conditions.agreement:.0%}",
        "",
        "=== DETECTED CONDITIONS ===",
    ]

    for cond in conditions.conditions_detected:
        lines.append(f"  • {cond.value}")

    emoji = intensity_emoji.get(conditions.recommended_intensity, "")

    lines.extend([
        "",
        "=== RECOMMENDATION ===",
        f"Favorability: {conditions.favorability:.0%}",
        f"Intensity:    {emoji} {conditions.recommended_intensity.value.upper()}",
        f"Primitives:   {', '.join(conditions.recommended_primitives)}",
        "",
        f"Reasoning: {conditions.reasoning}",
    ])

    return "\n".join(lines)


def format_adaptive_report(result: AdaptiveResult) -> str:
    """Format adaptive result as human-readable report."""
    lines = [
        f"Task: {result.task[:60]}...",
        "",
        "=== EXECUTION ===",
        f"Intensity: {result.intensity_used.value}",
        f"Primitives: {', '.join(result.primitives_used)}",
        f"Model calls: {result.model_calls}",
        f"Latency: {result.latency_ms:.0f}ms",
        "",
        "=== QUALITY ===",
        f"Confidence: {result.confidence:.0%}",
        f"Would single model work: {'Yes' if result.would_single_model_work else 'No'}",
        f"Efficiency gain: {result.efficiency_gain:.2f}x",
        "",
        "=== RESPONSE ===",
        f"{result.response[:300]}...",
    ]

    return "\n".join(lines)
