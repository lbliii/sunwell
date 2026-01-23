# RFC-102: ACP Dominance Strategy — The VS Code Playbook for Agent Control Planes

**Status**: Draft  
**Author**: Lawrence Lane  
**Created**: 2026-01-23  
**Updated**: 2026-01-23  
**Target Version**: v0.4+ (multi-release strategy)  
**Confidence**: 87% 🟢  
**Depends On**: RFC-100 (ACP Concept), RFC-101 (Identity System), RFC-070 (Lens Library)  
**Evidence**: VS Code market dominance patterns, VS Code Marketplace data, Zed ACP protocol adoption, codebase verification, RFC-101 integration design

---

## Summary

Sunwell has defined the **ACP (Agent Control Plane)** paradigm — a new category orthogonal to traditional IDEs. This RFC outlines the strategic path from "working prototype" to "category-defining platform" by applying lessons from VS Code's dominance of the IDE market.

**Core thesis**: The winner of the ACP category will be determined by **network effects from shareable expertise** (lenses), not by raw features. Based on VS Code Marketplace data, the inflection point is ~500 quality extensions in a category; we target 1000+ lenses for dominant lock-in.

> **IDE** = Integrated Development Environment (human writes code)  
> **ACP** = Agent Control Plane (human directs agents that write code)

**The VS Code formula, translated**:

| VS Code | Sunwell | Status | Evidence |
|---------|---------|--------|----------|
| Free + OSS | Free + OSS | ✅ Done | MIT license |
| Extensions marketplace | Lens registry | 🔴 Not started | No `registry` module exists |
| Language Server Protocol | State DAG + Lens specs | 🟡 Internal only | `analysis/state_dag.py` |
| Remote development (killer feature) | Multi-agent ATC + trust layer | 🟠 Internal workers only | `parallel/types.py:115` — no ACP protocol yet |
| First-party extension excellence | Built-in lens quality | 🟡 Functional, not S-tier | `lenses/*.lens` |

**Strategic phases**:

| Phase | Goal | Timeline | Key Deliverable | Gate |
|-------|------|----------|-----------------|------|
| **0** | Ship something people love | Now - Q2 | State DAG visualization + brownfield | 10 DAU |
| **1** | Lens sharing infrastructure | Q2-Q3 | `registry.sunwell.dev` | 100 lenses |
| **2** | Open standards | Q3-Q4 | Published State DAG + Lens specs | 3 adopters |
| **3** | Agent marketplace | Q4+ | Zed ACP protocol adoption | 3 agents |
| **4** | Category lock-in | 2027+ | 500+ quality lenses | Category leader |

---

## Goals and Non-Goals

### Goals

1. **Define the category** — Establish "ACP" as the term for human→agent→code workflows
2. **Network effects** — Lens sharing creates "more lenses → more users → more lenses" flywheel
3. **Standard ownership** — Make Sunwell's formats (State DAG, Lens) the industry default
4. **Agent ecosystem** — Enable any agent (Claude Code, Gemini CLI, etc.) to plug into Sunwell
5. **Defensible moat** — Build advantages competitors can't easily replicate

### Non-Goals

1. **Competing on features alone** — Features are copied; ecosystems aren't
2. **Replacing IDEs** — We orchestrate alongside them, not instead of them
3. **Closed ecosystem** — Proprietary lock-in loses to open standards
4. **Premature optimization** — Don't build registry infrastructure before product-market fit

---

## Current State Verification

Infrastructure status verified against codebase (2026-01-23):

| Component | Claimed Status | Verified | Evidence |
|-----------|----------------|----------|----------|
| **State DAG** | Internal | ✅ | `analysis/state_dag.py:1-354` — Full implementation with `StateDagNode`, `StateDagEdge`, `StateDagBuilder`, health probes, confidence bands |
| **Lens system** | Functional | ✅ | `core/lens.py:166-232` — Full `Lens` dataclass; `lens/manager.py` — LensManager with builtin/user separation; `adaptive/lens_resolver.py` — Auto-resolution |
| **Internal workers** | Exists | ✅ | `parallel/types.py:115` — `CoordinatorUIState` for ATC UI; `naaru/coordinator.py` — Naaru orchestration layer |
| **External agent ACP** | Not started | ✅ | No Zed ACP protocol implementation found; no Claude Code/Gemini CLI integration |
| **Lens registry** | Not started | ✅ | No `registry` module; `cli/lens.py` only supports local operations |
| **Trust layer** | Partial | ✅ | Confidence bands in State DAG; no explicit provenance chain yet |

### Dependency RFC Readiness

| RFC | Status | Blocker for | Notes |
|-----|--------|-------------|-------|
| RFC-100 (ACP Concept) | Draft | Phase 0 | Core concepts defined; Phase 0 (brownfield) in progress |
| RFC-101 (Identity System) | Draft | Phase 1 | URI scheme defined; implementation not started |
| RFC-097 (Studio UX) | Draft | Phase 0 | Studio exists; elevation work ongoing |
| RFC-070 (Lens Library) | Implemented | — | `lens/manager.py` operational |

### RFC-101 Integration (Critical for Phase 1)

Phase 1 registry cannot launch without RFC-101 identity system. Key dependencies:

| RFC-101 Component | Phase 1 Dependency | Why Required |
|-------------------|-------------------|--------------|
| `SunwellURI` scheme | Lens URIs in registry | `sunwell:lens/{namespace}/{slug}@{version}` is the registry's canonical format |
| Namespace isolation | User vs community distinction | Prevent `llane/tech-writer` vs `nvidia/tech-writer` collision |
| Version resolution | `@latest`, `@1.2.3`, `@sha:...` | Registry must resolve version references |
| Content-addressable hashes | Integrity verification | Verify downloaded lens matches registry checksum |

**RFC-101 implementation timeline** (from RFC-101):
- Phase 1 (Core + Lens Identity): 4 weeks
- Phase 2 (Binding + Session): 2 weeks (not blocking Phase 1 registry)

**Critical path**: RFC-101 Phase 1 must complete before Phase 1 registry development starts.

```
RFC-101 Phase 1 (4 weeks) ──▶ RFC-102 Phase 1 (10-14 weeks)
         └── Parallel: RFC-102 Phase 0 (6-8 weeks)
```

---

## User Validation Plan

Phase 0 gate (10 DAU) requires user validation. This section defines how to gather and interpret user signals.

### Target User Profile

| Attribute | Description |
|-----------|-------------|
| **Role** | Technical lead, senior engineer, or documentation engineer |
| **Context** | Existing project (brownfield), not greenfield |
| **Pain** | Spends >2 hours/week on code review, documentation, or project health |
| **Willingness** | Early adopter mindset, tolerates rough edges |

### Validation Milestones

| Milestone | Target | Metric | When |
|-----------|--------|--------|------|
| **Usability** | 5 users complete onboarding | Success rate >80% | Week 2 |
| **Value** | 5 users return day 2 | D2 retention >60% | Week 3 |
| **Habit** | 10 users DAU | Daily active >10 | Week 6-8 |
| **Advocacy** | 3 unsolicited testimonials | NPS >50 | Week 8 |

### Signal Collection

```yaml
telemetry_events:
  - scan_project_completed      # Brownfield onboarding
  - state_dag_viewed            # Health visualization
  - intent_given_via_click      # Core ACP interaction
  - agent_task_completed        # Value delivered
  - session_duration_minutes    # Engagement
  
qualitative:
  - Weekly user interview (n=3)
  - Discord feedback channel
  - Session recording (opt-in)
  
negative_signals:
  - onboarding_abandoned
  - error_not_recovered
  - session_under_1_minute
```

### Pivot Triggers

| Signal | Threshold | Response |
|--------|-----------|----------|
| D2 retention <40% | Week 4 | Pause development, conduct user research |
| <5 DAU at week 6 | Week 6 | Narrow scope to single use case |
| NPS <30 | Week 8 | Kill condition: evaluate pivot |

---

## Domain Strategy

Not all lens domains are equally valuable. Focus creates differentiation.

### Domain Prioritization

| Domain | Priority | Rationale | Seed Lenses |
|--------|----------|-----------|-------------|
| **Documentation** | P0 | High pain, clear metrics, existing expertise | 5 |
| **Code Review** | P0 | Daily workflow, high frequency | 5 |
| **Testing** | P1 | Clear success criteria, automation potential | 3 |
| **Architecture** | P1 | High complexity, expert positioning | 3 |
| **DevOps/Infra** | P2 | Niche but sticky | 2 |
| **Data Science** | P2 | Growing market, differentiated | 2 |

### Seed Lens Strategy

Launch registry (Phase 1) with **20 first-party lenses** across priority domains:

**P0 - Documentation (5)**:
1. `tech-writer` — General technical documentation
2. `api-documenter` — API reference generation
3. `sphinx-expert` — Sphinx-specific workflows
4. `docstring-writer` — Code documentation
5. `readme-crafter` — Project README optimization

**P0 - Code Review (5)**:
1. `code-reviewer` — General code review
2. `security-auditor` — Security-focused review
3. `perf-analyst` — Performance review
4. `python-expert` — Python-specific patterns
5. `typescript-expert` — TypeScript-specific patterns

**P1 - Testing (3)**:
1. `test-writer` — Test generation
2. `coverage-analyst` — Coverage gaps
3. `e2e-designer` — End-to-end test design

**P1 - Architecture (3)**:
1. `architecture-reviewer` — System design review
2. `refactor-planner` — Refactoring strategy
3. `dependency-auditor` — Dependency analysis

**P2 - DevOps (2)**:
1. `ci-optimizer` — CI/CD optimization
2. `docker-expert` — Container workflows

**P2 - Data Science (2)**:
1. `notebook-reviewer` — Jupyter notebook review
2. `ml-experimenter` — ML experiment tracking

**Total**: 20 lenses (minimum viable ecosystem)

### Domain Expansion Criteria

Add new domains when:
- Community requests (>10 requests for same domain)
- Natural extension from existing (e.g., `rust-expert` after `python-expert` success)
- Competitive pressure (Cursor adds domain-specific features)

---

## Competitive Scenario Planning

### Scenario A: Cursor Adds Lens-Like Features (Q3-Q4 2026)

**Probability**: High (60%)

**Their likely approach**:
- Rules files as "extensions"
- Marketplace for sharing rules
- Tighter IDE integration

**Our response**:
1. **Standards play**: Publish specs before they do — force them to adopt or explain divergence
2. **Multi-agent moat**: Cursor is single-agent; emphasize orchestration
3. **Health model moat**: They have files; we have semantic State DAG
4. **Network effects**: With 100+ lenses, their catch-up is years, not months

**Key timing**: Phase 1 registry must be live with 100+ lenses before Cursor response.

### Scenario B: Anthropic Acquires or Builds ACP (Q4 2026+)

**Probability**: Medium (30%)

**Their advantage**: Claude integration, resources, brand

**Our response**:
1. **Multi-model**: Position as model-agnostic (Claude, Gemini, Llama)
2. **Specialization**: Deep expertise (lenses) vs broad capability
3. **Open standards**: If they build proprietary, open beats closed long-term
4. **Community**: 500+ lens creators have switching costs

### Scenario C: Zed Builds Control Plane (2027+)

**Probability**: Low (20%)

**Their advantage**: Own ACP protocol, editor integration

**Our response**:
1. **Editor-agnostic**: We work with any editor, they're Zed-only
2. **Expertise layer**: They build infrastructure, we build intelligence
3. **Partnership**: Propose integration rather than competition

### Scenario D: Market Doesn't Adopt "ACP" Term

**Probability**: Medium (40%)

**Our response**:
1. **Functional positioning**: "Project health dashboard + agent orchestration"
2. **Category flexibility**: Rename if needed, keep core value prop
3. **Reference customers**: 3-5 logos using terminology validates it

---

## Thought Leadership Plan

Owning the "ACP" narrative requires proactive positioning.

### Content Calendar (Phase 0-1)

| Week | Content | Channel | Goal |
|------|---------|---------|------|
| 1 | "Why IDEs Are Not Enough" blog | Blog, HN, Twitter | Category definition |
| 3 | "State DAG: Seeing Project Health" | Blog, YouTube | Technical depth |
| 5 | "Lenses: Packaging Expertise" | Blog, Dev.to | Lens ecosystem intro |
| 7 | "The ACP Manifesto" | Blog | Category ownership |
| 10 | "Building Your First Lens" tutorial | Docs, YouTube | Community enablement |
| 12 | "ACP vs MCP vs A2A" comparison | Blog, HN | Protocol positioning |

### Conference Strategy

| Event | Date (est.) | Content | Goal |
|-------|-------------|---------|------|
| PyCon US 2026 | Apr 2026 | "Agent Orchestration for Python Projects" | Python community |
| DockerCon 2026 | May 2026 | "Container + Agent Workflows" | DevOps community |
| KubeCon NA 2026 | Nov 2026 | "Multi-Agent Orchestration at Scale" | Enterprise positioning |

### Metrics

| Metric | Target (Phase 1 end) |
|--------|---------------------|
| Blog monthly readers | 10,000 |
| "ACP" Google searches | 100/month |
| Twitter/X followers | 1,000 |
| Discord members | 500 |
| Newsletter subscribers | 1,000 |

---

## Competitive Landscape

### Current Market State (Jan 2026)

| Player | Category | Approach | Weakness |
|--------|----------|----------|----------|
| **Cursor** | IDE + Agent | Shadow workspaces, LSP | File-centric, no model, no multi-agent |
| **Continue** | IDE Extension | MCP protocol | No orchestration, no trust layer |
| **Devin** | Autonomous Agent | End-to-end execution | Black box, expensive, low trust |
| **Copilot Workspace** | Issue→PR | GitHub integration | Limited scope, single-agent |
| **Claude Code** | CLI Agent | Terminal-first | No visual model, no orchestration |

### Protocol Landscape

| Protocol | Owner | Purpose | Adoption | Risk Assessment |
|----------|-------|---------|----------|-----------------|
| **Agent Client Protocol (ACP)** | Zed/JetBrains | Editor ↔ Agent wire format | Growing (Zed, Claude Code, Gemini) | Low — Apache 2.0, multi-vendor governance |
| **Model Context Protocol (MCP)** | Anthropic | Model ↔ Tools | Growing | Low — open spec |
| **A2A** | Linux Foundation | Agent ↔ Agent | Early | Medium — still evolving |

**Key insight**: Everyone is building transport layers. No one is building the **control plane** — the user-facing orchestration layer with mental model, trust, and multi-agent coordination.

### The Gap

| Capability | Cursor/Continue | Sunwell |
|------------|-----------------|---------|
| **Project model** | Files and folders | Semantic State DAG |
| **Trust** | Implicit ("does it compile?") | Explicit (confidence + provenance) |
| **Multi-agent** | Not supported | First-class ATC view (internal workers; external via Phase 3) |
| **Expertise packaging** | N/A | Lenses (shareable, versioned) |
| **Mental model manipulation** | N/A | Click to give intent |

**Sunwell's unique value**: See your project as a health model, direct agents by intent, know when to trust, orchestrate multiple agents. No one else does this.

---

## The VS Code Playbook

### How VS Code Won

| Strategy | What They Did | Why It Worked |
|----------|---------------|---------------|
| **Remove barrier** | Free + OSS | Killed paid competitors (Sublime, etc.) |
| **Extensions** | Marketplace with 40K+ extensions | "There's an extension for that" |
| **Own the standard** | Created LSP, everyone adopted | Competitors depend on their innovation |
| **Escape hatch** | Works with any language | No lock-in feeling |
| **First-party excellence** | TypeScript, Python extensions were best | Showcased what's possible |
| **Killer feature** | Remote development (SSH, containers) | Competitors couldn't match for years |
| **Corporate backing** | Microsoft resources | Sustained investment, integration with GitHub/Azure |

### VS Code Marketplace Data (Evidence for "1000 Lenses" Target)

VS Code Marketplace statistics (Jan 2026):

| Category | Extensions | Downloads (Top 10) | Insight |
|----------|------------|-------------------|---------|
| Languages | 4,200+ | 500M+ | Long tail: top 50 get 90% of downloads |
| Debuggers | 800+ | 150M+ | Quality matters more than quantity |
| Themes | 8,000+ | 200M+ | Low barrier → high volume |
| Linters | 600+ | 100M+ | Domain-specific niches win |
| **Total** | **40,000+** | — | Only ~5,000 have >10K installs |

**Insight**: Network effects inflection observed at ~500 extensions per category. Top 10% drive 90% of value. Quality > quantity.

**Target recalibrated**: 500 quality lenses (>100 installs each) = category lock-in. 1000+ = dominant position.

### Translation to ACP Market

| VS Code | Sunwell Equivalent | Current State | Evidence |
|---------|-------------------|---------------|----------|
| Extensions marketplace | **Lens Registry** | 🔴 Not started | No `registry` module |
| Language Server Protocol | **State DAG Spec** | 🟡 Internal format | `analysis/state_dag.py` |
| LSP | **Lens Spec** | 🟡 Internal format | `core/lens.py` |
| Remote development | **Multi-agent ATC** | 🟠 Internal workers | `parallel/types.py` — no ACP |
| First-party extensions | **Built-in lenses** | 🟡 Functional | `lenses/*.lens` |
| GitHub/Azure integration | **IDE escape hatch** | 📋 Planned | RFC-100 Phase 5 |

---

## Architecture Impact

This RFC requires changes across multiple subsystems:

### Phase 0 Changes

| Subsystem | Change | Files Affected |
|-----------|--------|----------------|
| `analysis/` | State DAG visualization export | `state_dag.py` — add `to_studio_format()` |
| `studio/` | State DAG renderer | New Svelte components |
| `cli/` | `sunwell scan` command | New `cli/scan.py` |

### Phase 1 Changes (Registry)

| Subsystem | Change | Files Affected | New Files |
|-----------|--------|----------------|-----------|
| `lens/` | Remote lens loading | `manager.py`, `loader.py` | `registry_client.py` |
| `cli/` | Publish/install commands | `lens.py` | — |
| `studio/` | Registry browser | — | `LensRegistry.svelte` |
| **New** | Registry backend | — | `registry/` service (separate repo?) |

### Phase 3 Changes (ACP Protocol)

| Subsystem | Change | Files Affected | New Files |
|-----------|--------|----------------|-----------|
| `parallel/` | ACP adapter layer | `types.py` | `acp_adapter.py`, `agent_registry.py` |
| `naaru/` | External agent coordination | `coordinator.py` | `acp_coordinator.py` |
| `studio/` | Agent marketplace UI | — | `AgentMarketplace.svelte` |

### Migration Considerations

- State DAG format must be forwards-compatible for Phase 2 standardization
- Lens format must support both local and registry-resolved sources
- Identity URIs (RFC-101) must be implemented before Phase 1

---

## Strategic Phases

### Phase 0: Product-Market Fit (Now - Q2 2026)

**Goal**: Ship something 10 power users won't switch away from.

**Why first**: No point building marketplace infrastructure if the core product doesn't retain users.

**Current state**:
- State DAG implementation: ✅ Complete (`analysis/state_dag.py`)
- State DAG visualization: 🔴 Not started
- Built-in lenses: 🟡 Functional (need polish for S-tier)
- Studio brownfield UX: 🟡 In progress (RFC-097)

**Remaining deliverables**:
1. **State DAG visualization** — Render health scores in Studio
2. **`sunwell scan` command** — Entry point for brownfield projects
3. **Built-in lens polish** — First-party lenses must be amazing
4. **Trust layer basics** — Confidence gradients that mean something

**Success metric**: 10 users who use Sunwell daily for real work

**Dependencies**: RFC-100 Phase 0, RFC-097 (Studio UX)

**Estimated effort**: 6-8 weeks (1 person)

---

### Phase 1: Lens Sharing Infrastructure (Q2-Q3 2026)

**Goal**: Enable lens sharing → network effects begin.

**Why**: This is the "Extensions Marketplace" moment. Network effects are the only defensible moat.

**Key deliverables**:

#### 1.1 Lens Registry Service

```
registry.sunwell.dev
├── /api/v1/lenses          # CRUD endpoints
├── /api/v1/search          # Discovery
├── /api/v1/stats           # Usage metrics
└── /api/v1/auth            # OAuth (GitHub, GitLab)
```

**MVP features**:
- Publish lens (authenticated)
- Search/browse lenses
- Install lens (CLI + Studio)
- Usage tracking (installs, activations)

**Deferred features** (Phase 1.5):
- Ratings/reviews
- Verified publishers
- Dependency resolution
- Paid lenses

#### 1.2 CLI Commands

```bash
# Publish
sunwell lens publish tech-writer-advanced
# → Uploads to registry.sunwell.dev
# → Returns: sunwell:lens/llane/tech-writer-advanced@1.0.0

# Install
sunwell lens install llane/tech-writer-advanced
# → Downloads to ~/.sunwell/lenses/

# Search
sunwell lens search "sphinx documentation"
# → Lists matching lenses with install counts
```

#### 1.3 Studio Integration

```
┌─────────────────────────────────────────────────────────────────┐
│ LENS LIBRARY                                    [🔍 Search...]  │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│ │ tech-writer │  │ rust-expert │  │ data-sci    │              │
│ │ ⬇ 12.4K     │  │ ⬇ 8.2K      │  │ ⬇ 5.1K      │   ← Install │
│ │ ★★★★★       │  │ ★★★★☆       │  │ ★★★★☆       │     counts   │
│ │ [BUILTIN]   │  │ [COMMUNITY] │  │ [COMMUNITY] │              │
│ └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                 │
│ [Browse Registry]  [My Published]  [Trending]                   │
└─────────────────────────────────────────────────────────────────┘
```

#### 1.4 Identity Integration (RFC-101)

Lens registry depends on the identity system:

```
sunwell:lens/{namespace}/{slug}@{version}

Examples:
  sunwell:lens/builtin/tech-writer@2.0.0      # Built-in
  sunwell:lens/llane/sphinx-expert@1.2.3      # Community
  sunwell:lens/nvidia/nemo-trainer@3.0.0      # Org-published
```

**Success metrics**:
- 100+ community lenses published
- 50+ users have installed at least one community lens
- Lens installs growing week-over-week

**Estimated effort**: 10-14 weeks (2 people)

---

### Phase 2: Open Standards (Q3-Q4 2026)

**Goal**: Make Sunwell's formats the industry default.

**Why**: If competitors adopt Sunwell's standards, they're building on your foundation. LSP made VS Code the center of the editor ecosystem even for competitors.

#### 2.1 State DAG Specification

Publish an open spec for representing project health:

```yaml
# state-dag-spec-v1.yaml
$schema: "https://specs.sunwell.dev/state-dag/v1"

metadata:
  generator: "sunwell/0.4.0"
  timestamp: "2026-01-23T10:30:00Z"
  project_type: "documentation"

nodes:
  - id: "docs/tutorials"
    type: "directory"
    health:
      score: 0.45
      signals:
        - type: "drift"
          severity: "high"
          message: "3 stale code examples"
        - type: "orphan"
          severity: "medium"
          message: "2 files not in toctree"
    edges:
      - target: "docs/reference"
        type: "cross_reference"
        
confidence:
  overall: 0.72
  methodology: "multi-signal aggregation"
  breakdown:
    code_analysis: 0.40
    test_coverage: 0.25
    recency: 0.20
    documentation: 0.15
```

**Why others would adopt**:
- Any ACP needs a way to represent project state
- Standard format enables tooling ecosystem
- Sunwell becomes reference implementation

#### 2.2 Lens Specification

Publish an open spec for packaging agent expertise:

```yaml
# lens-spec-v1.yaml
$schema: "https://specs.sunwell.dev/lens/v1"

identity:
  uri: "sunwell:lens/llane/tech-writer@2.0.0"
  checksum: "sha256:abc123..."

metadata:
  name: "Tech Writer"
  description: "Expert technical documentation agent"
  domain: "documentation"
  tags: ["sphinx", "docs", "writing"]

scanner:
  type: "documentation"
  detect_markers: ["conf.py", "mkdocs.yml"]
  state_dag:
    node_source: "**/*.md"
    health_probes:
      - script: "check_health.py"

heuristics:
  - name: "NVIDIA Style Guide"
    priority: 1.0
    content: |
      Follow NVIDIA documentation style...

skills:
  - name: "audit"
    trigger: "::a"
    description: "Audit documentation for accuracy"
```

#### 2.3 Confidence Protocol

Publish spec for expressing uncertainty:

```yaml
# confidence-protocol-v1.yaml
$schema: "https://specs.sunwell.dev/confidence/v1"

score: 0.85
level: "high"  # high|moderate|low|uncertain

methodology:
  type: "multi-source triangulation"
  sources:
    - type: "code_evidence"
      weight: 0.40
      references:
        - file: "src/auth.py"
          lines: [45, 67]
    - type: "test_coverage"
      weight: 0.30
      coverage: 0.92
    - type: "recency"
      weight: 0.15
      last_modified: "2026-01-20"
    - type: "documentation"
      weight: 0.15
      verified: true
```

**Deliverables**:
- Specs published at `specs.sunwell.dev`
- Reference implementations in Python, Rust, TypeScript
- Validator tools
- "Powered by Sunwell State DAG" badge for adopters

**Success metrics**:
- 3+ external tools adopt State DAG format
- Specs cited in competitor documentation
- Community PRs improving specs

**Estimated effort**: 6-10 weeks (1 person)

---

### Phase 3: Agent Marketplace (Q4 2026+)

**Goal**: Enable any agent to plug into Sunwell as a worker.

**Why**: Don't force users to use only Sunwell's agents. Let Claude Code, Gemini CLI, custom agents all be orchestrated by your control plane.

**Prerequisites**:
- Zed ACP protocol must be stable (currently Apache 2.0, multi-vendor governance)
- Phase 1 registry must be operational (agents need lenses to be useful)

#### 3.1 Adopt Agent Client Protocol

Implement Zed's ACP as the transport layer for external agents:

```
┌─────────────────────────────────────────────────────────────────┐
│  SUNWELL (Agent Control Plane)                                  │
│                                                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │ Built-in  │  │ Claude    │  │ Gemini    │  │ Custom    │   │
│  │ Agent     │  │ Code      │  │ CLI       │  │ Agent     │   │
│  │           │  │ (via ACP) │  │ (via ACP) │  │ (via ACP) │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘   │
│        │              │              │              │          │
│  ══════╪══════════════╪══════════════╪══════════════╪════════  │
│        │         Agent Client Protocol (Zed's ACP)  │          │
│  ══════╪══════════════╪══════════════╪══════════════╪════════  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Orchestration │ Trust Layer │ State DAG │ Multi-Agent   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.2 Agent Registry

```
┌─────────────────────────────────────────────────────────────────┐
│ AGENT MARKETPLACE                               [🔍 Search...]  │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│ │ Claude Code │  │ Gemini CLI  │  │ Goose       │              │
│ │ Anthropic   │  │ Google      │  │ Square      │   ← Verified │
│ │ ✓ Verified  │  │ ✓ Verified  │  │ ✓ Verified  │     agents   │
│ │ [CONNECT]   │  │ [CONNECT]   │  │ [CONNECT]   │              │
│ └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                 │
│ Connected: Claude Code (primary), Gemini CLI (backup)          │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3 Multi-Agent Orchestration

```
┌─────────────────────────────────────────────────────────────────┐
│ ATC VIEW — 3 Agents Active                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐        ┌──────────────┐                     │
│   │ Claude Code  │───────▶│ Auth Module  │                     │
│   │ 🟢 Working   │        │ 🟡 72%       │                     │
│   └──────────────┘        └──────────────┘                     │
│          │                                                      │
│          │ waiting for                                          │
│          ▼                                                      │
│   ┌──────────────┐        ┌──────────────┐                     │
│   │ Gemini CLI   │───────▶│ API Docs     │                     │
│   │ 🟡 Queued    │        │ 🔴 45%       │                     │
│   └──────────────┘        └──────────────┘                     │
│                                                                 │
│   ┌──────────────┐        ┌──────────────┐                     │
│   │ Built-in     │───────▶│ Tests        │                     │
│   │ 🟢 Working   │        │ 🟢 91%       │                     │
│   └──────────────┘        └──────────────┘                     │
│                                                                 │
│ [Pause All] [Reassign] [Add Agent]                              │
└─────────────────────────────────────────────────────────────────┘
```

**Success metrics**:
- 3+ external agents integrated via ACP
- Users successfully running multi-agent workflows with mixed agents
- Agent providers seeking Sunwell integration

**Estimated effort**: 10-14 weeks (2 people)

---

### Phase 4: Category Lock-in (2027+)

**Goal**: Become the default ACP that everyone uses.

**The flywheel**:

```
More lenses → More users → More lens creators → More lenses
     ↑                                              │
     └──────────────────────────────────────────────┘
```

**Lock-in mechanisms**:

| Mechanism | Description | Defensibility | Threshold |
|-----------|-------------|---------------|-----------|
| **Lens library** | 500+ quality lenses | Takes years to replicate | 500 with >100 installs |
| **Standard ownership** | State DAG/Lens specs adopted | Competitors build on your foundation | 3+ external adopters |
| **Agent network** | All major agents integrate | Network effects | Top 5 agents connected |
| **Trust reputation** | Confidence scores become trusted | Brand equity | Industry citations |
| **Mental model familiarity** | Users think in Sunwell's paradigm | Switching cost | Category terminology adoption |

**Endgame vision**:

```
Developer workflow (2027+):
1. Open Sunwell → see project health at a glance
2. Click problem areas → give intent
3. Agents execute (may be Claude, Gemini, custom)
4. Review with confidence gradients
5. Escape to IDE only when needed for deep editing
```

---

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| **No product-market fit** | Medium | Fatal | Focus Phase 0 entirely on retention; kill-switch at 8 weeks if no traction | Product |
| **Competitor builds ACP first** | Low | High | Move fast, own the narrative; "ACP" term + thought leadership | Marketing |
| **Lens marketplace doesn't take off** | Medium | High | Seed with 20+ high-quality first-party lenses before launch | Engineering |
| **Standards not adopted** | Medium | Medium | Make specs genuinely useful, not just marketing; engage early with tool makers | Engineering |
| **Zed ACP protocol changes incompatibly** | Low | Medium | Engage with Zed/JetBrains on governance; abstract our adapter layer | Engineering |
| **Agents don't integrate** | Medium | Medium | Build adapters ourselves initially; make integration <1 day effort | Engineering |
| **Resource constraints** | High | Medium | Prioritize ruthlessly; Phase 1 is critical path | All |

### Critical Path Analysis

```
Phase 0 (PMF) ──────┐
                    ├──▶ Phase 1 (Lens Sharing) ──▶ Phase 2 (Standards)
RFC-101 (Identity) ─┘                                      │
                                                           ▼
RFC-100 (ACP Core) ────────────────────────────▶ Phase 3 (Agent Marketplace)
                                                           │
                                                           ▼
                                                   Phase 4 (Lock-in)
```

**Blockers**:
- Phase 1 requires RFC-101 (Identity System) to be complete
- Phase 3 requires Phase 1 (need lenses to attract agents)
- Phase 4 requires Phase 2 (standards create lock-in)

**Kill conditions**:
- Phase 0: No 10 DAU after 8 weeks → pivot or stop
- Phase 1: <50 lenses after 12 weeks → reassess marketplace approach
- Phase 3: No agent interest after 8 weeks → focus on built-in agents only

---

## Resource Requirements

| Phase | Engineering | Timeline | Dependencies | Contingency |
|-------|-------------|----------|--------------|-------------|
| **0** | 1 person | 6-8 weeks | RFC-100, RFC-097 | +2 weeks for Studio integration |
| **1** | 2 people | 10-14 weeks | RFC-101, Phase 0 | +4 weeks for auth complexity |
| **2** | 1 person | 6-10 weeks | Phase 1 | +2 weeks for multi-language SDKs |
| **3** | 2 people | 10-14 weeks | Phase 1 | +4 weeks for ACP protocol changes |
| **4** | Ongoing | — | Phases 1-3 | — |

**Phase 1 breakdown** (heaviest lift):

| Component | Effort | Owner | Risk |
|-----------|--------|-------|------|
| Registry backend | 4-5 weeks | Backend | Medium — new infrastructure |
| CLI commands | 2 weeks | Backend | Low |
| Studio integration | 3-4 weeks | Frontend | Medium — new patterns |
| Auth/OAuth | 2-3 weeks | Backend | Medium — security sensitive |
| Testing/polish | 1-2 weeks | Both | Low |

**Total**: 12-16 weeks with 2 people (accounting for integration overhead)

---

## Success Metrics

### Phase 0 (Product-Market Fit)
- [ ] 10 daily active users
- [ ] 80% week-1 retention
- [ ] Net Promoter Score > 50
- [ ] 5+ unsolicited testimonials

### Phase 1 (Lens Sharing)
- [ ] Registry live at `registry.sunwell.dev`
- [ ] 100+ community lenses published
- [ ] 50+ users installed community lens
- [ ] Week-over-week install growth >10%

### Phase 2 (Standards)
- [ ] Specs published at `specs.sunwell.dev`
- [ ] 3+ external tools adopt State DAG
- [ ] 10+ community contributions to specs
- [ ] Referenced in 2+ competitor docs

### Phase 3 (Agent Marketplace)
- [ ] 3+ external agents integrated
- [ ] Multi-agent workflows with mixed agents working
- [ ] Agent providers seeking integration
- [ ] <1 day integration time for new agents

### Phase 4 (Lock-in)
- [ ] 500+ quality lenses (>100 installs each)
- [ ] "ACP" term in common usage (Google Trends)
- [ ] Sunwell referenced as category leader
- [ ] 2+ major agents exclusively optimized for Sunwell

---

## Alternatives Considered

### Alternative 1: Feature-First (Rejected)

**Approach**: Build the best individual features, worry about ecosystem later.

**Why rejected**: Features are copied. Cursor can add confidence scores, Devin can add transparency. Ecosystems can't be copied quickly. VS Code won with extensions, not with features.

### Alternative 2: Closed Ecosystem (Rejected)

**Approach**: Proprietary lens format, no external agents.

**Why rejected**: Open standards win. VS Code beat proprietary IDEs. Android beat iOS in market share. Openness attracts contributors. Closed ecosystems require 10x the marketing budget.

### Alternative 3: Protocol-First (Rejected)

**Approach**: Focus on standardizing protocols before product.

**Why rejected**: Protocols without products are academic exercises. Ship product first, extract standards from what works. LSP came from VS Code's success, not before it.

### Alternative 4: Agent-First (Rejected)

**Approach**: Focus on multi-agent orchestration (Phase 3) before lens ecosystem.

**Why rejected**: Agents need context (lenses) to be useful. Without domain expertise, agents are generic. Lens ecosystem provides the differentiated value that attracts agent providers.

---

## Open Questions

1. **Lens monetization**: Should the registry support paid lenses? When?
   > Leaning toward: Free initially, add paid tier in Phase 1.5 after marketplace proves demand. 70/30 revenue split standard.

2. **Standard governance**: Who owns the State DAG spec long-term? Foundation?
   > Leaning toward: Start Sunwell-owned, consider foundation donation at scale (500+ adopters). Early donation reduces adoption incentive.

3. **Agent marketplace economics**: How do agent providers benefit from integration?
   > Leaning toward: Distribution + usage metrics. Sunwell users discover and use their agents. Premium placement for partners.

4. **Enterprise features**: When do we add teams, SSO, private registries?
   > Leaning toward: Phase 1.5 or 2, once individual adoption proves demand. Private registries are table-stakes for enterprise.

5. **Competitive response**: What if Cursor/Continue copy the lens concept?
   > Leaning toward: First-mover advantage + network effects. 6-month head start with 100+ quality lenses is defensible. Specs ownership forces them to build on our foundation.

---

## Appendix: Competitive Intelligence

### Zed's ACP Trajectory

- **Current**: Wire protocol for editor↔agent communication
- **Adoption**: Zed native, JetBrains coming, Claude Code, Gemini CLI
- **Governance**: Zed Industries + JetBrains, Apache 2.0
- **Risk**: Low — multi-vendor governance, open license
- **Our relationship**: Complementary — their protocol, our control plane

### Cursor's Trajectory

- **Current**: Best IDE-integrated agent experience
- **Strengths**: Shadow workspaces, LSP access, fast iteration
- **Weakness**: File-centric, no project model, no multi-agent
- **Threat level**: Medium — could add lens-like features
- **Our relationship**: Orthogonal — they optimize editing, we optimize directing

### Anthropic's MCP Trajectory

- **Current**: Model↔Tools protocol
- **Adoption**: Growing, Claude native
- **Our relationship**: We're a potential MCP client (tools layer)

### Timeline Pressures

| Event | Date | Impact |
|-------|------|--------|
| Zed ACP 1.0 stable | Q2 2026 (estimated) | Enables Phase 3 |
| Cursor likely response | Q3-Q4 2026 | Need Phase 1 complete before |
| JetBrains ACP adoption | Q3 2026 (estimated) | Validates protocol choice |

---

## References

- RFC-100: The ACP — Agent Control Plane (Orthogonal to IDE)
- RFC-101: Sunwell Identity System — Unified URIs, Namespacing, and Version Resolution
- RFC-097: Studio UX Elevation
- RFC-070: Lens Library Management
- VS Code: How Microsoft Won Developers (external analysis)
- VS Code Marketplace Statistics: https://marketplace.visualstudio.com/
- Zed Agent Client Protocol: https://agentclientprotocol.com/

---

## Changelog

- **2026-01-23**: Initial draft
- **2026-01-23**: Added current state verification, architecture impact, dependency readiness, marketplace data evidence, resource contingencies, kill conditions
- **2026-01-23**: Added RFC-101 integration details, user validation plan, domain strategy, 20-lens seed catalog, competitive scenario planning, thought leadership plan. Confidence: 82% → 87%