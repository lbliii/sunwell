# RFC-DRAFT: Chirp Component System

**Status:** Draft
**Created:** 2026-02-11
**Author:** Architecture Analysis

## Overview

Design a component and reactive state system for Chirp that embraces server-first rendering while providing the ergonomics of modern component frameworks. The goal is to make building interactive UIs as simple as React/Vue, but without shipping megabytes of JavaScript or rebuilding the wheel.

## Philosophy

**Server-first, progressively enhanced**
- Components render on the server, return HTML
- htmx handles reactivity via targeted server updates
- Optional client-side enhancement for rich interactions
- No build step, no bundler, no JSX compiler

**Embrace the platform**
- Use Python for logic, HTML for markup, htmx for interactivity
- Leverage native Web Components for client-side needs
- Work with Tornado's template system, don't fight it
- Keep it simple: components are just classes that render HTML

## Core Abstractions

### 1. Component Classes (Server-Side)

Components are Python classes that encapsulate:
- State management
- Rendering logic
- Event handling via htmx endpoints
- Lifecycle hooks

```python
# src/sunwell/interface/chirp/components/counter.py
from chirp.component import Component, State

class Counter(Component):
    """A simple counter component with increment/decrement."""

    # Declare reactive state
    count: State[int] = State(default=0)
    step: State[int] = State(default=1)

    def render(self) -> str:
        """Render the component to HTML."""
        return self.template("""
            <div class="counter" id="counter-{{ component.id }}">
                <div class="counter-display">
                    <span class="count">{{ count }}</span>
                </div>
                <div class="counter-controls">
                    <button hx-post="{{ component.url('decrement') }}"
                            hx-target="#counter-{{ component.id }}"
                            hx-swap="outerHTML">
                        -{{ step }}
                    </button>
                    <button hx-post="{{ component.url('increment') }}"
                            hx-target="#counter-{{ component.id }}"
                            hx-swap="outerHTML">
                        +{{ step }}
                    </button>
                </div>
            </div>
        """, count=self.count, step=self.step)

    # Component methods become htmx endpoints automatically
    async def increment(self):
        """Handle increment action."""
        self.count += self.step
        return self.render()

    async def decrement(self):
        """Handle decrement action."""
        self.count -= self.step
        return self.render()
```

**Usage in page:**
```html
{% from "components/counter.html" import Counter %}

<div class="card">
    <h3>Task Counter</h3>
    {{ Counter(count=5, step=1) }}
</div>
```

### 2. Component Registry & Routing

Components auto-register endpoints following a convention:

```
/_components/<component-name>/<instance-id>/<method>
```

Example:
```
POST /_components/counter/abc123/increment
POST /_components/task-list/xyz789/toggle-item?item_id=42
```

The registry handles:
- Component instance lifecycle (session-scoped, request-scoped, or persistent)
- State serialization/deserialization
- Automatic endpoint generation
- Security (CSRF, validation)

```python
# chirp/component/registry.py
class ComponentRegistry:
    """Global registry for component instances and routes."""

    def __init__(self):
        self._components: Dict[str, Type[Component]] = {}
        self._instances: Dict[str, Component] = {}

    def register(self, component_class: Type[Component]):
        """Register a component class."""
        name = component_class.__name__.lower()
        self._components[name] = component_class

    def create_instance(self, name: str, **props) -> Component:
        """Create a component instance with props."""
        component_class = self._components[name]
        instance = component_class(**props)
        self._instances[instance.id] = instance
        return instance

    def get_routes(self) -> List[Tuple[str, Callable]]:
        """Generate htmx endpoint routes for all components."""
        routes = []
        for name, component_class in self._components.items():
            # Auto-generate routes for component methods
            for method_name in component_class.get_actions():
                pattern = f"/_components/{name}/{{instance_id}}/{method_name}"
                routes.append((pattern, self._create_handler(name, method_name)))
        return routes
```

### 3. State Management

**State types:**
- `State[T]`: Reactive value, re-renders on change
- `Prop[T]`: Immutable value passed from parent
- `Computed[T]`: Derived value, cached until dependencies change
- `Effect`: Side effect that runs when dependencies change

```python
from chirp.component import Component, State, Prop, Computed

class TaskItem(Component):
    # Props (immutable, passed from parent)
    task_id: Prop[str]
    title: Prop[str]

    # State (mutable, triggers re-render)
    completed: State[bool] = State(default=False)
    editing: State[bool] = State(default=False)
    edit_value: State[str] = State(default="")

    # Computed (derived from other state)
    @Computed
    def status_class(self) -> str:
        return "task-completed" if self.completed else "task-pending"

    @Computed
    def can_save(self) -> bool:
        return self.editing and len(self.edit_value.strip()) > 0

    async def toggle_complete(self):
        """Toggle completion status."""
        self.completed = not self.completed
        # Could trigger server-side effects here
        await self.save_to_db()
        return self.render()

    async def start_editing(self):
        """Enter edit mode."""
        self.editing = True
        self.edit_value = self.title
        return self.render()

    async def save_edit(self, title: str):
        """Save edited title."""
        self.title = title  # Update prop (becomes new value)
        self.editing = False
        await self.save_to_db()
        return self.render()
```

### 4. Component Communication

**Parent → Child (Props):**
```python
class TaskList(Component):
    tasks: Prop[List[Dict]]

    def render(self):
        return self.template("""
            <div class="task-list">
                {% for task in tasks %}
                    {{ TaskItem(
                        task_id=task.id,
                        title=task.title,
                        completed=task.completed
                    ) }}
                {% endfor %}
            </div>
        """, tasks=self.tasks)
```

**Child → Parent (Events via htmx):**
```python
class TaskItem(Component):
    async def delete(self):
        """Delete task and notify parent."""
        # Delete from DB
        await self.delete_from_db()

        # Trigger parent list to re-render
        return Response(
            headers={
                "HX-Trigger": json.dumps({
                    "taskDeleted": {"task_id": self.task_id}
                })
            }
        )
```

Parent listens via htmx:
```html
<div class="task-list"
     hx-get="{{ component.url('refresh') }}"
     hx-trigger="taskDeleted from:body"
     hx-swap="outerHTML">
    <!-- tasks -->
</div>
```

**Sibling → Sibling (Event Bus):**
```python
# Via htmx events and SSE
class StatusBadge(Component):
    def render(self):
        return self.template("""
            <div class="status-badge"
                 hx-get="{{ component.url('refresh') }}"
                 hx-trigger="sse:status-changed"
                 hx-swap="outerHTML">
                {{ status }}
            </div>
        """)
```

### 5. Scoping Strategies

Components can have different lifecycles:

**Request-scoped (default):**
```python
class SearchResults(Component):
    """Ephemeral, created per request."""
    scope = ComponentScope.REQUEST
```

**Session-scoped:**
```python
class UserPreferences(Component):
    """Persists in session, survives page navigation."""
    scope = ComponentScope.SESSION
```

**Persistent:**
```python
class ProjectSettings(Component):
    """Backed by database, survives server restart."""
    scope = ComponentScope.PERSISTENT

    def save(self):
        """Persist state to DB."""
        db.save_component_state(self.id, self.to_dict())

    @classmethod
    def load(cls, component_id: str):
        """Load state from DB."""
        data = db.load_component_state(component_id)
        return cls.from_dict(data)
```

### 6. Template Macros (Simple Components)

For presentational components without logic, use Tornado template macros:

```html
{# components/badge.html #}
{% macro Badge(text, variant="primary", icon=None) %}
<span class="badge badge-{{ variant }}">
    {% if icon %}
        <span class="icon-{{ icon }}">{{ icon }}</span>
    {% end %}
    {{ text }}
</span>
{% end %}

{# Usage #}
{% from "components/badge.html" import Badge %}
{{ Badge("Active", variant="success", icon="✓") }}
```

For ultra-simple components, this is more ergonomic than full Component classes.

## Advanced Patterns

### 7. Optimistic Updates

```python
class TaskList(Component):
    tasks: State[List[Task]]

    async def add_task(self, title: str):
        """Add task with optimistic update."""
        # Create temporary task immediately
        temp_task = Task(id="temp-" + uuid4(), title=title, pending=True)
        self.tasks.append(temp_task)

        # Render with optimistic state
        html = self.render()

        # Save to server async
        real_task = await self.save_task(title)

        # Swap temp for real via htmx trigger
        return Response(
            html,
            headers={
                "HX-Trigger-After-Settle": json.dumps({
                    "taskCreated": {"temp_id": temp_task.id, "real_id": real_task.id}
                })
            }
        )
```

Client-side handler replaces temp with real:
```html
<script>
document.body.addEventListener('taskCreated', function(evt) {
    const detail = evt.detail;
    document.getElementById(detail.temp_id)?.setAttribute('id', detail.real_id);
});
</script>
```

### 8. Loading States

```python
class DataTable(Component):
    loading: State[bool] = State(default=False)
    data: State[List[Dict]] = State(default=[])

    def render(self):
        if self.loading:
            return self.template("""
                <div class="data-table loading">
                    <div class="spinner-thinking"></div>
                    <p>Loading data...</p>
                </div>
            """)

        return self.template("""
            <div class="data-table">
                <table>
                    {% for row in data %}
                        <tr>...</tr>
                    {% endfor %}
                </table>
                <button hx-get="{{ component.url('refresh') }}"
                        hx-indicator=".spinner">
                    Refresh
                </button>
            </div>
        """, data=self.data)

    async def refresh(self):
        self.loading = True
        # Show loading state immediately
        yield self.render()

        # Fetch data
        self.data = await fetch_data()
        self.loading = False

        # Render with data
        yield self.render()
```

### 9. Streaming Updates (SSE)

```python
class LogViewer(Component):
    """Stream log updates via Server-Sent Events."""

    def render(self):
        return self.template("""
            <div class="log-viewer"
                 hx-ext="sse"
                 sse-connect="{{ component.url('stream') }}"
                 sse-swap="log-entry"
                 hx-swap="beforeend">
                <div class="log-entries">
                    <!-- Entries streamed here -->
                </div>
            </div>
        """)

    async def stream(self):
        """Stream log entries as they arrive."""
        async for log_entry in self.tail_logs():
            yield f"event: log-entry\ndata: {self.render_entry(log_entry)}\n\n"
```

### 10. Composition & Slots

```python
class Card(Component):
    """Container component with slots."""

    title: Prop[str]
    header_slot: Prop[str] = ""
    footer_slot: Prop[str] = ""

    def render(self):
        return self.template("""
            <div class="card">
                <div class="card-header">
                    {{ header_slot | safe }}
                    <h3>{{ title }}</h3>
                </div>
                <div class="card-body">
                    {{ children | safe }}
                </div>
                {% if footer_slot %}
                    <div class="card-footer">
                        {{ footer_slot | safe }}
                    </div>
                {% end %}
            </div>
        """, title=self.title, header_slot=self.header_slot,
             footer_slot=self.footer_slot, children=self.children)

# Usage with nested components
Card(
    title="Task Statistics",
    header_slot=Badge("Live", variant="success"),
    footer_slot='<button class="btn">View All</button>'
).wrap(
    TaskStats(project_id="abc123")
)
```

## Implementation Sketch

### Base Component Class

```python
# chirp/component/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, ClassVar
from uuid import uuid4
import json

class ComponentScope(Enum):
    REQUEST = "request"
    SESSION = "session"
    PERSISTENT = "persistent"

class Component(ABC):
    """Base class for all Chirp components."""

    scope: ClassVar[ComponentScope] = ComponentScope.REQUEST

    def __init__(self, **props):
        self.id = f"{self.__class__.__name__.lower()}-{uuid4().hex[:8]}"
        self._props = props
        self._state = {}
        self._init_state()

    def _init_state(self):
        """Initialize state fields from class annotations."""
        for name, field_type in self.__annotations__.items():
            if isinstance(field_type, State):
                self._state[name] = field_type.default

    def template(self, template_str: str, **context) -> str:
        """Render a template string with context."""
        from tornado.template import Template
        t = Template(template_str)
        return t.generate(component=self, **context).decode('utf-8')

    @abstractmethod
    def render(self) -> str:
        """Render the component to HTML."""
        pass

    def url(self, action: str, **params) -> str:
        """Generate URL for component action."""
        base = f"/_components/{self.__class__.__name__.lower()}/{self.id}/{action}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            return f"{base}?{query}"
        return base

    @classmethod
    def get_actions(cls) -> List[str]:
        """Get list of component action methods."""
        return [
            name for name in dir(cls)
            if not name.startswith('_')
            and callable(getattr(cls, name))
            and name not in ['render', 'url', 'get_actions', 'template']
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize component state."""
        return {
            'id': self.id,
            'class': self.__class__.__name__,
            'props': self._props,
            'state': self._state
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Deserialize component state."""
        instance = cls(**data['props'])
        instance.id = data['id']
        instance._state = data['state']
        return instance
```

### State Descriptor

```python
# chirp/component/state.py
class State:
    """Reactive state field descriptor."""

    def __init__(self, default=None):
        self.default = default
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj._state.get(self.name, self.default)

    def __set__(self, obj, value):
        obj._state[self.name] = value
        # Could trigger re-render here in future
```

### Component Middleware

```python
# chirp/component/middleware.py
class ComponentMiddleware:
    """Middleware to handle component requests."""

    def __init__(self, registry: ComponentRegistry):
        self.registry = registry

    async def __call__(self, request: Request, call_next):
        # Check if this is a component request
        if request.path.startswith('/_components/'):
            return await self.handle_component_request(request)

        # Otherwise pass through
        return await call_next(request)

    async def handle_component_request(self, request: Request):
        # Parse: /_components/<component>/<instance_id>/<action>
        parts = request.path.split('/')[2:]  # Skip empty and '_components'
        component_name, instance_id, action = parts

        # Get or create component instance
        component = self.registry.get_instance(instance_id)
        if not component:
            return Response("Component not found", status=404)

        # Call action method
        method = getattr(component, action, None)
        if not method or not callable(method):
            return Response("Action not found", status=404)

        # Execute action (may be async)
        result = await method(**request.query_params) if asyncio.iscoroutinefunction(method) else method(**request.query_params)

        # Return HTML response
        return Response(result, media_type="text/html")
```

## Integration with Chirp

### App Setup

```python
# src/sunwell/interface/chirp/app.py
from chirp import Chirp
from chirp.component import ComponentRegistry, ComponentMiddleware

# Create app
app = Chirp(__name__)

# Setup component system
component_registry = ComponentRegistry()
app.middleware.append(ComponentMiddleware(component_registry))

# Auto-discover and register components
from sunwell.interface.chirp.components import *
component_registry.auto_discover('sunwell.interface.chirp.components')

# Component routes are automatically registered by middleware
```

### Page Integration

```python
# src/sunwell/interface/chirp/pages/projects/page.py
from chirp.page import PageHandler
from sunwell.interface.chirp.components import ProjectCard, TaskList

class ProjectsPage(PageHandler):
    async def get(self):
        projects = await self.load_projects()

        self.render('projects/page.html',
                   projects=projects,
                   TaskList=TaskList,
                   ProjectCard=ProjectCard)
```

```html
<!-- src/sunwell/interface/chirp/pages/projects/page.html -->
{% block content %}
<div class="projects-container">
    {% for project in projects %}
        {{ ProjectCard(
            project_id=project.id,
            name=project.name,
            description=project.description
        ) }}
    {% endfor %}
</div>
{% end %}
```

## Client-Side Enhancement (Optional)

For rich client-side interactivity, use Web Components:

```javascript
// src/sunwell/interface/chirp/pages/static/js/components/rich-editor.js
class RichEditor extends HTMLElement {
    connectedCallback() {
        this.innerHTML = `
            <div class="rich-editor">
                <div class="toolbar">
                    <button data-action="bold">B</button>
                    <button data-action="italic">I</button>
                </div>
                <div contenteditable="true" class="editor-content"></div>
            </div>
        `;

        this.setupToolbar();
    }

    setupToolbar() {
        this.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.execCommand(btn.dataset.action);
            });
        });
    }
}

customElements.define('rich-editor', RichEditor);
```

Use in component:
```python
class DocumentEditor(Component):
    def render(self):
        return self.template("""
            <div class="document-editor">
                <rich-editor>{{ content }}</rich-editor>
                <button hx-post="{{ component.url('save') }}"
                        hx-include="rich-editor .editor-content">
                    Save
                </button>
            </div>
        """, content=self.content)
```

## Benefits

1. **Familiar DX**: Component-based like React/Vue, but server-first
2. **No build step**: Plain Python + HTML + htmx, no bundler needed
3. **Progressive**: Start with simple macros, upgrade to full components as needed
4. **Type-safe**: Python type hints for props and state
5. **Testable**: Components are just Python classes
6. **Debuggable**: Server-side rendering = view source works
7. **Performant**: No JS frameworks, minimal client-side overhead
8. **Scalable**: Components compose naturally, clear boundaries

## Trade-offs

**Pros:**
- Server controls rendering (security, consistency)
- Less client-side complexity
- Works without JavaScript
- Easy to reason about data flow

**Cons:**
- Network latency for every interaction (mitigated by htmx caching)
- Can't do offline-first easily
- Limited animations (CSS only, or Web Components)
- Need to manage component lifecycle on server

## Next Steps

1. **Prototype base Component class** with State management
2. **Build ComponentRegistry** with auto-routing
3. **Create 3-5 example components** (Counter, TaskList, DataTable, Form)
4. **Add to Chirp core** as optional feature
5. **Document patterns** for common use cases
6. **Performance testing** with many components

## Open Questions

1. **State persistence**: How long do session-scoped components live?
2. **Memory management**: When to garbage collect component instances?
3. **Security**: How to prevent tampering with component IDs?
4. **Validation**: Should components validate their own props?
5. **Testing**: What's the best way to test component interactions?
6. **Nesting**: How deep can component trees go before performance suffers?

---

**Thoughts?** This gives us React/Vue-like ergonomics while staying true to Chirp's server-first philosophy. The key insight is that htmx already handles reactivity—we just need to make it easier to organize code into reusable, stateful components.
