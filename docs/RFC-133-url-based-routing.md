# RFC-133: URL-Based Routing for Sunwell Studio

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-24  
**Related**: RFC-086 (Startup Params), RFC-132 (ProjectGate), RFC-112 (Observatory)

---

## Executive Summary

This RFC proposes migrating Sunwell Studio from state-based routing (`app.route` rune) to URL-based routing with hash navigation. This enables **bookmarkable URLs**, **browser back/forward navigation**, **deep linking from CLI**, and **refresh resilience** — all without requiring SvelteKit or major architectural changes.

**Current state**: Navigation is stored in `_route = $state<Route>(Route.HOME)` and updated via `navigate()`. The browser URL never changes.

**Proposed state**: URL hash reflects current route and params. Navigation updates the URL, and URL changes update the app state (bidirectional sync).

---

## 🎯 Goals

| Goal | Benefit |
|------|---------|
| **Bookmarkable views** | Save `#/writer?lens=code-review` to quickly return |
| **Browser history** | Back button returns to previous view |
| **Refresh resilience** | F5 stays on current view, not reset to Home |
| **Deep linking** | CLI can open `http://localhost:5173#/project?path=/my/project` |
| **Shareable URLs** | Send colleague a link to specific Observatory visualization |
| **Debugging** | URL shows app state at a glance |

---

## 🚫 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Full SvelteKit migration | Overkill for a local dev tool; hash routing is sufficient |
| Server-side rendering | Not needed; Studio is always client-side |
| SEO optimization | Local tool, not public web app |
| Nested routes | Current flat route structure is appropriate |
| URL-based state persistence | Keep complex state in stores; URLs for navigation only |

---

## 📍 Route Inventory

### Primary Routes (User-Facing)

| Route | URL Pattern | Purpose | Params |
|-------|-------------|---------|--------|
| **Home** | `#/` | Landing, intent routing, project picker | — |
| **Project** | `#/project` | Main workspace | `?tab=project\|pipeline\|memory\|health\|state\|workers` |
| **Projects** | `#/projects` | Full-page project manager | — |
| **Planning** | `#/planning` | Full DAG visualization | `?level=project\|workspace\|environment` |
| **Writer** | `#/writer` | Writing environment | `?lens=<name>&file=<path>` |
| **Library** | `#/library` | Lens browser/editor | `?lens=<name>&view=library\|detail\|editor` |
| **Observatory** | `#/observatory` | AI cognition visualizations | `?viz=<name>&config=<encoded>` |
| **Evaluation** | `#/evaluation` | Performance metrics | `?task=<id>` |
| **Preview** | `#/preview` | Running app preview | — |

### Secondary Routes (Development/QA)

| Route | URL Pattern | Purpose |
|-------|-------------|---------|
| **Demo** | `#/demo` | Prism principle showcase |
| **Gallery** | `#/gallery` | Component visual testing |
| **Interface** | `#/interface` | Legacy conversational entry |

---

## 🗺️ User Journeys

### Journey 1: First-Time User
```
Browser: localhost:5173
    ↓ (no hash)
App: Redirect to #/
    ↓
ProjectGate: No valid project
    ↓
UI: Project creation wizard
    ↓
Navigate: #/project (with new project in store)
```

### Journey 2: Returning User with Bookmark
```
Browser: localhost:5173#/writer?lens=code-review
    ↓
Router: Parse hash → Route.WRITER, params={lens:'code-review'}
    ↓
App: Load Writer with lens pre-selected
    ↓
User: Edits, then clicks "Planning" in nav
    ↓
Navigate: Push #/planning to history
    ↓
User: Clicks browser back button
    ↓
Router: Pop to #/writer?lens=code-review
    ↓
App: Return to Writer (state preserved in store)
```

### Journey 3: CLI Deep Link
```
CLI: sunwell studio --project /my/app --mode writer --lens coder
    ↓ (current: WebSocket startup_params event)
    ↓ (proposed: open browser with URL)
Browser: localhost:5173#/writer?lens=coder
    ↓
App: Project loaded from CLI context, Writer opens
```

### Journey 4: Share Observatory Visualization
```
User A: Views ModelParadox in Observatory
    ↓
URL: #/observatory?viz=model-paradox&config=eyJ...encoded...
    ↓
User A: Copies URL, sends to User B
    ↓
User B: Opens link
    ↓
Router: Parse → load Observatory with same visualization state
```

### Journey 5: Tab Navigation in Project
```
User: On #/project (defaults to Project tab)
    ↓
Clicks "Pipeline" tab
    ↓
Navigate: Replace #/project?tab=pipeline
    ↓
User: Bookmarks this URL
    ↓
Later: Opens bookmark
    ↓
App: Opens Project view with Pipeline tab active
```

---

## 🏗️ Technical Design

### Approach: Hash-Based Routing

Use `window.location.hash` for routing. This approach:
- Works without server configuration
- Doesn't trigger page reloads
- Supports browser history API
- Requires minimal changes to existing code

### Core Router Module

```typescript
// studio/src/lib/router.ts

import { Route } from './constants';

export interface RouteState {
  route: Route;
  params: Record<string, string>;
}

/** Parse hash into route state */
export function parseHash(hash: string): RouteState {
  // Remove leading #/ or #
  const path = hash.replace(/^#\/?/, '');
  const [routePart, queryPart] = path.split('?');
  
  // Map path to Route constant
  const route = routeFromPath(routePart) ?? Route.HOME;
  
  // Parse query params
  const params: Record<string, string> = {};
  if (queryPart) {
    for (const pair of queryPart.split('&')) {
      const [key, value] = pair.split('=');
      if (key) params[key] = decodeURIComponent(value ?? '');
    }
  }
  
  return { route, params };
}

/** Build hash from route state */
export function buildHash(route: Route, params?: Record<string, string>): string {
  const path = pathFromRoute(route);
  const query = params ? buildQuery(params) : '';
  return query ? `#/${path}?${query}` : `#/${path}`;
}

/** Navigate to route (updates URL and state) */
export function navigateTo(route: Route, params?: Record<string, string>): void {
  const hash = buildHash(route, params);
  window.location.hash = hash;
  // State update happens via hashchange listener
}

/** Replace current route (no history entry) */
export function replaceTo(route: Route, params?: Record<string, string>): void {
  const hash = buildHash(route, params);
  window.history.replaceState(null, '', hash);
  // Manually trigger state update since replaceState doesn't fire hashchange
  syncStateFromHash();
}
```

### Route Mapping

```typescript
// studio/src/lib/router.ts (continued)

const ROUTE_PATHS: Record<Route, string> = {
  [Route.HOME]: '',
  [Route.PROJECT]: 'project',
  [Route.PROJECTS]: 'projects',
  [Route.PLANNING]: 'planning',
  [Route.WRITER]: 'writer',
  [Route.LIBRARY]: 'library',
  [Route.OBSERVATORY]: 'observatory',
  [Route.EVALUATION]: 'evaluation',
  [Route.PREVIEW]: 'preview',
  [Route.DEMO]: 'demo',
  [Route.GALLERY]: 'gallery',
  [Route.INTERFACE]: 'interface',
};

const PATH_ROUTES = Object.fromEntries(
  Object.entries(ROUTE_PATHS).map(([k, v]) => [v, k as Route])
);

function routeFromPath(path: string): Route | null {
  return PATH_ROUTES[path] ?? null;
}

function pathFromRoute(route: Route): string {
  return ROUTE_PATHS[route] ?? '';
}
```

### App Store Integration

```typescript
// studio/src/stores/app.svelte.ts (modified)

import { parseHash, buildHash, type RouteState } from '$lib/router';

let _route = $state<Route>(Route.HOME);
let _params = $state<Record<string, string>>({});

// Sync from URL on initial load and hash changes
function syncStateFromHash(): void {
  const { route, params } = parseHash(window.location.hash);
  _route = route;
  _params = params;
}

// Initialize router
export function initRouter(): () => void {
  // Sync on load
  syncStateFromHash();
  
  // Listen for hash changes (back/forward, manual URL edit)
  const handleHashChange = () => syncStateFromHash();
  window.addEventListener('hashchange', handleHashChange);
  
  return () => window.removeEventListener('hashchange', handleHashChange);
}

// Navigate (now updates URL)
export function navigate(route: Route, params?: Record<string, string>): void {
  const hash = buildHash(route, params);
  window.location.hash = hash;
}

// Helper for in-place param updates (tab changes, etc.)
export function updateParams(updates: Record<string, string>): void {
  const newParams = { ..._params, ...updates };
  // Filter out empty values
  const filtered = Object.fromEntries(
    Object.entries(newParams).filter(([_, v]) => v)
  );
  const hash = buildHash(_route, filtered);
  window.history.replaceState(null, '', hash);
  _params = filtered;
}
```

### App.svelte Initialization

```svelte
<!-- studio/src/App.svelte (modified) -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { initRouter } from './stores/app.svelte';
  
  onMount(() => {
    const cleanupRouter = initRouter();
    // ... existing setup ...
    
    return () => {
      cleanupRouter();
      // ... existing cleanup ...
    };
  });
</script>
```

---

## 🔄 Migration Strategy

### Phase 1: Add Router (Non-Breaking)

1. Add `router.ts` module with parsing/building functions
2. Add `initRouter()` to app store
3. Call `initRouter()` in `App.svelte` onMount
4. **No changes to existing `navigate()` calls yet**

State after Phase 1:
- URL updates when navigating
- Manual URL edits work
- Back/forward buttons work
- Existing code unchanged

### Phase 2: Update Navigation Calls

Update callers to pass params properly:

```typescript
// Before
goToWriter();
_params = { filePath, lens };

// After  
navigate(Route.WRITER, { file: filePath, lens });
```

### Phase 3: Add Route-Specific Params

Update route components to read from `app.params`:

```svelte
<!-- Writer.svelte -->
<script>
  import { app } from '../stores/app.svelte';
  
  // Before: params set separately by goToWriter()
  // After: read from URL params
  const lensName = $derived(app.params.lens ?? 'tech-writer');
  const filePath = $derived(app.params.file);
</script>
```

### Phase 4: CLI Integration

Update CLI to open browser with URL:

```python
# Before (open_cmd.py)
launch_studio(project=path, lens=lens, mode=mode)
# Sends WebSocket startup_params event

# After
import webbrowser
url = f"http://localhost:5173#/{mode}?lens={lens}"
webbrowser.open(url)
# Project context still via server/store, but route via URL
```

---

## 🔀 Alternatives Considered

### Alternative A: SvelteKit Migration (Rejected)

**Approach**: Full migration to SvelteKit with file-based routing.

**Pros**:
- Industry-standard approach
- Built-in SSR support
- Automatic code splitting

**Cons**:
- Massive migration effort
- SSR not needed (local tool)
- Overkill for 12 flat routes
- Would require restructuring entire codebase

**Decision**: Rejected — hash routing achieves goals with minimal effort.

### Alternative B: `svelte-spa-router` Library (Considered)

**Approach**: Use third-party router library.

**Pros**:
- Battle-tested
- Declarative route definitions
- Built-in guards/transitions

**Cons**:
- External dependency
- Learning curve for team
- May not integrate cleanly with Svelte 5 runes
- Our needs are simple enough for custom solution

**Decision**: Deferred — start with custom implementation, adopt library if complexity grows.

### Alternative C: History API (pushState) (Considered)

**Approach**: Use clean URLs (`/project` instead of `#/project`).

**Pros**:
- Cleaner URLs
- More "modern" feel

**Cons**:
- Requires server configuration (catch-all route)
- Vite dev server needs config
- More complex for local file serving

**Decision**: Deferred — hash routing works without server changes. Can migrate later if needed.

---

## 📊 URL Schema Reference

### Complete URL Examples

```
# Home (default)
http://localhost:5173#/

# Project with specific tab
http://localhost:5173#/project?tab=pipeline

# Writer with lens and file
http://localhost:5173#/writer?lens=code-review&file=/src/main.py

# Library viewing specific lens
http://localhost:5173#/library?lens=tech-writer&view=editor

# Planning at workspace level
http://localhost:5173#/planning?level=workspace

# Observatory with shared config
http://localhost:5173#/observatory?viz=model-paradox&config=eyJzY2FsZSI6MiwicGF1c2VkIjpmYWxzZX0

# Evaluation running specific task
http://localhost:5173#/evaluation?task=code-generation-01
```

### Param Encoding Rules

1. **Simple values**: Direct encoding (`lens=code-review`)
2. **Paths**: URL-encoded (`file=%2Fsrc%2Fmain.py`)
3. **Complex objects**: Base64-encoded JSON (`config=eyJ...`)
4. **Arrays**: Comma-separated (`tabs=project,pipeline`)

---

## ✅ Acceptance Criteria

### Must Have
- [ ] URL updates when navigating between routes
- [ ] Browser back/forward buttons work correctly
- [ ] Page refresh preserves current route
- [ ] Deep links work (paste URL → correct view loads)
- [ ] All 12 routes have URL mappings

### Should Have
- [ ] Route params reflected in URL (lens, file, tab, etc.)
- [ ] CLI can open specific URLs
- [ ] Observatory share URLs work

### Nice to Have
- [ ] URL updates on tab changes (replaceState, no history spam)
- [ ] Keyboard shortcut to copy current URL
- [ ] Analytics tracking via URL (future)

---

## 🧪 Testing Strategy

### Manual Testing Matrix

| Scenario | Steps | Expected |
|----------|-------|----------|
| Fresh load | Open `localhost:5173` | Redirects to `#/`, shows Home |
| Deep link | Open `#/writer?lens=coder` | Writer loads with coder lens |
| Back button | Navigate Home→Project→Planning, click back | Returns to Project |
| Refresh | On `#/project?tab=pipeline`, press F5 | Same view after reload |
| Invalid route | Navigate to `#/invalid` | Falls back to Home |
| Manual URL edit | Change `#/project` to `#/writer` | Switches to Writer |

### Automated Tests

```typescript
// studio/src/lib/router.test.ts
import { describe, it, expect } from 'vitest';
import { parseHash, buildHash } from './router';
import { Route } from './constants';

describe('parseHash', () => {
  it('parses empty hash as home', () => {
    expect(parseHash('')).toEqual({ route: Route.HOME, params: {} });
  });
  
  it('parses route with params', () => {
    expect(parseHash('#/writer?lens=coder&file=%2Fsrc%2Fmain.py')).toEqual({
      route: Route.WRITER,
      params: { lens: 'coder', file: '/src/main.py' }
    });
  });
});

describe('buildHash', () => {
  it('builds hash with params', () => {
    expect(buildHash(Route.WRITER, { lens: 'coder' })).toBe('#/writer?lens=coder');
  });
});
```

---

## 📈 Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Routes with URL support | 0/12 | 12/12 |
| Back button works | No | Yes |
| Refresh preserves state | No | Yes |
| CLI deep linking | Via WebSocket | Via URL |

---

## 🗓️ Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | Router module + init | 2 hours |
| **2** | Update navigation calls | 3 hours |
| **3** | Route-specific params | 4 hours |
| **4** | CLI integration | 2 hours |
| **5** | Testing + polish | 3 hours |

**Total estimated effort**: 14 hours (2 days)

---

## 📚 References

- [MDN: Using the History API](https://developer.mozilla.org/en-US/docs/Web/API/History_API)
- [Hash-based routing explained](https://www.patterns.dev/posts/client-side-routing)
- [Svelte 5 runes documentation](https://svelte.dev/docs/svelte/$state)
- RFC-086: Startup Params (current CLI→Studio communication)
- RFC-132: ProjectGate (project validation at entry)
