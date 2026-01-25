"""Shortcut execution system (RFC-107, RFC-109).

Provides direct invocation of skill shortcuts via the -s flag:

    sunwell -s a-2 docs/api.md        # Deep audit
    sunwell -s health                  # Health check
    sunwell -s p docs/overview.md     # Polish document

This module handles shortcut resolution, context building, and skill execution.
Migrated from do_cmd.py as part of RFC-109 CLI simplification.
"""

import contextlib
import re
import subprocess
from pathlib import Path

import click

from sunwell.cli.theme import create_sunwell_console

console = create_sunwell_console()


# ============================================================================
# Shell Completion (preserved from do_cmd.py)
# ============================================================================


def get_default_shortcuts() -> dict[str, str]:
    """Get shortcuts from default lens without full initialization.

    This provides a fast path for shell completion before full lens loading.
    Returns mapping of shortcut (without ::) to skill name.
    """
    return {
        # Audit & Validation
        "a": "audit-documentation",
        "a-2": "audit-documentation-deep",
        "health": "check-health",
        "score": "score-confidence",
        "drift": "detect-drift",
        "lint": "lint-structure",
        "vdr": "assess-vdr",
        "examples": "audit-code-examples",
        "readability": "check-readability",
        # Transformation
        "p": "polish-documentation",
        "m": "modularize-content",
        "md": "fix-markdown-syntax",
        "rst": "fix-rst-syntax",
        "fm": "generate-frontmatter",
        "style": "apply-style-guide",
        # Creation
        "overview": "create-overview-page",
        "architecture": "create-architecture-page",
        "features": "create-features-page",
        "ecosystem": "create-ecosystem-page",
        "map": "generate-navigation-map",
        # Pipelines
        "pipeline": "docs-pipeline",
        "swarm": "all-personas",
        # Utilities
        "r": "research-verify",
        "retro": "run-retrospective",
        "verify": "verify-claims",
    }


def complete_shortcut(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[str]:
    """Shell completion for shortcuts."""
    shortcuts = list(get_default_shortcuts().keys())
    # Handle both with and without :: prefix
    incomplete_clean = incomplete.lstrip(":")
    return [s for s in shortcuts if s.startswith(incomplete_clean)]


def complete_target(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[str]:
    """Shell completion for file paths."""
    base = Path(incomplete).parent if incomplete else Path(".")
    prefix = Path(incomplete).name if incomplete else ""

    completions = []
    try:
        for path in base.iterdir():
            if path.name.startswith("."):
                continue
            if path.name.startswith(prefix):
                if path.is_dir():
                    completions.append(f"{path}/")
                elif path.suffix in (
                    ".md",
                    ".rst",
                    ".txt",
                    ".py",
                    ".yaml",
                    ".yml",
                    ".json",
                    ".toml",
                ):
                    completions.append(str(path))
    except OSError:
        pass

    return sorted(completions)[:20]


# ============================================================================
# Shortcut Execution
# ============================================================================


async def run_shortcut(
    shortcut: str,
    target: str | None,
    context_str: str | None,
    lens_name: str,
    provider: str | None,
    model: str | None,
    plan_only: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Execute a shortcut command.

    Args:
        shortcut: Shortcut name (e.g., "a-2", "::a-2", "p")
        target: Target file/directory
        context_str: Additional context instructions
        lens_name: Lens to use
        provider: Model provider override
        model: Model name override
        plan_only: Show plan without executing
        json_output: Output as JSON
        verbose: Show detailed output
    """
    from sunwell.cli.helpers import resolve_model
    from sunwell.schema.loader import LensLoader
    from sunwell.skills.executor import SkillExecutor

    # Normalize shortcut (remove :: prefix if present)
    shortcut_clean = shortcut.lstrip(":")

    # Handle help shortcuts
    if shortcut_clean in ("?", "h", "help"):
        _show_shortcut_help()
        return

    # 1. Load lens
    loader = LensLoader()
    lens = await _resolve_lens(loader, lens_name)
    if not lens:
        console.print(f"[red]Lens not found:[/red] {lens_name}")
        return

    # 2. Resolve shortcut → skill
    if not lens.router or not lens.router.shortcuts:
        console.print("[red]Lens has no shortcuts defined[/red]")
        return

    # Try with and without :: prefix
    skill_name = lens.router.shortcuts.get(f"::{shortcut_clean}")
    if not skill_name:
        skill_name = lens.router.shortcuts.get(shortcut_clean)
    if not skill_name:
        # Fallback to default shortcuts
        skill_name = get_default_shortcuts().get(shortcut_clean)

    if not skill_name:
        console.print(f"[red]Unknown shortcut:[/red] {shortcut}")
        available = ", ".join(sorted(get_default_shortcuts().keys()))
        console.print(f"[dim]Available shortcuts: {available}[/dim]")
        return

    # 3. Find skill in lens
    skill = lens.get_skill(skill_name)
    if not skill:
        console.print(f"[red]Skill not found in lens:[/red] {skill_name}")
        return

    if verbose:
        console.print(f"[dim]Shortcut {shortcut} → skill {skill_name}[/dim]")

    # 4. Detect workspace
    workspace_root = _detect_workspace()
    if verbose and workspace_root:
        console.print(f"[dim]Workspace: {workspace_root}[/dim]")

    # 5. Build rich context
    context = await _build_skill_context(target, workspace_root)

    if plan_only:
        _show_execution_plan(
            shortcut, skill_name, skill, lens, target, context, verbose
        )
        return

    # 6. Create model
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider, model)
    except Exception as e:
        console.print(f"[red]Failed to create model:[/red] {e}")
        return

    if not synthesis_model:
        console.print("[red]No model available. Run 'sunwell setup' first.[/red]")
        return

    # 7. Create tool executor (RFC-117: with project context if available)
    from sunwell.project import ProjectResolutionError, resolve_project
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    workspace = workspace_root or Path.cwd()
    project = None
    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError:
        pass

    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace if project is None else None,
        policy=ToolPolicy(
            trust_level=ToolTrust.WORKSPACE,
            allowed_tools=skill.allowed_tools,
        ),
    )

    # 8. Execute skill
    executor = SkillExecutor(
        skill=skill,
        lens=lens,
        model=synthesis_model,
        workspace_root=workspace_root,
    )

    # Filter context to only string values
    exec_context: dict[str, str] = {
        k: v for k, v in context.items() if isinstance(v, str)
    }

    # Build explicit task description with document content
    task_parts = []
    if target:
        task_parts.append(f"**Target Document**: `{target}`")
    if context.get("diataxis_type"):
        task_parts.append(f"**Detected Diataxis Type**: {context['diataxis_type']}")
    if context_str:
        task_parts.append(f"**Additional Instructions**: {context_str}")
    if context.get("file_content"):
        content = context["file_content"]
        if len(content) > 50000:
            content = content[:50000] + "\n\n... [TRUNCATED - file too long] ..."
        task_parts.append(
            f"\n---\n\n**Document Content to Analyze**:\n\n```markdown\n{content}\n```"
        )

    if task_parts:
        exec_context["task"] = "\n".join(task_parts)

    # 9. Execute in agentic mode
    def on_tool_call(tool_name: str, args: dict) -> None:
        args_preview = ", ".join(
            f"{k}={repr(v)[:30]}" for k, v in list(args.items())[:2]
        )
        console.print(f"  [holy.radiant]✧ {tool_name}[/] [neutral.dim]({args_preview})[/]")

    def on_tool_result(tool_name: str, success: bool, output: str) -> None:
        if success:
            preview = output.replace("\n", " ")[:80]
            console.print(f"    [holy.success]✓[/] [neutral.dim]{preview}...[/]")
        else:
            console.print(f"    [void.purple]✗[/] {output[:100]}")

    if not json_output:
        console.print("[holy.radiant]◎ Executing...[/holy.radiant]")
        console.print("[neutral.dim]Agent can read files, search code, and iterate.[/]\n")

    result = await executor.execute(
        context=exec_context,
        validate=True,
        dry_run=False,
        agentic=True,
        max_tool_iterations=20,
        tool_executor=tool_executor,
        on_tool_call=on_tool_call if not json_output else None,
        on_tool_result=on_tool_result if not json_output else None,
    )

    # 10. Display result
    if json_output:
        import json as json_module
        output = {
            "shortcut": shortcut,
            "skill": skill_name,
            "target": target,
            "execution_time_ms": result.execution_time_ms,
            "confidence": result.confidence,
            "validation_passed": result.validation_passed,
            "content": result.content,
        }
        click.echo(json_module.dumps(output, indent=2))
    else:
        if verbose:
            console.print("\n[holy.radiant]Execution:[/holy.radiant]")
            console.print(f"  Time: {result.execution_time_ms}ms")
            v_icon = "★" if result.validation_passed else "△"
            console.print(f"  Validation: {v_icon} ({result.confidence:.0%})")
            if result.scripts_run:
                console.print(f"  Scripts: {', '.join(result.scripts_run)}")
            if result.refinement_count:
                console.print(f"  Refinements: {result.refinement_count}")
            console.print()

        console.print(result.content)


# ============================================================================
# Helper Functions
# ============================================================================


async def _resolve_lens(loader, lens_name: str):  # type: ignore[no-untyped-def]
    """Resolve lens by name, checking built-in and local paths."""
    from sunwell.core.types import LensReference
    from sunwell.fount.resolver import LensResolver

    resolver = LensResolver(loader=loader)

    # Try built-in lenses first
    builtin_paths = [
        Path(__file__).parent.parent.parent.parent / "lenses" / f"{lens_name}.lens",
        Path.cwd() / "lenses" / f"{lens_name}.lens",
        Path.cwd() / f"{lens_name}.lens",
    ]

    for path in builtin_paths:
        if path.exists():
            try:
                return loader.load(path)
            except Exception:
                continue

    # Try as a reference
    try:
        ref = LensReference(source=lens_name)
        return await resolver.resolve(ref)
    except Exception:
        pass

    return None


def _detect_workspace() -> Path | None:
    """Detect workspace root directory."""
    try:
        from sunwell.workspace.detector import WorkspaceDetector

        detector = WorkspaceDetector()
        workspace = detector.detect()
        return workspace.root
    except Exception:
        return Path.cwd()


async def _build_skill_context(
    target: str | None, workspace_root: Path | None
) -> dict[str, str | list[dict[str, str]]]:
    """Build rich context for skill execution."""
    context: dict[str, str | list[dict[str, str]]] = {}

    if workspace_root:
        context["workspace_root"] = str(workspace_root)

    if not target:
        return context

    target_path = Path(target).expanduser()
    if not target_path.is_absolute() and workspace_root:
        target_path = workspace_root / target_path

    if not target_path.exists():
        context["target"] = target
        return context

    # Basic file info
    context["target_file"] = str(target_path)
    with contextlib.suppress(Exception):
        context["file_content"] = target_path.read_text()
    context["file_type"] = target_path.suffix.lstrip(".")

    # Find related files
    if workspace_root:
        related = _find_related_files(target_path, workspace_root)
        if related:
            context["related_files"] = related

    # Git context
    git_diff = _get_git_diff(target_path)
    if git_diff:
        context["uncommitted_changes"] = git_diff

    # Diataxis type detection
    if target_path.suffix in (".md", ".rst"):
        diataxis_type = _detect_diataxis_type(target_path)
        if diataxis_type:
            context["diataxis_type"] = diataxis_type

    # Semantic context
    if workspace_root:
        semantic_context = await _get_semantic_context(target_path, workspace_root)
        if semantic_context:
            context["semantic_code_context"] = semantic_context

    return context


async def _get_semantic_context(target_path: Path, workspace_root: Path) -> str | None:
    """Get semantic code context using SmartContext."""
    try:
        from sunwell.indexing import create_smart_context
    except ImportError:
        return None

    try:
        smart_ctx = create_smart_context(workspace_root=workspace_root)
        file_content = target_path.read_text()

        query_parts = []
        if target_path.suffix in (".md", ".rst"):
            code_refs = re.findall(r"`([a-z_][a-z0-9_\.]+)`", file_content, re.I)
            query_parts.extend(code_refs[:10])
        elif target_path.suffix == ".py":
            query_parts.append(target_path.stem)
            imports = re.findall(r"from\s+(\S+)\s+import|import\s+(\S+)", file_content)
            for imp in imports[:5]:
                query_parts.extend([p for p in imp if p])

        if not query_parts:
            return None

        query = " ".join(query_parts[:10])
        result = await smart_ctx.get_context(query, max_chunks=3)

        if result.content:
            return result.content

    except Exception:
        pass

    return None


def _find_related_files(target: Path, workspace: Path) -> list[dict[str, str]]:
    """Find files related to target."""
    related: list[dict[str, str]] = []
    stem = target.stem

    for pattern in [f"test_{stem}.py", f"{stem}_test.py", f"test_{stem}.ts"]:
        for match in workspace.rglob(pattern):
            related.append({"path": str(match), "relation": "test"})
            if len(related) >= 5:
                return related

    if target.suffix in (".md", ".rst"):
        try:
            content = target.read_text()
            for match in re.findall(r"`([a-z_/]+\.py)`", content):
                impl_path = workspace / match
                if impl_path.exists():
                    related.append({"path": str(impl_path), "relation": "implementation"})
                    if len(related) >= 5:
                        return related
        except Exception:
            pass

    return related[:5]


def _get_git_diff(target: Path) -> str | None:
    """Get uncommitted changes for target file."""
    try:
        result = subprocess.run(
            ["git", "diff", "--", str(target)],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=target.parent,
        )
        return result.stdout if result.stdout else None
    except Exception:
        return None


def _detect_diataxis_type(target: Path) -> str | None:
    """Detect Diataxis document type from content."""
    try:
        content = target.read_text().lower()
    except Exception:
        return None

    if any(
        word in content
        for word in ["step 1", "step 2", "in this tutorial", "you will learn"]
    ):
        return "TUTORIAL"
    if any(word in content for word in ["how to", "guide", "troubleshooting"]):
        return "HOW-TO"
    if any(
        word in content
        for word in ["api reference", "parameters:", "returns:", "arguments:"]
    ):
        return "REFERENCE"
    if any(
        word in content for word in ["architecture", "how it works", "design", "concepts"]
    ):
        return "EXPLANATION"

    return None


def _show_execution_plan(
    shortcut: str,
    skill_name: str,
    skill,
    lens,
    target: str | None,
    context: dict,
    verbose: bool,
) -> None:
    """Show a rich execution plan preview."""
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table

    console.print()
    console.print(
        Panel(
            f"[holy.radiant]✧ Execution Plan: {shortcut}[/holy.radiant]",
            subtitle=f"[neutral.dim]{skill_name}[/neutral.dim]",
            border_style="holy.gold",
        )
    )

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="sunwell.heading")
    info_table.add_column("Value")

    info_table.add_row("Skill", f"[holy.success]{skill_name}[/holy.success]")
    info_table.add_row("Description", skill.description)
    info_table.add_row("Lens", f"{lens.metadata.name} v{lens.metadata.version}")
    info_table.add_row("Trust Level", f"[holy.gold]{skill.trust.value}[/holy.gold]")

    if skill.allowed_tools:
        tools = ", ".join(skill.allowed_tools)
        info_table.add_row("Tools", f"[neutral.dim]{tools}[/neutral.dim]")

    if skill.preset:
        info_table.add_row("Preset", f"[void.purple]{skill.preset}[/void.purple]")

    console.print(info_table)
    console.print()

    console.print("[sunwell.heading]▢ Context Injection:[/sunwell.heading]")
    ctx_table = Table(show_header=False, box=None, padding=(0, 2))
    ctx_table.add_column("Key", style="holy.radiant")
    ctx_table.add_column("Value")

    if target:
        ctx_table.add_row("Target", target)

    if context.get("workspace_root"):
        ctx_table.add_row("Workspace", context["workspace_root"])

    if context.get("file_type"):
        ctx_table.add_row("File Type", context["file_type"])

    if context.get("diataxis_type"):
        ctx_table.add_row("Diataxis", f"[holy.success]{context['diataxis_type']}[/]")

    if context.get("related_files"):
        related = context["related_files"]
        for i, rf in enumerate(related[:3]):
            label = "Related" if i == 0 else ""
            rel_type = rf.get("relation", "")
            ctx_table.add_row(label, f"[neutral.dim]{rf['path']}[/] ({rel_type})")
        if len(related) > 3:
            ctx_table.add_row("", f"[neutral.dim]... and {len(related) - 3} more[/]")

    if context.get("uncommitted_changes"):
        diff_lines = context["uncommitted_changes"].count("\n")
        ctx_table.add_row("Git Diff", f"[holy.gold]{diff_lines} uncommitted lines[/]")

    if context.get("file_content"):
        lines = context["file_content"].count("\n")
        ctx_table.add_row("Content", f"{lines} lines loaded")

    console.print(ctx_table)
    console.print()

    if skill.instructions and verbose:
        console.print("[sunwell.heading]≡ Skill Instructions:[/sunwell.heading]")
        console.print(Panel(
            Markdown(skill.instructions),
            border_style="neutral.dim",
            title="[neutral.dim]What the AI will do[/neutral.dim]",
            title_align="left",
        ))
        console.print()

    if skill.validate_with:
        console.print("[sunwell.heading]★ Validation:[/sunwell.heading]")
        val_table = Table(show_header=False, box=None, padding=(0, 2))
        val_table.add_column("Key", style="neutral.dim")
        val_table.add_column("Value")

        if skill.validate_with.validators:
            val_table.add_row("Validators", ", ".join(skill.validate_with.validators))
        if skill.validate_with.personas:
            val_table.add_row("Personas", ", ".join(skill.validate_with.personas))
        val_table.add_row(
            "Min Confidence", f"{skill.validate_with.min_confidence:.0%}"
        )
        console.print(val_table)
        console.print()

    console.print("━" * 50)
    console.print("[bold green]Ready to execute![/bold green]")
    console.print()
    cmd = f"sunwell -s {shortcut}"
    if target:
        cmd += f" {target}"
    console.print(f"  Run: [cyan]{cmd}[/cyan]")
    if not verbose:
        console.print(f"  More detail: [dim]{cmd} --plan --verbose[/dim]")
    console.print()


def _show_shortcut_help() -> None:
    """Show available shortcuts and their descriptions."""
    shortcuts = get_default_shortcuts()

    audit_keywords = ("audit", "check", "score", "drift", "lint", "vdr", "readability", "examples")
    creation_keywords = ("create", "generate")
    transform_keywords = ("polish", "modularize", "fix", "apply")

    audit_shortcuts = {
        k: v for k, v in shortcuts.items() if any(kw in v for kw in audit_keywords)
    }
    creation_shortcuts = {
        k: v for k, v in shortcuts.items() if any(kw in v for kw in creation_keywords)
    }
    transform_shortcuts = {
        k: v for k, v in shortcuts.items() if any(kw in v for kw in transform_keywords)
    }
    util_shortcuts = {
        k: v
        for k, v in shortcuts.items()
        if k not in audit_shortcuts
        and k not in creation_shortcuts
        and k not in transform_shortcuts
    }

    console.print("\n[bold cyan]📋 Available Shortcuts[/bold cyan]\n")

    console.print("[bold]Audit & Validation:[/bold]")
    for shortcut, skill in sorted(audit_shortcuts.items()):
        console.print(f"  [cyan]{shortcut:<14}[/cyan] {skill}")

    console.print("\n[bold]Content Creation:[/bold]")
    for shortcut, skill in sorted(creation_shortcuts.items()):
        console.print(f"  [cyan]{shortcut:<14}[/cyan] {skill}")

    console.print("\n[bold]Transformation:[/bold]")
    for shortcut, skill in sorted(transform_shortcuts.items()):
        console.print(f"  [cyan]{shortcut:<14}[/cyan] {skill}")

    console.print("\n[bold]Utilities:[/bold]")
    for shortcut, skill in sorted(util_shortcuts.items()):
        console.print(f"  [cyan]{shortcut:<14}[/cyan] {skill}")

    console.print("\n[dim]Usage: sunwell -s a-2 docs/api.md[/dim]")
    console.print("[dim]       sunwell -s a-2 docs/api.md \"focus on API examples\"[/dim]")
    console.print("[dim]Tip: Use --verbose for detailed execution info[/dim]")
