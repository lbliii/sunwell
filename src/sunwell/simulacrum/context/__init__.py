"""Context assembly and focus management.

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.simulacrum.context.assembler import ContextAssembler
from sunwell.simulacrum.context.focus import Focus, FocusFilter, detect_focus_shift
from sunwell.simulacrum.context.unified import UnifiedContextAssembler, UnifiedContext

__all__ = [
    "ContextAssembler",
    "Focus",
    "FocusFilter",
    "detect_focus_shift",
    "UnifiedContextAssembler",
    "UnifiedContext",
]
