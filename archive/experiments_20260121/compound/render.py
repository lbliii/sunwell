"""Rendering utilities for compound eye patterns."""

from __future__ import annotations

from sunwell.experiments.compound.attention import AttentionFoldResult
from sunwell.experiments.compound.types import (
    CompoundEyeResult,
    LateralInhibitionResult,
    TemporalDiffResult,
)
from sunwell.experiments.compound.signal import TemporalSignalResult


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


def render_signal_stability_map(result: TemporalSignalResult) -> str:
    """Render temporal signal stability as ASCII visualization."""
    lines = [
        "Temporal Signal Stability Map",
        "=" * 60,
        "",
        f"Frames: {result.n_frames} | Threshold: unanimous or majority",
        "Legend: 🟢=Stable 🔴=Flickering | Signals shown as [0,1,2...]",
        "",
    ]

    for region in result.regions:
        # Stability indicator
        if region.is_unanimous:
            indicator = "🟢"
        elif region.is_stable:
            indicator = "🟡"
        else:
            indicator = "🔴"

        # Signal string
        sig_str = ",".join(str(s) for s in region.signals)

        # Spread indicator
        spread_mark = " ⚠️" if region.spread == 2 else ""

        # Truncate region text
        region_text = region.region[:35].replace("\n", " ").ljust(35)

        lines.append(f"{indicator} [{sig_str}] {region_text}{spread_mark}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(
        f"Stability: {result.overall_stability:.0%} | "
        f"Unanimous: {result.unanimous_count}/{len(result.regions)} | "
        f"Flickering: {len(result.unstable_indices)}"
    )

    if result.high_spread_indices:
        lines.append(f"⚠️  High spread (0↔2): regions {list(result.high_spread_indices)}")

    return "\n".join(lines)


def render_attention_fold_map(result: AttentionFoldResult) -> str:
    """Render attention folding result."""
    lines = [
        "Attention Fold Results",
        "=" * 60,
        "",
        f"Total: {result.total_regions} | Stable: {len(result.stable_regions)} | Folded: {result.folded_count}",
        f"Average confidence on folded: {result.avg_confidence:.0%}",
        "",
        "Final Signals:",
    ]

    # Show final signals with indicators
    for i, signal in enumerate(result.final_signals):
        # Check if this was folded
        folded = next((f for f in result.folded_regions if f.index == i), None)

        if folded:
            # Was flickering, now resolved
            orig = ",".join(str(s) for s in folded.original_signals)
            indicator = "🔧"  # Fixed
            conf = f"{folded.confidence:.0%}"
            strategy = folded.strategy_used.value[:4]
            lines.append(
                f"  {indicator} [{i}] [{orig}] → {signal} (conf:{conf}, {strategy})"
            )
        else:
            # Was stable
            indicator = "✅"
            lines.append(f"  {indicator} [{i}] {signal} (stable)")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
