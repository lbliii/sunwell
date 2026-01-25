"""Deep Verification CLI command (RFC-047).

Usage:
    sunwell verify src/models/user.py
    sunwell verify src/models/user.py --level thorough
    sunwell verify src/models/user.py --verbose
    sunwell verify src/models/user.py --save-tests
"""


import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--level",
    "-l",
    type=click.Choice(["quick", "standard", "thorough"]),
    default="standard",
    help="Verification level (default: standard)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--save-tests", is_flag=True, help="Save generated tests to tests/generated/")
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama"]),
              default=None, help="Model provider (default: from config)")
@click.option("--model", "-m", help="Override model selection")
@click.option("--contract", "-c", help="Explicit contract/specification to verify against")
@click.option("--quiet", "-q", is_flag=True, help="Only show pass/fail result")
def verify(
    file_path: str,
    level: str,
    verbose: bool,
    save_tests: bool,
    provider: str | None,
    model: str | None,
    contract: str | None,
    quiet: bool,
) -> None:
    """Deep verification of code files (RFC-047).

    Verifies that code does the right thing, not just that it runs.

    \b
    Examples:
        sunwell verify src/models/user.py
        sunwell verify src/models/user.py --level thorough
        sunwell verify src/models/user.py --contract "Returns users sorted by date, newest first"
        sunwell verify src/models/user.py --provider openai  # Use OpenAI
    """
    asyncio.run(
        _verify_file(
            Path(file_path),
            level=level,
            verbose=verbose,
            save_tests=save_tests,
            provider_override=provider,
            model_override=model,
            contract=contract,
            quiet=quiet,
        )
    )


async def _verify_file(
    file_path: Path,
    level: str,
    verbose: bool,
    save_tests: bool,
    provider_override: str | None,
    model_override: str | None,
    contract: str | None,
    quiet: bool,
) -> None:
    """Execute deep verification on a file."""
    from sunwell.cli.helpers import resolve_model
    from sunwell.config import get_config
    from sunwell.naaru.artifacts import ArtifactSpec
    from sunwell.verification import create_verifier

    # Load config
    config = get_config()

    # Create model using resolve_model() helper
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider_override, model_override)
        if verbose:
            provider = provider_override or (config.model.default_provider if config else "ollama")
            model_name = model_override or (config.model.default_model if config else "gemma3:4b")
            console.print(f"[dim]Using model: {provider}:{model_name}[/dim]")

    except Exception as e:
        console.print(f"[red]Error: Could not load model: {e}[/red]")
        return

    if not synthesis_model:
        console.print("[red]No model available[/red]")
        return

    # Read file content
    try:
        content = file_path.read_text()
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        return

    # Create artifact spec
    artifact = ArtifactSpec(
        id=file_path.stem,
        description=f"Verify {file_path.name}",
        contract=contract or f"Code in {file_path.name} should be correct",
        produces_file=str(file_path),
        requires=frozenset(),
        domain_type="code",
    )

    # Create verifier
    verifier = create_verifier(
        model=synthesis_model,
        cwd=Path.cwd(),
        level=level,
    )

    if not quiet:
        console.print(
            Panel(
                f"[bold]Deep Verification[/bold]: {file_path}\n"
                f"Level: {level.upper()}",
                title="RFC-047",
                border_style="blue",
            )
        )

    # Run verification with progress display
    result = None

    if quiet:
        # Silent mode - just run and report result
        async for event in verifier.verify(artifact, content):
            if event.stage == "complete":
                result = event.data.get("result")
    else:
        # Interactive mode with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Starting verification...", total=None)

            async for event in verifier.verify(artifact, content):
                progress.update(task_id, description=f"{event.stage}: {event.message}")

                if verbose and event.stage not in ("start", "complete"):
                    console.print(f"  [dim]{event.message}[/dim]")

                if event.stage == "complete":
                    result = event.data.get("result")
                    progress.update(task_id, description="Complete")

    if result is None:
        console.print("[red]Verification failed to complete[/red]")
        return

    # Display results
    if quiet:
        # Minimal output
        if result.passed:
            console.print(f"[green]✓ PASSED[/green] ({result.confidence:.0%})")
        else:
            console.print(f"[red]✗ FAILED[/red] ({result.confidence:.0%})")
        return

    # Full output
    _display_result(result, verbose)

    # Save generated tests if requested
    if save_tests and result.generated_tests:
        _save_tests(file_path, result.generated_tests)


def _display_result(result, verbose: bool) -> None:
    """Display verification result."""

    # Summary line
    if result.passed:
        status = "[green]✓ PASSED[/green]"
        confidence_style = "green" if result.confidence >= 0.9 else "yellow"
    else:
        status = "[red]✗ FAILED[/red]"
        confidence_style = "red" if result.confidence < 0.5 else "yellow"

    console.print(
        f"\n{status} | "
        f"Confidence: [{confidence_style}]{result.confidence:.0%}[/{confidence_style}] | "
        f"Duration: {result.duration_ms}ms"
    )

    # Test results
    if result.test_results:
        tr = result.test_results
        console.print(
            f"\nTests: {tr.passed}/{tr.total_tests} passed "
            f"({tr.pass_rate:.0%})"
        )

    # Perspective summary
    if result.perspective_results:
        console.print("\n[bold]Perspectives:[/bold]")
        for p in result.perspective_results:
            icon = {"correct": "✓", "suspicious": "?", "incorrect": "✗"}[p.verdict]
            color = {"correct": "green", "suspicious": "yellow", "incorrect": "red"}[p.verdict]
            console.print(
                f"  [{color}]{icon}[/{color}] {p.perspective}: {p.verdict} ({p.confidence:.0%})"
            )

    # Issues
    if result.issues:
        console.print(f"\n[bold]Issues ({len(result.issues)}):[/bold]")
        for issue in result.issues[:5]:  # Show top 5
            severity_color = {
                "critical": "red",
                "high": "red",
                "medium": "yellow",
                "low": "dim",
            }[issue.severity]
            console.print(
                f"  [{severity_color}]{issue.severity.upper()}[/{severity_color}]: "
                f"{issue.description}"
            )

        if len(result.issues) > 5:
            console.print(f"  [dim]... and {len(result.issues) - 5} more[/dim]")

    # Recommendations
    if result.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for rec in result.recommendations[:3]:
            console.print(f"  • {rec}")

    # Verbose: test details
    if verbose and result.generated_tests:
        console.print(f"\n[bold]Generated Tests ({len(result.generated_tests)}):[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("Category")
        table.add_column("Status")

        for test in result.generated_tests:
            # Find test result
            test_result = None
            if result.test_results:
                for tr in result.test_results.test_results:
                    if tr.test_id == test.id:
                        test_result = tr
                        break

            status = "❓"
            if test_result:
                status = "[green]✓[/green]" if test_result.passed else "[red]✗[/red]"

            table.add_row(test.name, test.category, status)

        console.print(table)


def _save_tests(file_path: Path, tests: tuple) -> None:
    """Save generated tests to tests/generated/."""

    # Create output directory
    output_dir = Path.cwd() / "tests" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build test file
    test_file = output_dir / f"test_{file_path.stem}.py"

    imports = """\"\"\"Generated tests for {file_name}.

Auto-generated by sunwell verify (RFC-047).
Review and customize as needed.
\"\"\"

import pytest
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

"""

    content = imports.format(file_name=file_path.name)

    for test in tests:
        content += f"\n# {test.description}\n{test.code}\n"

    # Write file
    test_file.write_text(content)
    console.print(f"\n[green]Tests saved to:[/green] {test_file}")
