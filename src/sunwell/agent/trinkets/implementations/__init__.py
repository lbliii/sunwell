"""Trinket implementations.

Core trinkets for prompt composition:
- TimeTrinket: Current timestamp (priority 0, notification)
- BriefingTrinket: Session orientation (priority 10, system)
- LearningTrinket: Relevant learnings (priority 30, system)
- AwarenessTrinket: Behavioral self-observations (priority 35, system)
- ToolGuidanceTrinket: Tool hints and usage (priority 50, system)
- MemoryTrinket: Historical context (priority 70, context)
"""

from sunwell.agent.trinkets.implementations.awareness import AwarenessTrinket
from sunwell.agent.trinkets.implementations.briefing import BriefingTrinket
from sunwell.agent.trinkets.implementations.learning import LearningTrinket
from sunwell.agent.trinkets.implementations.memory import MemoryTrinket
from sunwell.agent.trinkets.implementations.time import TimeTrinket
from sunwell.agent.trinkets.implementations.tool_guidance import ToolGuidanceTrinket

__all__ = [
    "AwarenessTrinket",
    "BriefingTrinket",
    "LearningTrinket",
    "MemoryTrinket",
    "TimeTrinket",
    "ToolGuidanceTrinket",
]
