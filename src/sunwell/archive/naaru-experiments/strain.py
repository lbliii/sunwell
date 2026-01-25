"""Strain Detection — Find clusters of elevated signals.

The hypothesis: Individual signals miss the pattern. A single [2] might be fine,
but [1,2,2,1] indicates STRAIN — a cluster that needs group triage.

Strain types:
    - Spike: Isolated high signal [0,0,2,0,0]
    - Cluster: Adjacent elevated signals [0,1,2,2,1,0]
    - Chronic: Sustained low-grade elevation [1,1,1,1,1]
    - Escalating: Rising trend [0,1,1,2,2]

The higher model sees the GROUP with context, not individual chunks.

Example:
    >>> stream = await danger_scan(code, tiny_model)
    >>> strains = detect_strain(stream)
    >>>
    >>> for strain in strains:
    ...     # Send the whole cluster to big model for group triage
    ...     diagnosis = await triage_strain(strain, big_model)
"""


from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from sunwell.archive.naaru-experiments.signals import Trit
from sunwell.archive.naaru-experiments.streams import ChunkSignal, SignalStream

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


class StrainType(Enum):
    """Types of strain patterns."""

    SPIKE = "spike"
    """Isolated high signal: [0,0,2,0,0]"""

    CLUSTER = "cluster"
    """Adjacent elevated signals: [0,1,2,2,1,0]"""

    CHRONIC = "chronic"
    """Sustained low-grade: [1,1,1,1,1]"""

    ESCALATING = "escalating"
    """Rising trend: [0,1,1,2,2]"""

    CRITICAL = "critical"
    """Multiple high signals clustered: [2,2,2]"""


@dataclass(frozen=True, slots=True)
class Strain:
    """A detected strain region in a signal stream."""

    strain_type: StrainType
    """The type of strain pattern."""

    chunks: tuple[ChunkSignal, ...]
    """The chunks in this strain region."""

    start_index: int
    """Start index in original stream."""

    end_index: int
    """End index in original stream."""

    intensity: float
    """Strain intensity (0.0-1.0)."""

    @property
    def length(self) -> int:
        """Number of chunks in strain."""
        return len(self.chunks)

    @property
    def signals(self) -> tuple[int, ...]:
        """Raw signal values."""
        return tuple(c.signal.value for c in self.chunks)

    @property
    def text(self) -> str:
        """Combined text of all chunks in strain."""
        return "\n".join(c.chunk for c in self.chunks)

    @property
    def max_signal(self) -> Trit:
        """Highest signal in strain."""
        return Trit(max(c.signal.value for c in self.chunks))

    def __repr__(self) -> str:
        sigs = "".join(str(s) for s in self.signals)
        return f"Strain({self.strain_type.value}, [{sigs}], intensity={self.intensity:.0%})"


@dataclass(frozen=True, slots=True)
class StrainDiagnosis:
    """Result from higher model triaging a strain."""

    strain: Strain
    """The original strain."""

    severity: Trit
    """Overall severity after triage (0/1/2)."""

    diagnosis: str
    """The model's diagnosis of the strain."""

    recommended_action: str
    """What to do about it."""

    false_positive: bool
    """Whether the strain was a false positive."""


# =============================================================================
# Strain Detection
# =============================================================================


def detect_strain(
    stream: SignalStream,
    min_cluster_size: int = 2,
    warm_threshold: Trit = Trit.MAYBE,
) -> list[Strain]:
    """Detect strain regions in a signal stream.

    Finds clusters of elevated signals that indicate systemic issues.

    Args:
        stream: The signal stream to analyze
        min_cluster_size: Minimum adjacent elevated signals for cluster
        warm_threshold: Minimum signal to consider "elevated"

    Returns:
        List of detected strains
    """
    if not stream.chunks:
        return []

    strains: list[Strain] = []
    signals = [c.signal.value for c in stream.chunks]
    n = len(signals)

    # Find clusters of elevated signals
    i = 0
    while i < n:
        if signals[i] >= warm_threshold.value:
            # Start of potential cluster
            start = i
            while i < n and signals[i] >= warm_threshold.value:
                i += 1
            end = i

            cluster_chunks = stream.chunks[start:end]
            cluster_signals = signals[start:end]

            # Classify strain type
            strain_type = _classify_strain_type(cluster_signals)

            # Calculate intensity
            intensity = sum(cluster_signals) / (len(cluster_signals) * 2)  # Normalize to 0-1

            strains.append(Strain(
                strain_type=strain_type,
                chunks=cluster_chunks,
                start_index=start,
                end_index=end - 1,
                intensity=intensity,
            ))
        else:
            i += 1

    # Also detect isolated spikes (single 2 surrounded by 0s)
    for i, sig in enumerate(signals):
        if sig == 2:
            # Check if isolated
            before_ok = i == 0 or signals[i-1] == 0
            after_ok = i == n-1 or signals[i+1] == 0

            if before_ok and after_ok:
                # Check if not already in a strain
                already_detected = any(
                    s.start_index <= i <= s.end_index for s in strains
                )
                if not already_detected:
                    strains.append(Strain(
                        strain_type=StrainType.SPIKE,
                        chunks=(stream.chunks[i],),
                        start_index=i,
                        end_index=i,
                        intensity=1.0,
                    ))

    return sorted(strains, key=lambda s: s.start_index)


def _classify_strain_type(signals: list[int]) -> StrainType:
    """Classify the type of strain based on signal pattern."""
    n = len(signals)

    if n == 1:
        return StrainType.SPIKE

    # Check for critical (multiple 2s)
    high_count = sum(1 for s in signals if s == 2)
    if high_count >= 2:
        return StrainType.CRITICAL

    # Check for escalating trend
    if signals == sorted(signals):
        return StrainType.ESCALATING

    # Check for chronic (all same low-grade)
    if all(s == 1 for s in signals):
        return StrainType.CHRONIC

    # Default to cluster
    return StrainType.CLUSTER


def strain_summary(strains: list[Strain]) -> dict[str, any]:
    """Summarize detected strains."""
    if not strains:
        return {"count": 0, "types": {}, "max_intensity": 0.0}

    types = {}
    for s in strains:
        types[s.strain_type.value] = types.get(s.strain_type.value, 0) + 1

    return {
        "count": len(strains),
        "types": types,
        "max_intensity": max(s.intensity for s in strains),
        "total_chunks": sum(s.length for s in strains),
        "critical_count": sum(1 for s in strains if s.strain_type == StrainType.CRITICAL),
    }


# =============================================================================
# Group Triage
# =============================================================================


TRIAGE_PROMPT = """You are triaging a STRAIN — a cluster of concerning signals detected by initial screening.

CONTEXT: This strain was detected in the following content:

{strain_text}

SIGNAL PATTERN: {signals}
STRAIN TYPE: {strain_type}
INTENSITY: {intensity:.0%}

The initial screening flagged this as potentially problematic.

Your job:
1. Assess if this is a REAL issue or a FALSE POSITIVE
2. If real, rate severity: LOW (1), MEDIUM (2), HIGH (3)
3. Recommend action

Respond in this format:
SEVERITY: [0=false positive, 1=low, 2=high]
DIAGNOSIS: [one sentence explanation]
ACTION: [recommended action]"""


async def triage_strain(
    strain: Strain,
    model: ModelProtocol,
) -> StrainDiagnosis:
    """Have a higher model triage a strain cluster.

    The model sees the whole cluster with context, not individual chunks.

    Args:
        strain: The strain to triage
        model: The (larger) model for triage

    Returns:
        StrainDiagnosis with severity and recommendations
    """
    from sunwell.models import GenerateOptions

    prompt = TRIAGE_PROMPT.format(
        strain_text=strain.text,
        signals=strain.signals,
        strain_type=strain.strain_type.value,
        intensity=strain.intensity,
    )

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.2, max_tokens=200),
    )

    text = result.text

    # Parse response
    severity = Trit.MAYBE  # Default
    diagnosis = ""
    action = ""

    for line in text.split("\n"):
        line_upper = line.upper()
        if "SEVERITY:" in line_upper:
            if "0" in line or "FALSE" in line_upper:
                severity = Trit.NO
            elif "2" in line or "HIGH" in line_upper:
                severity = Trit.YES
            else:
                severity = Trit.MAYBE
        elif "DIAGNOSIS:" in line_upper:
            diagnosis = line.split(":", 1)[-1].strip()
        elif "ACTION:" in line_upper:
            action = line.split(":", 1)[-1].strip()

    return StrainDiagnosis(
        strain=strain,
        severity=severity,
        diagnosis=diagnosis or "Unable to parse diagnosis",
        recommended_action=action or "Review manually",
        false_positive=(severity == Trit.NO),
    )


async def triage_all_strains(
    strains: list[Strain],
    model: ModelProtocol,
) -> list[StrainDiagnosis]:
    """Triage all strains, prioritizing by intensity."""
    # Sort by intensity (highest first)
    sorted_strains = sorted(strains, key=lambda s: -s.intensity)

    diagnoses = []
    for strain in sorted_strains:
        diagnosis = await triage_strain(strain, model)
        diagnoses.append(diagnosis)

    return diagnoses


# =============================================================================
# Strain Visualization
# =============================================================================


def render_strain_map(stream: SignalStream, strains: list[Strain]) -> str:
    """Render stream with strain regions highlighted."""
    lines = []

    # Build strain lookup
    strain_at: dict[int, Strain] = {}
    for strain in strains:
        for i in range(strain.start_index, strain.end_index + 1):
            strain_at[i] = strain

    lines.append("Strain Map")
    lines.append("=" * 60)

    for i, chunk in enumerate(stream.chunks):
        # Signal indicator
        if chunk.signal == Trit.YES:
            sig = "🔴"
        elif chunk.signal == Trit.MAYBE:
            sig = "🟡"
        else:
            sig = "⚪"

        # Strain indicator
        if i in strain_at:
            strain = strain_at[i]
            if strain.strain_type == StrainType.CRITICAL:
                strain_mark = "⚠️ CRITICAL"
            elif strain.strain_type == StrainType.ESCALATING:
                strain_mark = "📈 ESCALATING"
            elif strain.strain_type == StrainType.CHRONIC:
                strain_mark = "📊 CHRONIC"
            else:
                strain_mark = "🔥 CLUSTER"
        else:
            strain_mark = ""

        text = chunk.chunk[:35].ljust(35)
        lines.append(f"{sig} [{chunk.signal.value}] {text} {strain_mark}")

    lines.append("=" * 60)

    # Summary
    summary = strain_summary(strains)
    lines.append(f"Strains: {summary['count']} | Critical: {summary.get('critical_count', 0)}")

    return "\n".join(lines)


# =============================================================================
# Full Pipeline
# =============================================================================


async def scan_and_triage(
    text: str,
    question: str,
    tiny_model: ModelProtocol,
    triage_model: ModelProtocol,
    chunker: callable | None = None,
) -> tuple[SignalStream, list[StrainDiagnosis]]:
    """Full pipeline: scan with tiny model, detect strains, triage with bigger model.

    Args:
        text: Text to analyze
        question: Question to ask per chunk
        tiny_model: Small model for initial scan
        triage_model: Larger model for strain triage
        chunker: How to split text

    Returns:
        Tuple of (signal_stream, strain_diagnoses)
    """
    from sunwell.archive.naaru-experiments.streams import chunk_by_line, classify_stream

    if chunker is None:
        chunker = chunk_by_line

    chunks = chunker(text)

    # Stage 1: Tiny model scans
    stream = await classify_stream(chunks, question, tiny_model)

    # Stage 2: Detect strains
    strains = detect_strain(stream)

    # Stage 3: Triage strains with bigger model
    diagnoses = []
    if strains:
        diagnoses = await triage_all_strains(strains, triage_model)

    return stream, diagnoses
