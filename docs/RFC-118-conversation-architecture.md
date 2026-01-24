# RFC-118: Conversation Architecture Overhaul

**Status**: Ready for Review  
**Author**: System  
**Created**: 2026-01-23  
**Updated**: 2026-01-23  
**Supersedes**: RFC-080 (partial)  
**Related**: RFC-113 (HTTP Bridge), RFC-114 (Backlog UI), RFC-117 (Project-Centric Workspace)

---

## Summary

The current conversation UI in Sunwell Studio is broken and conceptually confused. This RFC:

1. **Removes fake conversation mode from Home** — keyword matching pretending to be AI
2. **Clarifies where real conversation lives** — agent execution within workspaces
3. **Introduces Activity Panel** — project-scoped history of completed work
4. **Kills the ChatHistory sidebar** — useless overlay disconnected from reality

---

## Problem Statement

### Current State is Broken

The `/api/home/process-goal` endpoint accepts a `history` parameter but **completely ignores it**:

```python
@app.post("/api/home/process-goal")
async def home_process_goal(request: HomeProcessGoalRequest) -> dict[str, Any]:
    goal_lower = request.goal.lower()
    
    # Just keyword matching - no AI, no history awareness
    if any(k in goal_lower for k in ["build", "create", ...]):
        return {"type": "workspace", ...}
    
    # Fallback echoes input verbatim
    return {
        "type": "conversation",
        "response": f"I understand you want to: {request.goal}\n\n"
                    "How would you like me to help?",
    }
```

**Result**: When user says "research it" as a follow-up, the system responds:
> "I understand you want to: research it. How would you like me to help? I can build it, research it, or break it down."

This is nonsensical — the pronoun "it" isn't resolved, and offering "research it" as an option when they just said "research it" is absurd.

### ChatHistory Sidebar is Disconnected

The `ChatHistory.svelte` component shows `homeState.conversationHistory` — ephemeral in-memory messages with no:
- Project association
- Persistence
- Connection to `SimulacrumStore` (which already supports project-scoped sessions)
- Meaningful actions

### Conceptual Confusion

The Home screen tries to be conversational, but conversation is the wrong paradigm for:
- Goal entry (direct input is faster)
- Project selection (visual UI is better)
- Navigation (direct manipulation wins)

---

## Design Principles

### 1. Direct Action Over Conversation

**Before** (current broken state):
```
User:  "build an rts game"
AI:    "I understand you want to: build an rts game. How would you like me to help?"
User:  "build it"
AI:    "I understand you want to: build it. How would you like me to help?"
```

**After** (this RFC):
```
User:  "build an rts game"
→ Immediately opens workspace, starts agent execution
```

Conversation happens **during** execution, not **before** it.

### 2. Chat is for Active Collaboration

Real conversation is valuable when:
- Agent is executing and user wants to guide it
- User asks "why that approach?" mid-execution
- User says "skip that step" or "actually use X instead"
- Post-run debrief: "explain what you did"

### 3. History is Activity, Not Chat Logs

Users don't care about raw message transcripts. They care about:
- What goals were completed
- What files were changed
- What decisions were made
- How long things took

---

## Architecture

### Remove from Home

1. **Kill ConversationLayout for Home routing**
   - Home input → Intent detection → Immediate action
   - No "conversation mode" fallback

2. **Kill ChatHistory sidebar**
   - Delete `ChatHistory.svelte`
   - Remove chat history button from Home

3. **Simplify `/api/home/process-goal`**
   - Remove `history` parameter (unused anyway)
   - Return action, not conversation
   - Ambiguous input → Option cards, not chat

### Intent Detection → Action (New Flow)

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Intent Classifier                           │
│  (Fast heuristics + optional small LLM for ambiguous)       │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ EXECUTE  │       │   VIEW   │       │ CLARIFY  │
    │          │       │          │       │          │
    │ Open     │       │ Show     │       │ Option   │
    │ workspace│       │ project  │       │ cards    │
    │ Start    │       │ list,    │       │ (not     │
    │ agent    │       │ search,  │       │ chat)    │
    │          │       │ etc      │       │          │
    └──────────┘       └──────────┘       └──────────┘
```

### Workspace Conversation (Keep & Improve)

Real conversation lives inside the workspace during agent execution:

```
┌─────────────────────────────────────────────────────────────┐
│  Workspace: my-rts-game                                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │                      │  │ Agent Execution               │ │
│  │   Code Editor        │  │                               │ │
│  │                      │  │ ✅ Created package.json       │ │
│  │                      │  │ ✅ Set up Vite + TypeScript   │ │
│  │                      │  │ 🔄 Implementing game loop...  │ │
│  │                      │  │                               │ │
│  │                      │  │ ─────────────────────────────│ │
│  │                      │  │ 💬 You: "use Pixi.js not raw │ │
│  │                      │  │         canvas"              │ │
│  │                      │  │ ✨ Agent: "Switching to      │ │
│  │                      │  │           Pixi.js renderer"  │ │
│  │                      │  │                               │ │
│  │                      │  │ [input: type here to chat]   │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

This already exists via the WebSocket event stream (`/api/run/{run_id}/events`).

### Activity Panel (New)

Replace ChatHistory with a **project-scoped Activity Panel**:

```
┌─────────────────────────────────────────────────────────────┐
│ 📜 Activity — sunwell/studio                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Today                                                       │
│  ─────                                                       │
│  ✅ "implement backlog drag-drop"              45s • 3 files │
│     └─ BacklogPanel.svelte, GoalCard.svelte, backlog.svelte │
│                                                              │
│  ✅ "fix typescript errors"                    12s • 2 files │
│     └─ types.ts, utils.ts                                   │
│                                                              │
│  ❌ "add websocket support"                   failed • 1 min │
│     └─ Network error: connection refused                    │
│                                                              │
│  Yesterday                                                   │
│  ─────────                                                   │
│  ✅ "create EpicProgress component"           2min • 1 file  │
│     └─ EpicProgress.svelte                                  │
│                                                              │
│  [Show earlier...]                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Actions**:
- Click run → Expand to show full event log
- Click run → "Continue this work" (resume context)
- Filter by status (completed/failed/in-progress)

### Run Persistence (New)

The current `RunManager` is in-memory only — runs are lost on server restart. Activity Panel requires persistent history.

**Extended RunState** (`runs.py`):

```python
@dataclass
class RunState:
    run_id: str
    goal: str
    workspace: str | None = None
    lens: str | None = None
    provider: str | None = None
    model: str | None = None
    trust: str = "workspace"
    timeout: int = 300

    status: str = "pending"  # pending | running | complete | cancelled | error
    events: list[dict[str, Any]] = field(default_factory=list)
    _cancel_flag: bool = field(default=False, repr=False)

    # NEW: Activity Panel support
    started_at: datetime | None = None
    completed_at: datetime | None = None
    files_changed: list[str] = field(default_factory=list)
    error_message: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
```

**Persistence Strategy**:

```
~/.sunwell/runs/
├── index.json              # Fast lookup: {run_id: workspace, status, goal_preview}
└── by-workspace/
    └── {workspace_hash}/
        ├── runs.jsonl      # Append-only run records
        └── events/
            └── {run_id}.jsonl  # Full event log (lazy-loaded)
```

**RunManager changes**:
- `save_run(run: RunState)` — Persist on status change (running/complete/error)
- `load_runs(workspace: str, limit: int)` — Load from disk for Activity Panel
- Keep recent runs in memory for active execution, flush to disk on completion

**Why not use SimulacrumStore?**

SimulacrumStore is for conversation memory (turns, context, topology). Run history is execution metadata. Separate concerns:
- SimulacrumStore → "What did we discuss?"
- RunManager → "What work was done?"

---

## Implementation Plan

### Phase 1: Remove Broken Conversation + Clean Intent Routing (Day 1)

These are tightly coupled — do together to avoid broken intermediate states.

**Backend** (`main.py`):
1. Remove `history` parameter from `HomeProcessGoalRequest`
2. Remove `"conversation"` response type
3. Add `"clarify"` response type with options
4. Simplify intent routing to: `execute | view | clarify`

```python
class IntentResult:
    action: Literal["execute", "view", "clarify"]
    workspace: str | None  # For execute
    view_type: str | None  # For view
    options: list[dict] | None  # For clarify
```

**Frontend** (`studio/src/`):
1. Delete `ChatHistory.svelte`
2. Remove chat history button from `Home.svelte`
3. Remove `conversationHistory` from `home.svelte.ts`
4. Add `OptionCards.svelte` for clarify responses with `1/2/3` shortcuts

```svelte
<!-- OptionCards.svelte -->
<svelte:window onkeydown={handleKeydown} />

{#if response.type === 'clarify'}
  <div class="option-cards">
    {#each response.options as opt, i}
      <button onclick={() => selectOption(opt.action)}>
        <span class="shortcut">{i + 1}</span>
        <h3>{opt.label}</h3>
        <p>{opt.description}</p>
      </button>
    {/each}
  </div>
{/if}
```

### Phase 2: Run Persistence + Extended RunState (Day 2)

**Backend** (`runs.py`):
1. Add new fields to `RunState`:
   - `started_at: datetime | None`
   - `completed_at: datetime | None`
   - `files_changed: list[str]`
   - `error_message: str | None`
   - `pending_messages: list[UserMessage]`

2. Add persistence methods to `RunManager`:
   - `save_run(run: RunState)` — called on status transitions
   - `load_runs(workspace: str, limit: int)` — for Activity Panel
   - Storage: `~/.sunwell/runs/by-workspace/{hash}/runs.jsonl`

3. Track files changed during execution:
   - Instrument `write_file` tool to append to `run.files_changed`
   - Or: Diff workspace before/after (simpler but less accurate)

### Phase 3: Activity Panel + History Endpoint (Day 2-3)

**Backend** (`main.py`):
1. Extend `/api/run/history` endpoint:
   ```python
   @app.get("/api/run/history")
   async def get_run_history(
       workspace: str | None = None,
       status: str | None = None,
       limit: int = 50,
   ) -> list[RunSummary]:
       runs = _run_manager.load_runs(workspace, limit)
       if status:
           runs = [r for r in runs if r.status == status]
       return [run.to_summary() for run in runs]
   ```

**Frontend** (`studio/src/components/`):
1. New `ActivityPanel.svelte`:
   - Props: `projectPath: string`
   - Fetches from `/api/run/history?workspace={projectPath}`
   - Groups by day (Today, Yesterday, Earlier)
   - Shows: goal, status icon, duration, file count
   - Expand: full file list, error message
   - Actions: "Continue this work" → navigate with resume context

2. Add "Activity" tab next to Backlog in workspace

### Phase 4: Mid-Execution Messaging (Day 3-4)

**Backend** (`main.py`):
1. Add `/api/run/{run_id}/message` endpoint (see API section)
2. Add `UserMessage` dataclass and `pending_messages` queue
3. Emit `user_message` event to WebSocket stream

**Agent integration** (`agent/core.py`):
1. Check `run.pending_messages` between tool calls
2. If guidance message: incorporate into next reasoning step
3. If stop message: graceful shutdown with summary
4. Clear processed messages from queue

**Frontend** (`studio/src/components/`):
1. New `AgentInput.svelte` — input field in execution panel
2. POST to `/api/run/{run_id}/message` on submit
3. Display user messages inline with agent events
4. Visual distinction: user = right-aligned, agent = left-aligned

---

## Data Model

### RunState (Extended)

```python
# runs.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class UserMessage:
    """User message injected during execution."""
    content: str
    type: str = "guidance"  # guidance | stop | clarify
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RunState:
    """State for a single agent run."""
    run_id: str
    goal: str
    workspace: str | None = None
    lens: str | None = None
    provider: str | None = None
    model: str | None = None
    trust: str = "workspace"
    timeout: int = 300

    status: str = "pending"  # pending | running | complete | cancelled | error
    events: list[dict[str, Any]] = field(default_factory=list)
    _cancel_flag: bool = field(default=False, repr=False)

    # Activity Panel support
    started_at: datetime | None = None
    completed_at: datetime | None = None
    files_changed: list[str] = field(default_factory=list)
    error_message: str | None = None

    # Mid-execution messaging
    pending_messages: list[UserMessage] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_summary(self) -> dict[str, Any]:
        """Convert to API response format."""
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "workspace": self.workspace,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "files_changed": self.files_changed,
            "error_message": self.error_message,
            "event_count": len(self.events),
        }
```

### ClarifyResponse (New)

```typescript
// studio/src/stores/home.svelte.ts
interface ClarifyOption {
    label: string;
    description: string;
    action: string;  // e.g., "execute:code", "view:plan", "execute:research"
    shortcut?: number;  // 1, 2, 3 for keyboard nav
}

interface ClarifyResponse {
    type: "clarify";
    prompt: string;
    options: ClarifyOption[];
}
```

### RunSummary (Activity Panel)

```typescript
// studio/src/lib/types.ts
interface RunSummary {
    run_id: string;
    goal: string;
    workspace: string;
    status: "complete" | "error" | "cancelled" | "running" | "pending";
    started_at: string;  // ISO timestamp
    completed_at: string | null;
    duration_seconds: number | null;
    files_changed: string[];
    error_message: string | null;
    event_count: number;
}
```

---

## API Changes

### Removed

```diff
- POST /api/home/process-goal
-   history: list[dict]  # Never used
```

### Modified

```python
# /api/home/process-goal now returns:
{
    "type": "execute" | "view" | "clarify",
    
    # For execute:
    "workspace_spec": {...},
    "goal": str,
    
    # For view:
    "view_type": str,
    "data": {...},
    
    # For clarify:
    "prompt": str,
    "options": [{"label": str, "description": str, "action": str}]
}
```

### Added

```python
# New endpoint for workspace-filtered history with full metadata
GET /api/run/history?workspace={path}&limit={n}&status={filter}

# Response:
[
    {
        "run_id": str,
        "goal": str,
        "workspace": str,
        "status": "complete" | "error" | "cancelled" | "running",
        "started_at": str,  # ISO timestamp
        "completed_at": str | None,
        "duration_seconds": float | None,
        "files_changed": list[str],
        "error_message": str | None,
        "event_count": int
    }
]
```

```python
# Mid-execution message injection
POST /api/run/{run_id}/message
{
    "content": str,
    "type": "guidance" | "stop" | "clarify"  # Default: "guidance"
}

# Response:
{
    "accepted": bool,
    "run_status": str,  # Current run status
    "message": str      # Confirmation or error
}
```

**Message flow**:
1. POST arrives at server
2. Server validates run is still `running`
3. Message pushed to `RunState.pending_messages: list[UserMessage]`
4. Agent's event loop checks `pending_messages` between tool calls
5. Agent incorporates guidance into next action
6. `user_message` event emitted to WebSocket stream

```python
# Server-side handling (main.py)
@app.post("/api/run/{run_id}/message")
async def send_run_message(run_id: str, request: RunMessageRequest) -> dict:
    run = _run_manager.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != "running":
        return {"accepted": False, "run_status": run.status, 
                "message": f"Run is {run.status}, cannot accept messages"}
    
    run.pending_messages.append(UserMessage(
        content=request.content,
        type=request.type,
        timestamp=datetime.now(),
    ))
    
    # Emit event to WebSocket subscribers
    run.events.append({
        "type": "user_message",
        "data": {"content": request.content, "message_type": request.type}
    })
    
    return {"accepted": True, "run_status": "running", 
            "message": "Message queued for agent"}
```

---

## UI Component Changes

### Deleted

| File | Reason |
|------|--------|
| `ChatHistory.svelte` | Useless overlay with no persistence |
| `ConversationBlock.svelte` | Unused after Home simplification |
| Chat history button in Home | No longer needed |
| `conversationHistory` in `home.svelte.ts` | Ephemeral, disconnected from reality |

### Modified

| File | Changes |
|------|---------|
| `Home.svelte` | Remove conversation response handling, add OptionCards |
| `home.svelte.ts` | Remove `conversationHistory`, remove `mapBackendResponse` conversation case |
| `ConversationLayout.svelte` | Rename to `AgentConversation.svelte`, scope to workspace only |
| `runs.py` | Add timestamps, files_changed, pending_messages, persistence |
| `main.py` | Simplify process-goal, add run message endpoint |

### Added

| File | Purpose |
|------|---------|
| `ActivityPanel.svelte` | Project-scoped run history with grouping |
| `OptionCards.svelte` | Keyboard-navigable clarify options |
| `AgentInput.svelte` | Mid-execution message input |
| `~/.sunwell/runs/` | Persistent run storage directory |

---

## Migration

### Breaking Changes

1. **ChatHistory sidebar removed** — Users won't notice (it was useless)
2. **Conversation mode removed from Home** — Better UX replaces it

### Data Migration

None required. Existing `SimulacrumStore` data is preserved but accessed differently (through Activity Panel, not chat log).

---

## Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| Time from goal entry to agent start | ~5s (chat round-trips) | <1s (direct) |
| User confusion from broken follow-ups | High | Zero (no fake chat) |
| Project context in history | None | Full (activity panel) |
| Mid-execution guidance | Unsupported | Supported |

---

## Testing Strategy

### Phase 1 Tests (Intent Routing)

```python
# test_home_routing.py
def test_execute_intent():
    """Build/create/fix → execute response."""
    resp = client.post("/api/home/process-goal", json={"goal": "build a todo app"})
    assert resp.json()["type"] == "execute"

def test_clarify_intent():
    """Ambiguous input → clarify with options."""
    resp = client.post("/api/home/process-goal", json={"goal": "help me"})
    assert resp.json()["type"] == "clarify"
    assert len(resp.json()["options"]) >= 2

def test_no_conversation_type():
    """Conversation type removed."""
    resp = client.post("/api/home/process-goal", json={"goal": "anything"})
    assert resp.json()["type"] != "conversation"
```

### Phase 2 Tests (Run Persistence)

```python
# test_run_persistence.py
def test_run_timestamps_set():
    """Runs have started_at/completed_at."""
    run = run_manager.create_run("test goal", workspace="/tmp/test")
    run.status = "running"
    run.started_at = datetime.now()
    assert run.started_at is not None

def test_run_persisted_to_disk():
    """Completed runs saved to ~/.sunwell/runs/."""
    run = create_and_complete_run()
    assert (Path.home() / ".sunwell/runs/by-workspace").exists()
    loaded = run_manager.load_runs("/tmp/test", limit=1)
    assert loaded[0].run_id == run.run_id

def test_files_changed_tracked():
    """File writes recorded in run.files_changed."""
    run = run_manager.create_run("test", workspace="/tmp/test")
    run.files_changed.append("main.py")
    assert "main.py" in run.files_changed
```

### Phase 3 Tests (Activity Panel)

```python
# test_activity_api.py
def test_history_filters_by_workspace():
    """Workspace filter returns only matching runs."""
    create_run(workspace="/project/a")
    create_run(workspace="/project/b")
    resp = client.get("/api/run/history?workspace=/project/a")
    assert all(r["workspace"] == "/project/a" for r in resp.json())

def test_history_includes_metadata():
    """Response includes duration, files_changed."""
    resp = client.get("/api/run/history")
    run = resp.json()[0]
    assert "duration_seconds" in run
    assert "files_changed" in run
```

### Phase 4 Tests (Mid-Execution Messaging)

```python
# test_run_messaging.py
def test_message_accepted_when_running():
    """Messages accepted for running runs."""
    run = start_run()
    resp = client.post(f"/api/run/{run.run_id}/message", 
                       json={"content": "use React"})
    assert resp.json()["accepted"] is True

def test_message_rejected_when_complete():
    """Messages rejected for completed runs."""
    run = complete_run()
    resp = client.post(f"/api/run/{run.run_id}/message",
                       json={"content": "use React"})
    assert resp.json()["accepted"] is False

def test_message_event_emitted():
    """User message appears in event stream."""
    run = start_run()
    client.post(f"/api/run/{run.run_id}/message", json={"content": "test"})
    assert any(e["type"] == "user_message" for e in run.events)
```

### Frontend Tests

```typescript
// ActivityPanel.test.ts
test("groups runs by day", () => {
    const runs = [
        { started_at: "2026-01-23T10:00:00Z", goal: "today" },
        { started_at: "2026-01-22T10:00:00Z", goal: "yesterday" },
    ];
    const grouped = groupByDay(runs);
    expect(grouped["Today"]).toHaveLength(1);
    expect(grouped["Yesterday"]).toHaveLength(1);
});

// OptionCards.test.ts
test("keyboard shortcut selects option", async () => {
    render(OptionCards, { options: [{label: "A"}, {label: "B"}] });
    await fireEvent.keyDown(window, { key: "2" });
    expect(selectOption).toHaveBeenCalledWith(1);
});
```

---

## Alternatives Considered

### 1. Fix the Conversation Mode with Real AI

**Rejected**: Even with a working LLM, conversation is the wrong paradigm for goal entry. It adds latency and friction. Direct action is better.

### 2. Keep ChatHistory but Connect to SimulacrumStore

**Rejected**: Raw chat logs aren't what users want. Activity (completed work) is more useful than message transcripts.

### 3. Full Conversational Interface (ChatGPT-style)

**Rejected**: Sunwell is a development environment, not a chatbot. The value is in execution and code changes, not conversation. Conversation is a means, not an end.

---

## Design Decisions

### 1. Activity Panel: Tab (not sidebar)

**Decision**: Tab next to Backlog

**Rationale**:
- Activity is secondary to active work — shouldn't compete for screen space
- Matches existing Backlog pattern (both are "lists of work")
- User navigates to Activity intentionally, not passively notified
- Mobile/narrow screens: tabs collapse cleanly, sidebars don't

### 2. "Continue this work": Context restore (not file state)

**Decision**: Option A — restore SimulacrumStore context only

**Rationale**:
- File state restoration is fragile (files may have changed)
- User likely wants context ("what was I doing?"), not exact file state
- SimulacrumStore already has project-scoped sessions with full turn history
- Lower complexity, faster implementation, less brittle

**Implementation**:
```typescript
// ActivityPanel.svelte
function continueWork(run: RunSummary) {
    // 1. Load session context from SimulacrumStore
    // 2. Navigate to workspace with that project
    // 3. Agent can reference past work via memory retrieval
    goto(`/workspace?project=${run.workspace}&resume=${run.run_id}`);
}
```

### 3. Clarify options: Keyboard shortcuts enabled

**Decision**: `1/2/3` keys + click + Enter

**Rationale**:
- Power users expect keyboard navigation
- Low implementation cost (just keydown handler)
- Consistent with other option-selection UIs

**Implementation**:
```svelte
<svelte:window onkeydown={handleKeydown} />

{#each options as opt, i}
    <button>
        <span class="shortcut">{i + 1}</span>
        <h3>{opt.label}</h3>
    </button>
{/each}
```

---

## Appendix: What Conversation IS Good For

To be clear, this RFC doesn't eliminate conversation — it **scopes it correctly**:

| Context | Conversation? | Why |
|---------|---------------|-----|
| Home → Goal Entry | ❌ No | Direct action faster |
| Home → Project Selection | ❌ No | Visual picker better |
| Workspace → Mid-execution | ✅ Yes | Guide running agent |
| Workspace → Post-run | ✅ Yes | "Explain what you did" |
| Activity → Review | ⚠️ Maybe | Expand to see detail |

The agent conversation during execution is real and valuable. The fake conversation on Home was not.
