# RFC-122: Compound Learning — Evolving Sunwell's Knowledge

**Status**: Draft  
**Author**: Human + AI collaboration  
**Created**: 2026-01-24  
**Updated**: 2026-01-24 (v2: Fixed RFC-084 conflict, target SimulacrumStore)  
**Extends**: Simulacrum (`simulacrum/core/`), Naaru (`naaru/`), Agent (`agent/`)  
**Depends on**: RFC-119 (Event Bus), RFC-067 (Integration-Aware DAG), RFC-084 (Unified SimulacrumStore)

## Summary

Every successful task makes Sunwell better at similar tasks. This RFC extends the existing `Learning` system with structural patterns (templates) and integrates knowledge retrieval into the `HarmonicPlanner` via `Convergence`. No new parallel systems — this evolves what exists.

**The moat**: After N tasks, Sunwell has accumulated operational knowledge specific to YOUR codebase.

## Motivation

### Problem

Sunwell already extracts learnings (facts, patterns, dead ends) but:

1. **Not used during planning**: `LearningExtractor` captures knowledge, but `HarmonicPlanner` doesn't query it
2. **No structural patterns**: Learnings are facts ("Uses FastAPI"), not structures ("CRUD = model → routes → tests")
3. **No compound improvement**: Similar tasks don't benefit from previous executions

### What Exists Today

```
agent/learning.py              → LearningExtractor, LearningStore (extracts facts)
simulacrum/core/turn.py        → Learning dataclass (5 categories)
simulacrum/core/store.py       → SimulacrumStore (RFC-084: unified tiered storage)
naaru/convergence.py           → Convergence (7±2 slot working memory)
naaru/planners/harmonic.py     → HarmonicPlanner (generates plans)
```

> **Note**: `simulacrum/core/memory.py` is **deprecated** per RFC-084. This RFC targets `SimulacrumStore` instead, which already has embedding support via `_embedder` and tiered storage (HOT/WARM/COLD).

**The gap**: These components don't talk to each other during planning.

### What This RFC Adds

```
Learning categories:      +template, +heuristic (in turn.py)
SimulacrumStore:         +retrieve_for_planning() (uses existing _embedder)
LearningExtractor:       +extract_template(), +extract_heuristic()
HarmonicPlanner:         +knowledge injection via Convergence
Agent:                   +learning loop on task completion
```

---

## Goals

1. **Extend Learning**: Add `template` and `heuristic` categories with structural data
2. **Extend SimulacrumStore**: Add `retrieve_for_planning()` using existing embedder
3. **Extend LearningExtractor**: Extract templates from successful novel tasks
4. **Integrate with HarmonicPlanner**: Use Convergence to inject knowledge
5. **Automatic learning loop**: Success → extract → enrich (no human intervention)

## Non-Goals

- New parallel storage system (use existing Simulacrum)
- New parallel memory system (use existing Convergence)
- Cross-project knowledge (future RFC)

---

## Design

### Architecture: Extending What Exists

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Task Input                                 │
│                     "Add CRUD endpoints for Product"                    │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  SimulacrumStore.retrieve_for_planning()  [NEW METHOD]                 │
│                                                                        │
│   Existing categories:          NEW categories:                        │
│   ├── fact                      ├── template (structural patterns)     │
│   ├── preference                └── heuristic (ordering hints)         │
│   ├── constraint                                                       │
│   ├── pattern                                                          │
│   └── dead_end                                                         │
│                                                                        │
│   Uses existing _embedder for semantic matching                        │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Convergence (existing 7±2 slots)                                      │
│                                                                        │
│   [slot1: facts]  [slot2: constraints]  [slot3: templates]             │
│   [slot4: dead_ends]  [slot5: heuristics]  [slot6: ...]                │
│                                                                        │
│   Shards pre-fetch knowledge while model thinks                        │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  HarmonicPlanner.plan() [EXTENDED]                                     │
│                                                                        │
│   1. Get knowledge from Convergence                                    │
│   2. If template matches: use structural guidance                      │
│   3. Apply constraints, avoid dead ends                                │
│   4. Generate plan with full context                                   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           Execution                                     │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LearningExtractor [EXTENDED]                                          │
│                                                                        │
│   Existing: extract_from_code(), extract_with_llm()                    │
│   NEW: extract_template(), extract_heuristic()                         │
│                                                                        │
│   On success: extract patterns → LongTermMemory.store()                │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Part 1: Extend Learning Dataclass

**File**: `src/sunwell/simulacrum/core/turn.py`

```python
# EXTEND existing Learning dataclass

@dataclass(frozen=True, slots=True)
class Learning:
    """An extracted piece of knowledge from the conversation.
    
    RFC-122: Extended with template and heuristic categories.
    
    Note: The `id` property remains based on `category:fact` for backwards
    compatibility. New fields (template_data, embedding, use_count) are
    metadata that don't affect identity — same fact in same category = same learning.
    """
    
    fact: str
    """The actual learning/insight."""
    
    source_turns: tuple[str, ...]
    """Turn IDs this was extracted from."""
    
    confidence: float
    """How confident we are in this learning (0-1)."""
    
    category: Literal[
        "fact",        # Existing: "Uses FastAPI"
        "preference",  # Existing: "Prefers pytest"
        "constraint",  # Existing: "Tests required"
        "pattern",     # Existing: "Uses factory pattern"
        "dead_end",    # Existing: "Sync DB doesn't work"
        "template",    # NEW: Structural task patterns
        "heuristic",   # NEW: Ordering/strategy hints
    ]
    """Type of learning."""
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    superseded_by: str | None = None
    """If this learning was updated, pointer to newer version."""
    
    # RFC-122: Template-specific data (optional, for category="template")
    template_data: TemplateData | None = None
    """Structural data for template-type learnings."""
    
    # RFC-122: Embedding for semantic retrieval (computed lazily)
    embedding: tuple[float, ...] | None = None
    """Pre-computed embedding for fast retrieval."""
    
    # RFC-122: Usage tracking (updated via LearningStore.record_usage)
    use_count: int = 0
    """How many times this learning has been used."""
    
    last_used: str | None = None
    """Timestamp of last usage."""

    # ... existing methods (id, to_turn, etc.) unchanged ...


@dataclass(frozen=True, slots=True)
class TemplateData:
    """Structural data for template-type learnings.
    
    RFC-122: Captures reusable task patterns.
    """
    
    name: str
    """Human-readable name: "CRUD Endpoint" """
    
    # Pattern matching
    match_patterns: tuple[str, ...]
    """Keywords that suggest this template: ("CRUD", "REST", "endpoint")"""
    
    # Variables
    variables: tuple[TemplateVariable, ...]
    """Extractable variables from goal text."""
    
    # Structure (integrates with RFC-067)
    produces: tuple[str, ...]
    """Artifacts this creates: ("{{entity}}Model", "{{entity}}Routes")"""
    
    requires: tuple[str, ...]
    """Prerequisites: ("Database",)"""
    
    # Constraints
    expected_artifacts: tuple[str, ...]
    """Files that should be created: ("models/{{entity}}.py",)"""
    
    validation_commands: tuple[str, ...]
    """Commands to verify success: ("pytest tests/test_{{entity}}.py",)"""
    
    suggested_order: int = 50
    """Execution priority (lower = earlier)."""


@dataclass(frozen=True, slots=True)
class TemplateVariable:
    """A variable extractable from goal text."""
    
    name: str
    description: str
    var_type: Literal["string", "file", "choice"]
    extraction_hints: tuple[str, ...]
    default: str | None = None
```

---

### Part 2: Extend SimulacrumStore with Planning Retrieval

**File**: `src/sunwell/simulacrum/core/store.py`

> **Note**: We extend `SimulacrumStore` (not the deprecated `LongTermMemory`). SimulacrumStore already has `_embedder: EmbeddingProtocol` for semantic search and tiered storage.

```python
# EXTEND existing SimulacrumStore class

@dataclass
class SimulacrumStore:
    """Persistent conversation memory with hierarchical chunking.
    
    RFC-122: Extended with retrieve_for_planning() for HarmonicPlanner integration.
    """
    
    # ... existing fields (base_path, config, _hot_dag, _embedder, etc.) ...
    
    # RFC-122: NEW METHOD
    async def retrieve_for_planning(
        self,
        goal: str,
        limit_per_category: int = 5,
    ) -> PlanningContext:
        """Retrieve all relevant knowledge for planning a task.
        
        Uses existing _embedder for semantic matching against learnings stored in DAG.
        Returns categorized results for injection into HarmonicPlanner.
        
        Args:
            goal: Task description to match against
            limit_per_category: Max items per category
        
        Returns:
            PlanningContext with categorized learnings
        """
        # Get all learnings from the DAG
        learnings = self._hot_dag.get_active_learnings()
        
        # Compute goal embedding using existing embedder
        goal_embedding: tuple[float, ...] | None = None
        if self._embedder:
            try:
                embedding_result = await self._embedder.embed([goal])
                goal_embedding = tuple(embedding_result[0])
            except Exception:
                goal_embedding = None
        
        # Score all learnings by relevance
        scored: list[tuple[float, Learning]] = []
        
        for learning in learnings:
            if goal_embedding and learning.embedding:
                similarity = self._cosine_similarity(goal_embedding, learning.embedding)
            else:
                # Fallback: keyword matching
                similarity = self._keyword_similarity(goal, learning.fact)
            
            # Boost by confidence and usage
            use_count = getattr(learning, 'use_count', 0)
            boost = learning.confidence * (1.0 + 0.05 * min(use_count, 10))
            final_score = similarity * boost
            
            if final_score > 0.3:
                scored.append((final_score, learning))
        
        # Sort by score
        scored.sort(key=lambda x: -x[0])
        
        # Categorize
        facts: list[Learning] = []
        constraints: list[Learning] = []
        dead_ends: list[Learning] = []
        templates: list[Learning] = []
        heuristics: list[Learning] = []
        patterns: list[Learning] = []
        
        for _score, learning in scored:
            if learning.category == "fact" and len(facts) < limit_per_category:
                facts.append(learning)
            elif learning.category == "preference" and len(facts) < limit_per_category:
                facts.append(learning)
            elif learning.category == "constraint" and len(constraints) < limit_per_category:
                constraints.append(learning)
            elif learning.category == "dead_end" and len(dead_ends) < limit_per_category:
                dead_ends.append(learning)
            elif learning.category == "template" and len(templates) < limit_per_category:
                templates.append(learning)
            elif learning.category == "heuristic" and len(heuristics) < limit_per_category:
                heuristics.append(learning)
            elif learning.category == "pattern" and len(patterns) < limit_per_category:
                patterns.append(learning)
        
        return PlanningContext(
            facts=tuple(facts),
            constraints=tuple(constraints),
            dead_ends=tuple(dead_ends),
            templates=tuple(templates),
            heuristics=tuple(heuristics),
            patterns=tuple(patterns),
            goal=goal,
        )
    
    @staticmethod
    def _cosine_similarity(
        a: tuple[float, ...],
        b: tuple[float, ...],
    ) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    @staticmethod
    def _keyword_similarity(query: str, fact: str) -> float:
        """Keyword-based similarity fallback."""
        query_words = set(query.lower().split())
        fact_words = set(fact.lower().split())
        overlap = len(query_words & fact_words)
        if not query_words:
            return 0.0
        return overlap / len(query_words)


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """All knowledge relevant to a planning task.
    
    RFC-122: Structured context for HarmonicPlanner.
    """
    
    facts: tuple[Learning, ...]
    constraints: tuple[Learning, ...]
    dead_ends: tuple[Learning, ...]
    templates: tuple[Learning, ...]
    heuristics: tuple[Learning, ...]
    patterns: tuple[Learning, ...]
    goal: str
    
    def to_convergence_slots(self) -> list[Slot]:
        """Convert to Convergence slots for HarmonicPlanner."""
        from sunwell.naaru.convergence import Slot, SlotSource
        
        slots = []
        
        if self.facts:
            slots.append(Slot(
                id="knowledge:facts",
                content=[f.fact for f in self.facts],
                relevance=0.9,
                source=SlotSource.MEMORY_FETCHER,
            ))
        
        if self.constraints:
            slots.append(Slot(
                id="knowledge:constraints",
                content=[f"⚠️ {c.fact}" for c in self.constraints],
                relevance=1.0,  # Constraints are high priority
                source=SlotSource.MEMORY_FETCHER,
            ))
        
        if self.dead_ends:
            slots.append(Slot(
                id="knowledge:dead_ends",
                content=[f"❌ {d.fact}" for d in self.dead_ends],
                relevance=0.95,  # Dead ends are important to avoid
                source=SlotSource.MEMORY_FETCHER,
            ))
        
        if self.templates:
            slots.append(Slot(
                id="knowledge:templates",
                content=self.templates,  # Full Learning objects for template matching
                relevance=0.85,
                source=SlotSource.MEMORY_FETCHER,
            ))
        
        if self.heuristics:
            slots.append(Slot(
                id="knowledge:heuristics",
                content=[f"💡 {h.fact}" for h in self.heuristics],
                relevance=0.7,
                source=SlotSource.MEMORY_FETCHER,
            ))
        
        return slots
    
    def to_prompt_section(self) -> str:
        """Format for injection into planner prompt."""
        sections = []
        
        if self.facts or self.patterns:
            sections.append("## Project Knowledge")
            for f in self.facts[:10]:
                sections.append(f"- {f.fact}")
            for p in self.patterns[:5]:
                sections.append(f"- {p.fact}")
        
        if self.constraints:
            sections.append("\n## Constraints (must follow)")
            for c in self.constraints[:5]:
                sections.append(f"- ⚠️ {c.fact}")
        
        if self.dead_ends:
            sections.append("\n## Dead Ends (don't do these)")
            for d in self.dead_ends[:5]:
                sections.append(f"- ❌ {d.fact}")
        
        if self.templates:
            sections.append("\n## Known Task Patterns")
            for t in self.templates[:3]:
                if t.template_data:
                    sections.append(f"- **{t.template_data.name}**: {t.fact}")
        
        if self.heuristics:
            sections.append("\n## Heuristics")
            for h in self.heuristics[:5]:
                sections.append(f"- 💡 {h.fact}")
        
        return "\n".join(sections)
    
    @property
    def best_template(self) -> Learning | None:
        """Get the highest-confidence matching template."""
        if not self.templates:
            return None
        return max(self.templates, key=lambda t: t.confidence)
```

---

### Part 3: Extend LearningExtractor

**File**: `src/sunwell/agent/learning.py`

```python
# EXTEND existing LearningExtractor class

@dataclass
class LearningExtractor:
    """Extracts learnings from generated code and fix attempts.
    
    RFC-122: Extended with template and heuristic extraction.
    """
    
    use_llm: bool = False
    model: ModelProtocol | None = None
    
    # ... existing methods (extract_from_code, extract_with_llm, etc.) ...
    
    # RFC-122: NEW METHOD
    async def extract_template(
        self,
        goal: Goal,
        result: GoalResult,
        plan: Plan,
    ) -> Learning | None:
        """Extract a reusable template from successful novel task.
        
        Criteria for extraction:
        - Multiple artifacts created (structured output)
        - Consistent file naming pattern
        - Clean success (no retries)
        
        Args:
            goal: The completed goal
            result: Execution result
            plan: Plan that was executed
        
        Returns:
            Template Learning if extractable, None otherwise
        """
        # Check if this is extractable
        if len(result.artifacts_created) < 2:
            return None
        if len(result.files_changed) < 2:
            return None
        
        if not self.model:
            return None
        
        # Use LLM to analyze pattern
        prompt = f"""Analyze this successful task for repeatable patterns.

Goal: {goal.description}

Files created/modified:
{chr(10).join(f'- {f}' for f in result.files_changed)}

Artifacts produced:
{chr(10).join(f'- {a}' for a in result.artifacts_created)}

Tasks executed:
{chr(10).join(f'- {t.description}' for t in plan.tasks[:10])}

Is this a repeatable pattern? If yes, extract:
1. Pattern name (e.g., "CRUD Endpoint", "Service Module")
2. Variables that could be parameterized (e.g., "entity" extracted from "User")
3. Expected artifacts for the pattern (with {{variable}} placeholders)
4. Prerequisites (what must exist before this pattern)
5. Validation commands

Return JSON with:
{{"is_pattern": true/false, "name": "...", "match_patterns": [...], "variables": [...], "produces": [...], "requires": [...], "expected_artifacts": [...], "validation": [...]}}
"""
        
        try:
            response = await self.model.generate(
                prompt=prompt,
                response_format={"type": "json_object"},
            )
            
            data = json.loads(response.content)
            if not data.get("is_pattern"):
                return None
            
            template_data = TemplateData(
                name=data["name"],
                match_patterns=tuple(data.get("match_patterns", [])),
                variables=tuple(
                    TemplateVariable(
                        name=v["name"],
                        description=v.get("description", ""),
                        var_type=v.get("type", "string"),
                        extraction_hints=tuple(v.get("hints", [])),
                    )
                    for v in data.get("variables", [])
                ),
                produces=tuple(data.get("produces", [])),
                requires=tuple(data.get("requires", [])),
                expected_artifacts=tuple(data.get("expected_artifacts", [])),
                validation_commands=tuple(data.get("validation", [])),
            )
            
            return Learning(
                fact=f"Task pattern: {template_data.name}",
                source_turns=(),
                confidence=0.7,  # Start moderate, boost with reuse
                category="template",
                template_data=template_data,
            )
        
        except (json.JSONDecodeError, KeyError):
            return None
    
    # RFC-122: NEW METHOD
    def extract_heuristic(
        self,
        goal: Goal,
        result: GoalResult,
        plan: Plan,
    ) -> Learning | None:
        """Extract ordering/strategy heuristic from successful task.
        
        Args:
            goal: The completed goal
            result: Execution result
            plan: Plan that was executed
        
        Returns:
            Heuristic Learning if extractable
        """
        if len(plan.tasks) < 3:
            return None
        
        # Analyze task ordering for patterns
        task_types = []
        for task in plan.tasks:
            desc_lower = task.description.lower()
            if "model" in desc_lower or "schema" in desc_lower:
                task_types.append("model")
            elif "route" in desc_lower or "endpoint" in desc_lower or "api" in desc_lower:
                task_types.append("routes")
            elif "test" in desc_lower:
                task_types.append("tests")
            elif "config" in desc_lower or "setup" in desc_lower:
                task_types.append("config")
        
        # Check for common patterns
        if task_types:
            # Model before routes before tests
            if "model" in task_types and "tests" in task_types:
                model_idx = task_types.index("model")
                tests_idx = len(task_types) - 1 - task_types[::-1].index("tests")
                if model_idx < tests_idx:
                    return Learning(
                        fact="Create models before writing tests",
                        source_turns=(),
                        confidence=0.6,
                        category="heuristic",
                    )
        
        return None


# EXTEND existing LearningStore class

@dataclass
class LearningStore:
    """In-memory store for learnings during a session.
    
    RFC-122: Extended with template storage and usage tracking.
    Thread-safe for Python 3.14t free-threading.
    """
    
    learnings: list[Learning] = field(default_factory=list)
    dead_ends: list[DeadEnd] = field(default_factory=list)
    
    # RFC-122: Thread-safe lock for mutable operations
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    
    # ... existing methods ...
    
    # RFC-122: NEW METHOD (thread-safe)
    def record_usage(self, learning_id: str, success: bool) -> None:
        """Record that a learning was used.
        
        Thread-safe for free-threading (3.14t).
        
        Args:
            learning_id: ID of learning used
            success: Whether the task succeeded
        """
        with self._lock:
            for i, learning in enumerate(self.learnings):
                if learning.id == learning_id:
                    # Adjust confidence based on outcome
                    new_confidence = learning.confidence
                    if success:
                        new_confidence = min(1.0, new_confidence + 0.05)
                    else:
                        new_confidence = max(0.1, new_confidence - 0.1)
                    
                    # Create updated learning (immutable dataclass)
                    updated = Learning(
                        fact=learning.fact,
                        source_turns=learning.source_turns,
                        confidence=new_confidence,
                        category=learning.category,
                        template_data=getattr(learning, 'template_data', None),
                        embedding=getattr(learning, 'embedding', None),
                        use_count=getattr(learning, 'use_count', 0) + 1,
                        last_used=datetime.now().isoformat(),
                    )
                    self.learnings[i] = updated
                    break
    
    # RFC-122: NEW METHOD
    def get_templates(self) -> list[Learning]:
        """Get all template learnings."""
        with self._lock:
            return [l for l in self.learnings if l.category == "template"]
```

---

### Part 4: Extend HarmonicPlanner

**File**: `src/sunwell/naaru/planners/harmonic.py`

```python
# EXTEND existing HarmonicPlanner class

@dataclass
class HarmonicPlanner:
    """Plans by generating multiple candidates and selecting the best.
    
    RFC-122: Extended with knowledge injection via Convergence.
    """
    
    model: ModelProtocol
    candidates: int = 5
    variance: VarianceStrategy = VarianceStrategy.PROMPTING
    refinement_rounds: int = 1
    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    project_schema: ProjectSchema | None = None
    convergence: Convergence | None = None  # EXISTING - now used for knowledge
    use_free_threading: bool = True
    event_callback: Callable[[Any], None] | None = None
    scoring_version: ScoringVersion = ScoringVersion.V2
    
    # RFC-122: Knowledge integration via SimulacrumStore
    simulacrum: SimulacrumStore | None = None
    """Reference to SimulacrumStore for knowledge retrieval (RFC-084 compatible)."""
    
    async def plan_with_metrics(
        self,
        goal: str,
        context: str = "",
    ) -> tuple[ArtifactGraph, PlanMetrics | PlanMetricsV2]:
        """Generate and evaluate plan candidates.
        
        RFC-122: Extended to inject knowledge from SimulacrumStore via Convergence.
        """
        # RFC-122: Retrieve relevant knowledge
        planning_context = None
        if self.simulacrum:
            planning_context = await self.simulacrum.retrieve_for_planning(goal)
            
            # Inject into Convergence for use during generation
            if self.convergence and planning_context:
                for slot in planning_context.to_convergence_slots():
                    await self.convergence.add(slot)
        
        # RFC-122: Check for template match
        template = planning_context.best_template if planning_context else None
        
        if template and template.template_data:
            # Template-guided planning
            return await self._plan_with_template(goal, template, planning_context, context)
        
        # Standard harmonic planning with knowledge context
        knowledge_context = ""
        if planning_context:
            knowledge_context = planning_context.to_prompt_section()
        
        full_context = f"{knowledge_context}\n\n{context}".strip()
        
        # ... existing candidate generation logic with full_context ...
        
        return await self._generate_and_select(goal, full_context)
    
    async def _plan_with_template(
        self,
        goal: str,
        template: Learning,
        planning_context: PlanningContext,
        additional_context: str,
    ) -> tuple[ArtifactGraph, PlanMetrics | PlanMetricsV2]:
        """Plan using template structure.
        
        RFC-122: Template-guided artifact generation.
        """
        template_data = template.template_data
        
        # Extract variables from goal
        variables = await self._extract_template_variables(goal, template_data)
        
        # Build artifacts from template
        artifacts = []
        for artifact_pattern in template_data.expected_artifacts:
            resolved = self._substitute_variables(artifact_pattern, variables)
            artifacts.append(ArtifactSpec(
                id=resolved,
                description=f"Create {resolved}",
                produces=(resolved,),
                # Connect to template's requires
                requires=tuple(
                    self._substitute_variables(r, variables)
                    for r in template_data.requires
                ),
            ))
        
        # Build graph
        graph = ArtifactGraph.from_specs(artifacts, limits=self.limits)
        
        # Compute metrics
        metrics = self._compute_metrics(graph, goal)
        
        # Emit event
        if self.event_callback:
            self.event_callback({
                "type": "template_matched",
                "template_id": template.id,
                "template_name": template_data.name,
                "variables": variables,
                "confidence": template.confidence,
            })
        
        return graph, metrics
    
    async def _extract_template_variables(
        self,
        goal: str,
        template_data: TemplateData,
    ) -> dict[str, str]:
        """Extract variable values from goal text."""
        if not template_data.variables:
            return {}
        
        if not self.model:
            return {}
        
        var_specs = "\n".join(
            f"- {v.name}: {v.description} (hints: {', '.join(v.extraction_hints)})"
            for v in template_data.variables
        )
        
        prompt = f"""Extract template variables from this goal.

Template: {template_data.name}
Variables to extract:
{var_specs}

Goal: "{goal}"

Return JSON mapping variable names to extracted values.
Example: {{"entity": "Product"}}
"""
        
        try:
            response = await self.model.generate(
                prompt=prompt,
                response_format={"type": "json_object"},
            )
            return json.loads(response.content)
        except (json.JSONDecodeError, Exception):
            return {}
    
    def _substitute_variables(
        self,
        pattern: str,
        variables: dict[str, str],
    ) -> str:
        """Substitute {{var}} patterns."""
        result = pattern
        for name, value in variables.items():
            result = result.replace(f"{{{{{name}}}}}", value)
            result = result.replace(f"{{{{{name}_lower}}}}}", value.lower())
            result = result.replace(f"{{{{{name}_upper}}}}}", value.upper())
        return result
```

---

### Part 5: Extend Agent with Learning Loop

**File**: `src/sunwell/agent/core.py`

```python
# EXTEND existing Agent class

@dataclass
class Agent:
    """The unified agent entry point (RFC-110).
    
    RFC-122: Extended with compound learning loop.
    """
    
    # ... existing fields ...
    # Note: Agent already has `simulacrum: SimulacrumStore | None` field
    
    _learning_extractor: LearningExtractor = field(default_factory=LearningExtractor, init=False)
    
    async def run(self, goal: str, ...) -> AgentResult:
        """Execute a goal.
        
        RFC-122: Extended with knowledge retrieval and learning loop.
        """
        # ... existing setup ...
        
        # RFC-122: Connect planner to SimulacrumStore for knowledge retrieval
        if self.simulacrum and hasattr(self._planner, 'simulacrum'):
            self._planner.simulacrum = self.simulacrum
        
        # ... existing execution ...
        
        result = await self._execute(goal, plan, ...)
        
        # RFC-122: Learning loop on completion
        await self._learn_from_execution(goal_obj, result, plan, planning_context)
        
        return result
    
    async def _learn_from_execution(
        self,
        goal: Goal,
        result: GoalResult,
        plan: Plan,
        context_used: PlanningContext | None,
    ) -> None:
        """Extract and store learnings from task execution.
        
        RFC-122: Compound learning loop.
        Uses SimulacrumStore.add_learning() for persistence.
        """
        if not self.simulacrum:
            return
        
        if not result.success:
            # Record dead end via SimulacrumStore
            if result.failure_reason:
                self.simulacrum.add_learning(
                    fact=f"Failed approach: {result.failure_reason}",
                    category="dead_end",
                    confidence=0.8,
                )
            return
        
        # Extract facts from generated code
        for file_path in result.files_changed:
            try:
                content = Path(file_path).read_text()
                facts = self._learning_extractor.extract_from_code(content, file_path)
                for fact in facts:
                    # Store via SimulacrumStore
                    category = fact.category if fact.category in ("fact", "pattern") else "fact"
                    self.simulacrum.add_learning(
                        fact=fact.fact,
                        category=category,
                        confidence=fact.confidence,
                    )
            except Exception:
                pass  # File may not exist or be readable
        
        # Check if template-guided (don't extract template from template)
        was_templated = context_used and context_used.best_template is not None
        
        if not was_templated:
            # Try to extract a reusable template
            template = await self._learning_extractor.extract_template(goal, result, plan)
            if template:
                self.simulacrum.add_learning(
                    fact=template.fact,
                    category="template",
                    confidence=template.confidence,
                )
                # Store template data in DAG metadata (separate storage)
                if template.template_data:
                    self._store_template_data(template)
        
        # Extract heuristics
        heuristic = self._learning_extractor.extract_heuristic(goal, result, plan)
        if heuristic:
            self.simulacrum.add_learning(
                fact=heuristic.fact,
                category="heuristic",
                confidence=heuristic.confidence,
            )
        
        # Record usage of knowledge that was used
        if context_used:
            for learning in (
                context_used.facts + 
                context_used.constraints + 
                context_used.templates +
                context_used.heuristics +
                context_used.patterns
            ):
                self._learning_store.record_usage(learning.id, success=True)
```

---

### Part 6: Built-in Templates

**File**: `src/sunwell/agent/builtin_templates.py` (new small file)

```python
"""Built-in templates for common patterns.

RFC-122: Seed templates that work out of the box.
"""

from sunwell.simulacrum.core.turn import Learning, TemplateData, TemplateVariable


BUILTIN_TEMPLATES: tuple[Learning, ...] = (
    Learning(
        fact="CRUD endpoint pattern: model → routes → tests",
        source_turns=(),
        confidence=0.9,
        category="template",
        template_data=TemplateData(
            name="CRUD Endpoint",
            match_patterns=("CRUD", "REST", "endpoint", "API for"),
            variables=(
                TemplateVariable(
                    name="entity",
                    description="Model name (User, Post, Product)",
                    var_type="string",
                    extraction_hints=("for {{entity}}", "{{entity}} API"),
                ),
            ),
            produces=("{{entity}}Model", "{{entity}}Routes", "{{entity}}Tests"),
            requires=("Database",),
            expected_artifacts=(
                "models/{{entity_lower}}.py",
                "api/{{entity_lower}}_routes.py",
                "tests/test_{{entity_lower}}.py",
            ),
            validation_commands=(
                "pytest tests/test_{{entity_lower}}.py -v",
            ),
        ),
    ),
    
    Learning(
        fact="Authentication pattern: middleware → routes → tests",
        source_turns=(),
        confidence=0.9,
        category="template",
        template_data=TemplateData(
            name="Authentication",
            match_patterns=("auth", "login", "OAuth", "JWT", "session"),
            variables=(),
            produces=("AuthMiddleware", "AuthRoutes", "User"),
            requires=("Database",),
            expected_artifacts=(
                "auth/middleware.py",
                "auth/routes.py",
                "tests/test_auth.py",
            ),
            validation_commands=("pytest tests/test_auth.py -v",),
        ),
    ),
)


# Common constraints
BUILTIN_CONSTRAINTS: tuple[Learning, ...] = (
    Learning(
        fact="Never commit secrets or .env files",
        source_turns=(),
        confidence=1.0,
        category="constraint",
    ),
    Learning(
        fact="All features should have test coverage",
        source_turns=(),
        confidence=0.8,
        category="constraint",
    ),
)


# Common dead ends
BUILTIN_DEAD_ENDS: tuple[Learning, ...] = (
    Learning(
        fact="Don't use synchronous database calls in async handlers",
        source_turns=(),
        confidence=0.9,
        category="dead_end",
    ),
)
```

---

## Storage

**No new storage locations** — uses existing Simulacrum persistence:

```
.sunwell/
├── simulacrum.json       # Existing - now includes templates, heuristics
├── sessions/             # Existing (RFC-120)
└── backlog/              # Existing
```

The `simulacrum.json` already serializes `LongTermMemory.learnings` — templates and heuristics are just new categories.

---

## Event Bus Integration (RFC-119)

Uses existing event infrastructure:

```python
# Emit via existing event_callback on HarmonicPlanner

event_callback({
    "type": "knowledge_retrieved",
    "facts_count": len(planning_context.facts),
    "constraints_count": len(planning_context.constraints),
    "templates_count": len(planning_context.templates),
})

event_callback({
    "type": "template_matched",
    "template_id": template.id,
    "template_name": template_data.name,
    "variables": variables,
})

event_callback({
    "type": "learning_extracted",
    "learning_id": learning.id,
    "category": learning.category,
})
```

---

## Implementation Plan

### Phase 1: Extend Learning Model (0.5 day)

| Task | File |
|------|------|
| Add `template`, `heuristic` categories | `src/sunwell/simulacrum/core/turn.py` |
| Add `TemplateData`, `TemplateVariable` | `src/sunwell/simulacrum/core/turn.py` |
| Add `template_data`, `embedding`, `use_count` fields | `src/sunwell/simulacrum/core/turn.py` |

### Phase 2: Extend SimulacrumStore (1 day)

| Task | File |
|------|------|
| Add `retrieve_for_planning()` | `src/sunwell/simulacrum/core/store.py` |
| Add `PlanningContext` dataclass | `src/sunwell/simulacrum/core/store.py` |
| Integrate with existing `_embedder` | `src/sunwell/simulacrum/core/store.py` |
| Add `to_convergence_slots()` | `src/sunwell/simulacrum/core/store.py` |

### Phase 3: Extend LearningExtractor (1 day)

| Task | File |
|------|------|
| Add `extract_template()` | `src/sunwell/agent/learning.py` |
| Add `extract_heuristic()` | `src/sunwell/agent/learning.py` |
| Add thread-safe `record_usage()` to LearningStore | `src/sunwell/agent/learning.py` |

### Phase 4: Extend HarmonicPlanner (1 day)

| Task | File |
|------|------|
| Add `simulacrum: SimulacrumStore` field | `src/sunwell/naaru/planners/harmonic.py` |
| Inject knowledge via Convergence | `src/sunwell/naaru/planners/harmonic.py` |
| Add `_plan_with_template()` | `src/sunwell/naaru/planners/harmonic.py` |
| Add `_extract_template_variables()` | `src/sunwell/naaru/planners/harmonic.py` |

### Phase 5: Extend Agent (0.5 day)

| Task | File |
|------|------|
| Add `_learn_from_execution()` | `src/sunwell/agent/core.py` |
| Connect planner to simulacrum | `src/sunwell/agent/core.py` |

### Phase 6: Built-ins & Testing (1 day)

| Task | File |
|------|------|
| Create builtin templates | `src/sunwell/agent/builtin_templates.py` |
| Load builtins on startup | `src/sunwell/simulacrum/core/store.py` |
| Integration tests | `tests/test_compound_learning.py` |

**Total: ~5 days** (reduced from 7 by reusing infrastructure)

---

## What Changes vs. What's New

| Component | Change Type | Lines Changed (est.) |
|-----------|-------------|---------------------|
| `src/sunwell/simulacrum/core/turn.py` | Extend | +80 lines |
| `src/sunwell/simulacrum/core/store.py` | Extend | +120 lines |
| `src/sunwell/agent/learning.py` | Extend | +150 lines |
| `src/sunwell/naaru/planners/harmonic.py` | Extend | +100 lines |
| `src/sunwell/agent/core.py` | Extend | +50 lines |
| `src/sunwell/agent/builtin_templates.py` | **New** | +80 lines |

**Total new code**: ~580 lines  
**No new modules besides `builtin_templates.py`**

> **Note**: This RFC does NOT touch the deprecated `simulacrum/core/memory.py`. All storage goes through `SimulacrumStore` per RFC-084.

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Knowledge retrieval latency | <100ms | Instrumentation |
| Template match rate | 40%+ after 20 tasks | Log analysis |
| Compound speedup | 20% faster for repeated patterns | Time comparison |
| Dead end prevention | 0 repeated failures for same cause | Failure analysis |
| Integration: uses existing Convergence | 100% | Code review |
| Integration: uses existing SimulacrumStore | 100% | Code review |

---

## Design Notes

### Thread-Safety (Python 3.14t)

All mutable operations on `LearningStore` use `threading.Lock`:

```python
# LearningStore has _lock field
def record_usage(self, learning_id: str, success: bool) -> None:
    with self._lock:
        # ... safe mutation ...
```

`SimulacrumStore.retrieve_for_planning()` is read-only and thread-safe.

### Why SimulacrumStore, Not LongTermMemory?

1. `memory.py` is **deprecated** per RFC-084 (emits `DeprecationWarning`)
2. `SimulacrumStore` already has `_embedder: EmbeddingProtocol` for semantic search
3. `SimulacrumStore.add_learning()` method already exists
4. Tiered storage (HOT/WARM/COLD) is already implemented

### Learning ID Stability

The `Learning.id` property remains `hash(f"{category}:{fact}")`:
- Template metadata doesn't affect identity
- Same fact in same category = same learning (deduplication works)
- `use_count` and `embedding` are mutable metadata, not identity

### Template Data Storage

`TemplateData` is stored as a field on `Learning`, serialized with the DAG.
For large template libraries, consider separate `templates.json` file (future RFC).

---

## The One-Liner

> **Every successful task makes Sunwell better at similar tasks** — by extending the existing Learning system with templates and integrating it into HarmonicPlanner via Convergence.

No new systems. Just evolution.

---

## References

- `src/sunwell/simulacrum/core/turn.py` — Existing Learning dataclass (5 categories → 7)
- `src/sunwell/simulacrum/core/store.py` — SimulacrumStore (RFC-084 unified storage)
- `src/sunwell/agent/learning.py` — Existing LearningExtractor, LearningStore
- `src/sunwell/naaru/convergence.py` — Existing Convergence (7±2 slots)
- `src/sunwell/naaru/planners/harmonic.py` — Existing HarmonicPlanner
- RFC-067: Integration-Aware DAG — `produces`/`requires` pattern
- RFC-084: Unified SimulacrumStore — **deprecated** `memory.py`, use `store.py`
- RFC-119: Unified Event Bus — event emissions
