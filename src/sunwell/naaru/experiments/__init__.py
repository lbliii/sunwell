"""Experimental patterns for emergent intelligence.

These are prototypes exploring the "Lighthouse Lens" architecture:
many tiny model calls creating emergent behavior.

Experiments:
- speculative: Race N models, first valid wins
- consensus: N models vote, supermajority wins  
- cascade: Gradient of gates, most exit early
- cellular: Graph emerges from local cell decisions
- dialectic: Split task into complementary lenses (thesis/antithesis/synthesis)

The Fresnel Lens Insight:
    A lighthouse lens isn't one massive piece of glass.
    It's hundreds of small prisms, each simple, together
    focusing light miles out to sea.
    
    Sunwell isn't one massive model.
    It's hundreds of small model calls, each cheap,
    together producing professional-quality output.

The Prism Insight:
    LLMs don't have unique perspectives like humans.
    Voting is just sampling the same distribution.
    
    Instead, SPLIT the task into complementary lenses:
    - Thesis + Antithesis → Synthesis
    - Expand + Contract → Selection
    - Structure + Content → Integration
    - Do + Don't → Balance
"""

from sunwell.naaru.experiments.speculative import (
    speculative_discover,
    speculative_classify,
    SpeculativeResult,
)
from sunwell.naaru.experiments.consensus import (
    consensus_classify,
    consensus_decision,
    should_use_tools,
    should_use_harmonic,
    ConsensusResult,
)
from sunwell.naaru.experiments.cascade import (
    GradientCascade,
    CascadeResult,
    create_standard_cascade,
    create_aggressive_cascade,
    create_conservative_cascade,
)
from sunwell.naaru.experiments.cellular import (
    cellular_discover,
    cellular_vs_monolithic,
    CellularDiscoveryResult,
)
from sunwell.naaru.experiments.dialectic import (
    dialectic_decide,
    expand_contract,
    structure_then_content,
    positive_negative_split,
    DialecticResult,
    ExpandContractResult,
    StructureContentResult,
)
from sunwell.naaru.experiments.signals import (
    Trit,
    Signal,
    SignalVector,
    SignalTrace,
    SharedMemory,
    SignalNetwork,
    extract_signals,
    signal_cascade,
    binary_classify,
    trit_classify,
)
from sunwell.naaru.experiments.streams import (
    ChunkSignal,
    SignalStream,
    classify_stream,
    danger_scan,
    complexity_scan,
    code_review_stream,
    claim_verification_stream,
    comprehensive_scan,
    chunk_by_sentence,
    chunk_by_line,
    chunk_by_clause,
)
from sunwell.naaru.experiments.escalation import (
    SignalAccumulator,
    EscalationResult,
    escalate_hot_chunks,
    cascade_triage,
    render_heat_map,
    ThresholdAction,
    threshold_scan,
)
from sunwell.naaru.experiments.strain import (
    StrainType,
    Strain,
    StrainDiagnosis,
    detect_strain,
    strain_summary,
    triage_strain,
    triage_all_strains,
    render_strain_map,
    scan_and_triage,
)
from sunwell.naaru.experiments.content_validation import (
    ContentType,
    ValidationResult,
    infer_expected_type,
    detect_content_type,
    fast_validate,
    validate_content_quality,
    validate_and_maybe_escalate,
)

__all__ = [
    # Speculative
    "speculative_discover",
    "speculative_classify",
    "SpeculativeResult",
    # Consensus
    "consensus_classify",
    "consensus_decision",
    "should_use_tools",
    "should_use_harmonic",
    "ConsensusResult",
    # Cascade
    "GradientCascade",
    "CascadeResult",
    "create_standard_cascade",
    "create_aggressive_cascade",
    "create_conservative_cascade",
    # Cellular
    "cellular_discover",
    "cellular_vs_monolithic",
    "CellularDiscoveryResult",
    # Dialectic (prism patterns)
    "dialectic_decide",
    "expand_contract",
    "structure_then_content",
    "positive_negative_split",
    "DialecticResult",
    "ExpandContractResult",
    "StructureContentResult",
    # Signals (LLM binary)
    "Trit",
    "Signal",
    "SignalVector",
    "SignalTrace",
    "SharedMemory",
    "SignalNetwork",
    "extract_signals",
    "signal_cascade",
    "binary_classify",
    "trit_classify",
    # Streams (per-chunk signals)
    "ChunkSignal",
    "SignalStream",
    "classify_stream",
    "danger_scan",
    "complexity_scan",
    "code_review_stream",
    "claim_verification_stream",
    "comprehensive_scan",
    "chunk_by_sentence",
    "chunk_by_line",
    "chunk_by_clause",
    # Escalation (accumulation + selective routing)
    "SignalAccumulator",
    "EscalationResult",
    "escalate_hot_chunks",
    "cascade_triage",
    "render_heat_map",
    "ThresholdAction",
    "threshold_scan",
    # Strain (cluster detection + group triage)
    "StrainType",
    "Strain",
    "StrainDiagnosis",
    "detect_strain",
    "strain_summary",
    "triage_strain",
    "triage_all_strains",
    "render_strain_map",
    "scan_and_triage",
    # Content validation (format detection + escalation)
    "ContentType",
    "ValidationResult",
    "infer_expected_type",
    "detect_content_type",
    "fast_validate",
    "validate_content_quality",
    "validate_and_maybe_escalate",
]
