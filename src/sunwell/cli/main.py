"""Main CLI entry point - Click group and top-level commands."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.cli.helpers import check_free_threading, load_dotenv
from sunwell.core.freethreading import runtime_info

# Import command modules to register them
from sunwell.cli import runtime_cmd, setup, bind, session, config_cmd, apply, skill, lens, ask, chat, naaru_cmd

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.option("--quiet", "-q", is_flag=True, help="Suppress warnings")
def main(quiet: bool = False) -> None:
    """Sunwell - RAG for Judgment.

    Apply professional expertise to LLM interactions through lens-based
    heuristic retrieval and validation.
    
    For optimal performance, use Python 3.14t (free-threaded):
    /usr/local/bin/python3.14t -m sunwell chat
    """
    load_dotenv()
    check_free_threading(quiet=quiet)


# Register all command groups and commands
main.add_command(runtime_cmd.runtime)
main.add_command(setup.setup)
main.add_command(apply.apply)
main.add_command(chat.chat)
main.add_command(ask.ask)
main.add_command(bind.bind)
main.add_command(session.sessions)
main.add_command(config_cmd.config)
main.add_command(skill.exec)
main.add_command(skill.validate)
main.add_command(lens.lens)

# Register benchmark commands (RFC-018)
from sunwell.benchmark.cli import benchmark
main.add_command(benchmark)

# Register naaru commands (RFC-019, RFC-032)
main.add_command(naaru_cmd.naaru)
