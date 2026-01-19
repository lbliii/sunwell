"""Refinement Layer - Optionally improve the selected output (RFC-033).

This module implements the Refinement Layer of Naaru's unified architecture.
It provides three strategies for refining outputs:
- none: Skip refinement (free)
- tiered: Lightweight validation first, escalate if needed (0-2000 tokens)
- full: Always use full LLM judge, iterate until approved (~2000 tokens per iteration)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.diversity import Candidate


@dataclass(frozen=True, slots=True)
class RefinementResult:
    """Result from refinement layer."""
    
    text: str
    """The refined output text."""
    
    refined: bool
    """Whether refinement was applied."""
    
    attempts: int
    """Number of refinement attempts."""
    
    tokens: int
    """Total tokens used for refinement."""
    
    issues_found: list[str]
    """Issues that were addressed."""
    
    approved: bool
    """Whether the output was approved (for tiered/full)."""


async def refine_none(
    candidate: Candidate,
    task: str = "",
) -> RefinementResult:
    """Refinement Strategy: None - Skip refinement.
    
    Returns the candidate as-is without any refinement.
    
    Args:
        candidate: The selected candidate
        task: Original task (unused, for API consistency)
        
    Returns:
        RefinementResult with refined=False
        
    Cost: Free
    Use when: Cost-constrained, or initial quality is sufficient
    """
    return RefinementResult(
        text=candidate.text,
        refined=False,
        attempts=0,
        tokens=0,
        issues_found=[],
        approved=True,
    )


async def refine_tiered(
    candidate: Candidate,
    task: str,
    model: ModelProtocol,
    judge_model: ModelProtocol | None = None,
    purity_threshold: float = 6.0,
) -> RefinementResult:
    """Refinement Strategy: Tiered - Lightweight validation first, escalate if needed.
    
    Uses lightweight structural checks first, then escalates to full judge
    only if issues are found or confidence is low.
    
    Args:
        candidate: The selected candidate to refine
        task: Original task description
        model: Model for generation (if refinement needed)
        judge_model: Model for judging (if None, uses model)
        purity_threshold: Minimum quality score to approve (0-10)
        
    Returns:
        RefinementResult with refinement details
        
    Cost: 0-2000 tokens depending on escalation
    Use when: Want quality gate without always paying full judge cost
    """
    if judge_model is None:
        judge_model = model
    
    # Step 1: Lightweight structural check
    issues = _lightweight_validate(candidate.text, task)
    
    if not issues:
        # Pass without full judge
        return RefinementResult(
            text=candidate.text,
            refined=False,
            attempts=0,
            tokens=0,
            issues_found=[],
            approved=True,
        )
    
    # Step 2: Escalate to full judge
    verdict, score, judge_issues, judge_tokens = await _judge_output(
        judge_model, task, candidate.text
    )
    
    if verdict == "approve" or score >= purity_threshold:
        return RefinementResult(
            text=candidate.text,
            refined=False,
            attempts=0,
            tokens=judge_tokens,
            issues_found=judge_issues,
            approved=True,
        )
    
    # Step 3: Refine based on feedback
    from sunwell.models.protocol import GenerateOptions
    
    refine_prompt = f"""Your previous response had issues:
{chr(10).join(f'- {issue}' for issue in judge_issues[:5])}

Original task: {task[:500]}

Please fix these issues and provide an improved response."""
    
    refine_options = GenerateOptions(
        temperature=0.5,  # Lower temp for refinement
        max_tokens=2048,
    )
    
    result = await model.generate(refine_prompt, options=refine_options)
    refine_tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
    
    return RefinementResult(
        text=result.text,
        refined=True,
        attempts=1,
        tokens=judge_tokens + refine_tokens,
        issues_found=judge_issues,
        approved=False,  # May need another iteration, but we stop here for tiered
    )


async def refine_full(
    candidate: Candidate,
    task: str,
    model: ModelProtocol,
    judge_model: ModelProtocol | None = None,
    max_attempts: int = 2,
    purity_threshold: float = 6.0,
) -> RefinementResult:
    """Refinement Strategy: Full - Always use full LLM judge, iterate until approved.
    
    Uses full judge model for every iteration, refining until approved
    or max attempts reached.
    
    Args:
        candidate: The selected candidate to refine
        task: Original task description
        model: Model for generation
        judge_model: Model for judging (if None, uses model)
        max_attempts: Maximum refinement attempts
        purity_threshold: Minimum quality score to approve (0-10)
        
    Returns:
        RefinementResult with refinement details
        
    Cost: ~2000 tokens per iteration
    Use when: High-stakes, need guaranteed quality
    """
    if judge_model is None:
        judge_model = model
    
    current = candidate.text
    total_tokens = 0
    all_issues: list[str] = []
    attempts = 0
    
    for attempt in range(max_attempts):
        # Judge the current output
        verdict, score, issues, judge_tokens = await _judge_output(
            judge_model, task, current
        )
        total_tokens += judge_tokens
        all_issues.extend(issues)
        
        if verdict == "approve" or score >= purity_threshold:
            return RefinementResult(
                text=current,
                refined=attempts > 0,
                attempts=attempts,
                tokens=total_tokens,
                issues_found=all_issues,
                approved=True,
            )
        
        # Refine based on feedback
        from sunwell.models.protocol import GenerateOptions
        
        refine_prompt = f"""Your previous response had issues:
{chr(10).join(f'- {issue}' for issue in issues[:5])}

Original task: {task[:500]}

Please fix these issues and provide an improved response."""
        
        refine_options = GenerateOptions(
            temperature=0.5,  # Lower temp for refinement
            max_tokens=2048,
        )
        
        result = await model.generate(refine_prompt, options=refine_options)
        refine_tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
        total_tokens += refine_tokens
        
        current = result.text
        attempts += 1
    
    # Max attempts reached - get final score
    _, final_score, _, judge_tokens = await _judge_output(judge_model, task, current)
    total_tokens += judge_tokens
    
    return RefinementResult(
        text=current,
        refined=True,
        attempts=attempts,
        tokens=total_tokens,
        issues_found=all_issues,
        approved=final_score >= purity_threshold,
    )


def _lightweight_validate(output: str, task: str) -> list[str]:
    """Lightweight structural validation (no LLM).
    
    Returns list of issues found, or empty list if none.
    """
    issues: list[str] = []
    
    # Check for common problems
    if len(output.strip()) < 50:
        issues.append("Output too short")
    
    if output.count('TODO') > 0:
        issues.append("Contains TODO markers")
    
    if output.count('...') > 2:
        issues.append("Contains multiple ellipses (incomplete)")
    
    # For code tasks, check basic structure
    if 'code' in task.lower() or 'function' in task.lower() or 'class' in task.lower():
        if 'def ' not in output and 'class ' not in output:
            issues.append("Missing function or class definition")
        if '```' not in output and 'def ' in output:
            issues.append("Code not properly formatted")
    
    return issues


async def _judge_output(
    judge_model: ModelProtocol,
    task: str,
    output: str,
) -> tuple[str, float, list[str], int]:
    """Judge an output using the judge model.
    
    Returns:
        Tuple of (verdict, score, issues, tokens)
        verdict: "approve" or "reject"
        score: 0-10 quality score
        issues: List of issues found
        tokens: Tokens used
    """
    from sunwell.models.protocol import GenerateOptions
    
    judge_prompt = f"""Evaluate this output for the task: {task[:500]}

Output:
{output[:2000]}

Respond in JSON format:
{{
    "verdict": "approve" or "reject",
    "score": 0-10,
    "issues": ["issue1", "issue2", ...]
}}"""
    
    result = await judge_model.generate(
        judge_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=500),
    )
    
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
    
    # Parse JSON response
    import json
    import re
    
    text = result.text.strip()
    
    # Try to extract JSON
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            verdict = data.get("verdict", "reject")
            score = float(data.get("score", 5.0))
            issues = data.get("issues", [])
            return verdict, score, issues, tokens
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    # Fallback: try to extract score from text
    score_match = re.search(r'score[:\s]+(\d+\.?\d*)', text, re.IGNORECASE)
    if score_match:
        score = float(score_match.group(1))
        verdict = "approve" if score >= 7.0 else "reject"
        issues = ["Could not parse detailed issues"]
        return verdict, score, issues, tokens
    
    # Default fallback
    return "reject", 5.0, ["Could not parse judge response"], tokens
