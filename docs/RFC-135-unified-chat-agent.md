# RFC-135: Unified Chat-Agent Experience

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-25  
**Updated**: 2026-01-25  
**Related**: RFC-128 (Session Checkpoints), RFC-134 (Task Queue Interactivity), RFC-110 (Agent Simplification)

> **Dependency Status**:
> - RFC-128: Provides `AgentCheckpoint` and `CheckpointPhase` — **VERIFIED** in `naaru/checkpoint.py`
> - RFC-134: Provides task queue modification during execution — **VERIFIED** via `add_task_to_queue` event
> - RFC-110: Agent simplification — **VERIFIED** in `agent/core.py`

---

## Executive Summary

Sunwell has two separate experiences that should be one:

| Current | Entry Point | Capabilities |
|---------|-------------|--------------|
| **Chat** | `sunwell chat` | Conversation, simple tool loop, memory/identity |
| **Agent** | `sunwell "goal"` | Harmonic planning, validation gates, auto-fix, exits when done |

Users expect a **Claude Code / Cursor-like experience**: start conversing, seamlessly transition to execution when needed, return to conversation at checkpoints or completion.

**Current**: Two isolated worlds. Chat can't plan. Agent can't converse.

**Proposed**: Unified loop with **intent detection** and **checkpoint-based handoff** between conversation and execution modes.

```
┌─────────────────────────────────────────────────────────────┐
│                     Unified Chat Loop                        │
│                                                              │
│   User Input                                                 │
│       ↓                                                      │
│   ┌───────────────┐                                          │
│   │ Intent Router │                                          │
│   └───────┬───────┘                                          │
│           │                                                  │
│     ┌─────┴─────┐                                            │
│     ↓           ↓                                            │
│  Question    Task/Goal                                       │
│     ↓           ↓                                            │
│  Respond    ┌────────────┐                                   │
│     ↓       │   Agent    │                                   │
│     │       │  Planning  │                                   │
│     │       └─────┬──────┘                                   │
│     │             ↓                                          │
│     │       ┌────────────┐                                   │
│     │       │  Execute   │←──── Checkpoint ────┐             │
│     │       │  with      │      (confirm,      │             │
│     │       │  Gates     │       clarify,      │             │
│     │       └─────┬──────┘       error)        │             │
│     │             ↓                            │             │
│     │       ┌────────────┐                     │             │
│     │       │ Completion │─────────────────────┘             │
│     │       └─────┬──────┘                                   │
│     │             ↓                                          │
│     └────────────→ Continue Conversation ←───────────────────┘
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Goals

| Goal | Benefit |
|------|---------|
| **Single entry point** | `sunwell chat` handles both conversation and execution |
| **Intent detection** | Automatically route questions vs tasks |
| **Seamless transition** | No mode switching, no restart |
| **Checkpoint handoff** | Agent yields control at key moments |
| **Shared context** | Conversation history flows into agent, learnings persist |
| **Claude Code parity** | Match the UX users expect from modern AI coding tools |

---

## 🚫 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Replace `sunwell "goal"` CLI | Keep direct goal execution for scripts/CI |
| Fully autonomous mode | Checkpoints require user involvement by design |
| Real-time collaboration | Single-user focus for now |
| Studio integration (this RFC) | Studio can adopt same patterns in future RFC |

---

## 📍 User Journey Analysis

### Journey 1: Conversation → Execution → Conversation

**Current Experience**:
```
$ sunwell chat
You: What's in this codebase?
Assistant: This is a FastAPI project with...

You: Add user authentication
Assistant: [Describes how to add auth - doesn't actually do it]

# User must exit chat, run sunwell "add auth", then re-enter chat
```

**Proposed Experience**:
```
$ sunwell chat
You: What's in this codebase?
Assistant: This is a FastAPI project with...

You: Add user authentication

[Agent activates]
✦ Planning...
★ Plan ready (4 tasks)
   1. Create models/user.py (User, hash_password)
   2. Create routes/auth.py (login, register, logout)
   3. Create middleware/auth.py (JWT verification)
   4. Update main.py (include router)

Proceed? [Y/n/edit]: y

[1/4] Creating models/user.py...
   ✓ wrote models/user.py

[2/4] Creating routes/auth.py...
   ✓ wrote routes/auth.py (38 lines)

[Gate: syntax] ✓ passed
[Gate: lint] ✓ passed

[3/4] Creating middleware/auth.py...
   ✓ wrote middleware/auth.py

[4/4] Updating main.py...
   ✓ edited main.py (+3 lines)

✓ Complete. 4 files created/modified.

You: Can you also add rate limiting to the login endpoint?

[Agent activates for smaller task...]
```

### Journey 2: Checkpoint on Uncertainty

**Proposed Experience**:
```
You: Refactor the database layer to use SQLAlchemy

[Agent activates]
✦ Planning...

⚠️ Checkpoint: Clarification needed

I found 2 database approaches in use:
- `db/raw.py` uses raw SQL queries
- `db/models.py` uses dataclasses with manual queries

Which should I migrate to SQLAlchemy?
  [1] Both (full migration)
  [2] Just raw.py (keep dataclasses as-is)
  [3] Let me specify files

You: 1

★ Plan ready (6 tasks)...
[Continues with execution]
```

### Journey 3: Checkpoint on Failure

**Proposed Experience**:
```
[2/4] Creating routes/auth.py...
   ✓ wrote routes/auth.py

[Gate: syntax] ✗ FAILED
   - Line 23: undefined name 'hash_password'

⚠️ Checkpoint: Validation failed

The generated code has an error. How should I proceed?
  [a] Auto-fix (attempt Compound Eye repair)
  [s] Skip this task
  [m] Manual - let me fix it myself
  [r] Retry with different approach

You: a

[Auto-fixing...]
   ✓ Added import from models/user.py
   ✓ Re-validated: syntax passes

[Continues with task 3...]
```

### Journey 4: Interleaved Questions During Execution

**Proposed Experience**:
```
[2/4] Creating routes/auth.py...
   ✓ wrote routes/auth.py

You: Wait, what JWT library are you using?

[Execution paused]

I'm using `python-jose` for JWT handling. It's already in your 
pyproject.toml dependencies. I chose it because:
- Lightweight
- Supports multiple algorithms
- Already present in project

Continue execution? [Y/n]: y

[3/4] Creating middleware/auth.py...
```

### Journey 5: Adding Tasks Mid-Execution

**Proposed Experience**:
```
[2/4] Creating routes/auth.py...
   ✓ wrote routes/auth.py

You: Actually, also add password reset functionality

[Queue updated]
   ✓ [2/5] routes/auth.py complete
   → [3/5] middleware/auth.py (running)
   ○ [4/5] Update main.py
   ★ [5/5] Add password reset routes (NEW)

[Continues execution with new task in queue...]
```

---

## 🏗️ Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    UnifiedChatLoop                          │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ IntentRouter │───▶│  ChatMode    │    │  AgentMode   │  │
│  │              │    │ (streaming)  │    │ (planning +  │  │
│  │ - classify   │    │              │    │  execution)  │  │
│  │ - threshold  │    └──────────────┘    └──────┬───────┘  │
│  └──────────────┘                               │          │
│                                                 │          │
│  ┌──────────────────────────────────────────────▼────────┐ │
│  │                  CheckpointHandler                     │ │
│  │                                                        │ │
│  │  - confirmation (before execution)                    │ │
│  │  - clarification (ambiguous goal)                     │ │
│  │  - failure (gate failed, error)                       │ │
│  │  - completion (task done)                             │ │
│  │  - interruption (user input during execution)         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  SharedContext                        │  │
│  │  - ConversationHistory (survives mode switches)       │  │
│  │  - SessionContext (workspace, project type)           │  │
│  │  - PersistentMemory (learnings, decisions, failures)  │  │
│  │  - IdentityStore (user preferences)                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### IntentRouter

Classifies user input into conversation vs task.

```python
# src/sunwell/chat/intent.py

from dataclasses import dataclass
from enum import Enum


class Intent(Enum):
    CONVERSATION = "conversation"  # Question, discussion, clarification
    TASK = "task"                  # Action request, goal
    INTERRUPT = "interrupt"        # Input during execution
    COMMAND = "command"            # /slash command or :: shortcut


@dataclass(frozen=True, slots=True)
class IntentClassification:
    intent: Intent
    confidence: float
    task_description: str | None = None  # Extracted goal if TASK
    reasoning: str | None = None         # Why this classification


class IntentRouter:
    """Classify user input intent for chat-agent routing."""
    
    # High-signal task indicators
    TASK_VERBS = frozenset({
        "add", "create", "build", "implement", "make", "write",
        "fix", "refactor", "update", "modify", "change", "delete",
        "remove", "migrate", "convert", "generate", "setup", "configure",
    })
    
    # High-signal conversation indicators
    QUESTION_STARTERS = frozenset({
        "what", "why", "how", "when", "where", "who", "which",
        "can you explain", "tell me about", "describe",
    })
    
    def __init__(self, model=None, threshold: float = 0.7):
        """
        Args:
            model: Optional LLM for ambiguous cases
            threshold: Confidence threshold for task classification
        """
        self.model = model
        self.threshold = threshold
    
    async def classify(self, user_input: str, context: str | None = None) -> IntentClassification:
        """Classify user input intent.
        
        Uses heuristics first, falls back to LLM for ambiguous cases.
        """
        # Check for explicit commands
        if user_input.startswith("/") or user_input.startswith("::"):
            return IntentClassification(
                intent=Intent.COMMAND,
                confidence=1.0,
            )
        
        # Heuristic classification
        lower = user_input.lower().strip()
        words = lower.split()
        
        # Check for task indicators
        first_word = words[0] if words else ""
        has_task_verb = first_word in self.TASK_VERBS
        has_imperative = any(w in self.TASK_VERBS for w in words[:3])
        
        # Check for question indicators
        is_question = lower.endswith("?")
        has_question_starter = any(lower.startswith(q) for q in self.QUESTION_STARTERS)
        
        # Score
        task_score = 0.0
        if has_task_verb:
            task_score += 0.5
        if has_imperative:
            task_score += 0.2
        if not is_question:
            task_score += 0.1
        if len(words) > 3 and has_task_verb:  # "Add user authentication" vs "Add"
            task_score += 0.2
        
        conv_score = 0.0
        if is_question:
            conv_score += 0.4
        if has_question_starter:
            conv_score += 0.4
        
        # Determine intent
        if task_score >= self.threshold:
            return IntentClassification(
                intent=Intent.TASK,
                confidence=task_score,
                task_description=user_input,
                reasoning="Imperative verb detected",
            )
        
        if conv_score >= self.threshold:
            return IntentClassification(
                intent=Intent.CONVERSATION,
                confidence=conv_score,
                reasoning="Question pattern detected",
            )
        
        # Ambiguous - use LLM if available
        if self.model and abs(task_score - conv_score) < 0.3:
            return await self._classify_with_llm(user_input, context)
        
        # Default to higher score
        if task_score > conv_score:
            return IntentClassification(
                intent=Intent.TASK,
                confidence=task_score,
                task_description=user_input,
                reasoning="Heuristic: task score higher",
            )
        
        return IntentClassification(
            intent=Intent.CONVERSATION,
            confidence=conv_score,
            reasoning="Heuristic: conversation score higher",
        )
    
    async def _classify_with_llm(self, user_input: str, context: str | None) -> IntentClassification:
        """Use LLM for ambiguous classification."""
        prompt = f"""Classify this user input as either TASK or CONVERSATION.

TASK: User wants something done (create, modify, fix code)
CONVERSATION: User wants information, explanation, or discussion

User input: "{user_input}"

Respond with only: TASK or CONVERSATION"""

        result = await self.model.generate(
            ({"role": "user", "content": prompt},),
        )
        
        text = result.text.strip().upper()
        is_task = "TASK" in text
        
        return IntentClassification(
            intent=Intent.TASK if is_task else Intent.CONVERSATION,
            confidence=0.8,  # LLM classification
            task_description=user_input if is_task else None,
            reasoning="LLM classification",
        )
```

### Checkpoint System

Agent yields control back to chat at specific points via **user-facing checkpoints**.

> **Design Note: CheckpointType vs CheckpointPhase**
> 
> The codebase already has `CheckpointPhase` in `naaru/checkpoint.py` for **internal agent state** 
> (ORIENT_COMPLETE, PLAN_COMPLETE, etc.). This RFC introduces `ChatCheckpointType` for 
> **user-facing handoff points** in the unified loop. The distinction:
> 
> | Concept | Purpose | Location | Persistence |
> |---------|---------|----------|-------------|
> | `CheckpointPhase` | Agent internal workflow state | `naaru/checkpoint.py` | Saved to disk for crash recovery |
> | `ChatCheckpointType` | User interaction points | `chat/checkpoint.py` | In-memory only |
> 
> These are complementary: when agent saves a `CheckpointPhase.PLAN_COMPLETE`, the unified loop 
> yields a `ChatCheckpointType.CONFIRMATION` to the user.

```python
# src/sunwell/chat/checkpoint.py

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChatCheckpointType(Enum):
    """User-facing checkpoint types for chat-agent handoff.
    
    Distinct from naaru.checkpoint.CheckpointPhase which tracks internal agent state.
    These represent points where the unified loop yields control to the user.
    """
    CONFIRMATION = "confirmation"      # Before execution starts (maps to PLAN_COMPLETE)
    CLARIFICATION = "clarification"    # Need more info from user (during planning)
    FAILURE = "failure"                # Gate failed, error occurred
    COMPLETION = "completion"          # Task or goal complete (maps to REVIEW_COMPLETE)
    INTERRUPTION = "interruption"      # User typed during execution


@dataclass(frozen=True, slots=True)
class ChatCheckpoint:
    """A point where agent yields control to chat.
    
    This is the user-facing checkpoint yielded by UnifiedChatLoop.
    For internal agent state persistence, see naaru.checkpoint.AgentCheckpoint.
    """
    
    type: ChatCheckpointType
    message: str
    options: tuple[str, ...] = ()      # Available choices
    default: str | None = None         # Default choice
    context: dict[str, Any] | None = None  # Additional data
    
    # For FAILURE checkpoints
    error: str | None = None
    recovery_options: tuple[str, ...] = ()
    
    # For COMPLETION checkpoints
    summary: str | None = None
    files_changed: tuple[str, ...] = ()
    
    # Link to internal agent checkpoint (for resume support)
    agent_checkpoint_id: str | None = None


class CheckpointResponse:
    """User's response to a checkpoint."""
    
    def __init__(self, choice: str, additional_input: str | None = None):
        self.choice = choice
        self.additional_input = additional_input
    
    @property
    def proceed(self) -> bool:
        return self.choice.lower() in ("y", "yes", "proceed", "continue", "a", "auto")
    
    @property
    def skip(self) -> bool:
        return self.choice.lower() in ("s", "skip", "n", "no")
    
    @property
    def manual(self) -> bool:
        return self.choice.lower() in ("m", "manual")
    
    @property
    def abort(self) -> bool:
        return self.choice.lower() in ("q", "quit", "abort", "cancel")
```

### Unified Chat Loop

The new main loop that handles both modes.

> **Design Note: Async Generator Pattern**
> 
> The `UnifiedChatLoop.run()` method uses an async generator with `yield` and `asend()`.
> This pattern has edge cases that must be handled carefully:
> 
> 1. **Initialization**: Caller must call `await gen.asend(None)` before first input
> 2. **StopIteration**: Generator can complete unexpectedly; wrap in try/except
> 3. **Cleanup**: Use `aclose()` for graceful shutdown
> 4. **Concurrent input**: User input during execution queued via `_pending_input`

```python
# src/sunwell/chat/unified.py

import asyncio
from collections.abc import AsyncIterator
from enum import Enum
from pathlib import Path
from typing import Any

from sunwell.agent import Agent, AgentEvent, EventType
from sunwell.chat.checkpoint import ChatCheckpoint, ChatCheckpointType, CheckpointResponse
from sunwell.chat.intent import Intent, IntentRouter
from sunwell.context.session import SessionContext
from sunwell.memory.persistent import PersistentMemory


class LoopState(Enum):
    """State machine for the unified loop."""
    IDLE = "idle"                 # Waiting for user input
    CLASSIFYING = "classifying"   # Analyzing intent
    CONVERSING = "conversing"     # Generating chat response
    PLANNING = "planning"         # Agent creating plan
    CONFIRMING = "confirming"     # Awaiting user confirmation
    EXECUTING = "executing"       # Running tasks
    INTERRUPTED = "interrupted"   # User input during execution
    COMPLETED = "completed"       # Goal finished
    ERROR = "error"               # Unrecoverable error


class UnifiedChatLoop:
    """Unified chat-agent experience with seamless transitions.
    
    Manages the state machine between conversation and agent modes,
    yielding user-facing ChatCheckpoints at handoff points.
    
    Thread Safety:
        Not thread-safe. Use one loop per conversation.
    
    Error Handling:
        - Generator errors are caught and converted to ERROR state
        - User can recover via checkpoint or /abort command
        - Internal agent errors yield FAILURE checkpoints
    """
    
    def __init__(
        self,
        model,
        tool_executor,
        workspace: Path,
        *,
        intent_router: IntentRouter | None = None,
        auto_confirm: bool = False,
        stream_progress: bool = True,
    ):
        self.model = model
        self.tool_executor = tool_executor
        self.workspace = workspace
        self.intent_router = intent_router or IntentRouter(model)
        self.auto_confirm = auto_confirm
        self.stream_progress = stream_progress
        
        # Shared state
        self.conversation_history: list[dict] = []
        self.session: SessionContext | None = None
        self.memory: PersistentMemory | None = None
        
        # Execution state
        self._state = LoopState.IDLE
        self._pending_input: asyncio.Queue[str] = asyncio.Queue()
        self._current_agent: Agent | None = None
        self._cancel_requested = False
    
    @property
    def is_executing(self) -> bool:
        """True if agent is currently executing tasks."""
        return self._state in (LoopState.PLANNING, LoopState.EXECUTING)
    
    def request_cancel(self) -> None:
        """Request graceful cancellation of current execution."""
        self._cancel_requested = True
    
    async def run(self) -> AsyncIterator[str | ChatCheckpoint | AgentEvent]:
        """Main loop - yields responses, checkpoints, and optionally progress events.
        
        Usage:
            gen = loop.run()
            await gen.asend(None)  # Initialize
            
            while True:
                result = await gen.asend(user_input)
                if isinstance(result, ChatCheckpoint):
                    response = get_user_choice(result)
                    result = await gen.asend(response)
                elif isinstance(result, AgentEvent):
                    display_progress(result)
                else:
                    display_response(result)
        
        Yields:
            str: Conversational response
            ChatCheckpoint: User decision point
            AgentEvent: Progress event (if stream_progress=True)
        
        Raises:
            GeneratorExit: On aclose() call
        """
        # Initialize session and memory
        self.session = SessionContext.build(self.workspace, "", None)
        self.memory = PersistentMemory.load(self.workspace)
        self._state = LoopState.IDLE
        
        try:
            while True:
                # Get user input
                user_input = yield  # Caller sends input via .asend()
                
                if user_input is None:
                    break
                
                # Handle abort request
                if self._cancel_requested:
                    self._cancel_requested = False
                    self._state = LoopState.IDLE
                    yield "Execution cancelled."
                    continue
                
                # Add to conversation history
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input,
                })
                
                # Handle input during execution (interruption)
                if self.is_executing:
                    await self._pending_input.put(user_input)
                    continue
                
                # Classify intent
                self._state = LoopState.CLASSIFYING
                classification = await self.intent_router.classify(
                    user_input,
                    context=self._get_conversation_context(),
                )
                
                # Route based on intent
                if classification.intent == Intent.COMMAND:
                    response = await self._handle_command(user_input)
                    self._state = LoopState.IDLE
                    yield response
                    
                elif classification.intent == Intent.TASK:
                    # Transition to agent mode
                    async for event in self._execute_goal(classification.task_description):
                        yield event
                    self._state = LoopState.IDLE
                        
                else:  # CONVERSATION
                    self._state = LoopState.CONVERSING
                    response = await self._generate_response(user_input)
                    self._state = LoopState.IDLE
                    yield response
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response,
                    })
                    
        except GeneratorExit:
            # Graceful shutdown via aclose()
            self._state = LoopState.IDLE
            if self.memory:
                self.memory.sync()
        except Exception as e:
            self._state = LoopState.ERROR
            yield ChatCheckpoint(
                type=ChatCheckpointType.FAILURE,
                message=f"Unexpected error: {e}",
                error=str(e),
                recovery_options=("retry", "abort"),
                default="abort",
            )
    
    async def _execute_goal(self, goal: str) -> AsyncIterator[str | ChatCheckpoint | AgentEvent]:
        """Execute a goal with checkpoints and optional progress streaming.
        
        Flow:
            1. PLANNING: Generate plan via agent.plan()
            2. CONFIRMING: Yield ChatCheckpoint for user approval (unless auto_confirm)
            3. EXECUTING: Run agent.run(), streaming AgentEvents if stream_progress=True
            4. Handle interruptions, failures, completion via ChatCheckpoints
        
        Tool Calling:
            During execution, the agent uses AgentLoop with native tool calling.
            This is handled internally by Agent.run() — the unified loop does not
            call tools directly. Chat mode uses the existing _generate_with_tools
            pattern from cli/chat.py for simple tool loops.
        """
        self._state = LoopState.PLANNING
        self._current_agent = Agent(
            model=self.model,
            tool_executor=self.tool_executor,
            cwd=self.workspace,
            stream_inference=self.stream_progress,
        )
        
        try:
            # Update session with goal
            self.session = SessionContext.build(self.workspace, goal, None)
            
            # Plan first (stream planning events if enabled)
            plan_data = None
            async for event in self._current_agent.plan(self.session, self.memory):
                if self.stream_progress:
                    yield event  # Stream planning progress to UI
                if event.type == EventType.PLAN_WINNER:
                    plan_data = event.data
            
            if not plan_data:
                yield "I couldn't create a plan for that goal."
                return
            
            # Checkpoint: Confirmation (links to agent's PLAN_COMPLETE phase)
            self._state = LoopState.CONFIRMING
            if not self.auto_confirm:
                checkpoint = ChatCheckpoint(
                    type=ChatCheckpointType.CONFIRMATION,
                    message=self._format_plan_summary(plan_data),
                    options=("Y", "n", "edit"),
                    default="Y",
                    agent_checkpoint_id=f"plan-{self.session.session_id}",
                )
                response = yield checkpoint
                
                if response.abort:
                    yield "Cancelled."
                    return
                
                if not response.proceed:
                    yield "Okay, let me know if you'd like to try a different approach."
                    return
            
            # Execute with checkpoint handling
            self._state = LoopState.EXECUTING
            async for event in self._current_agent.run(self.session, self.memory):
                # Check for cancellation
                if self._cancel_requested:
                    self._cancel_requested = False
                    yield ChatCheckpoint(
                        type=ChatCheckpointType.COMPLETION,
                        message="Execution cancelled by user",
                        summary=f"Completed {len(self._current_agent._task_graph.completed_ids)} tasks before cancel",
                    )
                    return
                
                # Check for pending user input (interruption)
                if not self._pending_input.empty():
                    user_input = await self._pending_input.get()
                    self._state = LoopState.INTERRUPTED
                    
                    # Pause and handle
                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.INTERRUPTION,
                        message=f"You said: {user_input}",
                        options=("respond", "continue", "abort"),
                        default="respond",
                    )
                    response = yield checkpoint
                    
                    if response.abort:
                        yield "Execution aborted."
                        return
                    
                    if response.choice == "respond":
                        # Answer the question with execution context
                        answer = await self._generate_response(
                            user_input,
                            execution_context=event.data,
                        )
                        yield answer
                    
                    self._state = LoopState.EXECUTING
                
                # Stream progress events to UI
                if self.stream_progress and event.type in (
                    EventType.TASK_START,
                    EventType.TASK_COMPLETE,
                    EventType.MODEL_TOKENS,
                    EventType.GATE_START,
                    EventType.GATE_PASS,
                ):
                    yield event
                
                # Handle agent events that require user interaction
                if event.type == EventType.GATE_FAIL:
                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.FAILURE,
                        message="Validation failed",
                        error=event.data.get("error_message"),
                        recovery_options=("auto-fix", "skip", "manual", "retry", "abort"),
                        default="auto-fix",
                    )
                    response = yield checkpoint
                    
                    if response.abort:
                        yield "Execution aborted due to validation failure."
                        return
                    
                    # Agent handles auto-fix internally via Compound Eye
                    # Other choices recorded for the agent to handle
                    
                elif event.type == EventType.TASK_COMPLETE and not self.stream_progress:
                    # Yield progress update (only if not streaming all events)
                    yield self._format_task_complete(event.data)
                    
                elif event.type == EventType.COMPLETE:
                    # Checkpoint: Completion
                    self._state = LoopState.COMPLETED
                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.COMPLETION,
                        message="Execution complete",
                        summary=event.data.get("summary"),
                        files_changed=tuple(event.data.get("files", [])),
                    )
                    yield checkpoint
                    
                    # Add completion to conversation
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": f"Done! {event.data.get('summary', '')}",
                    })
                    
        except Exception as e:
            self._state = LoopState.ERROR
            yield ChatCheckpoint(
                type=ChatCheckpointType.FAILURE,
                message=f"Execution error: {e}",
                error=str(e),
                recovery_options=("retry", "abort"),
                default="abort",
            )
        finally:
            self._current_agent = None
    
    async def _generate_response(
        self,
        user_input: str,
        execution_context: dict | None = None,
    ) -> str:
        """Generate conversational response."""
        
        messages = self._build_messages(user_input)
        
        if execution_context:
            # Add execution context for mid-execution questions
            messages.insert(-1, {
                "role": "system",
                "content": f"Current execution context: {execution_context}",
            })
        
        response_parts = []
        async for chunk in self.model.generate_stream(tuple(messages)):
            response_parts.append(chunk)
        
        return "".join(response_parts)
    
    def _build_messages(self, user_input: str) -> list[dict]:
        """Build message list with conversation history."""
        
        messages = [{"role": "system", "content": self._system_prompt}]
        
        # Add recent conversation history (last 10 turns)
        messages.extend(self.conversation_history[-20:])
        
        # Add current input if not already there
        if not messages or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def _get_conversation_context(self) -> str:
        """Get recent conversation as context string."""
        recent = self.conversation_history[-6:]
        return "\n".join(
            f"{m['role']}: {m['content'][:200]}"
            for m in recent
        )
    
    def _format_plan_summary(self, plan_data: dict) -> str:
        """Format plan for confirmation checkpoint."""
        tasks = plan_data.get("task_list", [])
        gates = plan_data.get("gate_list", [])
        
        lines = [
            f"★ Plan ready ({len(tasks)} tasks, {len(gates)} validation gates)",
            "",
        ]
        
        for i, task in enumerate(tasks[:10], 1):
            lines.append(f"   {i}. {task['description'][:60]}")
        
        if len(tasks) > 10:
            lines.append(f"   ... and {len(tasks) - 10} more")
        
        lines.append("")
        lines.append("Proceed?")
        
        return "\n".join(lines)
    
    def _format_task_complete(self, data: dict) -> str:
        """Format task completion message."""
        task_num = data.get("task_index", 0) + 1
        total = data.get("total_tasks", 0)
        desc = data.get("description", "")
        
        return f"[{task_num}/{total}] ✓ {desc}"
    
    @property
    def _system_prompt(self) -> str:
        return """You are Sunwell, an AI assistant for software development.

You can both:
1. Answer questions and have conversations
2. Execute coding tasks (create files, modify code, etc.)

When the user asks you to DO something (create, add, fix, refactor), 
you'll transition to execution mode with a plan.

When the user asks questions, explain or discuss freely.

Current workspace: {workspace}""".format(workspace=self.workspace)
    
    async def _handle_command(self, command: str) -> str:
        """Handle /slash commands."""
        # Delegate to existing command handlers
        # (Same as current chat.py implementation)
        return f"Command: {command}"
```

### Integration with CLI

Update `sunwell chat` to use the unified loop.

```python
# src/sunwell/cli/chat.py (updated)

@click.command()
@click.option("--auto-confirm", is_flag=True, help="Skip confirmation checkpoints")
@click.option("--stream-progress/--no-stream-progress", default=True, 
              help="Stream task progress during execution")
# ... other options
def chat(..., auto_confirm: bool, stream_progress: bool):
    """Interactive chat with seamless agent execution."""
    
    # ... existing setup code ...
    
    # Use UnifiedChatLoop instead of _chat_loop
    from sunwell.chat.unified import UnifiedChatLoop
    
    loop = UnifiedChatLoop(
        model=llm,
        tool_executor=tool_executor,
        workspace=Path.cwd(),
        auto_confirm=auto_confirm,
        stream_progress=stream_progress,
    )
    
    asyncio.run(_run_unified_loop(loop, console))


async def _run_unified_loop(loop: UnifiedChatLoop, console) -> None:
    """Run the unified loop with Rich console.
    
    Handles:
        - User input collection
        - ChatCheckpoint rendering and response collection
        - AgentEvent progress display
        - Graceful shutdown via Ctrl+C or /quit
    """
    from sunwell.agent.events import AgentEvent, EventType
    from sunwell.chat.checkpoint import ChatCheckpoint, ChatCheckpointType
    
    gen = loop.run()
    
    try:
        await gen.asend(None)  # Initialize
        
        while True:
            try:
                # Check if we're executing (allow concurrent input)
                if loop.is_executing:
                    # Non-blocking check for input during execution
                    console.print("[dim]Type to interrupt execution...[/dim]")
                
                user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("/quit", "/exit"):
                    break
                
                if user_input.lower() == "/abort" and loop.is_executing:
                    loop.request_cancel()
                    continue
                
                # Send input and process all responses
                result = await gen.asend(user_input)
                
                while result is not None:
                    if isinstance(result, ChatCheckpoint):
                        # Handle checkpoint UI
                        response = await _handle_checkpoint(result, console)
                        result = await gen.asend(response)
                        
                    elif isinstance(result, AgentEvent):
                        # Render progress event
                        _render_agent_event(result, console)
                        try:
                            result = await gen.asend(None)
                        except StopAsyncIteration:
                            break
                            
                    else:
                        # Regular text response
                        console.print(Markdown(result))
                        try:
                            result = await gen.asend(None)
                        except StopAsyncIteration:
                            break
                            
            except KeyboardInterrupt:
                if loop.is_executing:
                    console.print("\n[yellow]Cancelling execution...[/yellow]")
                    loop.request_cancel()
                else:
                    console.print("\n[yellow]Interrupted[/yellow]")
                    break
                    
    finally:
        # Graceful shutdown
        await gen.aclose()
        console.print("[dim]Session saved.[/dim]")


def _render_agent_event(event: AgentEvent, console) -> None:
    """Render an AgentEvent as progress output."""
    
    if event.type == EventType.TASK_START:
        task_id = event.data.get("task_id", "")
        desc = event.data.get("description", "")[:50]
        console.print(f"[cyan]✦[/cyan] {desc}")
        
    elif event.type == EventType.TASK_COMPLETE:
        task_id = event.data.get("task_id", "")
        duration = event.data.get("duration_ms", 0)
        console.print(f"[green]✓[/green] Complete ({duration}ms)")
        
    elif event.type == EventType.GATE_START:
        gate_type = event.data.get("gate_type", "")
        console.print(f"[dim][Gate: {gate_type}][/dim]", end=" ")
        
    elif event.type == EventType.GATE_PASS:
        console.print("[green]✓[/green]")
        
    elif event.type == EventType.MODEL_TOKENS:
        # Show token counter (update in place)
        count = event.data.get("token_count", 0)
        console.print(f"\r[dim]{count} tokens...[/dim]", end="")


async def _handle_checkpoint(checkpoint: ChatCheckpoint, console) -> CheckpointResponse:
    """Render checkpoint and get user response."""
    from sunwell.chat.checkpoint import CheckpointResponse
    
    if checkpoint.type == ChatCheckpointType.CONFIRMATION:
        console.print(f"\n[bold]{checkpoint.message}[/bold]")
        console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        choice = console.input(f"[{checkpoint.default}]: ").strip() or checkpoint.default
        return CheckpointResponse(choice)
    
    elif checkpoint.type == ChatCheckpointType.FAILURE:
        console.print(f"\n[red]⚠️ {checkpoint.message}[/red]")
        if checkpoint.error:
            console.print(f"[dim]{checkpoint.error}[/dim]")
        console.print(f"Options: {', '.join(checkpoint.recovery_options)}")
        choice = console.input(f"[{checkpoint.default}]: ").strip() or checkpoint.default
        return CheckpointResponse(choice)
    
    elif checkpoint.type == ChatCheckpointType.COMPLETION:
        console.print(f"\n[green]✓ {checkpoint.message}[/green]")
        if checkpoint.summary:
            console.print(checkpoint.summary)
        if checkpoint.files_changed:
            console.print(f"[dim]Files: {', '.join(checkpoint.files_changed)}[/dim]")
        return CheckpointResponse("continue")
    
    elif checkpoint.type == ChatCheckpointType.INTERRUPTION:
        console.print(f"\n[yellow]⏸ Execution paused[/yellow]")
        console.print(checkpoint.message)
        choice = console.input("[respond/continue/abort]: ").strip() or "respond"
        return CheckpointResponse(choice)
    
    return CheckpointResponse("continue")
```

---

## 🔀 Alternatives Considered

### Alternative A: Keep Separate Modes (Status Quo)

**Approach**: `sunwell chat` for conversation, `sunwell "goal"` for execution.

**Pros**:
- No development effort
- Clear separation of concerns

**Cons**:
- Poor UX - users expect unified experience
- Context lost between modes
- Doesn't match Claude Code / Cursor patterns

**Decision**: Rejected — UX is unacceptably fragmented.

### Alternative B: Make Agent Fully Conversational

**Approach**: Agent responds conversationally, also does tasks.

**Pros**:
- Single mode
- Simpler architecture

**Cons**:
- Loses structured planning benefits
- Hard to implement checkpoints
- Validation gates don't fit conversational model

**Decision**: Rejected — structured execution is valuable.

### Alternative C: Explicit Mode Toggle

**Approach**: User types `/agent` to enter agent mode, `/chat` to exit.

**Pros**:
- Explicit user control
- Simple implementation

**Cons**:
- Extra friction
- Users must know command
- Still feels like two modes

**Decision**: Partially adopted — auto-detect preferred, but `/agent` can force agent mode.

---

## ⚠️ Risks & Edge Cases

### Risk 1: Async Generator Complexity

**Problem**: The `yield` / `asend()` pattern is non-trivial. Edge cases:
- Caller forgets to initialize with `asend(None)`
- Generator completes unexpectedly during checkpoint
- Concurrent input during execution causes race conditions

**Mitigation**:
- Added `LoopState` enum to track state machine explicitly
- Added comprehensive try/except/finally in `run()`
- Queue-based handling for concurrent input (`_pending_input`)
- Documented usage pattern with examples

### Risk 2: Intent Classification Errors

**Problem**: Heuristic classification may misroute:
- "Fix the typo in README" → TASK (correct)
- "Can you fix the typo in README?" → CONVERSATION (incorrect — should be TASK)
- "Update" → Ambiguous

**Mitigation**:
- LLM fallback for ambiguous cases (score difference < 0.3)
- Added `/agent [goal]` force command for explicit task execution
- Added `/chat` force command to stay in conversation mode
- Confidence threshold configurable (default 0.7)

### Risk 3: Tool Calling Mode Confusion

**Problem**: Chat mode uses `_generate_with_tools` (simple loop), Agent mode uses `AgentLoop` (with validation). Which is used when?

**Mitigation**:
- **Chat mode (CONVERSATION intent)**: Uses `_generate_with_tools` for simple one-off tool calls
- **Agent mode (TASK intent)**: Uses full `Agent.run()` with `AgentLoop`, validation gates, Compound Eye
- Documented clearly in `_execute_goal()` docstring

### Risk 4: Long-Running Execution Blocking

**Problem**: 5+ minute executions block user interaction.

**Mitigation**:
- Interrupt queue allows user input during execution
- `request_cancel()` for graceful cancellation via Ctrl+C or `/abort`
- Streaming progress events keep UI responsive
- Agent checkpoints saved periodically for crash recovery

### Risk 5: Checkpoint State Divergence

**Problem**: `ChatCheckpoint` (user-facing) and `AgentCheckpoint` (internal) could diverge.

**Mitigation**:
- `ChatCheckpoint.agent_checkpoint_id` links to internal state
- Clear documentation distinguishing the two concepts
- Both saved atomically at phase boundaries

### Edge Case Matrix

| Scenario | Handling |
|----------|----------|
| User types during planning | Queued until CONFIRMING state |
| User types during execution | INTERRUPTION checkpoint |
| User Ctrl+C during execution | `request_cancel()` → graceful stop |
| User Ctrl+C during conversation | Exit loop normally |
| Gate fails, user chooses "manual" | Exit execution, return to conversation |
| Network error during model call | FAILURE checkpoint with retry option |
| Empty user input | Skip (continue prompt) |
| `/` command during execution | Not processed until execution completes |

---

## 📊 Feature Matrix

| Feature | Current Chat | Current Agent | Unified (Proposed) |
|---------|--------------|---------------|-------------------|
| Conversation | ✅ | ❌ | ✅ |
| Harmonic planning | ❌ | ✅ | ✅ |
| Validation gates | ❌ | ✅ | ✅ |
| Auto-fix (Compound Eye) | ❌ | ✅ | ✅ |
| User checkpoints | ❌ | ❌ | ✅ |
| Mid-execution questions | ❌ | ❌ | ✅ |
| Streaming progress | ❌ | ✅ | ✅ |
| Graceful cancellation | ❌ | ❌ | ✅ |
| Shared memory | ✅ | ✅ | ✅ |
| Intent detection | ❌ | N/A | ✅ |
| Seamless transitions | ❌ | ❌ | ✅ |
| Crash recovery | ❌ | ✅ (AgentCheckpoint) | ✅ (linked) |

---

## ✅ Acceptance Criteria

### Must Have
- [ ] Intent router classifies conversation vs task with >90% accuracy on test set
- [ ] Tasks trigger full Agent pipeline (planning, gates, execution)
- [ ] `ChatCheckpoint.CONFIRMATION` before execution starts
- [ ] `ChatCheckpoint.FAILURE` on gate failures with recovery options
- [ ] `ChatCheckpoint.COMPLETION` with summary and files changed
- [ ] Conversation history persists across mode transitions
- [ ] Graceful error handling (no uncaught exceptions crash the loop)

### Should Have
- [ ] Mid-execution interruption via `ChatCheckpoint.INTERRUPTION`
- [ ] Streaming progress events (`AgentEvent`) during execution
- [ ] Cancel execution gracefully via `/abort` or Ctrl+C
- [ ] LLM fallback for ambiguous intent classification (score diff < 0.3)
- [ ] `/agent [goal]` force command for explicit task execution
- [ ] `/chat` force command to prevent task detection

### Nice to Have
- [ ] Intent confidence shown to user with "Did you mean to execute this?" prompt
- [ ] Add task to queue during execution (via RFC-134)
- [ ] Token counter display during generation
- [ ] Resume from `AgentCheckpoint` on restart

---

## 🧪 Testing Strategy

### Unit Tests

```python
# tests/test_intent_router.py

import pytest
from sunwell.chat.intent import IntentRouter, Intent


@pytest.fixture
def router():
    return IntentRouter(model=None, threshold=0.7)


@pytest.mark.parametrize("input_text,expected", [
    # Clear TASK intents
    ("Add user authentication", Intent.TASK),
    ("Create a REST API", Intent.TASK),
    ("Fix the bug in auth.py", Intent.TASK),
    ("Refactor the database layer", Intent.TASK),
    ("Implement logging", Intent.TASK),
    ("Delete the old migration files", Intent.TASK),
    
    # Clear CONVERSATION intents
    ("What does this function do?", Intent.CONVERSATION),
    ("How does authentication work?", Intent.CONVERSATION),
    ("Can you explain the architecture?", Intent.CONVERSATION),
    ("Why is this failing?", Intent.CONVERSATION),
    ("Tell me about the database schema", Intent.CONVERSATION),
    
    # Commands
    ("/help", Intent.COMMAND),
    ("::research", Intent.COMMAND),
    
    # Edge cases (these require LLM fallback ideally)
    # ("Can you fix the typo?", Intent.TASK),  # Ambiguous - question form but task intent
])
async def test_intent_classification(router, input_text, expected):
    result = await router.classify(input_text)
    assert result.intent == expected


async def test_intent_confidence_bounds(router):
    """Confidence should be between 0 and 1."""
    result = await router.classify("Add user authentication")
    assert 0.0 <= result.confidence <= 1.0


async def test_intent_with_context(router):
    """Context should influence classification."""
    # Without context: could be either
    result1 = await router.classify("Update it")
    
    # With context: clearly a task
    result2 = await router.classify(
        "Update it",
        context="user: I have a bug in auth.py\nassistant: I see the issue..."
    )
    # Context should increase task confidence
    assert result2.confidence >= result1.confidence or result2.intent == Intent.TASK
```

### Integration Tests

```python
# tests/test_unified_chat.py

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from sunwell.chat.unified import UnifiedChatLoop, LoopState
from sunwell.chat.checkpoint import ChatCheckpoint, ChatCheckpointType, CheckpointResponse


@pytest.fixture
def mock_model():
    model = AsyncMock()
    model.generate_stream = AsyncMock(return_value=iter(["Hello, ", "world!"]))
    return model


@pytest.fixture
def mock_executor():
    return MagicMock()


async def test_conversation_response(mock_model, mock_executor):
    """Test that questions get conversational responses."""
    loop = UnifiedChatLoop(mock_model, mock_executor, Path("/tmp"))
    
    gen = loop.run()
    await gen.asend(None)  # Initialize
    
    result = await gen.asend("What is Python?")
    
    assert isinstance(result, str)
    assert loop._state == LoopState.IDLE


async def test_task_triggers_checkpoint(mock_model, mock_executor):
    """Test that tasks trigger confirmation checkpoint."""
    # Mock the agent planning
    mock_model.generate = AsyncMock(return_value=MagicMock(
        text="Plan: 1. Create file",
        tool_calls=[],
    ))
    
    loop = UnifiedChatLoop(mock_model, mock_executor, Path("/tmp"))
    
    gen = loop.run()
    await gen.asend(None)  # Initialize
    
    result = await gen.asend("Create a hello world script")
    
    # Should get planning events first, then checkpoint
    while not isinstance(result, ChatCheckpoint):
        result = await gen.asend(None)
    
    assert isinstance(result, ChatCheckpoint)
    assert result.type == ChatCheckpointType.CONFIRMATION


async def test_cancellation_during_execution(mock_model, mock_executor):
    """Test that cancellation works during execution."""
    loop = UnifiedChatLoop(mock_model, mock_executor, Path("/tmp"), auto_confirm=True)
    
    gen = loop.run()
    await gen.asend(None)
    
    # Start a task
    result = await gen.asend("Add authentication")
    
    # Request cancellation
    loop.request_cancel()
    
    # Next yield should acknowledge cancellation
    while not isinstance(result, (str, ChatCheckpoint)):
        result = await gen.asend(None)
    
    # Loop should return to idle
    assert loop._state in (LoopState.IDLE, LoopState.COMPLETED)


async def test_graceful_shutdown(mock_model, mock_executor):
    """Test that aclose() properly shuts down the loop."""
    loop = UnifiedChatLoop(mock_model, mock_executor, Path("/tmp"))
    
    gen = loop.run()
    await gen.asend(None)
    
    # Close the generator
    await gen.aclose()
    
    assert loop._state == LoopState.IDLE
```

---

## 🗓️ Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | IntentRouter with heuristics + LLM fallback | 6 hours |
| **2** | ChatCheckpoint types and CheckpointResponse | 2 hours |
| **3** | UnifiedChatLoop with LoopState machine | 8 hours |
| **4** | Integrate with Agent.run() + event streaming | 8 hours |
| **5** | Checkpoint UI in CLI with progress rendering | 6 hours |
| **6** | Mid-execution interruption + cancellation | 6 hours |
| **7** | Force commands (/agent, /chat, /abort) | 2 hours |
| **8** | Testing + edge cases | 8 hours |
| **9** | Documentation | 2 hours |

**Total estimated effort**: 48 hours (~6 days)

---

## 🔗 Dependencies

### Verified Dependencies

| Dependency | Status | Location | What We Use |
|------------|--------|----------|-------------|
| **RFC-128 (Session Checkpoints)** | ✅ Verified | `naaru/checkpoint.py` | `AgentCheckpoint`, `CheckpointPhase` for crash recovery |
| **RFC-134 (Task Queue Interactivity)** | ✅ Verified | `agent/events.py` | Events for mid-execution task queue updates |
| **RFC-110 (Agent Simplification)** | ✅ Verified | `agent/core.py` | Unified `Agent.run()` interface |

### Module Dependencies

- **`agent/core.py`**: Agent.run() already yields `AgentEvent` — no changes needed
- **`context/session.py`**: `SessionContext.build()` — no changes needed
- **`memory/persistent.py`**: `PersistentMemory.load()` — no changes needed
- **`agent/events.py`**: May add new event types for chat-agent transitions

### New Modules

- **`chat/intent.py`**: IntentRouter (new)
- **`chat/checkpoint.py`**: ChatCheckpoint, ChatCheckpointType (new)
- **`chat/unified.py`**: UnifiedChatLoop (new)

---

## 📚 References

- `src/sunwell/cli/chat.py` — Current chat implementation
- `src/sunwell/agent/core.py` — Agent execution
- `src/sunwell/cli/main.py` — Goal execution entry point
- Claude Code UX patterns
- Cursor agent mode behavior
