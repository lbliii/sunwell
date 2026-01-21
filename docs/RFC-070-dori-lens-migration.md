# RFC-070: DORI Lens Migration — Technical Writing Expertise for Sunwell

**Status**: Implemented ✅  
**Created**: 2026-01-21  
**Completed**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 95% 🟢  
**Depends on**: RFC-011 (Agent Skills), RFC-030 (Unified Router)

---

## Summary

Port the complete DORI documentation framework (59 rules) to Sunwell as a "Technical Writer" lens with integrated skills, demonstrating how Sunwell's architecture improves upon Cursor-specific rules with:

1. **Judgment + Action** — Heuristics guide thinking, skills execute procedures
2. **Automatic Routing** — Router suggests relevant skills based on intent
3. **Validation Integration** — Skills bind to validators and personas
4. **Portable Format** — Agent Skills YAML works across agent platforms

**The pitch**: DORI's documentation expertise, supercharged by Sunwell's coordinated intelligence.

---

## Background

### What is DORI?

DORI (Documentation Operating Research Intelligence) is a rule-based documentation framework with 59 `.mdc` rules that provide:

- **Quality principles** — Signal-to-noise, Diataxis alignment, progressive disclosure
- **Validation procedures** — Audit docs against source code with confidence scoring
- **Content creation** — Specialized templates for overviews, architecture, tutorials
- **Adversarial testing** — Personas that stress-test documentation
- **Orchestration** — Intelligent routing to the right rule based on intent

### The Problem with .mdc Rules

1. **Cursor-specific** — Only works in Cursor IDE
2. **No action capability** — Rules are instructions, not executable
3. **Flat structure** — No distinction between judgment and procedure
4. **Manual routing** — User must know which rule to invoke
5. **No validation integration** — Rules don't verify their own output

### The Sunwell Advantage

| DORI Limitation | Sunwell Solution |
|-----------------|------------------|
| Cursor-only | Agent Skills YAML (portable) |
| Instructions-only | Skills with scripts, templates, tools |
| Flat rules | Heuristics (think) + Skills (do) |
| Manual routing | Router with skill triggers |
| No validation | `validate_with` binds skills to validators |
| No memory | Simulacrum remembers decisions |
| Single model | Naaru coordination (Voice + Wisdom) |

---

## Goals

1. **Complete migration** — All 59 DORI rules → Sunwell lens + skills
2. **Improved architecture** — Clear separation of judgment vs. action
3. **Automatic skill routing** — Router suggests skills based on intent
4. **Validation integration** — Every skill specifies its quality gates
5. **Portable format** — Export to Agent Skills for other platforms
6. **CI/CD ready** — Foundation for "Docs Rabbit" PR reviewer

## Non-Goals

1. **UI changes** — Studio integration is future work
2. **Backward compatibility** — Fresh implementation, not shim layer
3. **All NVIDIA-specific rules** — Focus on portable core; NVIDIA extensions separate

---

## Detailed Design

### Part 1: Rule Classification

#### 1.1 DORI Rules → Sunwell Components

| DORI Category | Count | Sunwell Type | Purpose |
|---------------|-------|--------------|---------|
| `modules/` | 8 | **Heuristics** | How to think |
| `personas/` | 5 | **Personas** | Adversarial testing |
| `validation/` | 9 | **Skills** | Checking procedures |
| `transformation/` | 5 | **Skills** | Change procedures |
| `content/` | 5 | **Skills** | Creation procedures |
| `workflows/` | 5 | **Workflows** | Multi-step chains |
| `commands/` | 8 | **Skills** (aliases) | User shortcuts |
| `utilities/` | 10 | **Skills** | Helper procedures |
| `system/` | 4 | **Router** | Orchestration |
| **Total** | **59** | — | — |

#### 1.2 Migration Mapping

```yaml
# modules/ → heuristics
modules/docs-quality-principles → heuristic: signal-to-noise, diataxis-scoping, progressive-disclosure
modules/diataxis-framework → framework: diataxis
modules/docs-communication-style → heuristic: communication-style
modules/evidence-handling → heuristic: evidence-standards
modules/docs-ux-patterns → heuristic: ux-patterns
modules/docs-output-format → heuristic: output-formatting
modules/validation-patterns → heuristic: validation-scoring
modules/execution-patterns → heuristic: execution-patterns

# personas/ → personas
personas/persona-novice → persona: novice
personas/persona-skeptic → persona: skeptic
personas/persona-pragmatist → persona: pragmatist
personas/persona-expert → persona: expert
docs-personas → persona: audience-definitions

# validation/ → skills
validation/docs-audit → skill: audit-documentation
validation/docs-audit-enhanced → skill: audit-documentation-deep
validation/docs-confidence-scoring → skill: score-confidence
validation/docs-drift → skill: detect-drift
validation/docs-health → skill: check-health
validation/docs-readability-checker → skill: check-readability
validation/docs-structural-lint → skill: lint-structure
validation/docs-vdr-assessment → skill: assess-vdr
validation/docs-code-example-audit → skill: audit-code-examples

# transformation/ → skills
transformation/docs-polish → skill: polish-documentation
transformation/docs-modularize-content → skill: modularize-content
transformation/docs-frontmatter → skill: generate-frontmatter
transformation/docs-map-maker → skill: generate-navigation-map
transformation/docs-migration-fern-gap-analysis → skill: analyze-fern-migration

# content/ → skills
content/docs-draft → skill: draft-documentation
content/docs-content-overview-page → skill: create-overview-page
content/docs-content-architecture-page → skill: create-architecture-page
content/docs-content-ecosystem-page → skill: create-ecosystem-page
content/docs-content-key-features-page → skill: create-features-page

# workflows/ → workflows
workflows/docs-writing-workflow → workflow: writing-pipeline
workflows/docs-pipeline → workflow: research-draft-verify
workflows/docs-chain-executor → workflow: custom-chain
workflows/docs-reflexion → workflow: reflexion-loop
workflows/docs-workflow-templates → workflow: templates

# utilities/ → skills
utilities/docs-style-guide → skill: apply-style-guide
utilities/docs-md-syntax → skill: fix-markdown-syntax
utilities/docs-rst-syntax → skill: fix-rst-syntax
utilities/docs-bump-version → skill: bump-version
utilities/docs-atomic-commits → skill: format-commit-message
utilities/docs-bootstrap-sphinx → skill: bootstrap-sphinx
utilities/docs-dir-index-format → skill: format-index-page
utilities/docs-assist-merge-conflict-resolution → skill: resolve-merge-conflict
utilities/docs-retro → skill: run-retrospective
utilities/docs-task-management → skill: manage-tasks

# system/ → router
system/docs-os → router: command-shortcuts
system/docs-orchestrator → router: intent-routing
system/docs-context-analyzer → router: context-analysis
system/docs-help-system → skill: show-help
```

### Part 2: Skill Triggers (New Feature)

#### 2.1 The Problem

Currently, skills are manually invoked. The router picks lenses, but doesn't suggest skills.

#### 2.2 The Solution: Skill Triggers

Add `triggers` field to skills for automatic discovery:

```python
# src/sunwell/skills/types.py

@dataclass(frozen=True, slots=True)
class Skill:
    """An agent skill that provides action capabilities."""
    
    name: str
    description: str
    skill_type: SkillType
    
    # NEW: Trigger patterns for automatic discovery
    triggers: tuple[str, ...] = ()
    """Keywords/patterns that suggest this skill.
    
    When router analyzes intent, it matches against skill triggers
    to suggest relevant skills alongside lens selection.
    
    Example: triggers: ("audit", "validate", "check", "verify")
    """
    
    # Existing fields...
    instructions: str | None = None
    allowed_tools: tuple[str, ...] = ()
    validate_with: SkillValidation = field(default_factory=SkillValidation)
```

#### 2.3 Router Integration

Extend `UnifiedRouter` to include skill suggestions:

```python
# src/sunwell/routing/unified.py

@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Result of unified routing."""
    
    intent: Intent
    complexity: Complexity
    lens: str | None
    tools: tuple[str, ...]
    mood: Mood
    expertise: Expertise
    confidence: float
    reasoning: str
    
    # NEW: Skill suggestions
    suggested_skills: tuple[str, ...] = ()
    """Skills whose triggers match the input."""
    
    skill_confidence: float = 0.0
    """Confidence in skill suggestions (0.0-1.0)."""


class UnifiedRouter:
    """RFC-030 unified router with skill discovery."""
    
    async def route(
        self,
        input_text: str,
        context: dict[str, Any] | None = None,
        lens: Lens | None = None,
    ) -> RoutingDecision:
        """Route input to lens and suggest relevant skills."""
        
        # Existing routing logic...
        decision = await self._route_to_lens(input_text, context)
        
        # NEW: Match skill triggers
        if lens and lens.skills:
            suggested = self._match_skill_triggers(input_text, lens.skills)
            decision = dataclasses.replace(
                decision,
                suggested_skills=suggested,
                skill_confidence=self._compute_skill_confidence(suggested, input_text),
            )
        
        return decision
    
    def _match_skill_triggers(
        self,
        input_text: str,
        skills: tuple[Skill, ...],
    ) -> tuple[str, ...]:
        """Find skills whose triggers match the input."""
        input_lower = input_text.lower()
        matches = []
        
        for skill in skills:
            if any(trigger in input_lower for trigger in skill.triggers):
                matches.append(skill.name)
        
        return tuple(matches)
```

### Part 3: Lens Structure

#### 3.1 File Organization

```
sunwell/
├── lenses/
│   ├── tech-writer.lens              # Main lens definition
│   └── tech-writer-nvidia.lens       # NVIDIA-specific extensions
│
├── skills/
│   ├── docs-core-skills.yaml         # Shared documentation skills
│   ├── docs-validation-skills.yaml   # Audit, drift, health checks
│   ├── docs-creation-skills.yaml     # Draft, overview, architecture
│   ├── docs-transformation-skills.yaml # Polish, modularize, frontmatter
│   └── docs-utility-skills.yaml      # Syntax fixes, version bumps
```

#### 3.2 Main Lens: `tech-writer.lens`

```yaml
lens:
  metadata:
    name: "Technical Writer"
    domain: "documentation"
    version: "2.0.0"
    description: "Complete technical writing expertise with Diataxis, validation, and CI/CD support"
    author: "Sunwell Team"
    license: "MIT"
    compatible_schemas: []  # Universal

  # ==========================================================================
  # HEURISTICS — How to Think
  # ==========================================================================
  
  heuristics:
    principles:
      # From modules/docs-quality-principles
      - name: "Signal over Noise"
        rule: "Every sentence must earn its place"
        test: "Would the user lose information if this was removed?"
        always:
          - "Front-load the most important information"
          - "Use concrete examples with real code"
          - "Provide file:line references for claims"
          - "Use active voice"
        never:
          - "Marketing language (powerful, flexible, easy, robust)"
          - "Vague qualifiers (many, various, different)"
          - "Theoretical advice without evidence"
          - "Passive voice when active works"
        priority: 10

      # From modules/diataxis-framework
      - name: "Diataxis Purity"
        rule: "Every page fits one Diataxis quadrant"
        test: "Does this page have a single clear purpose?"
        always:
          - "Identify content type before writing"
          - "Match structure to type (tutorial/how-to/explanation/reference)"
          - "Cross-link to related content types"
        never:
          - "Mix tutorial steps with API reference tables"
          - "Explain concepts in how-to guides"
          - "Include step-by-step in explanations"
        priority: 9

      # From modules/docs-communication-style
      - name: "PACE Communication"
        rule: "Professional, Active, Conversational, Engaging"
        always:
          - "Start with conclusion (inverted pyramid)"
          - "Use specific examples with evidence"
          - "Keep sentences short and scannable"
        never:
          - "Academic tone (upon conducting, comprehensive evaluation)"
          - "Casual tone (Hey! So I found...)"
          - "Dense paragraphs without structure"
        priority: 8

      # From modules/evidence-handling
      - name: "Evidence Standards"
        rule: "Claims must be verifiable with file:line references"
        always:
          - "Include file path relative to workspace root"
          - "Include line numbers (single: :45, range: :45-52)"
          - "Use backticks for code formatting"
        never:
          - "Cite without line numbers"
          - "Make claims without source"
          - "Include evidence trails in published docs"
        priority: 8

      # From modules/docs-ux-patterns
      - name: "UX Pattern Detection"
        rule: "Convert parallel content to interactive elements"
        always:
          - "Numbered parallel headers → tab sets"
          - "Before/After comparisons → tab sets"
          - "Platform variants → tab sets"
          - "Advanced content → dropdowns"
        never:
          - "Tab sets for sequential steps"
          - "Dropdowns for critical information"
        priority: 6

    anti_heuristics:
      - name: "Marketing Trap"
        description: "Promotional language that adds no information"
        triggers: ["powerful", "flexible", "easy", "robust", "seamless", "cutting-edge"]
        correction: "Replace with specific, measurable claims"

      - name: "Academic Trap"
        description: "Overly formal, passive, theoretical"
        triggers: ["upon conducting", "comprehensive evaluation", "the artifact", "it should be noted"]
        correction: "Use PACE tone: Professional, Active, Conversational, Engaging"

      - name: "Wall of Text"
        description: "Dense paragraphs without structure"
        triggers: ["paragraph > 5 sentences", "no headers in 500+ words", "no code in API docs"]
        correction: "Use lists, code blocks, and headers for scannability"

      - name: "Buried Lede"
        description: "Critical information hidden in later sections"
        triggers: ["first, let me explain", "before we begin", "to understand this"]
        correction: "Front-load the conclusion, details follow"

    communication:
      tone:
        - Professional
        - Active
        - Conversational
        - Engaging
      structure: "Conclusion first, details later (inverted pyramid)"

  # ==========================================================================
  # FRAMEWORK — Methodology
  # ==========================================================================
  
  framework:
    name: "Diataxis"
    description: "A systematic framework for technical documentation"
    decision_tree: |
      Ask: "What is the user trying to DO?"
      
      Learn by doing → TUTORIAL
      Accomplish task → HOW-TO
      Understand concepts → EXPLANATION
      Look up facts → REFERENCE
    
    categories:
      - name: "TUTORIAL"
        purpose: "Learn by doing guided lesson"
        structure: [learning_objectives, prerequisites, guided_steps, expected_outcomes, next_steps]
        includes: ["Learning objectives", "Guided steps", "Expected outcomes"]
        excludes: ["Reference tables", "All options", "Deep why explanations"]
        triggers: ["tutorial", "getting started", "learn", "first steps", "quickstart"]

      - name: "HOW_TO"
        purpose: "Accomplish specific task"
        structure: [goal, prerequisites, steps, troubleshooting]
        includes: ["Clear goal", "Practical steps", "Troubleshooting"]
        excludes: ["Concept teaching", "Complete reference", "Guided learning"]
        triggers: ["how to", "configure", "set up", "deploy", "fix", "troubleshoot"]

      - name: "EXPLANATION"
        purpose: "Understand concepts and architecture"
        structure: [context, how_it_works, components, design_rationale]
        includes: ["Concepts", "Why/how it works", "Architecture"]
        excludes: ["Step-by-step", "Complete options", "Guided lessons"]
        triggers: ["understand", "architecture", "concepts", "overview", "why"]

      - name: "REFERENCE"
        purpose: "Look up specific information"
        structure: [purpose, categories, comprehensive_listings]
        includes: ["All options", "Technical specs", "Tables"]
        excludes: ["Conceptual explanations", "Step-by-step", "Teaching"]
        triggers: ["reference", "api", "parameters", "configuration", "options"]

  # ==========================================================================
  # PERSONAS — Adversarial Testing
  # ==========================================================================
  
  personas:
    - name: "novice"
      description: "Technical user new to THIS specific tool"
      background: "Knows APIs, terminals, codebases. Doesn't know THIS tool."
      goals: ["Understand what it does", "Get started quickly", "Know if it solves their problem"]
      friction_points:
        - "Tool-specific jargon without explanation"
        - "Assumed knowledge about internals"
        - "Missing prerequisites"
        - "Incomplete examples"
      attack_vectors:
        - "You said 'apply a lens' but what IS a lens?"
        - "What's the minimum I need to get this working?"
        - "Where do I actually type this command?"

    - name: "skeptic"
      description: "Senior dev who's seen many tools fail"
      background: "Deep technical knowledge, high standards, limited patience"
      goals: ["Understand tradeoffs", "See proof it works", "Identify failure modes"]
      friction_points:
        - "Marketing speak instead of facts"
        - "Missing edge cases"
        - "No benchmarks or comparisons"
      attack_vectors:
        - "What happens at scale?"
        - "Show me the failure modes"
        - "Why should I use this instead of X?"

    - name: "pragmatist"
      description: "Busy developer who just wants working code"
      background: "Competent, time-pressured, prefers examples"
      goals: ["Working code NOW", "Minimal reading", "Copy-paste solutions"]
      friction_points:
        - "Long explanations before code"
        - "Incomplete examples"
        - "Missing imports"
      attack_vectors:
        - "Can I copy this and have it work?"
        - "Where's the TL;DR?"
        - "Just show me the code"

    - name: "expert"
      description: "Systems architect looking for edge cases"
      background: "Deep expertise, security-conscious, scale-focused"
      goals: ["Understand architecture", "Identify security implications", "Plan for scale"]
      friction_points:
        - "Missing security considerations"
        - "No architecture diagrams"
        - "Unclear scaling characteristics"
      attack_vectors:
        - "What happens with malicious input?"
        - "How does this behave under load?"
        - "What are the security boundaries?"

  # ==========================================================================
  # VALIDATORS — Quality Gates
  # ==========================================================================
  
  validators:
    deterministic:
      - name: "no-marketing-fluff"
        check: "Reject marketing language"
        pattern: "\\b(powerful|flexible|easy|robust|seamless|cutting-edge)\\b"
        severity: "warning"

      - name: "evidence-format"
        check: "File references use file:line format"
        pattern: "`[^`]+\\.(py|ts|js|yaml|json|md):\\d+(-\\d+)?`"
        severity: "warning"

      - name: "no-passive-voice"
        check: "Avoid passive constructions"
        pattern: "\\b(is|are|was|were|been|being)\\s+\\w+ed\\b"
        severity: "info"

    heuristic:
      - name: "signal-to-noise"
        check: "Every sentence adds value"
        guidance: "Remove if user loses nothing"
        confidence_threshold: 0.7
        severity: "warning"

      - name: "diataxis-purity"
        check: "Single content type per page"
        guidance: "Split if mixing tutorial + reference"
        confidence_threshold: 0.8
        severity: "warning"

      - name: "front-loaded"
        check: "Most important information in first paragraph"
        guidance: "Start with conclusion"
        confidence_threshold: 0.7
        severity: "warning"

      - name: "evidence-required"
        check: "Technical claims have file:line references"
        guidance: "Add source citation"
        confidence_threshold: 0.8
        severity: "warning"

  # ==========================================================================
  # ROUTER — Intent and Skill Routing
  # ==========================================================================
  
  router:
    tiers:
      - level: 0
        name: "Fast Path"
        triggers: ["typo", "indent", "format", "spacing", "fix syntax"]
        retrieval: false
        validation: false
        skills: ["fix-markdown-syntax", "fix-rst-syntax"]

      - level: 1
        name: "Standard"
        triggers: []
        retrieval: true
        validation: true

      - level: 2
        name: "Deep Analysis"
        triggers: ["audit", "comprehensive", "review", "deep", "validate all"]
        retrieval: true
        validation: true
        personas: ["skeptic", "expert"]
        require_confirmation: true
        skills: ["audit-documentation-deep", "check-health"]

    intent_categories:
      VALIDATION: ["audit", "check", "verify", "validate", "lint", "review"]
      CREATION: ["draft", "create", "write", "generate", "new"]
      TRANSFORMATION: ["polish", "improve", "modularize", "split", "refactor"]
      INFORMATION: ["help", "what", "how", "explain", "show"]

    # Command shortcuts (from system/docs-os)
    shortcuts:
      "::a": "audit-documentation"
      "::a-2": "audit-documentation-deep"
      "::p": "polish-documentation"
      "::m": "modularize-content"
      "::w": "writing-pipeline"
      "::health": "check-health"
      "::md": "fix-markdown-syntax"
      "::rst": "fix-rst-syntax"
      "::fm": "generate-frontmatter"
      "::overview": "create-overview-page"
      "::architecture": "create-architecture-page"
      "::features": "create-features-page"
      "::?": "show-help"

  # ==========================================================================
  # WORKFLOWS — Multi-Step Chains
  # ==========================================================================
  
  workflows:
    - name: "writing-pipeline"
      description: "Full documentation writing workflow"
      shortcut: "::w"
      steps:
        - skill: classify-content
          description: "Identify Diataxis type"
        - skill: research-codebase
          description: "Extract evidence from source"
        - skill: plan-structure
          description: "Outline based on type"
        - skill: draft-content
          description: "Write with heuristics"
        - skill: validate-output
          description: "Run validators"
        - skill: run-personas
          description: "Stress test with personas"
      on_failure: reflexion-loop

    - name: "audit-pipeline"
      description: "Complete documentation audit"
      shortcut: "::a-full"
      steps:
        - skill: audit-documentation
          description: "Quick validation"
        - skill: score-confidence
          description: "Calculate confidence scores"
        - skill: detect-drift
          description: "Find stale content"
        - skill: check-readability
          description: "Assess readability"
      output: "Comprehensive audit report"

    - name: "reflexion-loop"
      description: "Iterative improvement when validation fails"
      max_iterations: 3
      steps:
        - action: analyze-failures
        - action: generate-improvements
        - action: re-validate
      exit_condition: "confidence >= 0.85 or no improvement"

  # ==========================================================================
  # SKILLS — Action Capabilities
  # ==========================================================================
  
  skills:
    # Include skill libraries
    - include: ../skills/docs-validation-skills.yaml
    - include: ../skills/docs-creation-skills.yaml
    - include: ../skills/docs-transformation-skills.yaml
    - include: ../skills/docs-utility-skills.yaml

  # ==========================================================================
  # QUALITY POLICY
  # ==========================================================================
  
  quality_policy:
    min_confidence: 0.7
    required_validators: ["no-marketing-fluff"]
    persona_agreement: 0.5
    retry_limit: 2

  skill_retry:
    max_attempts: 3
    backoff_ms: [100, 500, 2000]
    retry_on: ["timeout", "validation_failure"]
    abort_on: ["security_violation", "script_crash"]
```

#### 3.3 Validation Skills: `docs-validation-skills.yaml`

```yaml
# skills/docs-validation-skills.yaml
# Validation and auditing skills for technical documentation

skills:
  # ==========================================================================
  # AUDIT SKILLS
  # ==========================================================================
  
  - name: audit-documentation
    description: "Quick validation of documentation against source code"
    type: inline
    triggers: ["audit", "validate", "check", "verify", "::a"]
    allowed-tools: [read_file, search_files]
    instructions: |
      ## Goal
      Validate documentation claims against source code.
      
      ## Process
      1. Extract all technical claims from the document
      2. For each claim, search codebase for verification
      3. Check function signatures, parameters, defaults
      4. Verify code examples match actual source
      5. Calculate confidence score per claim
      
      ## Output Format
      ```markdown
      ## 🔍 Audit: [Document Name]
      
      **Summary**: [N] claims analyzed, [N] verified ([%])
      **Confidence**: [N]% [🟢|🟡|🟠|🔴]
      
      ### ✅ Verified ([N])
      - Claim: [description] — `file:line`
      
      ### ⚠️ Issues ([N])
      - Claim: [description] — [issue] — Fix: [action]
      
      ### 📋 Action Items
      - [ ] [Priority fix 1]
      - [ ] [Priority fix 2]
      ```
    validate_with:
      validators: [evidence-required]
      min_confidence: 0.8

  - name: audit-documentation-deep
    description: "Comprehensive audit with triangulation and confidence scoring"
    type: inline
    triggers: ["deep audit", "comprehensive", "thorough", "::a-2"]
    allowed-tools: [read_file, search_files, run_command]
    instructions: |
      ## Goal
      Deep validation with 3-path triangulation for critical claims.
      
      ## Process
      1. Classify claims by criticality (high/medium/low)
      2. For HIGH criticality claims, validate via:
         - Path A: Source code verification
         - Path B: Test file verification
         - Path C: Config/schema verification
      3. Aggregate results: all 3 agree = HIGH confidence
      4. Calculate overall confidence score
      5. Run reflexion if confidence < 80%
      
      ## Triangulation Example
      **Claim**: "API accepts `limit` parameter with default 100"
      
      - Path A (Source): `api/users.py:45` → `def get_users(limit: int = 100)`
      - Path B (Tests): `tests/test_users.py:23` → asserts limit == 100
      - Path C (Schema): `openapi.yaml:156` → default: 100
      
      **Result**: 3/3 agree → HIGH confidence (93%)
    validate_with:
      validators: [evidence-required]
      personas: [skeptic]
      min_confidence: 0.85

  - name: score-confidence
    description: "Calculate detailed confidence scores for documentation claims"
    type: inline
    triggers: ["confidence", "score", "scoring", "::score"]
    instructions: |
      ## Scoring Rubric
      
      | Component | Weight | Criteria |
      |-----------|--------|----------|
      | Evidence Strength | 40 pts | Direct match: 40, Partial: 25, Outdated: 10, None: 0 |
      | Consistency | 30 pts | Multiple sources agree: 30, Some agree: 20, Conflict: 0 |
      | Recency | 15 pts | < 30 days: 15, < 90 days: 10, < 1 year: 5, Older: 0 |
      | Test Coverage | 15 pts | Has tests: 15, Partial: 8, None: 0 |
      
      ## Confidence Levels
      - 🟢 90-100%: HIGH — Ship it
      - 🟡 70-89%: MODERATE — Review recommended
      - 🟠 50-69%: LOW — Needs work
      - 🔴 0-49%: UNCERTAIN — Do not ship
    validate_with:
      min_confidence: 0.7

  - name: detect-drift
    description: "Find documentation that has drifted from source code"
    type: inline
    triggers: ["drift", "stale", "outdated", "out of date"]
    allowed-tools: [read_file, search_files, run_command]
    instructions: |
      ## Goal
      Identify documentation that no longer matches source code.
      
      ## Detection Methods
      1. **Timestamp comparison**: Doc modified < Source modified
      2. **Signature mismatch**: Documented signature ≠ actual signature
      3. **Deprecated references**: Doc mentions removed/renamed items
      4. **Version drift**: Doc mentions old version numbers
      
      ## Output
      ```markdown
      ## 📉 Drift Report
      
      ### 🔴 Critical Drift ([N] files)
      - `docs/api.md` — Last updated 6 months ago, source changed 12 times
      
      ### 🟡 Moderate Drift ([N] files)
      - `docs/config.md` — 3 config options removed from source
      ```
    scripts:
      - name: check_drift.py
        language: python
        description: Compare doc timestamps to source timestamps
        content: |
          import os
          import sys
          from pathlib import Path
          
          def check_drift(doc_path, source_path):
              doc_mtime = Path(doc_path).stat().st_mtime
              source_mtime = Path(source_path).stat().st_mtime
              return source_mtime > doc_mtime
          
          if __name__ == '__main__':
              print("DRIFT" if check_drift(sys.argv[1], sys.argv[2]) else "OK")

  - name: check-health
    description: "System-wide documentation health check"
    type: inline
    triggers: ["health", "health check", "status", "::health"]
    allowed-tools: [read_file, search_files, run_command, list_files]
    instructions: |
      ## Health Checks
      
      1. **Drift**: Docs newer than source?
      2. **Readability**: Flesch-Kincaid score acceptable?
      3. **Syntax**: Valid Markdown/MyST/RST?
      4. **Links**: All internal links resolve?
      5. **Orphans**: Docs not linked from nav?
      6. **Bloat**: Files > 2000 lines?
      
      ## Output
      ```markdown
      ## 🏥 Documentation Health
      
      **Overall**: [HEALTHY|WARNING|CRITICAL]
      
      | Check | Status | Details |
      |-------|--------|---------|
      | Drift | 🟢 | 45/47 files current |
      | Readability | 🟡 | 3 files > grade 12 |
      | Syntax | 🟢 | All valid |
      | Links | 🔴 | 5 broken links |
      | Orphans | 🟡 | 2 orphaned files |
      ```

  - name: check-readability
    description: "Assess documentation readability scores"
    type: inline
    triggers: ["readability", "readable", "grade level"]
    instructions: |
      ## Readability Metrics
      
      - **Flesch-Kincaid Grade**: Target 8-10 for technical docs
      - **Sentence Length**: Target < 25 words average
      - **Paragraph Length**: Target < 5 sentences
      
      ## Guidelines
      - API docs: Grade 10-12 acceptable
      - Tutorials: Grade 8-10 preferred
      - Quickstarts: Grade 6-8 ideal

  - name: lint-structure
    description: "Validate documentation structure against templates"
    type: inline
    triggers: ["lint", "structure", "template", "schema"]
    allowed-tools: [read_file]
    instructions: |
      ## Structure Validation
      
      Check that documents match their Diataxis type structure:
      
      - TUTORIAL: Has objectives, prerequisites, steps, next_steps
      - HOW-TO: Has goal, prerequisites, steps, troubleshooting
      - EXPLANATION: Has context, how_it_works, components
      - REFERENCE: Has purpose, categories, listings

  - name: audit-code-examples
    description: "Verify all code examples in documentation actually work"
    type: inline
    triggers: ["code examples", "examples", "snippets"]
    allowed-tools: [read_file, search_files, run_command]
    instructions: |
      ## Code Example Validation
      
      1. Extract all code blocks from document
      2. For Python: Check syntax with `ast.parse()`
      3. For imports: Verify modules exist
      4. For function calls: Verify functions exist with correct signatures
      
      ## Output
      ```markdown
      ### Code Example Audit
      
      - ✅ Line 45: Python syntax valid
      - ⚠️ Line 78: Import 'foo' not found in codebase
      - ❌ Line 112: Function `bar()` has different signature
      ```
    scripts:
      - name: check_python_syntax.py
        language: python
        content: |
          import ast
          import sys
          
          code = sys.stdin.read()
          try:
              ast.parse(code)
              print("VALID")
          except SyntaxError as e:
              print(f"ERROR: {e}")
              sys.exit(1)
```

#### 3.4 Creation Skills: `docs-creation-skills.yaml`

```yaml
# skills/docs-creation-skills.yaml
# Content creation skills for technical documentation

skills:
  - name: draft-documentation
    description: "Create new documentation with evidence-based research"
    type: inline
    triggers: ["draft", "write", "create doc", "new doc"]
    allowed-tools: [read_file, search_files, write_file]
    instructions: |
      ## Goal
      Create documentation grounded in source code evidence.
      
      ## Process
      1. **Research**: Search codebase for relevant files
      2. **Extract**: Pull function signatures, docstrings, tests
      3. **Classify**: Determine Diataxis type
      4. **Structure**: Apply type-appropriate template
      5. **Draft**: Write with heuristics (signal-to-noise, evidence)
      6. **Cite**: Include file:line references for claims
      
      ## Rules
      - Only include verifiable claims
      - Mark uncertain content with TODO
      - Link to related content types
    validate_with:
      validators: [evidence-required, no-marketing-fluff, front-loaded]
      personas: [novice, pragmatist]
      min_confidence: 0.75

  - name: create-overview-page
    description: "Create product/platform overview (Explanation type)"
    type: inline
    triggers: ["overview", "introduction", "what is", "::overview"]
    instructions: |
      ## Diataxis Type: EXPLANATION
      
      ## Structure
      1. **Opening Hook**: What problem does this solve? (1-2 sentences)
      2. **What It Is**: Clear definition (1 paragraph)
      3. **Key Capabilities**: 3-5 bullet points
      4. **How It Works**: High-level flow (with diagram)
      5. **When to Use**: Use cases and anti-patterns
      6. **Next Steps**: Links to tutorial, how-to, reference
      
      ## Guidelines
      - 30-second scan test: Value clear immediately
      - No step-by-step instructions (link to tutorial)
      - Include architecture diagram if applicable
    templates:
      - name: overview-template.md
        content: |
          # ${Product Name}
          
          ${One-sentence hook: what problem does this solve?}
          
          ## What is ${Product Name}?
          
          ${Clear definition in 2-3 sentences}
          
          ## Key Capabilities
          
          - **${Capability 1}**: ${Brief description}
          - **${Capability 2}**: ${Brief description}
          - **${Capability 3}**: ${Brief description}
          
          ## How It Works
          
          ${High-level explanation with diagram}
          
          ```mermaid
          graph LR
              A[Input] --> B[${Product}]
              B --> C[Output]
          ```
          
          ## When to Use ${Product Name}
          
          **Use when**:
          - ${Use case 1}
          - ${Use case 2}
          
          **Don't use when**:
          - ${Anti-pattern 1}
          
          ## Next Steps
          
          - [Get Started](./quickstart.md) — Tutorial
          - [Configure ${Product}](./configure.md) — How-to
          - [API Reference](./reference.md) — Reference
    validate_with:
      validators: [front-loaded, no-marketing-fluff]
      personas: [novice]
      min_confidence: 0.7

  - name: create-architecture-page
    description: "Create architecture explanation page"
    type: inline
    triggers: ["architecture", "how it works", "internals", "::architecture"]
    instructions: |
      ## Diataxis Type: EXPLANATION
      
      ## Structure
      1. **Purpose**: Why this architecture exists
      2. **Components**: Major parts and responsibilities
      3. **Data Flow**: How data moves through system
      4. **Key Decisions**: Why it's built this way
      5. **Diagrams**: Visual representations
      
      ## Diagram Requirements
      - Component diagram showing major parts
      - Sequence diagram for key workflows
      - Use Mermaid for portability
    validate_with:
      validators: [evidence-required]
      personas: [expert]
      min_confidence: 0.8

  - name: create-features-page
    description: "Create comprehensive key features catalog (Reference type)"
    type: inline
    triggers: ["features", "capabilities", "key features", "::features"]
    instructions: |
      ## Diataxis Type: REFERENCE
      
      ## Structure
      1. **Overview**: What this catalog covers
      2. **Feature Categories**: Grouped by function
      3. **Feature Entries**: Name, description, status, links
      
      ## Feature Entry Format
      ```markdown
      ### Feature Name
      
      **Status**: GA | Beta | Preview
      **Since**: v1.2.0
      
      Brief description of what it does.
      
      - [How to use](./how-to/feature.md)
      - [API Reference](./reference/feature.md)
      ```
    validate_with:
      validators: [evidence-required]
      min_confidence: 0.75

  - name: create-ecosystem-page
    description: "Create ecosystem/positioning page"
    type: inline
    triggers: ["ecosystem", "positioning", "comparison", "::ecosystem"]
    instructions: |
      ## Diataxis Type: EXPLANATION
      
      ## Structure
      1. **Ecosystem Overview**: Where this fits
      2. **Related Tools**: What it works with
      3. **Comparison**: How it differs from alternatives
      4. **Integration Points**: How to connect
      
      ## Guidelines
      - Be factual about comparisons
      - Focus on complementary, not competitive
      - Include integration diagrams
```

#### 3.5 Transformation Skills: `docs-transformation-skills.yaml`

```yaml
# skills/docs-transformation-skills.yaml
# Transformation and improvement skills

skills:
  - name: polish-documentation
    description: "Quick improvements for clarity, style, and structure"
    type: inline
    triggers: ["polish", "improve", "clean up", "::p"]
    allowed-tools: [read_file, edit_file]
    instructions: |
      ## Goal
      Quick polish pass focusing on signal-to-noise and scannability.
      
      ## Checks
      1. Remove marketing fluff
      2. Front-load conclusions
      3. Convert walls of text to lists
      4. Add code examples where missing
      5. Fix passive voice
      6. Apply UX patterns (tabs, dropdowns)
      
      ## Output
      Show before/after for each change with reasoning.
    validate_with:
      validators: [signal-to-noise, no-marketing-fluff]
      min_confidence: 0.7

  - name: modularize-content
    description: "Break monolithic document into modular topics"
    type: inline
    triggers: ["modularize", "split", "break up", "::m"]
    allowed-tools: [read_file, write_file, list_files]
    instructions: |
      ## Goal
      Split a long document into well-scoped subtopics.
      
      ## Process
      1. Identify distinct topics (by Diataxis type)
      2. Create topic directory structure
      3. Extract each topic to separate file
      4. Create index.md linking all topics
      5. Update cross-references
      
      ## Output Structure
      ```
      topic/
      ├── index.md          # Overview with links
      ├── getting-started.md  # Tutorial sections
      ├── configuration.md    # How-to sections
      └── reference.md        # Reference sections
      ```

  - name: generate-frontmatter
    description: "Generate consistent frontmatter for documentation files"
    type: inline
    triggers: ["frontmatter", "metadata", "::fm"]
    allowed-tools: [read_file, edit_file]
    instructions: |
      ## Frontmatter Schema
      ```yaml
      ---
      title: "Page Title"
      description: "One-sentence description"
      author: "Author Name"
      date_created: "YYYY-MM-DD"
      date_modified: "YYYY-MM-DD"
      diataxis_type: "tutorial|how-to|explanation|reference"
      audience: ["data-scientists", "mles", "admins"]
      keywords: ["keyword1", "keyword2"]
      ---
      ```
      
      ## Process
      1. Analyze document content
      2. Classify Diataxis type
      3. Identify target audience
      4. Extract keywords
      5. Generate frontmatter block

  - name: generate-navigation-map
    description: "Generate navigation indexes for documentation"
    type: inline
    triggers: ["navigation", "index", "map", "toc", "::map"]
    allowed-tools: [read_file, list_files, write_file]
    instructions: |
      ## Goal
      Create navigation structure from existing documents.
      
      ## Output Types
      1. **Index page**: Grouped links with descriptions
      2. **TOC file**: For Sphinx/MkDocs
      3. **Sitemap**: For search/SEO
```

### Part 4: Type System Changes

#### 4.1 Skill Triggers

```python
# src/sunwell/skills/types.py

@dataclass(frozen=True, slots=True)
class Skill:
    """An agent skill that provides action capabilities."""
    
    name: str
    description: str
    skill_type: SkillType
    
    # NEW: Trigger patterns for automatic discovery
    triggers: tuple[str, ...] = ()
    """Keywords/patterns that suggest this skill.
    
    When router analyzes intent, it matches against skill triggers
    to suggest relevant skills alongside lens selection.
    """
    
    # Existing fields unchanged...
    compatibility: str | None = None
    allowed_tools: tuple[str, ...] = ()
    parameters_schema: dict | None = None
    instructions: str | None = None
    scripts: tuple[Script, ...] = ()
    templates: tuple[Template, ...] = ()
    resources: tuple[Resource, ...] = ()
    source: str | None = None
    path: str | None = None
    trust: TrustLevel = TrustLevel.SANDBOXED
    timeout: int = 30
    override: bool = False
    validate_with: SkillValidation = field(default_factory=SkillValidation)
```

#### 4.2 Router Decision with Skills

```python
# src/sunwell/routing/unified.py

@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Result of unified routing."""
    
    intent: Intent
    complexity: Complexity
    lens: str | None
    tools: tuple[str, ...]
    mood: Mood
    expertise: Expertise
    confidence: float
    reasoning: str
    
    # NEW: Skill suggestions
    suggested_skills: tuple[str, ...] = ()
    skill_confidence: float = 0.0
```

#### 4.3 Lens Shortcuts

```python
# src/sunwell/core/lens.py

@dataclass(frozen=True, slots=True)
class Router:
    """Intent routing configuration."""
    
    tiers: tuple[RouterTier, ...] = ()
    intent_categories: tuple[str, ...] = ()
    signals: dict[str, str] = field(default_factory=dict)
    
    # NEW: Command shortcuts
    shortcuts: dict[str, str] = field(default_factory=dict)
    """Maps shortcut commands to skill names.
    
    Example: {"::a": "audit-documentation", "::p": "polish-documentation"}
    """
```

### Part 5: Schema Loader Updates

```python
# src/sunwell/schema/loader.py (updates)

def _parse_skill(self, skill_data: dict, base_path: Path) -> Skill:
    """Parse a skill from YAML data."""
    
    # Existing parsing...
    
    # NEW: Parse triggers
    triggers = tuple(skill_data.get("triggers", []))
    
    return Skill(
        name=skill_data["name"],
        description=skill_data["description"],
        skill_type=SkillType(skill_data.get("type", "inline")),
        triggers=triggers,  # NEW
        # ... rest unchanged
    )


def _parse_router(self, router_data: dict) -> Router:
    """Parse router configuration."""
    
    # Existing parsing...
    
    # NEW: Parse shortcuts
    shortcuts = router_data.get("shortcuts", {})
    
    return Router(
        tiers=tiers,
        intent_categories=tuple(router_data.get("intent_categories", {}).keys()),
        signals=router_data.get("signals", {}),
        shortcuts=shortcuts,  # NEW
    )
```

---

## Implementation Plan

### Phase 1: Core Migration (3 days)

| Task | Description | Effort |
|------|-------------|--------|
| 1.1 | Add `triggers` field to Skill type | S |
| 1.2 | Add `shortcuts` to Router type | S |
| 1.3 | Update schema loader for new fields | M |
| 1.4 | Create `tech-writer.lens` with heuristics, personas, validators | L |
| 1.5 | Unit tests for new types | M |

### Phase 2: Skills Migration (2 days)

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Create `docs-validation-skills.yaml` (9 skills) | L |
| 2.2 | Create `docs-creation-skills.yaml` (5 skills) | M |
| 2.3 | Create `docs-transformation-skills.yaml` (5 skills) | M |
| 2.4 | Create `docs-utility-skills.yaml` (10 skills) | L |
| 2.5 | Integration tests for skills | M |

### Phase 3: Router Integration (2 days)

| Task | Description | Effort |
|------|-------------|--------|
| 3.1 | Update UnifiedRouter for skill suggestions | M |
| 3.2 | Implement shortcut command handling | M |
| 3.3 | Add skill discovery to routing decision | M |
| 3.4 | Update CLI for skill suggestions | S |
| 3.5 | Integration tests for routing | M |

### Phase 4: Workflows (1 day)

| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | Implement `writing-pipeline` workflow | M |
| 4.2 | Implement `audit-pipeline` workflow | M |
| 4.3 | Implement `reflexion-loop` workflow | M |
| 4.4 | Workflow tests | S |

### Phase 5: Documentation & Export (1 day)

| Task | Description | Effort |
|------|-------------|--------|
| 5.1 | Document lens usage | M |
| 5.2 | Export to Agent Skills format | M |
| 5.3 | Create migration guide for DORI users | M |

**Total: ~9-10 days**

---

## Success Criteria

1. **Complete coverage** — All 59 DORI rules have Sunwell equivalents
2. **Skill routing works** — `::a` triggers `audit-documentation` skill
3. **Validation integration** — Skills run validators and personas
4. **Portable export** — Can export to Agent Skills SKILL.md format
5. **Improved workflow** — Router suggests skills automatically
6. **Documentation** — Clear migration guide for DORI users

---

## Usage Examples

### Example 1: Quick Audit

```
User: ::a

Router:
  Shortcut detected: "::a" → audit-documentation
  
Skill: audit-documentation
  1. Extract claims from active document
  2. Search codebase for evidence
  3. Calculate confidence scores
  4. Run validators: evidence-required
  
Output:
  ## 🔍 Audit: api-reference.md
  
  **Summary**: 23 claims, 21 verified (91%)
  **Confidence**: 88% 🟡
  
  ### ✅ Verified (21)
  ...
  
  ### ⚠️ Issues (2)
  1. Line 45: Function signature changed — `api/users.py:67`
  2. Line 78: Config option removed — was `CACHE_TTL`
```

### Example 2: Natural Language with Skill Suggestion

```
User: "I need to validate this documentation thoroughly"

Router:
  Intent: VALIDATION
  Complexity: STANDARD
  Lens: tech-writer
  Suggested Skills: [audit-documentation-deep, check-health]
  
Response:
  I can help validate this documentation. Based on your request, I suggest:
  
  1. **audit-documentation-deep** — Comprehensive audit with triangulation
  2. **check-health** — System-wide health check
  
  Which would you like to run? Or type `::a-2` for deep audit.
```

### Example 3: Writing Workflow

```
User: ::w

Workflow: writing-pipeline
  Step 1: classify-content
    → Diataxis type: HOW-TO
  
  Step 2: research-codebase
    → Found 12 relevant files
    → Extracted 8 function signatures
  
  Step 3: plan-structure
    → Goal, Prerequisites, Steps, Troubleshooting
  
  Step 4: draft-content
    → [Draft generated with evidence citations]
  
  Step 5: validate-output
    → Validators passed: evidence-required ✅, no-marketing-fluff ✅
  
  Step 6: run-personas
    → novice: "Where do I type this command?" → Added clarification
    → pragmatist: "Can I copy-paste?" → Yes ✅
  
Output: [Polished documentation with all validations passed]
```

---

## Migration Guide for DORI Users

### Command Mapping

| DORI Command | Sunwell Equivalent |
|--------------|-------------------|
| `::a` | `::a` (same) |
| `::a-2` | `::a-2` (same) |
| `::p` | `::p` (same) |
| `::m` | `::m` (same) |
| `::w` | `::w` (same) |
| `::health` | `::health` (same) |
| `::overview` | `::overview` (same) |
| `::architecture` | `::architecture` (same) |
| `::as novice` | Automatic via `validate_with.personas` |
| `::auto` | Default behavior (router always active) |

### What's New in Sunwell

1. **Skill suggestions** — Router recommends relevant skills
2. **Validation binding** — Skills automatically run validators
3. **Persona integration** — Stress testing built into skill execution
4. **Memory** — Simulacrum remembers past decisions
5. **Multi-model** — Voice (fast) + Wisdom (careful) coordination
6. **Portable** — Export to Agent Skills for other platforms

### What's Preserved

1. **All DORI commands** — Same shortcuts work
2. **All heuristics** — Signal-to-noise, Diataxis, etc.
3. **All personas** — novice, skeptic, pragmatist, expert
4. **All validation patterns** — Confidence scoring, triangulation
5. **All content templates** — Overview, architecture, features

---

## Future Work

1. **Studio integration** — Skill picker in UI
2. **CI/CD integration** — "Docs Rabbit" PR reviewer
3. **NVIDIA extensions** — NVIDIA-specific style guide, templates
4. **Skill marketplace** — Share skills via Fount registry
5. **Learning** — Simulacrum learns from validation feedback

---

## Related RFCs

- **RFC-011**: Agent Skills — Skills foundation
- **RFC-030**: Unified Router — Routing infrastructure
- **RFC-020**: Cognitive Routing — Intent classification
- **RFC-021**: Spellbook — Portable workflow incantations
- **RFC-064**: Lens Management — Lens composition

---

## Appendix A: Complete Rule Mapping

| # | DORI Rule | Sunwell Component | Type |
|---|-----------|-------------------|------|
| 1 | modules/docs-quality-principles | heuristic: signal-to-noise, diataxis-scoping, progressive-disclosure | Heuristic |
| 2 | modules/diataxis-framework | framework: diataxis | Framework |
| 3 | modules/docs-communication-style | heuristic: communication-style | Heuristic |
| 4 | modules/evidence-handling | heuristic: evidence-standards | Heuristic |
| 5 | modules/docs-ux-patterns | heuristic: ux-patterns | Heuristic |
| 6 | modules/docs-output-format | heuristic: output-formatting | Heuristic |
| 7 | modules/validation-patterns | heuristic: validation-scoring | Heuristic |
| 8 | modules/execution-patterns | heuristic: execution-patterns | Heuristic |
| 9 | personas/persona-novice | persona: novice | Persona |
| 10 | personas/persona-skeptic | persona: skeptic | Persona |
| 11 | personas/persona-pragmatist | persona: pragmatist | Persona |
| 12 | personas/persona-expert | persona: expert | Persona |
| 13 | docs-personas | persona: audience-definitions | Persona |
| 14 | validation/docs-audit | skill: audit-documentation | Skill |
| 15 | validation/docs-audit-enhanced | skill: audit-documentation-deep | Skill |
| 16 | validation/docs-confidence-scoring | skill: score-confidence | Skill |
| 17 | validation/docs-drift | skill: detect-drift | Skill |
| 18 | validation/docs-health | skill: check-health | Skill |
| 19 | validation/docs-readability-checker | skill: check-readability | Skill |
| 20 | validation/docs-structural-lint | skill: lint-structure | Skill |
| 21 | validation/docs-vdr-assessment | skill: assess-vdr | Skill |
| 22 | validation/docs-code-example-audit | skill: audit-code-examples | Skill |
| 23 | transformation/docs-polish | skill: polish-documentation | Skill |
| 24 | transformation/docs-modularize-content | skill: modularize-content | Skill |
| 25 | transformation/docs-frontmatter | skill: generate-frontmatter | Skill |
| 26 | transformation/docs-map-maker | skill: generate-navigation-map | Skill |
| 27 | transformation/docs-migration-fern-gap-analysis | skill: analyze-fern-migration | Skill |
| 28 | content/docs-draft | skill: draft-documentation | Skill |
| 29 | content/docs-content-overview-page | skill: create-overview-page | Skill |
| 30 | content/docs-content-architecture-page | skill: create-architecture-page | Skill |
| 31 | content/docs-content-ecosystem-page | skill: create-ecosystem-page | Skill |
| 32 | content/docs-content-key-features-page | skill: create-features-page | Skill |
| 33 | workflows/docs-writing-workflow | workflow: writing-pipeline | Workflow |
| 34 | workflows/docs-pipeline | workflow: research-draft-verify | Workflow |
| 35 | workflows/docs-chain-executor | workflow: custom-chain | Workflow |
| 36 | workflows/docs-reflexion | workflow: reflexion-loop | Workflow |
| 37 | workflows/docs-workflow-templates | workflow: templates | Workflow |
| 38 | utilities/docs-style-guide | skill: apply-style-guide | Skill |
| 39 | utilities/docs-md-syntax | skill: fix-markdown-syntax | Skill |
| 40 | utilities/docs-rst-syntax | skill: fix-rst-syntax | Skill |
| 41 | utilities/docs-bump-version | skill: bump-version | Skill |
| 42 | utilities/docs-atomic-commits | skill: format-commit-message | Skill |
| 43 | utilities/docs-bootstrap-sphinx | skill: bootstrap-sphinx | Skill |
| 44 | utilities/docs-dir-index-format | skill: format-index-page | Skill |
| 45 | utilities/docs-assist-merge-conflict-resolution | skill: resolve-merge-conflict | Skill |
| 46 | utilities/docs-retro | skill: run-retrospective | Skill |
| 47 | utilities/docs-task-management | skill: manage-tasks | Skill |
| 48 | commands/audit | alias: audit-documentation | Alias |
| 49 | commands/audit-deep | alias: audit-documentation-deep | Alias |
| 50 | commands/draft | alias: draft-documentation | Alias |
| 51 | commands/polish | alias: polish-documentation | Alias |
| 52 | commands/overview | alias: create-overview-page | Alias |
| 53 | commands/architecture | alias: create-architecture-page | Alias |
| 54 | commands/auto | router: default | Router |
| 55 | commands/help | skill: show-help | Skill |
| 56 | system/docs-os | router: shortcuts | Router |
| 57 | system/docs-orchestrator | router: intent-routing | Router |
| 58 | system/docs-context-analyzer | router: context-analysis | Router |
| 59 | system/docs-help-system | skill: show-help | Skill |

---

## Appendix B: Agent Skills Export

The tech-writer lens can be exported to standard Agent Skills format for use in other platforms:

```
skills/
├── audit-documentation/
│   └── SKILL.md
├── create-overview-page/
│   └── SKILL.md
├── polish-documentation/
│   └── SKILL.md
└── ...
```

Each SKILL.md follows the [Agent Skills specification](https://agentskills.io):

```markdown
# audit-documentation

Quick validation of documentation against source code.

## Instructions

1. Extract all technical claims from the document
2. For each claim, search codebase for verification
3. Check function signatures, parameters, defaults
4. Verify code examples match actual source
5. Calculate confidence score per claim

## Verification

After generating content, verify:
- [ ] All claims have file:line references
- [ ] No marketing language

**Minimum confidence:** 80%

---

Compatibility: Requires file system access
Trust: sandboxed
```
