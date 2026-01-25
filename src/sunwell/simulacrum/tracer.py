"""Turn-by-turn evolution tracer for Simulacrum analysis.

Provides visibility into how the Simulacrum learns and evolves across turns:
- What facts/behaviors were extracted per turn
- How identity confidence evolves
- Memory state snapshots
- Debugging hooks for refinement

Thread Safety:
    Uses threading.Lock for thread-safe tracing in free-threaded Python (3.14t).
    All mutations to TRACER state are protected by locks.

Usage:
    from sunwell.simulacrum.tracer import TurnTracer, TRACER

    # In chat loop
    TRACER.begin_turn(turn_id, user_message)
    TRACER.log_extraction("fact", "User has cats named Milo and Kiki", 0.85)
    TRACER.log_extraction("behavior", "Uses casual language", 0.8)
    TRACER.log_identity_update(old_confidence=0.5, new_confidence=0.7)
    TRACER.end_turn(assistant_response)

    # Get evolution report
    report = TRACER.get_evolution_report()
"""


import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class ExtractionEvent:
    """A single extraction event (fact or behavior)."""

    timestamp: datetime
    extraction_type: str  # "fact", "behavior", "learning"
    content: str
    category: str | None = None  # "names", "preferences", "context", etc.
    confidence: float = 0.0
    filtered_as_echo: bool = False  # True if this was filtered out

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.extraction_type,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "filtered": self.filtered_as_echo,
        }


@dataclass(slots=True)
class IdentitySnapshot:
    """Snapshot of identity state at a point in time."""

    timestamp: datetime
    observation_count: int
    confidence: float
    prompt_preview: str | None  # First 100 chars of identity prompt
    tone: str | None
    values: list[str]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "observations": self.observation_count,
            "confidence": self.confidence,
            "prompt_preview": self.prompt_preview,
            "tone": self.tone,
            "values": self.values,
        }


@dataclass(slots=True)
class TurnTrace:
    """Trace of a single conversation turn."""

    turn_id: str
    turn_number: int
    timestamp: datetime
    user_message_preview: str  # First 100 chars

    # Extractions
    extractions: list[ExtractionEvent] = field(default_factory=list)
    filtered_extractions: list[ExtractionEvent] = field(default_factory=list)

    # Identity evolution
    identity_before: IdentitySnapshot | None = None
    identity_after: IdentitySnapshot | None = None
    identity_digested: bool = False

    # Assistant response (for context)
    assistant_response_preview: str | None = None

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp.isoformat(),
            "user_message": self.user_message_preview,
            "extractions": [e.to_dict() for e in self.extractions],
            "filtered": [e.to_dict() for e in self.filtered_extractions],
            "identity_before": self.identity_before.to_dict() if self.identity_before else None,
            "identity_after": self.identity_after.to_dict() if self.identity_after else None,
            "digested": self.identity_digested,
            "assistant_response": self.assistant_response_preview,
        }


class TurnTracer:
    """Traces turn-by-turn evolution of Simulacrum state.

    Provides debugging visibility and analysis for:
    - What's being extracted per turn
    - What's being filtered out (echo detection)
    - How identity confidence evolves
    - Memory state changes

    Thread Safety:
        All state mutations are protected by _lock for free-threading safety.
    """

    def __init__(self, enabled: bool = True, persist_path: Path | None = None):
        """Initialize tracer.

        Args:
            enabled: Whether tracing is active
            persist_path: Optional path to persist traces (for later analysis)
        """
        self.enabled = enabled
        self.persist_path = persist_path
        self.traces: list[TurnTrace] = []
        self._current_trace: TurnTrace | None = None
        self._turn_counter = 0
        self._lock = threading.Lock()

    def begin_turn(self, turn_id: str, user_message: str) -> None:
        """Begin tracing a new turn."""
        if not self.enabled:
            return

        with self._lock:
            self._turn_counter += 1
            self._current_trace = TurnTrace(
                turn_id=turn_id,
                turn_number=self._turn_counter,
                timestamp=datetime.now(),
                user_message_preview=user_message[:100] + "..." if len(user_message) > 100 else user_message,
            )

    def log_extraction(
        self,
        extraction_type: str,
        content: str,
        confidence: float = 0.0,
        category: str | None = None,
        filtered: bool = False,
    ) -> None:
        """Log an extraction event."""
        if not self.enabled:
            return

        with self._lock:
            if not self._current_trace:
                return

            event = ExtractionEvent(
                timestamp=datetime.now(),
                extraction_type=extraction_type,
                content=content,
                category=category,
                confidence=confidence,
                filtered_as_echo=filtered,
            )

            if filtered:
                self._current_trace.filtered_extractions.append(event)
            else:
                self._current_trace.extractions.append(event)

    def log_identity_snapshot(
        self,
        when: str,  # "before" or "after"
        observation_count: int,
        confidence: float,
        prompt: str | None = None,
        tone: str | None = None,
        values: list[str] | None = None,
    ) -> None:
        """Log identity state snapshot."""
        if not self.enabled:
            return

        with self._lock:
            if not self._current_trace:
                return

            snapshot = IdentitySnapshot(
                timestamp=datetime.now(),
                observation_count=observation_count,
                confidence=confidence,
                prompt_preview=prompt[:100] + "..." if prompt and len(prompt) > 100 else prompt,
                tone=tone,
                values=values or [],
            )

            if when == "before":
                self._current_trace.identity_before = snapshot
            else:
                self._current_trace.identity_after = snapshot

    def log_digest(self) -> None:
        """Mark that identity was digested this turn."""
        if not self.enabled:
            return
        with self._lock:
            if self._current_trace:
                self._current_trace.identity_digested = True

    def end_turn(self, assistant_response: str | None = None) -> TurnTrace | None:
        """End the current turn trace."""
        if not self.enabled:
            return None

        with self._lock:
            if not self._current_trace:
                return None

            if assistant_response:
                self._current_trace.assistant_response_preview = (
                    assistant_response[:100] + "..."
                    if len(assistant_response) > 100
                    else assistant_response
                )

            self.traces.append(self._current_trace)
            trace = self._current_trace
            self._current_trace = None

        # Persist outside lock (I/O operation)
        if self.persist_path and trace:
            self._persist_trace(trace)

        return trace

    def _persist_trace(self, trace: TurnTrace) -> None:
        """Persist a trace to disk."""
        if not self.persist_path:
            return

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file
        with open(self.persist_path, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

    def get_evolution_report(self) -> str:
        """Generate a human-readable evolution report."""
        # Snapshot traces under lock for thread-safe reading
        with self._lock:
            traces_snapshot = list(self.traces)

        if not traces_snapshot:
            return "No turns traced yet."

        lines = [
            "═══════════════════════════════════════════════════",
            "           SIMULACRUM EVOLUTION REPORT             ",
            "═══════════════════════════════════════════════════",
            f"Total turns: {len(self.traces)}",
            "",
        ]

        # Summary stats (using snapshot)
        total_extractions = sum(len(t.extractions) for t in traces_snapshot)
        total_filtered = sum(len(t.filtered_extractions) for t in traces_snapshot)
        digest_count = sum(1 for t in traces_snapshot if t.identity_digested)

        lines.extend([
            f"Extractions: {total_extractions} accepted, {total_filtered} filtered",
            f"Identity digests: {digest_count}",
            "",
            "───────────────────────────────────────────────────",
            "                  TURN-BY-TURN                     ",
            "───────────────────────────────────────────────────",
        ])

        for trace in traces_snapshot:
            lines.append(f"\n╭─ Turn {trace.turn_number} [{trace.turn_id[:8]}...]")
            lines.append(f"│  User: {trace.user_message_preview}")

            if trace.extractions:
                lines.append("│  📝 Extracted:")
                for e in trace.extractions:
                    cat_label = f" [{e.category}]" if e.category else ""
                    lines.append(f"│     • {e.extraction_type}{cat_label}: {e.content} ({e.confidence:.0%})")

            if trace.filtered_extractions:
                lines.append("│  🚫 Filtered (echoes):")
                for e in trace.filtered_extractions:
                    lines.append(f"│     • {e.content}")

            if trace.identity_before and trace.identity_after:
                before = trace.identity_before
                after = trace.identity_after
                delta = after.confidence - before.confidence
                delta_str = f"+{delta:.0%}" if delta > 0 else f"{delta:.0%}"
                lines.append(f"│  🧠 Identity: {before.confidence:.0%} → {after.confidence:.0%} ({delta_str})")
                lines.append(f"│     Observations: {before.observation_count} → {after.observation_count}")

            if trace.identity_digested:
                lines.append("│  ⚡ Identity digested this turn")

            lines.append("╰───")

        # Confidence evolution (using snapshot)
        confidence_history = []
        for t in traces_snapshot:
            if t.identity_after:
                confidence_history.append((t.turn_number, t.identity_after.confidence))

        if confidence_history:
            lines.extend([
                "",
                "───────────────────────────────────────────────────",
                "             CONFIDENCE EVOLUTION                  ",
                "───────────────────────────────────────────────────",
            ])

            # Simple ASCII sparkline
            if len(confidence_history) >= 2:
                max_conf = max(c for _, c in confidence_history)
                min(c for _, c in confidence_history)

                for turn, conf in confidence_history:
                    bar_len = int((conf / max(max_conf, 0.01)) * 30)
                    bar = "█" * bar_len + "░" * (30 - bar_len)
                    lines.append(f"Turn {turn:2d}: {bar} {conf:.0%}")

        lines.append("")
        lines.append("═══════════════════════════════════════════════════")

        return "\n".join(lines)

    def get_json_export(self) -> list[dict]:
        """Export all traces as JSON-serializable dicts."""
        with self._lock:
            return [t.to_dict() for t in self.traces]

    def clear(self) -> None:
        """Clear all traces."""
        with self._lock:
            self.traces.clear()
            self._current_trace = None
            self._turn_counter = 0


# Global tracer instance (enabled by default, can be configured)
TRACER = TurnTracer(enabled=True)


def enable_tracing(persist_path: Path | None = None) -> None:
    """Enable turn tracing with optional persistence."""
    global TRACER
    with TRACER._lock:
        TRACER.enabled = True
        TRACER.persist_path = persist_path


def disable_tracing() -> None:
    """Disable turn tracing."""
    global TRACER
    with TRACER._lock:
        TRACER.enabled = False
