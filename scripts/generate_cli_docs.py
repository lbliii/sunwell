#!/usr/bin/env python
"""Generate CLI reference documentation from Click commands.

This script introspects the Sunwell CLI to generate comprehensive
markdown documentation for all commands and options.

Usage:
    python scripts/generate_cli_docs.py > docs/cli-reference.md
    python scripts/generate_cli_docs.py --output docs/cli-reference.md
"""

import sys
from io import StringIO
from typing import TextIO

import click


def get_command_help(cmd: click.Command, prefix: str = "") -> str:
    """Extract help text for a command.

    Args:
        cmd: Click command to document
        prefix: Command prefix (e.g., "sunwell config")

    Returns:
        Formatted help string
    """
    # Get the short help
    help_text = cmd.help or cmd.get_short_help_str() or "No description available."
    return help_text.strip()


def format_param(param: click.Parameter) -> str:
    """Format a parameter for documentation.

    Args:
        param: Click parameter to format

    Returns:
        Markdown formatted parameter string
    """
    if isinstance(param, click.Option):
        # Format option
        opts = "/".join(param.opts)
        if param.secondary_opts:
            opts += "/" + "/".join(param.secondary_opts)

        type_name = ""
        if param.type and param.type.name != "TEXT":
            type_name = f" `{param.type.name}`"

        default = ""
        if param.default is not None and param.default != ():
            if isinstance(param.default, bool):
                default = f" (default: {str(param.default).lower()})"
            else:
                default = f" (default: {param.default})"

        help_text = param.help or ""
        required = " **(required)**" if param.required else ""

        return f"- `{opts}`{type_name}{required}: {help_text}{default}"

    elif isinstance(param, click.Argument):
        # Format argument
        name = param.name.upper()
        required = "" if param.required else " (optional)"
        return f"- `{name}`{required}"

    return ""


def document_command(
    cmd: click.Command, name: str, prefix: str = "sunwell", level: int = 2
) -> str:
    """Generate markdown documentation for a single command.

    Args:
        cmd: Click command to document
        name: Command name
        prefix: Parent command prefix
        level: Heading level

    Returns:
        Markdown documentation string
    """
    lines = []
    full_name = f"{prefix} {name}" if prefix else name
    heading = "#" * level

    lines.append(f"{heading} `{full_name}`")
    lines.append("")

    # Description
    help_text = get_command_help(cmd, prefix)
    lines.append(help_text)
    lines.append("")

    # Arguments
    args = [p for p in cmd.params if isinstance(p, click.Argument)]
    if args:
        lines.append("**Arguments:**")
        lines.append("")
        for arg in args:
            lines.append(format_param(arg))
        lines.append("")

    # Options
    opts = [p for p in cmd.params if isinstance(p, click.Option)]
    # Filter out --help which is standard
    opts = [o for o in opts if "--help" not in o.opts]
    if opts:
        lines.append("**Options:**")
        lines.append("")
        for opt in opts:
            lines.append(format_param(opt))
        lines.append("")

    # Subcommands (for groups)
    if isinstance(cmd, click.Group):
        ctx = click.Context(cmd)
        subcommands = cmd.list_commands(ctx)
        if subcommands:
            lines.append("**Subcommands:**")
            lines.append("")
            for sub_name in sorted(subcommands):
                sub_cmd = cmd.get_command(ctx, sub_name)
                if sub_cmd and not sub_cmd.hidden:
                    sub_help = get_command_help(sub_cmd, "")
                    lines.append(f"- `{sub_name}`: {sub_help}")
            lines.append("")

    return "\n".join(lines)


def document_group_commands(
    group: click.Group, prefix: str = "sunwell", level: int = 2, output: TextIO = sys.stdout
) -> None:
    """Document all subcommands of a group.

    Args:
        group: Click group to document
        prefix: Command prefix
        level: Starting heading level
        output: Output stream
    """
    ctx = click.Context(group)
    for name in sorted(group.list_commands(ctx)):
        cmd = group.get_command(ctx, name)
        if cmd is None:
            continue

        # Skip hidden commands
        if cmd.hidden:
            continue

        doc = document_command(cmd, name, prefix, level)
        output.write(doc)
        output.write("\n")

        # Recurse into subgroups
        if isinstance(cmd, click.Group):
            sub_ctx = click.Context(cmd)
            for sub_name in sorted(cmd.list_commands(sub_ctx)):
                sub_cmd = cmd.get_command(sub_ctx, sub_name)
                if sub_cmd and not sub_cmd.hidden:
                    sub_doc = document_command(
                        sub_cmd, sub_name, f"{prefix} {name}", level + 1
                    )
                    output.write(sub_doc)
                    output.write("\n")


def generate_cli_reference(output: TextIO = sys.stdout) -> None:
    """Generate complete CLI reference documentation.

    Args:
        output: Output stream to write to
    """
    from sunwell.interface.cli.core.main import main

    # Header
    output.write("# Sunwell CLI Reference\n\n")
    output.write("Complete reference for all Sunwell CLI commands.\n\n")
    output.write("## Quick Reference\n\n")
    output.write("```bash\n")
    output.write("# Run a goal\n")
    output.write('sunwell "Build a REST API with auth"\n\n')
    output.write("# Use a skill shortcut\n")
    output.write("sunwell -s a-2 docs/api.md\n\n")
    output.write("# Interactive mode\n")
    output.write("sunwell chat\n\n")
    output.write("# Show all commands\n")
    output.write("sunwell --help\n")
    output.write("```\n\n")

    # Main command
    output.write("## Main Command\n\n")
    doc = document_command(main, "sunwell", "", 3)
    output.write(doc)
    output.write("\n")

    # Commands by category
    output.write("## Commands\n\n")

    # Tier 1-2: Visible commands
    output.write("### Primary Commands\n\n")
    output.write("These are the main commands for everyday use.\n\n")

    primary = ["config", "project", "sessions", "lens", "setup", "serve"]
    ctx = click.Context(main)

    for name in primary:
        cmd = main.get_command(ctx, name)
        if cmd:
            doc = document_command(cmd, name, "sunwell", 4)
            output.write(doc)
            output.write("\n")

            # Document subcommands
            if isinstance(cmd, click.Group):
                sub_ctx = click.Context(cmd)
                for sub_name in sorted(cmd.list_commands(sub_ctx)):
                    sub_cmd = cmd.get_command(sub_ctx, sub_name)
                    if sub_cmd and not getattr(sub_cmd, "hidden", False):
                        sub_doc = document_command(
                            sub_cmd, sub_name, f"sunwell {name}", 5
                        )
                        output.write(sub_doc)
                        output.write("\n")

    # Additional visible commands
    output.write("### Additional Commands\n\n")
    output.write("Utility commands for debugging and analysis.\n\n")

    additional = ["debug", "lineage", "review", "chat"]
    for name in additional:
        cmd = main.get_command(ctx, name)
        if cmd and not cmd.hidden:
            doc = document_command(cmd, name, "sunwell", 4)
            output.write(doc)
            output.write("\n")

    # Footer
    output.write("---\n\n")
    output.write("*Generated from Click command definitions*\n")


def main_generate() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate CLI reference docs")
    parser.add_argument(
        "--output", "-o", type=str, help="Output file (default: stdout)"
    )
    args = parser.parse_args()

    if args.output:
        with open(args.output, "w") as f:
            generate_cli_reference(f)
        print(f"Generated: {args.output}")
    else:
        generate_cli_reference(sys.stdout)


if __name__ == "__main__":
    main_generate()
