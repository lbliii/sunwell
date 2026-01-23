"""Shortcut execution command (RFC-107).

Provides direct CLI invocation of DORI-compatible shortcuts:

    sunwell do ::a-2 docs/api.md        # Deep audit
    sunwell do ::health                  # Health check
    sunwell do ::p docs/overview.md     # Polish document

The core critical use case is making `sunwell do ::a-2 this doc` work
seamlessly with rich context injection.
"""


import asyncio
import contextlib
import re
import subprocess
from pathlib import Path

import click
from rich.console import Console

console = Console()


def _get_default_lens_shortcuts() -> dict[str, str]:
    """Get shortcuts from default lens without full initialization.

    This provides a fast path for shell completion before full lens loading.
    """
    return {
        "::a": "audit-documentation",
        "::a-2": "audit-documentation-deep",
        "::p": "polish-documentation",
        "::m": "modularize-content",
        "::health": "check-health",
        "::score": "score-confidence",
        "::drift": "detect-drift",
        "::lint": "lint-structure",
        "::vdr": "assess-vdr",
        "::examples": "audit-code-examples",
        "::readability": "check-readability",
        "::md": "fix-markdown-syntax",
        "::rst": "fix-rst-syntax",
        "::fm": "generate-frontmatter",
        "::overview": "create-overview-page",
        "::architecture": "create-architecture-page",
        "::features": "create-features-page",
        "::ecosystem": "create-ecosystem-page",
        "::map": "generate-navigation-map",
        "::style": "apply-style-guide",
        "::retro": "run-retrospective",
        "::?": "show-help",
        "::h": "show-help",
    }


def complete_shortcut(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[str]:
    """Complete shortcut commands from lens."""
    shortcuts = list(_get_default_lens_shortcuts().keys())
    return [s for s in shortcuts if s.startswith(incomplete)]


def complete_target(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[str]:
    """Complete file paths for target argument."""
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


@click.command("do")
@click.argument("shortcut", shell_complete=complete_shortcut)
@click.argument("target", required=False, shell_complete=complete_target)
@click.option("--lens", "-l", default="tech-writer", help="Lens to use")
@click.option("--provider", "-p", default=None, help="Model provider")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--dry-run", is_flag=True, help="Show what would be executed without running")
def do_cmd(
    shortcut: str,
    target: str | None,
    lens: str,
    provider: str | None,
    model: str | None,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Execute a shortcut command.

    Shortcuts are DORI-compatible command aliases that trigger skills.
    Use `sunwell do ::?` to see available shortcuts.

    \b
    Examples:
        sunwell do ::a-2 docs/api.md        # Deep audit
        sunwell do ::health                  # Health check
        sunwell do ::p docs/overview.md     # Polish document
        sunwell do ::?                       # Show available shortcuts
    """
    asyncio.run(
        _do_shortcut(shortcut, target, lens, provider, model, verbose, dry_run)
    )


async def _do_shortcut(
    shortcut: str,
    target: str | None,
    lens_name: str,
    provider: str | None,
    model: str | None,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Execute shortcut → skill pipeline."""
    from sunwell.cli.helpers import resolve_model
    from sunwell.schema.loader import LensLoader
    from sunwell.skills.executor import SkillExecutor

    # Handle special shortcuts
    if shortcut in ("::?", "::h", "::help"):
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

    # Normalize shortcut (add :: if missing)
    if not shortcut.startswith("::"):
        shortcut = f"::{shortcut}"

    skill_name = lens.router.shortcuts.get(shortcut)
    if not skill_name:
        # Try without :: prefix
        skill_name = lens.router.shortcuts.get(shortcut.lstrip(":"))

    if not skill_name:
        console.print(f"[red]Unknown shortcut:[/red] {shortcut}")
        available = ", ".join(sorted(lens.router.shortcuts.keys()))
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

    # 5. Build rich context (S-tier: smart context injection)
    context = await _build_skill_context(target, workspace_root)

    if dry_run:
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

    # 7. Create tool executor for agentic mode (model can use tools to explore)
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    tool_executor = ToolExecutor(
        workspace=workspace_root or Path.cwd(),
        policy=ToolPolicy(
            trust_level=ToolTrust.WORKSPACE,  # Read/write in workspace
            allowed_tools=skill.allowed_tools,  # Skill can restrict tools
        ),
    )

    # 8. Execute skill
    executor = SkillExecutor(
        skill=skill,
        lens=lens,
        model=synthesis_model,
        workspace_root=workspace_root,
    )

    # Filter context to only string values (executor expects dict[str, str])
    exec_context: dict[str, str] = {
        k: v for k, v in context.items() if isinstance(v, str)
    }

    # Build explicit task description with document content
    task_parts = []
    if target:
        task_parts.append(f"**Target Document**: `{target}`")
    if context.get("diataxis_type"):
        task_parts.append(f"**Detected Diataxis Type**: {context['diataxis_type']}")
    if context.get("file_content"):
        # Truncate very long files
        content = context["file_content"]
        if len(content) > 50000:
            content = content[:50000] + "\n\n... [TRUNCATED - file too long] ..."
        task_parts.append(
            f"\n---\n\n**Document Content to Analyze**:\n\n```markdown\n{content}\n```"
        )

    if task_parts:
        exec_context["task"] = "\n".join(task_parts)

    # 9. Execute in agentic mode - ALWAYS. The floor is agentic.
    # Even models without native tool calling use JSON emulation.

    # Callbacks for real-time progress
    def on_tool_call(tool_name: str, args: dict) -> None:
        args_preview = ", ".join(
            f"{k}={repr(v)[:30]}" for k, v in list(args.items())[:2]
        )
        console.print(f"  [cyan]⚡ {tool_name}[/cyan] [dim]({args_preview})[/dim]")

    def on_tool_result(tool_name: str, success: bool, output: str) -> None:
        if success:
            preview = output.replace("\n", " ")[:80]
            console.print(f"    [green]✓[/green] [dim]{preview}...[/dim]")
        else:
            console.print(f"    [red]✗[/red] {output[:100]}")

    console.print("[bold cyan]🤖 Executing...[/bold cyan]")
    console.print("[dim]Agent can read files, search code, and iterate.[/dim]\n")

    result = await executor.execute(
        context=exec_context,
        validate=True,
        dry_run=False,
        agentic=True,
        max_tool_iterations=20,
        tool_executor=tool_executor,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
    )

    # 10. Display result
    if verbose:
        console.print("\n[cyan]Execution:[/cyan]")
        console.print(f"  Time: {result.execution_time_ms}ms")
        validation_icon = "✅" if result.validation_passed else "⚠️"
        console.print(f"  Validation: {validation_icon} ({result.confidence:.0%})")
        if result.scripts_run:
            console.print(f"  Scripts: {', '.join(result.scripts_run)}")
        if result.refinement_count:
            console.print(f"  Refinements: {result.refinement_count}")
        console.print()

    console.print(result.content)


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
        # Fallback to cwd
        return Path.cwd()


async def _build_skill_context(
    target: str | None, workspace_root: Path | None
) -> dict[str, str | list[dict[str, str]]]:
    """Build rich context for skill execution (S-tier feature).

    RFC-108: Now uses SmartContext for semantic code retrieval.

    Goes beyond just file content to provide:
    - Related files (tests, implementations, schemas)
    - Git context (uncommitted changes)
    - Diataxis type detection
    - Semantic code context (RFC-108)
    """
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

    # S-tier: Find related files
    if workspace_root:
        related = _find_related_files(target_path, workspace_root)
        if related:
            context["related_files"] = related

    # S-tier: Git context for drift detection
    git_diff = _get_git_diff(target_path)
    if git_diff:
        context["uncommitted_changes"] = git_diff

    # S-tier: Diataxis type detection for docs
    if target_path.suffix in (".md", ".rst"):
        diataxis_type = _detect_diataxis_type(target_path)
        if diataxis_type:
            context["diataxis_type"] = diataxis_type

    # RFC-108: Add semantic code context if available
    if workspace_root:
        semantic_context = await _get_semantic_context(target_path, workspace_root)
        if semantic_context:
            context["semantic_code_context"] = semantic_context

    return context


async def _get_semantic_context(target_path: Path, workspace_root: Path) -> str | None:
    """Get semantic code context using RFC-108 SmartContext.

    Extracts relevant code snippets based on the target file content.
    """
    try:
        from sunwell.indexing import SmartContext
    except ImportError:
        return None

    try:
        # Create SmartContext (will use cached index or grep fallback)
        smart_ctx = SmartContext(workspace_root=workspace_root, index=None)

        # Extract query from file content
        file_content = target_path.read_text()

        # For documentation, extract code references and function names
        query_parts = []
        if target_path.suffix in (".md", ".rst"):
            # Look for backticked code references
            import re
            code_refs = re.findall(r"`([a-z_][a-z0-9_\.]+)`", file_content, re.I)
            query_parts.extend(code_refs[:10])

        # For code files, use the file name and any imports
        elif target_path.suffix == ".py":
            query_parts.append(target_path.stem)
            # Extract import names
            import re
            imports = re.findall(r"from\s+(\S+)\s+import|import\s+(\S+)", file_content)
            for imp in imports[:5]:
                query_parts.extend([p for p in imp if p])

        if not query_parts:
            return None

        # Query for relevant context
        query = " ".join(query_parts[:10])
        result = await smart_ctx.get_context(query, top_k=3)

        if result.context:
            return result.context

    except Exception:
        pass

    return None


def _find_related_files(target: Path, workspace: Path) -> list[dict[str, str]]:
    """Find files related to target (tests, implementations, schemas)."""
    related: list[dict[str, str]] = []
    stem = target.stem

    # Look for test files
    for pattern in [f"test_{stem}.py", f"{stem}_test.py", f"test_{stem}.ts"]:
        for match in workspace.rglob(pattern):
            related.append({"path": str(match), "relation": "test"})
            if len(related) >= 5:
                return related

    # Look for implementation if this is a doc
    if target.suffix in (".md", ".rst"):
        # Extract module references from content
        try:
            content = target.read_text()
            # Simple heuristic: look for backticked paths
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

    # Simple heuristics
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

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold cyan]⚡ Execution Plan: {shortcut}[/bold cyan]",
            subtitle=f"[dim]{skill_name}[/dim]",
            border_style="cyan",
        )
    )

    # Skill info table
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="bold")
    info_table.add_column("Value")

    info_table.add_row("Skill", f"[green]{skill_name}[/green]")
    info_table.add_row("Description", skill.description)
    info_table.add_row("Lens", f"{lens.metadata.name} v{lens.metadata.version}")
    info_table.add_row("Trust Level", f"[yellow]{skill.trust.value}[/yellow]")

    if skill.allowed_tools:
        tools = ", ".join(skill.allowed_tools)
        info_table.add_row("Tools", f"[dim]{tools}[/dim]")

    if skill.preset:
        info_table.add_row("Preset", f"[magenta]{skill.preset}[/magenta]")

    console.print(info_table)
    console.print()

    # Context section
    console.print("[bold]📁 Context Injection:[/bold]")
    ctx_table = Table(show_header=False, box=None, padding=(0, 2))
    ctx_table.add_column("Key", style="cyan")
    ctx_table.add_column("Value")

    if target:
        ctx_table.add_row("Target", target)

    if context.get("workspace_root"):
        ctx_table.add_row("Workspace", context["workspace_root"])

    if context.get("file_type"):
        ctx_table.add_row("File Type", context["file_type"])

    if context.get("diataxis_type"):
        ctx_table.add_row("Diataxis Type", f"[green]{context['diataxis_type']}[/green]")

    if context.get("related_files"):
        related = context["related_files"]
        for i, rf in enumerate(related[:3]):
            label = "Related" if i == 0 else ""
            rel_type = rf.get("relation", "")
            ctx_table.add_row(label, f"[dim]{rf['path']}[/dim] ({rel_type})")
        if len(related) > 3:
            ctx_table.add_row("", f"[dim]... and {len(related) - 3} more[/dim]")

    if context.get("uncommitted_changes"):
        diff_lines = context["uncommitted_changes"].count("\n")
        ctx_table.add_row("Git Diff", f"[yellow]{diff_lines} lines of uncommitted changes[/yellow]")

    if context.get("file_content"):
        lines = context["file_content"].count("\n")
        ctx_table.add_row("Content", f"{lines} lines loaded")

    console.print(ctx_table)
    console.print()

    # Show skill instructions (the exciting part!)
    if skill.instructions and verbose:
        console.print("[bold]📜 Skill Instructions:[/bold]")
        console.print(Panel(
            Markdown(skill.instructions),
            border_style="dim",
            title="[dim]What the AI will do[/dim]",
            title_align="left",
        ))
        console.print()

    # Validation info
    if skill.validate_with:
        console.print("[bold]✅ Validation:[/bold]")
        val_table = Table(show_header=False, box=None, padding=(0, 2))
        val_table.add_column("Key", style="dim")
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

    # Next steps
    console.print("━" * 50)
    console.print("[bold green]Ready to execute![/bold green]")
    console.print()
    cmd = f"sunwell do {shortcut}"
    if target:
        cmd += f" {target}"
    console.print(f"  Run: [cyan]{cmd}[/cyan]")
    if not verbose:
        console.print(f"  More detail: [dim]{cmd} --dry-run --verbose[/dim]")
    console.print()


def _show_shortcut_help() -> None:
    """Show available shortcuts and their descriptions."""
    shortcuts = _get_default_lens_shortcuts()

    # Group by category
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

    console.print("\n[dim]Usage: sunwell do ::a-2 docs/api.md[/dim]")
    console.print("[dim]Tip: Use --verbose for detailed execution info[/dim]")
