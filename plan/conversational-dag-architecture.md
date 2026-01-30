# RFC: Conversational DAG Architecture

**Status**: Draft  
**Date**: 2026-01-30  
**Supersedes**: RFC-135 (Unified Chat-Agent Loop intent classification)

---

## Summary

Redesign Sunwell's interaction model around a DAG-based intent classifier where **all interactions are conversational at the root**. Actions (reading, writing, planning) are branches of the conversation tree, not separate modes. This replaces the disabled binary classifier with a more nuanced, permission-aware system.

---

## Motivation

### The Problem

The binary "chat vs task" classification (RFC-135) is currently disabled due to tool-calling integration issues. This creates UX problems:

1. Users can't reliably ask questions without triggering unwanted file modifications
2. The system either always uses tools or never uses them
3. No middle ground for "analyze but don't modify" workflows

### The Wrong Abstraction

Binary classification is fundamentally flawed because:

- **Everything is conversational** - The agent is always responding in a conversation
- **Actions are a subset** - Writing code is just one possible outcome, not a separate mode
- **Permission is a spectrum** - Read-only analysis differs from destructive writes

### Competitive Analysis

| Tool | Intent Model | User Control |
|------|-------------|--------------|
| Claude Code | Implicit (smart but opaque) | None |
| Aider | Explicit 4 modes | Must switch manually |
| Codex CLI | Implicit | None |
| **Sunwell (proposed)** | Conversational DAG | Smart + explicit override |

---

## Design

### Core Insight

The question isn't "chat or task?" but "how deep into the action tree should we go?"

### The Conversation DAG

```
Conversation (root)
├── Understand (no tools)
│   ├── Clarify - Ask for more information
│   └── Explain - Explain a concept
├── Analyze (read-only tools)
│   ├── Review - Code review, feedback
│   └── Audit - Investigate, debug, trace
├── Plan (may lead to action)
│   ├── Design - Architecture decisions
│   └── Decompose - Break into tasks
└── Act (tools required)
    ├── Read - Search, list, grep
    └── Write - File modifications
        ├── Create - New files
        ├── Modify - Edit existing
        └── Delete - Remove files
```

### Node Types

```python
from enum import Enum

class IntentNode(Enum):
    """Nodes in the conversational intent DAG."""
    
    # Root - all interactions start here
    CONVERSATION = "conversation"
    
    # Understanding branch (no tools needed)
    UNDERSTAND = "understand"
    CLARIFY = "clarify"
    EXPLAIN = "explain"
    
    # Analysis branch (read-only tools)
    ANALYZE = "analyze"
    REVIEW = "review"
    AUDIT = "audit"
    
    # Planning branch (may lead to action)
    PLAN = "plan"
    DESIGN = "design"
    DECOMPOSE = "decompose"
    
    # Action branch (tools required)
    ACT = "act"
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
```

### Classification Output

Instead of binary `chat | task`, the classifier outputs a path:

```python
from dataclasses import dataclass
from sunwell.tools.core.types import ToolTrust

@dataclass(frozen=True, slots=True)
class IntentClassification:
    """Result of intent classification."""
    
    path: tuple[IntentNode, ...]
    """Path through DAG, e.g., (CONVERSATION, ACT, WRITE, MODIFY)"""
    
    confidence: float
    """Classification confidence (0.0-1.0)"""
    
    requires_approval: bool
    """True for write/delete nodes"""
    
    tool_scope: ToolTrust
    """Maps to existing trust levels"""
    
    reasoning: str
    """Why this path was chosen (for debugging/transparency)"""
```

### Permission Escalation

Depth in the tree correlates with permission requirements:

| Depth | Node Types | Permission Level | Approval |
|-------|------------|------------------|----------|
| 1 | Understand | None (chat only) | No |
| 1 | Analyze | Read-only tools | No |
| 2 | Plan | Read-only tools | No |
| 2 | Read | Read-only tools | No |
| 3 | Write | Write tools | Yes |
| 4 | Delete | Delete tools | Explicit |

### User Intervention

Users can navigate the tree explicitly:

1. **Prefix syntax**: `@explain how does auth work?` forces the Explain node
2. **Checkpoints**: Automatic approval at branch transitions (Plan→Act)
3. **Go up**: During diff preview, `[U]p` returns to Plan without applying

### Example Classifications

| User Input | Classified Path | Why |
|------------|-----------------|-----|
| "What does this function do?" | Conversation → Understand → Explain | Question about concept |
| "Review this PR" | Conversation → Analyze → Review | Analysis request |
| "Find all usages of AuthService" | Conversation → Act → Read | Needs search tools |
| "Add input validation to login" | Conversation → Act → Write → Modify | Needs to edit file |
| "Delete the legacy auth module" | Conversation → Act → Write → Delete | Destructive action |

---

## Implementation

### Phase 1: Intent Layer (P0)

Create new module `src/sunwell/agent/intent/`:

```
intent/
├── __init__.py          # Public API
├── dag.py               # IntentNode enum, DAG structure
├── classifier.py        # LLM-based path classification
└── permissions.py       # Node-to-ToolTrust mapping
```

**dag.py**:
- `IntentNode` enum (as shown above)
- `INTENT_DAG` - adjacency list defining valid paths
- `IntentClassification` dataclass
- `get_valid_children(node)` - returns valid next nodes
- `path_depth(path)` - returns depth in tree

**classifier.py**:
- `classify_intent(message, context) -> IntentClassification`
- Uses structured output from LLM
- Falls back to conservative (shallow) path on low confidence
- Caches classification for multi-turn conversations

**permissions.py**:
- `get_tool_scope(path) -> ToolTrust`
- `requires_approval(path) -> bool`
- `get_checkpoint_trigger(from_node, to_node) -> bool`

### Phase 2: Integration (P0)

Modify `src/sunwell/agent/chat/unified.py`:

```python
async def process_message(self, message: str) -> AsyncIterator[ChatResult]:
    # Classify intent
    classification = await self.intent_classifier.classify(
        message=message,
        context=self.context,
    )
    
    # Emit classification event
    yield IntentClassifiedEvent(
        path=classification.path,
        confidence=classification.confidence,
    )
    
    # Check for approval if needed
    if classification.requires_approval and not self.auto_confirm:
        response = yield ApprovalCheckpoint(
            message=f"This will {classification.path[-1].value} files. Proceed?",
            path=classification.path,
        )
        if not response.approved:
            # Move up the tree
            classification = classification.with_path(classification.path[:-1])
    
    # Execute based on path
    tool_scope = get_tool_scope(classification.path)
    # ... rest of execution
```

### Phase 3: User Override (P1)

Handle `@node` prefix in `unified_loop.py`:

```python
def parse_node_prefix(message: str) -> tuple[IntentNode | None, str]:
    """Extract @node prefix if present."""
    if message.startswith("@"):
        parts = message.split(" ", 1)
        prefix = parts[0][1:].lower()  # Remove @ and lowercase
        try:
            node = IntentNode(prefix)
            return node, parts[1] if len(parts) > 1 else ""
        except ValueError:
            pass
    return None, message
```

### Phase 4: Events and Hooks (P1)

Add new event types to `agent/hooks/types.py`:

```python
class HookEvent(Enum):
    # ... existing events ...
    
    # New DAG events
    INTENT_CLASSIFIED = "intent_classified"
    NODE_TRANSITION = "node_transition"
```

Update hooks config to support node transitions:

```toml
# .sunwell/hooks.toml
[hooks.on_node_transition]
from = "plan"
to = "act"
run = "./scripts/confirm-action.sh"
block_if_fails = true
```

---

## UI/UX Changes

### Progress Display

Show DAG path in progress visualization:

```
┌─ Path: Conversation → Act → Write ─────────────────┐
│ ✦ Analyzing context       [████████████] 100%      │
│ ✧ Implementing auth       [████████░░░░]  67%      │
│   └─ Writing tests        [██░░░░░░░░░░]  20%      │
├────────────────────────────────────────────────────│
│ Tokens: 4,523 │ Time: 12s │ Cost: $0.03            │
└────────────────────────────────────────────────────┘
```

### Diff Preview

Show path and offer "go up" option:

```
Path: Conversation → Act → Write → Modify

Proposed changes to src/auth/login.py:

  @@ -45,6 +45,8 @@
   def authenticate(user: str, password: str) -> bool:
  -    return check_password(user, password)
  +    if not validate_input(user, password):
  +        raise ValidationError("Invalid credentials format")
  +    return check_password(user, password)

[A]pply / [S]kip / [E]dit / [D]iff all / [U]p (back to Plan)
```

### Holy Light Theme Extensions

Add to `theme.py`:

```python
# DAG path display
"dag.node.current": "bold bright_yellow",
"dag.node.completed": "dim green",
"dag.node.pending": "dim white",
"dag.arrow": "holy.gold.dim",

# Diff colors
"holy.diff.add": "green",
"holy.diff.remove": "red",
"holy.diff.context": "dim white",
"holy.diff.hunk": "holy.gold",
```

---

## Migration

### From RFC-135

The existing `UnifiedChatLoop` intent classification is disabled. This RFC:

1. Removes the binary classifier
2. Adds the DAG-based classifier
3. Maintains backward compatibility with existing checkpoint system
4. Integrates with existing `ToolTrust` levels

### Backward Compatibility

- Existing tool trust levels map directly to DAG depth
- Checkpoint system unchanged (just triggers at different points)
- No changes to tool execution itself

---

## Open Questions

1. **Classifier frequency**: Should classification run on every turn, or only when intent is ambiguous?
   - Proposal: Run always, but cache result if confidence > 0.9 and context unchanged

2. **Prefix syntax**: Should `@node` be the syntax, or something else like `/node` or `#node`?
   - Proposal: `@node` aligns with mention syntax in other tools

3. **Path visibility**: Should DAG path always be shown, or only at depth > 1?
   - Proposal: Show only at depth > 1 to avoid noise on simple questions

4. **Hook modification**: Should hooks be able to modify the DAG path?
   - Proposal: Yes, `block_if_fails` on `on_node_transition` effectively does this

---

## Related Work

- **RFC-131**: Holy Light CLI Theme (visual identity)
- **RFC-135**: Unified Chat-Agent Loop (superseded)
- **RFC-138**: Agent package reorganization

---

## Milestones

| Priority | Milestone | Deliverable |
|----------|-----------|-------------|
| P0 | Intent Layer | `agent/intent/` module with DAG types and classifier |
| P0 | Integration | DAG classifier integrated with unified loop |
| P0 | User Hooks | `.sunwell/hooks.toml` with `on_node_transition` |
| P0 | Inline Diffs | Diff preview when entering WRITE nodes |
| P1 | Progress Display | DAG path in progress visualization |
| P1 | User Override | `@node` prefix handling |
| P1 | Notifications | Desktop alerts integrated with hooks |

---

## Success Criteria

- [ ] Intent correctly classified as path through DAG (not binary)
- [ ] Permission escalation works: write/delete nodes require approval
- [ ] User can override with `@explain`, `@review` prefixes
- [ ] Hooks can trigger on `on_node_transition`
- [ ] Diff preview shows when entering WRITE nodes
- [ ] Progress display shows current DAG path
- [ ] No regression in existing tool execution behavior
