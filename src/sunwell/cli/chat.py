"""Chat command - Interactive headspace chat session."""


import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from sunwell.binding import BindingManager
from sunwell.cli.helpers import create_model
from sunwell.core.errors import SunwellError
from sunwell.core.types import LensReference
from sunwell.embedding import create_embedder
from sunwell.fount.client import FountClient
from sunwell.fount.resolver import LensResolver
from sunwell.runtime.commands import ChatSession, handle_command
from sunwell.runtime.model_router import ModelRouter
from sunwell.schema.loader import LensLoader
from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.store import SimulacrumStore
from sunwell.simulacrum.core.turn import Learning

if TYPE_CHECKING:
    from sunwell.naaru.shards import ShardPool

console = Console()


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


@dataclass
class RAGResult:
    """Result of RAG retrieval with transparency info."""
    context: str
    """Formatted context string for prompt injection."""
    references: list[tuple[str, float]]
    """List of (reference_string, relevance_score) tuples."""
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
        return RAGResult(context="", references=[])

    # RFC-108: Check if this is the new SmartContext
    try:
        from sunwell.indexing import SmartContext
        if isinstance(context_provider, SmartContext):
            result = await context_provider.get_context(query, top_k=top_k)
            references = [
                (f"{c.file_path}:{c.start_line}-{c.end_line}", c.score)
                for c in result.chunks
            ] if hasattr(result, 'chunks') and result.chunks else []

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
            references = [
                (chunk.reference, retrieval.relevance_scores.get(chunk.id, 0.0))
                for chunk in retrieval.chunks
            ]
            return RAGResult(
                context=retrieval.to_prompt_context(max_chunks=top_k),
                references=references,
            )
    except Exception:
        pass

    return RAGResult(context="", references=[])


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


@dataclass
class ChatState:
    """Mutable state for chat loop - enables model switching."""
    model: object
    model_name: str
    lens_name: str = "Assistant"
    tools_enabled: bool = False
    trust_level: str = "workspace"
    models_used: list[str] = field(default_factory=list)
    last_response: str = ""
    tool_executor: object = None
    pending_observations: list[str] = field(default_factory=list)
    """Queue for M'uru observations to display after streaming completes."""

    # Project context (for /context command)
    project_context: dict = field(default_factory=dict)
    """Cached project context data."""
    workspace_context: dict | None = None
    """RFC-103 workspace context (linked sources, symbols)."""

    # Semantic RAG (Phase 3)
    codebase_indexer: object | None = None
    """Codebase indexer for semantic retrieval."""
    rag_enabled: bool = False
    """Whether semantic RAG is enabled for this session."""
    rag_stats: dict = field(default_factory=dict)
    """Stats about the codebase index (file_count, chunk_count, etc.)."""

    def switch_model(self, new_model: object, new_name: str) -> None:
        """Switch to a new model, tracking history."""
        self.models_used.append(self.model_name)
        self.model = new_model
        self.model_name = new_name

    def queue_observation(self, message: str) -> None:
        """Queue an observation message to display after streaming."""
        self.pending_observations.append(message)

    def flush_observations(self, console) -> None:
        """Display and clear all queued observation messages."""
        for msg in self.pending_observations:
            console.print(msg)
        self.pending_observations.clear()

    @property
    def mode(self) -> str:
        """Return 'Agent' if tools enabled, else 'Chat'."""
        return "Agent" if self.tools_enabled else "Chat"

    @property
    def mode_display(self) -> str:
        """Return mode with trust level for display."""
        if self.tools_enabled:
            return f"Agent ({self.trust_level})"
        return "Chat"


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
@click.option("--smart", is_flag=True, help="Enable RFC-015 Adaptive Model Selection")
@click.option("--mirror", is_flag=True, help="Enable RFC-015 Mirror Neurons (self-introspection)")
@click.option("--model-routing", is_flag=True, help="Enable RFC-015 Model-Aware Task Routing")
@click.option("--router-model", default=None, help="Tiny LLM for cognitive routing (RFC-020)")
@click.option("--naaru/--no-naaru", default=True, help="RFC-019: Enable Naaru Shards for parallel processing")
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
    smart: bool,
    mirror: bool,
    model_routing: bool,
    router_model: str | None,
    naaru: bool,
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
            console.print(f"[red]Not found:[/red] '{binding_or_lens}' is neither a binding nor a lens file")
            console.print("[dim]List bindings: sunwell bind list[/dim]")
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
        console.print(f"[red]Error loading/resolving lens:[/red] {e.message}")
        sys.exit(1)

    # Initialize memory store
    store = SimulacrumStore(Path(memory_path))

    # Create or resume session
    if session:
        try:
            dag = store.load_session(session)
            console.print(f"[green]✓ Resumed session:[/green] {session}")
            console.print(f"[dim]  {len(dag.turns)} turns, {len(dag.learnings)} learnings[/dim]")
        except FileNotFoundError:
            store.new_session(session)
            dag = store.get_dag()
            console.print(f"[green]✓ Created new session:[/green] {session}")
    else:
        session = store.new_session()
        dag = store.get_dag()
        console.print(f"[green]✓ New session:[/green] {session}")

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

    # Determine mode label
    mode_label = "Agent" if tools_enabled else "Chat"
    mode_color = "green" if tools_enabled else "blue"
    trust_display = f" ({trust_level or 'workspace'})" if tools_enabled else ""

    rag_status = " | RAG" if enable_rag and codebase_indexer else ""
    console.print(Panel(
        f"[bold]{lens.metadata.name}[/bold] ({provider}:{model}): [{mode_color}]{mode_label}{trust_display}[/{mode_color}]{rag_status}\n"
        f"Commands: /switch, /search, /context, /index, /rag, /quit"
        + (" | /tools on/off" if not tools_enabled else ""),
        title=f"Session: {session}",
        border_style=mode_color,
    ))

    # Main chat loop with model state
    asyncio.run(_chat_loop(
        dag=dag,
        store=store,
        initial_model=llm,
        initial_model_name=f"{provider}:{model}",
        system_prompt=system_prompt,
        tools_enabled=tools_enabled or False,
        trust_level=trust_level or "workspace",
        smart=smart,
        lens=lens,
        mirror_enabled=mirror,
        model_routing_enabled=model_routing,
        memory_path=Path(memory_path),
        naaru_enabled=naaru,  # RFC-019: Naaru-powered chat
        identity_enabled=naaru,  # RFC-023: Adaptive identity (follows naaru flag)
        project_context=ctx_data,  # For /context command
        workspace_context=workspace_data,  # RFC-103 linked sources
        codebase_indexer=codebase_indexer,  # Phase 3: Semantic RAG
        rag_enabled=enable_rag and codebase_indexer is not None,
        rag_stats=rag_stats,
    ))


async def _generate_with_tools(
    model,
    messages: list[dict],
    tool_executor,
    console,
    max_iterations: int = 10,
) -> str:
    """Generate response with tool calling support.

    Handles the multi-turn tool calling loop:
    1. Send prompt + tools to model
    2. If model returns tool calls, execute them
    3. Send tool results back to model
    4. Repeat until model returns text or max iterations
    """
    from sunwell.models.protocol import Message
    from sunwell.tools.builtins import CORE_TOOLS

    # Get available tools from executor
    available_tool_names = tool_executor.get_available_tools()

    # Build tools list from CORE_TOOLS
    tool_list = [CORE_TOOLS[name] for name in available_tool_names if name in CORE_TOOLS]

    # Add mirror tools if mirror handler is configured (RFC-015)
    if tool_executor.mirror_handler:
        from sunwell.mirror.tools import MIRROR_TOOL_TRUST, MIRROR_TOOLS
        from sunwell.tools.types import ToolTrust

        # Get current trust level
        current_trust = tool_executor.policy.trust_level if tool_executor.policy else ToolTrust.WORKSPACE
        trust_order = ["discovery", "read_only", "workspace", "shell", "full"]
        current_idx = trust_order.index(current_trust.value.lower()) if hasattr(current_trust, 'value') else 2

        # Add mirror tools available at current trust level
        for tool_name, tool_def in MIRROR_TOOLS.items():
            required_level = MIRROR_TOOL_TRUST.get(tool_name, "workspace")
            required_idx = trust_order.index(required_level)
            if current_idx >= required_idx:
                tool_list.append(tool_def)

    tools = tuple(tool_list)

    # Build conversation as Message objects
    conversation: list[Message] = []
    for msg in messages:
        conversation.append(Message(role=msg["role"], content=msg["content"]))

    response_text = ""

    for _iteration in range(max_iterations):
        # Generate with tools
        result = await model.generate(
            tuple(conversation),
            tools=tools,
            tool_choice="auto",
        )

        # If no tool calls, we're done
        if not result.has_tool_calls:
            response_text = result.text
            # Render with markdown formatting
            console.print(Markdown(response_text))
            break

        # Add assistant message with tool calls to conversation
        conversation.append(Message(
            role="assistant",
            content=result.content,
            tool_calls=result.tool_calls,
        ))

        # Execute each tool call
        for tool_call in result.tool_calls:
            console.print(f"\n[cyan]⚡ {tool_call.name}[/cyan]", end="")
            args_preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(tool_call.arguments.items())[:2])
            console.print(f"[dim]({args_preview})[/dim]")

            # Execute the tool
            tool_result = await tool_executor.execute(tool_call)

            # Show result status
            if tool_result.success:
                output_preview = tool_result.output[:100] + "..." if len(tool_result.output) > 100 else tool_result.output
                console.print(f"[green]✓[/green] [dim]{output_preview}[/dim]")
            else:
                console.print(f"[red]✗[/red] {tool_result.error}")

            # Add tool result to conversation
            conversation.append(Message(
                role="tool",
                content=tool_result.output if tool_result.success else f"Error: {tool_result.error}",
                tool_call_id=tool_call.id,
            ))

        console.print()  # Newline after tool results
    else:
        # Max iterations reached
        console.print(f"\n[yellow]⚠ Max tool iterations ({max_iterations}) reached[/yellow]")
        response_text = result.text if result else ""

    return response_text


async def _chat_loop(
    dag: ConversationDAG,
    store: SimulacrumStore,
    initial_model,
    initial_model_name: str,
    system_prompt: str,
    tools_enabled: bool = False,
    trust_level: str = "workspace",
    smart: bool = False,
    lens = None,
    mirror_enabled: bool = False,
    model_routing_enabled: bool = False,
    memory_path: Path | None = None,
    naaru_enabled: bool = True,  # RFC-019: Naaru-powered chat
    identity_enabled: bool = True,  # RFC-023: Adaptive identity
    project_context: dict | None = None,  # For /context command
    workspace_context: dict | None = None,  # RFC-103 linked sources
    codebase_indexer: object | None = None,  # Phase 3: Semantic RAG
    rag_enabled: bool = False,
    rag_stats: dict | None = None,
) -> None:
    """Main interactive chat loop with model-switching support.

    When naaru_enabled=True, uses Naaru's Shards for parallel processing:
    - Consolidator: Extract learnings in background
    - Memory Fetcher: Pre-fetch relevant history
    - Lookahead: Pre-embed queries for next turn

    When identity_enabled=True (RFC-023), uses adaptive identity:
    - Extracts behavioral observations from user messages
    - Periodically digests into identity prompt
    - Injects identity into system prompt
    """

    # RFC-023: Initialize identity store
    identity_store = None
    if identity_enabled and memory_path:
        try:
            from sunwell.identity.store import IdentityStore
            from sunwell.naaru.persona import MURU
            identity_store = IdentityStore(memory_path / "sessions" / dag._session_id if hasattr(dag, '_session_id') else memory_path / "sessions" / "default")
            if identity_store.identity.is_usable():
                console.print(f"[cyan]{MURU.name}:[/cyan] Identity loaded (confidence: {identity_store.identity.confidence:.0%})")
            elif identity_store.identity.observations:
                console.print(f"[cyan]{MURU.name}:[/cyan] Building identity ({len(identity_store.identity.observations)} observations)")
        except Exception as e:
            console.print(f"[dim yellow]Identity disabled: {e}[/dim yellow]")
            identity_store = None

    # Set up tool executor if tools enabled
    tool_executor = None
    mirror_handler = None

    if tools_enabled:
        from sunwell.tools.executor import ToolExecutor
        from sunwell.tools.types import ToolPolicy, ToolTrust

        # RFC-117: Try to resolve project context, fall back to cwd
        from sunwell.project import ProjectResolutionError, resolve_project

        project = None
        try:
            project = resolve_project(cwd=Path.cwd())
            workspace_root = project.root
        except ProjectResolutionError:
            # No project manifest/registry - use cwd (legacy behavior)
            workspace_root = Path.cwd()

        # Create sandbox for shell commands if trust allows
        sandbox = None
        if trust_level in ("shell", "full"):
            from sunwell.skills.sandbox import ScriptSandbox
            from sunwell.skills.types import TrustLevel
            sandbox = ScriptSandbox(trust=TrustLevel.SANDBOXED)

        policy = ToolPolicy(
            trust_level=ToolTrust.from_string(trust_level),
        )

        # RFC-015: Set up mirror handler if enabled
        if mirror_enabled or model_routing_enabled:
            # RFC-085: MirrorHandler now uses Self.get() for source introspection
            # so we just pass the user's workspace (cwd), not Sunwell source root
            from sunwell.mirror import MirrorHandler

            # Get lens config for model routing
            lens_config = None
            if lens and hasattr(lens, "raw_config"):
                lens_config = lens.raw_config

            mirror_storage = memory_path / "mirror" if memory_path else Path(".sunwell/mirror")

            mirror_handler = MirrorHandler(
                workspace=workspace_root,  # User's workspace (RFC-117: from project or cwd)
                storage_path=mirror_storage,
                lens=lens,
                lens_config=lens_config,
                session_model=initial_model_name,
            )

            if mirror_enabled:
                console.print("[cyan]Mirror Neurons:[/cyan] Enabled (self-introspection)")
            if model_routing_enabled:
                console.print("[cyan]Model Routing:[/cyan] Enabled (task-aware model selection)")

        # RFC-027: Set up expertise tools if lens is available
        expertise_handler = None
        if lens:
            from sunwell.embedding import create_embedder
            from sunwell.runtime.retriever import ExpertiseRetriever
            from sunwell.tools.expertise import ExpertiseToolHandler

            embedder = create_embedder()
            retriever = ExpertiseRetriever(lens=lens, embedder=embedder, top_k=5)
            expertise_handler = ExpertiseToolHandler(retriever=retriever, lens=lens)
            console.print("[cyan]Self-Directed Expertise:[/cyan] Enabled (RFC-027)")

        # RFC-117: Use project if available, otherwise workspace
        tool_executor = ToolExecutor(
            project=project,
            workspace=workspace_root if project is None else None,
            sandbox=sandbox,
            policy=policy,
            mirror_handler=mirror_handler,
            expertise_handler=expertise_handler,
        )

    # Mutable chat state
    state = ChatState(
        model=initial_model,
        model_name=initial_model_name,
        lens_name=lens.metadata.name if lens else "Assistant",
        tools_enabled=tools_enabled,
        trust_level=trust_level,
        tool_executor=tool_executor,
        project_context=project_context or {},
        workspace_context=workspace_context,
        codebase_indexer=codebase_indexer,
        rag_enabled=rag_enabled,
        rag_stats=rag_stats or {},
    )

    # Set up model router if requested (RFC-015)
    model_router = None
    if smart:
        # Determine provider from model name (crude)
        provider = initial_model_name.split(":")[0]
        stupid_model = None
        if provider == "ollama":
            stupid_model = create_model("ollama", "gemma3:1b")
        elif provider == "openai":
            stupid_model = create_model("openai", "gpt-4o-mini")

        model_router = ModelRouter(
            primary_model=initial_model,
            stupid_model=stupid_model,
            lens=lens,
        )

        if lens:
            console.print("[cyan]Adaptive Model Selection:[/cyan] Enabled")

    # RFC-019: Initialize Naaru Shards for parallel processing
    shard_pool = None
    convergence = None
    tiny_model = None  # For fact extraction
    if naaru_enabled:
        try:
            from sunwell.naaru.convergence import Convergence
            from sunwell.naaru.shards import ShardPool

            convergence = Convergence(capacity=7)  # Miller's Law: 7±2 items
            shard_pool = ShardPool(convergence=convergence)

            # Create tiny LLM for fact extraction (RFC-020 style micro-distillation)
            try:
                from sunwell.config import get_config, resolve_naaru_model
                from sunwell.models.ollama import OllamaModel
                from sunwell.naaru.persona import MURU

                cfg = get_config()
                voice_model = resolve_naaru_model(
                    cfg.naaru.voice,
                    cfg.naaru.voice_models,
                    check_availability=True,
                )
                if voice_model:
                    tiny_model = OllamaModel(
                        model=voice_model,
                        use_native_api=cfg.naaru.use_native_ollama_api,
                    )
                    console.print(f"[cyan]{MURU.name}:[/cyan] Enabled (parallel + LLM learning via {voice_model})")
                else:
                    tiny_model = None
                    console.print(f"[cyan]{MURU.name}:[/cyan] Enabled (parallel + regex learning)")
            except Exception:
                # Fall back to regex extraction
                from sunwell.naaru.persona import MURU
                tiny_model = None
                console.print(f"[cyan]{MURU.name}:[/cyan] Enabled (parallel + regex learning)")
        except ImportError:
            naaru_enabled = False  # Fall back if Naaru not available

    # RFC-013: No explicit initialization needed - SimulacrumStore handles it

    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()

            if not user_input:
                continue

            # Handle / commands (built-in chat commands)
            if user_input.startswith("/"):
                cmd_result = await _handle_chat_command(
                    user_input, dag, store, state,
                    identity_store=identity_store,
                    tiny_model=tiny_model,
                    system_prompt=system_prompt,
                    lens=lens,  # RFC-131: Pass lens for identity
                )
                if cmd_result == "quit":
                    break
                continue

            # RFC-107 Phase 3: Handle :: skill shortcuts with full execution
            if user_input.startswith("::"):
                # Create ChatSession with model, workspace, and tools
                skill_session = ChatSession(
                    lens=lens,
                    model=state.model,
                    workspace_root=Path.cwd(),
                    tool_executor=tool_executor if tools_enabled else None,
                )
                is_command, result = await handle_command(user_input, skill_session)
                if is_command and result:
                    console.print()
                    console.print(Markdown(result))
                    # Add to conversation history for context
                    dag.add_user_message(user_input)
                    dag.add_assistant_message(result, model=state.model_name)
                continue

            # RFC-023: Inject identity into system prompt
            # RFC-131: Use lens identity if available, fallback to M'uru
            from sunwell.identity.injection import build_system_prompt_with_identity
            user_identity = None
            if identity_store and identity_store.identity.is_usable():
                user_identity = identity_store.identity
            effective_system_prompt = build_system_prompt_with_identity(
                system_prompt, user_identity, lens=lens, include_agent_identity=True
            )

            # RFC-013: Assemble context using hierarchical chunking (hot/warm/cold tiers)
            # This enables infinite rolling history across model switches
            messages, context_stats = store.assemble_messages(
                query=user_input,
                system_prompt=effective_system_prompt,
                max_tokens=4000,
            )

            # Show retrieval info
            if context_stats["retrieved_chunks"] > 0:
                console.print(f"[dim]Retrieved {context_stats['hot_turns']} turns from {context_stats['retrieved_chunks']} chunks[/dim]")
            if context_stats["compression_applied"]:
                console.print(f"[dim]Compressed old context ({context_stats['warm_summaries']} warm, {context_stats['cold_summaries']} cold summaries)[/dim]")

            # RFC-108: Semantic RAG with graceful fallback
            # Show what was retrieved with transparency
            rag_result = RAGResult(context="", references=[])
            if state.rag_enabled and state.codebase_indexer:
                try:
                    rag_result = await _retrieve_relevant_code(
                        state.codebase_indexer, user_input, top_k=3
                    )
                    if rag_result.found_code:
                        # Show transparent references with fallback indicator
                        mode = "[yellow]grep[/yellow]" if rag_result.fallback_used else "[cyan]semantic[/cyan]"
                        refs_display = ", ".join(
                            f"{ref.split(':')[0]} ({score:.0%})"
                            for ref, score in rag_result.references[:3]
                        )
                        console.print(f"[dim]RAG ({mode}) → {refs_display}[/dim]")
                except Exception:
                    pass  # Non-fatal

            # Add current user input (with RAG context if available)
            if rag_result.found_code:
                # Inject retrieved code context before user's question
                augmented_input = f"{rag_result.context}\n\n---\n\n**User Question**: {user_input}"
                messages.append({"role": "user", "content": augmented_input})
            else:
                messages.append({"role": "user", "content": user_input})

            # Now add user turn to DAG for future history
            dag.add_user_message(user_input)

            # Extract facts from user message (name, preferences, context)
            # RFC-019: Use Naaru Consolidator Shard if available
            # RFC-023: Also extract behaviors for identity
            # Messages are queued to state.pending_observations to avoid interleaving with streaming
            if shard_pool and naaru_enabled:
                # Fire-and-forget: Shard extracts in background with tiny LLM
                asyncio.create_task(_naaru_extract_user_facts_and_behaviors(
                    shard_pool, dag, user_input, state, tiny_model, identity_store
                ))
            else:
                # Inline extraction (fallback) - queue to state to avoid interleaving
                try:
                    from sunwell.simulacrum.extractors.extractor import extract_user_facts
                    user_facts = extract_user_facts(user_input)
                    for fact_text, category, confidence in user_facts:
                        learning = Learning(
                            fact=fact_text,
                            source_turns=(dag.active_head,) if dag.active_head else (),
                            confidence=confidence,
                            category=category,
                        )
                        dag.add_learning(learning)
                        state.queue_observation(f"[dim]+ Noted: {fact_text}[/dim]")
                except ImportError:
                    pass

                # RFC-023: Extract behaviors (fallback regex)
                if identity_store:
                    try:
                        from sunwell.identity.extractor import extract_behaviors_regex
                        behaviors = extract_behaviors_regex(user_input)
                        from sunwell.naaru.persona import MURU
                        for behavior_text, confidence in behaviors:
                            identity_store.add_observation(behavior_text, confidence)
                            state.queue_observation(MURU.msg_observed(behavior_text))
                    except ImportError:
                        pass

            # RFC-015: Adaptive Model Selection
            if model_router:
                # Pass requires_tools hint to the router (from state.tools_enabled)
                recommended_model_id = await model_router.route(
                    user_input,
                    requires_tools=state.tools_enabled
                )

                # If the recommended model is different and from the same provider, switch
                provider = state.model_name.split(":")[0]
                if recommended_model_id != state.model_name.split(":")[1]:
                    try:
                        new_llm = create_model(provider, recommended_model_id)
                        state.switch_model(new_llm, f"{provider}:{recommended_model_id}")
                        console.print(f"[dim]Auto-switched to {recommended_model_id} for this task[/dim]")
                    except Exception:
                        pass # Ignore failures in auto-switching

            mode_indicator = f"[green]{state.mode}[/green]" if state.tools_enabled else ""
            console.print(f"\n[bold green]{state.lens_name}[/bold green] [dim]({state.model_name})[/dim]{' ' + mode_indicator if mode_indicator else ''}: ", end="")

            if state.tools_enabled and state.tool_executor:
                # Tool-aware generation
                response = await _generate_with_tools(
                    model=state.model,
                    messages=messages,
                    tool_executor=state.tool_executor,
                    console=console,
                )
            else:
                # Standard streaming generation with proper message structure
                from sunwell.models.protocol import Message

                # Convert dict messages to Message objects with proper roles
                structured_messages = tuple(
                    Message(role=m["role"], content=m["content"])
                    for m in messages
                )

                response_parts = []
                # Use Live display for streaming markdown rendering
                with Live(Markdown(""), console=console, refresh_per_second=8, transient=False) as live:
                    async for chunk in state.model.generate_stream(structured_messages):
                        response_parts.append(chunk)
                        # Re-render markdown with accumulated text
                        live.update(Markdown("".join(response_parts)))
                response = "".join(response_parts)

            console.print()  # Ensure newline after Live display

            # Display any queued observations from background tasks (after streaming)
            state.flush_observations(console)

            # Track last response for /write command
            state.last_response = response

            # Add assistant turn to DAG (tracks which model generated it)
            dag.add_assistant_message(response, model=state.model_name)

            # Auto-extract learnings from response
            # RFC-019: Use Naaru Consolidator Shard if available
            # Note: These learnings appear after the next user input (fire-and-forget)
            if shard_pool and naaru_enabled:
                # Fire-and-forget: Shard consolidates learnings in background
                asyncio.create_task(_naaru_consolidate_learnings(
                    shard_pool, dag, response, user_input, state
                ))
            else:
                # Inline extraction (fallback)
                try:
                    from sunwell.simulacrum.extractors.extractor import auto_extract_learnings
                    extracted = auto_extract_learnings(response, min_confidence=0.6)
                    for learning_text, category, confidence in extracted[:3]:
                        learning = Learning(
                            fact=learning_text,
                            source_turns=(dag.active_head,) if dag.active_head else (),
                            confidence=confidence,
                            category=category,
                        )
                        dag.add_learning(learning)
                except ImportError:
                    pass  # Learning extractor not available

            # RFC-023: Check if identity digest needed
            if identity_store and identity_store.needs_digest(len(dag.turns)):
                asyncio.create_task(_digest_identity_background(
                    identity_store, tiny_model, len(dag.turns), state
                ))

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Saving session...[/yellow]")
            break
        except EOFError:
            break
        except SunwellError as e:
            # Structured error with recovery hints
            console.print(f"\n[red]Error {e.error_id}:[/red] {e.message}")
            if e.recovery_hints:
                console.print("[yellow]Recovery options:[/yellow]")
                for i, hint in enumerate(e.recovery_hints, 1):
                    console.print(f"  {i}. {hint}")
            if e.is_recoverable:
                console.print("[dim]Session preserved. You can retry or use a different approach.[/dim]")
            continue
        except Exception as e:
            # Unexpected error - log and continue
            console.print(f"\n[red]Unexpected error:[/red] {e}")
            console.print("[dim]Type /quit to exit or continue with your next message.[/dim]")
            continue

    # Save on exit with model history
    store.save_session()

    # RFC-023: Persist identity to global on exit
    if identity_store:
        try:
            from sunwell.naaru.persona import MURU
            await identity_store.persist_to_global()
            console.print(f"[dim]{MURU.name} saved ({len(identity_store.identity.observations)} observations)[/dim]")
        except Exception:
            pass  # Non-critical

    if state.models_used:
        console.print(f"[dim]Models used: {' → '.join(state.models_used + [state.model_name])}[/dim]")
    console.print("[green]✓ Session saved[/green]")


async def _handle_chat_command(
    command: str,
    dag: ConversationDAG,
    store: SimulacrumStore,
    state: ChatState,
    identity_store=None,  # RFC-023: Identity store
    tiny_model=None,  # RFC-023: For identity refresh
    system_prompt: str = "",  # Base system prompt from lens
    lens=None,  # RFC-131: Lens for identity resolution
) -> str | None:
    """Handle chat commands. Returns 'quit' to exit."""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/quit" or cmd == "/exit":
        return "quit"

    elif cmd == "/switch":
        # Switch to a different model mid-conversation
        if not arg:
            console.print("[red]Usage: /switch <provider>:<model>[/red]")
            console.print("  Examples: /switch anthropic:claude-sonnet-4-20250514")
            console.print("            /switch openai:gpt-4o")
            console.print("            /switch openai:o1-preview")
            console.print(f"  Current: {state.model_name}")
        else:
            try:
                if ":" in arg:
                    new_provider, new_model = arg.split(":", 1)
                else:
                    new_provider = arg
                    new_model = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514"}.get(arg, "gpt-4o")

                new_llm = create_model(new_provider, new_model)
                old_name = state.model_name
                state.switch_model(new_llm, f"{new_provider}:{new_model}")

                console.print(f"[green]✓ Switched model:[/green] {old_name} → {state.model_name}")
                console.print("[dim]Your headspace (learnings, history, dead ends) is preserved.[/dim]")
            except Exception as e:
                console.print(f"[red]Failed to switch: {e}[/red]")

    elif cmd == "/models":
        # Show model history
        if state.models_used:
            console.print(f"[bold]Model history:[/bold] {' → '.join(state.models_used + [state.model_name])}")
        else:
            console.print(f"[bold]Current model:[/bold] {state.model_name}")

    elif cmd == "/tools":
        # Toggle or configure tools
        if not arg:
            console.print(f"[bold]Tools:[/bold] {'Enabled' if state.tools_enabled else 'Disabled'} ({state.mode_display})")
            console.print("  Usage: /tools on|off")
            if state.tools_enabled:
                console.print(f"  Trust level: {state.trust_level}")
        elif arg.lower() in ("on", "enable", "yes"):
            if not state.tool_executor:
                # Initialize tool executor
                from pathlib import Path as PathLib

                from sunwell.project import ProjectResolutionError, resolve_project
                from sunwell.tools.executor import ToolExecutor
                from sunwell.tools.types import ToolPolicy, ToolTrust

                # RFC-117: Try to resolve project context
                project = None
                workspace = PathLib.cwd()
                try:
                    project = resolve_project(cwd=workspace)
                except ProjectResolutionError:
                    pass  # Use cwd fallback

                policy = ToolPolicy(trust_level=ToolTrust.from_string(state.trust_level))
                state.tool_executor = ToolExecutor(
                    project=project,
                    workspace=workspace if project is None else None,
                    sandbox=None,
                    policy=policy,
                )
            state.tools_enabled = True
            console.print(f"[green]✓ Tools enabled[/green] ({state.trust_level})")
        elif arg.lower() in ("off", "disable", "no"):
            state.tools_enabled = False
            console.print("[yellow]✓ Tools disabled[/yellow]")
        else:
            console.print(f"[red]Unknown: /tools {arg}[/red]")
            console.print("  Usage: /tools on|off")

    elif cmd == "/context":
        # Show current workspace context
        if state.project_context:
            summary = _format_context_summary(state.project_context, state.workspace_context)
            console.print(summary)

            # Show RAG stats
            if state.rag_enabled and state.rag_stats:
                console.print("")
                console.print("### Semantic RAG (Phase 3)")
                console.print("**Status**: Enabled")
                console.print(f"**Files indexed**: {state.rag_stats.get('file_count', 0)}")
                console.print(f"**Code chunks**: {state.rag_stats.get('chunk_count', 0)}")
                console.print(f"**From cache**: {state.rag_stats.get('from_cache', False)}")
            elif state.rag_enabled:
                console.print("")
                console.print("### Semantic RAG")
                console.print("**Status**: Enabled but no index loaded")
        else:
            console.print("[dim]No workspace context loaded.[/dim]")
            console.print("[dim]Run with --workspace flag or from a project directory.[/dim]")

    elif cmd == "/refresh":
        # Rebuild workspace context
        console.print("[dim]Refreshing context...[/dim]")
        try:
            # Clear cache
            cache_path = Path.cwd() / ".sunwell" / "context.json"
            if cache_path.exists():
                cache_path.unlink()

            # Rebuild
            _, new_ctx = _build_smart_workspace_context(use_cache=False)
            state.project_context = new_ctx

            # Also refresh workspace context
            new_ws_ctx, new_ws_data = await _load_workspace_context(Path.cwd())
            if new_ws_data:
                state.workspace_context = new_ws_data

            ptype = new_ctx.get("type", "unknown")
            framework = new_ctx.get("framework")
            type_info = ptype.title()
            if framework:
                type_info += f" ({framework})"

            console.print(f"[green]✓ Context refreshed:[/green] {type_info}")
            if state.workspace_context:
                links = len(state.workspace_context.get("links", []))
                symbols = len(state.workspace_context.get("symbols", []))
                console.print(f"[dim]  {links} linked sources, {symbols} symbols[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to refresh: {e}[/red]")

    elif cmd == "/index":
        # Rebuild codebase index for RAG
        console.print("[dim]Rebuilding codebase index...[/dim]")
        try:
            # Clear cache
            cache_path = Path.cwd() / ".sunwell" / "index" / "codebase_index.json"
            if cache_path.exists():
                cache_path.unlink()

            # Need embedder - get it from the store or create new
            from sunwell.embedding import create_embedder
            embedder = create_embedder()

            # Rebuild index
            new_indexer, new_stats = await _build_codebase_index(
                Path.cwd(), embedder, force_rebuild=True
            )

            if new_indexer and new_stats.get("indexed"):
                state.codebase_indexer = new_indexer
                state.rag_stats = new_stats
                state.rag_enabled = True
                console.print(
                    f"[green]✓ Index rebuilt:[/green] {new_stats.get('chunk_count', 0)} chunks "
                    f"from {new_stats.get('file_count', 0)} files"
                )
            else:
                console.print("[yellow]No code files found to index[/yellow]")
        except Exception as e:
            console.print(f"[red]Failed to rebuild index: {e}[/red]")

    elif cmd == "/search":
        # Manual code search (Phase 4: Visible RAG)
        if not arg:
            console.print("[yellow]Usage: /search <query>[/yellow]")
            console.print("[dim]Example: /search authentication handler[/dim]")
        elif not state.codebase_indexer:
            console.print("[yellow]No codebase index. Run /index first.[/yellow]")
        else:
            try:
                result = await _retrieve_relevant_code(state.codebase_indexer, arg, top_k=5)
                if result.found_code:
                    console.print(f"\n[bold]Search results for:[/bold] {arg}\n")
                    for ref, score in result.references:
                        # Parse reference for nicer display
                        console.print(f"  [cyan]{score:.0%}[/cyan] {ref}")
                    console.print("")
                    console.print("[dim]Tip: These chunks will be used as context if you ask about this topic.[/dim]")
                else:
                    console.print(f"[dim]No relevant code found for: {arg}[/dim]")
            except Exception as e:
                console.print(f"[red]Search failed: {e}[/red]")

    elif cmd == "/rag":
        # Toggle RAG (Phase 4)
        if arg.lower() == "on":
            if state.codebase_indexer:
                state.rag_enabled = True
                console.print("[green]✓ RAG enabled[/green]")
            else:
                console.print("[yellow]No codebase index. Run /index first.[/yellow]")
        elif arg.lower() == "off":
            state.rag_enabled = False
            console.print("[green]✓ RAG disabled[/green]")
        else:
            status = "[green]enabled[/green]" if state.rag_enabled else "[dim]disabled[/dim]"
            chunks = state.rag_stats.get("chunk_count", 0) if state.rag_stats else 0
            console.print(f"RAG: {status} ({chunks} chunks indexed)")
            console.print("[dim]Usage: /rag on|off[/dim]")

    elif cmd == "/save":
        store.save_session()
        console.print("[green]✓ Session saved[/green]")

    elif cmd == "/write":
        # Write last response to a file
        if not arg:
            console.print("[red]Usage: /write <path>[/red]")
            console.print("  Saves the last assistant response to a file")
        elif not state.last_response:
            console.print("[yellow]No response to save yet[/yellow]")
        else:
            from pathlib import Path
            try:
                path = Path(arg).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(state.last_response)
                console.print(f"[green]✓ Saved to:[/green] {path}")
            except Exception as e:
                console.print(f"[red]Failed to write: {e}[/red]")

    elif cmd == "/read":
        # Read a file into context
        if not arg:
            console.print("[red]Usage: /read <path>[/red]")
        else:
            from pathlib import Path
            try:
                path = Path(arg).expanduser()
                if not path.exists():
                    console.print(f"[red]File not found: {path}[/red]")
                else:
                    content = path.read_text()
                    # Show preview and add to context
                    lines = content.split('\n')
                    preview = '\n'.join(lines[:10])
                    if len(lines) > 10:
                        preview += f"\n... ({len(lines) - 10} more lines)"
                    console.print(f"[dim]Read {path} ({len(lines)} lines):[/dim]")
                    console.print(f"```\n{preview}\n```")
                    # Add as a system message
                    dag.add_user_message(f"[File: {path}]\n```\n{content}\n```")
            except Exception as e:
                console.print(f"[red]Failed to read: {e}[/red]")

    elif cmd == "/debug":
        # Debug commands for troubleshooting
        if arg == "prompt" or arg == "system":
            # Show the effective system prompt
            # RFC-131: Pass lens for identity resolution
            from sunwell.identity.injection import build_system_prompt_with_identity
            user_identity = None
            if identity_store and identity_store.identity.is_usable():
                user_identity = identity_store.identity
            effective_prompt = build_system_prompt_with_identity(
                system_prompt, user_identity, lens=lens, include_agent_identity=True
            )
            console.print("[bold]Effective System Prompt:[/bold]")
            console.print("─" * 60)
            console.print(effective_prompt)
            console.print("─" * 60)
            console.print(f"[dim]Length: {len(effective_prompt)} chars[/dim]")
        elif arg == "identity":
            if identity_store:
                console.print("[bold]Identity Debug:[/bold]")
                console.print(f"  Paused: {identity_store.identity.paused}")
                console.print(f"  Confidence: {identity_store.identity.confidence:.0%}")
                console.print(f"  Observations: {len(identity_store.identity.observations)}")
                console.print(f"  Usable: {identity_store.identity.is_usable()}")
                if identity_store.identity.prompt:
                    console.print(f"  Prompt length: {len(identity_store.identity.prompt)} chars")
            else:
                console.print("[yellow]Identity store not initialized[/yellow]")
        else:
            console.print("[bold]Debug commands:[/bold]")
            console.print("  /debug prompt   - Show effective system prompt")
            console.print("  /debug identity - Show identity state")

    elif cmd == "/stats":
        stats = dag.stats
        console.print(f"Turns: {stats['total_turns']} | Branches: {stats['branches']} | "
                     f"Dead ends: {stats['dead_ends']} | Learnings: {stats['learnings']}")

    elif cmd == "/branch":
        if not arg:
            console.print("[red]Usage: /branch <name>[/red]")
        else:
            dag.branch(arg)
            console.print(f"[green]✓ Created branch:[/green] {arg}")

    elif cmd == "/checkout":
        if not arg:
            console.print("[red]Usage: /checkout <branch>[/red]")
            console.print(f"Available: {', '.join(dag.branches.keys()) or 'none'}")
        else:
            try:
                dag.checkout(arg)
                console.print(f"[green]✓ Switched to:[/green] {arg}")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")

    elif cmd == "/dead-end":
        dag.mark_dead_end()
        console.print("[yellow]✓ Marked current path as dead end[/yellow]")

    elif cmd == "/learn":
        if not arg:
            console.print("[red]Usage: /learn <fact>[/red]")
        else:
            learning = Learning(
                fact=arg,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=1.0,
                category="fact",
            )
            dag.add_learning(learning)
            console.print("[green]✓ Learning added[/green]")

    elif cmd == "/learnings":
        learnings = dag.get_active_learnings()
        if not learnings:
            console.print("[dim]No learnings yet[/dim]")
        else:
            console.print("[bold]Learnings:[/bold]")
            for l in learnings:
                console.print(f"  [{l.category}] {l.fact}")

    elif cmd == "/memory":
        # RFC-026: Unified memory view
        import json as json_module

        from sunwell.simulacrum.unified_view import UnifiedMemoryView

        view = UnifiedMemoryView.from_session(
            dag=dag,
            identity_store=identity_store,
            session_name=store.session_name if hasattr(store, 'session_name') else "",
        )

        if arg.lower() == "json":
            console.print(json_module.dumps(view.to_json(), indent=2))
        elif arg.lower() == "facts":
            if view.facts:
                console.print("[bold]Facts:[/bold]")
                for f in view.facts:
                    status = "✅" if f.quality_score and f.quality_score >= 0.7 else "⚠️"
                    console.print(f"  {status} [{f.category}] {f.content} ({int(f.confidence*100)}%)")
            else:
                console.print("[dim]No facts learned yet[/dim]")
        elif arg.lower() == "identity":
            if view.identity_prompt:
                console.print(f"[bold]Identity (confidence: {int(view.identity_confidence*100)}%):[/bold]")
                console.print(f"  {view.identity_prompt}")
            else:
                console.print("[dim]No identity model yet[/dim]")
        else:
            console.print(view.render_panel())

    elif cmd == "/identity":
        # RFC-023: Identity management commands
        if not identity_store:
            console.print("[yellow]Identity system not enabled[/yellow]")
            console.print("[dim]Start chat with --identity flag or check memory_path configuration[/dim]")
        else:
            from sunwell.identity.commands import handle_identity_command
            await handle_identity_command(
                arg, identity_store, console, tiny_model, len(dag.turns)
            )

    elif cmd == "/help":
        console.print("""
[bold]File Operations:[/bold]
  /write <path>     Save last response to a file
  /read <path>      Read a file into context

[bold]Model & Tools:[/bold]
  /switch <p:m>     Switch model (e.g. /switch anthropic:claude-sonnet-4-20250514)
  /models           Show model history for this session
  /tools on|off     Toggle Agent mode (tool calling)

[bold]Memory Commands (RFC-026):[/bold]
  /memory           View unified memory (facts, identity, behaviors)
  /memory facts     Show just facts
  /memory identity  Show identity model
  /memory json      Export as JSON
  /learnings        Show all learnings
  /learn <fact>     Add a learning/insight

[bold]Simulacrum Commands:[/bold]
  /branch <name>    Create a named branch
  /checkout <name>  Switch to a branch
  /dead-end         Mark current path as dead end
  /stats            Show session statistics
  /save             Save session
  /quit             Exit (auto-saves)

[bold]Identity (RFC-023):[/bold]
  /identity         View your identity model
  /identity rate    Rate how accurate the model is (1-5)
  /identity refresh Force re-synthesis
  /identity pause   Stop learning (keep existing)
  /identity resume  Continue learning
  /identity clear   Start fresh
  /identity export  Export to JSON

[bold]Evolution Analysis:[/bold]
  /trace            Show turn-by-turn evolution report
  /trace clear      Clear trace history
  /trace json       Export traces as JSON

[bold]Workspace Context:[/bold]
  /context          Show detected project, key files, RAG stats
  /refresh          Rebuild workspace context cache
  /index            Rebuild codebase RAG index

[bold]Semantic Code Search (RAG):[/bold]
  /search <query>   Search codebase for relevant code
  /rag on|off       Toggle per-query code retrieval

[bold]Tip:[/bold] Your headspace persists when you /switch models!
[bold]Tip:[/bold] Use /tools on to enable Agent mode with file read/write!
[bold]Tip:[/bold] RAG auto-retrieves relevant code for each question!
""")

    elif cmd == "/trace":
        # Turn-by-turn evolution analysis
        from sunwell.simulacrum.tracer import TRACER

        if arg.lower() == "clear":
            TRACER.clear()
            console.print("[green]✓ Trace history cleared[/green]")
        elif arg.lower() == "json":
            import json
            traces = TRACER.get_json_export()
            if traces:
                console.print(json.dumps(traces, indent=2))
            else:
                console.print("[yellow]No traces recorded yet[/yellow]")
        else:
            report = TRACER.get_evolution_report()
            console.print(report)

    else:
        console.print(f"[red]Unknown command: {cmd}[/red]")
        console.print("[dim]Type /help for available commands[/dim]")

    return None


# RFC-019: Naaru Shard helper functions for background processing

async def _naaru_extract_user_facts(
    shard_pool: ShardPool,
    dag: ConversationDAG,
    user_input: str,
    state: ChatState,
    tiny_model=None,  # Optional tiny LLM for fact extraction
) -> None:
    """Use Naaru Consolidator Shard to extract facts from user input.

    Uses tiny LLM (gemma3:1b) for flexible fact extraction:
    - "i have a cat named milo" → Noted: User has a cat named Milo
    - "her nickname is kiki" → Noted: User's cat's nickname is Kiki

    Falls back to regex patterns if no tiny model available.

    Runs in background while model generates response.
    Queues messages to state.pending_observations for display after streaming.
    """
    try:
        # Prefer LLM-based extraction (more flexible)
        if tiny_model:
            from sunwell.simulacrum.extractors.extractor import extract_user_facts_with_llm
            user_facts = await extract_user_facts_with_llm(user_input, tiny_model)
        else:
            # Fall back to regex
            from sunwell.simulacrum.extractors.extractor import extract_user_facts
            user_facts = extract_user_facts(user_input)

        for fact_text, category, confidence in user_facts:
            learning = Learning(
                fact=fact_text,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=confidence,
                category=category,
            )
            dag.add_learning(learning)
            from sunwell.naaru.persona import MURU
            state.queue_observation(MURU.msg_noted(fact_text, category))
    except Exception as e:
        # Log but don't crash - this is background task
        from sunwell.naaru.persona import MURU
        state.queue_observation(MURU.msg_error("fact extraction", str(e)))


async def _naaru_consolidate_learnings(
    shard_pool: ShardPool,
    dag: ConversationDAG,
    response: str,
    user_input: str,
    state: ChatState | None = None,  # For queueing visibility messages
) -> None:
    """Use Naaru Consolidator Shard to extract learnings from response.

    Runs in background after response is shown to user.
    Queues messages about what was learned for display after streaming.
    """

    try:
        # Use Shard's consolidate method
        await shard_pool.consolidate_learnings(
            task={"user_input": user_input, "response": response},
            result={"content": response},
        )

        # Also run inline extraction for now (Shard stores in Convergence)
        from sunwell.simulacrum.extractors.extractor import auto_extract_learnings
        extracted = auto_extract_learnings(response, min_confidence=0.6)

        added_count = 0
        for learning_text, category, confidence in extracted[:3]:
            learning = Learning(
                fact=learning_text,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=confidence,
                category=category,
            )
            dag.add_learning(learning)
            added_count += 1
            # Queue what M'uru learned for display after streaming
            if state:
                from sunwell.naaru.persona import MURU
                state.queue_observation(MURU.msg_learned(learning_text))

        # Summary if learnings were added
        if added_count > 0 and state:
            state.queue_observation(f"[dim]📚 Total learnings in session: {len(dag.learnings)}[/dim]")
    except Exception as e:
        if state:
            from sunwell.naaru.persona import MURU
            state.queue_observation(MURU.msg_error("consolidation", str(e)))


# RFC-023: Identity extraction and digest helper functions

async def _naaru_extract_user_facts_and_behaviors(
    shard_pool: ShardPool,
    dag: ConversationDAG,
    user_input: str,
    state: ChatState,
    tiny_model=None,
    identity_store=None,
) -> None:
    """Extract facts AND behaviors from user input.

    RFC-023 extension of _naaru_extract_user_facts to also capture
    behavioral observations for the identity system.

    Includes turn-by-turn tracing for evolution analysis.
    Queues messages to state.pending_observations for display after streaming.
    """
    # Import tracer for turn evolution tracking
    from sunwell.simulacrum.tracer import TRACER

    # Begin tracing this turn
    turn_id = dag.active_head or "unknown"
    TRACER.begin_turn(turn_id, user_input)

    # Snapshot identity before extraction
    if identity_store:
        TRACER.log_identity_snapshot(
            "before",
            observation_count=len(identity_store.identity.observations),
            confidence=identity_store.identity.confidence,
            prompt=identity_store.identity.prompt,
            tone=identity_store.identity.tone,
            values=identity_store.identity.values,
        )

    try:
        if tiny_model:
            # Use two-tier extraction (RFC-023)
            from sunwell.identity.extractor import extract_with_categories
            facts, behaviors = await extract_with_categories(user_input, tiny_model)

            from sunwell.naaru.persona import MURU

            # Store facts in DAG (existing behavior)
            for fact_text, category, confidence in facts:
                learning = Learning(
                    fact=fact_text,
                    source_turns=(dag.active_head,) if dag.active_head else (),
                    confidence=confidence,
                    category=category,
                )
                dag.add_learning(learning)
                state.queue_observation(MURU.msg_noted(fact_text, category))

                # Trace the extraction
                TRACER.log_extraction("fact", fact_text, confidence, category)

            # Store behaviors in identity store (RFC-023)
            if identity_store:
                for behavior_text, confidence in behaviors:
                    identity_store.add_observation(
                        behavior_text,
                        confidence,
                        turn_id=dag.active_head
                    )
                    state.queue_observation(MURU.msg_observed(behavior_text))

                    # Trace the extraction
                    TRACER.log_extraction("behavior", behavior_text, confidence)
        else:
            # Fall back to regex for both
            from sunwell.simulacrum.extractors.extractor import extract_user_facts
            user_facts = extract_user_facts(user_input)

            from sunwell.naaru.persona import MURU

            for fact_text, category, confidence in user_facts:
                learning = Learning(
                    fact=fact_text,
                    source_turns=(dag.active_head,) if dag.active_head else (),
                    confidence=confidence,
                    category=category,
                )
                dag.add_learning(learning)
                state.queue_observation(MURU.msg_noted(fact_text, category))

                # Trace the extraction
                TRACER.log_extraction("fact", fact_text, confidence, category)

            # RFC-023: Extract behaviors with regex fallback
            if identity_store:
                from sunwell.identity.extractor import extract_behaviors_regex
                behaviors = extract_behaviors_regex(user_input)
                for behavior_text, confidence in behaviors:
                    identity_store.add_observation(behavior_text, confidence)
                    state.queue_observation(MURU.msg_observed(behavior_text))

                    # Trace the extraction
                    TRACER.log_extraction("behavior", behavior_text, confidence)

        # Snapshot identity after extraction
        if identity_store:
            TRACER.log_identity_snapshot(
                "after",
                observation_count=len(identity_store.identity.observations),
                confidence=identity_store.identity.confidence,
                prompt=identity_store.identity.prompt,
                tone=identity_store.identity.tone,
                values=identity_store.identity.values,
            )

    except Exception as e:
        from sunwell.naaru.persona import MURU
        state.queue_observation(MURU.msg_error("extraction", str(e)))
    finally:
        # End the turn trace (without assistant response - that's added later)
        TRACER.end_turn()


async def _digest_identity_background(
    identity_store,
    tiny_model,
    turn_count: int,
    state: ChatState,
) -> None:
    """Background task to digest identity from observations.

    RFC-023: Synthesizes behavioral observations into identity prompt.
    Queues messages to state.pending_observations for display after streaming.
    """
    try:
        from sunwell.identity.digest import digest_identity, quick_digest

        obs_texts = [o.observation for o in identity_store.identity.observations]

        if tiny_model:
            new_identity = await digest_identity(
                observations=obs_texts,
                current_identity=identity_store.identity,
                tiny_model=tiny_model,
            )
        else:
            # Heuristic fallback
            prompt, confidence = await quick_digest(obs_texts, identity_store.identity.prompt)
            if prompt:
                from sunwell.identity.store import Identity
                new_identity = Identity(
                    observations=identity_store.identity.observations,
                    prompt=prompt,
                    confidence=confidence,
                )
            else:
                return

        if new_identity.is_usable():
            identity_store.update_digest(
                prompt=new_identity.prompt,
                confidence=new_identity.confidence,
                turn_count=turn_count,
                tone=new_identity.tone,
                values=new_identity.values,
            )
            from sunwell.naaru.persona import MURU
            state.queue_observation(MURU.msg_identity_updated(new_identity.confidence))
    except Exception as e:
        from sunwell.naaru.persona import MURU
        state.queue_observation(MURU.msg_error("identity digest", str(e)))
