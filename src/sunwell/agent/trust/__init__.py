"""Adaptive trust system for progressive autonomy.

Tracks user approval patterns and offers autonomy upgrades when
users consistently approve certain operation types.

Usage:
    from sunwell.agent.trust import ApprovalTracker, AutoApproveConfig
    
    tracker = ApprovalTracker(workspace)
    tracker.record_decision(path, approved=True)
    
    if tracker.should_suggest_upgrade(path):
        # Offer to auto-approve this path type
        ...
"""

from sunwell.agent.trust.approval_tracker import (
    ApprovalPattern,
    ApprovalTracker,
)
from sunwell.agent.trust.auto_approve import (
    AutoApproveConfig,
    AutoApproveRule,
)

__all__ = [
    "ApprovalPattern",
    "ApprovalTracker",
    "AutoApproveConfig",
    "AutoApproveRule",
]
