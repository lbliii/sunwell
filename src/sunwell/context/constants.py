"""Context size limits and constants for RFC-024."""

# Context size thresholds
MAX_INLINE_CHARS = 500       # Inline directly in prompt
MAX_CONTEXT_CHARS = 8192     # Include as separate context block
MAX_TOTAL_CONTEXT = 32768    # Total context budget per request
