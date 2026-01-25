"""Event printing helpers for CLI."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.events import AgentEvent

from sunwell.cli.theme import console


def print_event(event: AgentEvent, verbose: bool) -> None:
    """Print an agent event to console with Holy Light styling (RFC-131).

    Args:
        event: Agent event to print
        verbose: Whether to show verbose output
    """
    from sunwell.agent import EventType

    if event.type == EventType.PLAN_WINNER:
        data = event.data or {}
        tasks = data.get("tasks", 0)
        gates = data.get("gates", 0)
        technique = data.get("technique", "unknown")
        console.print(f"\n[holy.success]★[/] [sunwell.heading]Plan ready[/] ({technique})")
        console.print(f"  [holy.gold]├─[/] {tasks} tasks")
        console.print(f"  [holy.gold]└─[/] {gates} validation gates")
    elif event.type == EventType.ERROR:
        console.print(f"  [void.purple]✗[/] [sunwell.error]Error:[/] {event.data}")
    elif verbose:
        console.print(f"  [neutral.dim]· {event.type.value}: {event.data}[/]")


def print_plan_details(
    data: dict[str, str | int | list[dict[str, str | list[str]]]],
    verbose: bool,
    goal: str,
) -> None:
    """Print rich plan details with truncation (RFC-090, RFC-131).

    Args:
        data: Plan data dictionary
        verbose: Whether to show verbose output
        goal: The goal string
    """
    technique = data.get("technique", "unknown")
    tasks = data.get("tasks", 0)
    gates = data.get("gates", 0)
    task_list = data.get("task_list", [])
    gate_list = data.get("gate_list", [])

    # RFC-131: Holy Light styled header
    console.print(f"[holy.success]★[/] [sunwell.heading]Plan ready[/] ({technique})")
    console.print(f"  [holy.gold]├─[/] {tasks} tasks")
    console.print(f"  [holy.gold]└─[/] {gates} validation gates\n")

    # Task list with truncation
    if task_list:
        console.print("[sunwell.heading]✦ Tasks[/]")
        display_limit = len(task_list) if verbose else 10
        for i, task in enumerate(task_list[:display_limit], 1):
            deps = ""
            if task.get("depends_on"):
                if verbose:
                    # Show IDs with --verbose
                    deps = f" [neutral.dim](←{','.join(task['depends_on'][:3])})[/]"
                else:
                    # Show numbers by default
                    dep_nums = [
                        str(j + 1) for j, t in enumerate(task_list)
                        if t["id"] in task["depends_on"]
                    ]
                    deps = f" [neutral.dim](←{','.join(dep_nums)})[/]" if dep_nums else ""

            produces = ""
            if task.get("produces"):
                produces = f" [green]→[/] {task['produces'][0]}"

            # Format: index. [id] description deps produces
            task_id = task["id"][:12].ljust(12)
            desc = task["description"][:35].ljust(35)
            console.print(f"  {i:2}. [holy.gold.dim][{task_id}][/] {desc}{deps}{produces}")

        # Truncation notice
        if not verbose and len(task_list) > 10:
            remaining = len(task_list) - 10
            console.print(f"  [neutral.dim]... and {remaining} more (use --verbose)[/]")
        console.print()

    # Gate list
    if gate_list:
        console.print("[sunwell.heading]✦ Validation Gates[/]")
        for gate in gate_list:
            after = ", ".join(gate.get("after_tasks", [])[:3])
            gtype = gate.get("type", "unknown").ljust(12)
            gid = gate["id"]
            console.print(f"  [holy.gold]├─[/] [{gid}] {gtype} [neutral.dim]after: {after}[/]")
        console.print()

    # Next steps with Holy Light styling
    console.print(f"[holy.gold]{'━' * 54}[/]")
    console.print("[sunwell.heading]✧ Next steps:[/]")
    # Escape the goal for display (avoid rich markup issues)
    safe_goal = goal.replace("[", "\\[").replace("]", "\\]")
    console.print(f'  [holy.gold]›[/] sunwell "{safe_goal}" [neutral.dim]— Run[/]')
    console.print(f'  [holy.gold]›[/] sunwell "{safe_goal}" --plan --open [neutral.dim]— Studio[/]')
    console.print('  [holy.gold]›[/] sunwell plan "..." -o . [neutral.dim]— Save[/]')
