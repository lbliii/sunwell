"""Internal commands — Studio integration and power user tools.

This module consolidates Tier 4 commands that are:
- Used by Studio via HTTP API (not direct subprocess)
- Power user tools not needed in day-to-day usage
- Internal debugging and diagnostic tools

Commands are organized under `sunwell internal <group> <subcommand>` to reduce
top-level namespace clutter while maintaining full functionality.

Note: The actual implementations remain in their original modules.
This is a thin routing layer for organization.
"""

import click


@click.group(name="internal", hidden=True)
def internal() -> None:
    """Internal commands for Studio integration and power users.

    These commands are not shown in main help but are fully functional.
    Use `sunwell internal --help` to see available subcommands.

    Subcommand Groups:
        backlog     Autonomous backlog management (RFC-046)
        dag         DAG and incremental execution (RFC-074)
        scan        State DAG scanning (RFC-100)
        workspace   Workspace-aware scanning (RFC-103)
        weakness    Weakness cascade analysis (RFC-063)
        workers     Multi-instance coordination (RFC-051)
        workflow    Autonomous workflow execution (RFC-086)
        index       Codebase indexing (RFC-108)
        nav         ToC navigation (RFC-124)
        intel       Project intelligence (RFC-045)
        briefing    Briefing system (RFC-071)
        security    Security-first execution (RFC-089)
        surface     Surface primitives (RFC-072)
        interface   Generative interface (RFC-075)

    Examples:
        sunwell internal backlog show
        sunwell internal dag plan
        sunwell internal workspace detect
    """
    pass


def register_internal_commands(parent_group: click.Group) -> None:
    """Register internal commands from their original modules.

    This function imports and registers all internal commands under
    the internal group. Called from main.py during CLI initialization.

    Args:
        parent_group: The parent click group (typically main)
    """
    # Import commands from their original locations
    from sunwell.interface.cli.commands import (
        backlog_cmd,
        briefing_cmd,
        dag_cmd,
        index_cmd,
        intel_cmd,
        interface_cmd,
        nav_cmd,
        scan_cmd,
        security_cmd,
        weakness_cmd,
        workers_cmd,
        workflow_cmd,
        workspace_cmd,
    )
    from sunwell.interface.cli.surface import surface

    # Register under internal group
    internal.add_command(backlog_cmd.backlog, name="backlog")
    internal.add_command(dag_cmd.dag, name="dag")
    internal.add_command(scan_cmd.scan, name="scan")
    internal.add_command(workspace_cmd.workspace, name="workspace")
    internal.add_command(weakness_cmd.weakness, name="weakness")
    internal.add_command(workers_cmd.workers, name="workers")
    internal.add_command(workflow_cmd.workflow, name="workflow")
    internal.add_command(index_cmd.index, name="index")
    internal.add_command(nav_cmd.nav, name="nav")
    internal.add_command(intel_cmd.intel, name="intel")
    internal.add_command(briefing_cmd.briefing, name="briefing")
    internal.add_command(security_cmd.security, name="security")
    internal.add_command(interface_cmd.interface, name="interface")
    internal.add_command(surface, name="surface")

    # Add the internal group to parent
    parent_group.add_command(internal)
