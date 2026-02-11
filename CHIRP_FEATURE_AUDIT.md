# Chirp & Pounce Feature Audit

**Date**: February 11, 2026
**Repos Reviewed**:
- `../chirp` - Chirp web framework (v0.1.0+unreleased)
- `../pounce` - Pounce ASGI server
- `../chirp-pad` - Reference implementation

---

## Executive Summary

### ✅ Features We're Already Using
1. **Page convention routing** - `pages/` filesystem structure
2. **SSR with Kida templates** - Server-side rendering
3. **Dependency injection** - Service providers
4. **Template filters** - Custom filters (format_duration, format_tokens, etc.)
5. **StaticFiles middleware** - CSS/JS serving
6. **View Transitions API** - Smooth navigation (`view_transitions=True`)
7. **htmx integration** - Progressive enhancement
8. **EventStream** - SSE for real-time updates (basic)
9. **Pounce ASGI server** - `app.run()` internally uses Pounce
10. **App.provide()** - Singleton service registration

### 🔴 High-Value Features We're Missing
1. **Reactive templates** - Automatic SSE push of changed blocks
2. **Form helpers** - Built-in form field macros + validation
3. **Markdown support** - `{{ content | markdown }}` filter
4. **Layout context providers** - `_context.py` files
5. **Built-in template filters** - `field_errors`, `qs` (query strings)
6. **Contract validation** - `chirp check` for hypermedia contracts
7. **Database integration** - `chirp.data.Database`
8. **AI integration** - Built-in LLM streaming
9. **HTTP/2 support** - Pounce extras
10. **Zstd compression** - Pounce stdlib compression

---

## Detailed Feature Analysis

### 1. Reactive Templates 🔥 HIGH PRIORITY

**What it is**: Automatic SSE push of changed template blocks based on static dependency analysis.

**How it works**:
```python
# Store emits change events
from chirp.pages.reactive import ReactiveBus, ChangeEvent

bus = ReactiveBus()

def update_project(project_id: str, data: dict) -> None:
    # Mutate data
    project.update(data)

    # Emit change event
    bus.emit_sync(ChangeEvent(
        scope=project_id,
        changed_paths=frozenset({"project.name", "project.updated_at"}),
    ))

# Route sets up reactive stream
from chirp.pages.reactive import reactive_stream, DependencyIndex

index = DependencyIndex()
index.register_template(env, "projects/{project_id}/page.html")
index.derive("project.task_count", from_paths={"project.tasks"})

@app.route("/projects/{project_id}/live")
def live(project_id: str) -> EventStream:
    return reactive_stream(
        bus,
        scope=project_id,
        index=index,
        context_builder=lambda: {"project": get_project(project_id)},
    )
```

**Benefits**:
- **Zero client-side code** - No manual SSE event handling
- **Granular updates** - Only changed blocks re-render, not full page
- **Automatic dependency tracking** - Kida analyzes which blocks use which data
- **Derived paths** - Update `project.tasks` → auto-invalidates `project.task_count`

**Status in chirp-pad**: ✅ Used extensively for live document editing

**Recommendation**: **ADOPT** for:
- `/projects/{id}` - Live project status updates
- `/backlog` - Real-time goal updates
- `/coordinator` - Worker status monitoring
- `/memory` - Live memory updates

**Effort**: Medium (1-2 days to implement per page)

---

### 2. Form Helpers 🔥 HIGH PRIORITY

**What it is**: Built-in form field macros + validation utilities.

**Features**:
- `form_or_errors()` - Combines form binding + validation in one call
- `form_values()` - Convert dataclass to `dict[str, str]` for re-population
- Form field macros - `{% from "chirp/forms.html" import text_field %}`
- `field_errors` filter - Extract validation messages per field

**Example**:
```python
from chirp.validation import form_or_errors, form_values

@app.route("/projects/new", methods=["POST"])
async def create_project(request: Request) -> AnyResponse:
    result = await form_or_errors(ProjectForm, request)

    if isinstance(result, ValidationError):
        return Template("projects/new.html",
            errors=result.errors,
            values=form_values(result.input),  # Re-populate form
        )

    # result is ProjectForm dataclass
    project = create_project(result.name, result.root)
    return Redirect(f"/projects/{project.id}")
```

**Template usage**:
```html
{% from "chirp/forms.html" import text_field, textarea_field %}

<form method="post">
    {{ text_field("name", "Project Name", values, errors) }}
    {{ textarea_field("description", "Description", values, errors) }}
    <button type="submit">Create</button>
</form>
```

**Status in chirp-pad**: ✅ Not used (simple app), but available

**Current Sunwell approach**: Manual form handling with htmx POST

**Recommendation**: **ADOPT** for:
- `/projects/new` - Project creation form
- `/settings` - Settings forms (provider, API keys, preferences)
- `/backlog` - Goal creation forms

**Benefits**:
- **Less boilerplate** - No try/except for validation
- **Consistent UX** - Built-in error display patterns
- **Type-safe** - Dataclass-based forms

**Effort**: Low (1-2 hours to refactor existing forms)

---

### 3. Markdown Support 🟡 MEDIUM PRIORITY

**What it is**: Built-in markdown rendering filter.

**Usage**:
```python
from chirp.markdown import register_markdown_filter

register_markdown_filter(app)
```

**Template**:
```html
<div class="content">
    {{ document.markdown_content | markdown }}
</div>
```

**Features**:
- GFM (GitHub Flavored Markdown) - tables, strikethrough, autolinks
- Safe HTML - Escapes unsafe tags
- Syntax highlighting - Code blocks with Pygments
- Extensions - Footnotes, TOC, etc.

**Status in chirp-pad**: ✅ Used for document rendering

**Current Sunwell approach**: No markdown rendering (?)

**Recommendation**: **ADOPT** if:
- We want to display documentation pages in the UI
- Memory entries contain markdown
- Goal descriptions support markdown formatting

**Effort**: Trivial (2 lines of code)

---

### 4. Layout Context Providers 🟡 MEDIUM PRIORITY

**What it is**: `_context.py` files that provide data to nested layouts automatically.

**Structure**:
```
pages/
  _layout.html          # Root layout
  _context.py           # Provides: current_user, config
  projects/
    _layout.html        # Projects layout
    _context.py         # Provides: project_list, default_project
    {project_id}/
      _context.py       # Provides: project, recent_runs
      page.py           # Can access all parent context
```

**Example**:
```python
# pages/_context.py
async def context(request: Request, config: ConfigService) -> dict[str, Any]:
    return {
        "app_name": "Sunwell Studio",
        "version": "0.1.0",
        "current_user": await get_current_user(request),
    }

# pages/projects/{project_id}/_context.py
async def context(request: Request, project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise NotFound()

    return {
        "project": project,
        "recent_runs": get_recent_runs(project_id, limit=10),
    }

# pages/projects/{project_id}/page.py
def get(project) -> Page:  # 'project' injected from _context.py!
    return Page("projects/{project_id}/page.html")
```

**Benefits**:
- **Shared context** - Parent layouts + child pages get same data
- **Cleaner routes** - No repeated queries in every handler
- **Automatic nesting** - Chirp composes context from all _context.py in path

**Status in chirp-pad**: ✅ Used for document loading

**Current Sunwell approach**: Services injected into each route handler individually

**Recommendation**: **CONSIDER** - Would clean up code but requires refactoring

**Effort**: Medium (2-3 days to refactor all pages)

---

### 5. Built-in Template Filters 🟢 LOW PRIORITY

**What they are**:
- `field_errors(errors, "field_name")` - Extract validation errors for a field
- `qs({"page": 2, "q": "test"})` - Build query string (`?page=2&q=test`)

**Usage**:
```html
{# Show errors for a specific field #}
{% if errors | field_errors("name") %}
  <p class="error">{{ errors | field_errors("name") }}</p>
{% end %}

{# Build URL with query params #}
<a href="/projects{{ {"status": "active"} | qs }}">Active Projects</a>
```

**Status**: Available in Chirp unreleased version

**Current Sunwell approach**: Manual error extraction

**Recommendation**: **ADOPT** when forms are refactored (see #2)

**Effort**: Trivial (auto-registered)

---

### 6. Contract Validation 🟡 MEDIUM PRIORITY

**What it is**: `chirp check` CLI command that validates hypermedia contracts.

**Checks**:
- All `hx-get/hx-post/hx-put` targets exist as routes
- Forms have corresponding POST handlers
- Fragments reference valid template blocks
- SSE endpoints return `EventStream`

**Usage**:
```bash
$ chirp check sunwell.interface.chirp:create_app

✓ 42 routes registered
✓ 18 fragments valid
✗ Error: <form hx-post="/projects/delete"> → route not found
✗ Warning: Fragment "projects/list.html:card" not found
```

**Benefits**:
- **Catch broken links at build time** - Before users see 404s
- **Refactoring safety** - Rename a route, find all affected templates
- **CI integration** - Fail builds if contracts break

**Status in chirp-pad**: Not used (small app)

**Current Sunwell approach**: Manual testing

**Recommendation**: **ADOPT** for CI pipeline

**Effort**: Low (5 minutes to add to CI)

---

### 7. Database Integration 🔴 HIGH PRIORITY (?)

**What it is**: `chirp.data.Database` - Typed async database access.

**Features**:
- **SQL in, dataclasses out** - Not an ORM, just a query runner
- **SQLite built-in** - Zero config
- **PostgreSQL support** - Install `chirp[data-pg]`
- **Migrations** - `chirp.data.migrate()`
- **Type-safe** - `await db.fetch(User, "SELECT * FROM users")`

**Example**:
```python
from chirp.data import Database, get_db
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Project:
    id: int
    name: str
    root: str
    created_at: float

db = Database("sqlite:///sunwell.db")

# Fetch many
projects = await db.fetch(Project, "SELECT * FROM projects WHERE active = ?", True)

# Fetch one
project = await db.fetch_one(Project, "SELECT * FROM projects WHERE id = ?", 42)

# Execute
await db.execute("UPDATE projects SET name = ? WHERE id = ?", "New Name", 42)
```

**Status in chirp-pad**: ✅ Used for document storage

**Current Sunwell approach**: File-based storage (YAML, JSON)

**Recommendation**: **EVALUATE** - Do we need a database?
- **Pro**: Faster queries, transactions, migrations
- **Con**: Adds complexity, current file-based approach works

**Effort**: High (1 week to migrate ProjectRegistry, BacklogService, etc.)

---

### 8. AI Integration 🟡 MEDIUM PRIORITY

**What it is**: Built-in LLM streaming with tool use.

**Features**:
- Provider-agnostic - Anthropic, OpenAI, etc.
- Streaming - Token-by-token via SSE
- Tool calling - Automatic tool schema generation
- Structured output - Constrain LLM to dataclasses

**Example**:
```python
from chirp.ai import AIProvider, stream_chat

provider = AIProvider.from_config(provider="anthropic", api_key=key)

@app.route("/chat/stream")
def chat_stream(request: Request) -> EventStream:
    messages = get_messages(request)

    async def stream():
        async for chunk in stream_chat(provider, messages):
            yield f"data: {json.dumps(chunk)}\n\n"

    return EventStream(stream())
```

**Status in chirp-pad**: ✅ Core feature (AI-assisted editing)

**Current Sunwell approach**: Manual Anthropic API integration

**Recommendation**: **CONSIDER** if we want in-browser AI chat

**Effort**: Medium (2-3 days to integrate)

---

### 9. Pounce Advanced Features 🟢 LOW PRIORITY

**Features we're not using**:

#### HTTP/2 Support
```bash
pip install bengal-pounce[h2]
```

**Benefits**:
- **Stream multiplexing** - Multiple requests over one connection
- **Header compression** - HPACK reduces bandwidth
- **Server push** - Proactively send assets

**Recommendation**: **SKIP** for now - HTTP/1.1 is sufficient

---

#### Zstd Compression
```python
# Pounce uses stdlib compression.zstd (PEP 784) automatically
# No code changes needed - just enable via Content-Encoding negotiation
```

**Benefits**:
- **Better compression** - 20-30% smaller than gzip
- **Faster** - 3x faster decompression than gzip

**Status**: Auto-enabled if client supports it

**Recommendation**: **ALREADY WORKS** - No action needed

---

#### TLS Support
```bash
pip install bengal-pounce[tls]
pounce app:app --ssl-certfile cert.pem --ssl-keyfile key.pem
```

**Recommendation**: **SKIP** - Use reverse proxy (nginx/Caddy) for TLS

---

#### Multi-worker Mode
```bash
pounce app:app --workers 4
```

**Benefits**:
- **Free-threading** - With Python 3.14t, threads share interpreter
- **Auto-detect** - Falls back to processes if GIL present

**Recommendation**: **DEFER** - Single worker is sufficient for dev

---

### 10. CLI Tools 🟡 MEDIUM PRIORITY

**Chirp CLI commands**:
- `chirp new myapp` - Scaffold new project
- `chirp run app:app` - Start dev server
- `chirp check app:app` - Validate contracts

**Status**: Available but we use custom `sunwell serve` command

**Recommendation**: **KEEP CURRENT** - Our CLI is integrated

---

## Adoption Roadmap

### Phase 1: Quick Wins (1-2 days)
1. ✅ **Markdown support** - `register_markdown_filter(app)` (2 lines)
2. ✅ **Built-in filters** - Auto-registered (`field_errors`, `qs`)
3. ✅ **Contract validation** - Add `chirp check` to CI

### Phase 2: Form Refactoring (2-3 days)
1. **Adopt form helpers** - Use `form_or_errors()`, `form_values()`
2. **Form field macros** - `{% from "chirp/forms.html" import text_field %}`
3. **Refactor**:
   - `/projects/new` → Use form macros
   - `/settings/*` → Use form macros
   - `/backlog` → Use form macros

### Phase 3: Reactive Templates (1 week)
1. **Set up ReactiveBus** - Global singleton for change events
2. **Create DependencyIndex** - Register templates
3. **Add reactive streams**:
   - `/projects/{id}/live` → Live project updates
   - `/coordinator/live` → Worker status
   - `/memory/live` → Memory updates
4. **Emit change events** - From ProjectService, SessionService, etc.

### Phase 4: Layout Context (Optional, 1 week)
1. **Create root `_context.py`** - App-wide data (config, user)
2. **Add nested `_context.py`** - Per-section data
3. **Refactor routes** - Remove redundant queries

### Phase 5: Database (Optional, 2 weeks)
1. **Evaluate need** - Is file-based storage sufficient?
2. **If yes**: Design schema for Projects, Goals, etc.
3. **Migrate data** - ProjectRegistry → Database
4. **Update services** - Use `db.fetch()` instead of YAML

---

## Current Status vs. Best Practices

| Feature | Sunwell | chirp-pad | Recommendation |
|---------|---------|-----------|----------------|
| **Page routing** | ✅ Used | ✅ Used | Keep |
| **SSR** | ✅ Used | ✅ Used | Keep |
| **Dependency injection** | ✅ Used | ✅ Used | Keep |
| **StaticFiles middleware** | ✅ Used | ✅ Used | Keep |
| **Reactive templates** | ❌ Not used | ✅ Used | **Adopt** |
| **Form helpers** | ❌ Not used | ❌ Not needed | **Adopt** |
| **Markdown** | ❌ Not used | ✅ Used | **Adopt** |
| **Layout context** | ❌ Not used | ✅ Used | Consider |
| **Database** | ❌ File-based | ✅ SQLite | Evaluate |
| **AI streaming** | ✅ Custom | ✅ Built-in | Keep custom |
| **Contract validation** | ❌ Manual | ❌ Not used | **Adopt** |

---

## Recommendations Summary

### 🔥 High Priority (Adopt Now)
1. **Reactive templates** - Huge UX improvement for real-time updates
2. **Form helpers** - Reduce boilerplate, consistent patterns
3. **Markdown support** - Trivial to add, enables rich content

### 🟡 Medium Priority (Evaluate)
1. **Layout context** - Cleaner code but requires refactoring
2. **Contract validation** - Great for CI but not critical
3. **Database integration** - Only if file-based storage becomes limiting

### 🟢 Low Priority (Skip for Now)
1. **HTTP/2** - Not needed yet
2. **Multi-worker mode** - Single worker is fine for dev
3. **AI integration** - We have custom implementation

---

## Next Steps

1. **Add markdown support** - 2 lines in `chirp/main.py`
2. **Prototype reactive templates** - Pick one page (e.g., `/coordinator`)
3. **Refactor one form** - `/projects/new` with form helpers
4. **Add `chirp check` to CI** - Catch broken links

After prototyping, decide if we want to adopt reactive templates broadly or stick with manual SSE handling.

---

## Questions for Discussion

1. **Do we need reactive templates?** - Is manual SSE handling sufficient?
2. **Database migration?** - Is file-based storage a bottleneck?
3. **Layout context providers?** - Worth the refactoring effort?
4. **AI integration?** - Keep custom or use Chirp's built-in?

Let me know which features you'd like to prioritize!
