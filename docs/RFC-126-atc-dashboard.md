# RFC-126: ATC Dashboard — Air Traffic Control for Agent Swarms

**Status**: Draft  
**Author**: Human + AI collaboration  
**Created**: 2026-01-24  
**Extends**: Studio (`studio/`), Agent Events (`agent/events.py`), Guardrails (`guardrails/`)  
**Depends on**: RFC-119 (Event Bus), RFC-071 (Briefing), RFC-048 (Guardrails)

## Summary

Add a project-scoped **ATC (Air Traffic Control) tab** to Studio that surfaces agent status, blocked signals, and clearance requests in a unified view. The human becomes the ATC: routing, deconflicting, clearing obstacles, and arming agents with context — not micromanaging every action.

**The shift**: From "show me every step" to "tell me when you need me."

## Motivation

### Problem

Current Studio UX is built around **watching agents work**:

```
┌─────────────────────────────────────────────────────────────┐
│  Observatory: Watch AI cognition in real-time               │
│  Progress: [████████░░] 6/10 tasks                          │
│  Live Feed: [streaming every event...]                      │
└─────────────────────────────────────────────────────────────┘
```

This is exhausting for multi-agent/multi-task workflows. You're watching a security camera feed when you should be looking at a flight board.

### The ATC Mental Model

> "I'm the ATC of a swarm of intelligences. I need to trust them. But as their boss I also need to arm them with info, tools, processes, and support to do their job and stay unblocked."

| ATC Responsibility | Current Sunwell | With ATC Dashboard |
|--------------------|-----------------|-------------------|
| **Routing** | Manual goal assignment | Flight board shows queue, priorities |
| **Deconflicting** | Hidden in DAG | Visual dependency/conflict view |
| **Clearing obstacles** | Escalations buried in logs | Clearance panel surfaces decisions |
| **Providing context** | Scattered across briefing/request | Context injection panel |
| **Monitoring** | Watch every event | Status board + exception alerts |

### What Already Exists (Backend)

The infrastructure is complete — it's just not surfaced:

| Capability | Implementation | Location |
|------------|----------------|----------|
| Task status | `TaskStatus` enum | `naaru/types.py:58-67` |
| Run tracking | `RunState` | `server/runs.py` |
| Escalation protocol | `EscalationHandler` | `guardrails/escalation.py` |
| Confidence thresholds | `CONFIDENCE_THRESHOLDS` | `reasoning/decisions.py:240-247` |
| Context injection | `Briefing`, `PrefetchPlan` | `memory/briefing.py`, `prefetch/dispatcher.py` |
| Blocked signals | `BriefingStatus.BLOCKED`, `blockers` | `memory/briefing.py:32-74` |
| Event system | 40+ event types with UI hints | `agent/events.py` |

**This RFC surfaces what's already there.**

## Goals

1. **Flight Board**: Unified view of all active tasks with status, ETA, confidence
2. **Clearance Panel**: Surface escalations as "decisions needed" with clear options
3. **Context Panel**: Inject context into agents without writing code
4. **Blocked Alerts**: Prominent notification when agents are stuck
5. **Project-scoped**: ATC tab is per-project, not global

## Non-Goals

- New backend event types (use existing)
- Real-time collaboration (future RFC)
- Cross-project ATC view (future RFC)
- Automated conflict resolution (human decides)

---

## Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STUDIO - ATC TAB                                 │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      FLIGHT BOARD                                │    │
│  │                                                                  │    │
│  │  🟢 auth-module      CRUISING    87% conf   ETA 3m              │    │
│  │  🟡 db-schema        HOLDING     needs: enum decision           │    │
│  │  🟢 api-routes       APPROACH    92% conf   ready for review    │    │
│  │  🔴 tests            GO-AROUND   lint fail  3 errors            │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │    CLEARANCE PANEL       │  │        CONTEXT PANEL             │    │
│  │                          │  │                                  │    │
│  │  ⚠️ 1 decision needed    │  │  📋 Briefing                     │    │
│  │                          │  │  Mission: Build forum app        │    │
│  │  db-schema is HOLDING    │  │  Status: in_progress             │    │
│  │                          │  │  Progress: 4/7 artifacts         │    │
│  │  Need: UserRole enum     │  │                                  │    │
│  │  [A] admin/user/guest    │  │  🔥 Hot Files                    │    │
│  │  [B] owner/member/viewer │  │  • src/models/user.py            │    │
│  │                          │  │  • src/routes/auth.py            │    │
│  │  [Approve A] [Approve B] │  │                                  │    │
│  │  [Skip] [Let me edit]    │  │  ➕ Add Context                  │    │
│  │                          │  │  [________________________]      │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Flight Board Component

The Flight Board shows all active "flights" (tasks/goals) for the current project.

#### Data Model

```typescript
// studio/src/lib/types/atc.ts

interface Flight {
  id: string;
  description: string;
  status: FlightStatus;
  confidence: number;        // 0.0 - 1.0
  eta_seconds: number | null;
  started_at: string;
  blocked_reason: string | null;
  error_message: string | null;
  depends_on: string[];
  progress: number;          // 0 - 100
}

type FlightStatus = 
  | 'queued'      // PENDING/READY - waiting for runway
  | 'taxiing'     // Starting up
  | 'cruising'    // IN_PROGRESS - normal operation
  | 'holding'     // BLOCKED - waiting for clearance
  | 'approach'    // Nearly complete, ready for review
  | 'landed'      // COMPLETED
  | 'go-around'   // FAILED - needs retry
  | 'diverted';   // SKIPPED

interface FlightBoard {
  project_id: string;
  flights: Flight[];
  clearance_needed: number;  // Count of HOLDING flights
  updated_at: string;
}
```

#### Mapping from Existing Types

```typescript
// Map TaskStatus to FlightStatus
function toFlightStatus(task: TaskStatus, confidence: number): FlightStatus {
  switch (task) {
    case 'pending': return 'queued';
    case 'ready': return 'queued';
    case 'in_progress': 
      return confidence > 0.85 ? 'cruising' : 'cruising'; // Could add 'turbulence' for low conf
    case 'blocked': return 'holding';
    case 'completed': return 'landed';
    case 'failed': return 'go-around';
    case 'skipped': return 'diverted';
  }
}
```

#### Visual Design

```
┌────┬────────────────────┬───────────┬───────┬────────┬─────────┐
│    │ Flight             │ Status    │ Conf  │ ETA    │ Actions │
├────┼────────────────────┼───────────┼───────┼────────┼─────────┤
│ 🟢 │ auth-module        │ cruising  │ 87%   │ 3m     │   ⋮     │
│ 🟡 │ db-schema          │ holding   │ --    │ --     │ [Clear] │
│ 🟢 │ api-routes         │ approach  │ 92%   │ 1m     │   ⋮     │
│ 🔴 │ tests              │ go-around │ --    │ --     │ [Retry] │
│ ⚪ │ deployment         │ queued    │ --    │ ~10m   │   ⋮     │
└────┴────────────────────┴───────────┴───────┴────────┴─────────┘

Status indicators:
🟢 = healthy (cruising, approach, landed)
🟡 = needs attention (holding, taxiing)
🔴 = problem (go-around)
⚪ = waiting (queued, diverted)
```

### Clearance Panel Component

Surfaces `EventType.ESCALATE` events as actionable decisions.

#### Data Model

```typescript
// studio/src/lib/types/atc.ts

interface ClearanceRequest {
  id: string;
  flight_id: string;
  flight_description: string;
  reason: EscalationReason;
  details: string;
  options: ClearanceOption[];
  recommended: string;        // Option ID
  confidence: number | null;
  created_at: string;
}

interface ClearanceOption {
  id: string;
  label: string;
  description: string;
  action: 'approve' | 'approve_once' | 'skip' | 'abort' | 'split' | 'modify' | 'relax';
  risk_acknowledgment: string | null;
}

type EscalationReason = 
  | 'forbidden_action'
  | 'dangerous_action' 
  | 'scope_exceeded'
  | 'low_confidence'
  | 'missing_tests'
  | 'ambiguous_goal'
  | 'needs_decision';    // NEW: Agent found options, needs human to pick
```

#### Integration with Existing EscalationHandler

```python
# sunwell/guardrails/escalation.py - No changes needed!
# The existing EscalationHandler already produces this data.
# We just need to surface it in Studio.

# Existing options from _get_options_for_reason():
# - approve, approve_once, skip, abort
# - split (for scope_exceeded)
# - modify (for low_confidence)
# - relax (for missing_tests, scope_exceeded)
```

#### Visual Design

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ CLEARANCE NEEDED                                    [1]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  db-schema is HOLDING                                       │
│                                                             │
│  Reason: needs_decision                                     │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  I need to define the UserRole enum. I found two patterns   │
│  in similar projects:                                       │
│                                                             │
│  Option A: Access-based                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ class UserRole(Enum):                               │   │
│  │     ADMIN = "admin"      # Full access              │   │
│  │     USER = "user"        # Standard access          │   │
│  │     GUEST = "guest"      # Read-only                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Option B: Ownership-based                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ class UserRole(Enum):                               │   │
│  │     OWNER = "owner"      # Created the resource     │   │
│  │     MEMBER = "member"    # Can contribute           │   │
│  │     VIEWER = "viewer"    # Can only view            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Which matches your domain?                                 │
│                                                             │
│  [Approve A] [Approve B] [Skip] [Let me type something]    │
│                                              ↑ recommended  │
└─────────────────────────────────────────────────────────────┘
```

### Context Panel Component

Shows current briefing and allows quick context injection.

#### Data Model

```typescript
// studio/src/lib/types/atc.ts

interface ProjectContext {
  briefing: Briefing | null;
  hot_files: string[];
  recent_learnings: Learning[];
  injected_context: ContextEntry[];
}

interface ContextEntry {
  id: string;
  content: string;
  source: 'user' | 'briefing' | 'learning';
  created_at: string;
}

interface Briefing {
  mission: string;
  status: 'not_started' | 'in_progress' | 'blocked' | 'complete';
  progress: string;
  last_action: string;
  next_action: string | null;
  hazards: string[];
  blockers: string[];
  hot_files: string[];
}
```

#### Integration with Existing Briefing

```python
# sunwell/memory/briefing.py - Already complete!
# Briefing.to_prompt() already formats for injection.
# We just need to display it and allow additions.
```

#### Visual Design

```
┌─────────────────────────────────────────────────────────────┐
│ 📋 PROJECT CONTEXT                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Mission: Build a forum app with users, posts, comments     │
│  Status: in_progress                                        │
│  Progress: 4/7 artifacts complete                           │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🔥 Hot Files                                               │
│  • src/models/user.py                          [Open]       │
│  • src/models/post.py                          [Open]       │
│  • src/routes/auth.py                          [Open]       │
│                                                             │
│  ⚠️ Hazards                                                 │
│  • Don't use raw SQL — use SQLAlchemy ORM                   │
│  • Auth tokens expire after 24h, not 1h                     │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  ➕ Add Context                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ We use snake_case for all database columns          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                         [Add] [Add as File] │
│                                                             │
│  Recent additions:                                          │
│  • "Use pytest, not unittest" (2 min ago)         [Remove]  │
│  • "FastAPI, not Flask" (5 min ago)               [Remove]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### CLI: `sunwell context`

Quick context injection from terminal.

```bash
# Add inline context
sunwell context add "We use snake_case for database columns"
sunwell context add "Auth uses JWT, not sessions"

# Add file as context
sunwell context add --file ARCHITECTURE.md
sunwell context add --file docs/API.md

# Show current context
sunwell context show

# Clear injected context
sunwell context clear

# Add hazard (things to avoid)
sunwell context hazard "Don't modify legacy/ directory"

# Add blocker (things blocking progress)
sunwell context blocker "Waiting for API key from DevOps"
```

#### Implementation

```python
# sunwell/cli/context_cmd.py (NEW)

import click
from pathlib import Path
from sunwell.memory.briefing import Briefing, BriefingStore

@click.group()
def context():
    """Manage project context for agents."""
    pass

@context.command()
@click.argument('content')
@click.option('--file', '-f', type=Path, help='Add file contents as context')
def add(content: str, file: Path | None):
    """Add context that agents will see."""
    store = BriefingStore.load_or_create(Path.cwd())
    
    if file:
        content = file.read_text()
        store.add_context(content, source=f"file:{file}")
    else:
        store.add_context(content, source="user")
    
    store.save()
    click.echo(f"✓ Added context ({len(content)} chars)")

@context.command()
def show():
    """Show current project context."""
    store = BriefingStore.load_or_create(Path.cwd())
    briefing = store.briefing
    
    if briefing:
        click.echo(briefing.to_prompt())
    
    if store.injected_context:
        click.echo("\n## Injected Context\n")
        for entry in store.injected_context:
            click.echo(f"• {entry.content[:60]}...")

@context.command()
@click.argument('hazard')
def hazard(hazard: str):
    """Add a hazard (thing to avoid)."""
    store = BriefingStore.load_or_create(Path.cwd())
    store.add_hazard(hazard)
    store.save()
    click.echo(f"⚠️ Added hazard: {hazard}")

@context.command()
@click.argument('blocker')
def blocker(blocker: str):
    """Add a blocker (thing preventing progress)."""
    store = BriefingStore.load_or_create(Path.cwd())
    store.add_blocker(blocker)
    store.save()
    click.echo(f"🚫 Added blocker: {blocker}")
```

### Event Integration

#### New Event: `CLEARANCE_NEEDED`

```python
# sunwell/agent/events.py - Add to EventType enum

CLEARANCE_NEEDED = "clearance_needed"
"""Agent needs human decision to proceed."""

# Add UI hint
_DEFAULT_UI_HINTS["clearance_needed"] = EventUIHints(
    icon="⚠️",
    severity="warning",
    dismissible=False,
    animation="pulse",
)
```

#### Studio Event Handler

```typescript
// studio/src/stores/atc.svelte.ts (NEW)

import { writable, derived } from 'svelte/store';
import { onEvent } from './events';

interface ATCState {
  flights: Flight[];
  clearanceRequests: ClearanceRequest[];
  projectContext: ProjectContext | null;
}

const initialState: ATCState = {
  flights: [],
  clearanceRequests: [],
  projectContext: null,
};

export const atcState = writable<ATCState>(initialState);

// Derived stores for quick access
export const clearanceCount = derived(
  atcState,
  $state => $state.clearanceRequests.length
);

export const holdingFlights = derived(
  atcState,
  $state => $state.flights.filter(f => f.status === 'holding')
);

// Event handlers
export function initATCEventHandlers() {
  onEvent((event) => {
    switch (event.type) {
      case 'task_start':
        addOrUpdateFlight(event.data);
        break;
      case 'task_complete':
        updateFlightStatus(event.data.task_id, 'landed');
        break;
      case 'task_failed':
        updateFlightStatus(event.data.task_id, 'go-around');
        break;
      case 'escalate':
      case 'clearance_needed':
        addClearanceRequest(event.data);
        break;
      case 'briefing_loaded':
        updateProjectContext(event.data);
        break;
    }
  });
}

// API calls
export async function resolveClearance(
  requestId: string,
  optionId: string
): Promise<void> {
  await fetch('/api/clearance/resolve', {
    method: 'POST',
    body: JSON.stringify({ request_id: requestId, option_id: optionId }),
  });
  
  atcState.update(state => ({
    ...state,
    clearanceRequests: state.clearanceRequests.filter(r => r.id !== requestId),
  }));
}
```

### API Routes

```python
# sunwell/server/routes/atc.py (NEW)

from fastapi import APIRouter
from sunwell.guardrails.escalation import EscalationHandler

router = APIRouter(prefix="/atc", tags=["atc"])

@router.get("/flights")
async def get_flights(project_id: str) -> list[dict]:
    """Get all flights for a project."""
    # Aggregate from RunManager + TaskGraph
    ...

@router.get("/clearance")
async def get_clearance_requests(project_id: str) -> list[dict]:
    """Get pending clearance requests."""
    handler = EscalationHandler()
    return [handler.get_pending(id) for id in handler._pending]

@router.post("/clearance/resolve")
async def resolve_clearance(request_id: str, option_id: str) -> dict:
    """Resolve a clearance request with chosen option."""
    handler = EscalationHandler()
    escalation = handler.get_pending(request_id)
    
    resolution = handler._process_response(escalation, {
        "option_id": option_id,
        "acknowledged": True,
    })
    
    return {"status": "resolved", "action": resolution.action}

@router.get("/context")
async def get_project_context(project_id: str) -> dict:
    """Get current project context/briefing."""
    ...

@router.post("/context/add")
async def add_context(project_id: str, content: str, source: str = "user") -> dict:
    """Add context to project briefing."""
    ...
```

---

## Implementation Plan

### Phase 1: Flight Board (Week 1)

1. Create `studio/src/lib/types/atc.ts` with type definitions
2. Create `studio/src/stores/atc.svelte.ts` with state management
3. Create `studio/src/components/atc/FlightBoard.svelte`
4. Wire up existing `task_*` events to flight status
5. Add ATC tab to project view

### Phase 2: Clearance Panel (Week 1-2)

1. Create `studio/src/components/atc/ClearancePanel.svelte`
2. Add `CLEARANCE_NEEDED` event type
3. Create `/api/clearance/*` routes
4. Wire up `EventType.ESCALATE` → clearance panel
5. Add resolve/dismiss flow

### Phase 3: Context Panel (Week 2)

1. Create `studio/src/components/atc/ContextPanel.svelte`
2. Create `sunwell/cli/context_cmd.py`
3. Create `/api/context/*` routes
4. Wire up briefing display + injection

### Phase 4: Polish (Week 2-3)

1. Add keyboard shortcuts (C = clearance, F = flights, X = context)
2. Add notification badge when clearance needed
3. Add sound/haptic for clearance requests (optional)
4. Mobile-responsive layout
5. Tests

---

## Alternatives Considered

### 1. Extend Observatory Instead of New Tab

**Rejected**: Observatory is about watching cognition patterns. ATC is about operational control. Different purposes, different UX.

### 2. Global ATC View (Cross-Project)

**Deferred**: Single-project ATC is simpler and matches the "one project at a time" mental model. Cross-project can come later.

### 3. Auto-Resolution of Some Decisions

**Deferred**: Trust needs to be built. Start with human-in-loop for all decisions, then add "trust this agent to decide X" later.

---

## Success Metrics

1. **Reduced context switching**: User stays in ATC tab during multi-task work
2. **Faster clearance resolution**: Time from escalation → resolution decreases
3. **Context injection usage**: Users actively add context (not just relying on briefing)
4. **Blocked time reduction**: Time tasks spend in HOLDING state decreases

---

## Open Questions

1. **Notification preferences**: How aggressive should clearance alerts be? Toast? Sound? Badge only?
2. **Mobile UX**: Should mobile get a simplified "clearance only" view?
3. **History**: Should we show completed flights, or just active ones?
4. **Multi-user**: When we add collaboration, how do clearance assignments work?

---

## Related Documents

- RFC-048: Autonomy Guardrails
- RFC-071: Briefing System
- RFC-119: Event Bus
- RFC-123: Convergence Loops (convergence states map to flight status)
