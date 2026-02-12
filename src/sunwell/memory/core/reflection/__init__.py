"""Reflection system for Phase 3: Higher-order insights.

Synthesizes reflections and mental models from learnings to provide:
- Constraint causality: WHY patterns exist
- Mental models: Coherent topic understanding
- Token efficiency: Single context vs multiple learnings

Part of Hindsight-inspired memory enhancements.
"""

from sunwell.memory.core.reflection.causality import CausalityAnalyzer
from sunwell.memory.core.reflection.patterns import PatternDetector
from sunwell.memory.core.reflection.reflector import Reflector
from sunwell.memory.core.reflection.types import (
    MentalModel,
    PatternCluster,
    Reflection,
)

__all__ = [
    # Types
    "Reflection",
    "MentalModel",
    "PatternCluster",
    # Core components
    "Reflector",
    "PatternDetector",
    "CausalityAnalyzer",
]
