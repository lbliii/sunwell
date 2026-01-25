"""Chat command - Interactive headspace chat session.

RFC-135: Unified Chat-Agent Experience
Uses UnifiedChatLoop for seamless conversation ↔ agent execution
transitions with checkpoint-based handoffs.
"""


import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.markdown import Markdown
from rich.panel import Panel

from sunwell.binding import BindingManager
from sunwell.cli.helpers import create_model
from sunwell.cli.theme import create_sunwell_console
from sunwell.core.errors import SunwellError
from sunwell.core.types import LensReference
from sunwell.embedding import create_embedder
from sunwell.fount.client import FountClient
from sunwell.fount.resolver import LensResolver
from sunwell.schema.loader import LensLoader
from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.store import SimulacrumStore

if TYPE_CHECKING:
    from sunwell.agent.events import AgentEvent
    from sunwell.chat import ChatCheckpoint, UnifiedChatLoop

console = create_sunwell_console()


# =============================================================================
# Project Detection & Smart Context
# =============================================================================

# Project type detection patterns
_PROJECT_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "requirements.txt", "Pipfile"),
    "node": ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"),
    "rust": ("Cargo.toml",),
    "go": ("go.mod",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "ruby": ("Gemfile",),
    "php": ("composer.json",),
    "dotnet": ("*.csproj", "*.sln"),
    "svelte": ("svelte.config.js", "svelte.config.ts"),
    "react": ("next.config.js", "next.config.ts", "vite.config.ts"),
    "tauri": ("tauri.conf.json",),
}

# Key files to always include in context (if they exist)
_KEY_FILES = (
    "README.md", "README.rst", "README.txt", "README",
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "Makefile", "justfile",
    ".env.example",
)

# Entry point patterns by project type
_ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "python": ("src/*/cli.py", "src/*/__main__.py", "main.py", "app.py", "cli.py"),
    "node": ("src/index.ts", "src/index.js", "index.ts", "index.js", "src/main.ts"),
    "rust": ("src/main.rs", "src/lib.rs"),
    "go": ("main.go", "cmd/*/main.go"),
}


def _detect_project_type(cwd: Path) -> tuple[str, str | None]:
    """Detect project type from marker files.

    Returns:
        Tuple of (project_type, framework) e.g. ("python", "FastAPI")
    """
    for ptype, markers in _PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                if list(cwd.glob(marker)):
                    return ptype, None
            elif (cwd / marker).exists():
                # Try to detect framework
                framework = _detect_framework(cwd, ptype)
                return ptype, framework
    return "unknown", None


def _detect_framework(cwd: Path, ptype: str) -> str | None:
    """Detect framework from config files."""
    if ptype == "python":
        pyproject = cwd / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "fastapi" in content.lower():
                return "FastAPI"
            if "django" in content.lower():
                return "Django"
            if "flask" in content.lower():
                return "Flask"
            if "click" in content.lower():
                return "CLI (Click)"
    elif ptype == "node":
        pkg = cwd / "package.json"
        if pkg.exists():
            import json
            try:
                data = json.loads(pkg.read_text())
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "next" in deps:
                    return "Next.js"
                if "svelte" in deps or "@sveltejs/kit" in deps:
                    return "SvelteKit"
                if "react" in deps:
                    return "React"
                if "vue" in deps:
                    return "Vue"
            except json.JSONDecodeError:
                pass
    return None


def _is_project_directory(cwd: Path) -> bool:
    """Check if cwd looks like a project directory."""
    # Has any project marker
    for markers in _PROJECT_MARKERS.values():
        for marker in markers:
            if "*" in marker:
                if list(cwd.glob(marker)):
                    return True
            elif (cwd / marker).exists():
                return True

    # Has .git directory
    if (cwd / ".git").is_dir():
        return True

    # Has common project files
    if (cwd / "README.md").exists() or (cwd / "Makefile").exists():
        return True

    return False


def _find_key_files(cwd: Path) -> list[tuple[str, str]]:
    """Find key files and return (path, first_lines) tuples."""
    found = []
    for name in _KEY_FILES:
        path = cwd / name
        if path.exists() and path.is_file():
            try:
                content = path.read_text()
                # Get first meaningful lines (skip empty)
                lines = [l for l in content.split("\n") if l.strip()][:5]
                preview = "\n".join(lines)
                if len(preview) > 300:
                    preview = preview[:300] + "..."
                found.append((name, preview))
            except (OSError, UnicodeDecodeError):
                found.append((name, "(binary or unreadable)"))
    return found


def _find_entry_points(cwd: Path, ptype: str) -> list[str]:
    """Find likely entry point files."""
    patterns = _ENTRY_POINTS.get(ptype, ())
    found = []
    for pattern in patterns:
        matches = list(cwd.glob(pattern))
        found.extend(str(m.relative_to(cwd)) for m in matches[:3])
    return found[:5]  # Limit to 5 entry points


def _build_directory_tree(cwd: Path, max_files: int = 40, max_depth: int = 3) -> str:
    """Build a compact directory tree."""
    ignore_patterns = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
        ".egg-info", ".tox", ".coverage", "htmlcov", ".next", ".svelte-kit",
        "target", ".cargo",
    }

    lines = []
    file_count = 0

    for root, dirs, files in cwd.walk():
        dirs[:] = [d for d in sorted(dirs)
                   if d not in ignore_patterns and not d.startswith(".")]

        rel_root = root.relative_to(cwd)
        depth = len(rel_root.parts)

        if depth > max_depth:
            continue

        indent = "  " * depth
        if depth > 0:
            lines.append(f"{indent}{rel_root.name}/")

        for f in sorted(files)[:15]:
            if f.startswith(".") and f not in {".env.example", ".gitignore"}:
                continue
            lines.append(f"{indent}  {f}")
            file_count += 1
            if file_count >= max_files:
                lines.append(f"{indent}  ...")
                return "\n".join(lines)

    return "\n".join(lines)


def _load_cached_context(cache_path: Path) -> dict | None:
    """Load cached context if fresh (< 1 hour old)."""
    import json
    import time

    if not cache_path.exists():
        return None

    try:
        stat = cache_path.stat()
        age_hours = (time.time() - stat.st_mtime) / 3600
        if age_hours > 1:  # Stale after 1 hour
            return None

        return json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_context_cache(cache_path: Path, context: dict) -> None:
    """Save context to cache."""
    import json

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(context, indent=2))


def _build_smart_workspace_context(use_cache: bool = True) -> tuple[str, dict]:
    """Build intelligent workspace context with project detection.

    Returns:
        Tuple of (formatted_context, context_dict)
    """
    cwd = Path.cwd()
    cache_path = cwd / ".sunwell" / "context.json"

    # Try cache first
    if use_cache:
        cached = _load_cached_context(cache_path)
        if cached:
            return _format_context(cached), cached

    # Detect project
    ptype, framework = _detect_project_type(cwd)
    key_files = _find_key_files(cwd)
    entry_points = _find_entry_points(cwd, ptype) if ptype != "unknown" else []
    tree = _build_directory_tree(cwd)

    context = {
        "path": str(cwd),
        "name": cwd.name,
        "type": ptype,
        "framework": framework,
        "key_files": [(k, v) for k, v in key_files],
        "entry_points": entry_points,
        "tree": tree,
    }

    # Cache for next time
    try:
        _save_context_cache(cache_path, context)
    except OSError:
        pass  # Non-fatal

    return _format_context(context), context


def _format_context(ctx: dict) -> str:
    """Format context dict into markdown for system prompt."""
    lines = [
        "## Workspace Context",
        "",
        f"**Project**: `{ctx['name']}` ({ctx['path']})",
    ]

    # Project type badge
    ptype = ctx.get("type", "unknown")
    framework = ctx.get("framework")
    if ptype != "unknown":
        type_line = f"**Type**: {ptype.title()}"
        if framework:
            type_line += f" ({framework})"
        lines.append(type_line)

    lines.append("")

    # Key files with preview
    key_files = ctx.get("key_files", [])
    if key_files:
        lines.append("### Key Files")
        for name, preview in key_files[:3]:  # Limit to 3 for prompt size
            lines.append(f"\n**{name}**:")
            lines.append("```")
            lines.append(preview)
            lines.append("```")
        lines.append("")

    # Entry points
    entry_points = ctx.get("entry_points", [])
    if entry_points:
        lines.append(f"**Entry points**: {', '.join(f'`{e}`' for e in entry_points)}")
        lines.append("")

    # Directory tree
    tree = ctx.get("tree", "")
    if tree:
        lines.append("### Structure")
        lines.append("```")
        lines.append(tree)
        lines.append("```")

    lines.append("")
    lines.append("You can reference files by their relative paths.")

    return "\n".join(lines)


def _build_workspace_context(max_files: int = 50) -> str:
    """Build workspace context (simple fallback version)."""
    context, _ = _build_smart_workspace_context(use_cache=True)
    return context


# =============================================================================
# RFC-103: Workspace & SourceContext Integration
# =============================================================================


async def _load_workspace_context(cwd: Path) -> tuple[str | None, dict | None]:
    """Load RFC-103 workspace and source context if available.

    Returns:
        Tuple of (formatted_context, workspace_data) or (None, None) if not configured.
    """
    try:
        from sunwell.analysis.workspace import WorkspaceConfig
    except ImportError:
        return None, None

    config = WorkspaceConfig(cwd)
    workspace = config.load()

    if not workspace:
        return None, None

    # Build context from workspace
    lines = [
        "## Linked Source Code (RFC-103)",
        "",
    ]

    workspace_data = {
        "topology": workspace.topology,
        "links": [],
        "symbols": [],
    }

    for link in workspace.confirmed_links:
        link_info = {
            "path": str(link.target),
            "language": link.language,
            "relationship": link.relationship,
            "confidence": link.confidence,
        }
        workspace_data["links"].append(link_info)

        lines.append(f"**{link.target.name}** (`{link.target}`)")
        lines.append(f"- Language: {link.language or 'unknown'}")
        lines.append(f"- Relationship: {link.relationship}")
        lines.append("")

    # Try to load source context for symbol awareness
    try:
        from sunwell.analysis.source_context import SourceContext

        for link in workspace.confirmed_links:
            if link.relationship == "source_code":
                # Check for cached source context
                ctx_cache = cwd / ".sunwell" / "source_context" / f"{link.target.name}.json"
                ctx = None

                if ctx_cache.exists():
                    # Load from cache (fast path)
                    import json
                    import time

                    stat = ctx_cache.stat()
                    age_hours = (time.time() - stat.st_mtime) / 3600
                    if age_hours < 24:  # 24-hour cache
                        try:
                            data = json.loads(ctx_cache.read_text())
                            workspace_data["symbols"].extend(data.get("symbols", [])[:50])
                        except (json.JSONDecodeError, OSError):
                            pass

                if not workspace_data["symbols"]:
                    # Build fresh (slower, only on first load)
                    try:
                        ctx = await SourceContext.build(link.target)
                        # Cache key symbols
                        key_symbols = []
                        for name, sym in list(ctx.symbols.items())[:100]:
                            key_symbols.append({
                                "name": name,
                                "kind": sym.kind,
                                "signature": sym.signature,
                                "deprecated": sym.deprecated,
                            })
                        workspace_data["symbols"].extend(key_symbols[:50])

                        # Save to cache
                        ctx_cache.parent.mkdir(parents=True, exist_ok=True)
                        import json
                        ctx_cache.write_text(json.dumps({
                            "symbols": key_symbols,
                            "indexed_at": ctx.indexed_at.isoformat(),
                        }))
                    except Exception:
                        pass  # Non-fatal

        # Add symbols to context
        if workspace_data["symbols"]:
            lines.append("### Key Symbols")
            lines.append("")
            for sym in workspace_data["symbols"][:20]:  # Limit for prompt size
                sig = f"({sym.get('signature', '')})" if sym.get("signature") else ""
                deprecated = " ⚠️ DEPRECATED" if sym.get("deprecated") else ""
                lines.append(f"- `{sym['name']}`{sig} — {sym['kind']}{deprecated}")
            if len(workspace_data["symbols"]) > 20:
                lines.append(f"- ... and {len(workspace_data['symbols']) - 20} more")
            lines.append("")

    except ImportError:
        pass  # SourceContext not available

    return "\n".join(lines), workspace_data


# =============================================================================
# Phase 3/RFC-108: Semantic RAG - Continuous Codebase Indexing
# =============================================================================


async def _build_codebase_index(
    cwd: Path,
    embedder,
    force_rebuild: bool = False,
) -> tuple[object | None, dict]:
    """Build or load cached codebase embedding index using RFC-108 IndexingService.

    Returns:
        Tuple of (SmartContext, stats_dict) or (None, {}) if indexing fails.

    RFC-108: This now uses the new IndexingService with:
    - Content-aware chunking (AST for code, paragraphs for prose)
    - Priority indexing (hot files first)
    - Graceful degradation (falls back to grep if embedding fails)

    RFC-124: Also loads ToC navigation for structural queries.
    """
    try:
        from sunwell.indexing import IndexingService, create_smart_context
    except ImportError:
        # Fall back to legacy indexer if new module not available
        return await _build_codebase_index_legacy(cwd, embedder, force_rebuild)

    stats = {
        "indexed": False,
        "file_count": 0,
        "chunk_count": 0,
        "from_cache": False,
        "project_type": "unknown",
        "fallback_reason": None,
        "toc_loaded": False,
    }

    try:
        # Create indexing service (RFC-108)
        service = IndexingService(
            workspace_root=cwd,
            embedder=embedder,
        )

        # Start indexing (background with priority files first)
        await service.start()

        # Wait for priority files to be indexed (fast startup)
        # The service continues indexing in background
        status = service.get_status()

        stats["indexed"] = status.state.value in ("ready", "updating")
        stats["file_count"] = status.file_count or 0
        stats["chunk_count"] = status.chunk_count or 0
        stats["from_cache"] = status.priority_complete or False
        stats["project_type"] = status.project_type or "unknown"

        if status.fallback_reason:
            stats["fallback_reason"] = status.fallback_reason

        # Return SmartContext with ToC navigation (RFC-124) and codebase graph (RFC-045)
        smart_ctx = create_smart_context(
            workspace_root=cwd,
            indexer=service,
            model=None,  # Uses keyword fallback for ToC navigation
            auto_load_toc=True,
            auto_load_graph=True,
        )
        stats["toc_loaded"] = smart_ctx.navigator is not None
        stats["graph_loaded"] = smart_ctx.codebase_graph is not None

        return smart_ctx, stats

    except Exception as e:
        stats["fallback_reason"] = str(e)
        # Return SmartContext without index - will use grep/ToC/graph fallback
        try:
            smart_ctx = create_smart_context(
                workspace_root=cwd,
                indexer=None,
                model=None,
                auto_load_toc=True,
                auto_load_graph=True,
            )
            stats["toc_loaded"] = smart_ctx.navigator is not None
            stats["graph_loaded"] = smart_ctx.codebase_graph is not None
            return smart_ctx, stats
        except Exception:
            return None, stats


async def _build_codebase_index_legacy(
    cwd: Path,
    embedder,
    force_rebuild: bool = False,
) -> tuple[object | None, dict]:
    """Legacy codebase indexer (pre-RFC-108 fallback)."""
    try:
        from sunwell.workspace.detector import Workspace
        from sunwell.workspace.indexer import CodebaseIndexer
    except ImportError:
        return None, {}

    cache_dir = cwd / ".sunwell" / "index"
    cache_file = cache_dir / "codebase_index.json"

    stats = {
        "indexed": False,
        "file_count": 0,
        "chunk_count": 0,
        "from_cache": False,
    }

    # Check cache (24-hour lifetime)
    if not force_rebuild and cache_file.exists():
        import json
        import time

        try:
            stat = cache_file.stat()
            age_hours = (time.time() - stat.st_mtime) / 3600
            if age_hours < 24:
                data = json.loads(cache_file.read_text())
                stats["indexed"] = True
                stats["file_count"] = data.get("file_count", 0)
                stats["chunk_count"] = data.get("chunk_count", 0)
                stats["from_cache"] = True

                # Rebuild indexer from cached embeddings
                from sunwell.workspace.indexer import CodebaseIndex, CodeChunk

                chunks = [
                    CodeChunk(
                        file_path=Path(c["file_path"]),
                        start_line=c["start_line"],
                        end_line=c["end_line"],
                        content=c["content"],
                        chunk_type=c["chunk_type"],
                        name=c.get("name"),
                    )
                    for c in data.get("chunks", [])
                ]

                indexer = CodebaseIndexer(embedder)
                indexer._index = CodebaseIndex(
                    chunks=chunks,
                    embeddings=data.get("embeddings", {}),
                    file_count=stats["file_count"],
                    total_lines=data.get("total_lines", 0),
                )
                return indexer, stats
        except (json.JSONDecodeError, OSError, KeyError):
            pass  # Cache invalid, rebuild

    # Detect ignore patterns
    ignore_patterns = (
        "__pycache__", "node_modules", ".venv", "venv", ".git",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
        ".egg-info", ".tox", "htmlcov", ".next", ".svelte-kit", "target",
    )

    workspace = Workspace(
        root=cwd,
        is_git=(cwd / ".git").is_dir(),
        name=cwd.name,
        ignore_patterns=ignore_patterns,
    )

    indexer = CodebaseIndexer(embedder)

    try:
        index = await indexer.index_workspace(workspace)
        stats["indexed"] = True
        stats["file_count"] = index.file_count
        stats["chunk_count"] = len(index.chunks)

        # Cache the index
        import json
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "file_count": index.file_count,
            "chunk_count": len(index.chunks),
            "total_lines": index.total_lines,
            "chunks": [
                {
                    "file_path": str(c.file_path),
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "content": c.content,
                    "chunk_type": c.chunk_type,
                    "name": c.name,
                }
                for c in index.chunks
            ],
            "embeddings": index.embeddings,
        }
        cache_file.write_text(json.dumps(cache_data))

        return indexer, stats
    except Exception:
        return None, stats


@dataclass(frozen=True, slots=True)
class RAGResult:
    """Result of RAG retrieval with transparency info."""

    context: str
    """Formatted context string for prompt injection."""

    references: tuple[tuple[str, float], ...] = ()
    """Tuple of (reference_string, relevance_score) pairs."""

    fallback_used: bool = False
    """RFC-108: Whether fallback (grep) was used instead of semantic search."""

    @property
    def found_code(self) -> bool:
        """Whether any relevant code was found."""
        return bool(self.references)


async def _retrieve_relevant_code(
    context_provider,
    query: str,
    top_k: int = 3,
) -> RAGResult:
    """Retrieve relevant code chunks for a query.

    RFC-108: Now supports SmartContext with graceful fallback.

    Args:
        context_provider: Either SmartContext (RFC-108) or legacy CodebaseIndexer
        query: The search query
        top_k: Maximum number of results

    Returns:
        RAGResult with context and transparency info.
    """
    if not context_provider:
        return RAGResult(context="")

    # RFC-108: Check if this is the new SmartContext
    try:
        from sunwell.indexing import SmartContext
        if isinstance(context_provider, SmartContext):
            result = await context_provider.get_context(query, top_k=top_k)
            references = tuple(
                (f"{c.file_path}:{c.start_line}-{c.end_line}", c.score)
                for c in result.chunks
            ) if hasattr(result, 'chunks') and result.chunks else ()

            return RAGResult(
                context=result.context,
                references=references,
                fallback_used=result.fallback_used,
            )
    except ImportError:
        pass  # SmartContext not available, try legacy

    # Legacy CodebaseIndexer path
    try:
        retrieval = await context_provider.retrieve(query, top_k=top_k, threshold=0.3)
        if retrieval.chunks:
            # Build references list for transparency
            references = tuple(
                (chunk.reference, retrieval.relevance_scores.get(chunk.id, 0.0))
                for chunk in retrieval.chunks
            )
            return RAGResult(
                context=retrieval.to_prompt_context(max_chunks=top_k),
                references=references,
            )
    except Exception:
        pass

    return RAGResult(context="")


def _format_context_summary(ctx_data: dict, workspace_data: dict | None = None) -> str:
    """Format context summary for /context command."""
    lines = [
        "## Current Context",
        "",
        f"**Project**: {ctx_data.get('name', 'unknown')}",
        f"**Path**: {ctx_data.get('path', 'unknown')}",
        f"**Type**: {ctx_data.get('type', 'unknown')}",
    ]

    if ctx_data.get("framework"):
        lines.append(f"**Framework**: {ctx_data['framework']}")

    # Key files
    key_files = ctx_data.get("key_files", [])
    if key_files:
        lines.append(f"**Key files**: {', '.join(k[0] for k in key_files)}")

    # Entry points
    entry_points = ctx_data.get("entry_points", [])
    if entry_points:
        lines.append(f"**Entry points**: {', '.join(entry_points)}")

    # Workspace info
    if workspace_data:
        lines.append("")
        lines.append("### Linked Sources (RFC-103)")
        for link in workspace_data.get("links", []):
            lines.append(f"- {Path(link['path']).name}: {link['language']} ({link['relationship']})")

        symbols = workspace_data.get("symbols", [])
        if symbols:
            lines.append(f"**Symbols indexed**: {len(symbols)}")

    # Cache info
    cache_path = Path(ctx_data.get("path", ".")) / ".sunwell" / "context.json"
    if cache_path.exists():
        import time
        age_mins = int((time.time() - cache_path.stat().st_mtime) / 60)
        lines.append(f"**Cache age**: {age_mins} minutes")

    return "\n".join(lines)


@click.command()
@click.argument("binding_or_lens", required=False)
@click.option("--session", "-s", help="Session name (creates new or resumes existing)")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--provider", "-p", default=None, help="Provider")
@click.option("--memory-path", type=click.Path(), default=".sunwell/memory", help="Memory store path")
@click.option("--tools/--no-tools", default=None, help="Override tool calling (Agent mode)")
@click.option("--trust", type=click.Choice(["discovery", "read_only", "workspace", "shell"]),
              default=None, help="Override tool trust level")
@click.option("--workspace/--no-workspace", default=None,
              help="Inject workspace context (auto-detected if omitted)")
@click.option("--rag/--no-rag", default=None,
              help="Enable semantic code retrieval (auto if workspace detected)")
@click.option("--auto-confirm", is_flag=True, help="Skip confirmation checkpoints (for testing/CI)")
@click.option("--stream-progress/--no-stream-progress", default=True, help="Stream progress events during execution")
@click.option("--smart", is_flag=True, default=False, help="Enable Adaptive Model Selection")
@click.option("--mirror", is_flag=True, default=False, help="Enable Mirror Neurons (self-introspection)")
@click.option("--model-routing", is_flag=True, default=False, help="Enable Model-Aware Task Routing")
def chat(
    binding_or_lens: str | None,
    session: str | None,
    model: str | None,
    provider: str | None,
    memory_path: str,
    tools: bool | None,
    trust: str | None,
    workspace: bool | None,
    rag: bool | None,
    auto_confirm: bool,
    stream_progress: bool,
    smart: bool,
    mirror: bool,
    model_routing: bool,
) -> None:
    """Start an interactive headspace chat session.

    Uses your default binding if no argument given. Can also specify
    a binding name or lens path directly.

    Your headspace (learnings, dead ends, context) persists across:
    - Model switches: /switch anthropic:claude-sonnet-4-20250514
    - Session restarts: sunwell chat --session my-project

    Key commands:
    - /switch <provider:model>: Switch models mid-conversation
    - /branch <name>: Create a branch to try something
    - /dead-end: Mark current path as dead end
    - /learn <fact>: Add a persistent learning
    - /quit: Exit (auto-saves)

    Examples:

        sunwell chat                              # Uses default binding

        sunwell chat writer                       # Uses 'writer' binding

        sunwell chat lenses/tech-writer.lens     # Direct lens path

        sunwell chat --session auth-debug        # Named session

        # Mid-conversation: /switch anthropic:claude-sonnet-4-20250514
    """
    manager = BindingManager()
    lens_path: str | None = None

    # Track if CLI overrode the provider (important for model defaults)
    cli_provider_override = provider is not None
    cli_model_override = model is not None

    # Tool settings (may be overridden by CLI flags)
    tools_enabled = tools  # CLI override or None
    trust_level = trust  # CLI override or None

    # Resolve binding or lens path
    if binding_or_lens:
        # Check if it's a binding name first
        binding = manager.get(binding_or_lens)
        if binding:
            lens_path = binding.lens_path
            # Only use binding's model if provider wasn't overridden
            # (otherwise the model might be wrong for the new provider)
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            # Use binding's tool settings if not overridden
            if tools_enabled is None:
                tools_enabled = binding.tools_enabled
            if trust_level is None:
                trust_level = binding.trust_level
        elif Path(binding_or_lens).exists():
            # It's a lens path
            lens_path = binding_or_lens
        else:
            console.print(f"[void.purple]✗ Not found:[/] '{binding_or_lens}'")
            console.print("[neutral.dim]List bindings: sunwell bind list[/neutral.dim]")
            sys.exit(1)
    else:
        # Try default binding
        binding = manager.get_default()
        if binding:
            lens_path = binding.lens_path
            # Only use binding's model if provider wasn't overridden
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            # Use binding's tool settings if not overridden
            if tools_enabled is None:
                tools_enabled = binding.tools_enabled
            if trust_level is None:
                trust_level = binding.trust_level
        else:
            console.print("[yellow]No binding specified and no default set.[/yellow]")
            console.print()
            console.print("Options:")
            console.print("  1. Run [cyan]sunwell setup[/cyan] to create default bindings")
            console.print("  2. Specify a lens: [cyan]sunwell chat path/to/lens.lens[/cyan]")
            console.print("  3. Create a binding: [cyan]sunwell bind create my-chat --lens my.lens[/cyan]")
            sys.exit(1)

    # Set defaults
    provider = provider or "ollama"
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
            "mock": "mock",
        }.get(provider, "gpt-4o")

    # Load lens
    fount = FountClient()
    loader = LensLoader(fount_client=fount)
    resolver = LensResolver(loader=loader)

    try:
        source = str(lens_path)
        if not (source.startswith("/") or source.startswith("./") or source.startswith("../")):
            source = f"./{source}"

        ref = LensReference(source=source)
        lens = asyncio.run(resolver.resolve(ref))
    except SunwellError as e:
        console.print(f"[void.purple]✗ Error loading lens:[/] {e.message}")
        sys.exit(1)

    # Initialize memory store
    store = SimulacrumStore(Path(memory_path))

    # Create or resume session
    if session:
        try:
            dag = store.load_session(session)
            console.print(f"[holy.success]★ Resumed session:[/] {session}")
            console.print(f"[neutral.dim]  {len(dag.turns)} turns, {len(dag.learnings)} learnings[/neutral.dim]")
        except FileNotFoundError:
            store.new_session(session)
            dag = store.get_dag()
            console.print(f"[holy.success]★ Created session:[/] {session}")
    else:
        session = store.new_session()
        dag = store.get_dag()
        console.print(f"[holy.success]★ New session:[/] {session}")

    # Create model
    llm = create_model(provider, model)
    embedder = create_embedder()

    # Set embedder on store for semantic retrieval (RFC-013)
    store.set_embedder(embedder)

    # Build system prompt from lens
    system_prompt = lens.to_context()

    # Inject workspace context (auto-detect if not specified)
    inject_workspace = workspace
    if inject_workspace is None:
        # Auto-detect: enable if in a project directory
        inject_workspace = _is_project_directory(Path.cwd())

    # Store context data for /context command
    ctx_data: dict = {}
    workspace_data: dict | None = None

    if inject_workspace:
        workspace_context, ctx_data = _build_smart_workspace_context(use_cache=True)
        system_prompt = f"{system_prompt}\n\n{workspace_context}"

        # Show what was detected
        ptype = ctx_data.get("type", "unknown")
        framework = ctx_data.get("framework")
        if ptype != "unknown":
            type_info = ptype.title()
            if framework:
                type_info += f" ({framework})"
            console.print(f"[cyan]Project:[/cyan] {type_info} detected")
        else:
            console.print("[cyan]Workspace:[/cyan] Context injected")

        # RFC-103: Load linked source context if available
        try:
            linked_context, workspace_data = asyncio.run(
                _load_workspace_context(Path.cwd())
            )
            if linked_context:
                system_prompt = f"{system_prompt}\n\n{linked_context}"
                link_count = len(workspace_data.get("links", [])) if workspace_data else 0
                symbol_count = len(workspace_data.get("symbols", [])) if workspace_data else 0
                if link_count > 0:
                    console.print(
                        f"[cyan]Workspace:[/cyan] {link_count} linked project(s), "
                        f"{symbol_count} symbols indexed"
                    )
        except Exception:
            pass  # Non-fatal - workspace context is optional

    # RFC-108: Continuous codebase indexing (enabled by default)
    codebase_indexer = None
    rag_stats: dict = {}
    enable_rag = rag if rag is not None else inject_workspace  # Auto-enable if workspace detected

    if enable_rag:
        try:
            console.print("[dim]Building codebase index...[/dim]", end="")
            codebase_indexer, rag_stats = asyncio.run(
                _build_codebase_index(Path.cwd(), embedder)
            )
            if rag_stats.get("indexed"):
                cache_note = " (cached)" if rag_stats.get("from_cache") else ""
                project_type = rag_stats.get("project_type", "")
                type_note = f" [{project_type}]" if project_type and project_type != "unknown" else ""
                console.print(
                    f"\r[cyan]RAG:[/cyan] {rag_stats.get('chunk_count', 0)} chunks from "
                    f"{rag_stats.get('file_count', 0)} files{cache_note}{type_note}   "
                )
            elif rag_stats.get("fallback_reason"):
                # RFC-108: Show graceful degradation
                console.print(f"\r[yellow]RAG:[/yellow] grep fallback ({rag_stats.get('fallback_reason', 'no embedder')})   ")
            else:
                console.print("\r[dim]RAG: indexing skipped[/dim]         ")
        except Exception as e:
            console.print(f"\r[dim]RAG: disabled ({e})[/dim]         ")

    # Auto-detect advanced features (RFC-015, RFC-020)
    # User flags override auto-detection
    try:
        from sunwell.indexing import detect_auto_features

        auto_features = detect_auto_features(
            workspace_root=Path.cwd(),
            session_length=len(dag.nodes) if hasattr(dag, "nodes") else 0,
            goal_complexity="medium",  # Default, could analyze lens
            explicit_mirror=mirror if mirror else None,
            explicit_routing=model_routing if model_routing else None,
            explicit_smart=smart if smart else None,
        )

        # Apply auto-detected features (only if user didn't explicitly set)
        if not mirror and auto_features.mirror_enabled:
            mirror = True
            console.print("[dim]Auto-enabled: Mirror Neurons (complex session)[/dim]")
        if not model_routing and auto_features.model_routing_enabled:
            model_routing = True
            console.print("[dim]Auto-enabled: Model Routing (multiple models)[/dim]")
        if not smart and auto_features.smart_enabled:
            smart = True
            console.print("[dim]Auto-enabled: Smart Mode (cost optimization)[/dim]")
    except ImportError:
        pass  # Auto-config not available

    # Mode display
    rag_status = " | RAG" if enable_rag and codebase_indexer else ""
    console.print(Panel(
        f"[bold]{lens.metadata.name}[/bold] ({provider}:{model}): [cyan]Unified ({trust_level or 'workspace'})[/cyan]{rag_status}\n"
        f"Commands: /quit, /agent <goal>, /chat, /status",
        title=f"Session: {session}",
        border_style="cyan",
    ))

    # RFC-135: Unified chat-agent loop
    asyncio.run(_run_unified_loop(
        model=llm,
        workspace=Path.cwd(),
        trust_level=trust_level or "workspace",
        auto_confirm=auto_confirm,
        stream_progress=stream_progress,
        dag=dag,
        store=store,
        memory_path=Path(memory_path),
        lens=lens,
    ))


# =============================================================================
# RFC-135: Unified Chat-Agent Loop
# =============================================================================


async def _run_unified_loop(
    model,
    workspace: Path,
    trust_level: str = "workspace",
    auto_confirm: bool = False,
    stream_progress: bool = True,
    dag: ConversationDAG | None = None,
    store: SimulacrumStore | None = None,
    memory_path: Path | None = None,
    lens=None,
) -> None:
    """Run the unified chat-agent loop (RFC-135).

    Provides seamless transitions between conversation and execution modes:
    - Intent classification routes input to chat or agent
    - Checkpoints enable user control at key decision points
    - Progress events stream execution status to UI
    """
    from sunwell.chat import (
        ChatCheckpoint,
        ChatCheckpointType,
        CheckpointResponse,
        UnifiedChatLoop,
    )
    from sunwell.agent.events import AgentEvent, EventType
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    # Set up tool executor
    from sunwell.project import ProjectResolutionError, resolve_project

    project = None
    workspace_root = workspace
    try:
        project = resolve_project(cwd=workspace)
        workspace_root = project.root
    except ProjectResolutionError:
        pass

    policy = ToolPolicy(trust_level=ToolTrust.from_string(trust_level))
    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace_root if project is None else None,
        sandbox=None,
        policy=policy,
    )

    # Create unified loop
    loop = UnifiedChatLoop(
        model=model,
        tool_executor=tool_executor,
        workspace=workspace,
        auto_confirm=auto_confirm,
        stream_progress=stream_progress,
    )

    # Start the generator
    gen = loop.run()
    await gen.asend(None)  # Initialize

    # Track execution state for display
    current_task: str | None = None
    total_tasks: int = 0

    try:
        while True:
            # Get user input
            state_indicator = ""
            if loop.is_executing:
                state_indicator = " [yellow](executing)[/yellow]"
            user_input = console.input(f"\n[bold cyan]You:{state_indicator}[/bold cyan] ").strip()

            if not user_input:
                continue

            # Handle quit commands directly
            if user_input.lower() in ("/quit", "/exit", "/q"):
                break

            # Send input to the loop
            result = await gen.asend(user_input)

            # Process results until we need more input
            while result is not None:
                if isinstance(result, str):
                    # Conversation response
                    _render_response(result, lens)
                    if dag:
                        dag.add_user_message(user_input)
                        dag.add_assistant_message(result, model=str(model))
                    result = None  # Wait for next user input

                elif isinstance(result, ChatCheckpoint):
                    # Handle checkpoint
                    response = _handle_checkpoint(result, console)
                    if response is None:
                        # User aborted
                        break
                    result = await gen.asend(response)

                elif isinstance(result, AgentEvent):
                    # Render progress event
                    _render_agent_event(result, console)
                    # Get next event
                    result = await gen.asend(None)

                else:
                    # Unknown result type
                    result = None

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Saving session...[/yellow]")
    except EOFError:
        pass
    except GeneratorExit:
        pass
    finally:
        # Clean up
        try:
            await gen.aclose()
        except Exception:
            pass

        # Save session
        if store:
            store.save_session()
            console.print("[holy.success]★ Session saved[/holy.success]")


def _handle_checkpoint(
    checkpoint: ChatCheckpoint,
    console,
) -> CheckpointResponse | None:
    """Handle a ChatCheckpoint by prompting user for decision.

    Returns:
        CheckpointResponse with user's choice, or None to abort
    """
    from sunwell.chat import ChatCheckpointType, CheckpointResponse

    # Display checkpoint message
    console.print()

    if checkpoint.type == ChatCheckpointType.CONFIRMATION:
        console.print(f"[cyan]{checkpoint.message}[/cyan]")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "Y"
        choice = console.input(f"[bold]Proceed?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.FAILURE:
        console.print(f"[red]✗ {checkpoint.message}[/red]")
        if checkpoint.error:
            console.print(f"[dim]{checkpoint.error}[/dim]")
        if checkpoint.recovery_options:
            console.print(f"[yellow]Recovery options: {', '.join(checkpoint.recovery_options)}[/yellow]")
        default = checkpoint.default or "abort"
        choice = console.input(f"[bold]Action?[/bold] [{default}] ").strip() or default
        if choice.lower() in ("q", "quit", "abort"):
            return None
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.COMPLETION:
        console.print(f"[green]★ {checkpoint.message}[/green]")
        if checkpoint.summary:
            console.print(f"[dim]{checkpoint.summary}[/dim]")
        if checkpoint.files_changed:
            console.print(f"[dim]Files: {', '.join(checkpoint.files_changed[:5])}[/dim]")
        return CheckpointResponse("done")

    elif checkpoint.type == ChatCheckpointType.INTERRUPTION:
        console.print(f"[yellow]⚡ Paused:[/yellow] {checkpoint.message}")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "continue"
        choice = console.input(f"[bold]Action?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.CLARIFICATION:
        console.print(f"[cyan]? {checkpoint.message}[/cyan]")
        user_input = console.input("[bold]Your response:[/bold] ").strip()
        return CheckpointResponse("respond", additional_input=user_input)

    else:
        # Unknown checkpoint type - default to continue
        return CheckpointResponse("continue")


def _render_agent_event(event: AgentEvent, console) -> None:
    """Render an AgentEvent for the CLI.

    Uses minimal output for streaming updates, with detailed info
    for significant events like task completion or failures.
    """
    from sunwell.agent.events import EventType

    if event.type == EventType.TASK_START:
        task_desc = event.data.get("description", "Working...")[:60]
        task_id = event.data.get("task_id", "")
        console.print(f"[cyan]→[/cyan] {task_desc}")

    elif event.type == EventType.TASK_COMPLETE:
        task_id = event.data.get("task_id", "")
        duration_ms = event.data.get("duration_ms", 0)
        duration_note = f" ({duration_ms}ms)" if duration_ms else ""
        console.print(f"[green]✓[/green] Done{duration_note}")

    elif event.type == EventType.GATE_START:
        gate_name = event.data.get("gate_name", "Validation")
        console.print(f"[dim]  Checking: {gate_name}...[/dim]", end="\r")

    elif event.type == EventType.GATE_PASS:
        gate_name = event.data.get("gate_name", "Validation")
        console.print(f"[green]  ✓ {gate_name}[/green]     ")

    elif event.type == EventType.GATE_FAIL:
        error = event.data.get("error_message", "Validation failed")
        console.print(f"[red]  ✗ {error}[/red]")

    elif event.type == EventType.MODEL_TOKENS:
        # Minimal token count display (overwrite line)
        tokens = event.data.get("total_tokens", 0)
        console.print(f"[dim]  Tokens: {tokens}[/dim]", end="\r")

    elif event.type == EventType.PLAN_WINNER:
        tasks = event.data.get("tasks", 0)
        gates = event.data.get("gates", 0)
        technique = event.data.get("technique", "")
        technique_note = f" ({technique})" if technique else ""
        console.print(f"[cyan]★ Plan ready:[/cyan] {tasks} tasks, {gates} validation gates{technique_note}")

    elif event.type == EventType.COMPLETE:
        tasks_done = event.data.get("tasks_completed", 0)
        gates_done = event.data.get("gates_passed", 0)
        duration = event.data.get("duration_s", 0)
        summary = f"{tasks_done} tasks, {gates_done} gates"
        if duration:
            summary += f" ({duration:.1f}s)"
        console.print(f"\n[green]★ Complete:[/green] {summary}")


def _render_response(response: str, lens=None) -> None:
    """Render a conversational response."""
    lens_name = lens.metadata.name if lens and hasattr(lens, "metadata") else "Sunwell"
    console.print(f"\n[bold green]{lens_name}:[/bold green]")
    console.print(Markdown(response))

