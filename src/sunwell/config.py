"""Sunwell configuration management.

Loads configuration from .sunwell/config.yaml with sensible defaults.
All settings can be overridden via environment variables (SUNWELL_*).

Config locations (in priority order):
1. Explicit path passed to load_config()
2. .sunwell/config.yaml (project-local)
3. ~/.sunwell/config.yaml (user-global)
4. Built-in defaults

Thread Safety:
    Uses threading.Lock for thread-safe lazy initialization in
    free-threaded Python (3.14t).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sunwell.types.config import EmbeddingConfig, ModelConfig, NaaruConfig, OllamaConfig


@dataclass
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


@dataclass
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


@dataclass
class SimulacrumConfig:
    """Configuration for simulacrum management."""

    base_path: str = ".sunwell/memory"
    """Base path for simulacrum storage."""

    spawn: SpawnConfig = field(default_factory=SpawnConfig)
    """Auto-spawn configuration."""

    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    """Lifecycle management configuration."""


# Config classes moved to sunwell.types.config - imported above


@dataclass
class SunwellConfig:
    """Root configuration for Sunwell."""

    simulacrum: SimulacrumConfig = field(default_factory=SimulacrumConfig)
    """Simulacrum configuration."""

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    """Embedding configuration."""

    model: ModelConfig = field(default_factory=ModelConfig)
    """Model defaults."""

    naaru: NaaruConfig = field(default_factory=NaaruConfig)
    """Naaru coordinated intelligence configuration."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    """Ollama server parallelism configuration."""

    verbose: bool = False
    """Enable verbose output by default."""


# Global config instance (lazy-loaded, thread-safe)
_config: SunwellConfig | None = None
_config_lock = threading.Lock()


def _deep_update(base: dict, updates: dict) -> dict:
    """Recursively update a dict with another dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _apply_env_overrides(config_dict: dict) -> dict:
    """Apply environment variable overrides.

    Environment variables follow pattern: SUNWELL_SECTION_SUBSECTION_KEY
    Uses double underscore or known section names to split correctly.

    Examples:
        SUNWELL_HEADSPACE_SPAWN_ENABLED=false
        SUNWELL_HEADSPACE_SPAWN_MAX_HEADSPACES=50
        SUNWELL_EMBEDDING_OLLAMA_MODEL=nomic-embed-text
    """
    prefix = "SUNWELL_"

    # Known section structure for proper splitting
    known_sections = {
        "simulacrum": {"spawn", "lifecycle", "base_path"},
        "embedding": {"prefer_local", "ollama_model", "ollama_url", "fallback_to_hash"},
        "model": {"default_provider", "default_model", "smart_routing"},
        "naaru": {
            "name", "title", "voice", "wisdom", "router",
            "harmonic_synthesis", "resonance", "convergence", "discernment", "attunement",
            "enable_parallel_execution", "max_parallel_tasks", "max_parallel_llm_requests",
        },
        "ollama": {"base_url", "num_parallel", "max_loaded_models", "connection_pool_size", "request_timeout"},
    }

    # Known keys that contain underscores (to avoid splitting them)
    compound_keys = {
        "base_path", "prefer_local", "ollama_model", "ollama_url", "fallback_to_hash",
        "default_provider", "default_model", "smart_routing", "novelty_threshold",
        "min_queries_before_spawn", "domain_coherence_threshold", "max_simulacrums",
        "auto_name", "stale_days", "archive_days", "min_useful_nodes",
        "min_useful_learnings", "auto_archive", "auto_merge_empty",
        "protect_recently_spawned_days",
        # Naaru keys
        "voice_temperature", "voice_models", "wisdom_models", "purity_threshold",
        "harmonic_synthesis", "num_analysis_shards", "num_synthesis_shards",
        "router_temperature", "router_cache_size",
        "enable_parallel_execution", "max_parallel_tasks", "max_parallel_llm_requests",
        "use_native_ollama_api", "alternate_titles",
        # Ollama keys
        "base_url", "num_parallel", "max_loaded_models", "connection_pool_size", "request_timeout",
    }

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Get the path after prefix, lowercase
        path_str = key[len(prefix):].lower()

        # Try to parse intelligently by finding known structure
        path_parts = []
        remaining = path_str

        # First level: known section
        for section in known_sections:
            if remaining.startswith(section + "_"):
                path_parts.append(section)
                remaining = remaining[len(section) + 1:]
                break

        if not path_parts:
            # Unknown section, skip
            continue

        # Second level: subsection or key
        section = path_parts[0]
        if section in known_sections:
            for subsection in known_sections[section]:
                if remaining.startswith(subsection + "_") or remaining == subsection:
                    path_parts.append(subsection)
                    remaining = remaining[len(subsection):].lstrip("_")
                    break

        # Remaining is the key (might have underscores)
        if remaining:
            # Try to match compound keys
            matched = False
            for compound in compound_keys:
                if remaining == compound or remaining.replace("_", "") == compound.replace("_", ""):
                    path_parts.append(compound)
                    matched = True
                    break
            if not matched:
                path_parts.append(remaining.replace("_", "_"))  # Keep as-is

        if len(path_parts) < 2:
            continue

        # Navigate to the right place in config
        current = config_dict
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            if isinstance(current[part], dict):
                current = current[part]
            else:
                break

        # Set the value with type coercion
        final_key = path_parts[-1]
        if value.lower() in ("true", "false"):
            current[final_key] = value.lower() == "true"
        elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            current[final_key] = int(value)
        else:
            try:
                current[final_key] = float(value)
            except ValueError:
                current[final_key] = value

    return config_dict


def _dict_to_config(data: dict) -> SunwellConfig:
    """Convert a dict to SunwellConfig."""
    # Build nested configs
    simulacrum_data = data.get("simulacrum", {})
    spawn_config = SpawnConfig(**simulacrum_data.get("spawn", {}))
    lifecycle_config = LifecycleConfig(**simulacrum_data.get("lifecycle", {}))
    simulacrum_config = SimulacrumConfig(
        base_path=simulacrum_data.get("base_path", ".sunwell/memory"),
        spawn=spawn_config,
        lifecycle=lifecycle_config,
    )

    embedding_config = EmbeddingConfig(**data.get("embedding", {}))
    model_config = ModelConfig(**data.get("model", {}))
    naaru_config = NaaruConfig(**data.get("naaru", {}))
    ollama_config = OllamaConfig(**data.get("ollama", {}))

    return SunwellConfig(
        simulacrum=simulacrum_config,
        embedding=embedding_config,
        model=model_config,
        naaru=naaru_config,
        ollama=ollama_config,
        verbose=data.get("verbose", False),
    )


def load_config(path: str | Path | None = None) -> SunwellConfig:
    """Load configuration from file with defaults and env overrides.

    Priority (highest to lowest):
    1. Environment variables (SUNWELL_*)
    2. Explicit path if provided
    3. .sunwell/config.yaml (project-local)
    4. ~/.sunwell/config.yaml (user-global)
    5. Built-in defaults

    Args:
        path: Optional explicit config file path.

    Returns:
        Merged SunwellConfig instance.
    """
    global _config

    # Start with defaults as dict
    config_dict: dict[str, Any] = {
        "simulacrum": {
            "base_path": ".sunwell/memory",
            "spawn": {
                "enabled": True,
                "novelty_threshold": 0.7,
                "min_queries_before_spawn": 3,
                "domain_coherence_threshold": 0.5,
                "max_simulacrums": 20,
                "auto_name": True,
            },
            "lifecycle": {
                "stale_days": 30,
                "archive_days": 90,
                "min_useful_nodes": 3,
                "min_useful_learnings": 1,
                "auto_archive": True,
                "auto_merge_empty": True,
                "protect_recently_spawned_days": 7,
            },
        },
        "embedding": {
            "prefer_local": True,
            "ollama_model": "all-minilm",
            "ollama_url": "http://localhost:11434",
            "fallback_to_hash": True,
        },
        "model": {
            "default_provider": "openai",
            "default_model": "gpt-4o",
            "smart_routing": False,
        },
        "naaru": {
            "name": "M'uru",
            "title": "The Naaru",
            "titles": ["M'uru", "The Naaru"],
            "alternate_titles": True,
            "use_native_ollama_api": True,
            # =================================================================
            # 2-Tier Model Architecture (RFC-081)
            # Simplified: classifier (1b) + worker (20b)
            # Middle-tier (4b-12b) removed - quality gap not worth latency
            # =================================================================
            # Voice: Fast classifier for routing + trivial answers
            "voice": "gemma3:1b",
            "voice_models": ["gemma3:1b", "llama3.2:3b", "qwen2.5:1.5b"],
            "voice_temperature": 0.3,
            # Wisdom: The brain - generation, judging, complex reasoning
            "wisdom": "gpt-oss:20b",
            "wisdom_models": ["gpt-oss:20b", "gemma3:12b", "llama3:70b"],
            "purity_threshold": 6.0,
            "harmonic_synthesis": True,
            "resonance": 2,
            "convergence": 7,
            "discernment": True,
            "attunement": True,
            "num_analysis_shards": 2,
            "num_synthesis_shards": 2,
            # RFC-030: Unified Router (uses voice model)
            "router": "gemma3:1b",
            "router_temperature": 0.1,
            "router_cache_size": 1000,
            # RFC-034: Parallel Task Execution
            "enable_parallel_execution": True,
            "max_parallel_tasks": 8,
            "max_parallel_llm_requests": None,
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "num_parallel": None,  # Auto-detect from server
            "max_loaded_models": None,  # Server default
            "connection_pool_size": 20,
            "request_timeout": 120.0,
        },
        "verbose": False,
    }

    # Try to load from files
    config_paths = []
    if path:
        config_paths.append(Path(path))
    config_paths.extend([
        Path(".sunwell/config.yaml"),
        Path.home() / ".sunwell" / "config.yaml",
    ])

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f) or {}
                _deep_update(config_dict, file_config)
                break  # Use first found config
            except Exception:
                pass  # Skip invalid config files

    # Apply environment overrides
    config_dict = _apply_env_overrides(config_dict)

    # Convert to typed config
    _config = _dict_to_config(config_dict)
    return _config


def get_config() -> SunwellConfig:
    """Get the current configuration, loading if needed.

    Thread-safe with double-check locking for free-threaded Python.
    """
    global _config

    # Fast path: already initialized
    if _config is not None:
        return _config

    # Slow path: acquire lock, double-check, load
    with _config_lock:
        if _config is None:
            _config = load_config()
        return _config


def reset_config() -> None:
    """Reset the global config (useful for testing).

    Thread-safe for free-threaded Python.
    """
    global _config
    with _config_lock:
        _config = None


def resolve_naaru_model(
    config_value: str,
    model_list: list[str],
    check_availability: bool = True,
) -> str | None:
    """Resolve a naaru model setting to an actual model name.

    Handles "auto" by trying models from the list in order.

    Args:
        config_value: The configured value ("auto" or a model name).
        model_list: List of models to try when config_value is "auto".
        check_availability: If True, verify model is available (Ollama only).

    Returns:
        Model name to use, or None if no model available.
    """
    # If explicit model specified, use it
    if config_value and config_value != "auto":
        return config_value

    # Auto-resolve: try each model in order
    if not check_availability:
        # No availability check - just return first in list
        return model_list[0] if model_list else None

    # Check Ollama availability
    try:
        import httpx

        config = get_config()
        ollama_url = config.embedding.ollama_url

        # Get available models
        response = httpx.get(f"{ollama_url}/api/tags", timeout=2.0)
        if response.status_code != 200:
            # Ollama not available, return first model (may fail later)
            return model_list[0] if model_list else None

        available = {m["name"] for m in response.json().get("models", [])}

        # Find first available model
        for model in model_list:
            # Check exact match and base name (e.g., "gemma3:1b" vs "gemma3")
            if model in available:
                return model
            # Check without tag
            base = model.split(":")[0]
            for avail in available:
                if avail.startswith(base):
                    return avail

        # No model from list available
        return model_list[0] if model_list else None

    except Exception:
        # Any error - just return first model
        return model_list[0] if model_list else None


def save_default_config(path: str | Path = ".sunwell/config.yaml") -> Path:
    """Save the default configuration to a file.

    Creates a well-documented config file with all options.

    Args:
        path: Where to save the config.

    Returns:
        Path to the saved config file.
    """
    config_content = '''# Sunwell Configuration
# https://github.com/sunwell/sunwell

# Simulacrum management (auto-evolving memory)
simulacrum:
  # Base path for simulacrum storage
  base_path: ".sunwell/memory"

  # Auto-spawn configuration
  spawn:
    # Enable automatic simulacrum creation from query patterns
    enabled: true

    # How different a query must be to trigger spawn (0-1)
    # Higher = more conservative spawning
    novelty_threshold: 0.7

    # Minimum queries in a domain before spawning
    min_queries_before_spawn: 3

    # How related queries must be to form a coherent simulacrum (0-1)
    domain_coherence_threshold: 0.5

    # Maximum number of simulacrums (prevents unbounded growth)
    max_simulacrums: 20

    # Auto-generate names from detected topics
    auto_name: true

  # Lifecycle management (archival, cleanup)
  lifecycle:
    # Days without access before marked stale
    stale_days: 30

    # Days without access before auto-archiving
    archive_days: 90

    # Minimum nodes for simulacrum to be useful
    min_useful_nodes: 3

    # Minimum learnings for simulacrum to be useful
    min_useful_learnings: 1

    # Automatically archive stale simulacrums
    auto_archive: true

    # Auto-merge empty simulacrums into similar ones
    auto_merge_empty: true

    # Don't cleanup recently spawned simulacrums (days)
    protect_recently_spawned_days: 7

# Embedding configuration
embedding:
  # Prefer local (Ollama) embeddings over cloud APIs
  prefer_local: true

  # Default Ollama embedding model
  ollama_model: "all-minilm"

  # Ollama server URL
  ollama_url: "http://localhost:11434"

  # Fall back to hash embeddings if no provider available
  fallback_to_hash: true

# Model defaults
model:
  # Default provider (openai, anthropic, ollama)
  default_provider: "openai"

  # Default model name
  default_model: "gpt-4o"

  # Enable adaptive model selection by default
  smart_routing: false

# Naaru - Coordinated Intelligence Architecture (RFC-019)
# Thematic naming based on Naaru lore from World of Warcraft
naaru:
  # Persona - Your Naaru's identity (RFC-023)
  # Name your Naaru! This is used when someone asks "what's your name?"
  name: "M'uru"

  # Title used in status messages (alternates with name)
  title: "The Naaru"

  # List of titles to cycle through in messages
  # e.g., "M'uru noted..." then "The Naaru observed..."
  titles:
    - "M'uru"
    - "The Naaru"

  # Whether to alternate between titles (false = always use name)
  alternate_titles: true

  # Use native Ollama API (/api/generate) instead of OpenAI-compatible (/v1/chat)
  # Native API has explicit system prompt override - better for identity enforcement
  # See: https://docs.ollama.com/api/generate
  use_native_ollama_api: true

  # ==========================================================================
  # 2-Tier Model Architecture (RFC-081)
  # Simplified: classifier (1b) + worker (20b)
  # Middle-tier (4b-12b) removed - quality gap not worth latency savings
  # ==========================================================================

  # Voice - Fast classifier for routing + trivial answers (~1s responses)
  # Uses gemma3:1b by default - can also answer simple questions directly
  voice: "gemma3:1b"

  # Fallback models if voice unavailable
  voice_models:
    - "gemma3:1b"
    - "llama3.2:3b"
    - "qwen2.5:1.5b"

  # Voice temperature (lower = more precise classification)
  voice_temperature: 0.3

  # Wisdom - The brain for generation, judging, complex reasoning (~15-20s)
  # gpt-oss:20b provides consistent high quality across all tasks
  wisdom: "gpt-oss:20b"

  # Fallback models if wisdom unavailable  
  wisdom_models:
    - "gpt-oss:20b"
    - "gemma3:12b"
    - "llama3:70b"

  # Purity threshold - Minimum quality score to approve (0-10)
  purity_threshold: 6.0

  # Harmonic Synthesis - Multiple voices in alignment
  # Enables multi-persona generation with voting
  harmonic_synthesis: true

  # Resonance - Feedback that amplifies quality
  # Max refinement attempts for rejected proposals
  resonance: 2

  # Convergence - Shared working memory slots (Miller's Law: 7±2)
  convergence: 7

  # Discernment - Quick insight before deep judgment
  # Enables tiered validation (fast model → full wisdom)
  discernment: true

  # Attunement - Intent-aware cognitive routing (RFC-020)
  attunement: true

  # Shards - Parallel helpers (fragments working in parallel)
  num_analysis_shards: 2
  num_synthesis_shards: 2

  # Parallel Task Execution (RFC-034)
  # Execute independent tasks concurrently for faster completion
  enable_parallel_execution: true

  # Maximum concurrent tasks
  # Increased from 4 to 8: handles synthesis + judge models in parallel
  # For high VRAM (24GB+): try 12-16
  # For multi-GPU: try num_parallel * num_gpus
  max_parallel_tasks: 8

  # Maximum concurrent LLM requests (null = auto-detect from Ollama)
  # Set explicitly to override auto-detection
  # max_parallel_llm_requests: 8

# Ollama Server Configuration
# Controls parallelism at the Ollama server level
# See: https://github.com/ollama/ollama/blob/main/docs/faq.md#how-does-ollama-handle-concurrent-requests
ollama:
  # Ollama server URL
  base_url: "http://localhost:11434"

  # Max parallel requests per model (maps to OLLAMA_NUM_PARALLEL)
  # null = auto-detect from server (default: 4 if sufficient VRAM)
  # Increase this for high VRAM systems (8-12 for 24GB+)
  num_parallel: null

  # Max models loaded concurrently (maps to OLLAMA_MAX_LOADED_MODELS)
  # null = server default (3 * num_gpus, or 3 for CPU)
  max_loaded_models: null

  # Connection pool size for concurrent requests
  # Should be >= num_parallel * models_in_use
  connection_pool_size: 20

  # Request timeout in seconds
  request_timeout: 120.0

# Global settings
verbose: false
'''

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config_content)
    return path
