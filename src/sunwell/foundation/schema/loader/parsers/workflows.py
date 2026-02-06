"""Workflows and refiners parsing."""

from sunwell.foundation.schema.models.workflow import Refiner, Workflow, WorkflowStep


def parse_workflows(data: list[dict]) -> tuple[Workflow, ...]:
    """Parse workflows."""
    workflows = []
    for w in data:
        steps = tuple(
            WorkflowStep(
                name=s["name"],
                action=s["action"],
                quality_gates=tuple(s.get("quality_gates", [])),
            )
            for s in w.get("steps", [])
        )
        workflows.append(
            Workflow(
                name=w["name"],
                trigger=w.get("trigger"),
                steps=steps,
                state_management=w.get("state_management", False),
            )
        )
    return tuple(workflows)


def parse_refiners(data: list[dict]) -> tuple[Refiner, ...]:
    """Parse refiners."""
    return tuple(
        Refiner(
            name=r["name"],
            purpose=r["purpose"],
            when=r.get("when"),
            operations=tuple(r.get("operations", [])),
        )
        for r in data
    )
