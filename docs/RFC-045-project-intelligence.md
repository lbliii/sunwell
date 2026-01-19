# RFC-045: Project Intelligence — The Persistent Codebase Mind

**Status**: Draft (Revised)  
**Created**: 2026-01-19  
**Revised**: 2026-01-19  
**Authors**: Sunwell Team  
**Depends on**: RFC-013 (Hierarchical Memory), RFC-014 (Multi-Topology Memory), RFC-030 (Unified Router), RFC-036 (Artifact Planning), RFC-042 (Adaptive Agent)

---

## Summary

Project Intelligence transforms Sunwell from a stateless code assistant into a **persistent codebase mind** that remembers decisions, understands relationships, and learns preferences. While competitors like Claude Code start fresh every session, Sunwell builds cumulative understanding that compounds over time.

**Core insight**: The moat isn't better prompts or bigger context windows. It's **institutional knowledge** — the accumulated understanding that a senior engineer has about a codebase after months of working on it.

**One-liner**: Claude Code is a brilliant contractor who forgets you after every job. Sunwell is a team member who learns your codebase, remembers decisions, and gets better over time.

---

## Motivation

### The Stateless Problem

Current AI coding assistants (including Sunwell without this RFC) are **stateless**:

```
Session 1: User asks for auth implementation
  → AI suggests JWT + bcrypt
  → User says "no, we need OAuth for enterprise"
  → AI implements OAuth

Session 2: User asks to add another endpoint
  → AI suggests JWT + bcrypt again  ← FORGOT EVERYTHING
  → User: "We already decided OAuth!"
```

This happens because:
- Context windows are finite
- Sessions are isolated
- No learning persists

### What a Senior Engineer Knows

A senior engineer on the team knows:

1. **Architectural decisions** — "We use SQLAlchemy because we might migrate to Postgres"
2. **Past failures** — "We tried Redis caching but it added too much operational complexity"
3. **Code patterns** — "This team prefers functional style, explicit imports, small functions"
4. **Domain terms** — "When we say 'shard' we mean customer partition, not DB shard"
5. **Hot spots** — "billing.py is fragile; any changes need extra testing"
6. **Ownership** — "Alice owns auth, Bob owns payments, ask Carol about infra"

### The Opportunity

Sunwell already has the foundations:
- RFC-013: Hierarchical memory with HOT/WARM/COLD tiers
- RFC-014: Multi-topology memory (spatial, topological, structural)
- RFC-030: Unified router for complexity/intent classification
- RFC-042: Signal-driven adaptive execution

What's missing:
- **Decision memory** — Why we chose X over Y
- **Codebase graph** — Semantic understanding of relationships
- **Pattern learning** — Adapting to user/project style
- **Failure memory** — What didn't work and why
- **Cross-session continuity** — Same context across days/weeks

---

## Goals and Non-Goals

### Goals

1. **Persist architectural decisions** — Record why we chose X over Y, surface when relevant
2. **Build semantic codebase understanding** — Know relationships, not just file contents
3. **Learn user/project style** — Adapt to naming, structure, and communication preferences
4. **Remember failures** — Never suggest the same broken approach twice
5. **Maintain cross-session continuity** — Pick up where we left off, even weeks later
6. **Zero-config value** — Intelligence builds automatically from normal usage
7. **Privacy-first** — Local-only by default, granular opt-out, no cloud dependency

### Non-Goals

1. **Real-time code analysis** — We build graphs incrementally, not on every keystroke
2. **Replace LSP/IDE features** — Codebase graph complements, doesn't replace tree-sitter/LSP
3. **Team sync** — Multi-user intelligence sharing is future work (this RFC: single user)
4. **Learning from external codebases** — Patterns learned are project-specific only
5. **Automated decision-making** — Intelligence informs, user decides (surface conflicts, don't resolve)
6. **100% accuracy** — Pattern learning is probabilistic; explicit overrides always win

---

## Design Overview

### Two Complementary Systems

Project Intelligence is **not** a replacement for Simulacrum — it's a **complement**. They serve different purposes:

| System | Focus | Remembers | Source |
|--------|-------|-----------|--------|
| **Simulacrum** (RFC-013/014) | Conversation intelligence | What was said, learnings, dead ends | Conversations |
| **Project Intelligence** (RFC-045) | Codebase intelligence | Decisions, code structure, patterns, failures | Code + conversations |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED PROJECT CONTEXT                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SIMULACRUM (existing)              PROJECT INTELLIGENCE (new)             │
│   ══════════════════════             ═══════════════════════════            │
│   "What was said"                    "What exists & why"                    │
│                                                                             │
│   ┌────────────────────┐             ┌────────────────────┐                 │
│   │ Working Memory     │             │ Codebase Graph     │                 │
│   │ (current turns)    │             │ (call graph, deps) │                 │
│   ├────────────────────┤             ├────────────────────┤                 │
│   │ Long-term Memory   │────────────►│ Decision Memory    │                 │
│   │ (learnings, facts) │  extracts   │ (why we chose X)   │                 │
│   ├────────────────────┤             ├────────────────────┤                 │
│   │ Episodic Memory    │────────────►│ Failure Memory     │                 │
│   │ (past sessions)    │  extracts   │ (what didn't work) │                 │
│   ├────────────────────┤             ├────────────────────┤                 │
│   │ Topology Memory    │◄───────────►│ Pattern Learning   │                 │
│   │ (spatial, struct)  │  enriches   │ (user preferences) │                 │
│   └────────────────────┘             └────────────────────┘                 │
│            │                                   │                            │
│            └───────────────┬───────────────────┘                            │
│                            ▼                                                │
│                 ┌────────────────────┐                                      │
│                 │   ProjectContext   │                                      │
│                 │   (unified API)    │                                      │
│                 └────────────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Between Systems

```python
@dataclass
class ProjectContext:
    """Unified context combining Simulacrum + Project Intelligence."""
    
    # Conversation intelligence (existing)
    simulacrum: SimulacrumStore
    """RFC-013 + RFC-014: Conversation history, learnings, topology."""
    
    # Codebase intelligence (new)
    decisions: DecisionMemory
    """Architectural decisions with rationale."""
    
    codebase: CodebaseGraph
    """Semantic understanding of code structure."""
    
    patterns: PatternProfile
    """Learned user/project preferences."""
    
    failures: FailureMemory
    """Failed approaches with root cause analysis."""
    
    @classmethod
    async def load(cls, project_root: Path) -> ProjectContext:
        """Load both systems from project root."""
        return cls(
            simulacrum=SimulacrumStore(project_root / ".sunwell" / "sessions"),
            decisions=DecisionMemory(project_root / ".sunwell" / "intelligence"),
            codebase=CodebaseGraph.load(project_root / ".sunwell" / "intelligence"),
            patterns=PatternProfile.load(project_root / ".sunwell" / "intelligence"),
            failures=FailureMemory(project_root / ".sunwell" / "intelligence"),
        )
```

### Extraction: Simulacrum → Project Intelligence

When Simulacrum demotes conversation chunks, we extract durable intelligence:

```python
class IntelligenceExtractor:
    """Extract project intelligence from conversation history."""
    
    async def on_chunk_demotion(
        self,
        chunk: Chunk,
        context: ProjectContext,
    ) -> None:
        """Called when Simulacrum demotes a chunk to warm/cold tier."""
        
        # 1. Extract architectural decisions from conversation
        decisions = await self._extract_decisions(chunk)
        for decision in decisions:
            await context.decisions.record(decision)
        
        # 2. Extract failure patterns from error discussions
        failures = await self._extract_failures(chunk)
        for failure in failures:
            await context.failures.record(failure)
        
        # 3. Learn patterns from user edits/rejections
        edits = self._extract_edits(chunk)
        for edit in edits:
            context.patterns.learn_from_edit(
                original=edit.original,
                edited=edit.edited,
            )
    
    async def _extract_decisions(self, chunk: Chunk) -> list[Decision]:
        """Extract decisions from conversation turns.
        
        Looks for patterns like:
        - "Let's use X instead of Y because..."
        - "We decided on X"
        - "I chose X over Y since..."
        """
        ...
    
    async def _extract_failures(self, chunk: Chunk) -> list[FailedApproach]:
        """Extract failures from conversation turns.
        
        Looks for patterns like:
        - "That didn't work because..."
        - "Error: ..."
        - "Let's try a different approach"
        """
        ...
```

### Enrichment: Project Intelligence → Simulacrum

Project Intelligence enriches Simulacrum's topology memory:

```python
async def enrich_simulacrum_topology(
    context: ProjectContext,
) -> None:
    """Add codebase knowledge to Simulacrum's topology memory."""
    
    unified_store = context.simulacrum._unified_store
    
    # Add concept clusters from codebase graph
    for concept, locations in context.codebase.concept_clusters.items():
        for loc in locations:
            node = MemoryNode(
                content=f"Concept '{concept}' implemented here",
                location=loc,
                facets={"type": "code_concept"},
            )
            unified_store.add(node)
    
    # Add decision context as retrievable nodes
    for decision in await context.decisions.get_decisions():
        node = MemoryNode(
            content=f"Decision: {decision.question} → {decision.choice}",
            facets={
                "type": "decision",
                "category": decision.category,
            },
        )
        unified_store.add(node)
```

### Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROJECT INTELLIGENCE LAYERS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 4: LEARNED PATTERNS                                          │   │
│  │  Style preferences, naming conventions, common refactors            │   │
│  │  Updated: Continuously via implicit feedback                        │   │
│  │  Source: User edits, acceptances, rejections (from Simulacrum)      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               ▲                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 3: DECISION MEMORY                                           │   │
│  │  Why we chose X, what we rejected, rationale, context               │   │
│  │  Updated: When architectural decisions are made                     │   │
│  │  Source: Extracted from conversations (Simulacrum) + explicit       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               ▲                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 2: CODEBASE GRAPH                                            │   │
│  │  Call graph, type flow, dependencies, concept clusters, hot paths   │   │
│  │  Updated: On file changes (incremental) or full scan                │   │
│  │  Source: Static analysis (AST) + dynamic traces                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               ▲                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 1: SIMULACRUM (RFC-013 + RFC-014)                            │   │
│  │  Conversation history, working memory, episodic memory, topology    │   │
│  │  Updated: Every turn                                                │   │
│  │  Source: Conversations                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Two Systems (Not One)?

**Separation of concerns**:

| Concern | Simulacrum | Project Intelligence |
|---------|------------|---------------------|
| **Retention** | Sessions expire, compress | Decisions persist forever |
| **Source** | Conversations only | Code + conversations + traces |
| **Granularity** | Turn-level | Artifact/decision-level |
| **Retrieval** | Semantic + temporal | Semantic + structural |
| **Sharing** | Personal (per user) | Project-wide (shareable) |

**Practical reasons**:
1. Simulacrum is already complex (RFC-013 + RFC-014) — don't overload it
2. Codebase graph needs different storage (graph DB vs. document store)
3. Decisions may be shared across team; conversations are personal
4. Testing is easier with clear boundaries

---

## Components

### 1. Decision Memory

Architectural decisions are first-class citizens that persist forever.

```python
@dataclass(frozen=True, slots=True)
class Decision:
    """An architectural decision that persists across sessions."""
    
    id: str
    """Unique identifier (hash of context + choice)."""
    
    category: str
    """Category: 'database', 'auth', 'framework', 'pattern', etc."""
    
    question: str
    """What decision was being made: 'Which database to use?'"""
    
    choice: str
    """What was chosen: 'SQLAlchemy with SQLite'."""
    
    rejected: tuple[RejectedOption, ...]
    """Options that were considered but rejected."""
    
    rationale: str
    """Why this choice was made."""
    
    context: str
    """Project context when decision was made."""
    
    confidence: float
    """How confident we are this is still the right choice."""
    
    timestamp: datetime
    """When decision was made."""
    
    session_id: str
    """Which session this came from."""
    
    supersedes: str | None = None
    """ID of decision this replaces (if changed)."""


@dataclass(frozen=True, slots=True)
class RejectedOption:
    """An option that was considered but rejected."""
    
    option: str
    """What was rejected: 'Redis caching'."""
    
    reason: str
    """Why it was rejected: 'Too much operational complexity for our scale'."""
    
    might_reconsider_when: str | None = None
    """Conditions that might change this: 'If we need sub-ms latency'."""
```

**Storage**: `.sunwell/intelligence/decisions.jsonl`

**Usage**:

```python
class DecisionMemory:
    """Manages architectural decisions across sessions."""
    
    async def record_decision(
        self,
        category: str,
        question: str,
        choice: str,
        rejected: list[tuple[str, str]],
        rationale: str,
    ) -> Decision:
        """Record a new architectural decision."""
        ...
    
    async def get_decisions(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[Decision]:
        """Get decisions, optionally filtered by category."""
        ...
    
    async def find_relevant_decisions(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[Decision]:
        """Find decisions relevant to a query using embeddings."""
        ...
    
    async def check_contradiction(
        self,
        proposed_choice: str,
        category: str,
    ) -> Decision | None:
        """Check if proposed choice contradicts an existing decision."""
        ...
```

**Example flow**:

```
User: Add Redis caching to the user service

Sunwell: I found a relevant past decision:

  📋 Decision (session 12, 2 weeks ago):
  Category: caching
  Question: Should we add Redis caching?
  Choice: No - use in-memory LRU cache instead
  Rationale: "Redis adds operational complexity (another service to manage). 
              Our scale doesn't justify it yet. LRU cache handles 95% of cases."
  Might reconsider when: "If we need distributed caching or sub-ms latency"

  Do you want to:
  1. Proceed with Redis anyway (I'll update the decision)
  2. Use LRU cache (matching previous decision)
  3. Explain why circumstances have changed
```

---

### 2. Codebase Graph

Semantic understanding of the codebase, not just file contents.

```python
@dataclass
class CodebaseGraph:
    """Semantic understanding of a codebase."""
    
    # === Static Analysis (built from AST) ===
    
    call_graph: nx.DiGraph
    """Function A calls function B. Edges have call_count from traces."""
    
    type_graph: nx.DiGraph
    """Type A flows to type B. Tracks data paths through the system."""
    
    import_graph: nx.DiGraph
    """Module A imports module B. Used for dependency analysis."""
    
    class_hierarchy: nx.DiGraph
    """Class A inherits from class B. Includes protocols/ABCs."""
    
    # === Semantic Clustering (built from embeddings) ===
    
    concept_clusters: dict[str, list[CodeLocation]]
    """Concept → locations. 'authentication' → [auth.py, middleware.py, decorators.py]"""
    
    similar_functions: dict[str, list[str]]
    """Function → similar functions. Detect potential duplication."""
    
    # === Dynamic Analysis (from execution traces) ===
    
    hot_paths: list[CodePath]
    """Most frequently executed paths. From profiling or trace sampling."""
    
    error_prone: list[CodeLocation]
    """Locations that have caused errors historically."""
    
    # === Metadata ===
    
    file_ownership: dict[Path, str]
    """File → owner (from git blame or explicit)."""
    
    change_frequency: dict[Path, float]
    """File → change rate. High churn = risky to modify."""
    
    coupling_scores: dict[tuple[str, str], float]
    """(Module A, Module B) → coupling score. High = tightly coupled."""


@dataclass(frozen=True, slots=True)
class CodeLocation:
    """A location in the codebase."""
    
    file: Path
    line_start: int
    line_end: int
    symbol: str | None = None  # Function/class name if applicable


@dataclass(frozen=True, slots=True)
class CodePath:
    """A path through the codebase (e.g., a call chain)."""
    
    nodes: tuple[str, ...]  # Function names
    frequency: float  # How often this path is taken
    latency_p50: float | None = None  # Median latency if available
```

**Building the graph**:

```python
class CodebaseAnalyzer:
    """Builds and maintains the codebase graph."""
    
    async def full_scan(self, root: Path) -> CodebaseGraph:
        """Full codebase scan. Run once on first use or after major changes."""
        ...
    
    async def incremental_update(
        self,
        changed_files: list[Path],
        graph: CodebaseGraph,
    ) -> CodebaseGraph:
        """Update graph incrementally after file changes."""
        # Only reanalyze changed files and their direct dependents
        ...
    
    async def add_execution_trace(
        self,
        trace: ExecutionTrace,
        graph: CodebaseGraph,
    ) -> CodebaseGraph:
        """Incorporate runtime trace data (hot paths, error locations)."""
        ...
```

**Usage example**:

```
User: Refactor the payment system

Sunwell: Payment system analysis from codebase graph:

📊 Impact Analysis:
- 47 call sites across 12 modules
- 3 hot paths: checkout (40%), subscription (35%), refund (25%)
- Tight coupling with billing.py (score: 0.82)
- High churn file: payment.py changed 23 times in last month

⚠️ Risk Factors:
- payment.py:process_refund has caused 3 production errors
- billing.py is owned by @alice (consider involving her)
- checkout path has no test coverage for edge case at line 156

🎯 Recommended Approach:
1. Add PaymentProtocol interface first (0 existing callers affected)
2. Migrate hot paths one at a time with feature flags
3. Add test coverage for refund flow before touching it

Proceed with step 1?
```

---

### 3. Pattern Learning

Learn user preferences through implicit feedback.

```python
@dataclass
class PatternProfile:
    """Learned patterns for a user/project."""
    
    # === Code Style ===
    
    naming_conventions: dict[str, str]
    """{'function': 'snake_case', 'class': 'PascalCase', 'constant': 'UPPER_SNAKE'}"""
    
    import_style: Literal["absolute", "relative", "mixed"]
    """Preferred import style."""
    
    type_annotation_level: Literal["none", "public", "all"]
    """How much type annotation to use."""
    
    docstring_style: Literal["google", "numpy", "sphinx", "none"]
    """Docstring format preference."""
    
    # === Architecture Preferences ===
    
    abstraction_level: float
    """0.0 = concrete/simple, 1.0 = abstract/enterprise. Learned from feedback."""
    
    test_preference: Literal["tdd", "after", "minimal", "none"]
    """When/how much to write tests."""
    
    error_handling: Literal["exceptions", "result_types", "mixed"]
    """Error handling style."""
    
    # === Communication Preferences ===
    
    explanation_verbosity: float
    """0.0 = terse, 1.0 = detailed. Learned from "too much"/"not enough" feedback."""
    
    code_comment_level: float
    """0.0 = no comments, 1.0 = heavily commented."""
    
    prefers_questions: bool
    """Does user prefer being asked, or just getting answers?"""
    
    # === Learning Source ===
    
    confidence: dict[str, float]
    """Confidence in each learned pattern."""
    
    evidence: dict[str, list[str]]
    """Evidence for each pattern (session IDs where learned)."""


class PatternLearner:
    """Learns patterns from implicit user feedback."""
    
    def learn_from_edit(
        self,
        original: str,
        edited: str,
        profile: PatternProfile,
    ) -> PatternProfile:
        """User edited AI output → learn what they changed."""
        # If user adds type hints → increase type_annotation_level
        # If user removes comments → decrease code_comment_level
        # If user renames variables → learn naming preference
        ...
    
    def learn_from_rejection(
        self,
        rejected_output: str,
        reason: str | None,
        profile: PatternProfile,
    ) -> PatternProfile:
        """User rejected output → learn what was wrong."""
        ...
    
    def learn_from_acceptance(
        self,
        accepted_output: str,
        profile: PatternProfile,
    ) -> PatternProfile:
        """User accepted output without edits → reinforce patterns."""
        ...
```

#### Prior Art and Approach

Pattern learning from user behavior is a studied problem. Our approach draws from:

| System | Technique | What We Learn |
|--------|-----------|---------------|
| **GitHub Copilot** | Training on user's repo | We can't retrain; use codebase mining instead |
| **Tabnine** | Local model fine-tuning | Too heavy; we use lightweight feature extraction |
| **IntelliSense** | Static analysis of existing code | Good for bootstrap; we extend with edit tracking |
| **Grammarly** | Explicit style preferences | Users won't configure; we infer from behavior |

**Our approach** (hybrid):

1. **Codebase Mining (Bootstrap)**
   - AST analysis: Extract naming patterns, import style, type annotation usage
   - Docstring detection: Identify style (Google/NumPy/Sphinx/none)
   - Achievable accuracy: ~70% (limited by codebase consistency)

2. **Edit Diff Analysis (Refinement)**
   - Compare AI output to user's edited version
   - Use `difflib.SequenceMatcher` for structural comparison
   - Focus on detectable signals: naming changes, type additions, comment removal
   - Achievable accuracy: ~85% for detectable patterns

3. **Explicit Feedback (Override)**
   - User says "too verbose" → reduce explanation_verbosity
   - User says "use snake_case" → set naming convention explicitly
   - Achievable accuracy: ~95% (direct user intent)

**Known limitations**:
- Edit diffs don't capture *why* user changed something
- Some patterns (abstraction level) are hard to detect automatically
- Small sample sizes lead to overfitting (mitigated by confidence thresholds)

**Storage**: `.sunwell/intelligence/patterns.json`

**Usage**:

```
Session 1:
  Sunwell generates: def getUserData(userId: int) -> dict:
  User edits to: def get_user_data(user_id: int) -> UserData:
  → Learned: snake_case functions, type hints, custom return types

Session 2:
  User: Add a function to fetch orders
  Sunwell (applying learned patterns):
    def get_orders(user_id: int) -> list[Order]:
        """Fetch orders for a user."""
        ...
  User: Perfect!
  → Reinforced: Current patterns are correct
```

---

### 4. Failure Memory

Remember what didn't work and why.

```python
@dataclass(frozen=True, slots=True)
class FailedApproach:
    """An approach that was tried and failed."""
    
    id: str
    """Unique identifier."""
    
    description: str
    """What was attempted: 'Async SQLAlchemy with connection pooling'"""
    
    error_type: str
    """Type of failure: 'runtime_error', 'test_failure', 'user_rejection', 'timeout'"""
    
    error_message: str
    """Actual error or rejection reason."""
    
    context: str
    """What we were trying to achieve."""
    
    code_snapshot: str | None
    """The code that failed (if applicable)."""
    
    fix_attempted: str | None
    """What fix was tried (if any)."""
    
    root_cause: str | None
    """Root cause analysis (if determined)."""
    
    similar_to: list[str]
    """IDs of similar past failures (pattern detection)."""
    
    timestamp: datetime
    session_id: str


class FailureMemory:
    """Tracks failed approaches to avoid repeating mistakes."""
    
    async def record_failure(
        self,
        description: str,
        error_type: str,
        error_message: str,
        context: str,
        code: str | None = None,
    ) -> FailedApproach:
        """Record a failed approach."""
        ...
    
    async def check_similar_failures(
        self,
        proposed_approach: str,
        top_k: int = 3,
    ) -> list[FailedApproach]:
        """Check if proposed approach is similar to past failures."""
        ...
    
    async def get_failure_patterns(self) -> list[FailurePattern]:
        """Identify recurring failure patterns."""
        # E.g., "Async database operations fail 80% of the time in this codebase"
        ...
```

**Usage**:

```
User: Let's try using asyncio for the database calls

Sunwell: ⚠️ Similar approach failed before:

  🔴 Failed Approach (session 8):
  Description: Async SQLAlchemy with connection pooling
  Error: "Cannot use connection pool with async engine"
  Root cause: SQLite doesn't support true async; asyncio wrapper just threads
  
  This has failed 3 times in this project. The codebase uses sync SQLAlchemy.
  
  Options:
  1. Proceed anyway (maybe you've fixed the underlying issue?)
  2. Use sync approach (matching existing code)
  3. Explain what's different this time
```

---

### 5. Cross-Session Continuity

Project context persists across sessions automatically.

```python
@dataclass
class ProjectContext:
    """Aggregated project intelligence for a session."""
    
    # From existing RFC-013/014
    session_memory: SimulacrumStore
    
    # New in RFC-045
    decisions: DecisionMemory
    codebase: CodebaseGraph
    patterns: PatternProfile
    failures: FailureMemory
    
    # Session state
    active_goals: list[str]
    """What we're currently working on."""
    
    blocked_on: list[Blocker]
    """What's blocking progress (waiting for user, external, etc.)."""
    
    
class ProjectIntelligence:
    """Main interface for project intelligence."""
    
    async def load(self, project_root: Path) -> ProjectContext:
        """Load project intelligence, creating if needed."""
        ...
    
    async def save(self, context: ProjectContext) -> None:
        """Persist current state."""
        ...
    
    async def start_session(self, context: ProjectContext) -> SessionStart:
        """Begin a new session with existing context."""
        # Returns summary of what we remember
        ...
    
    async def end_session(self, context: ProjectContext) -> None:
        """End session, persist learnings."""
        ...
```

**Session start experience**:

```
$ sunwell chat

Sunwell: Welcome back! Resuming project context:

📋 Recent Work (last session, 2 days ago):
- Added OAuth authentication (completed)
- Started payment integration (blocked: waiting for Stripe API key)

🧠 Active Decisions:
- Using SQLAlchemy + Postgres
- OAuth for auth (switched from JWT per your request)
- pytest for testing

📊 Codebase State:
- 47 files, 3,200 lines
- 2 files changed since last session (by git)
- No new test failures

💡 Learned Preferences:
- snake_case, type hints, Google docstrings
- Prefers detailed explanations
- Writes tests after implementation

What would you like to work on?
```

---

## Storage Structure

```
.sunwell/
├── intelligence/
│   ├── decisions.jsonl       # Architectural decisions (append-only)
│   ├── failures.jsonl        # Failed approaches (append-only)
│   ├── patterns.json         # Learned patterns (overwritten)
│   └── codebase/
│       ├── graph.pickle      # Serialized codebase graph
│       ├── embeddings.npz    # Function/class embeddings
│       └── index.json        # File → symbols index
├── sessions/                  # From RFC-013
│   ├── hot/                   # Current session
│   ├── warm/                  # Recent sessions
│   └── cold/                  # Archived sessions
└── config.yaml               # Project-level settings
```

---

## Design Decisions

### Decision Memory Storage: JSONL vs SQLite vs SimulacrumStore

| Option | Pros | Cons |
|--------|------|------|
| **JSONL (chosen)** | Human-readable, git-friendly, append-only natural, simple | No indexing, linear scan for queries |
| SQLite | Fast queries, ACID, built-in indexing | Binary file, merge conflicts, overkill for ~100s of decisions |
| Extend SimulacrumStore | Unified storage, existing compression | Conversations ≠ decisions semantically, different access patterns |

**Decision**: JSONL for decisions/failures. Rationale:
- Decisions are append-mostly (rarely updated)
- Expected volume: 10-100 decisions per project (linear scan is fine)
- Human readability aids debugging and manual edits
- Git diffs are meaningful
- Embedding-based retrieval handles "find relevant" queries

**Reconsider if**: Decision count exceeds 1,000 per project.

---

### Codebase Graph: AST vs Tree-sitter vs LSP

| Option | Pros | Cons |
|--------|------|------|
| Python `ast` module | Zero dependencies, precise for Python | Python-only, no incremental parsing |
| **Tree-sitter (chosen)** | Multi-language, incremental, fast | External dependency, less Python-specific info |
| LSP integration | Rich semantic info, already running | Complex setup, server management, slow startup |

**Decision**: Tree-sitter for parsing, Python `ast` for Python-specific analysis. Rationale:
- Tree-sitter handles multi-language projects (JS config, YAML, etc.)
- Incremental parsing is essential for large codebases
- Python `ast` provides type-specific info when needed
- No LSP server management overhead

**Scale targets**:
| Codebase Size | Full Scan | Incremental Update | Memory |
|---------------|-----------|-------------------|--------|
| 10K LOC | < 5s | < 500ms | < 50MB |
| 100K LOC | < 30s | < 2s | < 200MB |
| 1M LOC | < 5min | < 10s | < 1GB (lazy-loaded) |

---

### Pattern Learning: Edit Diff vs Explicit Feedback vs Codebase Mining

| Option | Pros | Cons |
|--------|------|------|
| **Edit diff analysis (primary)** | Implicit, no user effort | Noisy signal, complex diff parsing |
| Explicit feedback ("too verbose") | Clear signal, user intent | Requires user action, low engagement |
| **Codebase mining (bootstrap)** | Instant patterns from existing code | Assumes consistency, may learn bad patterns |

**Decision**: Hybrid approach:
1. **Bootstrap**: Mine existing codebase for initial patterns (naming, imports, docstrings)
2. **Refine**: Edit diffs adjust patterns over time
3. **Override**: Explicit feedback always wins

**Confidence thresholds**:
- Bootstrap patterns: 60% confidence (inferred from code)
- Edit-confirmed patterns: 80% confidence (user implicitly agreed)
- Explicit feedback: 95% confidence (user stated preference)

---

## Integration with Existing Systems

### With Simulacrum (RFC-013 + RFC-014) — The Core Relationship

Simulacrum and Project Intelligence are **complementary systems** that share data bidirectionally:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA FLOW                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   SIMULACRUM                         PROJECT INTELLIGENCE        │
│                                                                  │
│   Conversations ──────────────────────► Decision Memory          │
│   (chunk demotion)     extracts         (why we chose X)         │
│                                                                  │
│   Episodic Memory ────────────────────► Failure Memory           │
│   (dead ends)          extracts         (what didn't work)       │
│                                                                  │
│   User Edits ─────────────────────────► Pattern Learning         │
│   (tracked in turns)   learns from      (user preferences)       │
│                                                                  │
│   Topology Memory ◄───────────────────  Codebase Graph           │
│   (spatial, struct)    enriched by      (code structure)         │
│                                                                  │
│   Context Assembly ◄──────────────────  All Intelligence         │
│   (what to include)    informed by      (what's relevant)        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Hook: On Chunk Demotion

When Simulacrum demotes a conversation chunk (HOT → WARM → COLD), we extract durable intelligence:

```python
# Register with SimulacrumStore
class SimulacrumStore:
    def __init__(self, ..., intelligence_extractor: IntelligenceExtractor | None = None):
        self._intelligence_extractor = intelligence_extractor
    
    async def _demote_chunk(self, chunk: Chunk, new_tier: str) -> None:
        """Demote chunk to new tier and extract intelligence."""
        # Existing demotion logic...
        await self._chunk_manager.demote(chunk, new_tier)
        
        # NEW: Extract intelligence before archiving
        if self._intelligence_extractor:
            await self._intelligence_extractor.on_chunk_demotion(chunk)
```

#### Hook: Context Assembly

When Simulacrum assembles context for a prompt, include relevant intelligence:

```python
class ContextAssembler:
    def __init__(self, ..., project_context: ProjectContext | None = None):
        self._project_context = project_context
    
    async def assemble(self, query: str, budget: int) -> AssembledContext:
        """Assemble context from all sources."""
        context_parts = []
        
        # Existing: conversation history
        context_parts.extend(await self._get_relevant_turns(query, budget // 2))
        
        # NEW: relevant decisions
        if self._project_context:
            decisions = await self._project_context.decisions.find_relevant(query, top_k=3)
            if decisions:
                context_parts.append(self._format_decisions(decisions))
            
            # Similar failures as warnings
            failures = await self._project_context.failures.check_similar(query)
            if failures:
                context_parts.append(self._format_failure_warnings(failures))
        
        return AssembledContext(parts=context_parts)
```

#### Hook: Session Start

When starting a session, load both systems:

```python
async def start_session(project_root: Path) -> ProjectContext:
    """Initialize unified context for a session."""
    
    # Load Simulacrum (existing)
    simulacrum = SimulacrumStore(project_root / ".sunwell" / "sessions")
    await simulacrum.load_hot_tier()
    
    # Load Project Intelligence (new)
    intelligence = await ProjectIntelligence.load(project_root)
    
    # Wire them together
    extractor = IntelligenceExtractor(intelligence)
    simulacrum._intelligence_extractor = extractor
    
    # Create unified context
    return ProjectContext(
        simulacrum=simulacrum,
        decisions=intelligence.decisions,
        codebase=intelligence.codebase,
        patterns=intelligence.patterns,
        failures=intelligence.failures,
    )
```

### With RFC-014 (Multi-Topology Memory)

Project Intelligence enriches Simulacrum's topology with codebase knowledge:

```python
async def enrich_topology_from_codebase(
    unified_store: UnifiedMemoryStore,
    codebase: CodebaseGraph,
) -> None:
    """Add codebase concepts to topology memory for retrieval."""
    
    # Add concept clusters from code analysis
    for concept, locations in codebase.concept_clusters.items():
        for loc in locations:
            node = MemoryNode(
                content=f"Concept '{concept}' at {loc.file}:{loc.line_start}",
                location=loc,
                facets={
                    "type": "code_concept",
                    "source": "codebase_graph",
                },
            )
            unified_store.add(node)
    
    # Add hot paths for awareness
    for path in codebase.hot_paths:
        node = MemoryNode(
            content=f"Hot path: {' → '.join(path.nodes)}",
            facets={
                "type": "hot_path",
                "frequency": path.frequency,
            },
        )
        unified_store.add(node)
```

### With RFC-030 (Unified Router)

Routing decisions use learned patterns:
```python
async def route_with_intelligence(
    request: str,
    router: UnifiedRouter,
    context: ProjectContext,
) -> RoutingDecision:
    decision = await router.route(request)
    
    # Adjust based on learned patterns
    if context.patterns.prefers_questions:
        decision = decision.with_clarification_enabled()
    
    if context.patterns.test_preference == "tdd":
        decision = decision.with_focus(["testing"])
    
    return decision
```

### With RFC-036 (Artifact Planning)

Codebase graph informs artifact discovery:
```python
async def discover_with_intelligence(
    goal: str,
    planner: ArtifactPlanner,
    context: ProjectContext,
) -> ArtifactGraph:
    # Check for contradicting decisions
    for decision in context.decisions.find_relevant(goal):
        if contradicts(goal, decision):
            raise DecisionConflict(decision)
    
    # Check for similar past failures
    failures = await context.failures.check_similar_failures(goal)
    if failures:
        warn_about_failures(failures)
    
    # Plan with codebase awareness
    return await planner.discover_graph(
        goal,
        codebase=context.codebase,
        patterns=context.patterns,
    )
```

### With RFC-042 (Adaptive Agent)

Signals include intelligence context:
```python
@dataclass
class AdaptiveSignals:
    # Existing signals
    complexity: Complexity
    error_state: ErrorState
    
    # New: Intelligence signals
    has_relevant_decision: bool
    has_similar_failure: bool
    codebase_impact_score: float
    pattern_confidence: float
```

---

## Privacy and Security

### What's Stored

| Data | Contains Code? | PII Risk | Mitigation |
|------|----------------|----------|------------|
| Decisions | Snippets only | Low | User reviews before commit |
| Codebase Graph | Structure only | None | No actual code stored |
| Patterns | No | Low | Preferences, not content |
| Failures | Error messages | Low | Sanitize stack traces |

### Opt-Out

```yaml
# .sunwell/config.yaml
intelligence:
  enabled: true  # Master switch
  
  decisions:
    enabled: true
    auto_record: false  # Require explicit confirmation
    
  codebase_graph:
    enabled: true
    include_private: false  # Exclude _private functions
    
  pattern_learning:
    enabled: true
    
  failure_memory:
    enabled: true
    include_code: false  # Don't store code snippets
```

### Git Integration

Intelligence data can be:
1. **Gitignored** (default): Personal to each developer
2. **Committed**: Shared team knowledge
3. **Separate repo**: Shared but not in main repo

```yaml
# .sunwell/config.yaml
intelligence:
  sharing: "gitignore"  # or "commit" or "external"
```

---

## Metrics and Evaluation

### Intelligence Quality Metrics

```python
@dataclass(frozen=True, slots=True)
class IntelligenceMetrics:
    """Measure the quality of project intelligence."""
    
    decision_relevance: float
    """How often surfaced decisions were relevant (user accepted/used)."""
    
    failure_prevention_rate: float
    """How often we prevented repeated failures."""
    
    pattern_accuracy: float
    """How often generated code matched learned patterns without edits."""
    
    codebase_coverage: float
    """What percentage of codebase is in the graph."""
    
    session_continuity_score: float
    """How well we maintained context across sessions."""
```

### Competitive Benchmarks

Compare against Claude Code on:

1. **Repeated mistake rate**: How often does the AI suggest something the user already rejected?
2. **Pattern consistency**: Does generated code match project style without explicit instruction?
3. **Context recall**: Can the AI recall decisions from 10+ sessions ago?
4. **Refactoring safety**: Does the AI warn about high-impact changes?

---

## CLI Integration

```bash
# View project intelligence
sunwell intel status
# Output:
# 📊 Project Intelligence Status
# Decisions: 23 recorded (5 this week)
# Patterns: 87% confident in style preferences
# Codebase: 234 functions, 45 classes, 12 hot paths
# Failures: 8 recorded, 3 recurring patterns

# View specific intelligence
sunwell intel decisions --category auth
sunwell intel failures --recent 10
sunwell intel patterns

# Manual operations
sunwell intel record-decision  # Interactive decision recording
sunwell intel scan             # Force full codebase scan
sunwell intel forget --session 5  # Forget specific session
sunwell intel export           # Export for team sharing
```

---

## Risks and Mitigations

### Risk 1: Stale Intelligence

**Problem**: Decisions become outdated but aren't updated.

**Mitigation**:
- Confidence decay over time
- Prompt for review when decision is old + relevant
- Detect contradictions with current code state

### Risk 2: Wrong Pattern Learning

**Problem**: Learn incorrect patterns from limited data.

**Mitigation**:
- Require N samples before confident
- Allow explicit pattern override
- Show "learned because..." transparency

### Risk 3: Large Graph for Large Codebases

**Problem**: Codebase graph becomes too large for memory.

**Mitigation**:
- Incremental updates (only changed files)
- Lazy loading of subgraphs
- Tiered storage (hot/warm/cold for graph too)

### Risk 4: Privacy Concerns

**Problem**: Users don't want code/decisions stored.

**Mitigation**:
- Granular opt-out per component
- Local-only by default (no cloud)
- Clear data on request

### Risk 5: Pattern Learning Complexity

**Problem**: Learning style from edit diffs is research-grade hard. Diffs capture *what* changed, not *why*.

**Mitigation**:
- Start with **detectable patterns only**: naming, imports, type hints, docstrings
- Use codebase mining for bootstrap (70% accuracy acceptable)
- Explicit feedback overrides learned patterns
- **Spike required**: Prototype `PatternLearner` before full implementation
- Transparency: Show "learned because you changed X to Y" so users can correct

**Acceptance criteria for Phase 3**:
- Naming convention detection: 90% accuracy on test corpus
- Type annotation preference: 85% accuracy
- Docstring style: 95% accuracy (easy to detect)
- Complex patterns (abstraction level): Defer to explicit feedback

### Risk 6: Decision Contradiction Handling

**Problem**: User explicitly contradicts a past decision. How do we handle?

**Mitigation**:
- Surface the conflict clearly: "This contradicts decision X from session Y"
- User chooses: update decision, proceed anyway, or abort
- Never silently override; always record the change with `supersedes` link
- Support "temporary override" for experimentation

---

## Testing Strategy

### Unit Tests

```python
class TestDecisionMemory:
    async def test_records_decision(self):
        memory = DecisionMemory(path=tmp_path)
        decision = await memory.record_decision(
            category="database",
            question="Which database?",
            choice="SQLite",
            rejected=[("Postgres", "Overkill for prototype")],
            rationale="Simple, zero config",
        )
        assert decision.choice == "SQLite"
    
    async def test_finds_relevant_decisions(self):
        # Record some decisions
        # Query for relevance
        # Assert correct ones returned
        ...
    
    async def test_detects_contradiction(self):
        # Record "use SQLite" decision
        # Check contradiction with "use Postgres" proposal
        # Assert contradiction detected
        ...


class TestPatternLearner:
    def test_learns_from_edit(self):
        learner = PatternLearner()
        profile = PatternProfile()
        
        original = "def getUserData(userId):"
        edited = "def get_user_data(user_id: int):"
        
        new_profile = learner.learn_from_edit(original, edited, profile)
        
        assert new_profile.naming_conventions["function"] == "snake_case"
        assert new_profile.type_annotation_level != "none"
```

### Integration Tests

```python
class TestProjectIntelligence:
    async def test_session_continuity(self):
        """Intelligence persists across sessions."""
        intel = ProjectIntelligence(root=tmp_path)
        
        # Session 1: Make a decision
        ctx1 = await intel.load()
        await ctx1.decisions.record_decision(...)
        await intel.save(ctx1)
        
        # Session 2: Decision should be there
        ctx2 = await intel.load()
        decisions = await ctx2.decisions.get_decisions()
        assert len(decisions) == 1
```

---

## Implementation Plan

### Phase 0: Spike — Pattern Learning Feasibility (Week 0, 2-3 days)

**Purpose**: Validate that edit-diff analysis can reliably detect style patterns.

**Deliverables**:
- [ ] Prototype `PatternLearner.learn_from_edit()` with 10 test cases
- [ ] Measure accuracy on naming convention detection
- [ ] Measure accuracy on type annotation detection
- [ ] Document findings and adjust Phase 3 scope

**Go/No-Go**: If naming detection < 80% accuracy, descope Phase 3 to codebase mining only.

---

### Phase 1: Decision Memory (Week 1-2) — **Lowest Risk, Highest Value**

- [ ] Implement `Decision` and `DecisionMemory` dataclasses
- [ ] JSONL storage with embedding-based retrieval
- [ ] Add CLI commands: `sunwell intel decisions`, `sunwell intel record-decision`
- [ ] Integrate with agent to surface relevant decisions (contradiction check)
- [ ] Tests: record, retrieve, find_relevant, check_contradiction
- [ ] Documentation

**Exit criteria**: Decision surfacing works in chat; user can override decisions.

---

### Phase 2: Codebase Graph (Week 3-4)

- [ ] Implement `CodebaseAnalyzer` with tree-sitter + Python ast
- [ ] Build call graph and import graph (static analysis)
- [ ] Add `concept_clusters` via embeddings
- [ ] Implement `incremental_update()` for file changes
- [ ] Scale test: 100K LOC codebase in < 30s full scan
- [ ] Tests and documentation

**Exit criteria**: `sunwell intel scan` completes on Sunwell repo; impact analysis works.

---

### Phase 3: Pattern Learning (Week 5-6) — **Contingent on Phase 0**

**If Phase 0 succeeds**:
- [ ] Implement `PatternProfile` bootstrap from codebase mining
- [ ] Implement `PatternLearner.learn_from_edit()` (detectable patterns only)
- [ ] Implement `learn_from_acceptance()` and `learn_from_rejection()`
- [ ] Apply patterns to code generation prompts
- [ ] Transparency: Show "learned from session X" in `sunwell intel patterns`
- [ ] Tests and documentation

**If Phase 0 fails** (< 80% accuracy):
- [ ] Implement `PatternProfile` bootstrap only (no edit learning)
- [ ] Add explicit pattern configuration in `.sunwell/config.yaml`
- [ ] Document limitation; revisit in future RFC

**Exit criteria**: Generated code uses learned naming conventions without explicit instruction.

---

### Phase 4: Failure Memory (Week 7)

- [ ] Implement `FailedApproach` and `FailureMemory`
- [ ] Auto-record failures from agent execution errors
- [ ] Embedding-based `check_similar_failures()`
- [ ] Surface warnings before re-attempting known failures
- [ ] Tests and documentation

**Exit criteria**: Re-attempting a failed approach triggers a warning.

---

### Phase 5: Integration (Week 8)

- [ ] `ProjectContext` aggregates all intelligence layers
- [ ] `ProjectIntelligence.start_session()` shows context summary
- [ ] Integration with RFC-042 signals (intelligence-aware routing)
- [ ] CLI polish: `sunwell intel status`, `sunwell intel export`
- [ ] Benchmarks: Measure repeated mistake rate, pattern accuracy, context recall
- [ ] Documentation and examples

**Exit criteria**: All success criteria metrics collected; comparison to baseline available.

---

## Success Criteria

### Metrics and Measurement Methodology

| Metric | Target | Measurement |
|--------|--------|-------------|
| Repeated mistake rate | < 5% | Count suggestions matching rejected options in FailureMemory, divide by total suggestions |
| Pattern accuracy | > 85% | Generate code, measure edit distance to user's accepted version (lower = better) |
| Context recall | > 90% | Query for decisions >30 days old, measure precision/recall vs. manual labels |
| Refactoring safety | > 95% | For changes to coupled code (score > 0.5), measure warning rate |
| User satisfaction | Qualitative | "Teammate" sentiment in feedback (survey after 10+ sessions) |

### Detailed Criteria

1. **Repeated mistake rate < 5%**
   - AI rarely suggests what user already rejected
   - Measurement: `rejected_suggestions / total_suggestions` where rejected is in FailureMemory
   - Baseline: Current Sunwell (no memory) = ~20% estimated

2. **Pattern accuracy > 85%**
   - Generated code matches style without explicit instruction
   - Measurement: For code generation, compare to user's final version
   - Detectable patterns only: naming, imports, type hints, docstrings
   - Exclude: abstraction level, architecture choices (too subjective)

3. **Context recall > 90%**
   - Can surface relevant decisions from 30+ days ago
   - Measurement: Create test corpus of 50 decisions, query with natural language
   - Success = relevant decision in top-3 results

4. **Refactoring safety > 95%**
   - Warns about high-impact changes to coupled code
   - Measurement: For files with coupling_score > 0.5 or change_frequency > 10/month
   - Success = warning surfaced before user commits

5. **User satisfaction**
   - "It feels like working with a teammate who knows the codebase"
   - Measurement: Post-session survey after 10+ sessions
   - Target: 4/5 average on "feels like it remembers context"

---

## Summary

Project Intelligence transforms Sunwell from a stateless assistant into a **persistent codebase mind** through:

1. **Decision Memory** — Remember why we chose X over Y
2. **Codebase Graph** — Understand relationships, not just files
3. **Pattern Learning** — Adapt to user/project style
4. **Failure Memory** — Never repeat the same mistake
5. **Cross-Session Continuity** — Pick up where we left off

**The result**: Claude Code forgets you after every session. Sunwell becomes a team member who knows your codebase, remembers your decisions, and gets better over time.

---

## References

### Internal RFCs

- RFC-013: Hierarchical Memory with Progressive Compression
- RFC-014: Multi-Topology Memory Extension
- RFC-030: Unified Router
- RFC-036: Artifact-First Planning
- RFC-042: Adaptive Agent

### External References

- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) — Incremental parsing library used for Codebase Graph
- [ADR (Architecture Decision Records)](https://adr.github.io/) — Inspiration for Decision Memory format
- [difflib](https://docs.python.org/3/library/difflib.html) — Python standard library for edit diff analysis
