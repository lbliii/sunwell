"""Context builder for workspace context."""

import json
import time
from pathlib import Path

from sunwell.cli.chat.project_detector import ProjectDetector


class ContextBuilder:
    """Builds workspace context for chat prompts."""

    def __init__(self, cwd: Path | None = None) -> None:
        """Initialize context builder.

        Args:
            cwd: Current working directory (defaults to Path.cwd())
        """
        self._cwd = cwd or Path.cwd()
        self._cache_path = self._cwd / ".sunwell" / "context.json"

    def build_smart_workspace_context(
        self,
        use_cache: bool = True,
    ) -> tuple[str, dict]:
        """Build intelligent workspace context with project detection.

        Args:
            use_cache: Whether to use cached context if available

        Returns:
            Tuple of (formatted_context, context_dict)
        """
        # Try cache first
        if use_cache:
            cached = self._load_cached_context()
            if cached:
                return self._format_context(cached), cached

        # Detect project
        ptype, framework = ProjectDetector.detect_project_type(self._cwd)
        key_files = ProjectDetector.find_key_files(self._cwd)
        entry_points = ProjectDetector.find_entry_points(self._cwd, ptype) if ptype != "unknown" else []
        tree = ProjectDetector.build_directory_tree(self._cwd)

        context = {
            "path": str(self._cwd),
            "name": self._cwd.name,
            "type": ptype,
            "framework": framework,
            "key_files": [(k, v) for k, v in key_files],
            "entry_points": entry_points,
            "tree": tree,
        }

        # Cache for next time
        try:
            self._save_context_cache(context)
        except OSError:
            pass  # Non-fatal

        return self._format_context(context), context

    def build_workspace_context(self) -> str:
        """Build workspace context (simple fallback version).

        Returns:
            Formatted context string
        """
        context, _ = self.build_smart_workspace_context(use_cache=True)
        return context

    def _load_cached_context(self) -> dict | None:
        """Load cached context if fresh (< 1 hour old).

        Returns:
            Cached context dict or None if stale/missing
        """
        if not self._cache_path.exists():
            return None

        try:
            stat = self._cache_path.stat()
            age_hours = (time.time() - stat.st_mtime) / 3600
            if age_hours > 1:  # Stale after 1 hour
                return None

            return json.loads(self._cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_context_cache(self, context: dict) -> None:
        """Save context to cache.

        Args:
            context: Context dict to cache
        """
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(context, indent=2))

    def _format_context(self, ctx: dict) -> str:
        """Format context dict into markdown for system prompt.

        Args:
            ctx: Context dictionary

        Returns:
            Formatted markdown string
        """
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

    def format_context_summary(self, ctx_data: dict, workspace_data: dict | None = None) -> str:
        """Format context summary for /context command.

        Args:
            ctx_data: Context dictionary
            workspace_data: Optional workspace data from RFC-103

        Returns:
            Formatted summary string
        """
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
            age_mins = int((time.time() - cache_path.stat().st_mtime) / 60)
            lines.append(f"**Cache age**: {age_mins} minutes")

        return "\n".join(lines)
