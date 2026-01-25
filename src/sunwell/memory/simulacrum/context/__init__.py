"""Context assembly and focus management.

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.memory.simulacrum.context.assembler import ContextAssembler
from sunwell.memory.simulacrum.context.focus import Focus, FocusFilter, detect_focus_shift
from sunwell.memory.simulacrum.context.unified import UnifiedContext, UnifiedContextAssembler

__all__ = [
    "ContextAssembler",
    "Focus",
    "FocusFilter",
    "detect_focus_shift",
    "UnifiedContextAssembler",
    "UnifiedContext",
]
