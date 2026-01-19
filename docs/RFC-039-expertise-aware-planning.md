# RFC-039: Expertise-Aware Planning

| Field | Value |
|-------|-------|
| **RFC** | 039 |
| **Title** | Expertise-Aware Planning |
| **Status** | Implemented |
| **Created** | 2026-01-19 |
| **Author** | llane |
| **Builds on** | RFC-027 (Self-Directed Expertise), RFC-036 (Artifact-First), RFC-037 (Goal-First CLI) |

---

## Abstract

RFC-037 introduced a goal-first interface (`sunwell "goal"`) that routes directly to the artifact planner. But this bypasses Sunwell's expertise system — lenses containing domain knowledge, heuristics, and validation rules that should inform **what**, **how**, and **when** to create artifacts.

This RFC proposes **expertise-aware planning**: the agent automatically detects the goal's domain, loads relevant lenses, and injects applicable heuristics into artifact planning and generation. The result is higher-quality output that follows best practices without requiring users to specify a lens.

```
Current (RFC-037):
    Goal → Artifact Planner → Artifacts → Execute

Proposed (RFC-039):
    Goal → Domain Detection → Lens Selection → Expertise Extraction
                                                      ↓
                               Artifact Planner (heuristic-informed)
                                                      ↓
                               Artifacts → Execute → Validate (lens rules)
```

---

## Goals and Non-Goals

### Goals

1. **Automatic lens selection** — Detect domain from goal, load matching lenses
2. **Heuristic injection** — Relevant always/never patterns inform artifact prompts
3. **Validation integration** — Lens validators check generated content
4. **Progressive enhancement** — Falls back gracefully if no matching lens exists
5. **DORI integration** — Documentation rules (Diataxis, style guides) apply to doc goals

### Non-Goals

1. **Replace explicit lenses** — `sunwell chat --binding writer` still uses explicit lens
2. **Require lenses** — Goals work without any lenses (baseline behavior)
3. **Modify lens format** — Existing lenses work as-is

---

## Motivation

### The Knowledge Gap

Consider: `sunwell "Write docs for the CLI module"`

**Current behavior (RFC-037)**:
- Artifact planner creates: `docs/cli.md`, `docs/api-reference.md`
- No knowledge of Diataxis framework, NVIDIA style guide, progressive disclosure
- Generic documentation that doesn't follow best practices

**With expertise-aware planning**:
- Detects domain: documentation
- Loads: tech-writer.lens, DORI rules (Diataxis framework)
- Injects heuristics: "Use progressive disclosure", "Front-load value", "PACE tone"
- Creates artifacts informed by expertise: proper Diataxis types, correct structure
- Validates: Checks signal-to-noise, readability, link integrity

### The DORI Connection

DORI rules encode years of documentation expertise:
- **What** to create: Diataxis types (tutorial, how-to, explanation, reference)
- **How** to write: Signal-to-noise, inverted pyramid, evidence handling
- **When** to split: Content scope guidelines, modularization triggers

This knowledge should automatically flow into documentation artifacts.

### Domain-Specific Patterns

| Goal Domain | Expertise Source | Key Heuristics |
|-------------|------------------|----------------|
| Documentation | tech-writer.lens, DORI | Diataxis, progressive disclosure, PACE tone |
| Code | coder.lens, code-reviewer | Clean code, testing patterns, error handling |
| Review | code-reviewer.lens | Security, performance, maintainability |
| Project setup | team-dev.lens | Structure conventions, CI/CD, tooling |

---

## Design

### 1. Domain Classification

Fast, local classification of goal domain:

```python
class DomainClassifier:
    """Classify goal into domain categories."""
    
    # Keywords that indicate domain
    DOMAIN_SIGNALS = {
        "documentation": ["docs", "document", "write docs", "readme", "api docs", 
                         "tutorial", "guide", "explain", "describe"],
        "code": ["implement", "create function", "build", "code", "add feature",
                "refactor", "fix bug", "write test"],
        "review": ["review", "audit", "check", "analyze", "security", "performance"],
        "project": ["project", "setup", "initialize", "scaffold", "structure"],
    }
    
    def classify(self, goal: str) -> tuple[str, float]:
        """Return (domain, confidence)."""
        goal_lower = goal.lower()
        
        scores = {}
        for domain, signals in self.DOMAIN_SIGNALS.items():
            score = sum(1 for s in signals if s in goal_lower)
            scores[domain] = score
        
        if not any(scores.values()):
            return ("general", 0.0)
        
        best_domain = max(scores, key=scores.get)
        confidence = scores[best_domain] / len(self.DOMAIN_SIGNALS[best_domain])
        
        return (best_domain, min(confidence, 1.0))
```

### 2. Lens Discovery

Find lenses matching the detected domain:

```python
class LensDiscovery:
    """Discover and load lenses for a domain."""
    
    # Domain to lens mapping
    DOMAIN_LENSES = {
        "documentation": ["tech-writer.lens", "team-writer.lens"],
        "code": ["coder.lens", "team-dev.lens"],
        "review": ["code-reviewer.lens", "team-qa.lens"],
        "project": ["team-dev.lens", "team-pm.lens"],
    }
    
    # External lens sources (e.g., DORI rules)
    EXTERNAL_SOURCES = {
        "documentation": [
            "~/.cursor/rules/modules/diataxis-framework",
            "~/.cursor/rules/validation/docs-quality-principles",
        ],
    }
    
    async def discover(
        self, 
        domain: str, 
        search_paths: list[Path] | None = None,
    ) -> list[Lens]:
        """Find and load lenses for domain."""
        lenses = []
        
        # Default search paths
        if search_paths is None:
            search_paths = [
                Path.cwd() / "lenses",
                Path.home() / ".sunwell" / "lenses",
            ]
        
        # Find matching lens files
        lens_names = self.DOMAIN_LENSES.get(domain, [])
        for path in search_paths:
            for name in lens_names:
                lens_path = path / name
                if lens_path.exists():
                    lens = await self._load_lens(lens_path)
                    if lens:
                        lenses.append(lens)
        
        return lenses
```

### 3. Expertise Extraction

Extract relevant heuristics based on goal:

```python
class ExpertiseExtractor:
    """Extract applicable heuristics from lenses."""
    
    def __init__(self, lenses: list[Lens], embedder: Embedder | None = None):
        self.lenses = lenses
        self.embedder = embedder
        self._all_heuristics = self._collect_heuristics()
    
    async def extract(
        self, 
        goal: str, 
        artifact_type: str | None = None,
        top_k: int = 5,
    ) -> ExpertiseContext:
        """Extract heuristics relevant to goal and artifact type."""
        
        # Keyword-based filtering (fast)
        candidates = self._keyword_filter(goal, artifact_type)
        
        # Semantic ranking if embedder available
        if self.embedder and len(candidates) > top_k:
            candidates = await self._semantic_rank(goal, candidates, top_k)
        
        # Build context
        return ExpertiseContext(
            heuristics=candidates[:top_k],
            validators=[v for l in self.lenses for v in l.validators],
            domain_context=self._build_domain_context(),
        )
    
    def _keyword_filter(
        self, 
        goal: str, 
        artifact_type: str | None,
    ) -> list[Heuristic]:
        """Fast keyword-based filtering."""
        goal_words = set(goal.lower().split())
        
        scored = []
        for h in self._all_heuristics:
            # Match on name, rule text
            h_words = set(f"{h.name} {h.rule}".lower().split())
            overlap = len(goal_words & h_words)
            
            # Boost if artifact type matches
            if artifact_type and artifact_type in h.name.lower():
                overlap += 2
            
            if overlap > 0:
                scored.append((h, overlap))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        return [h for h, _ in scored]


@dataclass
class ExpertiseContext:
    """Expertise context to inject into planning."""
    
    heuristics: list[Heuristic]
    validators: list[Validator]
    domain_context: str  # Markdown summary of domain expertise
    
    def to_prompt_section(self) -> str:
        """Format as prompt section for injection."""
        parts = ["## Domain Expertise\n"]
        
        if self.domain_context:
            parts.append(self.domain_context)
            parts.append("")
        
        if self.heuristics:
            parts.append("### Key Principles\n")
            for h in self.heuristics:
                parts.append(f"**{h.name}**: {h.rule}")
                if h.always:
                    parts.append("- Always: " + "; ".join(h.always[:3]))
                if h.never:
                    parts.append("- Never: " + "; ".join(h.never[:3]))
                parts.append("")
        
        return "\n".join(parts)
```

### 4. Enhanced Artifact Planner

Inject expertise into artifact discovery:

```python
class ExpertiseAwareArtifactPlanner(ArtifactPlanner):
    """Artifact planner with expertise injection."""
    
    def __init__(
        self,
        model: Model,
        domain_classifier: DomainClassifier | None = None,
        lens_discovery: LensDiscovery | None = None,
        expertise_extractor: ExpertiseExtractor | None = None,
    ):
        super().__init__(model)
        self.domain_classifier = domain_classifier or DomainClassifier()
        self.lens_discovery = lens_discovery or LensDiscovery()
        self._expertise_extractor: ExpertiseExtractor | None = None
    
    async def discover_graph(
        self,
        goal: str,
        context: dict,
    ) -> ArtifactGraph:
        """Discover artifacts with expertise awareness."""
        
        # 1. Classify domain
        domain, confidence = self.domain_classifier.classify(goal)
        
        # 2. Discover lenses (if confidence high enough)
        lenses = []
        if confidence >= 0.3:
            lenses = await self.lens_discovery.discover(domain)
        
        # 3. Extract expertise
        expertise_context = None
        if lenses:
            extractor = ExpertiseExtractor(lenses)
            expertise_context = await extractor.extract(goal)
        
        # 4. Build enhanced prompt
        system_prompt = self._build_system_prompt(expertise_context)
        
        # 5. Discover artifacts (expertise-informed)
        response = await self.model.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._format_discovery_prompt(goal, context)},
            ],
        )
        
        # 6. Parse and validate
        graph = self._parse_artifact_graph(response.text)
        
        # 7. Store expertise for execution phase
        self._current_expertise = expertise_context
        
        return graph
    
    def _build_system_prompt(self, expertise: ExpertiseContext | None) -> str:
        """Build system prompt with expertise injection."""
        base = ARTIFACT_DISCOVERY_SYSTEM_PROMPT
        
        if expertise:
            base += "\n\n" + expertise.to_prompt_section()
        
        return base
```

### 5. Execution-Time Validation

Use lens validators during artifact execution:

```python
class ValidatedExecutor:
    """Executor that applies lens validators to outputs."""
    
    def __init__(
        self,
        base_executor: ArtifactExecutor,
        validators: list[Validator],
    ):
        self.base_executor = base_executor
        self.validators = validators
    
    async def execute(
        self, 
        artifact: Artifact, 
        context: dict,
    ) -> ExecutionResult:
        """Execute artifact and validate output."""
        
        # Execute
        result = await self.base_executor.execute(artifact, context)
        
        if not result.success:
            return result
        
        # Find applicable validators
        applicable = [
            v for v in self.validators
            if self._validator_applies(v, artifact)
        ]
        
        # Run validation
        validation_results = []
        for validator in applicable:
            v_result = await self._run_validator(validator, result.content)
            validation_results.append(v_result)
        
        # Check for failures
        failures = [r for r in validation_results if not r.passed]
        
        if failures and self._should_retry(failures):
            # Retry with validation feedback
            result = await self._retry_with_feedback(artifact, context, failures)
        
        result.validation_results = validation_results
        return result
```

---

## Integration Points

### CLI (RFC-037)

```python
# In main.py _run_agent()

async def _run_agent(goal: str, ...):
    # Create expertise-aware planner
    planner = ExpertiseAwareArtifactPlanner(
        model=synthesis_model,
        domain_classifier=DomainClassifier(),
        lens_discovery=LensDiscovery(),
    )
    
    # Planning now incorporates expertise
    graph = await planner.discover_graph(goal, context)
    ...
```

### Chat Mode

When using `sunwell chat`, explicit lens selection continues to work:

```python
# Explicit lens = use that lens's expertise
sunwell chat tech-writer

# No explicit lens = auto-detect per message
sunwell chat  # Uses domain classifier for each query
```

### DORI Rules Integration

DORI rules can be loaded as a special lens source:

```python
class DORIRulesLoader:
    """Load DORI rules as expertise source."""
    
    RULE_PATHS = {
        "diataxis": "modules/diataxis-framework/RULE.mdc",
        "quality": "modules/docs-quality-principles/RULE.mdc",
        "style": "utilities/docs-style-guide/RULE.mdc",
        "validation": "validation/docs-audit/RULE.mdc",
    }
    
    def load_as_heuristics(self, rule_path: Path) -> list[Heuristic]:
        """Parse DORI rule into heuristics."""
        content = rule_path.read_text()
        
        # Extract sections as heuristics
        heuristics = []
        for section in self._parse_sections(content):
            heuristics.append(Heuristic(
                name=section.title,
                rule=section.summary,
                always=section.do_patterns,
                never=section.dont_patterns,
            ))
        
        return heuristics
```

---

## Example Flow

```
User: sunwell "Write docs for the CLI module"

1. Domain Classification
   → domain: "documentation", confidence: 0.9

2. Lens Discovery  
   → Found: tech-writer.lens, team-writer.lens
   → External: DORI diataxis-framework, docs-quality-principles

3. Expertise Extraction
   → Heuristics: "Progressive Disclosure", "Signal-to-Noise", 
                 "Diataxis-Aligned Scoping", "Inverted Pyramid"
   → Validators: readability-checker, structural-lint

4. Artifact Discovery (expertise-informed)
   Prompt includes:
   "## Domain Expertise
    ### Key Principles
    **Progressive Disclosure**: Layer information so users get what they need...
    - Always: Front-load value, 30-second scan test
    - Never: Bury critical info, mix Diataxis types
    
    **Diataxis-Aligned Scoping**: Every page fits one quadrant..."
   
   → Artifacts discovered:
     - cli-overview.md (EXPLANATION type, progressive layers)
     - cli-reference.md (REFERENCE type, comprehensive)
     - cli-quickstart.md (TUTORIAL type, guided)

5. Execution with Validation
   → Each artifact generated with heuristics in prompt
   → Validators check: readability, structure, signal-to-noise
   → Retry if validation fails

6. Result
   ✓ 3 artifacts created, all validation passed
   ✓ Documentation follows Diataxis framework
   ✓ NVIDIA style guide compliance
```

---

## Configuration

### Lens Search Paths

```yaml
# ~/.sunwell/config.yaml
expertise:
  lens_paths:
    - ./lenses
    - ~/.sunwell/lenses
    - ~/.cursor/rules  # DORI rules
  
  # Domain overrides
  domain_lenses:
    documentation:
      - tech-writer.lens
      - ~/.cursor/rules/modules/diataxis-framework
    code:
      - coder.lens
```

### Per-Goal Override

```bash
# Explicit lens (bypass auto-detection)
sunwell "Write docs" --lens tech-writer.lens

# Disable expertise (baseline behavior)
sunwell "Write docs" --no-expertise
```

---

## Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Domain accuracy | Correct domain classification | ≥90% |
| Lens hit rate | Goals with matching lens | ≥70% |
| Validation pass rate | First-try validation pass | ≥80% |
| Quality improvement | Human eval vs baseline | +15% |

---

## Implementation Plan

### Phase 1: Domain Classification
- [ ] Implement `DomainClassifier`
- [ ] Unit tests for domain detection
- [ ] Fallback to "general" domain

### Phase 2: Lens Discovery  
- [ ] Implement `LensDiscovery`
- [ ] DORI rules loader
- [ ] Search path configuration

### Phase 3: Expertise Extraction
- [ ] Implement `ExpertiseExtractor`
- [ ] `ExpertiseContext` formatting
- [ ] Integration with embedder for semantic ranking

### Phase 4: Planner Integration
- [ ] Create `ExpertiseAwareArtifactPlanner`
- [ ] Prompt injection
- [ ] CLI integration

### Phase 5: Validation
- [ ] Implement `ValidatedExecutor`
- [ ] Retry with feedback
- [ ] Validation metrics

---

## Related RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-027 | Self-directed expertise tools (execution-time) |
| RFC-036 | Artifact-first planning (base planner) |
| RFC-037 | Goal-first CLI (entry point) |
| RFC-038 | Harmonic planning (can combine with expertise) |

---

## Open Questions

1. **Embedding cost** — Should we always embed for semantic ranking, or only when keyword filtering returns too many?

2. **External rules** — How to handle DORI rules that aren't in lens format? Converter? Native support?

3. **Multi-domain goals** — "Write docs and tests for CLI" spans documentation + code. Merge expertise?

4. **Confidence threshold** — What's the right threshold for "confident enough to load expertise"?
