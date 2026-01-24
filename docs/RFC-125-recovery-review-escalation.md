# RFC-125: Recovery, Review & Escalation — Never Lose Progress

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-123 (Convergence Loops), RFC-042 (Validation Gates), RFC-040 (Plan Persistence)  
**Confidence**: 85% 🟢

## Summary

When Sunwell can't automatically fix errors, **preserve all progress and present a review interface** — like GitHub's merge conflict resolution UI. The user sees what succeeded, what failed, and can fix issues themselves or provide hints for the agent to retry.

## Motivation

### Problem

Currently, when convergence loops escalate or gates fail:

```
Agent generates 5 files → Gate fails on file 3 → ERROR → User sees only error message
```

**What's lost:**
- Files 1-2 that passed validation ✓
- File 3's content (even if 95% correct)
- Context about what was attempted
- Path to recovery

**What should happen:**

```
Agent generates 5 files → Gate fails on file 3 → SAVE ALL → REVIEW UI

┌─────────────────────────────────────────────────────────────────┐
│  🔄 Review Required: 1 issue needs attention                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ api/models.py          — Passed lint, types, imports         │
│  ✅ api/routes.py          — Passed lint, types                  │
│  ⚠️  api/handlers.py       — 2 syntax errors (lines 45, 67)     │
│  ⏸️ api/tests/test_api.py  — Waiting (depends on handlers.py)   │
│  ⏸️ api/main.py            — Waiting (depends on all)           │
│                                                                  │
│  [View Errors]  [Auto-Fix]  [Edit Manually]  [Ask Agent]        │
└─────────────────────────────────────────────────────────────────┘
```

### User Story

> "When Sunwell can't fix something, I want to see what it generated, understand what went wrong, and choose how to proceed. Don't throw away 90% good work because of 10% issues."

### The GitHub Merge Conflict Analogy

GitHub's PR merge conflict UI is perfect inspiration:

1. **Shows what succeeded**: Files without conflicts are merged
2. **Highlights conflicts**: Clear visual of problem areas with context
3. **Preserves both versions**: Original + incoming changes visible
4. **Multiple resolution paths**: Accept theirs, accept mine, manual edit
5. **Resume workflow**: After fixing, continue where left off

Sunwell needs the same for code generation failures.

---

## Goals

1. **Never lose progress**: All generated artifacts are saved, regardless of validation status
2. **Clear review interface**: Visual diff of what worked vs what failed
3. **Multiple recovery paths**: Auto-retry, manual fix, provide hints, abort cleanly
4. **Context preservation**: Everything needed to continue is saved
5. **Self-healing context**: Provide agent full picture to course-correct

## Non-Goals

- Replace human judgment for fundamental design issues
- Auto-commit partial/broken code
- Hide errors from users

---

## Design

### 1. Recovery State Model

```python
# sunwell/recovery/types.py

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime

class ArtifactStatus(Enum):
    """Status of a single artifact in recovery state."""
    PASSED = "passed"          # All gates passed
    FAILED = "failed"          # Gate(s) failed, needs review
    WAITING = "waiting"        # Blocked on failed dependency
    SKIPPED = "skipped"        # User chose to skip
    FIXED = "fixed"            # User fixed manually


@dataclass(frozen=True, slots=True)
class RecoveryArtifact:
    """A single artifact with its validation state."""
    path: Path
    content: str
    status: ArtifactStatus
    errors: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    
    @property
    def needs_review(self) -> bool:
        return self.status == ArtifactStatus.FAILED


@dataclass
class RecoveryState:
    """Complete state for recovery/review workflow.
    
    Saved to: .sunwell/recovery/{goal_hash}.json
    """
    # Identity
    goal: str
    goal_hash: str
    run_id: str
    
    # Artifacts
    artifacts: dict[str, RecoveryArtifact] = field(default_factory=dict)
    
    # What failed
    failed_gate: str | None = None
    failure_reason: str = ""
    error_details: list[str] = field(default_factory=list)
    
    # Context for retry
    iteration_history: list[dict] = field(default_factory=list)
    fix_attempts: list[dict] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def passed_artifacts(self) -> list[RecoveryArtifact]:
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.PASSED]
    
    @property
    def failed_artifacts(self) -> list[RecoveryArtifact]:
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.FAILED]
    
    @property
    def waiting_artifacts(self) -> list[RecoveryArtifact]:
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.WAITING]
    
    @property
    def recovery_possible(self) -> bool:
        """True if any artifacts passed — worth recovering."""
        return len(self.passed_artifacts) > 0
```

### 2. Recovery Manager

```python
# sunwell/recovery/manager.py

class RecoveryManager:
    """Manages saving and loading recovery state.
    
    Automatically saves on:
    - Gate failure
    - Convergence escalation
    - Timeout
    - User cancellation
    
    Example:
        >>> manager = RecoveryManager(Path(".sunwell/recovery"))
        >>> 
        >>> # On failure, save state
        >>> state = manager.create_from_execution(execution, error)
        >>> manager.save(state)
        >>> 
        >>> # Later, list pending recoveries
        >>> pending = manager.list_pending()
        >>> print(f"{len(pending)} runs need review")
        >>> 
        >>> # Review and fix
        >>> state = manager.load(goal_hash)
        >>> state.artifacts["api.py"].status = ArtifactStatus.FIXED
        >>> manager.save(state)
        >>> 
        >>> # Resume with fixed state
        >>> result = await agent.resume_from_recovery(state)
    """
    
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def create_from_execution(
        self,
        goal: str,
        run_id: str,
        artifacts: dict[str, Artifact],
        gate_results: list[GateResult],
        failure_reason: str,
    ) -> RecoveryState:
        """Create recovery state from failed execution."""
        ...
    
    def save(self, state: RecoveryState) -> Path:
        """Save recovery state atomically."""
        ...
    
    def load(self, goal_hash: str) -> RecoveryState | None:
        """Load recovery state by goal hash."""
        ...
    
    def list_pending(self) -> list[RecoverySummary]:
        """List all pending recoveries."""
        ...
    
    def mark_resolved(self, goal_hash: str) -> None:
        """Mark recovery as resolved (move to archive)."""
        ...
```

### 3. Self-Healing Context Injection

When the agent retries after escalation, provide **full context**:

```python
# sunwell/recovery/context.py

def build_healing_context(state: RecoveryState) -> str:
    """Build rich context for agent to self-heal.
    
    Provides:
    - What succeeded and why
    - What failed with exact errors
    - What was attempted before
    - Suggested fixes based on error patterns
    """
    return f"""
## Recovery Context

### Goal
{state.goal}

### What Succeeded ✅
{_format_passed(state.passed_artifacts)}

### What Failed ⚠️
{_format_failed(state.failed_artifacts)}

### Error Details
{_format_errors(state.error_details)}

### Previous Fix Attempts
{_format_fix_history(state.fix_attempts)}

### Suggested Approach
{_suggest_fixes(state)}

### Instructions
Focus ONLY on fixing the failed artifacts. The passed artifacts are correct.
Do not regenerate passed artifacts unless they depend on failed ones.
"""
```

### 4. Review Interface (CLI)

```bash
$ sunwell review

┌─────────────────────────────────────────────────────────────────┐
│  🔄 1 Run Needs Review                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Run: abc123 (2 minutes ago)                                     │
│  Goal: "Build REST API with user authentication"                 │
│                                                                  │
│  ✅ 3 passed    ⚠️ 1 failed    ⏸️ 2 waiting                     │
│                                                                  │
│  Failed: api/auth.py                                             │
│    Line 45: SyntaxError: expected ':'                           │
│    Line 67: NameError: 'User' is not defined                    │
│                                                                  │
│  [a] Auto-fix with agent                                        │
│  [e] Edit api/auth.py in $EDITOR                                │
│  [h] Give agent a hint                                          │
│  [s] Skip and continue (write passed files)                     │
│  [v] View full file                                             │
│  [d] View diff from last attempt                                │
│  [q] Abort                                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Review Interface (Studio)

```typescript
// Studio Observatory → Recovery Panel

interface RecoveryPanel {
  // Visual artifact status grid
  artifacts: ArtifactCard[];
  
  // Expandable error details
  errorDetails: {
    file: string;
    errors: ErrorAnnotation[];  // With line numbers, suggestions
  }[];
  
  // Action buttons
  actions: {
    autoFix: () => Promise<void>;     // Retry with healing context
    editFile: (path: string) => void;  // Open in editor
    giveHint: (hint: string) => void;  // Add context for retry
    skipFailed: () => void;            // Write only passed files
    abort: () => void;
  };
  
  // Diff viewer for failed files
  diffView: {
    original: string;
    attempted: string;
    errors: ErrorMarker[];
  };
}
```

### 6. Integration Points

#### When Convergence Escalates

```python
# In ConvergenceLoop.run()

# Max iterations reached
self.result = ConvergenceResult(
    status=ConvergenceStatus.ESCALATED,
    ...
)

# NEW: Save recovery state
recovery_state = self._recovery_manager.create_from_execution(
    goal=self._goal,
    run_id=self._run_id,
    artifacts=artifacts,
    gate_results=gate_results,
    failure_reason="max_iterations",
)
self._recovery_manager.save(recovery_state)

yield convergence_escalated_event(
    iterations=self.config.max_iterations,
    recovery_id=recovery_state.goal_hash,  # NEW: Include recovery ID
    passed_count=len(recovery_state.passed_artifacts),
    failed_count=len(recovery_state.failed_artifacts),
)
```

#### When Gate Fails

```python
# In Agent._execute_with_gates()

if event.type == EventType.GATE_FAIL:
    # NEW: Save recovery state before returning
    recovery_state = self._save_recovery_state(
        artifacts=artifacts,
        failed_gate=event.data["gate_id"],
        error=event.data["error_message"],
    )
    
    yield escalate_with_recovery_event(
        reason="gate_failure",
        recovery_id=recovery_state.goal_hash,
        ...
    )
```

#### Resume from Recovery

```python
# sunwell/agent/core.py

async def resume_from_recovery(
    self,
    recovery_state: RecoveryState,
    user_hint: str | None = None,
) -> AsyncIterator[AgentEvent]:
    """Resume execution from recovery state.
    
    Args:
        recovery_state: Saved state from previous failure
        user_hint: Optional hint from user to guide fixes
    """
    # Build healing context
    healing_context = build_healing_context(recovery_state)
    if user_hint:
        healing_context += f"\n\n### User Hint\n{user_hint}"
    
    # Only regenerate failed artifacts
    failed_ids = {str(a.path) for a in recovery_state.failed_artifacts}
    
    # Re-run with focused context
    async for event in self._execute_focused_fix(
        failed_ids=failed_ids,
        context=healing_context,
        existing_artifacts=recovery_state.passed_artifacts,
    ):
        yield event
```

---

## Events

New events for recovery visibility:

```python
# sunwell/agent/events.py

class EventType(Enum):
    # ... existing events ...
    
    # Recovery events
    RECOVERY_SAVED = "recovery_saved"
    """Recovery state saved — user can review."""
    
    RECOVERY_LOADED = "recovery_loaded"
    """Resuming from recovery state."""
    
    RECOVERY_RESOLVED = "recovery_resolved"
    """Recovery completed — all artifacts passed."""
    
    RECOVERY_ABORTED = "recovery_aborted"
    """User chose to abort recovery."""
```

---

## CLI Commands

```bash
# List pending recoveries
sunwell review                    # Interactive review
sunwell review --list             # Just list, no interaction

# Actions on specific recovery
sunwell review abc123 --auto-fix  # Retry with agent
sunwell review abc123 --skip      # Write passed files only
sunwell review abc123 --abort     # Delete recovery state

# Resume with hint
sunwell review abc123 --hint "The User model is in models/user.py"

# View details
sunwell review abc123 --errors    # Show all errors
sunwell review abc123 --diff      # Show diff from last attempt
sunwell review abc123 --context   # Show healing context
```

---

## Success Criteria

1. **Never lose artifacts**: Gate failure saves all generated content
2. **Clear status**: User knows exactly what passed/failed/waiting
3. **Multiple paths**: Auto-fix, manual edit, hint, skip, abort
4. **Seamless resume**: Continue from exactly where it stopped
5. **Rich context**: Agent has everything needed to self-heal

---

## Implementation Plan

### Phase 1: Recovery State (1 day)
- [ ] `RecoveryState` and `RecoveryArtifact` types
- [ ] `RecoveryManager` with save/load/list
- [ ] Integration with convergence loop escalation

### Phase 2: CLI Review (1 day)
- [ ] `sunwell review` command
- [ ] Interactive menu with actions
- [ ] Resume from recovery

### Phase 3: Self-Healing Context (0.5 day)
- [ ] `build_healing_context()` function
- [ ] Integration with agent resume
- [ ] User hint support

### Phase 4: Studio Integration (1 day)
- [ ] Recovery panel component
- [ ] Error annotation viewer
- [ ] Diff viewer for failed files

---

## Open Questions

1. **Retention**: How long to keep recovery states? (Proposal: 7 days or until resolved)
2. **Partial writes**: Should we write passed files immediately or wait for full resolution?
3. **Concurrent recoveries**: Can user have multiple pending recoveries?

---

## Related RFCs

- RFC-123: Convergence Loops — Triggers recovery on escalation
- RFC-042: Validation Gates — Gate failures trigger recovery
- RFC-040: Plan Persistence — Recovery state format alignment
- RFC-122: Compound Learning — Learn from recovery patterns
