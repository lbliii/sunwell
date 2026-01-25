"""Rich terminal output for demo results (RFC-095).

Renders beautiful, shareable terminal output that demonstrates
the Prism Principle effectively.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.benchmark.demo.executor import DemoComparison, DemoResult
from sunwell.benchmark.demo.scorer import FEATURE_DISPLAY_NAMES, DemoScore
from sunwell.benchmark.demo.tasks import DemoTask


class DemoPresenter:
    """Renders demo results to terminal using Rich.

    Creates visually compelling output that:
    - Screenshots well for social proof
    - Clearly shows the quality difference
    - Explains what happened (in verbose mode)
    """

    def __init__(self, verbose: bool = False) -> None:
        """Initialize presenter.

        Args:
            verbose: Whether to show detailed output (judge feedback, etc.)
        """
        self.console = Console()
        self.verbose = verbose

    def present(self, comparison: DemoComparison, model_name: str = "unknown") -> None:
        """Render the full demo comparison.

        Args:
            comparison: The complete comparison result.
            model_name: Name of the model used for display.
        """
        # Header
        self._render_header(model_name)

        # Separator
        self.console.print("━" * 60)
        self.console.print()

        # Single-shot section
        self._render_result(
            "STEP 1: Single-shot (what you'd get from raw prompting)",
            comparison.single_shot,
            comparison.single_score,
            comparison.task,
        )

        # Separator
        self.console.print("━" * 60)
        self.console.print()

        # Sunwell section
        self._render_result(
            "STEP 2: Sunwell + Resonance (same model, structured cognition)",
            comparison.sunwell,
            comparison.sunwell_score,
            comparison.task,
        )

        # Separator
        self.console.print("━" * 60)
        self.console.print()

        # Comparison table
        self._render_comparison(comparison)

        # Separator
        self.console.print("━" * 60)
        self.console.print()

        # Tagline
        self._render_tagline(comparison)

    def _render_header(self, model_name: str) -> None:
        """Render the demo header."""
        self.console.print()
        self.console.print(
            Panel(
                "[bold cyan]🔮 Sunwell Demo[/bold cyan] — See the Prism Principle in action",
                border_style="cyan",
            )
        )
        self.console.print()
        self.console.print(f"Using model: [cyan]{model_name}[/cyan]")
        self.console.print()

    def _render_result(
        self,
        title: str,
        result: DemoResult,
        score: DemoScore,
        task: DemoTask,
    ) -> None:
        """Render a single result (single-shot or Sunwell)."""
        self.console.print(f"[bold]{title}[/bold]")
        self.console.print()

        # Show prompt for single-shot
        if result.method == "single_shot":
            self.console.print(f'Prompt: "[dim]{task.prompt}[/dim]"')
            self.console.print()

        # Timing
        self.console.print(f"⏳ Generated in {result.time_ms}ms")

        # Show iterations for Sunwell
        if result.iterations > 0:
            self.console.print(f"   Refined {result.iterations} time(s)")

        self.console.print()

        # Code result in a panel
        code_display = self._truncate_code(result.code, max_lines=15)
        score_color = self._score_color(score.score)
        self.console.print(
            Panel(
                code_display,
                title=f"[{score_color}]Score: {score.score}/10[/{score_color}]",
                border_style=score_color,
            )
        )

        # Scoring details (verbose mode or for issues)
        if self.verbose or score.issues:
            self.console.print()
            self._render_scoring(score, task.expected_features)

        self.console.print()

    def _render_scoring(
        self,
        score: DemoScore,
        expected_features: frozenset[str],
    ) -> None:
        """Render feature scoring details."""
        for feature in expected_features:
            display_name = FEATURE_DISPLAY_NAMES.get(feature, feature)
            present = score.features.get(feature, False)
            icon = "[green]✅[/green]" if present else "[red]❌[/red]"
            self.console.print(f"  {icon} {display_name}")

    def _render_comparison(self, comparison: DemoComparison) -> None:
        """Render the comparison table."""
        self.console.print("[bold]📊 COMPARISON[/bold]")
        self.console.print()

        table = Table(show_header=True, header_style="bold")
        table.add_column("Metric", style="cyan")
        table.add_column("Single-shot", justify="center")
        table.add_column("Sunwell", justify="center")
        table.add_column("Delta", justify="center")

        # Lines
        single_lines = comparison.single_score.lines
        sunwell_lines = comparison.sunwell_score.lines
        lines_delta = sunwell_lines - single_lines
        table.add_row(
            "Lines",
            str(single_lines),
            str(sunwell_lines),
            f"[green]+{lines_delta}[/green]" if lines_delta > 0 else str(lines_delta),
        )

        # Score
        single_score = comparison.single_score.score
        sunwell_score = comparison.sunwell_score.score
        score_delta = sunwell_score - single_score
        table.add_row(
            "Score",
            f"{single_score}/10",
            f"{sunwell_score}/10",
            f"[green]+{score_delta:.1f}[/green]" if score_delta > 0 else f"{score_delta:.1f}",
        )

        # Time
        single_time = comparison.single_shot.time_ms
        sunwell_time = comparison.sunwell.time_ms
        time_delta = sunwell_time - single_time
        table.add_row(
            "Time",
            f"{single_time}ms",
            f"{sunwell_time}ms",
            f"[yellow]+{time_delta}ms[/yellow]" if time_delta > 0 else f"{time_delta}ms",
        )

        # Feature comparison
        for feature in comparison.task.expected_features:
            display_name = FEATURE_DISPLAY_NAMES.get(feature, feature)
            single_has = comparison.single_score.features.get(feature, False)
            sunwell_has = comparison.sunwell_score.features.get(feature, False)
            table.add_row(
                display_name,
                "[green]✅[/green]" if single_has else "[red]❌[/red]",
                "[green]✅[/green]" if sunwell_has else "[red]❌[/red]",
                "",
            )

        self.console.print(table)
        self.console.print()

        # Improvement percentage
        improvement = comparison.improvement_percent
        if improvement > 0:
            self.console.print(
                f"[bold green]Improvement: +{improvement:.0f}%[/bold green]"
            )
        self.console.print()

    def _render_tagline(self, comparison: DemoComparison) -> None:
        """Render the closing tagline and next steps."""
        self.console.print(
            "[bold cyan]🔮 Same model. Same prompt. Different architecture.[/bold cyan]"
        )
        self.console.print()
        self.console.print(
            "   [italic]The capability was already there. Sunwell revealed it.[/italic]"
        )
        self.console.print()

        if self.verbose:
            self.console.print("[dim]What happened:[/dim]")
            self.console.print("[dim]  1. Single-shot collapsed to minimal implementation[/dim]")
            self.console.print("[dim]  2. Judge identified missing quality signals[/dim]")
            self.console.print("[dim]  3. Resonance fed structured feedback to the model[/dim]")
            self.console.print("[dim]  4. Model revealed production-quality code it knew[/dim]")
            self.console.print()
            self.console.print("[dim]Prism Principle: small models contain multitudes.[/dim]")
            self.console.print("[dim]Sunwell's architecture reveals what's already there.[/dim]")
            self.console.print()

        self.console.print("[bold]Next steps:[/bold]")
        self.console.print('  sunwell "your goal here"    [dim]Run your own task[/dim]')
        self.console.print("  sunwell chat                [dim]Interactive conversation[/dim]")
        self.console.print("  sunwell --help              [dim]See all commands[/dim]")
        self.console.print()

    def _truncate_code(self, code: str, max_lines: int = 15) -> str:
        """Truncate code for display, keeping it readable."""
        # Extract from markdown if present
        if "```" in code:
            import re
            match = re.search(r"```(?:python)?\n(.*?)```", code, re.DOTALL)
            if match:
                code = match.group(1)

        lines = code.strip().split("\n")
        if len(lines) <= max_lines:
            return code.strip()

        # Show first and last lines with ellipsis
        half = max_lines // 2
        truncated = [*lines[:half], "  # ... (truncated) ...", *lines[-half:]]
        return "\n".join(truncated)

    def _score_color(self, score: float) -> str:
        """Get color based on score."""
        if score >= 8:
            return "green"
        elif score >= 5:
            return "yellow"
        else:
            return "red"


class QuietPresenter:
    """Minimal presenter for --quiet mode."""

    def __init__(self) -> None:
        self.console = Console()

    def present(self, comparison: DemoComparison, model_name: str = "unknown") -> None:
        """Show minimal output."""
        single = comparison.single_score.score
        sunwell = comparison.sunwell_score.score
        improvement = comparison.improvement_percent

        self.console.print(
            f"Single-shot: {single}/10 | Sunwell: {sunwell}/10 | +{improvement:.0f}%"
        )


class JsonPresenter:
    """JSON presenter for --json mode.

    Uses plain print() to avoid Rich Console adding ANSI escape codes
    which break JSON parsing in the Tauri frontend.
    """

    def __init__(self, include_code: bool = True) -> None:
        """Initialize JSON presenter.

        Args:
            include_code: Whether to include actual code in output.
        """
        self.include_code = include_code

    def present(self, comparison: DemoComparison, model_name: str = "unknown") -> None:
        """Output as JSON.

        Uses plain print() (not Rich Console) to ensure clean JSON output
        without ANSI escape codes or control characters.
        """
        import json

        single_shot_data = {
            "score": comparison.single_score.score,
            "lines": comparison.single_score.lines,
            "time_ms": comparison.single_shot.time_ms,
            "features": comparison.single_score.features,
            "tokens": {
                "prompt": comparison.single_shot.prompt_tokens,
                "completion": comparison.single_shot.completion_tokens,
                "total": comparison.single_shot.total_tokens,
            },
        }

        sunwell_data = {
            "score": comparison.sunwell_score.score,
            "lines": comparison.sunwell_score.lines,
            "time_ms": comparison.sunwell.time_ms,
            "iterations": comparison.sunwell.iterations,
            "features": comparison.sunwell_score.features,
            "tokens": {
                "prompt": comparison.sunwell.prompt_tokens,
                "completion": comparison.sunwell.completion_tokens,
                "total": comparison.sunwell.total_tokens,
            },
        }

        # Include code if requested (default: yes)
        if self.include_code:
            single_shot_data["code"] = self._extract_code(comparison.single_shot.code)
            sunwell_data["code"] = self._extract_code(comparison.sunwell.code)

        # Include component breakdown if available
        breakdown_data = None
        if comparison.sunwell.breakdown:
            bd = comparison.sunwell.breakdown
            breakdown_data = {
                "lens": {
                    "name": bd.lens_name,
                    "detected": bd.lens_detected,
                    "heuristics_applied": list(bd.heuristics_applied),
                },
                "prompt": {
                    "type": bd.prompt_type,
                    "requirements_added": list(bd.requirements_added),
                },
                "judge": {
                    "score": bd.judge_score,
                    "issues": list(bd.judge_issues),
                    "passed": bd.judge_passed,
                },
                "resonance": {
                    "triggered": bd.resonance_triggered,
                    "succeeded": bd.resonance_succeeded,
                    "iterations": bd.resonance_iterations,
                    "improvements": list(bd.resonance_improvements),
                },
                "result": {
                    "final_score": bd.final_score,
                    "features_achieved": list(bd.features_achieved),
                    "features_missing": list(bd.features_missing),
                },
            }

        data = {
            "model": model_name,
            "task": {
                "name": comparison.task.name,
                "prompt": comparison.task.prompt,
            },
            "single_shot": single_shot_data,
            "sunwell": sunwell_data,
            "improvement_percent": round(comparison.improvement_percent, 1),
        }

        # Add breakdown to the output (shows what each component contributed)
        if breakdown_data:
            data["breakdown"] = breakdown_data

        # Use plain print() to avoid Rich Console ANSI escape codes
        print(json.dumps(data, indent=2))

    def _extract_code(self, code: str) -> str:
        """Extract code from markdown if present and sanitize."""
        from sunwell.models import sanitize_llm_content

        if "```" in code:
            import re

            match = re.search(r"```(?:python)?\n(.*?)```", code, re.DOTALL)
            code = match.group(1).strip() if match else code.strip()
        else:
            code = code.strip()

        # Use existing sanitization (RFC-091)
        return sanitize_llm_content(code) or ""
