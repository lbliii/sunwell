"""Structured model ID parsing.

Extracts family, version, size, provider, and custom flags from model identifiers.
Handles diverse formats from OpenAI, Anthropic, Ollama, and custom fine-tuned models.

Examples:
    "gpt-4o" → family="gpt", version=(4,), variant="o"
    "claude-3.5-sonnet" → family="claude", version=(3,5), variant="sonnet"
    "llama3.3:70b" → family="llama", version=(3,3), size=70_000_000_000
    "ollama/qwen3:32b" → family="qwen", version=(3,), size=32B, provider="ollama"
    "mycompany/llama3-ft-v2" → family="llama", version=(3,), org="mycompany", custom=True
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Parsed model specification.

    Attributes:
        family: Model family name (gpt, claude, llama, qwen, etc.)
        version: Version tuple for comparison (3, 5) > (3,)
        variant: Model variant (sonnet, turbo, instruct, etc.)
        size: Parameter count in billions (70B = 70_000_000_000)
        provider: Provider prefix (ollama, together, groq, etc.)
        org: Organization prefix for custom models
        custom: True if this is a fine-tuned or custom model
    """

    family: str
    version: tuple[int, ...] = ()
    variant: str | None = None
    size: int | None = None
    provider: str | None = None
    org: str | None = None
    custom: bool = False


# Compiled regex patterns for O(1) matching per family
_PATTERNS: dict[str, re.Pattern[str]] = {
    # OpenAI: gpt-4o, gpt-4-turbo, gpt-4o-2024-08-06, gpt-4o-mini
    "openai": re.compile(
        r"^(?P<family>gpt)(?:-(?P<version>[\d.]+))?(?P<variant_o>o)?(?:-(?P<variant>\w+))?(?:-\d{4}-\d{2}-\d{2})?$",
        re.IGNORECASE,
    ),
    # OpenAI o-series: o1, o1-preview, o3-mini
    "o_series": re.compile(
        r"^(?P<family>o\d+)(?:-(?P<variant>\w+))?$",
        re.IGNORECASE,
    ),
    # Anthropic: claude-3.5-sonnet, claude-3-opus, claude-sonnet-4-20250514
    # Version can be either after claude- or after a variant name
    "anthropic": re.compile(
        r"^(?P<family>claude)(?:-(?P<version1>[\d.]+))?(?:-(?P<variant1>\w+))?(?:-(?P<version2>[\d.]+))?(?:-(?P<variant2>\w+))?(?:-\d{8})?$",
        re.IGNORECASE,
    ),
    # Llama: llama3.3:70b, llama3.1-8b, llama3.3-code-ft, meta-llama/Llama-3.3-70B-Instruct
    "llama": re.compile(
        r"^(?:(?P<org>[\w-]+)/)?(?P<family>llama|Llama)[\s-]?(?P<version>[\d.]+)"
        r"(?:[:-](?P<size>\d+)[Bb])?(?:-(?P<variant>[\w-]+))?$",
        re.IGNORECASE,
    ),
    # Qwen: qwen2.5, qwen3:32b, qwen2.5-coder-32b
    "qwen": re.compile(
        r"^(?P<family>qwen)(?P<version>[\d.]+)?(?:-(?P<variant>\w+))?(?:[:-](?P<size>\d+)[Bb])?$",
        re.IGNORECASE,
    ),
    # Mistral: mistral-large, mixtral-8x7b, mistral-small-latest
    # Size pattern must come before variant to avoid \w+ eating the size
    "mistral": re.compile(
        r"^(?P<family>mistral|mixtral)(?:-(?P<size>\d+x\d+|\d+)[Bb])?(?:-(?P<variant>[a-z]+))?(?:-latest)?$",
        re.IGNORECASE,
    ),
    # Gemini: gemini-2.0-flash, gemini-1.5-pro, gemini-exp-1206
    "gemini": re.compile(
        r"^(?P<family>gemini)(?:-(?P<version>[\d.]+|exp))?(?:-(?P<variant>\w+))?(?:-\d+)?$",
        re.IGNORECASE,
    ),
    # DeepSeek: deepseek-r1, deepseek-v3, deepseek-coder
    "deepseek": re.compile(
        r"^(?P<family>deepseek)(?:-(?P<variant>[rv]\d+|\w+))?$",
        re.IGNORECASE,
    ),
    # Phi: phi-3, phi-3.5-mini
    "phi": re.compile(
        r"^(?P<family>phi)(?:-(?P<version>[\d.]+))?(?:-(?P<variant>\w+))?$",
        re.IGNORECASE,
    ),
    # Gemma: gemma-2b, gemma-7b-it
    "gemma": re.compile(
        r"^(?P<family>gemma)(?:-(?P<size>\d+)[Bb])?(?:-(?P<variant>\w+))?$",
        re.IGNORECASE,
    ),
}

# Provider prefixes that indicate hosting platform
_PROVIDER_PREFIXES = frozenset({
    "ollama",
    "together",
    "anyscale",
    "fireworks",
    "groq",
    "openrouter",
    "perplexity",
    "deepinfra",
})

# Known first-party organizations (not custom)
_FIRST_PARTY_ORGS = frozenset({
    "meta",
    "meta-llama",
    "mistralai",
    "google",
    "openai",
    "anthropic",
    "deepseek-ai",
    "qwen",
    "microsoft",
})


def parse_model_id(model_id: str) -> ModelSpec:
    """Parse a model ID into structured components.

    Handles:
    - Provider prefixes (ollama/, together/)
    - Version numbers (3.5, 3.3, 4)
    - Size suffixes (:70b, -8b)
    - Variants (sonnet, turbo, instruct)
    - Custom/fine-tuned models

    Args:
        model_id: Raw model identifier from configuration

    Returns:
        ModelSpec with parsed components
    """
    provider = None
    org = None

    # Extract provider prefix (ollama/, together/)
    if "/" in model_id:
        parts = model_id.split("/", 1)
        prefix_lower = parts[0].lower()

        if prefix_lower in _PROVIDER_PREFIXES:
            provider = prefix_lower
            model_id = parts[1]
        elif prefix_lower not in _FIRST_PARTY_ORGS:
            # Organization prefix (mycompany/model)
            org = parts[0]
            model_id = parts[1]
        else:
            # First-party org like meta-llama/Llama-3.3
            org = parts[0]
            model_id = parts[1]

    # Try each pattern
    for family_hint, pattern in _PATTERNS.items():
        match = pattern.match(model_id)
        if match:
            groups = match.groupdict()

            # Extract family
            family = (groups.get("family") or family_hint).lower()

            # Parse version - handle multiple version fields (anthropic)
            version_str = (
                groups.get("version")
                or groups.get("version1")
                or groups.get("version2")
                or ""
            )
            version = _parse_version(version_str)

            # Parse size
            size_str = groups.get("size", "") or ""
            size = _parse_size(size_str)

            # Extract variant - handle various patterns
            # OpenAI: "o" suffix (gpt-4o) vs additional variant (gpt-4o-mini)
            variant_o = groups.get("variant_o", "")
            variant = groups.get("variant") or groups.get("variant1") or groups.get("variant2")

            # For OpenAI, combine "o" suffix with variant if both present
            if variant_o and variant:
                # gpt-4o-mini → variant="mini" (o is part of version marker)
                pass  # variant is already "mini"
            elif variant_o and not variant:
                # gpt-4o → variant="o"
                variant = variant_o

            # For Anthropic: if variant1 is a version number, use variant2
            # claude-3-opus: variant1="opus", version1="3"
            # claude-sonnet-4: variant1="sonnet", version2="4"
            if family_hint == "anthropic" and groups.get("variant1"):
                v1 = groups.get("variant1", "")
                # Check if variant1 looks like a version (all digits/dots)
                if v1 and not v1.replace(".", "").isdigit():
                    # It's a real variant name like "sonnet" or "opus"
                    if groups.get("variant2"):
                        # Both present, use variant1 (first non-numeric)
                        variant = v1
                    else:
                        variant = v1

            # Determine if custom
            is_custom = org is not None and org.lower() not in _FIRST_PARTY_ORGS

            return ModelSpec(
                family=family,
                version=version,
                variant=variant.lower() if variant else None,
                size=size,
                provider=provider,
                org=org,
                custom=is_custom,
            )

    # Unknown model — extract what we can
    return ModelSpec(
        family=_extract_family(model_id),
        provider=provider,
        org=org,
        custom=True,  # Assume custom if unknown
    )


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string to tuple for comparison.

    Examples:
        "3.5" → (3, 5)
        "4" → (4,)
        "3.3.1" → (3, 3, 1)
        "" → ()
    """
    if not version_str:
        return ()

    parts = []
    for part in version_str.split("."):
        # Extract leading digits
        digits = ""
        for c in part:
            if c.isdigit():
                digits += c
            else:
                break
        if digits:
            parts.append(int(digits))

    return tuple(parts)


def _parse_size(size_str: str) -> int | None:
    """Parse size string to parameter count.

    Examples:
        "70" → 70_000_000_000
        "8x7" → 56_000_000_000 (MoE)
        "1.5" → 1_500_000_000
        "" → None
    """
    if not size_str:
        return None

    size_str = size_str.lower().strip()

    # Handle MoE format (8x7)
    if "x" in size_str:
        parts = size_str.split("x")
        if len(parts) == 2:
            try:
                return int(parts[0]) * int(parts[1]) * 1_000_000_000
            except ValueError:
                return None

    # Handle decimal (1.5b)
    try:
        return int(float(size_str) * 1_000_000_000)
    except ValueError:
        return None


def _extract_family(model_id: str) -> str:
    """Extract family name from unknown model ID.

    Strips common suffixes and extracts first word-like segment.
    """
    # Remove common suffixes
    clean = re.sub(
        r"[-_]?(instruct|chat|base|v\d+|ft|tuned|finetune|gguf|q\d+).*$",
        "",
        model_id,
        flags=re.IGNORECASE,
    )

    # Remove size suffixes
    clean = re.sub(r"[:-]?\d+[Bb]$", "", clean)

    # Take first word-like segment
    match = re.match(r"^[a-zA-Z]+", clean)
    return match.group(0).lower() if match else "unknown"
