"""Experimental patterns for multi-model coordination.

These are prototypes exploring the "Lighthouse Lens" architecture:
many small model calls producing higher-quality outputs.

Experiments:
- speculative: Race N models, first valid wins
- consensus: N models vote, supermajority wins
- cascade: Gradient of gates, most exit early
- cellular: Graph emerges from local cell decisions
- dialectic: Split task into complementary lenses (thesis/antithesis/synthesis)
- compound: Bio-inspired patterns from insect compound eyes

Substrate Experiments (small models as computational substrate):
- automata: LLM cellular automaton — cells evolve thoughts based on neighbors
- swarm: Stigmergic intelligence — agents leave traces that fade/reinforce
- hierarchy: LLMs as neural network layers — information flows up abstraction

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

The Compound Eye Insight:
    Insect compound eyes don't see high-resolution images.
    They excel at detecting CHANGE and BOUNDARIES.

    - Lateral Inhibition: Adjacent sensors suppress each other,
      making edges (where signals differ) stand out.
    - Temporal Differencing: Comparing frames over time detects motion.

    For LLMs: Don't ask "is this good?" — ask "where does the signal CHANGE?"
    Don't trust one run — compare multiple runs to find UNCERTAINTY.

The Substrate Insight:
    What if small models aren't the endpoint but the substrate?
    Like neurons compose into minds, transistors into CPUs,
    cells into organisms — small models can compose into
    something greater than any individual model.

    - Automata: Complex reasoning emerges from simple local rules
    - Swarm: Solutions emerge from collective trace patterns
    - Hierarchy: Abstraction emerges from layered processing

    The question isn't "how good is this 1B model?"
    It's "what can we build with thousands of them?"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# =============================================================================
# Lazy Loading System
# =============================================================================
# 
# This module uses lazy loading to improve import performance.
# Only the submodule you actually use gets loaded.
#
# Example:
#   from sunwell.experiments import lateral_inhibition_scan
#   # Only compound.py loads, not all 15+ submodules
#
# =============================================================================

# Mapping: attribute name -> (module, actual_name)
# If actual_name is None, it's the same as attribute name
_LAZY_IMPORTS: dict[str, tuple[str, str | None]] = {
    # Automata
    "AutomatonResult": ("automata", None),
    "Cell": ("automata", None),
    "GridState": ("automata", None),
    "automaton_vs_single": ("automata", None),
    "compare_grid_sizes": ("automata", None),
    "compare_neighborhoods": ("automata", None),
    "extract_thought_clusters": ("automata", None),
    "llm_automaton": ("automata", None),
    "visualize_evolution": ("automata", None),
    "visualize_grid": ("automata", None),
    
    # Cascade
    "CascadeResult": ("cascade", None),
    "GradientCascade": ("cascade", None),
    "create_aggressive_cascade": ("cascade", None),
    "create_conservative_cascade": ("cascade", None),
    "create_standard_cascade": ("cascade", None),
    
    # Compound eye
    "AttentionFoldResult": ("compound", None),
    "CompoundEyeResult": ("compound", None),
    "FoldedRegion": ("compound", None),
    "FoldStrategy": ("compound", None),
    "LateralInhibitionResult": ("compound", None),
    "OmmatidiumSignal": ("compound", None),
    "RegionStability": ("compound", None),
    "SignalStability": ("compound", None),
    "TemporalDiffResult": ("compound", None),
    "TemporalFrame": ("compound", None),
    "TemporalSignalResult": ("compound", None),
    "attention_fold": ("compound", None),
    "chunk_by_lines": ("compound", None),
    "chunk_code_by_function": ("compound", None),
    "compound_eye_scan": ("compound", None),
    "lateral_inhibition_scan": ("compound", None),
    "render_attention_fold_map": ("compound", None),
    "render_compound_map": ("compound", None),
    "render_lateral_map": ("compound", None),
    "render_signal_stability_map": ("compound", None),
    "render_temporal_map": ("compound", None),
    "temporal_diff_scan": ("compound", None),
    "temporal_signal_scan": ("compound", None),
    
    # Consensus
    "ConsensusResult": ("consensus", None),
    "consensus_classify": ("consensus", None),
    "consensus_decision": ("consensus", None),
    "should_use_harmonic": ("consensus", None),
    "should_use_tools": ("consensus", None),
    
    # Content validation
    "ContentType": ("content_validation", None),
    "ValidationResult": ("content_validation", None),
    "detect_content_type": ("content_validation", None),
    "fast_validate": ("content_validation", None),
    "infer_expected_type": ("content_validation", None),
    "validate_and_maybe_escalate": ("content_validation", None),
    "validate_content_quality": ("content_validation", None),
    
    # Dialectic
    "DialecticResult": ("dialectic", None),
    "ExpandContractResult": ("dialectic", None),
    "StructureContentResult": ("dialectic", None),
    "dialectic_decide": ("dialectic", None),
    "expand_contract": ("dialectic", None),
    "positive_negative_split": ("dialectic", None),
    "structure_then_content": ("dialectic", None),
    
    # Escalation
    "EscalationResult": ("escalation", None),
    "SignalAccumulator": ("escalation", None),
    "ThresholdAction": ("escalation", None),
    "cascade_triage": ("escalation", None),
    "escalate_hot_chunks": ("escalation", None),
    "render_heat_map": ("escalation", None),
    "threshold_scan": ("escalation", None),
    
    # Gradient
    "GradientFlowResult": ("gradient", None),
    "PropagationMetrics": ("gradient", None),
    "Subtask": ("gradient", None),
    "SubtaskResult": ("gradient", None),
    "analyze_propagation": ("gradient", None),
    "format_gradient_report": ("gradient", None),
    "gradient_flow_solve": ("gradient", None),
    "run_gradient_experiment": ("gradient", None),
    
    # Hierarchy
    "HierarchyResult": ("hierarchy", None),
    "Layer": ("hierarchy", None),
    "UnitOutput": ("hierarchy", None),
    "analytical_hierarchy": ("hierarchy", None),
    "compare_architectures": ("hierarchy", None),
    "creative_hierarchy": ("hierarchy", None),
    "deep_hierarchy": ("hierarchy", None),
    "hierarchical_process": ("hierarchy", None),
    "hierarchy_consistency_experiment": ("hierarchy", None),
    "hierarchy_vs_single": ("hierarchy", None),
    "layer_statistics": ("hierarchy", None),
    "optimal_depth_experiment": ("hierarchy", None),
    "trace_information_flow": ("hierarchy", None),
    "visualize_hierarchy": ("hierarchy", None),
    "wide_hierarchy": ("hierarchy", None),
    
    # Interference
    "InterferenceExperimentResult": ("interference", None),
    "InterferenceResult": ("interference", None),
    "PerspectiveResponse": ("interference", None),
    "format_interference_report": ("interference", None),
    "interference_scan": ("interference", None),
    "interference_to_confidence": ("interference", None),
    "run_interference_experiment": ("interference", None),
    "should_escalate": ("interference", None),
    
    # Phase transition
    "PhaseTransition": ("phase_transition", None),
    "SweepPoint": ("phase_transition", None),
    "SweepResult": ("phase_transition", None),
    "find_diminishing_returns_point": ("phase_transition", None),
    "format_sweep_report": ("phase_transition", None),
    "run_phase_experiment": ("phase_transition", None),
    "sweep_parameters": ("phase_transition", None),
    
    # Resonance
    "IterationResult": ("resonance_amp", None),
    "ResonanceExperimentResult": ("resonance_amp", None),
    "ResonanceResult": ("resonance_amp", None),
    "find_resonance_peak": ("resonance_amp", None),
    "format_resonance_report": ("resonance_amp", None),
    "get_quality_curve": ("resonance_amp", None),
    "plot_resonance_curve": ("resonance_amp", None),
    "resonance_experiment": ("resonance_amp", None),
    "run_resonance_batch": ("resonance_amp", None),
    
    # Signals
    "SharedMemory": ("signals", None),
    "Signal": ("signals", None),
    "SignalNetwork": ("signals", None),
    "SignalTrace": ("signals", None),
    "SignalVector": ("signals", None),
    "Trit": ("signals", None),
    "binary_classify": ("signals", None),
    "extract_signals": ("signals", None),
    "signal_cascade": ("signals", None),
    "trit_classify": ("signals", None),
    
    # Speculative
    "SpeculativeResult": ("speculative", None),
    "speculative_classify": ("speculative", None),
    
    # Strain
    "Strain": ("strain", None),
    "StrainDiagnosis": ("strain", None),
    "StrainType": ("strain", None),
    "detect_strain": ("strain", None),
    "render_strain_map": ("strain", None),
    "scan_and_triage": ("strain", None),
    "strain_summary": ("strain", None),
    "triage_all_strains": ("strain", None),
    "triage_strain": ("strain", None),
    
    # Streams
    "ChunkSignal": ("streams", None),
    "SignalStream": ("streams", None),
    "chunk_by_clause": ("streams", None),
    "chunk_by_line": ("streams", None),
    "chunk_by_sentence": ("streams", None),
    "claim_verification_stream": ("streams", None),
    "classify_stream": ("streams", None),
    "code_review_stream": ("streams", None),
    "complexity_scan": ("streams", None),
    "comprehensive_scan": ("streams", None),
    "danger_scan": ("streams", None),
    
    # Swarm
    "AgentContribution": ("swarm", None),
    "SwarmResult": ("swarm", None),
    "Trace": ("swarm", None),
    "agent_performance": ("swarm", None),
    "compare_evaporation_rates": ("swarm", None),
    "compare_swarm_sizes": ("swarm", None),
    "swarm_diversity_experiment": ("swarm", None),
    "swarm_solve": ("swarm", None),
    "swarm_vs_single": ("swarm", None),
    "trace_lineage": ("swarm", None),
    "visualize_traces": ("swarm", None),
}

# Cache for loaded modules
_loaded_modules: dict[str, object] = {}


def __getattr__(name: str) -> object:
    """Lazy load attributes on first access."""
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        actual_name = attr_name or name
        
        # Check cache first
        cache_key = f"{module_name}.{actual_name}"
        if cache_key in _loaded_modules:
            return _loaded_modules[cache_key]
        
        # Import the submodule
        import importlib
        full_module = f"sunwell.experiments.{module_name}"
        module = importlib.import_module(full_module)
        
        # Get the attribute
        attr = getattr(module, actual_name)
        _loaded_modules[cache_key] = attr
        return attr
    
    raise AttributeError(f"module 'sunwell.experiments' has no attribute {name!r}")


def __dir__() -> list[str]:
    """List all available attributes for tab completion."""
    return list(__all__)


# =============================================================================
# __all__ - Public API
# =============================================================================

__all__ = [
    # Speculative
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
    # Compound eye (bio-inspired edge/uncertainty detection)
    "OmmatidiumSignal",
    "LateralInhibitionResult",
    "TemporalFrame",
    "RegionStability",
    "TemporalDiffResult",
    "CompoundEyeResult",
    "SignalStability",
    "TemporalSignalResult",
    "FoldStrategy",
    "FoldedRegion",
    "AttentionFoldResult",
    "lateral_inhibition_scan",
    "temporal_diff_scan",
    "temporal_signal_scan",
    "attention_fold",
    "compound_eye_scan",
    "chunk_code_by_function",
    "chunk_by_lines",
    "render_lateral_map",
    "render_temporal_map",
    "render_signal_stability_map",
    "render_attention_fold_map",
    "render_compound_map",
    # Vortex experiments (multi-model primitives)
    # Interference
    "InterferenceResult",
    "InterferenceExperimentResult",
    "PerspectiveResponse",
    "interference_scan",
    "run_interference_experiment",
    "interference_to_confidence",
    "should_escalate",
    "format_interference_report",
    # Gradient
    "GradientFlowResult",
    "Subtask",
    "SubtaskResult",
    "PropagationMetrics",
    "gradient_flow_solve",
    "run_gradient_experiment",
    "analyze_propagation",
    "format_gradient_report",
    # Phase Transition
    "SweepResult",
    "SweepPoint",
    "PhaseTransition",
    "sweep_parameters",
    "run_phase_experiment",
    "find_diminishing_returns_point",
    "format_sweep_report",
    # Resonance
    "ResonanceResult",
    "ResonanceExperimentResult",
    "IterationResult",
    "resonance_experiment",
    "run_resonance_batch",
    "find_resonance_peak",
    "get_quality_curve",
    "format_resonance_report",
    "plot_resonance_curve",
    # Substrate experiments (small models as computational substrate)
    # Automata (cellular automaton with LLMs)
    "Cell",
    "GridState",
    "AutomatonResult",
    "llm_automaton",
    "visualize_grid",
    "visualize_evolution",
    "extract_thought_clusters",
    "compare_grid_sizes",
    "compare_neighborhoods",
    "automaton_vs_single",
    # Swarm (stigmergic intelligence)
    "Trace",
    "AgentContribution",
    "SwarmResult",
    "swarm_solve",
    "visualize_traces",
    "trace_lineage",
    "agent_performance",
    "compare_swarm_sizes",
    "compare_evaporation_rates",
    "swarm_vs_single",
    "swarm_diversity_experiment",
    # Hierarchy (LLMs as neural network layers)
    "UnitOutput",
    "Layer",
    "HierarchyResult",
    "hierarchical_process",
    "analytical_hierarchy",
    "creative_hierarchy",
    "deep_hierarchy",
    "wide_hierarchy",
    "visualize_hierarchy",
    "layer_statistics",
    "trace_information_flow",
    "compare_architectures",
    "hierarchy_vs_single",
    "optimal_depth_experiment",
    "hierarchy_consistency_experiment",
]


# =============================================================================
# Notes
# =============================================================================
#
# NOTE: speculative_discover depends on prism.artifacts (removed in refactor)
# NOTE: Vortex is at sunwell.vortex (refactored)
#       Use: from sunwell.vortex import Vortex, solve, VortexConfig
# NOTE: Eye tuning disabled - requires prism/vortex adaptive routing
#       TODO: Reimplement eye_tuning with current vortex API
# NOTE: cellular experiments depend on prism.artifacts (removed in refactor)
