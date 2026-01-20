# RFC-052: Team Intelligence — Shared Knowledge Across Developers

**Status**: Draft (Revised)  
**Created**: 2026-01-19  
**Last Updated**: 2026-01-20  
**Revision**: 2 — Added design alternatives, clarified RFC-045 relationship, added RejectedOption  
**Authors**: Sunwell Team  
**Depends on**: RFC-045 (Project Intelligence), RFC-049 (External Integration), RFC-051 (Multi-Instance)  
**Enables**: Phase 5 Enterprise Ready, team adoption, organizational knowledge capture  
**Confidence**: 85% (design reviewed, implementation-ready)

---

## Revision History

| Rev | Date | Changes |
|-----|------|---------|
| 2 | 2026-01-20 | Added "Design Alternatives Considered" section with 3 options. Added "Relationship to RFC-045" section clarifying storage model and Decision↔TeamDecision mapping. Added RejectedOption dataclass. Added confidence field to TeamDecision. Updated implementation plan with migration phase. |
| 1 | 2026-01-19 | Initial draft |

---

## Summary

Team Intelligence enables multiple developers to share Sunwell's accumulated knowledge — decisions, patterns, failures, and codebase understanding — across a team. Instead of each developer's Sunwell instance learning independently, teams benefit from collective intelligence: a decision made by Alice is visible to Bob's Sunwell, a failure pattern discovered by Carol prevents everyone from hitting the same wall.

**Core insight**: Individual Sunwell instances are smart. But a team where every instance shares knowledge is exponentially smarter. The first person to solve a problem solves it for everyone.

**Design approach**: Git-based synchronization with conflict resolution. Shared intelligence is stored in the repository (committed to git), while personal preferences remain local. This leverages existing workflows (PR review, branch merging) and requires zero infrastructure.

**One-liner**: One team member learns it once, everyone's Sunwell knows it forever.

---

## Motivation

### The Island Problem (Team Edition)

RFC-045 (Project Intelligence) gave each Sunwell instance persistent memory. But each instance is still an island:

```
┌────────────────────────────────────────────────────────────────────┐
│                     ISOLATED INTELLIGENCE                           │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Alice's Sunwell          Bob's Sunwell          Carol's Sunwell   │
│  ─────────────────        ─────────────────      ─────────────────│
│  Decision: Use OAuth      Decision: ???          Decision: ???     │
│  Pattern: snake_case      Pattern: ???           Pattern: ???      │
│  Failure: Redis complex   Failure: ???           Failure: ???      │
│                                                                    │
│  Alice spent 30 minutes deciding OAuth over JWT.                   │
│  Bob spends another 30 minutes re-discovering the same thing.      │
│  Carol's Sunwell suggests JWT — hasn't learned from the team.      │
│                                                                    │
│  Repeated work × N developers = massive waste.                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### What Senior Engineers Know (Team Context)

A senior engineer on a team knows not just their own decisions, but the team's collective wisdom:

| Individual Knowledge | Team Knowledge |
|---------------------|----------------|
| "I chose OAuth" | "We chose OAuth (Alice's decision, for enterprise SSO)" |
| "Redis was hard for me" | "Team policy: avoid Redis unless necessary (3 failed attempts)" |
| "I like snake_case" | "Project standard: snake_case (enforced in PR review)" |
| "This function is fragile" | "billing.py is owned by DevOps — always tag them" |

### The Team Intelligence Opportunity

```
┌────────────────────────────────────────────────────────────────────┐
│                     SHARED INTELLIGENCE                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                    ┌───────────────────────┐                       │
│                    │   TEAM KNOWLEDGE       │                       │
│                    │   (Git-synchronized)   │                       │
│                    ├───────────────────────┤                       │
│                    │ Decisions: 47          │                       │
│                    │ Patterns: enforced     │                       │
│                    │ Failures: 23 recorded  │                       │
│                    │ Ownership: mapped      │                       │
│                    └───────────┬───────────┘                       │
│                                │                                   │
│          ┌─────────────────────┼─────────────────────┐             │
│          │                     │                     │             │
│          ▼                     ▼                     ▼             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │ Alice's      │      │ Bob's        │      │ Carol's      │      │
│  │ Sunwell      │      │ Sunwell      │      │ Sunwell      │      │
│  │              │      │              │      │              │      │
│  │ + Personal   │      │ + Personal   │      │ + Personal   │      │
│  │   prefs      │      │   prefs      │      │   prefs      │      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
│                                                                    │
│  Alice decides OAuth → Team Knowledge → Bob's & Carol's Sunwell    │
│  Carol hits Redis wall → Team Knowledge → Alice & Bob warned       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### What Team Intelligence Enables

| Before (Individual) | After (Team) |
|---------------------|--------------|
| Decision discovered per-person | Decision learned once, shared to all |
| Patterns vary by developer | Team patterns enforced consistently |
| Failures repeated across team | Failure learned once, prevents repeats |
| Onboarding takes weeks | New member inherits team knowledge instantly |
| Knowledge leaves with developer | Knowledge persists in repository |

### Real-World Scenario

```
Friday:
  Alice: "sunwell, should we use Redis for caching?"
  Alice's Sunwell: "Let me research..." [30 minutes]
  Alice's Sunwell: "Recommendation: LRU cache. Redis adds complexity."
  Alice: "Sounds good, let's go with LRU"
  → Decision recorded and synced to team knowledge

Monday:
  Bob (new team member): "sunwell, add Redis caching to user service"
  Bob's Sunwell: "⚠️ Team decision (Alice, Friday):
                  We chose LRU cache over Redis.
                  Rationale: Redis adds operational complexity.
                  
                  This decision has been applied 3 times since Friday.
                  
                  Options:
                  1. Use LRU cache (matching team decision)
                  2. Override for this case (I'll record why)
                  3. Propose changing the team decision"

Bob just saved 30 minutes AND stayed consistent with the team.
```

---

## Goals and Non-Goals

### Goals

1. **Share architectural decisions** — Team-wide decisions visible to all instances
2. **Sync failure patterns** — Failures discovered by one prevent others from repeating
3. **Enforce team patterns** — Code style and conventions enforced consistently
4. **Preserve ownership knowledge** — Who owns what, who to ask about what
5. **Git-native synchronization** — No additional infrastructure; works with existing workflows
6. **Conflict resolution** — Handle contradicting decisions gracefully
7. **Privacy boundaries** — Personal preferences stay local; team knowledge is shared
8. **Instant onboarding** — New team members inherit accumulated knowledge

### Non-Goals

1. **Real-time sync** — Git-based means eventual consistency (minutes, not seconds)
2. **Cross-repository sharing** — Team intelligence is per-repository
3. **Centralized server** — No Sunwell cloud service; everything is local + git
4. **Conversation sharing** — Personal conversations stay private (RFC-013/014)
5. **Automatic conflict resolution** — Conflicts require human decision
6. **Access control** — Everyone with repo access sees team intelligence (use git permissions)
7. **Analytics/dashboards** — No team-wide reporting in this RFC

---

## Design Alternatives Considered

### Option A: Git-Based Synchronization (Recommended)

Store team knowledge in `.sunwell/team/` as JSONL files committed to the repository. Synchronization happens via standard git operations (pull/push).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OPTION A: GIT-BASED                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Storage: .sunwell/team/*.jsonl (committed to git)                          │
│  Sync: git pull / git push                                                  │
│  Conflict Resolution: Standard git merge + AI-assisted resolution           │
│                                                                             │
│  Advantages:                                                                │
│  + Zero infrastructure — uses existing git workflows                        │
│  + Audit trail via git history                                              │
│  + Works offline                                                            │
│  + Branch-aware (feature branch = isolated decisions)                       │
│  + PR review for decision changes                                           │
│                                                                             │
│  Disadvantages:                                                             │
│  - Eventual consistency (minutes, not seconds)                              │
│  - Merge conflicts in JSONL files                                           │
│  - Requires team to commit .sunwell/ directory                              │
│  - No real-time notifications                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Option B: Centralized Server (Rejected)

Run a Sunwell server that all team members connect to for real-time sync.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OPTION B: CENTRALIZED SERVER                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Storage: Server database (PostgreSQL/SQLite)                               │
│  Sync: WebSocket/HTTP API                                                   │
│  Conflict Resolution: Server-side with timestamps                           │
│                                                                             │
│  Advantages:                                                                │
│  + Real-time sync (milliseconds)                                            │
│  + No git conflicts                                                         │
│  + Centralized access control                                               │
│  + Push notifications                                                       │
│                                                                             │
│  Disadvantages:                                                             │
│  - Requires infrastructure (server, database)                               │
│  - Single point of failure                                                  │
│  - Network dependency                                                       │
│  - No offline support                                                       │
│  - Conflicts with "local-first" philosophy                                  │
│  - Authentication/authorization complexity                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Rejection reason**: Centralized server conflicts with Sunwell's core "local-first, no cloud dependency" philosophy. It adds infrastructure complexity and a single point of failure. Git-based sync leverages existing workflows and keeps everything local.

### Option C: Git Submodule for Shared Knowledge (Rejected)

Store team knowledge in a separate git repository, linked as a submodule.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OPTION C: GIT SUBMODULE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Storage: Separate repo (sunwell-team-knowledge) as submodule               │
│  Sync: git submodule update                                                 │
│  Conflict Resolution: Isolated repo = simpler merges                        │
│                                                                             │
│  Advantages:                                                                │
│  + Clean separation of code vs knowledge                                    │
│  + Can share across multiple repos                                          │
│  + Independent versioning                                                   │
│                                                                             │
│  Disadvantages:                                                             │
│  - Submodule complexity (many developers struggle with them)                │
│  - Extra repository to manage                                               │
│  - Decisions disconnected from the code they apply to                       │
│  - Cross-repo goal: explicitly out of scope for this RFC                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Rejection reason**: Git submodules add complexity that outweighs benefits for single-repo teams. Cross-repository sharing is future work — this RFC focuses on per-repository team intelligence.

### Recommendation

**Option A (Git-Based)** is recommended because:

1. **Zero infrastructure** — No server to deploy or maintain
2. **Leverages existing workflows** — Teams already use git for code review
3. **Audit trail** — Git history shows who changed what decision and when
4. **Offline-capable** — Works without network; syncs when connected
5. **Branch-aware** — Feature branches can have experimental decisions

The tradeoff of eventual consistency (minutes vs seconds) is acceptable because:
- Team decisions are not latency-sensitive
- Conflicts are rare (decisions are append-mostly)
- Git merge conflicts can be auto-resolved for compatible changes

---

## Relationship to RFC-045 (Personal vs Team Knowledge)

RFC-045 introduced `Decision` for **personal** decisions stored locally. RFC-052 introduces `TeamDecision` for **shared** decisions stored in git. These are complementary, not conflicting.

### Storage Model

```
.sunwell/
├── intelligence/            # RFC-045: Personal knowledge (GITIGNORED)
│   ├── decisions.jsonl      # Personal decisions
│   ├── failures.jsonl       # Personal failure memory
│   └── patterns.yaml        # Personal style preferences
│
├── team/                    # RFC-052: Team knowledge (GIT-TRACKED)
│   ├── decisions.jsonl      # Team decisions
│   ├── failures.jsonl       # Team failure patterns
│   ├── patterns.yaml        # Enforced team patterns
│   └── ownership.yaml       # Code ownership map
│
├── personal/                # RFC-052: Personal preferences (GITIGNORED)
│   ├── preferences.yaml     # Communication style, verbosity
│   └── local-overrides.yaml # Personal overrides of team patterns
│
└── sessions/                # RFC-013: Conversation history (GITIGNORED)
```

### Decision Type Relationship

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DECISION TYPE HIERARCHY                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  RFC-045 Decision (personal)           RFC-052 TeamDecision (shared)        │
│  ════════════════════════════          ═════════════════════════════        │
│  id: str                               id: str                              │
│  category: str                         category: str                        │
│  question: str                         question: str                        │
│  choice: str                           choice: str                          │
│  rejected: tuple[RejectedOption]       rejected: tuple[RejectedOption]      │
│  rationale: str                        rationale: str                       │
│  confidence: float                     confidence: float  ← ADDED           │
│  timestamp: datetime                   timestamp: datetime                  │
│  supersedes: str | None                supersedes: str | None               │
│  ──────────────────────────            ──────────────────────────           │
│  session_id: str   (personal)          author: str       (team)             │
│  context: str      (personal)          endorsements: tuple[str]             │
│  source: "conversation"|"bootstrap"    applies_until: datetime | None       │
│  metadata: dict | None                 tags: tuple[str]                     │
│                                                                             │
│  Storage: .sunwell/intelligence/       Storage: .sunwell/team/              │
│  Sharing: Never                        Sharing: Git commit                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Promotion Flow (Personal → Team)

When a personal decision should become team-wide:

```python
# User: "This decision should apply to the whole team"
# Sunwell promotes personal → team

personal_decision: Decision = ...  # From RFC-045

team_decision = TeamDecision(
    id=personal_decision.id,
    category=personal_decision.category,
    question=personal_decision.question,
    choice=personal_decision.choice,
    rejected=personal_decision.rejected,
    rationale=personal_decision.rationale,
    confidence=personal_decision.confidence,
    timestamp=datetime.now(),
    supersedes=None,
    # Team-specific fields
    author=get_git_user_email(),
    endorsements=(),  # Author is implicit first endorser
    applies_until=None,
    tags=(),
)

await team_store.record_decision(team_decision)
# → Commits to .sunwell/team/decisions.jsonl
# → Personal decision remains in .sunwell/intelligence/ as local reference
```

### Query Priority

When looking up decisions, Sunwell checks in order:

1. **Team decisions** (authoritative for the project)
2. **Personal decisions** (local overrides or not-yet-shared)
3. **Bootstrap decisions** (inferred from code analysis)

```python
async def find_relevant_decision(self, query: str) -> Decision | TeamDecision | None:
    # Team takes precedence
    team_decisions = await self.team.find_relevant_decisions(query)
    if team_decisions:
        return team_decisions[0]
    
    # Fall back to personal
    personal_decisions = await self.personal.find_relevant_decisions(query)
    if personal_decisions:
        return personal_decisions[0]
    
    return None
```

---

## Design Overview

### Layered Knowledge Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KNOWLEDGE LAYERS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 3: PERSONAL (local only, .gitignore'd)                         │  │
│  │  ───────────────────────────────────────────────────────────────────  │  │
│  │  • Explanation verbosity preferences                                  │  │
│  │  • Personal shortcuts and aliases                                     │  │
│  │  • Communication style (terse vs detailed)                            │  │
│  │  • Session history (RFC-013 Simulacrum)                               │  │
│  │                                                                       │  │
│  │  Storage: .sunwell/personal/ (gitignored)                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 2: TEAM (git-synchronized, committed)                          │  │
│  │  ───────────────────────────────────────────────────────────────────  │  │
│  │  • Architectural decisions                                            │  │
│  │  • Failure patterns (team-wide)                                       │  │
│  │  • Code conventions and patterns                                      │  │
│  │  • File/module ownership                                              │  │
│  │  • Dependency policies                                                │  │
│  │                                                                       │  │
│  │  Storage: .sunwell/team/ (committed to git)                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 1: PROJECT (git-synchronized, auto-generated)                  │  │
│  │  ───────────────────────────────────────────────────────────────────  │  │
│  │  • Codebase graph (call graph, dependencies)                          │  │
│  │  • Inferred patterns from code analysis                               │  │
│  │  • Test coverage maps                                                 │  │
│  │  • Complexity hotspots                                                │  │
│  │                                                                       │  │
│  │  Storage: .sunwell/project/ (can be regenerated)                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Synchronization Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GIT-BASED SYNCHRONIZATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Alice's Machine                                Bob's Machine               │
│  ─────────────────                              ─────────────────           │
│                                                                             │
│  1. Alice makes decision                                                    │
│     ↓                                                                       │
│  2. Sunwell records to .sunwell/team/decisions.jsonl                        │
│     ↓                                                                       │
│  3. Alice commits: "sunwell: record OAuth decision"                         │
│     ↓                                                                       │
│  4. Alice pushes to remote                                                  │
│                      ↓                                                      │
│                   [Remote Repository]                                       │
│                      ↓                                                      │
│  5. Bob pulls latest                            ← git pull                  │
│     ↓                                                                       │
│  6. Bob's Sunwell detects change                                            │
│     ↓                                                                       │
│  7. Bob's Sunwell loads new decision                                        │
│     ↓                                                                       │
│  8. Bob asks similar question → gets team's answer                          │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Conflict Scenario:                                                         │
│                                                                             │
│  Alice: "Use PostgreSQL"      Bob: "Use MySQL" (same time, different branch)│
│     ↓                            ↓                                          │
│  Both commit to .sunwell/team/decisions.jsonl                               │
│     ↓                            ↓                                          │
│  Git merge conflict on decisions.jsonl                                      │
│     ↓                                                                       │
│  Sunwell detects: "⚠️ Conflicting decisions detected"                       │
│     ↓                                                                       │
│  Team resolves in PR review (human decides)                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Storage Structure

```
.sunwell/
├── .gitignore               # Ignores personal/, intelligence/, sessions/
│
├── team/                    # ← GIT TRACKED (RFC-052: shared team knowledge)
│   ├── decisions.jsonl      # Team architectural decisions
│   ├── failures.jsonl       # Team failure patterns
│   ├── patterns.yaml        # Enforced code patterns
│   ├── ownership.yaml       # File/module ownership map
│   ├── policies.yaml        # Team policies (dependency, testing, etc.)
│   └── vocabulary.yaml      # Domain terminology
│
├── project/                 # ← GIT TRACKED (auto-generated, shareable)
│   ├── graph.pickle         # Codebase graph (can regenerate)
│   ├── embeddings.npz       # Function embeddings
│   └── index.json           # Symbol index
│
├── intelligence/            # ← GITIGNORED (RFC-045: personal intelligence)
│   ├── decisions.jsonl      # Personal decisions (not shared)
│   ├── failures.jsonl       # Personal failure memory
│   ├── patterns.yaml        # Personal style preferences
│   └── embeddings.json      # Personal decision embeddings
│
├── personal/                # ← GITIGNORED (RFC-052: personal preferences)
│   ├── preferences.yaml     # Communication style, verbosity
│   └── local-overrides.yaml # Personal overrides of team patterns
│
├── sessions/                # ← GITIGNORED (RFC-013: conversation history)
│   ├── hot/
│   ├── warm/
│   └── cold/
│
└── config.yaml              # Mix of shared and personal settings
```

**Key distinction**:
- `.sunwell/team/decisions.jsonl` → Shared via git (TeamDecision)
- `.sunwell/intelligence/decisions.jsonl` → Local only (RFC-045 Decision)

---

## Components

### 1. Team Knowledge Store

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum


class KnowledgeScope(Enum):
    """Where knowledge is stored and shared."""
    
    PERSONAL = "personal"   # Local only, gitignored
    TEAM = "team"           # Git-tracked, shared
    PROJECT = "project"     # Git-tracked, auto-generated


@dataclass(frozen=True, slots=True)
class RejectedOption:
    """An option that was considered but rejected.
    
    Shared type with RFC-045 Decision.rejected for compatibility.
    """
    
    option: str
    """What was rejected: 'Redis caching'."""
    
    reason: str
    """Why it was rejected: 'Too much operational complexity'."""
    
    might_reconsider_when: str | None = None
    """Conditions that might change this: 'If we need sub-ms latency'."""


@dataclass(frozen=True, slots=True)
class TeamDecision:
    """An architectural decision shared across the team.
    
    Related to RFC-045 Decision but with team-specific fields.
    Can be promoted from personal Decision via KnowledgePropagator.
    """
    
    id: str
    """Unique identifier (hash of context + choice)."""
    
    category: str
    """Category: 'database', 'auth', 'framework', 'pattern', etc."""
    
    question: str
    """What decision was being made."""
    
    choice: str
    """What was chosen."""
    
    rejected: tuple[RejectedOption, ...]
    """Options that were considered but rejected."""
    
    rationale: str
    """Why this choice was made."""
    
    confidence: float
    """How confident the team is this is the right choice (0.0-1.0).
    
    Consistent with RFC-045 Decision.confidence for interoperability.
    """
    
    # === Team Metadata ===
    
    author: str
    """Who made this decision (git username or email)."""
    
    timestamp: datetime
    """When decision was made."""
    
    supersedes: str | None = None
    """ID of decision this replaces (if changed)."""
    
    endorsements: tuple[str, ...] = ()
    """Team members who endorsed this decision."""
    
    applies_until: datetime | None = None
    """Expiration date for temporary decisions."""
    
    tags: tuple[str, ...] = ()
    """Tags for categorization and search."""


@dataclass(frozen=True, slots=True)
class TeamFailure:
    """A failure pattern shared across the team."""
    
    id: str
    """Unique identifier."""
    
    description: str
    """What approach failed."""
    
    error_type: str
    """Type of failure."""
    
    root_cause: str
    """Why it failed."""
    
    prevention: str
    """How to avoid this in the future."""
    
    # === Team Metadata ===
    
    author: str
    """Who discovered this failure."""
    
    timestamp: datetime
    """When failure was recorded."""
    
    occurrences: int = 1
    """How many times this has been hit across team."""
    
    affected_files: tuple[str, ...] = ()
    """Files/modules where this failure applies."""


@dataclass
class TeamPatterns:
    """Enforced code patterns for the team."""
    
    naming_conventions: dict[str, str]
    """{'function': 'snake_case', 'class': 'PascalCase'}"""
    
    import_style: Literal["absolute", "relative", "mixed"]
    """Enforced import style."""
    
    type_annotation_level: Literal["none", "public", "all"]
    """Required type annotation level."""
    
    docstring_style: Literal["google", "numpy", "sphinx", "none"]
    """Enforced docstring format."""
    
    test_requirements: dict[str, str]
    """{'new_functions': 'required', 'bug_fixes': 'required'}"""
    
    # === Enforcement ===
    
    enforcement_level: Literal["suggest", "warn", "enforce"]
    """How strictly to apply patterns."""
    
    exceptions: dict[str, str]
    """Paths exempt from specific patterns."""


@dataclass
class TeamOwnership:
    """Ownership mapping for files and modules."""
    
    # path_pattern → owner(s)
    owners: dict[str, list[str]]
    """{'src/billing/*': ['alice', 'bob'], 'src/auth/*': ['carol']}"""
    
    # owner → areas of expertise
    expertise: dict[str, list[str]]
    """{'alice': ['payments', 'billing'], 'bob': ['auth', 'security']}"""
    
    # Required reviewers for paths
    required_reviewers: dict[str, list[str]]
    """{'src/billing/*': ['alice']}"""


class TeamKnowledgeStore:
    """Manages team-shared knowledge.
    
    All team knowledge is stored in .sunwell/team/ and committed to git.
    Changes are detected via git status/diff.
    """
    
    def __init__(self, root: Path):
        self.root = root
        self.team_dir = root / ".sunwell" / "team"
        self.team_dir.mkdir(parents=True, exist_ok=True)
        
        self._decisions_path = self.team_dir / "decisions.jsonl"
        self._failures_path = self.team_dir / "failures.jsonl"
        self._patterns_path = self.team_dir / "patterns.yaml"
        self._ownership_path = self.team_dir / "ownership.yaml"
    
    # === Decisions ===
    
    async def record_decision(
        self,
        decision: TeamDecision,
        auto_commit: bool = True,
    ) -> None:
        """Record a team decision.
        
        If auto_commit is True, commits the change to git.
        """
        # Append to decisions file
        async with aiofiles.open(self._decisions_path, "a") as f:
            await f.write(json.dumps(asdict(decision), default=str) + "\n")
        
        if auto_commit:
            await self._commit(
                f"sunwell: record decision — {decision.question[:50]}",
                [self._decisions_path],
            )
    
    async def get_decisions(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[TeamDecision]:
        """Get team decisions, optionally filtered."""
        decisions = await self._load_decisions()
        
        if category:
            decisions = [d for d in decisions if d.category == category]
        
        if active_only:
            now = datetime.now()
            decisions = [
                d for d in decisions
                if d.supersedes is None and (d.applies_until is None or d.applies_until > now)
            ]
        
        return decisions
    
    async def find_relevant_decisions(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[TeamDecision]:
        """Find decisions relevant to a query using embeddings."""
        # Use embedding similarity search
        decisions = await self.get_decisions()
        # ... embedding-based retrieval ...
        return decisions[:top_k]
    
    async def check_contradiction(
        self,
        proposed_choice: str,
        category: str,
    ) -> TeamDecision | None:
        """Check if proposed choice contradicts existing team decision."""
        decisions = await self.get_decisions(category=category)
        
        for decision in decisions:
            # Check if proposed choice was previously rejected
            for rejected in decision.rejected:
                if self._similar(proposed_choice, rejected.option):
                    return decision
        
        return None
    
    # === Failures ===
    
    async def record_failure(
        self,
        failure: TeamFailure,
        auto_commit: bool = True,
    ) -> None:
        """Record a team failure pattern."""
        # Check for existing similar failure (increment occurrence)
        existing = await self._find_similar_failure(failure)
        if existing:
            # Update occurrence count
            updated = dataclasses.replace(existing, occurrences=existing.occurrences + 1)
            await self._update_failure(updated)
        else:
            # Append new failure
            async with aiofiles.open(self._failures_path, "a") as f:
                await f.write(json.dumps(asdict(failure), default=str) + "\n")
        
        if auto_commit:
            await self._commit(
                f"sunwell: record failure — {failure.description[:50]}",
                [self._failures_path],
            )
    
    async def check_similar_failures(
        self,
        proposed_approach: str,
    ) -> list[TeamFailure]:
        """Check if proposed approach matches past team failures."""
        failures = await self._load_failures()
        similar = []
        
        for failure in failures:
            if self._similar(proposed_approach, failure.description):
                similar.append(failure)
        
        return similar
    
    # === Patterns ===
    
    async def get_patterns(self) -> TeamPatterns:
        """Get team code patterns."""
        if not self._patterns_path.exists():
            return TeamPatterns(
                naming_conventions={},
                import_style="absolute",
                type_annotation_level="public",
                docstring_style="google",
                test_requirements={},
                enforcement_level="suggest",
                exceptions={},
            )
        
        data = yaml.safe_load(self._patterns_path.read_text())
        return TeamPatterns(**data)
    
    async def update_patterns(
        self,
        patterns: TeamPatterns,
        auto_commit: bool = True,
    ) -> None:
        """Update team patterns."""
        self._patterns_path.write_text(yaml.dump(asdict(patterns)))
        
        if auto_commit:
            await self._commit(
                "sunwell: update team patterns",
                [self._patterns_path],
            )
    
    # === Ownership ===
    
    async def get_ownership(self) -> TeamOwnership:
        """Get file/module ownership mapping."""
        if not self._ownership_path.exists():
            return TeamOwnership(owners={}, expertise={}, required_reviewers={})
        
        data = yaml.safe_load(self._ownership_path.read_text())
        return TeamOwnership(**data)
    
    async def get_owners(self, file_path: Path) -> list[str]:
        """Get owners for a specific file."""
        ownership = await self.get_ownership()
        
        for pattern, owners in ownership.owners.items():
            if self._path_matches(file_path, pattern):
                return owners
        
        return []
    
    # === Git Operations ===
    
    async def _commit(self, message: str, files: list[Path]) -> None:
        """Stage and commit changes."""
        for file in files:
            await run_git(self.root, ["add", str(file.relative_to(self.root))])
        
        await run_git(self.root, ["commit", "-m", message])
    
    async def sync(self) -> SyncResult:
        """Sync team knowledge with remote.
        
        1. Pull latest changes
        2. Detect conflicts
        3. Report new knowledge from team
        """
        # Pull latest
        try:
            await run_git(self.root, ["pull", "--rebase"])
        except subprocess.CalledProcessError as e:
            if "CONFLICT" in str(e.stderr):
                return SyncResult(
                    success=False,
                    conflicts=await self._detect_conflicts(),
                )
            raise
        
        # Detect new knowledge from team
        new_decisions = await self._detect_new_decisions()
        new_failures = await self._detect_new_failures()
        
        return SyncResult(
            success=True,
            new_decisions=new_decisions,
            new_failures=new_failures,
            conflicts=[],
        )
    
    async def _detect_conflicts(self) -> list[KnowledgeConflict]:
        """Detect conflicts in team knowledge files."""
        conflicts = []
        
        for path in [self._decisions_path, self._failures_path]:
            if path.exists():
                content = path.read_text()
                if "<<<<<<" in content or "======" in content:
                    conflicts.append(KnowledgeConflict(
                        file=path,
                        type="merge_conflict",
                    ))
        
        return conflicts
```

---

### 2. Conflict Resolution

```python
@dataclass(frozen=True, slots=True)
class KnowledgeConflict:
    """A conflict in team knowledge."""
    
    file: Path
    """File with conflict."""
    
    type: Literal["merge_conflict", "decision_contradiction", "pattern_override"]
    """Type of conflict."""
    
    local_version: str | None = None
    """Local version of conflicting content."""
    
    remote_version: str | None = None
    """Remote version of conflicting content."""
    
    suggested_resolution: str | None = None
    """AI-suggested resolution."""


class ConflictResolver:
    """Resolves conflicts in team knowledge.
    
    Strategies:
    1. Auto-merge compatible changes (non-conflicting lines)
    2. Prefer newer decision (timestamp-based)
    3. Escalate true conflicts for human resolution
    """
    
    def __init__(self, store: TeamKnowledgeStore):
        self.store = store
    
    async def resolve_decision_conflict(
        self,
        local: TeamDecision,
        remote: TeamDecision,
    ) -> TeamDecision | KnowledgeConflict:
        """Attempt to resolve conflicting decisions.
        
        Resolution strategies:
        1. If same question, different answers → true conflict (escalate)
        2. If one supersedes other → use superseding decision
        3. If different questions → both valid (merge)
        """
        # Same question?
        if self._same_question(local.question, remote.question):
            # Same answer? → merge endorsements
            if local.choice == remote.choice:
                return dataclasses.replace(
                    local if local.timestamp > remote.timestamp else remote,
                    endorsements=tuple(set(local.endorsements) | set(remote.endorsements)),
                )
            
            # Different answers → true conflict
            return KnowledgeConflict(
                file=self.store._decisions_path,
                type="decision_contradiction",
                local_version=f"{local.choice} (by {local.author})",
                remote_version=f"{remote.choice} (by {remote.author})",
                suggested_resolution=self._suggest_decision_resolution(local, remote),
            )
        
        # Different questions → both valid
        return local  # Both will be kept
    
    def _suggest_decision_resolution(
        self,
        local: TeamDecision,
        remote: TeamDecision,
    ) -> str:
        """Suggest resolution for conflicting decisions."""
        if local.timestamp > remote.timestamp:
            newer, older = local, remote
        else:
            newer, older = remote, local
        
        return (
            f"Conflict: '{local.question}'\n"
            f"  {older.author} chose: {older.choice}\n"
            f"  {newer.author} chose: {newer.choice}\n\n"
            f"Suggestion: Discuss with team. Consider:\n"
            f"  1. Is one choice clearly better for the use case?\n"
            f"  2. Can both approaches coexist (conditional decision)?\n"
            f"  3. Should this be a per-developer preference?\n"
        )
    
    async def resolve_merge_conflict(self, path: Path) -> bool:
        """Attempt to resolve git merge conflict in knowledge file.
        
        For JSONL files, we can often auto-merge by keeping all unique entries.
        """
        if not path.exists():
            return False
        
        content = path.read_text()
        if "<<<<<<" not in content:
            return True  # No conflict
        
        # Parse conflict markers
        lines = content.split("\n")
        resolved_lines = []
        in_conflict = False
        local_lines = []
        remote_lines = []
        
        for line in lines:
            if line.startswith("<<<<<<<"):
                in_conflict = True
                local_lines = []
            elif line.startswith("======="):
                remote_lines = []
            elif line.startswith(">>>>>>>"):
                in_conflict = False
                # Merge: keep all unique entries
                all_entries = set(local_lines) | set(remote_lines)
                resolved_lines.extend(all_entries)
            elif in_conflict:
                if "=======" not in content[:content.index(line)]:
                    local_lines.append(line)
                else:
                    remote_lines.append(line)
            else:
                resolved_lines.append(line)
        
        # Write resolved content
        path.write_text("\n".join(resolved_lines))
        return True
```

---

### 3. Knowledge Propagation

```python
class KnowledgePropagator:
    """Propagates knowledge between layers.
    
    Flow:
    1. Personal decision → prompt to share with team
    2. Team decision → propagate to all local instances
    3. Project analysis → available to team
    """
    
    def __init__(
        self,
        team_store: TeamKnowledgeStore,
        personal_store: PersonalKnowledgeStore,
    ):
        self.team_store = team_store
        self.personal_store = personal_store
    
    async def promote_to_team(
        self,
        decision: Decision,
        author: str,
    ) -> TeamDecision:
        """Promote a personal decision to team knowledge.
        
        Called when user confirms a decision should be shared.
        """
        team_decision = TeamDecision(
            id=decision.id,
            category=decision.category,
            question=decision.question,
            choice=decision.choice,
            rejected=decision.rejected,
            rationale=decision.rationale,
            author=author,
            timestamp=datetime.now(),
        )
        
        await self.team_store.record_decision(team_decision)
        return team_decision
    
    async def check_team_knowledge(
        self,
        query: str,
    ) -> TeamKnowledgeContext:
        """Check team knowledge for relevant context.
        
        Called before any decision or action to surface team wisdom.
        """
        relevant_decisions = await self.team_store.find_relevant_decisions(query)
        similar_failures = await self.team_store.check_similar_failures(query)
        patterns = await self.team_store.get_patterns()
        
        return TeamKnowledgeContext(
            decisions=relevant_decisions,
            failures=similar_failures,
            patterns=patterns,
        )
    
    async def on_git_pull(self) -> list[TeamKnowledgeUpdate]:
        """Handle new team knowledge after git pull.
        
        Returns list of new knowledge for user notification.
        """
        # Detect changes in team knowledge files
        result = await self.team_store.sync()
        
        updates = []
        
        for decision in result.new_decisions:
            updates.append(TeamKnowledgeUpdate(
                type="decision",
                summary=f"New team decision: {decision.question}",
                author=decision.author,
                detail=f"Choice: {decision.choice}",
            ))
        
        for failure in result.new_failures:
            updates.append(TeamKnowledgeUpdate(
                type="failure",
                summary=f"New failure pattern: {failure.description}",
                author=failure.author,
                detail=f"Prevention: {failure.prevention}",
            ))
        
        return updates


@dataclass(frozen=True, slots=True)
class TeamKnowledgeUpdate:
    """Notification of new team knowledge."""
    
    type: Literal["decision", "failure", "pattern", "ownership"]
    summary: str
    author: str
    detail: str


@dataclass
class TeamKnowledgeContext:
    """Team knowledge relevant to current context."""
    
    decisions: list[TeamDecision]
    failures: list[TeamFailure]
    patterns: TeamPatterns
    
    def format_for_prompt(self) -> str:
        """Format team knowledge for inclusion in LLM prompt."""
        parts = []
        
        if self.decisions:
            parts.append("## Team Decisions\n")
            for d in self.decisions:
                parts.append(f"- **{d.question}**: {d.choice} (by {d.author})")
                if d.rationale:
                    parts.append(f"  Rationale: {d.rationale}")
        
        if self.failures:
            parts.append("\n## Team Failure Patterns\n")
            for f in self.failures:
                parts.append(f"- ⚠️ **{f.description}** (hit {f.occurrences}x)")
                parts.append(f"  Prevention: {f.prevention}")
        
        if self.patterns.enforcement_level != "none":
            parts.append("\n## Team Patterns\n")
            parts.append(f"- Naming: {self.patterns.naming_conventions}")
            parts.append(f"- Docstrings: {self.patterns.docstring_style}")
        
        return "\n".join(parts)
```

---

### 4. Onboarding Support

```python
class TeamOnboarding:
    """Helps new team members understand accumulated knowledge.
    
    When a new developer runs 'sunwell init', they get:
    1. Summary of team decisions
    2. Key failure patterns to avoid
    3. Code patterns to follow
    4. Ownership map
    """
    
    def __init__(self, store: TeamKnowledgeStore):
        self.store = store
    
    async def generate_onboarding_summary(self) -> OnboardingSummary:
        """Generate onboarding summary for new team member."""
        decisions = await self.store.get_decisions()
        failures = await self.store.get_failures()
        patterns = await self.store.get_patterns()
        ownership = await self.store.get_ownership()
        
        # Categorize decisions by topic
        decision_by_category = defaultdict(list)
        for d in decisions:
            decision_by_category[d.category].append(d)
        
        # Find high-occurrence failures
        critical_failures = sorted(failures, key=lambda f: -f.occurrences)[:5]
        
        return OnboardingSummary(
            total_decisions=len(decisions),
            decisions_by_category=dict(decision_by_category),
            critical_failures=critical_failures,
            patterns=patterns,
            ownership_summary=self._summarize_ownership(ownership),
            top_contributors=self._get_top_contributors(decisions),
        )
    
    def _summarize_ownership(self, ownership: TeamOwnership) -> dict[str, str]:
        """Create human-readable ownership summary."""
        summary = {}
        for path, owners in ownership.owners.items():
            summary[path] = f"Owned by: {', '.join(owners)}"
        return summary
    
    def _get_top_contributors(self, decisions: list[TeamDecision]) -> list[str]:
        """Get team members who contributed most decisions."""
        author_counts = Counter(d.author for d in decisions)
        return [author for author, _ in author_counts.most_common(5)]


@dataclass
class OnboardingSummary:
    """Summary for new team member onboarding."""
    
    total_decisions: int
    decisions_by_category: dict[str, list[TeamDecision]]
    critical_failures: list[TeamFailure]
    patterns: TeamPatterns
    ownership_summary: dict[str, str]
    top_contributors: list[str]
    
    def format_welcome_message(self) -> str:
        """Format as welcome message for new team member."""
        return f"""
🎉 Welcome to the team! Here's what Sunwell has learned:

📋 **Team Decisions**: {self.total_decisions} recorded
   Categories: {', '.join(self.decisions_by_category.keys())}
   
⚠️ **Critical Failures to Avoid**:
{self._format_failures()}

📝 **Code Patterns**:
   - Naming: {self.patterns.naming_conventions}
   - Docstrings: {self.patterns.docstring_style}
   - Type hints: {self.patterns.type_annotation_level}

👥 **Key Contributors**: {', '.join(self.top_contributors)}

Run `sunwell team decisions` to see all team decisions.
Run `sunwell team failures` to see failure patterns.
"""
    
    def _format_failures(self) -> str:
        lines = []
        for f in self.critical_failures[:3]:
            lines.append(f"   - {f.description} ({f.occurrences}x)")
        return "\n".join(lines)
```

---

### 5. Integration with Project Intelligence (RFC-045)

```python
class UnifiedIntelligence:
    """Unifies personal and team intelligence.
    
    Priority order for lookups:
    1. Team decisions (shared, authoritative)
    2. Personal decisions (local override if allowed)
    3. Project analysis (auto-generated)
    """
    
    def __init__(
        self,
        team_store: TeamKnowledgeStore,
        personal_store: PersonalKnowledgeStore,  # From RFC-045
        project_analyzer: CodebaseAnalyzer,       # From RFC-045
    ):
        self.team = team_store
        self.personal = personal_store
        self.project = project_analyzer
    
    async def find_relevant_decision(
        self,
        query: str,
    ) -> Decision | TeamDecision | None:
        """Find most relevant decision for a query.
        
        Checks team knowledge first, then personal.
        """
        # Check team decisions first (authoritative)
        team_decisions = await self.team.find_relevant_decisions(query)
        if team_decisions:
            return team_decisions[0]
        
        # Fall back to personal decisions
        personal_decisions = await self.personal.find_relevant_decisions(query)
        if personal_decisions:
            return personal_decisions[0]
        
        return None
    
    async def check_approach(
        self,
        proposed_approach: str,
    ) -> ApproachCheck:
        """Check if proposed approach has known issues.
        
        Combines team and personal failure knowledge.
        """
        team_failures = await self.team.check_similar_failures(proposed_approach)
        personal_failures = await self.personal.check_similar_failures(proposed_approach)
        team_decision = await self.team.check_contradiction(proposed_approach, "architecture")
        
        warnings = []
        
        if team_failures:
            for f in team_failures:
                warnings.append(ApproachWarning(
                    level="team",
                    message=f"Team failure ({f.occurrences}x): {f.description}",
                    prevention=f.prevention,
                ))
        
        if personal_failures:
            for f in personal_failures:
                warnings.append(ApproachWarning(
                    level="personal",
                    message=f"Personal failure: {f.description}",
                    prevention=f.root_cause,
                ))
        
        if team_decision:
            warnings.append(ApproachWarning(
                level="team",
                message=f"Contradicts team decision: {team_decision.question}",
                prevention=f"Team chose: {team_decision.choice}",
            ))
        
        return ApproachCheck(
            safe=len(warnings) == 0,
            warnings=warnings,
        )
    
    async def get_context_for_file(
        self,
        file_path: Path,
    ) -> FileContext:
        """Get all relevant context for working on a file.
        
        Combines ownership, patterns, decisions, and analysis.
        """
        owners = await self.team.get_owners(file_path)
        patterns = await self.team.get_patterns()
        
        # Find relevant decisions for this file's domain
        file_name = file_path.stem
        relevant_decisions = await self.team.find_relevant_decisions(file_name)
        
        # Get codebase graph context
        dependencies = await self.project.get_dependencies(file_path)
        dependents = await self.project.get_dependents(file_path)
        
        return FileContext(
            owners=owners,
            patterns=patterns,
            relevant_decisions=relevant_decisions,
            dependencies=dependencies,
            dependents=dependents,
        )
```

---

## Configuration

```yaml
# sunwell.yaml

team:
  enabled: true
  
  # Synchronization
  sync:
    auto_commit: true              # Commit changes automatically
    auto_push: false               # Push requires explicit action
    pull_on_start: true            # Pull team knowledge on session start
    notify_new_knowledge: true     # Notify about new team knowledge
  
  # Sharing settings
  sharing:
    decisions: true                # Share architectural decisions
    failures: true                 # Share failure patterns
    patterns: true                 # Share code patterns
    ownership: true                # Share ownership mapping
  
  # Privacy boundaries
  privacy:
    share_session_history: false   # Never share conversations
    share_personal_prefs: false    # Keep preferences local
    anonymize_failures: false      # Include author names
  
  # Conflict handling
  conflicts:
    auto_merge_compatible: true    # Auto-merge non-conflicting changes
    prefer_newer: false            # Don't auto-resolve by timestamp
    require_review: true           # Escalate true conflicts
  
  # Onboarding
  onboarding:
    show_summary_on_init: true     # Show team knowledge summary
    interactive_tour: false        # Skip interactive onboarding
  
  # Enforcement
  enforcement:
    patterns: "warn"               # suggest, warn, or enforce
    decisions: "warn"              # How strictly to apply team decisions
```

---

## CLI Integration

```bash
# Team knowledge management
sunwell team status              # Show team knowledge summary
sunwell team decisions           # List all team decisions
sunwell team decisions --category auth  # Filter by category
sunwell team failures            # List team failure patterns
sunwell team patterns            # Show enforced patterns
sunwell team ownership           # Show ownership map

# Sharing
sunwell team share               # Share pending local knowledge
sunwell team share --decision ID # Share specific decision
sunwell team promote             # Promote personal decision to team

# Synchronization
sunwell team sync                # Pull and push team knowledge
sunwell team pull                # Pull team knowledge only
sunwell team push                # Push local team changes

# Conflict resolution
sunwell team conflicts           # List unresolved conflicts
sunwell team resolve ID          # Interactive conflict resolution

# Onboarding
sunwell team onboard             # Show onboarding summary
sunwell team contributors        # List top knowledge contributors

# Audit
sunwell team audit               # Check for stale/conflicting decisions
sunwell team history             # Show team knowledge changelog
```

### Example Session

```
$ sunwell team status

📊 Team Intelligence Status

📋 Decisions: 47 recorded
   - Database: 8 decisions
   - Auth: 12 decisions
   - Architecture: 15 decisions
   - Patterns: 12 decisions
   
⚠️ Failures: 23 patterns recorded
   - Top: "Redis caching complexity" (hit 5x)
   - Top: "Async SQLAlchemy issues" (hit 3x)
   
📝 Patterns: Enforced (warn level)
   - snake_case functions
   - Google docstrings
   - Type hints on public functions
   
👥 Top Contributors:
   1. alice@team.com (18 decisions)
   2. bob@team.com (12 decisions)
   3. carol@team.com (9 decisions)

Last sync: 5 minutes ago
Pending local changes: 2 decisions

───────────────────────────────────────────────────────────────

$ sunwell team decisions --category auth

🔐 Auth Decisions (12)

1. [2026-01-15] OAuth over JWT
   Author: alice@team.com
   Choice: OAuth 2.0 with PKCE
   Rationale: "Enterprise SSO requirement, better security model"
   Rejected: JWT (stateless but no SSO), Session tokens (scalability)
   Endorsements: bob@team.com, carol@team.com
   
2. [2026-01-10] Password hashing
   Author: bob@team.com
   Choice: Argon2id
   Rationale: "Memory-hard, recommended by OWASP"
   Rejected: bcrypt (older), PBKDF2 (not memory-hard)
   
...

───────────────────────────────────────────────────────────────

$ sunwell agent "Add JWT authentication"

⚠️ Team Knowledge Alert

This approach may conflict with team decisions:

  📋 Decision: OAuth over JWT
  Author: alice@team.com (2026-01-15)
  Team chose: OAuth 2.0 with PKCE
  Rationale: "Enterprise SSO requirement"
  
  Your proposed JWT authentication was considered but rejected
  because: "stateless but no SSO support"
  
Options:
  1. Use OAuth 2.0 (matching team decision)
  2. Proceed with JWT anyway (I'll record your override)
  3. Propose changing the team decision (starts discussion)

Choose [1/2/3]: 
```

---

## Integration with Existing Systems

### With RFC-045 (Project Intelligence)

```python
# Project Intelligence now checks team knowledge first

class ProjectIntelligence:
    def __init__(
        self,
        root: Path,
        team_store: TeamKnowledgeStore | None = None,
    ):
        # ... existing init ...
        self.team = team_store or TeamKnowledgeStore(root)
        self.unified = UnifiedIntelligence(
            team_store=self.team,
            personal_store=self.decisions,
            project_analyzer=self.codebase,
        )
    
    async def get_context(self, query: str) -> ProjectContext:
        """Get unified context combining team + personal + project."""
        # Include team knowledge
        team_ctx = await self.team.check_team_knowledge(query)
        
        # ... existing personal context ...
        
        return ProjectContext(
            team_decisions=team_ctx.decisions,
            team_failures=team_ctx.failures,
            team_patterns=team_ctx.patterns,
            # ... personal context ...
        )
```

### With RFC-042 (Adaptive Agent)

```python
# Agent includes team context in decisions

class AdaptiveAgent:
    async def execute(self, goal: str) -> AsyncIterator[AgentEvent]:
        # Check team knowledge before execution
        team_ctx = await self.intelligence.unified.check_approach(goal)
        
        if team_ctx.warnings:
            yield AgentEvent(
                type="team_warning",
                data={"warnings": team_ctx.warnings},
            )
            # Wait for user confirmation on conflicts
            ...
```

### With RFC-049 (External Integration)

```python
# External events can reference team ownership

class EventProcessor:
    async def _goal_from_issue(self, event: ExternalEvent) -> Goal:
        # Find team owners for affected files
        affected_files = self._extract_files_from_issue(event)
        owners = []
        for f in affected_files:
            file_owners = await self.team_store.get_owners(f)
            owners.extend(file_owners)
        
        return Goal(
            ...
            metadata={"suggested_reviewers": list(set(owners))},
        )
```

---

## Risks and Mitigations

### Risk 1: Conflicting Decisions Across Team

**Problem**: Two developers make incompatible decisions simultaneously.

**Mitigation**:
- Git merge conflict detection
- AI-suggested resolutions
- Required PR review for decision changes
- Clear escalation path

### Risk 2: Stale Team Knowledge

**Problem**: Old decisions remain even when no longer applicable.

**Mitigation**:
- `applies_until` expiration dates
- Periodic team knowledge audit (`sunwell team audit`)
- Confidence decay over time
- Easy superseding workflow

### Risk 3: Over-Enforcement of Patterns

**Problem**: Team patterns are too strict, hindering productivity.

**Mitigation**:
- Configurable enforcement levels (suggest/warn/enforce)
- Exception paths for specific directories
- Personal override capability
- Easy feedback loop to adjust patterns

### Risk 4: Privacy Concerns

**Problem**: Developers don't want personal conversations shared.

**Mitigation**:
- Clear layer separation (team vs. personal)
- Conversations are NEVER shared (RFC-013 stays local)
- Explicit opt-in for sharing decisions
- Anonymization option for failures

### Risk 5: Git Bloat

**Problem**: Team knowledge files grow unbounded.

**Mitigation**:
- JSONL format (append-only, compactable)
- Periodic compaction of superseded decisions
- Binary files (embeddings) in `.gitignore` if regenerable

---

## Testing Strategy

### Unit Tests

```python
class TestTeamKnowledgeStore:
    async def test_records_decision(self, tmp_path):
        store = TeamKnowledgeStore(tmp_path)
        decision = TeamDecision(
            id="d1",
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rejected=(),
            rationale="Scalability",
            author="alice",
            timestamp=datetime.now(),
        )
        
        await store.record_decision(decision, auto_commit=False)
        
        decisions = await store.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].choice == "PostgreSQL"
    
    async def test_finds_contradiction(self, tmp_path):
        store = TeamKnowledgeStore(tmp_path)
        # Record decision rejecting MySQL
        decision = TeamDecision(
            id="d1",
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rejected=(RejectedOption("MySQL", "Licensing concerns"),),
            ...
        )
        await store.record_decision(decision, auto_commit=False)
        
        # Check contradiction
        conflict = await store.check_contradiction("MySQL", "database")
        assert conflict is not None
        assert conflict.choice == "PostgreSQL"


class TestConflictResolver:
    async def test_merges_endorsements(self):
        resolver = ConflictResolver(...)
        local = TeamDecision(..., endorsements=("alice",))
        remote = TeamDecision(..., endorsements=("bob",))
        
        result = await resolver.resolve_decision_conflict(local, remote)
        
        assert isinstance(result, TeamDecision)
        assert set(result.endorsements) == {"alice", "bob"}
```

### Integration Tests

```python
class TestTeamSync:
    async def test_sync_propagates_decisions(self, two_user_setup):
        """Decision by Alice is visible to Bob after sync."""
        alice_store, bob_store = two_user_setup
        
        # Alice records decision
        decision = TeamDecision(...)
        await alice_store.record_decision(decision)
        
        # Alice pushes
        await alice_store.push()
        
        # Bob pulls
        result = await bob_store.sync()
        
        assert len(result.new_decisions) == 1
        assert result.new_decisions[0].author == "alice"
```

---

## Implementation Plan

### Phase 1: Core Team Store (Week 1-2)

- [ ] `RejectedOption` shared type (compatible with RFC-045)
- [ ] `TeamDecision`, `TeamFailure` dataclasses with `confidence` field
- [ ] `TeamKnowledgeStore` with JSONL storage in `.sunwell/team/`
- [ ] Basic git operations (commit, no push/pull yet)
- [ ] Unit tests
- [ ] Storage path isolation (`.sunwell/team/` vs `.sunwell/intelligence/`)

### Phase 2: Synchronization (Week 3)

- [ ] Git pull/push integration
- [ ] Change detection after pull
- [ ] `SyncResult` with new knowledge notifications
- [ ] Basic conflict detection

### Phase 3: Conflict Resolution (Week 4)

- [ ] `ConflictResolver` with auto-merge for compatible changes
- [ ] AI-suggested resolutions
- [ ] CLI: `sunwell team conflicts`, `sunwell team resolve`
- [ ] Integration tests with simulated conflicts

### Phase 4: Knowledge Propagation (Week 5)

- [ ] `KnowledgePropagator` for personal → team promotion
- [ ] `Decision` → `TeamDecision` conversion with field mapping
- [ ] Team knowledge injection into prompts
- [ ] Warning system for contradictions
- [ ] `TeamKnowledgeContext` formatting

### Phase 4.5: Migration Support (Week 5-6)

- [ ] Migration script for existing RFC-045 decisions → team decisions
- [ ] Preserve original decision metadata in `TeamDecision.metadata`
- [ ] CLI: `sunwell team migrate --from-personal`
- [ ] Validation to prevent duplicate migrations
- [ ] Rollback support

### Phase 5: Integration (Week 6)

- [ ] Integrate with RFC-045 (`UnifiedIntelligence`)
- [ ] Integrate with RFC-042 (team warnings in agent)
- [ ] Integrate with RFC-049 (ownership in external goals)
- [ ] CLI polish: `sunwell team status`, `sunwell team decisions`

### Phase 6: Onboarding & Polish (Week 7)

- [ ] `TeamOnboarding` with summary generation
- [ ] Welcome message on `sunwell init`
- [ ] Configuration options
- [ ] Documentation
- [ ] End-to-end tests

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Decision propagation | < 1 minute | Time from commit to visibility on other machine |
| Conflict detection | 100% | All git conflicts in team files detected |
| Onboarding time reduction | 50% | Time for new member to understand codebase decisions |
| Repeated failure prevention | > 80% | Team failures caught before re-attempt |
| Team adoption | 3+ developers | Active contributors to team knowledge |

---

## Open Questions

### Q1: How to Handle Large Teams?

**Question**: Does decision volume become unmanageable with 20+ developers?

**Proposed answer**: 
- Decisions are append-only but searchable via embeddings
- Old/superseded decisions can be archived
- Categories and tags help filtering
- Summary views show only active decisions

### Q2: Multi-Repository Teams?

**Question**: Can team knowledge span multiple repositories?

**Proposed answer**: Not in this RFC. Each repository has independent team knowledge. Cross-repo sharing requires future work (possibly via git submodules or external sync).

### Q3: Enterprise SSO / Permissions?

**Question**: Can we restrict who can modify team decisions?

**Proposed answer**: Use git permissions. Team knowledge files are just files in the repo — existing branch protection rules apply.

---

## Future Work

1. **Cross-repo team knowledge** — Share decisions across organization repositories
2. **Team analytics** — Dashboard showing knowledge growth, top contributors
3. **Decision voting** — Formal process for contentious decisions
4. **Knowledge templates** — Pre-built team knowledge for common stacks
5. **Slack/Teams integration** — Notify team of new decisions via chat
6. **Compliance audit trail** — Track decision changes for regulated industries

---

## Summary

Team Intelligence enables shared knowledge across developers through:

| Component | Purpose |
|-----------|---------|
| **TeamKnowledgeStore** | Git-tracked storage for decisions, failures, patterns |
| **ConflictResolver** | Handle merge conflicts in team knowledge |
| **KnowledgePropagator** | Promote personal knowledge to team |
| **UnifiedIntelligence** | Combine team + personal + project knowledge |
| **TeamOnboarding** | Welcome new members with accumulated wisdom |

### The Result

```
Before (Individual):                After (Team Intelligence):
────────────────────                ──────────────────────────
Each dev learns independently       One learns, all benefit
Decisions repeated per person       Decisions shared instantly
New members start from zero         New members inherit knowledge
Knowledge leaves with developer     Knowledge persists in repo

Time to team alignment: weeks       Time to team alignment: minutes
```

**One team member learns it once, everyone's Sunwell knows it forever.**

---

## References

### RFCs

- RFC-045: Project Intelligence — `src/sunwell/intelligence/`
- RFC-049: External Integration — `src/sunwell/external/`
- RFC-051: Multi-Instance Coordination — `src/sunwell/parallel/`

### Implementation Files (to be created)

```
src/sunwell/team/
├── __init__.py
├── types.py              # TeamDecision, TeamFailure, TeamPatterns
├── store.py              # TeamKnowledgeStore
├── conflicts.py          # ConflictResolver
├── propagation.py        # KnowledgePropagator
├── unified.py            # UnifiedIntelligence
├── onboarding.py         # TeamOnboarding
└── config.py             # Team configuration

# Modified files
src/sunwell/intelligence/context.py    # Add team context integration
src/sunwell/adaptive/agent.py          # Add team warning injection
src/sunwell/external/processor.py      # Add ownership lookup
src/sunwell/cli/main.py                # Add 'team' command group
```

### External References

- [Architecture Decision Records (ADR)](https://adr.github.io/) — Inspiration for decision format
- [Git-based workflows](https://www.atlassian.com/git/tutorials/comparing-workflows) — Sync model inspiration
- [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) — Ownership mapping inspiration

---

*Last updated: 2026-01-19*
