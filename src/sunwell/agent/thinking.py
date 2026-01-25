"""Thinking Detection for Inference Visibility (RFC-081).

Detects reasoning blocks in streaming model output:
- <think>...</think> tags
- <critic>...</critic> tags
- <synthesize>...</synthesize> tags
- "Thinking..." patterns

Used by the agent to emit MODEL_THINKING events during generation.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

ThinkingPhase = Literal["think", "critic", "synthesize", "reasoning", "unknown"]

# Patterns for detecting thinking content
THINKING_PATTERNS: dict[ThinkingPhase, tuple[str, str]] = {
    "think": (r"<think>", r"</think>"),
    "critic": (r"<critic>", r"</critic>"),
    "synthesize": (r"<synthesize>", r"</synthesize>"),
    "reasoning": (r"Thinking\.\.\.", r"\n\n"),  # gpt-oss style
}


@dataclass(frozen=True, slots=True)
class ThinkingBlock:
    """A detected thinking block from model output."""

    phase: ThinkingPhase
    content: str
    is_complete: bool


@dataclass(slots=True)
class ThinkingDetector:
    """Detects thinking blocks in streaming output.

    Feed chunks of text as they arrive, and the detector will
    return any completed thinking blocks.

    Example:
        >>> detector = ThinkingDetector()
        >>> for chunk in stream:
        ...     blocks = detector.feed(chunk)
        ...     for block in blocks:
        ...         print(f"[{block.phase}] {block.content[:50]}...")
    """

    _buffer: str = field(default="")
    _current_phase: ThinkingPhase | None = field(default=None)
    _phase_start_pos: int = field(default=0)

    def feed(self, chunk: str) -> list[ThinkingBlock]:
        """Feed a chunk, return any completed thinking blocks.

        Args:
            chunk: Text chunk from model stream

        Returns:
            List of detected thinking blocks (may be empty)
        """
        self._buffer += chunk
        results: list[ThinkingBlock] = []

        # If not currently in a thinking block, look for opening tags
        if self._current_phase is None:
            for phase, (open_pat, _) in THINKING_PATTERNS.items():
                match = re.search(open_pat, self._buffer)
                if match:
                    self._current_phase = phase
                    self._phase_start_pos = match.end()
                    # Emit start event (empty content, not complete)
                    results.append(ThinkingBlock(phase=phase, content="", is_complete=False))
                    break

        # If in a thinking block, look for closing tag
        if self._current_phase is not None:
            _, close_pat = THINKING_PATTERNS[self._current_phase]
            match = re.search(close_pat, self._buffer[self._phase_start_pos :])
            if match:
                # Extract content between open and close
                end = self._phase_start_pos + match.start()
                content = self._buffer[self._phase_start_pos : end]
                results.append(
                    ThinkingBlock(
                        phase=self._current_phase,
                        content=content.strip(),
                        is_complete=True,
                    )
                )
                # Clear buffer after the closing tag
                end_pos = self._phase_start_pos + match.end()
                self._buffer = self._buffer[end_pos:]
                self._current_phase = None
                self._phase_start_pos = 0

        # Prevent buffer from growing unbounded (keep last 1000 chars if not in block)
        if self._current_phase is None and len(self._buffer) > 1000:
            self._buffer = self._buffer[-500:]

        return results

    def get_current_thinking(self) -> str | None:
        """Get the content of the current in-progress thinking block.

        Returns:
            Current thinking content if in a block, None otherwise
        """
        if self._current_phase is None:
            return None
        return self._buffer[self._phase_start_pos :]

    def is_thinking(self) -> bool:
        """Check if currently inside a thinking block."""
        return self._current_phase is not None

    def reset(self) -> None:
        """Reset the detector state."""
        self._buffer = ""
        self._current_phase = None
        self._phase_start_pos = 0
