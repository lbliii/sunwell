# Chirp Patterns Learned from chirp-pad

## 🎓 Key Learnings from chirp-pad Demo

After studying the chirp-pad collaborative editor, I've identified several advanced patterns we should adopt for the Sunwell migration:

---

## 1. 📁 Page Convention Routing (vs Decorator Routing)

### Current Approach (Sunwell)
```python
# src/sunwell/interface/chirp/routes/home.py
@app.route("/")
async def home(request: Request) -> Template:
    return Template("home.kida", ...)
```

### Better Approach (from chirp-pad)
```python
# src/sunwell/interface/chirp/pages/page.py
def get() -> Page:
    return Page("page.html", "content")

# src/sunwell/interface/chirp/pages/projects/{project_id}/page.py
def get(project_id: str) -> Page:
    return Page("projects/{project_id}/page.html", "content")
```

**Benefits:**
- Filesystem = URL structure (intuitive)
- Nested layouts via `_layout.html`
- Context providers via `_context.py`
- No route registration boilerplate
- Better organization for large apps

**Action**: Migrate from decorator routes to page convention after Phase 1

---

## 2. 🔄 Reactive SSE (Auto-rerendering)

### Current Approach (Sunwell)
```python
# Manual event streaming
async def run_events(run_id: str):
    async def event_stream():
        for event in run.events:
            yield f"data: {json.dumps(event)}\n\n"
    return EventStream(event_stream())
```

### Better Approach (from chirp-pad)
```python
from chirp.pages.reactive import reactive_stream

@contract(returns=SSEContract(event_types=frozenset({"task_complete", "model_thinking"})))
def get(run_id: str, request: Request) -> EventStream:
    """SSE stream that auto-pushes re-rendered blocks when data changes."""

    def build_context() -> dict:
        run = get_run(run_id)
        return {"run": run, "tasks": run.tasks}

    return reactive_stream(
        event_bus,           # Bus that emits ChangeEvents
        scope=run_id,        # Filter events by scope
        index=dep_index,     # Knows which blocks depend on what data
        context_builder=build_context,
        origin=session_id,   # Skip events from same user
    )
```

**Template:**
```html
<div hx-ext="sse" sse-connect="/runs/{{ run_id }}/stream">
    {% block task_list %}
    <div id="tasks" sse-swap="task_list">
        {% for task in tasks %}
            <div>{{ task.description }}</div>
        {% end %}
    </div>
    {% end %}
</div>
```

**Benefits:**
- Server pushes HTML fragments (not JSON)
- No manual event serialization
- Automatic dependency tracking
- Origin filtering (skip self-caused updates)

**Action**: Use `reactive_stream()` for Observatory/DAG/Agent execution views

---

## 3. 💉 Service Injection (Type-based DI)

### Current Approach (Sunwell)
```python
# Global state or manual passing
@app.route("/projects")
async def projects(request: Request):
    store = get_project_store()  # Manual lookup
    projects = await store.list()
    return Template("projects.kida", projects=projects)
```

### Better Approach (from chirp-pad)
```python
# server.py - Register providers
app.provide(ProjectStore, get_project_store)
app.provide(RunManager, get_run_manager)
app.provide(SunwellConfig, lambda: config)

# routes - Type-annotated injection
def get(store: ProjectStore, config: SunwellConfig) -> Page:
    projects = store.list()
    return Page("projects/page.html", projects=projects, config=config)
```

**Benefits:**
- No global state imports
- Cleaner testing (mock via provider)
- Type-safe
- Explicit dependencies

**Action**: Add service providers for ProjectStore, RunManager, MemoryFacade, etc.

---

## 4. 🎯 Multiple SSE Streams (Separate Concerns)

### Pattern from chirp-pad
```html
{# Main document stream #}
<div hx-ext="sse" sse-connect="/doc/{{ doc_id }}/stream">
    <div id="content" sse-swap="content">...</div>
    <div id="status" sse-swap="status">...</div>
</div>

{# Separate AI activity stream #}
<div hx-ext="sse" sse-connect="/doc/{{ doc_id }}/activity">
    <div id="activity-log" sse-swap="activity_row">...</div>
</div>
```

### Apply to Sunwell
```html
{# Main run events stream #}
<div hx-ext="sse" sse-connect="/runs/{{ run_id }}/events">
    <div id="tasks" sse-swap="task_list">...</div>
    <div id="status" sse-swap="run_status">...</div>
</div>

{# Separate memory events stream #}
<div hx-ext="sse" sse-connect="/runs/{{ run_id }}/memory">
    <div id="memories" sse-swap="memory_updates">...</div>
</div>

{# Separate Observatory stream #}
<div hx-ext="sse" sse-connect="/runs/{{ run_id }}/observatory">
    <canvas id="viz" sse-swap="viz_event">...</canvas>
</div>
```

**Benefits:**
- Separation of concerns
- Independent reconnection/buffering
- Easier debugging
- Selective subscription

**Action**: Split SSE streams by concern (tasks, memory, observatory, logs)

---

## 5. 📝 FormAction (Progressive Enhancement)

### Pattern from chirp-pad
```python
from chirp import FormAction
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class NewProjectForm:
    name: str
    description: str = ""

def post(form: NewProjectForm, store: ProjectStore) -> FormAction:
    project = store.create(name=form.name, description=form.description)
    return FormAction(f"/projects/{project.id}")  # Redirects (303 or HX-Redirect)
```

**Benefits:**
- Automatic form binding to dataclass
- Validation errors auto-handled
- Progressive enhancement (works without JS)
- Clean redirect pattern

**Action**: Use FormAction for all form submissions (projects, goals, settings)

---

## 6. 🎨 Template Organization

### chirp-pad Structure
```
pages/
├── _layout.html              # Root layout (applied to all)
├── _not_found.html           # 404 handler
├── page.py                   # Home page
├── documents/
│   ├── page.html             # Document list
│   ├── page.py               # GET handler
│   └── new.py                # POST handler
└── doc/{doc_id}/
    ├── _context.py           # Shared context provider
    ├── page.html             # Editor template
    ├── page.py               # GET handler
    ├── save.py               # POST /doc/:id/save
    ├── stream.py             # GET /doc/:id/stream (SSE)
    └── _presence_badge.html  # Partial template
```

### Apply to Sunwell
```
pages/
├── _layout.html              # Base layout with nav
├── page.py                   # Home page
├── projects/
│   ├── page.html             # Project list
│   ├── page.py               # GET /projects
│   ├── new.py                # POST /projects/new
│   └── {project_id}/
│       ├── page.html         # Project detail
│       ├── page.py           # GET /projects/:id
│       ├── delete.py         # POST /projects/:id/delete
│       └── runs/
│           └── {run_id}/
│               ├── page.html
│               ├── page.py   # GET /projects/:id/runs/:run_id
│               └── stream.py # SSE stream
├── observatory/
│   ├── page.html
│   ├── page.py
│   └── {run_id}/
│       ├── page.html
│       ├── page.py
│       └── stream.py         # Observatory-specific SSE
└── dag/
    ├── page.html
    └── page.py
```

**Benefits:**
- URL structure mirrors filesystem
- Co-located templates and handlers
- Nested layouts automatic
- Partials prefixed with `_`

---

## 7. 🔧 Template Filters

### Pattern from chirp-pad
```python
# server.py
@app.template_filter("format_time")
def format_time(timestamp: float) -> str:
    diff = time.time() - timestamp
    if diff < 60:
        return f"{int(diff)}s ago"
    return f"{int(diff / 60)}m ago"

@app.template_filter("format_tool_args")
def format_tool_args(args: dict) -> str:
    # Custom formatting logic
    return ", ".join(f"{k}={v}" for k, v in args.items())
```

### Template Usage
```html
<span class="timestamp">{{ task.created_at | format_time }}</span>
<span class="args">{{ tool_call.args | format_tool_args }}</span>
```

### Apply to Sunwell
```python
@app.template_filter("format_duration")
def format_duration(ms: float) -> str:
    if ms < 1000:
        return f"{int(ms)}ms"
    return f"{ms / 1000:.1f}s"

@app.template_filter("format_tokens")
def format_tokens(count: int) -> str:
    if count < 1000:
        return str(count)
    return f"{count / 1000:.1f}k"

@app.template_filter("excerpt")
def excerpt(text: str, length: int = 100) -> str:
    return text[:length] + "..." if len(text) > length else text
```

**Action**: Add domain-specific filters for durations, tokens, file sizes, etc.

---

## 8. 🎭 View Transitions

### Pattern from chirp-pad
```python
# server.py
app = App(
    AppConfig(
        view_transitions=True,  # Enables View Transition API
        ...
    )
)
```

### Template
```html
{# _layout.html - Chirp auto-injects meta tag and htmx config #}
<body hx-boost="true" hx-swap="innerHTML transition:true">
    <main id="app-content">
        {% block content %}{% end %}
    </main>
</body>
```

**Benefits:**
- Smooth cross-fade between pages
- Native browser API (no JS library)
- Works with htmx
- Automatically enabled by Chirp

**Action**: Enable `view_transitions=True` in AppConfig

---

## 9. 🛡️ SSE Contracts (Type Safety)

### Pattern from chirp-pad
```python
from chirp.contracts import SSEContract, contract

@contract(returns=SSEContract(
    event_types=frozenset({"status", "toolbar-title", "presence"}),
))
def get(doc_id: str, request: Request) -> EventStream:
    return reactive_stream(...)
```

**Benefits:**
- Type-checked event types
- `app.check()` validates SSE connections
- Compile-time errors for typos
- Documentation

### Apply to Sunwell
```python
@contract(returns=SSEContract(
    event_types=frozenset({
        "task_start", "task_complete", "task_error",
        "model_thinking", "model_tokens",
        "memory_update", "artifact_created",
    }),
))
def get(run_id: str, request: Request) -> EventStream:
    return reactive_stream(...)
```

**Action**: Add SSE contracts to all event streams

---

## 10. 🔐 Origin Filtering (Skip Self-Updates)

### Pattern from chirp-pad
```javascript
// Generate user ID and append to SSE URL
var userId = localStorage.getItem("user-id") || generateId();
var url = "/doc/123/stream?sid=" + userId;
```

```python
# stream.py
def get(doc_id: str, request: Request) -> EventStream:
    session_id = request.query.get("sid", "")
    return reactive_stream(
        bus,
        scope=doc_id,
        origin=session_id,  # Skip events from this user
    )
```

**Use Case (Sunwell):**
- User clicks "Run" → creates run → don't show duplicate notification
- User saves goal → don't re-render their own change

**Action**: Add session ID to SSE URLs and use origin filtering

---

## Migration Roadmap with New Patterns

### Phase 1B: Refactor Foundation (Week 2)
- [ ] Convert decorator routes to page convention
- [ ] Add service providers (ProjectStore, RunManager, etc.)
- [ ] Add template filters (format_duration, format_tokens, etc.)
- [ ] Enable view_transitions
- [ ] Test page convention with Projects page

### Phase 2: SSE with Reactive Streams (Weeks 3-5)
- [ ] Implement reactive_stream for run events
- [ ] Split SSE into multiple streams (tasks, memory, observatory)
- [ ] Add SSE contracts for type safety
- [ ] Add origin filtering
- [ ] Migrate Observatory to use reactive Canvas updates

### Phase 3: Forms & Polish (Weeks 6-8)
- [ ] Migrate all forms to FormAction pattern
- [ ] Add conflict resolution for concurrent edits
- [ ] Performance optimization
- [ ] Full cutover

---

## Files to Study in chirp-pad

### Essential Reading
1. **`server.py`** - App factory, service injection, template filters
2. **`pages/doc/{doc_id}/stream.py`** - Reactive SSE pattern
3. **`pages/doc/{doc_id}/page.html`** - Multiple SSE streams, sse-swap
4. **`pages/_layout.html`** - Global layout with hx-boost
5. **`pages/documents/new.py`** - FormAction pattern
6. **`pages/doc/{doc_id}/save.py`** - Conflict resolution

### Optional (Advanced)
- `reactive.py` - ReactiveBus implementation
- `pages/doc/{doc_id}/_context.py` - Context providers
- `pages/doc/{doc_id}/chat/stream.py` - AI streaming

---

## Summary: What Changes for Sunwell

| Pattern | Current | New (from chirp-pad) |
|---------|---------|----------------------|
| **Routing** | Decorator `@app.route()` | Page convention `pages/*/page.py` |
| **SSE** | Manual JSON events | Reactive HTML fragments |
| **State** | Global imports | Type-based injection |
| **Forms** | Manual POST handlers | FormAction + dataclass |
| **Templates** | Single base template | Nested layouts via `_layout.html` |
| **Filters** | None | Custom filters for domain formatting |
| **Transitions** | None | View Transitions API |
| **Contracts** | None | SSE type contracts |

**Overall Impact**: More maintainable, type-safe, and closer to framework idioms.

---

## Next Steps

1. **Finish Phase 1** with current decorator approach (don't block progress)
2. **Prototype** page convention with one route (Projects page)
3. **Validate** reactive_stream with Observatory (Week 3)
4. **Gradually refactor** as we add new pages

**Estimated Effort**: +1 week to adopt all patterns, but saves 2-3 weeks in Phase 2-3 due to better abstractions.
