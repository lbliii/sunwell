# RFC-044: Puzzle-First Planning — Context-Aware Architecture Discovery

**Status**: Revised (Context-First)  
**Created**: 2026-01-19  
**Revised**: 2026-01-19  
**Authors**: Sunwell Team  
**Depends on**: RFC-036 (Artifact-First Planning), RFC-038 (Harmonic Planning), **RFC-045 (Project Intelligence)**  
**Related**: RFC-039 (Expertise-Aware Planning)

---

## Summary

Puzzle-First Planning transforms sparse specifications into well-architected plans by treating every project as a puzzle with three distinct regions: a **center** (unique value proposition), **edges** (commodity requirements), and **middle** (connecting domain logic).

**Key change (Context-First revision)**: This RFC now **depends on RFC-045 (Project Intelligence)** for context-aware defaults instead of static priors:

| Before (Static) | After (Context-First) |
|-----------------|----------------------|
| Invent center via LLM | Ask user, or reuse past decision |
| Hardcoded priors | Codebase patterns + decision memory |
| Always add protocols | Match existing abstraction level |
| Works standalone | Consumer of Project Intelligence |

**Core insight**: The DAG isn't just a build order — it's a **value gradient** where leaves are swappable commodities and the root is the unique reason this project exists.

**Architectural principle**: Defaults come from **Project Intelligence** (RFC-045), not hardcoded registries. The codebase already has patterns, past decisions, and user preferences — the planner extracts and applies them.

---

## Motivation

### The Specification Gap Problem

A detailed RFC produces better plans than a sparse goal — but the *desired outcome* is often the same:

```
Sparse:   "Build a REST API with users"
Detailed: "Build a REST API with users, JWT auth, SQLite database,
           structured error responses, unit tests for models,
           integration tests for routes, using Flask..."
```

The detailed version just makes explicit what any senior engineer would assume. **Why should the user have to write that?**

### Current Behavior

The `ArtifactPlanner` (RFC-036) asks the LLM "what must exist?" — forcing the LLM to invent all decisions:

- Auth mechanism? (invents one)
- Database? (picks arbitrarily)
- Error handling? (maybe)
- Tests? (maybe)
- Framework? (picks one)

Results vary based on LLM mood, not architectural wisdom.

### Desired Behavior

The planner should:

1. **Clarify the center** — Ask user what's unique, or accept "standard implementation"
2. **Mine context for defaults** — Use codebase patterns, past decisions, learned preferences (RFC-045)
3. **Match abstraction level** — If project uses protocols, continue; if simple, don't over-engineer
4. **Discover the middle** — What connects generic to unique?

**Context-first principle**: Project Intelligence (RFC-045) provides the context; PuzzlePlanner applies the puzzle model to it.

---

## Design Options Considered

### Option A: Project Intelligence Integration (Recommended)

Use RFC-045's codebase graph, decision memory, and pattern learning to derive context-aware defaults. The puzzle model is an **architecture layer** on top of intelligence.

**Pros**:
- Context-aware (uses what's already in the codebase)
- Learns from user behavior (pattern learning)
- Remembers past decisions (decision memory)
- Warns about past failures (failure memory)
- Gets better over time

**Cons**:
- Requires RFC-045 to be implemented first
- More complex dependency chain

### Option B: Static Prior Registry (Original RFC-044)

Use a hardcoded registry of `ArchitecturePrior` objects keyed by intent.

**Pros**:
- Works standalone (no dependencies)
- Predictable, reproducible
- Fast (no lookups)

**Cons**:
- Ignores project context
- Same defaults for all projects
- Doesn't learn or improve
- "Sane defaults" may not match user's domain

### Option C: LLM-Based Everything

Let the LLM invent center, choose defaults, decide abstractions.

**Pros**:
- Context-aware (reads current code)
- No infrastructure needed

**Cons**:
- Non-deterministic ("LLM mood" problem)
- Expensive (multiple LLM calls)
- No memory across sessions
- Can't learn from feedback

**Decision**: Option A. RFC-045 provides the intelligence; RFC-044 provides the puzzle model. Together they produce context-aware, well-architected plans that improve over time.

**Fallback**: If RFC-045 is not available (new project, no intelligence yet), fall back to Option B (static priors) with user dialogue for center.

---

## Design

### The Puzzle Model

Every project is a puzzle with three regions:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EDGES (Leaves)                              │
│                    Commodity, swappable, protocols                  │
│     ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐               │
│     │ DB   │  │ Auth │  │ HTTP │  │ Tests│  │ Logs │               │
│     │Proto │  │Proto │  │      │  │      │  │      │               │
│     └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘               │
│        │         │         │         │         │                    │
│        └────┬────┴────┬────┴────┬────┴────┬────┘                    │
│             │         │         │         │                         │
│             ▼         ▼         ▼         ▼                         │
│     ┌─────────────────────────────────────────────┐                 │
│     │              MIDDLE (Interior)              │                 │
│     │         Domain logic, connections           │                 │
│     │   UserModel, PostService, VoteLogic, ...    │                 │
│     └─────────────────────┬───────────────────────┘                 │
│                           │                                         │
│                           ▼                                         │
│               ┌───────────────────────┐                             │
│               │     CENTER (Root)     │                             │
│               │   Unique value prop   │                             │
│               │                       │                             │
│               │  "reputation-based    │                             │
│               │   content moderation" │                             │
│               └───────────────────────┘                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### The Value Gradient

The DAG represents a gradient from generic to unique:

| Layer | DAG Position | Characteristics | Example |
|-------|--------------|-----------------|---------|
| **Edges** | Leaves | Swappable, commodity, protocol-wrapped | DatabaseProtocol, AuthProvider |
| **Middle** | Interior | Domain-specific, connects layers | UserModel, PostService |
| **Center** | Root | Unique value, why this exists | "Trust-based moderation system" |

**Key principle**: Everything flows toward the center. The root artifact IS the elevator pitch.

---

## Components

### 1. Center Discovery (Context-First)

The center is what makes this project worth creating. **Key change**: We don't invent it — we ask the user or reuse a past decision.

```python
@dataclass(frozen=True, slots=True)
class ProjectCenter:
    """The unique value proposition of a project."""
    
    description: str
    """One sentence: why this project is interesting."""
    
    differentiator: str
    """What makes this different from generic alternatives."""
    
    pitch: str
    """Elevator pitch derived from the center."""
    
    source: CenterSource
    """How this center was determined."""


class CenterSource(Enum):
    """How the center was determined."""
    
    USER_EXPLICIT = "user_explicit"      # User specified in goal
    USER_DIALOGUE = "user_dialogue"      # User chose from options
    PAST_DECISION = "past_decision"      # From decision memory (RFC-045)
    STANDARD = "standard"                # User accepted "no unique angle"
    INFERRED = "inferred"                # LLM inferred (fallback only)
```

**Context-First Discovery Process**:

```python
async def discover_center(
    goal: str,
    intelligence: ProjectIntelligence,  # RFC-045
    interactive: bool = True,
) -> ProjectCenter:
    """Determine the center through context, not invention."""
    
    # Step 1: Check if goal explicitly specifies what's unique
    if has_explicit_center(goal):
        return extract_center_from_goal(goal, source=CenterSource.USER_EXPLICIT)
    
    # Step 2: Check past decisions for this type of project
    past_decisions = await intelligence.decisions.find_relevant(
        query=goal,
        category="project_center",
    )
    if past_decisions:
        decision = past_decisions[0]
        return ProjectCenter(
            description=decision.choice,
            differentiator=decision.rationale,
            pitch=f"Based on past decision: {decision.choice}",
            source=CenterSource.PAST_DECISION,
        )
    
    # Step 3: Interactive mode — ask user
    if interactive:
        return await _ask_user_for_center(goal, intelligence)
    
    # Step 4: Non-interactive fallback — standard implementation
    return ProjectCenter(
        description=f"Standard {detect_intent(goal)} implementation",
        differentiator="No unique angle specified",
        pitch=goal,
        source=CenterSource.STANDARD,
    )


async def _ask_user_for_center(
    goal: str,
    intelligence: ProjectIntelligence,
) -> ProjectCenter:
    """Present options and let user choose."""
    
    # Generate 2-3 options (LLM helps here)
    options = await _generate_center_options(goal, count=3)
    
    print(f"Goal: {goal}\n")
    print("I can approach this a few ways:\n")
    
    for i, opt in enumerate(options, 1):
        print(f"  {i}. **{opt.description}**")
        print(f"     {opt.differentiator}\n")
    
    print(f"  {len(options)+1}. Standard implementation (no unique angle)\n")
    print("  Or describe what makes yours unique:\n")
    
    choice = await get_user_input("> ")
    
    # Parse choice
    if choice.isdigit():
        idx = int(choice) - 1
        if idx < len(options):
            selected = options[idx]
            # Record as decision for future reference
            await intelligence.decisions.record(
                category="project_center",
                question=f"What's unique about: {goal}",
                choice=selected.description,
                rationale=selected.differentiator,
            )
            return ProjectCenter(
                description=selected.description,
                differentiator=selected.differentiator,
                pitch=selected.pitch,
                source=CenterSource.USER_DIALOGUE,
            )
        else:
            return ProjectCenter(
                description=f"Standard {detect_intent(goal)} implementation",
                differentiator="User chose standard implementation",
                pitch=goal,
                source=CenterSource.STANDARD,
            )
    else:
        # User described their own center
        return ProjectCenter(
            description=choice,
            differentiator=f"User-specified: {choice}",
            pitch=choice,
            source=CenterSource.USER_EXPLICIT,
        )
```

**When to Skip Center Discovery**:

```python
def should_skip_center_discovery(goal: str) -> bool:
    """Some goals don't need a unique angle."""
    
    # Specification compliance (RFC implementation, etc.)
    if re.search(r"RFC\s*\d+|implement.*spec|comply with", goal, re.I):
        return True
    
    # Explicit "just build it" requests
    if any(kw in goal.lower() for kw in ["simple", "basic", "standard", "minimal"]):
        return True
    
    return False
```

---

**Legacy: LLM-Based Center Discovery (Fallback Only)**

For non-interactive mode without past decisions, fall back to LLM inference:

```python
async def _infer_center_fallback(
    goal: str,
    model: ModelProtocol,
) -> ProjectCenter:
    """LLM inference fallback — use only when no other option."""
    
    prompt = f"""GOAL: {goal}
INTENT: {intent}

=== CENTER DISCOVERY ===

Every project has commodity parts (auth, DB, tests) and a UNIQUE part.
Find the CENTER — the one thing that makes this interesting.

Questions to ask:
- "If this is a forum, why use it instead of Reddit?"
- "If this is a story, why read it instead of another pirate tale?"
- "If this is an API, what's the clever part?"

BAD centers (too generic):
- "A forum for discussions" (that's just... a forum)
- "A pirate adventure" (that's just... genre)
- "A REST API" (that's just... architecture)

GOOD centers (unique angle):
- "Forum where trust is earned by verified helpful answers"
- "Pirate captain who's secretly afraid of water"
- "API that auto-generates SDKs from usage patterns"

If the goal doesn't specify what's unique, INVENT something interesting.
The center should make someone go "oh, that's cool."

Output JSON:
{{
  "description": "One sentence describing the unique value",
  "differentiator": "What makes this different from alternatives",
  "pitch": "Elevator pitch (2-3 sentences)"
}}"""

    result = await model.generate(prompt)
    # ... parse and return ProjectCenter
```

**Examples**:

| Goal | Discovered Center |
|------|-------------------|
| "Build a forum app" | "Forum where reputation unlocks moderation powers" |
| "Write a pirate story" | "A pirate captain who can't swim must cross an ocean" |
| "Create a TODO app" | "TODO app that learns your procrastination patterns" |
| "Build a REST API" | "API with automatic client SDK generation from usage" |

### 2. Edge Filling (Context-First with RFC-045)

Edges are commodity requirements — things ANY project of this type needs.

**Key architectural decision**: Defaults come from **Project Intelligence** (RFC-045) in priority order:

```
1. Codebase Patterns  — What does this project already use?
2. Past Decisions     — What did we decide before for similar needs?
3. Learned Patterns   — What style does the user prefer?
4. Lens Heuristics    — What does the domain lens recommend?
5. Fallback Priors    — Reasonable defaults (last resort)
```

**Context-First Edge Resolution**:

```python
async def resolve_edges(
    gaps: GapAnalysis,
    intelligence: ProjectIntelligence,  # RFC-045
    lens: Lens | None = None,
) -> list[ResolvedEdge]:
    """Fill gaps using context-first priority."""
    
    resolved = []
    
    for gap in gaps.unspecified:
        # 1. Check codebase patterns first
        pattern = await intelligence.codebase.get_pattern(gap)
        if pattern:
            resolved.append(ResolvedEdge(
                name=gap,
                value=pattern.value,
                source=EdgeSource.CODEBASE_PATTERN,
                rationale=f"Already using {pattern.value} in {pattern.location}",
                requires_protocol=pattern.uses_abstraction,
            ))
            continue
        
        # 2. Check past decisions
        decision = await intelligence.decisions.find_by_category(gap)
        if decision:
            resolved.append(ResolvedEdge(
                name=gap,
                value=decision.choice,
                source=EdgeSource.PAST_DECISION,
                rationale=decision.rationale,
                requires_protocol=decision.metadata.get("protocol", False),
            ))
            continue
        
        # 3. Check learned patterns
        preference = intelligence.patterns.get_preference(gap)
        if preference and preference.confidence > 0.7:
            resolved.append(ResolvedEdge(
                name=gap,
                value=preference.value,
                source=EdgeSource.LEARNED_PATTERN,
                rationale=f"Learned from {preference.evidence_count} past interactions",
                requires_protocol=False,  # Match existing style
            ))
            continue
        
        # 4. Check lens heuristics
        if lens:
            lens_prior = extract_prior_from_lens(lens, gap)
            if lens_prior:
                resolved.append(ResolvedEdge(
                    name=gap,
                    value=lens_prior.value,
                    source=EdgeSource.LENS_HEURISTIC,
                    rationale=lens_prior.rationale,
                    requires_protocol=lens_prior.implies_protocol,
                ))
                continue
        
        # 5. Fallback to static priors
        fallback = FALLBACK_PRIORS.get(gap)
        if fallback:
            resolved.append(ResolvedEdge(
                name=gap,
                value=fallback.default_value,
                source=EdgeSource.FALLBACK_PRIOR,
                rationale=fallback.rationale,
                requires_protocol=fallback.volatility == Volatility.HIGH,
            ))
    
    return resolved


class EdgeSource(Enum):
    """Where an edge default came from."""
    
    CODEBASE_PATTERN = "codebase"    # Already in the project
    PAST_DECISION = "decision"       # From decision memory
    LEARNED_PATTERN = "learned"      # From pattern learning
    LENS_HEURISTIC = "lens"          # From active lens
    FALLBACK_PRIOR = "fallback"      # Static fallback
```

**Why Context-First is Better**:

| Static Priors | Context-First (RFC-045) |
|---------------|------------------------|
| Same for all projects | Adapts to THIS project |
| Ignores existing code | Uses what's already there |
| Doesn't learn | Gets better over time |
| May conflict with past decisions | Honors past decisions |
| Generic style | Matches user's style |

---

**Fallback Priors (Last Resort)**

When RFC-045 has no context (new project, no intelligence yet), fall back to reasonable defaults. These are **reference examples** — the goal is to use them rarely:

```python
@dataclass(frozen=True, slots=True)
class ArchitecturePrior:
    """A default decision for unspecified requirements."""
    
    name: str
    """What decision this addresses (e.g., 'database')."""
    
    applies_to: frozenset[str]
    """Intents this prior applies to (e.g., {'api', 'webapp'})."""
    
    default_value: str
    """The sane default choice."""
    
    rationale: str
    """Why this is the sane default."""
    
    volatility: Volatility
    """How likely this decision is to change."""
    
    requires_protocol: bool
    """Whether to wrap in protocol for swappability."""
    
    protocol_name: str | None
    """Name of protocol if requires_protocol is True."""
    
    alternatives: tuple[str, ...]
    """Known alternatives that might swap in later."""


class Volatility(Enum):
    """How likely a decision is to change."""
    
    HIGH = "high"      # Almost always changes (DB, auth provider)
    MEDIUM = "medium"  # Sometimes changes (logging, caching)
    LOW = "low"        # Rarely changes (framework, language)
```

**Default priors by intent**:

> **Design principle for defaults**: Choose the option that minimizes initial friction while maximizing future flexibility. Defaults should be "obviously correct for prototyping" with clear upgrade paths.

```yaml
API:
  database:
    default: SQLite
    rationale: |
      Zero config, file-based, clear upgrade path to Postgres.
      Evidence: SQLite handles 100K+ reads/sec, sufficient for most prototypes.
      Django, Rails both default to SQLite for development.
      Upgrade path: SQLAlchemy/Peewee abstractions make Postgres swap trivial.
    volatility: HIGH
    protocol: DatabaseProtocol
    alternatives: [Postgres, MySQL, MongoDB]
    upgrade_trigger: ">1 concurrent writer, >10GB data, need JSONB/full-text"
    
  auth:
    default: JWT + bcrypt
    rationale: |
      Stateless (no session table), no Redis dependency, well-understood.
      Evidence: PyJWT is most-downloaded Python auth library (50M+/month).
      bcrypt cost factor 12 = ~250ms hash time, resistant to GPU attacks.
      Upgrade path: AuthProvider protocol allows OAuth/SAML swap.
    volatility: MEDIUM
    protocol: AuthProvider
    alternatives: [OAuth, API keys, SAML]
    upgrade_trigger: "Enterprise SSO requirement, third-party integrations"
    
  error_handling:
    default: Structured JSON errors with HTTP codes
    rationale: |
      Machine-readable, debuggable, follows RFC 7807 (Problem Details).
      Evidence: OpenAPI/Swagger expects structured errors for SDK generation.
      Format: {"error": str, "code": str, "details": dict}
    volatility: LOW
    protocol: null
    
  tests:
    default: pytest with unit (models) + integration (routes)
    rationale: |
      pytest is Python's dominant test framework (90%+ market share).
      Unit tests for models: fast, isolated, catch logic bugs.
      Integration tests for routes: catch wiring bugs, ~10x slower.
      Evidence: Google Testing Blog recommends 70/20/10 unit/integration/e2e.
    volatility: LOW
    protocol: null
    
  framework:
    default: Flask
    rationale: |
      Minimal deps (~5), well-documented, easy to understand.
      Evidence: Flask's single-file hello-world is 5 lines.
      FastAPI is faster but adds Pydantic/Starlette complexity.
      Upgrade path: WSGI→ASGI migration is well-documented.
    volatility: LOW
    protocol: null
    upgrade_trigger: "Need async, automatic OpenAPI, 10K+ req/sec"

CLI:
  arg_parsing:
    default: argparse (stdlib)
    rationale: |
      Zero dependencies, ships with Python, sufficient for most CLIs.
      Evidence: argparse is used by pip, pytest, black, and most stdlib tools.
      click/typer are nicer but add deps; argparse is always available.
    volatility: LOW
    protocol: null
    upgrade_trigger: "Complex subcommands, need auto-completion"
    
  config:
    default: Environment variables
    rationale: |
      12-factor app compliant, composable, no file parsing.
      Evidence: Docker, Kubernetes, Heroku all use env vars as primary config.
      os.environ is always available; no YAML/TOML parser needed.
    volatility: MEDIUM
    protocol: ConfigProvider
    alternatives: [YAML file, TOML, JSON]
    upgrade_trigger: "Complex nested config, need validation, multiple environments"

Story:
  structure:
    default: Three-act
    rationale: |
      Proven structure with 2000+ years of evidence (Aristotle's Poetics).
      Evidence: Save the Cat, Story Grid, and most screenplay guides use 3-act.
      Reader expectations are calibrated to 25/50/25 act proportions.
    volatility: LOW
    protocol: null
    
  pov:
    default: Third person limited
    rationale: |
      Balances intimacy (one character's thoughts) with flexibility.
      Evidence: Most bestselling fiction uses 3rd limited (per Publisher's Weekly analysis).
      Easier to write than omniscient, more flexible than first person.
    volatility: MEDIUM
    protocol: null  # But write POV-agnostic where possible
    upgrade_trigger: "Multiple POV characters, unreliable narrator effect"
    
  conflict:
    default: External + Internal
    rationale: |
      External conflict drives plot; internal conflict drives character arc.
      Evidence: Robert McKee's "Story" argues dual conflict is required for depth.
      Pure external = action movie; pure internal = literary fiction (smaller audience).
    volatility: LOW
    protocol: null

Game:
  loop:
    default: Fixed timestep
    rationale: |
      Deterministic physics, replay-friendly, easier debugging.
      Evidence: Gaffer on Games' "Fix Your Timestep" is industry standard.
      Fixed step = reproducible behavior across hardware.
    volatility: LOW
    protocol: null
    upgrade_trigger: "Variable physics (soft-body), need frame interpolation"
    
  input:
    default: Event-driven with buffering
    rationale: |
      Responsive feel, frame-independent, handles input lag gracefully.
      Evidence: SDL, GLFW, and most game frameworks use event queues.
      Buffering prevents dropped inputs during frame spikes.
    volatility: MEDIUM
    protocol: InputProvider
    alternatives: [Polling, async streams]
    upgrade_trigger: "Fighting game (frame-perfect input), complex gesture recognition"
    
  state:
    default: Explicit state machine
    rationale: |
      Debuggable (print current state), serializable (save/load), testable.
      Evidence: Unity's Animator, Unreal's Behavior Trees are state machines.
      Implicit state (scattered booleans) is the #1 source of game bugs.
    volatility: LOW
    protocol: null
    upgrade_trigger: "Need hierarchical states, complex AI behavior"
```

### 3. Volatility-Aware Swappability

High-volatility decisions get **protocol wrappers** — designed-in seams for future changes.

```python
def should_wrap_in_protocol(prior: ArchitecturePrior) -> bool:
    """Determine if a decision needs a protocol wrapper."""
    return prior.volatility == Volatility.HIGH or prior.requires_protocol


def generate_protocol_artifact(prior: ArchitecturePrior) -> ArtifactSpec:
    """Generate a protocol artifact for a high-volatility decision."""
    return ArtifactSpec(
        id=prior.protocol_name,
        description=f"Interface for {prior.name} operations",
        contract=f"Protocol defining {prior.name} capabilities",
        requires=frozenset(),  # Protocols are always leaves
        produces_file=f"src/protocols/{prior.name.lower()}.py",
        domain_type="protocol",
        metadata={"volatility": prior.volatility.value},
    )


def generate_implementation_artifact(
    prior: ArchitecturePrior,
) -> ArtifactSpec:
    """Generate implementation artifact that depends on its protocol."""
    impl_name = f"{prior.default_value.replace(' ', '')}Impl"
    
    requires = frozenset()
    if prior.requires_protocol and prior.protocol_name:
        requires = frozenset({prior.protocol_name})
    
    return ArtifactSpec(
        id=impl_name,
        description=f"{prior.default_value} implementation of {prior.name}",
        contract=f"Implements {prior.protocol_name or prior.name}",
        requires=requires,
        produces_file=f"src/impl/{prior.name.lower()}.py",
        domain_type="implementation",
        metadata={
            "swappable_with": list(prior.alternatives),
            "default_for": prior.name,
        },
    )
```

**Result**: High-volatility decisions become TWO artifacts:

```
DatabaseProtocol (leaf, no deps)
       ↑
SQLiteDatabase (depends on protocol)
```

Future swap: Add `PostgresDatabase` that also depends on `DatabaseProtocol` — zero changes to business logic.

### 4. Gap Detection

Detect what's unspecified in the goal:

```python
@dataclass(frozen=True, slots=True)
class GapAnalysis:
    """Analysis of what's specified vs. unspecified in a goal."""
    
    intent: str
    """Detected intent (api, cli, story, game, etc.)."""
    
    specified: frozenset[str]
    """Decisions explicitly mentioned in the goal."""
    
    unspecified: frozenset[str]
    """Decisions that need defaults."""
    
    center_specified: bool
    """Whether the unique value prop is explicit."""


async def analyze_gaps(
    goal: str,
    model: ModelProtocol,
) -> GapAnalysis:
    """Detect what's specified and what needs defaults."""
    
    prompt = f"""GOAL: {goal}

Analyze what's SPECIFIED vs. UNSPECIFIED:

SPECIFIED = explicitly mentioned in the goal
UNSPECIFIED = needed but not mentioned

Categories to check:
- Intent (what type of project?)
- Center (what's unique about it?)
- Database (if applicable)
- Authentication (if applicable)
- Error handling
- Tests
- Framework/structure

Output JSON:
{{
  "intent": "api|cli|story|game|webapp|other",
  "specified": ["items", "explicitly", "mentioned"],
  "unspecified": ["items", "not", "mentioned"],
  "center_specified": true/false
}}"""

    result = await model.generate(prompt)
    # ... parse and return GapAnalysis
```

### 5. The Puzzle Planner (Context-First)

Orchestrates center discovery, gap filling, and artifact generation **using Project Intelligence (RFC-045)**:

```python
@dataclass
class PuzzlePlanner:
    """Plans by treating projects as puzzles with center, edges, and middle.
    
    Context-First revision: Uses RFC-045 for intelligent defaults.
    """
    
    model: ModelProtocol
    base_planner: ArtifactPlanner
    
    # RFC-045: Project Intelligence integration
    intelligence: ProjectIntelligence | None = None
    """Project intelligence for context-aware planning."""
    
    # Settings
    interactive: bool = True
    """Whether to ask user for center (vs. inferring)."""
    
    lens: Lens | None = None
    """Active lens for domain-specific heuristics."""
    
    async def plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ArtifactGraph:
        """Plan with context-first puzzle approach."""
        
        # Step 1: Analyze gaps
        gaps = await analyze_gaps(goal, self.model)
        
        # Step 2: Check for similar past failures (RFC-045)
        if self.intelligence:
            failures = await self.intelligence.failures.check_similar(goal)
            if failures:
                await self._warn_about_failures(failures)
        
        # Step 3: Discover center (context-first)
        center = await self._discover_center_contextual(goal, gaps)
        
        # Step 4: Resolve edges (context-first priority)
        edges = await self._resolve_edges_contextual(gaps)
        
        # Step 5: Build enriched goal
        enriched = self._enrich_goal(goal, center, edges)
        
        # Step 6: Discover middle artifacts (domain logic)
        middle_graph = await self.base_planner.discover_graph(enriched, context)
        
        # Step 7: Generate edge artifacts (match abstraction level)
        edge_artifacts = self._generate_edge_artifacts(edges)
        
        # Step 8: Merge into full graph
        full_graph = self._merge_graphs(edge_artifacts, middle_graph)
        
        # Step 9: Ensure center is root
        full_graph = self._ensure_center_is_root(full_graph, center)
        
        # Step 10: Verify shape (value gradient)
        self._verify_shape(full_graph)
        
        # Step 11: Record decisions for future (RFC-045)
        if self.intelligence:
            await self._record_decisions(center, edges)
        
        return full_graph
    
    async def _discover_center_contextual(
        self,
        goal: str,
        gaps: GapAnalysis,
    ) -> ProjectCenter:
        """Context-first center discovery."""
        
        # Skip if goal is spec-compliance
        if should_skip_center_discovery(goal):
            return ProjectCenter(
                description=goal,
                differentiator="Specification compliance",
                pitch=goal,
                source=CenterSource.STANDARD,
            )
        
        # Use RFC-045 intelligence if available
        if self.intelligence:
            return await discover_center(
                goal=goal,
                intelligence=self.intelligence,
                interactive=self.interactive,
            )
        
        # Fallback: ask user or infer
        if self.interactive:
            return await _ask_user_for_center_simple(goal)
        else:
            return await _infer_center_fallback(goal, self.model)
    
    async def _resolve_edges_contextual(
        self,
        gaps: GapAnalysis,
    ) -> list[ResolvedEdge]:
        """Context-first edge resolution."""
        
        if self.intelligence:
            return await resolve_edges(
                gaps=gaps,
                intelligence=self.intelligence,
                lens=self.lens,
            )
        else:
            # Fallback to static priors
            return self._resolve_edges_fallback(gaps)
    
    def _generate_edge_artifacts(
        self,
        edges: list[ResolvedEdge],
    ) -> list[ArtifactSpec]:
        """Generate edge artifacts, matching existing abstraction level."""
        artifacts = []
        
        for edge in edges:
            # Only add protocols if:
            # 1. Edge requires protocol (high volatility), AND
            # 2. Project already uses protocols OR is medium+ complexity
            if edge.requires_protocol and self._should_add_protocol():
                # Add protocol artifact
                artifacts.append(ArtifactSpec(
                    id=f"{edge.name.title()}Protocol",
                    description=f"Interface for {edge.name} operations",
                    contract=f"Protocol defining {edge.name} capabilities",
                    requires=frozenset(),
                    domain_type="protocol",
                    metadata={"source": edge.source.value},
                ))
                
                # Add implementation artifact
                artifacts.append(ArtifactSpec(
                    id=f"{edge.value.replace(' ', '')}Impl",
                    description=f"{edge.value} implementation",
                    contract=f"Implements {edge.name.title()}Protocol",
                    requires=frozenset({f"{edge.name.title()}Protocol"}),
                    domain_type="implementation",
                    metadata={"swappable": True},
                ))
            else:
                # Direct implementation (no protocol overhead)
                artifacts.append(ArtifactSpec(
                    id=f"{edge.name.title()}",
                    description=f"{edge.value} for {edge.name}",
                    contract=edge.rationale,
                    requires=frozenset(),
                    domain_type="implementation",
                ))
        
        return artifacts
    
    def _should_add_protocol(self) -> bool:
        """Determine if project warrants protocol abstractions."""
        if self.intelligence:
            # Match existing abstraction level
            return self.intelligence.codebase.uses_protocols
        # Default: don't over-engineer
        return False
    
    async def _record_decisions(
        self,
        center: ProjectCenter,
        edges: list[ResolvedEdge],
    ) -> None:
        """Record decisions for future reference (RFC-045)."""
        
        # Record center if user-specified
        if center.source in (CenterSource.USER_DIALOGUE, CenterSource.USER_EXPLICIT):
            await self.intelligence.decisions.record(
                category="project_center",
                question="What's unique about this project?",
                choice=center.description,
                rationale=center.differentiator,
            )
        
        # Record edge decisions that came from user or fallback
        for edge in edges:
            if edge.source in (EdgeSource.FALLBACK_PRIOR, EdgeSource.LENS_HEURISTIC):
                await self.intelligence.decisions.record(
                    category=edge.name,
                    question=f"What to use for {edge.name}?",
                    choice=edge.value,
                    rationale=edge.rationale,
                )
```

---

## Examples

### Example 1: Sparse API Goal

**Input**: "Build a forum app"

**Gap Analysis**:
```yaml
intent: api
specified: [forum, app]
unspecified: [database, auth, tests, error_handling, framework, center]
center_specified: false
```

**Center Discovery**:
```yaml
description: "Forum where reputation unlocks moderation powers"
differentiator: "Trust is earned through verified helpful answers, not just activity"
pitch: "A forum where quality contributions unlock real power. Answer questions 
        well, get verified by the community, and earn the ability to moderate."
```

**Enriched Goal**:
```
Build a forum app

=== PROJECT CENTER (unique value) ===
Forum where reputation unlocks moderation powers
Differentiator: Trust is earned through verified helpful answers

=== ARCHITECTURE DECISIONS (sane defaults) ===
- database: SQLite (zero config, upgrade path to Postgres)
- auth: JWT + bcrypt (stateless, no session storage)
- tests: pytest unit + integration (standard, fast)
- error_handling: Structured JSON (machine-readable)
- framework: Flask (minimal, well-documented)

=== SWAPPABILITY SEAMS (high-volatility) ===
- DatabaseProtocol → SQLite (swappable: Postgres, MySQL)
- AuthProvider → JWT (swappable: OAuth, API keys)
```

**Generated DAG**:
```
Wave 1 (Leaves - parallel):
  DatabaseProtocol, AuthProvider, UserProtocol, PostProtocol, ReputationProtocol

Wave 2:
  SQLiteDatabase, JWTAuth, UserModel, PostModel, ReputationEngine

Wave 3:
  UserService, PostService, ModerationService

Wave 4:
  ReputationBasedModeration  ← CENTER (root)

Wave 5:
  App
```

### Example 2: Creative Goal

**Input**: "Write a pirate story"

**Gap Analysis**:
```yaml
intent: story
specified: [pirate]
unspecified: [structure, pov, conflict, characters, setting, center]
center_specified: false
```

**Center Discovery**:
```yaml
description: "A pirate captain who can't swim must cross an ocean"
differentiator: "The captain's secret vulnerability inverts the pirate power fantasy"
pitch: "Captain Blackwood has never told her crew she can't swim. When their 
        ship is damaged and the only hope is a three-day voyage through 
        storm-tossed waters, her greatest enemy isn't the navy — it's the sea."
```

**Enriched Goal**:
```
Write a pirate story

=== PROJECT CENTER (unique value) ===
A pirate captain who can't swim must cross an ocean
Differentiator: The captain's secret vulnerability inverts the power fantasy

=== ARCHITECTURE DECISIONS (sane defaults) ===
- structure: Three-act (proven, reader expectations)
- pov: Third person limited (flexible, intimate)
- conflict: External (navy pursuit) + Internal (fear, trust)
- setting: Ship at sea, port town, destination island

=== NARRATIVE SEAMS (flexibility) ===
- Write scenes that survive POV shifts where possible
- Ending should have multiple valid resolutions planted
- Secondary characters modular (can add/remove)
```

**Generated DAG**:
```
Wave 1 (Leaves - parallel):
  CaptainBlackwood, TheSecret, ShipTheSiren, CrewEnsemble, SettingCaribbean

Wave 2:
  Act1_EstablishSecret, Act1_IncitingIncident

Wave 3:
  Act2_StormSequence, Act2_CrewSuspicion, Act2_NavyPursuit

Wave 4:
  Act3_TruthRevealed, Act3_Climax

Wave 5:
  Resolution_SecretToStrength  ← CENTER (root)
```

---

## Integration with Existing Planners

### With ArtifactPlanner (RFC-036)

`PuzzlePlanner` uses `ArtifactPlanner` as its base for middle-layer discovery:

```python
planner = PuzzlePlanner(
    model=model,
    priors=DEFAULT_PRIORS,
    base_planner=ArtifactPlanner(model=model),
)
```

The base planner receives the enriched goal and handles artifact discovery. PuzzlePlanner adds:
- Center discovery
- Edge generation (protocols + defaults)
- Shape verification

### With HarmonicPlanner (RFC-038)

For maximum quality, combine puzzle-first with harmonic optimization:

```python
planner = PuzzlePlanner(
    model=model,
    priors=DEFAULT_PRIORS,
    base_planner=HarmonicPlanner(
        model=model,
        candidates=5,
        variance=VarianceStrategy.PROMPTING,
    ),
)
```

Harmonic generates multiple candidate middle-layers; puzzle ensures they all have the same center and edges.

### With Lenses (Primary Prior Source)

Lenses are the **primary source** of architecture priors — no hardcoded defaults to merge with:

```python
def extract_priors_from_lens(lens: Lens) -> list[DerivedPrior]:
    """Extract architecture priors from lens heuristics.
    
    The lens is the single source of truth for domain-specific wisdom.
    No hardcoded DEFAULT_PRIORS registry.
    """
    priors = []
    
    for heuristic in lens.heuristics:
        for rule in heuristic.always:
            priors.append(DerivedPrior(
                source=f"lens:{lens.metadata.name}/{heuristic.name}",
                pattern=rule,
                implies_protocol="Protocol" in rule or "injection" in rule.lower(),
                rationale=heuristic.rule,
            ))
    
    return priors
```

**Example**: The `coder.lens` heuristics become architecture guidance:

```yaml
# From coder.lens
heuristics:
  - name: "Type Safety First"
    always:
      - "Use Protocol for structural typing over ABC"
      # → Planner knows: wrap external deps in protocols
      
  - name: "Testing Support"
    always:
      - "Use dependency injection"
      # → Planner knows: services receive dependencies, don't create them
```

**Example**: A `tech-writer.lens` provides documentation-specific guidance:

```yaml
# From tech-writer.lens
framework:
  name: "Diataxis"
  categories: [TUTORIAL, HOW_TO, EXPLANATION, REFERENCE]
  # → Planner knows: structure artifacts by Diataxis type
```

---

## Configuration

### Custom Priors via Lenses

Priors are customized through **lenses**, not separate configuration files:

```yaml
# my-project.lens
lens:
  metadata:
    name: "Enterprise Python API"
    extends: coder  # Inherit from coder.lens
    
  heuristics:
    - name: "Database Choice"
      rule: "Use Postgres for production-grade APIs"
      always:
        - "Use Postgres with SQLAlchemy ORM"
        - "Wrap in DatabaseProtocol for testability"
      
    - name: "Auth Requirements"  
      rule: "Enterprise auth with SSO support"
      always:
        - "Use OAuth 2.0 with SAML fallback"
        - "Wrap in AuthProvider protocol"
```

This approach:
- Keeps domain knowledge in lenses (single source of truth)
- Allows project-specific customization via custom lenses
- Supports inheritance (`extends: coder`)
- Reuses existing lens infrastructure

### Center Hints

Users can hint at the center without full specification:

```yaml
# .sunwell/project.yaml
center:
  hint: "Focus on the AI-assisted moderation"
  # Planner will expand this into full center
```

---

## Metrics

### Plan Quality Indicators

```python
@dataclass(frozen=True, slots=True)
class PuzzleMetrics:
    """Metrics specific to puzzle-shaped plans."""
    
    has_clear_center: bool
    """Root artifact represents unique value."""
    
    edge_coverage: float
    """Percentage of expected edges present."""
    
    seam_count: int
    """Number of protocol seams for swappability."""
    
    value_gradient_score: float
    """How well the DAG flows from generic to unique."""
    
    center_reachability: float
    """What percentage of artifacts have path to center."""
```

### Shape Verification

```python
def verify_shape(graph: ArtifactGraph, center_id: str) -> list[str]:
    """Verify the DAG has proper puzzle shape."""
    issues = []
    
    # Check center is root
    if center_id not in graph.roots():
        issues.append(f"Center '{center_id}' is not a root")
    
    # Check all paths lead to center
    for artifact in graph.artifacts.values():
        if not graph.has_path(artifact.id, center_id):
            issues.append(f"Artifact '{artifact.id}' has no path to center")
    
    # Check leaves are commodity/protocol
    for leaf_id in graph.leaves():
        leaf = graph.artifacts[leaf_id]
        if leaf.domain_type not in ("protocol", "commodity", "external"):
            issues.append(f"Leaf '{leaf_id}' is not commodity type")
    
    return issues
```

---

## CLI Integration

```bash
# Standard planning (auto-detects sparse goals)
sunwell agent "Build a forum app" --strategy puzzle

# With center hint
sunwell agent "Build a forum app" --center "reputation-based moderation"

# Show puzzle analysis
sunwell agent "Build a forum app" --strategy puzzle --show-puzzle

# Output:
# CENTER: Forum where reputation unlocks moderation powers
# EDGES: DatabaseProtocol, AuthProvider, ...
# SEAMS: Database (SQLite→Postgres), Auth (JWT→OAuth)
# SHAPE: ✓ Valid value gradient
```

---

## Future Work

### 1. Learning Priors from Feedback

Track which defaults get overridden and adjust:

```python
# If users frequently swap SQLite → Postgres for "forum" intent
# Consider changing the default for that intent
```

### 2. Domain-Specific Prior Packs

```yaml
# Enterprise API priors
enterprise:
  auth:
    default: OAuth 2.0 + SAML
  database:
    default: Postgres
  logging:
    default: Structured JSON to SIEM
```

### 3. Center Refinement Loop

After initial plan, ask: "Does this center still feel right?"

```python
# If execution reveals the center should be different,
# restructure the DAG to flow toward new center
```

---

## Risks and Mitigations

### Risk 1: Center Discovery Produces Generic Results

**Problem**: LLM returns "A forum for discussions" instead of something unique.

**Detection**: Check `center.differentiator` length and specificity:
```python
def validate_center(center: ProjectCenter) -> CenterQuality:
    issues = []
    
    # Differentiator should be substantive (>20 chars)
    if len(center.differentiator) < 20:
        issues.append("Differentiator too short")
    
    # Check for banned generic phrases
    generic_phrases = ["for users", "easy to use", "simple", "powerful"]
    if any(p in center.description.lower() for p in generic_phrases):
        issues.append("Description contains generic marketing language")
    
    # Pitch should mention something not in the original goal
    # (indicates actual invention happened)
    
    return CenterQuality(
        is_valid=len(issues) == 0,
        issues=tuple(issues),
        confidence=1.0 - (len(issues) * 0.2),
    )
```

**Mitigation**: 
- Retry with stronger prompt if validation fails
- Fall back to user prompt: "What makes this project unique?"
- Accept generic center but log warning

### Risk 2: Sane Defaults Don't Match User's Domain

**Problem**: User building enterprise software gets SQLite default.

**Detection**: Keywords in goal that suggest different defaults:
```python
ENTERPRISE_KEYWORDS = {"enterprise", "production", "scale", "million", "compliance"}
EMBEDDED_KEYWORDS = {"embedded", "iot", "microcontroller", "raspberry"}

def detect_domain_mismatch(goal: str, priors: list[ArchitecturePrior]) -> list[str]:
    warnings = []
    goal_lower = goal.lower()
    
    if any(k in goal_lower for k in ENTERPRISE_KEYWORDS):
        if any(p.name == "database" and p.default_value == "SQLite" for p in priors):
            warnings.append("Goal suggests enterprise scale but using SQLite default")
    
    return warnings
```

**Mitigation**:
- Emit warnings when domain signals conflict with lens priors
- Users can create project-specific lenses with appropriate defaults
- Intent detection should distinguish `api` from `enterprise_api`

### Risk 3: Goal Has No Clear Center

**Problem**: "Implement RFC 7540 HTTP/2 parser" — the center IS the specification, no "unique angle" needed.

**Detection**: 
```python
def is_specification_goal(goal: str) -> bool:
    """Check if goal is spec-compliance, not creative."""
    spec_patterns = [
        r"RFC\s*\d+",
        r"implement.*spec",
        r"comply with",
        r"per the standard",
    ]
    return any(re.search(p, goal, re.I) for p in spec_patterns)
```

**Mitigation**:
- For specification goals, skip center discovery
- Set center to the spec itself: `ProjectCenter(description="Full RFC 7540 compliance", ...)`
- Mark `center_invented=False` in metadata

### Risk 4: Multiple Valid Centers Exist

**Problem**: "Build a social app" could center on privacy, viral growth, or content curation.

**Detection**: N/A (discovered during execution)

**Mitigation**:
- When `--center` flag not provided, present top 3 candidates:
  ```
  Possible centers:
  1. Privacy-first social network (differentiator: local-first, no tracking)
  2. Viral content discovery (differentiator: algorithm transparency)
  3. Community curation (differentiator: human moderators over AI)
  
  Choose [1-3] or describe your own:
  ```
- For non-interactive mode, pick first and log alternatives

### Risk 5: Protocol Overhead for Simple Projects

**Problem**: "Create hello.py" gets wrapped in protocols unnecessarily.

**Detection**: Complexity router (existing infrastructure):
```python
async def should_use_puzzle_planning(goal: str, router: UnifiedRouter) -> bool:
    complexity = await router.assess_complexity(goal)
    return complexity.level != ComplexityLevel.TRIVIAL
```

**Mitigation**:
- Skip puzzle planning for trivial goals (fall back to base ArtifactPlanner)
- Minimum artifact threshold: only generate protocols if graph has 5+ artifacts

---

## Testing Strategy

### Unit Tests

```python
# tests/naaru/planners/test_puzzle.py

class TestGapAnalysis:
    """Test gap detection accuracy."""
    
    async def test_detects_missing_database(self):
        gaps = await analyze_gaps("Build a REST API", mock_model)
        assert "database" in gaps.unspecified
    
    async def test_detects_specified_database(self):
        gaps = await analyze_gaps("Build API with Postgres", mock_model)
        assert "database" in gaps.specified
    
    async def test_detects_center_when_present(self):
        goal = "Build a forum where reputation unlocks moderation"
        gaps = await analyze_gaps(goal, mock_model)
        assert gaps.center_specified is True


class TestCenterValidation:
    """Test center quality checks."""
    
    def test_rejects_generic_center(self):
        center = ProjectCenter(
            description="A forum for discussions",
            differentiator="Easy to use",
            pitch="A forum.",
        )
        result = validate_center(center)
        assert not result.is_valid
    
    def test_accepts_specific_center(self):
        center = ProjectCenter(
            description="Forum where reputation unlocks moderation powers",
            differentiator="Trust earned through verified helpful answers",
            pitch="Quality contributions unlock real power...",
        )
        result = validate_center(center)
        assert result.is_valid


class TestPriorSelection:
    """Test prior retrieval and application."""
    
    def test_api_intent_gets_database_prior(self):
        priors = get_priors_for_intent("api", {"database"})
        assert any(p.name == "database" for p in priors)
    
    def test_story_intent_no_database_prior(self):
        priors = get_priors_for_intent("story", {"database"})
        assert not any(p.name == "database" for p in priors)


class TestShapeVerification:
    """Test DAG shape validation."""
    
    def test_detects_center_not_root(self):
        graph = make_graph_with_center_as_interior()
        issues = verify_shape(graph, "center")
        assert "not a root" in issues[0]
    
    def test_accepts_valid_shape(self):
        graph = make_valid_puzzle_graph()
        issues = verify_shape(graph, "center")
        assert issues == []
```

### Integration Tests

```python
# tests/naaru/planners/test_puzzle_integration.py

class TestPuzzlePlannerE2E:
    """End-to-end puzzle planning tests."""
    
    @pytest.mark.integration
    async def test_sparse_api_goal(self, live_model):
        """Sparse goal should produce complete architecture."""
        planner = PuzzlePlanner(model=live_model, priors=DEFAULT_PRIORS)
        graph = await planner.plan("Build a forum app")
        
        # Should have protocols (edges)
        leaves = graph.leaves()
        assert any("Protocol" in lid for lid in leaves)
        
        # Should have clear root (center)
        roots = graph.roots()
        assert len(roots) == 1  # Single convergence point
        
        # Should be valid DAG
        assert graph.validate() == []
    
    @pytest.mark.integration  
    async def test_detailed_goal_preserves_specs(self, live_model):
        """Detailed goal should not override explicit choices."""
        planner = PuzzlePlanner(model=live_model, priors=DEFAULT_PRIORS)
        graph = await planner.plan("Build API with Postgres and OAuth")
        
        # Should use Postgres, not SQLite default
        artifacts = graph.to_dict()["artifacts"]
        db_artifacts = [a for a in artifacts.values() if "database" in a["id"].lower()]
        assert any("postgres" in str(a).lower() for a in db_artifacts)
```

### Benchmark Tasks

Add to `benchmark/tasks/planning/`:

```yaml
# benchmark/tasks/planning/puzzle-sparse-api.yaml
id: puzzle-sparse-api
description: Test puzzle planning on sparse API goal
goal: "Build a forum app"
expected:
  has_protocols: true
  has_center: true
  min_artifacts: 8
  max_artifacts: 25
validation:
  - type: shape
    check: center_is_root
  - type: coverage
    required: [database, auth, tests]
```

---

## Architecture Impact

### File Structure

```
src/sunwell/naaru/planners/
├── __init__.py          # Add PuzzlePlanner export
├── artifact.py          # Existing - no changes
├── harmonic.py          # Existing - no changes
├── puzzle.py            # NEW: PuzzlePlanner implementation
└── protocol.py          # Existing - no changes

src/sunwell/naaru/puzzle/
├── __init__.py          # Module exports
├── center.py            # Center discovery logic
├── gaps.py              # Gap analysis logic
├── lens_priors.py       # Extract priors FROM lenses (not hardcoded)
├── shape.py             # Shape verification
└── types.py             # ProjectCenter, GapAnalysis, etc.
```

**Note**: No `priors/` directory with hardcoded YAML files. Priors are extracted from the active lens at planning time.

### Integration Points

| Component | Change Required |
|-----------|-----------------|
| `cli/agent_cmd.py` | Add `--strategy puzzle` option |
| `cli/naaru_cmd.py` | Add `--strategy puzzle` option |
| `naaru/planners/__init__.py` | Export `PuzzlePlanner` |
| `naaru/artifacts.py` | No changes (reuse existing) |
| `project/schema.py` | No changes (can extend later) |

### Strategy Registry

```python
# src/sunwell/naaru/planners/__init__.py

STRATEGY_PLANNERS = {
    "artifact_first": ArtifactPlanner,
    "harmonic": HarmonicPlanner,
    "puzzle": PuzzlePlanner,  # NEW
}
```

---

## Summary

Puzzle-First Planning ensures sparse specifications produce well-architected plans by:

1. **Finding the center** — The unique value prop becomes the DAG root
2. **Filling the edges** — Sane defaults for commodity requirements
3. **Designing seams** — High-volatility decisions wrapped in protocols
4. **Verifying the shape** — DAG flows from generic (leaves) to unique (root)

The result: "Build a REST API" gets the same architectural treatment as a 2000-line RFC, informed by the project's history, patterns, and decisions.

---

## Implementation Order

**RFC-045 must be implemented first.** This RFC is a consumer of Project Intelligence.

```
1. RFC-045: Project Intelligence (8 weeks)
   ├── Decision Memory
   ├── Codebase Graph
   ├── Pattern Learning
   └── Failure Memory

2. RFC-044: Puzzle Planning (2-3 weeks)
   ├── Context-first center discovery
   ├── Context-first edge resolution
   ├── Shape verification (value gradient)
   └── Integration with ArtifactPlanner

3. Combined Testing
   └── Benchmark: context-aware vs. static priors
```

**Fallback mode**: RFC-044 can run without RFC-045 using static priors and user dialogue. This allows testing the puzzle model before full intelligence integration.

---

## References

- RFC-035: Project Schema (domain-specific artifact types)
- RFC-036: Artifact-First Planning (base artifact discovery)
- RFC-038: Harmonic Planning (multi-candidate optimization)
- RFC-039: Expertise-Aware Planning (lens-based domain expertise)
- **RFC-045: Project Intelligence (context provider for this RFC)**