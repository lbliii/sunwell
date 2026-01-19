# RFC-035: Domain-Agnostic Project Framework

| Field | Value |
|-------|-------|
| **RFC** | 035 |
| **Title** | Domain-Agnostic Project Framework |
| **Status** | Draft |
| **Created** | 2026-01-18 |
| **Author** | llane |
| **Builds on** | RFC-034 (Contract-Aware Planning), Lenses |

---

## Abstract

Sunwell's RFC-034 introduced contract-aware parallel task planning with `produces`, `requires`, and `modifies` fields that track artifact dependencies and resource conflicts. These concepts are **inherently domain-agnostic** — they apply equally to software protocols, novel characters, architectural blueprints, or research papers.

This RFC proposes a **Project Schema** system that allows users to define their domain's artifact types, relationships, and validation rules. Combined with existing **Lenses** (which define *how* to approach work), this creates a complete domain-agnostic framework:

```
Project = Schema (structure) + Lens (approach)
         ↓
    RFC-034 Engine (execution)
```

**Key insight**: The same dependency resolution, conflict detection, and parallel execution that makes code development efficient also makes novel writing consistent, research coherent, and architecture coordinated.

---

## Goals and Non-Goals

### Goals

1. **Domain-agnostic project support** — Fiction, architecture, research, and software all use the same core infrastructure
2. **User-defined artifact types** — Users declare what entities exist in their domain (characters, protocols, components)
3. **Automatic dependency resolution** — Sunwell builds task graphs from artifact definitions
4. **Lens integration** — Lenses provide domain-specific heuristics, validators, and personas
5. **Consistency validation** — Domain-specific rules catch inconsistencies early

### Non-Goals

1. **Pre-built domain schemas** — Users define their own (though we may provide templates)
2. **GUI builder** — Schema definitions are YAML; UI tools can be built later
3. **Runtime schema modification** — Schemas are static per project
4. **Cross-project artifact sharing** — Artifacts live within one project

---

## Motivation

### The Universal Problem

Every complex project has the same fundamental challenges:

| Challenge | Software | Fiction | Architecture |
|-----------|----------|---------|--------------|
| **Define before use** | Interfaces before implementations | Character bible before scenes | Blueprints before construction |
| **Track dependencies** | Module A imports B | Scene requires character exists | Foundation before walls |
| **Detect conflicts** | Two tasks editing same file | Character in two places at once | Overlapping floor plans |
| **Validate consistency** | Type checking | Timeline coherence | Structural integrity |

RFC-034 solved this for software with `produces`, `requires`, `modifies`. But these concepts map directly to any domain:

```python
# Software
Task(produces=["UserProtocol"], requires=["BaseProtocol"], modifies=["user.py"])

# Fiction  
Task(produces=["Character_John"], requires=[], modifies=["bible/john.md"])

# Architecture
Task(produces=["FloorPlan_2F"], requires=["Foundation"], modifies=["plans/floor2.dwg"])
```

### The Missing Piece

RFC-034 assumes software. Lenses assume a perspective. What's missing is a way to tell Sunwell:

> "This project has these kinds of things (characters, scenes, timelines), they relate to each other like this, and here's how to check for consistency."

That's what a **Project Schema** provides.

---

## Solution: Project Schema

### Schema Definition

A schema defines the **structure** of a domain:

```yaml
# .sunwell/schema.yaml
project:
  name: "The London Conspiracy"
  type: fiction
  version: "1.0.0"

# What kinds of artifacts exist
artifact_types:
  character:
    description: "A person in the story"
    fields:
      required: [name, traits]
      optional: [age, backstory, voice_pattern, relationships]
    produces: "Character_{id}"
    
  location:
    description: "A place where scenes occur"
    fields:
      required: [name, era]
      optional: [atmosphere, description, coordinates]
    produces: "Setting_{id}"
    
  relationship:
    description: "Dynamic between two characters"
    fields:
      required: [characters, initial_state]
      optional: [arc, pivotal_scenes]
    requires:
      - "Character_{characters[0]}"
      - "Character_{characters[1]}"
    produces: "Relationship_{characters[0]}_{characters[1]}"
    
  scene:
    description: "A unit of narrative action"
    fields:
      required: [summary, pov, location, timeline_position]
      optional: [characters_present, conflict, outcome]
    requires:
      - "Character_{pov}"
      - "Setting_{location}"
    modifies:
      - "timeline/{timeline_position}"
      - "character_state/{pov}"
    when:
      # Conditional requirements
      - if: "characters_present"
        requires: "Character_{char}" for char in characters_present
      - if: "relationship_development"
        requires: "Relationship_{relationship_development}"

# Validation rules
validators:
  - name: timeline_consistency
    description: "No character can be in two places at the same time"
    rule: |
      For each character C and time T:
        scenes where C.pov == C or C in characters_present
        at timeline_position == T
        must have the same location
    severity: error
    
  - name: voice_consistency
    description: "Character dialogue should match their voice_pattern"
    rule: |
      When scene contains dialogue from character C:
        dialogue style should match C.voice_pattern
    severity: warning
    method: llm  # Requires LLM to evaluate
    
  - name: relationship_arc
    description: "Relationship state changes must be earned by scenes"
    rule: |
      If Relationship R changes state from A to B:
        there must exist a scene S where R is developed
        and S.timeline_position precedes the state change
    severity: error

# Planning hints
planning:
  default_strategy: contract_first
  phases:
    - name: worldbuilding
      artifact_types: [character, location, relationship]
      parallel: true
      description: "Define characters, places, and relationships first"
    - name: drafting
      artifact_types: [scene]
      parallel: "when no timeline conflicts"
      description: "Write scenes, parallelizing independent timelines"
    - name: revision
      parallel: false
      description: "Sequential revision pass"
```

### Artifact Definitions

Users define specific artifacts conforming to the schema:

```yaml
# artifacts/characters/john.yaml
type: character
id: john

name: "John Hartwell"
age: 45
traits:
  - stubborn
  - loyal
  - haunted
backstory: "Former soldier, served in the Crimean War. Lost his brother in battle."
voice_pattern: "Terse sentences. Military jargon. Avoids discussing emotions."

relationships:
  - target: mary
    initial: distrust
    arc: "distrust → grudging respect → love"
```

```yaml
# artifacts/scenes/ch01_arrival.yaml
type: scene
id: ch01_arrival

summary: "John arrives in London, haunted by war memories"
pov: john
location: london_docks
timeline_position: day_1

characters_present:
  - john
  
conflict: "John struggles with crowds triggering war memories"
outcome: "John finds lodging but remains isolated"
```

### Schema Resolution

When Sunwell loads a project, it:

1. **Parses the schema** → Understands artifact types and rules
2. **Loads all artifacts** → Finds YAML files matching schema types
3. **Resolves dependencies** → Builds the RFC-034 task graph automatically
4. **Validates constraints** → Checks schema rules before execution

```python
@dataclass
class ProjectSchema:
    """Domain-agnostic project definition."""
    
    name: str
    project_type: str
    artifact_types: dict[str, ArtifactType]
    validators: list[ValidatorConfig]
    planning_config: PlanningConfig
    
    @classmethod
    def load(cls, project_root: Path) -> "ProjectSchema":
        """Load schema from .sunwell/schema.yaml"""
        schema_path = project_root / ".sunwell" / "schema.yaml"
        with open(schema_path) as f:
            data = yaml.safe_load(f)
        return cls._parse(data)
    
    def resolve_artifact(self, artifact_path: Path) -> Task:
        """Convert a user's artifact definition into an RFC-034 Task."""
        with open(artifact_path) as f:
            artifact = yaml.safe_load(f)
        
        artifact_type = self.artifact_types[artifact["type"]]
        
        return Task(
            id=artifact["id"],
            description=f"Create {artifact_type.description}: {artifact.get('name', artifact['id'])}",
            mode=TaskMode.GENERATE,
            produces=self._expand_pattern(artifact_type.produces, artifact),
            requires=self._expand_patterns(artifact_type.requires, artifact),
            modifies=self._expand_patterns(artifact_type.modifies, artifact),
            parallel_group=self._get_phase(artifact_type),
            is_contract=artifact_type.is_contract_type,
        )
    
    def _expand_pattern(self, pattern: str, artifact: dict) -> frozenset[str]:
        """Expand template patterns like 'Character_{id}' → 'Character_john'"""
        # Simple template expansion
        result = pattern
        for key, value in artifact.items():
            result = result.replace(f"{{{key}}}", str(value))
        return frozenset([result])
```

---

## Integration with Lenses

### Lens + Schema Composition

Lenses define **how** to approach work; schemas define **what** exists. Together:

| Layer | Provides | Example |
|-------|----------|---------|
| **Schema** | Artifact structure, relationships, constraints | "Characters have traits and voice patterns" |
| **Lens** | Heuristics, personas, validators, skills | "Show don't tell", "Conflict per scene" |
| **RFC-034** | Dependency resolution, parallel execution | Task graph, conflict detection |

### Domain-Specific Lenses

Each domain would have specialized lenses:

**Fiction:**
- `developmental-editor.lens` — Story arc, character development, pacing
- `continuity-editor.lens` — Timeline, facts, consistency
- `line-editor.lens` — Prose quality, dialogue, voice
- `sensitivity-reader.lens` — Representation, harmful tropes

**Architecture:**
- `structural-engineer.lens` — Load-bearing, safety codes
- `accessibility-reviewer.lens` — ADA compliance, universal design
- `sustainability-auditor.lens` — Energy efficiency, materials

**Research:**
- `methodology-reviewer.lens` — Research design, validity
- `citation-checker.lens` — Source verification, attribution
- `clarity-editor.lens` — Academic writing, accessibility

### Lens-Schema Binding

Lenses can declare which schemas they're compatible with:

```yaml
# developmental-editor.lens
lens:
  metadata:
    name: "Developmental Editor"
    compatible_schemas: ["fiction", "screenplay", "memoir"]
    
  schema_extensions:
    # Additional validation when this lens is active
    validators:
      - name: "character_arc_complete"
        check: "Every major character must change by the end"
        applies_to: character
        when: "character.role == 'major'"
```

### Lens Dataclass Modifications

To support schema binding, the existing `Lens` and `LensMetadata` classes require modifications:

**`core/lens.py:21-31`** — Add `compatible_schemas` to metadata:

```python
@dataclass(frozen=True, slots=True)
class LensMetadata:
    """Lens metadata."""

    name: str
    domain: str | None = None
    version: SemanticVersion = field(default_factory=lambda: SemanticVersion(0, 1, 0))
    description: str | None = None
    author: str | None = None
    license: str | None = None
    
    # RFC-035: Schema compatibility
    compatible_schemas: tuple[str, ...] = ()  # Schema types this lens works with
    """Schema types this lens is designed for.
    
    Empty tuple means universal (works with any schema or no schema).
    Example: ("fiction", "screenplay", "memoir")
    """
```

**`core/lens.py:74-127`** — Add `schema_validators` to Lens:

```python
@dataclass(slots=True)
class Lens:
    """The core expertise container."""

    metadata: LensMetadata
    
    # ... existing fields ...
    
    # RFC-035: Schema-specific validators
    schema_validators: tuple[SchemaValidator, ...] = ()
    """Validators that only apply when a compatible schema is active.
    
    These extend the project schema's validators with lens-specific checks.
    """
```

**New dataclass** in `core/validator.py`:

```python
@dataclass(frozen=True, slots=True)
class SchemaValidator:
    """Lens-provided validator for schema artifacts.
    
    Unlike HeuristicValidator (general content checks), SchemaValidator
    targets specific artifact types defined in a project schema.
    """
    
    name: str
    check: str  # What to verify
    applies_to: str  # Artifact type (e.g., "character", "scene")
    condition: str | None = None  # When to apply (e.g., "character.role == 'major'")
    severity: Severity = Severity.WARNING
    method: ValidationMethod = ValidationMethod.LLM
```

**Composition behavior**: When a lens with `compatible_schemas` is applied to a project:

1. **Schema match check**: Lens only activates if `project.schema.type in lens.metadata.compatible_schemas`
2. **Validator merging**: `schema_validators` are added to the project's validator list
3. **Inheritance preserved**: `extends` and `compose` work normally; child lenses inherit parent's `compatible_schemas`

---

## Validator Execution Engine

Schema validators need an execution mechanism. This builds on existing infrastructure.

### Validator Types

| Type | Existing Location | Schema Usage |
|------|------------------|--------------|
| **Deterministic** | `core/validator.py:11-32` | File-based checks (syntax, structure) |
| **Heuristic** | `core/validator.py:34-73` | LLM-based judgment (quality, style) |
| **Schema** | NEW | Artifact relationship checks |

### Schema Validator Execution

Schema validators use a **constraint DSL** that compiles to executable checks:

```yaml
validators:
  - name: timeline_consistency
    description: "No character can be in two places at the same time"
    rule: |
      FOR character IN artifacts.characters
      FOR scene_a, scene_b IN artifacts.scenes
      WHERE character IN scene_a.characters_present
        AND character IN scene_b.characters_present
        AND scene_a.timeline_position == scene_b.timeline_position
      ASSERT scene_a.location == scene_b.location
    severity: error
    method: constraint  # Deterministic, not LLM
```

**Implementation** (`project/validators.py`):

```python
@dataclass
class ConstraintValidator:
    """Executes constraint DSL rules against project artifacts."""
    
    def validate(
        self,
        rule: str,
        artifacts: dict[str, list[Artifact]],
    ) -> list[ValidationResult]:
        """Execute a constraint rule against loaded artifacts.
        
        The DSL supports:
        - FOR x IN collection: iteration
        - WHERE condition: filtering  
        - ASSERT condition: the actual check
        
        Returns list of violations (empty = valid).
        """
        parsed = self._parse_rule(rule)
        violations = []
        
        for binding in self._enumerate_bindings(parsed.for_clauses, artifacts):
            if self._matches_where(parsed.where_clause, binding):
                if not self._check_assert(parsed.assert_clause, binding):
                    violations.append(self._make_violation(parsed, binding))
        
        return violations
```

### LLM-Based Validators

For nuanced checks that can't be expressed as constraints:

```yaml
validators:
  - name: voice_consistency
    description: "Character dialogue matches their voice_pattern"
    rule: |
      When evaluating dialogue from character {character.name}:
      - Voice pattern: {character.voice_pattern}
      - Dialogue sample: {scene.dialogue}
      
      Does the dialogue match the established voice pattern?
    severity: warning
    method: llm  # Uses HeuristicValidator infrastructure
```

**Execution**: LLM validators reuse `HeuristicValidator.to_prompt()` with artifact field substitution.

### Validator Precedence

When both schema and lens define validators for the same artifact type:

1. **Schema validators run first** (structural integrity)
2. **Lens validators run second** (domain expertise)
3. **Conflicts**: Lens validators can override schema validators by name (explicit opt-out)

```yaml
# In lens file
schema_extensions:
  validator_overrides:
    - name: timeline_consistency
      action: skip  # Skip schema's timeline check
      reason: "This lens handles timeline differently"
```

---

## Schema Module Disambiguation

The codebase has an existing `sunwell/schema/` module. This RFC introduces `.sunwell/schema.yaml`. Clarification:

| Component | Location | Purpose |
|-----------|----------|---------|
| **Lens Schema Loader** | `sunwell/schema/loader.py` | Parses `.lens` YAML files into `Lens` objects |
| **Project Schema** | `.sunwell/schema.yaml` | User-defined domain artifact types (NEW) |
| **Project Schema Loader** | `sunwell/project/schema.py` | Parses project schemas into `ProjectSchema` (NEW) |

**No collision**: The existing `schema/` module handles lens file parsing. The new `project/` module handles project-level domain schemas. They operate at different levels:

```
sunwell/schema/          → Lens file format specification
sunwell/project/         → Project domain schema (RFC-035)
.sunwell/schema.yaml     → User's project schema instance
```

---

## Planning Strategy Integration

Project schemas define `planning.phases`. This integrates with RFC-034's `PlanningStrategy`:

### Phase-to-Strategy Mapping

```yaml
# In project schema
planning:
  default_strategy: contract_first  # Maps to PlanningStrategy.CONTRACT_FIRST
  phases:
    - name: worldbuilding
      artifact_types: [character, location, relationship]
      parallel: true
      maps_to: contracts  # RFC-034 parallel group
    - name: drafting
      artifact_types: [scene]
      parallel: "when no timeline conflicts"
      maps_to: implementations
```

**Integration point** (`naaru/planners/agent.py`):

```python
class AgentPlanner:
    """Plans arbitrary user tasks using LLM decomposition."""
    
    # Existing
    strategy: PlanningStrategy = PlanningStrategy.CONTRACT_FIRST
    
    # RFC-035 addition
    project_schema: ProjectSchema | None = None
    
    def _build_planning_prompt(self, goals: list[str], context: dict | None) -> str:
        """Build the planning prompt with optional schema awareness."""
        prompt = self._base_prompt(goals, context)
        
        if self.project_schema:
            # Inject artifact types and phases from schema
            prompt += self._schema_context(self.project_schema)
        
        return prompt
    
    def _schema_context(self, schema: ProjectSchema) -> str:
        """Generate schema-aware planning context."""
        return f"""
## Project Schema: {schema.name}

### Artifact Types
{self._format_artifact_types(schema.artifact_types)}

### Planning Phases
{self._format_phases(schema.planning_config.phases)}

When decomposing tasks:
1. Respect artifact dependency order (requires → produces)
2. Assign parallel_group based on phase mappings
3. Use is_contract=True for definition tasks, False for content tasks
"""
```

### Conflict Resolution

When schema phases conflict with RFC-034's automatic grouping:

```yaml
resolution_policy: schema_wins | rfc034_wins | merge

# schema_wins: Use schema phases exclusively
# rfc034_wins: Ignore schema phases, use CONTRACT_FIRST analysis
# merge: Schema phases as hints, RFC-034 refines within phases
```

Default: `merge` — Schema provides high-level structure, RFC-034 optimizes within phases.

---

## Migration Path

### Existing Projects (No Schema)

Projects without `.sunwell/schema.yaml` continue to work unchanged:

```python
class ProjectSchema:
    @classmethod
    def load_or_default(cls, project_root: Path) -> "ProjectSchema | None":
        """Load schema if present, return None otherwise."""
        schema_path = project_root / ".sunwell" / "schema.yaml"
        if schema_path.exists():
            return cls.load(project_root)
        return None  # No schema = software/general mode
```

### Existing Lenses (No Schema Binding)

Lenses without `compatible_schemas` are **universal** — they work with any project:

```python
def is_lens_compatible(lens: Lens, schema: ProjectSchema | None) -> bool:
    """Check if lens can be used with project."""
    if not lens.metadata.compatible_schemas:
        return True  # Universal lens
    if schema is None:
        return True  # No schema = accept any lens
    return schema.project_type in lens.metadata.compatible_schemas
```

### Gradual Adoption

1. **Phase 1**: Users can add `.sunwell/schema.yaml` to any project
2. **Phase 2**: Existing lenses continue working (universal)
3. **Phase 3**: New domain-specific lenses can declare `compatible_schemas`
4. **Phase 4**: Schema-bound lenses provide richer validation

No breaking changes to existing workflows.

---

## User Experience

### Project Initialization

```bash
# Create a new project with a schema
sunwell init --type fiction --name "The London Conspiracy"

# This creates:
# .sunwell/
#   schema.yaml      # Fiction schema with character, scene, etc.
#   config.yaml      # Project configuration
# artifacts/
#   characters/
#   locations/
#   scenes/
```

### Defining Artifacts

```bash
# Interactive definition
sunwell define character john
# Prompts for required fields, validates against schema

# From file
sunwell define artifacts/characters/john.yaml

# Bulk import
sunwell define artifacts/characters/*.yaml
```

### Working with Lenses

```bash
# Apply a lens for the session
sunwell lens apply developmental-editor

# Run a task with schema + lens awareness
sunwell run "Write the scene where John and Mary meet"

# Sunwell automatically:
# 1. Checks schema: requires Character_john, Character_mary, Relationship_john_mary
# 2. Applies lens: uses "developmental-editor" heuristics
# 3. Validates: runs timeline_consistency, voice_consistency
```

### Validation

```bash
# Validate entire project against schema + lens
sunwell validate

# Output:
# ═══════════════════════════════════════════════════════════════
# 📋 Validation Report: The London Conspiracy
# ═══════════════════════════════════════════════════════════════
#
# Schema Validators:
#   ✅ timeline_consistency: No conflicts found
#   ⚠️ relationship_arc: Relationship john_mary changes to 'love' 
#      but no pivotal scene establishes this (ch07 → ch10)
#   ✅ voice_consistency: All dialogue matches character patterns
#
# Lens Validators (developmental-editor):
#   ✅ character_arc_complete: John shows growth (isolated → connected)
#   ⚠️ conflict_per_scene: Chapter 4 lacks clear conflict
#
# Missing Dependencies:
#   ❌ Scene ch05_argument requires Relationship_john_mary 
#      but relationship not defined until ch06
#
# Suggested Actions:
#   1. Add pivotal scene between ch07-ch10 for john_mary relationship
#   2. Add conflict to Chapter 4
#   3. Move relationship definition before ch05
```

### Visualization

```bash
# Generate dependency graph
sunwell graph --output mermaid

# Output:
# ```mermaid
# graph TD
#     subgraph worldbuilding
#         john["📜 Character: John"]
#         mary["📜 Character: Mary"]
#         london["📜 Setting: London"]
#         john_mary["📜 Relationship: John ↔ Mary"]
#     end
#     subgraph drafting
#         ch01["🔧 Scene: Ch1 Arrival"]
#         ch02["🔧 Scene: Ch2 Flashback"]
#         ch05["🔧 Scene: Ch5 Meeting"]
#     end
#     john --> ch01
#     london --> ch01
#     mary --> ch02
#     john --> ch05
#     mary --> ch05
#     john_mary --> ch05
# ```
```

---

## Implementation Plan

### Phase 1: Schema Core (Week 1-2)

| Task | File | Deliverable |
|------|------|-------------|
| ArtifactType dataclass | `sunwell/project/schema.py` | Type definition |
| ProjectSchema loader | `sunwell/project/schema.py` | YAML parsing with `load_or_default()` |
| Schema → Task resolver | `sunwell/project/resolver.py` | RFC-034 integration |
| ConstraintValidator | `sunwell/project/validators.py` | DSL parser and executor |
| Constraint DSL parser | `sunwell/project/dsl.py` | FOR/WHERE/ASSERT parsing |

**Exit criteria**: Can load schema, resolve artifacts to tasks, run constraint validators

**Validation test**: Load fiction schema, create character + scene artifacts, verify timeline_consistency validator catches conflicts.

### Phase 2: Lens Integration (Week 2-3)

| Task | File | Deliverable |
|------|------|-------------|
| Add `compatible_schemas` to LensMetadata | `sunwell/core/lens.py:21-31` | Field addition |
| Add `schema_validators` to Lens | `sunwell/core/lens.py:74-127` | Field addition |
| SchemaValidator dataclass | `sunwell/core/validator.py` | New validator type |
| `is_lens_compatible()` function | `sunwell/project/compatibility.py` | Binding logic |
| Schema-aware planning prompt | `sunwell/naaru/planners/agent.py` | `_schema_context()` method |
| Validator merge logic | `sunwell/project/validators.py` | Schema + Lens validator ordering |

**Exit criteria**: Lens + Schema validation works together; `developmental-editor.lens` validates fiction schema artifacts

**Validation test**: Apply `developmental-editor` lens to fiction project, verify both schema validators AND lens schema_validators run.

### Phase 3: CLI Integration (Week 3-4)

| Task | File | Deliverable |
|------|------|-------------|
| `sunwell init --type` | `sunwell/cli/init.py` | Project creation from template |
| `sunwell define` | `sunwell/cli/define.py` | Interactive artifact creation |
| `sunwell validate` | `sunwell/cli/validate.py` | Full validation with reports |
| `sunwell graph` | `sunwell/cli/graph.py` | Mermaid visualization |
| Schema detection | `sunwell/cli/helpers.py` | Auto-detect `.sunwell/schema.yaml` |

**Exit criteria**: Full CLI workflow works end-to-end

**Validation test**: `sunwell init --type fiction`, define 2 characters + 1 scene, run `sunwell validate`, see timeline check pass.

### Phase 4: Template Schemas + Integration Tests (Week 4)

| Task | Deliverable |
|------|-------------|
| Fiction schema template | `schemas/fiction.yaml` |
| Research schema template | `schemas/research.yaml` |
| Documentation schema template | `schemas/documentation.yaml` |
| Integration test: fiction project | `tests/integration/test_fiction_schema.py` |
| Integration test: research project | `tests/integration/test_research_schema.py` |

**Exit criteria**: Users can start with templates; non-software domains verified working

**Validation test**: Full end-to-end test creating a 3-chapter fiction project with `AgentPlanner`, verifying task graph respects schema phases.

---

## Schema Specification

### Artifact Type Definition

```yaml
artifact_types:
  <type_name>:
    description: string              # Human-readable description
    fields:
      required: [field_name, ...]    # Must be present
      optional: [field_name, ...]    # May be present
    produces: string                 # Template for produced artifact ID
    requires: [string, ...]          # Templates for required artifacts
    modifies: [string, ...]          # Templates for modified resources
    is_contract: boolean             # True if this defines an interface
    when:                            # Conditional requirements
      - if: field_condition
        requires: template
```

### Template Syntax

Templates use `{field_name}` for simple substitution:

```yaml
produces: "Character_{id}"          # → "Character_john"
requires:
  - "Character_{pov}"               # → "Character_john"
  - "Setting_{location}"            # → "Setting_london"
```

For iteration over lists:

```yaml
requires:
  - "Character_{char}" for char in characters_present
```

### Validator Definition

```yaml
validators:
  - name: string                     # Unique identifier
    description: string              # What it checks
    rule: string                     # Constraint DSL or LLM prompt
    severity: error | warning | info # How serious
    method: constraint | llm         # How to evaluate (see Validator Execution Engine)
    applies_to: artifact_type        # Optional: only for this type
```

**Method options**:
- `constraint`: Deterministic DSL (FOR/WHERE/ASSERT) — fast, reproducible
- `llm`: LLM-based judgment — flexible, handles nuance

---

## Design Decisions

### Decision 1: Schema Format

| Option | Format | Pros | Cons |
|--------|--------|------|------|
| **A: YAML** | `.sunwell/schema.yaml` | Human-readable, familiar | Verbose, no validation |
| **B: JSON Schema** | `.sunwell/schema.json` | Strict validation, tooling | Less readable |
| **C: Python DSL** | `schema.py` | Type-safe, IDE support | Requires Python knowledge |

**Recommendation**: **Option A (YAML)** with JSON Schema validation. YAML is accessible to non-programmers while JSON Schema provides strictness.

### Decision 2: Artifact Storage

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: YAML files** | One file per artifact | Human-editable, git-friendly | Many files |
| **B: SQLite** | Single database | Fast queries, relations | Not human-editable |
| **C: Markdown** | Frontmatter + content | Writer-friendly | Parsing complexity |

**Recommendation**: **Option A (YAML files)** for schema-defined artifacts, **Option C (Markdown)** for content artifacts (scenes, chapters). This matches how writers actually work.

### Decision 3: Validator Execution

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: Heuristic only** | Pattern matching, rules | Fast, deterministic | Limited expressiveness |
| **B: LLM only** | All validation via LLM | Flexible, understands nuance | Slow, non-deterministic |
| **C: Tiered** | Heuristic first, LLM for complex | Best of both | Implementation complexity |

**Recommendation**: **Option C (Tiered)** — Fast heuristic checks for structural issues, LLM for nuanced checks like "voice consistency" or "character motivation believability".

### Decision 4: Constraint DSL vs Python Functions

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: Custom DSL** | FOR/WHERE/ASSERT syntax | YAML-embeddable, sandboxed | Parser complexity, learning curve |
| **B: Python functions** | `def validate(artifacts):` | Full power, familiar | Security risk, requires Python knowledge |
| **C: JSONPath + assertions** | Standard query language | Well-documented, tooling exists | Limited expressiveness |

**Recommendation**: **Option A (Custom DSL)** for these reasons:

1. **Security**: No arbitrary code execution in user-provided YAML
2. **Portability**: Rules are data, not code — can be version-controlled, shared
3. **Simplicity**: Limited vocabulary (FOR, WHERE, ASSERT) is easier to learn than Python
4. **Debugging**: DSL rules produce clear violation messages with bindings

**Fallback**: If DSL proves too limiting, add `method: python` with sandboxed execution (pyodide) in future.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Schema too complex for users** | Medium | High | Provide templates, good error messages, wizard CLI |
| **Template syntax confusing** | Medium | Medium | Keep simple `{field}` syntax, document well |
| **LLM validators slow** | Medium | Low | Run async, cache results, make optional |
| **Cross-artifact validation expensive** | Low | Medium | Incremental validation, only affected artifacts |
| **Schema changes break projects** | Medium | High | Schema versioning, migration tooling |
| **Constraint DSL too limited** | Medium | Medium | Start simple, add constructs as needed; LLM fallback |
| **Lens-schema mismatch confusion** | Low | Medium | Clear error: "Lens X requires schema type Y, but project has Z" |

---

## Examples

### Fiction Project

```
my-novel/
├── .sunwell/
│   ├── schema.yaml                  # Fiction schema
│   └── config.yaml
├── artifacts/
│   ├── characters/
│   │   ├── john.yaml
│   │   └── mary.yaml
│   ├── locations/
│   │   └── london.yaml
│   └── relationships/
│       └── john_mary.yaml
├── chapters/
│   ├── ch01_arrival.md              # Frontmatter + prose
│   └── ch02_flashback.md
└── lenses/
    └── developmental-editor.lens    # Project-specific customizations
```

### Research Paper Project

```yaml
# .sunwell/schema.yaml for research
artifact_types:
  hypothesis:
    fields:
      required: [statement, variables, prediction]
    produces: "Hypothesis_{id}"
    is_contract: true
    
  experiment:
    fields:
      required: [hypothesis, method, sample_size]
    requires: ["Hypothesis_{hypothesis}"]
    produces: "Experiment_{id}"
    
  result:
    fields:
      required: [experiment, data, analysis]
    requires: ["Experiment_{experiment}"]
    produces: "Result_{id}"
    
  claim:
    fields:
      required: [statement, evidence]
    requires:
      - "Result_{r}" for r in evidence
    produces: "Claim_{id}"

validators:
  - name: evidence_required
    rule: "Every claim must cite at least one result"
    severity: error
    
  - name: hypothesis_tested
    rule: "Every hypothesis must have at least one experiment"
    severity: warning
```

---

## Success Criteria

### Quantitative

- [ ] Schema loading <100ms for typical project (50 artifacts)
- [ ] Constraint validation <500ms for 50 artifacts
- [ ] LLM validation <10s per validator (async, parallelized)
- [ ] Template schemas work out-of-box for fiction, research, docs

### Qualitative

- [ ] Non-programmer can define artifacts in YAML
- [ ] Dependency errors caught before execution
- [ ] Validation messages are actionable with fix suggestions
- [ ] Graph visualization shows clear structure with phase groupings
- [ ] Existing lenses work unchanged (backward compatibility)
- [ ] Schema-bound lenses refuse incompatible projects with clear message

### Integration Tests

- [ ] `test_fiction_schema.py`: Create characters, verify timeline validator
- [ ] `test_research_schema.py`: Create hypothesis → experiment → result chain
- [ ] `test_lens_schema_binding.py`: Verify `compatible_schemas` enforcement
- [ ] `test_migration_path.py`: Existing project works without schema

---

## Future Work

1. **Schema Marketplace** — Share and discover schemas for different domains
2. **Schema Migrations** — Tooling for evolving schemas over time
3. **Cross-Project References** — Link artifacts between projects (e.g., series)
4. **GUI Builder** — Visual schema and artifact editor
5. **Real-time Validation** — IDE integration for live feedback

---

## References

### Code References

| Component | Location | Purpose |
|-----------|----------|---------|
| Task dataclass | `naaru/types.py:148-289` | RFC-034 task model with produces/requires/modifies |
| Lens dataclass | `core/lens.py:74-127` | Expertise container (modify for schema binding) |
| LensMetadata | `core/lens.py:21-31` | Lens metadata (add compatible_schemas) |
| DeterministicValidator | `core/validator.py:11-32` | Script-based validators |
| HeuristicValidator | `core/validator.py:34-73` | LLM-based validators |
| AgentPlanner | `naaru/planners/agent.py:22-100` | Planning prompts (add schema context) |
| Analysis utilities | `naaru/analysis.py:26-84` | RFC-034 graph analysis |
| Lens files | `lenses/*.lens` | Existing lens YAML format |

### New Files (RFC-035)

| Component | Location | Purpose |
|-----------|----------|---------|
| ProjectSchema | `project/schema.py` | Schema dataclass and loader |
| ArtifactType | `project/schema.py` | Artifact type definition |
| ConstraintValidator | `project/validators.py` | DSL-based validator |
| SchemaValidator | `core/validator.py` | Lens-provided schema validator |
| Constraint DSL | `project/dsl.py` | FOR/WHERE/ASSERT parser |

### Related RFCs

- **RFC-034**: Contract-Aware Parallel Task Planning (foundation)
- **RFC-011**: Agent Skills (lens skills integration)
- **RFC-021**: Spellbook (lens workflows)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-18 | Initial draft |
| 2026-01-18 | Added: Lens Dataclass Modifications (compatible_schemas, schema_validators) |
| 2026-01-18 | Added: Validator Execution Engine with constraint DSL specification |
| 2026-01-18 | Added: Schema Module Disambiguation (schema/ vs .sunwell/schema.yaml) |
| 2026-01-18 | Added: Planning Strategy Integration (phases → CONTRACT_FIRST mapping) |
| 2026-01-18 | Added: Migration Path for existing projects and lenses |
| 2026-01-18 | Added: Decision 4 (Constraint DSL vs Python Functions) |
| 2026-01-18 | Updated: Implementation Plan with validation tests per phase |
| 2026-01-18 | Updated: Code references with accurate line numbers |