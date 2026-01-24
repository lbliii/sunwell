# RFC-119: Unified Event Bus — CLI/Studio Visibility

**Status**: Evaluated  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Evaluated**: 2026-01-24 (88% confidence)  

## Summary

Make all agent runs visible across CLI and Studio by routing through a unified event bus. Goals triggered via CLI should appear in Studio's Observatory and other views.

## Motivation

### Problem

Currently, CLI and Studio operate in isolation:

```
CLI runs agent directly → Events go to terminal only
Studio runs via server → Events go to WebSocket only
```

This means:
- Goals started via `sunwell run "..."` don't appear in Observatory
- Project work done via CLI is invisible to Studio
- Users switching between CLI and Studio lose context

### Inspiration: Pachyderm Console

Pachyderm solved this by making both `pachctl` (CLI) and Console clients of the same backend (`pachd`):

```
pachctl create pipeline → pachd → Console sees it
Console clicks "Run" → pachd → CLI can list it
```

Key patterns from Pachyderm:
- **Single source of truth**: Backend server manages all state
- **SubscribeJob API**: Streaming subscription for real-time job updates
- **ListJob API**: Query all jobs regardless of origin

## Goals

1. **Unified visibility**: CLI-triggered goals appear in Studio Observatory
2. **No frontend dependency**: CLI works offline without server
3. **Seamless experience**: Studio shows all project activity
4. **Backward compatible**: Existing CLI behavior preserved

## Non-Goals

- Force CLI to require server (opportunistic only)
- Replace direct agent execution (fallback always available)
- Real-time CLI output in Studio terminal (future RFC)

## Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Sunwell Server                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Run Manager                           │   │
│  │  - Create runs (from CLI or Studio)                      │   │
│  │  - Store events (persistent within session)              │   │
│  │  - Broadcast to all connected WebSocket clients          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│           ┌───────────────┼───────────────┐                     │
│           ▼               ▼               ▼                     │
│     POST /api/run   WS /api/events   GET /api/runs              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
        ▲                       ▲
        │                       │
   ┌────┴────┐             ┌────┴────┐
   │   CLI   │             │  Studio │
   │ (client)│             │ (client)│
   └─────────┘             └─────────┘
```

### New Endpoints

#### 1. Global Event Stream

```
WS /api/events?project_id=X  (WebSocket)
```

Subscribe to **all** events for a project, regardless of which client triggered them.

**Query parameters**:
- `project_id` (optional): Filter events to specific project

```typescript
// Message format (v1)
{
  "v": 1,                      // Schema version for future compatibility
  "run_id": "abc123",
  "type": "task_start",
  "data": { "task_id": "t1", "description": "..." },
  "timestamp": "2026-01-24T10:30:00Z",
  "source": "cli" | "studio" | "api"  // Track origin
}
```

**Server implementation**:
```python
@app.websocket("/api/events")
async def global_events(websocket: WebSocket, project_id: str | None = None):
    """Subscribe to all events, optionally filtered by project."""
    await websocket.accept()
    
    if not await _event_bus.subscribe(websocket, project_filter=project_id):
        await websocket.close(code=4029, reason="Too many connections")
        return
    
    try:
        # Keep connection alive, events pushed via broadcast()
        while True:
            await websocket.receive_text()  # Ping/pong
    except WebSocketDisconnect:
        pass
    finally:
        await _event_bus.unsubscribe(websocket)
```

#### 2. List Runs

```
GET /api/runs?project_id=X&limit=20
```

Returns all runs for a project, regardless of origin:

```typescript
{
  "runs": [
    {
      "run_id": "abc123",
      "goal": "Add OAuth",
      "status": "running",
      "source": "cli",
      "started_at": "2026-01-24T10:30:00Z",
      "event_count": 42
    },
    ...
  ]
}
```

#### 3. Subscribe to Run (existing, unchanged)

```
WS /api/run/{run_id}/events
```

Existing per-run WebSocket stays the same.

### CLI Changes

#### Server Detection

```python
# sunwell/cli/server_bridge.py

# Default server URL (matches server/main.py)
DEFAULT_SERVER_URL = "http://127.0.0.1:8080"

async def detect_server(url: str = DEFAULT_SERVER_URL) -> str | None:
    """Check if Sunwell server is running.
    
    Returns server URL if available, None otherwise.
    Fast timeout (500ms) to avoid blocking CLI startup.
    """
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.get(f"{url}/api/health")
            if resp.status_code == 200:
                return url
    except (httpx.ConnectError, httpx.TimeoutException):
        pass  # Server not running — expected case
    return None
```

#### Route Through Server (when available)

```python
# Modified sunwell/cli/main.py

async def _run_agent(...):
    # Check if server is available
    server_url = await detect_server()
    
    if server_url:
        # Route through server for visibility
        return await _run_via_server(server_url, goal, **options)
    else:
        # Direct execution (existing behavior)
        return await _run_direct(goal, **options)


async def _run_via_server(server_url: str, goal: str, **options):
    """Execute goal through server for unified visibility."""
    async with httpx.AsyncClient() as client:
        # Start run
        resp = await client.post(f"{server_url}/api/run", json={
            "goal": goal,
            "workspace": str(Path.cwd()),
            "source": "cli",  # Tag the origin
            **options,
        })
        run_id = resp.json()["run_id"]
        
        # Stream events to terminal
        async with client.stream_ws(f"{server_url}/api/run/{run_id}/events") as ws:
            async for event in ws:
                _print_event(event)  # Existing terminal renderer
```

### Server Changes

#### RunState Model Updates

```python
# sunwell/server/runs.py (additions to existing model)

from datetime import datetime

@dataclass
class RunState:
    """State for a single agent run."""
    
    run_id: str
    goal: str
    workspace: str | None = None
    project_id: str | None = None
    # ... existing fields ...
    
    # NEW: Track run origin and timing
    source: str = "studio"  # "cli" | "studio" | "api"
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
```

#### Global Event Broadcasting

```python
# sunwell/server/events.py (new file)

class EventBus:
    """Global event bus for all connected clients."""
    
    def __init__(self):
        self._subscribers: set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def subscribe(self, ws: WebSocket):
        async with self._lock:
            self._subscribers.add(ws)
    
    async def unsubscribe(self, ws: WebSocket):
        async with self._lock:
            self._subscribers.discard(ws)
    
    async def broadcast(self, event: dict):
        """Send event to ALL subscribers."""
        async with self._lock:
            for ws in list(self._subscribers):
                try:
                    await ws.send_json(event)
                except:
                    self._subscribers.discard(ws)

# Global instance
_event_bus = EventBus()
```

#### Modified Run Execution

```python
@app.post("/api/run")
async def start_run(request: RunRequest) -> dict:
    run = _run_manager.create_run(
        goal=request.goal,
        workspace=request.workspace,
        source=request.source or "studio",  # Track origin
        ...
    )
    
    # Start execution in background, broadcast to all
    asyncio.create_task(_execute_and_broadcast(run))
    
    return {"run_id": run.run_id, "status": "started"}


async def _execute_and_broadcast(run: RunState):
    """Execute agent and broadcast events globally."""
    async for event in _execute_agent(run):
        event_dict = {
            **event.to_dict(),
            "run_id": run.run_id,
            "source": run.source,
        }
        run.events.append(event_dict)
        
        # Broadcast to ALL connected clients
        await _event_bus.broadcast(event_dict)
```

### Studio Changes

#### Subscribe to Global Events

```typescript
// stores/agent.svelte.ts

export async function subscribeToGlobalEvents(): () => void {
    const ws = new WebSocket(`${API_BASE}/api/events`);
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // Update agent state for current run
        if (data.run_id === _currentRunId || !_currentRunId) {
            handleAgentEvent(data);
        }
        
        // Always update run history
        updateRunHistory(data);
    };
    
    return () => ws.close();
}
```

#### Show Run Source in UI

```svelte
<!-- Observatory badge showing run origin -->
<span class="badge {run.source === 'cli' ? 'cli' : 'studio'}">
    {run.source === 'cli' ? '⌨️ CLI' : '🖥️ Studio'}
</span>
```

## Migration

### Phase 1: Server-Side Global Events (1-2 days)

| Task | File | Status |
|------|------|--------|
| Add `EventBus` class | `src/sunwell/server/events.py` (new) | ⬜ |
| Add `source`, `started_at` to `RunState` | `src/sunwell/server/runs.py` | ⬜ |
| Add `/api/events` WebSocket endpoint | `src/sunwell/server/main.py` | ⬜ |
| Add `/api/runs` list endpoint | `src/sunwell/server/main.py` | ⬜ |
| Wire broadcasting into run execution | `src/sunwell/server/main.py` | ⬜ |
| Add event retention/eviction | `src/sunwell/server/runs.py` | ⬜ |

**Verification**: `pytest tests/integration/test_unified_events.py -k "TestGlobalEventBroadcast"`

### Phase 2: CLI Server Bridge (1 day)

| Task | File | Status |
|------|------|--------|
| Add `detect_server()` function | `src/sunwell/cli/server_bridge.py` (new) | ⬜ |
| Add `_run_via_server()` function | `src/sunwell/cli/main.py` | ⬜ |
| Modify `_run_agent()` to check server | `src/sunwell/cli/main.py` | ⬜ |
| Add `--no-server` flag for forced local | `src/sunwell/cli/main.py` | ⬜ |

**Verification**: `pytest tests/integration/test_unified_events.py -k "TestServerDetection or TestFallback"`

### Phase 3: Studio Integration (1 day)

| Task | File | Status |
|------|------|--------|
| Add `subscribeToGlobalEvents()` | `studio/src/lib/socket.ts` | ⬜ |
| Update Observatory to use global stream | `studio/src/components/observatory/` | ⬜ |
| Add run source badges | `studio/src/components/observatory/RunCard.svelte` | ⬜ |
| Show run history from `/api/runs` | `studio/src/stores/agent.svelte.ts` | ⬜ |

**Verification**: Manual test — start Studio, run CLI command, verify appears in Observatory

## Testing

```python
# tests/integration/test_unified_events.py

import pytest
from sunwell.cli.server_bridge import detect_server

class TestServerDetection:
    """Server detection tests."""
    
    async def test_detect_server_when_running(self, test_server):
        """Should return URL when server is running."""
        url = await detect_server()
        assert url == "http://127.0.0.1:8080"
    
    async def test_detect_server_when_not_running(self):
        """Should return None when server not running."""
        url = await detect_server("http://127.0.0.1:9999")
        assert url is None
    
    async def test_detect_server_fast_timeout(self):
        """Should timeout quickly (<1s) when server unreachable."""
        import time
        start = time.monotonic()
        await detect_server("http://192.0.2.1:8080")  # Non-routable
        elapsed = time.monotonic() - start
        assert elapsed < 1.0


class TestGlobalEventBroadcast:
    """Global event streaming tests."""
    
    async def test_cli_run_visible_in_studio(self, test_server):
        """CLI-triggered run should appear in Studio."""
        events = []
        
        # Studio subscribes to global events
        async with websocket_connect(f"{test_server}/api/events") as ws:
            asyncio.create_task(collect_events(ws, events))
            
            # CLI starts run through server
            result = await run_cli_command("sunwell run 'Add tests'")
            await asyncio.sleep(0.5)  # Allow events to propagate
        
        # Verify Studio received events with correct source
        assert any(e["type"] == "task_start" for e in events)
        assert any(e["source"] == "cli" for e in events)
        assert all(e.get("v") == 1 for e in events)  # Schema version
    
    async def test_project_filtering(self, test_server):
        """Events should filter by project_id."""
        project_a_events = []
        project_b_events = []
        
        async with websocket_connect(f"{test_server}/api/events?project_id=proj-a") as ws_a:
            async with websocket_connect(f"{test_server}/api/events?project_id=proj-b") as ws_b:
                asyncio.create_task(collect_events(ws_a, project_a_events))
                asyncio.create_task(collect_events(ws_b, project_b_events))
                
                # Run in project A
                await api_post(f"{test_server}/api/run", {
                    "goal": "Test", "project_id": "proj-a", "source": "api"
                })
                await asyncio.sleep(0.5)
        
        assert len(project_a_events) > 0
        assert len(project_b_events) == 0


class TestFallbackBehavior:
    """CLI fallback tests."""
    
    async def test_cli_works_without_server(self):
        """CLI should work when server not running."""
        # Ensure no server
        assert await detect_server() is None
        
        # Direct execution should work
        result = await run_cli_command("sunwell run 'Add tests'")
        assert result.exit_code == 0
    
    async def test_cli_fallback_on_server_error(self, test_server):
        """CLI should fallback if server returns error."""
        # TODO: Inject server error, verify fallback


class TestLoadHandling:
    """Load and concurrency tests."""
    
    async def test_max_concurrent_runs(self, test_server):
        """Should reject runs when at capacity."""
        # Start MAX_ACTIVE_RUNS runs
        run_ids = []
        for i in range(10):
            resp = await api_post(f"{test_server}/api/run", {"goal": f"Run {i}"})
            run_ids.append(resp["run_id"])
        
        # Next run should be rejected
        with pytest.raises(HTTPError) as exc:
            await api_post(f"{test_server}/api/run", {"goal": "Overflow"})
        assert exc.value.status_code == 429
    
    async def test_connection_limit(self, test_server):
        """Should reject WebSocket connections at limit."""
        connections = []
        for i in range(100):
            ws = await websocket_connect(f"{test_server}/api/events")
            connections.append(ws)
        
        # 101st connection should fail
        with pytest.raises(WebSocketError):
            await websocket_connect(f"{test_server}/api/events")
        
        # Cleanup
        for ws in connections:
            await ws.close()
```

## Security Considerations

### Authentication Model

Local-first trust model (same as current HTTP API):

```
┌─────────────────────────────────────────────────────────────┐
│  localhost:8080 — Trusted Zone                              │
│                                                             │
│  CLI ──────┐                                                │
│            ├──► Server ◄──── Studio                         │
│  Scripts ──┘      │                                         │
│                   │                                         │
│         No auth required for localhost                      │
└─────────────────────────────────────────────────────────────┘
```

**Current behavior (preserved)**:
- Server binds to `127.0.0.1:8080` only (not `0.0.0.0`)
- No authentication for local connections
- External access requires explicit `--host` flag (future)

**CLI→Server flow**:
```python
# No auth token needed for localhost
async def _run_via_server(server_url: str, goal: str, **options):
    # Server validates request is from localhost via socket peer address
    resp = await client.post(f"{server_url}/api/run", json={...})
```

**WebSocket connections**:
- Global `/api/events` accepts any localhost connection
- Per-run `/api/run/{run_id}/events` unchanged
- Future: Add bearer token for remote access (separate RFC)

### Threat Model

| Threat | Mitigation | Status |
|--------|------------|--------|
| Remote event injection | Localhost binding only | ✅ Current |
| Event eavesdropping | Localhost only, no sensitive data in events | ✅ Current |
| Run hijacking | Run IDs are UUIDs, localhost only | ✅ Current |
| DoS via many connections | Max 100 WebSocket connections | 🆕 New |

### Connection Limits

```python
class EventBus:
    MAX_SUBSCRIBERS = 100  # Prevent resource exhaustion
    
    async def subscribe(self, ws: WebSocket) -> bool:
        async with self._lock:
            if len(self._subscribers) >= self.MAX_SUBSCRIBERS:
                return False  # Reject connection
            self._subscribers.add(ws)
            return True
```

## Alternatives Considered

### 1. Shared Event Log File

CLI writes events to file, Studio polls file.

**Rejected**: Complex file locking, polling latency, cross-platform issues.

### 2. Force CLI Through Server Always

Make server required for CLI.

**Rejected**: Breaks offline usage, heavy dependency.

### 3. Push from CLI to Studio

CLI directly pushes to running Studio process.

**Rejected**: Complex IPC, race conditions, no persistence.

## Event Retention Strategy

Events are stored in-memory with automatic eviction:

```python
# sunwell/server/runs.py

class RunManager:
    """Thread-safe manager for active runs."""
    
    MAX_RUNS = 100           # Max runs to retain
    MAX_AGE_SECONDS = 3600   # 1 hour TTL
    
    def _cleanup_expired(self) -> None:
        """Evict runs older than MAX_AGE or when at capacity."""
        now = datetime.utcnow()
        expired = [
            run_id for run_id, run in self._runs.items()
            if (now - run.started_at).total_seconds() > self.MAX_AGE_SECONDS
            or run.status in ("complete", "error", "cancelled")
        ]
        
        # Sort by age, keep newest
        if len(self._runs) >= self.MAX_RUNS:
            by_age = sorted(self._runs.items(), key=lambda x: x[1].started_at)
            expired.extend(r[0] for r in by_age[:len(by_age)//2])
        
        for run_id in set(expired):
            del self._runs[run_id]
```

**Eviction triggers**:
1. Run completes/fails → eligible for eviction
2. Age > 1 hour → evicted on next cleanup
3. Count > 100 → oldest 50% evicted

**Reconnection support**: Clients can fetch missed events via `/api/runs/{run_id}` which returns buffered events.

## Load Considerations

### Concurrent Runs

```python
# Max concurrent active (running) runs
MAX_ACTIVE_RUNS = 10

@app.post("/api/run")
async def start_run(request: RunRequest) -> dict:
    active_count = sum(1 for r in _run_manager.list_runs() if r.status == "running")
    if active_count >= MAX_ACTIVE_RUNS:
        raise HTTPException(429, "Too many concurrent runs")
    ...
```

### Event Throughput

Expected load:
- **Events/run**: ~50-500 (planning, tasks, gates, completion)
- **Concurrent subscribers**: 1-5 (CLI + Studio + scripts)
- **Peak throughput**: ~100 events/second

Mitigation for high throughput:
```python
async def broadcast(self, event: dict):
    """Broadcast with backpressure."""
    async with self._lock:
        tasks = [
            asyncio.wait_for(ws.send_json(event), timeout=1.0)
            for ws in self._subscribers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Drop slow consumers
        for ws, result in zip(list(self._subscribers), results):
            if isinstance(result, asyncio.TimeoutError):
                self._subscribers.discard(ws)
```

## Open Questions

~~1. **Event retention**: How long to keep events in memory?~~ → Resolved: 1 hour TTL + 100 run cap
~~2. **Project scoping**: Filter events by project?~~ → Resolved: `/api/events?project_id=X`
~~3. **Authentication**: Use existing auth or anonymous local access?~~ → Resolved: localhost trust model

**Remaining**:
1. **Event schema versioning**: Add `"version": 1` field to events for future compatibility?
2. **Compression**: Enable WebSocket compression for high-throughput scenarios?

## Success Metrics

- CLI runs visible in Studio within 500ms
- No regression in CLI standalone performance
- Zero new dependencies for CLI

## References

- Pachyderm Console: gRPC `SubscribeJob` streaming API
- RFC-113: HTTP API Layer
- RFC-117: Project Workspace Isolation
