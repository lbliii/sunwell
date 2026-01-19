"""Configuration type definitions - single source of truth for all config classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.naaru.rotation import ModelSize
    from sunwell.naaru.planners.protocol import PlanningStrategy


@dataclass
class EmbeddingConfig:
    """Configuration for embeddings."""

    prefer_local: bool = True
    """Prefer local (Ollama) embeddings over cloud APIs."""

    ollama_model: str = "all-minilm"
    """Default Ollama embedding model."""

    ollama_url: str = "http://localhost:11434"
    """Ollama server URL."""

    fallback_to_hash: bool = True
    """Fall back to hash embeddings if no provider available."""


@dataclass
class ModelConfig:
    """Configuration for model defaults."""

    default_provider: str = "openai"
    """Default model provider."""

    default_model: str = "gpt-4o"
    """Default model name."""

    smart_routing: bool = False
    """Enable adaptive model selection by default."""


@dataclass
class NaaruConfig:
    """Configuration for the Naaru coordinated intelligence architecture.
    
    This is the single source of truth. Used by:
    - config.py for YAML/env loading
    - naaru/naaru.py for runtime defaults
    
    Thematic naming based on Naaru lore:
    - Voice: The model that speaks/creates (synthesis)
    - Wisdom: The model that judges/evaluates
    - Harmonic: Multiple voices in alignment (multi-persona generation)
    - Convergence: Shared purpose/working memory
    - Resonance: Feedback that amplifies quality
    - Discernment: Quick insight before deep judgment
    - Attunement: Intent-aware routing
    - Purity: How pure the Light must be (quality threshold)
    """

    # Persona - The Naaru's identity (RFC-023)
    name: str = "M'uru"
    """The Naaru's name (used when asked directly)."""

    title: str = "The Naaru"
    """A title/descriptor for the Naaru."""

    titles: list[str] = field(default_factory=lambda: ["M'uru", "The Naaru"])
    """List of titles to alternate between in messages."""

    alternate_titles: bool = True
    """Whether to alternate between titles in messages."""

    # Ollama API mode - native API has better system prompt override
    use_native_ollama_api: bool = True
    """Use native /api/generate instead of /v1/chat for better identity enforcement."""

    # Voice (synthesis model) - "auto" tries common small models
    voice: str = "auto"
    """Model for code generation. "auto" = try common small models."""

    # Prioritized list of small models to try for voice (first available wins)
    voice_models: list[str] = field(default_factory=lambda: [
        "gemma3:1b", "gemma2:2b", "llama3.2:1b", "phi3:mini", "qwen2:0.5b"
    ])
    """Models to try for voice (in order of preference)."""

    voice_temperature: float = 0.3
    """Temperature for voice generation (lower = more precise)."""

    # Wisdom (judge model) - "auto" tries common capable models
    wisdom: str = "auto"
    """Model for quality judgment. "auto" = try common capable models."""

    # Prioritized list of capable models to try for wisdom
    wisdom_models: list[str] = field(default_factory=lambda: [
        "gemma3:4b", "gemma2:9b", "llama3.2:3b", "phi3:medium", "qwen2:7b"
    ])
    """Models to try for wisdom (in order of preference)."""

    purity_threshold: float = 6.0
    """Minimum quality score to approve proposals (0-10)."""

    # Naaru features
    harmonic_synthesis: bool = True
    """Enable multi-persona generation with voting."""

    resonance: int = 2
    """Max refinement attempts for rejected proposals."""

    convergence: int = 7
    """Working memory slots (Miller's Law: 7±2)."""

    discernment: bool = True
    """Enable tiered validation (fast model before full judgment)."""

    attunement: bool = True
    """Enable intent-aware cognitive routing (RFC-020).
    
    DEPRECATED in RFC-030: Use `router` instead. This flag is kept for
    backward compatibility and will be removed in v0.6.
    """

    attunement_model: Any | None = None
    """Model for cognitive routing (None = use voice model).
    
    DEPRECATED in RFC-030: Use `router` instead.
    """

    # RFC-030: Unified Router (replaces attunement, discernment, model routing)
    router: str = "qwen2.5:1.5b"
    """Single model for ALL routing decisions (RFC-030).
    
    This tiny model handles:
    - Intent classification
    - Complexity assessment
    - Lens selection
    - Tool prediction
    - User mood/expertise detection
    
    Recommended: qwen2.5:1.5b (fast, accurate JSON output)
    """

    router_temperature: float = 0.1
    """Temperature for router model (lower = more consistent)."""

    router_cache_size: int = 1000
    """LRU cache size for routing decisions."""

    # Shards (parallel helpers)
    num_analysis_shards: int = 2
    """Number of analysis worker shards."""

    num_synthesis_shards: int = 2
    """Number of synthesis worker shards."""
    
    # RFC-034: Parallel Task Execution
    enable_parallel_execution: bool = True
    """Execute independent tasks in parallel when possible (RFC-034)."""
    
    max_parallel_tasks: int = 4
    """Maximum tasks to execute concurrently (RFC-034)."""
    
    planning_strategy: str = "contract_first"
    """How to decompose goals into tasks (RFC-034).
    
    - "sequential": RFC-032 behavior, linear dependencies
    - "contract_first": Identify contracts first, then implementations (default)
    - "resource_aware": Minimize file conflicts for maximum parallelism
    """
    
    parallel_failure_mode: Literal["complete", "cancel"] = "complete"
    """What to do when one task in a parallel batch fails (RFC-034).
    
    - "complete": Let other tasks finish (default, maximizes useful work)
    - "cancel": Stop all sibling tasks immediately
    """

    # RFC-038: Harmonic Planning
    harmonic_planning: bool = True
    """Enable multi-candidate plan generation (RFC-038).
    
    Default True because:
    - With Naaru, overhead is <50ms (negligible)
    - Quality improvement is significant (>15% better plans)
    - Users get better plans without thinking about it
    
    Use --no-harmonic to disable explicitly.
    """

    harmonic_candidates: int = 5
    """Number of plan candidates to generate.
    
    5 is the sweet spot: enough diversity, near-zero marginal cost with Naaru.
    Benchmarks show diminishing returns beyond 7.
    """

    harmonic_refinement: int = 1
    """Rounds of iterative plan refinement.
    
    Default 1 (single refinement pass) because:
    - Cheap with Naaru (context cached in Convergence)
    - Often improves score by 5-10%
    - Second pass rarely improves further
    
    Set to 0 for fastest planning, 2 for quality-critical work.
    """

    harmonic_variance: str = "prompting"
    """Variance strategy for candidate generation.
    
    - "prompting": Different discovery prompts (parallel-first, minimal, etc.)
    - "temperature": Vary temperature for exploration
    - "constraints": Add different structural constraints
    - "mixed": Combination of prompting and temperature
    """

    # Thought Rotation (RFC-028)
    rotation: bool = True
    """Enable thought rotation for structured perspective shifting."""

    rotation_intensity: str = "auto"
    """Rotation intensity: "auto", "heavy", "standard", "light", "none".
    
    - auto: Detect model size and adjust automatically
    - heavy: Explicit XML frames, longer frame durations (for tiny models)
    - standard: Explicit XML frames, normal durations (for small models)
    - light: Soft markers, shorter durations (for medium models)
    - none: No rotation (for large models or when disabled)
    """

    rotation_frames: list[str] | None = None
    """Override default frames. None = auto-select based on task type."""

    lexer_model: Any | None = None
    """Model for ThoughtLexer task classification (RFC-028).
    
    Needs a model capable of producing JSON (qwen2.5:3b recommended).
    If None, falls back to attunement_model, then keyword classification.
    """

    # RFC-033: Unified Architecture (composable layers)
    diversity: str = "auto"
    """Diversity strategy: "none", "sampling", "rotation", "harmonic", "auto".
    
    - none: Single generation (1x cost)
    - sampling: Temperature-based diversity (3x cost, 0 prompt overhead)
    - rotation: Cognitive frame markers (1.2x cost)
    - harmonic: Multi-persona generation (3.5x-6x cost)
    - auto: Select based on task analysis
    """
    
    diversity_count: int = 3
    """Number of candidates for sampling/harmonic strategies."""
    
    diversity_temps: tuple[float, ...] = (0.3, 0.7, 1.0)
    """Temperature values for sampling strategy."""
    
    selection: str = "auto"
    """Selection strategy: "passthrough", "heuristic", "voting", "judge", "auto".
    
    - passthrough: Return first candidate (free)
    - heuristic: Score using rules (free, CPU only)
    - voting: Personas vote on candidates (~500 tokens)
    - judge: Full LLM evaluation (~1000 tokens per candidate)
    - auto: Select based on diversity strategy and task
    """
    
    refinement: str = "auto"
    """Refinement strategy: "none", "tiered", "full", "auto".
    
    - none: Skip refinement (free)
    - tiered: Lightweight validation first, escalate if needed (0-2000 tokens)
    - full: Always use full LLM judge, iterate until approved (~2000 tokens per iteration)
    - auto: Select based on cost budget and task
    """
    
    refinement_max_attempts: int = 2
    """Maximum refinement attempts for tiered/full strategies."""
    
    cost_budget: str = "normal"
    """Cost budget: "minimal", "normal", "quality".
    
    - minimal: ≤1.5x cost (single generation)
    - normal: ≤4x cost (sampling + heuristic or rotation + tiered)
    - quality: ≤10x cost (harmonic + voting + full refinement)
    """
    
    task_type: str = "auto"
    """Task type hint: "code", "creative", "analysis", "auto".
    
    Used for heuristic selection and task analysis.
    """

    @classmethod
    def for_model_size(cls, model_size: "ModelSize", **overrides: Any) -> "NaaruConfig":
        """Create config optimized for a specific model size.
        
        Smaller models benefit from more scaffolding (rotation, harmonic synthesis).
        Larger models perform better with less structure.
        
        Args:
            model_size: The target model size
            **overrides: Override any preset values
            
        Returns:
            NaaruConfig tuned for the model size
        """
        from sunwell.naaru.rotation import ModelSize
        
        presets: dict[ModelSize, dict[str, Any]] = {
            ModelSize.TINY: {
                "rotation": True,
                "rotation_intensity": "heavy",
                "harmonic_synthesis": True,
                "resonance": 3,
            },
            ModelSize.SMALL: {
                "rotation": True,
                "rotation_intensity": "standard",
                "harmonic_synthesis": True,
                "resonance": 2,
            },
            ModelSize.MEDIUM: {
                "rotation": True,
                "rotation_intensity": "light",
                "harmonic_synthesis": False,
                "resonance": 1,
            },
            ModelSize.LARGE: {
                "rotation": False,
                "rotation_intensity": "none",
                "harmonic_synthesis": False,
                "resonance": 0,
            },
        }
        base = presets.get(model_size, presets[ModelSize.SMALL])
        base.update(overrides)
        return cls(**base)
