# RFC-071: Briefing System — Rolling Handoff Notes for Agent Continuity

**Status**: Draft → Evaluated (Ready for Planning)  
**Created**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 88% 🟢  
**Depends on**: RFC-065 (Unified Memory), RFC-013 (Simulacrum)  
**Complements**: RFC-045 (Project Intelligence), RFC-040 (Incremental Build), RFC-069 (Cascade)

---

## Summary

Introduce a **Briefing System** — a rolling, overwritten handoff note that provides instant orientation at session start. Unlike accumulated learnings (which grow over time), the briefing is **compressed each session**, acting as "Twitter for LLMs" where the character constraint enforces salience.

**The insight**: The lossy nature is the feature. Like a game of telephone, each session compresses what matters, naturally filtering signal from noise.

**Extended insight**: The briefing isn't just orientation — it's a **dispatch signal** that coordinates expensive operations. A tiny model reads the briefing and pre-loads code, skills, and DAG context before the main agent starts.

---

## Goals

1. **Instant orientation** — Agent knows "where we are" in <5 seconds, no retrieval needed
2. **Momentum preservation** — Capture direction, not just state (last action → next action)
3. **Hazard awareness** — Proactive warnings prevent repeating mistakes
4. **Compression as curation** — Overwriting forces prioritization; stale details fade naturally
5. **Pointer-based depth** — Link to deep memory without loading it
6. **Dispatch signaling** — Briefing informs prefetch of code, skills, and DAG context

## Non-Goals

1. **Replace learnings** — Briefing complements, doesn't replace, accumulated knowledge
2. **Full history** — DAG remains the source of truth for complete history
3. **Multi-project** — One briefing per project (cross-project is out of scope)
4. **Semantic search** — Briefing is read directly, not queried

---

## Motivation

### The Memory Trilemma

Current agent memory systems face three competing pressures:

| Pressure | Problem |
|---|---|
| **Completeness** | Full history bloats context, reduces relevance |
| **Recency** | Forgetting everything loses continuity |
| **Relevance** | Retrieval adds latency, may miss what matters |

The Briefing System solves this by creating a **third memory tier**:

```
┌─────────────────────────────────────────────────────────────┐
│  BRIEFING (~300 tokens, always loaded)                      │
│  "Twitter for LLMs" — constraint enforces salience          │
├─────────────────────────────────────────────────────────────┤
│  WORKING MEMORY (current session)                           │
│  Resets each session                                        │
├─────────────────────────────────────────────────────────────┤
│  LONG-TERM MEMORY (DAG + Learnings)                         │
│  Accumulates, requires retrieval                            │
└─────────────────────────────────────────────────────────────┘
```

### The Telephone Game Insight

When you pass a message through multiple people, irrelevant details fade while core meaning persists. This is usually seen as a bug — but for agent memory, it's a feature:

```
Session 1: "Implemented JWT auth in src/auth.py"
Session 2: "Added token refresh, auth is 80% done"
Session 3: "Auth complete, needs integration tests"
Session 4: "Tests done, ready to ship"
```

Each briefing compresses the previous state into what **actually matters for the next action**. Old details don't accumulate — they naturally fade unless they keep being relevant.

### Evidence: Current Pain Points

```python
# Current: Agent loads ALL learnings at start
# src/sunwell/adaptive/agent.py:313-318
learnings = learning_store.query(limit=50)  # May include stale, irrelevant facts

# Current: No "where are we?" summary
# Agent must infer state from learnings + DAG + last messages

# Proposed: Instant orientation
briefing = Briefing.load(project_path)  # ~300 tokens, always relevant
```

---

## Design

### Storage Structure

```
.sunwell/
├── memory/
│   ├── learnings.jsonl      # Long-term (accumulates) — RFC-065
│   ├── decisions.jsonl      # Long-term (accumulates) — RFC-065
│   ├── failures.jsonl       # Long-term (accumulates) — RFC-065
│   └── briefing.json        # Rolling (OVERWRITTEN)  ← NEW
```

Single file, always overwritten. No history accumulation in the briefing itself.

### Data Model (Python)

```python
# src/sunwell/memory/briefing.py

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.memory.types import Learning
    from sunwell.simulacrum.core.turn import Turn


class BriefingStatus(Enum):
    """Current state of the work."""
    
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class Briefing:
    """Rolling handoff note — overwritten each session.
    
    This is NOT accumulated history — it's a compressed "where are we now."
    Think: Twitter for LLMs. The constraint enforces salience.
    
    Design principles:
    1. ~300 tokens max — fits in any context window
    2. Overwritten, not appended — forces compression
    3. Pointers, not content — links to deep memory
    4. Actionable — orientation + momentum + hazards
    """
    
    # === ORIENTATION (5-second scan) ===
    mission: str
    """What we're trying to accomplish (1 sentence)."""
    
    status: BriefingStatus
    """Current state: not_started, in_progress, blocked, complete."""
    
    progress: str
    """Brief summary of where we are (1-2 sentences)."""
    
    # === MOMENTUM (direction, not just state) ===
    last_action: str
    """What was just done (1 sentence)."""
    
    next_action: str | None
    """What should happen next (1 sentence). None if complete."""
    
    # === HAZARDS (what NOT to do) ===
    hazards: tuple[str, ...] = field(default_factory=tuple)
    """Things to avoid — max 3, most critical only."""
    
    # === BLOCKERS (what's preventing progress) ===
    blockers: tuple[str, ...] = field(default_factory=tuple)
    """What's preventing progress. Empty if not blocked."""
    
    # === FOCUS (where to look) ===
    hot_files: tuple[str, ...] = field(default_factory=tuple)
    """Files currently relevant — max 5."""
    
    # === DEEP MEMORY POINTERS ===
    goal_hash: str | None = None
    """Links to DAG goal for full history."""
    
    related_learnings: tuple[str, ...] = field(default_factory=tuple)
    """Learning IDs to pull if more context needed — max 5."""
    
    # === DISPATCH HINTS (optional, for advanced routing) ===
    predicted_skills: tuple[str, ...] = field(default_factory=tuple)
    """Skills the agent predicted it would need next."""
    
    suggested_lens: str | None = None
    """Lens that best fits the current work."""
    
    complexity_estimate: str | None = None
    """Expected complexity: trivial, moderate, complex, requires_human."""
    
    estimated_files_touched: int | None = None
    """Rough estimate of files that will be modified."""
    
    # === METADATA ===
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""
    
    # === METHODS ===
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        data = {
            "mission": self.mission,
            "status": self.status.value,
            "progress": self.progress,
            "last_action": self.last_action,
            "next_action": self.next_action,
            "hazards": list(self.hazards),
            "blockers": list(self.blockers),
            "hot_files": list(self.hot_files),
            "goal_hash": self.goal_hash,
            "related_learnings": list(self.related_learnings),
            "updated_at": self.updated_at,
            "session_id": self.session_id,
        }
        # Optional dispatch hints (only include if set)
        if self.predicted_skills:
            data["predicted_skills"] = list(self.predicted_skills)
        if self.suggested_lens:
            data["suggested_lens"] = self.suggested_lens
        if self.complexity_estimate:
            data["complexity_estimate"] = self.complexity_estimate
        if self.estimated_files_touched is not None:
            data["estimated_files_touched"] = self.estimated_files_touched
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Briefing:
        """Deserialize from JSON."""
        return cls(
            mission=data["mission"],
            status=BriefingStatus(data["status"]),
            progress=data["progress"],
            last_action=data["last_action"],
            next_action=data.get("next_action"),
            hazards=tuple(data.get("hazards", [])),
            blockers=tuple(data.get("blockers", [])),
            hot_files=tuple(data.get("hot_files", [])),
            goal_hash=data.get("goal_hash"),
            related_learnings=tuple(data.get("related_learnings", [])),
            # Dispatch hints
            predicted_skills=tuple(data.get("predicted_skills", [])),
            suggested_lens=data.get("suggested_lens"),
            complexity_estimate=data.get("complexity_estimate"),
            estimated_files_touched=data.get("estimated_files_touched"),
            # Metadata
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            session_id=data.get("session_id", ""),
        )
    
    def to_prompt(self) -> str:
        """Format for injection into agent system prompt.
        
        This is what the agent sees at session start.
        Optimized for instant orientation (<5 seconds).
        """
        lines = [
            "## Current State (Briefing)",
            "",
            f"**Mission**: {self.mission}",
            f"**Status**: {self.status.value.replace('_', ' ').title()}",
            f"**Progress**: {self.progress}",
            "",
            f"**Last Action**: {self.last_action}",
        ]
        
        if self.next_action:
            lines.append(f"**Next Action**: {self.next_action}")
        
        if self.hazards:
            lines.append("")
            lines.append("**Hazards** (avoid these):")
            for h in self.hazards:
                lines.append(f"- ⚠️ {h}")
        
        if self.blockers:
            lines.append("")
            lines.append("**Blockers**:")
            for b in self.blockers:
                lines.append(f"- 🚫 {b}")
        
        if self.hot_files:
            lines.append("")
            lines.append(f"**Focus Files**: {', '.join(f'`{f}`' for f in self.hot_files)}")
        
        return "\n".join(lines)
    
    def save(self, project_path: Path) -> None:
        """Save briefing to project (OVERWRITES existing)."""
        briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"
        briefing_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(briefing_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, project_path: Path) -> Briefing | None:
        """Load briefing from project. Returns None if not found."""
        briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"
        
        if not briefing_path.exists():
            return None
        
        with open(briefing_path) as f:
            return cls.from_dict(json.load(f))
    
    @classmethod
    def create_initial(cls, mission: str, goal_hash: str | None = None) -> Briefing:
        """Create initial briefing for a new goal."""
        return cls(
            mission=mission,
            status=BriefingStatus.NOT_STARTED,
            progress="Starting fresh.",
            last_action="Goal received.",
            next_action="Begin planning.",
            goal_hash=goal_hash,
        )


# =============================================================================
# Execution Summary (for briefing generation)
# =============================================================================


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    """Summary of what happened during agent execution.
    
    Built from task graph completion and agent state.
    Used to generate the next briefing at session end.
    """
    
    last_action: str
    """What was accomplished this session (1 sentence)."""
    
    next_action: str | None
    """What should happen next (None if complete)."""
    
    modified_files: tuple[str, ...]
    """Files that were created or modified."""
    
    tasks_completed: int
    """Number of tasks completed."""
    
    gates_passed: int
    """Number of quality gates passed."""
    
    new_learnings: tuple[str, ...]
    """Learning IDs generated this session."""
    
    new_hazards: tuple[str, ...]
    """Hazards discovered this session."""
    
    resolved_hazards: tuple[str, ...]
    """Hazards that were addressed this session."""
    
    @classmethod
    def from_task_graph(cls, task_graph: Any, learnings: list[Any]) -> ExecutionSummary:
        """Build summary from completed task graph."""
        completed = task_graph.completed_ids if hasattr(task_graph, "completed_ids") else []
        gates = task_graph.gates if hasattr(task_graph, "gates") else []
        
        # Determine last action from completed tasks
        if completed:
            last_action = f"Completed {len(completed)} task(s): {', '.join(completed[:3])}"
            if len(completed) > 3:
                last_action += f" and {len(completed) - 3} more"
        else:
            last_action = "No tasks completed."
        
        # Determine next action from pending tasks
        pending = task_graph.pending_ids if hasattr(task_graph, "pending_ids") else []
        next_action = f"Continue with: {pending[0]}" if pending else None
        
        # Collect modified files from task outputs
        modified = []
        for task_id in completed:
            task = task_graph.get_task(task_id) if hasattr(task_graph, "get_task") else None
            if task and hasattr(task, "output_files"):
                modified.extend(task.output_files)
        
        return cls(
            last_action=last_action,
            next_action=next_action,
            modified_files=tuple(modified[:10]),  # Limit to 10
            tasks_completed=len(completed),
            gates_passed=len([g for g in gates if g.passed]),
            new_learnings=tuple(l.id for l in learnings[:5]),
            new_hazards=(),  # Populated by agent
            resolved_hazards=(),  # Populated by agent
        )


# =============================================================================
# Compression Function
# =============================================================================


def compress_briefing(
    old_briefing: Briefing | None,
    summary: ExecutionSummary,
    new_status: BriefingStatus,
    blockers: list[str] | None = None,
    predicted_skills: list[str] | None = None,
    suggested_lens: str | None = None,
    complexity_estimate: str | None = None,
) -> Briefing:
    """Create new briefing by compressing old state + session work.
    
    This is the "telephone game" compression function.
    Each call produces a fresh briefing that captures current state.
    
    Args:
        old_briefing: Previous briefing (or None for first session)
        summary: Execution summary from this session
        new_status: Current status after this session
        blockers: Current blockers (replaces old)
        predicted_skills: Skills predicted for next session
        suggested_lens: Lens suggested for next session
        complexity_estimate: Complexity estimate for remaining work
    
    Returns:
        New briefing that overwrites the old one
    """
    # Start with old briefing or defaults
    if old_briefing:
        mission = old_briefing.mission
        goal_hash = old_briefing.goal_hash
        session_id = old_briefing.session_id
        
        # Carry forward hazards, removing resolved ones
        old_hazards = set(old_briefing.hazards)
        if summary.resolved_hazards:
            old_hazards -= set(summary.resolved_hazards)
        hazards = list(old_hazards)
        
        # Carry forward learnings
        old_learning_ids = list(old_briefing.related_learnings)
    else:
        mission = "Unknown mission"
        goal_hash = None
        session_id = ""
        hazards = []
        old_learning_ids = []
    
    # Add new hazards (keep max 3 most recent)
    if summary.new_hazards:
        hazards = (list(summary.new_hazards) + hazards)[:3]
    
    # Update learning references (keep max 5 most recent)
    learning_ids = list(summary.new_learnings) + old_learning_ids
    learning_ids = learning_ids[:5]
    
    # Construct progress summary
    if new_status == BriefingStatus.COMPLETE:
        progress = f"Complete. {summary.last_action}"
    elif new_status == BriefingStatus.BLOCKED:
        progress = f"Blocked. {summary.last_action}"
    else:
        progress = summary.last_action
    
    return Briefing(
        mission=mission,
        status=new_status,
        progress=progress,
        last_action=summary.last_action,
        next_action=summary.next_action,
        hazards=tuple(hazards),
        blockers=tuple(blockers or []),
        hot_files=tuple(summary.modified_files[:5]),
        goal_hash=goal_hash,
        related_learnings=tuple(learning_ids),
        # Dispatch hints
        predicted_skills=tuple(predicted_skills or []),
        suggested_lens=suggested_lens,
        complexity_estimate=complexity_estimate,
        estimated_files_touched=len(summary.modified_files) if summary.modified_files else None,
        # Metadata
        session_id=session_id,
    )


# =============================================================================
# Prefetch Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class PrefetchPlan:
    """What to pre-load based on briefing signals."""
    
    files_to_read: tuple[str, ...]
    """Code files to pre-read into context."""
    
    learnings_to_load: tuple[str, ...]
    """Learning IDs to retrieve."""
    
    skills_needed: tuple[str, ...]
    """Skills/heuristics to activate."""
    
    dag_nodes_to_fetch: tuple[str, ...]
    """DAG node IDs to pre-traverse."""
    
    suggested_lens: str | None
    """Lens that best matches the work type."""


@dataclass(frozen=True, slots=True)
class PrefetchedContext:
    """Pre-loaded context ready for main agent.
    
    Result of executing a PrefetchPlan. Contains all the
    context that was pre-loaded before the main agent starts.
    """
    
    files: dict[str, str]
    """Map of file path → file content."""
    
    learnings: tuple[Any, ...]  # tuple[Learning, ...] at runtime
    """Pre-loaded learnings from memory store."""
    
    dag_context: tuple[Any, ...]  # tuple[Turn, ...] at runtime
    """Pre-fetched DAG nodes for conversation history."""
    
    active_skills: tuple[str, ...]
    """Skills that have been activated."""
    
    lens: str | None
    """Lens that was selected (or None for default)."""
```

### Data Model (Rust — Tauri Bridge)

```rust
// studio/src-tauri/src/briefing.rs

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use thiserror::Error;

/// Briefing-specific errors
#[derive(Debug, Error)]
pub enum BriefingError {
    #[error("Failed to read briefing: {0}")]
    ReadError(#[from] std::io::Error),
    
    #[error("Failed to parse briefing: {0}")]
    ParseError(#[from] serde_json::Error),
}

// Implement serialization for Tauri
impl serde::Serialize for BriefingError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

/// Briefing status — matches Python BriefingStatus
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BriefingStatus {
    NotStarted,
    InProgress,
    Blocked,
    Complete,
}

/// Rolling handoff note — read by Studio for project orientation
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Briefing {
    pub mission: String,
    pub status: BriefingStatus,
    pub progress: String,
    pub last_action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next_action: Option<String>,
    #[serde(default)]
    pub hazards: Vec<String>,
    #[serde(default)]
    pub blockers: Vec<String>,
    #[serde(default)]
    pub hot_files: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub goal_hash: Option<String>,
    #[serde(default)]
    pub related_learnings: Vec<String>,
    
    // Dispatch hints (optional)
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub predicted_skills: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggested_lens: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub complexity_estimate: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub estimated_files_touched: Option<i32>,
    
    // Metadata
    pub updated_at: String,
    #[serde(default)]
    pub session_id: String,
}

impl Default for Briefing {
    fn default() -> Self {
        Self {
            mission: String::new(),
            status: BriefingStatus::NotStarted,
            progress: String::new(),
            last_action: String::new(),
            next_action: None,
            hazards: Vec::new(),
            blockers: Vec::new(),
            hot_files: Vec::new(),
            goal_hash: None,
            related_learnings: Vec::new(),
            predicted_skills: Vec::new(),
            suggested_lens: None,
            complexity_estimate: None,
            estimated_files_touched: None,
            updated_at: String::new(),
            session_id: String::new(),
        }
    }
}

// =============================================================================
// Tauri Commands
// =============================================================================

/// Get briefing for a project
#[tauri::command]
pub async fn get_briefing(path: String) -> Result<Option<Briefing>, BriefingError> {
    let project_path = PathBuf::from(&path);
    let briefing_path = project_path.join(".sunwell/memory/briefing.json");
    
    if !briefing_path.exists() {
        return Ok(None);
    }
    
    let content = std::fs::read_to_string(&briefing_path)?;
    let briefing: Briefing = serde_json::from_str(&content)?;
    
    Ok(Some(briefing))
}

/// Check if project has a briefing
#[tauri::command]
pub async fn has_briefing(path: String) -> bool {
    let project_path = PathBuf::from(&path);
    project_path.join(".sunwell/memory/briefing.json").exists()
}
```

### Data Model (TypeScript — Svelte)

```typescript
// studio/src/lib/types.ts (additions)

export type BriefingStatus = 'not_started' | 'in_progress' | 'blocked' | 'complete';

export interface Briefing {
  mission: string;
  status: BriefingStatus;
  progress: string;
  lastAction: string;
  nextAction: string | null;
  hazards: string[];
  blockers: string[];
  hotFiles: string[];
  goalHash: string | null;
  relatedLearnings: string[];
  
  // Dispatch hints (optional)
  predictedSkills?: string[];
  suggestedLens?: string | null;
  complexityEstimate?: string | null;
  estimatedFilesTouched?: number | null;
  
  // Metadata
  updatedAt: string;
  sessionId: string;
}
```

### Svelte Store

```typescript
// studio/src/stores/briefing.svelte.ts

import type { Briefing } from '$lib/types';

let _briefing = $state<Briefing | null>(null);
let _isLoading = $state(false);
let _error = $state<string | null>(null);

export const briefing = {
  get current() { return _briefing; },
  get isLoading() { return _isLoading; },
  get error() { return _error; },
  // Computed
  get hasBriefing() { return _briefing !== null; },
  get isBlocked() { return _briefing?.status === 'blocked'; },
  get isComplete() { return _briefing?.status === 'complete'; },
  get hasHazards() { return (_briefing?.hazards.length ?? 0) > 0; },
  get hasDispatchHints() { 
    return (_briefing?.predictedSkills?.length ?? 0) > 0 || 
           _briefing?.suggestedLens != null; 
  },
};

export async function loadBriefing(projectPath: string): Promise<void> {
  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    _briefing = await invoke<Briefing | null>('get_briefing', { path: projectPath });
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    _briefing = null;
  } finally {
    _isLoading = false;
  }
}

export function clearBriefing(): void {
  _briefing = null;
}
```

---

## Integration with RFC-065 (Unified Memory)

The briefing system bridges with RFC-065's unified memory architecture:

### Briefing → Learning Extraction

When a briefing transitions to `COMPLETE`, we can generate a completion learning:

```python
# src/sunwell/memory/briefing.py (additional function)

from sunwell.memory.types import Learning, LearningCategory


def briefing_to_learning(briefing: Briefing) -> Learning | None:
    """Generate a learning from a completed briefing.
    
    When a mission completes, we extract a summary learning that
    persists in the unified memory store. This bridges the transient
    briefing with the accumulated learning system.
    
    Returns:
        Learning if briefing is complete, None otherwise
    """
    if briefing.status != BriefingStatus.COMPLETE:
        return None
    
    return Learning(
        id=f"briefing-{briefing.goal_hash or briefing.session_id}",
        fact=f"Completed: {briefing.mission}. {briefing.progress}",
        category=LearningCategory.TASK_COMPLETION,
        goal=briefing.goal_hash,
        source_type="briefing",
        confidence=1.0,  # Briefing completions are high confidence
        metadata={
            "hot_files": list(briefing.hot_files),
            "hazards_encountered": list(briefing.hazards),
        },
    )
```

### Learning → Briefing Priming

Related learnings can be pre-loaded based on briefing pointers:

```python
# Integration point in context assembly

def get_briefing_learnings(
    briefing: Briefing,
    memory_store: MemoryStore,
) -> list[Learning]:
    """Get learnings linked from briefing.
    
    Uses RFC-065's MemoryStore to retrieve learnings by ID.
    Falls back to semantic search if IDs not found.
    """
    if briefing.related_learnings:
        # Direct ID lookup (fast)
        return memory_store.get_by_ids(list(briefing.related_learnings))
    elif briefing.goal_hash:
        # Query by goal hash
        return memory_store.query(goal=briefing.goal_hash, limit=5)
    else:
        # Fall back to mission-based relevance
        return memory_store.query(briefing.mission, limit=5)
```

---

## Agent Integration

### Session Start (Load Briefing)

```python
# src/sunwell/adaptive/agent.py (modifications to _load_memory)

async def _load_memory(self) -> AsyncIterator[AgentEvent]:
    """Load Simulacrum session, learnings, AND briefing."""
    
    # Load briefing FIRST (instant orientation)
    briefing = Briefing.load(self.cwd)
    if briefing:
        yield AgentEvent(
            EventType.BRIEFING_LOADED,
            {
                "mission": briefing.mission,
                "status": briefing.status.value,
                "has_hazards": len(briefing.hazards) > 0,
                "has_dispatch_hints": bool(briefing.predicted_skills or briefing.suggested_lens),
            },
        )
        # Store for context assembly
        self._briefing = briefing
    
    # Then load disk-persisted learnings...
    disk_loaded = self._learning_store.load_from_disk(self.cwd)
    if disk_loaded > 0:
        yield AgentEvent(
            EventType.MEMORY_LEARNING,
            {"loaded": disk_loaded, "source": "disk"},
        )
    
    # ... rest of existing _load_memory code
```

### Context Assembly

```python
# src/sunwell/simulacrum/context/assembler.py (modifications)

class ContextAssembler:
    """Assembles context for LLM from multiple sources."""
    
    def assemble(
        self,
        query: str,
        briefing: Briefing | None = None,
    ) -> str:
        """Assemble context for LLM, with briefing as first priority.
        
        Context hierarchy:
        1. Briefing (always first if present) — instant orientation
        2. Relevant learnings (filtered by briefing if available)
        3. Recent conversation turns
        4. Semantic memory results
        """
        sections = []
        
        # 1. BRIEFING (always first if present)
        if briefing:
            sections.append(briefing.to_prompt())
            sections.append("")
        
        # 2. Relevant learnings (filtered by briefing pointers if available)
        if briefing and briefing.related_learnings:
            # Prioritize linked learnings
            learnings = self.memory_store.get_by_ids(list(briefing.related_learnings))
        else:
            # Fall back to relevance query
            learnings = self.memory_store.query(query, limit=10)
        
        if learnings:
            sections.append("## Relevant Learnings")
            for l in learnings:
                sections.append(f"- {l.fact}")
            sections.append("")
        
        # 3. Recent turns from DAG
        recent = self.dag.get_recent_turns(limit=5)
        if recent:
            sections.append("## Recent Context")
            for turn in recent:
                sections.append(f"- {turn.role}: {turn.content[:100]}...")
            sections.append("")
        
        return "\n".join(sections)
```

### Session End (Write Briefing)

```python
# src/sunwell/adaptive/agent.py (modifications to _save_memory)

async def _save_memory(self) -> AsyncIterator[AgentEvent]:
    """Save session state and write new briefing."""
    
    # Existing: save learnings to disk
    saved = self._learning_store.save_to_disk(self.cwd)
    if saved > 0:
        yield AgentEvent(
            EventType.MEMORY_SAVED,
            {"saved": saved},
        )
    
    # NEW: Generate execution summary and compress briefing
    if hasattr(self, "_task_graph") and self._task_graph:
        summary = ExecutionSummary.from_task_graph(
            self._task_graph,
            self._session_learnings,
        )
        
        # Determine new status
        new_status = self._determine_status()
        
        # Predict skills for next session (based on pending work)
        predicted_skills = predict_skills_from_briefing(self._briefing) if self._briefing else []
        
        # Compress and write new briefing
        new_briefing = compress_briefing(
            old_briefing=self._briefing,
            summary=summary,
            new_status=new_status,
            blockers=self._current_blockers,
            predicted_skills=predicted_skills,
            suggested_lens=suggest_lens_from_briefing(self._briefing) if self._briefing else None,
        )
        new_briefing.save(self.cwd)
        
        yield AgentEvent(
            EventType.BRIEFING_SAVED,
            {
                "status": new_briefing.status.value,
                "next_action": new_briefing.next_action,
                "tasks_completed": summary.tasks_completed,
            },
        )
        
        # If mission complete, generate completion learning
        if new_status == BriefingStatus.COMPLETE:
            completion_learning = briefing_to_learning(new_briefing)
            if completion_learning:
                self._learning_store.add(completion_learning)
                yield AgentEvent(
                    EventType.MEMORY_LEARNING,
                    {"fact": completion_learning.fact, "category": "task_completion"},
                )
    
    def _determine_status(self) -> BriefingStatus:
        """Determine briefing status from task graph state."""
        if not hasattr(self, "_task_graph") or not self._task_graph:
            return BriefingStatus.IN_PROGRESS
        
        if self._current_blockers:
            return BriefingStatus.BLOCKED
        
        pending = getattr(self._task_graph, "pending_ids", [])
        if not pending:
            return BriefingStatus.COMPLETE
        
        return BriefingStatus.IN_PROGRESS
```

### New Event Types

```python
# src/sunwell/adaptive/events.py (additions)

class EventType(Enum):
    # ... existing events ...
    
    # Briefing events (RFC-071)
    BRIEFING_LOADED = "briefing_loaded"
    """Briefing loaded at session start."""
    
    BRIEFING_SAVED = "briefing_saved"
    """Briefing saved at session end."""
    
    # Prefetch events (RFC-071)
    PREFETCH_START = "prefetch_start"
    """Starting briefing-driven prefetch."""
    
    PREFETCH_COMPLETE = "prefetch_complete"
    """Prefetch completed, context warm."""
    
    PREFETCH_TIMEOUT = "prefetch_timeout"
    """Prefetch timed out, proceeding without warm context."""
    
    LENS_SUGGESTED = "lens_suggested"
    """Lens suggested based on briefing analysis."""


# Event factory helpers

def briefing_loaded_event(
    mission: str,
    status: str,
    has_hazards: bool,
    has_dispatch_hints: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a briefing loaded event."""
    return AgentEvent(
        EventType.BRIEFING_LOADED,
        {
            "mission": mission,
            "status": status,
            "has_hazards": has_hazards,
            "has_dispatch_hints": has_dispatch_hints,
            **kwargs,
        },
    )


def prefetch_complete_event(
    files_loaded: int,
    learnings_loaded: int,
    skills_activated: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a prefetch complete event."""
    return AgentEvent(
        EventType.PREFETCH_COMPLETE,
        {
            "files_loaded": files_loaded,
            "learnings_loaded": learnings_loaded,
            "skills_activated": skills_activated,
            **kwargs,
        },
    )
```

---

## UI Integration (Studio)

### Project Card Enhancement

The discovered projects list can show briefing status:

```svelte
<!-- studio/src/components/ProjectCard.svelte -->

<script lang="ts">
  import type { ProjectStatus } from '$lib/types';
  import { briefing, loadBriefing } from '../stores/briefing.svelte';
  
  let { project }: { project: ProjectStatus } = $props();
  
  $effect(() => {
    if (project.path) {
      loadBriefing(project.path);
    }
  });
</script>

<div class="project-card">
  <h3>{project.name}</h3>
  
  {#if briefing.current}
    <div class="briefing-summary">
      <span class="status status-{briefing.current.status}">
        {briefing.current.status.replace('_', ' ')}
      </span>
      <p class="progress">{briefing.current.progress}</p>
      
      {#if briefing.current.nextAction}
        <p class="next-action">
          <strong>Next:</strong> {briefing.current.nextAction}
        </p>
      {/if}
      
      {#if briefing.hasHazards}
        <div class="hazards">
          <span class="hazard-icon">⚠️</span>
          <span>{briefing.current.hazards.length} hazard(s)</span>
        </div>
      {/if}
    </div>
  {:else}
    <p class="no-briefing">No active work</p>
  {/if}
</div>
```

### Briefing Panel

Dedicated panel for viewing/understanding current briefing:

```svelte
<!-- studio/src/components/BriefingPanel.svelte -->

<script lang="ts">
  import { briefing } from '../stores/briefing.svelte';
  
  const statusColors = {
    not_started: 'gray',
    in_progress: 'blue',
    blocked: 'red',
    complete: 'green',
  };
</script>

{#if briefing.current}
  <div class="briefing-panel">
    <header>
      <h2>Current Briefing</h2>
      <span 
        class="status-badge" 
        style="--color: {statusColors[briefing.current.status]}"
      >
        {briefing.current.status.replace('_', ' ')}
      </span>
    </header>
    
    <section class="mission">
      <h3>Mission</h3>
      <p>{briefing.current.mission}</p>
    </section>
    
    <section class="progress">
      <h3>Progress</h3>
      <p>{briefing.current.progress}</p>
    </section>
    
    <section class="momentum">
      <div class="action last">
        <span class="label">Last:</span>
        <span>{briefing.current.lastAction}</span>
      </div>
      {#if briefing.current.nextAction}
        <div class="action next">
          <span class="label">Next:</span>
          <span>{briefing.current.nextAction}</span>
        </div>
      {/if}
    </section>
    
    {#if briefing.hasHazards}
      <section class="hazards">
        <h3>⚠️ Hazards</h3>
        <ul>
          {#each briefing.current.hazards as hazard}
            <li>{hazard}</li>
          {/each}
        </ul>
      </section>
    {/if}
    
    {#if briefing.current.blockers.length > 0}
      <section class="blockers">
        <h3>🚫 Blockers</h3>
        <ul>
          {#each briefing.current.blockers as blocker}
            <li>{blocker}</li>
          {/each}
        </ul>
      </section>
    {/if}
    
    {#if briefing.current.hotFiles.length > 0}
      <section class="hot-files">
        <h3>Focus Files</h3>
        <div class="file-list">
          {#each briefing.current.hotFiles as file}
            <code>{file}</code>
          {/each}
        </div>
      </section>
    {/if}
    
    {#if briefing.hasDispatchHints}
      <section class="dispatch-hints">
        <h3>🎯 Dispatch Hints</h3>
        {#if briefing.current.suggestedLens}
          <p><strong>Suggested Lens:</strong> {briefing.current.suggestedLens}</p>
        {/if}
        {#if briefing.current.predictedSkills?.length}
          <p><strong>Skills:</strong> {briefing.current.predictedSkills.join(', ')}</p>
        {/if}
        {#if briefing.current.complexityEstimate}
          <p><strong>Complexity:</strong> {briefing.current.complexityEstimate}</p>
        {/if}
      </section>
    {/if}
    
    <footer>
      <span class="updated">
        Updated: {new Date(briefing.current.updatedAt).toLocaleString()}
      </span>
    </footer>
  </div>
{:else}
  <div class="no-briefing">
    <p>No active briefing for this project.</p>
    <p class="hint">Start a goal to create one.</p>
  </div>
{/if}
```

---

## Cross-Stack Touchpoints

| Layer | File | Change |
|-------|------|--------|
| **Python** | `src/sunwell/memory/briefing.py` | NEW: `Briefing`, `ExecutionSummary`, `PrefetchPlan`, `PrefetchedContext`, `compress_briefing()` |
| **Python** | `src/sunwell/adaptive/agent.py` | Load briefing at start, save at end, integrate with task graph |
| **Python** | `src/sunwell/adaptive/events.py` | Add `BRIEFING_LOADED`, `BRIEFING_SAVED`, `PREFETCH_START`, `PREFETCH_COMPLETE`, `PREFETCH_TIMEOUT`, `LENS_SUGGESTED` |
| **Python** | `src/sunwell/simulacrum/context/assembler.py` | Include briefing in context assembly |
| **Python** | `src/sunwell/prefetch/dispatcher.py` | NEW: `analyze_briefing_for_prefetch()`, `execute_prefetch()` |
| **Python** | `src/sunwell/routing/briefing_router.py` | NEW: `predict_skills_from_briefing()`, `suggest_lens_from_briefing()` |
| **Rust** | `studio/src-tauri/src/briefing.rs` | NEW: `Briefing` struct with dispatch hints, `BriefingError`, `get_briefing` command |
| **Rust** | `studio/src-tauri/src/lib.rs` | Register briefing commands |
| **TypeScript** | `studio/src/lib/types.ts` | Add `Briefing`, `BriefingStatus` with dispatch hint fields |
| **Svelte** | `studio/src/stores/briefing.svelte.ts` | NEW: briefing store with dispatch hint computed |
| **Svelte** | `studio/src/components/BriefingPanel.svelte` | NEW: briefing display with dispatch hints section |
| **Svelte** | `studio/src/components/ProjectCard.svelte` | Show briefing summary |

---

## Migration & Compatibility

### No Migration Required

The briefing system is purely additive:
- New file (`.sunwell/memory/briefing.json`)
- New events (`BRIEFING_LOADED`, `BRIEFING_SAVED`, `PREFETCH_*`, `LENS_SUGGESTED`)
- No changes to existing data structures

### Graceful Degradation

If no briefing exists:
- Agent proceeds without orientation context
- UI shows "No active briefing"
- First session creates initial briefing

If prefetch fails or times out:
- Agent continues with cold start
- `PREFETCH_TIMEOUT` event emitted
- No user-facing error

---

## Testing Strategy

### Unit Tests (Python)

```python
# tests/test_briefing.py

def test_briefing_roundtrip():
    """Briefing serializes and deserializes correctly."""
    briefing = Briefing(
        mission="Build auth system",
        status=BriefingStatus.IN_PROGRESS,
        progress="JWT signing complete",
        last_action="Added RS256 in auth.py",
        next_action="Implement refresh endpoint",
        hazards=("Don't expose without rate limiting",),
        hot_files=("src/auth.py",),
        # Dispatch hints
        predicted_skills=("security", "api_design"),
        suggested_lens="security-reviewer",
    )
    
    data = briefing.to_dict()
    restored = Briefing.from_dict(data)
    
    assert restored.mission == briefing.mission
    assert restored.status == briefing.status
    assert restored.hazards == briefing.hazards
    assert restored.predicted_skills == briefing.predicted_skills
    assert restored.suggested_lens == briefing.suggested_lens


def test_briefing_optional_fields():
    """Briefing handles missing optional fields gracefully."""
    minimal_data = {
        "mission": "Test",
        "status": "in_progress",
        "progress": "Testing",
        "last_action": "Started",
        # No optional fields
    }
    
    briefing = Briefing.from_dict(minimal_data)
    
    assert briefing.mission == "Test"
    assert briefing.hazards == ()
    assert briefing.predicted_skills == ()
    assert briefing.suggested_lens is None


def test_compress_briefing_with_summary():
    """Compression uses ExecutionSummary correctly."""
    old = Briefing(
        mission="Build API",
        status=BriefingStatus.IN_PROGRESS,
        progress="In progress",
        last_action="Added endpoint",
        hazards=("No auth yet", "No rate limiting"),
    )
    
    summary = ExecutionSummary(
        last_action="Added authentication",
        next_action="Add rate limiting",
        modified_files=("src/auth.py", "src/config.py"),
        tasks_completed=3,
        gates_passed=2,
        new_learnings=("learning-1",),
        new_hazards=(),
        resolved_hazards=("No auth yet",),
    )
    
    new = compress_briefing(
        old_briefing=old,
        summary=summary,
        new_status=BriefingStatus.IN_PROGRESS,
    )
    
    assert "No auth yet" not in new.hazards
    assert "No rate limiting" in new.hazards
    assert new.last_action == "Added authentication"
    assert "src/auth.py" in new.hot_files


def test_compress_briefing_limits_hazards():
    """Compression keeps only 3 most recent hazards."""
    old = Briefing(
        mission="Test",
        status=BriefingStatus.IN_PROGRESS,
        progress="Testing",
        last_action="Test",
        hazards=("Old 1", "Old 2", "Old 3"),
    )
    
    summary = ExecutionSummary(
        last_action="Added more",
        next_action="Continue",
        modified_files=(),
        tasks_completed=1,
        gates_passed=0,
        new_learnings=(),
        new_hazards=("New 1", "New 2"),
        resolved_hazards=(),
    )
    
    new = compress_briefing(
        old_briefing=old,
        summary=summary,
        new_status=BriefingStatus.IN_PROGRESS,
    )
    
    assert len(new.hazards) == 3
    assert new.hazards[0] == "New 1"  # Most recent first


def test_briefing_to_prompt_format():
    """Prompt format is scannable and complete."""
    briefing = Briefing(
        mission="Build auth",
        status=BriefingStatus.IN_PROGRESS,
        progress="80% done",
        last_action="Added JWT",
        next_action="Add refresh",
        hazards=("No rate limiting",),
        hot_files=("auth.py", "config.py"),
    )
    
    prompt = briefing.to_prompt()
    
    assert "## Current State (Briefing)" in prompt
    assert "**Mission**: Build auth" in prompt
    assert "⚠️ No rate limiting" in prompt
    assert "`auth.py`" in prompt


def test_briefing_to_learning():
    """Completed briefing generates learning."""
    briefing = Briefing(
        mission="Implement user authentication",
        status=BriefingStatus.COMPLETE,
        progress="Complete. All endpoints secured.",
        last_action="Added rate limiting",
        next_action=None,
        goal_hash="abc123",
        hot_files=("src/auth.py",),
        hazards=("Watch for token expiry edge cases",),
    )
    
    learning = briefing_to_learning(briefing)
    
    assert learning is not None
    assert "Implement user authentication" in learning.fact
    assert learning.category == LearningCategory.TASK_COMPLETION
    assert learning.goal == "abc123"


def test_briefing_to_learning_not_complete():
    """Non-complete briefing returns None."""
    briefing = Briefing(
        mission="Work in progress",
        status=BriefingStatus.IN_PROGRESS,
        progress="Still working",
        last_action="Did stuff",
        next_action="Do more",
    )
    
    learning = briefing_to_learning(briefing)
    
    assert learning is None
```

### Integration Tests

```python
def test_agent_loads_and_saves_briefing(tmp_path):
    """Agent loads briefing at start and saves at end."""
    # Setup: create initial briefing
    initial = Briefing.create_initial("Build forum app")
    initial.save(tmp_path)
    
    # Run agent
    agent = AdaptiveAgent(cwd=tmp_path, goal="Add user model")
    events = list(agent.run())
    
    # Verify: briefing loaded event
    load_events = [e for e in events if e.type == EventType.BRIEFING_LOADED]
    assert len(load_events) == 1
    
    # Verify: briefing saved event
    save_events = [e for e in events if e.type == EventType.BRIEFING_SAVED]
    assert len(save_events) == 1
    
    # Verify: briefing updated on disk
    updated = Briefing.load(tmp_path)
    assert updated.last_action != initial.last_action


def test_prefetch_with_timeout(tmp_path):
    """Prefetch times out gracefully."""
    briefing = Briefing(
        mission="Test timeout",
        status=BriefingStatus.IN_PROGRESS,
        progress="Testing",
        last_action="Started",
        next_action="Continue",
        hot_files=("nonexistent.py",),
    )
    briefing.save(tmp_path)
    
    # Mock slow prefetch
    async def slow_prefetch(*args):
        await asyncio.sleep(10)  # Longer than timeout
    
    agent = AdaptiveAgent(cwd=tmp_path, goal="Test")
    # Agent should continue despite timeout
    events = list(agent.run())
    
    timeout_events = [e for e in events if e.type == EventType.PREFETCH_TIMEOUT]
    # Either timeout or no prefetch events (both acceptable)
    assert len([e for e in events if e.type == EventType.ERROR]) == 0
```

---

## Advanced: Briefing as Dispatch Signal

The briefing isn't just orientation context — it's a **prefetch signal** that can inform the entire system before the main agent even starts.

### The Insight

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         BRIEFING DISPATCH                                 │
│                                                                          │
│  briefing.json is tiny (~300 tokens)                                     │
│  A cheap/fast model can read it instantly                                │
│  And tell the system what to pre-load                                    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │  CODE PREFETCH │ │  SKILL ROUTING │ │  DAG PREFETCH  │
        │                │ │                │ │                │
        │  hot_files →   │ │  next_action → │ │  goal_hash →   │
        │  pre-read into │ │  load relevant │ │  pre-traverse  │
        │  context       │ │  lens/skills   │ │  related nodes │
        └────────────────┘ └────────────────┘ └────────────────┘
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    │
                                    ▼
                    ┌────────────────────────────────┐
                    │       MAIN AGENT STARTS        │
                    │                                │
                    │  Context already warm:         │
                    │  • Relevant code loaded        │
                    │  • Right skills selected       │
                    │  • DAG context pre-fetched     │
                    └────────────────────────────────┘
```

### Signal Extraction

Each briefing field can drive prefetch decisions:

| Briefing Field | Prefetch Signal | What Gets Pre-Loaded |
|---|---|---|
| `hot_files` | Code context | Read files into context before agent starts |
| `next_action` | Skill prediction | Select relevant lens/heuristics |
| `hazards` | Learning retrieval | Pre-load learnings about those hazards |
| `status: blocked` | Troubleshooting mode | Load debugging skills, error patterns |
| `goal_hash` | DAG traversal | Pre-fetch related conversation nodes |
| `related_learnings` | Memory priming | Load specific learnings into context |

### Prefetch Worker Architecture

```python
# src/sunwell/prefetch/dispatcher.py

import asyncio
from pathlib import Path
from typing import Any

from sunwell.memory.briefing import Briefing, PrefetchPlan, PrefetchedContext


# Default prefetch timeout (seconds)
PREFETCH_TIMEOUT = 2.0


async def analyze_briefing_for_prefetch(
    briefing: Briefing,
    router_model: str = "gpt-4o-mini",  # Tiny model for dispatch
) -> PrefetchPlan:
    """Use cheap model to analyze briefing and plan prefetch.
    
    This runs BEFORE the main agent, using a tiny model to:
    1. Parse the briefing signals
    2. Predict what context will be needed
    3. Return a prefetch plan
    
    The main agent then starts with warm context.
    """
    from sunwell.models import create_model
    
    prompt = f"""Analyze this briefing and predict what context the agent will need.

BRIEFING:
{briefing.to_prompt()}

Return a JSON object with:
- files_to_read: list of file paths likely needed (based on hot_files + next_action)
- learnings_to_load: learning IDs to retrieve (based on hazards + related_learnings)
- skills_needed: which skills apply (testing, debugging, refactoring, api_design, etc.)
- dag_nodes_to_fetch: if goal_hash present, what related nodes to pre-load
- suggested_lens: best lens for this work type (coder, reviewer, architect, etc.)
"""
    
    # Use tiny model for fast dispatch
    model = create_model("openai", router_model)
    response = await model.generate(prompt, json_mode=True)
    
    return PrefetchPlan(
        files_to_read=tuple(response.get("files_to_read", [])),
        learnings_to_load=tuple(response.get("learnings_to_load", [])),
        skills_needed=tuple(response.get("skills_needed", [])),
        dag_nodes_to_fetch=tuple(response.get("dag_nodes_to_fetch", [])),
        suggested_lens=response.get("suggested_lens"),
    )


async def execute_prefetch(
    plan: PrefetchPlan,
    project_path: Path,
    timeout: float = PREFETCH_TIMEOUT,
) -> PrefetchedContext | None:
    """Execute the prefetch plan in parallel with timeout.
    
    This can run while the user is still typing or while
    the main agent is being initialized.
    
    Returns None if timeout exceeded.
    """
    async def _do_prefetch() -> PrefetchedContext:
        async with asyncio.TaskGroup() as tg:
            files_task = tg.create_task(_read_files(plan.files_to_read, project_path))
            learnings_task = tg.create_task(_load_learnings(plan.learnings_to_load, project_path))
            dag_task = tg.create_task(_fetch_dag_nodes(plan.dag_nodes_to_fetch, project_path))
        
        return PrefetchedContext(
            files=files_task.result(),
            learnings=learnings_task.result(),
            dag_context=dag_task.result(),
            active_skills=plan.skills_needed,
            lens=plan.suggested_lens,
        )
    
    try:
        return await asyncio.wait_for(_do_prefetch(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def _read_files(paths: tuple[str, ...], project_path: Path) -> dict[str, str]:
    """Read files into memory."""
    files = {}
    for path in paths:
        full_path = project_path / path
        if full_path.exists():
            try:
                files[path] = full_path.read_text()
            except Exception:
                pass  # Skip unreadable files
    return files


async def _load_learnings(ids: tuple[str, ...], project_path: Path) -> tuple[Any, ...]:
    """Load learnings by ID from memory store."""
    from sunwell.memory.store import MemoryStore
    
    store = MemoryStore(project_path / ".sunwell" / "memory")
    return tuple(store.get_by_ids(list(ids)))


async def _fetch_dag_nodes(ids: tuple[str, ...], project_path: Path) -> tuple[Any, ...]:
    """Fetch DAG nodes for conversation history."""
    # Placeholder - implement based on DAG structure
    return ()
```

### Skill/Lens Routing

The `next_action` field can predict what kind of work is coming:

```python
# src/sunwell/routing/briefing_router.py

import re
from sunwell.memory.briefing import Briefing


SKILL_PATTERNS = {
    # Testing patterns
    r"test|spec|coverage|assert": ["testing", "pytest", "coverage"],
    
    # Debugging patterns  
    r"fix|bug|error|debug|broken": ["debugging", "error_analysis", "logging"],
    
    # Refactoring patterns
    r"refactor|clean|extract|rename": ["refactoring", "code_quality"],
    
    # API patterns
    r"endpoint|route|api|rest|graphql": ["api_design", "http", "serialization"],
    
    # Security patterns
    r"auth|security|permission|token": ["security", "auth", "crypto"],
    
    # Performance patterns
    r"optimi|perf|fast|slow|cache": ["performance", "profiling", "caching"],
}

LENS_MAPPING = {
    "testing": "qa-engineer",
    "debugging": "debugger", 
    "refactoring": "refactorer",
    "api_design": "api-architect",
    "security": "security-reviewer",
    "performance": "performance-engineer",
}


def predict_skills_from_briefing(briefing: Briefing) -> list[str]:
    """Predict needed skills from briefing signals."""
    text = f"{briefing.next_action or ''} {briefing.progress} {' '.join(briefing.hazards)}"
    text = text.lower()
    
    needed_skills = []
    for pattern, skills in SKILL_PATTERNS.items():
        if re.search(pattern, text):
            needed_skills.extend(skills)
    
    return list(set(needed_skills))


def suggest_lens_from_briefing(briefing: Briefing) -> str | None:
    """Suggest best lens based on predicted work type."""
    skills = predict_skills_from_briefing(briefing)
    
    # Return first matching lens
    for skill in skills:
        if skill in LENS_MAPPING:
            return LENS_MAPPING[skill]
    
    return None  # Use default lens
```

### Integration with Agent Startup

```python
# src/sunwell/adaptive/agent.py (enhanced run method)

async def run(
    self,
    goal: str,
    context: dict[str, Any] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Run agent with briefing-driven prefetch."""
    start_time = time()
    
    # Step 1: Load briefing (instant, ~1ms)
    briefing = Briefing.load(self.cwd)
    
    prefetched: PrefetchedContext | None = None
    
    if briefing:
        yield AgentEvent(
            EventType.BRIEFING_LOADED,
            {
                "mission": briefing.mission,
                "status": briefing.status.value,
                "has_hazards": len(briefing.hazards) > 0,
            },
        )
        self._briefing = briefing
        
        # Step 2: Dispatch prefetch (tiny model, ~500ms)
        yield AgentEvent(EventType.PREFETCH_START, {"briefing": briefing.mission})
        
        try:
            prefetch_plan = await analyze_briefing_for_prefetch(briefing)
            
            # Step 3: Execute prefetch with timeout
            prefetched = await execute_prefetch(prefetch_plan, self.cwd)
            
            if prefetched:
                # Step 4: Apply suggested lens if different from current
                if prefetch_plan.suggested_lens and (
                    not self.lens or prefetch_plan.suggested_lens != self.lens.name
                ):
                    yield AgentEvent(
                        EventType.LENS_SUGGESTED,
                        {"suggested": prefetch_plan.suggested_lens, "reason": "briefing_routing"},
                    )
                
                yield AgentEvent(
                    EventType.PREFETCH_COMPLETE,
                    {
                        "files_loaded": len(prefetched.files),
                        "learnings_loaded": len(prefetched.learnings),
                        "skills_activated": list(prefetched.active_skills),
                    },
                )
                
                # Context is now warm
                self._prefetched_context = prefetched
            else:
                # Prefetch timed out
                yield AgentEvent(EventType.PREFETCH_TIMEOUT, {})
                
        except Exception as e:
            # Prefetch failed, continue without warm context
            yield AgentEvent(EventType.PREFETCH_TIMEOUT, {"error": str(e)})
    
    # Continue with normal execution (with or without prefetched context)
    async for event in self._load_memory():
        yield event
    
    # ... rest of run method
```

### Event Flow with Prefetch

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Session Start                                                          │
└─────────────────────────────────────────────────────────────────────────┘
         │
         │ (1) BRIEFING_LOADED (instant, ~1ms)
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Dispatch Analysis (tiny model, ~500ms)                                 │
│                                                                         │
│  "next_action: Add tests for auth" → skills: [testing, auth]            │
│  "hot_files: [auth.py]" → prefetch: auth.py                             │
│  "hazards: [no rate limiting]" → load: rate_limiting learnings          │
└─────────────────────────────────────────────────────────────────────────┘
         │
         │ (2) PREFETCH_START
         │ (3) PREFETCH_COMPLETE {files: 3, learnings: 2, skills: [testing]}
         │     — OR —
         │ (3) PREFETCH_TIMEOUT (if >2s, proceed anyway)
         │ (4) LENS_SUGGESTED {suggested: "qa-engineer"}
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Main Agent Starts (context already warm)                               │
│                                                                         │
│  • auth.py already in context                                           │
│  • Testing skills activated                                             │
│  • Rate limiting learnings loaded                                       │
│  • QA lens applied                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Benefits of Dispatch Architecture

| Benefit | Description |
|---|---|
| **Warm context** | Main agent starts with relevant code/learnings already loaded |
| **Smart routing** | Right lens/skills selected based on predicted work |
| **Parallel init** | Prefetch runs while main model is initializing |
| **Cheap dispatch** | Tiny model (~500ms, ~$0.001) makes routing decisions |
| **Adaptive** | Briefing naturally captures what was needed last time |
| **Fault tolerant** | Timeout ensures prefetch never blocks startup |

### Connection to Existing RFCs

| RFC | How Briefing Dispatch Helps |
|---|---|
| **RFC-020 (Cognitive Routing)** | Briefing provides routing signals for tiny model |
| **RFC-065 (Unified Memory)** | Briefing bridges to learning store via IDs |
| **RFC-066 (Intelligent Run)** | Prefetch aligns with intelligent execution flow |
| **RFC-069 (Cascade)** | Blocked status can trigger troubleshooting sub-agents |
| **RFC-070 (Lens Management)** | Briefing can suggest lens based on work type |
| **RFC-040 (Incremental Build)** | `hot_files` aligns with incremental change detection |

---

## Alternatives Considered

### Alternative 1: Extend Learnings with "Current State" Learning

**Approach**: Add a special learning category for current state, query it first.

**Rejected because**:
- Learnings are meant to accumulate; current state should overwrite
- Would pollute the learning store with transient state
- Doesn't capture momentum (last → next)

### Alternative 2: Use Existing `HandoffState`

**Approach**: Evolve `HandoffState` to be the briefing.

**Rejected because**:
- `HandoffState` accumulates attempts (growing list)
- Designed for model-to-model transfer, not session continuity
- More comprehensive than needed (we want constraint)

### Alternative 3: Store Briefing in DAG

**Approach**: Add briefing as a special node in the conversation DAG.

**Rejected because**:
- DAG is for conversation history, not working state
- Would require DAG load just to get orientation
- Briefing should be instantly accessible without DAG parsing

### Chosen: Separate Briefing File

**Why**:
- Single file, instant load (no parsing DAG or querying learnings)
- Clear separation of concerns (orientation vs. knowledge vs. history)
- Constraint enforced by design (overwrite, not append)
- Easy to inspect/debug (single JSON file)

---

## Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| **Orientation time** | <1 second | Time from session start to briefing loaded |
| **Context efficiency** | <500 tokens | Size of briefing.to_prompt() |
| **Continuity** | 90%+ sessions | Sessions that successfully load previous briefing |
| **Hazard retention** | 100% | Critical hazards survive across sessions |
| **Prefetch accuracy** | 80%+ | Files prefetched that were actually used |
| **Skill prediction** | 70%+ | Predicted skills match actual work done |
| **Warm start rate** | 90%+ | Sessions with successful prefetch completion |
| **Prefetch latency** | <2 seconds | Time from briefing load to prefetch complete |

---

## Implementation Plan

### Phase 1: Core (Python)
1. Create `src/sunwell/memory/briefing.py` with `Briefing`, `ExecutionSummary`, `PrefetchPlan`, `PrefetchedContext`
2. Add event types to `events.py`
3. Integrate into `AdaptiveAgent._load_memory()` and `_save_memory()`
4. Add `briefing_to_learning()` bridge to RFC-065

### Phase 2: Context Integration
1. Modify `ContextAssembler.assemble()` to include briefing
2. Add briefing-aware learning retrieval
3. Wire up `compress_briefing()` in agent save cycle

### Phase 3: Bridge (Rust)
1. Create `studio/src-tauri/src/briefing.rs` with `BriefingError`
2. Register commands in `lib.rs`

### Phase 4: UI (Svelte)
1. Add types to `types.ts` with dispatch hint fields
2. Create `briefing.svelte.ts` store
3. Create `BriefingPanel.svelte` with dispatch hints section
4. Integrate into project cards

### Phase 5: Prefetch Workers (Advanced)
1. Create `src/sunwell/prefetch/dispatcher.py`
2. Create `src/sunwell/routing/briefing_router.py`
3. Integrate prefetch with timeout into agent startup
4. Connect to lens suggestion (RFC-070)

### Phase 6: Polish
1. Add comprehensive tests (including prefetch timeout tests)
2. Handle edge cases (missing briefing, corrupted JSON, slow dispatch)
3. Add CLI command to view/clear briefing
4. Add prefetch statistics to Studio

---

## Open Questions

1. **Breadcrumbs?** Should we keep last N briefings as optional history? Start without, add if needed.

2. **User editing?** Should Studio allow manual briefing edits? Probably yes, for course correction.

3. **Multi-goal?** One briefing per project, or per active goal? Start with one per project; can expand.

4. **Auto-clear on goal complete?** Should briefing auto-clear when status is `complete`? Probably keep it until new goal starts.

5. **Prefetch model?** Should dispatch model be configurable? Start with `gpt-4o-mini`, make configurable later.

---

## Summary

The Briefing System introduces "Twitter for LLMs" — a rolling, compressed handoff note that provides instant orientation without context bloat. The constraint (overwrite, ~300 tokens) enforces salience, creating a natural curation mechanism where relevant details persist and irrelevant ones fade.

**Key insight**: Lossy compression is the feature, not a limitation. Like the telephone game, each session compresses the previous state into what actually matters for the next action.

**Extended insight**: The briefing isn't just orientation — it's a **dispatch signal** that informs the entire system. A tiny model can read the briefing and pre-load code, skills, and DAG context before the main agent even starts. This transforms cold starts into warm starts, with context already primed for the predicted work.

```
Briefing (~300 tokens)
    │
    ├─→ Orientation (agent reads, instant context)
    │
    ├─→ Code Prefetch (hot_files → pre-read)
    │
    ├─→ Skill Routing (next_action → load relevant lens)
    │
    ├─→ DAG Prefetch (goal_hash → pre-traverse related nodes)
    │
    ├─→ Learning Priming (hazards → load relevant learnings)
    │
    └─→ Learning Bridge (completion → RFC-065 unified memory)
```

The briefing becomes the **small, cheap signal** that coordinates expensive operations — a dispatch layer that makes Sunwell's memory system feel anticipatory, not reactive.
