# RFC-010: Sunwell — RAG for Judgment

| Field | Value |
|-------|-------|
| **RFC** | 010 |
| **Title** | Sunwell: RAG for Judgment |
| **Status** | Draft |
| **Created** | 2026-01-15 |
| **Author** | llane |

---

## Abstract

RAG revolutionized how LLMs access knowledge—instead of baking facts into weights, you retrieve relevant information at runtime. But RAG only solves *what to know*. It doesn't solve *how to think*.

**Sunwell is RAG for judgment.**

```
RAG:      Query → Retrieve FACTS → Inject → Generate
Sunwell:  Query → Retrieve HEURISTICS → Inject → Generate → Validate
```

Where RAG retrieves documents from a knowledge base, Sunwell retrieves professional heuristics from an expertise graph. The retrieval is contextual—not "inject everything" but "inject what's relevant to this task."

| System | Retrieves | Based on | Output |
|--------|-----------|----------|--------|
| **RAG** | Facts, documents | Semantic similarity | Informed response |
| **Sunwell** | Heuristics, judgment | Intent + context | Professional-quality response |

### Why It Matters

Current approaches (Cursor rules, system prompts) inject ALL rules into context on EVERY request:
- **Wasteful**: 10,000-25,000 tokens consumed even when only 3 rules apply
- **Noisy**: Irrelevant rules confuse the model and degrade output quality
- **Doesn't scale**: Context bloat limits lens complexity

Sunwell uses **vector search over the expertise graph** to retrieve only relevant components:
- **Lower token usage** per request (measure in PoC)
- **Higher signal-to-noise** = better outputs
- **Scales to larger component sets** without full-context injection

### Key Properties

- **Headless**: No IDE, no platform—pure runtime that travels with you
- **Model-agnostic**: Attach to OpenAI, Anthropic, local vLLM, Ollama—any model
- **Graph-based**: Heuristics form a network with branching, inheritance, composition
- **Retrieval-based**: RAG over expertise—only inject what's relevant
- **Efficient**: lower token usage vs flat injection (measure in PoC)
- **Validated**: Built-in quality gates, persona testing, confidence scoring

**One-liner**: *RAG retrieves what you need to know. Sunwell retrieves how you should think.*

---

## Problem Statement

### The Gap

LLMs can generate text about any domain, but they lack the **professional judgment** that distinguishes expert work from competent work.

| Layer | What it provides | Current solutions |
|-------|------------------|-------------------|
| **Knowledge** | Facts, information | RAG, retrieval ✅ |
| **Methodology** | Processes, workflows | Prompts, agents ✅ |
| **Professional Heuristics** | How to think, adapt, judge | **Unsolved** ❌ |

### The Chef Analogy

A chef following a recipe but missing ingredients doesn't panic. They:
1. **Identify function**: "Lemon was for acid"
2. **Find substitute**: "Vinegar works"
3. **Compensate**: "Reduce garlic to balance"
4. **Adapt presentation**: "Different texture, adjust plating"

An LLM with the recipe but without chef heuristics either:
- Fails ("I can't make this without lemon")
- Substitutes badly ("Here's your garlic-vinegar disaster")
- Doesn't notice the gap at all

**The gap between "has the recipe" and "can cook" is professional judgment.**

### Why Existing Solutions Don't Work

| Approach | What it does | Why it's insufficient |
|----------|--------------|----------------------|
| **Fine-tuning** | Bakes knowledge into weights | Expensive, static, can't swap |
| **RAG** | Retrieves relevant facts | Facts ≠ perspective |
| **System prompts** | One-shot context injection | Shallow, no state, no validation |
| **Agent frameworks** | Tool use + orchestration | Focuses on *what* to do, not *how* to think |
| **Rules (Cursor, etc.)** | Static markdown files | Flat, no routing, IDE-locked |

### Why Rules Aren't Enough

IDE rules (Cursor rules, GitHub Copilot instructions) are a step toward portable expertise but fundamentally limited:

```
RULES (Static Injection)              SUNWELL (Dynamic Retrieval)
                                      
┌─────────────────────┐               ┌─────────────────────────────┐
│                     │               │      EXPERTISE GRAPH        │
│  rule-1.md ─────────┼──┐            │                             │
│  rule-2.md ─────────┼──┤            │   ┌───┐         ┌───┐       │
│  rule-3.md ─────────┼──┼── ALL ──▶  │   │ H │────────▶│ H │       │
│  rule-4.md ─────────┼──┤   injected │   └─┬─┘         └─┬─┘       │
│  rule-5.md ─────────┼──┘            │     │      ╲      │         │
│                     │               │     ▼       ╲     ▼         │
└─────────────────────┘               │   ┌───┐     ╲  ┌───┐        │
                                      │   │ V │      ╲▶│ W │        │
                                      │   └───┘        └───┘        │
                                      │                             │
                                      │   Query: "write docs"       │
                                      │      ↓                      │
                                      │   Router selects: H₁, V₂    │
                                      │   (relevant subset)         │
                                      └─────────────────────────────┘
```

| Rules | Sunwell |
|-------|---------|
| Flat file list | Directed graph with edges |
| **All rules injected always** | **RAG retrieval—only relevant nodes** |
| Higher token usage per request | **Lower token usage per request (measure in PoC)** |
| No state between calls | Persistent context |
| IDE-specific (Cursor, Copilot) | **Headless—any client, any model** |
| Text injection only | Injection + validation loop |
| Manual composition | Inheritance, composition, override |
| No quality feedback | Built-in validators + personas |
| Doesn't scale as rule sets grow | **Scales to larger component sets (measure in PoC)** |

**The key insight**: Rules are like stuffing an entire textbook into context every time. Sunwell is like having a librarian who knows which pages you need—lower token usage and better signal-to-noise (measure in PoC).

---

## Solution: Expertise Graphs

### Core Concept

A **lens** is an expertise graph—a network of heuristics, validators, and workflows with a retrieval layer that selects relevant nodes based on context:

```
User → Lens Runtime → LLM → Validated Output
           │
    ┌──────┴──────┐
    │    LENS     │
    │ • Heuristics│  ← How to think
    │ • Framework │  ← Domain methodology  
    │ • Personas  │  ← Audience simulation
    │ • Validators│  ← Quality gates
    │ • Workflows │  ← Multi-step processes
    └─────────────┘
```

### Key Properties

| Property | Description |
|----------|-------------|
| **External** | Lens is worn, not learned—model stays general-purpose |
| **Instant** | No training, no fine-tuning—apply immediately |
| **Swappable** | Change lenses for different domains |
| **Validated** | Built-in quality gates catch bad outputs |
| **Testable** | Persona simulation stress-tests results |

### Differentiation from Agent Skills

| | Agent Skills | Lens |
|--|--------------|------|
| **Answers** | "What can I do?" | "How should I think?" |
| **Focus** | Actions, tools | Perspective, judgment |
| **Examples** | Browse web, execute code | Prioritize, substitute, validate |
| **Implementation** | Function calling, MCP | Context injection, heuristics |

**Skills give agents hands. Lenses give agents taste.**

They're complementary: an agent with chef skills can look up recipes; an agent with a chef lens knows *which* recipe and *how* to adapt it.

### Lens Composition: Building Expertise Networks

Unlike flat rules, lenses form a composable graph with inheritance and branching:

```yaml
# Base lens with core heuristics
base-writer.lens:
  heuristics:
    - signal-over-noise
    - evidence-required
    - audience-awareness

# Inherits from base, adds domain-specific expertise
tech-writer.lens:
  extends: base-writer
  framework: diataxis
  validators: [code-block-syntax, link-checker]
  
# Inherits from tech-writer, adds company standards  
acme-docs.lens:
  extends: tech-writer
  style_guide: acme-style
  templates: [acme-api-reference, acme-tutorial]
  
# Composable: combine multiple lenses
api-launch.lens:
  compose:
    - lens: tech-writer
      priority: 1
    - lens: security-auditor
      priority: 10 # Security always overrides style
    - lens: ux-writer
      priority: 2
  
  # Conflict Resolution Strategy
  # options: priority_wins, latest_wins, merge_with_warnings
  resolve_strategy: priority_wins
```

### Heuristic Precedence & Priority Matrices

When multiple lenses overlap (e.g., a "Security" lens demanding verbosity for clarity vs. a "Tech Writer" lens demanding brevity), Sunwell uses a **Priority Matrix** to resolve the heuristic tension:

| Level | Name | Behavior |
|-------|------|----------|
| **10** | **Safety/Security** | Hard constraints. Cannot be overridden. |
| **8**  | **Legal/Compliance** | Mandatory legal requirements. |
| **5**  | **Domain Framework** | Core methodology (e.g., Diataxis structure). |
| **3**  | **Company Style** | Standard internal branding and tone. |
| **1**  | **General Heuristic** | Base principles (e.g., "Signal over Noise"). |

**Precedence Rule**: Higher priority nodes suppress conflicting lower-priority nodes. If priorities are equal, the runtime triggers a **Refinement Loop** to seek a "Balanced Solution."

---

**Inheritance graph**:
```
                    ┌─────────────────┐
                    │   base-writer   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌───────────┐  ┌───────────┐  ┌───────────┐
        │tech-writer│  │ ux-writer │  │legal-writer│
        └─────┬─────┘  └───────────┘  └───────────┘
              │
       ┌──────┴──────┐
       ▼             ▼
  ┌─────────┐  ┌──────────┐
  │acme-docs│  │nvidia-docs│
  └─────────┘  └──────────┘
```

This enables:
- **Shared foundations**: Common heuristics inherited, not duplicated
- **Domain specialization**: Layer on domain-specific expertise
- **Team customization**: Company standards as a layer
- **Composition**: Combine expertise for complex tasks

---

## Architecture

### RAG vs Sunwell Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  RAG PIPELINE                                                        │
│                                                                      │
│  Query ──▶ Embed ──▶ Vector Search ──▶ Retrieve Docs ──▶ Inject ──▶ LLM
│                      (similarity)       (facts)                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  SUNWELL PIPELINE                                                    │
│                                                                      │
│  Query ──▶ Classify ──▶ Graph Walk ──▶ Retrieve ──▶ Inject ──▶ LLM ──▶ Validate
│            (intent)     (routing)      (heuristics)              │      │
│                                                                  │      │
│                                                        ◀─────────┘      │
│                                                     (refinement loop)   │
└─────────────────────────────────────────────────────────────────────────┘
```

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                       SUNWELL RUNTIME                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Classifier │→ │  Retriever  │→ │  Validator  │              │
│  │  (intent)   │  │  (graph)    │  │  (quality)  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│         │                                   │                    │
│         ▼                                   ▼                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    LENS DEFINITION                       │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ │    │
│  │  │ Heuristics│ │ Framework │ │ Personas  │ │Validators│ │    │
│  │  └───────────┘ └───────────┘ └───────────┘ └──────────┘ │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐              │    │
│  │  │ Workflows │ │ Refiners  │ │Provenance │              │    │
│  │  └───────────┘ └───────────┘ └───────────┘              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MODEL PROTOCOL                               │
│         (OpenAI, Anthropic, Local vLLM, Ollama, etc.)           │
└─────────────────────────────────────────────────────────────────┘
```

### RAG Over Expertise: The Core Technical Innovation

Sunwell doesn't just *replace* RAG—it **uses RAG internally** to retrieve relevant expertise from the lens graph. This is the key scalability mechanism.

#### The Problem with Flat Injection

```
FLAT RULES (Cursor, Copilot instructions):

┌─────────────────────────────────────────────────────────────┐
│  rule-1.md (800 tokens)  ───────────────────────┐          │
│  rule-2.md (600 tokens)  ───────────────────────┤          │
│  rule-3.md (500 tokens)  ───────────────────────┤          │
│  rule-4.md (700 tokens)  ───────────────────────┼─► ALL    │
│  rule-5.md (400 tokens)  ───────────────────────┤   INJECTED
│  ...                                            │   EVERY   │
│  rule-20.md (550 tokens) ───────────────────────┘   TIME    │
│                                                             │
│  Token usage grows with rule count (measure in PoC)         │
│  Even when only 3 rules are relevant                        │
└─────────────────────────────────────────────────────────────┘
```

#### The Sunwell Approach: Selective Retrieval

```
SUNWELL (RAG over expertise graph):

┌─────────────────────────────────────────────────────────────────────────┐
│                      EXPERTISE INDEX (Vector DB)                         │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Embedded: heuristic descriptions, validator triggers,          │    │
│  │            persona capabilities, workflow patterns               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              ↑                                          │
│                         Vector search                                   │
│                              │                                          │
│  Query: "Write API docs for auth module"                                │
│                              │                                          │
│                              ▼                                          │
│  Retrieved (semantic match):                                            │
│    ✓ signal-over-noise (800 tokens)                                    │
│    ✓ evidence-required (600 tokens)                                    │
│    ✓ diataxis-reference (500 tokens)                                   │
│    ✗ tutorial-structure (not relevant)                                 │
│    ✗ persona-skeptic (not relevant)                                    │
│    ✗ ... 15 other components (not relevant)                            │
│                                                                          │
│  Injected: only relevant components (measure in PoC)                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Why This Matters

| Metric | Flat Injection | Sunwell (RAG) | Impact (target) |
|--------|----------------|---------------|-----------------|
| **Tokens/request** | Higher | Lower | Measure in PoC |
| **API cost** | Higher | Lower | Measure in PoC |
| **Latency** | Higher | Lower | Measure in PoC |
| **Output quality** | Noise from irrelevant rules | Focused, relevant | Primary benefit |
| **Scalability** | Degrades as rule sets grow | Supports larger component sets | Measure in PoC |

**The token savings are the mechanism. The quality improvement is the value.**

Injecting 50 rules when only 5 are relevant creates noise—the model has to parse everything, decide what's relevant, and may get confused by conflicting rules. Selective retrieval means higher signal-to-noise, which means better outputs.

#### Automatic Discovery

This architecture enables **automatic discovery** of relevant expertise. Given a task prompt, the runtime selects the subset of heuristics, validators, and personas that best match intent and context, instead of requiring manual selection.

This means:
- **Modular POV discovery**: "What perspective should I apply?" → semantic match
- **Skill discovery**: "What capabilities do I need?" → semantic match  
- **Tool discovery**: "What validators should run?" → semantic match

#### Retrieval Mechanism Comparison

| Aspect | Traditional RAG | Sunwell |
|--------|-----------------|---------|
| **Index** | Document embeddings | Expertise component embeddings |
| **Query** | Natural language | Intent + context |
| **Retrieval** | k-nearest documents | Relevant heuristics + validators |
| **Result** | Text chunks (facts) | Expertise nodes (judgment) |

**Traditional RAG**: "How do I authenticate?" → retrieves auth documentation  
**Sunwell**: "Write API docs for auth" → retrieves documentation expertise to *apply*

The key insight: **RAG retrieves what you need to know. Sunwell retrieves how you should think.**

### Component Breakdown

#### 1. Lens Definition

A YAML/Python specification of a professional perspective:

```yaml
lens:
  metadata:
    name: "Technical Writer"
    domain: "documentation"
    version: "1.0.0"
    
  heuristics:
    - name: "Signal over Noise"
      rule: "Every sentence must earn its place"
      test: "Would the user lose info if removed?"
      always: ["Front-load value", "Use concrete examples"]
      never: ["Marketing fluff", "Vague qualifiers"]
      
    # Anti-Heuristics: Define common failure modes to avoid
    anti_heuristics:
      - name: "The Academic Trap"
        description: "Overly formal, passive voice, or theoretical tone"
        triggers: ["Upon conducting", "comprehensive evaluation", "the artifact"]
        correction: "Use PACE tone: Professional, Active, Conversational, Engaging"
```
    name: "Diataxis"
    categories:
      - name: "TUTORIAL"
        purpose: "Learn by doing"
        structure: ["objectives", "prerequisites", "steps"]
        
  personas:
    - name: "novice"
      background: "Technical, new to THIS tool"
      goals: ["Understand what it does", "Get started"]
      friction_points: ["Jargon", "Assumed knowledge"]
      
  validators:
    - name: "no_marketing_fluff"
      check: "Reject 'powerful', 'flexible', 'easy'"
      severity: "warning"
```

#### 2. Lens Runtime

The runtime is responsible for:
- Injecting relevant lens components into the prompt
- Executing the model call
- Running validators on the output
- Running persona-based critiques (optional)
- Producing a response with content, validation results, and confidence

#### 3. Model Interface

The runtime uses a provider-agnostic model interface that supports both full-response and streaming outputs. Specific providers are adapters that implement this interface.

### Integration Points

Sunwell is designed for easy integration. Proposed client surfaces include:
- CLI for scripts and CI/CD
- SDK for applications
- HTTP API for web apps and extensions
- IDE extensions that invoke the runtime under the hood

#### 4. Router

Intent classification and tier-based execution (from DORI's orchestrator). This prevents the "Tax on Everything"—simple tasks shouldn't pay the latency/token price of full expertise retrieval.

| Tier | Name | Target Complexity | Behavior |
|------|------|-------------------|----------|
| **0** | **Fast Path** | Typos, formatting, simple Q&A | No retrieval. No validation. Direct model call. |
| **1** | **Standard** | General content creation | Retrieval active. Basic deterministic validators. |
| **2** | **Deep Lens** | Architecture, audits, high-stakes | Retrieval + Persona testing + Refinement Loop. |

```yaml
router:
  tiers:
    - level: 0
      name: "Fast Path"
      triggers: ["typo", "indent", "format"]
      behavior: 
        retrieval: false
        validation: false
        auto_proceed: true
      
    - level: 2
      name: "Deep Analysis"  
      triggers: ["ambiguous", "architect", "audit"]
      behavior: 
        retrieval: true
        validation: true
        personas: ["skeptic", "expert"]
        require_confirmation: true
```

---

## Portability: Bring Your Expertise Anywhere

The key differentiator from IDE rules: Sunwell lenses are **headless**—they exist independent of any specific tool or platform.

### Distribution Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR EXPERTISE                                │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    tech-writer.lens                          │   │
│   │  (YAML + Python validators + persona definitions)            │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│        ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│        │  Cursor  │   │  VS Code │   │   CLI    │                  │
│        │ Extension│   │ Extension│   │  `sunwell`│                 │
│        └────┬─────┘   └────┬─────┘   └────┬─────┘                  │
│             │              │              │                         │
│             ▼              ▼              ▼                         │
│        ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│        │  Claude  │   │  GPT-4   │   │  Local   │                  │
│        │          │   │          │   │  vLLM    │                  │
│        └──────────┘   └──────────┘   └──────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Portability Scenarios

| Scenario | How it works |
|----------|--------------|
| **Switch IDEs** | Same lens file works in Cursor, VS Code, Vim, web UI |
| **Switch models** | Same lens works with Claude, GPT-4, Llama, local models |
| **Team sharing** | Lens is a git-tracked artifact—version, branch, PR |
| **Cross-project** | Personal lens library travels with you |
| **Offline** | Lens + local model = fully offline professional AI |

### Lens as Portable Identity

Your professional expertise becomes a portable artifact:

```bash
# Your lens library
~/lenses/
├── tech-writer.lens      # Your documentation expertise
├── code-reviewer.lens    # Your code review standards
├── architect.lens        # Your system design principles
└── team-acme.lens        # Company-specific standards (inherited from tech-writer)

# Use anywhere
$ sunwell apply tech-writer --model claude "Write API docs for auth.py"
$ sunwell apply tech-writer --model local/llama "Write API docs for auth.py"

# In any IDE with Sunwell extension
# In any web app using Sunwell API
# In any script calling Sunwell runtime
```

**Your expertise travels with you—not locked to a workspace, IDE, or model.**

### Lens Fount: npm for Professional Expertise

```bash
# Install a community lens
$ sunwell install sunwell/tech-writer

# Install from any fount
$ sunwell install npm:@acme/code-reviewer
$ sunwell install github:jane/sales-email-writer

# Publish your lens
$ sunwell publish my-lens.lens --fount sunwell

# List installed lenses
$ sunwell list
sunwell/tech-writer@1.2.0
sunwell/code-reviewer@2.0.0
./my-custom.lens (local)
```

**Fount Features**:
- **Versioning**: Semantic versioning, lock files
- **Dependencies**: Lenses can depend on other lenses
- **Discovery**: Search by domain, rating, downloads
- **Private founts**: Enterprise self-hosted option

```yaml
# Lens with dependencies
lens:
  metadata:
    name: "ACME API Docs"
    
  extends: "sunwell/tech-writer@^1.0"  # Semver range
  
  dependencies:
    - "sunwell/security-reviewer@2.0"  # Compose with security lens
```

---

## The Vision: An Open Standard for Professional AI

Sunwell isn't a product—it's a **standard** that enables anyone to:

1. **Define** professional expertise as a portable artifact (`.lens` files)
2. **Share** lenses via git, npm, or any package manager
3. **Run** lenses against any model using the Sunwell runtime
4. **Compose** lenses to build specialized expertise from reusable components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         THE SUNWELL ECOSYSTEM                           │
│                                                                          │
│   YOU                    COMMUNITY                  SUNWELL              │
│   ┌─────────────┐        ┌─────────────┐           ┌─────────────┐      │
│   │ Your        │        │ Published   │           │ Runtime     │      │
│   │ .lens files │───────▶│ Lens        │──────────▶│ (executes   │      │
│   │             │        │ Fount       │           │  lenses)    │      │
│   └─────────────┘        └─────────────┘           └──────┬──────┘      │
│                                                           │             │
│                          ┌────────────────────────────────┼─────────┐   │
│                          ▼                ▼               ▼         │   │
│                    ┌──────────┐     ┌──────────┐    ┌──────────┐   │   │
│                    │  OpenAI  │     │ Anthropic│    │  Local   │   │   │
│                    │  API     │     │  API     │    │  vLLM    │   │   │
│                    └──────────┘     └──────────┘    └──────────┘   │   │
│                                                                     │   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why an Open Standard?

| Approach | Problem |
|----------|---------|
| Proprietary lenses | Vendor lock-in, can't customize |
| Platform-specific rules | Cursor rules don't work in VS Code |
| Prompt libraries | No validation, no composition, no versioning |

**LDL (Lens Definition Language)** is the open standard. **Sunwell runtime** is the reference implementation. Anyone can:
- Create lenses using LDL
- Publish lenses to any fount
- Build alternative runtimes
- Extend the schema

---

## Proof of Concept: DORI

DORI (Documentation Operating Research Intelligence) is the first lens built on Sunwell, proving the architecture works.

| Component | LDL Equivalent | What It Does |
|-----------|----------------|--------------|
| `docs-quality-principles` | `heuristics.principles` | Signal-to-noise, always-apply rules |
| `diataxis-framework` | `framework` | Content classification methodology |
| `persona-*` (4 personas) | `personas` | Adversarial testing from different POVs |
| `docs-audit` | `validators` | Quality gates (deterministic + heuristic) |
| `docs-orchestrator` | `router` | Intent classification, tiered execution |
| `evidence-handling` | `provenance` | Citation and verification patterns |

**DORI proves**: A complex, production-quality expertise system can be expressed as an LDL lens.

---

## Creating Your Own Lens

### Quick Start: Minimal Lens

A lens can be as simple as a few heuristics:

```yaml
# my-first.lens
lens:
  metadata:
    name: "Code Reviewer"
    domain: "software"
    version: "0.1.0"
    
  heuristics:
    principles:
      - name: "Security First"
        rule: "Every code change must consider security implications"
        always: ["Check for injection vulnerabilities", "Validate all inputs"]
        never: ["Trust user input", "Hardcode secrets"]
        
      - name: "Readability"
        rule: "Code is read more than written"
        always: ["Descriptive names", "Small functions", "Comments for why, not what"]
```

Run it:
```bash
$ sunwell apply my-first.lens --model claude "Review this PR: ..."
```

That's it. No infrastructure, no training, no fine-tuning.

### Building Up: Adding Components

As your lens matures, add more components:

```yaml
# code-reviewer.lens (evolved)
lens:
  metadata:
    name: "Senior Code Reviewer"
    version: "1.0.0"
    
  heuristics:
    principles: [...]  # Your core principles
    
  # Add a framework for categorizing reviews
  framework:
    name: "Review Categories"
    categories:
      - name: "SECURITY"
        triggers: ["auth", "crypto", "input", "sql"]
        severity: "blocking"
      - name: "PERFORMANCE"
        triggers: ["loop", "query", "cache", "memory"]
        severity: "important"
      - name: "STYLE"
        triggers: ["naming", "formatting", "comments"]
        severity: "suggestion"
        
  # Add personas to stress-test reviews
  personas:
    - name: "junior_dev"
      background: "New to the codebase"
      goals: ["Understand the change", "Learn patterns"]
      attack_vectors: ["Why is this better than the old way?"]
      
    - name: "security_auditor"
      background: "Paranoid about vulnerabilities"
      attack_vectors: ["What if this input is malicious?", "Where's the sanitization?"]
      
  # Add validators for automated checks
  validators:
    deterministic:
      - name: "lint_check"
        script: "eslint --format json"
        severity: "error"
    heuristic:
      - name: "complexity_check"
        check: "Functions over 50 lines should be split"
        confidence_threshold: 0.8
```

### Composition: Standing on Shoulders

Don't start from scratch—inherit from existing lenses:

```yaml
# acme-reviewer.lens
lens:
  metadata:
    name: "ACME Code Reviewer"
    version: "1.0.0"
    
  extends: "sunwell/code-reviewer@1.0"  # Inherit community lens
  
  # Add company-specific rules
  heuristics:
    principles:
      - name: "ACME Logging Standard"
        rule: "All errors must use AcmeLogger"
        always: ["Include correlation ID", "Use structured logging"]
        
  # Override inherited validators
  validators:
    deterministic:
      - name: "acme_lint"
        script: "acme-lint --strict"  # Company linter
```

Now `acme-reviewer.lens` has all the community best practices PLUS your company standards.

---

## Lens Definition Language (LDL)

### Schema Overview

```yaml
# sunwell-lens-schema.yaml
lens:
  # === METADATA ===
  metadata:
    name: string              # Human-readable name
    domain: string            # Domain identifier
    version: semver           # Semantic version
    description: string       # What this lens does
    
  # === CORE HEURISTICS ===
  # The "three pillars" equivalent - always-active professional principles
  heuristics:
    principles:
      - name: string
        rule: string          # The core principle
        test: string          # How to check compliance
        always: [string]      # Always do these
        never: [string]       # Never do these
        examples:             # Concrete examples
          good: [string]
          bad: [string]
          
    communication:
      tone: [string]          # Communication style
      structure: string       # Output structure pattern
      
  # === DOMAIN FRAMEWORK ===
  # The professional methodology (Diataxis, IRAC, Classical French, etc.)
  framework:
    name: string
    description: string
    classification:
      decision_tree: string   # How to categorize work
      categories:
        - name: string
          purpose: string
          structure: [string]
          includes: [string]
          excludes: [string]
          
  # === PERSONAS ===
  # Stakeholder/audience simulation for testing
  personas:
    - name: string
      description: string
      background: string      # What they know
      goals: [string]         # What they want
      friction_points: [string]  # What frustrates them
      attack_vectors: [string]   # How they critique
      evaluation_prompt: string  # Prompt for persona evaluation
      output_format: string   # How to report findings
      
  # === VALIDATORS ===
  # Quality gates (deterministic + heuristic)
  validators:
    deterministic:            # Script-based, reproducible
      - name: string
        type: "script"
        script: string        # Path or inline
        severity: enum        # error | warning | info
        
    heuristic:                # AI-based, judgment calls
      - name: string
        type: "heuristic"
        check: string         # What to verify
        method: string        # triangulation | pattern_match | checklist
        confidence_threshold: float
        
  # === WORKFLOWS ===
  # Multi-step processes
  workflows:
    - name: string
      trigger: string         # When to use
      steps:
        - name: string
          action: string
          quality_gates: [string]
      state_management: boolean  # Persist across sessions?
      
  # === REFINERS ===
  # Improvement operations
  refiners:
    - name: string
      purpose: string
      when: string            # Conditions
      operations: [string]
      
  # === PROVENANCE ===
  # Evidence/citation patterns
  provenance:
    format: string            # "file:line" or domain equivalent
    types: [string]           # Evidence categories
    requirements:
      - context: string
        required: boolean
        
  # === ROUTER ===
  # Orchestration rules
  router:
    tiers:
      - level: int
        name: string
        triggers: [string]
        behavior:
          show_analysis: boolean
          require_confirmation: boolean
          
    intent_classification:
      categories: [string]
      signals: object         # keyword → intent mapping

  # === QUALITY POLICY ===
  # Confidence scoring and gate requirements
  quality_policy:
    min_confidence: float     # Overall score required to pass
    required_validators: [string] # These MUST pass
    persona_agreement: float  # Min % of personas that must approve
    retry_limit: int          # Max refinement loops
```

---

## Example Lenses

### Technical Writer Lens (DORI)

```yaml
lens:
  metadata:
    name: "Technical Writer"
    domain: "documentation"
    version: "1.0.0"
    
  heuristics:
    principles:
      - name: "Signal over Noise"
        rule: "Every sentence must earn its place"
        test: "Would the user lose information if this was removed?"
        always:
          - "Front-load the most important information"
          - "Use concrete examples with real code"
          - "Provide file:line references for claims"
        never:
          - "Marketing language (powerful, flexible, easy)"
          - "Vague qualifiers (many, various, different)"
          - "Theoretical advice without evidence"
        examples:
          good: ["This API supports batch operations up to 1,000 items"]
          bad: ["Our powerful API makes batch processing easy"]
          
      - name: "Evidence Required"
        rule: "Claims must be verifiable"
        test: "Can I find the source for this claim?"
        always:
          - "Include file:line references"
          - "Show code examples from actual source"
          - "Triangulate from multiple sources"
        never:
          - "Make claims without checking source"
          - "Copy from outdated docs without verifying"
          
  framework:
    name: "Diataxis"
    classification:
      categories:
        - name: "TUTORIAL"
          purpose: "Learn by doing guided lesson"
          structure: ["objectives", "prerequisites", "steps", "next_steps"]
          includes: ["learning objectives", "guided steps", "expected outcomes"]
          excludes: ["reference tables", "all options", "why explanations"]
          
        - name: "HOW_TO"
          purpose: "Accomplish specific task"
          structure: ["goal", "prerequisites", "steps", "troubleshooting"]
          includes: ["goal statement", "practical steps", "common issues"]
          excludes: ["concept teaching", "complete reference"]
          
        - name: "EXPLANATION"
          purpose: "Understand concepts/architecture"
          structure: ["context", "how_it_works", "components", "integration"]
          includes: ["concepts", "why/how", "design rationale"]
          excludes: ["step-by-step instructions", "complete options"]
          
        - name: "REFERENCE"
          purpose: "Look up specific information"
          structure: ["purpose", "categories", "comprehensive_listings"]
          includes: ["all options", "technical specs", "tables"]
          excludes: ["conceptual explanations", "tutorials"]
          
  personas:
    - name: "novice"
      description: "Technical user new to THIS specific tool"
      background: "Knows APIs, terminals, codebases. Doesn't know THIS tool."
      goals: ["Understand what it does", "Get started quickly"]
      friction_points: ["Tool-specific jargon", "Assumed knowledge", "Missing steps"]
      attack_vectors:
        - "You said 'run ::a' but where do I type this?"
        - "What's the minimum setup needed?"
        
    - name: "skeptic"
      description: "Senior dev who's seen many tools fail"
      background: "Deep technical knowledge, high standards"
      goals: ["Understand tradeoffs", "See proof it works"]
      friction_points: ["Marketing speak", "Missing edge cases", "No benchmarks"]
      attack_vectors:
        - "What happens at scale?"
        - "Show me the failure modes"
        
    - name: "pragmatist"
      description: "Busy developer who just wants to copy-paste"
      background: "Competent, time-pressured"
      goals: ["Working code NOW", "Minimal reading"]
      friction_points: ["Long explanations before code", "Incomplete examples"]
      attack_vectors:
        - "Can I copy this and have it work?"
        - "Where's the TL;DR?"
        
  validators:
    deterministic:
      - name: "syntax_check"
        script: "validate_code_blocks.py"
        severity: "error"
        
      - name: "link_check"
        script: "verify_links.py"
        severity: "error"
        
    heuristic:
      - name: "no_marketing_fluff"
        check: "Reject sentences with 'powerful', 'flexible', 'easy', 'robust'"
        method: "pattern_match"
        confidence_threshold: 0.9
        
      - name: "evidence_required"
        check: "Technical claims must have file:line references"
        method: "pattern_match"
        confidence_threshold: 0.8
```

### More Example Lenses

These examples show how LDL applies across domains:

#### Legal Contract Reviewer

```yaml
lens:
  metadata:
    name: "Contract Reviewer"
    domain: "legal"
    
  heuristics:
    principles:
      - name: "Risk Identification"
        rule: "Every clause must be assessed for risk exposure"
        always: ["Flag liability caps", "Note indemnification", "Check termination terms"]
        never: ["Assume boilerplate is safe", "Skip definitions section"]
        
  framework:
    name: "IRAC"  # Issue, Rule, Application, Conclusion
    categories:
      - name: "LIABILITY"
        triggers: ["indemnif", "damages", "liable"]
        severity: "critical"
      - name: "TERMINATION"
        triggers: ["terminate", "breach", "cure period"]
        severity: "high"
        
  personas:
    - name: "opposing_counsel"
      attack_vectors: ["How would I exploit this clause?", "What's ambiguous here?"]
    - name: "business_stakeholder"
      attack_vectors: ["What does this actually mean for us?", "What's the worst case?"]
```

#### Data Scientist Notebook Reviewer

```yaml
lens:
  metadata:
    name: "Notebook Reviewer"
    domain: "data-science"
    
  heuristics:
    principles:
      - name: "Reproducibility"
        rule: "Anyone should be able to rerun this notebook and get the same results"
        always: ["Set random seeds", "Pin library versions", "Document data sources"]
        never: ["Hardcode file paths", "Skip data validation steps"]
        
      - name: "Leakage Prevention"
        rule: "Training data must never leak into validation"
        always: ["Split before preprocessing", "Use pipelines", "Check feature timing"]
        
  validators:
    deterministic:
      - name: "cell_execution_order"
        script: "nbqa check-order"
        severity: "error"
    heuristic:
      - name: "no_data_leakage"
        check: "Train/test split happens before any feature engineering"
        
  personas:
    - name: "skeptical_reviewer"
      attack_vectors: ["Can I reproduce this?", "Is this p-hacking?", "What's the baseline?"]
```

#### Sales Email Writer

```yaml
lens:
  metadata:
    name: "Sales Email Writer"
    domain: "sales"
    
  heuristics:
    principles:
      - name: "Value First"
        rule: "Lead with what they get, not what you're selling"
        always: ["Specific benefit in first line", "Quantify value", "One clear CTA"]
        never: ["Start with 'I'", "Generic opener", "Multiple asks"]
        
  framework:
    name: "AIDA"  # Attention, Interest, Desire, Action
    categories:
      - name: "COLD_OUTREACH"
        structure: ["hook", "pain_point", "solution_tease", "soft_cta"]
      - name: "FOLLOW_UP"
        structure: ["context_reminder", "new_value", "clear_ask"]
        
  personas:
    - name: "busy_executive"
      background: "Gets 200 emails/day, 3 seconds to decide"
      attack_vectors: ["Why should I care?", "What's in it for me?"]
```

These examples demonstrate: **LDL works for any domain where professional judgment matters.**

---

## Implementation Plan

### Phase 1: Open Source Foundation (Weeks 1-4)

| Task | Deliverable | Validates |
|------|-------------|-----------|
| LDL schema spec | `ldl-spec.md` + JSON Schema | Standard is documented |
| Reference runtime | `sunwell-py` (MIT license) | Runtime works |
| CLI tool | `sunwell` CLI | Developer experience |
| Port DORI to LDL | `lenses/tech-writer.lens` | Real-world lens works |

**Exit criteria**: 
- `pip install sunwell` works
- `sunwell apply tech-writer.lens "prompt"` produces output
- LDL spec is published and versionable

### Phase 2: Ecosystem Tools (Weeks 5-8)

| Task | Deliverable | Validates |
|------|-------------|-----------|
| Persona evaluation | `sunwell test --personas` | Validation loop works |
| Multi-model support | OpenAI, Anthropic, Ollama | Model agnosticism |
| Lens validator | `sunwell validate my.lens` | Schema enforcement |
| VS Code extension | `sunwell-vscode` | IDE integration |

**Exit criteria**:
- Works with 3+ model providers
- Can validate lens syntax before runtime
- IDE extension provides inline lens application

### Phase 3: Community & Registry (Weeks 9-12)

| Task | Deliverable | Validates |
|------|-------------|-----------|
| Lens fount | `fount.sunwell.ai` | Distribution works |
| Community lenses | 5+ contributed lenses | Others can create lenses |
| `extends` support | Lens inheritance | Composition works |
| Documentation site | `docs.sunwell.ai` | Onboarding works |

**Exit criteria**:
- `sunwell install sunwell/code-reviewer` works
- At least 3 external contributors have published lenses
- Inheritance chain works (base → domain → company)

### Phase 4: Scale (Weeks 13-16)

| Task | Deliverable | Validates |
|------|-------------|-----------|
| Managed API | `api.sunwell.ai` | Hosted option |
| Private registries | Enterprise self-host | Enterprise adoption |
| Cursor extension | Native Cursor integration | IDE market |
| Analytics | Usage metrics | Product-market fit |

**Exit criteria**:
- 100+ public lenses in fount
- 10+ organizations using Sunwell
- Clear revenue path established

---

## Technical Decisions

### Why RAG Over the Expertise Graph?

The retrieval mechanism is the core technical differentiator:

| Alternative | Why Not |
|-------------|---------|
| **Flat injection** | Doesn't scale—context bloat at 50+ rules |
| **Manual selection** | Burden on user—defeats automation |
| **Keyword matching** | Too brittle—misses semantic relevance |
| **LLM-based routing** | Too slow—adds latency to every request |
| **Vector search (RAG)** | ✅ Fast, semantic, scales to 1000+ |

**Implementation**:
On lens load, embed each component’s description and triggers into a vector index. For each request, embed the task prompt and retrieve the top‑k components to inject.

**Why this scales**:
- Embedding is done once per lens
- Retrieval is done per request
- Only relevant components are injected

### Why Python 3.14 Free-Threaded?

Free‑threaded Python enables true parallelism for validation and persona testing when those operations are CPU‑bound. This is an implementation option, not a dependency.

### Why YAML for Lens Definitions?

- **Human readable**: Domain experts can read/edit
- **Version controllable**: Git-friendly
- **Extensible**: Easy to add new fields
- **Tooling**: Good editor support

Python fallback for complex logic:

```yaml
validators:
  - name: "custom_check"
    type: "python"
    module: "my_lens.validators"
    function: "check_flavor_balance"
```

### Why Protocol-Based Model Interface?

```python
class ModelProtocol(Protocol):
    async def generate(self, prompt: str) -> str: ...
```

- **Swap models**: OpenAI today, local tomorrow
- **Test with mocks**: Fast unit tests
- **Multi-model**: Compare outputs across models

---

## Business Model: Open Core

### Philosophy

**LDL is open. The ecosystem around it creates value.**

| Component | Model | Rationale |
|-----------|-------|-----------|
| **LDL Schema** | Open source (MIT) | Standard must be free to enable adoption |
| **Sunwell Runtime** | Open source (MIT) | Reference implementation, encourage contributions |
| **CLI Tools** | Open source | Developer experience drives adoption |
| **Lens Registry** | Freemium | Free for public lenses, paid for private |
| **Managed API** | Usage-based | Convenience for teams that don't want to self-host |
| **Enterprise** | License | Support, SLAs, custom lens development |

### Revenue Streams

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          REVENUE MODEL                                   │
│                                                                          │
│  OPEN (Free)                    PAID                                    │
│  ┌─────────────────┐            ┌─────────────────────────────────┐     │
│  │ • LDL Schema    │            │ • Private lens hosting          │     │
│  │ • Runtime       │            │ • Managed API (per-request)     │     │
│  │ • CLI           │            │ • Enterprise support            │     │
│  │ • Public lenses │            │ • Custom lens development       │     │
│  └─────────────────┘            │ • Lens marketplace commission   │     │
│                                 └─────────────────────────────────┘     │
│                                                                          │
│  Adoption ──────────────────────▶ Network effects ────▶ Monetization   │
└─────────────────────────────────────────────────────────────────────────┘
```

1. **Lens Registry** (npm for lenses):
   - Free: Publish/consume public lenses
   - Paid: Private lenses, team features, analytics

2. **Managed API** (convenience):
   - Usage-based pricing
   - No infrastructure to manage
   - Multiple models supported

3. **Enterprise**:
   - Self-hosted deployment support
   - Custom lens development services
   - SLAs and priority support

4. **Marketplace** (future):
   - Third-party lens sales
   - Revenue share with lens authors

### Why Open Source the Core?

| Open | Result |
|------|--------|
| Schema | Lenses are portable, not locked to us |
| Runtime | Anyone can build integrations |
| CLI | Developers adopt without procurement |

**Network effects**: Every public lens makes the ecosystem more valuable. `acme-docs.lens` extends `tech-writer.lens` extends `base-writer.lens`. Switching costs compound as the inheritance chain grows.

### Competitive Position

| Competitor | What they do | Sunwell difference |
|------------|--------------|-------------------|
| Fine-tuning | Bake knowledge in | External, swappable, instant |
| RAG vendors | Retrieve facts | **Retrieve judgment, not facts** |
| Prompt libraries | One-shot context | **Open standard, composable, validated** |
| IDE rules (Cursor) | Static workspace rules | **Headless, portable, model-agnostic** |
| Proprietary AI tools | Closed systems | **Open standard, community-driven** |

### Moat Analysis

| Layer | Defensibility | Notes |
|-------|---------------|-------|
| **Standard adoption** | High | First-mover on "RAG for judgment" framing |
| **Lens ecosystem** | High | Network effects from composition |
| **Community** | High | Expertise contributed by domain experts |
| **Runtime quality** | Medium | Can be replicated, but trust takes time |
| **Integration depth** | High | IDE extensions, CI/CD integrations |

**Primary moat**: The lens ecosystem. Once there are 1000+ public lenses with inheritance relationships, the network effect is insurmountable.

---

## Open Questions

1. **Schema evolution**: How do we version LDL while maintaining backward compatibility? JSON Schema versioning patterns?

2. **Lens quality**: How do we surface "good" lenses in the fount? Rating systems? Certification?

3. **Conflict resolution**: When composing lenses, how do we resolve conflicting heuristics? Priority rules? User choice?

4. **Local-first**: Should lenses be fully offline-capable, or can they reference external resources?

5. **Governance**: Who decides what goes into the LDL spec? RFC process? Foundation?

6. **Testing**: How do we test that a lens "works"? Benchmark datasets per domain? Community test suites?

---

## Success Criteria

### Phase 1: Foundation
- [ ] LDL spec published with JSON Schema
- [ ] `pip install sunwell` works
- [ ] DORI fully expressed as a `.lens` file
- [ ] Works with at least OpenAI

### Phase 2: Ecosystem Tools
- [ ] Works with OpenAI, Anthropic, and local models (Ollama/vLLM)
- [ ] `sunwell validate` catches schema errors
- [ ] IDE extension provides basic functionality

### Phase 3: Community
- [ ] Registry has 10+ public lenses
- [ ] 3+ external contributors have published lenses
- [ ] Lens inheritance (`extends`) works across registries
- [ ] Documentation enables self-service lens creation

### Phase 4: Scale
- [ ] 100+ public lenses
- [ ] 1000+ weekly active `sunwell` CLI users
- [ ] At least one enterprise deployment
- [ ] Clear path to sustainability (revenue or sponsorship)

---

## Appendix A: DORI → Sunwell Migration Path

DORI is the first production-grade lens. Below is the mapping from DORI's `.cursor/rules` structure to the Sunwell LDL:

| DORI Component | Sunwell LDL Mapping | Migration Status |
|----------------|---------------------|------------------|
| `docs-quality-principles` | `heuristics.principles` | Ready |
| `docs-communication-style`| `heuristics.communication`| Ready |
| `diataxis-framework`      | `framework` | Ready |
| `persona-novice/skeptic`  | `personas` | Ready |
| `docs-audit`              | `validators.heuristic` | In-progress |
| `docs-health`             | `validators.deterministic` | Ready |
| `docs-orchestrator`       | `router` | Planned |
| `evidence-handling`       | `provenance` | Ready |

```
prompt-library/.cursor/rules/
├── modules/                    → lens.heuristics + lens.provenance
│   ├── docs-quality-principles → heuristics.principles
│   ├── docs-communication-style→ heuristics.communication
│   ├── diataxis-framework     → framework
│   ├── evidence-handling      → provenance
│   └── validation-patterns    → validators.heuristic
├── personas/                   → lens.personas
│   ├── persona-novice         → personas[0]
│   ├── persona-skeptic        → personas[1]
│   └── ...
├── validation/                 → lens.validators
│   ├── docs-audit             → validators.heuristic
│   └── docs-health            → validators.deterministic
├── workflows/                  → lens.workflows
│   ├── docs-writing-workflow  → workflows[0]
│   └── docs-pipeline          → workflows[1]
├── system/                     → lens.router
│   └── docs-orchestrator      → router
└── transformation/             → lens.refiners
    ├── docs-polish            → refiners[0]
    └── docs-modularize        → refiners[1]
```

---

## Appendix B: Name Origin

**Sunwell**: A source of light and clarity.

- **Sun**: Illumination, clarity, seeing things as they are
- **Well**: A source, something you draw from
- **Combined**: A source of clear vision

The lens metaphor extends naturally: Sunwell provides the lenses through which AI sees clearly.

---

## References

- [Diataxis Framework](https://diataxis.fr/) — Documentation methodology used in DORI
- [Python 3.14 Free-Threaded](https://docs.python.org/3.14/whatsnew/3.14.html) — No-GIL Python
- DORI Implementation — `prompt-library/.cursor/rules/`

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-15 | Initial draft |
