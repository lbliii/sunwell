"""Compact Turn Format (CTF) - Token-efficient storage for conversation turns.

CTF is a header-based, tab-separated format designed to reduce token usage
by 30-50% compared to JSON by eliminating repeated keys and structural overhead.

RFC-013: Hierarchical Memory with Progressive Compression

Turn Encoding Example:
#CTF v1 turns=2 fields=role,content,timestamp,model
user	hello	2026-01-15T10:00:00	-
assistant	hi there	2026-01-15T10:00:01	gpt-4o

Chunk Summary Encoding Example:
#CTF v1 type=summaries count=2 fields=chunk_id,turn_range,summary,themes
micro_abc123	0-10	User introduced themselves	identity|capabilities
micro_def456	10-20	Tested file limitations	tools|limitations
"""


import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.simulacrum.core.turn import Turn

# Constants
FIELD_SEP = "\t"
RECORD_SEP = "\n"
NULL_VALUE = "-"
CTF_VERSION = "1"

# Maximum content length before truncation
MAX_CONTENT_LENGTH = 2000


class CTFEncoder:
    """Encodes conversation turns into Compact Turn Format."""

    @staticmethod
    def encode_turns(turns: tuple[Turn, ...]) -> str:
        """Convert a sequence of turns into a CTF string.

        Achieves ~40% token reduction for typical conversation data.

        Args:
            turns: Sequence of Turn objects

        Returns:
            CTF-encoded string
        """
        if not turns:
            return ""

        fields = ["role", "content", "timestamp", "model"]

        # 1. Generate Header
        header = f"#CTF v{CTF_VERSION} turns={len(turns)} fields={','.join(fields)}"
        lines = [header]

        # 2. Generate Data Rows
        for turn in turns:
            # Escape content to protect separators
            content = CTFEncoder._escape_content(turn.content)

            row = FIELD_SEP.join([
                turn.turn_type.value,
                content,
                turn.timestamp,
                turn.model or NULL_VALUE,
            ])
            lines.append(row)

        return RECORD_SEP.join(lines)

    @staticmethod
    def _escape_content(content: str, max_len: int = MAX_CONTENT_LENGTH) -> str:
        """Escape and optionally truncate content for CTF storage.

        Args:
            content: Raw content string
            max_len: Maximum length before truncation

        Returns:
            Escaped content string
        """
        # Truncate long content
        if len(content) > max_len:
            content = content[:max_len] + "…[truncated]"

        # Replace field/record separators with Unicode control pictures
        return content.replace("\t", "␉").replace("\n", "␊")


class CTFDecoder:
    """Decodes conversation turns from Compact Turn Format."""

    @staticmethod
    def decode_turns(ctf_content: str) -> list[Turn]:
        """Parse a CTF string back into Turn objects.

        Args:
            ctf_content: CTF-encoded string

        Returns:
            List of Turn objects
        """
        from sunwell.simulacrum.core.turn import Turn, TurnType

        if not ctf_content or not ctf_content.startswith("#CTF"):
            raise ValueError("Invalid CTF format: missing header")

        lines = ctf_content.strip().split(RECORD_SEP)
        if len(lines) < 2:
            return []

        # Parse Header for field mapping
        header = lines[0]
        fields_part = [p for p in header.split() if p.startswith("fields=")]
        if not fields_part:
            raise ValueError("Invalid CTF header: missing fields definition")
        fields = fields_part[0].split("=")[1].split(",")

        turns = []
        for line in lines[1:]:
            if not line.strip():
                continue

            values = line.split(FIELD_SEP)
            if len(values) < len(fields):
                continue  # Skip malformed rows

            # Map fields to values
            data = dict(zip(fields, values, strict=False))

            # Unescape content
            content = CTFDecoder._unescape_content(data.get("content", ""))

            turns.append(Turn(
                content=content,
                turn_type=TurnType(data.get("role", "user")),
                timestamp=data.get("timestamp", ""),
                model=data.get("model") if data.get("model") != NULL_VALUE else None,
            ))

        return turns

    @staticmethod
    def _unescape_content(content: str) -> str:
        """Restore escaped characters."""
        return content.replace("␉", "\t").replace("␊", "\n")


def encode_chunk_summaries(summaries: list[dict]) -> str:
    """Encode chunk summaries to CTF format.

    Args:
        summaries: List of dicts with keys: chunk_id, turn_range, summary, themes

    Returns:
        CTF-encoded string
    """
    if not summaries:
        return ""

    fields = ["chunk_id", "turn_range", "summary", "themes"]
    header = f"#CTF v{CTF_VERSION} type=summaries count={len(summaries)} fields={','.join(fields)}"

    lines = [header]
    for s in summaries:
        # Format turn_range as "start-end" string
        turn_range = s.get("turn_range", "")
        if isinstance(turn_range, (list, tuple)) and len(turn_range) == 2:
            turn_range = f"{turn_range[0]}-{turn_range[1]}"

        row = FIELD_SEP.join([
            s.get("chunk_id", ""),
            str(turn_range),
            CTFEncoder._escape_content(s.get("summary", ""), max_len=500),
            "|".join(s.get("themes", [])),
        ])
        lines.append(row)

    return RECORD_SEP.join(lines)


def decode_chunk_summaries(ctf_content: str) -> list[dict]:
    """Decode chunk summaries from CTF format.

    Args:
        ctf_content: CTF-encoded string

    Returns:
        List of dicts with keys: chunk_id, turn_range, summary, themes
    """
    if not ctf_content or not ctf_content.startswith("#CTF"):
        return []

    lines = ctf_content.strip().split(RECORD_SEP)
    summaries = []

    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split(FIELD_SEP)
        if len(values) >= 4:
            # Parse turn_range back to tuple
            turn_range_str = values[1]
            turn_range: tuple[int, int] | str = turn_range_str
            if "-" in turn_range_str:
                parts = turn_range_str.split("-")
                with contextlib.suppress(ValueError):
                    turn_range = (int(parts[0]), int(parts[1]))

            summaries.append({
                "chunk_id": values[0],
                "turn_range": turn_range,
                "summary": CTFDecoder._unescape_content(values[2]),
                "themes": [t for t in values[3].split("|") if t],
            })

    return summaries
