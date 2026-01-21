# RFC-065: Unified Memory Architecture

> **Status:** Draft → Evaluated (Ready for Planning)  
> **Created:** 2026-01-20  
> **Last Updated:** 2026-01-20  
> **Author:** Agent + Human collaboration  
> **Depends on:** RFC-013, RFC-014, RFC-042, RFC-045, RFC-052  
> **Supersedes:** Portions of RFC-013, RFC-042, RFC-045  
> **Confidence:** 92% 🟢

### Revision History

| Date | Change | Reason |
|------|--------|--------|
| 2026-01-20 | Initial draft | Document unified memory architecture |
| 2026-01-20 | v2: Composition over inheritance | Frozen dataclass inheritance is error-prone; use standalone Decision/Failure types with `to_learning()` |
| 2026-01-20 | v2: Fixed `query()` sort order | Was sorting dates ascending instead of newest-first |
| 2026-01-20 | v2: Added `from_dict()` methods | Decision and Failure need explicit deserialization |
| 2026-01-20 | v2: Key Design Decisions section | Document rationale for major design choices |
| 2026-01-20 | v2: Expanded test coverage | Added tests for composition pattern, Rust unified priority |
| 2026-01-20 | v3: Complete touchpoint audit | Added AgentState, ProjectLearnings, agent store, memory_learning event |

## Summary

Consolidate Sunwell's fragmented learning and memory systems into a single, well-designed architecture. Currently, there are 4+ storage locations, 2 duplicate `Learning` classes, and multiple overlapping stores. This RFC unifies them into one coherent system with **aligned types across Python, Rust (Tauri), and TypeScript (Svelte)**.

## Goals

1. **Single Source of Truth**: One storage location (`.sunwell/memory/`) for all learnings
2. **Single Type Definition**: One `Learning` class in Python, with aligned Rust and TypeScript types
3. **Cross-Stack Contract**: JSON schema that Python writes and Rust/Svelte reads
4. **Migration Without Breakage**: Seamlessly migrate existing data from legacy locations
5. **Thread-Safe**: Support Python 3.14t free-threading and concurrent Studio reads

## Non-Goals

1. **SQLite Migration**: Not in scope for this RFC (can be a future optimization)
2. **Embedding Search**: Semantic/vector search is deferred (keyword search is MVP)
3. **Cross-Project Learnings**: Sharing learnings between projects is out of scope
4. **Simulacrum Rewrite**: Conversation DAG remains separate; we only extract learnings from it

## Motivation

### Current State: Technical Debt

Each RFC added its own storage mechanism without consolidation:

| RFC | System | Storage Location | Format |
|-----|--------|------------------|--------|
| RFC-013/014 | Simulacrum | `.sunwell/sessions/` | Custom DAG |
| RFC-042 | Adaptive Agent | `.sunwell/learnings/` | JSON arrays |
| RFC-045 | Project Intelligence | `.sunwell/intelligence/` | JSONL |
| RFC-052 | Team Intelligence | `.sunwell/team/` | JSONL |

### Problems

1. **Duplicate Classes**: Two `Learning` dataclasses, two `LearningExtractor` classes
2. **Fragmented Storage**: Learnings in 3+ locations with different formats
3. **Integration Pain**: Studio had to read from multiple paths to display learnings
4. **Inconsistent APIs**: Different stores have different interfaces
5. **No Single Source of Truth**: Hard to answer "what does the agent know?"

### Evidence

```bash
# Multiple Learning classes
src/sunwell/simulacrum/core/turn.py:160:class Learning:
src/sunwell/adaptive/learning.py:32:class Learning:

# Multiple storage paths
.sunwell/learnings/*.json           # Naaru format
.sunwell/intelligence/learnings.jsonl  # RFC-045 format
.sunwell/intelligence/decisions.jsonl  # Decisions
.sunwell/intelligence/failures.jsonl   # Failures
.sunwell/sessions/                     # Simulacrum
```

### Cross-Stack Touchpoint Summary

All files that need modification across Python, Rust, and Svelte/TypeScript:

| Layer | File | Current | Change Required |
|-------|------|---------|-----------------|
| **Python** | `src/sunwell/adaptive/learning.py:32` | `class Learning` | Deprecate → use `memory.types.Learning` |
| **Python** | `src/sunwell/simulacrum/core/turn.py:160` | `class Learning` | Deprecate → use `memory.types.Learning` |
| **Python** | `src/sunwell/naaru/naaru.py` | Emits `memory_learning` with `fact` | Emit structured `learning` object |
| **Python** | `src/sunwell/adaptive/agent.py` | Uses `LearningStore` | Use `MemoryStore` |
| **Rust** | `studio/src-tauri/src/memory.rs:41` | `struct Learning` | Update fields: add `goal`, `source_type`, `metadata` |
| **Rust** | `studio/src-tauri/src/memory.rs` | `get_intelligence` reads legacy paths | Read `.sunwell/memory/` first |
| **Rust** | `studio/src-tauri/src/memory.rs` | `ProjectLearnings` uses `Vec<String>` | Use `Vec<Decision>`, `Vec<Failure>` |
| **TypeScript** | `studio/src/lib/types.ts:154` | `AgentState.learnings: string[]` | Change to `Learning[]` |
| **TypeScript** | `studio/src/lib/types.ts:76` | `ProjectLearnings.decisions: string[]` | Change to `Decision[]` |
| **TypeScript** | `studio/src/lib/types.ts:348` | `interface Learning` | Add `goal`, `sourceType`, `metadata` |
| **Svelte** | `studio/src/stores/agent.svelte.ts` | Handles `fact: string` | Handle structured `learning` object |
| **Svelte** | `studio/src/components/LearningsPanel.svelte` | `learnings?: string[]` | Change to `Learning[]` |
| **Svelte** | `studio/src/components/MemoryView.svelte` | Shows `DeadEnd` | Merge into `Failure` display |

## Design

### Unified Storage Structure

```
.sunwell/
├── memory/                          # NEW: Unified memory store
│   ├── learnings.jsonl              # All learnings (single format)
│   ├── decisions.jsonl              # Architectural decisions
│   ├── failures.jsonl               # Failed approaches (merged with dead_ends)
│   ├── artifacts/                   # Execution artifacts metadata
│   │   └── {goal_hash}.json         # Per-goal artifact completion
│   └── index.json                   # Quick lookup index
│
├── plans/                           # KEPT: Execution state (RFC-040)
│   └── {goal_hash}.json
│
├── sessions/                        # KEPT: Conversation DAG (RFC-013)
│   └── {session_id}/                # But learnings extracted to memory/
│
└── codebase/                        # KEPT: Static analysis (RFC-045)
    ├── graph.pickle
    └── patterns.json
```

### Unified Data Model

#### Learning (Single Definition)

```python
# src/sunwell/memory/types.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LearningCategory(Enum):
    """Categories of learnings for filtering and relevance scoring."""
    
    TASK_COMPLETION = "task_completion"  # What was built
    PATTERN = "pattern"                   # Code patterns discovered
    TYPE = "type"                         # Type definitions, schemas
    API = "api"                           # Endpoints, interfaces
    FIX = "fix"                           # What fixed errors
    DECISION = "decision"                 # Architectural choices (elevated)
    FAILURE = "failure"                   # What didn't work (elevated)


@dataclass(frozen=True, slots=True)
class Learning:
    """A fact learned from agent execution, code analysis, or user feedback.
    
    This is the SINGLE learning type used throughout Sunwell.
    All other Learning classes are deprecated.
    
    Attributes:
        id: Unique identifier (hash of fact + category)
        fact: The learned information
        category: Classification for filtering
        confidence: How certain we are (0.0-1.0)
        source: Where this came from (file, task_id, session, user)
        source_type: Type of source (task, analysis, user, session)
        created_at: When learned
        goal: Original goal context (if applicable)
        metadata: Additional context
    """
    
    id: str
    fact: str
    category: LearningCategory
    confidence: float = 0.8
    source: str | None = None
    source_type: str = "task"  # task, analysis, user, session
    created_at: datetime = field(default_factory=datetime.now)
    goal: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONL storage."""
        return {
            "id": self.id,
            "fact": self.fact,
            "category": self.category.value,
            "confidence": self.confidence,
            "source": self.source,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat(),
            "goal": self.goal,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Learning:
        """Deserialize from JSONL storage."""
        return cls(
            id=data["id"],
            fact=data["fact"],
            category=LearningCategory(data["category"]),
            confidence=data.get("confidence", 0.8),
            source=data.get("source"),
            source_type=data.get("source_type", "task"),
            created_at=datetime.fromisoformat(data["created_at"]),
            goal=data.get("goal"),
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def create(
        cls,
        fact: str,
        category: LearningCategory | str,
        **kwargs,
    ) -> Learning:
        """Factory method with auto-generated ID."""
        import hashlib
        
        if isinstance(category, str):
            category = LearningCategory(category)
        
        # Generate stable ID from content
        content = f"{category.value}:{fact}"
        learning_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        return cls(id=learning_id, fact=fact, category=category, **kwargs)
```

#### Decision and Failure (Elevated Learnings)

Decisions and failures are special categories of learnings with additional fields. 
We use **composition over inheritance** to avoid frozen dataclass inheritance issues:

```python
@dataclass(frozen=True, slots=True)
class Decision:
    """An architectural decision with rationale.
    
    Stored in memory/decisions.jsonl for quick access,
    but also indexed in memory/learnings.jsonl as a Learning.
    
    Design choice: Composition over inheritance. Frozen dataclass
    inheritance with __post_init__ is error-prone. Instead, Decision
    is a standalone type with a to_learning() method for indexing.
    """
    
    id: str
    decision: str  # The decision made (maps to Learning.fact)
    rationale: str
    scope: str = "project"  # project, file, function
    supersedes: str | None = None  # ID of decision this replaces
    created_at: datetime = field(default_factory=datetime.now)
    goal: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONL storage."""
        return {
            "id": self.id,
            "decision": self.decision,
            "rationale": self.rationale,
            "scope": self.scope,
            "supersedes": self.supersedes,
            "created_at": self.created_at.isoformat(),
            "goal": self.goal,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        """Deserialize from JSONL storage."""
        return cls(
            id=data["id"],
            decision=data["decision"],
            rationale=data.get("rationale", ""),
            scope=data.get("scope", "project"),
            supersedes=data.get("supersedes"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            goal=data.get("goal"),
        )
    
    def to_learning(self) -> Learning:
        """Convert to Learning for unified index."""
        return Learning.create(
            fact=self.decision,
            category=LearningCategory.DECISION,
            confidence=1.0,
            source=f"decision:{self.id}",
            source_type="user",
            goal=self.goal,
            metadata={"rationale": self.rationale, "scope": self.scope},
        )
    
    @classmethod
    def create(cls, decision: str, rationale: str, **kwargs) -> Decision:
        """Factory method with auto-generated ID."""
        import hashlib
        content = f"decision:{decision}"
        decision_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        return cls(id=decision_id, decision=decision, rationale=rationale, **kwargs)


@dataclass(frozen=True, slots=True)  
class Failure:
    """A failed approach with context.
    
    Stored in memory/failures.jsonl for quick access,
    but also indexed in memory/learnings.jsonl as a Learning.
    """
    
    id: str
    fact: str  # What didn't work
    approach: str  # What was attempted
    context: str = ""  # Additional failure context
    created_at: datetime = field(default_factory=datetime.now)
    goal: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONL storage."""
        return {
            "id": self.id,
            "fact": self.fact,
            "approach": self.approach,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "goal": self.goal,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Failure:
        """Deserialize from JSONL storage."""
        return cls(
            id=data["id"],
            fact=data.get("fact", data.get("approach", "")),  # Fallback for legacy
            approach=data.get("approach", ""),
            context=data.get("context", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            goal=data.get("goal"),
        )
    
    def to_learning(self) -> Learning:
        """Convert to Learning for unified index."""
        return Learning.create(
            fact=self.fact,
            category=LearningCategory.FAILURE,
            confidence=1.0,
            source=f"failure:{self.id}",
            source_type="task",
            goal=self.goal,
            metadata={"approach": self.approach, "context": self.context},
        )
    
    @classmethod
    def create(cls, fact: str, approach: str, **kwargs) -> Failure:
        """Factory method with auto-generated ID."""
        import hashlib
        content = f"failure:{approach}:{fact}"
        failure_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        return cls(id=failure_id, fact=fact, approach=approach, **kwargs)
```

### Unified Memory Store

```python
# src/sunwell/memory/store.py

from dataclasses import dataclass, field
from pathlib import Path
import json
import threading
from collections.abc import Iterator

from sunwell.memory.types import Learning, Decision, Failure, LearningCategory


@dataclass
class MemoryStore:
    """Unified memory store for all Sunwell learnings.
    
    Single interface for:
    - Reading/writing learnings
    - Querying by category, goal, source
    - Relevance-based retrieval
    - Persistence to .sunwell/memory/
    
    Thread-safe with file locking.
    
    Example:
        >>> store = MemoryStore.load(project_root)
        >>> store.add(Learning.create("User model has email field", "type"))
        >>> 
        >>> # Query by category
        >>> types = store.query(category=LearningCategory.TYPE)
        >>>
        >>> # Relevance search
        >>> relevant = store.search("user authentication", limit=5)
    """
    
    base_path: Path
    _learnings: dict[str, Learning] = field(default_factory=dict)
    _decisions: dict[str, Decision] = field(default_factory=dict)
    _failures: dict[str, Failure] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _dirty: bool = field(default=False)
    
    # Paths
    @property
    def learnings_path(self) -> Path:
        return self.base_path / "learnings.jsonl"
    
    @property
    def decisions_path(self) -> Path:
        return self.base_path / "decisions.jsonl"
    
    @property
    def failures_path(self) -> Path:
        return self.base_path / "failures.jsonl"
    
    @property
    def index_path(self) -> Path:
        return self.base_path / "index.json"
    
    # =========================================================================
    # Factory Methods
    # =========================================================================
    
    @classmethod
    def load(cls, project_root: Path) -> MemoryStore:
        """Load or create memory store for a project.
        
        Also migrates from legacy locations if found.
        """
        memory_path = project_root / ".sunwell" / "memory"
        memory_path.mkdir(parents=True, exist_ok=True)
        
        store = cls(base_path=memory_path)
        store._load_from_disk()
        store._migrate_legacy(project_root)
        
        return store
    
    # =========================================================================
    # Core Operations
    # =========================================================================
    
    def add(self, learning: Learning) -> None:
        """Add a learning (deduplicates by ID)."""
        with self._lock:
            if learning.id in self._learnings:
                return  # Already exists
            
            self._learnings[learning.id] = learning
            self._dirty = True
    
    def add_decision(
        self,
        decision: str,
        rationale: str,
        scope: str = "project",
        **kwargs,
    ) -> Decision:
        """Add a decision (also indexes as Learning).
        
        Stores the full Decision in decisions.jsonl and creates
        a corresponding Learning entry in learnings.jsonl for
        unified querying.
        """
        d = Decision.create(decision=decision, rationale=rationale, scope=scope, **kwargs)
        with self._lock:
            if d.id not in self._decisions:
                self._decisions[d.id] = d
                # Also add as Learning for unified queries
                self._learnings[d.id] = d.to_learning()
                self._dirty = True
        return d
    
    def add_failure(
        self,
        fact: str,
        approach: str,
        context: str = "",
        **kwargs,
    ) -> Failure:
        """Add a failure (also indexes as Learning).
        
        Stores the full Failure in failures.jsonl and creates
        a corresponding Learning entry in learnings.jsonl for
        unified querying.
        """
        f = Failure.create(fact=fact, approach=approach, context=context, **kwargs)
        with self._lock:
            if f.id not in self._failures:
                self._failures[f.id] = f
                # Also add as Learning for unified queries
                self._learnings[f.id] = f.to_learning()
                self._dirty = True
        return f
    
    def get(self, learning_id: str) -> Learning | None:
        """Get a learning by ID."""
        return self._learnings.get(learning_id)
    
    def query(
        self,
        category: LearningCategory | None = None,
        goal: str | None = None,
        source: str | None = None,
        min_confidence: float = 0.0,
        limit: int | None = None,
    ) -> list[Learning]:
        """Query learnings with filters."""
        results = []
        
        for learning in self._learnings.values():
            if category and learning.category != category:
                continue
            if goal and learning.goal != goal:
                continue
            if source and learning.source != source:
                continue
            if learning.confidence < min_confidence:
                continue
            results.append(learning)
        
        # Sort by confidence (highest first), then by date (newest first)
        # Note: Using negative timestamp for newest-first without reverse=True
        results.sort(key=lambda l: (-l.confidence, -l.created_at.timestamp()))
        
        if limit:
            results = results[:limit]
        
        return results
    
    def search(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float = 0.5,
    ) -> list[Learning]:
        """Relevance-based search (simple keyword matching).
        
        For semantic search, use with an embedder.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for learning in self._learnings.values():
            if learning.confidence < min_confidence:
                continue
            
            fact_lower = learning.fact.lower()
            
            # Simple scoring: word overlap
            fact_words = set(fact_lower.split())
            overlap = len(query_words & fact_words)
            
            if overlap > 0 or query_lower in fact_lower:
                score = overlap / len(query_words) if query_words else 0
                if query_lower in fact_lower:
                    score += 0.5  # Bonus for substring match
                scored.append((score * learning.confidence, learning))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [l for _, l in scored[:limit]]
    
    @property
    def decisions(self) -> list[Decision]:
        """All decisions."""
        return list(self._decisions.values())
    
    @property
    def failures(self) -> list[Failure]:
        """All failures."""
        return list(self._failures.values())
    
    @property
    def stats(self) -> dict[str, int]:
        """Statistics about stored learnings."""
        by_category = {}
        for learning in self._learnings.values():
            cat = learning.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
        
        return {
            "total": len(self._learnings),
            "decisions": len(self._decisions),
            "failures": len(self._failures),
            "by_category": by_category,
        }
    
    # =========================================================================
    # Persistence
    # =========================================================================
    
    def save(self) -> None:
        """Persist all learnings to disk."""
        if not self._dirty:
            return
        
        with self._lock:
            self._save_jsonl(self.learnings_path, self._learnings.values())
            self._save_jsonl(self.decisions_path, self._decisions.values())
            self._save_jsonl(self.failures_path, self._failures.values())
            self._save_index()
            self._dirty = False
    
    def flush(self) -> None:
        """Alias for save()."""
        self.save()
    
    def _save_jsonl(self, path: Path, items: Iterator[Learning]) -> None:
        """Save items to JSONL file with file-level locking.
        
        Uses atomic write (write to temp, then rename) to prevent corruption
        from concurrent processes (e.g., Studio reading while agent writes).
        """
        import tempfile
        
        # Write to temp file first
        temp_path = path.with_suffix('.jsonl.tmp')
        with open(temp_path, "w") as f:
            for item in items:
                f.write(json.dumps(item.to_dict()) + "\n")
        
        # Atomic rename (POSIX guarantees this is atomic)
        temp_path.rename(path)
    
    def _save_index(self) -> None:
        """Save quick-lookup index."""
        index = {
            "version": "1.0",
            "stats": self.stats,
            "categories": list(LearningCategory.__members__.keys()),
        }
        self.index_path.write_text(json.dumps(index, indent=2))
    
    def _load_from_disk(self) -> None:
        """Load learnings from disk.
        
        Load order matters:
        1. Learnings first (base data)
        2. Decisions (full data, updates Learning entry)
        3. Failures (full data, updates Learning entry)
        """
        # Load main learnings
        if self.learnings_path.exists():
            with open(self.learnings_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        learning = Learning.from_dict(data)
                        self._learnings[learning.id] = learning
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        
        # Load decisions (full data stored separately)
        # Also create/update Learning entry for unified queries
        if self.decisions_path.exists():
            with open(self.decisions_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        decision = Decision.from_dict(data)
                        self._decisions[decision.id] = decision
                        # Ensure Learning exists for unified queries
                        self._learnings[decision.id] = decision.to_learning()
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        
        # Load failures (full data stored separately)
        # Also create/update Learning entry for unified queries
        if self.failures_path.exists():
            with open(self.failures_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        failure = Failure.from_dict(data)
                        self._failures[failure.id] = failure
                        # Ensure Learning exists for unified queries
                        self._learnings[failure.id] = failure.to_learning()
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
    
    # =========================================================================
    # Migration
    # =========================================================================
    
    def _migrate_legacy(self, project_root: Path) -> None:
        """Migrate from legacy storage locations."""
        migrated = 0
        
        # 1. Migrate from .sunwell/learnings/*.json (Naaru format)
        naaru_dir = project_root / ".sunwell" / "learnings"
        if naaru_dir.exists():
            for json_file in naaru_dir.glob("*.json"):
                migrated += self._migrate_naaru_file(json_file)
        
        # 2. Migrate from .sunwell/intelligence/learnings.jsonl
        intel_learnings = project_root / ".sunwell" / "intelligence" / "learnings.jsonl"
        if intel_learnings.exists():
            migrated += self._migrate_intel_learnings(intel_learnings)
        
        # 3. Migrate from .sunwell/intelligence/decisions.jsonl
        intel_decisions = project_root / ".sunwell" / "intelligence" / "decisions.jsonl"
        if intel_decisions.exists():
            migrated += self._migrate_intel_decisions(intel_decisions)
        
        # 4. Migrate from .sunwell/intelligence/failures.jsonl
        intel_failures = project_root / ".sunwell" / "intelligence" / "failures.jsonl"
        if intel_failures.exists():
            migrated += self._migrate_intel_failures(intel_failures)
        
        # 5. Migrate dead_ends from adaptive system
        intel_dead_ends = project_root / ".sunwell" / "intelligence" / "dead_ends.jsonl"
        if intel_dead_ends.exists():
            migrated += self._migrate_dead_ends(intel_dead_ends)
        
        if migrated > 0:
            self._dirty = True
            self.save()
    
    def _migrate_naaru_file(self, path: Path) -> int:
        """Migrate Naaru execution learnings."""
        migrated = 0
        try:
            with open(path) as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return 0
            
            for entry in data:
                task_id = entry.get("task_id", "")
                description = entry.get("task_description", "")
                goal = entry.get("goal", "")
                timestamp = entry.get("timestamp")
                
                if task_id and description:
                    learning = Learning.create(
                        fact=f"Completed: {description}",
                        category=LearningCategory.TASK_COMPLETION,
                        confidence=1.0,
                        source=task_id,
                        source_type="task",
                        goal=goal,
                        created_at=datetime.fromisoformat(timestamp) if timestamp else datetime.now(),
                    )
                    self.add(learning)
                    migrated += 1
        except (json.JSONDecodeError, OSError):
            pass
        
        return migrated
    
    def _migrate_intel_learnings(self, path: Path) -> int:
        """Migrate intelligence learnings."""
        migrated = 0
        try:
            with open(path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    
                    # Map old format to new
                    learning = Learning.create(
                        fact=data.get("fact", ""),
                        category=data.get("category", "pattern"),
                        confidence=data.get("confidence", 0.7),
                        source=data.get("source_file"),
                        source_type="analysis",
                    )
                    self.add(learning)
                    migrated += 1
        except (json.JSONDecodeError, OSError):
            pass
        
        return migrated
    
    def _migrate_intel_decisions(self, path: Path) -> int:
        """Migrate intelligence decisions."""
        migrated = 0
        try:
            with open(path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    
                    decision = Decision.create(
                        fact=data.get("decision", ""),
                        category=LearningCategory.DECISION,
                        rationale=data.get("rationale", ""),
                        scope=data.get("scope", "project"),
                        confidence=1.0,
                        source_type="user",
                    )
                    self.add(decision)
                    migrated += 1
        except (json.JSONDecodeError, OSError):
            pass
        
        return migrated
    
    def _migrate_intel_failures(self, path: Path) -> int:
        """Migrate intelligence failures."""
        migrated = 0
        try:
            with open(path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    
                    failure = Failure.create(
                        fact=data.get("approach", ""),
                        category=LearningCategory.FAILURE,
                        approach=data.get("approach", ""),
                        context=data.get("context", ""),
                        confidence=1.0,
                        source_type="task",
                    )
                    self.add(failure)
                    migrated += 1
        except (json.JSONDecodeError, OSError):
            pass
        
        return migrated
    
    def _migrate_dead_ends(self, path: Path) -> int:
        """Migrate dead ends as failures."""
        return self._migrate_intel_failures(path)  # Same format
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Python (Agent)                                                 │
│   ┌──────────────────┐                                          │
│   │  MemoryStore     │──────────────────────┐                   │
│   │  (write)         │                      │                   │
│   └──────────────────┘                      ▼                   │
│                                    .sunwell/memory/              │
│                                    ├── learnings.jsonl           │
│                                    ├── decisions.jsonl           │
│                                    ├── failures.jsonl            │
│                                    └── index.json                │
│                                             │                    │
│   Rust (Tauri)                             │                    │
│   ┌──────────────────┐                     │                    │
│   │  get_intelligence│◄────────────────────┘                    │
│   │  (read)          │                                          │
│   └────────┬─────────┘                                          │
│            │ IPC                                                 │
│            ▼                                                     │
│   TypeScript (Svelte)                                           │
│   ┌──────────────────┐     ┌──────────────────┐                 │
│   │  project.svelte  │────▶│  MemoryView.svelte│                │
│   │  (store)         │     │  (display)        │                │
│   └──────────────────┘     └──────────────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Contract: JSONL format with camelCase keys (Rust serde) ──▶ TypeScript interfaces
```

### Key Invariants

1. **Python WRITES** to `.sunwell/memory/` — single writer
2. **Rust READS** from `.sunwell/memory/` — multiple readers OK
3. **Atomic writes** via temp file + rename prevents read corruption
4. **Category enum** values identical across all three languages
5. **Field names** use snake_case in JSON, camelCase in TypeScript (Rust serde handles conversion)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Type drift between Python/Rust/TypeScript | Medium | High | Contract tests in CI; shared JSON schema |
| Migration corrupts existing data | Low | High | Backup before migration; test with real projects |
| Concurrent write corruption | Low | Medium | Atomic writes via temp+rename |
| Studio reads stale data | Medium | Low | Add file watcher for hot reload |
| Performance with large learning sets | Low | Medium | Index file for quick stats; lazy load in Studio |

---

## Key Design Decisions

### 1. Composition Over Inheritance for Decision/Failure

**Decision**: `Decision` and `Failure` are standalone types with `to_learning()` methods, 
rather than subclasses of `Learning`.

**Rationale**:
- **Frozen dataclass inheritance is error-prone**: Using `__post_init__` with 
  `object.__setattr__` on frozen parent classes leads to subtle bugs and maintenance burden.
- **Different storage needs**: Decisions and Failures have their own JSONL files 
  (`decisions.jsonl`, `failures.jsonl`) with different schemas.
- **Type safety**: Explicit conversion via `to_learning()` makes the data flow clear 
  and allows different confidence values, metadata, etc.
- **Rust/TypeScript alignment**: Non-inheriting types map cleanly to Rust structs 
  and TypeScript interfaces.

**Trade-off**: Slight code duplication (separate `to_dict`/`from_dict` implementations) 
is acceptable for improved type safety and maintainability.

### 2. JSONL Over SQLite

**Decision**: Use JSONL files for storage.

**Rationale**:
- **Human-readable**: Easier debugging and manual inspection
- **Append-friendly**: New learnings can be appended without rewriting
- **Atomic writes**: Temp file + rename pattern prevents corruption
- **Cross-platform**: No native dependencies

**Trade-off**: Querying requires full scan. For <10k learnings this is acceptable. 
SQLite migration can be a future optimization if needed.

### 3. Single Writer, Multiple Readers

**Decision**: Python agent is the only writer; Rust/TypeScript read only.

**Rationale**:
- **Simplifies concurrency**: No need for distributed locking
- **Clear ownership**: Agent creates learnings; Studio displays them
- **Atomic writes**: Temp file + rename ensures readers never see partial writes

**Trade-off**: Studio cannot edit/delete learnings directly. This is acceptable 
as learnings are derived from agent execution.

### 4. Unified Index with Category-Specific Files

**Decision**: Store full data in `decisions.jsonl`/`failures.jsonl` but also index 
in `learnings.jsonl` as Learning entries.

**Rationale**:
- **Unified queries**: `store.query()` searches all learning types
- **Full fidelity**: Category-specific files preserve all fields (rationale, approach, etc.)
- **Backward compatibility**: Existing code reading `learnings.jsonl` continues to work

**Trade-off**: Some data duplication between files. This is acceptable given 
typical learning set sizes (<10MB total).

---

## Cross-Stack Type Contract

This section defines the **exact JSON schema** that all three layers must agree on. Python writes these files, Rust reads them for the Studio backend, and TypeScript types match for the Svelte frontend.

### JSON Schema: Learning

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Learning",
  "description": "A fact learned from agent execution, code analysis, or user feedback",
  "type": "object",
  "required": ["id", "fact", "category", "created_at"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique identifier (SHA256 hash prefix of category:fact)"
    },
    "fact": {
      "type": "string",
      "description": "The learned information"
    },
    "category": {
      "type": "string",
      "enum": ["task_completion", "pattern", "type", "api", "fix", "decision", "failure"],
      "description": "Classification for filtering and relevance"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "default": 0.8,
      "description": "Confidence score (0.0-1.0)"
    },
    "source": {
      "type": ["string", "null"],
      "description": "Source reference (file path, task ID, etc.)"
    },
    "source_type": {
      "type": "string",
      "enum": ["task", "analysis", "user", "session"],
      "default": "task",
      "description": "Type of source"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp"
    },
    "goal": {
      "type": ["string", "null"],
      "description": "Original goal context if applicable"
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "default": {},
      "description": "Additional context"
    }
  }
}
```

### JSON Schema: Decision (standalone type)

Decision is a **standalone type**, not an extension of Learning. The Python `to_learning()` 
method creates a corresponding Learning entry for unified queries.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Decision",
  "description": "An architectural decision with rationale",
  "type": "object",
  "required": ["id", "decision", "rationale", "created_at"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique identifier (SHA256 hash prefix)"
    },
    "decision": {
      "type": "string",
      "description": "The decision made"
    },
    "rationale": {
      "type": "string",
      "description": "Why this decision was made"
    },
    "scope": {
      "type": "string",
      "enum": ["project", "file", "function"],
      "default": "project"
    },
    "supersedes": {
      "type": ["string", "null"],
      "description": "ID of decision this replaces"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "goal": {
      "type": ["string", "null"],
      "description": "Goal context this decision was made for"
    }
  }
}
```

### JSON Schema: Failure (standalone type)

Failure is a **standalone type**, not an extension of Learning. The Python `to_learning()` 
method creates a corresponding Learning entry for unified queries.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Failure",
  "description": "A failed approach with context",
  "type": "object",
  "required": ["id", "fact", "approach", "created_at"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique identifier (SHA256 hash prefix)"
    },
    "fact": {
      "type": "string",
      "description": "What didn't work"
    },
    "approach": {
      "type": "string",
      "description": "What was attempted"
    },
    "context": {
      "type": "string",
      "default": "",
      "description": "Additional failure context"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "goal": {
      "type": ["string", "null"],
      "description": "Goal context this failure occurred in"
    }
  }
}
```

### Rust Types (studio/src-tauri/src/memory.rs)

```rust
//! Memory Types — Aligned with Python sunwell.memory.types
//!
//! These types MUST match the JSON schema above.
//! Any changes require updating Python and TypeScript as well.

use serde::{Deserialize, Serialize};

/// Learning categories - must match Python LearningCategory enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum LearningCategory {
    TaskCompletion,
    Pattern,
    Type,
    Api,
    Fix,
    Decision,
    Failure,
}

/// Source types for learnings
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum SourceType {
    #[default]
    Task,
    Analysis,
    User,
    Session,
}

/// A fact learned from agent execution - UNIFIED TYPE
/// Replaces the previous Learning struct with additional fields
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct Learning {
    pub id: String,
    pub fact: String,
    pub category: String,  // Use string for flexibility, validate in code
    #[serde(default = "default_confidence")]
    pub confidence: f32,
    pub source: Option<String>,
    #[serde(default)]
    pub source_type: String,
    pub created_at: Option<String>,
    pub goal: Option<String>,
    #[serde(default)]
    pub metadata: serde_json::Value,
}

fn default_confidence() -> f32 { 0.8 }

/// Decision - Learning with rationale
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct Decision {
    pub id: String,
    pub decision: String,  // Maps to "fact" in Learning
    pub rationale: String,
    #[serde(default = "default_scope")]
    pub scope: String,
    pub created_at: Option<String>,
    pub supersedes: Option<String>,
    pub goal: Option<String>,
}

fn default_scope() -> String { "project".to_string() }

/// Failure - Learning with approach context
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct Failure {
    pub id: String,
    pub fact: String,
    pub approach: String,
    #[serde(default)]
    pub context: String,
    pub created_at: Option<String>,
    pub goal: Option<String>,
}

/// Memory statistics from index.json
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryStats {
    pub session_id: Option<String>,
    pub total_learnings: u32,
    pub total_decisions: u32,
    pub total_failures: u32,
    pub by_category: std::collections::HashMap<String, u32>,
}

/// Unified intelligence data for Studio display
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IntelligenceData {
    pub decisions: Vec<Decision>,
    pub failures: Vec<Failure>,
    pub learnings: Vec<Learning>,
    pub total_decisions: u32,
    pub total_failures: u32,
    pub total_learnings: u32,
}
```

### TypeScript Types (studio/src/lib/types.ts)

```typescript
// ═══════════════════════════════════════════════════════════════
// MEMORY / UNIFIED LEARNINGS (RFC-065)
// ═══════════════════════════════════════════════════════════════

/**
 * Learning categories - must match Python LearningCategory enum
 */
export type LearningCategory =
  | 'task_completion'
  | 'pattern'
  | 'type'
  | 'api'
  | 'fix'
  | 'decision'
  | 'failure';

/**
 * Source types for learnings
 */
export type SourceType = 'task' | 'analysis' | 'user' | 'session';

/**
 * A fact learned from agent execution - UNIFIED TYPE (RFC-065)
 * 
 * This replaces the previous Learning interface with additional fields
 * for goal tracking and metadata.
 */
export interface Learning {
  id: string;
  fact: string;
  category: LearningCategory;
  confidence: number;
  source: string | null;
  sourceType: SourceType;
  createdAt: string | null;
  /** Goal context this learning was extracted from */
  goal: string | null;
  /** Additional context (flexible key-value pairs) */
  metadata: Record<string, unknown>;
}

/**
 * Decision - standalone type for architectural decisions (RFC-065)
 * 
 * Note: This is NOT a subtype of Learning. Python's MemoryStore.add_decision()
 * creates both a Decision entry AND a corresponding Learning entry for unified queries.
 */
export interface Decision {
  id: string;
  decision: string;
  rationale: string;
  scope: 'project' | 'file' | 'function';
  createdAt: string | null;
  supersedes: string | null;
  goal: string | null;
}

/**
 * Failure - standalone type for failed approaches (RFC-065)
 * 
 * Note: This is NOT a subtype of Learning. Python's MemoryStore.add_failure()
 * creates both a Failure entry AND a corresponding Learning entry for unified queries.
 */
export interface Failure {
  id: string;
  fact: string;
  approach: string;
  context: string;
  createdAt: string | null;
  goal: string | null;
}

/**
 * Memory statistics from .sunwell/memory/index.json
 */
export interface MemoryStats {
  sessionId: string | null;
  totalLearnings: number;
  totalDecisions: number;
  totalFailures: number;
  byCategory: Record<LearningCategory, number>;
  // Legacy fields for backwards compatibility
  hotTurns: number;
  warmFiles: number;
  warmSizeMb: number;
  coldFiles: number;
  coldSizeMb: number;
  totalTurns: number;
  branches: number;
  deadEnds: number;
  learnings: number;
}

/**
 * Unified intelligence data for Studio display (RFC-065)
 */
export interface IntelligenceData {
  decisions: Decision[];
  failures: Failure[];
  learnings: Learning[];
  totalDecisions: number;
  totalFailures: number;
  totalLearnings: number;
  // Legacy fields
  deadEnds: DeadEnd[];
  totalDeadEnds: number;
}

// Legacy type alias for backwards compatibility
export interface DeadEnd {
  approach: string;
  reason: string;
  context: string | null;
  createdAt: string | null;
}
```

### Category Alignment Table

| Python Enum | JSON Value | Rust Enum | TypeScript Type |
|-------------|------------|-----------|-----------------|
| `LearningCategory.TASK_COMPLETION` | `"task_completion"` | `TaskCompletion` | `'task_completion'` |
| `LearningCategory.PATTERN` | `"pattern"` | `Pattern` | `'pattern'` |
| `LearningCategory.TYPE` | `"type"` | `Type` | `'type'` |
| `LearningCategory.API` | `"api"` | `Api` | `'api'` |
| `LearningCategory.FIX` | `"fix"` | `Fix` | `'fix'` |
| `LearningCategory.DECISION` | `"decision"` | `Decision` | `'decision'` |
| `LearningCategory.FAILURE` | `"failure"` | `Failure` | `'failure'` |

---

## Rust Backend Updates (Tauri)

The `studio/src-tauri/src/memory.rs` file needs significant updates to read from the unified location.

### Updated get_intelligence Command

```rust
/// Get intelligence data from UNIFIED memory location (RFC-065)
#[tauri::command]
pub async fn get_intelligence(path: String) -> Result<IntelligenceData, String> {
    let project_path = PathBuf::from(&path);
    
    // PRIMARY: Read from unified .sunwell/memory/ (RFC-065)
    let memory_path = project_path.join(".sunwell/memory");
    let mut data = IntelligenceData::default();
    
    if memory_path.exists() {
        // Read unified learnings
        let learnings_path = memory_path.join("learnings.jsonl");
        if learnings_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&learnings_path) {
                for line in content.lines() {
                    if line.is_empty() { continue; }
                    if let Ok(learning) = serde_json::from_str::<Learning>(line) {
                        data.learnings.push(learning);
                    }
                }
            }
        }
        
        // Read decisions
        let decisions_path = memory_path.join("decisions.jsonl");
        if decisions_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&decisions_path) {
                for line in content.lines() {
                    if line.is_empty() { continue; }
                    if let Ok(decision) = serde_json::from_str::<Decision>(line) {
                        data.decisions.push(decision);
                    }
                }
            }
        }
        
        // Read failures
        let failures_path = memory_path.join("failures.jsonl");
        if failures_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&failures_path) {
                for line in content.lines() {
                    if line.is_empty() { continue; }
                    if let Ok(failure) = serde_json::from_str::<Failure>(line) {
                        data.failures.push(failure);
                    }
                }
            }
        }
    }
    
    // FALLBACK: Read from legacy locations if unified is empty
    // This enables gradual migration
    if data.learnings.is_empty() && data.decisions.is_empty() {
        data = read_legacy_intelligence(&project_path)?;
    }
    
    // Update totals
    data.total_learnings = data.learnings.len() as u32;
    data.total_decisions = data.decisions.len() as u32;
    data.total_failures = data.failures.len() as u32;
    
    Ok(data)
}

/// Read from legacy locations (for migration period)
fn read_legacy_intelligence(project_path: &PathBuf) -> Result<IntelligenceData, String> {
    // ... existing logic from current memory.rs lines 217-364 ...
    // This preserves backwards compatibility during migration
}
```

---

## Svelte Component Updates

### MemoryView.svelte - Category Colors

Update category styling to include new categories:

```svelte
<style>
  /* Category colors - RFC-065 unified categories */
  .category-task_completion { background: rgba(52, 211, 153, 0.2); color: #34d399; }
  .category-pattern { background: rgba(167, 139, 250, 0.2); color: #a78bfa; }
  .category-type { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
  .category-api { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
  .category-fix { background: rgba(52, 211, 153, 0.2); color: #34d399; }
  .category-decision { background: rgba(201, 162, 39, 0.2); color: #c9a227; }
  .category-failure { background: rgba(248, 113, 113, 0.2); color: #f87171; }
</style>
```

### LearningsPanel.svelte - Goal Context Display

```svelte
<script lang="ts">
  import type { Learning } from '$lib/types';
  
  interface Props {
    learnings?: Learning[];  // Changed from string[] to Learning[]
    collapsed?: boolean;
  }
  
  let { learnings = [], collapsed = $bindable(false) }: Props = $props();
</script>

<!-- Updated to show structured learnings -->
{#each visibleLearnings as learning (learning.id)}
  <li class="learning-item" style="animation-delay: {i * 30}ms">
    <span class="learning-fact">{learning.fact}</span>
    {#if learning.goal}
      <span class="learning-goal">from: {learning.goal.slice(0, 30)}...</span>
    {/if}
    <span class="meta-tag category-{learning.category}">{learning.category}</span>
  </li>
{/each}
```

### AgentState Updates (studio/src/lib/types.ts)

The `AgentState` interface currently stores learnings as `string[]`. This needs updating 
to support structured learnings:

```typescript
export interface AgentState {
  status: AgentStatus;
  goal: string | null;
  tasks: Task[];
  currentTaskIndex: number;
  totalTasks: number;
  startTime: number | null;
  endTime: number | null;
  error: string | null;
  // RFC-065: Changed from string[] to Learning[]
  learnings: Learning[];
  concepts: Concept[];
  // ... rest unchanged
}
```

### ProjectLearnings Updates (studio/src/lib/types.ts)

The `ProjectLearnings` type used by `getProjectLearnings()` should use the new types:

```typescript
export interface ProjectLearnings {
  original_goal: string | null;
  // RFC-065: Changed from string[] to Decision[]
  decisions: Decision[];
  // RFC-065: Changed from string[] to Failure[]  
  failures: Failure[];
  completed_tasks: string[];
  pending_tasks: string[];
}
```

### Agent Store Updates (studio/src/stores/agent.svelte.ts)

The agent store needs updating to handle structured learning events:

```typescript
// Change initial state
const initialState: AgentState = {
  // ...existing fields...
  learnings: [],  // Now Learning[], not string[]
  concepts: [],
};

// Update memory_learning event handler
case 'memory_learning': {
  // RFC-065: Receive structured Learning objects
  const learning = data.learning as Learning | undefined;
  const fact = (data.fact as string) ?? '';  // Fallback for legacy events
  
  if (learning) {
    // New structured format
    const newConcepts = extractConceptsFromLearning(learning);
    _state = {
      ..._state,
      learnings: [..._state.learnings, learning],
      concepts: deduplicateConcepts([..._state.concepts, ...newConcepts]),
    };
  } else if (fact) {
    // Legacy format (for backwards compatibility during migration)
    const legacyLearning: Learning = {
      id: `legacy-${Date.now()}`,
      fact,
      category: 'pattern',
      confidence: 0.8,
      source: null,
      sourceType: 'task',
      createdAt: new Date().toISOString(),
      goal: _state.goal,
      metadata: {},
    };
    const newConcepts = extractConcepts(fact);
    _state = {
      ..._state,
      learnings: [..._state.learnings, legacyLearning],
      concepts: deduplicateConcepts([..._state.concepts, ...newConcepts]),
    };
  }
  break;
}

// New helper function
function extractConceptsFromLearning(learning: Learning): Concept[] {
  return extractConcepts(learning.fact);
}
```

### Event Contract: memory_learning

The `memory_learning` event emitted by Python needs to send structured data:

```python
# OLD (string-only)
self._emit_event("memory_learning", fact="User model has email field")

# NEW (structured Learning)
self._emit_event(
    "memory_learning",
    learning={
        "id": learning.id,
        "fact": learning.fact,
        "category": learning.category.value,
        "confidence": learning.confidence,
        "source": learning.source,
        "source_type": learning.source_type,
        "created_at": learning.created_at.isoformat(),
        "goal": learning.goal,
        "metadata": learning.metadata,
    },
    # Include fact for backwards compatibility
    fact=learning.fact,
)
```

### Rust get_project_learnings Command

The `get_project_learnings` command needs updating to return structured data:

```rust
/// Get learnings for a project (used by project iteration UI)
#[tauri::command]
pub async fn get_project_learnings(path: String) -> Result<ProjectLearnings, String> {
    let project_path = PathBuf::from(&path);
    let memory_path = project_path.join(".sunwell/memory");
    
    let mut result = ProjectLearnings::default();
    
    // Read from unified location (RFC-065)
    if memory_path.exists() {
        // Read decisions
        let decisions_path = memory_path.join("decisions.jsonl");
        if decisions_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&decisions_path) {
                for line in content.lines() {
                    if line.is_empty() { continue; }
                    if let Ok(decision) = serde_json::from_str::<Decision>(line) {
                        result.decisions.push(decision);
                    }
                }
            }
        }
        
        // Read failures
        let failures_path = memory_path.join("failures.jsonl");
        if failures_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&failures_path) {
                for line in content.lines() {
                    if line.is_empty() { continue; }
                    if let Ok(failure) = serde_json::from_str::<Failure>(line) {
                        result.failures.push(failure);
                    }
                }
            }
        }
    }
    
    // ... rest of implementation for tasks
    
    Ok(result)
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectLearnings {
    pub original_goal: Option<String>,
    pub decisions: Vec<Decision>,  // Changed from Vec<String>
    pub failures: Vec<Failure>,    // Changed from Vec<String>
    pub completed_tasks: Vec<String>,
    pub pending_tasks: Vec<String>,
}
```

---

### Integration Points

#### 1. Agent Startup

```python
# In Naaru or AdaptiveAgent initialization

async def _load_memory(self) -> None:
    """Load unified memory store."""
    from sunwell.memory.store import MemoryStore
    
    self.memory = MemoryStore.load(self.project_root)
    
    # Log what was loaded
    stats = self.memory.stats
    if stats["total"] > 0:
        self._emit_event("memory_loaded", **stats)
```

#### 2. During Execution

```python
# After task completion

def _record_completion(self, task: Task, output: str) -> None:
    """Record task completion as learning."""
    learning = Learning.create(
        fact=f"Completed: {task.description}",
        category=LearningCategory.TASK_COMPLETION,
        confidence=1.0,
        source=task.id,
        source_type="task",
        goal=self.current_goal,
    )
    self.memory.add(learning)
    
    # Extract patterns from output
    for pattern in self._extract_patterns(output):
        self.memory.add(pattern)
```

#### 3. Context Building

```python
# When planning or creating artifacts

def _build_context(self, goal: str) -> dict[str, Any]:
    """Build context with relevant learnings."""
    return {
        "cwd": str(self.project_root),
        "completed": self._completed_artifacts,
        "learnings": [
            l.fact for l in self.memory.search(goal, limit=10)
        ],
        "decisions": [
            f"{d.fact}: {d.rationale}" for d in self.memory.decisions[-5:]
        ],
        "failures": [
            f"Avoid: {f.approach} ({f.fact})" for f in self.memory.failures[-3:]
        ],
    }
```

#### 4. Studio Integration

```rust
// In studio/src-tauri/src/memory.rs

pub async fn get_memory_stats(path: String) -> Result<MemoryStats, String> {
    let project_path = PathBuf::from(&path);
    let memory_path = project_path.join(".sunwell/memory");
    
    // Read from unified location
    let learnings_path = memory_path.join("learnings.jsonl");
    let index_path = memory_path.join("index.json");
    
    // ... rest of implementation
}
```

## Migration Plan

### Phase 1: Add Unified Store (Non-Breaking) — Python

1. Create `src/sunwell/memory/` module with new types and store
2. Add migration logic that reads from all legacy locations
3. Write to new unified location (`.sunwell/memory/`)
4. Existing code continues to work (reads from old locations)

**Files to create:**
- `src/sunwell/memory/__init__.py`
- `src/sunwell/memory/types.py` (Learning, Decision, Failure, LearningCategory)
- `src/sunwell/memory/store.py` (MemoryStore)

### Phase 2: Update Writers (Gradual) — Python

1. Update Naaru to write to unified store (`src/sunwell/naaru/naaru.py`)
2. Update AdaptiveAgent to use unified store (`src/sunwell/adaptive/agent.py`)
3. Update CLI commands to use unified store (`src/sunwell/cli/agent/run.py`)
4. Update learning extractor to use new types (`src/sunwell/adaptive/learning.py`)

**Commits:**
- `memory: add unified memory types and store`
- `naaru: switch to unified memory store`
- `adaptive: switch to unified memory store`
- `cli: update run command to use unified memory`

### Phase 2.5: Update Event Emission — Python

Update `memory_learning` event to send structured Learning objects:

1. Update `src/sunwell/naaru/events.py` or equivalent to emit structured data
2. Include `learning` object in event payload (structured Learning)
3. Keep `fact` field for backwards compatibility during migration

**Files to modify:**
- Event emitters in `src/sunwell/naaru/naaru.py`
- Event emitters in `src/sunwell/adaptive/agent.py`

**Commits:**
- `events: emit structured Learning in memory_learning event`

### Phase 3: Update Studio Backend — Rust

1. Update `studio/src-tauri/src/memory.rs` with new types
2. Update `get_intelligence` to read from unified location first
3. Update `get_project_learnings` to return structured Decision/Failure
4. Update `ProjectLearnings` struct to use `Vec<Decision>` and `Vec<Failure>`
5. Keep legacy fallback for migration period
6. Update `MemoryStats` to include new fields

**Files to modify:**
- `studio/src-tauri/src/memory.rs` (types + commands)
- `studio/src-tauri/src/project.rs` (if get_project_learnings lives here)

**Commits:**
- `studio: update memory types for RFC-065`
- `studio: read from unified memory location`
- `studio: update get_project_learnings for structured data`

### Phase 4: Update Studio Frontend — Svelte/TypeScript

1. Update `studio/src/lib/types.ts` with new types
2. Update `AgentState.learnings` from `string[]` to `Learning[]`
3. Update `ProjectLearnings` to use `Decision[]` and `Failure[]`
4. Update `MemoryView.svelte` with new category colors
5. Update `LearningsPanel.svelte` to show structured learnings
6. Update `agent.svelte.ts` to handle structured `memory_learning` events
7. Update `project.svelte.ts` for `getProjectLearnings()` if needed

**Files to modify:**
- `studio/src/lib/types.ts` (Learning, Decision, Failure, AgentState, ProjectLearnings)
- `studio/src/stores/agent.svelte.ts` (memory_learning event, AgentState.learnings)
- `studio/src/stores/project.svelte.ts` (getProjectLearnings if needed)
- `studio/src/components/MemoryView.svelte` (category colors, DeadEnd→Failure)
- `studio/src/components/LearningsPanel.svelte` (string[] → Learning[])

**Commits:**
- `studio: update TypeScript types for RFC-065`
- `studio: update agent store for structured learnings`
- `studio: update MemoryView with unified categories`
- `studio: update LearningsPanel for structured learnings`

### Phase 5: Deprecate Old Code — Python

1. Add deprecation warnings to old `Learning` classes
2. Add deprecation warnings to old `LearningStore`
3. Document migration path in docstrings

### Phase 6: Remove Legacy (Breaking) — Python

1. Remove `src/sunwell/adaptive/learning.py` (old Learning class)
2. Remove `src/sunwell/simulacrum/core/turn.py` Learning class  
3. Remove redundant extractors (`src/sunwell/simulacrum/extractors/extractor.py`)
4. Clean up old storage paths (optional - keep for read compatibility)

## Deprecation Schedule

### Python

| Item | Deprecated In | Removed In |
|------|---------------|------------|
| `adaptive.learning.Learning` | 0.2.0 | 0.3.0 |
| `adaptive.learning.LearningStore` | 0.2.0 | 0.3.0 |
| `adaptive.learning.LearningExtractor` | 0.2.0 | 0.3.0 |
| `simulacrum.core.turn.Learning` | 0.2.0 | 0.3.0 |
| `simulacrum.extractors.extractor.LearningExtractor` | 0.2.0 | 0.3.0 |

### Storage Paths

| Path | Deprecated In | Removed In |
|------|---------------|------------|
| `.sunwell/learnings/` | 0.2.0 | Never (read for migration) |
| `.sunwell/intelligence/learnings.jsonl` | 0.2.0 | Never (read for migration) |
| `.sunwell/intelligence/decisions.jsonl` | 0.2.0 | Never (read for migration) |
| `.sunwell/intelligence/failures.jsonl` | 0.2.0 | Never (read for migration) |

### Rust/TypeScript (Studio)

| Item | Deprecated In | Removed In |
|------|---------------|------------|
| Legacy `read_legacy_intelligence()` fallback | 0.3.0 | 0.4.0 |
| Old `DeadEnd` type (merged into `Failure`) | 0.2.0 | 0.3.0 |

## Testing Strategy

### Python Unit Tests

```python
# tests/test_memory_store.py

def test_memory_store_add_and_query():
    """Test basic add/query operations."""
    store = MemoryStore(base_path=tmp_path)
    
    learning = Learning.create("User has email", LearningCategory.TYPE)
    store.add(learning)
    
    results = store.query(category=LearningCategory.TYPE)
    assert len(results) == 1
    assert results[0].fact == "User has email"


def test_memory_store_deduplication():
    """Test that duplicate learnings are ignored."""
    store = MemoryStore(base_path=tmp_path)
    
    learning = Learning.create("Same fact", LearningCategory.PATTERN)
    store.add(learning)
    store.add(learning)  # Duplicate
    
    assert len(store.query()) == 1


def test_memory_store_migration():
    """Test migration from legacy locations."""
    # Create legacy files
    naaru_dir = tmp_path / ".sunwell" / "learnings"
    naaru_dir.mkdir(parents=True)
    (naaru_dir / "20260120.json").write_text(json.dumps([
        {"task_id": "task1", "task_description": "Create model", "goal": "test"}
    ]))
    
    # Load should migrate
    store = MemoryStore.load(tmp_path)
    
    results = store.query(category=LearningCategory.TASK_COMPLETION)
    assert len(results) == 1


def test_atomic_write_survives_concurrent_read():
    """Test that writes don't corrupt reads (thread-safety)."""
    import threading
    
    store = MemoryStore(base_path=tmp_path)
    errors = []
    
    def writer():
        for i in range(100):
            store.add(Learning.create(f"fact-{i}", LearningCategory.PATTERN))
            store.save()
    
    def reader():
        for _ in range(100):
            try:
                # Simulate Studio reading the file
                if store.learnings_path.exists():
                    content = store.learnings_path.read_text()
                    for line in content.splitlines():
                        if line:
                            json.loads(line)  # Should not fail mid-write
            except json.JSONDecodeError as e:
                errors.append(e)
    
    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0, f"Concurrent read saw corrupted JSON: {errors}"


def test_decision_creates_learning_entry():
    """Test that add_decision creates both Decision and Learning."""
    store = MemoryStore(base_path=tmp_path)
    
    decision = store.add_decision(
        decision="Use PostgreSQL for persistence",
        rationale="ACID compliance, JSON support",
        scope="project",
    )
    
    # Decision should be stored
    assert len(store.decisions) == 1
    assert store.decisions[0].decision == "Use PostgreSQL for persistence"
    
    # Learning should also be created for unified queries
    learnings = store.query(category=LearningCategory.DECISION)
    assert len(learnings) == 1
    assert "PostgreSQL" in learnings[0].fact
    assert learnings[0].metadata.get("rationale") == "ACID compliance, JSON support"


def test_failure_creates_learning_entry():
    """Test that add_failure creates both Failure and Learning."""
    store = MemoryStore(base_path=tmp_path)
    
    failure = store.add_failure(
        fact="Direct SQL queries caused N+1 problem",
        approach="Raw SQL instead of ORM",
        context="Performance testing revealed 500ms latency",
    )
    
    # Failure should be stored
    assert len(store.failures) == 1
    
    # Learning should also be created for unified queries
    learnings = store.query(category=LearningCategory.FAILURE)
    assert len(learnings) == 1
    assert learnings[0].metadata.get("approach") == "Raw SQL instead of ORM"


def test_decision_to_learning_roundtrip():
    """Test Decision.to_learning() produces valid Learning."""
    decision = Decision.create(
        decision="Use dataclasses for DTOs",
        rationale="Immutability, type hints",
        scope="file",
        goal="Implement user API",
    )
    
    learning = decision.to_learning()
    
    assert learning.fact == "Use dataclasses for DTOs"
    assert learning.category == LearningCategory.DECISION
    assert learning.confidence == 1.0
    assert learning.goal == "Implement user API"
    assert learning.source_type == "user"
    assert "rationale" in learning.metadata


def test_failure_serialization():
    """Test Failure.to_dict() and from_dict() roundtrip."""
    original = Failure.create(
        fact="Memory leak under load",
        approach="Unbounded cache",
        context="Load test with 10k requests",
        goal="Optimize performance",
    )
    
    data = original.to_dict()
    restored = Failure.from_dict(data)
    
    assert restored.id == original.id
    assert restored.fact == original.fact
    assert restored.approach == original.approach
    assert restored.context == original.context
    assert restored.goal == original.goal
```

### Python Integration Tests

```python
# tests/test_memory_integration.py

async def test_agent_uses_unified_memory():
    """Test that agent loads and writes to unified store."""
    # Run agent
    result = await naaru.run("Create a user model")
    
    # Check unified store
    store = MemoryStore.load(project_root)
    completions = store.query(category=LearningCategory.TASK_COMPLETION)
    assert len(completions) > 0


async def test_follow_up_task_sees_learnings():
    """Test that follow-up tasks see prior learnings."""
    # First run
    await naaru.run("Create user model")
    
    # Second run should see prior work
    result = await naaru.run("Add email validation to user")
    
    # Context should include prior learnings
    assert "user model" in result.context_used.lower()
```

### Rust Unit Tests

```rust
// studio/src-tauri/src/memory.rs

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_reads_unified_memory() {
        let tmp = TempDir::new().unwrap();
        let memory_dir = tmp.path().join(".sunwell/memory");
        std::fs::create_dir_all(&memory_dir).unwrap();
        
        // Write unified format
        std::fs::write(
            memory_dir.join("learnings.jsonl"),
            r#"{"id": "abc123", "fact": "User has email", "category": "type", "confidence": 0.9, "created_at": "2026-01-20T00:00:00Z"}
{"id": "def456", "fact": "API uses REST", "category": "api", "confidence": 0.8, "created_at": "2026-01-20T00:00:00Z"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_learnings, 2);
        assert_eq!(data.learnings[0].category, "type");
    }

    #[tokio::test]
    async fn test_reads_unified_decisions() {
        let tmp = TempDir::new().unwrap();
        let memory_dir = tmp.path().join(".sunwell/memory");
        std::fs::create_dir_all(&memory_dir).unwrap();
        
        std::fs::write(
            memory_dir.join("decisions.jsonl"),
            r#"{"id": "d1", "decision": "Use async", "rationale": "Better for I/O", "scope": "project", "created_at": "2026-01-20T00:00:00Z"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_decisions, 1);
        assert_eq!(data.decisions[0].rationale, "Better for I/O");
    }

    #[tokio::test]
    async fn test_reads_unified_failures() {
        let tmp = TempDir::new().unwrap();
        let memory_dir = tmp.path().join(".sunwell/memory");
        std::fs::create_dir_all(&memory_dir).unwrap();
        
        std::fs::write(
            memory_dir.join("failures.jsonl"),
            r#"{"id": "f1", "fact": "Memory leak", "approach": "Unbounded cache", "context": "Load test", "created_at": "2026-01-20T00:00:00Z"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_failures, 1);
        assert_eq!(data.failures[0].approach, "Unbounded cache");
    }

    #[tokio::test]
    async fn test_fallback_to_legacy() {
        let tmp = TempDir::new().unwrap();
        // Only legacy location exists
        let intel_dir = tmp.path().join(".sunwell/intelligence");
        std::fs::create_dir_all(&intel_dir).unwrap();
        std::fs::write(
            intel_dir.join("decisions.jsonl"),
            r#"{"id": "d1", "decision": "Legacy decision", "rationale": "Old format"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_decisions, 1);
    }

    #[tokio::test]
    async fn test_unified_takes_priority_over_legacy() {
        let tmp = TempDir::new().unwrap();
        
        // Create both unified and legacy locations
        let memory_dir = tmp.path().join(".sunwell/memory");
        let intel_dir = tmp.path().join(".sunwell/intelligence");
        std::fs::create_dir_all(&memory_dir).unwrap();
        std::fs::create_dir_all(&intel_dir).unwrap();
        
        // Unified has 1 decision
        std::fs::write(
            memory_dir.join("decisions.jsonl"),
            r#"{"id": "unified-d1", "decision": "Unified decision", "rationale": "New format", "created_at": "2026-01-20T00:00:00Z"}"#,
        ).unwrap();
        
        // Legacy has 2 decisions
        std::fs::write(
            intel_dir.join("decisions.jsonl"),
            r#"{"id": "legacy-d1", "decision": "Legacy 1", "rationale": "Old"}
{"id": "legacy-d2", "decision": "Legacy 2", "rationale": "Old"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        
        // Should use unified (1 decision), not legacy (2 decisions)
        assert_eq!(data.total_decisions, 1);
        assert_eq!(data.decisions[0].id, "unified-d1");
    }
}
```

### Cross-Stack Contract Tests

```python
# tests/test_cross_stack_contract.py
"""Verify that Python output matches what Rust/TypeScript expects."""

import json
import subprocess
from sunwell.memory.types import Learning, Decision, Failure, LearningCategory
from sunwell.memory.store import MemoryStore


def test_learning_json_matches_typescript_interface():
    """Verify Learning.to_dict() produces valid JSON for TypeScript."""
    learning = Learning.create(
        fact="User model has email field",
        category=LearningCategory.TYPE,
        confidence=0.9,
        source="models.py",
        source_type="analysis",
        goal="Create user model",
    )
    
    data = learning.to_dict()
    
    # Required fields
    assert "id" in data and isinstance(data["id"], str)
    assert "fact" in data and isinstance(data["fact"], str)
    assert "category" in data and data["category"] in [
        "task_completion", "pattern", "type", "api", "fix", "decision", "failure"
    ]
    assert "confidence" in data and 0 <= data["confidence"] <= 1
    assert "created_at" in data  # ISO 8601 string
    
    # Optional fields present
    assert "source" in data
    assert "source_type" in data
    assert "goal" in data
    assert "metadata" in data


def test_decision_json_matches_typescript_interface():
    """Verify Decision.to_dict() produces valid JSON for TypeScript."""
    decision = Decision.create(
        fact="Use SQLAlchemy for ORM",
        category=LearningCategory.DECISION,
        rationale="Industry standard, good docs",
        scope="project",
    )
    
    data = decision.to_dict()
    
    # Decision-specific fields
    assert "rationale" in data
    assert "scope" in data and data["scope"] in ["project", "file", "function"]


def test_jsonl_format_parseable_by_rust():
    """Verify JSONL output is valid line-by-line JSON."""
    store = MemoryStore(base_path=tmp_path)
    
    for i in range(5):
        store.add(Learning.create(f"Fact {i}", LearningCategory.PATTERN))
    store.save()
    
    # Read and parse each line (simulating Rust)
    content = store.learnings_path.read_text()
    lines = [l for l in content.splitlines() if l.strip()]
    
    assert len(lines) == 5
    for line in lines:
        parsed = json.loads(line)  # Must not raise
        assert "id" in parsed
        assert "fact" in parsed
```

## Success Metrics

### Python
1. **Single Source of Truth**: All learnings written to `.sunwell/memory/`
2. **No Duplicate Classes**: One `Learning` type in `sunwell.memory.types`
3. **Consistent API**: `MemoryStore` is the only interface for memory operations
4. **Migration Works**: Legacy data from `.sunwell/learnings/` and `.sunwell/intelligence/` migrated
5. **Thread-Safe**: Atomic writes prevent corruption under concurrent access

### Rust (Tauri)
6. **Types Aligned**: Rust structs deserialize Python's JSON output without errors
7. **Unified Read**: `get_intelligence` reads from `.sunwell/memory/` first
8. **Fallback Works**: Legacy locations still readable during migration period

### Svelte (TypeScript)
9. **Types Aligned**: TypeScript interfaces match Rust's JSON serialization
10. **UI Displays**: MemoryView shows all learning categories with correct colors
11. **No Console Errors**: No type mismatches or deserialization errors in dev tools

### Cross-Stack
12. **Contract Test Passes**: Python output parseable by Rust tests
13. **E2E Works**: Agent writes → Studio reads cycle works in integration test

## Alternatives Considered

### A. Keep Separate Stores, Add Facade

Add a facade that reads from all locations but doesn't consolidate storage.

**Rejected**: Doesn't solve the duplicate classes problem, and makes writes more complex.

### B. SQLite Instead of JSONL

Use SQLite for structured queries.

**Rejected for now**: JSONL is simpler, human-readable, and sufficient for current scale. Can migrate to SQLite later if needed.

### C. Full Rewrite of Simulacrum

Merge Simulacrum completely into this system.

**Rejected**: Simulacrum (conversation DAG) serves a different purpose (conversation history, not learnings). Keep it separate, just extract learnings from it.

## Open Questions

1. **Embeddings**: Should we add embedding-based semantic search now or later?
   - **Recommendation**: Later. Keyword search is sufficient for MVP. Can add `sunwell.memory.embeddings` module in future RFC.

2. **TTL**: Should learnings expire?
   - **Recommendation**: No expiration by default. High-confidence learnings (`>=0.9`) should persist indefinitely. Could add optional `expires_at` field for temporary learnings.

3. **Cross-Project**: Should learnings be shareable across projects?
   - **Recommendation**: Out of scope. RFC-052 (Team Intelligence) handles shared knowledge via `.sunwell/team/` which is git-tracked.

4. **Windows File Locking**: Does atomic rename work on Windows?
   - **Status**: POSIX rename is atomic. On Windows, `os.replace()` is atomic. Python's `Path.rename()` maps to the right syscall. ✅ Resolved.

5. **Studio Hot Reload**: Should Studio watch `.sunwell/memory/` for changes?
   - **Recommendation**: Yes, use Tauri's file watcher to refresh memory view when agent writes. Defer to future PR.

## References

### RFCs
- RFC-013: Simulacrum (Conversation Memory)
- RFC-014: Memory Tiers
- RFC-042: Adaptive Agent
- RFC-045: Project Intelligence
- RFC-052: Team Intelligence
- RFC-054: Learnings Display

### Current Implementation (to be consolidated)
- `src/sunwell/adaptive/learning.py:32` — Old Learning class (Python)
- `src/sunwell/adaptive/learning.py:77` — Old LearningExtractor (Python)
- `src/sunwell/simulacrum/core/turn.py:160` — Old Learning class (Python)
- `src/sunwell/simulacrum/extractors/extractor.py:139` — Old LearningExtractor (Python)
- `studio/src-tauri/src/memory.rs:41` — Current Learning struct (Rust)
- `studio/src/lib/types.ts:348` — Current Learning interface (TypeScript)
- `studio/src/components/MemoryView.svelte` — Memory display component (Svelte)
- `studio/src/components/LearningsPanel.svelte` — Real-time learnings (Svelte)
