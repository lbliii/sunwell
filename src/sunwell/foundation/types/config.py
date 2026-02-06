"""Configuration type definitions - single source of truth for all config classes."""


from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sunwell.contracts.events import AgentEvent
    from sunwell.foundation.types.model_size import ModelSize


@dataclass(frozen=True, slots=True)
class SpawnConfig:
    """Configuration for automatic simulacrum spawning."""

    enabled: bool = True
    """Whether auto-spawning is enabled."""

    novelty_threshold: float = 0.7
    """How different a query must be from existing simulacrums to trigger spawn (0-1)."""

    min_queries_before_spawn: int = 3
    """Minimum queries in a new domain before spawning."""

    domain_coherence_threshold: float = 0.5
    """How related queries must be to form a coherent simulacrum."""

    max_simulacrums: int = 20
    """Maximum simulacrums to prevent unbounded growth."""

    auto_name: bool = True
    """Auto-generate simulacrum names from detected topics."""


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    """Configuration for simulacrum lifecycle management."""

    stale_days: int = 30
    """Days without access before simulacrum is considered stale."""

    archive_days: int = 90
    """Days without access before auto-archiving."""

    min_useful_nodes: int = 3
    """Minimum nodes for a simulacrum to be considered useful."""

    min_useful_learnings: int = 1
    """Minimum learnings for a simulacrum to be considered useful."""

    auto_archive: bool = True
    """Automatically archive stale simulacrums."""

    auto_merge_empty: bool = True
    """Auto-merge empty simulacrums into similar ones."""

    protect_recently_spawned_days: int = 7
    """Don't cleanup simulacrums spawned within this many days."""


@dataclass(frozen=True, slots=True)
class SimulacrumConfig:
    """Configuration for simulacrum management."""

    base_path: str = ".sunwell/memory"
    """Base path for simulacrum storage."""

    spawn: SpawnConfig = field(default_factory=SpawnConfig)
    """Auto-spawn configuration."""

    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    """Lifecycle management configuration."""


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    """Configuration for Ollama server parallelism.

    Maps to Ollama environment variables:
    - OLLAMA_NUM_PARALLEL: Max parallel requests per model
    - OLLAMA_MAX_LOADED_MODELS: Max models loaded concurrently
    - OLLAMA_MAX_QUEUE: Max queued requests (default: 512)

    See: https://github.com/ollama/ollama/blob/main/docs/faq.md#how-does-ollama-handle-concurrent-requests
    """

    base_url: str = "http://localhost:11434"
    """Ollama server URL."""

    num_parallel: int | None = None
    """Max parallel requests per model. None = auto-detect from server.

    Maps to OLLAMA_NUM_PARALLEL. If None, Sunwell queries the server
    or defaults to 4 (Ollama's default when sufficient VRAM).
    """

    max_loaded_models: int | None = None
    """Max models loaded concurrently. None = server default (3 * GPUs).

    Maps to OLLAMA_MAX_LOADED_MODELS.
    """

    connection_pool_size: int = 20
    """httpx connection pool size for concurrent requests.

    Should be >= num_parallel * num_models_in_use.
    """

    request_timeout: float = 120.0
    """Request timeout in seconds for generation calls."""


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class BindingConfig:
    """Configuration for lens bindings."""

    default: str = "coder"
    """Default binding name (used when no binding specified)."""


@dataclass(frozen=True, slots=True)
class LensConfig:
    """Lens-related configuration (RFC-131: Helm-style layering).

    Enables global lens defaults that are applied to all sessions,
    similar to Helm's values.yaml pattern.

    Configure in ~/.sunwell/defaults.yaml or .sunwell/config.yaml:
        lens:
          default_compose:
            - sunwell/base/muru
          search_paths:
            - ./lenses
            - ~/.sunwell/lenses
    """

    default_compose: tuple[str, ...] = ("base/muru",)
    """Base lenses applied to ALL sessions (RFC-131).

    These lenses are composed (prepended) to every resolved lens,
    providing global defaults like M'uru identity. Paths are resolved
    via search_paths (default: ./lenses, ~/.sunwell/lenses).

    Default: ["base/muru"] → resolves to lenses/base/muru.lens

    To use a different identity:
        default_compose:
          - my-custom-identity

    To disable identity entirely:
        default_compose: []
    """

    search_paths: tuple[str, ...] = ("./lenses", "~/.sunwell/lenses")
    """Paths to search for lens files.

    Paths are searched in order. Supports:
    - Relative paths (from current directory)
    - Home directory (~)
    - Absolute paths
    """


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Configuration for model defaults (local-first)."""

    default_provider: str = "ollama"
    """Default model provider (ollama for local-first)."""

    default_model: str = "llama3.1:8b"
    """Default model name (llama3.1:8b for local-first with native tool support)."""

    smart_routing: bool = False
    """Enable adaptive model selection by default."""


@dataclass(frozen=True, slots=True)
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

    titles: tuple[str, ...] = ("M'uru", "The Naaru")
    """List of titles to alternate between in messages."""

    alternate_titles: bool = True
    """Whether to alternate between titles in messages."""

    # Ollama API mode - native API has better system prompt override
    use_native_ollama_api: bool = True
    """Use native /api/generate instead of /v1/chat for better identity enforcement."""

    # ==========================================================================
    # 2-Tier Model Architecture (RFC-081)
    # Simplified: classifier (1b) + worker (20b)
    # Middle-tier (4b-12b) removed - quality gap not worth latency savings
    # ==========================================================================

    # Voice: Fast classifier for routing + trivial answers (~1s responses)
    voice: str = "llama3.1:8b"
    """Model for routing/classification. Fast, can answer trivial directly."""

    # Fallback models if voice unavailable
    voice_models: tuple[str, ...] = ("llama3.1:8b", "gemma3:1b", "llama3.2:3b")
    """Models to try for voice (in order of preference)."""

    voice_temperature: float = 0.3
    """Temperature for voice generation (lower = more precise)."""

    # Wisdom: The brain for generation, judging, complex reasoning (~15-20s)
    wisdom: str = "gpt-oss:20b"
    """Model for generation/judgment. High quality, consistent output."""

    # Fallback models if wisdom unavailable
    wisdom_models: tuple[str, ...] = ("gpt-oss:20b", "gemma3:12b", "llama3:70b")
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

    # RFC-030: Unified Router (replaces attunement, discernment, model routing)
    router: str = "llama3.1:8b"
    """Single model for ALL routing decisions (RFC-030).

    This tiny model handles:
    - Intent classification
    - Complexity assessment
    - Lens selection
    - Tool prediction
    - User mood/expertise detection

    Recommended: llama3.1:8b (good tool support, accurate JSON output)
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

    max_parallel_tasks: int = 8
    """Maximum tasks to execute concurrently (RFC-034).

    Increased from 4 to 8 because:
    - Ollama defaults to OLLAMA_NUM_PARALLEL=4 per model
    - With synthesis + judge models, that's 8 concurrent requests
    - Modern GPUs handle this well with context parallelism

    Set higher if you have:
    - High VRAM (24GB+): Try 12-16
    - Multiple GPUs: Try num_parallel * num_gpus
    - CPU inference with lots of RAM: Try 16-32
    """

    max_parallel_llm_requests: int | None = None
    """Maximum concurrent LLM requests to Ollama. None = auto-detect.

    When None, Sunwell uses min(max_parallel_tasks, ollama_num_parallel).
    Set explicitly to override the auto-detected limit.
    """

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

    # RFC-053: Studio Agent Bridge - Event streaming
    event_callback: Callable[[AgentEvent], None] | None = None
    """Callback for streaming AgentEvent objects (RFC-053).

    When set, events are forwarded to this callback during execution.
    Used by Studio to receive real-time progress updates via --json mode.

    Example:
        >>> def emit_json(event: AgentEvent) -> None:
        ...     print(json.dumps(event.to_dict()), flush=True)
        >>> config = NaaruConfig(event_callback=emit_json)
    """

    @classmethod
    def for_model_size(cls, model_size: ModelSize, **overrides: Any) -> NaaruConfig:
        """Create config optimized for a specific model size.

        Smaller models benefit from harmonic synthesis (multi-persona generation).
        Larger models perform well with simpler pipelines.

        Args:
            model_size: The target model size
            **overrides: Override any preset values

        Returns:
            NaaruConfig tuned for the model size
        """
        from sunwell.foundation.types.model_size import ModelSize

        presets: dict[ModelSize, dict[str, Any]] = {
            ModelSize.TINY: {
                "harmonic_synthesis": True,
                "resonance": 3,
            },
            ModelSize.SMALL: {
                "harmonic_synthesis": True,
                "resonance": 2,
            },
            ModelSize.MEDIUM: {
                "harmonic_synthesis": False,
                "resonance": 1,
            },
            ModelSize.LARGE: {
                "harmonic_synthesis": False,
                "resonance": 0,
            },
        }
        base = presets.get(model_size, presets[ModelSize.SMALL])
        base.update(overrides)
        return cls(**base)
