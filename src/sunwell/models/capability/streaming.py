"""Typed streaming with tool call awareness.

Provides visibility into tool calling during streaming,
rather than hiding tool calls until generation completes.

Key types:
- StreamChunkType: Type of content in each chunk
- StreamChunk: A typed chunk from the stream
- ToolStreamParser: Incremental parser for tool calls in streams
"""

import re
from dataclasses import dataclass
from enum import Enum


class StreamChunkType(Enum):
    """Types of chunks in a tool-aware stream."""

    TEXT = "text"
    """Regular text content."""

    TOOL_START = "tool_start"
    """Beginning of a tool call."""

    TOOL_ARGS = "tool_args"
    """Partial tool call arguments (streaming)."""

    TOOL_END = "tool_end"
    """End of a tool call."""

    THINKING = "thinking"
    """Reasoning/thinking content (for reasoning models)."""


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A typed chunk from tool-aware streaming.

    Provides visibility into tool calling during streaming,
    rather than hiding tool calls until generation completes.
    """

    type: StreamChunkType
    """What kind of content this chunk contains."""

    content: str | None = None
    """Text content (for TEXT and THINKING chunks)."""

    tool_name: str | None = None
    """Tool being called (for TOOL_* chunks)."""

    tool_call_id: str | None = None
    """Unique ID for this tool call."""

    partial_args: str | None = None
    """Partial JSON arguments (for TOOL_ARGS chunks)."""

    is_complete: bool = False
    """For TOOL_END: whether arguments are complete and valid."""


class ToolStreamParser:
    """Parse streaming response into typed chunks.

    Handles incremental JSON parsing for tool call arguments.
    Detects tool call boundaries and emits appropriate chunk types.
    """

    # Pattern to detect start of JSON tool call
    _TOOL_START_PATTERN = re.compile(r'(\{["\']?tool["\']?:|\{["\']?function["\']?:|```json)')

    # Pattern to extract tool name
    _TOOL_NAME_PATTERN = re.compile(r'["\']?(?:tool|function)["\']?\s*:\s*["\']([^"\']+)["\']')

    def __init__(self) -> None:
        self._buffer = ""
        self._in_tool_call = False
        self._current_tool_id: str | None = None
        self._current_tool_name: str | None = None
        self._args_buffer = ""
        self._call_count = 0

    def feed(self, raw_chunk: str) -> list[StreamChunk]:
        """Feed a raw chunk and return typed chunks.

        Args:
            raw_chunk: Raw text from model stream

        Returns:
            List of typed StreamChunks (may be empty)
        """
        chunks: list[StreamChunk] = []
        self._buffer += raw_chunk

        # Check for tool call start patterns
        if not self._in_tool_call:
            match = self._TOOL_START_PATTERN.search(self._buffer)
            if match:
                # Emit any text before the tool call
                text_before = self._buffer[: match.start()]
                if text_before.strip():
                    chunks.append(
                        StreamChunk(
                            type=StreamChunkType.TEXT,
                            content=text_before,
                        )
                    )

                # Start tool call tracking
                self._in_tool_call = True
                self._call_count += 1
                self._current_tool_id = f"stream_{self._call_count}"
                self._args_buffer = self._buffer[match.start() :]
                self._buffer = ""

                chunks.append(
                    StreamChunk(
                        type=StreamChunkType.TOOL_START,
                        tool_call_id=self._current_tool_id,
                    )
                )
            else:
                # No tool call detected, buffer text for potential partial match
                # Keep last 20 chars in buffer for pattern matching
                if len(self._buffer) > 50:
                    emit = self._buffer[:-20]
                    self._buffer = self._buffer[-20:]
                    if emit.strip():
                        chunks.append(
                            StreamChunk(
                                type=StreamChunkType.TEXT,
                                content=emit,
                            )
                        )
                return chunks

        if self._in_tool_call:
            # Accumulate args
            self._args_buffer += self._buffer
            self._buffer = ""

            # Try to extract tool name if not yet known
            if self._current_tool_name is None:
                name_match = self._TOOL_NAME_PATTERN.search(self._args_buffer)
                if name_match:
                    self._current_tool_name = name_match.group(1)

            # Emit partial args
            if self._args_buffer:
                chunks.append(
                    StreamChunk(
                        type=StreamChunkType.TOOL_ARGS,
                        tool_name=self._current_tool_name,
                        tool_call_id=self._current_tool_id,
                        partial_args=self._args_buffer,
                    )
                )

            # Check for tool call end
            # Complete JSON object or code block end
            stripped = self._args_buffer.rstrip()
            brace_balance = stripped.count("{") - stripped.count("}")

            if (brace_balance == 0 and stripped.endswith("}")) or stripped.endswith("```"):
                # Find where the JSON ends
                end_pos = self._find_json_end(self._args_buffer)

                chunks.append(
                    StreamChunk(
                        type=StreamChunkType.TOOL_END,
                        tool_name=self._current_tool_name,
                        tool_call_id=self._current_tool_id,
                        is_complete=True,
                    )
                )

                # Keep any text after the tool call for processing
                remaining_after = self._args_buffer[end_pos:].strip() if end_pos else ""

                # Reset state for potential next tool call
                self._in_tool_call = False
                self._current_tool_id = None
                self._current_tool_name = None
                self._args_buffer = ""

                # If there's more content, recursively process it
                if remaining_after:
                    self._buffer = remaining_after
                    chunks.extend(self.feed(""))

        return chunks

    def _find_json_end(self, text: str) -> int:
        """Find the end position of a JSON object in text."""
        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return i + 1

        return len(text)

    def finalize(self) -> list[StreamChunk]:
        """Finalize parsing and emit any remaining content.

        Call this when the stream ends to flush any buffered content.

        Returns:
            List of final StreamChunks
        """
        chunks: list[StreamChunk] = []

        # If we were in a tool call, close it
        if self._in_tool_call:
            chunks.append(
                StreamChunk(
                    type=StreamChunkType.TOOL_END,
                    tool_name=self._current_tool_name,
                    tool_call_id=self._current_tool_id,
                    is_complete=False,  # Incomplete if stream ended mid-call
                )
            )
            self._in_tool_call = False

        # Emit any remaining buffered text
        remaining = self._buffer + self._args_buffer
        if remaining.strip():
            chunks.append(
                StreamChunk(
                    type=StreamChunkType.TEXT,
                    content=remaining,
                )
            )

        # Reset state
        self._buffer = ""
        self._args_buffer = ""
        self._current_tool_id = None
        self._current_tool_name = None

        return chunks

    def reset(self) -> None:
        """Reset parser state for reuse."""
        self._buffer = ""
        self._in_tool_call = False
        self._current_tool_id = None
        self._current_tool_name = None
        self._args_buffer = ""
        self._call_count = 0
