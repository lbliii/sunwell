# RFC-118: Conversation Architecture Overhaul

**Status**: Draft  
**Author**: System  
**Created**: 2026-01-23  
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

**Data source**: Leverages existing infrastructure:
- `RunManager` tracks runs with goal, status, events
- `SimulacrumStore` has project-scoped sessions
- `ExecutionCache` tracks execution history

**Actions**:
- Click run → Expand to show full event log
- Click run → "Continue this work" (resume context)
- Filter by status (completed/failed/in-progress)

---

## Implementation Plan

### Phase 1: Remove Broken Conversation (Day 1)

1. **Delete `ChatHistory.svelte`**
2. **Remove chat history button from Home**
3. **Simplify `process-goal` endpoint**:
   - Remove unused `history` parameter
   - Remove "conversation" response type
   - Ambiguous → Return `type: "clarify"` with options

### Phase 2: Clean Up Home Routing (Day 1-2)

1. **New intent classifier** with clear outcomes:
   ```python
   class IntentResult:
       action: Literal["execute", "view", "clarify"]
       workspace: str | None  # For execute
       view_type: str | None  # For view
       options: list[dict] | None  # For clarify
   ```

2. **Option cards for ambiguity** (not chat):
   ```typescript
   interface ClarifyResponse {
     type: "clarify";
     prompt: string;
     options: Array<{
       label: string;
       description: string;
       action: string;  // e.g., "execute:code", "view:plan"
     }>;
   }
   ```

3. **Frontend renders option cards**:
   ```svelte
   {#if response.type === 'clarify'}
     <div class="option-cards">
       {#each response.options as opt}
         <button onclick={() => selectOption(opt.action)}>
           <h3>{opt.label}</h3>
           <p>{opt.description}</p>
         </button>
       {/each}
     </div>
   {/if}
   ```

### Phase 3: Activity Panel (Day 2-3)

1. **New component `ActivityPanel.svelte`**:
   - Props: `projectPath: string`
   - Fetches from `/api/run/history?workspace={projectPath}`
   - Groups by day
   - Shows goal, status, duration, files changed

2. **Extend `/api/run/history` endpoint**:
   ```python
   @app.get("/api/run/history")
   async def get_run_history(
       workspace: str | None = None,
       limit: int = 50,
   ) -> list[RunSummary]:
       # Filter by workspace if provided
       # Include files_changed, duration, error message
   ```

3. **Integrate into project workspace**:
   - Add "Activity" tab next to Backlog
   - Or: Collapsible panel in workspace sidebar

### Phase 4: Workspace Conversation (Day 3-4)

1. **Improve agent execution UI**:
   - Clear input field for mid-execution messages
   - Messages appear inline with execution events
   - Visual distinction between user guidance and agent actions

2. **Wire user messages to agent**:
   - Already supported by `RunState` — just need UI
   - POST to `/api/run/{run_id}/message` (new endpoint)
   - Agent receives via event loop

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
# New endpoint for workspace filtering
GET /api/run/history?workspace={path}&limit={n}

# New endpoint for mid-execution messages
POST /api/run/{run_id}/message
{
    "content": str
}
```

---

## UI Component Changes

### Deleted

- `ChatHistory.svelte` — Useless overlay
- `ConversationBlock.svelte` — Unused after Home simplification
- Chat history button in Home header

### Modified

- `ConversationLayout.svelte` → Renamed to `AgentConversation.svelte`, scoped to workspace
- `Home.svelte` → No more conversation response handling

### Added

- `ActivityPanel.svelte` — Project-scoped run history
- `OptionCards.svelte` — For clarify responses
- `AgentInput.svelte` — Input for mid-execution chat

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

## Alternatives Considered

### 1. Fix the Conversation Mode with Real AI

**Rejected**: Even with a working LLM, conversation is the wrong paradigm for goal entry. It adds latency and friction. Direct action is better.

### 2. Keep ChatHistory but Connect to SimulacrumStore

**Rejected**: Raw chat logs aren't what users want. Activity (completed work) is more useful than message transcripts.

### 3. Full Conversational Interface (ChatGPT-style)

**Rejected**: Sunwell is a development environment, not a chatbot. The value is in execution and code changes, not conversation. Conversation is a means, not an end.

---

## Open Questions

1. **Should Activity Panel be a tab or always-visible sidebar?**
   - Tab: Cleaner, but requires navigation
   - Sidebar: Always visible, but takes space

2. **How to handle "continue this work" from Activity?**
   - Option A: Just restore SimulacrumStore context
   - Option B: Full session resume with file state

3. **Should clarify options support keyboard shortcuts?**
   - 1/2/3 keys to select option
   - Or just click/enter

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
