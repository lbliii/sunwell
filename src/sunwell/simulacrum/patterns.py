"""Shared pre-compiled regex patterns for the simulacrum package.

Centralizes domain detection patterns to avoid duplication and ensures
all patterns are compiled once at module load time (O(1) per match).

Used by:
- context/focus.py
- extractors/facet_extractor.py
"""

import re
from typing import Pattern

# =============================================================================
# Domain Detection Patterns
# =============================================================================
# Pre-compiled patterns for detecting topic domains in text.
# Each pattern is compiled once at module load, avoiding per-call overhead.

DOMAIN_PATTERNS: dict[str, Pattern[str]] = {
    # Technical domains
    "auth": re.compile(
        r"\b(auth|login|logout|session|token|jwt|oauth|password|credential|permission|role)\b",
        re.IGNORECASE,
    ),
    "api": re.compile(
        r"\b(api|endpoint|request|response|rest|graphql|http|status|route)\b",
        re.IGNORECASE,
    ),
    "database": re.compile(
        r"\b(database|db|sql|query|table|index|postgres|mysql|mongo|redis)\b",
        re.IGNORECASE,
    ),
    "cache": re.compile(
        r"\b(cache|redis|memcache|ttl|expire|invalidat)\b",
        re.IGNORECASE,
    ),
    "network": re.compile(
        r"\b(network|socket|tcp|udp|dns|proxy|firewall|timeout|connection)\b",
        re.IGNORECASE,
    ),
    "error": re.compile(
        r"\b(error|exception|fail|crash|bug|issue|problem|broken)\b",
        re.IGNORECASE,
    ),
    "performance": re.compile(
        r"\b(performance|slow|fast|latency|throughput|optimize|bottleneck)\b",
        re.IGNORECASE,
    ),
    "security": re.compile(
        r"\b(security|vulnerab|inject|xss|csrf|encrypt|decrypt|hash)\b",
        re.IGNORECASE,
    ),
    "config": re.compile(
        r"\b(config|setting|environment|env|variable|parameter|option)\b",
        re.IGNORECASE,
    ),
    "deploy": re.compile(
        r"\b(deploy|release|ci|cd|pipeline|docker|kubernetes|container)\b",
        re.IGNORECASE,
    ),
    # Actions
    "debug": re.compile(
        r"\b(debug|trace|log|inspect|investigate|diagnose)\b",
        re.IGNORECASE,
    ),
    "refactor": re.compile(
        r"\b(refactor|restructure|reorganize|clean|simplify)\b",
        re.IGNORECASE,
    ),
    "test": re.compile(
        r"\b(test|spec|assert|mock|fixture|coverage)\b",
        re.IGNORECASE,
    ),
    "document": re.compile(
        r"\b(document|doc|readme|comment|explain)\b",
        re.IGNORECASE,
    ),
    "cli": re.compile(
        r"\b(command[- ]?line|cli|terminal|shell)\b",
        re.IGNORECASE,
    ),
}

# File path pattern for detecting file references in text
FILE_PATH_PATTERN: Pattern[str] = re.compile(
    r"[\w/]+\.(py|ts|js|go|rs|java|rb|md|yaml|json)"
)


def detect_domains(text: str) -> list[str]:
    """Detect domain tags in text using pre-compiled patterns.

    Args:
        text: Text to analyze

    Returns:
        List of detected domain tags
    """
    domains = []
    text_lower = text.lower()
    for domain, pattern in DOMAIN_PATTERNS.items():
        if pattern.search(text_lower):
            domains.append(domain)
    return domains


def extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text.

    Args:
        text: Text to analyze

    Returns:
        List of detected file extensions (e.g., ["py", "ts"])
    """
    return FILE_PATH_PATTERN.findall(text)
