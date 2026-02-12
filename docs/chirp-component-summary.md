# Chirp Component System - Summary

## TL;DR

A **server-first component system** for Chirp that gives you React-like developer experience without shipping JavaScript frameworks. Components are Python classes that manage state and render HTML, with htmx handling all the reactivity.

```python
class Counter(Component):
    count: State[int] = State(default=0)

    def render(self):
        return f"""
            <div>
                <span>{self.count}</span>
                <button hx-post="{self.url('increment')}">+1</button>
            </div>
        """

    async def increment(self):
        self.count += 1
        return self.render()
```

That's it. No JSX, no bundler, no build step. Just Python and HTML.

## Key Documents

1. **[RFC-DRAFT-chirp-components.md](./RFC-DRAFT-chirp-components.md)**
   - Full system design and philosophy
   - Core abstractions (Component, State, Props, Computed)
   - State management and scoping strategies
   - Advanced patterns (streaming, optimistic updates)

2. **[chirp-component-example.md](./chirp-component-example.md)**
   - Real-world ProjectCard component implementation
   - Complete with all features: expand/collapse, validation, deletion
   - Shows component composition and event communication
   - Performance characteristics and migration path

3. **[chirp-component-architecture.md](./chirp-component-architecture.md)**
   - System architecture diagrams
   - Request flow visualization
   - Comparison with SPAs, traditional server rendering, Web Components
   - Design patterns and testing strategies

## Core Concepts

### Components are Python Classes

```python
from chirp.component import Component, State, Prop

class TaskItem(Component):
    # Props: passed from parent, immutable
    task_id: Prop[str]
    title: Prop[str]

    # State: internal, mutable, triggers re-render
    completed: State[bool] = State(default=False)

    def render(self) -> str:
        return self.template("""
            <div class="task">
                <input type="checkbox" {{ "checked" if completed else "" }}
                       hx-post="{{ component.url('toggle') }}">
                <span>{{ title }}</span>
            </div>
        """, completed=self.completed, title=self.title)

    async def toggle(self):
        self.completed = not self.completed
        return self.render()
```

### Reactivity via htmx

Components render to HTML with htmx attributes:
- `hx-post` → trigger component action
- `hx-target` → where to swap result
- `hx-swap` → how to swap (innerHTML, outerHTML, etc)
- `sse-connect` → live streaming updates

```html
<button hx-post="/_components/task-item/abc123/toggle"
        hx-target="#task-abc123"
        hx-swap="outerHTML">
    Toggle
</button>
```

### Automatic Endpoint Registration

Component methods become htmx endpoints automatically:

```python
class ProjectCard(Component):
    async def expand(self):      # POST /_components/project-card/{id}/expand
        ...

    async def delete(self):      # DELETE /_components/project-card/{id}/delete
        ...

    async def validate(self):    # POST /_components/project-card/{id}/validate
        ...
```

No manual route definitions needed.

### State Management

Three types of reactive state:

```python
# State: mutable, triggers re-render
count: State[int] = State(default=0)

# Prop: immutable, passed from parent
title: Prop[str]

# Computed: derived from other state, cached
@Computed
def status(self) -> str:
    return "done" if self.count >= 10 else "pending"
```

### Component Communication

**Parent → Child (Props)**
```python
ProjectList(tasks=all_tasks)  # Pass data down
```

**Child → Parent (Events via htmx)**
```python
async def delete(self):
    await self.delete_from_db()
    return Response("", headers={
        "HX-Trigger": json.dumps({"taskDeleted": {"id": self.id}})
    })
```

**Sibling → Sibling (Event Bus)**
```html
<div hx-get="/refresh"
     hx-trigger="taskDeleted from:body">
    <!-- Refreshes when ANY task is deleted -->
</div>
```

## Usage Example

### Define Component

```python
# components/project_card.py
class ProjectCard(Component):
    project_id: Prop[str]
    name: Prop[str]
    expanded: State[bool] = State(default=False)

    def render(self):
        return self.template("""
            <div class="card">
                <h3>{{ name }}</h3>
                <button hx-post="{{ component.url('toggle') }}">
                    {{ "▼" if expanded else "▶" }}
                </button>
                {% if expanded %}
                    <div class="details">...</div>
                {% end %}
            </div>
        """, name=self.name, expanded=self.expanded)

    async def toggle(self):
        self.expanded = not self.expanded
        return self.render()
```

### Use in Page

```python
# pages/projects/page.py
class ProjectsPage(PageHandler):
    async def get(self):
        projects = await load_projects()
        self.render('projects.html', projects=projects)
```

```html
<!-- projects.html -->
{% for project in projects %}
    {{ ProjectCard(
        project_id=project.id,
        name=project.name
    ) }}
{% endfor %}
```

That's it! Component is automatically interactive with expand/collapse.

## Advantages

### Over Traditional Server Rendering

✅ **Persistent state** - Components remember state between requests
✅ **Granular updates** - Update just one component, not entire page
✅ **Reusable** - Define once, use everywhere
✅ **Type-safe** - Python type hints for props/state

### Over SPAs (React/Vue)

✅ **No build step** - Write Python + HTML, deploy
✅ **Smaller payload** - ~10KB HTML vs ~500KB JS bundle
✅ **SEO native** - HTML from server, no SSR gymnastics
✅ **Progressive** - Works without JavaScript
✅ **Server control** - Business logic stays on server (security)

### Over Plain htmx

✅ **Organized** - Components encapsulate logic + rendering
✅ **Composable** - Build complex UIs from simple components
✅ **Stateful** - No manual state management in hidden inputs
✅ **Testable** - Unit test component classes

## When to Use What

### Template Macros
Use for simple presentational components:
```html
{% macro Badge(text, variant) %}
<span class="badge badge-{{ variant }}">{{ text }}</span>
{% end %}
```
**Good for:** Icons, badges, buttons, cards (no logic)

### Component Classes
Use for interactive components with state:
```python
class DataTable(Component):
    data: State[List]
    sort_by: State[str]
    # ... sorting/filtering logic
```
**Good for:** Forms, lists, tables, complex UI (with logic)

### Web Components
Use for rich client-side widgets:
```javascript
class RichEditor extends HTMLElement { ... }
```
**Good for:** WYSIWYG editors, charts, calendars (client-side heavy)

### Hybrid
Combine all three:
```python
class DocumentEditor(Component):
    """Server component wrapping Web Component."""

    def render(self):
        return f"""
            <div>
                {Badge("Draft", "warning")}  {# Macro #}
                <rich-editor>{self.content}</rich-editor>  {# Web Component #}
            </div>
        """
```

## Performance

**Initial page load:**
- HTML rendered on server: ~10KB
- htmx library: ~14KB
- Total: ~24KB (vs ~500KB for React app)

**Subsequent interactions:**
- Each action: ~1-5KB HTML fragment
- No framework overhead
- Server render: ~5-20ms
- Network latency: ~50-200ms (main bottleneck)

**Scaling:**
- Each component action = Python function call
- Can handle 1000+ concurrent components
- State stored in session (Redis) or DB
- Stateless components = no memory overhead

## Next Steps

### Phase 1: Prototype (1 week)
- [ ] Implement base `Component` class
- [ ] Add `State`, `Prop`, `Computed` descriptors
- [ ] Build `ComponentRegistry` with routing
- [ ] Create 2-3 example components

### Phase 2: Integration (1 week)
- [ ] Add `ComponentMiddleware` to Chirp
- [ ] Template integration (`{% component %}` tag)
- [ ] Session state persistence
- [ ] Testing utilities

### Phase 3: Real Components (2 weeks)
- [ ] Convert ProjectCard to component
- [ ] Build TaskList component
- [ ] Create DataTable component
- [ ] Add form components

### Phase 4: Advanced Features (2+ weeks)
- [ ] SSE streaming support
- [ ] Optimistic updates
- [ ] Component lifecycle hooks
- [ ] Performance monitoring

## Questions to Resolve

1. **State Persistence:** How long do session-scoped components live? Should we have TTL?

2. **Security:** How to prevent component ID tampering? Sign IDs? Check permissions?

3. **Memory Management:** When to garbage collect component instances? LRU cache?

4. **Nesting Depth:** Any limits on component composition depth? Performance impact?

5. **Error Handling:** How do components handle errors? Show error state? Retry?

6. **Database Queries:** Should components query DB directly? Or inject services?

7. **Testing:** How to test component interactions? Fixtures? Test harness?

8. **Deployment:** Any special considerations for deploying component apps? State migration?

## Resources

- **htmx documentation:** https://htmx.org/
- **Web Components:** https://developer.mozilla.org/en-US/docs/Web/Web_Components
- **Tornado templates:** https://www.tornadoweb.org/en/stable/template.html
- **Similar projects:**
  - Phoenix LiveView (Elixir)
  - Laravel Livewire (PHP)
  - Hotwire (Ruby)
  - HTMX + Alpine.js

## Conclusion

Chirp components bring modern component architecture to server-first web development. You get:

- **React-like DX** (components, props, state)
- **htmx reactivity** (no framework JS)
- **Python power** (type safety, testing, libraries)
- **Progressive enhancement** (works without JS)
- **Zero build step** (write code, deploy)

It's the best of both worlds: component ergonomics + server simplicity.

**Status:** Ready for prototyping and feedback.
