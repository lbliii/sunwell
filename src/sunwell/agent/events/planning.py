"""Plan transparency event factories (RFC-090).

Event factories for plan lifecycle:
- plan_winner_event: Plan selection complete with task details
"""

from typing import TYPE_CHECKING, Any

from sunwell.agent.events.types import AgentEvent, EventType

if TYPE_CHECKING:
    from sunwell.agent.events.types import GateSummary, TaskSummary


def plan_winner_event(
    tasks: int,
    gates: int,
    technique: str,
    selected_candidate_id: str = "candidate-0",
    task_list: list["TaskSummary"] | None = None,
    gate_list: list["GateSummary"] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a plan winner event with optional task details (RFC-090).

    Emitted when plan selection is complete. Includes task/gate counts
    for backward compatibility, plus optional detailed lists.

    Args:
        tasks: Number of tasks in the plan
        gates: Number of validation gates
        technique: Planning technique used ("single_shot", "harmonic", "minimal")
        selected_candidate_id: ID of the selected plan candidate (required by frontend)
        task_list: Optional list of task summaries for display
        gate_list: Optional list of gate summaries for display
    """
    from sunwell.agent.events.schemas import create_validated_event

    data: dict[str, Any] = {
        "tasks": tasks,
        "gates": gates,
        "technique": technique,
        "selected_candidate_id": selected_candidate_id,
        **kwargs,
    }

    # RFC-090: Include task details if available
    if task_list is not None:
        data["task_list"] = task_list
    if gate_list is not None:
        data["gate_list"] = gate_list

    return create_validated_event(EventType.PLAN_WINNER, data)
