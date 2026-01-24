# RFC-113: Native HTTP Bridge — Python ↔ Svelte Direct Communication

**Status**: Draft  
**Created**: 2026-01-23  
**Author**: @llane  
**Breaking**: YES — Removes Rust/Tauri layer  
**Priority**: P1 — Architecture Simplification

---

## Summary

Replace the current **Python → Rust (Tauri) → Svelte** architecture with **Python → HTTP/WebSocket → Svelte**. This eliminates 13,000+ lines of Rust glue code that provides no unique value—just subprocess spawning and JSON forwarding.

**The thesis**: Rust adds complexity without value in our architecture. Python can serve HTTP directly; Svelte can run in a browser. One fewer language, zero subprocess fragility.

---

## Problem Statement

### Current Architecture (3-Language Bridge)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SVELTE FRONTEND                              │
│                                                                     │
│  TypeScript event handlers → waits for Tauri IPC                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ Tauri IPC
┌─────────────────────────────────────────────────────────────────────┐
│                     RUST BACKEND (13K lines)                        │
│                                                                     │
│  27 modules × ~480 lines each                                       │
│  What they do: spawn subprocess, read stdout, forward JSON          │
│  What they DON'T do: ML inference, computation, unique value        │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ subprocess stdout (NDJSON)
┌─────────────────────────────────────────────────────────────────────┐
│                       PYTHON BACKEND                                │
│                                                                     │
│  Actual intelligence: LLM calls, planning, tools, memory            │
│  95 event types, 50K+ lines of real logic                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Pain Points

| Problem | Evidence | Impact |
|---------|----------|--------|
| **Event synchronization hell** | 8+ rounds of "fix event X missing field Y" in chat history | Hours of debugging, fragile releases |
| **Three languages, three places to add event types** | Python `EventType`, Rust `NaaruEvent`, TypeScript handlers | Every new event = 3 files to change |
| **Subprocess fragility** | `Command::new("sunwell")` — process spawn, PATH issues, stderr interleaving | Windows issues, debugging nightmares |
| **No Rust value-add** | 13K lines of Rust does: spawn, read, forward. No ML, no unique capability | Maintenance burden for zero benefit |
| **Compilation overhead** | Rust incremental builds ~30s, full ~2min | Slow iteration during UI development |

### What Rust Actually Does

Looking at `studio/src-tauri/src/`:

| Module | Lines | What It Does |
|--------|-------|--------------|
| `dag.rs` | 1,994 | DAG visualization, subprocess spawn |
| `commands.rs` | 1,693 | Aggregated command handlers |
| `agent.rs` | 692 | Spawn subprocess, duplicate EventType enum (lines 23-136) |
| `memory.rs` | 688 | Spawn `sunwell memory` subprocess, forward result |
| `heuristic_detect.rs` | 661 | Heuristic detection, subprocess |
| `workspace.rs` | 653 | Spawn `sunwell workspace` subprocess |
| `writer.rs` | 625 | Writing assistance, subprocess |
| `lens.rs` | 593 | Spawn `sunwell lens` subprocess |
| ... (19 more) | ~5,333 | Same pattern: subprocess spawn, JSON forward |

**Total: 12,932 lines of Rust across 27 modules, with 127 subprocess spawn calls.**

### Why We Originally Chose Tauri

1. ✅ **Desktop app packaging** — Cross-platform .app/.exe/.deb
2. ✅ **System access** — File system, shell execution
3. ⚠️ **Performance** — Assumed native was faster (wrong — LLM calls dominate)
4. ❌ **Rust ecosystem** — Never used (no Rust ML, no Rust-native features)

**Realization**: We use Tauri as a glorified WebView wrapper. Electron does the same. So does a browser + local Python server.

---

## Proposed Architecture

### Python HTTP/WebSocket Server + Browser UI

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER                                     │
│                                                                     │
│  Svelte SPA                                                         │
│  - Same components, stores, styling                                 │
│  - fetch() for REST, WebSocket for streaming                        │
│  - Optional: Electron/Tauri wrapper for desktop packaging           │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ HTTP REST + WebSocket
┌─────────────────────────────────────────────────────────────────────┐
│                     PYTHON SERVER                                   │
│                                                                     │
│  FastAPI/Litestar/Starlette                                         │
│  - /api/run POST → start agent, return run_id                       │
│  - /api/events/{run_id} WebSocket → stream events                   │
│  - /api/memory GET/POST → memory operations                         │
│  - Direct access to agent, no subprocess                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ direct Python import
┌─────────────────────────────────────────────────────────────────────┐
│                       PYTHON AGENT                                  │
│                                                                     │
│  Same code, zero changes:                                           │
│  - AdaptiveAgent, HarmonicPlanner, Naaru                            │
│  - Tools, memory, validation                                        │
│  - Event streaming via async yield                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Benefits

| Benefit | Before | After |
|---------|--------|-------|
| **Languages** | 3 (Python, Rust, TypeScript) | 2 (Python, TypeScript) |
| **Event definition** | 3 places | 1 (Python) + TypeScript types |
| **Subprocess spawn** | Every Tauri command | Never (direct import) |
| **Build time** | ~2min (Rust) | ~5s (Vite HMR) |
| **Lines of code** | +13K Rust | -13K Rust |
| **Debugging** | stdout/stderr parsing, process isolation | Python debugger, breakpoints |

---

## Design

### Run Management

Agent runs are tracked by `run_id` to support:
- **Concurrent runs**: Multiple browser tabs or clients
- **Resumable connections**: WebSocket reconnection to existing run
- **Cancellation**: Stop a run mid-execution

```python
# src/sunwell/server/runs.py
from dataclasses import dataclass, field
from uuid import uuid4
import threading

@dataclass
class RunState:
    run_id: str
    goal: str
    status: str = "pending"  # pending | running | complete | cancelled | error
    events: list[dict] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)

# In-memory run registry (single server instance)
_runs: dict[str, RunState] = {}
_lock = threading.Lock()

def create_run(goal: str) -> RunState:
    run_id = str(uuid4())
    run = RunState(run_id=run_id, goal=goal)
    with _lock:
        _runs[run_id] = run
    return run

def get_run(run_id: str) -> RunState | None:
    return _runs.get(run_id)
```

### Event Streaming via WebSocket

**Design choice**: Goal is sent via POST body, not URL path. This avoids URL-encoding issues with long/complex goals containing special characters.

```python
# src/sunwell/server/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sunwell.agent.core import Agent
from sunwell.server.runs import create_run, get_run

app = FastAPI(title="Sunwell Studio API")

class RunRequest(BaseModel):
    goal: str
    workspace: str | None = None
    lens: str | None = None

@app.post("/api/run")
async def start_run(request: RunRequest) -> dict:
    """Start an agent run, return run_id for WebSocket connection."""
    run = create_run(request.goal)
    return {"run_id": run.run_id, "status": "pending"}

@app.websocket("/api/run/{run_id}/events")
async def stream_events(websocket: WebSocket, run_id: str):
    """Stream agent events over WebSocket."""
    await websocket.accept()
    
    run = get_run(run_id)
    if not run:
        await websocket.send_json({"type": "error", "data": {"message": "Run not found"}})
        await websocket.close(code=4004)
        return
    
    # Replay any buffered events (for reconnection)
    for event in run.events:
        await websocket.send_json(event)
    
    if run.status == "complete":
        await websocket.close()
        return
    
    # Start agent if not already running
    if run.status == "pending":
        run.status = "running"
        agent = Agent()
        try:
            async for event in agent.run(run.goal):
                event_dict = event.to_dict()
                run.events.append(event_dict)  # Buffer for reconnection
                await websocket.send_json(event_dict)
                
                if run.cancel_event.is_set():
                    await websocket.send_json({"type": "cancelled", "data": {}})
                    break
            run.status = "complete"
        except WebSocketDisconnect:
            pass  # Client disconnected, run continues in background
        except Exception as e:
            run.status = "error"
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        finally:
            await websocket.close()

@app.delete("/api/run/{run_id}")
async def cancel_run(run_id: str) -> dict:
    """Cancel a running agent."""
    run = get_run(run_id)
    if not run:
        return {"error": "Run not found"}
    run.cancel_event.set()
    run.status = "cancelled"
    return {"status": "cancelled"}
```

```typescript
// studio/src/lib/api.ts
export async function startRun(goal: string, options?: { workspace?: string; lens?: string }) {
  const response = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, ...options }),
  });
  return response.json() as Promise<{ run_id: string; status: string }>;
}

export function streamEvents(runId: string, onEvent: (event: AgentEvent) => void) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${window.location.host}/api/run/${runId}/events`);
  
  ws.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    onEvent(event);
  };
  
  return {
    stop: () => ws.close(),
    cancel: async () => {
      await fetch(`/api/run/${runId}`, { method: 'DELETE' });
      ws.close();
    },
  };
}

// Convenience wrapper
export async function runAgent(goal: string, onEvent: (event: AgentEvent) => void) {
  const { run_id } = await startRun(goal);
  return streamEvents(run_id, onEvent);
}
```

### REST Endpoints for Non-Streaming

```python
@app.get("/api/memory")
async def get_memory() -> dict:
    """Get current session memory."""
    from sunwell.simulacrum import Simulacrum
    sim = Simulacrum.load()
    return sim.to_dict()

@app.get("/api/lenses")
async def list_lenses() -> list[dict]:
    """List available lenses."""
    from sunwell.lens import LensLibrary
    library = LensLibrary()
    return [lens.to_dict() for lens in library.list()]

@app.post("/api/project/analyze")
async def analyze_project(path: str) -> dict:
    """Analyze project structure."""
    from sunwell.project import ProjectAnalyzer
    analyzer = ProjectAnalyzer(path)
    return analyzer.analyze().to_dict()
```

### Same-Origin Serving (Recommended)

Serve Svelte static files from the Python server to eliminate CORS entirely:

```python
# src/sunwell/server/main.py
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Svelte build output location
STATIC_DIR = Path(__file__).parent.parent.parent.parent / "studio" / "build"

@app.get("/")
async def serve_spa():
    """Serve the Svelte SPA."""
    return FileResponse(STATIC_DIR / "index.html")

# Mount static assets AFTER API routes
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

**Benefits**:
- No CORS configuration needed
- Simpler deployment (single `sunwell serve` command)
- WebSocket connects to same origin automatically
- Works with browser security restrictions

### Type Safety via Pydantic + Code Generation

```python
# src/sunwell/server/generate_types.py
"""Generate TypeScript types from Python Pydantic models."""
from sunwell.agent.events import EventType
from sunwell.server.models import AgentEventSchema, RunRequest

def generate_typescript() -> str:
    """Generate TypeScript definitions from Python source of truth."""
    lines = [
        "// AUTO-GENERATED by: python -m sunwell.server.generate_types",
        "// DO NOT EDIT - changes will be overwritten",
        "",
        "export type EventType =",
    ]
    
    # Generate EventType union from Python enum
    event_values = [f'  | "{e.value}"' for e in EventType]
    lines.extend(event_values)
    lines.append("  ;")
    lines.append("")
    
    # Generate interfaces from Pydantic models
    lines.extend([
        "export interface AgentEvent {",
        "  type: EventType;",
        "  timestamp: number;",
        "  data: Record<string, unknown>;",
        "  ui_hints?: UIHints;",
        "}",
        "",
        "export interface UIHints {",
        "  icon?: string;",
        "  severity: 'info' | 'success' | 'warning' | 'error';",
        "  animation?: string;",
        "  progress?: number;",
        "}",
        "",
        "export interface RunRequest {",
        "  goal: string;",
        "  workspace?: string;",
        "  lens?: string;",
        "}",
        "",
        "export interface RunResponse {",
        "  run_id: string;",
        "  status: 'pending' | 'running' | 'complete' | 'cancelled' | 'error';",
        "}",
    ])
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(generate_typescript())
```

**Usage in build pipeline**:

```bash
# Generate before Vite build
python -m sunwell.server.generate_types > studio/src/lib/types.generated.ts
cd studio && npm run build
```

**Single source of truth**: Python defines events, TypeScript types are generated at build time.

### Desktop Packaging (If Needed)

Two options for desktop distribution:

**Option A: Electron Wrapper (Lightweight)**

```javascript
// electron/main.js
const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');

let pythonServer;

app.whenReady().then(() => {
  // Start Python server
  pythonServer = spawn('sunwell', ['serve', '--port', '8080']);
  
  // Create browser window pointing to local server
  const win = new BrowserWindow({ width: 1200, height: 800 });
  win.loadURL('http://localhost:8080');
});

app.on('quit', () => pythonServer?.kill());
```

**Option B: Browser-Only (Simplest)**

```bash
# User runs:
sunwell serve --open  # Starts server and opens browser

# Or with specific port:
sunwell serve --port 8080 --open
```

---

## CLI Serve Command

### Specification

```python
# src/sunwell/cli/serve_cmd.py
"""HTTP server command for Studio UI."""
import click
import webbrowser
from pathlib import Path

@click.command()
@click.option("--port", default=8080, help="Port to listen on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--open", "open_browser", is_flag=True, help="Open browser automatically")
@click.option("--dev", is_flag=True, help="Development mode (CORS enabled, no static)")
def serve(port: int, host: str, open_browser: bool, dev: bool):
    """Start the Sunwell Studio HTTP server.
    
    In production mode (default), serves the Svelte UI from the same origin.
    In development mode (--dev), enables CORS for Vite dev server on :5173.
    
    Examples:
        sunwell serve              # Start on localhost:8080
        sunwell serve --open       # Start and open browser
        sunwell serve --dev        # API only, for Vite dev server
    """
    import uvicorn
    from sunwell.server.main import create_app
    
    app = create_app(dev_mode=dev)
    
    url = f"http://{host}:{port}"
    click.echo(f"🌐 Sunwell Studio: {url}")
    
    if dev:
        click.echo("   Mode: Development (CORS enabled)")
        click.echo("   Run Vite separately: cd studio && npm run dev")
    else:
        click.echo("   Mode: Production (serving static UI)")
    
    if open_browser and not dev:
        webbrowser.open(url)
    
    uvicorn.run(app, host=host, port=port, log_level="info")
```

### App Factory

```python
# src/sunwell/server/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app(dev_mode: bool = False) -> FastAPI:
    """Create FastAPI application.
    
    Args:
        dev_mode: If True, enable CORS for Vite dev server.
                  If False, serve static Svelte build.
    """
    app = FastAPI(
        title="Sunwell Studio",
        description="AI Agent Development Environment",
        version="0.1.0",
    )
    
    # Register API routes
    from sunwell.server import routes
    app.include_router(routes.router, prefix="/api")
    
    if dev_mode:
        # Development: CORS for Vite on :5173
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Production: Serve Svelte static build
        from sunwell.server.static import mount_static
        mount_static(app)
    
    return app
```

---

## Migration Plan

### Phase 1: Add HTTP Server (Parallel Path)

**Goal**: Ship HTTP server alongside existing Tauri, no breaking changes.

**Tasks**:
1. Add `sunwell/server/` module with FastAPI app
2. Implement WebSocket streaming for `/api/run`
3. Implement REST endpoints for memory, lenses, project
4. Add TypeScript type generation script
5. Create `sunwell serve` CLI command

**Svelte Changes**:
- Add `USE_HTTP` environment variable
- When `USE_HTTP=true`, use fetch/WebSocket instead of Tauri invoke

```typescript
// studio/src/lib/api.ts
const USE_HTTP = import.meta.env.VITE_USE_HTTP === 'true';

export async function runGoal(goal: string): Promise<void> {
  if (USE_HTTP) {
    // New: WebSocket to Python server
    return runGoalHTTP(goal);
  } else {
    // Legacy: Tauri invoke
    return invoke('process_goal', { goal });
  }
}
```

### Phase 2: Validate HTTP Path

**Goal**: Ensure feature parity, no regressions.

**Tasks**:
1. Run full test suite with `USE_HTTP=true`
2. Validate all 70+ event types flow correctly
3. Performance comparison (latency, throughput)
4. Windows/macOS/Linux testing
5. Fix any issues discovered

### Phase 3: Deprecate Tauri Commands

**Goal**: Remove Rust command handlers one by one.

**Order** (by usage frequency):
1. `naaru.rs` (main agent execution)
2. `agent.rs` (legacy agent commands)
3. `memory.rs` (memory operations)
4. `project.rs` (project analysis)
5. `lens.rs` (lens operations)
6. ... remaining 22 modules

**Per-module process**:
1. Mark Tauri command as deprecated
2. Update Svelte to always use HTTP for that feature
3. Remove Rust module after 1 release cycle

### Phase 4: Remove Rust Layer

**Goal**: Complete migration, delete `src-tauri/src/`.

**Tasks**:
1. Delete all Rust command modules
2. Update `tauri.conf.json` to minimal (if keeping Tauri for packaging)
3. OR switch to Electron/browser-only distribution
4. Update CI/CD pipelines
5. Update documentation

### Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 1 week | HTTP server working in parallel |
| Phase 2 | 1 week | Full validation, feature parity |
| Phase 3 | 2 weeks | Incremental Rust removal |
| Phase 4 | 1 week | Complete migration |
| **Total** | **5 weeks** | Rust-free architecture |

---

## API Design

### Core Endpoints

```yaml
# Agent Execution
POST   /api/run                    # Start agent run, returns run_id
GET    /api/run/{run_id}           # Get run status
DELETE /api/run/{run_id}           # Cancel run
WS     /api/run/{run_id}/events    # Stream events (WebSocket)

# Memory
GET    /api/memory                 # Get current session memory
POST   /api/memory/checkpoint      # Save checkpoint
DELETE /api/memory                 # Clear session

# Lenses
GET    /api/lenses                 # List all lenses
GET    /api/lenses/{id}            # Get lens details
POST   /api/lenses/{id}/activate   # Set active lens

# Project
GET    /api/project                # Get current project info
POST   /api/project/analyze        # Analyze project structure
GET    /api/project/files          # List project files

# Health
GET    /api/health                 # Server health check
GET    /api/config                 # Get current configuration
```

### WebSocket Protocol

```typescript
// Client → Server
interface ClientMessage {
  type: 'start' | 'stop' | 'ping';
  payload?: unknown;
}

// Server → Client
interface ServerMessage {
  type: EventType | 'pong' | 'error';
  timestamp: number;
  data: Record<string, unknown>;
}
```

### Error Handling

```json
// HTTP errors
{
  "error": {
    "code": "AGENT_ERROR",
    "message": "Model not available",
    "details": { "provider": "anthropic", "status": 401 }
  }
}

// WebSocket errors (sent as event)
{
  "type": "error",
  "timestamp": 1706000000.0,
  "data": {
    "message": "Task execution failed",
    "task_id": "task-3",
    "recoverable": false
  }
}
```

---

## Session Management

### Current State (Tauri)

In the current architecture, session state lives in:
1. **Rust memory** — Active run state, WebSocket connections
2. **Python subprocess** — Simulacrum memory loaded per-run
3. **Disk** — `.sunwell/memory.json` persisted between runs

### New Architecture (HTTP)

**Stateless server with file-backed persistence**:

```python
# Session state strategy:
# 1. Run state: In-memory dict keyed by run_id (lost on server restart)
# 2. Memory/Simulacrum: Loaded from disk per-run (survives restarts)
# 3. Active workspace: Passed per-request or stored in browser localStorage

# No cookies or tokens needed for single-user local server
# Multi-user/remote deployment would need auth (out of scope for v1)
```

**Run lifecycle**:
```
POST /api/run {goal, workspace}
  → Create RunState in memory
  → Return run_id

WS /api/run/{run_id}/events
  → Load Simulacrum from disk (workspace/.sunwell/memory.json)
  → Execute agent, stream events
  → Save Simulacrum on complete
  → RunState remains in memory for reconnection

# On server restart: run_ids lost, but Simulacrum persisted
```

**Browser-side state**:
```typescript
// studio/src/lib/session.ts
export function getWorkspace(): string | null {
  return localStorage.getItem('sunwell_workspace');
}

export function setWorkspace(path: string): void {
  localStorage.setItem('sunwell_workspace', path);
}
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **CORS issues** | Medium | Use same-origin (serve Svelte from Python); dev mode enables CORS for Vite |
| **WebSocket reconnection** | Medium | Buffer events per run_id; client reconnects and replays from buffer |
| **Process isolation lost** | Low | Python errors crash server, not just subprocess — add exception handlers, structured logging |
| **Desktop packaging** | Low | Electron wrapper is trivial (20 lines); or accept browser-only for v1 |
| **Breaking change** | High | Phased migration with `VITE_USE_HTTP` feature flag ensures rollback |
| **Run state lost on restart** | Low | Simulacrum persists to disk; only in-flight runs lost (acceptable for local dev tool) |
| **Concurrent access** | Low | Single-user assumption; run registry uses threading.Lock for safety |

---

## Alternatives Considered

### Alternative A: Keep Tauri, Auto-Generate Rust

Generate Rust command handlers from Python definitions.

**Pros**: Keep desktop packaging, single binary  
**Cons**: Still 3 languages, still subprocess spawning, generated code is fragile

**Verdict**: ❌ Doesn't solve the fundamental complexity

### Alternative B: All-Rust + Svelte

Rewrite Python agent in Rust.

**Pros**: Fastest possible performance, single native binary  
**Cons**: 50K+ lines to rewrite, Rust ML ecosystem immature, 6+ months work

**Verdict**: ❌ Not worth the effort; LLM calls dominate latency, not language runtime

### Alternative C: Keep Architecture, Better Tooling

Add better event type generation, shared schemas, etc.

**Pros**: No migration needed  
**Cons**: Doesn't fix subprocess fragility, still 3 languages, still manual sync

**Verdict**: ❌ Band-aid on a design problem

---

## Success Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Event sync bugs | ~2/week | 0 | GitHub issues tagged `event-sync` |
| Build time (UI changes) | ~2 min | < 10s | CI timing |
| Lines of code | 12,932 Rust | 0 Rust | `wc -l studio/src-tauri/src/*.rs` |
| Languages maintained | 3 | 2 | Python + TypeScript only |
| Event types duplicated | 95 in Python, 95 in Rust | 95 in Python only | TypeScript generated |
| New event type cost | 3 files, ~30 min | 1 file + `make types`, ~5 min | Developer time |
| Subprocess spawns | 127 calls | 0 | `grep sunwell_command` |

---

## Implementation Checklist

### Phase 1: HTTP Server

**Server Module** (`src/sunwell/server/`):
- [ ] Create `src/sunwell/server/__init__.py`
- [ ] Create `src/sunwell/server/main.py` — FastAPI app factory
- [ ] Create `src/sunwell/server/routes.py` — API endpoint handlers
- [ ] Create `src/sunwell/server/runs.py` — Run state management
- [ ] Create `src/sunwell/server/static.py` — Static file serving
- [ ] Create `src/sunwell/server/generate_types.py` — TypeScript codegen

**Endpoints**:
- [ ] `POST /api/run` — Start agent run, return run_id
- [ ] `GET /api/run/{run_id}` — Get run status
- [ ] `DELETE /api/run/{run_id}` — Cancel run
- [ ] `WS /api/run/{run_id}/events` — Stream events with reconnection support
- [ ] `GET /api/memory` — Get session memory
- [ ] `POST /api/memory/checkpoint` — Save checkpoint
- [ ] `GET /api/lenses` — List lenses
- [ ] `POST /api/lenses/{id}/activate` — Activate lens
- [ ] `GET /api/project` — Get project info
- [ ] `POST /api/project/analyze` — Analyze project
- [ ] `GET /api/health` — Health check

**CLI**:
- [ ] Create `src/sunwell/cli/serve_cmd.py`
- [ ] Register `serve` command in CLI main
- [ ] Support `--port`, `--host`, `--open`, `--dev` flags

**Dependencies**:
- [ ] Move `fastapi` and `uvicorn` from optional to required in `pyproject.toml`

**Svelte Integration**:
- [ ] Add `VITE_USE_HTTP` feature flag
- [ ] Create `studio/src/lib/api-http.ts` — HTTP/WebSocket client
- [ ] Update stores to use conditional API layer
- [ ] Generate `studio/src/lib/types.generated.ts`
- [ ] Add npm script: `"generate-types": "python -m sunwell.server.generate_types > src/lib/types.generated.ts"`

### Phase 2: Validation

- [ ] Create HTTP integration tests (`tests/server/`)
- [ ] Test all 95 event types flow correctly
- [ ] Test WebSocket reconnection and event replay
- [ ] Test concurrent runs (multiple run_ids)
- [ ] Test cancellation mid-run
- [ ] Performance benchmark: latency (HTTP vs Tauri IPC)
- [ ] Performance benchmark: throughput (events/sec)
- [ ] Cross-platform testing (macOS, Linux, Windows)
- [ ] Error handling validation (network failures, invalid requests)

### Phase 3: Migration

**High-frequency modules first**:
- [ ] Deprecate `naaru.rs` — main agent execution
- [ ] Deprecate `agent.rs` — legacy agent (including `EventType` enum at lines 23-136)
- [ ] Deprecate `memory.rs` — memory operations
- [ ] Deprecate `project.rs` — project analysis
- [ ] Deprecate `lens.rs` — lens operations

**Remaining modules**:
- [ ] `briefing.rs`, `commands.rs`, `coordinator.rs`, `dag.rs`
- [ ] `demo.rs`, `eval.rs`, `heuristic_detect.rs`, `indexing.rs`
- [ ] `interface.rs`, `preview.rs`, `run_analysis.rs`, `security.rs`
- [ ] `self_knowledge.rs`, `surface.rs`, `weakness.rs`, `weakness_types.rs`
- [ ] `workflow.rs`, `workspace.rs`, `writer.rs`

**Per-module process**:
1. Mark Tauri command as `#[deprecated]`
2. Update Svelte to always use HTTP
3. Remove after 1 release cycle

**Documentation**:
- [ ] Update README with `sunwell serve` instructions
- [ ] Update Studio development docs
- [ ] Add HTTP API reference

### Phase 4: Cleanup

- [ ] Delete all Rust modules in `src-tauri/src/` (keep `main.rs` minimal if Tauri packaging)
- [ ] Remove unused Rust dependencies from `Cargo.toml`
- [ ] Update `tauri.conf.json` — remove command registrations
- [ ] Update CI/CD — remove Rust build steps (if browser-only)
- [ ] Update GitHub Actions workflows
- [ ] Archive `studio/src-tauri/` directory for reference
- [ ] Final documentation review

---

## References

### Internal

- RFC-053: Studio Agent Bridge (current architecture)
- RFC-110: Unified Execution Engine (agent refactoring)
- `studio/src-tauri/src/*.rs` — Current Rust bridge (12,932 lines)
- `studio/src-tauri/src/agent.rs:23-136` — Duplicate EventType enum to remove
- `src/sunwell/agent/events.py:124-324` — Python event definitions (95 types, source of truth)
- `src/sunwell/external/server.py` — Existing FastAPI WebhookServer (pattern reference)
- `src/sunwell/cli/external_cmd.py:31-122` — Existing `sunwell external start` server pattern

### External

- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [FastAPI Static Files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [Tauri vs Electron](https://tauri.app/v1/references/benchmarks/)
