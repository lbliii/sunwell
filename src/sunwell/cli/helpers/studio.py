"""Studio integration helpers."""

import json
from datetime import datetime
from pathlib import Path

from sunwell.cli.open_cmd import launch_studio
from sunwell.cli.theme import console


def open_plan_in_studio(
    plan_data: dict[str, str | int | list[dict[str, str | list[str]]]],
    goal: str,
    workspace: Path,
) -> None:
    """Save plan and open in Studio (RFC-090).

    Args:
        plan_data: Plan data dictionary
        goal: The goal string
        workspace: Workspace path
    """
    # Ensure .sunwell directory exists
    plan_dir = workspace / ".sunwell"
    plan_dir.mkdir(exist_ok=True)

    # Save plan with goal context
    plan_file = plan_dir / "current-plan.json"
    plan_data["goal"] = goal
    plan_data["created_at"] = datetime.now().isoformat()
    plan_file.write_text(json.dumps(plan_data, indent=2))

    console.print("\n[cyan]Opening plan in Studio...[/cyan]")

    # Launch Studio in planning mode with plan file
    launch_studio(
        project=str(workspace),
        lens="coder",
        mode="planning",
        plan_file=str(plan_file),
    )
