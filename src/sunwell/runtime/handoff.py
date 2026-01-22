"""Model handoff - transfer problem context between chats/models.

The core insight: when you've been troubleshooting with one model and want
fresh eyes from another, you shouldn't have to re-explain everything.

This module captures:
- What the problem is
- What's been tried
- What's been learned
- Key code context
- Current hypothesis

Then formats it as a "briefing" for the next model to pick up where you left off.
"""


import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class Attempt:
    """Record of something that was tried."""

    description: str
    """What was tried."""

    outcome: Literal["success", "partial", "failed", "unclear"]
    """How it went."""

    learning: str | None = None
    """What was learned from this attempt."""

    code_refs: list[str] = field(default_factory=list)
    """Code files/lines that were examined."""


@dataclass
class HandoffState:
    """Complete state for warm handoff between models.

    This is the "briefing document" you give to the next model.
    It captures everything needed to continue without starting over.
    """

    # Problem definition
    problem: str
    """What are we trying to solve?"""

    goal: str
    """What does success look like?"""

    # Context
    relevant_files: list[str] = field(default_factory=list)
    """Files that matter for this problem."""

    key_code_snippets: dict[str, str] = field(default_factory=dict)
    """file:line -> code snippet for critical context."""

    # Progress
    attempts: list[Attempt] = field(default_factory=list)
    """What's been tried so far."""

    learnings: list[str] = field(default_factory=list)
    """Key insights discovered."""

    dead_ends: list[str] = field(default_factory=list)
    """Approaches that don't work (don't retry)."""

    # Current state
    current_hypothesis: str = ""
    """Best current theory about the issue."""

    next_steps: list[str] = field(default_factory=list)
    """Suggested things to try."""

    blockers: list[str] = field(default_factory=list)
    """What's preventing progress."""

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""
    previous_models: list[str] = field(default_factory=list)

    def add_attempt(
        self,
        description: str,
        outcome: Literal["success", "partial", "failed", "unclear"],
        learning: str | None = None,
        code_refs: list[str] | None = None,
    ) -> None:
        """Record an attempt."""
        self.attempts.append(Attempt(
            description=description,
            outcome=outcome,
            learning=learning,
            code_refs=code_refs or [],
        ))
        if learning:
            self.learnings.append(learning)
        self.updated_at = datetime.now().isoformat()

    def mark_dead_end(self, approach: str) -> None:
        """Mark an approach as a dead end (don't retry)."""
        if approach not in self.dead_ends:
            self.dead_ends.append(approach)
        self.updated_at = datetime.now().isoformat()

    def save(self, path: Path) -> None:
        """Save handoff state to file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert attempts to dicts
        data = asdict(self)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> HandoffState:
        """Load handoff state from file."""
        with open(path) as f:
            data = json.load(f)

        # Reconstruct Attempt objects
        data["attempts"] = [Attempt(**a) for a in data.get("attempts", [])]

        return cls(**data)

    def to_briefing(self, include_code: bool = True) -> str:
        """Generate a briefing document for the next model.

        This is what you paste into the new chat to bring the model up to speed.
        """
        sections = []

        # Header
        sections.append("# Problem Handoff Briefing\n")
        sections.append(f"*Session continued from: {self.updated_at}*\n")
        if self.previous_models:
            sections.append(f"*Previously worked with: {', '.join(self.previous_models)}*\n")

        # Problem
        sections.append("## Problem\n")
        sections.append(f"{self.problem}\n")

        # Goal
        sections.append("## Goal\n")
        sections.append(f"{self.goal}\n")

        # Key files
        if self.relevant_files:
            sections.append("## Relevant Files\n")
            for f in self.relevant_files:
                sections.append(f"- `{f}`\n")

        # Code snippets
        if include_code and self.key_code_snippets:
            sections.append("## Key Code Context\n")
            for ref, code in self.key_code_snippets.items():
                sections.append(f"\n### `{ref}`\n```\n{code}\n```\n")

        # What's been tried
        if self.attempts:
            sections.append("## What's Been Tried\n")
            for i, attempt in enumerate(self.attempts, 1):
                icon = {"success": "✅", "partial": "🟡", "failed": "❌", "unclear": "❓"}[attempt.outcome]
                sections.append(f"\n### Attempt {i}: {attempt.description} {icon}\n")
                if attempt.learning:
                    sections.append(f"**Learning:** {attempt.learning}\n")
                if attempt.code_refs:
                    sections.append(f"**Files examined:** {', '.join(attempt.code_refs)}\n")

        # Dead ends
        if self.dead_ends:
            sections.append("## Dead Ends (Don't Retry)\n")
            for de in self.dead_ends:
                sections.append(f"- ❌ {de}\n")

        # Learnings
        if self.learnings:
            sections.append("## Key Learnings\n")
            for learning in self.learnings:
                sections.append(f"- {learning}\n")

        # Current state
        if self.current_hypothesis:
            sections.append("## Current Hypothesis\n")
            sections.append(f"{self.current_hypothesis}\n")

        # Next steps
        if self.next_steps:
            sections.append("## Suggested Next Steps\n")
            for i, step in enumerate(self.next_steps, 1):
                sections.append(f"{i}. {step}\n")

        # Blockers
        if self.blockers:
            sections.append("## Blockers\n")
            for blocker in self.blockers:
                sections.append(f"- ⚠️ {blocker}\n")

        # Call to action
        sections.append("\n---\n")
        sections.append("**Please continue from here. You have fresh context - what do you see that might have been missed?**\n")

        return "".join(sections)

    def to_prompt_injection(self) -> str:
        """Shorter version for injecting into a Sunwell prompt."""
        parts = [
            f"## Continuing Problem: {self.problem}",
            f"Goal: {self.goal}",
        ]

        if self.attempts:
            failed = [a for a in self.attempts if a.outcome == "failed"]
            if failed:
                parts.append(f"Already tried (didn't work): {', '.join(a.description for a in failed)}")

        if self.dead_ends:
            parts.append(f"Dead ends: {', '.join(self.dead_ends)}")

        if self.learnings:
            parts.append(f"Key learnings: {'; '.join(self.learnings[:3])}")

        if self.current_hypothesis:
            parts.append(f"Current theory: {self.current_hypothesis}")

        return "\n".join(parts)
