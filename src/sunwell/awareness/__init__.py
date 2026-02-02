"""Awareness - Behavioral self-observation from session data.

Extracts patterns about agent behavior (not project facts) from session
history, persists them, and injects self-correction hints into prompts.

The third leg of the Memory/Learning/Awareness framework:
- Memory: What I know (facts about the project)
- Learning: How I acquire knowledge (extraction from sessions)
- Awareness: How I behave (self-observations for correction)
"""

from sunwell.awareness.extractor import AwarenessExtractor
from sunwell.awareness.hooks import (
    extract_awareness_end_of_session,
    get_awareness_prompt_section,
)
from sunwell.awareness.patterns import AwarenessPattern, PatternType, format_patterns_for_prompt
from sunwell.awareness.store import AwarenessStore, load_awareness_for_session

__all__ = [
    "AwarenessExtractor",
    "AwarenessPattern",
    "AwarenessStore",
    "PatternType",
    "extract_awareness_end_of_session",
    "format_patterns_for_prompt",
    "get_awareness_prompt_section",
    "load_awareness_for_session",
]
