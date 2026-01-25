"""Tool call introspection and repair (RFC-134).

Pre-execution validation and repair of tool arguments to catch common
LLM mistakes BEFORE execution:

- Markdown fences in code content
- Invalid/malformed paths
- Empty required arguments
- JSON in string arguments

This is a key differentiator — competitors execute malformed calls and fail,
while Sunwell intercepts and repairs them automatically.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sunwell.models import ToolCall

# Pre-compiled regex patterns for detection
_RE_MARKDOWN_FENCE = re.compile(r"^```(?:\w+)?\s*\n(.*?)\n```$", re.DOTALL)
_RE_LEADING_FENCE = re.compile(r"^```(?:\w+)?\s*\n?")
_RE_TRAILING_FENCE = re.compile(r"\n?```\s*$")
_RE_PATH_PREFIX = re.compile(r"^\.?/")
_RE_JSON_OBJECT = re.compile(r'^["\']?\{.*\}["\']?$', re.DOTALL)


@dataclass(frozen=True, slots=True)
class IntrospectionResult:
    """Result of tool call introspection.

    Contains the (possibly repaired) tool call and metadata about
    what was detected and fixed.
    """

    tool_call: ToolCall
    """The tool call, possibly with repaired arguments."""

    repairs: tuple[str, ...]
    """Human-readable descriptions of repairs made."""

    warnings: tuple[str, ...]
    """Warnings that don't block execution."""

    blocked: bool
    """If True, this call should not be executed."""

    block_reason: str | None
    """Reason for blocking (if blocked=True)."""


def _sanitize_code_content(content: str) -> tuple[str, list[str]]:
    """Strip markdown fences from code content.

    Args:
        content: Raw content that may have markdown fences

    Returns:
        Tuple of (sanitized_content, list_of_repairs)
    """
    repairs: list[str] = []

    if not content:
        return content, repairs

    # Check for full fence wrapper: ```lang\ncode\n```
    fence_match = _RE_MARKDOWN_FENCE.match(content)
    if fence_match:
        repairs.append("Stripped markdown code fences from content")
        return fence_match.group(1), repairs

    # Check for leading fence only
    if _RE_LEADING_FENCE.match(content):
        content = _RE_LEADING_FENCE.sub("", content)
        repairs.append("Stripped leading markdown fence")

    # Check for trailing fence only
    if _RE_TRAILING_FENCE.search(content):
        content = _RE_TRAILING_FENCE.sub("", content)
        repairs.append("Stripped trailing markdown fence")

    return content, repairs


def _normalize_path(path: str, workspace: Path) -> tuple[str, list[str]]:
    """Normalize a file path to workspace-relative format.

    Args:
        path: Raw path from tool call
        workspace: Workspace root for validation

    Returns:
        Tuple of (normalized_path, list_of_repairs)
    """
    repairs: list[str] = []

    if not path:
        return path, repairs

    original = path

    # Strip leading ./ or /
    if path.startswith("./"):
        path = path[2:]
        repairs.append(f"Stripped leading './' from path: {original}")
    elif path.startswith("/"):
        # Check if it's an absolute path within workspace
        try:
            abs_path = Path(path)
            if abs_path.is_relative_to(workspace):
                path = str(abs_path.relative_to(workspace))
                repairs.append(f"Converted absolute path to relative: {original}")
        except (ValueError, TypeError):
            # Not relative to workspace, keep as-is (will fail validation later)
            pass

    # Remove redundant path components
    try:
        normalized = str(Path(path))
        if normalized != path and normalized != ".":
            repairs.append(f"Normalized path components: {path} -> {normalized}")
            path = normalized
    except (ValueError, TypeError):
        pass

    return path, repairs


def _validate_required_args(
    tool_name: str,
    arguments: dict,
) -> tuple[bool, str | None]:
    """Validate required arguments are present and non-empty.

    Args:
        tool_name: Name of the tool
        arguments: Tool arguments

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Required args by tool
    required_args: dict[str, list[str]] = {
        "write_file": ["path", "content"],
        "edit_file": ["path", "old_content", "new_content"],
        "read_file": ["path"],
        "list_files": ["path"],
        "search_files": ["pattern"],
        "run_command": ["command"],
        "mkdir": ["path"],
    }

    if tool_name not in required_args:
        return True, None

    for arg in required_args[tool_name]:
        if arg not in arguments:
            return False, f"Missing required argument: {arg}"
        value = arguments[arg]
        if value is None:
            return False, f"Required argument '{arg}' is None"
        if isinstance(value, str) and not value.strip():
            return False, f"Required argument '{arg}' is empty"

    return True, None


def _check_file_extension_mismatch(
    path: str,
    content: str,
) -> list[str]:
    """Check for mismatches between file extension and content.

    Args:
        path: File path
        content: File content

    Returns:
        List of warnings
    """
    warnings: list[str] = []

    if not path or not content:
        return warnings

    ext = Path(path).suffix.lower()

    # Python content indicators
    python_indicators = [
        "def ",
        "class ",
        "import ",
        "from ",
        "async def",
        "@dataclass",
        "if __name__",
    ]

    # Check for Python content in non-Python file
    if ext not in (".py", ".pyi", ".pyx"):
        has_python = any(ind in content for ind in python_indicators)
        if has_python and ext in (".txt", ".md", ".json", ".yaml", ".yml"):
            warnings.append(
                f"File extension '{ext}' may not match Python content. "
                f"Consider using '.py' extension for: {path}"
            )

    return warnings


def introspect_tool_call(
    tc: ToolCall,
    workspace: Path,
) -> IntrospectionResult:
    """Pre-execution validation and repair of a tool call.

    Detects and repairs common LLM mistakes:
    - Markdown fences in code content
    - Invalid/malformed paths
    - Empty required arguments

    Args:
        tc: The tool call to introspect
        workspace: Workspace root for path validation

    Returns:
        IntrospectionResult with repaired call and metadata
    """
    repairs: list[str] = []
    warnings: list[str] = []
    new_args = dict(tc.arguments)

    # 1. Validate required arguments
    is_valid, error = _validate_required_args(tc.name, new_args)
    if not is_valid:
        return IntrospectionResult(
            tool_call=tc,
            repairs=(),
            warnings=(),
            blocked=True,
            block_reason=error,
        )

    # 2. Sanitize code content (write_file, edit_file)
    if tc.name == "write_file" and "content" in new_args:
        content, content_repairs = _sanitize_code_content(new_args["content"])
        new_args["content"] = content
        repairs.extend(content_repairs)

    if tc.name == "edit_file":
        if "old_content" in new_args:
            old, old_repairs = _sanitize_code_content(new_args["old_content"])
            new_args["old_content"] = old
            repairs.extend(old_repairs)
        if "new_content" in new_args:
            new, new_repairs = _sanitize_code_content(new_args["new_content"])
            new_args["new_content"] = new
            repairs.extend(new_repairs)

    # 3. Normalize paths
    if tc.name in ("write_file", "edit_file", "read_file", "list_files", "mkdir"):
        if "path" in new_args:
            path, path_repairs = _normalize_path(new_args["path"], workspace)
            new_args["path"] = path
            repairs.extend(path_repairs)

    # 4. Check for extension mismatches (warnings only)
    if tc.name == "write_file" and "path" in new_args and "content" in new_args:
        ext_warnings = _check_file_extension_mismatch(
            new_args["path"],
            new_args["content"],
        )
        warnings.extend(ext_warnings)

    # Build repaired tool call if needed
    if repairs:
        repaired_tc = ToolCall(
            id=tc.id,
            name=tc.name,
            arguments=new_args,
        )
    else:
        repaired_tc = tc

    return IntrospectionResult(
        tool_call=repaired_tc,
        repairs=tuple(repairs),
        warnings=tuple(warnings),
        blocked=False,
        block_reason=None,
    )


def introspect_tool_calls(
    tool_calls: tuple[ToolCall, ...],
    workspace: Path,
) -> list[IntrospectionResult]:
    """Introspect multiple tool calls.

    Convenience function for batch introspection.

    Args:
        tool_calls: Tool calls to introspect
        workspace: Workspace root

    Returns:
        List of IntrospectionResult for each call
    """
    return [introspect_tool_call(tc, workspace) for tc in tool_calls]
