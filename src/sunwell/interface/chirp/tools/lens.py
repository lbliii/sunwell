"""Lens tools for Chirp MCP integration.

Exposes Sunwell's lens system (domain expertise) via Chirp's @app.tool() decorator.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chirp import App

logger = logging.getLogger(__name__)


def register_lens_tools(app: App) -> None:
    """Register lens-related tools with Chirp app.

    Registers:
    - sunwell_lens: Get lens expertise
    - sunwell_list_lenses: List available lenses
    - sunwell_route: Route shortcut to lens

    Args:
        app: Chirp application instance
    """

    def _get_lens_discovery():
        """Get LensDiscovery instance."""
        from sunwell.planning.naaru.expertise.discovery import LensDiscovery

        return LensDiscovery()

    def _get_lens_loader():
        """Get LensLoader instance."""
        from sunwell.foundation.schema.loader import LensLoader

        return LensLoader()

    @app.tool(
        "sunwell_lens",
        description="Get domain expertise from a lens (professional perspective and heuristics)"
    )
    def sunwell_lens(
        name: str,
        components: list[str] | None = None,
    ) -> dict:
        """Get lens as injectable expertise.

        A lens provides domain expertise including:
        - Heuristics: Professional guidelines and best practices
        - Anti-patterns: Common mistakes to avoid
        - Communication style: Tone and formatting guidance

        Args:
            name: Lens name (e.g., "coder", "tech-writer") or path to .lens file
            components: Optional list of specific heuristic names to include

        Returns:
            Dict with lens metadata and heuristics
        """
        try:
            discovery = _get_lens_discovery()
            loader = _get_lens_loader()

            # Find lens
            lens_path = discovery.find_lens(name)
            if not lens_path:
                available = discovery.list_available()
                return {
                    "error": f"Lens '{name}' not found",
                    "available": [l.name for l in available],
                }

            # Load lens
            lens = loader.load_lens(lens_path)

            # Format response
            result = {
                "name": lens.metadata.name,
                "domain": lens.metadata.domain,
                "version": str(lens.metadata.version) if lens.metadata.version else "0.1.0",
                "description": lens.metadata.description[:200] if lens.metadata.description else None,
                "heuristics_count": len(lens.heuristics),
                "skills_count": len(lens.skills) if hasattr(lens, "skills") else 0,
            }

            # Include heuristics summary
            if lens.heuristics:
                heuristics = []
                for h in lens.heuristics[:10]:  # Limit to 10 for summary
                    heuristics.append({
                        "name": h.name,
                        "type": h.type,
                        "description": h.description[:100] if h.description else None,
                    })
                result["heuristics"] = heuristics

            return result

        except Exception as e:
            logger.error(f"Error loading lens: {e}")
            return {"error": str(e)}

    @app.tool(
        "sunwell_list_lenses",
        description="List all available lenses with their domains and capabilities"
    )
    def sunwell_list_lenses() -> dict:
        """List available lenses.

        Returns:
            Dict with lenses list
        """
        try:
            discovery = _get_lens_discovery()

            # Get all lens files from search paths
            lenses = []
            for search_path in discovery.search_paths:
                if search_path.exists():
                    for lens_file in search_path.glob("*.lens"):
                        lenses.append({
                            "name": lens_file.stem,
                            "path": str(lens_file),
                            "domain": None,  # Would need to parse .lens file
                            "description": f"Lens file: {lens_file.name}",
                        })

            return {
                "lenses": lenses,
                "count": len(lenses),
            }

        except Exception as e:
            logger.error(f"Error listing lenses: {e}")
            return {"error": str(e), "lenses": []}

    @app.tool(
        "sunwell_route",
        description="Route a shortcut command to the appropriate lens"
    )
    def sunwell_route(command: str) -> dict:
        """Route shortcut to lens with confidence scoring.

        Args:
            command: Shortcut command (e.g., "::code", "::review")

        Returns:
            Dict with routing result and confidence
        """
        try:
            discovery = _get_lens_discovery()
            command_clean = command.strip().lower().replace("::", "")

            # Simple routing based on lens file names
            available_lenses = []
            for search_path in discovery.search_paths:
                if search_path.exists():
                    available_lenses.extend([f.stem for f in search_path.glob("*.lens")])

            # Try exact match
            for lens_name in available_lenses:
                if lens_name.lower() == command_clean:
                    return {
                        "command": command,
                        "lens": lens_name,
                        "confidence": 1.0,
                        "reason": "Exact name match",
                    }

            # Try partial match
            for lens_name in available_lenses:
                if command_clean in lens_name.lower():
                    return {
                        "command": command,
                        "lens": lens_name,
                        "confidence": 0.7,
                        "reason": "Partial name match",
                    }

            return {
                "command": command,
                "lens": None,
                "confidence": 0.0,
                "reason": "No matching lens found",
                "available": available_lenses,
            }

        except Exception as e:
            logger.error(f"Error routing command: {e}")
            return {"error": str(e), "lens": None}

    logger.debug("Registered lens tools: sunwell_lens, sunwell_list_lenses, sunwell_route")
