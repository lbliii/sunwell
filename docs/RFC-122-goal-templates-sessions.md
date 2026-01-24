# RFC-122: Goal Templates & Work Sessions

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-119 (Unified Event Bus), RFC-120 (Observability), RFC-114 (Backlog UI)

## Summary

Add goal templates for common patterns ("add CRUD endpoint", "write tests for X") and work sessions to batch related goals together. Enable "do this again" and "what did we do today?" workflows.

**Key distinction**: Work sessions (this RFC) are user-facing organizational groupings. They complement but differ from RFC-120's observability sessions, which track metrics automatically.

## Motivation

### Problem

Users often repeat similar goals with minor variations:

1. **Repetitive goals**: "Add CRUD for User", "Add CRUD for Product", "Add CRUD for Order"
2. **No organizational context**: Goals are flat list, no grouping by feature/project
3. **No "do it again"**: Can't easily repeat a successful goal pattern on a new target

### Inspiration: Pachyderm Pipelines

Pachyderm's declarative pipeline specs are reusable:
```yaml
pipeline:
  name: edges
transform:
  cmd: [python, /edges.py]
  image: opencv/opencv
input:
  pfs:
    glob: /*
    repo: images
```

The same spec can process different data. We want similar reusability for goals.

### User Stories

**Goal templates:**
> "I just added CRUD for Users. Now I want to do the same pattern for Products. Give me a template."

**Work sessions:**
> "I'm working on the 'Auth System' feature. Group all my auth-related goals together."

**"Do it again":**
> "That goal worked great. Run it again with `Order` instead of `User`."

---

## Goals

1. **Goal templates**: Extract reusable patterns from completed goals
2. **Work sessions**: Organize goals into logical feature/project groupings
3. **Template instantiation**: One-click create goal from template
4. **Session summary**: View all goals in a work session together

## Non-Goals

- Template marketplace/sharing (future)
- Automatic template extraction (starts manual)
- Cross-project templates
- Replacing RFC-120's observability sessions (complementary, not replacement)

---

## Design Alternatives

### Option A: Work Sessions as Metadata on Goals (Recommended)

Add `work_session_id` field to existing `Goal` dataclass. Sessions are lightweight references.

**Pros**:
- Minimal model changes
- Goals remain the source of truth
- Easy migration (existing goals have `work_session_id=None`)

**Cons**:
- Session queries require scanning goals
- Session state (active/completed) stored separately

### Option B: Sessions as First-Class Entities

Sessions own goals, goals have `parent_session_id`.

**Pros**:
- Clear ownership hierarchy
- Efficient session queries

**Cons**:
- Larger schema change
- Orphan goal handling complexity
- Conflicts with existing epic/milestone hierarchy (RFC-115)

### Option C: Virtual Sessions via Tags

Use goal tags like `session:auth-system` for grouping.

**Pros**:
- No new models
- Flexible, ad-hoc grouping

**Cons**:
- No session lifecycle (active/completed)
- Tag management overhead
- Naming collisions

**Decision**: Option A. Lightweight metadata approach integrates cleanly with existing goal infrastructure.

---

## Design

### Relationship with RFC-120

| Concept | RFC-120 (Observability) | RFC-122 (Work Sessions) |
|---------|-------------------------|-------------------------|
| Purpose | Automatic metrics tracking | User organizational grouping |
| Naming | Unnamed, auto-generated | User-named ("Auth System") |
| Lifecycle | Start at CLI/Studio launch | User creates/completes explicitly |
| Storage | `.sunwell/sessions/` | `.sunwell/work-sessions/` |
| Scope | Single execution session | Spans multiple days/sessions |

**Integration**: When a goal completes, RFC-120's `SessionTracker` records metrics. If the goal belongs to a work session (RFC-122), the `WorkSession` is updated with the goal completion.

```python
# Integration flow
async def on_goal_complete(goal: Goal, result: GoalResult):
    # RFC-120: Record observability metrics
    session_tracker.record_goal_complete(
        goal_id=goal.id,
        goal=goal.title,
        status="completed" if result.success else "failed",
        ...
    )
    
    # RFC-122: Update work session if applicable
    if goal.work_session_id:
        work_session_store.mark_goal_complete(goal.work_session_id, goal.id)
    
    # RFC-119: Emit event
    event_bus.emit(GoalCompletedEvent(goal_id=goal.id, ...))
```

### Part 1: Goal Templates

#### Data Model

```python
# sunwell/templates/models.py

@dataclass(frozen=True, slots=True)
class GoalTemplate:
    """A reusable goal pattern."""
    
    template_id: str
    name: str                      # "Add CRUD endpoint"
    description: str               # What this template does
    
    # Template pattern (with placeholders)
    goal_pattern: str              # "Add CRUD endpoints for {{entity}}"
    
    # Variables
    variables: tuple[TemplateVariable, ...]
    
    # Context hints
    suggested_files: tuple[str, ...]  # ("models/", "api/routes.py")
    tags: tuple[str, ...]             # ("crud", "api", "backend")
    
    # Source
    source_goal_id: str | None     # Goal this was extracted from
    created_at: datetime
    usage_count: int = 0


@dataclass(frozen=True, slots=True)
class TemplateVariable:
    """A variable in a goal template."""
    
    name: str                      # "entity"
    description: str               # "The entity name (e.g., User, Product)"
    var_type: Literal["string", "file", "choice"]
    choices: tuple[str, ...] | None = None  # For choice type
    default: str | None = None
    required: bool = True
```

#### Variable Extraction Algorithm

When creating a template from an existing goal, the user identifies values to parameterize:

```python
def extract_pattern(goal_text: str, extractions: list[tuple[str, str]]) -> str:
    """Extract a template pattern from a goal.
    
    Args:
        goal_text: Original goal text, e.g., "Add CRUD endpoints for User"
        extractions: List of (value, variable_name) pairs
                     e.g., [("User", "entity")]
    
    Returns:
        Pattern with placeholders, e.g., "Add CRUD endpoints for {{entity}}"
    """
    pattern = goal_text
    for value, var_name in extractions:
        # Case-insensitive replacement, preserve original case style
        pattern = pattern.replace(value, f"{{{{{var_name}}}}}")
    return pattern
```

**Edge cases**:
- Multiple occurrences: Replace all by default, user can refine
- Overlapping values: Process longest values first
- No matches: Warn user, suggest alternatives

#### Built-in Templates

```python
# sunwell/templates/builtins.py

BUILTIN_TEMPLATES: tuple[GoalTemplate, ...] = (
    GoalTemplate(
        template_id="crud-endpoint",
        name="Add CRUD Endpoint",
        description="Create a complete CRUD API for an entity",
        goal_pattern="Add CRUD endpoints for {{entity}} including create, read, update, delete operations",
        variables=(
            TemplateVariable(
                name="entity",
                description="Entity name (e.g., User, Product)",
                var_type="string",
                required=True,
            ),
        ),
        suggested_files=("models/", "api/"),
        tags=("crud", "api", "backend"),
        source_goal_id=None,
        created_at=datetime(2026, 1, 1),
    ),
    
    GoalTemplate(
        template_id="test-module",
        name="Write Tests for Module",
        description="Generate comprehensive tests for an existing module",
        goal_pattern="Write unit tests for {{module_path}} with {{coverage}}% coverage target",
        variables=(
            TemplateVariable(
                name="module_path",
                description="Path to module to test",
                var_type="file",
                required=True,
            ),
            TemplateVariable(
                name="coverage",
                description="Target coverage percentage",
                var_type="choice",
                choices=("80", "90", "100"),
                default="80",
            ),
        ),
        suggested_files=("tests/",),
        tags=("testing", "quality"),
        source_goal_id=None,
        created_at=datetime(2026, 1, 1),
    ),
    
    GoalTemplate(
        template_id="add-feature-flag",
        name="Add Feature Flag",
        description="Add a feature flag with conditional logic",
        goal_pattern="Add feature flag '{{flag_name}}' to control {{description}}",
        variables=(
            TemplateVariable(
                name="flag_name",
                description="Snake_case flag name",
                var_type="string",
                required=True,
            ),
            TemplateVariable(
                name="description",
                description="What the flag controls",
                var_type="string",
                required=True,
            ),
        ),
        suggested_files=("config/", "features/"),
        tags=("features", "config"),
        source_goal_id=None,
        created_at=datetime(2026, 1, 1),
    ),
    
    GoalTemplate(
        template_id="refactor-extract",
        name="Extract to Module",
        description="Extract code from one file into a new module",
        goal_pattern="Extract {{what}} from {{source_file}} into new module {{target_module}}",
        variables=(
            TemplateVariable(
                name="what",
                description="What to extract (e.g., 'auth logic', 'validation functions')",
                var_type="string",
                required=True,
            ),
            TemplateVariable(
                name="source_file",
                description="File to extract from",
                var_type="file",
                required=True,
            ),
            TemplateVariable(
                name="target_module",
                description="New module path",
                var_type="string",
                required=True,
            ),
        ),
        suggested_files=(),
        tags=("refactor", "cleanup"),
        source_goal_id=None,
        created_at=datetime(2026, 1, 1),
    ),
)
```

#### Template Store

```python
# sunwell/templates/store.py

class TemplateStore:
    """Manages goal templates. Thread-safe."""
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'templates'
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    
    def list_templates(self, tags: list[str] | None = None) -> list[GoalTemplate]:
        """List all templates, optionally filtered by tags."""
        templates = list(BUILTIN_TEMPLATES) + self._load_custom()
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        return sorted(templates, key=lambda t: -t.usage_count)
    
    def get_template(self, template_id: str) -> GoalTemplate | None:
        """Get a specific template."""
        for t in BUILTIN_TEMPLATES:
            if t.template_id == template_id:
                return t
        return self._load_custom_by_id(template_id)
    
    def create_from_goal(
        self,
        goal_id: str,
        name: str,
        extractions: list[tuple[str, str]],  # (value, var_name) pairs
        goal_store: GoalStore,
    ) -> GoalTemplate:
        """Create a template from a completed goal.
        
        Args:
            goal_id: ID of the source goal
            name: Human-readable template name
            extractions: Values to parameterize as (value, var_name) pairs
            goal_store: Store to fetch goal from
        
        Returns:
            Created template
        """
        goal = goal_store.get(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
        # Extract pattern
        pattern = extract_pattern(goal.description, extractions)
        
        # Build variables from extractions
        variables = tuple(
            TemplateVariable(
                name=var_name,
                description=f"Value extracted from: {value}",
                var_type="string",
                required=True,
            )
            for value, var_name in extractions
        )
        
        template = GoalTemplate(
            template_id=str(uuid4()),
            name=name,
            description=f"Based on goal: {goal.title}",
            goal_pattern=pattern,
            variables=variables,
            suggested_files=(),
            tags=(),
            source_goal_id=goal_id,
            created_at=datetime.now(UTC),
        )
        
        with self._lock:
            self._save(template)
        
        return template
    
    def instantiate(self, template_id: str, values: dict[str, str]) -> str:
        """Create a goal string from template + values.
        
        Args:
            template_id: Template to instantiate
            values: Variable name -> value mapping
        
        Returns:
            Resolved goal string
        
        Raises:
            ValueError: If required variable missing
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Validate all required variables provided
        for var in template.variables:
            if var.required and var.name not in values:
                raise ValueError(f"Missing required variable: {var.name}")
        
        # Apply defaults for optional variables
        resolved_values = {
            var.name: values.get(var.name, var.default)
            for var in template.variables
        }
        
        # Substitute variables
        goal = template.goal_pattern
        for name, value in resolved_values.items():
            if value is not None:
                goal = goal.replace(f"{{{{{name}}}}}", value)
        
        # Record usage
        self._increment_usage(template_id)
        
        return goal
```

### Part 2: Work Sessions

#### Data Model

```python
# sunwell/work_sessions/models.py

@dataclass
class WorkSession:
    """A user-defined logical grouping of related goals.
    
    Distinguished from RFC-120's SessionTracker (observability) by:
    - User-named and explicitly created
    - Spans multiple execution sessions
    - Organizational, not metrics-focused
    """
    
    session_id: str
    name: str                      # "Auth System Implementation"
    description: str | None
    
    # Goals in this session
    goal_ids: list[str]
    completed_goal_ids: set[str]   # Track completion within session
    
    # Status
    status: Literal["active", "completed", "archived"]
    
    # Timing
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    
    @property
    def goals_completed(self) -> int:
        return len(self.completed_goal_ids)
    
    @property
    def goals_total(self) -> int:
        return len(self.goal_ids)
    
    @property
    def progress(self) -> float:
        if self.goals_total == 0:
            return 0.0
        return self.goals_completed / self.goals_total
```

#### Goal Model Extension

```python
# Extension to sunwell/backlog/goals.py

@dataclass(frozen=True, slots=True)
class Goal:
    # ... existing fields ...
    
    # RFC-122: Work session grouping
    work_session_id: str | None = None
    """User-defined work session this goal belongs to.
    
    Distinct from RFC-120's observability sessions which are automatic.
    """
```

#### Work Session Store

```python
# sunwell/work_sessions/store.py

# Storage location: DISTINCT from RFC-120's .sunwell/sessions/
DEFAULT_WORK_SESSIONS_DIR = Path(".sunwell/work-sessions")


class WorkSessionStore:
    """Manages user-defined work sessions. Thread-safe."""
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'work-sessions'
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active_session: str | None = self._load_active()
    
    # ── Session Management ──────────────────────────────────
    
    def create_session(self, name: str, description: str | None = None) -> WorkSession:
        """Create a new work session."""
        session = WorkSession(
            session_id=str(uuid4()),
            name=name,
            description=description,
            goal_ids=[],
            completed_goal_ids=set(),
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            completed_at=None,
        )
        
        with self._lock:
            self._save(session)
            self._active_session = session.session_id
            self._save_active()
        
        return session
    
    def get_active(self) -> WorkSession | None:
        """Get the currently active work session."""
        if self._active_session:
            return self.get(self._active_session)
        return None
    
    def add_goal_to_session(
        self,
        goal_id: str,
        session_id: str | None = None,
    ) -> bool:
        """Add a goal to a work session (or active session).
        
        Returns True if goal was added, False if no session.
        """
        session_id = session_id or self._active_session
        if not session_id:
            return False
        
        with self._lock:
            session = self.get(session_id)
            if not session:
                return False
            
            if goal_id not in session.goal_ids:
                session.goal_ids.append(goal_id)
                session.updated_at = datetime.now(UTC)
                self._save(session)
        
        return True
    
    def mark_goal_complete(self, session_id: str, goal_id: str) -> None:
        """Mark a goal as completed within a session."""
        with self._lock:
            session = self.get(session_id)
            if session and goal_id in session.goal_ids:
                session.completed_goal_ids.add(goal_id)
                session.updated_at = datetime.now(UTC)
                self._save(session)
    
    def complete_session(self, session_id: str) -> None:
        """Mark a work session as completed."""
        with self._lock:
            session = self.get(session_id)
            if session:
                session.status = "completed"
                session.completed_at = datetime.now(UTC)
                self._save(session)
            
            if self._active_session == session_id:
                self._active_session = None
                self._save_active()
    
    # ── Queries ─────────────────────────────────────────────
    
    def list_sessions(
        self,
        status: str | None = None,
    ) -> list[WorkSession]:
        """List all work sessions."""
        sessions = []
        for path in self.store_path.glob("sess-*.json"):
            session = self._load(path)
            if session and (status is None or session.status == status):
                sessions.append(session)
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
    
    def get_session_summary(
        self,
        session_id: str,
        goal_store: GoalStore,
    ) -> WorkSessionSummary:
        """Get detailed summary of a work session."""
        session = self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        goals = [goal_store.get(gid) for gid in session.goal_ids]
        goals = [g for g in goals if g is not None]
        
        # Aggregate file changes from completed goals
        files_created: set[str] = set()
        files_modified: set[str] = set()
        
        for goal in goals:
            if goal.id in session.completed_goal_ids:
                # Would need goal result data - simplified here
                pass
        
        return WorkSessionSummary(
            session=session,
            goals=goals,
            files_created=len(files_created),
            files_modified=len(files_modified),
        )
```

### Part 3: Event Bus Integration (RFC-119)

```python
# Events emitted by this RFC

@dataclass(frozen=True)
class TemplateCreatedEvent:
    """Emitted when a new template is created."""
    template_id: str
    name: str
    source_goal_id: str | None


@dataclass(frozen=True)
class TemplateUsedEvent:
    """Emitted when a template is instantiated."""
    template_id: str
    goal_id: str  # Resulting goal
    variables: dict[str, str]


@dataclass(frozen=True)
class WorkSessionCreatedEvent:
    """Emitted when a work session is created."""
    session_id: str
    name: str


@dataclass(frozen=True)
class WorkSessionCompletedEvent:
    """Emitted when a work session is completed."""
    session_id: str
    name: str
    goals_completed: int
    goals_total: int
```

### Part 4: CLI Interface

#### Template Commands

```bash
# List available templates
sunwell template list

╭─────────────────────────────────────────────────────╮
│  📋 Goal Templates                                  │
╰─────────────────────────────────────────────────────╯

Built-in:
  crud-endpoint     Add CRUD Endpoint            (used 12x)
  test-module       Write Tests for Module       (used 8x)
  add-feature-flag  Add Feature Flag             (used 3x)
  refactor-extract  Extract to Module            (used 2x)

Custom:
  my-api-endpoint   Custom API endpoint pattern  (used 5x)

# Use a template
sunwell template use crud-endpoint

? entity: Product
? Ready to create goal? Yes

Created goal: "Add CRUD endpoints for Product including create, read, update, delete operations"
→ Run `sunwell run` to execute

# Create template from past goal
sunwell template create --from-goal abc123

? Template name: Add REST endpoint
? Variables to extract:
  - entity (from "User"): Yes
  - http_method (from "POST"): No
  
Created template: add-rest-endpoint

# Quick instantiate
sunwell template use crud-endpoint --entity=Order
```

#### Work Session Commands

```bash
# Start a new work session
sunwell ws start "Auth System"

Started work session: Auth System
All subsequent goals will be grouped here.

# Show current work session
sunwell ws status

╭─────────────────────────────────────────────────────╮
│  🎯 Work Session: Auth System                       │
│  Status: Active (2 hours)                           │
╰─────────────────────────────────────────────────────╯

Goals: 3 completed, 1 in progress, 2 queued

Completed:
  ✓ Add OAuth configuration
  ✓ Create auth callback route  
  ✓ Add session middleware

In Progress:
  ◐ Write auth tests

Queued:
  ○ Add password reset flow
  ○ Create admin auth routes

Files touched: 12
Lines changed: +450, -23

# End work session
sunwell ws complete

Work session "Auth System" completed!
  Duration: 3 hours
  Goals: 6 completed
  Files: 15 created, 8 modified

# List past work sessions
sunwell ws list

  ID        Name                Status      Goals  Duration
  ──────────────────────────────────────────────────────────
  sess-01   Auth System         completed   6/6    3h
  sess-02   API Refactor        completed   4/4    1.5h
  sess-03   Testing Sprint      active      2/5    --

# Note: `sunwell ws` is alias for `sunwell work-session`
```

### Part 5: Server API

```
# Templates
GET  /api/templates
GET  /api/templates/{id}
POST /api/templates                    # Create from goal
POST /api/templates/{id}/instantiate   # Create goal from template

# Work Sessions (distinct from /api/session which is RFC-120)
GET  /api/work-sessions
GET  /api/work-sessions/active
POST /api/work-sessions                # Create work session
POST /api/work-sessions/{id}/goals     # Add goal to work session
POST /api/work-sessions/{id}/complete
GET  /api/work-sessions/{id}/summary
```

### Part 6: Studio Integration

#### Template Picker

```svelte
<!-- TemplatePicker.svelte -->
<script lang="ts">
  import type { GoalTemplate } from '$lib/types';
  
  let templates = $state<GoalTemplate[]>([]);
  let selectedTemplate = $state<GoalTemplate | null>(null);
  let variables = $state<Record<string, string>>({});
  
  onMount(async () => {
    templates = await fetch('/api/templates').then(r => r.json());
  });
  
  async function createGoal() {
    const response = await fetch(
      `/api/templates/${selectedTemplate!.template_id}/instantiate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ variables }),
      }
    );
    const { goal } = await response.json();
    
    // Add to backlog
    await addToBacklog(goal);
    
    // Reset
    selectedTemplate = null;
    variables = {};
  }
</script>

<div class="template-picker">
  <h3>📋 Create from Template</h3>
  
  <div class="template-list">
    {#each templates as template}
      <button 
        class="template-item"
        class:selected={selectedTemplate?.template_id === template.template_id}
        onclick={() => {
          selectedTemplate = template;
          // Initialize defaults
          variables = Object.fromEntries(
            template.variables
              .filter(v => v.default)
              .map(v => [v.name, v.default!])
          );
        }}
      >
        <span class="name">{template.name}</span>
        <span class="description">{template.description}</span>
        <span class="usage">{template.usage_count}x used</span>
      </button>
    {/each}
  </div>
  
  {#if selectedTemplate}
    <div class="variables">
      <h4>Configure</h4>
      {#each selectedTemplate.variables as variable}
        <label>
          <span>{variable.name}{variable.required ? ' *' : ''}</span>
          {#if variable.var_type === 'choice'}
            <select bind:value={variables[variable.name]}>
              {#each variable.choices ?? [] as choice}
                <option value={choice}>{choice}</option>
              {/each}
            </select>
          {:else if variable.var_type === 'file'}
            <input 
              type="text" 
              placeholder={variable.description}
              bind:value={variables[variable.name]}
            />
            <!-- Could add file picker button -->
          {:else}
            <input 
              type="text" 
              placeholder={variable.description}
              bind:value={variables[variable.name]}
            />
          {/if}
        </label>
      {/each}
    </div>
    
    <button 
      class="create-button" 
      onclick={createGoal}
      disabled={selectedTemplate.variables.some(v => v.required && !variables[v.name])}
    >
      Create Goal
    </button>
  {/if}
</div>
```

#### Work Session Panel

```svelte
<!-- WorkSessionPanel.svelte -->
<script lang="ts">
  import type { WorkSession } from '$lib/types';
  
  let session = $derived(workSessionStore.active);
</script>

{#if session}
  <div class="session-panel">
    <header>
      <h3>🎯 {session.name}</h3>
      <span class="status">{session.status}</span>
      <button onclick={() => completeWorkSession(session.session_id)}>
        Complete
      </button>
    </header>
    
    <div class="progress">
      <div class="bar" style="width: {session.progress * 100}%"></div>
      <span>{session.goals_completed}/{session.goals_total} goals</span>
    </div>
    
    <div class="goal-list">
      {#each session.goal_ids as goalId}
        <GoalCard 
          {goalId} 
          completed={session.completed_goal_ids.has(goalId)}
        />
      {/each}
    </div>
  </div>
{:else}
  <div class="no-session">
    <p>No active work session</p>
    <button onclick={startWorkSession}>Start Work Session</button>
  </div>
{/if}
```

---

## Storage

```
.sunwell/
├── templates/
│   ├── custom/
│   │   ├── my-template.json
│   │   └── another.json
│   └── usage.json           # Usage counts
├── work-sessions/           # NOTE: Distinct from sessions/ (RFC-120)
│   ├── active.json          # Currently active work session ID
│   ├── sess-001.json
│   └── sess-002.json
├── sessions/                # RFC-120: Observability sessions (unchanged)
│   └── ...
```

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| User confusion between work sessions and observability sessions | Medium | Medium | Clear naming (`sunwell ws` vs automatic), distinct storage paths, documentation |
| Template variable extraction produces poor patterns | Low | Medium | User reviews pattern before saving, edit capability |
| Work session sprawl (too many abandoned sessions) | Low | Low | Archive old sessions, show only active by default |
| Template name collisions (builtin vs custom) | Low | Low | Namespace: builtins cannot be overwritten, `custom-` prefix for user templates |

---

## Implementation Plan

### Phase 1: Template Core (1 day)

1. Create `sunwell/templates/models.py`
2. Create `sunwell/templates/store.py`
3. Add builtin templates
4. Add CLI commands (`template list`, `template use`)
5. Add server endpoints

### Phase 2: Template Creation (0.5 day)

1. Add `template create --from-goal`
2. Add variable extraction logic with edge case handling
3. Wire event bus emissions

### Phase 3: Work Sessions Core (1 day)

1. Create `sunwell/work_sessions/models.py`
2. Create `sunwell/work_sessions/store.py`
3. Add `work_session_id` field to Goal model
4. Wire into goal creation flow
5. Add CLI commands (`ws start`, `ws status`, `ws complete`)
6. Add server endpoints (distinct from RFC-120's `/api/session`)

### Phase 4: Studio Integration (1 day)

1. Create TemplatePicker.svelte
2. Create WorkSessionPanel.svelte
3. Add to sidebar/backlog views
4. Wire into goal creation flow

### Phase 5: Integration Testing (0.5 day)

1. Test RFC-120 + RFC-122 coexistence
2. Test event bus emissions
3. End-to-end workflow tests

---

## Testing

```python
# test_templates.py
def test_instantiate_template():
    store = TemplateStore(tmp_path)
    
    goal = store.instantiate(
        "crud-endpoint",
        {"entity": "Product"}
    )
    
    assert goal == "Add CRUD endpoints for Product including create, read, update, delete operations"


def test_instantiate_missing_required_variable():
    store = TemplateStore(tmp_path)
    
    with pytest.raises(ValueError, match="Missing required variable"):
        store.instantiate("crud-endpoint", {})


def test_extract_pattern():
    pattern = extract_pattern(
        "Add CRUD endpoints for User with validation",
        [("User", "entity")]
    )
    
    assert pattern == "Add CRUD endpoints for {{entity}} with validation"


def test_extract_pattern_multiple_occurrences():
    pattern = extract_pattern(
        "Copy User from UserService to UserController",
        [("User", "entity")]
    )
    
    assert pattern == "Copy {{entity}} from {{entity}}Service to {{entity}}Controller"


# test_work_sessions.py
def test_work_session_groups_goals():
    store = WorkSessionStore(tmp_path)
    
    session = store.create_session("Auth Work")
    store.add_goal_to_session("g1")
    store.add_goal_to_session("g2")
    
    session = store.get(session.session_id)
    assert session.goal_ids == ["g1", "g2"]


def test_work_session_progress():
    store = WorkSessionStore(tmp_path)
    session = store.create_session("Test")
    
    store.add_goal_to_session("g1", session.session_id)
    store.add_goal_to_session("g2", session.session_id)
    store.add_goal_to_session("g3", session.session_id)
    
    store.mark_goal_complete(session.session_id, "g1")
    store.mark_goal_complete(session.session_id, "g2")
    
    session = store.get(session.session_id)
    assert session.progress == 2/3


def test_work_session_storage_path_distinct_from_rfc120():
    """Ensure work sessions don't collide with RFC-120 sessions."""
    store = WorkSessionStore(tmp_path)
    session = store.create_session("Test")
    
    # Work sessions go to work-sessions/
    assert (tmp_path / ".sunwell" / "work-sessions").exists()
    
    # Should NOT create in sessions/ (RFC-120's path)
    assert not (tmp_path / ".sunwell" / "sessions" / f"{session.session_id}.json").exists()
```

---

## Success Metrics

- Templates reduce repeated goal typing by 50%
- 80% of goals grouped into work sessions when user opts in
- Template instantiation < 100ms
- Zero confusion incidents between work sessions and observability sessions

---

## Future Extensions

- **Smart template suggestions**: Suggest templates based on context
- **Template sharing**: Export/import templates
- **Work session templates**: Predefined session workflows (e.g., "Feature Development" = design → implement → test → document)
- **Auto-session detection**: Group goals automatically by similarity
- **Cross-project templates**: Share templates across projects (requires namespace management)

---

## References

- Pachyderm pipeline specs
- RFC-114: Backlog UI (integration point)
- RFC-119: Unified Event Bus (event emissions)
- RFC-120: Observability & Debugging (distinct session concept)
