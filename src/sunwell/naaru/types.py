"""Type definitions for Naaru Architecture (RFC-016, RFC-019).

The Naaru is Sunwell's coordinated intelligence architecture.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class SessionStatus(Enum):
    """Status of an autonomous session."""
    
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(Enum):
    """Risk level for proposals."""
    
    TRIVIAL = "trivial"    # Comments, docs, formatting
    LOW = "low"            # Additive changes, new patterns
    MEDIUM = "medium"      # Behavioral changes
    HIGH = "high"          # Structural changes, API changes
    CRITICAL = "critical"  # Core module changes
    
    def can_auto_apply(self) -> bool:
        """Check if this risk level allows auto-apply."""
        return self in [RiskLevel.TRIVIAL, RiskLevel.LOW]


class OpportunityCategory(Enum):
    """Categories of improvement opportunities."""
    
    ERROR_HANDLING = "error_handling"
    TESTING = "testing"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    OTHER = "other"


@dataclass
class Opportunity:
    """An identified improvement opportunity.
    
    Represents something Sunwell could improve about itself.
    """
    
    id: str
    category: OpportunityCategory
    description: str
    target_module: str
    priority: float  # 0.0 - 1.0, higher is more important
    estimated_effort: str  # trivial, small, medium, large
    risk_level: RiskLevel
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "target_module": self.target_module,
            "priority": self.priority,
            "estimated_effort": self.estimated_effort,
            "risk_level": self.risk_level.value,
            "details": self.details,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Opportunity:
        """Create from dict."""
        return cls(
            id=data["id"],
            category=OpportunityCategory(data["category"]),
            description=data["description"],
            target_module=data["target_module"],
            priority=data["priority"],
            estimated_effort=data["estimated_effort"],
            risk_level=RiskLevel(data["risk_level"]),
            details=data.get("details", {}),
        )


@dataclass
class SessionConfig:
    """Configuration for an autonomous session.
    
    Controls how long the session runs, what it can do automatically,
    and various safety limits.
    """
    
    goals: list[str]
    max_hours: float = 8.0
    max_proposals: int = 50
    max_auto_apply: int = 10
    auto_apply_enabled: bool = True
    checkpoint_interval_minutes: int = 15
    min_seconds_between_changes: int = 30
    max_consecutive_failures: int = 3
    verbose: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "goals": self.goals,
            "max_hours": self.max_hours,
            "max_proposals": self.max_proposals,
            "max_auto_apply": self.max_auto_apply,
            "auto_apply_enabled": self.auto_apply_enabled,
            "checkpoint_interval_minutes": self.checkpoint_interval_minutes,
            "min_seconds_between_changes": self.min_seconds_between_changes,
            "max_consecutive_failures": self.max_consecutive_failures,
            "verbose": self.verbose,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionConfig:
        """Create from dict."""
        return cls(**data)


@dataclass
class CompletedTask:
    """Record of a completed task."""
    
    opportunity_id: str
    proposal_id: str | None
    result: str  # auto_applied, queued, rejected, failed
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "opportunity_id": self.opportunity_id,
            "proposal_id": self.proposal_id,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class SessionState:
    """Persistent state for an autonomous session.
    
    This is saved to disk at checkpoints and can be used
    to resume a paused session.
    """
    
    session_id: str
    config: SessionConfig
    status: SessionStatus = SessionStatus.INITIALIZING
    started_at: datetime = field(default_factory=datetime.now)
    checkpoint_at: datetime | None = None
    stopped_at: datetime | None = None
    stop_reason: str | None = None
    
    # Progress tracking
    opportunities: list[Opportunity] = field(default_factory=list)
    completed: list[CompletedTask] = field(default_factory=list)
    current_task: Opportunity | None = None
    
    # Counters
    proposals_created: int = 0
    proposals_auto_applied: int = 0
    proposals_queued: int = 0
    proposals_rejected: int = 0
    consecutive_failures: int = 0
    
    # Timing
    total_runtime_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "checkpoint_at": self.checkpoint_at.isoformat() if self.checkpoint_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "stop_reason": self.stop_reason,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "completed": [c.to_dict() for c in self.completed],
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "proposals_created": self.proposals_created,
            "proposals_auto_applied": self.proposals_auto_applied,
            "proposals_queued": self.proposals_queued,
            "proposals_rejected": self.proposals_rejected,
            "consecutive_failures": self.consecutive_failures,
            "total_runtime_seconds": self.total_runtime_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create from dict."""
        state = cls(
            session_id=data["session_id"],
            config=SessionConfig.from_dict(data["config"]),
            status=SessionStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
        )
        
        if data.get("checkpoint_at"):
            state.checkpoint_at = datetime.fromisoformat(data["checkpoint_at"])
        if data.get("stopped_at"):
            state.stopped_at = datetime.fromisoformat(data["stopped_at"])
        
        state.stop_reason = data.get("stop_reason")
        state.opportunities = [Opportunity.from_dict(o) for o in data.get("opportunities", [])]
        state.current_task = (
            Opportunity.from_dict(data["current_task"])
            if data.get("current_task") else None
        )
        
        state.proposals_created = data.get("proposals_created", 0)
        state.proposals_auto_applied = data.get("proposals_auto_applied", 0)
        state.proposals_queued = data.get("proposals_queued", 0)
        state.proposals_rejected = data.get("proposals_rejected", 0)
        state.consecutive_failures = data.get("consecutive_failures", 0)
        state.total_runtime_seconds = data.get("total_runtime_seconds", 0.0)
        
        return state
    
    def save(self, path: Path) -> None:
        """Save state to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> SessionState:
        """Load state from file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))
    
    def get_progress_summary(self) -> dict[str, Any]:
        """Get a summary of current progress."""
        total_opportunities = len(self.opportunities) + len(self.completed)
        completed_count = len(self.completed)
        
        return {
            "opportunities_total": total_opportunities,
            "opportunities_completed": completed_count,
            "opportunities_remaining": len(self.opportunities),
            "proposals_created": self.proposals_created,
            "proposals_auto_applied": self.proposals_auto_applied,
            "proposals_queued": self.proposals_queued,
            "proposals_rejected": self.proposals_rejected,
            "success_rate": (
                completed_count / total_opportunities
                if total_opportunities > 0 else 0
            ),
        }
