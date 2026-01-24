# RFC-122: Goal Templates & Session Grouping

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-119 (Unified Event Bus), RFC-114 (Backlog UI)

## Summary

Add goal templates for common patterns ("add CRUD endpoint", "write tests for X") and session grouping to batch related goals together. Enable "do this again" and "what did we do today?" workflows.

## Motivation

### Problem

Users often repeat similar goals with minor variations:

1. **Repetitive goals**: "Add CRUD for User", "Add CRUD for Product", "Add CRUD for Order"
2. **No session context**: Goals are flat list, no grouping by work session
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

**Session grouping:**
> "I'm working on the 'Auth System' feature. Group all my auth-related goals together."

**"Do it again":**
> "That goal worked great. Run it again with `Order` instead of `User`."

---

## Goals

1. **Goal templates**: Extract reusable patterns from completed goals
2. **Session grouping**: Organize goals into logical sessions/features
3. **Template instantiation**: One-click create goal from template
4. **Session summary**: View all goals in a session together

## Non-Goals

- Template marketplace/sharing (future)
- Automatic template extraction (starts manual)
- Cross-project templates

---

## Design

### Part 1: Goal Templates

#### Data Model

```python
# sunwell/templates/models.py

@dataclass(frozen=True)
class GoalTemplate:
    """A reusable goal pattern."""
    
    template_id: str
    name: str                      # "Add CRUD endpoint"
    description: str               # What this template does
    
    # Template pattern (with placeholders)
    goal_pattern: str              # "Add CRUD endpoints for {{entity}}"
    
    # Variables
    variables: list[TemplateVariable]
    
    # Context hints
    suggested_files: list[str]     # ["models/", "api/routes.py"]
    tags: list[str]                # ["crud", "api", "backend"]
    
    # Source
    source_goal_id: str | None     # Goal this was extracted from
    created_at: datetime
    usage_count: int = 0


@dataclass(frozen=True)
class TemplateVariable:
    """A variable in a goal template."""
    
    name: str                      # "entity"
    description: str               # "The entity name (e.g., User, Product)"
    var_type: str                  # "string" | "file" | "choice"
    choices: list[str] | None      # For choice type
    default: str | None
    required: bool = True


@dataclass
class TemplateInstance:
    """An instantiated template (ready to become a goal)."""
    
    template_id: str
    variables: dict[str, str]      # {"entity": "Product"}
    resolved_goal: str             # "Add CRUD endpoints for Product"
```

#### Built-in Templates

```python
# sunwell/templates/builtins.py

BUILTIN_TEMPLATES = [
    GoalTemplate(
        template_id="crud-endpoint",
        name="Add CRUD Endpoint",
        description="Create a complete CRUD API for an entity",
        goal_pattern="Add CRUD endpoints for {{entity}} including create, read, update, delete operations",
        variables=[
            TemplateVariable(
                name="entity",
                description="Entity name (e.g., User, Product)",
                var_type="string",
                required=True,
            ),
        ],
        suggested_files=["models/", "api/"],
        tags=["crud", "api", "backend"],
    ),
    
    GoalTemplate(
        template_id="test-module",
        name="Write Tests for Module",
        description="Generate comprehensive tests for an existing module",
        goal_pattern="Write unit tests for {{module_path}} with {{coverage}}% coverage target",
        variables=[
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
                choices=["80", "90", "100"],
                default="80",
            ),
        ],
        suggested_files=["tests/"],
        tags=["testing", "quality"],
    ),
    
    GoalTemplate(
        template_id="add-feature-flag",
        name="Add Feature Flag",
        description="Add a feature flag with conditional logic",
        goal_pattern="Add feature flag '{{flag_name}}' to control {{description}}",
        variables=[
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
        ],
        suggested_files=["config/", "features/"],
        tags=["features", "config"],
    ),
    
    GoalTemplate(
        template_id="refactor-extract",
        name="Extract to Module",
        description="Extract code from one file into a new module",
        goal_pattern="Extract {{what}} from {{source_file}} into new module {{target_module}}",
        variables=[
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
        ],
        tags=["refactor", "cleanup"],
    ),
]
```

#### Template Store

```python
# sunwell/templates/store.py

class TemplateStore:
    """Manages goal templates."""
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'templates'
        self.store_path.mkdir(parents=True, exist_ok=True)
    
    def list_templates(self, tags: list[str] | None = None) -> list[GoalTemplate]:
        """List all templates, optionally filtered by tags."""
        templates = BUILTIN_TEMPLATES + self._load_custom()
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        return sorted(templates, key=lambda t: -t.usage_count)
    
    def get_template(self, template_id: str) -> GoalTemplate | None:
        """Get a specific template."""
        ...
    
    def create_from_goal(self, goal_id: str, name: str, variables: list[TemplateVariable]) -> GoalTemplate:
        """Create a template from a completed goal."""
        # Fetch goal from history
        goal = goal_store.get(goal_id)
        
        # Extract pattern (replace specific values with variables)
        pattern = self._extract_pattern(goal.goal, variables)
        
        template = GoalTemplate(
            template_id=str(uuid4()),
            name=name,
            description=f"Based on goal: {goal.goal[:50]}...",
            goal_pattern=pattern,
            variables=variables,
            source_goal_id=goal_id,
            created_at=datetime.utcnow(),
        )
        
        self._save(template)
        return template
    
    def instantiate(self, template_id: str, values: dict[str, str]) -> str:
        """Create a goal string from template + values."""
        template = self.get_template(template_id)
        
        # Validate all required variables provided
        for var in template.variables:
            if var.required and var.name not in values:
                raise ValueError(f"Missing required variable: {var.name}")
        
        # Substitute variables
        goal = template.goal_pattern
        for name, value in values.items():
            goal = goal.replace(f"{{{{{name}}}}}", value)
        
        # Record usage
        self._increment_usage(template_id)
        
        return goal
```

### Part 2: Session Grouping

#### Data Model

```python
# sunwell/sessions/models.py

@dataclass
class Session:
    """A logical grouping of related goals."""
    
    session_id: str
    name: str                      # "Auth System Implementation"
    description: str | None
    
    # Goals in this session
    goal_ids: list[str]
    
    # Status
    status: str                    # "active" | "completed" | "archived"
    
    # Timing
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    
    # Stats (computed)
    @property
    def goals_completed(self) -> int: ...
    
    @property
    def goals_total(self) -> int: ...
    
    @property
    def progress(self) -> float: ...
```

#### Session Store

```python
# sunwell/sessions/store.py

class SessionStore:
    """Manages goal sessions."""
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'sessions'
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._active_session: str | None = None
    
    # ── Session Management ──────────────────────────────────
    
    def create_session(self, name: str, description: str | None = None) -> Session:
        """Create a new session."""
        session = Session(
            session_id=str(uuid4()),
            name=name,
            description=description,
            goal_ids=[],
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            completed_at=None,
        )
        self._save(session)
        self._active_session = session.session_id
        return session
    
    def get_active(self) -> Session | None:
        """Get the currently active session."""
        if self._active_session:
            return self.get(self._active_session)
        return None
    
    def add_goal_to_session(self, goal_id: str, session_id: str | None = None):
        """Add a goal to a session (or active session)."""
        session_id = session_id or self._active_session
        if not session_id:
            return  # No active session, goal is ungrouped
        
        session = self.get(session_id)
        session.goal_ids.append(goal_id)
        session.updated_at = datetime.utcnow()
        self._save(session)
    
    def complete_session(self, session_id: str):
        """Mark a session as completed."""
        session = self.get(session_id)
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        self._save(session)
        
        if self._active_session == session_id:
            self._active_session = None
    
    # ── Queries ─────────────────────────────────────────────
    
    def list_sessions(self, status: str | None = None) -> list[Session]:
        """List all sessions."""
        ...
    
    def get_session_summary(self, session_id: str) -> SessionSummary:
        """Get detailed summary of a session."""
        session = self.get(session_id)
        goals = [goal_store.get(gid) for gid in session.goal_ids]
        
        return SessionSummary(
            session=session,
            goals=goals,
            files_created=...,
            files_modified=...,
            total_duration=...,
        )
```

### Part 3: CLI Interface

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

#### Session Commands

```bash
# Start a new session
sunwell session start "Auth System"

Started session: Auth System
All subsequent goals will be grouped here.

# Show current session
sunwell session status

╭─────────────────────────────────────────────────────╮
│  🎯 Session: Auth System                            │
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

# End session
sunwell session complete

Session "Auth System" completed!
  Duration: 3 hours
  Goals: 6 completed
  Files: 15 created, 8 modified

# List past sessions
sunwell session list

  ID        Name                Status      Goals  Duration
  ──────────────────────────────────────────────────────────
  sess-01   Auth System         completed   6/6    3h
  sess-02   API Refactor        completed   4/4    1.5h
  sess-03   Testing Sprint      active      2/5    --
```

### Part 4: Server API

```
# Templates
GET  /api/templates
GET  /api/templates/{id}
POST /api/templates                    # Create from goal
POST /api/templates/{id}/instantiate   # Create goal from template

# Sessions
GET  /api/sessions
GET  /api/sessions/active
POST /api/sessions                     # Create session
POST /api/sessions/{id}/goals          # Add goal to session
POST /api/sessions/{id}/complete
GET  /api/sessions/{id}/summary
```

### Part 5: Studio Integration

#### Template Picker

```svelte
<!-- TemplatePicker.svelte -->
<script lang="ts">
  let templates = $state<GoalTemplate[]>([]);
  let selectedTemplate = $state<GoalTemplate | null>(null);
  let variables = $state<Record<string, string>>({});
  
  onMount(async () => {
    templates = await fetch('/api/templates').then(r => r.json());
  });
  
  async function createGoal() {
    const goal = await fetch(`/api/templates/${selectedTemplate.template_id}/instantiate`, {
      method: 'POST',
      body: JSON.stringify({ variables }),
    }).then(r => r.json());
    
    // Navigate to goal or add to backlog
    addToBacklog(goal);
  }
</script>

<div class="template-picker">
  <h3>📋 Create from Template</h3>
  
  <div class="template-list">
    {#each templates as template}
      <button 
        class="template-item"
        class:selected={selectedTemplate?.template_id === template.template_id}
        onclick={() => selectedTemplate = template}
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
          <span>{variable.name}</span>
          {#if variable.var_type === 'choice'}
            <select bind:value={variables[variable.name]}>
              {#each variable.choices as choice}
                <option value={choice}>{choice}</option>
              {/each}
            </select>
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
    
    <button class="create-button" onclick={createGoal}>
      Create Goal
    </button>
  {/if}
</div>
```

#### Session Panel

```svelte
<!-- SessionPanel.svelte -->
<script lang="ts">
  let session = $derived(sessionStore.active);
</script>

{#if session}
  <div class="session-panel">
    <header>
      <h3>🎯 {session.name}</h3>
      <span class="status">{session.status}</span>
      <button onclick={() => completeSession(session.session_id)}>
        Complete Session
      </button>
    </header>
    
    <div class="progress">
      <div class="bar" style="width: {session.progress * 100}%"></div>
      <span>{session.goals_completed}/{session.goals_total} goals</span>
    </div>
    
    <div class="goal-list">
      {#each session.goal_ids as goalId}
        <GoalCard {goalId} />
      {/each}
    </div>
  </div>
{:else}
  <div class="no-session">
    <p>No active session</p>
    <button onclick={startSession}>Start Session</button>
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
├── sessions/
│   ├── active.json          # Currently active session ID
│   ├── sess-001.json
│   └── sess-002.json
```

---

## Implementation Plan

### Phase 1: Template Core (1 day)

1. Create `sunwell/templates/models.py`
2. Create `sunwell/templates/store.py`
3. Add builtin templates
4. Add CLI commands (`template list`, `template use`)

### Phase 2: Template Creation (0.5 day)

1. Add `template create --from-goal`
2. Add variable extraction logic
3. Add server endpoints

### Phase 3: Sessions Core (1 day)

1. Create `sunwell/sessions/models.py`
2. Create `sunwell/sessions/store.py`
3. Wire into goal creation
4. Add CLI commands (`session start`, `session status`, `session complete`)

### Phase 4: Studio Integration (1 day)

1. Create TemplatePicker.svelte
2. Create SessionPanel.svelte
3. Add to sidebar/backlog
4. Wire into goal creation flow

---

## Testing

```python
# test_templates.py
async def test_instantiate_template():
    store = TemplateStore(tmp_path)
    
    goal = store.instantiate(
        "crud-endpoint",
        {"entity": "Product"}
    )
    
    assert goal == "Add CRUD endpoints for Product including create, read, update, delete operations"

async def test_create_from_goal():
    store = TemplateStore(tmp_path)
    
    # Mock a completed goal
    goal_store.save(Goal(
        goal_id="g1",
        goal="Add CRUD endpoints for User with validation",
        status="completed",
    ))
    
    template = store.create_from_goal(
        "g1",
        name="CRUD with validation",
        variables=[
            TemplateVariable(name="entity", var_type="string", required=True),
        ],
    )
    
    assert "{{entity}}" in template.goal_pattern


# test_sessions.py
async def test_session_groups_goals():
    store = SessionStore(tmp_path)
    
    session = store.create_session("Auth Work")
    store.add_goal_to_session("g1")
    store.add_goal_to_session("g2")
    
    session = store.get(session.session_id)
    assert session.goal_ids == ["g1", "g2"]

async def test_session_progress():
    store = SessionStore(tmp_path)
    session = store.create_session("Test")
    
    # Add goals with different statuses
    store.add_goal_to_session("g1")  # completed
    store.add_goal_to_session("g2")  # completed
    store.add_goal_to_session("g3")  # in_progress
    
    summary = store.get_session_summary(session.session_id)
    assert summary.session.progress == 2/3
```

---

## Success Metrics

- Templates reduce repeated goal typing by 50%
- 80% of goals grouped into sessions when user opts in
- Template instantiation < 100ms

---

## Future Extensions

- **Smart template suggestions**: Suggest templates based on context
- **Template sharing**: Export/import templates
- **Session templates**: Predefined session workflows
- **Auto-session detection**: Group goals automatically by similarity

---

## References

- Pachyderm pipeline specs
- RFC-114: Backlog UI (integration point)
- RFC-119: Unified Event Bus
