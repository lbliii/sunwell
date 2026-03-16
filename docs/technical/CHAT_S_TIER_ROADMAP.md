# Sunwell Chat: S-Tier Roadmap

**Goal**: Make Sunwell's chat mature, performant, reliable, and DRY — comparable to Chirp's Ollama demo and beyond.

**Status**: Analysis complete; implementation phases outlined. Verified against codebase 2026-03-16.

---

## Executive Summary

Sunwell's chat today is a minimal HTMX+SSE implementation that works but lacks polish. The agent layer (`UnifiedChatLoop`, `generate_response`, `ModelProtocol`) supports streaming and tool events; the gaps are in the **interface layer** (ChatService, templates, session handling), **correctness** (concurrent-send race, session leak, history inconsistency), and **streaming architecture** (routing indirection prevents naive token-by-token delivery).

This document identifies gaps, architectural decisions, and a phased plan to reach S-tier.

---

## 1. Current Architecture (Evidence-Based)

### 1.1 Data Flow

```
User → POST /chat/send (form) → ChatService.start_send() → asyncio.create_task
                                    ↓
                              is_multi_step(message)?
                              ├─ yes → _run_workflow (ExecutionManager DAG)
                              └─ no  → _run_loop (UnifiedChatLoop)
                                    ↓
                              Returns Fragment (chat_start: user bubble + sse-connect div)
                                    ↓
Browser swaps fragment → sse-connect opens GET /chat/stream?session_id=X
                                    ↓
ChatService.subscribe(session_id) → yields Fragments from event_queue
                                    ↓
_run_loop: UnifiedChatLoop.run() → yields str | ChatCheckpoint | AgentEvent
                                    ↓
ChatService maps to Fragments: assistant_message | tool_event | error_message
```

### 1.2 Key Files

| Layer | File | Responsibility |
|-------|------|----------------|
| **UI** | `pages/chat/page.html` | Chat container, form, message_thread |
| **UI** | `pages/chat/_message.html` | Fragment blocks: chat_start, assistant_message, tool_event, error |
| **Handler** | `pages/chat/send/page.py` | POST → start_send + Fragment scaffolding |
| **Handler** | `pages/chat/stream/page.py` | GET → EventStream from ChatService.subscribe |
| **Service** | `services/chat.py` | ChatService: session mgmt, _run_loop, _run_workflow, subscribe |
| **Agent** | `agent/chat/unified.py` | UnifiedChatLoop: DAG routing, checkpoints, execution |
| **Agent** | `agent/chat/conversation.py` | generate_response: collects full stream, returns str |
| **Agent** | `agent/chat/routing.py` | route_dag_classification: conversational vs execution paths |
| **Adapters** | `adapters/ollama.py`, `openai.py`, `anthropic.py` | generate_stream: token-by-token from model APIs |

### 1.3 What Already Works

- **Pattern 3 scaffolding**: POST returns user bubble + sse-connect div; SSE streams fragments.
- **Model streaming at adapter level**: Ollama, OpenAI, Anthropic adapters all implement `generate_stream` yielding per-token `str` chunks.
- **Tool events**: ChatService pushes `tool_event` fragments; `_message.html` renders them inline.
- **Markdown filter**: `register_markdown_filter(app)` in main.py — but **assistant_message uses plain `<p>`**, not `| markdown`.
- **Multi-path routing**: Single-step → UnifiedChatLoop; multi-step → ExecutionManager (Naaru DAG).
- **Channel adapter**: `run_for_channel` enables Telegram/etc. via same session store.

### 1.4 Routing Indirection (Critical for Streaming)

Token streaming is not a simple wrapper because `generate_response` is called **indirectly**:

```
ChatService._run_loop
  → UnifiedChatLoop.run()           # async generator, yields str | Checkpoint | Event
    → route_dag_classification()    # decides conversational vs execution
      → generate_response_fn()      # awaited — returns full str
```

`route_dag_classification` either returns `(LoopState, str)` for conversational paths or an async generator for execution paths. The conversational path **awaits** the response function. There is no place to yield intermediate tokens through this protocol without architectural change.

---

## 2. Gap Analysis

### 2.1 Token-by-Token Streaming

**Chirp Ollama**: Streams each token as `Fragment("chat.html", "stream_token", token=token)` via `ollama_chat_stream`; browser appends via `sse-swap="fragment"`; typing effect with cursor. Streaming phase runs after tool rounds complete (tools use non-streaming calls).

**Sunwell**: `generate_response` (`conversation.py:133-140`) streams internally but collects chunks and returns the full string. ChatService receives one `str` result and pushes one `assistant_message` Fragment.

**Root cause**: Two layers of indirection:

1. `conversation.py:133-140` — accumulates stream:
   ```python
   async for chunk in model.generate_stream(structured):
       response_parts.append(chunk)
   response = "".join(response_parts)
   return response
   ```

2. `routing.py` — `route_dag_classification` awaits `generate_response_fn(user_input)` for conversational paths (UNDERSTAND, ANALYZE, PLAN, fallback). No generator protocol for intermediate tokens.

**Architecture options**:

- **A (Side-channel)**: Keep existing generator protocol. Add an optional `token_callback: Callable[[str], None] | None` parameter to `generate_response`. When set, call it per chunk while still accumulating and returning the full string. `_run_loop` passes `lambda chunk: self._push(session, Fragment(..., "stream_token", token=chunk))` as the callback. Minimal refactor; works today.

- **B (Protocol refactor)**: Change `route_dag_classification` to yield intermediate `StreamToken(chunk)` events alongside final `str` results. Cleaner but touches routing, the DAG classifier, and the loop protocol. Higher risk.

**Recommendation**: **A** for Phase 2. It's pragmatic, testable, and doesn't disturb the agent layer protocol. Migrate to **B** later if streaming becomes a first-class concern in execution paths too.

### 2.2 Markdown Rendering

**Chirp**: `{{ msg.content | markdown }}` in assistant bubbles; `.msg-assistant.prose` CSS for code, lists, blockquotes.

**Sunwell**: `{{ content | default("") }}` in `<p>` — no markdown, no prose styling.

**Fix**: Use `{{ content | default("") | markdown }}` in `assistant_message` block. Add `prose` class. Markdown filter already registered in main.py. For streaming tokens, use `white-space: pre-wrap` (same as Chirp) and apply markdown only to completed messages in history.

### 2.3 Tool Activity Panel

**Chirp**: Dedicated sidebar with `sse-connect="/feed"`; `app.tool_events.subscribe()` yields `ToolCallEvent`; template block `activity_row`.

**Sunwell**: Tool events shown inline in chat thread via `tool_event` fragment. Activity feed (`/activity/feed`) exists but returns `events=[]`.

**Architecture mismatch**: Chirp uses `ToolEventBus`; Sunwell uses `AgentEvent` pushed through `asyncio.Queue`. Different event sources.

**Recommendation**: **Option C** — Collapsible "Tool Activity" panel in chat page that renders `tool_event` blocks in a dedicated scroll region. Same data, different layout. No new event bus. ChatService already pushes `tool_event` fragments; duplicate them to a second SSE target or use CSS to split the stream.

### 2.4 Model Selector

**Chirp**: Fetches `ollama list` models; `<select hx-post="/model">` dropdown; POST updates global `_model`.

**Sunwell**: `_resolve_model_web()` returns fixed `resolve_model("ollama", None)` — no UI to change, no per-session override.

**Fix**: Add model selector to chat header:
- `GET /chat/models` → query Ollama `/api/tags` (or config-based list)
- `POST /chat/model` → store model name on `ChatSession`
- `_run_loop` / `_run_workflow` → use `session.model or _resolve_model_web()`
- Template: `<select>` in chat header

### 2.5 Stream Toggle

**Chirp**: Checkbox `name="stream" value="1"` in form; when off, runs agent and returns single `chat_response` fragment (user + assistant) with no SSE scaffolding.

**Sunwell**: Always streams (SSE). No non-streaming path.

**Fix**: Add `stream` form field. When `stream=0`, `send/page.py` calls a synchronous-response path: run agent, await result, return single `chat_response` fragment (user + assistant). Requires:
- New `ChatService.send_sync(session_id, message) -> Fragment` that awaits the loop
- `_message.html` block `chat_response` with both bubbles
- `send/page.py` branches on `form.get("stream")`

Note: `is_multi_step` already routes to `_run_workflow`. Non-streaming path needs to handle both single-step and multi-step. For multi-step, show a loading state and poll or long-poll.

### 2.6 Clear Conversation

**Chirp**: `hx-post="/clear"` → `_clear_history()` → `chat_cleared` fragment replaces `#messages`.

**Sunwell**: No clear. Sessions accumulate in memory; no way to reset.

**Fix**: `POST /chat/clear` → clear `session.conversation_history`, clear `session._loop`, push `None` sentinel if stream active. Return fragment replacing `#chat-messages` with empty state.

### 2.7 Session Persistence Bug

**Current**: `chat/page.py:8` calls `ChatService.new_session_id()` on **every GET**:

```python
async def get(chat_svc: ChatService) -> dict:
    session_id = ChatService.new_session_id()  # Always new!
    messages = chat_svc.get_conversation_history(session_id)  # Always empty!
```

Refreshing the page creates a new session; the old conversation is orphaned.

**Recommendation**: Cookie-based. `get()` reads `session_id` from request cookie; creates new only if missing or expired; sets cookie in response. Simple, works without JS. Cookie should be `HttpOnly`, `SameSite=Lax`, with a reasonable TTL (e.g. 24h).

### 2.8 Concurrent Send Race Condition

**Not in original plan. Discovered in code review.**

**Current**: `start_send` calls `asyncio.create_task` unconditionally. Two rapid sends on the same session run two agents concurrently, both pushing to the same `event_queue` and appending to `conversation_history`.

**Result**: Interleaved fragments in the UI, corrupted conversation history, unpredictable agent behavior.

**Fix**: Guard on `session._loop is not None`:
```python
def start_send(self, session_id: str, message: str) -> None:
    session = self._get_or_create_session(session_id)
    if session._loop is not None:
        self._push(session, Fragment("chat/_message.html", "error_message",
                                     error="A response is already in progress."))
        return
    # ... proceed with create_task
```

Template: disable send button while SSE is active (`htmx:sseOpen` / `htmx:sseClose` events or `hx-disabled-elt`).

### 2.9 Session Memory Leak

**Not in original plan. Discovered in code review.**

**Current**: `_sessions: dict[str, ChatSession]` grows without bound. Sessions are never removed. Each session holds `conversation_history` (grows with each message) and `event_queue`.

**Fix**: TTL-based eviction. Options:
- Lazy eviction: on `_get_or_create_session`, prune sessions older than TTL (e.g. 1 hour)
- Background task: periodic sweep every N minutes
- LRU with max size: `OrderedDict` or similar, evict oldest when limit reached

Recommendation: Lazy eviction with a `last_active: float` timestamp on `ChatSession`. Check on access; prune stale entries. Low complexity, no background task needed.

### 2.10 Inconsistent History Append

**Not in original plan. Discovered in code review.**

**Current**: History append logic differs by code path:

| Path | User appended? | Assistant appended? |
|------|---------------|-------------------|
| `_run_loop` → `str` result | Yes | Yes |
| `_run_loop` → `ChatCheckpoint(COMPLETION)` | No | Yes |
| `_run_workflow` | Yes | Yes |

When `_run_loop` receives a `ChatCheckpoint(COMPLETION)`, only the assistant message is appended. The user message is lost from history, causing context drift in subsequent turns.

**Fix**: Always append both user and assistant messages at the start/end of the loop, regardless of result type. Move user append to the beginning of `_run_loop` (before `gen.asend`), and assistant append to the fragment-push site for all result types.

### 2.11 Stream Handler Missing Session Guard

**Not in original plan. Discovered in code review.**

**Current**: `stream/page.py` falls back to `ChatService.new_session_id()` when `session_id` is absent:
```python
session_id = request.query.get("session_id") or ChatService.new_session_id()
```

A request without `session_id` creates an orphan session with no agent running. `subscribe` blocks forever (only heartbeats sent). The browser hangs.

**Fix**: Return HTTP 400 when `session_id` is missing or doesn't correspond to an active session.

### 2.12 Loading Indicator

**Chirp**: Spinner "Thinking" with `htmx-indicator` for non-streaming mode.

**Sunwell**: No explicit loading state. If SSE connection is slow, user sees nothing between POST and first fragment.

**Fix**: Add `htmx-indicator` to the send form. Show spinner in the AI bubble immediately (via `chat_start` scaffolding). Remove spinner when first `stream_token` or `assistant_message` arrives. ChirpUI spinner component or simple CSS animation.

### 2.13 Error Handling & Reliability

**Current**: Exceptions in `_run_loop` push `error_message` fragment. No retry, no SSE reconnection logic.

**Improvements**:
- **SSE reconnect**: htmx-ext-sse supports reconnection. Ensure `/chat/stream` is idempotent for a given session_id (re-subscribing to a completed session should return immediately, not hang).
- **Heartbeat**: Long-running agent tasks can take 30s+. SSE heartbeat prevents proxy/browser timeout. Chirp's SSE handler already sends heartbeats — verify interval is adequate.
- **Queue backpressure**: `event_queue.put_nowait` logs and drops on `QueueFull`. Default queue is unbounded (so this never triggers), but if bounded queues are added, drops are silent. Use bounded queue with explicit overflow handling.
- **SSE done event**: Chirp Ollama sends `SSEEvent(event="done", data="complete")` and uses `sse-close="done"` to cleanly close the connection. Sunwell's sentinel is a `None` in the queue that stops the generator, but there's no explicit `done` event. Add `sse-close="done"` to the SSE div and emit a done event after the sentinel.

### 2.14 DRY Opportunities

| Concern | Chirp Ollama | Sunwell | Status |
|---------|--------------|---------|--------|
| Prose/markdown CSS | Inline in chat.html | None | Add to sunwell CSS; share via ChirpUI later |
| Fragment block names | `stream_token`, `chat_response`, `activity_row` | `assistant_message`, `tool_event` | Align incrementally as streaming is added |
| Tool event shape | `event.tool_name`, `event.arguments` | `tool_name`, `args` | Minor; align when touching templates |

**Deferred**: Extracting a shared `chirpui/chat.html` component is premature. Chirp Ollama is a self-contained example (no ChirpUI imports); Sunwell has a multi-path agent loop. The abstraction surface is too different today. Revisit after Phases 1-4 stabilize and the actual shared surface becomes clear.

---

## 3. Phased Implementation Plan

### Phase 1: Correctness & Quick Wins (2–3 days)

Priority: fix data corruption and usability bugs before adding features.

| Task | Files | Effort | Gap |
|------|-------|--------|-----|
| Concurrent send guard | `chat.py`, `_message.html` | 1 hr | 2.8 |
| Session persistence (cookie) | `page.py`, `send/page.py` | 1 hr | 2.7 |
| Session eviction (TTL) | `chat.py` (ChatSession) | 1 hr | 2.9 |
| Consistent history append | `chat.py` (_run_loop) | 30 min | 2.10 |
| Stream handler 400 on missing session | `stream/page.py` | 15 min | 2.11 |
| Markdown in assistant bubbles | `_message.html` | 5 min | 2.2 |
| Prose CSS for code/lists | `page.html` or shared CSS | 30 min | 2.2 |
| Clear conversation button | `page.html`, new `clear/page.py` | 1 hr | 2.6 |
| Loading spinner in chat_start | `_message.html`, `page.html` | 30 min | 2.12 |
| SSE done event + sse-close | `chat.py`, `_message.html` | 30 min | 2.13 |

### Phase 2: Token Streaming (4–5 days)

Uses the side-channel approach (Option A) to avoid refactoring the agent protocol.

| Task | Files | Effort | Notes |
|------|-------|--------|-------|
| Add `token_callback` param to `generate_response` | `conversation.py` | 1 hr | Call per-chunk alongside accumulation |
| Thread callback through routing | `unified.py`, `routing.py` | 3 hr | Pass through `_generate_response` → `generate_response_fn` → `route_dag_classification` |
| ChatService: create callback that pushes `stream_token` | `chat.py` | 2 hr | Callback creates Fragment and pushes to queue |
| `stream_token` block + cursor CSS | `_message.html` | 1 hr | `<span>{{ token }}</span>` appended to streaming div |
| Update `chat_start` scaffolding | `_message.html` | 30 min | Add `sse-close="done"`, cursor span |
| Final `assistant_message` with markdown after stream completes | `chat.py` | 1 hr | Replace streaming div with rendered markdown |
| Handle non-streaming models gracefully | `chat.py`, `conversation.py` | 1 hr | Fallback: no callback, single fragment |
| Test with Ollama, OpenAI, non-streaming | Manual | 2 hr | Verify all adapter paths |

### Phase 3: Tool Activity Panel (1 day)

| Task | Files | Effort |
|------|-------|--------|
| Two-column layout on chat page | `page.html` | 1 hr |
| Activity panel receiving tool_event blocks | `page.html`, `_message.html` | 2 hr |
| Collapsible on mobile / toggle button | CSS, `page.html` | 30 min |
| Empty state ("No tool activity yet") | `_message.html` | 15 min |

### Phase 4: Model Selector & Stream Toggle (2 days)

| Task | Files | Effort |
|------|-------|--------|
| `model` field on ChatSession | `chat.py` | 15 min |
| GET /chat/models (Ollama list + config) | New handler `models/page.py` | 1 hr |
| POST /chat/model (set per session) | New handler `model/page.py` | 1 hr |
| Model dropdown in header | `page.html` | 1 hr |
| `_run_loop` / `_run_workflow` use session.model | `chat.py` | 30 min |
| Stream toggle checkbox in form | `page.html` | 30 min |
| Non-streaming send path | `send/page.py`, `chat.py` | 2 hr |
| `chat_response` block (user + assistant) | `_message.html` | 30 min |

### Phase 5: Reliability Hardening (1–2 days)

| Task | Files | Effort |
|------|-------|--------|
| SSE reconnect handling (idempotent subscribe) | `chat.py`, `stream/page.py` | 2 hr |
| Bounded queue + overflow logging | `chat.py` | 1 hr |
| Heartbeat tuning for long agent runs | `chat.py` | 1 hr |
| Error recovery UX (retry button) | `_message.html` | 1 hr |
| Cancel in-progress run (button + endpoint) | `page.html`, new handler, `chat.py` | 2 hr |

### Phase 6: Convention Alignment (1 day, deferred)

Revisit after Phases 1-5 stabilize.

| Task | Files | Effort |
|------|-------|--------|
| Align fragment block naming with Chirp conventions | `_message.html`, `chat.py` | 2 hr |
| Document Pattern 3 streaming in Chirp | chirp docs | 2 hr |
| Evaluate shared chat component extraction | Design doc | 2 hr |

---

## 4. Architectural Principles

### 4.1 Single Source of Truth

- **Session state**: ChatService owns `ChatSession`; page handlers are thin.
- **Model config**: `ChatSession.model` for per-session; `_resolve_model_web()` as default.
- **Fragment templates**: One set of blocks in `_message.html`.

### 4.2 Correctness First

- No data corruption under concurrent access.
- Conversation history is consistent regardless of which code path runs.
- Sessions have bounded lifetime; stale state is evicted.

### 4.3 Fail Gracefully

- Markdown filter missing → fallback to plain text.
- Model list fails → show current model only, no dropdown.
- SSE disconnect → show "Reconnecting..." or "Connection lost"; allow retry.
- Non-streaming model → single fragment, no degradation.

### 4.4 Performance

- **Token streaming**: Reduces perceived latency; user sees progress immediately.
- **Bounded queues**: Prevent memory blow-up from slow consumers.
- **Session eviction**: Prevents OOM from abandoned sessions.
- **Lazy model list**: Fetch on demand, cache briefly.

### 4.5 Thread Safety (3.14t)

`ChatService._sessions` is accessed only from the asyncio event loop today (single-threaded). If any code path moves to a thread pool executor or free-threading context:
- `_sessions` access needs `threading.Lock` protection.
- `ChatSession` fields (`conversation_history`, `_loop`) need the same.
- Current design is safe under asyncio; document the constraint.

### 4.6 Testability

- `ChatService._run_loop` is async; use `asyncio.Queue` for test injection.
- `token_callback` can be a mock that collects tokens for assertion.
- Fragment rendering: unit test template blocks with mock context.
- Integration: TestClient for POST/GET flows.
- Concurrent send: test that second send is rejected while first is active.

---

## 5. Streaming Architecture Decision Record

### Context

Token-by-token streaming requires pushing fragments from inside `generate_response`, but `generate_response` is called deep in the agent protocol stack: `_run_loop` → `UnifiedChatLoop.run()` → `route_dag_classification` → `generate_response_fn()`.

### Decision

**Phase 2 uses Option A (side-channel callback).**

`generate_response` accepts an optional `token_callback: Callable[[str], None] | None`. When set, each chunk from `model.generate_stream` is forwarded to the callback before being appended to the accumulator. The function still returns the full string for protocol compatibility.

```python
async def generate_response(
    model, user_input, conversation_history, workspace,
    execution_context=None,
    token_callback: Callable[[str], None] | None = None,
) -> str:
    ...
    if hasattr(model, "generate_stream"):
        response_parts: list[str] = []
        async for chunk in model.generate_stream(structured):
            response_parts.append(chunk)
            if token_callback:
                token_callback(chunk)
        return "".join(response_parts)
```

### Consequences

- **Pro**: Zero change to `UnifiedChatLoop.run()` protocol, `route_dag_classification`, or checkpoint handling.
- **Pro**: Non-streaming models work unchanged (callback is never called).
- **Pro**: `_run_workflow` path can adopt the same callback pattern independently.
- **Con**: Callback is a side-effect; harder to test than a pure generator.
- **Con**: Final `assistant_message` fragment (with full markdown) is still sent after stream completes, causing a brief flash as the streaming div is replaced. Mitigate with CSS transition.

### Future

If streaming becomes a first-class concern (e.g., execution-path streaming, multi-model streaming), migrate to Option B: `route_dag_classification` yields `StreamToken` events. This is a larger refactor scoped to a future phase.

---

## 6. Dependencies

| Dependency | Purpose | Required Phase |
|------------|---------|---------------|
| chirp[markdown] (patitas) | `| markdown` filter | Phase 1 |
| htmx-ext-sse | SSE for streaming | Already present |
| ChirpUI | message_bubble, spinner, layout | Already present |
| Ollama (optional) | Model list, local inference | Phase 4 |

---

## 7. Success Criteria

### Phase 1 (Correctness)
- [x] Concurrent sends are rejected with user-facing message
- [x] Session persists across page refresh (cookie)
- [x] Stale sessions are evicted after TTL
- [x] History is consistent across all code paths
- [x] Stream handler returns 400 on missing session_id
- [x] Markdown rendered in assistant messages with prose styling
- [x] Clear conversation works
- [x] Loading spinner visible during agent processing
- [x] SSE connection closes cleanly via done event

### Phase 2 (Streaming)
- [x] Token-by-token streaming with typing cursor (Ollama)
- [x] Token-by-token streaming works with OpenAI/Anthropic adapters
- [x] Non-streaming models fall back to single fragment
- [x] Final message renders with full markdown after stream completes

### Phase 3 (Tool Panel)
- [x] Collapsible tool activity panel shows tool_event fragments
- [x] Panel collapses on mobile

### Phase 4 (Model & Toggle)
- [x] Model selector lists available models
- [x] Model selection persists per session
- [x] Stream toggle switches between streaming and full-response modes

### Phase 5 (Reliability)
- [x] SSE reconnect resumes or terminates gracefully
- [x] Long-running agent tasks don't timeout the SSE connection
- [x] User can cancel an in-progress run

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Side-channel callback leaks into agent tests | Medium | Low | Callback is optional; agent tests don't pass one |
| Streaming flash on markdown replacement | High | Low | CSS transition; or skip final replace if content matches |
| Cookie session_id reused across tabs | Medium | Medium | Use tab-scoped session (sessionStorage + hidden field) for multi-tab |
| Ollama unavailable → model selector empty | Medium | Low | Show "No models found" + manual input fallback |
| Session eviction during active stream | Low | High | Don't evict sessions with active `_loop` |

---

## 9. References

- Chirp Ollama example: `chirp/examples/ollama/app.py`
- Chirp Pattern 3: POST scaffolding + SSE stream
- ChatService: `sunwell/interface/chirp/services/chat.py`
- UnifiedChatLoop: `sunwell/agent/chat/unified.py`
- Routing: `sunwell/agent/chat/routing.py`
- Conversation: `sunwell/agent/chat/conversation.py`
- Model adapters: `sunwell/adapters/ollama.py`, `openai.py`, `anthropic.py`
- Sunwell chirp-mcp-integration.md
- Sunwell chirp-ui-dogfooding-plan.md
