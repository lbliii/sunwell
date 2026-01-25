"""Model capability system for intelligent tool calling routing.

RFC-136: Model-Agnostic Tool Calling

This module provides structured model parsing, version-aware capability detection,
and provider-specific adaptations for tool calling.

Key components:
- ModelSpec: Parsed model specification (family, version, size, etc.)
- ModelCapability: What a model can do (native tools, parallel, streaming, etc.)
- SchemaAdapter: Provider-specific schema conversion
- ToolCallNormalizer: Model-specific tool call parsing
- StreamChunk: Typed streaming events
- ToolError: Structured error handling

Usage:
    from sunwell.models.capability import parse_model_id, get_capability

    spec = parse_model_id("claude-3.5-sonnet")
    # ModelSpec(family="claude", version=(3, 5), variant="sonnet")

    capability = get_capability("claude-3.5-sonnet")
    # ModelCapability(native_tools=True, parallel_tools=True, ...)
"""

# Core parsing and registry
from sunwell.models.capability.parser import ModelSpec, parse_model_id
from sunwell.models.capability.registry import ModelCapability, get_capability

# Schema adapters
from sunwell.models.capability.schema import (
    AnthropicSchemaAdapter,
    OllamaSchemaAdapter,
    OpenAISchemaAdapter,
    SchemaAdapter,
    get_schema_adapter,
)

# Tool emulation
from sunwell.models.capability.emulation import (
    build_emulation_prompt,
    format_tool_descriptions,
    optimize_tool_definitions,
)

# Tool call normalization
from sunwell.models.capability.normalizer import (
    NormalizationResult,
    ToolCallNormalizer,
)

# Typed streaming
from sunwell.models.capability.streaming import (
    StreamChunk,
    StreamChunkType,
    ToolStreamParser,
)

# Tool description engineering
from sunwell.models.capability.tool_engineering import (
    ToolQuality,
    audit_tool,
    audit_tool_set,
    enhance_tool_description,
)

# Parallel execution
from sunwell.models.capability.parallel import (
    ParallelExecutionPlan,
    ToolCategory,
    can_parallelize,
    classify_tool,
    plan_parallel_execution,
)

# Validation
from sunwell.models.capability.validation import (
    ValidationResult,
    create_retry_prompt,
    format_validation_feedback,
    validate_tool_call,
)

# Response formatting
from sunwell.models.capability.response_format import (
    FormattedResult,
    ResponseFormat,
    format_tool_result,
    get_recommended_format,
)

# Namespacing
from sunwell.models.capability.namespacing import (
    denamespacify_tool_call,
    merge_registries,
    namespace_tools,
    parse_namespaced_name,
    resolve_tool,
)

# Evaluation
from sunwell.models.capability.evaluation import (
    EvaluationLogger,
    ToolCallEvent,
    ToolEvaluationMetrics,
    get_logger,
    get_metrics,
    log_tool_call,
)

__all__ = [
    # Parser
    "ModelSpec",
    "parse_model_id",
    # Registry
    "ModelCapability",
    "get_capability",
    # Schema adapters
    "SchemaAdapter",
    "OpenAISchemaAdapter",
    "AnthropicSchemaAdapter",
    "OllamaSchemaAdapter",
    "get_schema_adapter",
    # Emulation
    "build_emulation_prompt",
    "format_tool_descriptions",
    "optimize_tool_definitions",
    # Normalizer
    "ToolCallNormalizer",
    "NormalizationResult",
    # Streaming
    "StreamChunk",
    "StreamChunkType",
    "ToolStreamParser",
    # Tool engineering
    "ToolQuality",
    "audit_tool",
    "audit_tool_set",
    "enhance_tool_description",
    # Parallel
    "ToolCategory",
    "ParallelExecutionPlan",
    "classify_tool",
    "plan_parallel_execution",
    "can_parallelize",
    # Validation
    "ValidationResult",
    "validate_tool_call",
    "format_validation_feedback",
    "create_retry_prompt",
    # Response format
    "ResponseFormat",
    "FormattedResult",
    "format_tool_result",
    "get_recommended_format",
    # Namespacing
    "namespace_tools",
    "parse_namespaced_name",
    "resolve_tool",
    "denamespacify_tool_call",
    "merge_registries",
    # Evaluation
    "ToolEvaluationMetrics",
    "ToolCallEvent",
    "EvaluationLogger",
    "get_logger",
    "log_tool_call",
    "get_metrics",
]
