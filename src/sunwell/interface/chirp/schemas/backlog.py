"""Backlog/goal-related form schemas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NewGoalForm:
    """Form for creating a new goal.

    Fields:
        description: Goal description (required, max 500 chars)
        priority: Priority level (high/medium/low, defaults to medium)
    """

    description: str
    priority: str = "medium"
