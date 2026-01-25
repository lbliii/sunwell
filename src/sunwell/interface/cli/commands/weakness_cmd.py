"""RFC-063: Weakness CLI commands.

Commands for analyzing and fixing code weaknesses using DAG cascade.
"""

import asyncio
import json
import sys
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from sunwell.planning.naaru.artifacts import ArtifactGraph


def get_project_root(ctx: click.Context) -> Path:
    """Get project root from context or current directory."""
    # Check if workspace was set in context
    if ctx.obj and isinstance(ctx.obj, dict):
        if "workspace" in ctx.obj:
            return Path(ctx.obj["workspace"])
    # Fall back to current directory
    return Path.cwd()


@click.group()
def weakness() -> None:
    """Analyze and fix code weaknesses using DAG cascade."""
    pass


@weakness.command()
@click.option("--min-severity", default=0.3, help="Minimum severity to report (0.0-1.0)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def scan(ctx: click.Context, min_severity: float, as_json: bool) -> None:
    """Scan codebase for weaknesses."""
    project_root = get_project_root(ctx)

    async def _scan() -> dict[str, Any]:
        from sunwell.quality.weakness.analyzer import WeaknessAnalyzer

        # Build artifact graph from project
        graph = await _build_graph(project_root)

        analyzer = WeaknessAnalyzer(
            graph=graph,
            project_root=project_root,
        )

        scores = await analyzer.scan()

        # Filter by severity
        scores = [s for s in scores if s.total_severity >= min_severity]

        # Build report
        report = {
            "project_path": str(project_root),
            "scan_time": _timestamp(),
            "weaknesses": [
                {
                    "artifact_id": s.artifact_id,
                    "file_path": str(s.file_path),
                    "signals": [
                        {
                            "artifact_id": sig.artifact_id,
                            "file_path": str(sig.file_path),
                            "weakness_type": sig.weakness_type.value,
                            "severity": sig.severity,
                            "evidence": sig.evidence,
                        }
                        for sig in s.signals
                    ],
                    "fan_out": s.fan_out,
                    "depth": s.depth,
                    "total_severity": s.total_severity,
                    "cascade_risk": s.cascade_risk,
                }
                for s in scores
            ],
            "total_files_scanned": len(graph),
            "critical_count": sum(1 for s in scores if s.cascade_risk == "critical"),
            "high_count": sum(1 for s in scores if s.cascade_risk == "high"),
            "medium_count": sum(1 for s in scores if s.cascade_risk == "medium"),
            "low_count": sum(1 for s in scores if s.cascade_risk == "low"),
        }

        return report

    report = asyncio.run(_scan())

    if as_json:
        click.echo(json.dumps(report, indent=2))
    else:
        _print_scan_report(report)


@weakness.command()
@click.argument("artifact_id")
@click.option("--max-depth", default=5, help="Maximum cascade depth")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def preview(ctx: click.Context, artifact_id: str, max_depth: int, as_json: bool) -> None:
    """Preview cascade impact for a weak artifact."""
    project_root = get_project_root(ctx)

    async def _preview() -> dict[str, Any]:
        from sunwell.quality.weakness.analyzer import WeaknessAnalyzer
        from sunwell.quality.weakness.cascade import CascadeEngine

        graph = await _build_graph(project_root)

        # Find the weakness for this artifact
        analyzer = WeaknessAnalyzer(graph=graph, project_root=project_root)
        scores = await analyzer.scan()

        weakness = next((s for s in scores if s.artifact_id == artifact_id), None)
        if not weakness:
            return {"error": f"No weakness found for {artifact_id}"}

        # Preview cascade
        engine = CascadeEngine(
            graph=graph,
            project_root=project_root,
            max_cascade_depth=max_depth,
        )

        preview_result = await engine.preview_with_contracts(weakness)
        return preview_result.to_dict()

    result = asyncio.run(_preview())

    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        if "error" in result:
            click.echo(f"⊗ {result['error']}", err=True)
            sys.exit(1)
        _print_preview(result)


@weakness.command()
@click.argument("artifact_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--json", "as_json", is_flag=True, help="Output progress as JSON events")
@click.option("--wave-by-wave", is_flag=True, help="Approve each wave manually")
@click.option("--show-deltas", is_flag=True, help="Show diffs before executing")
@click.option(
    "--confidence-threshold", default=0.7, help="Min confidence to auto-proceed"
)
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama"]),
              default=None, help="Model provider (default: from config)")
@click.option("--model", "-m", default=None, help="Override model (e.g., gemma3:4b)")
@click.pass_context
def fix(
    ctx: click.Context,
    artifact_id: str,
    yes: bool,
    dry_run: bool,
    as_json: bool,
    wave_by_wave: bool,
    show_deltas: bool,
    confidence_threshold: float,
    provider: str | None,
    model: str | None,
) -> None:
    """Fix a weak artifact and all dependents.

    By default, executes all waves after initial approval.
    Use --wave-by-wave to approve each wave individually.
    Use --show-deltas to preview exact changes before executing.

    Confidence scoring (0.0-1.0) tracks:
    - Tests passed (+0.4)
    - Types clean (+0.2)
    - Lint clean (+0.1)
    - Contracts preserved (+0.3)

    If confidence drops below threshold, execution pauses for review.

    ESCALATION: If 2+ consecutive waves have low confidence, the cascade
    is escalated to full human review.
    """
    project_root = get_project_root(ctx)

    async def _fix() -> dict[str, Any]:
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner
        from sunwell.tools.executor import ToolExecutor
        from sunwell.quality.weakness.analyzer import WeaknessAnalyzer
        from sunwell.quality.weakness.cascade import CascadeEngine
        from sunwell.quality.weakness.executor import CascadeExecutor
        from sunwell.quality.weakness.types import WaveConfidence

        graph = await _build_graph(project_root)

        # Find the weakness
        analyzer = WeaknessAnalyzer(graph=graph, project_root=project_root)
        scores = await analyzer.scan()

        weakness = next((s for s in scores if s.artifact_id == artifact_id), None)
        if not weakness:
            return {"error": f"No weakness found for {artifact_id}"}

        engine = CascadeEngine(graph=graph, project_root=project_root)

        # Get preview with contracts
        preview_result = await engine.preview_with_contracts(weakness, include_deltas=show_deltas)

        if dry_run:
            result = preview_result.to_dict()
            result["tasks"] = engine.compute_regeneration_tasks(preview_result)
            return result

        # Create model and planner using resolve_model()
        from sunwell.interface.cli.helpers import resolve_model
        from sunwell.knowledge.project import ProjectResolutionError, resolve_project

        resolved_model = resolve_model(provider, model)
        planner = ArtifactPlanner(model=resolved_model)

        # RFC-117: Try to resolve project context
        project = None
        try:
            project = resolve_project(project_root=project_root)
        except ProjectResolutionError:
            pass

        tool_executor = ToolExecutor(
            project=project,
            workspace=project_root if project is None else None,
        )

        def emit_json(event: Any) -> None:
            if as_json:
                click.echo(json.dumps(event.to_dict()), nl=True)
                sys.stdout.flush()

        executor = CascadeExecutor(
            engine=engine,
            planner=planner,
            tool_executor=tool_executor,
            project_root=project_root,
            on_event=emit_json if as_json else None,
        )

        # Execute with wave-by-wave callbacks
        async def on_wave_complete(confidence: WaveConfidence) -> bool:
            if as_json:
                click.echo(
                    json.dumps(
                        {
                            "event": "wave_complete",
                            "wave_num": confidence.wave_num,
                            "confidence": confidence.confidence,
                            "deductions": list(confidence.deductions),
                        }
                    )
                )
            else:
                _print_wave_confidence(confidence)

            if wave_by_wave and not yes:
                return click.confirm("Continue to next wave?", default=True)
            return confidence.should_continue

        execution = await executor.execute(
            preview=preview_result,
            auto_approve=not wave_by_wave,
            confidence_threshold=confidence_threshold,
            on_wave_complete=on_wave_complete,
        )

        return execution.to_dict()

    # Confirmation prompt
    if not yes and not dry_run:
        click.echo(f"⚠️  This will regenerate {artifact_id} and all its dependents.")
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            sys.exit(0)

    result = asyncio.run(_fix())

    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        if "error" in result:
            click.echo(f"⊗ {result['error']}", err=True)
            sys.exit(1)
        if dry_run:
            _print_dry_run(result)
        else:
            _print_execution_result(result)


@weakness.command("extract-contract")
@click.argument("artifact_id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def extract_contract(ctx: click.Context, artifact_id: str, as_json: bool) -> None:
    """Extract and display the public interface contract for a file.

    Shows:
    - Public function signatures
    - Public class definitions
    - Module exports (__all__)
    - Key type annotations

    Useful for understanding what must be preserved during regeneration.
    """
    project_root = get_project_root(ctx)

    async def _extract() -> dict[str, Any]:
        from sunwell.quality.weakness.cascade import CascadeEngine

        graph = await _build_graph(project_root)
        engine = CascadeEngine(graph=graph, project_root=project_root)

        try:
            contract = await engine.extract_contract(artifact_id)
            return {
                "artifact_id": contract.artifact_id,
                "file_path": str(contract.file_path),
                "functions": list(contract.functions),
                "classes": list(contract.classes),
                "exports": list(contract.exports),
                "interface_hash": contract.interface_hash,
            }
        except KeyError:
            return {"error": f"Artifact not found: {artifact_id}"}

    result = asyncio.run(_extract())

    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        if "error" in result:
            click.echo(f"⊗ {result['error']}", err=True)
            sys.exit(1)
        _print_contract(result)


# =============================================================================
# Helpers
# =============================================================================


async def _build_graph(project_root: Path) -> ArtifactGraph:
    """Build artifact graph from project files."""
    from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec

    # Scan for Python files
    graph = ArtifactGraph()
    src_dir = project_root / "src"
    if not src_dir.exists():
        src_dir = project_root

    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        rel_path = py_file.relative_to(project_root)
        artifact = ArtifactSpec(
            id=str(rel_path),
            description=f"Python module: {rel_path}",
            contract="",
            produces_file=str(rel_path),
            requires=frozenset(),  # Would need import analysis for real deps
        )
        graph.add(artifact)

    return graph


def _timestamp() -> str:
    """Get ISO timestamp."""
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _print_scan_report(report: dict[str, Any]) -> None:
    """Print human-readable scan report."""
    click.echo("◈ Weakness Report")
    click.echo("─" * 60)
    click.echo(f"Files scanned: {report['total_files_scanned']}")
    click.echo(
        f"Critical: {report['critical_count']} | "
        f"High: {report['high_count']} | "
        f"Medium: {report['medium_count']} | "
        f"Low: {report['low_count']}"
    )
    click.echo()

    if report["weaknesses"]:
        click.echo("Top weaknesses:")
        for w in report["weaknesses"][:10]:
            types = ", ".join(s["weakness_type"] for s in w["signals"])
            risk = w["cascade_risk"].upper()
            click.echo(f"  ▸ {w['file_path']}")
            click.echo(f"    {types} │ Severity: {w['total_severity']:.0%} │ Risk: {risk}")
            click.echo(f"    → {w['fan_out']} dependents")
    else:
        click.echo("◆ No weaknesses found above threshold.")


def _print_preview(preview: dict[str, Any]) -> None:
    """Print human-readable cascade preview."""
    click.echo(f"⟁ Cascade Preview: {preview['weak_node']}")
    click.echo("─" * 60)
    click.echo(f"Weakness: {', '.join(preview['weakness_types'])} ({preview['severity']:.0%})")
    click.echo(f"Risk: {preview['cascade_risk'].upper()}")
    click.echo()
    click.echo("Cascade Impact:")
    click.echo(f"  Direct dependents: {len(preview['direct_dependents'])}")
    click.echo(f"  Transitive dependents: {len(preview['transitive_dependents'])}")
    click.echo(f"  Total impacted: {preview['total_impacted']} files")
    click.echo()
    click.echo("Regeneration Waves:")
    for i, wave in enumerate(preview["waves"]):
        click.echo(f"  Wave {i}: {', '.join(wave[:3])}{'...' if len(wave) > 3 else ''}")
    click.echo()
    click.echo(f"Estimated effort: {preview['estimated_effort']}")
    click.echo(f"Risk: {preview['risk_assessment']}")


def _print_wave_confidence(confidence: Any) -> None:
    """Print wave confidence result."""
    status = "◆" if confidence.confidence >= 0.7 else "▲"
    click.echo(f"\n{status} Wave {confidence.wave_num} Confidence: {confidence.confidence:.0%}")

    checks = [
        ("Tests", confidence.tests_passed),
        ("Types", confidence.types_clean),
        ("Lint", confidence.lint_clean),
        ("Contracts", confidence.contracts_preserved),
    ]
    for name, passed in checks:
        icon = "✓" if passed else "✗"
        click.echo(f"  {icon} {name}")

    if confidence.deductions:
        for d in confidence.deductions:
            click.echo(f"  ▲ {d}")


def _print_dry_run(result: dict[str, Any]) -> None:
    """Print dry-run task plan."""
    click.echo("◌ Dry Run ─ Task Plan")
    click.echo("─" * 60)
    for task in result.get("tasks", []):
        click.echo(f"  [{task.get('wave', '?')}] {task['id']}")
        click.echo(f"      {task['description'][:60]}...")
    click.echo()
    click.echo("Run without --dry-run to execute.")


def _print_execution_result(result: dict[str, Any]) -> None:
    """Print execution result."""
    if result.get("completed"):
        click.echo("◆ Cascade complete")
        click.echo(f"  Overall confidence: {result['overall_confidence']:.0%}")
        click.echo(f"  Waves completed: {len(result['wave_confidences'])}")
    elif result.get("aborted"):
        click.echo(f"⊗ Cascade aborted: {result.get('abort_reason', 'Unknown')}")
    else:
        click.echo(f"◐ Cascade paused at wave {result['current_wave']}")


def _print_contract(contract: dict[str, Any]) -> None:
    """Print extracted contract."""
    click.echo(f"⊟ Contract: {contract['artifact_id']}")
    click.echo("─" * 60)
    click.echo(f"File: {contract['file_path']}")
    click.echo(f"Hash: {contract['interface_hash']}")
    click.echo()

    if contract["functions"]:
        click.echo("Functions:")
        for f in contract["functions"]:
            click.echo(f"  {f}")

    if contract["classes"]:
        click.echo("\nClasses:")
        for c in contract["classes"]:
            click.echo(f"  {c}")

    if contract["exports"]:
        click.echo(f"\nExports: {', '.join(contract['exports'])}")
