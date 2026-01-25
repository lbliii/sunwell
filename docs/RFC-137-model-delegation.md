# RFC-137: Smart-to-Dumb Model Delegation

**Status**: Implemented  
**Created**: 2026-01-25  
**Author**: AI Assistant  
**Related**: RFC-134 (S-Tier Tool Calling), RFC-042 (Budget-Aware Technique Selection)

---

## Problem

Large tasks (multi-file generation, bulk refactoring, API scaffolding) are expensive when using smart models throughout. The expertise needed is front-loaded—understanding the task, identifying patterns, and setting constraints—but execution is routine code generation.

**Cost Example**:
- Task: "Generate CRUD endpoints for 5 entities"
- With Opus throughout: ~15,000 tokens × $15/M = $0.225
- With delegation: 1,000 tokens Opus + 14,000 tokens Haiku × $0.25/M = $0.019
- **Savings: ~92%**

## Solution

"Think once, generate many" pattern using `EphemeralLens`:

1. **Smart model** (Opus, o1, GPT-4o) analyzes task and creates `EphemeralLens`
2. **Cheap model** (Haiku, 4o-mini, Gemma) executes using lens guidance
3. Same lens can be reused across parallel workers (Agent Constellation)

The `EphemeralLens` captures:
- **Heuristics**: Domain-specific guidelines for this task
- **Patterns**: Code patterns to follow
- **Anti-patterns**: Things to avoid
- **Constraints**: Hard requirements
- **Examples**: Style reference snippets

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       AgentLoop.run()                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ should_use_     │
                    │ delegation()?   │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ NO                          │ YES
              ▼                             ▼
    ┌─────────────────┐          ┌─────────────────────────┐
    │ Normal execution│          │ create_ephemeral_lens() │
    │ with main model │          │ using smart_model       │
    └─────────────────┘          └───────────┬─────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────────┐
                                  │ Execute with            │
                                  │ delegation_model + lens │
                                  └─────────────────────────┘
```

## Integration Points

### 1. LoopConfig Additions

```python
@dataclass(frozen=True, slots=True)
class LoopConfig:
    # ... existing fields ...
    
    # RFC-137: Smart-to-dumb model delegation
    enable_delegation: bool = False
    """Enable smart-to-dumb model delegation for cost optimization."""

    delegation_threshold_tokens: int = 2000
    """Minimum expected output tokens to trigger delegation."""
```

### 2. RunOptions Additions

```python
@dataclass(frozen=True, slots=True)
class RunOptions:
    # ... existing fields ...
    
    enable_delegation: bool = False
    """Enable smart-to-dumb model delegation."""
    
    delegation_threshold_tokens: int = 2000
    """Minimum estimated output tokens to trigger delegation."""
    
    smart_model: ModelProtocol | str | None = None
    """Smart model for lens creation. Can be instance or name (resolved via registry)."""

    delegation_model: ModelProtocol | str | None = None
    """Cheap model for execution. Can be instance or name (resolved via registry)."""
```

### 3. Agent Class Additions

```python
@dataclass(slots=True)
class Agent:
    # ... existing fields ...
    
    # RFC-137: Model delegation
    smart_model: ModelProtocol | None = None
    """Smart model for ephemeral lens creation."""

    delegation_model: ModelProtocol | None = None
    """Cheap model for delegated task execution."""
```

### 4. ModelRegistry (NEW)

Thread-safe registry for model instance management:

```python
from sunwell.models.registry import ModelRegistry, get_registry, resolve_model

# Register models
registry = get_registry()
registry.register("opus", opus_model)
registry.register("haiku", haiku_model)

# Retrieve by name
smart = registry.get("opus")
cheap = registry.get("haiku")

# Resolve model references (string or instance)
model = resolve_model("opus")  # Returns instance from registry
model = resolve_model(opus_model)  # Pass-through for instances
```

**Built-in aliases**:
- `anthropic-smart` → `claude-3-opus-20240229`
- `anthropic-cheap` → `claude-3-haiku-20240307`
- `openai-smart` → `gpt-4o`
- `openai-cheap` → `gpt-4o-mini`

### 5. New Events

| Event | Description | Data Fields |
|-------|-------------|-------------|
| `DELEGATION_STARTED` | Smart-to-dumb delegation initiated | `task_description`, `smart_model`, `delegation_model`, `reason` |
| `EPHEMERAL_LENS_CREATED` | EphemeralLens generated | `task_scope`, `heuristics_count`, `patterns_count`, `generated_by` |

### 6. Decision Logic

Delegation triggers when any of:
- `estimated_tokens > delegation_threshold_tokens` (default: 2000)
- `budget_remaining < estimated_tokens * 3` (low budget)
- Task involves multiple files/endpoints/components

### 7. Wire-up Flow

```
SessionContext.build(options=RunOptions(...))
    ↓
Agent.run(session, memory)
    ↓
Agent stores session.options as _current_options
    ↓
Agent._execute_task_with_tools()
    ↓
LoopConfig gets enable_delegation from _current_options
    ↓
Models resolved: Agent fields → RunOptions → Registry
    ↓
AgentLoop created with smart_model, delegation_model
    ↓
AgentLoop.run() checks delegation and routes accordingly
```

## Existing Implementation

The `EphemeralLens` dataclass already exists in `sunwell/core/lens.py`:

```python
@dataclass(frozen=True, slots=True)
class EphemeralLens:
    """A dynamically-generated lens for a specific task."""
    heuristics: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    anti_patterns: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    task_scope: str = ""
    target_files: tuple[str, ...] = ()
    generated_by: str = ""
    generation_prompt: str = ""

    def to_context(self) -> str:
        """Convert to context string for injection into prompts."""
        # ... implementation
```

The generator functions exist in `sunwell/agent/ephemeral_lens.py`:
- `create_ephemeral_lens()`: Creates lens using smart model
- `should_use_delegation()`: Decides when to use delegation

**Integration complete**: `AgentLoop._run_with_delegation()` orchestrates the full flow.

## Cost Model

| Component | Tokens | With Opus | With Haiku |
|-----------|--------|-----------|------------|
| Lens creation | ~500-1000 | $0.008 | - |
| Task execution | ~5000-15000 | - | $0.003 |
| **Total** | - | $0.008 + $0.003 = $0.011 | - |
| **Baseline (all Opus)** | - | $0.225 | - |

**Break-even point**: ~3000 output tokens

## Migration

This is additive—existing code continues to work. To opt-in:

### Option 1: Via RunOptions (Recommended)

```python
from sunwell.agent.request import RunOptions
from sunwell.context.session import SessionContext

# Enable delegation with model names
options = RunOptions(
    enable_delegation=True,
    smart_model="claude-3-opus-20240229",
    delegation_model="claude-3-haiku-20240307",
)

# Build session with options
session = SessionContext.build(workspace, goal, options=options)

# Run agent
async for event in agent.run(session, memory):
    print(event)
```

### Option 2: Via Agent Constructor

```python
from sunwell.agent import Agent

# Configure models at construction
agent = Agent(
    model=primary_model,
    smart_model=opus_model,  # ModelProtocol instance
    delegation_model=haiku_model,
    tool_executor=executor,
)

# Enable delegation via options
options = RunOptions(enable_delegation=True)
session = SessionContext.build(workspace, goal, options=options)

async for event in agent.run(session, memory):
    print(event)
```

### Option 3: Via ModelRegistry

```python
from sunwell.models.registry import get_registry

# Pre-register models
registry = get_registry()
registry.register("opus", opus_model)
registry.register("haiku", haiku_model)

# Use names in options
options = RunOptions(
    enable_delegation=True,
    smart_model="opus",  # Resolved from registry
    delegation_model="haiku",
)
```

### Option 4: Direct AgentLoop (Low-level)

```python
from sunwell.agent.loop import AgentLoop, LoopConfig

loop = AgentLoop(
    model=primary,
    executor=executor,
    config=LoopConfig(enable_delegation=True),
    smart_model=opus_model,
    delegation_model=haiku_model,
)

async for event in loop.run(task, tools, system_prompt):
    print(event)
```

## Testing Strategy

1. **Unit tests**: `should_use_delegation()` returns correct decisions
2. **Integration tests**: `create_ephemeral_lens()` produces valid lenses
3. **E2E tests**: Full delegation flow with mock models
4. **Cost tests**: Verify delegation actually reduces token usage

## Future Work

- **Classifier-based delegation**: Use small model to decide delegation vs. direct
- **Lens caching**: Reuse lenses for similar tasks
- **Parallel delegation**: Same lens across multiple cheap workers
- **Quality feedback loop**: Track when delegation produces lower quality
