"""Configuration type definitions - single source of truth for all config classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    """Enable intent-aware cognitive routing (RFC-020)."""

    attunement_model: Any | None = None
    """Model for cognitive routing (None = use voice model)."""

    # Shards (parallel helpers)
    num_analysis_shards: int = 2
    """Number of analysis worker shards."""

    num_synthesis_shards: int = 2
    """Number of synthesis worker shards."""
