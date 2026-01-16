# DORI → Sunwell Extraction Plan

**Goal**: Full parity with DORI for technical writing in Sunwell.

---

## The Classification Framework

**Core Question**: Does this tell the LLM *how to think* or *how to do*?

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DECISION FRAMEWORK                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  "How should I think about this?"  →  LENS (Heuristics/Validators)  │
│  ─────────────────────────────────────────────────────────────────  │
│  • Quality principles (signal-to-noise)                             │
│  • Judgment criteria (what makes good docs)                         │
│  • Evaluation rubrics (confidence scoring)                          │
│  • Perspective shifts (personas)                                    │
│  • Methodology frameworks (Diataxis)                                │
│                                                                      │
│  "How do I execute this task?"    →  SKILL (Instructions/Scripts)   │
│  ─────────────────────────────────────────────────────────────────  │
│  • Step-by-step procedures                                          │
│  • File templates                                                   │
│  • Python scripts (deterministic checks)                            │
│  • Transformation operations                                        │
│  • Output formats                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Quick Classification Test

| Question | If YES → | If NO → |
|----------|----------|---------|
| Does it define what "good" means? | Lens | — |
| Does it provide evaluation criteria? | Lens | — |
| Does it shift perspective/persona? | Lens | — |
| Does it have step-by-step instructions? | Skill | — |
| Does it include executable scripts? | Skill | — |
| Does it produce a specific artifact? | Skill | — |
| Does it transform input → output? | Skill | — |

### Hybrid Components

Some DORI rules are **hybrid** — they contain both judgment and action:

| DORI Rule | Lens Part | Skill Part |
|-----------|-----------|------------|
| `docs-audit` | Triangulation protocol, confidence rubric | Python scripts (validate_code_blocks.py) |
| `docs-writing-workflow` | Quality gates, Diataxis alignment | Step-by-step procedure, output template |
| `docs-polish` | Signal-to-noise assessment | Transformation instructions |

**Strategy**: Extract judgment into lens, package action into skill, wire them together.

---

## DORI → Sunwell Mapping

### Already in Sunwell Lens (tech-writer.lens)

| DORI Component | Sunwell Location | Status |
|----------------|------------------|--------|
| `modules/docs-quality-principles` | `heuristics.principles` | ✅ Done |
| `modules/diataxis-framework` | `framework` | ✅ Done |
| `personas/*` (4 personas) | `personas` | ✅ Done |
| `modules/evidence-handling` | `provenance` | ✅ Done |
| `router` (tiered execution) | `router` | ✅ Done |
| Heuristic validators | `validators.heuristic` | ✅ Done |

### Needs Extraction → Lens Components

| DORI Component | Extract To | Priority |
|----------------|------------|----------|
| `modules/docs-communication-style` | `heuristics.communication` | P1 |
| `modules/docs-output-format` | `heuristics.output_format` | P1 |
| `modules/validation-patterns` | `validators.heuristic` | P1 |
| `modules/docs-ux-patterns` | `heuristics.ux_patterns` | P2 |
| `docs-orchestrator` (cognitive routing) | `router` enhancements | P2 |
| `docs-confidence-scoring` | `validators.confidence` | P2 |

### Needs Extraction → Skills

| DORI Component | Skill Name | Type | Priority |
|----------------|------------|------|----------|
| **Deterministic Scripts** | | | |
| `validate_code_blocks.py` | `validate_syntax` | script | P1 |
| `detect_drift.py` | `detect_drift` | script | P1 |
| `verify_docs.py` | `verify_docs` | script | P1 |
| `check_health.py` | `check_health` | script | P1 |
| `track_doc_coverage.py` | `track_coverage` | script | P2 |
| `find_orphans.py` | `find_orphans` | script | P2 |
| `enforce_frontmatter.py` | `enforce_frontmatter` | script | P2 |
| **Workflows** | | | |
| `docs-writing-workflow` | `write_docs` | instructions | P1 |
| `docs-pipeline` | `docs_pipeline` | instructions | P1 |
| `docs-audit` | `audit_docs` | hybrid | P1 |
| `docs-polish` | `polish_docs` | instructions | P1 |
| **Transformations** | | | |
| `docs-modularize-content` | `modularize` | instructions | P2 |
| `docs-frontmatter` | `generate_frontmatter` | instructions | P2 |
| `docs-map-maker` | `build_nav_map` | instructions | P2 |
| **Content Templates** | | | |
| `docs-content-overview-page` | `create_overview` | template | P1 |
| `docs-content-architecture-page` | `create_architecture` | template | P2 |
| `docs-content-ecosystem-page` | `create_ecosystem` | template | P2 |
| `docs-content-key-features-page` | `create_features` | template | P2 |
| `docs-draft` | `draft_from_code` | instructions | P1 |
| **Utilities** | | | |
| `docs-md-syntax` | `fix_md_syntax` | instructions | P2 |
| `docs-rst-syntax` | `fix_rst_syntax` | instructions | P2 |
| `docs-style-guide` | `apply_style_guide` | instructions | P2 |

---

## Phase 1: Core Parity (Dogfood Target)

**Goal**: Replace DORI for daily technical writing tasks.

### Lens Enhancements

```yaml
# Add to tech-writer.lens

heuristics:
  # ... existing ...
  
  communication:
    tone: [Professional, Active, Conversational, Engaging]  # PACE
    structure: "Conclusion first, details later"
    accessibility:
      - "Use they/their for pronouns"
      - "Avoid directional language (above/below)"
      - "Provide alt text for images"
  
  output_format:
    structure: |
      ## [Emoji] [Title]
      **Summary**: [2-3 sentences]
      **Status**: [Overall] | **Confidence**: [N]% [🟢🟡🟠🔴]
      ### [Main Sections]
      ### 📋 Action Items
    indicators:
      status: ["✅ Verified", "⚠️ Warning", "❌ Error"]
      confidence: ["🟢 High (90-100%)", "🟡 Moderate (70-89%)", "🟠 Low (50-69%)", "🔴 Uncertain (0-49%)"]
```

### Skills to Implement

```yaml
skills:
  # --- VALIDATION ---
  - name: validate_syntax
    type: inline
    description: "Check Python code blocks for syntax errors"
    instructions: |
      Run syntax validation on documentation files.
      Reports errors with file:line references.
    scripts:
      - name: validate_code_blocks.py
        language: python
        content: |
          # Port from prompt-library/scripts/doc-utils/validate_code_blocks.py
          ...
    validate_with:
      validators: [code_accuracy]
      min_confidence: 0.9

  - name: detect_drift
    type: inline
    description: "Find docs that are stale relative to referenced code"
    scripts:
      - name: detect_drift.py
        language: python
        content: |
          # Port from prompt-library/scripts/doc-utils/detect_drift.py
          ...

  - name: audit_docs
    type: inline
    description: "Comprehensive documentation audit with triangulation"
    instructions: |
      ## Quick Audit Process
      1. Identify document type (API, guide, tutorial, reference)
      2. List 5-10 most important technical claims
      3. Run deterministic checks (syntax, readability, links)
      4. Quick source verification for key claims
      5. Assign status: ✅ Verified | ⚠️ Suspicious | ❌ Wrong | ❓ Can't verify
      
      ## Triangulation Protocol
      For conceptual claims, check 3 independent sources:
      - Source Path: Find implementing code
      - Test Path: Find integration test
      - Schema Path: Find config/API schema
      
      ## Output Format
      ```markdown
      ## 🔍 Audit: [File]
      
      ### 🤖 Deterministic Checks
      - **Syntax**: ✅/❌
      - **Readability**: Score/100
      - **Links**: ✅/❌
      - **Freshness**: Fresh/Stale
      
      ### Key Claims
      - ✅ [Claim] - `file:line`
      - ⚠️ [Claim] - [issue]
      
      ### 📋 Action Items
      - [ ] [Fix]
      ```
    validate_with:
      validators: [evidence_required]
      personas: [skeptic]

  # --- CONTENT CREATION ---
  - name: write_docs
    type: inline
    description: "Systematic workflow for creating documentation"
    instructions: |
      ## Step 0: Classify Content Type
      Ask: "What is the user trying to DO?"
      - Learn by doing → TUTORIAL
      - Accomplish task → HOW-TO
      - Understand concepts → EXPLANATION
      - Look up info → REFERENCE
      
      ## Step 1: Scope and Plan
      - [ ] Diataxis type identified
      - [ ] User goal defined
      - [ ] Expected outcome stated
      - [ ] Target audience identified
      
      ## Step 2: Apply Progressive Disclosure
      Layer 1 (30s): What, who, key value
      Layer 2 (3-5min): Main concepts, common use cases
      Layer 3 (10+min): Advanced features, edge cases
      Layer 4 (as needed): Complete reference
      
      ## Step 3: Draft with Quality Principles
      - [ ] High signal-to-noise (no fluff)
      - [ ] Concrete examples with code
      - [ ] Evidence (file:line references)
      - [ ] Cross-links to related content
      
      ## Step 4: Format
      - Convert numbered parallel headers to tab sets
      - Convert advanced sections to dropdowns
      - Add reference targets for cross-linking
      
      ## Step 5: Validate
      Run audit_docs skill
    validate_with:
      validators: [no_marketing_fluff, evidence_required, front_loaded]
      personas: [novice, pragmatist]
      min_confidence: 0.7

  - name: draft_from_code
    type: inline
    description: "Evidence-first documentation from source code"
    instructions: |
      ## Evidence-First Drafting
      
      🛑 **Critical Rule: No Read = No Write**
      
      You are FORBIDDEN from generating a code block unless you have 
      read the file containing that code in this conversation.
      
      ## Process
      1. **Skeleton First**: Write prose, leave code as TODO comments
         `<!-- TODO: Insert code for 'init()' from src/core.py -->`
      
      2. **Filler Pass**: Read file, replace TODO with exact code
      
      3. **Section Pruning**: If section has no evidence:
         - Option A: Delete section
         - Option B: Mark as `> ⚠️ TODO: SME input required`
         - Never: Invent plausible text
      
      ## Output
      - Only verified claims
      - TODOs for gaps
      - Strip evidence trails before publication

  # --- TRANSFORMATION ---
  - name: polish_docs
    type: inline
    description: "Quick polish for clarity and style"
    instructions: |
      ## Polish Process
      
      ### 1. Assess Current State
      - Signal-to-noise: [High/Medium/Low]
      - Diataxis alignment: [Clear/Mixed/Unclear]
      - Progressive disclosure: [Layered/Flat]
      
      ### 2. Improve Signal-to-Noise
      - Remove fluff words (robust, powerful, flexible)
      - Add concrete examples
      - Add file:line evidence
      - Front-load key information
      
      ### 3. Improve Diataxis Alignment
      - Clarify content type
      - Add cross-links
      - Split if mixed types
      
      ### 4. Apply UX Patterns
      - Numbered examples → tab sets
      - Before/After → tab sets
      - Advanced sections → dropdowns
      
      ### Output
      ```markdown
      ## 🎨 Polish Complete
      
      ### Improvements
      - Removed [N] fluff instances
      - Added [N] examples
      - Converted [N] to tab sets
      
      ### Quality: [N/10] → [M/10]
      ```

  # --- CONTENT TEMPLATES ---
  - name: create_overview
    type: inline
    description: "Create product/platform overview page"
    instructions: |
      ## Overview Page Structure (EXPLANATION type)
      
      ### Required Sections
      1. **Opening Hook** (Layer 1)
         - One sentence: what it is
         - One sentence: who it's for
         - Key value proposition
      
      2. **Key Capabilities** (Layer 2)
         - 3-5 bullet points
         - Concrete, not abstract
      
      3. **How It Works** (Layer 2)
         - Brief conceptual explanation
         - Diagram if helpful
      
      4. **Getting Started** (Navigation)
         - Link to tutorial
         - Link to quickstart
      
      5. **Learn More** (Navigation)
         - Link to architecture
         - Link to reference
    templates:
      - name: overview.md
        content: |
          # ${ProductName}
          
          ${ProductName} is [one sentence description].
          
          **Built for**: [target audience]
          
          ## Key Capabilities
          
          - **[Capability 1]**: [Concrete benefit]
          - **[Capability 2]**: [Concrete benefit]
          - **[Capability 3]**: [Concrete benefit]
          
          ## How It Works
          
          [Brief conceptual explanation]
          
          ## Get Started
          
          ::::{grid} 2
          :gutter: 3
          
          :::{grid-item-card} Tutorial
          :link: tutorial
          Learn by building [something concrete]
          :::
          
          :::{grid-item-card} Quickstart
          :link: quickstart
          Get running in 5 minutes
          :::
          
          ::::
          
          ## Learn More
          
          - [Architecture](architecture) — How ${ProductName} works internally
          - [Reference](reference) — Complete API documentation
```

---

## Phase 2: Advanced Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Persona simulation | Run output through novice/skeptic/pragmatist/expert | P1 |
| Confidence scoring | Quantified uncertainty per claim | P2 |
| Pipeline state | Multi-session workflows with checkpoints | P2 |
| Content templates | Architecture, ecosystem, key-features pages | P2 |

---

## Dogfooding Plan

### Week 1: Core Skills
1. Port deterministic scripts (validate_syntax, detect_drift)
2. Implement audit_docs skill
3. Implement write_docs skill
4. Test on Sunwell's own docs

### Week 2: Content Creation
1. Implement draft_from_code skill
2. Implement create_overview template
3. Implement polish_docs skill
4. Document Sunwell using Sunwell

### Week 3: Validation Loop
1. Run personas on generated docs
2. Compare output quality to DORI
3. Iterate on heuristics based on failures
4. Measure token usage vs DORI

### Success Metrics

| Metric | Target |
|--------|--------|
| DORI commands covered | 100% of ::a, ::p, ::w, ::m |
| Token usage | ≤ DORI equivalent |
| Output quality (blind eval) | ≥ DORI equivalent |
| Dogfood coverage | All Sunwell docs created with Sunwell |

---

## Files to Create

```
sunwell/
├── lenses/
│   └── tech-writer.lens          # Enhanced with output_format, ux_patterns
├── skills/
│   ├── validation/
│   │   ├── validate_syntax/
│   │   │   └── validate_code_blocks.py
│   │   ├── detect_drift/
│   │   │   └── detect_drift.py
│   │   └── audit_docs/
│   │       └── SKILL.md
│   ├── creation/
│   │   ├── write_docs/
│   │   │   └── SKILL.md
│   │   ├── draft_from_code/
│   │   │   └── SKILL.md
│   │   └── create_overview/
│   │       ├── SKILL.md
│   │       └── templates/
│   │           └── overview.md
│   └── transformation/
│       └── polish_docs/
│           └── SKILL.md
└── src/
    └── sunwell/
        └── skills/
            ├── __init__.py
            ├── executor.py       # From RFC-011
            └── sandbox.py        # From RFC-011
```

---

## Next Actions

1. [ ] Enhance `tech-writer.lens` with communication/output_format heuristics
2. [ ] Port `validate_code_blocks.py` as first skill
3. [ ] Port `detect_drift.py` as second skill
4. [ ] Implement `audit_docs` skill with triangulation
5. [ ] Test on `sunwell/docs/` directory
6. [ ] Compare results to running DORI on same docs
