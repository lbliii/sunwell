"""Naaru - Coordinated Intelligence for Local Models (RFC-016, RFC-019).

The Naaru is Sunwell's answer to maximizing quality and throughput from small
local models. Instead of a simple worker pool, it implements coordinated 
intelligence with specialized components that work in harmony.

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │  ← Coordinates everything
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared working memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │  ← Parallel helpers
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

Thematic Naming (from Naaru lore):
- **Voice**: The model that speaks/creates (synthesis model)
- **Wisdom**: The model that judges/evaluates (judge model)
- **Harmonic**: Multiple voices in alignment (multi-persona generation)
- **Convergence**: Shared purpose/working memory (7±2 slots)
- **Shards**: Fragments working in parallel (CPU helpers)
- **Resonance**: Feedback that amplifies quality (refinement loop)
- **Discernment**: Quick insight before deep judgment (tiered validation)
- **Attunement**: Intent-aware routing (cognitive routing)
- **Purity**: How pure the Light must be (quality threshold)
- **Luminance**: Confidence/quality score

Example:
    >>> from sunwell.naaru import Naaru, NaaruConfig
    >>> from sunwell.models.ollama import OllamaModel
    >>> 
    >>> naaru = Naaru(
    ...     sunwell_root=Path("."),
    ...     synthesis_model=OllamaModel("gemma3:1b"),
    ...     judge_model=OllamaModel("gemma3:4b"),
    ...     config=NaaruConfig(
    ...         harmonic_synthesis=True,
    ...         resonance=2,
    ...         convergence=7,
    ...     ),
    ... )
    >>> 
    >>> results = await naaru.illuminate(
    ...     goals=["improve error handling"],
    ...     max_time_seconds=120,
    ... )

Lore:
    In World of Warcraft, the Naaru are beings of pure Light that coordinate
    and guide. The Sunwell was restored by a Naaru (M'uru). The metaphor fits:
    - Naaru = The coordinator
    - Convergence = Shared purpose/working memory
    - Shards = Fragments working in parallel
    - Resonance = Feedback that amplifies quality
    - Harmonic = Multiple voices in alignment
    - Illuminate = The Naaru's light reveals the best path
"""

# Core types
from sunwell.naaru.types import (
    SessionStatus,
    RiskLevel,
    Opportunity,
    OpportunityCategory,
    SessionConfig,
    SessionState,
)

# Core runners
from sunwell.naaru.loop import AutonomousRunner
from sunwell.naaru.discovery import OpportunityDiscoverer
from sunwell.naaru.signals import SignalHandler, StopReason
from sunwell.naaru.parallel import ParallelAutonomousRunner, WorkerStats

# The Coordinator
from sunwell.naaru.naaru import (
    Naaru,
    NaaruRegion,
    NaaruMessage,
    MessageBus,
    MessageType,
    HarmonicSynthesisWorker,
    ValidationWorker,
    AnalysisWorker,
    MemoryWorker,
    ExecutiveWorker,
)
# NaaruConfig moved to sunwell.types.config
from sunwell.types.config import NaaruConfig

# Convergence - Shared Working Memory
from sunwell.naaru.convergence import (
    Convergence,
    Slot,
    SlotSource,
)

# Shards - Parallel Helpers
from sunwell.naaru.shards import (
    Shard,
    ShardPool,
    ShardType,
)

# Resonance - Feedback Loop
from sunwell.naaru.resonance import (
    Resonance,
    ResonanceConfig,
    ResonanceResult,
    RefinementAttempt,
    create_resonance_handler,
)

# Discernment - Tiered Validation
from sunwell.naaru.discernment import (
    Discernment,
    DiscernmentVerdict,
    DiscernmentResult,
)


__all__ = [
    # Core Types
    "SessionStatus",
    "RiskLevel",
    "Opportunity",
    "OpportunityCategory",
    "SessionConfig",
    "SessionState",
    
    # Core Runners
    "AutonomousRunner",
    "OpportunityDiscoverer",
    "ParallelAutonomousRunner",
    "WorkerStats",
    "SignalHandler",
    "StopReason",
    
    # Naaru Coordinator
    "Naaru",
    "NaaruConfig",
    "NaaruRegion",
    "NaaruMessage",
    "MessageBus",
    "MessageType",
    
    # Naaru Workers
    "HarmonicSynthesisWorker",
    "ValidationWorker",
    "AnalysisWorker",
    "MemoryWorker",
    "ExecutiveWorker",
    
    # Convergence (Working Memory)
    "Convergence",
    "Slot",
    "SlotSource",
    
    # Shards (Parallel Helpers)
    "Shard",
    "ShardPool",
    "ShardType",
    
    # Resonance (Feedback Loop)
    "Resonance",
    "ResonanceConfig",
    "ResonanceResult",
    "RefinementAttempt",
    "create_resonance_handler",
    
    # Discernment (Tiered Validation)
    "Discernment",
    "DiscernmentVerdict",
    "DiscernmentResult",
]
