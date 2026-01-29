"""Lens Resolver for Agent Integration (RFC-064).

Resolves which lens to use for a goal based on:
1. Explicit lens (--lens flag or UI selection)
2. Project default (from .sunwell/config.yaml)
3. Auto-select based on goal analysis
4. None (no lens applied)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.foundation.utils import safe_yaml_load

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.planning.naaru.expertise.discovery import LensDiscovery
    from sunwell.planning.routing.unified import UnifiedRouter


@dataclass(frozen=True, slots=True)
class LensResolution:
    """Result of lens resolution."""

    lens: Lens | None
    source: str  # "explicit", "auto", "project_default", "none"
    confidence: float
    reason: str


async def resolve_lens_for_goal(
    goal: str,
    explicit_lens: str | None = None,
    project_path: Path | None = None,
    auto_select: bool = True,
    router: UnifiedRouter | None = None,
) -> LensResolution:
    """Resolve which lens to use for a goal.

    Priority:
    1. Explicit lens (--lens flag or UI selection)
    2. Project default (from .sunwell/config.yaml)
    3. Auto-select based on goal analysis
    4. None (no lens applied)

    Args:
        goal: The user's goal/task
        explicit_lens: User-specified lens name or path
        project_path: Project directory for finding project default
        auto_select: Whether to auto-select if no explicit lens
        router: Optional UnifiedRouter for intelligent selection

    Returns:
        LensResolution with lens and metadata
    """
    from sunwell.planning.naaru.expertise.discovery import LensDiscovery

    discovery = LensDiscovery()

    # 1. Explicit lens
    if explicit_lens:
        lens = await _load_lens(explicit_lens, discovery)
        if lens:
            return LensResolution(
                lens=lens,
                source="explicit",
                confidence=1.0,
                reason=f"User specified: {explicit_lens}",
            )
        return LensResolution(
            lens=None,
            source="explicit",
            confidence=0.0,
            reason=f"Could not load lens: {explicit_lens}",
        )

    # 2. Project default
    if project_path:
        config_path = project_path / ".sunwell" / "config.yaml"
        if config_path.exists():
            config = safe_yaml_load(config_path) or {}
            # Prefer default_lens_uri, fall back to default_lens for backwards compatibility
            default_lens = config.get("default_lens_uri") or config.get("default_lens")
            if default_lens:
                lens = await _load_lens(default_lens, discovery)
                if lens:
                    return LensResolution(
                        lens=lens,
                        source="project_default",
                        confidence=0.95,
                        reason=f"Project default: {default_lens}",
                    )

    # 3. Auto-select
    if auto_select:
        # Use router if available for intelligent selection
        if router:
            try:
                decision = await router.route(goal)
                if decision.lens:
                    lens = await _load_lens(decision.lens, discovery)
                    if lens:
                        return LensResolution(
                            lens=lens,
                            source="auto",
                            confidence=decision.confidence,
                            reason=f"Router selected: {decision.lens} ({decision.reasoning})",
                        )
            except Exception:
                pass  # Fall back to language/domain classification

        # Try language-based lens selection first
        try:
            from sunwell.planning.naaru.expertise.language import (
                detect_language,
                get_language_lens,
            )

            lang_result = detect_language(goal, project_path)
            if lang_result.is_confident:
                lang_lens_name = get_language_lens(lang_result.language)
                if lang_lens_name:
                    lens = await _load_lens(lang_lens_name, discovery)
                    if lens:
                        return LensResolution(
                            lens=lens,
                            source="auto",
                            confidence=lang_result.confidence,
                            reason=(
                                f"Language {lang_result.language.value}: {lens.metadata.name} "
                                f"(signals: {', '.join(lang_result.signals[:3])})"
                            ),
                        )
        except Exception:
            pass  # Fall back to domain classification

        # Fallback to domain classification
        try:
            from sunwell.planning.naaru.expertise.classifier import classify_domain

            domain = classify_domain(goal)
            lenses = await discovery.discover(domain, max_lenses=1)
            if lenses:
                return LensResolution(
                    lens=lenses[0],
                    source="auto",
                    confidence=0.8,
                    reason=f"Domain {domain.value}: {lenses[0].metadata.name}",
                )
        except Exception:
            pass  # No lens available

    # 4. No lens
    return LensResolution(
        lens=None,
        source="none",
        confidence=1.0,
        reason="No lens applied",
    )


async def _load_lens(name_or_path: str, discovery: LensDiscovery) -> Lens | None:
    """Load a lens by name or path.

    Error handling:
    - Returns None for missing files (graceful degradation)
    - Returns None for parse errors (logged, not raised)
    - Path traversal is prevented by search_path containment check
    """
    import logging

    from sunwell.core.types.types import LensReference
    from sunwell.features.fount.client import FountClient
    from sunwell.features.fount.resolver import LensResolver
    from sunwell.foundation.schema.loader import LensLoader

    log = logging.getLogger(__name__)

    # Check if it's a path
    if name_or_path.endswith(".lens") or "/" in name_or_path:
        path = Path(name_or_path)
        if not path.exists():
            # Try standard locations
            for search_path in discovery.search_paths:
                candidate = search_path / name_or_path
                if candidate.exists():
                    path = candidate
                    break

        if path.exists():
            # Security: Ensure path is within allowed search paths
            resolved = path.resolve()
            in_search_path = any(
                str(resolved).startswith(str(sp.resolve())) for sp in discovery.search_paths
            )
            if not in_search_path:
                log.warning(f"Lens path outside search paths: {path}")
                return None

            source = str(path)
            if not source.startswith("/"):
                source = f"./{source}"

            try:
                fount = FountClient()
                loader = LensLoader(fount_client=fount)
                resolver = LensResolver(loader=loader)
                ref = LensReference(source=source)
                return await resolver.resolve(ref)
            except Exception as e:
                log.warning(f"Failed to load lens {name_or_path}: {e}")
                return None

    # Try by name
    for search_path in discovery.search_paths:
        path = search_path / f"{name_or_path}.lens"
        if path.exists():
            return await _load_lens(str(path), discovery)

    log.debug(f"Lens not found: {name_or_path}")
    return None


async def list_available_lenses() -> list[dict]:
    """List all available lenses with their metadata.

    Returns:
        List of lens metadata dictionaries
    """
    from sunwell.planning.naaru.expertise.discovery import LensDiscovery

    discovery = LensDiscovery()
    lenses_data = []

    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for lens_path in search_path.glob("*.lens"):
            try:
                lens = await discovery._load_lens(lens_path)
                if lens:
                    lenses_data.append(
                        {
                            "name": lens.metadata.name,
                            "domain": lens.metadata.domain,
                            "version": str(lens.metadata.version),
                            "description": lens.metadata.description,
                            "path": str(lens_path),
                            "heuristics_count": len(lens.heuristics),
                            "skills_count": len(lens.skills),
                        }
                    )
            except Exception:
                continue

    return lenses_data


async def get_lens_detail(name: str) -> dict | None:
    """Get detailed information about a specific lens.

    Args:
        name: Lens name or path

    Returns:
        Detailed lens information or None if not found
    """
    from sunwell.planning.naaru.expertise.discovery import LensDiscovery

    discovery = LensDiscovery()
    lens = await _load_lens(name, discovery)

    if not lens:
        return None

    return {
        "name": lens.metadata.name,
        "domain": lens.metadata.domain,
        "version": str(lens.metadata.version),
        "description": lens.metadata.description,
        "author": lens.metadata.author,
        "heuristics": [
            {
                "name": h.name,
                "rule": h.rule,
                "priority": h.priority,
            }
            for h in lens.heuristics
        ],
        "communication_style": lens.communication.style if lens.communication else None,
        "skills": [s.name for s in lens.skills],
    }
