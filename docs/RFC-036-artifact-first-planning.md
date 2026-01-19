# RFC-036: Artifact-First Planning with Dynamic Discovery

| Field | Value |
|-------|-------|
| **RFC** | 036 |
| **Title** | Artifact-First Planning with Dynamic Discovery |
| **Status** | Draft |
| **Created** | 2026-01-19 |
| **Author** | llane |
| **Builds on** | RFC-034 (Contract-Aware Planning), RFC-035 (Domain-Agnostic Projects) |

---

## Abstract

Traditional AI agent planning is **procedural**: decompose a goal into steps, execute steps in order. This RFC proposes an **artifact-first** approach: identify what must exist when the goal is complete, then let dependency resolution determine execution order.

**The key insight**: Planning is a DAG problem, but we've been approaching it backwards. Instead of decomposing from the trunk (goal) to leaves (tasks), we identify all leaves (artifacts) and let them converge upward to the trunk (completed goal).

```
PROCEDURAL (current):     Goal → decompose → [Task 1] → [Task 2] → [Task 3] → Done
ARTIFACT-FIRST (proposed): [A] [B] [C] ← identify these    
                             ↘  ↓  ↙
                              [Done] ← convergence
```

**Why now?** This approach was impractical before AI because it required knowing all artifacts upfront. LLMs can **discover** the artifact graph dynamically, removing the omniscience requirement that made declarative planning impossible for fuzzy, creative, or exploratory work.

---

## Goals and Non-Goals

### Goals

1. **Artifact-first planning** — Ask "what must exist?" not "what steps to take?"
2. **Dynamic graph discovery** — AI identifies artifacts from fuzzy goals, discovers more mid-execution
3. **Dependency-driven execution** — Order emerges from the graph, not from decomposition
4. **Maximal parallelization** — All leaves can execute simultaneously
5. **Composable artifacts** — Artifacts are reusable across goals and projects

### Non-Goals

1. **Replace RFC-034** — This extends RFC-034's infrastructure, doesn't replace it
2. **Static-only graphs** — The graph can grow during execution
3. **Domain-specific** — Works for code, fiction, research, any domain (via RFC-035)
4. **Deterministic discovery** — LLM-based discovery is inherently non-deterministic

---

## Motivation

### The Procedural Trap

Current AI agents think procedurally:

```
User: "Build a REST API with authentication"

Agent (procedural thinking):
  1. First, I'll create the project structure
  2. Then, I'll define the User model
  3. Next, I'll implement authentication
  4. Then, I'll create the routes
  5. Finally, I'll wire it together
```

This has problems:

| Problem | Consequence |
|---------|-------------|
| **Sequential by default** | Steps 2-4 could parallelize, but procedural thinking serializes |
| **Order is arbitrary** | Why User before Auth? The decomposition imposes false ordering |
| **Brittle to changes** | Insert a step and you re-plan everything |
| **Verification is step-based** | "Did step 3 complete?" vs "Does Auth exist and work?" |

### The Build System Insight

Build systems solved this decades ago:

```makefile
# Make doesn't say "first compile a.c, then b.c, then link"
# It says "app needs a.o and b.o; figure out the order"

app: main.o utils.o auth.o
	$(CC) -o $@ $^

%.o: %.c
	$(CC) -c $< -o $@
```

**Execution order emerges from dependencies**, not from a prescribed sequence. This enables:

- Automatic parallelization (independent targets build simultaneously)
- Incremental builds (only rebuild what changed)
- Clear verification (does the target exist and satisfy its spec?)

### The Pre-AI Limitation

Why didn't we use this for AI agents? **Because you have to know the graph upfront.**

```makefile
# Someone had to write every dependency by hand:
app: main.o utils.o auth.o database.o config.o logging.o ...
```

This works for well-understood domains (compiling code) but fails for:

- **Creative work**: "Write a novel" — you don't know all characters upfront
- **Exploratory work**: "Make this faster" — you don't know the bottlenecks
- **Fuzzy goals**: "Build something like X" — you don't know the components

### The AI Unlock

LLMs remove the omniscience requirement:

```python
# Before AI: Human specifies graph → System resolves
artifacts = human_writes_makefile()  # High burden, must know everything

# With AI: Human specifies goal → AI discovers graph → System resolves
artifacts = llm.discover("Build a REST API with auth")  # Low burden
```

The LLM can:
1. **Identify artifacts** from a vague goal
2. **Infer dependencies** from semantics
3. **Discover new artifacts** mid-execution

This makes declarative/artifact-based planning viable for any domain.

---

## Core Concepts

### Artifact vs Task

| Concept | Task (RFC-034) | Artifact (RFC-036) |
|---------|---------------|-------------------|
| **Question** | "What should I do?" | "What must exist?" |
| **Identity** | Action description | Named thing with spec |
| **Completion** | Action finished | Thing exists and satisfies spec |
| **Dependencies** | "Do X before Y" | "Y requires X to exist" |
| **Verification** | "Did action complete?" | "Does artifact satisfy spec?" |

**Artifacts are nouns, tasks are verbs.** This RFC argues nouns are the better primitive.

### Artifact Specification

An artifact has an identity and a specification (contract):

```python
@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """What an artifact must provide/satisfy.
    
    The spec is the CONTRACT — like a Protocol/Interface in code.
    The artifact is the IMPLEMENTATION — the actual file/content.
    """
    
    id: str
    """Unique identifier: 'UserProtocol', 'Chapter1', 'Hypothesis_A'"""
    
    description: str
    """Human-readable: 'Protocol defining User with id, email, password_hash'"""
    
    contract: str
    """What this artifact must satisfy.
    
    For code: type signature, protocol definition
    For prose: outline, requirements
    For research: hypothesis statement, methodology spec
    """
    
    produces_file: str | None = None
    """File path this artifact creates/modifies."""
    
    requires: frozenset[str] = field(default_factory=frozenset)
    """Other artifact IDs that must exist before this can be created."""
    
    domain_type: str | None = None
    """RFC-035 schema type: 'character', 'protocol', 'hypothesis', etc."""
```

### The Artifact Graph

Artifacts form a directed acyclic graph (DAG) where edges represent dependencies:

```
UserProtocol ──┬──→ UserModel ────┬──→ UserRoutes ──┐
               │                  │                 │
AuthInterface ─┴──→ AuthService ──┴──→ AuthRoutes ──┼──→ App
                                                    │
DatabaseConfig ─────────────────────────────────────┘
```

**Leaves** (no dependencies): `UserProtocol`, `AuthInterface`, `DatabaseConfig`
**Roots** (nothing depends on them): `App`

Execution proceeds from leaves to roots. All leaves can execute in parallel.

---

## Planning Model

### From Decomposition to Discovery

**RFC-034 (procedural decomposition):**
```
Input: Goal
Process: LLM breaks goal into ordered steps
Output: Task list with depends_on relationships
```

**RFC-036 (artifact discovery):**
```
Input: Goal
Process: LLM identifies what must exist when goal is complete
Output: Artifact graph with requires relationships
```

### The Discovery Prompt

```python
def discover_artifacts(goal: str, context: str | None = None) -> list[ArtifactSpec]:
    """Discover artifacts needed to complete a goal."""
    
    prompt = f"""
GOAL: {goal}

CONTEXT:
{context or "No additional context."}

=== ARTIFACT DISCOVERY ===

Think about this goal differently. Don't ask "what steps should I take?"
Instead ask: "When this goal is complete, what THINGS will exist?"

For each thing that must exist, identify:
- id: A unique name (e.g., "UserProtocol", "Chapter1", "Hypothesis_A")
- description: What is this thing?
- contract: What must it provide/satisfy? (This is its specification)
- requires: What other artifacts must exist BEFORE this one can be created?
- produces_file: What file will contain this artifact?

=== DISCOVERY PRINCIPLES ===

1. CONTRACTS BEFORE IMPLEMENTATIONS
   Interfaces, protocols, outlines, specs — these have no dependencies.
   Implementations require their contracts to exist first.

2. IDENTIFY ALL LEAVES
   Leaves are artifacts with no requirements. They can all be created in parallel.
   Ask: "What can I create right now with no prerequisites?"

3. TRACE TO ROOT
   The root is the final artifact that satisfies the goal.
   Everything flows toward it.

4. SEMANTIC DEPENDENCIES
   A requires B if creating A needs to reference, implement, or build on B.
   "UserModel requires UserProtocol" because it implements that protocol.

=== EXAMPLE ===

Goal: "Build a REST API with user authentication"

Artifacts discovered:

```json
[
  {{
    "id": "UserProtocol",
    "description": "Protocol defining User entity",
    "contract": "Protocol with fields: id (UUID), email (str), password_hash (str), created_at (datetime)",
    "requires": [],
    "produces_file": "src/protocols/user.py"
  }},
  {{
    "id": "AuthInterface", 
    "description": "Interface for authentication operations",
    "contract": "Protocol with methods: authenticate(email, password) -> User | None, generate_token(user) -> str, verify_token(token) -> User | None",
    "requires": [],
    "produces_file": "src/protocols/auth.py"
  }},
  {{
    "id": "UserModel",
    "description": "SQLAlchemy model implementing UserProtocol",
    "contract": "Class User(Base) implementing UserProtocol with SQLAlchemy column mappings",
    "requires": ["UserProtocol"],
    "produces_file": "src/models/user.py"
  }},
  {{
    "id": "AuthService",
    "description": "JWT-based authentication service",
    "contract": "Class AuthService implementing AuthInterface using JWT tokens, bcrypt for password hashing",
    "requires": ["AuthInterface", "UserProtocol"],
    "produces_file": "src/services/auth.py"
  }},
  {{
    "id": "UserRoutes",
    "description": "REST endpoints for user operations",
    "contract": "Flask Blueprint with routes: POST /users (register), GET /users/me (profile), PUT /users/me (update)",
    "requires": ["UserModel", "AuthService"],
    "produces_file": "src/routes/users.py"
  }},
  {{
    "id": "App",
    "description": "Flask application factory",
    "contract": "create_app() function that initializes Flask, registers blueprints, configures database",
    "requires": ["UserRoutes"],
    "produces_file": "src/app.py"
  }}
]
```

Analysis:
- Leaves (parallel): UserProtocol, AuthInterface (no requirements)
- Second wave: UserModel, AuthService (require protocols)
- Third wave: UserRoutes (requires model + service)
- Root: App (final convergence)

=== NOW DISCOVER ARTIFACTS FOR ===

Goal: {goal}

Output ONLY valid JSON array of artifacts:
"""
    
    response = llm.generate(prompt)
    return parse_artifacts(response)
```

### Execution by Resolution

Once we have the artifact graph, execution is straightforward dependency resolution:

```python
async def execute_artifact_graph(
    artifacts: dict[str, ArtifactSpec],
    create_fn: Callable[[ArtifactSpec], Awaitable[Any]],
) -> dict[str, Any]:
    """Execute artifacts in dependency order, maximizing parallelism."""
    
    completed: dict[str, Any] = {}
    pending = set(artifacts.keys())
    
    while pending:
        # Find all artifacts whose dependencies are satisfied
        ready = [
            artifacts[aid] for aid in pending
            if all(req in completed for req in artifacts[aid].requires)
        ]
        
        if not ready:
            # Deadlock detection
            raise CyclicDependencyError(f"Cycle detected in: {pending}")
        
        # Execute all ready artifacts in parallel
        results = await asyncio.gather(
            *[create_fn(artifact) for artifact in ready],
            return_exceptions=True,
        )
        
        # Process results
        for artifact, result in zip(ready, results, strict=True):
            if isinstance(result, Exception):
                raise ArtifactCreationError(artifact.id, result)
            completed[artifact.id] = result
            pending.remove(artifact.id)
    
    return completed
```

---

## Dynamic Discovery

### The Static Limitation

Traditional build systems require complete graphs upfront. But real work often reveals new requirements:

> "I'm implementing AuthService and realize I need a TokenBlacklist for logout..."

### Mid-Execution Discovery

RFC-036 allows the artifact graph to grow during execution:

```python
async def execute_with_discovery(
    goal: str,
    initial_artifacts: dict[str, ArtifactSpec],
    create_fn: Callable[[ArtifactSpec], Awaitable[Any]],
    discover_fn: Callable[[str, dict[str, Any], ArtifactSpec], Awaitable[list[ArtifactSpec]]],
) -> dict[str, Any]:
    """Execute with dynamic artifact discovery."""
    
    artifacts = dict(initial_artifacts)
    completed: dict[str, Any] = {}
    pending = set(artifacts.keys())
    
    while pending:
        ready = [
            artifacts[aid] for aid in pending
            if all(req in completed for req in artifacts[aid].requires)
        ]
        
        if not ready:
            raise CyclicDependencyError(f"Cycle detected in: {pending}")
        
        for artifact in ready:
            # Create the artifact
            result = await create_fn(artifact)
            completed[artifact.id] = result
            pending.remove(artifact.id)
            
            # === DYNAMIC DISCOVERY ===
            # After creating an artifact, check if we discovered new needs
            new_artifacts = await discover_fn(goal, completed, artifact)
            
            for new_artifact in new_artifacts:
                if new_artifact.id not in artifacts:
                    # Validate: new artifact can only depend on existing artifacts
                    unknown_deps = new_artifact.requires - set(artifacts.keys())
                    if unknown_deps:
                        # Recursively discover dependencies
                        for dep_id in unknown_deps:
                            dep_artifacts = await discover_fn(goal, completed, new_artifact)
                            for dep in dep_artifacts:
                                artifacts[dep.id] = dep
                                pending.add(dep.id)
                    
                    artifacts[new_artifact.id] = new_artifact
                    pending.add(new_artifact.id)
    
    return completed
```

### Discovery Triggers

When should we look for new artifacts?

| Trigger | Example | Discovery Prompt |
|---------|---------|-----------------|
| **Post-creation** | After creating AuthService | "Given AuthService exists, what else might be needed?" |
| **Error recovery** | Import fails | "AuthService needs X which doesn't exist. What is X?" |
| **Spec refinement** | Contract clarification | "UserProtocol needs password validation. New artifact?" |
| **User feedback** | "Also add logout" | "Goal expanded. What new artifacts are needed?" |

### Discovery Prompt (Mid-Execution)

```python
async def discover_new_artifacts(
    goal: str,
    completed: dict[str, Any],
    just_created: ArtifactSpec,
) -> list[ArtifactSpec]:
    """Discover if creating an artifact revealed new needs."""
    
    prompt = f"""
GOAL: {goal}

COMPLETED ARTIFACTS:
{format_completed(completed)}

JUST CREATED:
- {just_created.id}: {just_created.description}
- File: {just_created.produces_file}
- Contract: {just_created.contract}

=== DISCOVERY CHECK ===

Now that {just_created.id} exists, consider:

1. Did creating it reveal any MISSING ARTIFACTS?
   - Dependencies that should have existed but don't
   - Supporting artifacts that would make this more complete
   - Error handlers, validators, or utilities needed

2. Did the contract EXPAND?
   - The spec mentioned something not yet in the graph
   - Integration points with systems not yet created

3. Is the goal CLOSER but still incomplete?
   - What else must exist for the original goal to be satisfied?

If new artifacts are needed, output them as JSON.
If no new artifacts are needed, output an empty array: []

IMPORTANT: Only identify artifacts that are TRULY NEEDED, not nice-to-haves.
"""
    
    response = await llm.generate(prompt)
    return parse_artifacts(response)
```

---

## Failure Recovery

Discovery can fail. The system must handle bad outputs gracefully.

### Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| **Empty graph** | 0 artifacts discovered | Re-prompt with examples; fall back to SEQUENTIAL |
| **Missing root** | No artifact satisfies goal | Ask "what final artifact completes the goal?" |
| **Cycle detected** | Topological sort fails | Show cycle; ask LLM to break it; allow manual edit |
| **Orphan artifacts** | Artifacts with no path to root | Warn; either connect or discard |
| **Spec too vague** | Contract is ambiguous | Re-prompt for specific contract; provide examples |
| **Graph explosion** | >MAX_ARTIFACTS discovered | Warn; require user confirmation to continue |

### Recovery Protocol

```python
async def discover_with_recovery(
    goal: str,
    max_retries: int = 3,
    max_artifacts: int = 50,
) -> ArtifactGraph:
    """Discover artifacts with failure recovery."""
    
    for attempt in range(max_retries):
        artifacts = await discover_artifacts(goal)
        
        # Validation checks
        if not artifacts:
            log.warning(f"Empty graph (attempt {attempt + 1})")
            goal = f"{goal}\n\nPrevious attempt found no artifacts. Be more concrete."
            continue
        
        if len(artifacts) > max_artifacts:
            raise GraphExplosionError(
                f"Discovery produced {len(artifacts)} artifacts (max: {max_artifacts}). "
                f"Consider breaking goal into smaller subgoals."
            )
        
        graph = build_graph(artifacts)
        
        if cycle := graph.detect_cycle():
            log.warning(f"Cycle detected: {cycle}")
            artifacts = await break_cycle(goal, artifacts, cycle)
            graph = build_graph(artifacts)
        
        if not graph.has_root():
            root = await discover_root(goal, artifacts)
            artifacts.append(root)
            graph = build_graph(artifacts)
        
        if orphans := graph.find_orphans():
            log.info(f"Orphan artifacts (not connected to root): {orphans}")
            # Orphans are allowed but logged — may be useful later
        
        return graph
    
    raise DiscoveryFailedError(f"Failed after {max_retries} attempts")
```

### Cycle Breaking

When the LLM discovers a cycle (A requires B, B requires A), ask it to resolve:

```python
async def break_cycle(
    goal: str,
    artifacts: list[ArtifactSpec],
    cycle: list[str],
) -> list[ArtifactSpec]:
    """Ask LLM to break a dependency cycle."""
    
    prompt = f"""
GOAL: {goal}

CYCLE DETECTED in artifact dependencies:
{' → '.join(cycle)} → {cycle[0]}

This is impossible to execute. One of these dependencies must be wrong.

Consider:
1. Is one dependency actually optional?
2. Should one artifact be split into two (interface + implementation)?
3. Are two artifacts actually the same thing?

Return the corrected artifact list with the cycle broken.
"""
    
    response = await llm.generate(prompt)
    return parse_artifacts(response)
```

### Manual Override

Users can always intervene:

```bash
# View discovered graph
sunwell plan --show-graph

# Edit artifact manually
sunwell plan --edit-artifact UserProtocol

# Add missing artifact
sunwell plan --add-artifact '{"id": "MissingThing", ...}'

# Remove problematic artifact
sunwell plan --remove-artifact ProblematicArtifact

# Force continue despite warnings
sunwell plan --force
```

---

## Integration with RFC-034

### Task → Artifact Mapping

RFC-034's `Task` can be viewed as "create this artifact":

```python
def artifact_to_task(artifact: ArtifactSpec) -> Task:
    """Convert an artifact spec to an RFC-034 task."""
    return Task(
        id=artifact.id,
        description=f"Create {artifact.description}",
        mode=TaskMode.GENERATE,
        
        # RFC-034 fields map directly
        produces=frozenset([artifact.id]),
        requires=artifact.requires,
        modifies=frozenset([artifact.produces_file]) if artifact.produces_file else frozenset(),
        
        # Contract becomes the task's specification
        is_contract=artifact.domain_type in ("protocol", "interface", "spec"),
        contract=artifact.contract,
        
        # Parallel group from domain type
        parallel_group="contracts" if artifact.requires == frozenset() else "implementations",
    )
```

### Coexistence

RFC-036 doesn't replace RFC-034. It provides an alternative **planning strategy**:

```python
class PlanningStrategy(Enum):
    """How to plan task execution."""
    
    SEQUENTIAL = "sequential"        # RFC-032: Linear task list
    CONTRACT_FIRST = "contract_first"  # RFC-034: Phases with parallelism
    RESOURCE_AWARE = "resource_aware"  # RFC-034: Minimize file conflicts
    ARTIFACT_FIRST = "artifact_first"  # RFC-036: Artifact discovery + resolution
```

Users can choose based on their needs:

| Strategy | Best For |
|----------|----------|
| `SEQUENTIAL` | Simple, well-understood tasks |
| `CONTRACT_FIRST` | Structured projects with clear interfaces |
| `RESOURCE_AWARE` | File-heavy projects needing conflict avoidance |
| `ARTIFACT_FIRST` | Fuzzy goals, creative work, exploration |

### Strategy Interaction

**Q: Can ARTIFACT_FIRST and RESOURCE_AWARE combine?**

Yes. They operate at different levels:

- `ARTIFACT_FIRST` is a **planning paradigm** — how to discover what to do
- `RESOURCE_AWARE` is an **execution constraint** — how to avoid conflicts

```python
# ARTIFACT_FIRST discovers artifacts, then applies RESOURCE_AWARE conflict detection
artifacts = discover_artifacts(goal)
tasks = [artifact_to_task(a) for a in artifacts]

# RFC-034's conflict detection still applies
for t1, t2 in parallel_candidates(tasks):
    if t1.modifies & t2.modifies:  # File conflict
        # Serialize these tasks despite both being "ready"
        schedule_sequentially(t1, t2)
```

**Recommended combination**: Use `ARTIFACT_FIRST` for planning, inherit `RESOURCE_AWARE` conflict detection automatically. This is the default when `ARTIFACT_FIRST` is selected.

---

## Integration with RFC-035

### Artifacts as Schema Instances

RFC-035 defines domain schemas. Artifacts are instances of those schemas:

```yaml
# RFC-035 schema defines the type
artifact_types:
  character:
    description: "A person in the story"
    fields:
      required: [name, traits]
    produces: "Character_{id}"

# RFC-036 artifact is an instance
artifacts:
  - id: "Character_john"
    domain_type: character
    description: "John Hartwell, the protagonist"
    contract: "name: John Hartwell, traits: [stubborn, loyal, haunted]"
    requires: []
```

### RFC-035 Dependency: Optional Enhancement

**Q: Does RFC-036 require RFC-035 to ship first?**

**No.** ARTIFACT_FIRST works standalone. RFC-035 is an **enhancement**, not a requirement.

| Mode | RFC-035 Status | Behavior |
|------|----------------|----------|
| **Standalone** | Not available | Generic artifact types, no schema validation |
| **Schema-aware** | Available | Domain-specific types, schema validation, richer contracts |

```python
def discover_artifacts(goal: str, schema: ProjectSchema | None = None) -> list[ArtifactSpec]:
    """Discover artifacts, with optional schema awareness."""
    
    if schema is None:
        # Standalone mode: generic discovery
        return _discover_generic(goal)
    else:
        # Schema-aware mode: RFC-035 integration
        return _discover_with_schema(goal, schema)
```

**Implementation order**: RFC-036 Phase 1-3 work without RFC-035. Phase 4 can add schema integration when RFC-035 ships.

### Schema-Aware Discovery

When a project has a schema, discovery uses it:

```python
def discover_artifacts_with_schema(
    goal: str,
    schema: ProjectSchema,
) -> list[ArtifactSpec]:
    """Discover artifacts using RFC-035 schema awareness."""
    
    prompt = f"""
GOAL: {goal}

PROJECT SCHEMA: {schema.name} (type: {schema.project_type})

AVAILABLE ARTIFACT TYPES:
{format_artifact_types(schema.artifact_types)}

PLANNING PHASES:
{format_phases(schema.planning_config.phases)}

=== SCHEMA-AWARE DISCOVERY ===

Identify artifacts needed for this goal. Each artifact must:
1. Be one of the defined artifact_types (or a generic artifact)
2. Follow the schema's field requirements
3. Respect the planning phases

For each artifact:
- id: Following the schema's produces pattern (e.g., "Character_{{id}}")
- domain_type: The artifact_type from the schema
- description: What is this specific instance?
- contract: The required fields filled in
- requires: Other artifacts (using their IDs)

=== EXAMPLE (fiction schema) ===

Goal: "Write the opening chapter where John arrives in London"

Artifacts:
- Character_john (domain_type: character, requires: [])
- Setting_london_docks (domain_type: location, requires: [])  
- Scene_ch01_arrival (domain_type: scene, requires: [Character_john, Setting_london_docks])

Now discover artifacts for: {goal}
"""
    
    response = llm.generate(prompt)
    return parse_artifacts(response)
```

---

## Verification Model

### Spec Satisfaction

Artifacts aren't just "done" — they must **satisfy their spec**:

```python
async def verify_artifact(
    artifact: ArtifactSpec,
    created_content: str,
) -> VerificationResult:
    """Verify that created content satisfies the artifact's contract."""
    
    # Tier 1: Deterministic checks (if applicable)
    if artifact.domain_type == "protocol":
        # Run mypy/pyright to verify type correctness
        type_result = await run_type_checker(artifact.produces_file)
        if not type_result.passed:
            return VerificationResult(
                passed=False,
                reason=f"Type check failed: {type_result.errors}",
            )
    
    # Tier 2: LLM-based verification
    prompt = f"""
ARTIFACT: {artifact.id}

CONTRACT (what it must satisfy):
{artifact.contract}

CREATED CONTENT:
{created_content}

=== VERIFICATION ===

Does the created content satisfy the contract?

Check:
1. Are all required elements present?
2. Does the implementation match the specification?
3. Are there any violations or missing pieces?

Output:
- passed: true/false
- reason: Explanation
- gaps: List of missing/incorrect elements (if any)
"""
    
    response = await llm.generate(prompt)
    return parse_verification(response)
```

### Verification vs Task Completion

| RFC-034 (Task) | RFC-036 (Artifact) |
|----------------|-------------------|
| "Did the action complete?" | "Does the artifact satisfy its spec?" |
| Binary: done/not done | Gradated: satisfies/partially/violates |
| Check once after action | Can re-verify anytime |
| Action-focused | Contract-focused |

---

## Example: Fiction Project

### Goal

> "Write Chapter 1 where John arrives in London, haunted by war memories"

### Artifact Discovery

```json
[
  {
    "id": "Character_john",
    "domain_type": "character",
    "description": "John Hartwell, former soldier, protagonist",
    "contract": "name: John Hartwell, age: 45, traits: [stubborn, loyal, haunted], backstory: Crimean War veteran, lost brother in battle",
    "requires": [],
    "produces_file": "artifacts/characters/john.yaml"
  },
  {
    "id": "Setting_london_docks",
    "domain_type": "location",
    "description": "London docks in 1856",
    "contract": "name: London Docks, era: 1856, atmosphere: foggy, crowded, industrial, sounds of commerce and ships",
    "requires": [],
    "produces_file": "artifacts/locations/london_docks.yaml"
  },
  {
    "id": "Scene_ch01_arrival",
    "domain_type": "scene",
    "description": "John arrives at London docks, war memories triggered by crowds",
    "contract": "pov: john, location: london_docks, conflict: crowds trigger war flashbacks, outcome: John finds lodging but remains isolated",
    "requires": ["Character_john", "Setting_london_docks"],
    "produces_file": "chapters/ch01_arrival.md"
  }
]
```

### Execution

```
Wave 1 (parallel):
  → Create Character_john
  → Create Setting_london_docks

Wave 2:
  → Create Scene_ch01_arrival (requires both from Wave 1)

Verification:
  ✓ Character_john satisfies character contract
  ✓ Setting_london_docks satisfies location contract
  ✓ Scene_ch01_arrival satisfies scene contract
  ✓ Scene references john's traits correctly
  ✓ Scene uses london_docks atmosphere
```

### Dynamic Discovery

While writing the scene, the LLM realizes:

> "The scene mentions a mysterious woman John notices. New artifact needed?"

```json
{
  "id": "Character_mysterious_woman",
  "domain_type": "character",
  "description": "Unnamed woman John notices at the docks (foreshadowing)",
  "contract": "name: Unknown, traits: [observant, out-of-place], first_appearance: ch01",
  "requires": [],
  "produces_file": "artifacts/characters/mysterious_woman.yaml"
}
```

The graph grows dynamically. The scene now requires this character too.

---

## Example: Software Project

### Goal

> "Add a user settings feature with dark mode toggle"

### Artifact Discovery

```json
[
  {
    "id": "SettingsProtocol",
    "domain_type": "protocol",
    "description": "Protocol for user settings operations",
    "contract": "Protocol with methods: get_settings(user_id) -> Settings, update_setting(user_id, key, value) -> Settings",
    "requires": [],
    "produces_file": "src/protocols/settings.py"
  },
  {
    "id": "SettingsSchema",
    "domain_type": "schema",
    "description": "Pydantic model for settings data",
    "contract": "class Settings(BaseModel): theme: Literal['light', 'dark'] = 'light', notifications: bool = True",
    "requires": [],
    "produces_file": "src/schemas/settings.py"
  },
  {
    "id": "SettingsService",
    "domain_type": "service",
    "description": "Service implementing settings storage and retrieval",
    "contract": "Class implementing SettingsProtocol with database persistence",
    "requires": ["SettingsProtocol", "SettingsSchema"],
    "produces_file": "src/services/settings.py"
  },
  {
    "id": "SettingsRoutes",
    "domain_type": "routes",
    "description": "REST endpoints for settings",
    "contract": "GET /settings, PATCH /settings with theme validation",
    "requires": ["SettingsService", "SettingsSchema"],
    "produces_file": "src/routes/settings.py"
  },
  {
    "id": "DarkModeToggle",
    "domain_type": "component",
    "description": "React component for theme switching",
    "contract": "Toggle component that calls PATCH /settings on change, persists to localStorage",
    "requires": ["SettingsRoutes"],
    "produces_file": "src/components/DarkModeToggle.tsx"
  }
]
```

### Execution Graph

```
SettingsProtocol ──┬──→ SettingsService ──┬──→ SettingsRoutes ──→ DarkModeToggle
                   │                      │
SettingsSchema ────┴──────────────────────┘
```

All protocols/schemas (leaves) execute in parallel, then services, then routes, then components.

---

## Implementation Plan

### Phase 1: Artifact Model (Week 1)

| Task | File | Deliverable |
|------|------|-------------|
| ArtifactSpec dataclass | `sunwell/naaru/artifacts.py` | Core artifact model |
| Artifact graph builder | `sunwell/naaru/artifacts.py` | Dependency graph construction |
| Graph resolution | `sunwell/naaru/artifacts.py` | Topological sort, cycle detection |
| Artifact → Task conversion | `sunwell/naaru/artifacts.py` | RFC-034 compatibility layer |

**Exit criteria**: Can define artifacts, build graph, resolve execution order

### Phase 2: Discovery Engine (Week 2)

| Task | File | Deliverable |
|------|------|-------------|
| Initial discovery prompt | `sunwell/naaru/planners/artifact.py` | Goal → artifacts |
| Schema-aware discovery | `sunwell/naaru/planners/artifact.py` | RFC-035 integration |
| Dynamic discovery | `sunwell/naaru/planners/artifact.py` | Mid-execution discovery |
| Discovery triggers | `sunwell/naaru/planners/artifact.py` | When to check for new artifacts |

**Exit criteria**: Can discover artifacts from fuzzy goals, with schema awareness

### Phase 3: Execution Engine (Week 3)

| Task | File | Deliverable |
|------|------|-------------|
| Parallel artifact executor | `sunwell/naaru/executor.py` | Dependency-driven execution |
| Dynamic graph expansion | `sunwell/naaru/executor.py` | Graph grows during execution |
| Verification integration | `sunwell/naaru/executor.py` | Spec satisfaction checks |
| Error handling | `sunwell/naaru/executor.py` | Failed artifact recovery |

**Exit criteria**: Full execution with parallelism and dynamic discovery

### Phase 4: Integration & Testing (Week 4)

| Task | File | Deliverable |
|------|------|-------------|
| Planning strategy enum | `sunwell/naaru/planners/protocol.py` | Add ARTIFACT_FIRST |
| CLI integration | `sunwell/cli/run.py` | `--strategy artifact_first` |
| Integration tests | `tests/integration/` | Fiction + software examples |
| Documentation | `docs/` | User guide for artifact-first planning |

**Exit criteria**: End-to-end workflow, user-facing feature complete

---

## Design Decisions

### Decision 1: Graph Representation

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: Dict[id, ArtifactSpec]** | Simple mapping | Easy to iterate, extend | Manual dependency validation |
| **B: NetworkX graph** | Full graph library | Algorithms included | Heavy dependency |
| **C: Custom DAG class** | Purpose-built | Optimized for our needs | More code to maintain |

**Recommendation**: **Option A** with custom resolution functions. Keep it simple, add NetworkX later if needed.

### Decision 2: Discovery Timing

| Option | When to Discover | Pros | Cons |
|--------|-----------------|------|------|
| **A: All upfront** | Before any execution | Complete graph known | May miss runtime discoveries |
| **B: After each artifact** | Post-creation | Catches emergent needs | Slower, more LLM calls |
| **C: Hybrid** | Upfront + on error/expansion | Balanced | Implementation complexity |

**Recommendation**: **Option C (Hybrid)** — Initial discovery upfront, dynamic discovery on errors or explicit expansion triggers.

### Decision 3: Verification Strategy

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: Always verify** | Check every artifact | High confidence | Slow |
| **B: Never verify** | Trust creation | Fast | May have broken artifacts |
| **C: Configurable** | User chooses | Flexible | Decision burden |
| **D: Risk-based** | Verify contracts/interfaces, skip implementations | Balanced | Heuristic accuracy |

**Recommendation**: **Option D (Risk-based)** — Verify contracts (they're the foundation), sample-verify implementations.

### Decision 4: Cycle Handling

| Option | Behavior | Pros | Cons |
|--------|----------|------|------|
| **A: Fail immediately** | Error on cycle detection | Clear failure | No recovery |
| **B: Merge cycle** | Combine cyclic artifacts | May work for some cases | Semantically unclear |
| **C: Ask LLM** | "How do we break this cycle?" | Intelligent resolution | Non-deterministic |

**Recommendation**: **Option A (Fail immediately)** with clear error message. Cycles indicate a discovery problem; LLM should re-discover.

### Decision 5: Operational Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| **Max artifacts per discovery** | 50 | Prevents runaway graphs; user must confirm to exceed |
| **Max dynamic discovery rounds** | 5 | Prevents infinite expansion; converges or fails |
| **Max graph depth** | 10 | Catches pathological linear chains |
| **Discovery timeout** | 60s | Single LLM call limit |
| **Total execution timeout** | 30min | Full graph execution limit |

```python
@dataclass(frozen=True, slots=True)
class ArtifactLimits:
    """Operational limits for artifact-first planning."""
    
    max_artifacts: int = 50
    """Maximum artifacts per discovery. Exceeding requires --force."""
    
    max_discovery_rounds: int = 5
    """Maximum dynamic discovery iterations before forced stop."""
    
    max_depth: int = 10
    """Maximum dependency chain depth. Deeper suggests poor decomposition."""
    
    discovery_timeout_seconds: float = 60.0
    """Timeout for a single discovery LLM call."""
    
    execution_timeout_seconds: float = 1800.0
    """Timeout for full graph execution (30 minutes)."""
```

**Recommendation**: Start conservative, allow user override with `--force` or config.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Discovery misses artifacts** | Medium | High | Allow manual artifact addition; dynamic discovery catches misses |
| **Too many LLM calls** | Medium | Medium | Batch discovery, cache results, rate limit |
| **Graph explosion** | Low | High | Limit max artifacts per discovery, warn user |
| **Cycles from discovery** | Medium | Medium | Validate graph after each discovery; clear error |
| **Verification too slow** | Medium | Low | Risk-based verification, async execution |
| **Spec ambiguity** | High | Medium | Structured contract format, examples in prompt |

---

## Success Criteria

### Quantitative

- [ ] **>50% parallelization** on multi-artifact goals (vs sequential baseline)
- [ ] **<5% cycle rate** in discovery (cycles should be rare)
- [ ] **>90% spec satisfaction** on first creation attempt
- [ ] **<3 dynamic discovery rounds** for typical goals (converges quickly)

### Qualitative

- [ ] Fuzzy goals ("make it better") produce meaningful artifact graphs
- [ ] Creative domains (fiction, research) work naturally
- [ ] Error messages clearly explain dependency issues
- [ ] Users understand the artifact graph visualization
- [ ] Dynamic discovery feels like "the system understood what I meant"

---

## Emergent Benefits

The artifact-first model produces benefits that **fall out of the structure** — you don't design them in, they emerge from modeling the problem correctly.

### Structural Parallelism

Procedural planning hides parallelism. You have to explicitly mark steps as parallelizable.

Artifact planning reveals parallelism. It's the natural consequence of "no dependencies = can start now."

```
Discovery identifies:
    A (requires: [])
    B (requires: [])  
    C (requires: [])
    D (requires: [A])
    E (requires: [B, C])
    F (requires: [D, E])

The graph:
    A ───→ D ───┐
    B ───┐      │
         ├──→ E ┴──→ F
    C ───┘

Execution:
    Wave 1: [A, B, C]  ← ALL leaves, parallel, automatic
    Wave 2: [D, E]     ← both ready after wave 1
    Wave 3: [F]        ← convergence
```

**You don't ask for parallelism. It falls out of the dependency structure.**

For a project with 16 artifacts in a balanced tree:
- Procedural: 16 sequential LLM calls
- Artifact: 4 waves (log₂(16)), each wave parallel
- **4x speedup** just from structure

Real projects have wide graphs. 8 protocols + 8 implementations:
- Procedural: 16 steps (LLM serializes even independent work)
- Artifact: 2 waves of 8 parallel calls each
- **8x speedup** per wave

The parallelism isn't a feature. It's what happens when you model dependencies explicitly.

### Adaptive Model Selection

Leaves have no dependencies. That means:
- No context to understand
- No integration to handle
- Just "create this thing to this spec"

**The artifact structure tells you which tasks are simple.**

```
Leaves (no context needed):
    UserProtocol     → "Define protocol with id, email, password_hash"
    AuthInterface    → "Define authenticate(), generate_token()"
    ConfigSchema     → "Define config with database_url, secret_key"
    
    Simple. Small model handles these.

Convergence (needs context):
    App → "Wire UserModel, AuthService, Routes, configure middleware..."
    
    Complex. Needs the big model.
```

Model routing from structure:

```python
def select_model(artifact: ArtifactSpec, graph: ArtifactGraph) -> str:
    """Route to appropriate model based on artifact complexity."""
    
    depth = graph.depth(artifact.id)  # 0 = leaf
    fan_in = len(artifact.requires)   # How many dependencies
    
    if depth == 0:
        return "small"      # Leaves: simple, no context
    elif fan_in <= 2:
        return "medium"     # Shallow deps: moderate complexity
    else:
        return "large"      # Convergence: needs full context
```

| Depth | Artifact Type | Model | Rationale |
|-------|--------------|-------|-----------|
| 0 (leaf) | Contracts, schemas, configs | Small/fast | No context, simple specs |
| 1-2 | Implementations | Medium | Reference contracts |
| 3+ | Integration, convergence | Large | Full context needed |

**The compound effect:**

```
16-artifact project:

Procedural:
    16 steps × large model = 16 expensive calls (sequential)

Artifact-first:
    Wave 1: 8 leaves × small model (parallel)   = 1 cheap batch
    Wave 2: 4 middle × medium model (parallel)  = 1 moderate batch  
    Wave 3: 2 middle × medium model (parallel)  = 1 moderate batch
    Wave 4: 2 convergence × large model         = 1 expensive batch
```

Result: **Faster AND cheaper AND parallel.** Most work uses cheap models. Expensive models only where needed.

### Isolated Failure Domains

In procedural planning, an error mid-sequence poisons everything after:

```
Procedural:
    Step 1 → Step 2 → Step 3 (error!) → Step 4 → Step 5
                           ↑
                Everything after is poisoned
```

In artifact planning, errors are isolated to their dependency subgraph:

```
Artifact:
    UserProtocol ─┬─→ UserModel (error!)
                  │
    AuthInterface ┴─→ AuthService ✓    ← Independent branch succeeds
```

Failed artifacts don't contaminate unrelated work. Recovery is surgical: recreate the failed artifact, its dependencies are explicit.

---

## Philosophical Notes

### Why This Matters

Most AI agents think like junior developers: "What do I do first? Then what?"

Expert developers think differently: "What needs to exist? How do the pieces fit together?"

RFC-036 encodes expert thinking into the planning model. The system doesn't follow steps; it **builds toward a structure**.

### The Inversion

```
Procedural:   Goal → Steps → Execute Steps → Done
Artifact:     Goal → Artifacts → Dependencies → Execute → Done
                         ↑
                    The key insight
```

The artifacts ARE the plan. The execution order emerges from their relationships.

### Why AI Enables This

Pre-AI: You had to know all artifacts upfront (impractical for fuzzy goals)
With AI: The system discovers artifacts dynamically (viable for any domain)

This is why artifact-first planning is a **new paradigm** — it wasn't possible before LLMs.

### Alignment with Reality

The universe doesn't decompose goals into steps. Complexity emerges bottom-up:

```
[quarks] [electrons] [forces]     ← primitives
         ↘    ↓    ↙
          [atoms]                 ← emergence
             ↓
        [molecules]               ← emergence  
             ↓
          [cells]                 ← emergence
             ↓
           [life]                 ← convergence
```

There's no cosmic planner saying "Step 1: Create carbon. Step 2: Add water." There are **building blocks** and **combination rules**, and complexity **emerges upward**.

Artifact-first planning mirrors this:
- **Artifacts are building blocks** — they exist or they don't
- **Dependencies are combination rules** — A requires B to exist
- **The goal emerges** — it's what you get when artifacts combine

This is why artifact-first planning feels natural. It's aligned with how complex systems actually form — in evolution, in markets, in ecosystems, in cities. Procedural planning imposes a designer's order. Artifact planning lets structure emerge.

```
Procedural agent:     "Here's my plan. Reality, comply."
Artifact agent:       "Here's what must exist. Let structure emerge."
```

---

## References

### Code References

| Component | Location | Purpose |
|-----------|----------|---------|
| Task dataclass | `naaru/types.py:148-289` | RFC-034 task model (for conversion) |
| PlanningStrategy | `naaru/planners/protocol.py` | Strategy enum (add ARTIFACT_FIRST) |
| AgentPlanner | `naaru/planners/agent.py` | Existing planner (coexistence) |
| ProjectSchema | `project/schema.py` | RFC-035 schema (for discovery) |
| Analysis utilities | `naaru/analysis.py` | Graph visualization (reuse) |

### Related RFCs

- **RFC-034**: Contract-Aware Parallel Task Planning (execution infrastructure)
- **RFC-035**: Domain-Agnostic Project Framework (schemas, validators)

### External Inspiration

- **Build systems**: Make, Bazel, Nix (declarative dependency resolution)
- **Dataflow programming**: Where computation flows from sources to sinks
- **Constraint satisfaction**: Declaring what must be true, not how to achieve it

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-19 | Initial draft |
| 2026-01-19 | Added: RFC-035 dependency clarification (optional, not required) |
| 2026-01-19 | Added: Strategy interaction section (ARTIFACT_FIRST + RESOURCE_AWARE) |
| 2026-01-19 | Added: Failure Recovery section with failure modes and recovery protocol |
| 2026-01-19 | Added: Decision 5 - Operational limits (max artifacts, timeouts, depth) |