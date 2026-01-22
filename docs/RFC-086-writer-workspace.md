# RFC-086: Universal Writing Environment

**Status**: Draft  
**Created**: 2026-01-21  
**Authors**: @llane  
**Depends on**:
- RFC-072 (Surface Primitives) — Primitive definitions
- RFC-080 (Unified Home Surface) — Block system
- RFC-082 (Fluid Canvas UI) — Page/canvas area model
- RFC-070 (Lens System) — Skills, heuristics, validators, **workflow chains**

**Inspired by**: DORI (Documentation Orchestrator with Reflexive Intelligence) — `::auto`, `::pipeline`, `::chain` patterns

**Confidence**: 88% 🟢 (procedural workflow engine selected; risks documented with mitigations)

---

## The Philosophy

> **"Everything is writing. Code is writing. Docs are writing. Specs are writing. Stories are writing.**
>
> **The only difference is the domain expertise you apply."**

In the AI era, the human's job is increasingly about **intent, review, and guidance** — all forms of writing:
- Code is just writing with a compiler
- Docs are just writing with a reader
- Specs are just writing with a team
- Stories are just writing with an audience

**The tool should adapt to the domain, not the other way around. That's what lenses do.**

---

## Summary

Define the **Universal Writing Environment** — an AI-native writing surface where **lenses provide domain expertise** for any kind of writing. Unlike traditional IDEs built for code (with docs as an afterthought), Sunwell treats all writing as first-class:

- **Lens-powered expertise** — `tech-writer.lens`, `pm.lens`, `novelist.lens`, `coder.lens` — same surface, different domain knowledge
- **Autonomous skill chains** — "audit and fix this doc" → 5-step workflow executes automatically
- **Checkpointed execution** — pause/resume workflows, state persists across sessions
- **Toggle view** (source ↔ preview) instead of cramped side-by-side split
- **Universal selection** — select text in any view, send to AI
- **`sunwell .`** — open any project with one command, lens auto-detected

**Key differentiator:** Not a code editor that also does docs. An **S-tier writing environment** where lenses provide infinite domain expertise.

---

## The Lens Ecosystem

Lenses transform a generic writing surface into a domain-specific powerhouse:

```yaml
# ═══════════════════════════════════════════════════════════════════════════
# TODAY — Shipped lenses
# ═══════════════════════════════════════════════════════════════════════════

tech-writer.lens:
  domain: "Technical Documentation"
  frameworks: [Diataxis, NVIDIA Style Guide, Progressive Disclosure]
  heuristics:
    - "Signal over noise — every sentence earns its place"
    - "Evidence required — claims have file:line refs"
    - "Front-load value — key info in first paragraph"
  validators: [no_marketing_fluff, diataxis_purity, evidence_required]
  skills: [audit, polish, modularize, draft, health-check]

coder.lens:
  domain: "Software Development"
  frameworks: [Types as Contracts, Composition over Inheritance]
  heuristics:
    - "Models are passive — no I/O in core/"
    - "Fail loudly — explicit errors over silent degradation"
  validators: [type_coverage, architecture_compliance]
  skills: [research, rfc, plan, implement, validate]

# ═══════════════════════════════════════════════════════════════════════════
# TOMORROW — Community/future lenses
# ═══════════════════════════════════════════════════════════════════════════

pm.lens:
  domain: "Product Management"
  frameworks: [PRFAQ, Jobs-to-be-Done, North Star Metric, RICE]
  heuristics:
    - "Every feature ties to user outcome"
    - "No solution without validated problem"
    - "Metrics before features"
  validators: [has_success_metrics, problem_before_solution]
  skills: [write-prd, prioritize-backlog, draft-prfaq, user-story]

qa.lens:
  domain: "Quality Assurance"
  frameworks: [BDD, Test Pyramid, Risk-Based Testing, Equivalence Partitioning]
  heuristics:
    - "Edge cases before happy path"
    - "Reproducibility is sacred"
    - "Test the contract, not the implementation"
  validators: [has_repro_steps, covers_edge_cases]
  skills: [write-test-plan, generate-cases, audit-coverage, bug-report]

novelist.lens:
  domain: "Fiction Writing"
  frameworks: [Three-Act Structure, Hero's Journey, Save the Cat, Scene-Sequel]
  heuristics:
    - "Show don't tell"
    - "Every scene needs conflict"
    - "Character wants something in every scene"
    - "Enter late, leave early"
  validators: [scene_has_conflict, dialogue_attribution]
  skills: [plot-outline, character-arc, dialogue-polish, pacing-check]

researcher.lens:
  domain: "Academic Writing"
  frameworks: [IMRaD, Literature Review, Citation Standards]
  heuristics:
    - "Claim requires citation"
    - "Correlation ≠ causation"
    - "Define terms before use"
  validators: [claims_cited, methodology_sound]
  skills: [draft-abstract, structure-paper, cite-sources, lit-review]

legal.lens:
  domain: "Legal Documents"
  frameworks: [Plain Language, Contract Structure, Risk Allocation]
  heuristics:
    - "Define before use"
    - "Avoid ambiguous pronouns"
    - "Active voice for obligations"
  validators: [terms_defined, unambiguous_language]
  skills: [draft-clause, review-risk, simplify-language]
```

### How Lenses Transform the Surface

Same primitives, different expertise:

| Lens | ProseEditor Shows | Outline Shows | Validation Checks | Suggested Actions |
|------|-------------------|---------------|-------------------|-------------------|
| `tech-writer` | Markdown with style warnings | Document structure | Marketing fluff, Diataxis purity | Audit, Polish, Modularize |
| `pm` | PRD with metric highlights | Requirements hierarchy | Missing success metrics | Write PRD, Prioritize |
| `novelist` | Prose with pacing indicators | Chapter/scene structure | Conflict per scene, show-don't-tell | Plot outline, Dialogue polish |
| `coder` | Code with type annotations | Symbol outline | Type coverage, architecture | Implement, Validate, RFC |
| `qa` | Test plan with coverage gaps | Test hierarchy | Edge case coverage | Generate cases, Audit coverage |

---

## Problem Statement

Sunwell has all the primitives needed for writing (`ProseEditor`, `Outline`, `Preview`, `DiffView`, `WordCount`) and comprehensive lenses with frameworks, heuristics, and validators. However:

1. **No dedicated writer layout** — Documentation projects get `ProseEditor + Outline` but no live preview, validation panel, or skill access
2. **Lens expertise is invisible** — The 730-line tech-writer.lens has no UI surface; users must know shortcuts like `::a`, `::p`
3. **No real-time feedback** — Validators exist but don't run live; heuristics aren't surfaced contextually
4. **Missing split view** — Writers need editor + preview side-by-side, not separate panels

### User Stories

**Technical Writer:**
> "As a technical writer contributing to Pachyderm docs, I want to open the docs folder in Sunwell, see my markdown alongside a live preview, get real-time feedback on style issues, and quickly access validation/polish skills — without memorizing command shortcuts."

**Product Manager:**
> "As a PM writing a PRD, I want Sunwell to catch when I describe a solution without a validated problem, remind me to add success metrics, and help me structure the doc with PRFAQ format."

**Novelist:**
> "As a novelist working on my second draft, I want Sunwell to flag scenes without conflict, warn when I'm telling instead of showing, and help me track character arcs across chapters."

**Developer:**
> "As a developer writing an RFC, I want Sunwell to ensure I've cited code evidence, check that my proposal follows our architecture patterns, and help me break the work into atomic commits."

**QA Engineer:**
> "As a QA engineer writing test plans, I want Sunwell to flag missing edge cases, ensure every test has reproducible steps, and help me generate test cases from requirements."

---

## Goals

1. **Universal writing surface** — Same canvas works for docs, code, specs, stories — lens determines expertise
2. **Lens auto-detection** — Open a docs project → `tech-writer.lens`; open a novel → `novelist.lens`
3. **Live preview** — Toggle between source and rendered view
4. **Lens surface** — Skills, heuristics, and validators visible in the UI
5. **Real-time feedback** — Domain-specific warnings appear as you type
6. **Autonomous workflows** — Multi-step skill chains with checkpoints and state persistence
7. **Framework awareness** — Diataxis for docs, Three-Act for novels, PRFAQ for PMs, etc.

## Non-Goals

1. **WYSIWYG editing** — ProseEditor remains markdown/text-native, not rich text
2. **Collaborative editing** — Real-time multiplayer is out of scope for v1
3. **Custom lens creation UI** — Lenses are still YAML files, not GUI-built (community can contribute)
4. **Domain-specific rendering** — Novel.lens won't render like Scrivener; PM.lens won't render like Jira

---

## Core Feature: Autonomous Workflow Execution

**This is the killer feature.** Not just validation feedback — **autonomous multi-step execution** like DORI's `::auto`, `::pipeline`, and `::chain`.

### The Vision

When you tell Sunwell to "audit this doc and fix the issues", it doesn't just report problems. It:

1. **Classifies intent** — Is this validation, creation, transformation, or refinement?
2. **Selects workflow** — Which skills/rules should be chained together?
3. **Executes autonomously** — Runs the chain with checkpoints and progress updates
4. **Self-corrects** — Uses reflexion loops to improve output quality
5. **Persists state** — Can pause and resume across sessions

### How This Differs from Simple AI Assist

| Simple AI Assist | Sunwell Autonomous Workflows |
|------------------|------------------------------|
| User: "Audit this" → AI: "Here are 5 issues" | User: "Audit this" → AI chains `analyze → audit → suggest-fixes` → "Found 5 issues, fixed 3, 2 need your input" |
| User: "Write docs for this API" → AI: "Here's a draft" | User: "Document this API" → AI chains `context-analyze → draft → audit → polish` → "Created docs, verified 12/12 claims, applied style guide" |
| Every step requires user prompt | Multi-step execution with checkpoints |
| No memory between interactions | State persisted to `.sunwell/state/` |

### Workflow Types

Inspired by DORI's tiered execution:

```typescript
type WorkflowTier = 
  | 'fast'      // Direct skill execution, no analysis
  | 'light'     // Brief acknowledgment, auto-proceed
  | 'full';     // Complete analysis, confirmation required

interface WorkflowExecution {
  tier: WorkflowTier;
  steps: WorkflowStep[];
  state: WorkflowState;
  checkpoints: boolean;          // Pause between steps?
  allowInterruption: boolean;    // Can user stop mid-chain?
}

interface WorkflowStep {
  skill: SkillRef;               // "validation/audit", "transformation/polish"
  purpose: string;
  input: StepInput;
  output?: StepOutput;
  status: 'pending' | 'running' | 'success' | 'warning' | 'error';
}

interface WorkflowState {
  id: string;
  branch: string;                // Git branch
  topic: string;                 // "Auth API Documentation"
  currentStep: number;
  completedSteps: WorkflowStep[];
  persistedAt: Date;
}
```

### Example: "Document this API"

User says: "Document the batch processing API"

Sunwell's response:

```
🎯 Task Analysis

Intent: CREATION (new documentation)
Diataxis: REFERENCE (API endpoint)
Complexity: Moderate (4-step chain)

📋 Workflow Plan

1. context-analyze → Understand feature scope, locate evidence
2. draft-claims    → Extract verifiable claims from source code
3. write-structure → Structure content with Diataxis template
4. audit-enhanced  → Validate all claims against code
5. apply-style     → NVIDIA style guide compliance

Proceed? [yes] [modify] [cancel]
```

User: "yes"

```
📍 Step 1/5: context-analyze
Status: Running...

Found:
- Source: `api/batch.py` (145 lines)
- Tests: `test_batch.py` (89 lines)
- Endpoint: POST /api/v1/batch
- Evidence quality: Strong

✅ Step 1 complete

---

📍 Step 2/5: draft-claims
Status: Running...

Extracted:
- 12 technical claims
- 3 code examples
- 2 TODOs flagged for SME review

✅ Step 2 complete

---

📍 Step 3/5: write-structure
Status: Running...

Created:
- Structure: REFERENCE (API docs)
- Sections: Overview, Endpoint, Parameters, Examples, Errors
- Cross-links: Added to API index

✅ Step 3 complete

---

📍 Step 4/5: audit-enhanced
Status: Running...

Verified:
- Claims: 12/12 (100%)
- Confidence: 94% 🟢
- Self-consistency: All paths agree

✅ Step 4 complete

---

📍 Step 5/5: apply-style
Status: Running...

Applied:
- Style fixes: 5
- Formatting: Consistent
- Accessibility: Verified

✅ Step 5 complete

---

🎉 Workflow Complete: "Document Batch API"

Status: Success ✅
Steps: 5/5
Confidence: 94% 🟢

Output: `docs/api/batch-processing.md`

📋 Follow-up
- [ ] Review 2 TODOs with SME
- [ ] Test code examples in staging
- [ ] Link from API index
```

### Checkpoint Behavior

At each checkpoint (configurable), user can:

- **Continue** — Proceed to next step
- **Skip** — Skip current step, continue chain
- **Stop** — End chain, keep completed work
- **Retry** — Re-run current step with adjustments

```typescript
interface CheckpointPrompt {
  stepComplete: number;
  totalSteps: number;
  summary: string;
  issues?: string[];
  options: ('continue' | 'skip' | 'stop' | 'retry' | 'modify')[];
}
```

### State Persistence

Chains can pause and resume across sessions.

**Directory structure:**
```
.sunwell/
├── state/
│   ├── main/                         # Git branch (slugified)
│   │   ├── batch-api-docs.json       # Topic state
│   │   └── auth-migration.json
│   └── feature-auth/                 # Another branch
│       └── api-redesign.json
└── config.yaml                       # Project-level settings
```

**Branch isolation:** State is keyed by Git branch (via `git rev-parse --abbrev-ref HEAD`). Switching branches switches workflow context. Branch names are slugified (e.g., `feature/auth-v2` → `feature-auth-v2`).

**State file format (JSON):**
```json
{
  "version": 1,
  "id": "wf-2026-01-21-batch-api",
  "topic": "Batch API Documentation",
  "chain": "feature-docs",
  "currentStep": 3,
  "startedAt": "2026-01-21T14:30:00Z",
  "updatedAt": "2026-01-21T14:35:22Z",
  "completedSteps": [
    {
      "skill": "context-analyze",
      "status": "success",
      "startedAt": "2026-01-21T14:30:00Z",
      "completedAt": "2026-01-21T14:30:02Z",
      "output": {
        "files_analyzed": ["api/batch.py", "tests/test_batch.py"],
        "evidence_quality": "strong"
      }
    },
    {
      "skill": "draft-claims",
      "status": "success",
      "startedAt": "2026-01-21T14:30:02Z",
      "completedAt": "2026-01-21T14:30:06Z",
      "output": {
        "claims_extracted": 12,
        "todos_flagged": 2
      }
    }
  ],
  "pendingSteps": [
    {"skill": "write-structure"},
    {"skill": "audit-enhanced"},
    {"skill": "apply-style"}
  ],
  "context": {
    "lens": "tech-writer.lens",
    "target_file": "docs/api/batch-processing.md",
    "working_dir": "/Users/dev/project"
  }
}
```

**Atomic writes:** State is written to a temp file first, then renamed (atomic on POSIX). Corrupted state files are backed up and workflow restarts from scratch.

**Resume command:** `sunwell resume` or "Resume last workflow" in UI

### Pre-Built Workflow Chains

```yaml
workflows:
  feature-docs:
    description: "Document a new feature end-to-end"
    steps:
      - context-analyze
      - draft-claims
      - write-structure
      - audit-enhanced
      - apply-style
    checkpoint_after: [2, 4]  # Pause after draft and audit
    
  health-check:
    description: "Comprehensive validation of existing docs"
    steps:
      - context-analyze
      - audit-enhanced
      - style-check
      - code-example-audit
      - confidence-score
    checkpoint_after: []  # Run all without pause
    
  quick-fix:
    description: "Fast issue resolution"
    steps:
      - context-analyze
      - auto-select-fixer
      - audit
    checkpoint_after: []
    
  modernize:
    description: "Update legacy documentation"
    steps:
      - audit-enhanced
      - draft-updates
      - modularize-content
      - apply-style
      - reflexion-loop
    checkpoint_after: [1, 4]
```

### Intelligent Routing

Like DORI's `::auto`, Sunwell routes natural language to appropriate workflows:

```yaml
intent_routing:
  CREATION:
    signals: ["write", "create", "document", "draft", "new"]
    workflow: feature-docs
    
  VALIDATION:
    signals: ["check", "audit", "verify", "validate"]
    workflow: health-check
    
  TRANSFORMATION:
    signals: ["restructure", "split", "modularize", "fix"]
    workflow: quick-fix
    
  REFINEMENT:
    signals: ["improve", "polish", "enhance", "tighten"]
    workflow: quick-fix
    
  # Fuzzy routing for ambiguous requests
  "fix the examples":
    interpretation: "VALIDATION (verify first, then fix)"
    workflow: health-check
    followup: "Found {n} issues. Fix them? [y/n]"
```

### UI Integration

The autonomous execution appears in the **WorkflowPanel** (new block):

```
┌─────────────────────────────────────────────────────────────────────┐
│ [file.md]                        [Source ◉ │ ○ Preview]   [Lens ▼] │
├──────────┬─────────────────────────────────────────────┬────────────┤
│ FileTree │                                             │ Workflow   │
│          │  # Batch Processing API                     │            │
│ docs/    │                                             │ Step 3/5   │
│ ├─ api/  │  POST /api/v1/batch                        │ [████▒▒▒]  │
│ │  └─ ba │  ...                                        │            │
│ │        │                                             │ ✅ Analyze │
│ │        │                                             │ ✅ Draft   │
│ │        │                                             │ 🔄 Write   │
│ │        │                                             │ ⏳ Audit   │
│ │        │                                             │ ⏳ Style   │
│ │        │                                             │            │
│ │        │                                             │ [Stop]     │
├──────────┴─────────────────────────────────────────────┴────────────┤
│ 📊 847 words │ 📑 REFERENCE │ 🔄 Step 3/5 │ tech-writer lens       │
└─────────────────────────────────────────────────────────────────────┘
```

### Error Handling

If a step fails:

```
⚠️ Chain Halted at Step 4/5 (audit-enhanced)

Reason: 3 claims could not be verified

Unverified claims:
1. "Rate limit is 1000/hour" — No source found
2. "Supports JSON and XML" — Only JSON found in code
3. "Timeout is 30 seconds" — Conflicting values: 30s vs 60s

Recovery Options:
1. [Fix claims] — Update document with correct values
2. [Skip audit] — Continue without verification (⚠️ risky)
3. [Stop here] — Keep completed work, end chain
4. [Flag for SME] — Mark claims as needing human review

Which option?
```

### Why This Matters

**Without autonomous workflows:**
```
User: "audit this"
AI: "Here are 5 issues"
User: "fix issue 1"
AI: "Fixed"
User: "fix issue 2"
AI: "Fixed"
User: "fix issue 3"
AI: "Fixed"
User: "now polish it"
AI: "Done"
User: "check style guide"
AI: "3 issues"
...
```
7 prompts for one task.

**With autonomous workflows:**
```
User: "audit and fix this doc"
AI: [chains audit → fix → polish → style-check automatically]
    "Fixed 5 issues, polished content, applied style guide.
     2 items need SME review. See updated doc."
```
1 prompt, same result.

### Workflow Engine Design Alternatives

Three architectural approaches were evaluated:

| Approach | Description | Pros | Cons | Verdict |
|----------|-------------|------|------|---------|
| **A: Procedural Engine** | Sequential step execution with explicit state machine | Simple to implement, predictable, easy debugging | No parallelism, rigid flow, harder to extend | ✅ Selected |
| **B: Event-Driven** | Steps emit events, listeners trigger next steps | Flexible, supports parallelism, loose coupling | Complex debugging, race conditions, harder to reason about state | ❌ Over-engineered |
| **C: Actor Model** | Each step is an actor with message passing | Maximum parallelism, fault isolation | Significant complexity, overkill for 5-10 step chains | ❌ Over-engineered |

**Selected: Procedural Engine (Option A)**

Rationale:
- Workflow chains are typically 3-7 sequential steps — parallelism adds complexity without benefit
- Debugging autonomous execution requires clear, linear traces
- Extends existing `Workflow` dataclass in `src/sunwell/core/workflow.py`
- Matches mental model of "audit → fix → polish" as a pipeline

**Engine Design:**

```python
# src/sunwell/workflow/engine.py (new)

@dataclass
class WorkflowEngine:
    """Procedural workflow executor with checkpoints and state persistence."""
    
    state_dir: Path = Path(".sunwell/state")
    
    async def execute(self, chain: Workflow, context: WriterContext) -> WorkflowResult:
        """Execute workflow steps sequentially with checkpoint support."""
        state = self._load_or_create_state(chain, context)
        
        for i, step in enumerate(chain.steps[state.current_step:], state.current_step):
            state.current_step = i
            
            # Check for user interruption
            if self._interrupted:
                await self._persist_state(state)
                return WorkflowResult(status="paused", state=state)
            
            # Execute step
            try:
                result = await self._execute_step(step, context)
                state.completed_steps.append(result)
                
                # Checkpoint if configured
                if i in chain.checkpoint_after:
                    await self._persist_state(state)
                    if not await self._confirm_continue(state):
                        return WorkflowResult(status="paused", state=state)
                        
            except StepError as e:
                return await self._handle_step_error(e, state, context)
        
        return WorkflowResult(status="completed", state=state)
```

**Why not event-driven?** Workflow chains are inherently sequential ("audit THEN fix THEN polish"). Event-driven adds indirection without benefit. The procedural approach also makes it trivial to implement "stop here and keep completed work" — just return the state.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Workflow engine complexity** | Medium | High | Start with 3 pre-built workflows; defer custom chain builder to v2 |
| **State corruption on crash** | Low | High | Atomic writes with temp file + rename; validate state on load |
| **LLM step timeouts** | Medium | Medium | Per-step timeout (default 60s); retry with backoff; skip option |
| **Preview selection mapping fails** | Medium | Low | Graceful fallback to source-only selection; log unmappable ranges |
| **Lens auto-detection wrong** | Low | Low | Easy manual override via status bar dropdown; remember user choice |
| **Validation performance on large docs** | Medium | Medium | Debounce (300ms); run deterministic validators only on keystroke; heuristic on save |

**Cancellation Behavior:**

When user stops mid-chain:
1. Current step completes or is cancelled (depending on interruptibility)
2. Completed steps are preserved in state
3. State is persisted to `.sunwell/state/{branch}/{topic}.json`
4. User can resume with `sunwell resume` or "Resume workflow" button
5. Partial outputs (e.g., half-edited file) are NOT applied — only completed steps have effect

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **View mode** | Toggle (source ↔ preview), not split | Simpler, more focused; split is IDE-brain |
| **Selection model** | Universal — select text in any view, send to AI | Interaction doesn't change based on view mode |
| **Lens binding** | Auto-detect from project, manual override | `tech-writer.lens` for docs projects; user can switch |
| **Validation timing** | Debounced (300ms after typing stops) | Balance responsiveness with CPU; avoid jitter |
| **Skill invocation** | Selection → action menu, shortcuts, natural language | Context-aware; work on what you're looking at |
| **Feedback granularity** | Inline warnings + collapsible panel | Inline for specific issues; panel for overview |

### Why Toggle, Not Split

Traditional IDEs show source + preview side-by-side. This is:
- **Cramped** — halves usable space for each
- **Distracting** — two things competing for attention
- **Unnecessary** — you're either writing or reviewing, rarely both simultaneously

Modern writing apps (iA Writer, Bear, Notion, Obsidian) use **toggle**:
- **Full focus** — 100% of space for current task
- **Clean** — one thing at a time
- **Fast switch** — ⌘P or click to flip

### Universal Selection Model

Key insight: **The interaction model shouldn't change based on view mode.**

```
┌─────────────────────────────────────────────────────────────────────┐
│ In SOURCE view:                                                      │
│                                                                      │
│   Select: "Our powerful API makes it easy to..."                    │
│   Right-click → [Improve] [Audit] [Ask] [Explain]                   │
│                                                                      │
│ In PREVIEW view:                                                     │
│                                                                      │
│   Select: "Our powerful API makes it easy to..."                    │
│   Right-click → [Improve] [Audit] [Ask] [Explain]  ← SAME ACTIONS   │
│                                                                      │
│ Result: Same actions work in both views.                            │
│ The AI receives selected text + file context regardless of view.    │
└─────────────────────────────────────────────────────────────────────┘
```

This is simpler than IDEs where preview is read-only and actions only work in source.

---

## Architecture

### Page Type: `docs:{project}`

Extends the Page interface from RFC-082:

```typescript
interface WriterPage extends Page {
  id: `docs:${string}`;           // "docs:pachyderm", "docs:sunwell"
  layout: WriterLayout;
  lens: LensRef;                  // Active lens (default: tech-writer)
  validationState: ValidationState;
  diataxisType: DiataxisType | null;  // Detected content type
}

interface WriterLayout extends Layout {
  arrangement: 'writer';          // New arrangement type
  viewMode: 'source' | 'preview'; // Toggle state (not split!)
  sidebars: ['FileTree', 'Outline'];
  statusBar: StatusBarConfig;
}

type ViewMode = 'source' | 'preview';
```

### Selection Model

Universal selection that works in both source and preview:

```typescript
interface SelectionContext {
  text: string;                   // Selected text
  file: string;                   // File path
  range: { start: number; end: number };  // Character offsets
  viewMode: ViewMode;             // Where selection was made
  
  // Resolved context (same in both views)
  lineRange?: { start: number; end: number };
  surroundingContext?: string;    // ±5 lines for AI context
}

interface SelectionAction {
  id: string;                     // "improve", "audit", "ask", "explain"
  label: string;
  shortcut?: string;              // "⌘I" for improve
  handler: (selection: SelectionContext) => Promise<void>;
}

// Actions available on any selection
const SELECTION_ACTIONS: SelectionAction[] = [
  { id: 'improve', label: 'Improve', shortcut: '⌘I' },
  { id: 'audit', label: 'Audit', shortcut: '⌘A' },
  { id: 'ask', label: 'Ask...', shortcut: '⌘K' },
  { id: 'explain', label: 'Explain' },
];
```

### Layout: `writer` Arrangement

New arrangement type specifically for documentation work. **Single main view with toggle.**

```
SOURCE MODE (editing):
┌────────────────────────────────────────────────────────────────────┐
│ [file1.md] [file2.md]              [Source ◉ │ ○ Preview] [Lens ▼]│
├──────────┬─────────────────────────────────────────────┬──────────┤
│ FileTree │                                             │ Outline  │
│          │  # Getting Started                          │          │
│ docs/    │                                             │ H1       │
│ ├─ get-  │  This guide helps you get up and running   │ ├─ H2    │
│ │  start │  with Sunwell in under 5 minutes.          │ │  └─ H3 │
│ ├─ ref/  │                                             │ └─ H2    │
│ └─ tut/  │  ## Prerequisites                           │          │
│          │  ░░░░░░░░░░░░░░░░░░░ ← selection            │          │
│          │                     [Improve] [Audit] [Ask] │          │
├──────────┴─────────────────────────────────────────────┴──────────┤
│ 📊 847 words │ 📑 TUTORIAL │ ⚠️ 2 │ tech-writer lens             │
└───────────────────────────────────────────────────────────────────┘

PREVIEW MODE (reviewing):
┌────────────────────────────────────────────────────────────────────┐
│ [file1.md] [file2.md]              [○ Source │ Preview ◉] [Lens ▼]│
├──────────┬─────────────────────────────────────────────┬──────────┤
│ FileTree │                                             │ Outline  │
│          │  Getting Started                            │          │
│ docs/    │  ════════════════                           │ H1       │
│ ├─ get-  │                                             │ ├─ H2    │
│ │  start │  This guide helps you get up and running   │ │  └─ H3 │
│ ├─ ref/  │  with Sunwell in under 5 minutes.          │ └─ H2    │
│ └─ tut/  │                                             │          │
│          │  Prerequisites                              │          │
│          │  ░░░░░░░░░░░ ← selection works here too!   │          │
│          │            [Improve] [Audit] [Ask]          │          │
├──────────┴─────────────────────────────────────────────┴──────────┤
│ 📊 847 words │ 📑 TUTORIAL │ ⚠️ 2 │ tech-writer lens             │
└───────────────────────────────────────────────────────────────────┘
```

**Toggle shortcut:** `⌘P` (or click the toggle)

### Component Sizing

| Component | Size | Position | Collapsible |
|-----------|------|----------|-------------|
| FileTree | 200px | Left sidebar | Yes (⌘B) |
| Main view | Remaining | Center | No |
| Outline | 200px | Right sidebar | Yes (⌘O) |
| StatusBar | 32px | Bottom | No |

**Simpler than split:** No divider dragging, no competing panes.

---

## Selection → Action Flow

The core interaction pattern: **Select text → Choose action → Get result**

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USER SELECTS TEXT (works in source OR preview)                   │
│                                                                      │
│    "Our powerful API makes it easy to integrate with any system"    │
│     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. ACTION MENU APPEARS (floating near selection)                    │
│                                                                      │
│    ┌─────────────────────────────┐                                  │
│    │ [Improve ⌘I] [Audit] [Ask…] │                                  │
│    └─────────────────────────────┘                                  │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ User clicks "Improve"
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. AI PROCESSES WITH LENS CONTEXT                                   │
│                                                                      │
│    Input:                                                            │
│    - Selected text                                                   │
│    - Surrounding context (±5 lines)                                  │
│    - Active lens heuristics (tech-writer: no marketing fluff)       │
│    - File metadata (Diataxis type: REFERENCE)                       │
│                                                                      │
│    Process:                                                          │
│    - Apply "Signal over Noise" heuristic                            │
│    - Check for marketing language                                    │
│    - Generate improved version                                       │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. RESULT SHOWN INLINE (or in panel for longer responses)           │
│                                                                      │
│    Original: "Our powerful API makes it easy to integrate..."       │
│    Improved: "The REST API supports 50+ integrations via webhooks"  │
│                                                                      │
│    [Accept] [Edit] [Dismiss]                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This Works

1. **No mode switching** — Same gesture works in source and preview
2. **Context-aware** — Lens heuristics inform the AI's response
3. **Non-destructive** — User chooses whether to accept changes
4. **Keyboard-friendly** — ⌘I for improve, ⌘K for ask

---

## New Blocks

### 1. ValidationBlock

Real-time feedback from lens validators.

```typescript
interface ValidationBlockProps {
  warnings: ValidationWarning[];
  errors: ValidationError[];
  suggestions: Suggestion[];
  lensName: string;
  isRunning: boolean;
}

interface ValidationWarning {
  line: number;
  column?: number;
  message: string;
  rule: string;           // "no_marketing_fluff", "front_loaded"
  severity: 'warning' | 'info';
  suggestion?: string;    // "Replace with specific claim"
}
```

**Features:**
- Collapsible (show count when collapsed, full list when expanded)
- Click warning → jump to line in editor
- Group by rule or by location
- Show validator source (which heuristic triggered it)

**Data source:** Runs validators from active lens on document content.

### 2. SkillsBlock

Quick access to lens skills/shortcuts.

```typescript
interface SkillsBlockProps {
  skills: SkillDef[];
  recentSkills: string[];  // Last 3 used
  categories: SkillCategory[];
}

interface SkillDef {
  id: string;              // "audit-documentation"
  name: string;            // "Audit"
  shortcut: string;        // "::a"
  description: string;
  category: 'validation' | 'creation' | 'transformation' | 'utility';
  icon: string;
}
```

**Layout:**
```
┌─────────────────────────────────────┐
│ 🛠️ Skills                    [···] │
├─────────────────────────────────────┤
│ Recent: [Audit] [Polish] [Preview]  │
├─────────────────────────────────────┤
│ Validation                          │
│   ::a  Audit documentation          │
│   ::a-2 Deep audit                  │
│   ::health Check health             │
│                                     │
│ Transformation                      │
│   ::p  Polish                       │
│   ::m  Modularize                   │
│   ::md Fix markdown                 │
└─────────────────────────────────────┘
```

**Interaction:**
- Click skill → execute it on current document
- Hover → show full description
- Type shortcut in editor → same effect

### 3. DiataxisBlock

Content type detection and guidance.

```typescript
interface DiataxisBlockProps {
  detectedType: DiataxisType | null;
  confidence: number;
  signals: DiataxisSignal[];
  recommendations: string[];
}

type DiataxisType = 'TUTORIAL' | 'HOW_TO' | 'EXPLANATION' | 'REFERENCE';

interface DiataxisSignal {
  type: DiataxisType;
  weight: number;
  reason: string;  // "Contains 'getting started'" → TUTORIAL
}
```

**Display:**
```
┌─────────────────────────────────────┐
│ 📑 Diataxis: TUTORIAL (87%)         │
├─────────────────────────────────────┤
│ Signals:                            │
│  • "getting started" in title       │
│  • Step-by-step structure           │
│  • Learning objectives present      │
├─────────────────────────────────────┤
│ ⚠️ Mixed signal: Reference table    │
│    detected. Consider moving to     │
│    separate reference page.         │
└─────────────────────────────────────┘
```

### 4. HeuristicsBlock (Optional)

Shows active heuristics from lens with examples.

```typescript
interface HeuristicsBlockProps {
  heuristics: Heuristic[];
  activeViolations: HeuristicViolation[];
}
```

**Use case:** Training mode — show what rules are being applied as user writes.

### 5. WorkflowPanel

Displays autonomous workflow execution progress.

```typescript
interface WorkflowPanelProps {
  workflow: WorkflowExecution | null;
  isRunning: boolean;
  onStop: () => void;
  onResume: () => void;
  onSkipStep: () => void;
}

interface WorkflowStepDisplay {
  name: string;
  status: 'pending' | 'running' | 'success' | 'warning' | 'error' | 'skipped';
  duration?: number;
  output?: StepSummary;
}
```

**Layout:**
```
┌─────────────────────────────────────┐
│ 🔄 Workflow: feature-docs           │
├─────────────────────────────────────┤
│ Step 3/5          [████▒▒▒]         │
│                                     │
│ ✅ context-analyze      2.1s        │
│ ✅ draft-claims         4.3s        │
│ 🔄 write-structure      ...         │
│ ⏳ audit-enhanced                   │
│ ⏳ apply-style                      │
│                                     │
│ [Stop] [Skip Step]                  │
├─────────────────────────────────────┤
│ 💾 State: .sunwell/state/main/...   │
└─────────────────────────────────────┘
```

**Interaction:**
- Click step → expand output details
- Stop → halt chain, preserve completed work
- Skip → skip current step, continue
- If paused, shows "Resume" button

---

## Lens Integration

### Auto-Detection

Lens detection builds on existing domain inference:

```python
# src/sunwell/surface/fallback.py — EXISTING (used as-is)
def get_domain_for_project(project_path: Path) -> str:
    """Returns: 'software', 'documentation', 'planning', 'data'"""

# src/sunwell/naaru/shards.py:212 — EXISTING domain→lens mapping
DOMAIN_LENS_MAP = {
    "documentation": "tech-writer.lens",
    "software": "coder.lens",
    "planning": "team-pm.lens",
    "data": "coder.lens",
}

# src/sunwell/surface/lens_detection.py — NEW (extends existing)
def get_lens_for_project(project_path: Path) -> str:
    """Detect appropriate lens from project structure.
    
    Uses existing domain detection + domain→lens mapping.
    Adds documentation-specific marker refinement.
    """
    domain = get_domain_for_project(project_path)
    
    # Refine documentation projects with specific markers
    if domain == "documentation":
        # Check for framework-specific markers
        DOC_MARKERS = {
            "fern/": "tech-writer.lens",      # Fern docs
            "docusaurus.config.js": "tech-writer.lens",
            "mkdocs.yml": "tech-writer.lens",
            "conf.py": "tech-writer.lens",    # Sphinx
            "novel.md": "novelist.lens",      # Fiction
            "manuscript/": "novelist.lens",
        }
        for marker, lens in DOC_MARKERS.items():
            if (project_path / marker).exists():
                return lens
    
    return DOMAIN_LENS_MAP.get(domain, "coder.lens")
```

**Integration with existing code:**
- `get_domain_for_project()` already handles pyproject.toml, package.json, etc.
- `DOMAIN_LENS_MAP` already exists in `naaru/shards.py`
- New function adds refinement layer for documentation subdomains

### Lens-to-Block Binding

ValidationBlock reads validators from active lens:

```python
# src/sunwell/surface/blocks.py (new)

@dataclass(frozen=True, slots=True)
class ValidationBlockDef(BlockDef):
    """Block that runs lens validators on current document."""
    
    id: str = "ValidationBlock"
    category: str = "feedback"
    component: str = "ValidationBlock"
    
    def get_validators(self, lens: Lens) -> list[Validator]:
        """Extract validators from lens definition."""
        return lens.validators.deterministic + lens.validators.heuristic
```

### Skill Execution

SkillsBlock invokes lens skills:

```python
# Integration with existing skill system

async def execute_skill(skill_id: str, context: WriterContext) -> SkillResult:
    """Execute a skill from the active lens."""
    lens = context.active_lens
    skill = lens.get_skill(skill_id)
    
    if skill.type == "inline":
        return await run_inline_skill(skill, context)
    elif skill.type == "script":
        return await run_script_skill(skill, context)
```

---

## Validation Pipeline

### Performance Budgets

| Operation | Target | Max | Notes |
|-----------|--------|-----|-------|
| Debounce delay | 300ms | 500ms | Balance responsiveness vs CPU |
| Deterministic validators | <50ms | 100ms | grep-based, no LLM |
| Heuristic validators (per) | <2s | 5s | LLM-based, run on save only |
| Full validation pass | <3s | 10s | All validators combined |
| Workflow step (typical) | <5s | 30s | Single skill execution |
| Workflow step (max) | 60s | 120s | Complex analysis steps |
| State persistence | <100ms | 500ms | Atomic JSON write |

**Validation strategy by trigger:**

| Trigger | Validators Run | Rationale |
|---------|----------------|-----------|
| Keystroke (debounced) | Deterministic only | Fast, no LLM cost |
| Save (⌘S) | All validators | Full feedback at natural pause point |
| Explicit (::a) | All + deep analysis | User requested comprehensive check |

### Timing

```
User types → 300ms debounce → Run deterministic validators → Update ValidationBlock
                    ↓
              Skip if user typing

User saves → Run ALL validators (deterministic + heuristic) → Full update
```

### Validator Execution

```python
@dataclass
class ValidationPipeline:
    """Run lens validators on document content."""
    
    lens: Lens
    debounce_ms: int = 300
    
    async def validate(self, content: str, file_path: Path) -> ValidationResult:
        """Run all validators from active lens."""
        results = []
        
        # Deterministic validators (fast, run first)
        for validator in self.lens.validators.deterministic:
            result = await self.run_deterministic(validator, content)
            results.extend(result)
        
        # Heuristic validators (may use LLM, run second)
        for validator in self.lens.validators.heuristic:
            result = await self.run_heuristic(validator, content)
            results.extend(result)
        
        return ValidationResult(
            warnings=[r for r in results if r.severity == 'warning'],
            errors=[r for r in results if r.severity == 'error'],
            suggestions=[r for r in results if r.severity == 'info'],
        )
```

### Inline Highlighting

Warnings appear as squiggles in ProseEditor:

```typescript
// studio/src/components/primitives/ProseEditor.svelte

interface EditorWarning {
  from: number;      // Character offset
  to: number;
  severity: 'warning' | 'error' | 'info';
  message: string;
}

// Use CodeMirror lint extension or custom decoration
```

---

## Diataxis Detection

### Signal Extraction

```python
DIATAXIS_SIGNALS = {
    DiataxisType.TUTORIAL: {
        "triggers": ["tutorial", "getting started", "learn", "first steps", "quickstart"],
        "structure": ["learning objectives", "prerequisites", "step 1", "next steps"],
        "weight": 1.0,
    },
    DiataxisType.HOW_TO: {
        "triggers": ["how to", "guide", "configure", "set up", "deploy", "fix"],
        "structure": ["goal", "steps", "troubleshooting"],
        "weight": 1.0,
    },
    DiataxisType.EXPLANATION: {
        "triggers": ["understand", "architecture", "concepts", "overview", "why"],
        "structure": ["context", "how it works", "design"],
        "weight": 1.0,
    },
    DiataxisType.REFERENCE: {
        "triggers": ["reference", "api", "parameters", "configuration", "options"],
        "structure": ["table", "parameters", "returns", "examples"],
        "weight": 1.0,
    },
}

def detect_diataxis(content: str, file_path: Path) -> DiataxisDetection:
    """Detect Diataxis content type from document."""
    scores = {t: 0.0 for t in DiataxisType}
    signals = []
    
    content_lower = content.lower()
    filename = file_path.stem.lower()
    
    for dtype, config in DIATAXIS_SIGNALS.items():
        for trigger in config["triggers"]:
            if trigger in filename:
                scores[dtype] += 0.3
                signals.append(DiataxisSignal(dtype, 0.3, f"'{trigger}' in filename"))
            if trigger in content_lower[:500]:  # Check intro
                scores[dtype] += 0.2
                signals.append(DiataxisSignal(dtype, 0.2, f"'{trigger}' in introduction"))
    
    # Structure detection
    # ... (check for headers matching structure patterns)
    
    best = max(scores, key=scores.get)
    confidence = scores[best] / sum(scores.values()) if sum(scores.values()) > 0 else 0
    
    return DiataxisDetection(
        detected_type=best if confidence > 0.4 else None,
        confidence=confidence,
        signals=signals,
    )
```

### Mixed Content Warning

If signals suggest multiple types:

```python
def check_diataxis_purity(detection: DiataxisDetection) -> list[Warning]:
    """Warn if document mixes Diataxis types."""
    warnings = []
    
    # If second-highest score is > 30% of highest, warn
    sorted_scores = sorted(detection.scores.items(), key=lambda x: -x[1])
    if len(sorted_scores) >= 2:
        first, second = sorted_scores[0], sorted_scores[1]
        if second[1] > first[1] * 0.3:
            warnings.append(Warning(
                message=f"Mixed content types detected: {first[0]} + {second[0]}",
                suggestion=f"Consider splitting into separate {first[0]} and {second[0]} pages",
                severity="warning",
            ))
    
    return warnings
```

---

## CLI Integration: `sunwell .`

### Command: `sunwell open`

Like `code .` for VS Code, Sunwell gets `sunwell .` (or `sunwell open .`):

```bash
# Open current directory in Sunwell Studio
sunwell .
sunwell open .

# Open specific path
sunwell open ~/projects/pachyderm/docs

# Open with explicit lens
sunwell open . --lens tech-writer

# Open in writer mode explicitly
sunwell open . --mode writer
```

### Implementation

```python
# src/sunwell/cli/open_cmd.py

import subprocess
from pathlib import Path

import click

from sunwell.surface.fallback import get_domain_for_project  # EXISTING
from sunwell.surface.lens_detection import get_lens_for_project  # NEW (see Lens Integration)


@click.command(name="open")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--lens", "-l", help="Override lens selection")
@click.option("--mode", "-m", type=click.Choice(["auto", "writer", "code", "planning"]), 
              default="auto", help="Workspace mode")
def open_project(path: str, lens: str | None, mode: str) -> None:
    """Open a project in Sunwell Studio.
    
    \b
    Examples:
        sunwell .                    # Open current directory
        sunwell open docs/           # Open docs folder
        sunwell open . --lens tech-writer
    """
    project_path = Path(path).resolve()
    
    # Auto-detect mode from domain if not specified
    if mode == "auto":
        domain = get_domain_for_project(project_path)  # EXISTING function
        mode = {
            "documentation": "writer",
            "software": "code", 
            "planning": "planning",
            "data": "code",
        }.get(domain, "code")
    
    # Auto-detect lens if not specified
    if not lens:
        lens = get_lens_for_project(project_path)  # NEW function (see Lens Integration)
    
    click.echo(f"Opening {project_path.name} in {mode} mode with {lens} lens...")
    
    # Launch Tauri app with arguments
    # The studio app reads these on startup
    launch_studio(
        project=str(project_path),
        lens=lens,
        mode=mode,
    )


def launch_studio(project: str, lens: str, mode: str) -> None:
    """Launch Sunwell Studio (Tauri app)."""
    import os
    import sys
    
    # Find the studio binary
    # In development: run via cargo
    # In production: use installed binary
    
    studio_dir = Path(__file__).parent.parent.parent.parent / "studio"
    
    if (studio_dir / "src-tauri").exists():
        # Development mode: run via cargo tauri
        subprocess.Popen(
            ["cargo", "tauri", "dev", "--", 
             "--project", project, 
             "--lens", lens, 
             "--mode", mode],
            cwd=studio_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # Production: look for installed binary
        binary = "sunwell-studio"
        if sys.platform == "darwin":
            binary = "/Applications/Sunwell.app/Contents/MacOS/Sunwell"
        elif sys.platform == "win32":
            binary = "C:\\Program Files\\Sunwell\\Sunwell.exe"
        
        subprocess.Popen(
            [binary, "--project", project, "--lens", lens, "--mode", mode],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
```

### Register in main.py

```python
# In src/sunwell/cli/main.py

# Add to imports
from sunwell.cli import open_cmd

# Register command
main.add_command(open_cmd.open_project, name="open")

# Also register '.' as an alias pattern in GoalFirstGroup
# so 'sunwell .' works without 'open'
```

### Alias: `sunwell .`

The `GoalFirstGroup` can detect `.` or paths as special:

```python
class GoalFirstGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args:
            return super().parse_args(ctx, args)
        
        first_arg = args[0]
        
        # Check if it's a path (starts with . or / or ~)
        if first_arg in (".", "..") or first_arg.startswith(("/", "~", "./")):
            # Treat as 'open' command
            ctx.ensure_object(dict)
            ctx.obj["_open_path"] = first_arg
            args = args[1:]
        
        # ... rest of existing logic
```

---

## Implementation Plan

### Phase 0: CLI Integration (1 day)

1. **Create `open_cmd.py`** with `sunwell open` command
2. **Register in main.py** as both `open` and `.` alias
3. **Add launch_studio()** function for Tauri app startup
4. **Wire Tauri args** — studio reads `--project`, `--lens`, `--mode`

### Phase 1: Core Layout (2 days)

1. **Add `writer` arrangement type** to `SurfaceArrangement`
2. **Implement view toggle** (source ↔ preview) with ⌘P
3. **Add `docs:{project}` page pattern** to RFC-082 Page types
4. **Wire status bar** with word count, Diataxis badge, warnings count

### Phase 2: Selection Actions (2 days)

1. **Implement SelectionContext** — capture selection from either view
2. **Create action menu** — floating menu near selection
3. **Wire selection → AI** — send text + context + lens heuristics
4. **Show inline results** with Accept/Edit/Dismiss

### Phase 3: Validation Block (1 day)

1. **Create ValidationBlock.svelte** — collapsible warnings panel
2. **Add to block registry** (`blocks.py`)
3. **Implement validation pipeline** with 300ms debounce
4. **Wire lens validators** to block

### Phase 4: Autonomous Workflow Execution (3 days) ⭐ KEY FEATURE

1. **Implement WorkflowEngine** — orchestrates multi-step chains
   ```python
   # src/sunwell/workflow/engine.py
   class WorkflowEngine:
       async def execute(self, chain: WorkflowChain, context: WriterContext) -> WorkflowResult
       async def pause(self, workflow_id: str) -> None
       async def resume(self, workflow_id: str) -> WorkflowResult
   ```

2. **Intent Router** — natural language → workflow selection
   ```python
   # src/sunwell/workflow/router.py
   class IntentRouter:
       def classify(self, user_input: str, context: WriterContext) -> IntentClassification
       def select_workflow(self, intent: Intent) -> WorkflowChain
   ```

3. **State Persistence** — save/restore workflow state
   ```python
   # src/sunwell/workflow/state.py
   class WorkflowState:
       def save(self, workflow: WorkflowExecution, path: Path) -> None
       def load(self, path: Path) -> WorkflowExecution
   ```

4. **WorkflowPanel.svelte** — progress display, controls
5. **Skill-to-Step mapping** — lens skills → workflow steps
6. **Checkpoint behavior** — pause prompts, recovery options

### Phase 5: Pre-Built Workflows (1 day)

1. **Define workflow templates** in lens YAML
   ```yaml
   workflows:
     feature-docs: [context-analyze, draft, write, audit, style]
     health-check: [analyze, audit, style, examples, score]
     quick-fix: [analyze, auto-fix, audit]
   ```
2. **`sunwell resume` command** — resume last paused workflow
3. **Workflow selection UI** — dropdown or command palette

### Phase 6: Diataxis + Status Bar (1 day)

1. **Implement Diataxis signal extraction**
2. **Add Diataxis badge to status bar** (click to expand details)
3. **Add purity checking** (warn on mixed types)

### Phase 7: Polish (1 day)

1. **Inline warning squiggles** in source view
2. **Lens selector dropdown** in header
3. **Keyboard shortcuts** (⌘P toggle, ⌘I improve, ⌘K ask)
4. **Persist view mode preference** per file

**Total: ~12 days** (autonomous workflows add 4 days but are the key differentiator)

---

## Svelte Component Stubs

### ValidationBlock.svelte

```svelte
<!--
  ValidationBlock.svelte — Real-time feedback from lens validators (RFC-086)
  
  Shows warnings, errors, and suggestions as user writes.
  Collapsible; click warning to jump to line.
-->
<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  
  interface ValidationWarning {
    line: number;
    column?: number;
    message: string;
    rule: string;
    severity: 'warning' | 'error' | 'info';
    suggestion?: string;
  }
  
  interface Props {
    warnings?: ValidationWarning[];
    lensName?: string;
    isRunning?: boolean;
    onNavigate?: (line: number) => void;
  }
  
  let {
    warnings = [],
    lensName = "tech-writer",
    isRunning = false,
    onNavigate,
  }: Props = $props();
  
  let collapsed = $state(false);
  
  const warningCount = $derived(warnings.filter(w => w.severity === 'warning').length);
  const errorCount = $derived(warnings.filter(w => w.severity === 'error').length);
</script>

<div class="validation-block" class:collapsed>
  <div class="header" onclick={() => collapsed = !collapsed}>
    <span class="title">
      {#if isRunning}
        <span class="spinner">⟳</span>
      {:else}
        ✓
      {/if}
      Validation
    </span>
    <span class="counts">
      {#if errorCount > 0}
        <span class="error-count">❌ {errorCount}</span>
      {/if}
      {#if warningCount > 0}
        <span class="warning-count">⚠️ {warningCount}</span>
      {/if}
      {#if errorCount === 0 && warningCount === 0}
        <span class="all-good">✅ All good</span>
      {/if}
    </span>
    <span class="lens-name">{lensName}</span>
  </div>
  
  {#if !collapsed}
    <div class="warnings" transition:fly={{ y: -10, duration: 150 }}>
      {#each warnings as warning}
        <div 
          class="warning-item {warning.severity}"
          onclick={() => onNavigate?.(warning.line)}
        >
          <span class="line">L{warning.line}</span>
          <span class="message">{warning.message}</span>
          <span class="rule">{warning.rule}</span>
        </div>
      {/each}
      {#if warnings.length === 0}
        <div class="empty">No issues found</div>
      {/if}
    </div>
  {/if}
</div>
```

### SkillsBlock.svelte

```svelte
<!--
  SkillsBlock.svelte — Quick access to lens skills (RFC-086)
  
  Shows available skills from active lens with shortcuts.
  Click to execute on current document.
-->
<script lang="ts">
  interface Skill {
    id: string;
    name: string;
    shortcut: string;
    description: string;
    category: string;
  }
  
  interface Props {
    skills?: Skill[];
    recentSkills?: string[];
    onExecute?: (skillId: string) => void;
  }
  
  let {
    skills = [],
    recentSkills = [],
    onExecute,
  }: Props = $props();
  
  const groupedSkills = $derived(() => {
    const groups: Record<string, Skill[]> = {};
    for (const skill of skills) {
      if (!groups[skill.category]) groups[skill.category] = [];
      groups[skill.category].push(skill);
    }
    return groups;
  });
  
  const recent = $derived(
    recentSkills
      .map(id => skills.find(s => s.id === id))
      .filter(Boolean)
      .slice(0, 3)
  );
</script>

<div class="skills-block">
  <div class="header">
    <span>🛠️ Skills</span>
  </div>
  
  {#if recent.length > 0}
    <div class="recent">
      <span class="label">Recent:</span>
      {#each recent as skill}
        <button class="skill-chip" onclick={() => onExecute?.(skill.id)}>
          {skill.name}
        </button>
      {/each}
    </div>
  {/if}
  
  <div class="categories">
    {#each Object.entries(groupedSkills()) as [category, categorySkills]}
      <div class="category">
        <div class="category-name">{category}</div>
        {#each categorySkills as skill}
          <button 
            class="skill-row"
            onclick={() => onExecute?.(skill.id)}
            title={skill.description}
          >
            <span class="shortcut">{skill.shortcut}</span>
            <span class="name">{skill.name}</span>
          </button>
        {/each}
      </div>
    {/each}
  </div>
</div>
```

---

## Success Criteria

### Core Experience
1. **`sunwell .` works** — Opens project in Studio with correct lens
2. **Toggle works** — ⌘P switches source ↔ preview instantly
3. **Selection → action works** — Select in either view, get action menu
4. **Validation runs live** — Type marketing word → see warning in <500ms
5. **Diataxis detected** — Status bar shows content type
6. **Lens auto-selected** — Docs project → tech-writer lens applied automatically
7. **Click warning → jump** — Navigate to issue in source view

### Autonomous Workflows (Key Differentiator)
8. **Natural language → workflow** — "Audit and fix this" triggers multi-step chain
9. **Workflow progress visible** — WorkflowPanel shows step progress
10. **Checkpoints work** — User can pause, skip step, or stop mid-chain
11. **State persists** — Close Sunwell, reopen, `sunwell resume` continues
12. **Pre-built workflows accessible** — `feature-docs`, `health-check`, `quick-fix` from UI
13. **Error recovery** — Failed step offers retry/skip/stop options

### Autonomy Feel
14. **7 prompts → 1 prompt** — Complex tasks (audit + fix + polish) complete with single request
15. **Transparent execution** — User sees what's happening at each step
16. **Interruptible** — User can always stop; completed work is preserved

---

## Competitive Analysis

How Sunwell compares to existing tools — not just for docs, but as a universal writing environment.

### The Landscape (2026)

| Tool | Philosophy | Target User | Domain Scope |
|------|------------|-------------|--------------|
| **VS Code + Copilot** | Traditional IDE with AI bolted on | Developers who want stability | Code only |
| **Cursor** | "Vibe coding" — AI rewrites, multi-file agents | Developers who embrace AI | Code only |
| **Antigravity** (Google) | Agent-first — autonomous agents with browser/terminal | Developers comfortable with high autonomy | Code only |
| **Kiro** (AWS) | Spec-driven — requirements → design → tasks | Teams wanting structure | Code + specs |
| **Notion AI** | Docs/wiki with AI features | Teams, knowledge workers | Docs, notes |
| **Scrivener** | Long-form writing tool | Novelists, academics | Fiction, research |
| **Sunwell** | **Lens-powered universal writing** | **Anyone who writes** | **Any domain via lenses** |

### The Key Insight

Every other tool is built for **one domain**:
- VS Code / Cursor / Antigravity / Kiro → **Code**
- Notion → **Team docs/wiki**
- Scrivener → **Long-form fiction**

Sunwell is built for **writing itself**, with domain expertise provided by lenses:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUNWELL                                        │
│                                                                             │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────┐  │
│   │ tech-     │  │ pm.lens   │  │ novelist. │  │ coder.    │  │ qa.lens │  │
│   │ writer    │  │           │  │ lens      │  │ lens      │  │         │  │
│   │ .lens     │  │           │  │           │  │           │  │         │  │
│   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬────┘  │
│         │              │              │              │              │       │
│         └──────────────┴──────────────┴──────────────┴──────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│                    ┌────────────────────────────────┐                       │
│                    │   Unified Writing Surface      │                       │
│                    │   + Autonomous Workflows       │                       │
│                    │   + Domain Expertise           │                       │
│                    └────────────────────────────────┘                       │
│                                                                             │
│                    "One tool. Any domain. Your expertise."                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Feature Comparison

| Feature | VS Code | Cursor | Antigravity | Kiro | **Sunwell** |
|---------|---------|--------|-------------|------|-------------|
| **Primary focus** | Code | Code | Code | Code | **Writing** |
| **Live preview** | Extension | Limited | Browser pane | Limited | **Toggle (⌘P)** |
| **Domain expertise** | None | None | None | Specs only | **Lenses** (Diataxis, heuristics) |
| **Autonomous workflows** | None | Tab/Agent | Full agents | Specs → tasks | **Lens skill chains** ⭐ |
| **Workflow checkpoints** | None | None | None | None | **Pause/resume chains** |
| **State persistence** | None | None | None | Spec files | **`.sunwell/state/`** |
| **Style feedback** | Linters | None | None | None | **Real-time validators** |
| **Selection → action** | Right-click | Chat | Agent tasks | Chat | **Universal (any view)** |
| **Content type awareness** | None | None | None | None | **Diataxis detection** |
| **Split/toggle view** | Split | Split | Split | Split | **Toggle** (simpler) |
| **Personas testing** | None | None | None | None | **4 personas** in lens |

### Where Others Fall Short for Writers

**VS Code + Copilot**
```
❌ AI is an add-on, not native
❌ No writing-specific feedback
❌ Preview requires extension setup
❌ No style guide integration
```

**Cursor**
```
✅ Excellent AI integration
❌ Code-centric — "vibe coding" not "vibe writing"
❌ No Diataxis awareness
❌ Selection only works in editor, not preview
❌ No domain expertise (lenses)
```

**Antigravity (Google)**
```
✅ Powerful autonomous agents
❌ Too much autonomy for docs (risk of unintended edits)
❌ Security concerns (agents can delete files)
❌ Overwhelming complexity for writing tasks
❌ Code-first, docs-second
```

**Kiro (AWS)**
```
✅ Spec-driven structure
❌ Performance issues reported
❌ Missing features (Python intellisense gaps)
❌ Specs are for code, not prose
❌ UI/UX rough spots
```

### Sunwell's Differentiation

| What Others Do | What Sunwell Does |
|----------------|-------------------|
| One prompt → one action | **One prompt → multi-step workflow** (chains 5+ skills) |
| AI suggests code completions | AI suggests **with lens expertise** (Diataxis, style guide) |
| Split view (cramped) | **Toggle view** (100% focus) |
| Actions only in source | **Actions work in preview too** |
| Generic assistance | **Domain-specific feedback** (marketing fluff detection, front-loading) |
| Learn your codebase | **Apply proven frameworks** (730 lines of tech-writer expertise) |
| Full autonomy or manual | **Checkpointed autonomy** with explicit control points |
| Lose state on close | **Persistent workflow state** — resume where you left off |

### Risk: Why Not Just Use Cursor?

Cursor is excellent for developers. But for technical writers:

```
Cursor:
  "Here's some code completions"
  "I rewrote your function"
  "Want me to refactor this file?"
  
Sunwell:
  "⚠️ This looks like marketing language ('powerful API')"
  "📑 Detected: TUTORIAL — structure looks good"
  "💡 Consider front-loading: key info should be in first paragraph"
  "Select any text → [Improve with style guide]"
```

Cursor doesn't know Diataxis. Cursor doesn't have heuristics for technical writing. Cursor can't tell you your HOW-TO guide accidentally became a TUTORIAL.

### What We're NOT Competing On

| Feature | Skip | Why |
|---------|------|-----|
| Unbounded agent autonomy | ✅ | Writers need checkpointed control, not surprises |
| Browser/terminal integration | ✅ | Writing doesn't need browser automation |
| Code execution/debugging | ✅ | Writing produces text, not executables |
| Complex split layouts | ✅ | Toggle view is simpler and sufficient |
| Extension marketplace | ✅ | Lens ecosystem replaces extensions |
| Domain-specific rendering | ✅ | Focus on editing, not final rendering |

### Positioning Statement

> **Sunwell is not a code editor that also does docs.**
> **Sunwell is not a docs tool that can't do code.**
>
> **Sunwell is an S-tier AI-native writing environment where lenses provide infinite domain expertise.**
>
> - Swap in `tech-writer.lens` → you have Diataxis, style guides, evidence-based validation
> - Swap in `novelist.lens` → you have Three-Act Structure, scene conflict checks, pacing analysis
> - Swap in `pm.lens` → you have PRFAQ templates, metrics validation, prioritization frameworks
> - Swap in `coder.lens` → you have type contracts, architecture patterns, RFC workflows
>
> **Same surface. Same autonomous workflows. Different expertise.**
>
> While others build tools for one domain, Sunwell builds a tool for **writing itself** — and lets lenses handle the rest.

---

## Open Questions

### Resolved ✅

1. ~~**Validation performance** — Should heuristic validators (LLM-based) run on every keystroke or only on save/explicit request?~~
   - ✅ **Resolved**: Deterministic on keystroke (debounced 300ms); heuristic on save only. See "Performance Budgets" section.

2. ~~**Workflow engine approach** — Procedural vs event-driven vs actor model?~~
   - ✅ **Resolved**: Procedural engine selected. See "Workflow Engine Design Alternatives" section.

3. ~~**State persistence format** — How is workflow state stored and branch-isolated?~~
   - ✅ **Resolved**: JSON files in `.sunwell/state/{branch}/`. See expanded "State Persistence" section.

### Open (Need Decision)

4. **Selection in preview** — How to map preview selection back to source lines?
   - *Proposed*: Track source→rendered mapping via markdown AST with source positions; fallback to nearest heading anchor
   - *Alternative*: Preview selection creates a "fuzzy" range that matches text content, not exact lines
   - **Decision needed**: Which approach? Fuzzy is simpler but less precise.

5. **Lens override UI** — How does user switch from auto-detected lens to another?
   - *Proposed*: Dropdown in status bar (like VS Code language selector)
   - **Status**: Approved, straightforward implementation

6. **View mode persistence** — Remember last view mode per file?
   - *Proposed*: Yes, stored in `.sunwell/config.yaml` under `view_preferences`
   - **Status**: Approved, low complexity

### Lens Ecosystem (Deferred to v2)

7. **Community lenses** — How do users share/discover lenses?
   - *Proposed*: `sunwell lens install novelist` from registry, or drop YAML in `.sunwell/lenses/`
   - **Status**: Deferred — v1 ships with built-in lenses only

8. **Lens composition** — Can you combine lenses? (e.g., `tech-writer` + `nvidia-style`)
   - *Proposed*: Yes, lenses can `extend:` other lenses; conflicts resolved by priority
   - **Status**: Deferred — requires lens schema versioning work

7. **Lens versioning** — How do we handle lens updates without breaking workflows?
   - *Proposed*: Lenses have `version:` field; `.sunwell/config.yaml` can pin versions

8. **Domain detection** — How accurate is auto-detection, and what's the fallback?
   - *Proposed*: Use file markers (mkdocs.yml → tech-writer, novel.md → novelist); fallback to prompt user

---

## Related RFCs

- **RFC-070**: Lens System — Defines lens structure (skills, heuristics, validators)
- **RFC-072**: Surface Primitives — ProseEditor, Preview, Outline definitions
- **RFC-080**: Unified Home Surface — Block system
- **RFC-082**: Fluid Canvas UI — Page/canvas area model
- **RFC-078**: Primitive & Provider Roadmap — Preview primitive (now complete)

---

## Appendix: Tech Writer Lens Integration Points

From `lenses/tech-writer.lens`:

### Skills to Surface

```yaml
shortcuts:
  "::a": "audit-documentation"
  "::a-2": "audit-documentation-deep"
  "::p": "polish-documentation"
  "::m": "modularize-content"
  "::health": "check-health"
  "::md": "fix-markdown-syntax"
  "::fm": "generate-frontmatter"
  "::overview": "create-overview-page"
  "::score": "score-confidence"
  "::style": "apply-style-guide"
```

### Validators to Run

```yaml
deterministic:
  - no_marketing_fluff  # grep for trigger words

heuristic:
  - signal_to_noise     # Every sentence adds value
  - evidence_required   # Claims have file:line refs
  - front_loaded        # Important info first
  - active_voice        # Prefer active voice
  - diataxis_purity     # Single content type
```

### Heuristics to Display

```yaml
principles:
  - Signal over Noise (priority: 10)
  - Diataxis Purity (priority: 9)
  - PACE Communication (priority: 8)
  - Evidence Standards (priority: 8)
  - Progressive Disclosure (priority: 8)
  - Audience Awareness (priority: 7)
  - UX Pattern Detection (priority: 6)
```
