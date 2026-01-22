"""Sunwell Error System.

Provides structured error handling with:
- Numeric error codes for programmatic handling
- User-friendly messages
- Recovery hints for self-healing
- Context for debugging
"""


from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    """Numeric error codes organized by category.

    Format: XYYY where X = category, YYY = specific error

    Categories:
        1xxx - Model/Provider errors
        2xxx - Lens errors
        3xxx - Tool/Skill errors
        4xxx - Validation errors
        5xxx - Configuration errors
        6xxx - Runtime errors
        7xxx - Network/IO errors
    """

    # 1xxx - Model/Provider Errors
    MODEL_NOT_FOUND = 1001
    MODEL_AUTH_FAILED = 1002
    MODEL_RATE_LIMITED = 1003
    MODEL_CONTEXT_EXCEEDED = 1004
    MODEL_TIMEOUT = 1005
    MODEL_API_ERROR = 1006
    MODEL_TOOLS_NOT_SUPPORTED = 1007
    MODEL_STREAMING_NOT_SUPPORTED = 1008
    MODEL_PROVIDER_UNAVAILABLE = 1009
    MODEL_RESPONSE_INVALID = 1010

    # 2xxx - Lens Errors
    LENS_NOT_FOUND = 2001
    LENS_PARSE_ERROR = 2002
    LENS_CIRCULAR_DEPENDENCY = 2003
    LENS_VERSION_CONFLICT = 2004
    LENS_MERGE_CONFLICT = 2005
    LENS_INVALID_SCHEMA = 2006
    LENS_FOUNT_UNAVAILABLE = 2007

    # 3xxx - Tool/Skill Errors
    TOOL_NOT_FOUND = 3001
    TOOL_PERMISSION_DENIED = 3002
    TOOL_EXECUTION_FAILED = 3003
    TOOL_TIMEOUT = 3004
    TOOL_INVALID_ARGUMENTS = 3005
    SKILL_NOT_FOUND = 3101
    SKILL_PARSE_ERROR = 3102
    SKILL_EXECUTION_FAILED = 3103
    SKILL_VALIDATION_FAILED = 3104
    SKILL_SANDBOX_VIOLATION = 3105

    # 4xxx - Validation Errors
    VALIDATION_SCRIPT_FAILED = 4001
    VALIDATION_TIMEOUT = 4002
    VALIDATION_INVALID_OUTPUT = 4003
    VALIDATION_CONFIDENCE_LOW = 4004

    # 5xxx - Configuration Errors
    CONFIG_MISSING = 5001
    CONFIG_INVALID = 5002
    CONFIG_ENV_MISSING = 5003

    # 6xxx - Runtime Errors
    RUNTIME_STATE_INVALID = 6001
    RUNTIME_MEMORY_EXHAUSTED = 6002
    RUNTIME_CONCURRENT_LIMIT = 6003

    # 7xxx - Network/IO Errors
    NETWORK_UNREACHABLE = 7001
    NETWORK_TIMEOUT = 7002
    FILE_NOT_FOUND = 7003
    FILE_PERMISSION_DENIED = 7004
    FILE_WRITE_FAILED = 7005

    @property
    def category(self) -> str:
        """Get the error category name."""
        prefix = self.value // 1000
        return {
            1: "model",
            2: "lens",
            3: "tool",
            4: "validation",
            5: "config",
            6: "runtime",
            7: "io",
        }.get(prefix, "unknown")

    @property
    def is_recoverable(self) -> bool:
        """Whether this error type is typically recoverable."""
        # Non-recoverable errors
        non_recoverable = {
            ErrorCode.MODEL_AUTH_FAILED,
            ErrorCode.CONFIG_MISSING,
            ErrorCode.CONFIG_INVALID,
            ErrorCode.LENS_CIRCULAR_DEPENDENCY,
        }
        return self not in non_recoverable


# Human-readable error messages
ERROR_MESSAGES: dict[ErrorCode, str] = {
    # Model errors
    ErrorCode.MODEL_NOT_FOUND: "Model '{model}' not found. Check if it's installed or available.",
    ErrorCode.MODEL_AUTH_FAILED: "Authentication failed for {provider}. Check your API key.",
    ErrorCode.MODEL_RATE_LIMITED: "Rate limited by {provider}. Retry after {retry_after}s.",
    ErrorCode.MODEL_CONTEXT_EXCEEDED: "Input exceeds model's context window ({limit} tokens).",
    ErrorCode.MODEL_TIMEOUT: "Request to {provider} timed out after {timeout}s.",
    ErrorCode.MODEL_API_ERROR: "API error from {provider}: {detail}",
    ErrorCode.MODEL_TOOLS_NOT_SUPPORTED: "Model '{model}' does not support tool calling.",
    ErrorCode.MODEL_STREAMING_NOT_SUPPORTED: "Model '{model}' does not support streaming.",
    ErrorCode.MODEL_PROVIDER_UNAVAILABLE: "Provider '{provider}' is unavailable. Is it running?",
    ErrorCode.MODEL_RESPONSE_INVALID: "Invalid response from model: {detail}",

    # Lens errors
    ErrorCode.LENS_NOT_FOUND: "Lens '{lens}' not found at '{path}'.",
    ErrorCode.LENS_PARSE_ERROR: "Failed to parse lens '{lens}': {detail}",
    ErrorCode.LENS_CIRCULAR_DEPENDENCY: "Circular dependency detected: {chain}",
    ErrorCode.LENS_VERSION_CONFLICT: "Version conflict for '{lens}': {detail}",
    ErrorCode.LENS_MERGE_CONFLICT: "Cannot merge lenses: {detail}",
    ErrorCode.LENS_INVALID_SCHEMA: "Invalid lens schema: {detail}",
    ErrorCode.LENS_FOUNT_UNAVAILABLE: "Fount registry unavailable. Using local lenses only.",

    # Tool/Skill errors
    ErrorCode.TOOL_NOT_FOUND: "Tool '{tool}' not registered.",
    ErrorCode.TOOL_PERMISSION_DENIED: "Permission denied for tool '{tool}': {detail}",
    ErrorCode.TOOL_EXECUTION_FAILED: "Tool '{tool}' failed: {detail}",
    ErrorCode.TOOL_TIMEOUT: "Tool '{tool}' timed out after {timeout}s.",
    ErrorCode.TOOL_INVALID_ARGUMENTS: "Invalid arguments for tool '{tool}': {detail}",
    ErrorCode.SKILL_NOT_FOUND: "Skill '{skill}' not found.",
    ErrorCode.SKILL_PARSE_ERROR: "Failed to parse skill '{skill}': {detail}",
    ErrorCode.SKILL_EXECUTION_FAILED: "Skill '{skill}' execution failed: {detail}",
    ErrorCode.SKILL_VALIDATION_FAILED: "Skill '{skill}' output validation failed: {detail}",
    ErrorCode.SKILL_SANDBOX_VIOLATION: "Skill '{skill}' violated sandbox: {detail}",

    # Validation errors
    ErrorCode.VALIDATION_SCRIPT_FAILED: "Validation script '{script}' failed with exit code {exit_code}.",
    ErrorCode.VALIDATION_TIMEOUT: "Validation timed out after {timeout}s.",
    ErrorCode.VALIDATION_INVALID_OUTPUT: "Validator '{validator}' returned invalid output: {detail}",
    ErrorCode.VALIDATION_CONFIDENCE_LOW: "Confidence score {score} below threshold {threshold}.",

    # Config errors
    ErrorCode.CONFIG_MISSING: "Required configuration '{key}' not found.",
    ErrorCode.CONFIG_INVALID: "Invalid configuration for '{key}': {detail}",
    ErrorCode.CONFIG_ENV_MISSING: "Environment variable '{var}' not set.",

    # Runtime errors
    ErrorCode.RUNTIME_STATE_INVALID: "Invalid runtime state: {detail}",
    ErrorCode.RUNTIME_MEMORY_EXHAUSTED: "Memory limit exceeded. Consider reducing context size.",
    ErrorCode.RUNTIME_CONCURRENT_LIMIT: "Concurrent request limit reached ({limit}).",

    # IO errors
    ErrorCode.NETWORK_UNREACHABLE: "Cannot reach {host}. Check your network connection.",
    ErrorCode.NETWORK_TIMEOUT: "Network request to {host} timed out.",
    ErrorCode.FILE_NOT_FOUND: "File not found: {path}",
    ErrorCode.FILE_PERMISSION_DENIED: "Permission denied: {path}",
    ErrorCode.FILE_WRITE_FAILED: "Failed to write file: {path}",
}


# Recovery hints for self-healing
RECOVERY_HINTS: dict[ErrorCode, list[str]] = {
    ErrorCode.MODEL_TOOLS_NOT_SUPPORTED: [
        "Switch to a model that supports tools (e.g., llama3:8b, gpt-4o-mini)",
        "Disable tools with --no-tools flag",
        "Use the model without tool calling for simple conversations",
    ],
    ErrorCode.MODEL_RATE_LIMITED: [
        "Wait {retry_after} seconds before retrying",
        "Switch to a different model or provider",
        "Reduce request frequency",
    ],
    ErrorCode.MODEL_CONTEXT_EXCEEDED: [
        "Reduce the input size or conversation history",
        "Use a model with a larger context window",
        "Enable automatic context summarization",
    ],
    ErrorCode.MODEL_PROVIDER_UNAVAILABLE: [
        "Check if the provider service is running (e.g., 'ollama serve')",
        "Verify the provider URL is correct",
        "Switch to a different provider",
    ],
    ErrorCode.MODEL_AUTH_FAILED: [
        "Set the API key environment variable ({env_var})",
        "Check if your API key is valid and not expired",
        "Verify you have access to the requested model",
    ],
    ErrorCode.LENS_NOT_FOUND: [
        "Check the lens path is correct",
        "Use 'sunwell list' to see available lenses",
        "Create the lens with 'sunwell init'",
    ],
    ErrorCode.TOOL_PERMISSION_DENIED: [
        "Increase trust level with --trust flag",
        "Add the path to allowed patterns in lens",
        "Run with elevated permissions if appropriate",
    ],
    ErrorCode.SKILL_SANDBOX_VIOLATION: [
        "Review skill script for forbidden operations",
        "Add required paths to sandbox allowlist",
        "Use a higher trust level if script is trusted",
    ],
    ErrorCode.CONFIG_ENV_MISSING: [
        "Set the environment variable: export {var}=<value>",
        "Add it to your .env file",
        "Use --{flag} command line option instead",
    ],
}


class SunwellError(Exception):
    """Base error type for all Sunwell errors.

    Provides structured error information for:
    - Programmatic error handling (code)
    - User-friendly display (message)
    - Self-healing capabilities (recovery_hints)
    - Debugging (context, cause)

    Example:
        >>> err = SunwellError(
        ...     code=ErrorCode.MODEL_TOOLS_NOT_SUPPORTED,
        ...     context={"model": "gemma3:1b", "provider": "ollama"}
        ... )
        >>> print(err)
        [SW-1007] Model 'gemma3:1b' does not support tool calling.
        >>> print(err.recovery_hints[0])
        Switch to a model that supports tools (e.g., llama3:8b, gpt-4o-mini)
    """

    def __init__(
        self,
        code: ErrorCode,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        self.code = code
        self.context = context or {}
        self.cause = cause
        super().__init__(str(self))

    @property
    def message(self) -> str:
        """Get the formatted user-friendly message."""
        template = ERROR_MESSAGES.get(self.code, "An error occurred: {detail}")
        try:
            return template.format(**self.context)
        except KeyError:
            # Fallback if context doesn't have all keys
            return template

    @property
    def recovery_hints(self) -> list[str]:
        """Get recovery suggestions for this error."""
        hints = RECOVERY_HINTS.get(self.code, [])
        # Format hints with context
        formatted = []
        for hint in hints:
            try:
                formatted.append(hint.format(**self.context))
            except KeyError:
                formatted.append(hint)
        return formatted

    @property
    def is_recoverable(self) -> bool:
        """Whether this error is typically recoverable."""
        return self.code.is_recoverable

    @property
    def category(self) -> str:
        """Get the error category."""
        return self.code.category

    @property
    def error_id(self) -> str:
        """Get the error ID string (e.g., 'SW-1007')."""
        return f"SW-{self.code.value}"

    def __str__(self) -> str:
        return f"[{self.error_id}] {self.message}"

    def __repr__(self) -> str:
        return f"SunwellError(code={self.code!r}, context={self.context!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for logging/API responses."""
        return {
            "error_id": self.error_id,
            "code": self.code.value,
            "category": self.category,
            "message": self.message,
            "recoverable": self.is_recoverable,
            "recovery_hints": self.recovery_hints,
            "context": self.context,
        }

    def for_llm(self) -> str:
        """Format error for LLM consumption (self-healing).

        Provides structured information the LLM can use to:
        - Understand what went wrong
        - Choose a recovery strategy
        - Avoid the same error
        """
        parts = [
            f"ERROR {self.error_id}: {self.message}",
            f"Category: {self.category}",
            f"Recoverable: {self.is_recoverable}",
        ]

        if self.recovery_hints:
            parts.append("Recovery options:")
            for i, hint in enumerate(self.recovery_hints, 1):
                parts.append(f"  {i}. {hint}")

        if self.context:
            parts.append(f"Context: {self.context}")

        return "\n".join(parts)


# Convenience factory functions

def model_error(
    code: ErrorCode,
    model: str,
    provider: str,
    detail: str = "",
    cause: Exception | None = None,
    **extra: Any,
) -> SunwellError:
    """Create a model-related error."""
    return SunwellError(
        code=code,
        context={"model": model, "provider": provider, "detail": detail, **extra},
        cause=cause,
    )


def tools_not_supported(model: str, provider: str) -> SunwellError:
    """Create a MODEL_TOOLS_NOT_SUPPORTED error."""
    return SunwellError(
        code=ErrorCode.MODEL_TOOLS_NOT_SUPPORTED,
        context={"model": model, "provider": provider},
    )


def lens_error(
    code: ErrorCode,
    lens: str,
    detail: str = "",
    path: str = "",
    cause: Exception | None = None,
) -> SunwellError:
    """Create a lens-related error."""
    return SunwellError(
        code=code,
        context={"lens": lens, "detail": detail, "path": path},
        cause=cause,
    )


def tool_error(
    code: ErrorCode,
    tool: str,
    detail: str = "",
    cause: Exception | None = None,
    **extra: Any,
) -> SunwellError:
    """Create a tool-related error."""
    return SunwellError(
        code=code,
        context={"tool": tool, "detail": detail, **extra},
        cause=cause,
    )


def config_error(
    code: ErrorCode,
    key: str = "",
    var: str = "",
    detail: str = "",
    flag: str = "",
) -> SunwellError:
    """Create a configuration error."""
    return SunwellError(
        code=code,
        context={"key": key, "var": var, "detail": detail, "flag": flag},
    )


# Error translation from external exceptions

def from_openai_error(exc: Exception, model: str, provider: str) -> SunwellError:
    """Translate OpenAI client exceptions to SunwellError."""
    exc_type = type(exc).__name__
    message = str(exc)

    # Parse error message for specific cases
    if "does not support tools" in message:
        return tools_not_supported(model, provider)

    if "rate_limit" in exc_type.lower() or "rate limit" in message.lower():
        # Try to extract retry-after
        retry_after = 60  # Default
        return SunwellError(
            code=ErrorCode.MODEL_RATE_LIMITED,
            context={"model": model, "provider": provider, "retry_after": retry_after},
            cause=exc,
        )

    if "auth" in exc_type.lower() or "401" in message:
        env_var = f"{provider.upper()}_API_KEY"
        return SunwellError(
            code=ErrorCode.MODEL_AUTH_FAILED,
            context={"model": model, "provider": provider, "env_var": env_var},
            cause=exc,
        )

    if "context" in message.lower() and ("exceeded" in message.lower() or "too long" in message.lower()):
        return SunwellError(
            code=ErrorCode.MODEL_CONTEXT_EXCEEDED,
            context={"model": model, "provider": provider, "limit": "unknown"},
            cause=exc,
        )

    if "timeout" in exc_type.lower() or "timeout" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_TIMEOUT,
            context={"model": model, "provider": provider, "timeout": "unknown"},
            cause=exc,
        )

    if "connection" in message.lower() or "unreachable" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_PROVIDER_UNAVAILABLE,
            context={"model": model, "provider": provider},
            cause=exc,
        )

    # Generic API error
    return SunwellError(
        code=ErrorCode.MODEL_API_ERROR,
        context={"model": model, "provider": provider, "detail": message},
        cause=exc,
    )


def from_anthropic_error(exc: Exception, model: str) -> SunwellError:
    """Translate Anthropic client exceptions to SunwellError."""
    exc_type = type(exc).__name__
    message = str(exc)
    provider = "anthropic"

    if "rate" in exc_type.lower() or "rate limit" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_RATE_LIMITED,
            context={"model": model, "provider": provider, "retry_after": 60},
            cause=exc,
        )

    if "auth" in exc_type.lower() or "401" in message or "invalid api key" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_AUTH_FAILED,
            context={"model": model, "provider": provider, "env_var": "ANTHROPIC_API_KEY"},
            cause=exc,
        )

    if "overloaded" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_PROVIDER_UNAVAILABLE,
            context={"model": model, "provider": provider},
            cause=exc,
        )

    if "context" in message.lower() or "too many tokens" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_CONTEXT_EXCEEDED,
            context={"model": model, "provider": provider, "limit": "unknown"},
            cause=exc,
        )

    if "timeout" in exc_type.lower() or "timeout" in message.lower():
        return SunwellError(
            code=ErrorCode.MODEL_TIMEOUT,
            context={"model": model, "provider": provider, "timeout": "unknown"},
            cause=exc,
        )

    # Generic API error
    return SunwellError(
        code=ErrorCode.MODEL_API_ERROR,
        context={"model": model, "provider": provider, "detail": message},
        cause=exc,
    )
