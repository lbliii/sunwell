"""MCP lens tools for Sunwell.

Provides sunwell_lens and sunwell_list tools for accessing lenses.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import mcp_json, omit_empty, truncate

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_lens_tools(mcp: FastMCP, lenses_dir: str | None = None) -> None:
    """Register lens-related tools.

    Args:
        mcp: FastMCP server instance
        lenses_dir: Optional path to lenses directory
    """
    from sunwell.foundation.schema.loader import LensLoader
    from sunwell.planning.naaru.expertise.discovery import LensDiscovery

    # Initialize discovery with custom path if provided
    discovery = LensDiscovery()
    if lenses_dir:
        discovery.search_paths.insert(0, Path(lenses_dir))

    loader = LensLoader()

    @mcp.tool()
    def sunwell_lens(
        name: str,
        components: list[str] | None = None,
        include_context: bool = True,
    ) -> str:
        """
        Get a lens as injectable expertise for your agent context.

        A lens provides domain expertise including:
        - Heuristics: Professional guidelines and best practices
        - Anti-patterns: Common mistakes to avoid
        - Communication style: Tone and formatting guidance
        - Framework: Methodology for the domain

        Set include_context=False for thin mode (~200 tokens metadata only).
        Set include_context=True (default) for full injectable context (~5-15k tokens).

        Args:
            name: Lens name (e.g., "coder", "tech-writer") or path to .lens file
            components: Optional list of specific heuristic names to include.
                       If None, includes all components.
            include_context: If True (default), include full injectable context.
                            If False, return metadata only (thin mode).

        Returns:
            JSON with lens metadata and optionally injectable context string
        """
        lens = _load_lens(name, discovery, loader)

        if not lens:
            return mcp_json(
                {
                    "error": f"Lens '{name}' not found",
                    "available": _list_available_names(discovery, loader),
                },
                "compact",
            )

        result: dict = omit_empty({
            "name": lens.metadata.name,
            "domain": lens.metadata.domain,
            "version": str(lens.metadata.version) if lens.metadata.version else "0.1.0",
            "description": truncate(lens.metadata.description, 200),
            "heuristics_count": len(lens.heuristics),
            "skills_count": len(lens.skills),
            "path": str(lens.source_path) if lens.source_path else None,
        })

        # Include shortcuts if lens has router
        if lens.router and lens.router.shortcuts:
            result["shortcuts"] = dict(lens.router.shortcuts)

        # Thin mode: metadata only
        if include_context:
            result["context"] = lens.to_context(components)
            return mcp_json(result, "full")

        return mcp_json(result, "compact")

    @mcp.tool()
    def sunwell_list(format: str = "compact") -> str:
        """
        List all available lenses with metadata.

        Choose format based on your token budget:
        - "minimal" / "summary": ~500 tokens - Names and domains only
        - "compact": ~2000 tokens - Full metadata as JSON (default)
        - "full": ~4000 tokens - Complete with heuristics preview

        Args:
            format: Output format - "minimal", "summary", "compact", or "full"

        Returns:
            JSON list of available lenses with metadata
        """
        # Normalize: treat "summary" as "minimal" for backward compat
        fmt = format.lower() if format else "compact"
        if fmt == "summary":
            fmt = "minimal"

        lenses_data: list[dict] = []

        for search_path in discovery.search_paths:
            if not search_path.exists():
                continue

            for lens_path in search_path.glob("*.lens"):
                try:
                    lens = loader.load(lens_path)
                    if not lens:
                        continue

                    entry: dict = {
                        "name": lens.metadata.name,
                        "domain": lens.metadata.domain,
                    }

                    if fmt != "minimal":
                        entry["path"] = str(lens_path)
                        entry.update(
                            {
                                "version": (
                                    str(lens.metadata.version)
                                    if lens.metadata.version
                                    else "0.1.0"
                                ),
                                "description": truncate(lens.metadata.description, 120),
                                "heuristics_count": len(lens.heuristics),
                                "skills_count": len(lens.skills),
                            }
                        )

                        # Include shortcuts
                        if lens.router and lens.router.shortcuts:
                            entry["shortcuts"] = list(lens.router.shortcuts.keys())

                    if fmt == "full":
                        entry["description"] = lens.metadata.description
                        # Include top heuristics preview
                        sorted_heuristics = sorted(
                            lens.heuristics,
                            key=lambda h: h.priority,
                            reverse=True,
                        )[:3]
                        entry["top_heuristics"] = [
                            {
                                "name": h.name,
                                "rule": truncate(h.rule, 100),
                            }
                            for h in sorted_heuristics
                        ]

                    lenses_data.append(entry)
                except Exception:
                    continue

            # Also check .lens.yaml files
            for lens_path in search_path.glob("*.lens.yaml"):
                try:
                    lens = loader.load(lens_path)
                    if not lens:
                        continue

                    entry = {
                        "name": lens.metadata.name,
                        "domain": lens.metadata.domain,
                    }

                    if fmt != "minimal":
                        entry["path"] = str(lens_path)
                        entry.update(
                            {
                                "version": (
                                    str(lens.metadata.version)
                                    if lens.metadata.version
                                    else "0.1.0"
                                ),
                                "description": truncate(lens.metadata.description, 120),
                                "heuristics_count": len(lens.heuristics),
                                "skills_count": len(lens.skills),
                            }
                        )

                    lenses_data.append(entry)
                except Exception:
                    continue

        # Sort by name
        lenses_data.sort(key=lambda x: x["name"])

        return mcp_json(
            {
                "lenses": lenses_data,
                "total": len(lenses_data),
                "format": fmt,
            },
            fmt if fmt in ("compact", "full") else "compact",
        )


def _load_lens(name: str, discovery, loader):
    """Load a lens by name or path."""
    from sunwell.foundation.core.lens import Lens

    # Check if it's a path
    if name.endswith(".lens") or "/" in name:
        path = Path(name)
        if path.exists():
            return loader.load(path)

    # Try by name in search paths
    for search_path in discovery.search_paths:
        for ext in [".lens", ".lens.yaml"]:
            lens_path = search_path / f"{name}{ext}"
            if lens_path.exists():
                try:
                    return loader.load(lens_path)
                except Exception:
                    continue

    return None


def _list_available_names(discovery, loader) -> list[str]:
    """Get list of available lens names."""
    names = []
    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue
        for lens_path in search_path.glob("*.lens"):
            try:
                lens = loader.load(lens_path)
                if lens:
                    names.append(lens.metadata.name)
            except Exception:
                continue
    return sorted(set(names))[:10]  # Return top 10
