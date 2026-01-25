# S-Tier Coverage Analysis Methodology

**Purpose**: Systematic process for ensuring comprehensive user journey, edge case, and feature coverage in any RFC, feature, or system design.

**When to Use**: Before finalizing any RFC, during design reviews, or when auditing existing features for gaps.

---

## Quick Start

```
1. Run ACTOR IDENTIFICATION         → Who/what interacts with this?
2. Run JOURNEY MAPPING              → What do they do, step by step?
3. Run EDGE CASE EXTRACTION         → What can go wrong?
4. Run FEATURE MATRIX               → What capabilities are needed?
5. Run COVERAGE AUDIT               → Is everything tested?
6. Run GAP ANALYSIS                 → What's missing?
```

---

## Phase 1: Actor Identification

### 1.1 Internal Actors (System Components)

List every system component that interacts with this feature.

```markdown
| Actor | Role | Entry Points | Exit Points |
|-------|------|--------------|-------------|
| [Component Name] | [What it does] | [How it receives input] | [What it produces] |
```

**Prompts to fill this table**:
- "What code modules touch this feature?"
- "What data flows through this feature?"
- "What services/APIs does this call?"
- "What services/APIs call this?"

### 1.2 External Actors (Human Users)

List every human role that interacts with this feature.

```markdown
| Actor | Goals | Context | Constraints |
|-------|-------|---------|-------------|
| [Role Name] | [What they want] | [When/where they use this] | [Limitations they face] |
```

**Prompts to fill this table**:
- "Who initiates this feature?"
- "Who observes the results?"
- "Who configures/maintains this?"
- "Who debugs when it fails?"
- "Who is affected by its behavior?"

### 1.3 Actor Checklist

- [ ] **Primary user** — The main person who triggers this feature
- [ ] **Secondary users** — People who interact with outputs
- [ ] **Administrators** — People who configure/manage
- [ ] **Developers** — People who extend/debug
- [ ] **Automated systems** — Cron jobs, CI/CD, monitoring
- [ ] **Upstream services** — What calls this?
- [ ] **Downstream services** — What does this call?

---

## Phase 2: Journey Mapping

### 2.1 Journey Template

For each actor, map their complete journey:

```markdown
## [Actor Name] Journey: [Journey Name]

### Trigger
What initiates this journey?

### Preconditions
What must be true before this journey starts?

### Steps
| Step | Action | System Response | Data Changed |
|------|--------|-----------------|--------------|
| 1 | [What actor does] | [What system does] | [State changes] |
| 2 | ... | ... | ... |

### Success Outcome
What does "done" look like?

### Failure Modes
What can go wrong at each step?

### Recovery Paths
How does the actor recover from failures?
```

### 2.2 Journey Categories

Map journeys in these categories:

#### Happy Path Journeys
The normal, expected flows when everything works.

```markdown
| ID | Journey | Actor | Frequency | Priority |
|----|---------|-------|-----------|----------|
| HP1 | [Name] | [Actor] | [Daily/Weekly/etc] | [P0/P1/P2] |
```

#### Configuration Journeys
Setting up, customizing, or changing behavior.

```markdown
| ID | Journey | Actor | Frequency | Priority |
|----|---------|-------|-----------|----------|
| CF1 | [Name] | [Actor] | [Frequency] | [Priority] |
```

#### Error Recovery Journeys
What happens when things go wrong.

```markdown
| ID | Journey | Actor | Trigger | Recovery Path |
|----|---------|-------|---------|---------------|
| ER1 | [Name] | [Actor] | [What failed] | [How to fix] |
```

#### Edge Case Journeys
Unusual but valid use cases.

```markdown
| ID | Journey | Actor | Conditions | Expected Behavior |
|----|---------|-------|------------|-------------------|
| EC1 | [Name] | [Actor] | [When this happens] | [What should occur] |
```

### 2.3 Journey Discovery Prompts

Ask these questions to find missing journeys:

**For Happy Paths**:
- "What's the most common way to use this?"
- "What's the simplest successful interaction?"
- "What does a new user do first?"
- "What does a power user do differently?"

**For Configuration**:
- "What can be customized?"
- "What needs to be set up before first use?"
- "What might change after initial setup?"
- "What settings affect behavior?"

**For Error Recovery**:
- "What if the network is down?"
- "What if data is corrupted?"
- "What if permissions are wrong?"
- "What if resources are exhausted?"
- "What if the user makes a mistake?"
- "What if an upstream service fails?"

**For Edge Cases**:
- "What if the input is empty?"
- "What if the input is maximum size?"
- "What if the input has special characters?"
- "What if two users do this simultaneously?"
- "What if this runs for a very long time?"
- "What if this is interrupted mid-way?"

---

## Phase 3: Edge Case Extraction

### 3.1 Edge Case Categories

#### Input Edge Cases
```markdown
| ID | Category | Condition | Expected Behavior | Test |
|----|----------|-----------|-------------------|------|
| IE1 | Empty | No input provided | [Behavior] | [ ] |
| IE2 | Minimal | Smallest valid input | [Behavior] | [ ] |
| IE3 | Maximum | Largest valid input | [Behavior] | [ ] |
| IE4 | Boundary | Just at limits | [Behavior] | [ ] |
| IE5 | Overflow | Beyond limits | [Behavior] | [ ] |
| IE6 | Invalid type | Wrong data type | [Behavior] | [ ] |
| IE7 | Malformed | Syntactically invalid | [Behavior] | [ ] |
| IE8 | Unicode | Special characters | [Behavior] | [ ] |
| IE9 | Injection | Potentially malicious | [Behavior] | [ ] |
```

#### State Edge Cases
```markdown
| ID | Category | Condition | Expected Behavior | Test |
|----|----------|-----------|-------------------|------|
| SE1 | Uninitialized | Before first use | [Behavior] | [ ] |
| SE2 | Mid-operation | During processing | [Behavior] | [ ] |
| SE3 | Post-failure | After error | [Behavior] | [ ] |
| SE4 | Concurrent | Multiple simultaneous | [Behavior] | [ ] |
| SE5 | Stale | Outdated data | [Behavior] | [ ] |
| SE6 | Locked | Resource unavailable | [Behavior] | [ ] |
```

#### Environment Edge Cases
```markdown
| ID | Category | Condition | Expected Behavior | Test |
|----|----------|-----------|-------------------|------|
| EE1 | No network | Connection lost | [Behavior] | [ ] |
| EE2 | Slow network | High latency | [Behavior] | [ ] |
| EE3 | No disk | Storage full | [Behavior] | [ ] |
| EE4 | No memory | RAM exhausted | [Behavior] | [ ] |
| EE5 | No permissions | Access denied | [Behavior] | [ ] |
| EE6 | Wrong version | Dependency mismatch | [Behavior] | [ ] |
| EE7 | Clock skew | Time out of sync | [Behavior] | [ ] |
```

#### Timing Edge Cases
```markdown
| ID | Category | Condition | Expected Behavior | Test |
|----|----------|-----------|-------------------|------|
| TE1 | Timeout | Operation too slow | [Behavior] | [ ] |
| TE2 | Race | Concurrent modification | [Behavior] | [ ] |
| TE3 | Interrupt | User cancels | [Behavior] | [ ] |
| TE4 | Retry | After failure | [Behavior] | [ ] |
| TE5 | Idempotent | Same operation twice | [Behavior] | [ ] |
```

### 3.2 Edge Case Discovery Matrix

Cross-reference inputs with states:

```
              │ Empty │ Valid │ Maximum │ Invalid │
──────────────┼───────┼───────┼─────────┼─────────┤
Uninitialized │  E1   │  E2   │   E3    │   E4    │
Normal        │  E5   │  E6   │   E7    │   E8    │
Mid-operation │  E9   │  E10  │   E11   │   E12   │
Post-failure  │  E13  │  E14  │   E15   │   E16   │
```

---

## Phase 4: Feature Matrix

### 4.1 Core Features

```markdown
| Feature | Description | Journeys Covered | Status |
|---------|-------------|------------------|--------|
| F1 | [What it does] | HP1, HP2, EC3 | ✅ |
| F2 | [What it does] | HP3, ER1 | ⚠️ Partial |
| F3 | [What it does] | - | ❌ Missing |
```

### 4.2 Feature Categories

#### Functional Features
- [ ] Core business logic
- [ ] Input validation
- [ ] Output formatting
- [ ] State management
- [ ] Error handling

#### Non-Functional Features
- [ ] Performance (latency, throughput)
- [ ] Scalability (concurrent users, data size)
- [ ] Reliability (uptime, recovery)
- [ ] Security (auth, sanitization)
- [ ] Observability (logging, metrics, traces)

#### Developer Experience Features
- [ ] API clarity
- [ ] Error messages
- [ ] Documentation
- [ ] Testing support
- [ ] Debug tooling

#### User Experience Features
- [ ] Progress visibility
- [ ] Cancellation support
- [ ] Feedback clarity
- [ ] Recovery guidance
- [ ] Accessibility

### 4.3 Feature Discovery Prompts

**For Core Features**:
- "What MUST this do to be useful?"
- "What's the minimum viable version?"
- "What would cause users to abandon this?"

**For Quality Features**:
- "How fast must this be?"
- "How many users might use this simultaneously?"
- "What happens if it fails?"
- "What data is sensitive?"

**For Experience Features**:
- "How does the user know it's working?"
- "How does the user know it failed?"
- "How does the user recover?"
- "How does a developer debug this?"

---

## Phase 5: Coverage Audit

### 5.1 Journey → Test Matrix

```markdown
| Journey | Unit Tests | Integration Tests | E2E Tests | Manual Tests |
|---------|------------|-------------------|-----------|--------------|
| HP1     | ✅ 3 tests | ✅ 1 test         | ⚠️ TODO   | N/A          |
| HP2     | ✅ 2 tests | ❌ None           | ❌ None   | N/A          |
| ER1     | ✅ 1 test  | ✅ 1 test         | N/A       | ✅ Runbook   |
```

### 5.2 Edge Case → Test Matrix

```markdown
| Edge Case | Covered By | Test Location | Status |
|-----------|------------|---------------|--------|
| IE1       | test_empty_input | test_foo.py:45 | ✅ |
| IE2       | - | - | ❌ Missing |
| SE3       | test_post_failure | test_bar.py:89 | ✅ |
```

### 5.3 Feature → Test Matrix

```markdown
| Feature | Test Coverage | Files | Priority |
|---------|---------------|-------|----------|
| F1      | 95%           | test_core.py | P0 |
| F2      | 60%           | test_secondary.py | P1 |
| F3      | 0%            | - | P2 |
```

### 5.4 Coverage Gaps Report

```markdown
## Coverage Summary

| Category | Total | Covered | Gap | % |
|----------|-------|---------|-----|---|
| Happy Paths | 5 | 5 | 0 | 100% |
| Error Recovery | 8 | 6 | 2 | 75% |
| Edge Cases | 20 | 12 | 8 | 60% |
| Features | 15 | 14 | 1 | 93% |

## Critical Gaps (Must Fix)
1. [Gap 1] - [Why it matters]
2. [Gap 2] - [Why it matters]

## Important Gaps (Should Fix)
1. [Gap 1] - [Why it matters]

## Nice-to-Have Gaps (Could Fix)
1. [Gap 1] - [Why it matters]
```

---

## Phase 6: Gap Analysis

### 6.1 Gap Discovery Questions

**Journey Gaps**:
- "Are there any actors we haven't considered?"
- "Are there any journeys that don't have a happy ending?"
- "Are there any journeys that can't be recovered?"
- "Are there any implicit journeys we forgot?"

**Edge Case Gaps**:
- "What's the worst input we could receive?"
- "What state could the system be in that we haven't tested?"
- "What environmental conditions haven't we considered?"
- "What timing issues might occur?"

**Feature Gaps**:
- "What would a competitor have that we don't?"
- "What would make a user say 'this is amazing'?"
- "What would make a developer say 'this is easy'?"
- "What would a security auditor ask about?"

### 6.2 Gap Prioritization

```markdown
| Gap ID | Description | Impact | Effort | Priority |
|--------|-------------|--------|--------|----------|
| G1 | [What's missing] | [User impact] | [Dev effort] | P0/P1/P2 |
```

**Impact Scoring**:
- **Critical (P0)**: Users cannot accomplish core task
- **High (P1)**: Users can work around but with pain
- **Medium (P2)**: Nice to have, improves experience
- **Low (P3)**: Edge case that rarely occurs

### 6.3 Gap Resolution

For each gap, document:

```markdown
## Gap: [ID] - [Description]

### Impact
Who is affected and how?

### Root Cause
Why was this missed?

### Proposed Solution
How do we fix it?

### Acceptance Criteria
How do we know it's fixed?

### Test Coverage
What tests will verify this?
```

---

## Checklists

### Pre-RFC Checklist

Before starting an RFC, verify:

- [ ] All actors identified
- [ ] All happy path journeys mapped
- [ ] All error recovery journeys mapped
- [ ] Edge cases extracted per category
- [ ] Features categorized
- [ ] Non-functional requirements listed

### Pre-Implementation Checklist

Before starting implementation, verify:

- [ ] All journeys have acceptance criteria
- [ ] All edge cases have expected behaviors
- [ ] All features have test plans
- [ ] Coverage targets defined (e.g., 90% journeys, 80% edges)

### Pre-Release Checklist

Before releasing, verify:

- [ ] All P0 journeys pass
- [ ] All P0 edge cases handled
- [ ] All P0 features complete
- [ ] Coverage audit shows acceptable gaps
- [ ] Documentation covers all journeys

---

## Templates

### Journey Documentation Template

```markdown
# [Feature Name] User Journeys

## Actors
[Actor table]

## Happy Path Journeys
[Journey tables and details]

## Error Recovery Journeys
[Journey tables and details]

## Edge Cases
[Edge case tables]

## Coverage Matrix
[Test coverage tables]

## Gaps
[Gap analysis]
```

### RFC Coverage Section Template

```markdown
## 📍 User Journey Analysis

### Actor Summary
| Actor Type | Count | Covered |
|------------|-------|---------|
| Internal | X | X |
| External | X | X |

### Journey Summary
| Category | Total | Covered |
|----------|-------|---------|
| Happy Path | X | X |
| Config | X | X |
| Error Recovery | X | X |
| Edge Cases | X | X |

### Coverage Matrix
[Detailed matrix]

### Gaps Identified
[List with resolutions]
```

---

## Integration with RFC Process

### RFC Sections to Add

Every RFC should include:

1. **Actor Identification** (Phase 1 output)
2. **Journey Mapping** (Phase 2 output)
3. **Edge Case Analysis** (Phase 3 output)
4. **Feature Matrix** (Phase 4 output)
5. **Test Strategy** with coverage targets
6. **Gap Analysis** if any remain

### Review Criteria

Reviewers should verify:

- [ ] All actor types considered
- [ ] ≥90% of happy paths mapped
- [ ] ≥80% of edge cases identified
- [ ] All P0 features have acceptance criteria
- [ ] Test plan covers all journeys
- [ ] No critical gaps remain

---

## Automation Support

### Scripts to Help

```bash
# Generate journey template
sunwell analyze journeys --rfc docs/RFC-XXX.md

# Audit test coverage against journeys
sunwell audit coverage --rfc docs/RFC-XXX.md --tests tests/

# Find missing edge cases
sunwell analyze edges --rfc docs/RFC-XXX.md

# Generate gap report
sunwell report gaps --rfc docs/RFC-XXX.md
```

### CI Integration

```yaml
# .github/workflows/rfc-quality.yml
- name: Check RFC Coverage
  run: |
    sunwell audit rfc docs/RFC-*.md --min-journey-coverage 90
    sunwell audit rfc docs/RFC-*.md --min-edge-coverage 80
```

---

## Examples

### Example: Tool Calling Feature

**Actors Identified**:
- AI Agent (internal) — executes tool calls
- Human User (external) — observes and intervenes
- Model Provider (external service) — generates tool calls

**Journeys Mapped**:
- A1-A11: Agent internal flow
- H1-H12: Human observation flow
- E1-E8: Edge cases

**Coverage Result**: 31/31 journeys = 100%

See: `docs/RFC-136-model-agnostic-tool-calling.md`

---

## Summary

**The S-Tier Standard**:

| Metric | Target | Minimum |
|--------|--------|---------|
| Actor Coverage | 100% | 90% |
| Happy Path Journeys | 100% | 95% |
| Error Recovery Journeys | 100% | 90% |
| Edge Case Coverage | 90% | 80% |
| Test Coverage | 95% | 85% |
| Critical Gaps | 0 | 0 |

**Key Principle**: If you can't map a journey, you can't test it. If you can't test it, you can't ship it with confidence.
