# Chirp Layered Component Architecture

## Design Decision: Composition Over Extension

**Question:** Should we extend chirp-ui to handle stateful components, or build separately?

**Answer:** Neither! Use **layered composition** - chirp-ui provides templates, component framework provides state/logic.

## Architecture

```
┌────────────────────────────────────────────────────┐
│  Layer 3: Application (Sunwell, ChirpPad, etc.)    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                     │
│  Choice 1: Use chirp-ui templates directly         │
│  ┌────────────────────────────────────────────┐   │
│  │  {% from "chirpui/card.html" import card %}│   │
│  │  {% call card(title="Simple") %}           │   │
│  │    <p>No state needed</p>                  │   │
│  │  {% end %}                                  │   │
│  └────────────────────────────────────────────┘   │
│                                                     │
│  Choice 2: Create stateful components              │
│  ┌────────────────────────────────────────────┐   │
│  │  class ProjectCard(Component):             │   │
│  │    expanded: State[bool]                   │   │
│  │    def render():                           │   │
│  │      # Uses chirp-ui templates ↓           │   │
│  │      return template("""                   │   │
│  │        {% from "chirpui/card" %}           │   │
│  │      """)                                   │   │
│  └────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Layer 2: Component Framework (chirp.component)    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                     │
│  - Base Component class                            │
│  - State/Prop/Computed descriptors                 │
│  - ComponentRegistry                               │
│  - htmx endpoint generation                        │
│  - Lifecycle hooks                                 │
│  - Uses chirp-ui templates for rendering ↓         │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Layer 1: Template Library (chirp-ui)              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                     │
│  - Pure Kida template macros                       │
│  - card, badge, modal, table, spinner, etc.       │
│  - CSS themes (Holy Light, etc.)                  │
│  - No Python logic                                 │
│  - No state management                             │
│  - Standalone package: pip install chirp-ui       │
└────────────────────────────────────────────────────┘
```

## Benefits of Layering

### ✅ **No Duplication**
Components reuse chirp-ui templates instead of reimplementing HTML/CSS:

```python
class TaskList(Component):
    def render(self):
        return self.template("""
            {% from "chirpui/card.html" import card %}
            {% from "chirpui/badge.html" import badge %}

            {% call card(title="Tasks") %}
                {% for task in tasks %}
                    {{ badge(task.status, variant=task.color) }}
                {% end %}
            {% end %}
        """)
```

### ✅ **chirp-ui Stays Simple**
- No Python logic complexity
- No state management overhead
- Easy to install and use standalone
- Clear scope: just templates + CSS

### ✅ **Component Framework Stays Focused**
- No HTML/CSS duplication
- Focus on state management and htmx routing
- Delegates rendering to chirp-ui

### ✅ **Progressive Complexity**
Users can adopt incrementally:
1. Start with chirp-ui templates (no framework)
2. Add component framework when needed
3. Mix both approaches in same app

### ✅ **Clear Separation of Concerns**
- chirp-ui = Presentation layer (how things look)
- Component framework = Logic layer (how things behave)
- Application = Business logic (what things do)

## Code Examples

### Example 1: Simple Page (chirp-ui only)

```html
<!-- No Python components needed, just templates -->
{% from "chirpui/card.html" import card %}
{% from "chirpui/badge.html" import badge %}
{% from "chirpui/table.html" import table, row %}

<h1>Projects</h1>

{% for project in projects %}
    {% call card(title=project.name) %}
        <p>{{ project.description }}</p>
        {% if project.active %}
            {{ badge("Active", variant="success") }}
        {% end %}
    {% end %}
{% endfor %}

{% call table(headers=["Name", "Status"]) %}
    {% for project in projects %}
        {{ row(project.name, project.status) }}
    {% endfor %}
{% end %}
```

**Benefits:** Fast, simple, no framework overhead.

### Example 2: Stateful Component (chirp-ui + Component)

```python
# components/project_card.py
from chirp.component import Component, State, Prop

class ProjectCard(Component):
    """Interactive project card using chirp-ui templates."""

    # Props from parent
    project_id: Prop[str]
    name: Prop[str]
    description: Prop[str]

    # Internal state
    expanded: State[bool] = State(default=False)
    loading: State[bool] = State(default=False)
    valid: State[bool] = State(default=True)

    def render(self):
        """Render using chirp-ui components."""
        return self.template("""
            {% from "chirpui/card.html" import card %}
            {% from "chirpui/badge.html" import badge %}
            {% from "chirpui/spinner.html" import spinner %}
            {% from "chirpui/empty.html" import empty_state %}

            {# Use chirp-ui card with dynamic state #}
            {% call card(
                title=name,
                collapsible=true,
                open=expanded,
                cls="project-card {{ 'loading' if loading else '' }}"
            ) %}
                <p>{{ description }}</p>

                {# Status badges from chirp-ui #}
                {% if valid %}
                    {{ badge("Valid", variant="success", icon="✓") }}
                {% else %}
                    {{ badge("Invalid", variant="error", icon="⚠") }}
                {% end %}

                {# Expanded content #}
                {% if expanded %}
                    <div class="project-details">
                        <dl>
                            <dt>ID</dt>
                            <dd><code>{{ project_id }}</code></dd>
                            <dt>Status</dt>
                            <dd>{{ "Valid" if valid else "Invalid" }}</dd>
                        </dl>

                        {# Actions with htmx #}
                        <button hx-post="{{ component.url('validate') }}"
                                hx-target="#{{ component.id }}"
                                hx-swap="outerHTML">
                            {% if loading %}
                                {{ spinner(size="sm") }} Validating...
                            {% else %}
                                Validate Path
                            {% end %}
                        </button>
                    </div>
                {% end %}

                {# Toggle button #}
                <button hx-post="{{ component.url('toggle') }}"
                        hx-target="#{{ component.id }}"
                        hx-swap="outerHTML">
                    {{ "Collapse" if expanded else "Expand" }}
                </button>
            {% end %}
        """,
        project_id=self.project_id,
        name=self.name,
        description=self.description,
        expanded=self.expanded,
        loading=self.loading,
        valid=self.valid)

    async def toggle(self):
        """htmx action: toggle expanded state."""
        self.expanded = not self.expanded
        return self.render()

    async def validate(self):
        """htmx action: validate project path."""
        self.loading = True
        yield self.render()  # Show loading state

        # Async validation
        import asyncio
        await asyncio.sleep(1)  # Simulate API call
        self.valid = await check_project_path(self.project_id)

        self.loading = False
        yield self.render()  # Show result
```

**Usage in template:**
```html
{% component ProjectCard(
    project_id=project.id,
    name=project.name,
    description=project.description
) %}
```

**Benefits:**
- State management + async actions
- Still uses chirp-ui for all rendering
- No HTML/CSS duplication

### Example 3: Hybrid Approach

Mix both approaches in the same page:

```html
<!-- pages/projects/page.html -->
{% from "chirpui/card.html" import card %}
{% from "chirpui/badge.html" import badge %}
{% from "chirpui/empty.html" import empty_state %}

<div class="projects-page">
    <header class="page-header">
        <h1>Projects</h1>

        {# Simple badge - just use chirp-ui #}
        {{ badge(projects | length ~ " total", variant="primary") }}
    </header>

    {% if projects %}
        <div class="projects-grid">
            {% for project in projects %}
                {# Complex card - use Component #}
                {% component ProjectCard(
                    project_id=project.id,
                    name=project.name,
                    description=project.description
                ) %}
            {% endfor %}
        </div>
    {% else %}
        {# Empty state - just use chirp-ui #}
        {% call empty_state(icon="✧", title="No Projects") %}
            <p>Create your first project to get started.</p>
            <button class="btn">+ New Project</button>
        {% end %}
    {% end %}
</div>
```

**Benefits:** Use the right tool for each job.

## When to Use Each Layer

### Use **chirp-ui templates** directly when:
- ✅ No state needed (static display)
- ✅ Simple presentation (badges, cards, alerts)
- ✅ Rapid prototyping
- ✅ Non-interactive sections

**Example:** About pages, static lists, headers/footers

### Use **Component classes** when:
- ✅ Need persistent state (expanded, selected, filters)
- ✅ Complex interactions (multi-step forms, drag-drop)
- ✅ Async operations (loading states, API calls)
- ✅ Real-time updates (SSE, polling)
- ✅ Need to test logic separately

**Example:** Data tables, project cards, live dashboards

## Package Distribution

### chirp-ui (standalone package)
```bash
pip install chirp-ui
```

**Contains:**
- Template macros (card, badge, modal, etc.)
- CSS files (base + themes)
- No Python component framework
- Used by: anyone using Kida/Tornado templates

**Repo:** `/Users/llane/Documents/github/python/chirp-ui`

### chirp (main framework)
```bash
pip install chirp
```

**Contains:**
- HTTP server (Pounce/Kida integration)
- Page Convention routing
- **NEW: `chirp.component` module** (Component base class, registry, etc.)
- Already imports chirp-ui templates automatically

**Repo:** `/Users/llane/Documents/github/python/chirp`

### Application (Sunwell)
```bash
pip install chirp chirp-ui
```

**Contains:**
- Business logic
- Component subclasses (ProjectCard, TaskList, etc.)
- Pages using both chirp-ui and Components

## Implementation Plan

### Phase 1: chirp-ui Improvements (Week 1-2)
Focus on the template layer first:

**Add to chirp-ui:**
- [ ] Holy Light theme CSS
- [ ] Badge component template
- [ ] Spinner component template
- [ ] Empty state component template
- [ ] Progress bar component template
- [ ] Status indicator component template

**Ship it:** `chirp-ui v0.2.0`

### Phase 2: Start Using chirp-ui in Sunwell (Week 3)
Dogfood the templates:

**In Sunwell:**
- [ ] Install chirp-ui
- [ ] Replace custom badges with chirp-ui badges
- [ ] Replace custom cards with chirp-ui cards
- [ ] Replace custom modals with chirp-ui modals
- [ ] Use Holy Light theme

**Result:** Sunwell UI is now built on chirp-ui templates

### Phase 3: Add Component Framework to Chirp (Week 4-5)
Build the logic layer:

**Add to chirp package:**
- [ ] `chirp/component/base.py` - Base Component class
- [ ] `chirp/component/state.py` - State/Prop/Computed descriptors
- [ ] `chirp/component/registry.py` - ComponentRegistry
- [ ] `chirp/component/middleware.py` - htmx endpoint handler
- [ ] Tests and documentation

**Ship it:** `chirp v0.3.0`

### Phase 4: Create Stateful Components in Sunwell (Week 6+)
Use the new framework:

**In Sunwell:**
- [ ] Create `ProjectCard` component using chirp-ui templates
- [ ] Create `TaskList` component using chirp-ui templates
- [ ] Create `DataTable` component using chirp-ui templates
- [ ] Convert complex pages to use Components

**Result:** Sunwell has both simple (template-only) and complex (stateful) components

## Success Criteria

✅ **chirp-ui remains simple** - Still just templates + CSS, no Python framework code

✅ **No duplication** - Components use chirp-ui templates instead of custom HTML

✅ **Progressive adoption** - Can use chirp-ui without Components, or both together

✅ **Clear architecture** - Three distinct layers with clear responsibilities

✅ **Dogfood working** - Sunwell uses chirp-ui templates and Components in production

## Open Questions

1. **Component registration:** Auto-discover via decorators or explicit registry calls?
   ```python
   # Option A: Decorator
   @component
   class ProjectCard(Component):
       pass

   # Option B: Explicit
   registry.register(ProjectCard)
   ```

2. **Template syntax:** Special `{% component %}` tag or just function call?
   ```html
   <!-- Option A: Custom tag -->
   {% component ProjectCard(name="Test") %}

   <!-- Option B: Function call -->
   {{ ProjectCard(name="Test").render() }}
   ```

3. **State persistence:** Session-scoped by default? Database-backed option?

4. **Testing approach:** How to test Components that use chirp-ui templates?

## Conclusion

**Layered architecture gives us the best of both worlds:**

- chirp-ui = Simple, focused, widely reusable template library
- Component framework = Powerful state management when needed
- No duplication = Components use chirp-ui templates

Start with chirp-ui improvements, dogfood in Sunwell, then add Component framework if complex use cases emerge. This keeps things simple and avoids premature complexity.
