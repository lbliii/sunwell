# RFC-078: Primitive & Provider Roadmap

**Status**: ✅ Complete (All primitives functional)  
**Created**: 2026-01-21  
**Last Updated**: 2026-01-21  
**Dependencies**: RFC-072 (Generative Surface), RFC-075 (Generative Interface)  
**Confidence**: 92% 🟢

---

## Summary

Prioritized roadmap for completing workspace primitives and adding data providers, ordered by **data availability** — what we can populate now vs. what requires new integrations.

---

## Problem Statement

RFC-072 defined 25 surface primitives and RFC-075 defined the provider system with 3 provider ABCs (`CalendarProvider`, `ListProvider`, `NotesProvider`). However:

1. **Primitives are stubs**: 4 key primitives (`DataTable`, `Preview`, `DiffView`, `Timeline`) exist as placeholder components with no functional implementation
2. **Providers are incomplete**: Only 3 native providers exist; common data sources (files, projects, git) have no provider abstraction
3. **No integration path**: The `IntentAnalyzer` prompt hardcodes available primitives — no mechanism to register new ones dynamically

This RFC defines the **completion order** based on data availability, ensuring we build functional primitives before adding new ones.

---

## Goals

1. **Complete existing primitive stubs** — Make `DataTable`, `Preview`, `DiffView`, `Timeline` functional
2. **Add high-value providers** — Files, Projects, Git providers that unlock common queries
3. **Define provider ABCs** — Establish contracts for new provider types
4. **Update integration layer** — Extend `IntentAnalyzer` and `InteractionRouter` for new capabilities
5. **Maintain data-first priority** — Only build what we can immediately populate

## Non-Goals

1. **New primitive components** — Focus on completing stubs, not adding Canvas/Charts yet
2. **External API integrations** — No Email/Finance/Contacts until local providers work
3. **User-configurable providers** — Plugin system is future work
4. **Provider caching layer** — Performance optimization comes after correctness

---

## Current State Assessment

### Primitive Implementation Status

| Primitive | File | Current State | Features |
|-----------|------|---------------|----------|
| DataTable | `studio/src/components/primitives/DataTable.svelte` | ✅ **Complete** (419 lines) | Sort, filter, inline edit, CSV export, type inference |
| Preview | `studio/src/components/primitives/Preview.svelte` | ✅ **Complete** (467 lines) | Markdown, code with line numbers, images, PDF, HTML iframe |
| DiffView | `studio/src/components/primitives/DiffView.svelte` | ✅ **Complete** (456 lines) | LCS diff algorithm, side-by-side + inline modes, stats |
| Timeline | `studio/src/components/primitives/Timeline.svelte` | ✅ **Complete** (572 lines) | Multi-track, 4 zoom levels, today marker, tooltips |

### Existing Provider Infrastructure

| Component | File | Status |
|-----------|------|--------|
| `CalendarProvider` ABC | `src/sunwell/providers/base.py:35-56` | ✅ Complete |
| `ListProvider` ABC | `src/sunwell/providers/base.py:80-108` | ✅ Complete |
| `NotesProvider` ABC | `src/sunwell/providers/base.py:134-163` | ✅ Complete |
| `SunwellCalendar` | `src/sunwell/providers/native/calendar.py` | ✅ Implemented |
| `SunwellLists` | `src/sunwell/providers/native/lists.py` | ✅ Implemented |
| `SunwellNotes` | `src/sunwell/providers/native/notes.py` | ✅ Implemented |
| `FilesProvider` ABC | — | ❌ Does not exist |
| `ProjectsProvider` ABC | — | ❌ Does not exist |
| `GitProvider` ABC | — | ❌ Does not exist |

### Integration Layer

| Component | File | Status |
|-----------|------|--------|
| `IntentAnalyzer` | `src/sunwell/interface/analyzer.py` | ✅ Works, but primitives hardcoded in prompt (line 52) |
| `InteractionRouter` | `src/sunwell/interface/router.py` | ✅ Works, extensible via match statement |
| `ViewRenderer` | `src/sunwell/interface/views.py` | ⚠️ Limited view types |

---

## Design Philosophy

> "Build the primitives you can feed, not the ones you wish you had."

A primitive without data is an empty shell. A provider without a primitive is invisible.

**Priority Formula**: `Data Availability × Composability × Use Frequency`

---

## Design Options

### Option A: Complete Primitives First (Recommended)

Complete all 4 stub primitives before adding any new providers.

**Pros**:
- Validates the primitive architecture end-to-end
- Existing providers (Calendar, Lists, Notes) can feed completed primitives immediately
- Lower risk — working with known contracts

**Cons**:
- Delays high-value queries like "find files" or "show git status"

### Option B: Vertical Slices

Complete one primitive + one provider as a pair, then iterate.

**Pros**:
- Faster time-to-value for specific use cases
- Can validate provider ↔ primitive integration earlier

**Cons**:
- More context switching
- May discover primitive issues late

### Option C: Providers First

Add all provider ABCs and implementations, then complete primitives.

**Pros**:
- Data layer complete; primitives can assume data exists

**Cons**:
- No way to visualize data until primitives done
- Harder to test providers in isolation

**Decision**: Option A with Phase 1 completing Table + Preview primitives alongside Files + Projects providers (a pragmatic hybrid).

---

## Tier 1: Immediate (Complete Existing Stubs)

These primitives have existing scaffolding and can be fed by current providers.

### 1.1 DataTable Primitive (Complete Stub)

**Current**: `studio/src/components/primitives/DataTable.svelte` — 50 line placeholder  
**Data Sources**: Lists provider, any `list[dict]`, file system metadata

```yaml
primitive:
  id: DataTable  # Note: file already named DataTable, not Table
  category: data
  can_be_primary: true
  can_be_secondary: true
  can_be_contextual: true
  
capabilities_to_add:
  - Render any list[dict] as sortable/filterable table
  - Inline editing (with callback to source)
  - Column type inference (text, number, date, checkbox)
  - Export to CSV/JSON
```

**Composability**: ★★★★★
- Lists → Table view of tasks
- Calendar → Table view of events
- Notes → Table of note metadata
- FileTree → Table of files with size, date, type

**Effort**: ~2 days (from stub to functional)

---

### 1.2 Preview Primitive (Extend Stub)

**Current**: `studio/src/components/primitives/Preview.svelte` — 73 lines, iframe only  
**Data Sources**: Any file in project, markdown notes, code output

```yaml
primitive:
  id: Preview
  category: universal
  can_be_primary: false
  can_be_secondary: true
  can_be_contextual: true
  
capabilities_to_add:  # iframe already works
  - Markdown rendering (marked or remark)
  - Image display (detect from file extension)
  - Syntax-highlighted code (Shiki)
  - PDF viewing (pdf.js)
```

**Composability**: ★★★★★
- ProseEditor → Live preview
- CodeEditor → Output preview
- Notes → Rendered view
- FileTree → Quick look

**Effort**: ~3 days (extend existing iframe with content-type routing)

---

### 1.3 DiffView Primitive (Complete Stub)

**Current**: `studio/src/components/primitives/DiffView.svelte` — 50 line placeholder  
**Data Sources**: Git history, file versions, any two text blocks

```yaml
primitive:
  id: DiffView  # Note: file already named DiffView, not Diff
  category: code
  can_be_primary: false
  can_be_secondary: true
  can_be_contextual: true
  
capabilities_to_add:
  - Side-by-side diff (use diff-match-patch or similar)
  - Inline diff
  - Syntax highlighting per language
  - Git integration (compare with HEAD, specific commit)
```

**Composability**: ★★★★☆
- CodeEditor → Compare with git HEAD
- ProseEditor → Version comparison
- Notes → Edit history

**Effort**: ~2 days (diff algorithm + two render modes)

---

### 1.4 Projects Provider (New)

**Current**: No provider exists; `RecentProjects.svelte` has inline logic  
**Data Sources**: `~/Sunwell/projects/` (already scanned), `.sunwell/` metadata

```yaml
provider:
  id: ProjectsProvider
  abc_location: src/sunwell/providers/base.py  # Add new ABC
  
methods:
  - list_projects() -> list[Project]
  - get_project(path: str) -> Project | None
  - get_project_status(path: str) -> ProjectStatus
  - search_projects(query: str) -> list[Project]
```

**Enables**:
- "what projects am I working on"
- "show me the status of Sunwell"
- "find my React projects"

**Effort**: ~1 day (extract from `RecentProjects.svelte`, add ABC)

---

### 1.5 Files Provider (New)

**Current**: No provider exists; `FileTree.svelte` has inline logic  
**Data Sources**: Any directory in file system

```yaml
provider:
  id: FilesProvider
  abc_location: src/sunwell/providers/base.py  # Add new ABC
  
methods:
  - list_files(path: str, recursive: bool = False) -> list[FileInfo]
  - search_files(query: str, path: str | None = None) -> list[FileInfo]
  - read_file(path: str) -> str
  - get_file_metadata(path: str) -> FileMetadata
```

**Enables**:
- "find all Python files in this project"
- "what files did I modify today"
- "show me large files"

**Effort**: ~1 day (extract from `FileTree.svelte`, add ABC)

---

## Tier 2: Near-Term (New Capabilities)

These require new implementations but data is extractable locally.

### 2.1 Timeline Primitive (Complete Stub)

**Current**: `studio/src/components/primitives/Timeline.svelte` — 50 line placeholder  
**Data Sources**: Calendar events, Git commits, file modifications

```yaml
primitive:
  id: Timeline
  category: planning
  can_be_primary: true
  can_be_secondary: true
  can_be_contextual: false
  
capabilities_to_add:
  - Horizontal timeline (hours/days/weeks/months scale)
  - Multiple tracks (calendar, git, files)
  - Zoom levels (day/week/month/year)
  - Event details on hover
```

**Composability**: ★★★★☆
- Calendar → Visual timeline
- Git → Commit timeline
- Projects → Milestone timeline

**Effort**: ~4 days (time scale math is non-trivial)

---

### 2.2 Git Provider (New)

**Current**: No provider exists  
**Data Sources**: Any `.git` directory

```yaml
provider:
  id: GitProvider
  abc_location: src/sunwell/providers/base.py  # Add new ABC
  
methods:
  - get_status(path: str) -> GitStatus
  - get_log(path: str, limit: int = 50) -> list[Commit]
  - get_branches(path: str) -> list[Branch]
  - get_diff(path: str, ref: str = "HEAD") -> str
  - search_commits(query: str, path: str | None = None) -> list[Commit]
```

**Decision needed**: Scope to current project only, or allow any repo path?

**Effort**: ~2 days (git CLI wrapper via `subprocess`)

---

### 2.3 Bookmarks Provider (New)

**Data Sources**: 
- Import from browser (Chrome/Safari/Firefox export)
- Parse markdown files with links
- `.sunwell/bookmarks.json` (native)

```yaml
provider:
  id: BookmarksProvider
  
methods:
  - search(query: str) -> list[Bookmark]
  - get_by_tag(tag: str) -> list[Bookmark]
  - add_bookmark(url: str, title: str, tags: list[str]) -> Bookmark
  - import_browser(browser: str, path: str) -> int  # count imported
```

**Decision needed**: Support all browsers or start with Chrome only?

**Effort**: ~2 days (import parsers for each browser format)

---

## Tier 3: Future (Requires Integration)

These need external API access or significant user setup. **Defer until Tier 1-2 complete.**

| Provider | Data Source | Complexity | Notes |
|----------|-------------|------------|-------|
| Canvas primitive | Freeform drawing | ~5 days | Needs RFC-080 for persistence schema |
| Contacts | vCard import, CardDAV | ~3 days | Fuzzy name matching needed |
| Email | IMAP, Gmail API | ~5 days | Credential management complexity |
| Finance | CSV import, Plaid | ~4 days | Category inference |
| Habits | Native JSON, Apple Health | ~2 days | Simple tracking |

---

## Architecture Impact

### New Provider ABCs

Add to `src/sunwell/providers/base.py`:

```python
@dataclass(frozen=True, slots=True)
class FileInfo:
    path: str
    name: str
    size: int
    modified: datetime
    is_directory: bool

class FilesProvider(ABC):
    @abstractmethod
    async def list_files(self, path: str, recursive: bool = False) -> list[FileInfo]: ...
    @abstractmethod
    async def search_files(self, query: str, path: str | None = None) -> list[FileInfo]: ...
    @abstractmethod
    async def read_file(self, path: str) -> str: ...
    @abstractmethod
    async def get_metadata(self, path: str) -> FileInfo | None: ...

@dataclass(frozen=True, slots=True)
class Project:
    path: str
    name: str
    last_opened: datetime
    status: str  # "active", "archived", "template"

class ProjectsProvider(ABC):
    @abstractmethod
    async def list_projects(self) -> list[Project]: ...
    @abstractmethod
    async def get_project(self, path: str) -> Project | None: ...
    @abstractmethod
    async def search_projects(self, query: str) -> list[Project]: ...
```

### IntentAnalyzer Updates

Extend prompt in `src/sunwell/interface/analyzer.py:52`:

```python
## View Types
- calendar: focus {start, end}
- list: focus {list_name}
- notes: focus {search} or {recent}
- search: query
- table: {data_source, columns}      # NEW
- preview: {file_path}               # NEW
- diff: {left_path, right_path}      # NEW
- timeline: {sources, range}         # NEW
```

### InteractionRouter Updates

Add cases to `src/sunwell/interface/router.py:117-136`:

```python
case "table":
    return await self._handle_table_view(analysis)
case "preview":
    return await self._handle_preview(analysis)
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Timeline rendering complexity underestimated | Medium | Schedule slip | Timebox to 4 days; if incomplete, ship with single-track only |
| Git provider subprocess overhead | Low | Performance | Cache status for 5s; batch log queries |
| Browser bookmark format changes | Low | Import failures | Graceful fallback; log unsupported formats |
| DataTable performance with large datasets | Medium | UX degradation | Virtual scrolling from day 1; limit to 1000 rows initially |
| Provider ABC changes break existing code | Low | Rework | Existing 3 providers are final; new ABCs don't affect them |

---

## Implementation Order

| Phase | Items | Effort | Baseline |
|-------|-------|--------|----------|
| **Phase 1** | DataTable (stub→full), Preview (extend), Projects, Files | 7 days | Stubs exist |
| **Phase 2** | DiffView (stub→full), Git, Bookmarks | 6 days | Stub exists for Diff |
| **Phase 3** | Timeline (stub→full) | 4 days | Stub exists |
| **Phase 4** | Canvas, Contacts, Habits | 10 days | From scratch |
| **Phase 5** | Email, Finance | 9 days | External APIs |

---

## Phase 1 Detailed Plan

### Day 1-2: DataTable Primitive

```
studio/src/components/primitives/DataTable.svelte
├── Accept data: list[dict] prop
├── Column inference from first row
├── Sort state (click header)
├── Filter state (text input per column)
├── Inline edit mode (double-click cell)
└── onEdit callback to parent
```

### Day 3-4: Preview Primitive

```
studio/src/components/primitives/Preview.svelte
├── Content-type detection from path/mime
├── Markdown: use marked + highlight.js
├── Code: Shiki for syntax highlighting  
├── Image: native <img> with lazy loading
├── PDF: pdf.js embed
└── Fallback: plain text display
```

### Day 5: Projects Provider

```
src/sunwell/providers/base.py        # Add ProjectsProvider ABC
src/sunwell/providers/native/projects.py
├── Extract logic from RecentProjects.svelte
├── Scan ~/Sunwell/projects/
├── Read .sunwell/project.json for metadata
└── Fuzzy search by name
```

### Day 6-7: Files Provider

```
src/sunwell/providers/base.py        # Add FilesProvider ABC
src/sunwell/providers/native/files.py
├── Extract logic from FileTree.svelte
├── list_files with os.scandir
├── search_files with glob + ripgrep fallback
└── Metadata: size, mtime, type inference
```

### Integration Updates

```
src/sunwell/interface/analyzer.py    # Add new view types to prompt
src/sunwell/interface/router.py      # Add table/preview handlers
src/sunwell/interface/views.py       # Implement renderers
```

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Functional primitives | 21/25 (4 stubs) | 25/25 | Manual audit |
| Provider ABCs | 3 | 6 | Count in base.py |
| Queries answerable | ~60% | +40% (84%) | Sample 50 common queries |
| Workspace compositions | Limited | 3x | Count valid primary×secondary combos |

---

## Open Questions

1. **Table editing** — Should edits flow back to source provider? 
   - *Proposed*: Yes, via `onEdit(row, column, newValue)` callback

2. **Git provider scope** — Just current project or any repo?
   - *Proposed*: Current project by default; explicit path for others

3. **Browser bookmarks** — Support all browsers or pick one?
   - *Proposed*: Start with Chrome; add Safari/Firefox in Phase 4

4. **Preview security** — How to sandbox HTML preview?
   - *Proposed*: Use `srcdoc` with CSP; no script execution

---

## Related RFCs

- RFC-072: Generative Surface (primitive system)
- RFC-075: Generative Interface (provider system)
- RFC-079: DataTable Primitive (detailed spec) — *to be written*
- RFC-080: Canvas Primitive (detailed spec) — *to be written*
