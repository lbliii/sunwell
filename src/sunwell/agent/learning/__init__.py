"""Learning extraction for intra-session and cross-session memory (RFC-042).

The adaptive agent extracts learnings from:
1. Generated code (patterns, types, conventions)
2. Fix attempts (what worked, what didn't)
3. Gate validations (successful approaches)

Learnings are stored in Simulacrum for:
- Intra-session: Propagate patterns to subsequent tasks
- Cross-session: Remember across days/weeks/months

NOTE: Two Learning Classes:
- `sunwell.agent.learning.Learning`: Simple in-memory dataclass for extraction.
  Used during agent execution for collecting facts. Lightweight, no persistence.
- `sunwell.simulacrum.core.turn.Learning`: Full-featured dataclass with
  template_data field for persistence to simulacrum memory. Use this when
  storing learnings long-term or when you need template-based reasoning.

The LearningExtractor in this module creates agent.Learning instances, which
can be converted to simulacrum.Learning when saving to memory.
"""

from sunwell.agent.learning.dead_end import DeadEnd
from sunwell.agent.learning.execution import learn_from_execution
from sunwell.agent.learning.extractor import LearningExtractor
from sunwell.agent.learning.learning import Learning
from sunwell.agent.learning.patterns import ToolPattern, classify_task_type
from sunwell.agent.learning.store import LearningStore

__all__ = [
    "Learning",
    "DeadEnd",
    "ToolPattern",
    "classify_task_type",
    "LearningExtractor",
    "LearningStore",
    "learn_from_execution",
]
