"""Model size classification for configuration tuning.

This module provides a simple enum for classifying models by parameter count,
used for selecting appropriate configuration presets.
"""

from __future__ import annotations

from enum import Enum


class ModelSize(str, Enum):
    """Model size categories for configuration tuning.

    Used to select appropriate defaults for harmonic synthesis,
    resonance, and other model-size-dependent features.
    """

    TINY = "tiny"      # <1B params (gemma3:1b, phi-3-mini)
    SMALL = "small"    # 1-4B params (llama3.2:3b, phi-3-small)
    MEDIUM = "medium"  # 4-13B params (llama3.1:8b, mistral)
    LARGE = "large"    # 13B+ params (llama3.1:70b, mixtral, gpt-oss:20b)

    @classmethod
    def from_param_count(cls, params_billions: float) -> ModelSize:
        """Infer size category from parameter count."""
        if params_billions < 1.0:
            return cls.TINY
        elif params_billions < 4.0:
            return cls.SMALL
        elif params_billions < 13.0:
            return cls.MEDIUM
        else:
            return cls.LARGE

    @classmethod
    def from_model_name(cls, name: str) -> ModelSize:
        """Infer size from common model name patterns.

        Looks for parameter count indicators in model names like:
        - "llama3.1:8b" -> MEDIUM
        - "gpt-oss:20b" -> LARGE
        - "gemma3:1b" -> TINY
        """
        import re

        name_lower = name.lower()

        # Look for explicit parameter counts (e.g., "8b", "70b", "1.5b")
        param_match = re.search(r"(\d+(?:\.\d+)?)\s*b(?:illion)?", name_lower)
        if param_match:
            params = float(param_match.group(1))
            return cls.from_param_count(params)

        # Known tiny models
        tiny_patterns = ["gemma3:1b", "phi-3-mini", "tinyllama"]
        if any(p in name_lower for p in tiny_patterns):
            return cls.TINY

        # Known small models
        small_patterns = ["3b", "phi-3-small", "llama3.2"]
        if any(p in name_lower for p in small_patterns):
            return cls.SMALL

        # Known large models
        large_patterns = ["70b", "mixtral", "gpt-4", "claude", "20b", "32b"]
        if any(p in name_lower for p in large_patterns):
            return cls.LARGE

        # Default to medium (most common local model size)
        return cls.MEDIUM
