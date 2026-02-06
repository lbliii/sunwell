"""MCP routing tools for Sunwell.

Provides sunwell_route tool for shortcut and command routing with confidence scoring.
Uses LayeredLensRegistry for priority-based lens resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import mcp_json, omit_empty, truncate

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.foundation.core.lens import Lens


def register_routing_tools(mcp: FastMCP, lenses_dir: str | None = None) -> None:
    """Register routing-related tools.

    Args:
        mcp: FastMCP server instance
        lenses_dir: Optional path to lenses directory
    """
    from sunwell.foundation.registry.layered import LayeredLensRegistry
    from sunwell.foundation.schema.loader import LensLoader
    from sunwell.planning.naaru.expertise.discovery import LensDiscovery

    # Build layered registry for priority-based resolution
    if lenses_dir:
        registry = LayeredLensRegistry.build(
            local_dir=Path(lenses_dir),
            installed_dir=Path.home() / ".sunwell" / "lenses",
            builtin_dir=Path(__file__).parent.parent.parent / "lenses",
        )
    else:
        registry = LayeredLensRegistry.from_discovery()

    # Also keep discovery for backward compatibility
    discovery = LensDiscovery()
    if lenses_dir:
        discovery.search_paths.insert(0, Path(lenses_dir))

    loader = LensLoader()

    # Build shortcut index from registry
    shortcut_index = registry.shortcuts.copy()
    # Add cross-lens shortcuts for fallback
    shortcut_index.update(_build_shortcut_index(discovery, loader))

    @mcp.tool()
    def sunwell_route(command: str, include_context: bool = True) -> str:
        """
        Route a command or shortcut to a lens with confidence scoring.

        Handles:
        - Shortcuts: ::code, ::review, ::test (defined in lens router.shortcuts)
        - Lens names: coder, tech-writer, code-reviewer
        - Domain keywords: coding, documentation, testing

        Returns JSON with:
        - lens: matched lens name
        - confidence: 0-1 score
        - confidence_tier: "high" (>=0.8), "medium" (>=0.5), "low" (<0.5)
        - alternatives: other possible matches
        - context: injectable expertise (if include_context=True)

        Args:
            command: The command, shortcut, or query to route
            include_context: If True (default), include full lens context.
                            Set False for routing-only queries.

        Returns:
            JSON with routing result, confidence, and optional context
        """
        # Normalize command
        cmd = command.strip()
        cmd_lower = cmd.lower()

        # Track match details
        lens: Lens | None = None
        confidence = 0.0
        match_type = "none"
        alternatives: list[dict] = []

        # 1. Exact shortcut match (highest confidence)
        if cmd in shortcut_index or cmd_lower in shortcut_index:
            shortcut_key = cmd if cmd in shortcut_index else cmd_lower
            lens_name, skill_name = shortcut_index[shortcut_key]
            lens = _load_lens_by_name(lens_name, discovery, loader)
            if lens:
                confidence = 1.0
                match_type = "shortcut_exact"

        # 2. Shortcut with :: prefix
        if not lens and cmd.startswith("::"):
            shortcut_clean = cmd[2:]  # Remove ::
            for key, (lens_name, skill_name) in shortcut_index.items():
                if key.endswith(shortcut_clean) or key == f"::{shortcut_clean}":
                    lens = _load_lens_by_name(lens_name, discovery, loader)
                    if lens:
                        confidence = 1.0
                        match_type = "shortcut_prefix"
                        break

        # 3. Direct lens name match
        if not lens:
            lens = _load_lens_by_name(cmd, discovery, loader)
            if lens:
                confidence = 0.95
                match_type = "lens_name"

        # 4. Domain/tag match
        if not lens:
            lens, confidence = _match_by_domain(cmd_lower, discovery, loader)
            if lens:
                match_type = "domain"

        # 5. Fuzzy match on description/heuristics
        if not lens:
            lens, confidence = _fuzzy_match(cmd_lower, discovery, loader)
            if lens:
                match_type = "fuzzy"

        # Build alternatives (other lenses that might match)
        if lens:
            alternatives = _find_alternatives(cmd_lower, lens.metadata.name, discovery, loader)

        # Determine confidence tier
        if confidence >= 0.8:
            tier = "high"
            guidance = "Confident match - proceed with this lens"
        elif confidence >= 0.5:
            tier = "medium"
            guidance = "Moderate confidence - consider alternatives"
        else:
            tier = "low"
            guidance = "Low confidence - review alternatives or clarify intent"

        # Build result
        if lens:
            result: dict = {
                "lens": lens.metadata.name,
                "confidence": round(confidence, 2),
                "confidence_tier": tier,
                "match_type": match_type,
                "guidance": guidance,
                "alternatives": alternatives,
                "path": str(lens.source_path) if lens.source_path else None,
            }

            # Include shortcuts from this lens
            if lens.router and lens.router.shortcuts:
                result["shortcuts"] = dict(lens.router.shortcuts)

            # Include context if requested
            if include_context:
                result["context"] = lens.to_context()
                return mcp_json(result, "full")

            return mcp_json(result, "compact")
        else:
            # No match found
            return mcp_json(
                {
                    "error": f"No lens found for: {command}",
                    "confidence": 0.0,
                    "confidence_tier": "none",
                    "suggestions": [
                        "Use '::' prefix for shortcuts (e.g., '::code' for coding)",
                        "Try a lens name directly (e.g., 'coder', 'tech-writer')",
                        "Use sunwell_list() to see available lenses",
                    ],
                    "available_shortcuts": list(shortcut_index.keys())[:10],
                },
                "compact",
            )

    @mcp.tool()
    def sunwell_shortcuts() -> str:
        """
        List all available shortcuts across all lenses.

        Returns a mapping of shortcuts to their lens and skill names.
        Use this to discover available quick commands.

        Returns:
            JSON mapping of shortcuts to {lens, skill}
        """
        result = {}
        for shortcut, lens_name in registry.shortcuts.items():
            # Get skill name from the lens's router
            entry = registry.get_entry(lens_name)
            skill_name = None
            if entry and entry.lens.router and entry.lens.router.shortcuts:
                skill_name = entry.lens.router.shortcuts.get(shortcut)
            result[shortcut] = omit_empty({
                "lens": lens_name,
                "skill": skill_name,
                "layer": entry.layer if entry else None,
            })
        return mcp_json(result, "compact")

    @mcp.tool()
    def sunwell_registry_info() -> str:
        """
        Get information about the layered lens registry.

        Shows lens counts by layer and any overrides/collisions.
        Useful for debugging lens resolution.

        Returns:
            JSON with registry summary, overrides, and collisions
        """
        # Summary by layer
        summary = registry.summary()

        # Get overrides
        overrides = []
        for lens_name, winner, overridden in registry.get_overrides():
            overrides.append({
                "lens": lens_name,
                "using": {
                    "layer": winner.layer,
                    "path": str(winner.source_path),
                },
                "overriding": [
                    {"layer": e.layer, "path": str(e.source_path)}
                    for e in overridden
                ],
            })

        # Get collisions
        collisions = {}
        for shortcut, entries in registry.get_collisions().items():
            collisions[shortcut] = [
                {
                    "lens": e.lens.metadata.name,
                    "layer": e.layer,
                    "qualified": e.qualified_name,
                }
                for e in entries
            ]

        return mcp_json(
            {
                "summary": summary,
                "total_lenses": sum(summary.values()),
                "overrides": overrides,
                "collisions": collisions,
                "layers": {
                    "local": ".sunwell/lenses/ (highest priority)",
                    "installed": "~/.sunwell/lenses/",
                    "builtin": "bundled with Sunwell (lowest priority)",
                },
            },
            "compact",
        )


def _build_shortcut_index(discovery, loader) -> dict[str, tuple[str, str]]:
    """Build index of shortcuts across all lenses.

    Returns:
        Dict mapping shortcut -> (lens_name, skill_name)
    """
    index: dict[str, tuple[str, str]] = {}

    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for lens_path in search_path.glob("*.lens"):
            try:
                lens = loader.load(lens_path)
                if not lens or not lens.router or not lens.router.shortcuts:
                    continue

                for shortcut, skill in lens.router.shortcuts.items():
                    # Store both with and without :: prefix
                    index[shortcut] = (lens.metadata.name, skill)
                    if shortcut.startswith("::"):
                        index[shortcut[2:]] = (lens.metadata.name, skill)
            except Exception:
                continue

    return index


def _load_lens_by_name(name: str, discovery, loader):
    """Load a lens by name."""
    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for ext in [".lens", ".lens.yaml"]:
            lens_path = search_path / f"{name}{ext}"
            if lens_path.exists():
                try:
                    return loader.load(lens_path)
                except Exception:
                    continue

        # Also try loading all lenses and matching by metadata.name
        for lens_path in search_path.glob("*.lens"):
            try:
                lens = loader.load(lens_path)
                if lens and lens.metadata.name.lower() == name.lower():
                    return lens
            except Exception:
                continue

    return None


def _match_by_domain(query: str, discovery, loader) -> tuple:
    """Match lens by domain keywords."""
    domain_keywords = {
        "code": ["coder", "coding", "programming", "development"],
        "documentation": ["docs", "writing", "technical writing", "writer"],
        "review": ["code review", "reviewing", "audit"],
        "test": ["testing", "tests", "qa", "quality"],
        "data": ["data", "analysis", "analytics"],
        "security": ["security", "auth", "authentication"],
    }

    best_lens = None
    best_confidence = 0.0

    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for lens_path in search_path.glob("*.lens"):
            try:
                lens = loader.load(lens_path)
                if not lens:
                    continue

                # Check domain match
                if lens.metadata.domain:
                    domain_lower = lens.metadata.domain.lower()
                    if query in domain_lower or domain_lower in query:
                        if 0.7 > best_confidence:
                            best_lens = lens
                            best_confidence = 0.7

                # Check tags match
                if lens.metadata.tags:
                    for tag in lens.metadata.tags:
                        if query in tag.lower() or tag.lower() in query:
                            if 0.6 > best_confidence:
                                best_lens = lens
                                best_confidence = 0.6
                            break

            except Exception:
                continue

    return best_lens, best_confidence


def _fuzzy_match(query: str, discovery, loader) -> tuple:
    """Fuzzy match on lens description and heuristics."""
    best_lens = None
    best_confidence = 0.0

    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for lens_path in search_path.glob("*.lens"):
            try:
                lens = loader.load(lens_path)
                if not lens:
                    continue

                # Check description
                if lens.metadata.description:
                    desc_lower = lens.metadata.description.lower()
                    if query in desc_lower:
                        confidence = 0.5
                        if confidence > best_confidence:
                            best_lens = lens
                            best_confidence = confidence

                # Check heuristic names
                for h in lens.heuristics:
                    if query in h.name.lower():
                        confidence = 0.4
                        if confidence > best_confidence:
                            best_lens = lens
                            best_confidence = confidence
                        break

            except Exception:
                continue

    return best_lens, best_confidence


def _find_alternatives(query: str, exclude_name: str, discovery, loader) -> list[dict]:
    """Find alternative lenses that might match."""
    alternatives = []

    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for lens_path in search_path.glob("*.lens"):
            try:
                lens = loader.load(lens_path)
                if not lens or lens.metadata.name == exclude_name:
                    continue

                # Simple relevance check
                relevant = False
                if lens.metadata.domain and query in lens.metadata.domain.lower():
                    relevant = True
                if lens.metadata.tags:
                    for tag in lens.metadata.tags:
                        if query in tag.lower():
                            relevant = True
                            break

                if relevant:
                    alternatives.append(
                        {
                            "name": lens.metadata.name,
                            "domain": lens.metadata.domain,
                            "reason": "domain/tag match",
                        }
                    )

                    if len(alternatives) >= 3:
                        return alternatives

            except Exception:
                continue

    return alternatives
