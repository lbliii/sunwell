# Chirp Component System - Concrete Example

## Real-World Example: Project Card Component

Let's build a real component for Sunwell's project list with full interactivity.

### The Component

```python
# src/sunwell/interface/chirp/components/project_card.py
from chirp.component import Component, State, Prop, Computed
from typing import Optional
from datetime import datetime

class ProjectCard(Component):
    """Interactive project card with status, actions, and live updates."""

    # Props (passed from parent, immutable)
    project_id: Prop[str]
    name: Prop[str]
    root: Prop[str]
    is_default: Prop[bool] = Prop(default=False)
    last_used: Prop[Optional[datetime]] = Prop(default=None)

    # State (internal, mutable, triggers re-render)
    valid: State[bool] = State(default=True)
    error_message: State[Optional[str]] = State(default=None)
    expanded: State[bool] = State(default=False)
    loading: State[bool] = State(default=False)

    # Computed properties
    @Computed
    def status_class(self) -> str:
        if not self.valid:
            return "project-invalid"
        if self.is_default:
            return "project-default"
        return "project-normal"

    @Computed
    def last_used_display(self) -> str:
        if not self.last_used:
            return "Never used"
        delta = datetime.now() - self.last_used
        if delta.days == 0:
            return "Today"
        elif delta.days == 1:
            return "Yesterday"
        else:
            return f"{delta.days} days ago"

    def render(self) -> str:
        """Render the complete project card."""
        return self.template("""
            <div class="project-card card {{ status_class }}"
                 id="{{ component.id }}"
                 hx-ext="sse"
                 sse-connect="/_components/project-card/{{ component.id }}/stream">

                {# Header #}
                <div class="project-header">
                    <div class="project-info">
                        <h3 class="project-name">
                            <a href="/projects/{{ project_id }}">{{ name }}</a>
                        </h3>

                        {# Badges #}
                        <div class="project-badges">
                            {% if is_default %}
                                <span class="badge badge-primary">
                                    <span class="icon-radiant">✦</span> Default
                                </span>
                            {% end %}

                            {% if not valid %}
                                <span class="badge badge-error">
                                    <span class="icon-error">⚠</span> Invalid
                                </span>
                            {% end %}
                        </div>
                    </div>

                    {# Actions Menu #}
                    <button class="btn-icon"
                            hx-post="{{ component.url('toggle_expand') }}"
                            hx-target="#{{ component.id }}"
                            hx-swap="outerHTML">
                        {{ "◆" if expanded else "◇" }}
                    </button>
                </div>

                {# Path Display #}
                <div class="project-path">
                    <code>{{ root }}</code>
                </div>

                {# Error Display #}
                {% if not valid and error_message %}
                    <div class="project-error">
                        <span class="icon-error">⚠</span>
                        <span>{{ error_message }}</span>
                    </div>
                {% end %}

                {# Expanded Details #}
                {% if expanded %}
                    <div class="project-details">
                        <dl class="project-meta">
                            <dt>ID</dt>
                            <dd><code>{{ project_id }}</code></dd>

                            <dt>Last Used</dt>
                            <dd>{{ last_used_display }}</dd>

                            <dt>Tasks</dt>
                            <dd>
                                <span hx-get="{{ component.url('get_task_count') }}"
                                      hx-trigger="load, sse:task-updated"
                                      hx-swap="innerHTML">
                                    Loading...
                                </span>
                            </dd>
                        </dl>

                        <div class="project-actions">
                            {% if not is_default and valid %}
                                <button class="btn btn-sm"
                                        hx-post="{{ component.url('set_default') }}"
                                        hx-target="#{{ component.id }}"
                                        hx-swap="outerHTML">
                                    Set as Default
                                </button>
                            {% end %}

                            <button class="btn btn-sm btn-ghost"
                                    hx-post="{{ component.url('validate_path') }}"
                                    hx-target="#{{ component.id }}"
                                    hx-swap="outerHTML">
                                <span class="htmx-indicator spinner"></span>
                                Validate Path
                            </button>

                            <button class="btn btn-sm btn-error"
                                    hx-delete="{{ component.url('delete') }}"
                                    hx-confirm="Delete project '{{ name }}'?"
                                    hx-target="#{{ component.id }}"
                                    hx-swap="outerHTML swap:1s">
                                Delete
                            </button>
                        </div>
                    </div>
                {% end %}
            </div>

            <style>
            .project-card { transition: all 0.3s ease; }
            .project-card.project-invalid { opacity: 0.7; border-color: var(--color-void-purple); }
            .project-card.project-default { border-left: 3px solid var(--color-radiant); }
            </style>
        """,
            component=self,
            project_id=self.project_id,
            name=self.name,
            root=self.root,
            is_default=self.is_default,
            valid=self.valid,
            error_message=self.error_message,
            expanded=self.expanded,
            status_class=self.status_class,
            last_used_display=self.last_used_display
        )

    # ============================================
    # Component Actions (become htmx endpoints)
    # ============================================

    async def toggle_expand(self):
        """Toggle expanded details view."""
        self.expanded = not self.expanded
        return self.render()

    async def set_default(self):
        """Set this project as default."""
        from sunwell.core.projects import ProjectManager

        # Update in database
        pm = ProjectManager()
        await pm.set_default_project(self.project_id)

        # Update component state
        self.is_default = True

        # Trigger other project cards to update
        return Response(
            self.render(),
            headers={
                "HX-Trigger": json.dumps({
                    "projectDefaultChanged": {
                        "project_id": self.project_id
                    }
                })
            }
        )

    async def validate_path(self):
        """Validate that project path exists."""
        import os

        self.loading = True
        yield self.render()  # Show loading state

        # Check path
        exists = os.path.exists(self.root)
        self.valid = exists
        self.error_message = None if exists else f"Path not found: {self.root}"
        self.loading = False

        yield self.render()  # Show result

    async def delete(self):
        """Delete this project."""
        from sunwell.core.projects import ProjectManager

        pm = ProjectManager()
        await pm.delete_project(self.project_id)

        # Return empty (removes card with swap animation)
        return Response(
            "",
            headers={
                "HX-Trigger": json.dumps({
                    "projectDeleted": {"project_id": self.project_id}
                })
            }
        )

    async def get_task_count(self):
        """Get current task count for project."""
        from sunwell.core.tasks import TaskManager

        tm = TaskManager()
        count = await tm.count_tasks(self.project_id)

        return f"""
            <span class="task-count">
                {count} task{"s" if count != 1 else ""}
            </span>
        """

    async def stream(self):
        """Stream live updates for this project."""
        # Subscribe to project events
        async for event in self.subscribe_to_project_events():
            if event.type == "task_updated":
                # Trigger task count refresh
                yield f"event: task-updated\ndata: {event.task_id}\n\n"

            elif event.type == "path_changed":
                # Update path and validate
                self.root = event.new_path
                await self.validate_path()
                yield f"event: refresh\ndata: {self.render()}\n\n"
```

### Usage in Page

```python
# src/sunwell/interface/chirp/pages/projects/page.py
from chirp.page import PageHandler
from sunwell.interface.chirp.components.project_card import ProjectCard

class ProjectsPage(PageHandler):
    async def get(self):
        from sunwell.core.projects import ProjectManager

        pm = ProjectManager()
        projects = await pm.list_projects()

        self.render('projects/page.html', projects=projects)
```

```html
<!-- src/sunwell/interface/chirp/pages/projects/page.html -->
{% block content %}
<div class="projects-container">
    <header class="page-header mb-lg">
        <h1><span class="icon-radiant">✦</span> Projects</h1>
        <button class="btn btn-primary"
                hx-get="/projects/new-form"
                hx-target="#modal-container">
            + New Project
        </button>
    </header>

    {% if projects %}
        <div class="projects-grid"
             hx-get="{{ url_for('projects_refresh') }}"
             hx-trigger="projectDeleted from:body, projectDefaultChanged from:body"
             hx-swap="innerHTML">

            {% for project in projects %}
                {% component ProjectCard(
                    project_id=project.id,
                    name=project.name,
                    root=project.root,
                    is_default=project.is_default,
                    last_used=project.last_used
                ) %}
            {% endfor %}
        </div>
    {% else %}
        <div class="empty-state card">
            <div class="empty-state-icon">✧</div>
            <h2>No Projects Yet</h2>
            <p class="text-muted">Create your first project to get started</p>
        </div>
    {% end %}
</div>

<div id="modal-container"></div>
{% end %}
```

## What This Gives Us

### 1. **Encapsulation**
All project card logic lives in one place:
- Rendering
- State management
- Event handling
- Validation logic

### 2. **Reusability**
Use the same component anywhere:
```html
{# Dashboard #}
{{ ProjectCard(project_id="abc", name="My Project", ...) }}

{# Search results #}
{{ ProjectCard(project_id="xyz", name="Found Project", ...) }}

{# Sidebar #}
{{ ProjectCard(project_id="def", name="Recent Project", ...) }}
```

### 3. **Testability**
Test components in isolation:
```python
def test_project_card_validation():
    card = ProjectCard(
        project_id="test",
        name="Test Project",
        root="/nonexistent/path"
    )

    await card.validate_path()

    assert not card.valid
    assert "Path not found" in card.error_message
```

### 4. **Type Safety**
```python
# This works
card = ProjectCard(project_id="abc", name="Test", root="/path")

# This fails at type check time
card = ProjectCard(project_id=123, name="Test")  # Error: project_id should be str
```

### 5. **Live Updates**
Components can stream updates:
```python
# Task completed → project card updates task count automatically
# Path changed → project card validates and updates automatically
# Default changed → all project cards update their badges
```

### 6. **Progressive Enhancement**
Works without JavaScript:
```html
<form action="/_components/project-card/abc123/set_default" method="POST">
    <button type="submit">Set as Default</button>
</form>
```

With htmx, it's AJAX and swaps in-place.

## Component Composition Example

Build complex UIs from simple components:

```python
class ProjectGrid(Component):
    """Container component for project cards."""

    projects: Prop[List[Project]]
    sort_by: State[str] = State(default="name")
    filter_invalid: State[bool] = State(default=False)

    @Computed
    def sorted_projects(self) -> List[Project]:
        projects = self.projects
        if self.filter_invalid:
            projects = [p for p in projects if p.valid]
        return sorted(projects, key=lambda p: getattr(p, self.sort_by))

    def render(self):
        return self.template("""
            <div class="project-grid">
                {# Toolbar #}
                <div class="grid-toolbar">
                    <select hx-post="{{ component.url('change_sort') }}"
                            hx-target="#{{ component.id }}"
                            name="sort_by">
                        <option value="name">Name</option>
                        <option value="last_used">Last Used</option>
                    </select>

                    <label>
                        <input type="checkbox"
                               hx-post="{{ component.url('toggle_filter') }}"
                               hx-target="#{{ component.id }}"
                               {% if filter_invalid %}checked{% end %}>
                        Hide invalid projects
                    </label>
                </div>

                {# Project Cards #}
                <div class="projects-grid">
                    {% for project in sorted_projects %}
                        {{ ProjectCard(
                            project_id=project.id,
                            name=project.name,
                            root=project.root,
                            is_default=project.is_default,
                            last_used=project.last_used
                        ) }}
                    {% endfor %}
                </div>
            </div>
        """, sorted_projects=self.sorted_projects)

    async def change_sort(self, sort_by: str):
        self.sort_by = sort_by
        return self.render()

    async def toggle_filter(self):
        self.filter_invalid = not self.filter_invalid
        return self.render()
```

Now your page is simple:
```html
{% block content %}
{{ ProjectGrid(projects=all_projects) }}
{% end %}
```

## Performance Characteristics

**Network requests:**
- Initial render: 1 request (page load)
- Toggle expand: 1 request
- Set default: 1 request + event broadcast
- Validate: 2 requests (loading state + result)
- Delete: 1 request + event broadcast

**Compared to SPA:**
- SPA: Load entire app (~500KB JS) + data fetching
- Chirp components: ~5-10KB per interaction, no framework overhead

**Server load:**
- Each component action is a lightweight Python function call
- State stored in session (Redis) or memory
- Can handle 1000s of concurrent component instances

## Migration Path

**Phase 1: Template Macros** (Week 1)
- Start with simple presentational components as macros
- Badge, Icon, Button, Card, EmptyState

**Phase 2: Stateful Components** (Week 2-3)
- Build Component base class
- Convert ProjectCard to full component
- Add ComponentRegistry and routing

**Phase 3: Complex Components** (Week 4-5)
- TaskList with drag-drop reordering
- DataTable with sorting/filtering
- Form components with validation

**Phase 4: Real-time Features** (Week 6+)
- SSE streaming for live updates
- Optimistic updates for instant feedback
- Multi-user collaboration (via SSE broadcast)

## Summary

This component system gives us:
- **React-like DX** (components, props, state, computed)
- **htmx-native reactivity** (server renders, htmx swaps)
- **No build step** (pure Python + HTML)
- **Type-safe** (Python type hints)
- **Progressive** (works without JS)
- **Testable** (components are just Python classes)

It's the best of both worlds: modern component architecture + server-first simplicity.
