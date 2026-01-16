"""Workflow data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """A single step in a workflow."""

    name: str
    action: str  # What to do
    quality_gates: tuple[str, ...] = ()  # Validators to run after


@dataclass(frozen=True, slots=True)
class Workflow:
    """A multi-step process.

    Workflows define sequences of operations that should be performed
    together, with optional quality gates between steps.
    """

    name: str
    trigger: str | None = None  # When to use this workflow
    steps: tuple[WorkflowStep, ...] = ()
    state_management: bool = False  # Persist across sessions?

    def get_step(self, name: str) -> WorkflowStep | None:
        """Get a step by name."""
        for step in self.steps:
            if step.name.lower() == name.lower():
                return step
        return None


@dataclass(frozen=True, slots=True)
class Refiner:
    """An improvement operation.

    Refiners are transformations applied to content to improve it,
    triggered by specific conditions or validation failures.
    """

    name: str
    purpose: str
    when: str | None = None  # Conditions to trigger
    operations: tuple[str, ...] = ()
