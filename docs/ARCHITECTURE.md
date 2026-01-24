# Sunwell Architecture

**Status**: Experimental

Sunwell is testing whether AI agents can work autonomously if you provide the right infrastructure: observability, control, trust, memory, and progress tracking.

---

## Core Hypothesis

Autonomous AI agents fail for infrastructure reasons, not capability reasons:

| Problem | Without Infrastructure | With Infrastructure |
|---------|----------------------|---------------------|
| Can't see what agent is doing | Flying blind | Observable reasoning |
| Agent does dangerous things | Uncontrolled | Constrained by guardrails |
| Don't know if output is correct | Manual review of everything | Confidence scoring |
| Agent forgets context | Repeats mistakes | Persistent memory |
| Don't know if progress is happening | No visibility | Goal tracking |

Sunwell provides these five capabilities. If they work well enough, autonomous local development becomes viable.

---

## The Five Capabilities

### 🔭 Observe

**Purpose**: See what the agent is doing and thinking.

**Components**:
- `reasoning/` — Step-by-step reasoning traces
- `navigation/` — ToC-based navigation through reasoning
- `analysis/` — State DAG, workspace analysis
- `surface/` — High-level status
- `lineage/` — Provenance tracking
- `session/` — Session state and replay
- `agent/events.py` — Real-time event streaming

**Key types**:

```python
@dataclass(frozen=True, slots=True)
class ReasoningStep:
    id: str
    timestamp: datetime
    action: str
    rationale: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    confidence: float
    parent_id: str | None = None
```

---

### 🎮 Control

**Purpose**: Define what the agent is allowed to do.

**Components**:
- `guardrails/` — Hard limits on actions
- `security/` — Permissions and access control
- `workflow/` — Approval flows
- `agent/gates.py` — Quality gates
- `agent/budget.py` — Token and cost limits

**Configuration**:

```yaml
guardrails:
  max_files_per_goal: 10
  forbidden_paths: ["secrets.py", ".env"]
  auto_approve: ["tests/*", "docs/*"]
  require_approval: ["src/core/*"]
```

**Key types**:

```python
@dataclass(frozen=True, slots=True)
class Guardrail:
    id: str
    type: GuardrailType  # HARD_LIMIT | SOFT_LIMIT | APPROVAL_REQUIRED
    condition: str
    action: GuardrailAction  # DENY | WARN | REQUIRE_APPROVAL
    message: str
```

---

### ✅ Trust

**Purpose**: Know when to believe agent outputs.

**Components**:
- `verification/` — Deep correctness checks
- `confidence/` — Confidence scoring
- `eval/` — Quality assessment
- `agent/validation.py` — Output validation

**Confidence levels**:

```
🟢 HIGH (90-100%)    — Likely correct
🟡 MODERATE (70-89%) — Review recommended
🟠 LOW (50-69%)      — Needs work
🔴 UNCERTAIN (<50%)  — Don't trust
```

**Key types**:

```python
@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    value: float  # 0.0 to 1.0
    level: ConfidenceLevel
    evidence_score: float
    consistency_score: float
    rationale: str
```

---

### 🧠 Memory

**Purpose**: Persistent knowledge across sessions.

**Components**:
- `intelligence/` — Project-level knowledge
- `memory/` — HOT/WARM/COLD storage tiers
- `indexing/` — Knowledge retrieval
- `embedding/` — Semantic search
- `project/` — Current project model
- `bootstrap/` — Fast knowledge acquisition from git history

**What gets remembered**:
- **Decisions**: "We chose OAuth over JWT" (with rationale)
- **Failures**: "That migration approach failed 3 times"
- **Patterns**: "User prefers snake_case"
- **Codebase facts**: "billing.py is fragile"

**Key types**:

```python
@dataclass(frozen=True, slots=True)
class Decision:
    id: str
    timestamp: datetime
    description: str
    rationale: str
    alternatives_considered: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class FailureRecord:
    id: str
    approach: str
    error: str
    times_attempted: int
```

---

### 📈 Progress

**Purpose**: Track goal completion and velocity.

**Components**:
- `backlog/` — Goal discovery and management
- `execution/` — Execution tracking
- `incremental/` — Incremental progress
- `integration/` — Integration verification
- `agent/metrics.py` — Velocity metrics

**Goal lifecycle**:

```
DISCOVERED → PROPOSED → APPROVED → IN_PROGRESS → VERIFYING → COMPLETED
                                                          ↘ STUCK
                                                          ↘ FAILED
```

**Key types**:

```python
@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    description: str
    source: GoalSource  # DISCOVERED | USER_REQUESTED | SYSTEM
    priority: Priority
    status: GoalStatus
    artifacts: tuple[Artifact, ...]
```

---

## Quality Techniques

Small local models produce poor output in single-shot prompting. Sunwell uses structured techniques to improve quality:

### Harmonic Synthesis

Multiple perspectives generate in parallel, then vote on best:

```
┌──────────┐   ┌──────────┐   ┌──────────┐
│ Critic   │   │ Expert   │   │ User     │
│ Plan A   │   │ Plan B   │   │ Plan C   │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     └──────────────┼──────────────┘
                    ↓
              Vote → Best Plan
```

### Resonance

Feedback loops refine output:

```
Voice (draft) → Wisdom (judge) → Voice (refine) → ...
                    ↓
              Structured feedback

Iteration 1: 3/10
Iteration 2: 6/10
Iteration 3: 8.5/10
```

### Lenses

Domain expertise injection via heuristics and personas:

```yaml
name: tech-writer
heuristics:
  - name: BLUF
    rule: Put conclusion first
personas:
  - name: confused-junior
    attack_vectors: ["Is this explained simply?"]
```

### Model Routing

Two-tier model system:
- **Voice** (gemma3:4b): Fast, 80% of tasks
- **Wisdom** (gemma3:12b): Complex reasoning, 20% of tasks

---

## Module Map

```
src/sunwell/
├── # OBSERVE
│   ├── reasoning/        Reasoning traces
│   ├── navigation/       ToC navigation
│   ├── analysis/         State DAG
│   ├── surface/          High-level status
│   ├── lineage/          Provenance
│   └── session/          Session state
│
├── # CONTROL
│   ├── guardrails/       Constraints
│   ├── security/         Permissions
│   └── workflow/         Approval flows
│
├── # TRUST
│   ├── verification/     Deep verification
│   ├── confidence/       Confidence scoring
│   └── eval/             Evaluation
│
├── # MEMORY
│   ├── intelligence/     Project knowledge
│   ├── memory/           Memory tiers
│   ├── indexing/         Retrieval
│   ├── embedding/        Semantic search
│   ├── context/          Context management
│   └── project/          Project state
│
├── # PROGRESS
│   ├── backlog/          Goal tracking
│   ├── execution/        Execution
│   ├── incremental/      Incremental progress
│   └── integration/      Integration checks
│
├── # QUALITY TECHNIQUES
│   ├── naaru/            Cognitive architecture
│   ├── simulacrum/       Persona simulation
│   ├── lens/             Domain expertise
│   ├── convergence/      Result synthesis
│   ├── mirror/           Self-improvement
│   └── routing/          Model routing
│
└── # INFRASTRUCTURE
    ├── models/           LLM providers
    ├── providers/        Provider adapters
    ├── tools/            Tool implementations
    ├── cli/              Commands
    └── server/           API server
```

---

## Data Flow

```
USER GOAL
    │
    ▼
┌─────────┐
│ MEMORY  │ ← Recall relevant context
└────┬────┘
     │
     ▼
┌─────────┐
│ CONTROL │ ← Check guardrails
└────┬────┘
     │
     ▼
┌─────────┐
│  PLAN   │ ← Harmonic synthesis
└────┬────┘
     │
     ▼
┌─────────┐     ┌─────────┐
│ EXECUTE │ ──→ │ OBSERVE │ (stream events)
└────┬────┘     └─────────┘
     │
     ▼
┌─────────┐
│  TRUST  │ ← Verify, score confidence
└────┬────┘
     │
     ▼
┌──────────┐
│ PROGRESS │ ← Update goal status
└────┬─────┘
     │
     ▼
┌─────────┐
│ MEMORY  │ ← Record decisions, patterns
└─────────┘
     │
     ▼
COMPLETED GOAL
```

---

## Design Principles

1. **Types as contracts** — Type signatures define behavior
2. **Immutable by default** — Frozen dataclasses, tuples over lists
3. **Explicit over implicit** — No magic, everything declared
4. **Fail loudly** — Errors are explicit, not silent

```python
@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    status: GoalStatus
    artifacts: tuple[Artifact, ...]  # tuple, not list
```

---

## Open Questions

This is experimental. We're testing:

1. **Does observability help?** — Can users actually debug agent failures with reasoning traces?
2. **Are guardrails sufficient?** — Can we define constraints that prevent harm without blocking useful work?
3. **Is confidence scoring useful?** — Do the scores correlate with actual correctness?
4. **Does memory improve outcomes?** — Do agents make fewer mistakes with persistent knowledge?
5. **Can progress tracking enable autonomy?** — Can agents discover and complete useful work on their own?

---

## Further Reading

- [THESIS-VERIFICATION.md](THESIS-VERIFICATION.md) — Benchmark methodology
- [ROADMAP-local-unlimited.md](ROADMAP-local-unlimited.md) — Implementation status
- Individual RFC documents for specific subsystems
