# Sunwell Roadmap: Local Unlimited Development

> **Vision**: 10 minutes of setup → unlimited local AI development forever

---

## The Value Proposition

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOCAL UNLIMITED                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   SETUP ONCE                      GET FOREVER                       │
│   ──────────────────              ──────────────────────────────    │
│   • Install Ollama                • 24/7 autonomous development     │
│   • Pull model (~4GB)             • Zero API costs ($0 × ∞ = $0)    │
│   • pip install sunwell           • Full privacy (nothing leaves)   │
│   • sunwell init                  • Learns your style over time     │
│   • Wait for scan (~30s)          • Remembers all decisions         │
│                                   • Never repeats mistakes          │
│   ≈ 10 minutes                    • Gets better with every session  │
│                                                                     │
│   ────────────────────────────────────────────────────────────────  │
│                                                                     │
│   Claude Code: $0.01/request × ∞ requests = $$$                     │
│   Sunwell:     $0/request × ∞ requests = $0                         │
│                                                                     │
│   The tradeoff: Setup friction for unlimited runway                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Moat: What Competitors Can't Copy

### 1. Persistent Intelligence (RFC-045)

Claude Code is stateless. Every session is fresh. Sunwell remembers:

| They Forget | We Remember |
|-------------|-------------|
| "We chose OAuth last week" | Decision Memory |
| "That approach failed 3 times" | Failure Memory |
| "User prefers snake_case" | Pattern Learning |
| "billing.py is fragile" | Codebase Graph |

**Result**: A senior engineer who knows your codebase vs. a brilliant contractor who forgets you after every job.

### 2. Proactive Development (RFC-046)

Claude Code waits to be told what to do. Sunwell sees what's wrong and proposes fixes:

```
Claude Code:                          Sunwell:
  Human: "Fix failing test"             Sunwell: "I found 3 issues:
  AI: [fixes]                             1. Failing test in auth_test.py
  Human: "Add type hints"                 2. Missing type hints in models/
  AI: [adds]                              3. TODO in api/routes.py:89
  Human: "Address that TODO"              
  AI: [addresses]                         Want me to fix them? [Y/n]"
```

### 3. Local-First Privacy

- No data leaves your machine
- No API keys to manage
- No rate limits
- No monthly bills
- Works offline

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SUNWELL STACK                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    AUTONOMY LAYER                             │  │
│  │  RFC-048 Guardrails │ RFC-049 External │ RFC-051 Multi-Agent  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   INTELLIGENCE LAYER                          │  │
│  │  RFC-045 Project Intelligence │ RFC-046 Autonomous Backlog    │  │
│  │  RFC-050 Fast Bootstrap       │ RFC-047 Deep Verification     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    PLANNING LAYER                             │  │
│  │  RFC-036 Artifact-First │ RFC-044 Puzzle │ RFC-038 Harmonic   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   EXECUTION LAYER                             │  │
│  │  RFC-042 Adaptive Agent │ RFC-030 Router │ Tools/Validation   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    MEMORY LAYER                               │  │
│  │  RFC-013 Hierarchical Memory │ RFC-014 Multi-Topology Memory  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    MODEL LAYER                                │  │
│  │  Ollama │ Local Models (Qwen, Llama, etc.) │ Optional Cloud   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## RFC Status

### ✅ Implemented (Foundation)

| RFC | Name | Status | Description |
|-----|------|--------|-------------|
| RFC-013 | Hierarchical Memory | ✅ Implemented | HOT/WARM/COLD memory tiers |
| RFC-014 | Multi-Topology Memory | ✅ Implemented | Spatial, topological, structural memory |
| RFC-030 | Unified Router | ✅ Implemented | Complexity/intent classification |
| RFC-036 | Artifact-First Planning | ✅ Implemented | Goal → artifact DAG decomposition |

### 📋 Designed (Ready to Implement)

| RFC | Name | Status | Description |
|-----|------|--------|-------------|
| RFC-038 | Harmonic Planning | 📋 Designed | Multi-candidate plan generation |
| RFC-042 | Adaptive Agent | 📋 Designed | Signal-driven technique selection |
| RFC-043 | Sunwell Studio | 📋 Designed | Beautiful minimal GUI |
| RFC-044 | Puzzle Planning | 📋 Designed | Center/middle/edge decomposition |
| RFC-045 | Project Intelligence | 📋 Designed | Persistent codebase mind |
| RFC-046 | Autonomous Backlog | 📋 Designed | Self-directed goal generation |
| RFC-047 | Deep Verification | 📋 Designed | Semantic correctness beyond syntax |

### ⬜ Needed (To Be Designed)

| RFC | Name | Priority | Description |
|-----|------|----------|-------------|
| RFC-048 | Autonomy Guardrails | 🔴 Critical | Safe unsupervised operation |
| RFC-049 | External Integration | 🟡 Medium | CI/Git/Issues connection |
| RFC-050 | Fast Bootstrap | 🟡 Medium | Day-1 intelligence from git |
| RFC-051 | Multi-Instance | 🟢 Low | Parallel autonomous agents |
| RFC-052 | Team Intelligence | 🟢 Future | Shared team decisions |
| RFC-053 | Hybrid Routing | 🟢 Future | Local + cloud model mix |

---

## Implementation Phases

### Phase 1: Intelligent Assistant (Current → Q1)

**Goal**: Sunwell that remembers and learns

```
User: "Build forum app"
Sunwell: [remembers past decisions, applies learned patterns, warns about past failures]
```

**RFCs to complete**:
- [ ] RFC-042 Adaptive Agent (signal-driven execution)
- [ ] RFC-045 Project Intelligence (decision/failure/pattern memory)
- [ ] RFC-044 Puzzle Planning (context-aware decomposition)

**Milestone**: A coding assistant that gets better the more you use it.

---

### Phase 2: Proactive Developer (Q1 → Q2)

**Goal**: Sunwell that sees what needs to be done

```
$ sunwell backlog
📋 Found 7 goals:
  1. [FIX] Failing test in auth_test.py
  2. [FIX] Type error in user.py
  ...

$ sunwell backlog --execute
```

**RFCs to complete**:
- [ ] RFC-046 Autonomous Backlog (goal generation)
- [ ] RFC-050 Fast Bootstrap (kill cold start)
- [ ] RFC-047 Deep Verification (trust the output)

**Milestone**: Sunwell proposes work; human approves and watches.

---

### Phase 3: Autonomous Agent (Q2 → Q3)

**Goal**: Sunwell that works while you sleep

```
$ sunwell backlog --autonomous

🤖 Autonomous mode enabled
   Working on: Fix failing tests, address TODOs, improve coverage
   Pausing for: Complex refactors, architecture changes

[runs overnight]

Morning: 12 goals completed, 3 awaiting review
```

**RFCs to complete**:
- [ ] RFC-048 Autonomy Guardrails (safe unsupervised operation)
- [ ] RFC-049 External Integration (react to CI/git/issues)

**Milestone**: Set it and forget it. Wake up to progress.

---

### Phase 4: Self-Improving System (Q3 → Q4)

**Goal**: Sunwell that improves itself

```
Sunwell observes: "My planning accuracy is 73% on complex tasks"
Sunwell proposes: "RFC-054: Improved complexity detection"
Sunwell implements: [writes the RFC, implements it, validates improvement]
```

**RFCs to complete**:
- [ ] RFC-051 Multi-Instance (parallel agents)
- [ ] Meta-loop capability (Sunwell on Sunwell repo)

**Milestone**: The system that builds itself.

---

### Phase 5: Enterprise Ready (Future)

**Goal**: Teams using Sunwell together

**RFCs to complete**:
- [ ] RFC-052 Team Intelligence Sync
- [ ] RFC-053 Hybrid Model Routing (local + cloud)
- [ ] Security/compliance features

**Milestone**: Enterprise adoption.

---

## Key Metrics

### Intelligence Quality

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Decision recall | > 90% | Can surface relevant decisions from 30+ days ago |
| Pattern accuracy | > 85% | Generated code matches learned style |
| Failure prevention | > 95% | Never suggests previously failed approaches |

### Autonomous Performance

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Goal relevance | > 80% | User executes/accepts generated goals |
| Execution success | > 90% | Goals complete without intervention |
| Stuck rate | < 5% | Goals that require human rescue |

### User Experience

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Setup time | < 15 min | Time from zero to first useful output |
| Cold start value | Day 1 | Fast bootstrap provides immediate intelligence |
| Session continuity | 100% | Never lose context between sessions |

---

## Competitive Position

### vs. Claude Code

| Dimension | Claude Code | Sunwell |
|-----------|-------------|---------|
| Model quality | ✅ Opus-class | ⚠️ Local 7B-70B |
| Memory | ❌ Stateless | ✅ Persistent |
| Privacy | ❌ Cloud | ✅ Local |
| Cost | 💰 Per-request | ✅ Free forever |
| Proactive | ❌ Reactive | ✅ Autonomous |
| Setup | ✅ Zero | ⚠️ 10 minutes |

**Our bet**: Memory + Privacy + Cost > Raw Model Quality for most use cases.

### vs. Cursor/Copilot

| Dimension | Cursor/Copilot | Sunwell |
|-----------|----------------|---------|
| Integration | ✅ IDE-native | ⚠️ Separate tool |
| Completion | ✅ Real-time | ❌ Not focus |
| Agentic | ⚠️ Limited | ✅ Full autonomy |
| Memory | ❌ Session only | ✅ Persistent |
| Planning | ❌ None | ✅ Artifact-first |

**Our bet**: Agentic development > inline completion for complex work.

---

## Risks and Mitigations

### Risk 1: Model Quality Ceiling

**Problem**: Local models can't match Opus for complex reasoning.

**Mitigation**: 
- RFC-053 (Hybrid Routing) allows cloud API for complex tasks
- Focus planning/infrastructure on maximizing what local models CAN do
- Techniques like Vortex/Harmonic extract more from smaller models

### Risk 2: Cold Start Problem

**Problem**: Intelligence needs time to build; day-1 is underwhelming.

**Mitigation**:
- RFC-050 (Fast Bootstrap) mines git history, docs, comments
- Immediate value from signal extraction (tests, TODOs, types)
- Clear UX showing intelligence building over time

### Risk 3: Autonomous Mistakes

**Problem**: Unsupervised agent makes destructive changes.

**Mitigation**:
- RFC-048 (Guardrails) with hard limits on scope
- Auto-approvable only for safe categories (tests, docs)
- Always possible to revert (git)
- Conservative defaults, opt-in to more autonomy

### Risk 4: Complexity Barrier

**Problem**: Too many RFCs, too complex to use.

**Mitigation**:
- Sunwell Studio (RFC-043) hides complexity behind beautiful UI
- "Just works" defaults; power users can configure
- Progressive disclosure: simple → supervised → autonomous

---

## The Dream

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   Monday 9am: "sunwell, let's build a SaaS app this week"           │
│                                                                     │
│   Monday 9pm: Basic CRUD, auth, database — all working              │
│               Sunwell: "I found 3 edge cases in your auth flow.     │
│                        Fixed them while you were at dinner."        │
│                                                                     │
│   Wednesday: Billing integration, Stripe webhooks                   │
│              Sunwell: "I noticed we discussed OAuth last month.     │
│                       Should I add Google/GitHub login?"            │
│                                                                     │
│   Friday: Deploy to production                                      │
│           Sunwell: "CI passed. I'll monitor for errors overnight.   │
│                     Have a good weekend."                           │
│                                                                     │
│   Saturday: Sunwell fixes 2 bugs from production logs               │
│             Sunwell adds test coverage for edge cases it found      │
│             Sunwell proposes 3 improvements for Monday review       │
│                                                                     │
│   Monday: You review, approve, ship. Start the next feature.        │
│                                                                     │
│   Cost: $0                                                          │
│   Data shared: None                                                 │
│   Sleep lost: None                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Next Actions

1. **Implement RFC-042** (Adaptive Agent) — Foundation for everything else
2. **Implement RFC-045** (Project Intelligence) — The moat
3. **Draft RFC-048** (Autonomy Guardrails) — Enable safe autonomous mode
4. **Draft RFC-050** (Fast Bootstrap) — Kill cold start problem
5. **Build RFC-043** (Sunwell Studio) — Beautiful UX that hides complexity

---

## References

- [RFC-042: Adaptive Agent](./RFC-042-adaptive-agent.md)
- [RFC-043: Sunwell Studio](./RFC-043-sunwell-studio.md)
- [RFC-044: Puzzle Planning](./RFC-044-puzzle-planning.md)
- [RFC-045: Project Intelligence](./RFC-045-project-intelligence.md)
- [RFC-046: Autonomous Backlog](./RFC-046-autonomous-backlog.md)
- [RFC-047: Deep Verification](./RFC-047-deep-verification.md)
- [TECHNICAL-VISION.md](../TECHNICAL-VISION.md)

---

*Last updated: 2026-01-19*
