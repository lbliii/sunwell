# Chirp Component Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Client)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   HTML/CSS   │      │     htmx     │      │ Web Components│  │
│  │              │◄─────┤  (reactivity)│      │   (optional)  │  │
│  │  Rendered    │      │              │      │               │  │
│  │  Components  │      │  - hx-post   │      │  - rich-editor│  │
│  │              │      │  - hx-swap   │      │  - chart      │  │
│  └──────────────┘      │  - hx-sse    │      │  - calendar   │  │
│                        └──────────────┘      └──────────────┘  │
│                               │                                  │
└───────────────────────────────┼──────────────────────────────────┘
                                │
                                │ HTTP/SSE
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│                       Server (Chirp + Tornado)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              ComponentMiddleware                            │ │
│  │  Routes: /_components/{name}/{id}/{action}                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                               │                                  │
│  ┌────────────────────────────▼──────────────────────────────┐ │
│  │              ComponentRegistry                             │ │
│  │  - Component classes                                       │ │
│  │  - Active instances (session-scoped, persistent, etc)      │ │
│  │  - State serialization                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                               │                                  │
│  ┌────────────────────────────▼──────────────────────────────┐ │
│  │                 Component Instances                        │ │
│  │                                                            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │ ProjectCard  │  │  TaskList    │  │  DataTable   │   │ │
│  │  │              │  │              │  │              │   │ │
│  │  │ Props:       │  │ Props:       │  │ Props:       │   │ │
│  │  │  - id        │  │  - tasks     │  │  - columns   │   │ │
│  │  │  - name      │  │              │  │  - rows      │   │ │
│  │  │              │  │ State:       │  │              │   │ │
│  │  │ State:       │  │  - filter    │  │ State:       │   │ │
│  │  │  - expanded  │  │  - sortBy    │  │  - page      │   │ │
│  │  │  - valid     │  │              │  │  - sortBy    │   │ │
│  │  │              │  │ Methods:     │  │              │   │ │
│  │  │ Methods:     │  │  - toggle()  │  │ Methods:     │   │ │
│  │  │  - expand()  │  │  - add()     │  │  - sort()    │   │ │
│  │  │  - delete()  │  │  - remove()  │  │  - paginate()│   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                               │                                  │
│  ┌────────────────────────────▼──────────────────────────────┐ │
│  │                    State Store                             │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │ │
│  │  │  Session   │  │  Database  │  │   Memory   │          │ │
│  │  │  (Redis)   │  │ (SQLite)   │  │  (Dict)    │          │ │
│  │  └────────────┘  └────────────┘  └────────────┘          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## Request Flow

### Standard Component Action

```
User clicks button
    │
    └──► htmx intercepts click
            │
            └──► POST /_components/project-card/abc123/delete
                    │
                    └──► ComponentMiddleware
                            │
                            ├──► Parse URL (component=project-card, id=abc123, action=delete)
                            │
                            └──► ComponentRegistry.get_instance(abc123)
                                    │
                                    └──► ProjectCard instance
                                            │
                                            ├──► await delete() method
                                            │       │
                                            │       ├──► Delete from database
                                            │       │
                                            │       └──► Return HTML (empty) + HX-Trigger event
                                            │
                                            └──► Response(html, headers)
                                                    │
                                                    └──► htmx receives response
                                                            │
                                                            ├──► Swaps out element (removes card)
                                                            │
                                                            └──► Triggers "projectDeleted" event
                                                                    │
                                                                    └──► Other components listening refresh themselves
```

### Streaming Component (SSE)

```
Component renders with sse-connect
    │
    └──► Browser opens SSE connection
            │
            └──► GET /_components/log-viewer/abc123/stream
                    │
                    └──► ComponentMiddleware
                            │
                            └──► LogViewer.stream() generator
                                    │
                                    └──► async for event in tail_logs():
                                            │
                                            ├──► yield "event: log-entry\n"
                                            │
                                            └──► htmx receives event
                                                    │
                                                    └──► Appends new log entry to DOM
```

## State Lifecycle

### Request-Scoped Component

```python
# Created fresh on each page load
class SearchResults(Component):
    scope = ComponentScope.REQUEST

# Timeline:
#   Page load → Component created → Render → Action → Re-render → Request ends → Destroyed
```

### Session-Scoped Component

```python
# Persists across page loads for user's session
class ShoppingCart(Component):
    scope = ComponentScope.SESSION

# Timeline:
#   First use → Component created → Saved to session
#   Next page → Loaded from session → Render → Action → Save to session
#   Session expires → Destroyed
```

### Persistent Component

```python
# Survives server restarts, backed by database
class UserDashboard(Component):
    scope = ComponentScope.PERSISTENT

    def save(self):
        db.save_component_state(self.id, self.to_dict())

    @classmethod
    def load(cls, component_id: str):
        data = db.load_component_state(component_id)
        return cls.from_dict(data)

# Timeline:
#   First use → Component created → Saved to DB
#   Server restart → [components cleared from memory]
#   Next load → Loaded from DB → Render → Action → Save to DB
```

## Comparison with Other Approaches

### vs. Traditional Server Rendering (PHP, Django, Rails)

| Aspect | Traditional | Chirp Components |
|--------|------------|------------------|
| State | Lost on each request | Preserved (session/persistent) |
| Reactivity | Full page reload | htmx swaps HTML fragments |
| Reusability | Partials/includes | Component classes + props |
| Type Safety | Templates are strings | Python type hints |
| Testing | Integration tests | Unit test component classes |

### vs. SPA Frameworks (React, Vue, Svelte)

| Aspect | SPA Framework | Chirp Components |
|--------|---------------|------------------|
| Initial Load | Large JS bundle (100-500KB) | HTML only (~10KB) |
| Interactivity | Client-side JS | Server-side Python + htmx |
| SEO | Needs SSR setup | Native (HTML from server) |
| Build Step | Required (webpack/vite) | None |
| Debugging | Source maps, React DevTools | View source, server logs |
| Offline | Can work offline | Requires network |

### vs. htmx alone (no components)

| Aspect | Plain htmx | Chirp Components |
|--------|------------|------------------|
| Organization | Routes + templates | Component classes |
| State | URL params or hidden inputs | Component state fields |
| Reusability | Copy-paste templates | Import component class |
| Composition | Template includes | Component nesting |
| Type Safety | None | Python type hints |
| Testing | Full integration | Unit test components |

### vs. Web Components (Custom Elements)

| Aspect | Web Components | Chirp Components |
|--------|----------------|------------------|
| Execution | Client-side JS | Server-side Python |
| Initial Render | After JS loads | Immediate (SSR) |
| State | Client-side only | Server-managed |
| Security | Trust client | Server validates |
| Language | JavaScript | Python |
| **Best For** | Rich client widgets | Business logic + rendering |

**Hybrid approach:**
```python
class RichTextEditor(Component):
    """Server component that wraps a Web Component."""

    def render(self):
        return self.template("""
            <div class="editor-wrapper">
                <!-- Server-rendered toolbar -->
                <div class="toolbar">
                    <button hx-post="{{ component.url('save') }}">Save</button>
                    <span class="autosave-indicator">{{ status }}</span>
                </div>

                <!-- Client-side rich editing -->
                <rich-editor content="{{ content }}"></rich-editor>
            </div>
        """)

    async def save(self):
        # Server handles persistence
        await self.persist_content()
        return self.render()
```

## Design Patterns

### 1. Container/Presentational Split

```python
# Container: handles data + logic
class ProjectListContainer(Component):
    async def get_projects(self):
        return await db.query("SELECT * FROM projects")

    def render(self):
        projects = await self.get_projects()
        return self.template("""
            <div class="project-list">
                {% for project in projects %}
                    {{ ProjectCard(project=project) }}
                {% endfor %}
            </div>
        """)

# Presentational: pure rendering
class ProjectCard(Component):
    project: Prop[Project]

    def render(self):
        return self.template("""
            <div class="card">
                <h3>{{ project.name }}</h3>
                <p>{{ project.description }}</p>
            </div>
        """)
```

### 2. Higher-Order Components

```python
def with_loading(component_class):
    """HOC that adds loading state to any component."""

    class LoadingWrapper(component_class):
        loading: State[bool] = State(default=False)

        def render(self):
            if self.loading:
                return '<div class="spinner-thinking"></div>'
            return super().render()

        async def __call_action__(self, action_name, *args, **kwargs):
            self.loading = True
            yield self.render()

            result = await super().__call_action__(action_name, *args, **kwargs)

            self.loading = False
            yield result

    return LoadingWrapper

@with_loading
class DataTable(Component):
    # Now automatically shows loading state for all actions
    pass
```

### 3. Render Props Pattern

```python
class DataFetcher(Component):
    """Fetches data and passes to child renderer."""

    url: Prop[str]
    render_child: Prop[Callable]

    async def fetch_data(self):
        response = await http.get(self.url)
        return response.json()

    def render(self):
        data = await self.fetch_data()
        return self.render_child(data)

# Usage
DataFetcher(
    url="/api/projects",
    render_child=lambda projects: ProjectList(projects=projects)
)
```

### 4. Context/Provider Pattern

```python
# Component context for dependency injection
class ComponentContext:
    def __init__(self):
        self._values = {}

    def provide(self, key: str, value: Any):
        self._values[key] = value

    def inject(self, key: str) -> Any:
        return self._values.get(key)

# Usage
class ProjectCard(Component):
    def __init__(self, **props):
        super().__init__(**props)
        self.db = self.context.inject('database')
        self.auth = self.context.inject('auth')

# Setup
context = ComponentContext()
context.provide('database', DatabaseConnection())
context.provide('auth', AuthService())
```

## Performance Optimization

### 1. Memoization

```python
class ExpensiveComponent(Component):
    data: Prop[List[Dict]]

    @lru_cache(maxsize=128)
    def process_data(self, data_hash: str) -> List[Dict]:
        """Expensive computation, cached by data hash."""
        # Heavy processing here
        return processed_data

    def render(self):
        data_hash = hash(json.dumps(self.data))
        processed = self.process_data(data_hash)
        return self.template("""...""", data=processed)
```

### 2. Lazy Loading

```python
class LazyDataTable(Component):
    """Loads data on-demand, not at render time."""

    def render(self):
        return self.template("""
            <div class="data-table"
                 hx-get="{{ component.url('load_data') }}"
                 hx-trigger="intersect once"
                 hx-swap="innerHTML">
                <div class="spinner"></div>
            </div>
        """)

    async def load_data(self):
        data = await fetch_large_dataset()
        return self.render_table(data)
```

### 3. Partial Updates

```python
class TaskList(Component):
    tasks: State[List[Task]]

    async def toggle_task(self, task_id: str):
        """Update only the changed task, not entire list."""
        task = next(t for t in self.tasks if t.id == task_id)
        task.completed = not task.completed

        # Return only the updated task HTML
        return self.template("""
            <div class="task-item" id="task-{{ task.id }}">
                <input type="checkbox" {{ "checked" if task.completed else "" }}>
                <span class="{{ 'completed' if task.completed else '' }}">
                    {{ task.title }}
                </span>
            </div>
        """, task=task)
```

## Testing Strategy

### Unit Tests

```python
def test_project_card_expand():
    card = ProjectCard(
        project_id="test123",
        name="Test Project",
        root="/path/to/project"
    )

    assert not card.expanded

    # Test action
    html = await card.toggle_expand()

    assert card.expanded
    assert "project-details" in html
```

### Integration Tests

```python
async def test_project_card_delete_flow():
    # Setup
    app = create_test_app()
    client = TestClient(app)

    # Create project
    project = await create_test_project()

    # Render card
    card = ProjectCard(project_id=project.id, name=project.name, root=project.root)
    card_html = card.render()

    # Extract delete URL
    delete_url = extract_url(card_html, 'delete')

    # Send delete request
    response = await client.delete(delete_url)

    assert response.status_code == 200
    assert response.html == ""  # Card removed
    assert "projectDeleted" in response.headers["HX-Trigger"]

    # Verify project deleted from DB
    assert not await project_exists(project.id)
```

### Visual Regression Tests

```python
def test_project_card_visual():
    card = ProjectCard(project_id="test", name="Test", root="/path")

    # Render in different states
    html_normal = card.render()
    card.expanded = True
    html_expanded = card.render()
    card.valid = False
    html_invalid = card.render()

    # Take screenshots
    screenshot(html_normal, "project-card-normal.png")
    screenshot(html_expanded, "project-card-expanded.png")
    screenshot(html_invalid, "project-card-invalid.png")

    # Compare with baseline
    assert images_match("project-card-normal.png", "baseline/normal.png")
```

## Summary

Chirp components provide:

✅ **Server-first architecture** - Business logic stays on the server
✅ **Component model** - Familiar React/Vue-like patterns
✅ **Type safety** - Python type hints for props and state
✅ **Progressive enhancement** - Works without JavaScript
✅ **htmx integration** - Natural reactivity without frameworks
✅ **Zero build step** - Write Python + HTML, deploy
✅ **SEO friendly** - Pure HTML server rendering
✅ **Testable** - Components are just Python classes

Best of both worlds: modern component architecture + server simplicity.
