"""Trinket composition system for modular prompt construction.

Trinkets are self-contained components that contribute sections to the
system prompt. They provide:

- **Modularity**: Each trinket owns its domain (time, learnings, briefing, etc.)
- **Priority ordering**: Explicit control over section order via priority field
- **Graceful degradation**: One failing trinket doesn't crash composition
- **Native async**: Full async support for database lookups, embeddings, etc.
- **Caching**: Cacheable sections stored and reused across turns

Inspired by MIRA's trinket pattern but with explicit priority ordering,
native async support, and no EventBus complexity.

## Architecture

```
TrinketComposer
├── TimeTrinket (priority 0, notification)
├── BriefingTrinket (priority 10, system, cacheable)
├── LearningTrinket (priority 30, system)
├── AwarenessTrinket (priority 35, system, cacheable)
├── ToolGuidanceTrinket (priority 50, system)
└── MemoryTrinket (priority 70, context)
           │
           ▼
    ComposedPrompt
    ├── system: str
    ├── context: str
    └── notification: str
```

## Usage

```python
from sunwell.agent.trinkets import (
    TrinketComposer,
    TrinketContext,
    TimeTrinket,
    BriefingTrinket,
    LearningTrinket,
)

# Setup
composer = TrinketComposer()
composer.register(TimeTrinket())
composer.register(BriefingTrinket(briefing))
composer.register(LearningTrinket(learning_store))

# Compose
ctx = TrinketContext(task="Build API", workspace=Path("."))
composed = await composer.compose(ctx)

# Use
if composed.has_system:
    messages.append(Message(role="system", content=composed.system))
```
"""

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
    TurnResult,
)
from sunwell.agent.trinkets.composer import ComposedPrompt, TrinketComposer
from sunwell.agent.trinkets.implementations import (
    AwarenessTrinket,
    BriefingTrinket,
    LearningTrinket,
    MemoryTrinket,
    TimeTrinket,
    ToolGuidanceTrinket,
)

__all__ = [
    # Base types
    "BaseTrinket",
    "TrinketContext",
    "TrinketPlacement",
    "TrinketSection",
    "TurnResult",
    # Composer
    "ComposedPrompt",
    "TrinketComposer",
    # Implementations
    "AwarenessTrinket",
    "BriefingTrinket",
    "LearningTrinket",
    "MemoryTrinket",
    "TimeTrinket",
    "ToolGuidanceTrinket",
]
