"""Utility functions for compound eye patterns."""

from __future__ import annotations

import re


def chunk_code_by_function(code: str) -> list[str]:
    """Split code into function-level chunks.

    Simple heuristic: split on 'def ' or 'class '.
    """
    # Split on function/class definitions
    pattern = r"(?=\n(?:def |class |async def ))"
    chunks = re.split(pattern, code)

    # Clean up
    chunks = [c.strip() for c in chunks if c.strip()]

    return chunks if chunks else [code]


def chunk_by_lines(text: str, chunk_size: int = 10) -> list[str]:
    """Split text into chunks of N lines."""
    lines = text.split("\n")
    chunks = []

    for i in range(0, len(lines), chunk_size):
        chunk = "\n".join(lines[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks if chunks else [text]


def render_lateral_map(result: LateralInhibitionResult) -> str:
    """Render lateral inhibition result as ASCII visualization."""
    lines = [
        "Lateral Inhibition Map",
        "=" * 60,
        "",
        "Legend: ⚪=0 🟡=1 🔴=2  |  [E]=Edge detected",
        "",
    ]

    for sig in result.signals:
        # Signal indicator
        if sig.raw_signal >= 0.66:
            indicator = "🔴"
        elif sig.raw_signal >= 0.33:
            indicator = "🟡"
        else:
            indicator = "⚪"

        # Edge marker
        edge_mark = " [E]" if sig.index in result.edge_indices else "    "

        # Truncate region text
        region_text = sig.region[:40].replace("\n", " ").ljust(40)

        # Inhibited signal bar
        bar_len = int(sig.inhibited_signal * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)

        lines.append(f"{indicator} [{bar}] {region_text}{edge_mark}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(f"Edges: {result.edges_found}/{result.total_regions} ({result.edge_ratio:.0%})")

    return "\n".join(lines)


def render_temporal_map(result: TemporalDiffResult) -> str:
    """Render temporal differencing result as ASCII visualization."""
    lines = [
        "Temporal Stability Map",
        "=" * 60,
        "",
        f"Frames captured: {result.n_frames}",
        "Legend: 🟢=Stable 🔴=Flickering",
        "",
    ]

    for region in result.regions:
        # Stability indicator
        indicator = "\U0001f7e2" if region.is_stable else "🔴"

        # Stability bar
        bar_len = int(region.stability_score * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)

        # Truncate region text
        region_text = region.region_text[:40].replace("\n", " ").ljust(40)

        lines.append(f"{indicator} [{bar}] {region_text}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(
        f"Stability: {result.overall_stability:.0%} | "
        f"Flickering: {len(result.unstable_regions)}/{len(result.regions)}"
    )

    return "\n".join(lines)


def render_compound_map(result: CompoundEyeResult) -> str:
    """Render full compound eye result."""
    lines = [
        "🪰 Compound Eye Scan Results",
        "=" * 60,
        "",
    ]

    # Lateral summary
    lines.append(f"Lateral Inhibition: {result.lateral.edges_found} edges detected")

    # Temporal summary
    lines.append(
        f"Temporal Stability: {result.temporal.overall_stability:.0%} "
        f"({len(result.temporal.unstable_regions)} flickering)"
    )

    # Hotspots
    if result.hotspots:
        lines.append("")
        lines.append("⚠️  HOTSPOTS (edges + flickering):")
        for idx in result.hotspots:
            region = result.lateral.signals[idx].region[:50].replace("\n", " ")
            lines.append(f"   [{idx}] {region}...")
    else:
        lines.append("")
        lines.append("✅ No hotspots detected")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
