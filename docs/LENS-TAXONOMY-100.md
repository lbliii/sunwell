# RFC-100: Sunwell Lens Taxonomy

**Status**: Draft  
**Version**: 1.0.0  
**Author**: Sunwell Team  
**Created**: 2026-01-23

---

## Executive Summary

This RFC proposes expanding Sunwell's lens library from **11 lenses to 100 lenses** across **12 domains**. The goal is comprehensive domain coverage for AI coding assistants (ACPs), enabling specialized expertise for any development task.

**Current state**: 11 lenses in `lenses/` directory  
**Proposed state**: 100 lenses with full ACP domain coverage  
**Timeline**: 12 weeks across 3 phases

---

## Problem Statement

### Current Limitations

Sunwell currently ships with **11 lenses** (`src/sunwell/lenses/`):

```
base-writer.lens, code-reviewer.lens, coder.lens, helper.lens,
team-dev.lens, team-pm.lens, team-qa.lens, team-writer.lens,
tech-writer-large-model.lens, tech-writer-refined.lens, tech-writer.lens
```

**Gaps identified**:

1. **Language coverage**: No language-specific lenses (Python, TypeScript, Go, Rust)
2. **Framework coverage**: No framework-specific lenses (React, FastAPI, Django)
3. **Specialized domains**: No security, ML/data, DevOps, or infrastructure lenses
4. **Domain depth**: Documentation has 5 variants; other domains have 1-2

### User Impact

| Scenario | Current Behavior | With 100 Lenses |
|----------|------------------|-----------------|
| Python code review | Generic `code-reviewer.lens` | `python-expert.lens` with ruff/ty patterns |
| React development | Generic `coder.lens` | `react-expert.lens` with RSC/hooks patterns |
| Security audit | Generic `code-reviewer.lens` | `security-auditor.lens` with OWASP |
| Terraform review | Generic `coder.lens` | `terraform-expert.lens` with IaC patterns |

### Evidence of Demand

The lens selection system (`src/sunwell/surface/lens_detection.py:16-21`) currently maps to only 4 base domains:

```python
DOMAIN_LENS_MAP: dict[str, str] = {
    "documentation": "tech-writer.lens",
    "software": "coder.lens",
    "planning": "team-pm.lens",
    "data": "coder.lens",
}
```

This coarse mapping loses valuable domain context available in the router system (`src/sunwell/adaptive/lens_resolver.py:113-126`).

---

## Goals

1. **Complete domain coverage**: Lenses for every common ACP task
2. **Specialized expertise**: Language, framework, and domain-specific patterns
3. **Measurable quality**: 20%+ output improvement vs. generic prompts
4. **Token efficiency**: 30%+ reduction through focused heuristics
5. **Maintainable catalog**: Clear inheritance, versioning, and testing

## Non-Goals

1. **Hyper-specific lenses**: Not creating `django-3.2-postgresql-on-aws.lens`
2. **Replacing composition**: Lenses should compose, not duplicate
3. **100% coverage**: Some niche domains can use nearest general lens
4. **Auto-generation**: All lenses are hand-crafted with expert heuristics

---

## Design Alternatives

### Option A: Build All 100 Lenses (Proposed)

Build comprehensive library of 100 specialized lenses.

**Pros**:
- Maximum coverage and expertise depth
- Clear domain boundaries
- Easy discovery and selection

**Cons**:
- High initial development cost (12 weeks)
- Maintenance burden for updates
- Risk of quality inconsistency

### Option B: 20-30 Core Lenses + Composition

Build fewer lenses that compose together.

**Pros**:
- Lower maintenance burden
- More flexible combinations
- Faster initial development

**Cons**:
- Composition complexity for users
- Performance overhead for multi-lens resolution
- Less discoverable than single-purpose lenses

### Option C: Dynamic Lens Generation

Generate specialized lenses on-demand from primitives.

**Pros**:
- Unlimited combinations
- Always up-to-date with latest patterns
- Lower storage requirements

**Cons**:
- Inconsistent quality
- Requires LLM call for lens generation
- Harder to test and validate

### Option D: Community Marketplace

Build core lenses; enable community contributions.

**Pros**:
- Scales beyond team capacity
- Domain experts contribute directly
- Diverse perspectives

**Cons**:
- Quality control challenges
- Versioning complexity
- Support burden

### Recommendation

**Option A** for foundation, with **Option D** as future phase.

Rationale:
- Need high-quality foundation before community contributions
- 100 lenses is achievable with clear template (`tech-writer.lens` as reference)
- Composition already supported via `extends` and `compose` fields

---

## Architecture Impact

### Lens Resolution Flow

```
User Goal → LensResolver → LensDiscovery → Domain Classification → Lens Selection
                                                ↓
                            src/sunwell/adaptive/lens_resolver.py:30-134
```

**No changes required** to resolution logic. New lenses are discovered automatically from `search_paths`.

### Lens Data Model

The `Lens` class (`src/sunwell/core/lens.py:165-299`) already supports:

- ✅ `extends` / `compose` for inheritance (line 181-182)
- ✅ `heuristics` / `anti_heuristics` (line 185-186)
- ✅ `framework` for methodology (line 190)
- ✅ `personas` for adversarial testing (line 193)
- ✅ `validators` for quality gates (line 196-197)
- ✅ `skills` for actions (line 213)
- ✅ `router` with shortcuts (line 207)
- ✅ `scanner` for state DAG (via `affordances`, line 250)

**No schema changes required.**

### Domain Detection

Current `lens_detection.py` maps 4 domains. With 100 lenses, expand to:

```python
# Proposed expansion to DOMAIN_LENS_MAP
DOMAIN_LENS_MAP: dict[str, str] = {
    "documentation": "tech-writer.lens",
    "software": "coder.lens",
    "planning": "team-pm.lens",
    "data": "data-pipeline-expert.lens",  # NEW
    "security": "security-auditor.lens",  # NEW
    "devops": "docker-expert.lens",       # NEW
    "ml": "ml-experimenter.lens",         # NEW
}
```

### Storage Impact

Each `.lens` file is ~20-50KB YAML. 100 lenses ≈ 2-5MB total.

- Loaded on-demand via `LensLoader` (`src/sunwell/schema/loader.py:56`)
- Cached via `LensIndexManager` (`src/sunwell/lens/index.py:103`)
- No memory concern for inactive lenses

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Quality inconsistency across 100 lenses | High | Medium | S-tier template, automated validators |
| Maintenance burden for framework updates | High | High | Version pinning, community contributions |
| User overwhelm with too many choices | Medium | Medium | Smart auto-selection, clear categories |
| Test coverage gaps | Medium | High | Automated lens validation suite |
| Outdated heuristics | High | Medium | Quarterly review cycle, deprecation policy |

### Mitigation Strategy

1. **Template enforcement**: All lenses must pass schema validation
2. **Automated testing**: Each lens tested against task corpus
3. **Freshness tracking**: Scanner probes detect stale content
4. **Clear ownership**: Each domain has designated maintainer

---

## Priority Definitions

| Level | Meaning | Timeline |
|-------|---------|----------|
| P0 | Core functionality, ship in Phase 1 | Weeks 1-4 |
| P1 | Important coverage, ship in Phase 2 | Weeks 5-8 |
| P2 | Nice-to-have, ship in Phase 3 | Weeks 9-12 |
| P3 | Future/community, post-launch | After v1.0 |

---

## Taxonomy Overview

| Category | Count | Priority | Description |
|----------|-------|----------|-------------|
| [Documentation](#1-documentation-10-lenses) | 10 | P0 | Technical writing, API docs, content types |
| [Code Quality](#2-code-quality--review-10-lenses) | 10 | P0 | Review, linting, standards enforcement |
| [Languages](#3-language-experts-15-lenses) | 15 | P0-P1 | Language-specific idioms and patterns |
| [Frameworks](#4-framework-experts-15-lenses) | 15 | P1 | Framework-specific best practices |
| [Testing](#5-testing--qa-8-lenses) | 8 | P0-P1 | Test generation, coverage, QA |
| [Architecture](#6-architecture--design-8-lenses) | 8 | P1 | System design, patterns, refactoring |
| [DevOps](#7-devops--infrastructure-10-lenses) | 10 | P1-P2 | CI/CD, containers, cloud, IaC |
| [Data & ML](#8-data--ml-10-lenses) | 10 | P1-P2 | Data science, ML, analytics |
| [Security](#9-security-6-lenses) | 6 | P0 | AppSec, auditing, compliance |
| [Business](#10-business--product-8-lenses) | 8 | P2 | PM, strategy, communications |
| [Creative](#11-creative-writing-6-lenses) | 6 | P3 | Fiction, marketing, UX writing |
| [Specialized](#12-specialized-domains-4-lenses) | 4 | P3 | Legal, academic, finance, medical |

---

## S-Tier Lens Template

Every lens should include these components:

```yaml
lens:
  metadata:
    name: ""
    domain: ""
    version: "1.0.0"
    description: ""
    author: "Sunwell Team"
    license: "MIT"
    use_cases: []
    tags: []

  # HEURISTICS — How to Think (40% of value)
  heuristics:
    principles: []      # 6-10 domain rules with always/never/examples
    anti_heuristics: [] # 3-5 traps to avoid
    communication: {}   # PACE tone configuration

  # FRAMEWORK — Methodology (20% of value)
  framework:
    name: ""
    decision_tree: ""
    categories: []

  # PERSONAS — Adversarial Testing (15% of value)
  personas: []          # 3-5 hostile reader archetypes

  # VALIDATORS — Quality Gates (10% of value)
  validators:
    deterministic: []   # grep-based hard checks
    heuristic: []       # AI-assisted soft checks

  # ROUTER — Intent Routing (5% of value)
  router:
    shortcuts: {}
    tiers: []

  # SKILLS — Action Capabilities (10% of value)
  skills: []

  # SCANNER — State DAG (optional)
  scanner:
    detect_markers: []
    health_probes: []
```

---

## 1. Documentation (10 Lenses)

### 1.1 `tech-writer` ✅ EXISTS

**Status**: S-tier (reference implementation)  
**Domain**: Technical Documentation  
**Extends**: —  
**Source**: `lenses/tech-writer.lens`

```yaml
key_differentiators:
  - Diataxis framework integration (framework.name: "Diataxis")
  - 7 heuristics including Signal over Noise, PACE Communication
  - 4 adversarial personas (novice, skeptic, pragmatist, expert)
  - 2 validators (deterministic + heuristic)
  - Complete skill library with shortcuts (::a, ::p, ::m, etc.)
  - Scanner for documentation State DAG

# Evidence: lenses/tech-writer.lens:26-127 (heuristics)
# Evidence: lenses/tech-writer.lens:282-347 (personas)
# Evidence: lenses/tech-writer.lens:457-477 (router shortcuts)
```

---

### 1.2 `api-documenter`

**Status**: To Build  
**Domain**: API Reference Documentation  
**Extends**: `tech-writer`

```yaml
focus: "REST/GraphQL/gRPC API documentation"

heuristics:
  principles:
    - name: "Request-Response Pairs"
      rule: "Every endpoint shows complete request AND response"
      always:
        - "Include authentication headers"
        - "Show all required parameters"
        - "Include realistic example values"
        - "Show success AND error responses"
      never:
        - "Abstract parameter descriptions without examples"
        - "Missing error codes"
        - "Placeholder values like 'string' or 'number'"
      examples:
        good: |
          POST /users
          Authorization: Bearer <token>
          {"name": "Jane", "email": "jane@example.com"}
          
          201 Created
          {"id": "usr_123", "name": "Jane", ...}
        bad: |
          POST /users
          Request body: user object

    - name: "Auth First"
      rule: "Authentication section appears before any endpoints"
      always:
        - "Show how to obtain credentials"
        - "Include token refresh flow"
        - "Document scopes/permissions"
      never:
        - "Bury auth in appendix"
        - "Assume reader knows the auth mechanism"

    - name: "Error Catalog"
      rule: "Every possible error has its own section"
      always:
        - "HTTP status code"
        - "Error code (machine-readable)"
        - "Error message (human-readable)"
        - "Resolution steps"
      never:
        - "Generic 'An error occurred'"
        - "Missing resolution guidance"

    - name: "Schema as Source of Truth"
      rule: "Types come from code, not imagination"
      always:
        - "Generate from OpenAPI/GraphQL schema"
        - "Show field types explicitly"
        - "Mark required vs optional"
        - "Include validation constraints"
      never:
        - "Hand-write schemas"
        - "Let docs drift from code"

    - name: "Pagination Patterns"
      rule: "Collection endpoints document pagination completely"
      always:
        - "Show cursor/offset parameters"
        - "Document max page size"
        - "Include next/prev navigation"
      never:
        - "Assume pagination is obvious"

    - name: "Rate Limiting Transparency"
      rule: "Document limits before users hit them"
      always:
        - "Requests per minute/hour"
        - "Headers indicating remaining quota"
        - "429 response handling"

  anti_heuristics:
    - name: "Endpoint Soup"
      triggers: ["no grouping", "alphabetical only", "flat list"]
      correction: "Group by resource/domain, not alphabetically"
    
    - name: "Swagger Dump"
      triggers: ["auto-generated only", "no examples", "no context"]
      correction: "Auto-generate structure, hand-craft examples"

framework:
  name: "OpenAPI-Aligned"
  categories:
    - name: "AUTHENTICATION"
      sections: [overview, obtaining_tokens, refresh, scopes]
    - name: "ENDPOINTS"
      sections: [resource_groups, operations, parameters, responses]
    - name: "SCHEMAS"
      sections: [models, enums, validation]
    - name: "ERRORS"
      sections: [error_format, error_codes, troubleshooting]
    - name: "WEBHOOKS"
      sections: [events, payload_format, verification, retry_policy]

personas:
  - name: "first_integration"
    description: "Developer making their first API call"
    background: "Knows HTTP, unfamiliar with THIS API"
    goals:
      - "Make successful authenticated request in < 5 minutes"
      - "Understand data model"
    friction_points:
      - "Can't find auth instructions"
      - "Examples don't work"
      - "Missing required fields"
    attack_vectors:
      - "I copied this exactly and got 401"
      - "What format is the date supposed to be?"
      - "Where do I get the API key?"

  - name: "sdk_builder"
    description: "Building client library from docs"
    background: "Expert developer, needs complete type information"
    goals:
      - "Generate accurate type definitions"
      - "Handle all error cases"
      - "Implement pagination correctly"
    attack_vectors:
      - "Is this field nullable?"
      - "What's the max length?"
      - "Are there undocumented fields?"

  - name: "security_reviewer"
    description: "Auditing API for security issues"
    background: "Security engineer reviewing integration"
    goals:
      - "Verify auth is properly documented"
      - "Check for sensitive data exposure"
      - "Understand rate limiting"
    attack_vectors:
      - "Can I enumerate users through this endpoint?"
      - "What data is in error messages?"
      - "Is there audit logging?"

validators:
  deterministic:
    - name: "has_auth_section"
      script: "grep -i 'authentication\\|authorization'"
      severity: "error"
    - name: "has_example_responses"
      script: "grep -E '(200|201|400|401|404|500)'"
      severity: "warning"

  heuristic:
    - name: "example_completeness"
      check: "Every endpoint has request AND response example"
      confidence_threshold: 0.85
    - name: "error_documentation"
      check: "All error codes have resolution steps"
      confidence_threshold: 0.8

skills:
  - name: "extract-openapi"
    description: "Generate OpenAPI spec from codebase"
    triggers: ["openapi", "swagger", "generate spec"]
    
  - name: "generate-examples"
    description: "Create realistic request/response pairs"
    triggers: ["examples", "sample requests"]
    
  - name: "validate-sync"
    description: "Check docs match actual API behavior"
    triggers: ["validate", "sync check", "drift"]

  - name: "generate-sdk-types"
    description: "Generate TypeScript/Python types from spec"
    triggers: ["types", "sdk", "client"]

scanner:
  detect_markers:
    - openapi.yaml
    - openapi.json
    - swagger.yaml
    - swagger.json
    - "*/routes/*"
    - "*/api/*"
    - "*/endpoints/*"
  
  health_probes:
    - name: "endpoint_documented"
      description: "Every route has corresponding docs"
      severity: "error"
    - name: "schema_has_examples"
      description: "Schema definitions include examples"
      severity: "warning"
    - name: "auth_documented"
      description: "Auth mechanism fully documented"
      severity: "error"

router:
  shortcuts:
    "::api": "Document API endpoint"
    "::endpoint": "Generate endpoint documentation"
    "::schema": "Document data schema"
    "::errors": "Generate error catalog"
```

---

### 1.3 `readme-crafter`

**Status**: To Build  
**Domain**: Project README Files  
**Extends**: `tech-writer`

```yaml
focus: "Project README files that get people started fast"

heuristics:
  principles:
    - name: "30-Second Value"
      rule: "Reader knows if this solves their problem in 30 seconds"
      always:
        - "One-sentence description at top"
        - "Clear 'what it does' before 'how'"
        - "Quick start within first scroll"
      never:
        - "Long backstory before features"
        - "Installation before explaining what it is"

    - name: "Copy-Paste Install"
      rule: "Installation works on first try"
      always:
        - "One command to install"
        - "Platform-specific tabs if needed"
        - "Version requirements explicit"
      never:
        - "Assume dependencies are installed"
        - "Multiple steps without explanation"

    - name: "Minimum Viable Example"
      rule: "Show working code in < 10 lines"
      always:
        - "Complete, runnable example"
        - "Expected output shown"
        - "All imports included"
      never:
        - "Snippets that won't run"
        - "Examples requiring setup not shown"

    - name: "Badge Hygiene"
      rule: "Badges provide useful status, not decoration"
      always:
        - "CI status"
        - "Version/release"
        - "License"
      never:
        - "More than 6 badges"
        - "Decorative badges"
        - "Broken badge links"

framework:
  name: "README Structure"
  sections:
    - title_and_badges
    - one_line_description
    - quick_start
    - installation
    - usage_examples
    - configuration
    - api_reference_link
    - contributing
    - license

personas:
  - name: "tire_kicker"
    description: "Evaluating if this solves their problem"
    attack_vectors:
      - "What does this actually do?"
      - "Is this maintained?"
      - "Is this production-ready?"

  - name: "impatient_user"
    description: "Wants working code NOW"
    attack_vectors:
      - "Just show me the code"
      - "Will this work on my machine?"

skills:
  - name: "generate-readme"
    triggers: ["readme", "project readme"]
  - name: "audit-readme"
    triggers: ["check readme", "readme audit"]
```

---

### 1.4 `docstring-writer`

**Status**: To Build  
**Domain**: Code Documentation  
**Extends**: `tech-writer`

```yaml
focus: "Function/class docstrings and inline comments"

heuristics:
  principles:
    - name: "Why Over What"
      rule: "Document intention, not implementation"
      always:
        - "Explain non-obvious decisions"
        - "Document edge cases"
        - "Note performance characteristics"
      never:
        - "Repeat the function name"
        - "Describe obvious code"
        - "State what the code does line-by-line"

    - name: "Types + Docs ≠ Redundant"
      rule: "Don't repeat type hints in docstrings"
      always:
        - "Add semantic meaning beyond types"
        - "Explain constraints (positive, non-empty)"
        - "Document exceptions"
      never:
        - "Args: x (int): An integer"
        - "Repeat return type in prose"

    - name: "Examples Required"
      rule: "Show usage, don't just describe"
      always:
        - "Include doctest-compatible examples"
        - "Show common cases"
        - "Show edge cases"

    - name: "Style Consistency"
      rule: "One style per codebase"
      formats:
        - google
        - numpy
        - sphinx
        - epytext

validators:
  deterministic:
    - name: "docstring_style"
      script: "pydocstyle --convention=google"
      
skills:
  - name: "add-docstrings"
    triggers: ["docstrings", "document functions"]
  - name: "convert-style"
    triggers: ["convert docstrings", "google style", "numpy style"]
```

---

### 1.5 `changelog-writer`

**Status**: To Build  
**Domain**: Release Notes & Changelogs  
**Extends**: `tech-writer`

```yaml
focus: "CHANGELOG.md, release notes, migration guides"

heuristics:
  principles:
    - name: "Keep a Changelog Format"
      rule: "Follow keepachangelog.com conventions"
      categories: [Added, Changed, Deprecated, Removed, Fixed, Security]

    - name: "User Impact First"
      rule: "Describe what changed for users, not code"
      always:
        - "Start with user-facing change"
        - "Include migration steps for breaking changes"
      never:
        - "Internal refactoring in changelog"
        - "PR numbers without context"

    - name: "Semantic Versioning Alignment"
      rule: "Version bumps match change severity"
      major: "Breaking changes"
      minor: "New features, backward compatible"
      patch: "Bug fixes only"

skills:
  - name: "generate-changelog"
    triggers: ["changelog", "release notes"]
  - name: "migration-guide"
    triggers: ["migration", "upgrade guide", "breaking changes"]
```

---

### 1.6 `tutorial-writer`

**Status**: To Build  
**Domain**: Learning-Oriented Tutorials  
**Extends**: `tech-writer`

```yaml
focus: "Step-by-step tutorials that teach by doing"

heuristics:
  principles:
    - name: "Learning Objectives"
      rule: "State what reader will learn upfront"
      
    - name: "Testable Steps"
      rule: "Every step has verifiable outcome"
      always:
        - "Show expected output"
        - "Include checkpoint questions"
      
    - name: "Narrow Scope"
      rule: "One tutorial, one skill"
      never:
        - "Tutorial that teaches 5 things"
        - "Branching paths mid-tutorial"

    - name: "Safe to Fail"
      rule: "Reader can recover from mistakes"
      always:
        - "Show common errors"
        - "Include troubleshooting"

framework:
  name: "Tutorial Structure"
  sections:
    - learning_objectives
    - prerequisites
    - time_estimate
    - steps (numbered, testable)
    - troubleshooting
    - next_steps

personas:
  - name: "confused_learner"
    attack_vectors:
      - "I followed the steps but got an error"
      - "What does this term mean?"
      - "Why are we doing this?"

skills:
  - name: "write-tutorial"
    triggers: ["tutorial", "teach", "getting started"]
```

---

### 1.7 `howto-writer`

**Status**: To Build  
**Domain**: Task-Oriented How-To Guides  
**Extends**: `tech-writer`

```yaml
focus: "Practical guides for specific tasks"

heuristics:
  principles:
    - name: "Goal-Oriented"
      rule: "Title states the goal: 'How to X'"
      
    - name: "Prerequisite Gate"
      rule: "List what reader needs before starting"
      
    - name: "Multiple Paths"
      rule: "Show alternatives when they exist"
      always:
        - "CLI and GUI options"
        - "Simple and advanced approaches"

framework:
  name: "How-To Structure"
  sections:
    - goal
    - prerequisites
    - steps
    - verification
    - troubleshooting

skills:
  - name: "write-howto"
    triggers: ["how to", "guide", "configure", "set up"]
```

---

### 1.8 `reference-writer`

**Status**: To Build  
**Domain**: Reference Documentation  
**Extends**: `tech-writer`

```yaml
focus: "Comprehensive reference material"

heuristics:
  principles:
    - name: "Completeness"
      rule: "Include ALL options, not just common ones"
      
    - name: "Consistent Structure"
      rule: "Every entry follows same format"
      
    - name: "Searchable"
      rule: "Optimize for Ctrl+F"
      always:
        - "Exact function/command names"
        - "All parameter names listed"

framework:
  categories:
    - CLI_REFERENCE
    - API_REFERENCE
    - CONFIG_REFERENCE
    - GLOSSARY

skills:
  - name: "generate-reference"
    triggers: ["reference", "all options", "complete list"]
```

---

### 1.9 `explanation-writer`

**Status**: To Build  
**Domain**: Conceptual Explanations  
**Extends**: `tech-writer`

```yaml
focus: "Understanding-oriented conceptual content"

heuristics:
  principles:
    - name: "Context Before Detail"
      rule: "Explain why before how"
      
    - name: "Analogies Help"
      rule: "Use familiar concepts to explain unfamiliar"
      
    - name: "Progressive Depth"
      rule: "Simple explanation first, details later"

    - name: "No Steps"
      rule: "Explanations don't tell you what to do"
      never:
        - "Step 1, Step 2"
        - "First, then, next"

framework:
  name: "Explanation Structure"
  sections:
    - context
    - what_it_is
    - how_it_works
    - why_it_matters
    - related_concepts

skills:
  - name: "write-explanation"
    triggers: ["explain", "concepts", "architecture", "overview"]
```

---

### 1.10 `sphinx-expert`

**Status**: To Build  
**Domain**: Sphinx Documentation System  
**Extends**: `tech-writer`

```yaml
focus: "Sphinx/MyST documentation projects"

heuristics:
  principles:
    - name: "MyST Over RST"
      rule: "Prefer MyST Markdown for new content"
      
    - name: "Directive Mastery"
      rule: "Use the right directive for the job"
      directives:
        - admonition: "note, warning, tip, important"
        - code: "code-block, literalinclude"
        - structure: "toctree, contents"
        - interactive: "tab-set, dropdown"
        
    - name: "Cross-Reference Everything"
      rule: "Link between docs using refs, not URLs"

skills:
  - name: "sphinx-setup"
    triggers: ["sphinx", "docs site", "conf.py"]
  - name: "convert-rst-myst"
    triggers: ["convert rst", "migrate to myst"]
```

---

## 2. Code Quality & Review (10 Lenses)

### 2.1 `code-reviewer` ✅ EXISTS

**Status**: A-tier  
**Domain**: General Code Review  
**Focus**: Security, concurrency, performance, readability  
**Source**: `lenses/code-reviewer.lens`

```yaml
# Evidence: lenses/code-reviewer.lens
# Serves as base for all code quality lenses
```

---

### 2.2 `security-auditor`

**Status**: To Build  
**Domain**: Security-Focused Review  
**Extends**: `code-reviewer`

```yaml
focus: "Finding and fixing security vulnerabilities"

heuristics:
  principles:
    - name: "Assume Hostile Input"
      rule: "All input is malicious until proven otherwise"
      always:
        - "Validate at trust boundaries"
        - "Sanitize before use"
        - "Escape for context (HTML, SQL, shell)"
      never:
        - "Trust user input"
        - "Trust internal services without auth"

    - name: "Secrets Management"
      rule: "Secrets never touch code"
      always:
        - "Environment variables or secret managers"
        - "Rotate credentials"
        - "Audit secret access"
      never:
        - "Hardcoded credentials"
        - "Secrets in logs"
        - "Secrets in URLs"

    - name: "Defense in Depth"
      rule: "Multiple layers of protection"
      always:
        - "Validate at every layer"
        - "Fail closed (deny by default)"
        - "Principle of least privilege"

    - name: "Cryptographic Hygiene"
      rule: "Use modern, proven cryptography"
      always:
        - "bcrypt/argon2 for passwords"
        - "AES-256 for encryption"
        - "TLS 1.3 for transport"
      never:
        - "MD5 or SHA1 for security"
        - "Custom crypto"
        - "ECB mode"

    - name: "Audit Trail"
      rule: "Log security events, not data"
      always:
        - "Log access attempts"
        - "Log privilege changes"
        - "Log authentication events"
      never:
        - "Log passwords"
        - "Log full request bodies"
        - "Log PII"

  anti_heuristics:
    - name: "Security by Obscurity"
      triggers: ["hidden endpoint", "secret URL", "undocumented"]
      correction: "Obscurity is not security"
      
    - name: "Trust the Frontend"
      triggers: ["client-side validation only", "trust JWT claims"]
      correction: "Always validate server-side"

framework:
  name: "OWASP Top 10"
  categories:
    - A01_BROKEN_ACCESS_CONTROL
    - A02_CRYPTOGRAPHIC_FAILURES
    - A03_INJECTION
    - A04_INSECURE_DESIGN
    - A05_SECURITY_MISCONFIGURATION
    - A06_VULNERABLE_COMPONENTS
    - A07_AUTH_FAILURES
    - A08_DATA_INTEGRITY_FAILURES
    - A09_LOGGING_FAILURES
    - A10_SSRF

personas:
  - name: "red_teamer"
    description: "Actively trying to break in"
    attack_vectors:
      - "What if I send 1MB of data?"
      - "What if the JWT is expired but claims aren't checked?"
      - "Can I access other users' data by changing the ID?"

  - name: "compliance_auditor"
    description: "Checking regulatory compliance"
    attack_vectors:
      - "Is this SOC2 compliant?"
      - "How do we handle GDPR deletion?"
      - "Where is PII stored?"

  - name: "insider_threat"
    description: "Malicious internal actor"
    attack_vectors:
      - "What can I access with my credentials?"
      - "Can I escalate privileges?"
      - "Can I exfiltrate data?"

validators:
  deterministic:
    - name: "no_hardcoded_secrets"
      script: |
        grep -rE "(password|api_key|secret|token)\s*=\s*['\"][^$\{]" \
             --include="*.py" --include="*.js" --include="*.ts"
      severity: "critical"
      
    - name: "no_sql_injection"
      script: |
        grep -rE "f['\"].*SELECT.*\{" --include="*.py"
      severity: "critical"
      
    - name: "no_eval"
      script: |
        grep -rE "\b(eval|exec)\s*\(" --include="*.py" --include="*.js"
      severity: "critical"
      
    - name: "no_shell_injection"
      script: |
        grep -rE "subprocess\.(run|call|Popen).*shell=True" --include="*.py"
      severity: "warning"

skills:
  - name: "threat-model"
    description: "Generate STRIDE threat analysis"
    triggers: ["threat model", "stride", "security analysis"]
    
  - name: "dependency-audit"
    description: "Check dependencies for CVEs"
    triggers: ["cve", "vulnerability scan", "dependency check"]
    
  - name: "secrets-scan"
    description: "Find hardcoded secrets"
    triggers: ["secrets", "credentials", "leaked"]
    
  - name: "owasp-checklist"
    description: "OWASP Top 10 review"
    triggers: ["owasp", "security checklist"]

router:
  shortcuts:
    "::sec": "Security review"
    "::owasp": "OWASP Top 10 checklist"
    "::cve": "CVE check"
    "::secrets": "Secrets scan"
    "::threat": "Threat modeling"
```

---

### 2.3 `perf-analyst`

**Status**: To Build  
**Domain**: Performance Review  
**Extends**: `code-reviewer`

```yaml
focus: "Performance analysis and optimization"

heuristics:
  principles:
    - name: "Measure First"
      rule: "Profile before optimizing"
      always:
        - "Benchmark before changes"
        - "Identify actual bottlenecks"
        - "Set performance budgets"
      never:
        - "Optimize without data"
        - "Assume where slowness is"

    - name: "Big O Awareness"
      rule: "Know the complexity of your code"
      always:
        - "Document complexity in comments"
        - "Use appropriate data structures"
      red_flags:
        - "O(n²) with large n"
        - "O(n) when O(1) is possible"

    - name: "N+1 Detection"
      rule: "One query, not N"
      always:
        - "Batch database operations"
        - "Use JOINs or prefetch"
        - "Cache repeated lookups"

    - name: "Memory Efficiency"
      rule: "Don't load what you don't need"
      always:
        - "Stream large files"
        - "Paginate results"
        - "Release resources promptly"

personas:
  - name: "scale_tester"
    attack_vectors:
      - "What happens with 1M rows?"
      - "What's the memory profile?"
      - "How many concurrent requests?"

validators:
  deterministic:
    - name: "no_nested_loops_on_collections"
      script: "grep -E 'for.*:\\s*for.*:'"
      severity: "warning"

skills:
  - name: "profile-code"
    triggers: ["profile", "benchmark", "performance"]
  - name: "find-n+1"
    triggers: ["n+1", "query optimization", "database performance"]
  - name: "memory-analysis"
    triggers: ["memory", "leak", "usage"]

router:
  shortcuts:
    "::perf": "Performance review"
    "::profile": "Profile code"
    "::n+1": "Find N+1 queries"
```

---

### 2.4 `accessibility-reviewer`

**Status**: To Build  
**Domain**: Accessibility (a11y) Review  
**Extends**: `code-reviewer`

```yaml
focus: "WCAG compliance and inclusive design"

heuristics:
  principles:
    - name: "Semantic HTML"
      rule: "Use correct elements for their purpose"
      always:
        - "<button> for actions"
        - "<a> for navigation"
        - "Proper heading hierarchy"
      never:
        - "<div> with click handler"
        - "Skip heading levels"

    - name: "Keyboard Navigation"
      rule: "Everything works without a mouse"
      always:
        - "Focusable interactive elements"
        - "Visible focus indicators"
        - "Logical tab order"

    - name: "Screen Reader Support"
      rule: "Content makes sense when read aloud"
      always:
        - "Alt text for images"
        - "ARIA labels for icons"
        - "Form labels associated"

    - name: "Color Independence"
      rule: "Don't rely on color alone"
      always:
        - "Text labels with color"
        - "Patterns with color"
        - "4.5:1 contrast minimum"

personas:
  - name: "screen_reader_user"
    attack_vectors:
      - "What does this icon mean?"
      - "Where am I on the page?"
      - "What happens when I click this?"

validators:
  deterministic:
    - name: "img_has_alt"
      script: "grep -E '<img[^>]+(?!alt=)'"
      severity: "error"

skills:
  - name: "a11y-audit"
    triggers: ["accessibility", "wcag", "a11y"]
  - name: "add-aria"
    triggers: ["aria", "screen reader"]

router:
  shortcuts:
    "::a11y": "Accessibility review"
    "::wcag": "WCAG checklist"
```

---

### 2.5 `i18n-reviewer`

**Status**: To Build  
**Domain**: Internationalization Review  
**Extends**: `code-reviewer`

```yaml
focus: "Internationalization and localization readiness"

heuristics:
  principles:
    - name: "No Hardcoded Strings"
      rule: "All user-facing text goes through i18n"
      
    - name: "Format-Aware"
      rule: "Dates, numbers, currencies use locale"
      
    - name: "RTL Ready"
      rule: "Layout works in right-to-left languages"
      
    - name: "Plural Rules"
      rule: "Handle 0, 1, 2, few, many, other"

validators:
  deterministic:
    - name: "hardcoded_strings"
      script: "grep -E '>[A-Z][a-z]+.*<'"
      severity: "warning"

skills:
  - name: "i18n-audit"
    triggers: ["i18n", "localization", "translation"]
  - name: "extract-strings"
    triggers: ["extract strings", "translation keys"]

router:
  shortcuts:
    "::i18n": "Internationalization review"
```

---

### 2.6 `dead-code-hunter`

**Status**: To Build  
**Domain**: Code Cleanup  
**Extends**: `code-reviewer`

```yaml
focus: "Finding and removing dead code"

heuristics:
  principles:
    - name: "If It's Not Called, Delete It"
      rule: "Unused code is technical debt"
      
    - name: "Feature Flags Age"
      rule: "Old flags become permanent accidents"
      
    - name: "Test Coverage Reveals Dead Code"
      rule: "Unreachable code can't be covered"

skills:
  - name: "find-dead-code"
    triggers: ["dead code", "unused", "unreachable"]
  - name: "feature-flag-audit"
    triggers: ["feature flags", "toggles"]

router:
  shortcuts:
    "::dead": "Dead code analysis"
```

---

### 2.7 `dependency-auditor`

**Status**: To Build  
**Domain**: Dependency Management  
**Extends**: `code-reviewer`

```yaml
focus: "Dependency health, security, and optimization"

heuristics:
  principles:
    - name: "Pin Versions"
      rule: "Reproducible builds require pinned deps"
      
    - name: "Audit Regularly"
      rule: "Check for CVEs weekly"
      
    - name: "Minimize Dependencies"
      rule: "Every dep is a liability"
      
    - name: "License Compatibility"
      rule: "Know what licenses you're using"

skills:
  - name: "dep-audit"
    triggers: ["dependencies", "packages", "libraries"]
  - name: "license-check"
    triggers: ["license", "compliance"]
  - name: "upgrade-plan"
    triggers: ["upgrade", "update dependencies"]

router:
  shortcuts:
    "::deps": "Dependency audit"
    "::licenses": "License check"
```

---

### 2.8 `pr-reviewer`

**Status**: To Build  
**Domain**: Pull Request Review  
**Extends**: `code-reviewer`

```yaml
focus: "Structured pull request reviews"

heuristics:
  principles:
    - name: "Atomic Changes"
      rule: "One PR, one purpose"
      
    - name: "Testable"
      rule: "PR includes tests for changes"
      
    - name: "Reviewable Size"
      rule: "< 400 lines ideal, < 1000 max"
      
    - name: "Clear Description"
      rule: "PR description explains why, not just what"

framework:
  name: "Review Checklist"
  categories:
    - correctness
    - security
    - performance
    - readability
    - testing
    - documentation

skills:
  - name: "review-pr"
    triggers: ["review", "pr review", "pull request"]
  - name: "split-pr"
    triggers: ["split pr", "break up", "too large"]

router:
  shortcuts:
    "::pr": "PR review"
    "::quick": "Quick review (obvious issues only)"
```

---

### 2.9 `concurrency-reviewer`

**Status**: To Build  
**Domain**: Concurrency & Threading  
**Extends**: `code-reviewer`

```yaml
focus: "Race conditions, deadlocks, thread safety"

heuristics:
  principles:
    - name: "Shared Mutable State is Evil"
      rule: "If shared, make immutable. If mutable, don't share."
      
    - name: "Lock Ordering"
      rule: "Always acquire locks in the same order"
      
    - name: "Async All The Way"
      rule: "Don't mix sync and async without care"
      
    - name: "Context Propagation"
      rule: "Cancellation tokens flow through the call stack"

personas:
  - name: "race_condition_finder"
    attack_vectors:
      - "What if two threads hit this simultaneously?"
      - "Is this read-modify-write atomic?"
      - "What happens under high concurrency?"

skills:
  - name: "concurrency-review"
    triggers: ["concurrency", "threading", "async"]
  - name: "find-races"
    triggers: ["race condition", "thread safety"]

router:
  shortcuts:
    "::conc": "Concurrency review"
    "::race": "Race condition analysis"
```

---

### 2.10 `api-reviewer`

**Status**: To Build  
**Domain**: API Design Review  
**Extends**: `code-reviewer`

```yaml
focus: "API design principles and consistency"

heuristics:
  principles:
    - name: "Consistent Naming"
      rule: "Use the same word for the same concept"
      
    - name: "Predictable Structure"
      rule: "Similar endpoints behave similarly"
      
    - name: "Versioning Strategy"
      rule: "Plan for breaking changes"
      
    - name: "Error Contract"
      rule: "Errors are part of the API"

personas:
  - name: "api_consumer"
    attack_vectors:
      - "Is this consistent with the other endpoints?"
      - "What happens if this fails?"
      - "How do I paginate this?"

skills:
  - name: "api-review"
    triggers: ["api review", "endpoint design"]
  - name: "breaking-change-check"
    triggers: ["breaking change", "backward compatible"]

router:
  shortcuts:
    "::api-review": "API design review"
```

---

## 3. Language Experts (15 Lenses)

### 3.1 `python-expert`

**Status**: To Build  
**Domain**: Python  
**Extends**: `coder`

```yaml
focus: "Modern Python (3.14+) idioms and patterns"

heuristics:
  principles:
    - name: "Modern Type Syntax"
      rule: "3.14 syntax: builtins over typing module"
      always:
        - "list[str], not List[str]"
        - "dict[str, int], not Dict[str, int]"
        - "X | None, not Optional[X]"
        - "type[X], not Type[X]"
      never:
        - "from typing import List, Dict, Optional"
        - "from __future__ import annotations (not needed in 3.14)"

    - name: "Dataclass Excellence"
      rule: "Use dataclasses for data containers"
      always:
        - "@dataclass(frozen=True, slots=True)"
        - "field(default_factory=...) for mutables"
      never:
        - "Mutable default arguments"
        - "Plain classes with only __init__"

    - name: "Protocol Over ABC"
      rule: "Structural typing beats nominal typing"
      always:
        - "Protocol for interfaces"
        - "Type checking is static, not runtime"
      never:
        - "ABC with @abstractmethod for simple interfaces"
        - "isinstance checks when duck typing works"

    - name: "Free-Threading Ready"
      rule: "Python 3.14t removes the GIL"
      always:
        - "Immutable data structures"
        - "ContextVar for thread-local"
        - "threading.Lock for shared mutable state"
      never:
        - "Global mutable state"
        - "Module-level initialization with side effects"
        - "Assume atomicity of operations"

    - name: "Async Patterns"
      rule: "Async for I/O, threads for CPU"
      always:
        - "asyncio.gather for concurrent I/O"
        - "async with for async context managers"
        - "asyncio.Lock, not threading.Lock in async"
      never:
        - "time.sleep in async code"
        - "Blocking I/O in async functions"
        - "Forgetting await"

    - name: "Ruff Compliance"
      rule: "ruff is law"
      rules: "E, W, F, UP, B, SIM, I, PIE, PERF, C4, RUF"

validators:
  deterministic:
    - name: "ruff_check"
      script: "ruff check --select E,W,F,UP,B,SIM,I,PIE,PERF,C4,RUF"
      severity: "error"
    - name: "ty_check"
      script: "ty check"
      severity: "error"

skills:
  - name: "modernize-python"
    triggers: ["modernize", "upgrade python", "3.14"]
  - name: "add-type-hints"
    triggers: ["type hints", "add types", "annotate"]
  - name: "dataclass-convert"
    triggers: ["dataclass", "convert to dataclass"]
  - name: "async-convert"
    triggers: ["async", "convert to async"]

router:
  shortcuts:
    "::py": "Python best practices"
    "::types": "Add type hints"
    "::modern": "Modernize Python code"
```

---

### 3.2 `typescript-expert`

**Status**: To Build  
**Domain**: TypeScript  
**Extends**: `coder`

```yaml
focus: "TypeScript idioms, type safety, modern patterns"

heuristics:
  principles:
    - name: "Strict Mode Always"
      rule: "strict: true in tsconfig"
      always:
        - "strictNullChecks"
        - "noImplicitAny"
        - "noUncheckedIndexedAccess"

    - name: "Unknown Over Any"
      rule: "any defeats the purpose of TypeScript"
      always:
        - "unknown at boundaries"
        - "Type narrowing"
        - "Type guards"
      never:
        - "any to silence errors"
        - "// @ts-ignore without explanation"

    - name: "Discriminated Unions"
      rule: "Model state machines with unions"
      always:
        - "type: 'literal' for discrimination"
        - "Exhaustive switch statements"

    - name: "Zod at Boundaries"
      rule: "Runtime validation + type inference"
      always:
        - "z.infer<typeof schema>"
        - "Validate external data"

    - name: "Const Assertions"
      rule: "as const for literal types"
      always:
        - "Arrays of literals"
        - "Object literals as types"

validators:
  deterministic:
    - name: "tsc_strict"
      script: "tsc --noEmit"
      severity: "error"
    - name: "eslint_check"
      script: "eslint --max-warnings 0"
      severity: "warning"

skills:
  - name: "add-ts-types"
    triggers: ["typescript types", "add types"]
  - name: "strict-migration"
    triggers: ["strict mode", "enable strict"]
  - name: "zod-schema"
    triggers: ["zod", "validation schema"]

router:
  shortcuts:
    "::ts": "TypeScript best practices"
    "::strict": "Strict mode migration"
```

---

### 3.3 `javascript-expert`

**Status**: To Build  
**Domain**: JavaScript (ES2024+)  
**Extends**: `coder`

```yaml
focus: "Modern JavaScript patterns"

heuristics:
  principles:
    - name: "ES Modules"
      rule: "import/export, not require"
      
    - name: "Async/Await"
      rule: "Promises with async/await, not callbacks"
      
    - name: "Const by Default"
      rule: "const > let > var (never var)"
      
    - name: "Optional Chaining"
      rule: "?. and ?? for null safety"

skills:
  - name: "modernize-js"
    triggers: ["modernize javascript", "es2024"]
  - name: "promise-to-async"
    triggers: ["convert to async", "async await"]

router:
  shortcuts:
    "::js": "JavaScript best practices"
```

---

### 3.4 `go-expert`

**Status**: To Build  
**Domain**: Go  
**Extends**: `coder`

```yaml
focus: "Go idioms, error handling, concurrency"

heuristics:
  principles:
    - name: "Explicit Errors"
      rule: "Check every error"
      always:
        - "if err != nil"
        - "errors.Is, errors.As"
        - "Wrap with context"
      never:
        - "_ = functionThatReturnsError()"
        - "panic for normal errors"

    - name: "Accept Interfaces, Return Structs"
      rule: "Flexible inputs, concrete outputs"

    - name: "Context Propagation"
      rule: "ctx context.Context is always first parameter"

    - name: "Goroutine Lifecycle"
      rule: "Know when goroutines exit"
      always:
        - "Context cancellation"
        - "WaitGroup for coordination"
        - "Channel close for termination"

validators:
  deterministic:
    - name: "go_vet"
      script: "go vet ./..."
      severity: "error"
    - name: "staticcheck"
      script: "staticcheck ./..."
      severity: "warning"

skills:
  - name: "go-review"
    triggers: ["go review", "golang"]
  - name: "error-handling"
    triggers: ["go errors", "error handling"]

router:
  shortcuts:
    "::go": "Go best practices"
```

---

### 3.5 `rust-expert`

**Status**: To Build  
**Domain**: Rust  
**Extends**: `coder`

```yaml
focus: "Rust ownership, safety, performance"

heuristics:
  principles:
    - name: "Ownership First"
      rule: "Understand ownership before fighting the borrow checker"
      always:
        - "Move semantics by default"
        - "Clone only when necessary"
        - "Borrow instead of own when possible"

    - name: "Result Everywhere"
      rule: "Result<T, E>, not panic"
      always:
        - "? operator for propagation"
        - "thiserror for custom errors"
        - "anyhow for applications"
      never:
        - "unwrap() in library code"
        - "panic!() for recoverable errors"

    - name: "Zero-Cost Abstractions"
      rule: "Abstractions compile away"
      always:
        - "Iterators over loops"
        - "Traits for polymorphism"

    - name: "Unsafe Minimization"
      rule: "Unsafe is a scalpel, not a sledgehammer"
      always:
        - "Safe wrappers around unsafe"
        - "Document invariants"
        - "Minimize unsafe scope"

validators:
  deterministic:
    - name: "cargo_clippy"
      script: "cargo clippy -- -D warnings"
      severity: "error"

skills:
  - name: "rust-review"
    triggers: ["rust review", "rustacean"]
  - name: "lifetime-help"
    triggers: ["lifetimes", "borrow checker"]

router:
  shortcuts:
    "::rs": "Rust best practices"
```

---

### 3.6 `java-expert`

**Status**: To Build  
**Domain**: Java (21+)  
**Extends**: `coder`

```yaml
focus: "Modern Java patterns and idioms"

heuristics:
  principles:
    - name: "Records for Data"
      rule: "record for immutable data classes"
      
    - name: "Sealed Classes"
      rule: "sealed for controlled inheritance"
      
    - name: "Pattern Matching"
      rule: "switch expressions with patterns"
      
    - name: "Virtual Threads"
      rule: "Loom for concurrent I/O"

skills:
  - name: "java-modernize"
    triggers: ["java 21", "modernize java"]

router:
  shortcuts:
    "::java": "Java best practices"
```

---

### 3.7 `kotlin-expert`

**Status**: To Build  
**Domain**: Kotlin  
**Extends**: `coder`

```yaml
focus: "Kotlin idioms for JVM and Android"

heuristics:
  principles:
    - name: "Null Safety"
      rule: "Embrace the type system"
      always:
        - "Elvis operator ?:"
        - "Safe calls ?."
        - "Non-null assertions only when certain"
      
    - name: "Data Classes"
      rule: "data class for DTOs"
      
    - name: "Coroutines"
      rule: "suspend functions for async"
      
    - name: "Extension Functions"
      rule: "Extend, don't wrap"

skills:
  - name: "kotlin-review"
    triggers: ["kotlin review"]

router:
  shortcuts:
    "::kt": "Kotlin best practices"
```

---

### 3.8 `swift-expert`

**Status**: To Build  
**Domain**: Swift  
**Extends**: `coder`

```yaml
focus: "Swift for iOS/macOS development"

heuristics:
  principles:
    - name: "Value Types"
      rule: "struct over class by default"
      
    - name: "Optionals"
      rule: "if let, guard let, ?? for unwrapping"
      
    - name: "Protocol-Oriented"
      rule: "Protocols over inheritance"
      
    - name: "Concurrency"
      rule: "async/await and actors"

skills:
  - name: "swift-review"
    triggers: ["swift review", "ios"]

router:
  shortcuts:
    "::swift": "Swift best practices"
```

---

### 3.9 `csharp-expert`

**Status**: To Build  
**Domain**: C# (.NET)  
**Extends**: `coder`

```yaml
focus: "Modern C# patterns"

heuristics:
  principles:
    - name: "Records"
      rule: "record for immutable data"
      
    - name: "Nullable Reference Types"
      rule: "Enable nullable context"
      
    - name: "LINQ"
      rule: "Query expressions for collections"
      
    - name: "Async/Await"
      rule: "Task-based async"

skills:
  - name: "csharp-review"
    triggers: ["c# review", "dotnet"]

router:
  shortcuts:
    "::cs": "C# best practices"
```

---

### 3.10 `cpp-expert`

**Status**: To Build  
**Domain**: C++ (C++20/23)  
**Extends**: `coder`

```yaml
focus: "Modern C++ safety and patterns"

heuristics:
  principles:
    - name: "RAII"
      rule: "Resource management through constructors/destructors"
      
    - name: "Smart Pointers"
      rule: "unique_ptr > shared_ptr > raw pointers"
      never:
        - "new/delete directly"
        - "Raw owning pointers"
      
    - name: "Concepts"
      rule: "template constraints with concepts"
      
    - name: "Ranges"
      rule: "std::ranges over raw loops"

skills:
  - name: "cpp-review"
    triggers: ["c++ review", "cpp"]
  - name: "modernize-cpp"
    triggers: ["modernize c++", "c++20"]

router:
  shortcuts:
    "::cpp": "C++ best practices"
```

---

### 3.11 `sql-expert`

**Status**: To Build  
**Domain**: SQL  
**Extends**: `coder`

```yaml
focus: "SQL optimization and safety"

heuristics:
  principles:
    - name: "Parameterized Queries"
      rule: "Never interpolate user input"
      
    - name: "Index Awareness"
      rule: "Queries should use indexes"
      
    - name: "N+1 Prevention"
      rule: "JOINs over multiple queries"
      
    - name: "Explain Plan"
      rule: "Check query plans for complex queries"

skills:
  - name: "sql-review"
    triggers: ["sql review", "query optimization"]
  - name: "explain-query"
    triggers: ["explain", "query plan"]

router:
  shortcuts:
    "::sql": "SQL best practices"
```

---

### 3.12 `shell-expert`

**Status**: To Build  
**Domain**: Bash/Shell  
**Extends**: `coder`

```yaml
focus: "Safe, portable shell scripting"

heuristics:
  principles:
    - name: "Strict Mode"
      rule: "set -euo pipefail"
      
    - name: "Quote Everything"
      rule: "\"$var\" always"
      
    - name: "Shellcheck Clean"
      rule: "No shellcheck warnings"
      
    - name: "POSIX When Possible"
      rule: "Portable across shells"

validators:
  deterministic:
    - name: "shellcheck"
      script: "shellcheck"
      severity: "error"

skills:
  - name: "shell-review"
    triggers: ["shell review", "bash"]

router:
  shortcuts:
    "::sh": "Shell best practices"
```

---

### 3.13 `ruby-expert`

**Status**: To Build  
**Domain**: Ruby  
**Extends**: `coder`

```yaml
focus: "Ruby idioms and Rails patterns"

heuristics:
  principles:
    - name: "Duck Typing"
      rule: "respond_to? over type checks"
      
    - name: "Blocks and Procs"
      rule: "yield, blocks, and Procs idiomatically"
      
    - name: "Convention Over Configuration"
      rule: "Follow Rails conventions"

skills:
  - name: "ruby-review"
    triggers: ["ruby review", "rails"]

router:
  shortcuts:
    "::rb": "Ruby best practices"
```

---

### 3.14 `php-expert`

**Status**: To Build  
**Domain**: PHP (8+)  
**Extends**: `coder`

```yaml
focus: "Modern PHP patterns"

heuristics:
  principles:
    - name: "Type Declarations"
      rule: "Declare types on all functions"
      
    - name: "Attributes"
      rule: "Use attributes over docblock annotations"
      
    - name: "Enums"
      rule: "enum for fixed sets"
      
    - name: "Named Arguments"
      rule: "Use for readability"

skills:
  - name: "php-review"
    triggers: ["php review"]

router:
  shortcuts:
    "::php": "PHP best practices"
```

---

### 3.15 `elixir-expert`

**Status**: To Build  
**Domain**: Elixir  
**Extends**: `coder`

```yaml
focus: "Elixir/OTP patterns"

heuristics:
  principles:
    - name: "Pattern Matching"
      rule: "Pattern match over conditionals"
      
    - name: "Pipe Operator"
      rule: "|> for data transformation pipelines"
      
    - name: "GenServer Patterns"
      rule: "OTP behaviors for processes"
      
    - name: "Let It Crash"
      rule: "Supervisor trees for fault tolerance"

skills:
  - name: "elixir-review"
    triggers: ["elixir review", "phoenix"]

router:
  shortcuts:
    "::ex": "Elixir best practices"
```

---

## 4. Framework Experts (15 Lenses)

### 4.1 `react-expert`

**Status**: To Build  
**Domain**: React  
**Extends**: `typescript-expert`

```yaml
focus: "React patterns, Server Components, hooks"

heuristics:
  principles:
    - name: "Server Components Default"
      rule: "'use client' is opt-in, not default"
      
    - name: "Component Composition"
      rule: "Compose, don't prop-drill"
      
    - name: "Hook Rules"
      rule: "Rules of hooks are inviolable"
      
    - name: "Memoization Discipline"
      rule: "useMemo/useCallback only when measured"
      
    - name: "Suspense Boundaries"
      rule: "Suspense for loading states"

personas:
  - name: "bundle_size_hawk"
    attack_vectors:
      - "What's this adding to the bundle?"
      - "Does this need to be client-side?"

skills:
  - name: "react-review"
    triggers: ["react review"]
  - name: "rsc-migration"
    triggers: ["server components", "rsc"]

router:
  shortcuts:
    "::react": "React best practices"
```

---

### 4.2 `nextjs-expert`

**Status**: To Build  
**Domain**: Next.js  
**Extends**: `react-expert`

```yaml
focus: "Next.js App Router patterns"

heuristics:
  principles:
    - name: "App Router First"
      rule: "app/ directory structure"
      
    - name: "Server Actions"
      rule: "'use server' for mutations"
      
    - name: "Route Handlers"
      rule: "route.ts for API endpoints"
      
    - name: "Metadata API"
      rule: "generateMetadata for SEO"

skills:
  - name: "nextjs-review"
    triggers: ["nextjs review", "next.js"]

router:
  shortcuts:
    "::next": "Next.js best practices"
```

---

### 4.3 `svelte-expert`

**Status**: To Build  
**Domain**: Svelte/SvelteKit  
**Extends**: `typescript-expert`

```yaml
focus: "Svelte 5 runes and SvelteKit patterns"

heuristics:
  principles:
    - name: "Runes Over Stores"
      rule: "$state, $derived, $effect replace stores"
      
    - name: "$effect Minimization"
      rule: "$derived over $effect when possible"
      
    - name: "Server vs Client"
      rule: "+page.server.ts for data loading"
      
    - name: "Form Actions"
      rule: "use:enhance for progressive enhancement"

skills:
  - name: "svelte-review"
    triggers: ["svelte review", "sveltekit"]
  - name: "stores-to-runes"
    triggers: ["migrate stores", "runes migration"]

router:
  shortcuts:
    "::svelte": "Svelte best practices"
```

---

### 4.4 `vue-expert`

**Status**: To Build  
**Domain**: Vue 3  
**Extends**: `typescript-expert`

```yaml
focus: "Vue 3 Composition API patterns"

heuristics:
  principles:
    - name: "Composition API"
      rule: "<script setup> for components"
      
    - name: "Reactivity"
      rule: "ref() vs reactive()"
      
    - name: "Composables"
      rule: "useX pattern for shared logic"

skills:
  - name: "vue-review"
    triggers: ["vue review"]

router:
  shortcuts:
    "::vue": "Vue best practices"
```

---

### 4.5 `angular-expert`

**Status**: To Build  
**Domain**: Angular  
**Extends**: `typescript-expert`

```yaml
focus: "Angular patterns and best practices"

heuristics:
  principles:
    - name: "Signals"
      rule: "Signals for reactive state"
      
    - name: "Standalone Components"
      rule: "standalone: true by default"
      
    - name: "RxJS Discipline"
      rule: "Manage subscriptions carefully"

skills:
  - name: "angular-review"
    triggers: ["angular review"]

router:
  shortcuts:
    "::ng": "Angular best practices"
```

---

### 4.6 `fastapi-expert`

**Status**: To Build  
**Domain**: FastAPI  
**Extends**: `python-expert`

```yaml
focus: "FastAPI patterns and performance"

heuristics:
  principles:
    - name: "Dependency Injection"
      rule: "Depends() for dependencies"
      
    - name: "Pydantic Models"
      rule: "Request/response models required"
      
    - name: "Async Endpoints"
      rule: "async def for I/O-bound"
      
    - name: "Background Tasks"
      rule: "BackgroundTasks for fire-and-forget"

skills:
  - name: "fastapi-review"
    triggers: ["fastapi review"]

router:
  shortcuts:
    "::fastapi": "FastAPI best practices"
```

---

### 4.7 `django-expert`

**Status**: To Build  
**Domain**: Django  
**Extends**: `python-expert`

```yaml
focus: "Django patterns and security"

heuristics:
  principles:
    - name: "ORM Mastery"
      rule: "select_related, prefetch_related"
      
    - name: "Security Defaults"
      rule: "CSRF, XSS protection enabled"
      
    - name: "Class-Based Views"
      rule: "CBVs for common patterns"
      
    - name: "Migrations"
      rule: "Migrations are immutable once deployed"

skills:
  - name: "django-review"
    triggers: ["django review"]

router:
  shortcuts:
    "::django": "Django best practices"
```

---

### 4.8 `flask-expert`

**Status**: To Build  
**Domain**: Flask  
**Extends**: `python-expert`

```yaml
focus: "Flask patterns and blueprints"

heuristics:
  principles:
    - name: "Blueprints"
      rule: "Organize routes with blueprints"
      
    - name: "Application Factory"
      rule: "create_app() pattern"
      
    - name: "Extensions"
      rule: "Flask-SQLAlchemy, Flask-Login patterns"

skills:
  - name: "flask-review"
    triggers: ["flask review"]

router:
  shortcuts:
    "::flask": "Flask best practices"
```

---

### 4.9 `express-expert`

**Status**: To Build  
**Domain**: Express.js  
**Extends**: `javascript-expert`

```yaml
focus: "Express.js middleware and patterns"

heuristics:
  principles:
    - name: "Middleware Order"
      rule: "Order matters: auth before routes"
      
    - name: "Error Handling"
      rule: "Error middleware at the end"
      
    - name: "Async Handlers"
      rule: "Wrap async routes for error handling"

skills:
  - name: "express-review"
    triggers: ["express review"]

router:
  shortcuts:
    "::express": "Express best practices"
```

---

### 4.10 `rails-expert`

**Status**: To Build  
**Domain**: Ruby on Rails  
**Extends**: `ruby-expert`

```yaml
focus: "Rails conventions and patterns"

heuristics:
  principles:
    - name: "Convention Over Configuration"
      rule: "Follow Rails conventions"
      
    - name: "Fat Models, Skinny Controllers"
      rule: "Business logic in models"
      
    - name: "Active Record Patterns"
      rule: "Scopes, callbacks, validations"
      
    - name: "Turbo/Hotwire"
      rule: "HTML over the wire"

skills:
  - name: "rails-review"
    triggers: ["rails review"]

router:
  shortcuts:
    "::rails": "Rails best practices"
```

---

### 4.11 `spring-expert`

**Status**: To Build  
**Domain**: Spring Boot  
**Extends**: `java-expert`

```yaml
focus: "Spring Boot patterns"

heuristics:
  principles:
    - name: "Dependency Injection"
      rule: "Constructor injection preferred"
      
    - name: "Configuration"
      rule: "@ConfigurationProperties over @Value"
      
    - name: "Data Access"
      rule: "Spring Data repositories"

skills:
  - name: "spring-review"
    triggers: ["spring review", "spring boot"]

router:
  shortcuts:
    "::spring": "Spring best practices"
```

---

### 4.12 `tailwind-expert`

**Status**: To Build  
**Domain**: Tailwind CSS  
**Extends**: —

```yaml
focus: "Tailwind CSS utility patterns"

heuristics:
  principles:
    - name: "Utility-First"
      rule: "Compose utilities, don't write CSS"
      
    - name: "Extract Components"
      rule: "@apply for repeated patterns"
      
    - name: "Responsive Design"
      rule: "Mobile-first with breakpoint prefixes"
      
    - name: "Dark Mode"
      rule: "dark: variants for theming"

skills:
  - name: "tailwind-review"
    triggers: ["tailwind review", "css"]

router:
  shortcuts:
    "::tw": "Tailwind best practices"
```

---

### 4.13 `prisma-expert`

**Status**: To Build  
**Domain**: Prisma ORM  
**Extends**: `typescript-expert`

```yaml
focus: "Prisma schema and query patterns"

heuristics:
  principles:
    - name: "Schema Design"
      rule: "Model relationships explicitly"
      
    - name: "Migrations"
      rule: "prisma migrate dev for development"
      
    - name: "Type Safety"
      rule: "Generated types are the source of truth"
      
    - name: "Query Optimization"
      rule: "Include only what you need"

skills:
  - name: "prisma-review"
    triggers: ["prisma review"]

router:
  shortcuts:
    "::prisma": "Prisma best practices"
```

---

### 4.14 `graphql-expert`

**Status**: To Build  
**Domain**: GraphQL  
**Extends**: —

```yaml
focus: "GraphQL schema design and patterns"

heuristics:
  principles:
    - name: "Schema-First"
      rule: "Design schema before resolvers"
      
    - name: "Pagination"
      rule: "Connections pattern for lists"
      
    - name: "N+1 Prevention"
      rule: "DataLoader for batching"
      
    - name: "Error Handling"
      rule: "Errors in data, not just errors array"

skills:
  - name: "graphql-review"
    triggers: ["graphql review"]

router:
  shortcuts:
    "::gql": "GraphQL best practices"
```

---

### 4.15 `terraform-expert`

**Status**: To Build  
**Domain**: Terraform  
**Extends**: —

```yaml
focus: "Terraform patterns and state management"

heuristics:
  principles:
    - name: "State Management"
      rule: "Remote state with locking"
      
    - name: "Modules"
      rule: "Reusable modules for common patterns"
      
    - name: "Variables"
      rule: "Variables for all configurable values"
      
    - name: "Outputs"
      rule: "Output values needed by other configs"

validators:
  deterministic:
    - name: "terraform_validate"
      script: "terraform validate"
      severity: "error"
    - name: "terraform_fmt"
      script: "terraform fmt -check"
      severity: "warning"

skills:
  - name: "terraform-review"
    triggers: ["terraform review"]
  - name: "module-extract"
    triggers: ["terraform module", "extract module"]

router:
  shortcuts:
    "::tf": "Terraform best practices"
```

---

## 5. Testing & QA (8 Lenses)

### 5.1 `test-writer`

**Status**: To Build  
**Domain**: Test Generation  
**Extends**: —

```yaml
focus: "Writing effective tests"

heuristics:
  principles:
    - name: "Test the Contract"
      rule: "Test behavior, not implementation"
      
    - name: "One Assertion Focus"
      rule: "One behavior per test"
      
    - name: "Arrange-Act-Assert"
      rule: "Clear structure in every test"
      
    - name: "Independence"
      rule: "Tests don't depend on each other"
      
    - name: "Meaningful Names"
      rule: "test_should_do_x_when_y"

framework:
  name: "Test Pyramid"
  categories:
    - UNIT: "Fast, isolated, many"
    - INTEGRATION: "External dependencies, fewer"
    - E2E: "Full system, few"

personas:
  - name: "ci_runner"
    attack_vectors:
      - "Is this test flaky?"
      - "Will this slow down CI?"
  
  - name: "future_maintainer"
    attack_vectors:
      - "What is this test actually testing?"
      - "Why did this test fail?"

skills:
  - name: "generate-unit-tests"
    triggers: ["unit tests", "generate tests"]
  - name: "find-test-gaps"
    triggers: ["coverage", "missing tests"]
  - name: "fix-flaky-test"
    triggers: ["flaky", "intermittent"]

router:
  shortcuts:
    "::test": "Generate tests"
    "::unit": "Unit tests"
```

---

### 5.2 `property-test-writer`

**Status**: To Build  
**Domain**: Property-Based Testing  
**Extends**: `test-writer`

```yaml
focus: "Hypothesis/fast-check property testing"

heuristics:
  principles:
    - name: "Properties Over Examples"
      rule: "Define invariants, generate inputs"
      
    - name: "Shrinking"
      rule: "Let the framework minimize failing cases"
      
    - name: "Strategy Composition"
      rule: "Build complex inputs from simple ones"

skills:
  - name: "write-property-test"
    triggers: ["property test", "hypothesis", "fast-check"]

router:
  shortcuts:
    "::prop": "Property-based tests"
```

---

### 5.3 `e2e-test-writer`

**Status**: To Build  
**Domain**: End-to-End Testing  
**Extends**: `test-writer`

```yaml
focus: "Playwright/Cypress E2E tests"

heuristics:
  principles:
    - name: "User Journeys"
      rule: "Test complete user workflows"
      
    - name: "Resilient Selectors"
      rule: "data-testid over CSS selectors"
      
    - name: "Wait Strategies"
      rule: "Wait for conditions, not time"
      
    - name: "Visual Regression"
      rule: "Screenshot comparisons for UI"

skills:
  - name: "write-e2e-test"
    triggers: ["e2e test", "playwright", "cypress"]

router:
  shortcuts:
    "::e2e": "E2E tests"
```

---

### 5.4 `api-test-writer`

**Status**: To Build  
**Domain**: API Testing  
**Extends**: `test-writer`

```yaml
focus: "API contract and integration testing"

heuristics:
  principles:
    - name: "Contract Testing"
      rule: "Verify API contracts"
      
    - name: "Status Codes"
      rule: "Test all expected status codes"
      
    - name: "Error Responses"
      rule: "Test error scenarios"
      
    - name: "Authentication"
      rule: "Test with/without auth"

skills:
  - name: "write-api-tests"
    triggers: ["api tests", "endpoint tests"]

router:
  shortcuts:
    "::api-test": "API tests"
```

---

### 5.5 `mutation-tester`

**Status**: To Build  
**Domain**: Mutation Testing  
**Extends**: `test-writer`

```yaml
focus: "Test quality via mutation testing"

heuristics:
  principles:
    - name: "Mutation Score"
      rule: "Killed mutants / total mutants"
      
    - name: "Surviving Mutants"
      rule: "Each survivor is a test gap"

skills:
  - name: "run-mutation"
    triggers: ["mutation testing", "test quality"]

router:
  shortcuts:
    "::mutate": "Mutation testing"
```

---

### 5.6 `coverage-analyst`

**Status**: To Build  
**Domain**: Test Coverage Analysis  
**Extends**: `test-writer`

```yaml
focus: "Coverage analysis and gap identification"

heuristics:
  principles:
    - name: "Branch Coverage"
      rule: "Branch > line coverage"
      
    - name: "Critical Paths"
      rule: "100% coverage on critical code"
      
    - name: "Diminishing Returns"
      rule: "90%+ overall is usually enough"

skills:
  - name: "analyze-coverage"
    triggers: ["coverage report", "test coverage"]
  - name: "suggest-tests"
    triggers: ["improve coverage", "coverage gaps"]

router:
  shortcuts:
    "::cov": "Coverage analysis"
```

---

### 5.7 `load-tester`

**Status**: To Build  
**Domain**: Performance Testing  
**Extends**: `test-writer`

```yaml
focus: "Load and stress testing"

heuristics:
  principles:
    - name: "Realistic Scenarios"
      rule: "Test patterns matching production"
      
    - name: "Gradual Ramp"
      rule: "Increase load gradually"
      
    - name: "Metrics Collection"
      rule: "Latency, throughput, error rate"

skills:
  - name: "write-load-test"
    triggers: ["load test", "performance test", "stress test"]

router:
  shortcuts:
    "::load": "Load testing"
```

---

### 5.8 `test-data-generator`

**Status**: To Build  
**Domain**: Test Data Generation  
**Extends**: `test-writer`

```yaml
focus: "Generating realistic test data"

heuristics:
  principles:
    - name: "Factories Over Fixtures"
      rule: "Generate data, don't hardcode"
      
    - name: "Edge Cases"
      rule: "Include boundary values"
      
    - name: "Anonymization"
      rule: "No real PII in test data"

skills:
  - name: "generate-test-data"
    triggers: ["test data", "fixtures", "factories"]

router:
  shortcuts:
    "::data": "Test data generation"
```

---

## 6. Architecture & Design (8 Lenses)

### 6.1 `architecture-reviewer`

**Status**: To Build  
**Domain**: System Architecture  
**Extends**: `code-reviewer`

```yaml
focus: "System design, boundaries, scalability"

heuristics:
  principles:
    - name: "Single Responsibility"
      rule: "Each component has one reason to change"
      
    - name: "Dependency Direction"
      rule: "Dependencies point toward stability"
      
    - name: "API Stability"
      rule: "Interfaces change less than implementations"
      
    - name: "Bounded Contexts"
      rule: "Clear boundaries between domains"

personas:
  - name: "new_developer"
    attack_vectors:
      - "How do I navigate this codebase?"
      - "Where does X live?"
  
  - name: "ops_engineer"
    attack_vectors:
      - "Can I deploy this independently?"
      - "What are the failure modes?"

skills:
  - name: "review-architecture"
    triggers: ["architecture review", "system design"]
  - name: "dependency-graph"
    triggers: ["dependencies", "module graph"]

router:
  shortcuts:
    "::arch": "Architecture review"
```

---

### 6.2 `refactor-planner`

**Status**: To Build  
**Domain**: Refactoring Strategy  
**Extends**: `architecture-reviewer`

```yaml
focus: "Safe, incremental refactoring"

heuristics:
  principles:
    - name: "Behavior Preservation"
      rule: "Tests before refactoring"
      
    - name: "Small Steps"
      rule: "One change type at a time"
      
    - name: "Strangler Fig"
      rule: "Gradually replace, don't rewrite"

skills:
  - name: "plan-refactor"
    triggers: ["refactor", "restructure"]
  - name: "strangler-plan"
    triggers: ["strangler fig", "migration"]

router:
  shortcuts:
    "::refactor": "Plan refactoring"
```

---

### 6.3 `ddd-expert`

**Status**: To Build  
**Domain**: Domain-Driven Design  
**Extends**: `architecture-reviewer`

```yaml
focus: "DDD patterns and modeling"

heuristics:
  principles:
    - name: "Ubiquitous Language"
      rule: "Code uses domain terminology"
      
    - name: "Aggregates"
      rule: "Consistency boundaries"
      
    - name: "Bounded Contexts"
      rule: "Explicit context boundaries"
      
    - name: "Domain Events"
      rule: "Communicate between contexts"

skills:
  - name: "model-domain"
    triggers: ["domain model", "ddd"]

router:
  shortcuts:
    "::ddd": "Domain-driven design"
```

---

### 6.4 `microservices-expert`

**Status**: To Build  
**Domain**: Microservices Architecture  
**Extends**: `architecture-reviewer`

```yaml
focus: "Microservices patterns and pitfalls"

heuristics:
  principles:
    - name: "Service Boundaries"
      rule: "Services own their data"
      
    - name: "Communication"
      rule: "Prefer async over sync"
      
    - name: "Resilience"
      rule: "Circuit breakers, retries, timeouts"
      
    - name: "Observability"
      rule: "Distributed tracing required"

skills:
  - name: "review-microservices"
    triggers: ["microservices", "service mesh"]

router:
  shortcuts:
    "::micro": "Microservices patterns"
```

---

### 6.5 `event-driven-expert`

**Status**: To Build  
**Domain**: Event-Driven Architecture  
**Extends**: `architecture-reviewer`

```yaml
focus: "Event sourcing and CQRS patterns"

heuristics:
  principles:
    - name: "Event Immutability"
      rule: "Events are facts, never changed"
      
    - name: "Eventual Consistency"
      rule: "Accept and design for it"
      
    - name: "Idempotency"
      rule: "Handle duplicate events"

skills:
  - name: "design-events"
    triggers: ["event sourcing", "cqrs", "events"]

router:
  shortcuts:
    "::events": "Event-driven patterns"
```

---

### 6.6 `api-designer`

**Status**: To Build  
**Domain**: API Design  
**Extends**: `architecture-reviewer`

```yaml
focus: "REST/GraphQL API design principles"

heuristics:
  principles:
    - name: "Consistency"
      rule: "Same patterns everywhere"
      
    - name: "Versioning"
      rule: "Plan for breaking changes"
      
    - name: "Pagination"
      rule: "Cursor-based for large sets"
      
    - name: "Error Design"
      rule: "Errors are part of the contract"

skills:
  - name: "design-api"
    triggers: ["api design", "rest design"]

router:
  shortcuts:
    "::api-design": "API design review"
```

---

### 6.7 `database-designer`

**Status**: To Build  
**Domain**: Database Design  
**Extends**: `architecture-reviewer`

```yaml
focus: "Schema design and optimization"

heuristics:
  principles:
    - name: "Normalization"
      rule: "3NF unless denormalization justified"
      
    - name: "Indexing"
      rule: "Index based on query patterns"
      
    - name: "Migrations"
      rule: "Backward compatible changes"
      
    - name: "Constraints"
      rule: "Enforce at database level"

skills:
  - name: "review-schema"
    triggers: ["database design", "schema review"]

router:
  shortcuts:
    "::db": "Database design review"
```

---

### 6.8 `scalability-reviewer`

**Status**: To Build  
**Domain**: Scalability Analysis  
**Extends**: `architecture-reviewer`

```yaml
focus: "Scaling patterns and bottlenecks"

heuristics:
  principles:
    - name: "Horizontal First"
      rule: "Scale out before up"
      
    - name: "Stateless Services"
      rule: "State in external stores"
      
    - name: "Caching Strategy"
      rule: "Cache at every layer"
      
    - name: "Sharding"
      rule: "Plan data partitioning"

skills:
  - name: "analyze-scalability"
    triggers: ["scalability", "scaling"]

router:
  shortcuts:
    "::scale": "Scalability analysis"
```

---

## 7. DevOps & Infrastructure (10 Lenses)

### 7.1 `docker-expert`

**Status**: To Build  
**Domain**: Docker/Containers  
**Extends**: —

```yaml
focus: "Dockerfile optimization and container patterns"

heuristics:
  principles:
    - name: "Layer Optimization"
      rule: "Order commands for cache efficiency"
      
    - name: "Multi-Stage Builds"
      rule: "Separate build and runtime"
      
    - name: "Security"
      rule: "Non-root user, minimal base"
      
    - name: "Size Minimization"
      rule: "Alpine or distroless"

validators:
  deterministic:
    - name: "hadolint"
      script: "hadolint Dockerfile"
      severity: "warning"

skills:
  - name: "optimize-dockerfile"
    triggers: ["dockerfile", "docker optimization"]
  - name: "multi-stage"
    triggers: ["multi-stage build"]

router:
  shortcuts:
    "::docker": "Docker best practices"
```

---

### 7.2 `kubernetes-expert`

**Status**: To Build  
**Domain**: Kubernetes  
**Extends**: `docker-expert`

```yaml
focus: "Kubernetes patterns and operations"

heuristics:
  principles:
    - name: "Resource Limits"
      rule: "Always set limits and requests"
      
    - name: "Health Probes"
      rule: "Liveness + readiness probes"
      
    - name: "ConfigMaps/Secrets"
      rule: "External configuration"
      
    - name: "Pod Disruption Budgets"
      rule: "Ensure availability during updates"

skills:
  - name: "review-manifests"
    triggers: ["kubernetes", "k8s manifests"]

router:
  shortcuts:
    "::k8s": "Kubernetes best practices"
```

---

### 7.3 `ci-optimizer`

**Status**: To Build  
**Domain**: CI/CD Pipelines  
**Extends**: —

```yaml
focus: "Fast, reliable CI/CD"

heuristics:
  principles:
    - name: "Fail Fast"
      rule: "Quick checks first"
      
    - name: "Parallelization"
      rule: "Independent jobs in parallel"
      
    - name: "Caching"
      rule: "Cache dependencies between runs"
      
    - name: "Flake Detection"
      rule: "Quarantine flaky tests"

skills:
  - name: "optimize-ci"
    triggers: ["ci optimization", "faster builds"]
  - name: "add-caching"
    triggers: ["ci caching"]

router:
  shortcuts:
    "::ci": "CI/CD optimization"
```

---

### 7.4 `github-actions-expert`

**Status**: To Build  
**Domain**: GitHub Actions  
**Extends**: `ci-optimizer`

```yaml
focus: "GitHub Actions workflows"

heuristics:
  principles:
    - name: "Reusable Workflows"
      rule: "DRY with composite actions"
      
    - name: "Matrix Builds"
      rule: "Test across versions"
      
    - name: "Caching"
      rule: "actions/cache for dependencies"
      
    - name: "Secrets"
      rule: "Environments for secrets"

skills:
  - name: "write-workflow"
    triggers: ["github actions", "workflow"]

router:
  shortcuts:
    "::gha": "GitHub Actions"
```

---

### 7.5 `observability-expert`

**Status**: To Build  
**Domain**: Monitoring & Observability  
**Extends**: —

```yaml
focus: "Logs, metrics, traces"

heuristics:
  principles:
    - name: "Three Pillars"
      rule: "Logs + Metrics + Traces"
      
    - name: "Structured Logging"
      rule: "JSON logs with correlation IDs"
      
    - name: "SLOs"
      rule: "Define and measure SLOs"
      
    - name: "Alerting"
      rule: "Alert on symptoms, not causes"

skills:
  - name: "add-observability"
    triggers: ["observability", "monitoring"]

router:
  shortcuts:
    "::obs": "Observability patterns"
```

---

### 7.6 `aws-expert`

**Status**: To Build  
**Domain**: AWS  
**Extends**: —

```yaml
focus: "AWS services and patterns"

heuristics:
  principles:
    - name: "IAM Least Privilege"
      rule: "Minimal permissions"
      
    - name: "Cost Awareness"
      rule: "Tag resources, set budgets"
      
    - name: "Multi-AZ"
      rule: "High availability by default"

skills:
  - name: "aws-review"
    triggers: ["aws", "amazon web services"]

router:
  shortcuts:
    "::aws": "AWS patterns"
```

---

### 7.7 `gcp-expert`

**Status**: To Build  
**Domain**: Google Cloud  
**Extends**: —

```yaml
focus: "GCP services and patterns"

heuristics:
  principles:
    - name: "Service Accounts"
      rule: "Workload identity"
      
    - name: "Regions and Zones"
      rule: "Multi-region for DR"

skills:
  - name: "gcp-review"
    triggers: ["gcp", "google cloud"]

router:
  shortcuts:
    "::gcp": "GCP patterns"
```

---

### 7.8 `azure-expert`

**Status**: To Build  
**Domain**: Microsoft Azure  
**Extends**: —

```yaml
focus: "Azure services and patterns"

skills:
  - name: "azure-review"
    triggers: ["azure", "microsoft azure"]

router:
  shortcuts:
    "::azure": "Azure patterns"
```

---

### 7.9 `helm-expert`

**Status**: To Build  
**Domain**: Helm Charts  
**Extends**: `kubernetes-expert`

```yaml
focus: "Helm chart development"

heuristics:
  principles:
    - name: "Values Schema"
      rule: "values.schema.json for validation"
      
    - name: "Templates"
      rule: "DRY with _helpers.tpl"
      
    - name: "Testing"
      rule: "helm test and helm lint"

skills:
  - name: "write-chart"
    triggers: ["helm chart", "helm template"]

router:
  shortcuts:
    "::helm": "Helm patterns"
```

---

### 7.10 `pulumi-expert`

**Status**: To Build  
**Domain**: Pulumi IaC  
**Extends**: —

```yaml
focus: "Pulumi infrastructure as code"

heuristics:
  principles:
    - name: "Real Code"
      rule: "Use TypeScript/Python properly"
      
    - name: "Component Resources"
      rule: "Encapsulate patterns"
      
    - name: "State Management"
      rule: "Pulumi Cloud or self-hosted"

skills:
  - name: "pulumi-review"
    triggers: ["pulumi"]

router:
  shortcuts:
    "::pulumi": "Pulumi patterns"
```

---

## 8. Data & ML (10 Lenses)

### 8.1 `notebook-reviewer`

**Status**: To Build  
**Domain**: Jupyter Notebooks  
**Extends**: `python-expert`

```yaml
focus: "Notebook quality and reproducibility"

heuristics:
  principles:
    - name: "Linear Execution"
      rule: "Run top-to-bottom without errors"
      
    - name: "No Hidden State"
      rule: "Restart and run all"
      
    - name: "Pinned Dependencies"
      rule: "requirements.txt in notebook dir"
      
    - name: "Clear Outputs"
      rule: "Commit without outputs or with cleared"

skills:
  - name: "review-notebook"
    triggers: ["notebook review", "jupyter"]
  - name: "extract-to-module"
    triggers: ["extract", "notebook to module"]

router:
  shortcuts:
    "::nb": "Notebook review"
```

---

### 8.2 `data-pipeline-expert`

**Status**: To Build  
**Domain**: Data Pipelines  
**Extends**: `python-expert`

```yaml
focus: "ETL/ELT pipeline patterns"

heuristics:
  principles:
    - name: "Idempotency"
      rule: "Re-running produces same result"
      
    - name: "Schema Evolution"
      rule: "Handle schema changes gracefully"
      
    - name: "Lineage"
      rule: "Track data provenance"
      
    - name: "Quality Gates"
      rule: "Validate at each stage"

skills:
  - name: "review-pipeline"
    triggers: ["data pipeline", "etl"]

router:
  shortcuts:
    "::etl": "Pipeline review"
```

---

### 8.3 `ml-experimenter`

**Status**: To Build  
**Domain**: ML Experiments  
**Extends**: `python-expert`

```yaml
focus: "ML experiment tracking and reproducibility"

heuristics:
  principles:
    - name: "Track Everything"
      rule: "Hyperparams, metrics, artifacts"
      
    - name: "Random Seeds"
      rule: "Explicit and logged"
      
    - name: "Data Versioning"
      rule: "Know what data trained what model"
      
    - name: "Evaluation Protocol"
      rule: "Train/val/test before any feature engineering"

skills:
  - name: "setup-tracking"
    triggers: ["experiment tracking", "mlflow"]

router:
  shortcuts:
    "::exp": "Experiment setup"
```

---

### 8.4 `ml-ops-expert`

**Status**: To Build  
**Domain**: MLOps  
**Extends**: `ml-experimenter`

```yaml
focus: "ML deployment and operations"

heuristics:
  principles:
    - name: "Model Registry"
      rule: "Versioned, centralized models"
      
    - name: "Feature Stores"
      rule: "Consistent features train/serve"
      
    - name: "Monitoring"
      rule: "Data drift, model performance"
      
    - name: "A/B Testing"
      rule: "Statistical rigor in model comparison"

skills:
  - name: "review-mlops"
    triggers: ["mlops", "model deployment"]

router:
  shortcuts:
    "::mlops": "MLOps review"
```

---

### 8.5 `pandas-expert`

**Status**: To Build  
**Domain**: Pandas  
**Extends**: `python-expert`

```yaml
focus: "Pandas performance and idioms"

heuristics:
  principles:
    - name: "Vectorization"
      rule: "No iterrows(), use vectorized ops"
      
    - name: "Method Chaining"
      rule: "Chain operations cleanly"
      
    - name: "Memory Efficiency"
      rule: "Appropriate dtypes"
      
    - name: "Copy vs View"
      rule: "Understand when copies are made"

skills:
  - name: "optimize-pandas"
    triggers: ["pandas optimization"]

router:
  shortcuts:
    "::pd": "Pandas review"
```

---

### 8.6 `sql-analytics-expert`

**Status**: To Build  
**Domain**: Analytics SQL  
**Extends**: `sql-expert`

```yaml
focus: "Analytics queries and window functions"

heuristics:
  principles:
    - name: "Window Functions"
      rule: "Use over() for analytics"
      
    - name: "CTEs"
      rule: "WITH clauses for readability"
      
    - name: "Materialized Views"
      rule: "Pre-compute expensive aggregations"

skills:
  - name: "write-analytics-query"
    triggers: ["analytics query", "reporting"]

router:
  shortcuts:
    "::analytics": "Analytics SQL"
```

---

### 8.7 `dbt-expert`

**Status**: To Build  
**Domain**: dbt  
**Extends**: `sql-analytics-expert`

```yaml
focus: "dbt project patterns"

heuristics:
  principles:
    - name: "Staging Models"
      rule: "One source, one staging model"
      
    - name: "Testing"
      rule: "Schema tests on all models"
      
    - name: "Documentation"
      rule: "Describe every model and column"
      
    - name: "Incremental Models"
      rule: "Use for large tables"

skills:
  - name: "review-dbt"
    triggers: ["dbt review"]

router:
  shortcuts:
    "::dbt": "dbt patterns"
```

---

### 8.8 `spark-expert`

**Status**: To Build  
**Domain**: Apache Spark  
**Extends**: `python-expert`

```yaml
focus: "Spark performance and patterns"

heuristics:
  principles:
    - name: "Partitioning"
      rule: "Partition by cardinality"
      
    - name: "Broadcast Joins"
      rule: "Broadcast small tables"
      
    - name: "Caching"
      rule: "Cache reused DataFrames"
      
    - name: "Skew Handling"
      rule: "Salt keys for skewed joins"

skills:
  - name: "optimize-spark"
    triggers: ["spark optimization"]

router:
  shortcuts:
    "::spark": "Spark review"
```

---

### 8.9 `visualization-expert`

**Status**: To Build  
**Domain**: Data Visualization  
**Extends**: —

```yaml
focus: "Effective data visualization"

heuristics:
  principles:
    - name: "Chart Selection"
      rule: "Right chart for the data story"
      
    - name: "Accessibility"
      rule: "Colorblind-safe palettes"
      
    - name: "Labels"
      rule: "Axis labels, titles, legends"
      
    - name: "Data-Ink Ratio"
      rule: "Minimize non-data ink"

skills:
  - name: "review-visualization"
    triggers: ["visualization", "chart review"]

router:
  shortcuts:
    "::viz": "Visualization review"
```

---

### 8.10 `llm-expert`

**Status**: To Build  
**Domain**: LLM Applications  
**Extends**: `python-expert`

```yaml
focus: "LLM integration patterns"

heuristics:
  principles:
    - name: "Prompt Engineering"
      rule: "Clear instructions, examples, constraints"
      
    - name: "Structured Output"
      rule: "JSON schema for parsing"
      
    - name: "Cost Management"
      rule: "Token counts, caching, batching"
      
    - name: "Evaluation"
      rule: "Systematic eval sets"
      
    - name: "Safety"
      rule: "Input/output filtering"

skills:
  - name: "review-llm-integration"
    triggers: ["llm integration", "openai", "anthropic"]

router:
  shortcuts:
    "::llm": "LLM patterns"
```

---

## 9. Security (6 Lenses)

> **Note**: `security-auditor` (section 2.2) is the foundation for all security lenses and extends `code-reviewer`. The lenses below extend `security-auditor`.

### 9.2 `threat-modeler`

**Status**: To Build  
**Domain**: Threat Modeling  
**Extends**: `security-auditor`

```yaml
focus: "STRIDE threat modeling"

heuristics:
  principles:
    - name: "STRIDE"
      rule: "Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation"
      
    - name: "Data Flow Diagrams"
      rule: "Map trust boundaries"
      
    - name: "Attack Trees"
      rule: "Enumerate attack paths"

skills:
  - name: "create-threat-model"
    triggers: ["threat model", "stride"]

router:
  shortcuts:
    "::threat": "Threat modeling"
```

---

### 9.3 `penetration-tester`

**Status**: To Build  
**Domain**: Penetration Testing  
**Extends**: `security-auditor`

```yaml
focus: "Offensive security testing"

heuristics:
  principles:
    - name: "OWASP Testing Guide"
      rule: "Systematic testing methodology"
      
    - name: "Reconnaissance"
      rule: "Information gathering first"
      
    - name: "Documentation"
      rule: "Document all findings with PoC"

skills:
  - name: "pentest-checklist"
    triggers: ["pentest", "penetration test"]

router:
  shortcuts:
    "::pentest": "Penetration testing"
```

---

### 9.4 `compliance-reviewer`

**Status**: To Build  
**Domain**: Compliance  
**Extends**: `security-auditor`

```yaml
focus: "SOC2, HIPAA, GDPR compliance"

heuristics:
  principles:
    - name: "Data Classification"
      rule: "Know what data you have"
      
    - name: "Access Controls"
      rule: "Least privilege, audit trails"
      
    - name: "Retention Policies"
      rule: "Know how long to keep data"
      
    - name: "Incident Response"
      rule: "Plan before you need it"

skills:
  - name: "compliance-review"
    triggers: ["compliance", "soc2", "hipaa", "gdpr"]

router:
  shortcuts:
    "::compliance": "Compliance review"
```

---

### 9.5 `crypto-reviewer`

**Status**: To Build  
**Domain**: Cryptography  
**Extends**: `security-auditor`

```yaml
focus: "Cryptographic implementations"

heuristics:
  principles:
    - name: "Don't Roll Your Own"
      rule: "Use established libraries"
      
    - name: "Modern Algorithms"
      rule: "AES-256, bcrypt/argon2, Ed25519"
      never:
        - "MD5 for security"
        - "SHA1 for security"
        - "DES/3DES"
        - "ECB mode"
      
    - name: "Key Management"
      rule: "HSMs or key management services"

skills:
  - name: "crypto-review"
    triggers: ["cryptography", "encryption"]

router:
  shortcuts:
    "::crypto": "Cryptography review"
```

---

### 9.6 `supply-chain-security`

**Status**: To Build  
**Domain**: Supply Chain Security  
**Extends**: `security-auditor`

```yaml
focus: "Dependency and build security"

heuristics:
  principles:
    - name: "SBOMs"
      rule: "Software Bill of Materials"
      
    - name: "Signed Artifacts"
      rule: "Sign releases"
      
    - name: "Dependency Pinning"
      rule: "Pin exact versions with hashes"
      
    - name: "Build Reproducibility"
      rule: "Same input → same output"

skills:
  - name: "supply-chain-review"
    triggers: ["supply chain", "sbom"]

router:
  shortcuts:
    "::supply": "Supply chain security"
```

---

## 10. Business & Product (8 Lenses)

### 10.1 `pm-strategist`

**Status**: To Build  
**Domain**: Product Management  
**Extends**: `team-pm`

```yaml
focus: "Product strategy and prioritization"

heuristics:
  principles:
    - name: "Problem First"
      rule: "Validate problem before solution"
      
    - name: "Metrics Before Features"
      rule: "How will we know it worked?"
      
    - name: "User Story Format"
      rule: "As a [who], I want [what], so that [why]"
      
    - name: "RICE Scoring"
      rule: "Reach × Impact × Confidence / Effort"

framework:
  name: "Product Development"
  categories:
    - DISCOVERY: "Problem validation, user research"
    - DEFINITION: "PRDs, specs, success metrics"
    - DELIVERY: "Execution, iteration"
    - EVALUATION: "Metrics review, learnings"

personas:
  - name: "ceo"
    attack_vectors:
      - "Why is this the highest priority?"
      - "What's the ROI?"
  
  - name: "engineer"
    attack_vectors:
      - "What exactly should I build?"
      - "What's the MVP?"
  
  - name: "customer"
    attack_vectors:
      - "How does this help me?"
      - "Is this worth paying for?"

skills:
  - name: "write-prd"
    triggers: ["prd", "product requirements"]
  - name: "prioritize-backlog"
    triggers: ["prioritize", "rice scoring"]
  - name: "write-user-story"
    triggers: ["user story", "stories"]

router:
  shortcuts:
    "::pm": "Product management"
    "::prd": "Write PRD"
    "::rice": "RICE scoring"
```

---

### 10.2 `prfaq-writer`

**Status**: To Build  
**Domain**: PRFAQ Documents  
**Extends**: `pm-strategist`

```yaml
focus: "Amazon-style PRFAQ documents"

heuristics:
  principles:
    - name: "Working Backwards"
      rule: "Start with the press release"
      
    - name: "Customer Focus"
      rule: "Write from customer perspective"
      
    - name: "FAQ Anticipation"
      rule: "Answer objections proactively"

skills:
  - name: "write-prfaq"
    triggers: ["prfaq", "press release"]

router:
  shortcuts:
    "::prfaq": "Write PRFAQ"
```

---

### 10.3 `pitch-deck-writer`

**Status**: To Build  
**Domain**: Pitch Decks  
**Extends**: —

```yaml
focus: "Investor pitch deck structure"

heuristics:
  principles:
    - name: "Hook First"
      rule: "Grab attention in slide 1"
      
    - name: "Problem-Solution"
      rule: "Clear problem before solution"
      
    - name: "Traction"
      rule: "Show proof of progress"
      
    - name: "Team"
      rule: "Why you can execute"

skills:
  - name: "write-pitch-deck"
    triggers: ["pitch deck", "investor deck"]

router:
  shortcuts:
    "::pitch": "Pitch deck structure"
```

---

### 10.4 `okr-writer`

**Status**: To Build  
**Domain**: OKRs  
**Extends**: `pm-strategist`

```yaml
focus: "Objectives and Key Results"

heuristics:
  principles:
    - name: "Ambitious Objectives"
      rule: "Inspiring, not incremental"
      
    - name: "Measurable Key Results"
      rule: "Numbers, not activities"
      
    - name: "3-5 KRs per Objective"
      rule: "Focus, not exhaustive list"

skills:
  - name: "write-okrs"
    triggers: ["okr", "objectives"]

router:
  shortcuts:
    "::okr": "Write OKRs"
```

---

### 10.5 `technical-spec-writer`

**Status**: To Build  
**Domain**: Technical Specifications  
**Extends**: `tech-writer`

```yaml
focus: "Technical design documents"

heuristics:
  principles:
    - name: "Context"
      rule: "Background and motivation"
      
    - name: "Goals and Non-Goals"
      rule: "Explicit scope"
      
    - name: "Options Considered"
      rule: "Show alternatives and tradeoffs"
      
    - name: "Proposed Solution"
      rule: "Detailed design"

skills:
  - name: "write-spec"
    triggers: ["technical spec", "design doc", "rfc"]

router:
  shortcuts:
    "::spec": "Technical spec"
```

---

### 10.6 `meeting-notes-writer`

**Status**: To Build  
**Domain**: Meeting Documentation  
**Extends**: —

```yaml
focus: "Effective meeting notes"

heuristics:
  principles:
    - name: "Decisions"
      rule: "Capture all decisions explicitly"
      
    - name: "Action Items"
      rule: "Who, what, when"
      
    - name: "Context"
      rule: "Link to relevant docs"

skills:
  - name: "write-meeting-notes"
    triggers: ["meeting notes", "minutes"]

router:
  shortcuts:
    "::notes": "Meeting notes"
```

---

### 10.7 `email-writer`

**Status**: To Build  
**Domain**: Professional Email  
**Extends**: —

```yaml
focus: "Clear, effective business email"

heuristics:
  principles:
    - name: "Subject Line"
      rule: "Action + topic in subject"
      
    - name: "BLUF"
      rule: "Bottom Line Up Front"
      
    - name: "One Ask"
      rule: "Clear single call to action"
      
    - name: "Brevity"
      rule: "5 sentences or less ideal"

skills:
  - name: "write-email"
    triggers: ["email", "draft email"]

router:
  shortcuts:
    "::email": "Write email"
```

---

### 10.8 `incident-reporter`

**Status**: To Build  
**Domain**: Incident Reports  
**Extends**: —

```yaml
focus: "Post-incident documentation"

heuristics:
  principles:
    - name: "Timeline"
      rule: "Precise chronology"
      
    - name: "Root Cause"
      rule: "5 Whys analysis"
      
    - name: "Blameless"
      rule: "Focus on systems, not people"
      
    - name: "Action Items"
      rule: "Preventive measures with owners"

skills:
  - name: "write-postmortem"
    triggers: ["postmortem", "incident report"]

router:
  shortcuts:
    "::incident": "Incident report"
```

---

## 11. Creative Writing (6 Lenses)

### 11.1 `novelist`

**Status**: To Build  
**Domain**: Fiction Writing  
**Extends**: —

```yaml
focus: "Fiction writing craft"

heuristics:
  principles:
    - name: "Show Don't Tell"
      rule: "Action reveals character"
      
    - name: "Conflict"
      rule: "Every scene needs tension"
      
    - name: "Enter Late, Leave Early"
      rule: "Cut the boring parts"
      
    - name: "Dialogue Tags"
      rule: "'Said' is invisible"

framework:
  name: "Narrative Structure"
  structures:
    - Three-Act Structure
    - Hero's Journey
    - Save the Cat
    - Scene-Sequel

personas:
  - name: "first_reader"
    attack_vectors:
      - "Would I keep reading?"
      - "Do I care about this character?"

skills:
  - name: "plot-outline"
    triggers: ["plot", "outline"]
  - name: "character-arc"
    triggers: ["character", "arc"]
  - name: "dialogue-polish"
    triggers: ["dialogue"]

router:
  shortcuts:
    "::novel": "Fiction writing"
```

---

### 11.2 `copywriter`

**Status**: To Build  
**Domain**: Marketing Copy  
**Extends**: —

```yaml
focus: "Persuasive marketing copy"

heuristics:
  principles:
    - name: "Benefits Over Features"
      rule: "What's in it for them?"
      
    - name: "Headline First"
      rule: "80% of readers only see headline"
      
    - name: "Social Proof"
      rule: "Show others succeed"
      
    - name: "Clear CTA"
      rule: "One obvious next step"

skills:
  - name: "write-copy"
    triggers: ["copy", "marketing"]

router:
  shortcuts:
    "::copy": "Marketing copy"
```

---

### 11.3 `ux-writer`

**Status**: To Build  
**Domain**: UX Writing  
**Extends**: —

```yaml
focus: "Interface microcopy"

heuristics:
  principles:
    - name: "Clarity Over Cleverness"
      rule: "Be clear, not cute"
      
    - name: "Action-Oriented"
      rule: "Verbs on buttons"
      
    - name: "Error Messages"
      rule: "What went wrong + how to fix"
      
    - name: "Consistent Voice"
      rule: "Same personality throughout"

skills:
  - name: "write-ux-copy"
    triggers: ["ux copy", "microcopy"]

router:
  shortcuts:
    "::ux": "UX writing"
```

---

### 11.4 `blog-writer`

**Status**: To Build  
**Domain**: Blog Posts  
**Extends**: `tech-writer`

```yaml
focus: "Engaging technical blog posts"

heuristics:
  principles:
    - name: "Hook Opening"
      rule: "First paragraph earns second paragraph"
      
    - name: "Scannable Structure"
      rule: "Headers, lists, code blocks"
      
    - name: "Personal Voice"
      rule: "Share your perspective"
      
    - name: "Call to Action"
      rule: "What should reader do next?"

skills:
  - name: "write-blog"
    triggers: ["blog post", "article"]

router:
  shortcuts:
    "::blog": "Blog writing"
```

---

### 11.5 `newsletter-writer`

**Status**: To Build  
**Domain**: Email Newsletters  
**Extends**: —

```yaml
focus: "Engaging newsletter content"

heuristics:
  principles:
    - name: "Subject Line"
      rule: "Open-worthy subject"
      
    - name: "Value Upfront"
      rule: "Deliver value in first scroll"
      
    - name: "Consistent Format"
      rule: "Predictable structure"
      
    - name: "One Primary CTA"
      rule: "Focus the ask"

skills:
  - name: "write-newsletter"
    triggers: ["newsletter"]

router:
  shortcuts:
    "::newsletter": "Newsletter writing"
```

---

### 11.6 `screenwriter`

**Status**: To Build  
**Domain**: Screenwriting  
**Extends**: `novelist`

```yaml
focus: "Screenplay and dialogue"

heuristics:
  principles:
    - name: "Visual Medium"
      rule: "Show through action, not narration"
      
    - name: "Subtext"
      rule: "Characters say one thing, mean another"
      
    - name: "Scene Description"
      rule: "Brief, evocative action lines"
      
    - name: "Format"
      rule: "Industry-standard screenplay format"

skills:
  - name: "write-screenplay"
    triggers: ["screenplay", "script"]

router:
  shortcuts:
    "::script": "Screenwriting"
```

---

## 12. Specialized Domains (4 Lenses)

### 12.1 `legal-writer`

**Status**: To Build  
**Domain**: Legal Documents  
**Extends**: —

```yaml
focus: "Contracts, policies, compliance docs"

heuristics:
  principles:
    - name: "Plain Language"
      rule: "Clear when possible, precise always"
      
    - name: "Defined Terms"
      rule: "Define before use, capitalize"
      
    - name: "Specific Over General"
      rule: "Enumerate explicitly"
      
    - name: "Failure Modes"
      rule: "What if party doesn't comply?"

skills:
  - name: "review-contract"
    triggers: ["contract", "legal review"]
  - name: "plain-language"
    triggers: ["simplify legal", "plain language"]

router:
  shortcuts:
    "::legal": "Legal writing"
```

---

### 12.2 `academic-writer`

**Status**: To Build  
**Domain**: Academic Writing  
**Extends**: —

```yaml
focus: "Research papers, citations, methodology"

heuristics:
  principles:
    - name: "Every Claim Cited"
      rule: "Evidence or citation required"
      
    - name: "IMRaD Structure"
      rule: "Introduction, Methods, Results, Discussion"
      
    - name: "Define Terms"
      rule: "No assumed knowledge"
      
    - name: "Limitations"
      rule: "Acknowledge weaknesses"

skills:
  - name: "write-abstract"
    triggers: ["abstract"]
  - name: "lit-review"
    triggers: ["literature review"]
  - name: "methodology"
    triggers: ["methodology section"]

router:
  shortcuts:
    "::academic": "Academic writing"
```

---

### 12.3 `finance-analyst`

**Status**: To Build  
**Domain**: Financial Analysis  
**Extends**: —

```yaml
focus: "Financial documents and analysis"

heuristics:
  principles:
    - name: "Precision"
      rule: "Numbers are exact"
      
    - name: "Assumptions Stated"
      rule: "Make all assumptions explicit"
      
    - name: "Sensitivity Analysis"
      rule: "What if assumptions change?"
      
    - name: "Audit Trail"
      rule: "Show your work"

skills:
  - name: "financial-review"
    triggers: ["financial analysis", "forecast"]

router:
  shortcuts:
    "::finance": "Financial analysis"
```

---

### 12.4 `medical-writer`

**Status**: To Build  
**Domain**: Medical/Healthcare Content  
**Extends**: —

```yaml
focus: "Healthcare documentation"

heuristics:
  principles:
    - name: "Evidence-Based"
      rule: "Claims require clinical evidence"
      
    - name: "Patient Safety"
      rule: "When in doubt, err toward caution"
      
    - name: "Regulatory Compliance"
      rule: "FDA, HIPAA, clinical guidelines"
      
    - name: "Plain Language"
      rule: "Patient-facing content must be accessible"

skills:
  - name: "medical-review"
    triggers: ["medical", "clinical"]

router:
  shortcuts:
    "::medical": "Medical writing"
```

---

## Inheritance Structure

Lenses use `extends` and `compose` for code reuse (`src/sunwell/core/lens.py:181-182`):

```
                    ┌─────────────────┐
                    │   base-writer   │
                    └────────┬────────┘
                             │ extends
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    tech-writer        novelist            researcher
         │
    ┌────┴────┐
    │         │
api-documenter  sphinx-expert


                    ┌─────────────────┐
                    │     coder       │
                    └────────┬────────┘
                             │ extends
         ┌───────────────────┼───────────────────┐
         │                   │                   │
  code-reviewer      python-expert         test-writer
         │                   │
    security-auditor    fastapi-expert
         │
    threat-modeler
```

**Key principle**: Child lenses inherit parent heuristics but can override with domain-specific rules.

---

## Summary: 100 Lenses

| # | Category | Count | Lenses |
|---|----------|-------|--------|
| 1 | Documentation | 10 | tech-writer ✅, api-documenter, readme-crafter, docstring-writer, changelog-writer, tutorial-writer, howto-writer, reference-writer, explanation-writer, sphinx-expert |
| 2 | Code Quality | 10 | code-reviewer ✅, **security-auditor**, perf-analyst, accessibility-reviewer, i18n-reviewer, dead-code-hunter, dependency-auditor, pr-reviewer, concurrency-reviewer, api-reviewer |
| 3 | Languages | 15 | python-expert, typescript-expert, javascript-expert, go-expert, rust-expert, java-expert, kotlin-expert, swift-expert, csharp-expert, cpp-expert, sql-expert, shell-expert, ruby-expert, php-expert, elixir-expert |
| 4 | Frameworks | 15 | react-expert, nextjs-expert, svelte-expert, vue-expert, angular-expert, fastapi-expert, django-expert, flask-expert, express-expert, rails-expert, spring-expert, tailwind-expert, prisma-expert, graphql-expert, terraform-expert |
| 5 | Testing | 8 | test-writer, property-test-writer, e2e-test-writer, api-test-writer, mutation-tester, coverage-analyst, load-tester, test-data-generator |
| 6 | Architecture | 8 | architecture-reviewer, refactor-planner, ddd-expert, microservices-expert, event-driven-expert, api-designer, database-designer, scalability-reviewer |
| 7 | DevOps | 10 | docker-expert, kubernetes-expert, ci-optimizer, github-actions-expert, observability-expert, aws-expert, gcp-expert, azure-expert, helm-expert, pulumi-expert |
| 8 | Data & ML | 10 | notebook-reviewer, data-pipeline-expert, ml-experimenter, ml-ops-expert, pandas-expert, sql-analytics-expert, dbt-expert, spark-expert, visualization-expert, llm-expert |
| 9 | Security | 5 | threat-modeler, penetration-tester, compliance-reviewer, crypto-reviewer, supply-chain-security (**security-auditor** counted in Code Quality) |
| 10 | Business | 8 | pm-strategist, prfaq-writer, pitch-deck-writer, okr-writer, technical-spec-writer, meeting-notes-writer, email-writer, incident-reporter |
| 11 | Creative | 6 | novelist, copywriter, ux-writer, blog-writer, newsletter-writer, screenwriter |
| 12 | Specialized | 4 | legal-writer, academic-writer, finance-analyst, medical-writer |

**Total**: 10 + 10 + 15 + 15 + 8 + 8 + 10 + 10 + 5 + 8 + 6 + 4 = **99 lenses** + **1 existing** (`code-reviewer`) = **100 lenses**

> **Note**: `security-auditor` is listed in Code Quality (section 2.2) because it's a specialized code review lens. It serves as the base for all Security lenses (section 9).

---

## Testing Strategy

### Lens Validation Suite

Each lens must pass automated validation before merge:

```yaml
validation_requirements:
  schema:
    - Valid YAML syntax
    - Conforms to Lens schema (src/sunwell/core/lens.py)
    - All required fields present (metadata.name, metadata.domain)

  heuristics:
    - Minimum 4 principles per lens
    - Each principle has: rule, always[], never[]
    - No duplicate principle names

  personas:
    - Minimum 2 personas for P0/P1 lenses
    - Each persona has: description, goals[], attack_vectors[]

  validators:
    - At least 1 deterministic validator
    - Scripts are syntactically valid (shellcheck, python -m py_compile)

  skills:
    - Referenced skills exist or are defined inline
    - No circular skill dependencies
```

### Benchmark Integration

Lenses are tested against task corpus in `benchmark/tasks/`:

```yaml
benchmark_thresholds:
  quality_improvement:
    min: 10%          # vs. no lens baseline
    target: 20%       # S-tier threshold

  token_efficiency:
    min: 15%          # reduction vs. no lens
    target: 30%       # S-tier threshold

  task_completion:
    min: 85%          # tasks completed successfully
    target: 95%       # S-tier threshold
```

### Freshness Monitoring

```yaml
freshness_policy:
  review_cycle: quarterly
  deprecation_warning: 6_months_stale
  auto_deprecate: 12_months_stale

  triggers_for_update:
    - Major framework release (e.g., React 19, Python 3.14)
    - Security advisory affecting covered patterns
    - User-reported accuracy issues > 3
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
Build 20 lenses across P0 domains:
- Documentation: 5 (api-documenter, readme-crafter, docstring-writer, changelog-writer, tutorial-writer)
- Code Quality: 5 (security-auditor, perf-analyst, pr-reviewer, concurrency-reviewer, dead-code-hunter)
- Languages: 5 (python-expert, typescript-expert, go-expert, rust-expert, sql-expert)
- Testing: 5 (test-writer, e2e-test-writer, coverage-analyst, api-test-writer, mutation-tester)

### Phase 2: Expansion (Weeks 5-8)
Build 30 lenses across P1 domains:
- Frameworks: 10 (react, nextjs, svelte, fastapi, django, express, tailwind, prisma, graphql, terraform)
- Architecture: 8 (all)
- DevOps: 7 (docker, kubernetes, ci-optimizer, github-actions, observability, aws, helm)
- Data & ML: 5 (notebook-reviewer, data-pipeline, ml-experimenter, pandas-expert, llm-expert)

### Phase 3: Completion (Weeks 9-12)
Build remaining 50 lenses:
- Languages: 10 remaining
- Frameworks: 5 remaining
- DevOps: 3 remaining
- Data & ML: 5 remaining
- Security: 5 remaining
- Business: 8 all
- Creative: 6 all
- Specialized: 4 all

---

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Lens coverage | 11 lenses, 4 domains | 100 lenses, 12 domains | Count in `lenses/` directory |
| S-tier quality | ~50% have all components | 100% have heuristics + personas + validators + skills | Schema validation pass rate |
| Auto-selection accuracy | 4 domains mapped | 12 domains mapped | `lens_detection.py` coverage |
| Quality improvement | No lens baseline | +20% task quality score | `benchmark/` task corpus |
| Token efficiency | Full context injection | +30% token reduction | Selective retrieval metrics |
| Test coverage | 2 lenses tested | 100% lenses tested | `tests/test_lenses.py` |

### Measurement Methods

```yaml
benchmark_corpus:
  location: benchmark/tasks/
  task_types: [code, docs, review, planning, agent]
  comparison: lens_vs_no_lens_baseline

quality_scoring:
  rubric: benchmark/rubrics/quality.yaml
  evaluator: gpt-4o-mini (cost-effective grading)
  metrics: [correctness, completeness, style_adherence]

token_metrics:
  source: src/sunwell/benchmark/runner.py
  tracked: [input_tokens, output_tokens, total_cost]
```

---

## Open Questions

1. **Lens granularity**: Should `fastapi-expert` and `django-expert` both exist, or should there be a single `python-web-expert` with framework sub-modes?

2. **Version pinning**: How do we handle lenses for specific framework versions (e.g., React 18 vs React 19 Server Components)?

3. **Community contributions**: What's the acceptance criteria for community-submitted lenses? Who reviews and merges?

4. **Deprecation policy**: When a lens becomes outdated (e.g., Angular.js), do we deprecate or redirect to successor?

5. **Cross-lens composition**: Should users be able to compose `python-expert + security-auditor` on the fly?

---

## Approval Criteria

This RFC is ready for implementation when:

- [x] Problem statement clearly defines user need
- [x] Design alternatives analyzed with tradeoffs
- [x] Architecture impact documented with code references
- [x] Risk analysis with mitigations
- [x] Testing strategy defined
- [x] Success metrics are measurable
- [ ] Open questions have answers or are deferred with rationale
- [ ] 2+ team members have reviewed

---

## References

### Codebase Evidence

| Component | Location | Description |
|-----------|----------|-------------|
| Lens model | `src/sunwell/core/lens.py:165-299` | Core `Lens` dataclass |
| Lens resolver | `src/sunwell/adaptive/lens_resolver.py:30-134` | Resolution priority logic |
| Lens detection | `src/sunwell/surface/lens_detection.py:16-46` | Domain-to-lens mapping |
| Lens loading | `src/sunwell/schema/loader.py:56` | YAML parsing |
| Fount resolver | `src/sunwell/fount/resolver.py:13-67` | Inheritance resolution |
| Reference lens | `lenses/tech-writer.lens` | S-tier implementation |

### Related RFCs

- RFC-011: Agent Skills (skill integration)
- RFC-021: Portable Workflow Incantations (spellbook)
- RFC-035: Schema compatibility
- RFC-070: Library metadata
- RFC-072: Surface affordances
- RFC-086: Lens detection
- RFC-087: Skill library sources
