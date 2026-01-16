# RFC-021: Spells - Portable Workflow Incantations

| Field | Value |
|-------|-------|
| **RFC** | 021 |
| **Title** | Spells - Portable Workflow Incantations |
| **Status** | Draft |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-010 (Core), RFC-011 (Skills), RFC-020 (Cognitive Router) |
| **Implements** | `src/sunwell/core/spell.py`, lens schema extension |

---

## Abstract

This RFC introduces **Spells** — portable workflow incantations that live inside lenses and provide not just routing metadata, but complete task context including instructions, templates, quality gates, and composable reagents (modules).

*In World of Warcraft, spells are magical abilities with specific effects. Sunwell Spells follow the same pattern: incantations that trigger specific workflows with full context.*

Unlike hardcoded shortcuts, Spells are:
- **Shareable** via the Fount alongside lenses
- **Customizable** per domain, project, and user
- **Composable** — spells can load reagents (modules) and reference other lenses
- **Rich** — beyond `{intent, focus}`, they carry full execution context

This makes Sunwell's command system as powerful as IDE-specific rule files, but portable and lens-native.

---

## Motivation

### The Gap: IDE Rules vs Sunwell Commands

IDE-specific rule systems (like Cursor's `.mdc` files) contain rich context:

```markdown
# .cursor/rules/commands/audit/RULE.mdc
---
description: Validate documentation against source code
globs: ["docs/**/*.md"]
triggers: ["::a", "audit", "validate"]
---

## Instructions

1. First, identify all technical claims in the document
2. For each claim, locate the source code that validates it
3. Score confidence based on evidence strength
4. Report findings in the standard format

## Output Template

| Claim | Evidence | Confidence | Status |
|-------|----------|------------|--------|

## Quality Gates

- [ ] All code references use `file:line` format
- [ ] Confidence scores are justified
- [ ] No unverified claims marked as verified

## Modules

- @modules/evidence-handling
- @modules/confidence-scoring
```

Sunwell's current commands (RFC-020) only provide routing:

```python
"::a": {"intent": "code_review", "focus": ["audit", "validation"]}
```

**Missing**: Instructions, templates, quality gates, module composition.

### The Vision: Spells as Portable Incantations

```yaml
# In code-reviewer.lens
spellbook:
  - incantation: "::security"
    aliases: ["::sec", "::s"]
    description: "Deep security review with OWASP checklist"
    intent: code_review
    focus: ["security", "vulnerability", "injection", "auth"]
    
    # Full context (like IDE rules)
    instructions: |
      1. Check for injection vulnerabilities (SQL, XSS, command)
      2. Verify authentication and session handling
      3. Review authorization and access control
      4. Check cryptographic implementations
      5. Identify information disclosure risks
    
    template: |
      ## Security Review: {{filename}}
      
      ### Critical Issues
      | Issue | Location | Severity | Recommendation |
      |-------|----------|----------|----------------|
      
      ### OWASP Checklist
      - [ ] A01: Broken Access Control
      - [ ] A02: Cryptographic Failures
      - [ ] A03: Injection
      ...
    
    validation:
      mode: warn  # warn | block | log
      gates:
        - "All issues have severity ratings"
        - "Recommendations are actionable"
        - "No false positives without justification"
    
    reagents:  # Components to load (WoW reagents are spell components!)
      - type: heuristic
        name: "Security First"
      - type: heuristic
        name: "Input Validation"
      - type: validator
        name: "security-check"
```

Now `::security` (or `::sec` or `::s`) provides **everything** needed to execute the task:
- Routing (intent, focus, lens)
- Instructions (how to approach)
- Template (expected output)
- Validation (quality gates with enforcement mode)
- Reagents (what to load)

---

## Terminology

| WoW Concept | Sunwell Equivalent | Description |
|-------------|-------------------|-------------|
| **Spell** | Workflow trigger | A reusable task definition |
| **Incantation** | Trigger | The `::command` that casts the spell |
| **Spellbook** | Collection | All spells in a lens |
| **Grimoire** | Loader | Manages spell discovery and resolution |
| **Reagents** | Modules | Components required to cast (heuristics, personas) |
| **Cantrips** | Built-in defaults | Simple spells always available |
| **Cast** | Execute | Running the spell |

---

## Architecture

### Spell Schema

```yaml
# Full spell definition
spellbook:
  - incantation: string          # Primary trigger "::security"
    aliases: list[string]        # Short forms ["::sec", "::s"]
    description: string          # Human-readable description
    
    # === ROUTING (RFC-020) ===
    intent: string               # code_review, documentation, testing, etc.
    focus: list[string]          # Keywords for retrieval boosting
    complexity: simple|moderate|complex
    top_k: int                   # Override default retrieval count (3-10)
    threshold: float             # Minimum relevance (0.2-0.5)
    
    # === CONTEXT ===
    instructions: string         # Detailed task guidance (markdown)
    template: string             # Expected output structure (with variables)
    examples:                    # Good/bad examples for few-shot learning
      - content: string
        quality: good|bad
        explanation: string      # Why this is good/bad
    
    # === REAGENTS (Modules) ===
    reagents:                    # Components required to cast
      - type: heuristic|persona|validator|lens
        name: string             # Name within the lens
        source: string           # Optional: lens name for cross-lens refs
        mode: include|boost      # include: force add, boost: increase priority
    
    # === VALIDATION ===
    validation:
      mode: warn|block|log       # How strictly to enforce
      gates: list[string]        # Checklist items
      must_contain: list[string] # Output must include these
      must_not_contain: list[string]
    
    # === WORKFLOW (RFC-011) ===
    skill: string                # Execute a specific skill
```

### Template Variables

Templates support these built-in variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{filename}}` | Current file name | `auth.py` |
| `{{filepath}}` | Full file path | `src/auth/auth.py` |
| `{{language}}` | Detected language | `python` |
| `{{date}}` | Current date | `2026-01-16` |
| `{{time}}` | Current time | `14:32:05` |
| `{{user}}` | Current user | `llane` |
| `{{lens}}` | Active lens name | `code-reviewer` |
| `{{project}}` | Project name | `sunwell` |

Custom variables can be defined in project config:

```yaml
# .sunwell/config.yaml
template_vars:
  team: "Platform Team"
  jira_prefix: "SUN"
```

### Resolution Order

```
User types: "::security review auth.py"
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1: User Spells (~/.sunwell/spells.yaml)                   │
│           User's personal spell customizations                   │
│                                                                  │
│  LAYER 2: Project Spells (.sunwell/spells.yaml)                  │
│           Project-specific spells and overrides                  │
│                                                                  │
│  LAYER 3: Active Lens (code-reviewer.lens)                       │
│           Domain-specific spells from lens spellbook             │
│                                                                  │
│  LAYER 4: Sunwell Cantrips (built-in)                            │
│           Default spells for common operations                   │
└──────────────────────────────────────────────────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  SpellResult  │
            │ - routing     │
            │ - instructions│
            │ - template    │
            │ - reagents    │
            │ - validation  │
            └───────────────┘
                    │
                    ▼
            Grimoire casts spell via CognitiveRouter
```

### Partial Override (Merge Semantics)

When a spell is defined at multiple layers, fields merge intelligently:

```yaml
# Layer 3 (lens) defines base spell
- incantation: "::security"
  instructions: |
    Check for OWASP Top 10...
  validation:
    mode: warn
    gates:
      - "All issues have severity"

# Layer 2 (project) adds to it
- incantation: "::security"
  merge: true  # Merge with lower layers instead of replace
  validation:
    gates:
      - "Include JIRA ticket"  # Added to existing gates
  template_vars:
    team: "Security Team"
```

**Merge rules**:
- `instructions`: Replace (use `instructions_append` to add)
- `focus`: Union of all focus terms
- `validation.gates`: Concatenate
- `reagents`: Concatenate (dedupe by type+name)
- Other fields: Override

### Integration with Generation

```
SpellResult
      │
      ├─► Routing → Select lens, adjust top_k, focus-boost query
      │
      ├─► Reagents → Load specific heuristics/personas/validators
      │      │
      │      ├─► mode: include → Force-add to context
      │      └─► mode: boost → Increase retrieval priority
      │
      ├─► Instructions → Prepend to system prompt
      │
      ├─► Template → Append to system prompt as expected format
      │
      ├─► Cast (Execute) → Generate response
      │
      └─► Validation → Post-generation check
             │
             ├─► mode: log → Log failures, return result
             ├─► mode: warn → Log + annotate result with warnings
             └─► mode: block → Retry or fail if gates not met
```

---

## Implementation

### Data Structures

```python
# src/sunwell/core/spell.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ReagentType(str, Enum):
    """Types of reagents that can be loaded by a spell."""
    HEURISTIC = "heuristic"
    PERSONA = "persona"
    VALIDATOR = "validator"
    LENS = "lens"


class ReagentMode(str, Enum):
    """How a reagent should be loaded."""
    INCLUDE = "include"  # Force-add to context
    BOOST = "boost"      # Increase retrieval priority


class ValidationMode(str, Enum):
    """How strictly to enforce quality gates."""
    LOG = "log"      # Log failures, return result anyway
    WARN = "warn"    # Log + annotate result with warnings
    BLOCK = "block"  # Retry or fail if gates not met


@dataclass(frozen=True, slots=True)
class Reagent:
    """A component required to cast a spell.
    
    Like WoW reagents, these are loaded when casting.
    """
    type: ReagentType
    name: str
    source: str | None = None  # Lens name for cross-lens refs
    mode: ReagentMode = ReagentMode.INCLUDE
    
    def __str__(self) -> str:
        source_str = f"{self.source}:" if self.source else ""
        return f"{self.type.value}:{source_str}{self.name}"


@dataclass(frozen=True, slots=True)
class SpellExample:
    """Good or bad example for a spell."""
    content: str
    quality: Literal["good", "bad"]
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class SpellValidation:
    """Validation configuration for a spell."""
    mode: ValidationMode = ValidationMode.WARN
    gates: tuple[str, ...] = ()
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Spell:
    """A portable workflow incantation with full execution context.
    
    Spells are magical incantations that trigger specific workflows
    with complete context — like WoW's spell system.
    """
    
    # Identity
    incantation: str                  # "::security", "::audit", etc.
    description: str                  # Human-readable description
    aliases: tuple[str, ...] = ()     # Short forms ["::sec", "::s"]
    
    # Routing (RFC-020)
    intent: str = "unknown"           # code_review, documentation, etc.
    focus: tuple[str, ...] = ()       # Keywords for retrieval boosting
    complexity: str = "moderate"      # simple, moderate, complex
    top_k: int | None = None          # Override default retrieval count
    threshold: float | None = None    # Override default threshold
    
    # Context
    instructions: str = ""            # Detailed task guidance
    template: str = ""                # Expected output structure
    examples: tuple[SpellExample, ...] = ()
    
    # Reagents (Modules)
    reagents: tuple[Reagent, ...] = ()
    
    # Validation
    validation: SpellValidation = field(default_factory=SpellValidation)
    
    # Workflow
    skill: str | None = None          # Execute a specific skill
    
    # Merge behavior
    merge: bool = False               # Merge with lower layers
    instructions_append: str = ""     # Append to instructions (for merge)
    
    def all_incantations(self) -> tuple[str, ...]:
        """Return all incantations including aliases."""
        return (self.incantation,) + self.aliases
    
    def to_routing_decision(self) -> "RoutingDecision":
        """Convert to RoutingDecision for CognitiveRouter."""
        from sunwell.routing.cognitive_router import (
            RoutingDecision, Intent, Complexity
        )
        
        return RoutingDecision(
            intent=Intent(self.intent),
            lens="",  # Determined by active lens
            secondary_lenses=[],
            focus=list(self.focus),
            complexity=Complexity(self.complexity),
            top_k=self.top_k or 5,
            threshold=self.threshold or 0.3,
            confidence=1.0,  # Spells are deterministic
            reasoning=f"Spell: {self.incantation}",
        )
    
    def to_system_context(self, template_vars: dict[str, str] | None = None) -> str:
        """Generate system prompt additions from spell context."""
        parts = []
        vars_ = template_vars or {}
        
        if self.instructions:
            instructions = self._apply_template_vars(self.instructions, vars_)
            parts.append(f"## Task Instructions\n\n{instructions}")
        
        if self.template:
            template = self._apply_template_vars(self.template, vars_)
            parts.append(f"## Expected Output Format\n\n{template}")
        
        if self.validation.gates:
            gates = "\n".join(f"- [ ] {g}" for g in self.validation.gates)
            parts.append(f"## Quality Checklist\n\n{gates}")
        
        if self.examples:
            good = [e for e in self.examples if e.quality == "good"]
            bad = [e for e in self.examples if e.quality == "bad"]
            
            if good:
                parts.append("## Good Examples\n\n" + "\n\n".join(
                    f"```\n{e.content}\n```" for e in good
                ))
            if bad:
                parts.append("## Avoid These Patterns\n\n" + "\n\n".join(
                    f"```\n{e.content}\n```\n*Why:* {e.explanation}" for e in bad
                ))
        
        return "\n\n---\n\n".join(parts)
    
    def _apply_template_vars(self, text: str, vars_: dict[str, str]) -> str:
        """Apply template variables to text."""
        result = text
        for key, value in vars_.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result
    
    def merge_with(self, base: "Spell") -> "Spell":
        """Merge this spell with a base spell (for override layers)."""
        if not self.merge:
            return self  # Full override
        
        # Merge fields
        merged_focus = tuple(set(base.focus) | set(self.focus))
        merged_gates = base.validation.gates + self.validation.gates
        merged_reagents = self._dedupe_reagents(base.reagents + self.reagents)
        
        # Instructions: append if instructions_append set
        merged_instructions = base.instructions
        if self.instructions:
            merged_instructions = self.instructions
        if self.instructions_append:
            merged_instructions = f"{merged_instructions}\n\n{self.instructions_append}"
        
        return Spell(
            incantation=self.incantation,
            description=self.description or base.description,
            aliases=self.aliases or base.aliases,
            intent=self.intent if self.intent != "unknown" else base.intent,
            focus=merged_focus,
            complexity=self.complexity if self.complexity != "moderate" else base.complexity,
            top_k=self.top_k or base.top_k,
            threshold=self.threshold or base.threshold,
            instructions=merged_instructions,
            template=self.template or base.template,
            examples=self.examples or base.examples,
            reagents=merged_reagents,
            validation=SpellValidation(
                mode=self.validation.mode,
                gates=merged_gates,
                must_contain=self.validation.must_contain or base.validation.must_contain,
                must_not_contain=self.validation.must_not_contain or base.validation.must_not_contain,
            ),
            skill=self.skill or base.skill,
            merge=False,  # Result is fully resolved
        )
    
    def _dedupe_reagents(self, reagents: tuple[Reagent, ...]) -> tuple[Reagent, ...]:
        """Deduplicate reagents by type+name."""
        seen = set()
        result = []
        for r in reagents:
            key = (r.type, r.name, r.source)
            if key not in seen:
                seen.add(key)
                result.append(r)
        return tuple(result)


@dataclass
class Grimoire:
    """Loads and manages spells from all sources.
    
    The Grimoire is the spellbook manager — it discovers spells from
    user config, project config, active lens, and built-in cantrips.
    """
    
    user_path: str = "~/.sunwell/spells.yaml"
    project_path: str = ".sunwell/spells.yaml"
    
    _user_spells: dict[str, Spell] = field(default_factory=dict)
    _project_spells: dict[str, Spell] = field(default_factory=dict)
    _lens_spells: dict[str, Spell] = field(default_factory=dict)
    _cantrips: dict[str, Spell] = field(default_factory=dict)  # Built-in defaults
    
    # Alias resolution cache
    _alias_map: dict[str, str] = field(default_factory=dict)
    
    def load(self, lens: "Lens | None" = None) -> None:
        """Load spells from all sources (gather the spellbooks)."""
        import os
        from pathlib import Path
        
        # Load user spells
        user_path = Path(os.path.expanduser(self.user_path))
        if user_path.exists():
            self._user_spells = self._load_yaml(user_path)
        
        # Load project spells
        project_path = Path(self.project_path)
        if project_path.exists():
            self._project_spells = self._load_yaml(project_path)
        
        # Load lens spells
        if lens and lens.spellbook:
            for spell in lens.spellbook:
                self._lens_spells[spell.incantation] = spell
                for alias in spell.aliases:
                    self._alias_map[alias] = spell.incantation
        
        # Load cantrips (built-in defaults)
        self._cantrips = self._get_cantrips()
        
        # Build alias map for all layers
        self._build_alias_map()
    
    def _load_yaml(self, path: "Path") -> dict[str, Spell]:
        """Load spells from a YAML spellbook."""
        import yaml
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        spells = {}
        for spell_data in data.get("spellbook", []):
            spell = self._parse_spell(spell_data)
            spells[spell.incantation] = spell
        
        return spells
    
    def _parse_spell(self, data: dict) -> Spell:
        """Parse a spell from YAML data."""
        # Parse reagents
        reagents = []
        for r in data.get("reagents", []):
            reagents.append(Reagent(
                type=ReagentType(r.get("type", "heuristic")),
                name=r["name"],
                source=r.get("source"),
                mode=ReagentMode(r.get("mode", "include")),
            ))
        
        # Parse validation
        validation_data = data.get("validation", {})
        validation = SpellValidation(
            mode=ValidationMode(validation_data.get("mode", "warn")),
            gates=tuple(validation_data.get("gates", [])),
            must_contain=tuple(validation_data.get("must_contain", [])),
            must_not_contain=tuple(validation_data.get("must_not_contain", [])),
        )
        
        # Parse examples
        examples = []
        for e in data.get("examples", []):
            examples.append(SpellExample(
                content=e["content"],
                quality=e.get("quality", "good"),
                explanation=e.get("explanation", ""),
            ))
        
        return Spell(
            incantation=data["incantation"],
            description=data.get("description", ""),
            aliases=tuple(data.get("aliases", [])),
            intent=data.get("intent", "unknown"),
            focus=tuple(data.get("focus", [])),
            complexity=data.get("complexity", "moderate"),
            top_k=data.get("top_k"),
            threshold=data.get("threshold"),
            instructions=data.get("instructions", ""),
            template=data.get("template", ""),
            examples=tuple(examples),
            reagents=tuple(reagents),
            validation=validation,
            skill=data.get("skill"),
            merge=data.get("merge", False),
            instructions_append=data.get("instructions_append", ""),
        )
    
    def _get_cantrips(self) -> dict[str, Spell]:
        """Get built-in cantrip spells (simple, always-available)."""
        return {
            "::a": Spell(
                incantation="::a",
                aliases=("::audit",),
                description="Audit code or documentation for accuracy",
                intent="code_review",
                focus=("audit", "validation", "accuracy"),
            ),
            "::review": Spell(
                incantation="::review",
                aliases=("::r",),
                description="General code review",
                intent="code_review",
                focus=("quality", "patterns", "issues"),
            ),
            "::test": Spell(
                incantation="::test",
                aliases=("::t",),
                description="Generate or review tests",
                intent="testing",
                focus=("testing", "coverage", "edge cases"),
            ),
            "::doc": Spell(
                incantation="::doc",
                aliases=("::d", "::write"),
                description="Write or improve documentation",
                intent="documentation",
                focus=("clarity", "examples", "structure"),
            ),
            "::help": Spell(
                incantation="::help",
                aliases=("::?", "::h"),
                description="Show available spells and help",
                intent="explanation",
                focus=("help", "commands", "usage"),
            ),
        }
    
    def _build_alias_map(self) -> None:
        """Build alias → incantation mapping for all layers."""
        for source in [
            self._cantrips,
            self._lens_spells,
            self._project_spells,
            self._user_spells,
        ]:
            for incantation, spell in source.items():
                for alias in spell.aliases:
                    self._alias_map[alias] = incantation
    
    def resolve(self, incantation: str) -> Spell | None:
        """Resolve an incantation (or alias) to a spell.
        
        Resolution order: user → project → lens → cantrips
        Merges spells if `merge: true` is set.
        """
        # Resolve alias to primary incantation
        primary = self._alias_map.get(incantation, incantation)
        
        # Collect spells from all layers (in reverse priority)
        layers = [
            self._cantrips.get(primary),
            self._lens_spells.get(primary),
            self._project_spells.get(primary),
            self._user_spells.get(primary),
        ]
        
        # Filter None and merge
        spells = [s for s in layers if s is not None]
        if not spells:
            return None
        
        # Start with base, merge higher layers
        result = spells[0]
        for spell in spells[1:]:
            result = spell.merge_with(result)
        
        return result
    
    def list_spells(self) -> list[Spell]:
        """List all available spells."""
        seen = set()
        result = []
        
        # Process in priority order
        for source in [
            self._user_spells,
            self._project_spells,
            self._lens_spells,
            self._cantrips,
        ]:
            for incantation in source:
                if incantation not in seen:
                    seen.add(incantation)
                    resolved = self.resolve(incantation)
                    if resolved:
                        result.append(resolved)
        
        return sorted(result, key=lambda s: s.incantation)
    
    def set_lens(self, lens: "Lens") -> None:
        """Update the active lens and reload lens spells."""
        self._lens_spells.clear()
        self._alias_map.clear()
        
        if lens.spellbook:
            for spell in lens.spellbook:
                self._lens_spells[spell.incantation] = spell
        
        self._build_alias_map()
```

### Lens Schema Extension

```python
# In src/sunwell/core/lens.py

@dataclass(frozen=True, slots=True)
class Lens:
    """A Sunwell expertise lens."""
    
    metadata: LensMetadata
    heuristics: tuple[Heuristic, ...]
    personas: tuple[Persona, ...]
    heuristic_validators: tuple[HeuristicValidator, ...]
    communication: CommunicationStyle | None
    skills: tuple[Skill, ...] = ()
    spellbook: tuple[Spell, ...] = ()  # NEW
```

### YAML Schema

```yaml
# Example: code-reviewer.lens with spellbook

lens:
  metadata:
    name: "Code Reviewer"
    version: "2.0.0"
    description: "Expert code review with security focus"
  
  spellbook:
    # Simple cantrip (routing only)
    - incantation: "::review"
      aliases: ["::r"]
      description: "General code review"
      intent: code_review
      focus: ["quality", "patterns", "issues"]
    
    # Full spell (complete context)
    - incantation: "::security"
      aliases: ["::sec", "::s"]
      description: "Deep security review with OWASP focus"
      intent: code_review
      focus: ["security", "vulnerability", "injection", "auth"]
      complexity: complex
      top_k: 8
      
      instructions: |
        Perform a comprehensive security review:
        
        1. **Input Validation**
           - Check all user inputs for sanitization
           - Look for SQL injection, XSS, command injection
           
        2. **Authentication & Session**
           - Verify password hashing (bcrypt, argon2)
           - Check session management
           - Look for hardcoded credentials
           
        3. **Authorization**
           - Verify access control checks
           - Look for IDOR vulnerabilities
           - Check role-based permissions
           
        4. **Cryptography**
           - Verify secure algorithms (no MD5, SHA1 for passwords)
           - Check for secure random number generation
           
        5. **Information Disclosure**
           - Check error messages for sensitive data
           - Look for debug information in production
      
      template: |
        ## Security Review: {{filename}}
        
        **Risk Level**: [CRITICAL | HIGH | MEDIUM | LOW]
        **Reviewer**: {{user}}
        **Date**: {{date}}
        
        ### Findings
        
        | # | Issue | Severity | Location | CWE |
        |---|-------|----------|----------|-----|
        
        ### Recommendations
        
        1. [Specific, actionable recommendations]
        
        ### OWASP Top 10 Checklist
        
        - [ ] A01:2021 – Broken Access Control
        - [ ] A02:2021 – Cryptographic Failures
        - [ ] A03:2021 – Injection
        - [ ] A04:2021 – Insecure Design
        - [ ] A05:2021 – Security Misconfiguration
        - [ ] A06:2021 – Vulnerable Components
        - [ ] A07:2021 – Auth Failures
        - [ ] A08:2021 – Data Integrity Failures
        - [ ] A09:2021 – Logging Failures
        - [ ] A10:2021 – SSRF
      
      validation:
        mode: warn
        gates:
          - "All issues have severity ratings"
          - "All issues reference specific code locations"
          - "Recommendations are actionable, not vague"
          - "CWE IDs provided where applicable"
          - "No false positives without justification"
      
      reagents:
        - type: heuristic
          name: "Security First"
          mode: include
        - type: heuristic
          name: "Input Validation"
          mode: boost
        - type: validator
          name: "security-check"
      
      examples:
        - quality: good
          content: |
            | 1 | SQL Injection | CRITICAL | `auth.py:45` | CWE-89 |
            
            The query uses string formatting:
            ```python
            query = f"SELECT * FROM users WHERE id = {user_id}"
            ```
            
            **Recommendation**: Use parameterized queries:
            ```python
            query = "SELECT * FROM users WHERE id = ?"
            cursor.execute(query, (user_id,))
            ```
        - quality: bad
          content: |
            Found some security issues. The code could be better.
          explanation: "Too vague, no specific locations, no actionable fixes"

  heuristics:
    principles:
      - name: "Security First"
        rule: "Every code change must consider security implications"
        # ...
```

### CognitiveRouter Integration

```python
# Updated CognitiveRouter

@dataclass
class CognitiveRouter:
    router_model: ModelProtocol
    available_lenses: list[str]
    grimoire: Grimoire | None = None  # NEW
    
    async def route(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[RoutingDecision, Spell | None]:
        """Route a task, returning routing decision and spell context."""
        
        # Check for spell incantations
        if self.grimoire:
            spell = self._check_spell(task)
            if spell:
                return spell.to_routing_decision(), spell
        
        # Natural language routing
        decision = await self._llm_route(task, context)
        return decision, None
    
    def _check_spell(self, task: str) -> Spell | None:
        """Check if task matches a spell incantation."""
        task_stripped = task.strip()
        
        if not task_stripped.startswith("::"):
            return None
        
        parts = task_stripped.split(maxsplit=1)
        incantation = parts[0].lower()
        
        return self.grimoire.resolve(incantation)
```

### RuntimeEngine Integration

```python
# In RuntimeEngine.execute()

async def execute(self, prompt: str, ...) -> ExecutionResult:
    # Route with spell context
    routing, spell = await self.cognitive_router.route(prompt)
    
    # Build template variables
    template_vars = self._get_template_vars(prompt)
    
    # Build system prompt
    system_parts = []
    
    # Add lens context (existing)
    system_parts.append(self._build_lens_context(routing))
    
    # Add spell context (NEW)
    if spell:
        spell_context = spell.to_system_context(template_vars)
        if spell_context:
            system_parts.append(spell_context)
        
        # Load reagents
        for reagent in spell.reagents:
            self._load_reagent(reagent)
    
    # Cast the spell (execute)
    result = await self._generate(
        prompt,
        system_prompt="\n\n".join(system_parts),
    )
    
    # Validate against quality gates
    if spell and spell.validation.gates:
        result = self._validate_gates(result, spell.validation)
    
    return result
```

---

## User Experience

### Discovering Spells

```bash
# List all available spells
$ sunwell spells

📖 Spellbook for code-reviewer.lens

  SPELL              DESCRIPTION
  ───────────────────────────────────────────
  ::review (::r)     General code review
  ::security (::s)   Deep security review with OWASP focus
  ::perf             Performance analysis
  ::arch             Architecture documentation

📜 Cantrips (built-in)

  ::help (::?)       Show spell help
  ::audit (::a)      Audit for accuracy

# Show spell details
$ sunwell spells ::security

⚡ ::security - Deep security review with OWASP focus

Aliases:     ::sec, ::s
Intent:      code_review
Focus:       security, vulnerability, injection, auth
Complexity:  complex

📋 Instructions:
   Perform a comprehensive security review...

📄 Template:
   ## Security Review: {{filename}}
   ...

✓ Quality Gates (warn mode):
   • All issues have severity ratings
   • All issues reference specific code locations
   ...

🧪 Reagents:
   • heuristic:Security First (include)
   • heuristic:Input Validation (boost)
   • validator:security-check
```

### Casting Spells

```bash
# Simple usage
$ sunwell chat
> ::security auth.py

⚡ Casting ::security on auth.py...

# The spell provides full context:
# - Instructions on how to do security review
# - Template for output format
# - Quality gates to check
# - Relevant heuristics loaded

# With alias
$ sunwell chat
> ::s auth.py

# Same spell, shorter incantation
```

### Customizing Spells

```yaml
# ~/.sunwell/spells.yaml (user overrides)
spellbook:
  - incantation: "::security"
    merge: true  # Merge with lens definition
    
    # Add to existing gates
    validation:
      gates:
        - "Include estimated fix time"
        - "Tag with JIRA ticket if applicable"
    
    # Override template
    template: |
      ## Security Findings
      
      **Reviewer**: {{user}}
      **Date**: {{date}}
      
      | Finding | Risk | Fix | Time Est |
      |---------|------|-----|----------|
```

```yaml
# .sunwell/spells.yaml (project overrides)
spellbook:
  - incantation: "::deploy-check"
    description: "Pre-deployment security checklist"
    intent: code_review
    focus: ["deployment", "security", "config"]
    
    instructions: |
      Check for project-specific deployment issues:
      1. Verify environment variables are not hardcoded
      2. Check database migration safety
      3. Verify feature flags are correctly set
    
    validation:
      mode: block  # Must pass before deployment
      gates:
        - "All env vars use secrets manager"
        - "Migrations are backward compatible"
```

---

## Fount Distribution

Spells travel with lenses when shared via the Fount:

```bash
# Publishing
$ sunwell publish code-reviewer.lens
Publishing code-reviewer.lens to Fount...
  - 15 heuristics
  - 3 personas
  - 8 spells           # Spellbook included!
  - 2 skills
✓ Published as sunwell/code-reviewer@2.0.0

# Installing
$ sunwell install sunwell/code-reviewer
Installing sunwell/code-reviewer@2.0.0...
  - 15 heuristics ✓
  - 3 personas ✓
  - 8 spells ✓          # Spellbook installed!
  - 2 skills ✓
✓ Installed to lenses/code-reviewer.lens

# Spells are immediately available
$ sunwell chat
> ::security
(Uses the installed spell with full context)
```

---

## Comparison: IDE Rules vs Sunwell Spells

| Feature | IDE Rules | Sunwell Spells |
|---------|-----------|----------------|
| **Location** | IDE-specific paths | Inside `.lens` files |
| **Portability** | Single IDE | Anywhere |
| **Shareable** | Copy files manually | Via Fount |
| **Instructions** | ✅ Markdown body | ✅ `instructions` field |
| **Templates** | ✅ In markdown | ✅ `template` field (with variables) |
| **Quality Gates** | ✅ Checklists | ✅ `validation.gates` with modes |
| **Module Loading** | ✅ `@modules/` | ✅ `reagents` with explicit typing |
| **Examples** | ✅ In markdown | ✅ `examples` with quality tags |
| **Aliases** | ❌ | ✅ `aliases` field |
| **Customizable** | Per-workspace | User → Project → Lens → Cantrips |
| **Merge Override** | ❌ Full replace | ✅ `merge: true` for partial |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| **Spell resolution latency** | <1ms for cached spells |
| **User adoption** | 50%+ of lens usage via spells |
| **Fount spellbooks** | 80%+ of published lenses include spells |
| **Customization rate** | 20%+ users have custom spells |
| **Alias usage** | 30%+ of spell casts use aliases |

---

## Implementation Plan

### Phase 1: Core Schema (Week 1)

1. Create `src/sunwell/core/spell.py`
   - `Spell`, `Reagent`, `SpellValidation` dataclasses
   - `Grimoire` for loading and resolution
2. Add `spellbook` to `Lens` dataclass
3. Update lens loader to parse spells from YAML
4. Unit tests for spell parsing and merging

### Phase 2: Router Integration (Week 2)

1. Update `CognitiveRouter` to use `Grimoire`
2. Return `(RoutingDecision, Spell)` tuple
3. Create `src/sunwell/core/cantrips.yaml` with defaults
4. Remove hardcoded command map from `cognitive_router.py`
5. Integration tests for spell routing

### Phase 3: Engine Integration (Week 3)

1. Update `RuntimeEngine` to inject spell context
2. Implement template variable resolution
3. Implement reagent loading (`_load_reagent`)
4. Implement validation modes (`_validate_gates`)
5. End-to-end tests

### Phase 4: CLI & UX (Week 4)

1. Add `sunwell spells` CLI command
2. Add `sunwell spells <incantation>` detail view
3. Update help system
4. Add shell completion for spell incantations

### Phase 5: Fount Integration (Week 5)

1. Include spellbooks in lens publishing
2. Include spellbooks in lens installation
3. Version compatibility handling
4. Documentation and examples

---

## Design Decisions

### Why "Spells"?

1. **Thematic consistency**: Sunwell is WoW-inspired. Spells fit naturally.

2. **Terminology**:
   - `Spell` — The workflow definition
   - `Incantation` — The trigger (::security)
   - `Spellbook` — Collection of spells in a lens
   - `Grimoire` — The spell manager/loader
   - `Reagents` — Required components (modules)
   - `Cantrips` — Built-in simple spells
   - `Cast` — Execute a spell

### Why List Format (not Dict)?

The YAML uses list format for consistency with existing lens structure:

```yaml
# ✅ Consistent with heuristics, personas
spellbook:
  - incantation: "::security"
    description: "..."

heuristics:
  - name: "Security First"
    rule: "..."

# ❌ Inconsistent (dict format)
spellbook:
  "::security":
    description: "..."
```

### Why "Reagents" instead of "Modules"?

In WoW, reagents are components required to cast spells. This:
- Reinforces the spell theme
- Makes it clear they're loaded during execution
- Explicit typing enables IDE autocomplete

### Why Not Chain Execution?

Workflow chaining (`chain: [::a, ::b, ::c]`) is **deferred to RFC-022** because it requires:
- State passing between steps
- Failure handling
- Nested chain support

These are complex enough to warrant dedicated design.

---

## Future Considerations

The mana (token cost) system was considered but deferred. If needed later:
- Track token usage per spell for analytics
- Warn users before expensive operations
- Set daily/session token budgets

This could be revisited when token costs become a user pain point.

---

## Open Questions

1. **Spell inheritance**: Should a lens be able to "extend" another lens's spells?

2. **Spell learning**: Should `sunwell learn` create a new spell from successful patterns?

3. **Conditional spells**: Should spells support conditional fields based on context?

---

## References

- RFC-010: Sunwell Core
- RFC-011: Lenses with Skills
- RFC-020: Cognitive Router
- [WoW Spell System](https://wowpedia.fandom.com/wiki/Spell)
- [Cursor Rules Documentation](https://docs.cursor.com/context/rules-for-ai)
