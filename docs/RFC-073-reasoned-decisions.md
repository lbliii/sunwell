# RFC-073: Reasoned Decisions — LLM-Driven Judgment Over Rule-Based Logic

**Status**: Draft (Revised)  
**Created**: 2026-01-21  
**Revised**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 85% 🟢  
**Depends on**:
- RFC-042 (Adaptive Agent) — Execution framework
- RFC-045 (Project Intelligence) — Memory, decisions, failures, patterns
- RFC-046 (Autonomous Backlog) — Goal generation
- RFC-048 (Autonomy Guardrails) — Safety boundaries
- RFC-074 (Incremental Execution) — Provenance tracking, execution history
- Existing: `Discernment` (`src/sunwell/naaru/discernment.py`) — Tiered validation
- Existing: `CodebaseGraph` (`src/sunwell/intelligence/codebase.py`) — Static/dynamic analysis
- Existing: `ArtifactGraph` (`src/sunwell/naaru/artifacts.py`) — Dependency DAG
- Existing: `ExecutionCache` (`src/sunwell/incremental/cache.py`) — Provenance queries

---

## Summary

Replace rule-based decisions throughout Sunwell with **reasoned decisions** — LLM-driven judgments that consider context, history, and nuance. Instead of `if X then Y`, the system asks "given X, what should we do and why?"

**The insight**: Traditional software encodes decisions in code. AI-native software delegates decisions to intelligence. The rules aren't the product — **the reasoning that generates appropriate responses is the product.**

**Core principle**: Every `match` statement, every severity mapping, every threshold check is a candidate for reasoned judgment.

---

## Goals

1. **Context-aware decisions** — Judgments consider surrounding code, project history, user patterns
2. **Explainable reasoning** — Every decision includes rationale, not just outcome
3. **Adaptive behavior** — System learns from feedback on its decisions
4. **Graceful degradation** — Falls back to rules when LLM unavailable or uncertain
5. **Transparent confidence** — Each decision reports how certain the reasoning is
6. **Human alignment** — Decisions converge toward user preferences over time

## Non-Goals

1. **Remove all code logic** — Deterministic operations (parsing, math) stay in code
2. **Eliminate guardrails** — Hard safety limits remain enforced
3. **Slow down fast paths** — Trivial operations don't need LLM reasoning
4. **Replace structural checks** — AST validation, syntax checking stay deterministic

### What Stays Deterministic (Per Domain)

| Domain | Deterministic | Reasoned |
|--------|---------------|----------|
| **Python** | AST parsing, syntax validation, regex matching | Severity, recovery strategy, approval |
| **Rust** | Framework detection, port parsing, lockfile detection | Ambiguous project type, path confidence |
| **TypeScript** | Type definitions, color lookups, DOM rendering | Display variant, escalation UI, tooltips |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Reasoning granularity** | Per-decision, not per-request | Allows mixing reasoned and deterministic in one flow |
| **Fallback strategy** | Reasoner → Rules → Conservative default | Never stuck; graceful degradation |
| **Confidence threshold** | 70% for autonomous, lower for suggestions | High bar for unsupervised action |
| **Learning feedback** | Explicit (user override) + implicit (outcome) | Both signals improve reasoning |
| **Model selection** | Wisdom model for judgment, Voice for execution | Match model capability to task |

### Model Selection Matrix

| Decision Type | Model | Rationale |
|---------------|-------|-----------|
| `severity_assessment` | Wisdom (qwen2.5:14b) | Requires nuanced context understanding |
| `recovery_strategy` | Wisdom (qwen2.5:14b) | Complex error analysis |
| `semantic_approval` | Wisdom (qwen2.5:14b) | Risk assessment needs judgment |
| `display_variant` | Voice (qwen2.5:7b) | Simple mapping, fast response |
| `pattern_extraction` | Wisdom (qwen2.5:14b) | Deep pattern understanding |
| Fallback (any) | Heuristics (Rust) | No LLM, deterministic |

*Note: Model names are Ollama references. Actual models configurable via `sunwell.toml`.*

---

## Motivation

### The Rule Explosion Problem

As Sunwell grows, decision logic accumulates:

```python
# Current: Severity is category-based
if todo_type == "FIXME":
    severity = "high"
elif todo_type == "HACK":
    severity = "medium"
else:
    severity = "low"

# But reality is nuanced:
# - "TODO: handle edge case" in test file → low
# - "TODO: validate payment amounts" in billing.py → critical
# - "FIXME: race condition" in cache.py → high
# - "FIXME: typo in docstring" → low
```

Rules can't capture context. Every edge case requires another branch. The code becomes a brittle decision tree that nobody can reason about.

---

## User Experience

### What the User Sees

From the user's perspective, Reasoned Decisions is **invisible infrastructure** — the system just makes better choices. But when confidence is lower or decisions need explanation, the rationale surfaces.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     END-USER EXPERIENCE FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USER ACTION                    SYSTEM BEHAVIOR                   USER SEES │
│  ────────────                   ───────────────                   ───────── │
│                                                                             │
│  ┌─────────────────┐                                                        │
│  │ sunwell backlog │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────────────────────────┐                               │
│  │ Signal Extraction                        │                               │
│  │ Found: TODO in billing.py:42             │                               │
│  │ "validate payment amounts before save"   │                               │
│  └────────┬────────────────────────────────┘                               │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────────────────────────┐                               │
│  │ REASONER (invisible to user)            │                               │
│  │                                          │                               │
│  │ Context assembled:                       │                               │
│  │ • billing.py in hot_path ✓               │                               │
│  │ • 3 downstream artifacts depend on this  │                               │
│  │ • File has high coupling to payments/    │                               │
│  │ • Similar TODO last week → user fixed it │                               │
│  │ • Past failure: missed validation → bug  │                               │
│  │                                          │                               │
│  │ Decision: severity=CRITICAL (92% conf)   │                               │
│  │ Rationale: "Payment validation in        │                               │
│  │   billing webhook is critical path..."   │                               │
│  └────────┬────────────────────────────────┘                               │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                                                                   │       │
│  │  BACKLOG                                                          │       │
│  │  ════════                                                         │       │
│  │                                                                   │       │
│  │  🔴 CRITICAL  billing.py:42                                       │       │
│  │     "TODO: validate payment amounts before save"                  │       │
│  │     ├─ Why critical? Payment validation in billing webhook.       │ ◄─────┤
│  │     │  3 downstream artifacts. Similar issue caused bug last week.│       │
│  │     └─ [Fix Now] [Dismiss] [Change Priority]                      │       │
│  │                                                                   │       │
│  │  🟡 MEDIUM   cache.py:89                                          │       │
│  │     "FIXME: race condition in cache invalidation"                 │       │
│  │     └─ [Fix Now] [Dismiss]                                        │       │
│  │                                                                   │       │
│  │  🟢 LOW      test_utils.py:15                                     │       │
│  │     "TODO: add more edge case tests"                              │       │
│  │                                                                   │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Interaction Examples

#### Example 1: Backlog Prioritization (CLI)

```bash
$ sunwell backlog

Scanning for signals... found 23 items

BACKLOG (prioritized by reasoned severity)
──────────────────────────────────────────
🔴 CRITICAL (2)
  1. billing.py:42 - TODO: validate payment amounts
     Why: Hot path, 3 dependents, similar issue caused bug
  2. auth.py:156 - FIXME: token refresh race condition
     Why: Error-prone file (5 past failures), security-critical

🟡 MEDIUM (8)
  3. cache.py:89 - FIXME: race condition
     Why: Not in hot path, low coupling
  ...

🟢 LOW (13)
  ...

[1-23] to fix, [d] dismiss, [?] explain priority
> ?1

PRIORITY EXPLANATION for billing.py:42
══════════════════════════════════════
Severity: CRITICAL (confidence: 92%)

Context factors:
  ✓ File is in hot_path (payments flow)
  ✓ 3 downstream artifacts depend on this
  ✓ High coupling score (0.85) with payments/, auth/
  ✓ Change frequency: HIGH (12 changes/month)
  ✓ Similar decision: decision-abc123 was also CRITICAL
  ✓ Past failure: Missed validation in billing caused prod bug (2 weeks ago)

User pattern: You've prioritized payment-related TODOs 8/8 times
```

#### Example 2: Studio UI (Weakness Panel)

```
┌─────────────────────────────────────────────────────────────────┐
│  WEAKNESSES                                        [Filter ▼]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 🔴 CRITICAL                                               │ │
│  │ billing.py:42                                             │ │
│  │ ──────────────────────────────────────────────────────────│ │
│  │ TODO: validate payment amounts before save                │ │
│  │                                                           │ │
│  │ ┌─────────────────────────────────────────────────────┐  │ │
│  │ │ 📊 Why Critical?                              [i]   │  │ │
│  │ │                                                     │  │ │
│  │ │ • In hot path (payments flow)                       │  │ │
│  │ │ • 3 artifacts depend on this                        │  │ │
│  │ │ • Similar TODO fixed last week                      │  │ │
│  │ │ • Past: missed validation → prod bug                │  │ │
│  │ │                                                     │  │ │
│  │ │ Confidence: 92% 🟢                                  │  │ │
│  │ └─────────────────────────────────────────────────────┘  │ │
│  │                                                           │ │
│  │  [Fix with Sunwell]  [Dismiss]  [Change Priority ▼]       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 🟡 MEDIUM                                                 │ │
│  │ cache.py:89                                               │ │
│  │ FIXME: race condition in cache invalidation               │ │
│  │                                                           │ │
│  │  [Fix with Sunwell]  [Dismiss]                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Example 3: User Override → Learning

When a user disagrees with the priority:

```bash
> d1    # dismiss item 1 (the CRITICAL billing.py TODO)

You're dismissing a CRITICAL item. Help me learn:
  [1] Wrong priority - should be lower
  [2] Already handled elsewhere
  [3] Not relevant to this project
  [4] Other
> 1

Got it. What priority feels right?
  [1] High  [2] Medium  [3] Low
> 3

Thanks! Recording: "TODO in billing/ with 'validate' → LOW when user dismisses"
This will improve future prioritization.
```

**Behind the scenes**:
1. `ProjectContext.decisions` records the override
2. `ProjectContext.patterns` learns "this user doesn't prioritize validation TODOs"
3. Next time: Reasoner sees this pattern, adjusts confidence
4. After 5+ similar overrides: System crystallizes rule

### Confidence-Based UI Behavior

| Confidence | User Experience |
|------------|-----------------|
| **90-100%** 🟢 | Silent. Decision applied, no explanation unless asked. |
| **70-89%** 🟡 | Banner. Shows rationale, user can override easily. |
| **50-69%** 🟠 | Modal. Asks user to confirm before proceeding. |
| **<50%** 🔴 | Fallback. Uses rule-based default, flags for review. |

### What's Different from Today

| Today (Rules) | With Reasoned Decisions |
|---------------|------------------------|
| `FIXME` → always HIGH | `FIXME` in test file → LOW |
| `TODO` → always LOW | `TODO` in billing.py → CRITICAL |
| Same priority every time | Learns from your overrides |
| No explanation | Always explains why |
| Can't adapt | Gets better over time |

---

### The Prism Principle Applied to Decisions

The Prism Principle says: small models contain multitudes; Sunwell refracts them into specialized perspectives.

The same principle applies to decisions:

```
Traditional:    Signal → Category → Fixed Severity → Action
Reasoned:       Signal → Context → LLM Judgment → Calibrated Action

              ╱──────── [Code context]
             ╱
Signal ────╱───────── [File importance]
            ╲
             ╲──────── [User patterns]
              ╲
               ╲────── [History of similar issues]
                       
                 ↓
           [Reasoned Judgment]
                 ↓
           severity: critical
           rationale: "Payment validation TODO in billing webhook"
           confidence: 92%
```

### Evidence: Where Rules Fail

| Scenario | Rule-Based | Reasoned |
|----------|------------|----------|
| `TODO: add tests` in `payments.py` | severity: low | severity: high (critical module, no coverage) |
| `FIXME: refactor` in `legacy.py` | severity: high | severity: low (deprecated, scheduled for removal) |
| Test file modification | auto-approve | flag (adds mocks that hide real bugs) |
| 3 consecutive failures | escalate to human | retry with different approach (transient issue) |
| Large file change | block | approve (generated migration, low risk) |

---

## Multi-Domain Coverage

Sunwell is a multi-language codebase. Reasoned decisions must work across all three domains:

| Domain | Location | Decision Examples |
|--------|----------|-------------------|
| **Python** | `src/sunwell/` | Signal severity, recovery strategy, auto-approval |
| **Rust** | `studio/src-tauri/src/` | Heuristic confidence, framework detection, path resolution |
| **Svelte/TypeScript** | `studio/src/` | Display thresholds, risk visualization, UI escalation |

### Cross-Domain Decision Protocol

All domains share a common decision wire format:

```typescript
// Shared across Python, Rust, TypeScript
interface ReasonedDecision {
  decision_type: string;           // e.g., "severity_assessment"
  outcome: unknown;                // Domain-specific result
  confidence: number;              // 0.0 - 1.0
  rationale: string;               // Human-readable explanation
  context_factors: string[];       // What influenced the decision
  similar_decisions?: string[];    // IDs of past similar decisions
}
```

### Domain-Specific Integration

#### Python: Core Reasoning Engine

The Reasoner lives in Python and handles complex judgment:

```python
# Python is the reasoning authority
decision = await reasoner.decide(
    decision_type=DecisionType.SEVERITY_ASSESSMENT,
    context={...},
)
```

#### Rust: Enhanced Heuristics

Rust heuristics provide fast paths. Reasoning enhances ambiguous cases:

```rust
// studio/src-tauri/src/heuristic_detect.rs — MODIFIED

pub fn heuristic_detect(path: &Path, reasoner: Option<&ReasonerClient>) -> Option<RunAnalysis> {
    // Fast path: deterministic heuristics
    if let Some(analysis) = detect_nodejs(path) {
        // If confidence is high, return immediately
        if analysis.confidence == Confidence::High {
            return Some(analysis);
        }
        
        // If ambiguous, enhance with reasoning (if available)
        if let Some(reasoner) = reasoner {
            if let Ok(enhanced) = reasoner.enhance_run_analysis(&analysis, path) {
                return Some(enhanced);
            }
        }
        
        return Some(analysis);
    }
    
    // ... other detections
    None
}
```

**Rust Decision Points to Enhance**:

| Current Code | File | Reasoned Enhancement |
|--------------|------|----------------------|
| Script priority `dev > start > serve` | `heuristic_detect.rs:68-76` | Context-aware: is this a library or app? |
| Framework detection order | `heuristic_detect.rs:133-161` | Consider package.json descriptions |
| Path resolution confidence | `workspace.rs:176-185` | Semantic project understanding |
| `needs_confirmation()` threshold 0.9 | `workspace.rs:42-44` | User pattern-based threshold |

#### Svelte/TypeScript: Display Decisions

Frontend receives decisions and may request clarification:

```typescript
// studio/src/lib/reasoning.ts — NEW

import { invoke } from '@tauri-apps/api/core';

export interface DisplayDecision extends ReasonedDecision {
  display_variant: 'badge' | 'banner' | 'modal' | 'silent';
  color: string;
  icon: string;
}

export async function getDisplayDecision(
  decisionType: string,
  context: Record<string, unknown>
): Promise<DisplayDecision> {
  // Request reasoning from backend
  const decision = await invoke<ReasonedDecision>('reason_decision', {
    decision_type: decisionType,
    context,
  });
  
  // Map to display variant based on confidence and risk
  return {
    ...decision,
    display_variant: mapToDisplayVariant(decision),
    color: getConfidenceColor(decision.confidence),
    icon: getDecisionIcon(decision),
  };
}

function mapToDisplayVariant(decision: ReasonedDecision): DisplayVariant {
  // High confidence, low risk → silent or badge
  if (decision.confidence >= 0.9) return 'badge';
  
  // Moderate confidence → banner with rationale
  if (decision.confidence >= 0.7) return 'banner';
  
  // Low confidence → modal requiring acknowledgment
  return 'modal';
}
```

**TypeScript Decision Points to Enhance**:

| Current Code | File | Reasoned Enhancement |
|--------------|------|----------------------|
| `getSeverityColor()` thresholds | `weakness.ts:129-134` | Context-aware severity display |
| `getRiskColor()` mapping | `weakness.ts:136-147` | User preference learning |
| `getConfidenceColor()` bands | `weakness.ts:149-154` | Calibrated confidence display |
| Critical filter `cascade_risk === 'critical'` | `weakness.svelte.ts:48-51` | Semantic critical detection |

### Decision Flow Across Domains

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-DOMAIN DECISION FLOW                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐   │
│  │     SVELTE      │     │       RUST       │     │     PYTHON       │   │
│  │   (Frontend)    │     │    (Tauri/CLI)   │     │   (Reasoner)     │   │
│  └────────┬────────┘     └────────┬─────────┘     └────────┬─────────┘   │
│           │                       │                        │              │
│           │  User clicks          │                        │              │
│           │  "Fix Weakness"       │                        │              │
│           ▼                       │                        │              │
│  ┌─────────────────┐              │                        │              │
│  │ Check display   │              │                        │              │
│  │ decision cache  │              │                        │              │
│  └────────┬────────┘              │                        │              │
│           │ miss                  │                        │              │
│           ▼                       ▼                        │              │
│  ┌─────────────────────────────────────────┐               │              │
│  │ invoke('reason_decision', context)      │               │              │
│  └─────────────────────────────────────────┘               │              │
│                       │                                    │              │
│                       ▼                                    │              │
│              ┌─────────────────┐                           │              │
│              │ Rust fast path  │                           │              │
│              │ (heuristics)    │                           │              │
│              └────────┬────────┘                           │              │
│                       │                                    │              │
│              ┌────────┴────────┐                           │              │
│              │                 │                           │              │
│              ▼                 ▼                           │              │
│      [High Confidence]  [Low Confidence]                   │              │
│              │                 │                           │              │
│              │                 └───────────────────────────┼──────┐       │
│              │                                             │      │       │
│              │                                             ▼      │       │
│              │                               ┌──────────────────┐ │       │
│              │                               │ Python Reasoner  │ │       │
│              │                               │ (LLM judgment)   │ │       │
│              │                               └────────┬─────────┘ │       │
│              │                                        │           │       │
│              └────────────────────────────────────────┼───────────┘       │
│                                                       │                   │
│                                                       ▼                   │
│                                        ┌──────────────────────────┐       │
│                                        │ ReasonedDecision (JSON)  │       │
│                                        └──────────────────────────┘       │
│                                                       │                   │
│              ◄────────────────────────────────────────┘                   │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     REASONED DECISION ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DECISION POINT                              │   │
│  │          "What severity for this TODO comment?"                  │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CONTEXT ASSEMBLER                             │   │
│  │                                                                  │   │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │   │
│  │   │ Code Context│  │ File Meta   │  │   Memory    │            │   │
│  │   │ (± 20 lines)│  │ (importance)│  │ (patterns)  │            │   │
│  │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │   │
│  │          │                │                │                    │   │
│  │          ▼                ▼                ▼                    │   │
│  │   ┌─────────────────────────────────────────────────────┐      │   │
│  │   │              REASONING PROMPT                        │      │   │
│  │   │                                                      │      │   │
│  │   │   Decision type: severity_assessment                 │      │   │
│  │   │   Signal: TODO comment                               │      │   │
│  │   │   Content: "validate payment amounts"                │      │   │
│  │   │   File: src/billing/webhooks.py                      │      │   │
│  │   │   Context: [surrounding code]                        │      │   │
│  │   │   Past decisions: [similar cases]                    │      │   │
│  │   │   User patterns: [what user cares about]             │      │   │
│  │   └──────────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       REASONER (Wisdom)                          │   │
│  │                                                                  │   │
│  │   Uses tool calling to emit structured judgment:                 │   │
│  │                                                                  │   │
│  │   decide_severity(                                               │   │
│  │       severity="critical",                                       │   │
│  │       confidence=0.92,                                           │   │
│  │       rationale="Payment validation in billing webhook is..."    │   │
│  │       similar_to=["decision-abc123"],                            │   │
│  │   )                                                              │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                    ┌────────────┴────────────┐                         │
│                    │                         │                         │
│                    ▼                         ▼                         │
│            [confidence ≥ 70%]         [confidence < 70%]               │
│                    │                         │                         │
│                    ▼                         ▼                         │
│             Use judgment              Fallback to rules                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Context Sources

The Reasoner's power comes from **rich context assembly**. Unlike simple rule-based decisions that see only the immediate signal, the Reasoner has access to Sunwell's full knowledge graph.

#### Available Context (Per Data Source)

| Source | Data | Use Case |
|--------|------|----------|
| **CodebaseGraph** (RFC-045) | `call_graph`, `import_graph`, `class_hierarchy` | Understand blast radius |
| | `hot_paths`, `error_prone` | Identify critical code paths |
| | `coupling_scores`, `change_frequency` | Assess modification risk |
| | `file_ownership`, `concept_clusters` | Route to right owner, find related code |
| **ArtifactGraph** (RFC-036) | `dependencies`, `execution_waves` | Understand impact on downstream work |
| | `verification_results`, `contracts` | Know what's already validated |
| **ExecutionCache** (RFC-074) | `upstream`, `downstream` (provenance) | Trace lineage of artifacts |
| | `skip_count`, `execution_time_ms` | Identify stable vs. flaky code |
| | `SkipDecision.reason` | Understand why work was/wasn't cached |
| **ProjectContext** (RFC-045) | `decisions` | "We chose OAuth because..." |
| | `failures` | "We tried X, it failed because..." |
| | `patterns` | "This user prefers functional style" |
| **GoalDependencyGraph** (RFC-051) | `file_mapping`, `conflicts` | Parallel scheduling safety |
| **ConversationDAG** (RFC-013) | `learnings`, `dead_ends`, `branches` | What was tried in this session |

#### Context Assembly Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT ASSEMBLER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INPUT: Decision request (e.g., "severity for TODO in billing.py:42")       │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ CodebaseGraph   │  │ ExecutionCache  │  │ ProjectContext  │             │
│  │ (RFC-045)       │  │ (RFC-074)       │  │ (RFC-045)       │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • hot_path? ✓   │  │ • upstream      │  │ • decisions     │             │
│  │ • error_prone?  │  │ • downstream    │  │ • failures      │             │
│  │ • coupling: 0.8 │  │ • skip_count: 5 │  │ • patterns      │             │
│  │ • churn: high   │  │ • exec_time: 2s │  │ • learnings     │             │
│  │ • owner: Alice  │  │ • last_status   │  │ • similar       │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                ▼                                            │
│                    ┌───────────────────────┐                                │
│                    │   ENRICHED CONTEXT    │                                │
│                    │                       │                                │
│                    │   file_path: billing.py                                │
│                    │   in_hot_path: true                                    │
│                    │   error_history: 3 past errors                         │
│                    │   coupling: high (payments, auth)                      │
│                    │   upstream_artifacts: [UserModel, PaymentAPI]          │
│                    │   similar_decisions: [decision-abc, decision-def]      │
│                    │   user_pattern: "prefers explicit error handling"      │
│                    │   past_failure: "missed validation caused prod bug"    │
│                    └───────────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Provenance Queries (Pachyderm-Inspired)

RFC-074's `ExecutionCache` provides O(1) lineage queries via recursive CTE:

```python
# What artifacts does this depend on?
upstream = cache.get_upstream("billing-validation")
# → ["UserModel", "PaymentAPI", "ConfigLoader"]

# What would break if this changes?
downstream = cache.get_downstream("billing-validation")
# → ["CheckoutFlow", "RefundHandler", "AuditLogger"]

# How stable is this artifact?
entry = cache.get("billing-validation")
entry.skip_count  # High = stable, frequently cached
entry.execution_time_ms  # Slow = complex, risky to change
```

This enables reasoning like: *"This TODO is in billing.py which has 3 downstream dependents including CheckoutFlow (critical path). Past executions show high churn. Severity: HIGH."*

### Decision Types

#### Phase 1: Signal Assessment

| Decision Type | Current Logic | Reasoned Judgment |
|--------------|---------------|-------------------|
| `severity_assessment` | Keyword → severity | Context-aware priority |
| `auto_fixable` | Category whitelist | Semantic fix complexity |
| `goal_priority` | Severity sort | Dependency + urgency + patterns |

```python
# src/sunwell/reasoning/decisions.py

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DecisionType(Enum):
    """Types of decisions that can be reasoned about."""
    
    # Phase 1: Signal Assessment
    SEVERITY_ASSESSMENT = "severity_assessment"
    AUTO_FIXABLE = "auto_fixable"
    GOAL_PRIORITY = "goal_priority"
    
    # Phase 2: Error Recovery
    FAILURE_DIAGNOSIS = "failure_diagnosis"
    RECOVERY_STRATEGY = "recovery_strategy"
    RETRY_VS_ABORT = "retry_vs_abort"
    
    # Phase 3: Approval & Escalation
    SEMANTIC_APPROVAL = "semantic_approval"
    ESCALATION_OPTIONS = "escalation_options"
    RISK_ASSESSMENT = "risk_assessment"
    
    # Phase 4: Learning
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    PATTERN_EXTRACTION = "pattern_extraction"
    PREFERENCE_INFERENCE = "preference_inference"


@dataclass(frozen=True, slots=True)
class ReasonedDecision:
    """Result of LLM reasoning about a decision."""
    
    decision_type: DecisionType
    outcome: Any  # Type depends on decision_type
    confidence: float  # 0.0 - 1.0
    rationale: str
    similar_decisions: tuple[str, ...] = ()  # IDs of similar past decisions
    context_used: tuple[str, ...] = ()  # What context influenced the decision
    
    @property
    def is_confident(self) -> bool:
        """Whether confidence meets threshold for autonomous action."""
        return self.confidence >= 0.70
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_type": self.decision_type.value,
            "outcome": self.outcome,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "similar_decisions": list(self.similar_decisions),
            "context_used": list(self.context_used),
        }
```

#### Phase 2: Error Recovery

| Decision Type | Current Logic | Reasoned Judgment |
|--------------|---------------|-------------------|
| `failure_diagnosis` | Error category | Semantic root cause |
| `recovery_strategy` | Fixed retries | Adaptive approach |
| `retry_vs_abort` | Counter threshold | Situation analysis |

```python
@dataclass(frozen=True, slots=True)
class RecoveryDecision(ReasonedDecision):
    """Decision about how to recover from a failure."""
    
    strategy: str  # "retry", "retry_different", "escalate", "abort"
    retry_hint: str | None = None  # Guidance for retry attempt
    escalation_reason: str | None = None  # Why human needed
    
    # Comparison with past failures
    similar_failure_ids: tuple[str, ...] = ()
    past_successful_recovery: str | None = None  # What worked before
```

#### Phase 3: Approval & Escalation

| Decision Type | Current Logic | Reasoned Judgment |
|--------------|---------------|-------------------|
| `semantic_approval` | Category whitelist | Actual change analysis |
| `escalation_options` | Match statement | Contextual options |
| `risk_assessment` | Size thresholds | Semantic impact |

#### Phase 4: Learning

| Decision Type | Current Logic | Reasoned Judgment |
|--------------|---------------|-------------------|
| `root_cause_analysis` | Manual annotation | Automatic diagnosis |
| `pattern_extraction` | Regex detection | Deep pattern understanding |
| `preference_inference` | Accept/reject signals | Behavioral analysis |

### The Reasoner

```python
# src/sunwell/reasoning/reasoner.py

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.models.protocol import GenerateOptions, Tool
from sunwell.reasoning.decisions import DecisionType, ReasonedDecision

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


@dataclass
class Reasoner:
    """LLM-driven decision maker with rich context assembly.
    
    The Reasoner replaces rule-based decisions with reasoned judgments.
    It assembles context from multiple sources (see "Context Sources" section),
    prompts the Wisdom model, and falls back to rules when confidence is low.
    
    Context Sources:
        - CodebaseGraph: Static/dynamic analysis (RFC-045)
        - ExecutionCache: Provenance tracking (RFC-074)
        - ProjectContext: Decision/failure memory (RFC-045)
        - ArtifactGraph: Dependency DAG (RFC-036)
        - ConversationDAG: Session learnings (RFC-013)
    
    Example:
        >>> reasoner = Reasoner(
        ...     model=wisdom_model,
        ...     project_context=project_ctx,
        ...     execution_cache=cache,
        ... )
        >>> decision = await reasoner.decide(
        ...     decision_type=DecisionType.SEVERITY_ASSESSMENT,
        ...     context={"signal": signal, "file_path": path, "content": content},
        ... )
        >>> if decision.is_confident:
        ...     return decision.outcome
        ... else:
        ...     return rule_based_fallback(signal)
    """
    
    model: "ModelProtocol"
    """Wisdom model for reasoning."""
    
    # === Context Sources ===
    
    project_context: Any = None  # ProjectContext from RFC-045
    """Unified context: decisions, failures, patterns, codebase graph."""
    
    execution_cache: Any = None  # ExecutionCache from RFC-074
    """Provenance tracking and execution history."""
    
    artifact_graph: Any = None  # ArtifactGraph from RFC-036
    """Dependency relationships between artifacts."""
    
    conversation_dag: Any = None  # ConversationDAG from RFC-013
    """Session learnings and exploration history."""
    
    # === Configuration ===
    
    fallback_rules: dict[DecisionType, Any] = field(default_factory=dict)
    """Rule-based fallbacks for each decision type."""
    
    confidence_threshold: float = 0.70
    """Minimum confidence for autonomous decisions."""
    
    _decision_history: list[ReasonedDecision] = field(
        default_factory=list, repr=False
    )
    
    async def decide(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
        force_reasoning: bool = False,
    ) -> ReasonedDecision:
        """Make a reasoned decision about the given context.
        
        Args:
            decision_type: What kind of decision to make
            context: Relevant context for the decision
            force_reasoning: If True, don't use fast path even for simple cases
            
        Returns:
            ReasonedDecision with outcome, confidence, and rationale
        """
        # 1. Assemble full context
        enriched = await self._enrich_context(decision_type, context)
        
        # 2. Check for high-confidence match with past decisions
        if not force_reasoning:
            cached = await self._check_similar_decisions(decision_type, enriched)
            if cached and cached.confidence >= 0.90:
                return cached
        
        # 3. Build reasoning prompt
        prompt = self._build_prompt(decision_type, enriched)
        tools = self._get_tools(decision_type)
        
        # 4. Reason with Wisdom model
        try:
            result = await self.model.generate(
                prompt,
                tools=tools,
                tool_choice="required",
                options=GenerateOptions(temperature=0.2),
            )
            
            decision = self._parse_decision(decision_type, result)
            
        except Exception as e:
            # Fallback to rules on any error
            decision = self._apply_fallback(decision_type, context, error=str(e))
        
        # 5. Record for learning
        self._decision_history.append(decision)
        if self.memory:
            await self._record_decision(decision, context)
        
        return decision
    
    async def _enrich_context(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble rich context from all available sources.
        
        Sources (see "Context Sources" section):
        - CodebaseGraph: Static/dynamic analysis (hot paths, coupling, ownership)
        - ExecutionCache: Provenance and execution history (RFC-074)
        - ProjectContext: Decisions, failures, patterns (RFC-045)
        - ArtifactGraph: Dependency relationships (RFC-036)
        """
        enriched = dict(context)
        
        # === CodebaseGraph (RFC-045): Static + Dynamic Analysis ===
        if "file_path" in context:
            graph = await self._load_codebase_graph()
            file_path = Path(context["file_path"])
            
            enriched["in_hot_path"] = file_path in graph.hot_paths
            enriched["is_error_prone"] = file_path in graph.error_prone
            enriched["change_frequency"] = graph.change_frequency.get(file_path, 0.0)
            enriched["file_ownership"] = graph.file_ownership.get(file_path)
            enriched["coupling"] = self._get_coupling_score(graph, file_path)
            enriched["concept_cluster"] = self._find_concept(graph, file_path)
        
        # === ExecutionCache (RFC-074): Provenance + History ===
        if "artifact_id" in context and self.execution_cache:
            artifact_id = context["artifact_id"]
            entry = self.execution_cache.get(artifact_id)
            
            if entry:
                enriched["skip_count"] = entry.skip_count  # High = stable
                enriched["last_execution_time_ms"] = entry.execution_time_ms
                enriched["last_status"] = entry.status.value
            
            # Lineage queries (O(1) via recursive CTE)
            enriched["upstream_artifacts"] = self.execution_cache.get_upstream(artifact_id)
            enriched["downstream_artifacts"] = self.execution_cache.get_downstream(artifact_id)
        
        # === ProjectContext (RFC-045): Memory + Learning ===
        if self.project_context:
            # Past decisions about similar situations
            enriched["similar_decisions"] = await self.project_context.decisions.query_similar(
                decision_type=decision_type.value,
                context=context,
                limit=5,
            )
            
            # Past failures that might be relevant
            enriched["related_failures"] = await self.project_context.failures.query_related(
                file_path=context.get("file_path"),
                error_type=context.get("error_type"),
                limit=3,
            )
            
            # Learned user patterns
            enriched["user_patterns"] = await self.project_context.patterns.get(
                category=decision_type.value,
            )
        
        # === ArtifactGraph (RFC-036): Dependencies ===
        if "artifact_id" in context and self.artifact_graph:
            artifact_id = context["artifact_id"]
            spec = self.artifact_graph.get(artifact_id)
            if spec:
                enriched["artifact_requires"] = list(spec.requires)
                enriched["artifact_contract"] = spec.contract
        
        # === ConversationDAG (RFC-013): Session Context ===
        if self.conversation_dag:
            enriched["session_learnings"] = [
                l.content for l in self.conversation_dag.learnings.values()
            ][:5]
            enriched["dead_ends"] = list(self.conversation_dag.dead_ends)[:3]
        
        return enriched
    
    def _build_prompt(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Build reasoning prompt for the decision type."""
        prompts = {
            DecisionType.SEVERITY_ASSESSMENT: self._severity_prompt,
            DecisionType.RECOVERY_STRATEGY: self._recovery_prompt,
            DecisionType.SEMANTIC_APPROVAL: self._approval_prompt,
            DecisionType.ROOT_CAUSE_ANALYSIS: self._root_cause_prompt,
            # ... other decision types
        }
        
        builder = prompts.get(decision_type)
        if builder:
            return builder(context)
        
        return self._generic_prompt(decision_type, context)
    
    def _severity_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for severity assessment using rich context."""
        return f"""Assess the severity of this code signal.

## Signal
- **Type**: {context.get('signal_type', 'unknown')}
- **Content**: {context.get('content', '')}
- **File**: {context.get('file_path', 'unknown')}

## Surrounding Code
```
{context.get('code_context', 'N/A')}
```

## Codebase Analysis (from CodebaseGraph)
- **In hot path**: {context.get('in_hot_path', 'unknown')}
- **Error-prone file**: {context.get('is_error_prone', 'unknown')}
- **Change frequency**: {context.get('change_frequency', 'unknown')} (high = risky)
- **Coupling score**: {context.get('coupling', 'unknown')} (high = wide blast radius)
- **Concept cluster**: {context.get('concept_cluster', 'unknown')}
- **Owner**: {context.get('file_ownership', 'unknown')}

## Provenance (from ExecutionCache)
- **Upstream artifacts**: {context.get('upstream_artifacts', [])}
- **Downstream artifacts**: {context.get('downstream_artifacts', [])} (what breaks if this changes)
- **Skip count**: {context.get('skip_count', 0)} (high = stable code)
- **Last execution time**: {context.get('last_execution_time_ms', 'N/A')}ms

## Project Memory (from ProjectContext)
**Similar past decisions**:
{self._format_similar(context.get('similar_decisions', []))}

**Related failures** (what went wrong before):
{self._format_failures(context.get('related_failures', []))}

**User patterns**:
{self._format_patterns(context.get('user_patterns', []))}

## Session Context
- **Learnings this session**: {context.get('session_learnings', [])}
- **Dead ends explored**: {context.get('dead_ends', [])}

---

Decide the severity by calling the appropriate tool. Consider:
1. **Hot path?** — Code in hot paths affects more users
2. **Blast radius** — How many downstream artifacts depend on this?
3. **History** — Is this file error-prone? High churn?
4. **Similar decisions** — What severity did we assign to similar signals?
5. **Past failures** — Did ignoring similar signals cause problems before?
6. **User preference** — What has this user cared about historically?"""

    def _get_tools(self, decision_type: DecisionType) -> tuple[Tool, ...]:
        """Get tool definitions for structured output."""
        if decision_type == DecisionType.SEVERITY_ASSESSMENT:
            return (
                Tool(
                    name="decide_severity",
                    description="Assess severity of a code signal",
                    parameters={
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low"],
                                "description": "Assessed severity level",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence 0-1 in this assessment",
                            },
                            "rationale": {
                                "type": "string",
                                "description": "Why this severity was chosen",
                            },
                            "context_factors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "What factors influenced the decision",
                            },
                        },
                        "required": ["severity", "confidence", "rationale"],
                    },
                ),
            )
        
        # ... tools for other decision types
        return ()
    
    def _apply_fallback(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
        error: str | None = None,
    ) -> ReasonedDecision:
        """Apply rule-based fallback when reasoning fails."""
        fallback = self.fallback_rules.get(decision_type)
        
        if fallback:
            outcome = fallback(context)
        else:
            outcome = self._conservative_default(decision_type)
        
        return ReasonedDecision(
            decision_type=decision_type,
            outcome=outcome,
            confidence=0.5,  # Low confidence for fallback
            rationale=f"Fallback: {error}" if error else "Fallback to rules",
        )
```

### Integration Points

#### 1. Signal Extraction (Phase 1)

```python
# src/sunwell/backlog/signals.py — MODIFIED

class SignalExtractor:
    """Extract observable signals from codebase."""
    
    def __init__(
        self,
        root: Path | None = None,
        reasoner: Reasoner | None = None,  # NEW
    ):
        self.root = Path(root) if root else Path.cwd()
        self.reasoner = reasoner  # LLM reasoning for severity
    
    async def _assess_severity(
        self,
        signal: ObservableSignal,
        code_context: str,
    ) -> Literal["critical", "high", "medium", "low"]:
        """Assess severity using reasoning or rules."""
        
        if self.reasoner:
            decision = await self.reasoner.decide(
                decision_type=DecisionType.SEVERITY_ASSESSMENT,
                context={
                    "signal_type": signal.signal_type,
                    "content": signal.message,
                    "file_path": str(signal.location.file),
                    "code_context": code_context,
                },
            )
            
            if decision.is_confident:
                return decision.outcome
        
        # Fallback to rule-based
        return self._rule_based_severity(signal)
```

#### 2. Error Recovery (Phase 2)

```python
# src/sunwell/adaptive/fixer.py — MODIFIED

class FixStage:
    """Fix errors with reasoned recovery strategies."""
    
    async def handle_failure(
        self,
        error: Exception,
        context: FailureContext,
    ) -> RecoveryAction:
        """Decide how to recover from a failure."""
        
        decision = await self.reasoner.decide(
            decision_type=DecisionType.RECOVERY_STRATEGY,
            context={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "stack_trace": context.stack_trace,
                "attempt_number": context.attempt_number,
                "code_being_generated": context.code,
                "past_failures": context.past_failures,
            },
        )
        
        if decision.outcome == "retry_different":
            # LLM suggests a different approach
            return RecoveryAction(
                strategy="retry",
                hint=decision.retry_hint,
                confidence=decision.confidence,
            )
        elif decision.outcome == "escalate":
            return RecoveryAction(
                strategy="escalate",
                reason=decision.escalation_reason,
            )
        else:
            return RecoveryAction(strategy=decision.outcome)
```

#### 3. Guardrails (Phase 3)

```python
# src/sunwell/guardrails/system.py — MODIFIED

class GuardrailSystem:
    """Guardrails with semantic approval reasoning."""
    
    async def can_auto_approve(self, goal: Goal) -> bool:
        """Check if goal can be auto-approved using reasoning."""
        
        decision = await self.reasoner.decide(
            decision_type=DecisionType.SEMANTIC_APPROVAL,
            context={
                "goal_title": goal.title,
                "goal_category": goal.category,
                "files_affected": goal.estimated_files,
                "change_description": goal.description,
            },
        )
        
        if decision.is_confident:
            if decision.outcome == "approve":
                return True
            elif decision.outcome == "flag":
                # LLM identified risk despite category
                return False
        
        # Fallback to category-based rules
        return goal.auto_approvable
```

#### 4. Learning (Phase 4)

```python
# src/sunwell/intelligence/failures.py — MODIFIED

class FailureMemory:
    """Remember failures with reasoned root cause analysis."""
    
    async def record_failure(
        self,
        failure: FailedApproach,
    ) -> FailedApproach:
        """Record failure with automatic root cause analysis."""
        
        # Use LLM to diagnose root cause
        decision = await self.reasoner.decide(
            decision_type=DecisionType.ROOT_CAUSE_ANALYSIS,
            context={
                "description": failure.description,
                "error_type": failure.error_type,
                "error_message": failure.error_message,
                "code_snapshot": failure.code_snapshot,
                "similar_failures": await self._find_similar(failure),
            },
        )
        
        if decision.is_confident:
            # Enrich failure with reasoned analysis
            return FailedApproach(
                **failure.__dict__,
                root_cause=decision.rationale,
                similar_to=list(decision.similar_decisions),
            )
        
        return failure
```

### Rust Reasoning Bridge

The Tauri backend bridges frontend requests to the Python reasoner:

```rust
// studio/src-tauri/src/reasoning.rs — NEW

use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReasonedDecision {
    pub decision_type: String,
    pub outcome: serde_json::Value,
    pub confidence: f32,
    pub rationale: String,
    pub context_factors: Vec<String>,
    pub similar_decisions: Vec<String>,
}

/// Request reasoning from Python backend.
/// 
/// Falls back to heuristic rules if Python unavailable.
#[tauri::command]
pub async fn reason_decision(
    decision_type: String,
    context: serde_json::Value,
) -> Result<ReasonedDecision, String> {
    // Try Python reasoner first
    let output = Command::new("sunwell")
        .args(["reason", &decision_type, "--context", &context.to_string(), "--json"])
        .output();
    
    match output {
        Ok(out) if out.status.success() => {
            serde_json::from_slice(&out.stdout)
                .map_err(|e| format!("Failed to parse reasoning: {}", e))
        }
        _ => {
            // Fallback to Rust heuristics
            Ok(heuristic_fallback(&decision_type, &context))
        }
    }
}

fn heuristic_fallback(decision_type: &str, context: &serde_json::Value) -> ReasonedDecision {
    // Rule-based fallback when Python unavailable
    match decision_type {
        "severity_assessment" => severity_heuristic(context),
        "display_variant" => display_heuristic(context),
        _ => ReasonedDecision {
            decision_type: decision_type.to_string(),
            outcome: serde_json::json!("unknown"),
            confidence: 0.5,
            rationale: "Heuristic fallback - Python reasoner unavailable".to_string(),
            context_factors: vec![],
            similar_decisions: vec![],
        },
    }
}

fn severity_heuristic(context: &serde_json::Value) -> ReasonedDecision {
    let signal_type = context.get("signal_type")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    
    let (severity, confidence) = match signal_type {
        "fixme_comment" => ("high", 0.8),
        "todo_comment" => ("low", 0.7),
        "type_error" => ("high", 0.9),
        "lint_warning" => ("medium", 0.85),
        _ => ("medium", 0.5),
    };
    
    ReasonedDecision {
        decision_type: "severity_assessment".to_string(),
        outcome: serde_json::json!(severity),
        confidence,
        rationale: format!("Heuristic: {} typically has {} severity", signal_type, severity),
        context_factors: vec![format!("signal_type={}", signal_type)],
        similar_decisions: vec![],
    }
}

fn display_heuristic(context: &serde_json::Value) -> ReasonedDecision {
    let confidence = context.get("confidence")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.5) as f32;
    
    let variant = if confidence >= 0.9 {
        "badge"
    } else if confidence >= 0.7 {
        "banner"
    } else {
        "modal"
    };
    
    ReasonedDecision {
        decision_type: "display_variant".to_string(),
        outcome: serde_json::json!(variant),
        confidence: 0.85,
        rationale: format!("Confidence {} maps to {} display", confidence, variant),
        context_factors: vec![format!("confidence={}", confidence)],
        similar_decisions: vec![],
    }
}
```

### Confidence Threshold Consistency

All domains must use consistent confidence thresholds:

```yaml
# Shared thresholds across Python, Rust, TypeScript
thresholds:
  autonomous_action: 0.70      # Can act without human approval
  high_confidence: 0.90        # Skip confirmation dialogs
  needs_confirmation: 0.70     # Show rationale in UI
  escalate_to_human: 0.50      # Require explicit approval
  fallback_to_rules: 0.50      # Use heuristic instead of reasoning

# Domain-specific applications
python:
  auto_approve_threshold: 0.70     # GuardrailSystem.can_auto_approve()
  calibration_target: 0.10         # ±10% accuracy

rust:
  needs_confirmation: 0.90         # workspace.rs:42-44
  heuristic_confidence_high: 0.85  # Skip reasoning for obvious cases

typescript:
  badge_threshold: 0.90            # Silent display
  banner_threshold: 0.70           # Show rationale
  modal_threshold: 0.50            # Require acknowledgment
```

### Learning Loop

```
┌────────────────────────────────────────────────────────────────────┐
│                      LEARNING LOOP                                  │
│                                                                    │
│   Decision Made                                                    │
│        │                                                           │
│        ▼                                                           │
│   ┌─────────────┐                                                  │
│   │   Record    │────────────────────────────────────────┐         │
│   │  Decision   │                                        │         │
│   └──────┬──────┘                                        │         │
│          │                                               │         │
│          ▼                                               ▼         │
│   ┌─────────────┐                              ┌─────────────┐     │
│   │   Observe   │                              │   Pattern   │     │
│   │   Outcome   │                              │   Database  │     │
│   └──────┬──────┘                              └─────────────┘     │
│          │                                               ▲         │
│          ▼                                               │         │
│   ┌─────────────────────────────────────────────────────────┐     │
│   │                  FEEDBACK SIGNALS                        │     │
│   │                                                          │     │
│   │  EXPLICIT:                   IMPLICIT:                   │     │
│   │  - User overrides decision   - Task succeeded            │     │
│   │  - User selects different    - Task failed               │     │
│   │  - User provides correction  - Similar pattern later     │     │
│   │                                                          │     │
│   └─────────────────────────────────────────────────────────┘     │
│          │                                                         │
│          ▼                                                         │
│   ┌─────────────┐                                                  │
│   │   Update    │                                                  │
│   │  Patterns   │──────────────────────────────────────────────────┘
│   └─────────────┘                                                  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Confidence Calibration

```python
@dataclass
class ConfidenceCalibrator:
    """Calibrate reasoner confidence based on historical accuracy."""
    
    async def calibrate(
        self,
        decision: ReasonedDecision,
        outcome: bool,  # Was the decision correct?
    ) -> None:
        """Update calibration based on outcome.
        
        If decisions at 80% confidence are only correct 60% of the time,
        adjust future confidence scores downward.
        """
        # Record outcome
        self._outcomes.append((decision.confidence, outcome))
        
        # Compute calibration curve
        # If model says 80% confident, should be right 80% of the time
        # Adjust future scores: adjusted = f(raw_confidence, calibration_curve)
```

---

## Implementation Plan

### Phase 1: Core Reasoner + Python Integration (Week 1-2)

**Python Domain**:
1. **Implement Reasoner core** (`src/sunwell/reasoning/reasoner.py`)
2. **Integrate with SignalExtractor** for severity reasoning
3. **Add fallback rules** for all decision types
4. **Benchmark accuracy** against current rule-based system

**Deliverables**:
- `src/sunwell/reasoning/reasoner.py` — Core reasoner
- `src/sunwell/reasoning/decisions.py` — Decision types
- `src/sunwell/cli/reason.py` — CLI interface for cross-domain access

### Phase 2: Rust Bridge + Heuristic Enhancement (Week 3-4)

**Rust Domain**:
1. **Add reasoning bridge** (`studio/src-tauri/src/reasoning.rs`)
2. **Enhance heuristic_detect** with reasoning fallback
3. **Update workspace.rs** confidence logic
4. **Add Tauri command** for frontend access

**Python Domain**:
1. **Extend Reasoner** with recovery decision types
2. **Integrate with FixStage** (formerly AdaptiveFixer)
3. **Add failure pattern matching**

**Deliverables**:
- `studio/src-tauri/src/reasoning.rs` — Tauri reasoning bridge
- Modified `studio/src-tauri/src/heuristic_detect.rs`
- Modified `studio/src-tauri/src/commands.rs`

### Phase 3: Frontend Integration + Display Decisions (Week 5-6)

**Svelte/TypeScript Domain**:
1. **Add reasoning client** (`studio/src/lib/reasoning.ts`)
2. **Create display decision logic** with threshold mapping
3. **Update weakness display** to use reasoned severity
4. **Add rationale tooltips** for moderate-confidence decisions

**Python Domain**:
1. **Add semantic approval decisions**
2. **Integrate with GuardrailSystem**
3. **Generate contextual escalation options**

**Deliverables**:
- `studio/src/lib/reasoning.ts` — Frontend reasoning client
- Modified `studio/src/lib/types/weakness.ts`
- Modified `studio/src/stores/weakness.svelte.ts`

### Phase 4: Learning Loop + Cross-Domain Calibration (Week 7-8)

**All Domains**:
1. **Implement root cause analysis** (Python)
2. **Add pattern extraction** (Python → shared storage)
3. **Build preference inference** (Python + TypeScript UI)
4. **Cross-domain calibration system**
5. **Threshold synchronization** across Python/Rust/TypeScript

**Deliverables**:
- `src/sunwell/reasoning/calibration.py`
- Shared threshold config (loaded by all domains)
- Updated `studio/src/lib/constants.ts` with thresholds

---

## Metrics

### Decision Quality (All Domains)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Agreement with user | ≥85% | User overrides / total decisions |
| Confidence calibration | ±10% | Predicted vs actual accuracy |
| Cross-domain consistency | ≥95% | Same input → same decision across domains |

### Latency Targets (Per Domain)

| Domain | Fast Path | Reasoning Path | Measurement |
|--------|-----------|----------------|-------------|
| **Python** (Reasoner) | N/A | <2000ms P95 | Full LLM reasoning |
| **Rust** (Heuristics) | <10ms P95 | <50ms P95 | Heuristic or cached |
| **TypeScript** (Display) | <5ms P95 | <100ms P95 | IPC to Rust/cached |

*Note: Original 500ms target was unrealistic for Wisdom model. Revised to 2000ms for full reasoning, with fast paths for high-confidence cases.*

### System Impact

| Metric | Before | Target |
|--------|--------|--------|
| False positive rate (severity) | ~30% | <10% |
| Unnecessary escalations | ~40% | <15% |
| Failed recovery attempts | ~50% | <25% |
| Heuristic-only decisions | 0% | ~80% (fast path) |

### Testing Strategy

| Test Type | Scope | Method |
|-----------|-------|--------|
| **Unit** | Individual decision types | Mock context, verify output shape |
| **Integration** | Cross-domain flow | E2E: Svelte → Rust → Python → response |
| **Calibration** | Confidence accuracy | Historical decisions + outcomes dataset |
| **A/B** | Reasoning vs heuristics | Shadow mode, compare user corrections |
| **Regression** | Threshold drift | Weekly calibration curve checks |

```python
# Example calibration test
def test_confidence_calibration():
    """Decisions at 80% confidence should be correct ~80% of the time."""
    decisions = load_historical_decisions(confidence_band=(0.75, 0.85))
    accuracy = sum(d.was_correct for d in decisions) / len(decisions)
    assert 0.70 <= accuracy <= 0.90, f"Calibration off: {accuracy:.0%}"
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Slow decisions | Fast path for high-confidence cached decisions |
| Wrong decisions | Conservative fallback + learning from overrides |
| Inconsistent reasoning | Calibration + similar decision retrieval |
| Model unavailable | Rule-based fallback for all decision types |
| User trust | Transparent rationale + confidence display |
| **Cross-domain drift** | Shared threshold config + consistency tests |
| **IPC latency** | Rust caching layer + batched requests |
| **Frontend blocking** | Async reasoning with optimistic UI |
| **Rust/Python version mismatch** | Shared JSON schema + contract tests |

---

## Future Directions

### LLM-as-Orchestrator

Once reasoning is proven, extend to meta-decisions:
- "Should I use artifact planning or agent planning for this goal?"
- "What validation strategy is appropriate here?"
- "Should I execute serially or in parallel?"

The Reasoner becomes the coordinator of coordinators — it doesn't just make leaf decisions, it decides *how* to structure the decision process itself.

### Self-Improving Rules

When the Reasoner consistently makes the same judgment, crystallize it into a rule:
- "I've seen 50 cases where TODO in billing/ is critical — add explicit rule"
- "Recovery strategy X works 90% of the time for error Y — encode it"

The system evolves its rule base based on accumulated reasoning.

---

## File Deliverables Summary

### Python (`src/sunwell/`)

| File | Purpose |
|------|---------|
| `reasoning/reasoner.py` | Core Reasoner class |
| `reasoning/decisions.py` | DecisionType enum, ReasonedDecision dataclass |
| `reasoning/calibration.py` | ConfidenceCalibrator for learning |
| `cli/reason.py` | CLI interface for cross-domain access |

### Rust (`studio/src-tauri/src/`)

| File | Purpose |
|------|---------|
| `reasoning.rs` | Tauri bridge to Python reasoner |
| `heuristic_detect.rs` (modified) | Enhanced with reasoning fallback |
| `workspace.rs` (modified) | Pattern-based confidence |
| `commands.rs` (modified) | New `reason_decision` command |

### TypeScript (`studio/src/`)

| File | Purpose |
|------|---------|
| `lib/reasoning.ts` | Frontend reasoning client |
| `lib/types/weakness.ts` (modified) | Add ReasonedDecision type |
| `lib/constants.ts` (modified) | Shared thresholds |
| `stores/weakness.svelte.ts` (modified) | Use reasoned severity |

---

## Related RFCs

### Context Sources (Required)
- **RFC-013 (Simulacrum)**: ConversationDAG — session learnings, dead ends, branches
- **RFC-036 (Artifact-First Planning)**: ArtifactGraph — dependency DAG, execution waves
- **RFC-045 (Project Intelligence)**: ProjectContext — decisions, failures, patterns, CodebaseGraph
- **RFC-074 (Incremental Execution)**: ExecutionCache — provenance queries, execution history (Pachyderm-inspired)

### Consumers
- **RFC-042 (Adaptive Agent)**: Uses Reasoner for execution decisions
- **RFC-046 (Autonomous Backlog)**: Priority reasoning
- **RFC-047 (Deep Verification)**: Confidence triangulation
- **RFC-048 (Autonomy Guardrails)**: Escalation reasoning
- **RFC-065 (Unified Memory)**: Pattern storage and retrieval
- **RFC-066 (Run Detection)**: Rust heuristics enhanced by reasoning

---

## Summary

Reasoned Decisions transforms Sunwell from a rule-executor to a judgment-maker. Instead of encoding every edge case in code, we delegate nuanced decisions to LLM reasoning with context, history, and calibrated confidence.

**The bet**: Reasoning + Context + Learning > Hardcoded Rules for complex decisions.

**The constraint**: Fast paths stay fast, safety limits stay enforced, fallbacks always exist.

**The outcome**: A system that makes better decisions over time because it *reasons* about each situation rather than pattern-matching against rigid categories.
