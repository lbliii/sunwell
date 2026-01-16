# RFC-016: Autonomous Mode — Self-Directed Evolution

| Field | Value |
|-------|-------|
| **RFC** | 016 |
| **Title** | Autonomous Mode: Self-Directed Evolution |
| **Status** | Draft |
| **Created** | 2026-01-15 |
| **Author** | llane |
| **Depends On** | RFC-015 (Mirror Neurons) |

---

## Abstract

RFC-015 gave Sunwell the ability to introspect and propose improvements. RFC-016 takes this further: **autonomous mode** lets Sunwell work independently for extended periods, continuously improving itself with minimal human intervention.

```
Manual Mode:     Human → Task → Sunwell → Result → Human reviews
Autonomous Mode: Human → Goals → Sunwell loops indefinitely → Human checks in
```

### Key Properties

1. **Long-running** — Can operate for hours or days
2. **Self-directed** — Chooses what to work on based on goals
3. **Gracefully interruptible** — Always safe to stop
4. **Observable** — Progress visible in real-time
5. **Bounded** — Safety limits prevent runaway behavior

---

## Problem Statement

Mirror neurons let Sunwell propose improvements, but:
- Each improvement requires human initiation
- No continuity between sessions
- Can't work overnight while human sleeps
- No prioritization of what to improve

### The Vision

```
$ sunwell autonomous start --goals "improve error handling, optimize latency"

🤖 Autonomous mode started
   Goals: improve error handling, optimize latency
   Session: auto_2026-01-15_19-45
   
   Press Ctrl+C or run 'sunwell autonomous stop' to gracefully exit
   View progress: sunwell autonomous status
   
[19:45:01] 🔍 Analyzing codebase for improvement opportunities...
[19:45:15] 💡 Found 12 potential improvements
[19:45:16] 📋 Prioritized by impact: error_handling (3), latency (5), other (4)
[19:46:02] 🔧 Working on: Add SSL error pattern recognition
[19:47:30] ✅ Proposal prop_abc123 created and queued
[19:47:31] 🔧 Working on: Parallelize file read operations
...

# Meanwhile, human can check in anytime:
$ sunwell autonomous status
🤖 Autonomous Session: auto_2026-01-15_19-45
   Running for: 2h 15m
   Proposals created: 8
   Proposals auto-applied: 3 (low-risk only)
   Proposals queued for review: 5
   Current task: Analyzing headspace memory patterns
   
   Next checkpoint: 15 minutes
   Safe to interrupt: YES ✓

# Graceful stop
$ sunwell autonomous stop
⏸️  Stopping gracefully...
   Finishing current task: Analyzing headspace memory patterns
   Saving checkpoint...
   Session paused. Resume with: sunwell autonomous resume
```

---

## Architecture

### Control Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS CONTROL LOOP                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                                                            │
│  │   GOALS     │  "improve error handling, optimize latency"                │
│  └──────┬──────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     DISCOVERY PHASE                                  │   │
│  │  • Scan codebase for improvement opportunities                       │   │
│  │  • Analyze execution history for patterns                            │   │
│  │  • Check test coverage gaps                                          │   │
│  │  • Review open TODOs and FIXMEs                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PRIORITIZATION PHASE                              │   │
│  │  • Score by goal alignment                                           │   │
│  │  • Estimate effort and risk                                          │   │
│  │  • Sort by impact/effort ratio                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      WORK PHASE                                      │   │
│  │  • Pick highest priority task                                        │   │
│  │  • Introspect relevant code                                          │   │
│  │  • Generate improvement proposal                                     │   │
│  │  • Run safety checks                                                 │   │
│  │  • Auto-apply if low-risk, else queue for review                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CHECKPOINT PHASE                                  │   │
│  │  • Save progress to disk                                             │   │
│  │  • Check for stop signal                                             │   │
│  │  • Check safety limits                                               │   │
│  │  • Emit heartbeat                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         │ (loop unless stopped or limits reached)                           │
│         └──────────────────────────────────────────────────────────────────▶│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Graceful Interruption

Multiple ways to stop, all graceful:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INTERRUPTION SIGNALS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Signal              Method                    Behavior                      │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Ctrl+C              SIGINT                    Finish current task, save     │
│  sunwell auto stop   File signal (.stop)      Finish current task, save     │
│  Time limit          Config (--max-hours)     Checkpoint and pause           │
│  Change limit        Config (--max-changes)   Checkpoint and pause           │
│  Error threshold     Auto (3 consecutive)     Checkpoint and pause           │
│  Idle timeout        Auto (no work found)     Checkpoint and exit            │
│                                                                              │
│  ALL signals result in:                                                      │
│  1. Complete current atomic operation                                        │
│  2. Save checkpoint with full state                                          │
│  3. Write summary report                                                     │
│  4. Clean exit (resumable)                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Safety Constraints

### Autonomous Mode Limits

```yaml
autonomous_policy:
  # Time limits
  max_continuous_hours: 8        # Force checkpoint after 8 hours
  checkpoint_interval_minutes: 15 # Save state every 15 min
  
  # Change limits
  max_proposals_per_session: 50   # Stop after 50 proposals
  max_auto_apply_per_session: 10  # Only 10 can be auto-applied
  max_consecutive_failures: 3     # Pause after 3 failures in a row
  
  # Risk thresholds for auto-apply
  auto_apply_risk_threshold: "low"  # Only auto-apply low-risk changes
  # Risk levels: trivial < low < medium < high < critical
  
  # Always queue for human review
  require_review:
    - risk_level: [medium, high, critical]
    - affects_modules: [core, safety, tools/types]
    - changes_tests: true
    - deletes_code: true
  
  # Cooldown between changes
  min_seconds_between_changes: 30
  
  # Resource limits
  max_memory_mb: 1024
  max_cpu_percent: 50  # Don't starve other processes
```

### Risk Assessment

```python
def assess_risk(proposal: Proposal) -> RiskLevel:
    """Determine risk level of a proposal."""
    
    # Critical: Never auto-apply
    if any(mod in proposal.diff for mod in IMMUTABLE_MODULES):
        return RiskLevel.CRITICAL
    
    # High: Structural changes
    if proposal.deletes_code or proposal.changes_api:
        return RiskLevel.HIGH
    
    # Medium: Behavioral changes
    if proposal.type in ["validator", "workflow"]:
        return RiskLevel.MEDIUM
    
    # Low: Additive changes
    if proposal.type == "heuristic" and not proposal.modifies_existing:
        return RiskLevel.LOW
    
    # Trivial: Comments, docs, formatting
    if proposal.type in ["documentation", "formatting"]:
        return RiskLevel.TRIVIAL
    
    return RiskLevel.MEDIUM  # Default to medium
```

---

## State Management

### Checkpoint Format

```json
{
  "session_id": "auto_2026-01-15_19-45",
  "started_at": "2026-01-15T19:45:00Z",
  "checkpoint_at": "2026-01-15T22:00:00Z",
  "status": "paused",
  
  "goals": ["improve error handling", "optimize latency"],
  
  "progress": {
    "opportunities_found": 45,
    "opportunities_completed": 12,
    "opportunities_remaining": 33,
    "proposals_created": 15,
    "proposals_auto_applied": 5,
    "proposals_queued": 8,
    "proposals_rejected": 2
  },
  
  "current_task": {
    "id": "opp_xyz789",
    "description": "Add memory error pattern",
    "started_at": "2026-01-15T21:58:00Z",
    "phase": "analysis"
  },
  
  "work_queue": [
    {"id": "opp_001", "priority": 0.95, "description": "..."},
    {"id": "opp_002", "priority": 0.87, "description": "..."}
  ],
  
  "completed": [
    {"id": "opp_003", "proposal": "prop_abc", "result": "auto_applied"},
    {"id": "opp_004", "proposal": "prop_def", "result": "queued"}
  ],
  
  "metrics": {
    "total_runtime_seconds": 8100,
    "avg_task_seconds": 675,
    "success_rate": 0.87
  }
}
```

### Resume Capability

```bash
# List paused sessions
$ sunwell autonomous list
SESSION                      STATUS    PROGRESS    LAST ACTIVE
auto_2026-01-15_19-45       paused    12/45       2h ago
auto_2026-01-14_10-30       completed 50/50       1d ago

# Resume a session
$ sunwell autonomous resume auto_2026-01-15_19-45
🔄 Resuming session auto_2026-01-15_19-45
   Restoring checkpoint from 2026-01-15T22:00:00Z
   Progress: 12/45 opportunities completed
   Current task: Add memory error pattern (continuing)
   
[22:15:01] 🔧 Resuming: Add memory error pattern
[22:15:30] ✅ Proposal prop_ghi789 created
...
```

---

## CLI Interface

### Commands

```bash
# Start autonomous mode
sunwell autonomous start [OPTIONS]

Options:
  --goals TEXT           Comma-separated improvement goals
  --max-hours FLOAT      Maximum runtime in hours (default: 8)
  --max-changes INT      Maximum proposals to create (default: 50)
  --auto-apply           Enable auto-apply for low-risk changes
  --review-all           Queue all proposals for review (no auto-apply)
  --checkpoint INT       Checkpoint interval in minutes (default: 15)
  --quiet                Minimal output (just heartbeats)
  --verbose              Detailed output for each step

# Check status
sunwell autonomous status [SESSION_ID]

# Stop gracefully
sunwell autonomous stop [SESSION_ID]

# Resume paused session
sunwell autonomous resume SESSION_ID

# List all sessions
sunwell autonomous list

# View session report
sunwell autonomous report SESSION_ID

# Review queued proposals
sunwell autonomous review [SESSION_ID]
```

### Example Session

```bash
$ sunwell autonomous start \
    --goals "improve error handling, add missing tests, optimize performance" \
    --max-hours 4 \
    --auto-apply

╔══════════════════════════════════════════════════════════════════════════════╗
║                        🤖 AUTONOMOUS MODE STARTED                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Session:     auto_2026-01-15_19-45                                          ║
║  Goals:       improve error handling, add missing tests, optimize performance ║
║  Max Runtime: 4 hours                                                         ║
║  Auto-Apply:  enabled (low-risk only)                                        ║
║                                                                               ║
║  Controls:                                                                    ║
║    • Ctrl+C           - Graceful stop                                        ║
║    • sunwell auto stop - Stop from another terminal                          ║
║    • sunwell auto status - Check progress                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

[19:45:01] 🔍 Phase: Discovery
           Scanning codebase for improvement opportunities...

[19:45:15] 📊 Found 23 opportunities:
           • Error handling: 8 improvements
           • Missing tests: 9 improvements  
           • Performance: 6 improvements

[19:45:16] 📋 Phase: Prioritization
           Ranking by goal alignment and effort...
           Top 5:
           1. [0.95] Add SSL error recognition (error handling)
           2. [0.92] Add memory error recognition (error handling)
           3. [0.89] Test coverage for proposals.py (missing tests)
           4. [0.85] Parallelize pattern analysis (performance)
           5. [0.82] Add JSON parse error pattern (error handling)

[19:45:17] 🔧 Phase: Work
           Starting: Add SSL error recognition

[19:46:02] 📖 Reading sunwell/mirror/analysis.py...
[19:46:05] 🔍 Analyzing FailureAnalyzer.known_patterns...
[19:46:30] 💡 Generating proposal...
[19:46:45] ✅ Created prop_ssl_001
           Risk: LOW → Auto-applying

[19:46:50] 🚀 Applied prop_ssl_001
           Added SSL error pattern with 90% confidence

[19:46:51] 💾 Checkpoint saved (1/23 complete)

[19:46:52] 🔧 Starting: Add memory error recognition
...

[21:45:00] ⏰ Max runtime (2h) approaching
           Completing current task...

[21:46:30] 💾 Final checkpoint saved

╔══════════════════════════════════════════════════════════════════════════════╗
║                        📊 SESSION SUMMARY                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Runtime:           2h 1m 29s                                                ║
║  Opportunities:     18/23 completed                                          ║
║  Proposals Created: 18                                                        ║
║    • Auto-applied:  7 (low-risk)                                             ║
║    • Queued:        9 (medium-risk, need review)                             ║
║    • Rejected:      2 (failed safety checks)                                 ║
║                                                                               ║
║  Next Steps:                                                                  ║
║    • Review queued proposals: sunwell autonomous review                      ║
║    • Resume session: sunwell autonomous resume auto_2026-01-15_19-45         ║
║    • View full report: sunwell autonomous report auto_2026-01-15_19-45       ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Implementation

### Core Types

```python
# src/sunwell/autonomous/types.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class SessionStatus(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class RiskLevel(Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Opportunity:
    """An identified improvement opportunity."""
    id: str
    category: str  # error_handling, tests, performance, etc.
    description: str
    target_module: str
    priority: float  # 0.0 - 1.0
    estimated_effort: str  # trivial, small, medium, large
    risk_level: RiskLevel
    
@dataclass
class SessionConfig:
    """Configuration for an autonomous session."""
    goals: list[str]
    max_hours: float = 8.0
    max_proposals: int = 50
    max_auto_apply: int = 10
    auto_apply_enabled: bool = True
    checkpoint_interval_minutes: int = 15
    min_seconds_between_changes: int = 30

@dataclass
class SessionState:
    """Persistent state for an autonomous session."""
    session_id: str
    config: SessionConfig
    status: SessionStatus
    started_at: datetime
    checkpoint_at: datetime | None = None
    
    # Progress tracking
    opportunities: list[Opportunity] = field(default_factory=list)
    completed: list[dict] = field(default_factory=list)
    current_task: Opportunity | None = None
    
    # Counters
    proposals_created: int = 0
    proposals_auto_applied: int = 0
    proposals_queued: int = 0
    consecutive_failures: int = 0
    
    # Timing
    total_runtime_seconds: float = 0
```

### Control Loop

```python
# src/sunwell/autonomous/loop.py
import asyncio
import signal
from pathlib import Path
from datetime import datetime, timedelta

class AutonomousLoop:
    """Main control loop for autonomous mode."""
    
    def __init__(
        self,
        config: SessionConfig,
        mirror_handler: MirrorHandler,
        storage_path: Path,
    ):
        self.config = config
        self.mirror = mirror_handler
        self.storage = storage_path
        self.state: SessionState | None = None
        self._stop_requested = False
        self._pause_requested = False
        
    async def start(self) -> None:
        """Start the autonomous loop."""
        # Setup signal handlers
        self._setup_signals()
        
        # Initialize state
        self.state = SessionState(
            session_id=f"auto_{datetime.now().strftime('%Y-%m-%d_%H-%M')}",
            config=self.config,
            status=SessionStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        # Main loop
        try:
            await self._run_loop()
        finally:
            await self._cleanup()
    
    async def _run_loop(self) -> None:
        """Main execution loop."""
        while not self._should_stop():
            # Discovery phase
            if not self.state.opportunities:
                await self._discover_opportunities()
            
            # Check if any work to do
            if not self.state.opportunities:
                self._emit("idle", "No opportunities found, exiting")
                break
            
            # Work phase
            await self._work_on_next()
            
            # Checkpoint phase
            await self._checkpoint()
            
            # Cooldown
            await asyncio.sleep(self.config.min_seconds_between_changes)
    
    async def _discover_opportunities(self) -> None:
        """Find improvement opportunities based on goals."""
        self._emit("discovery", "Scanning for opportunities...")
        
        opportunities = []
        
        for goal in self.config.goals:
            # Use mirror neurons to find opportunities
            if "error" in goal.lower():
                opps = await self._find_error_handling_opportunities()
                opportunities.extend(opps)
            elif "test" in goal.lower():
                opps = await self._find_test_opportunities()
                opportunities.extend(opps)
            elif "performance" in goal.lower() or "optim" in goal.lower():
                opps = await self._find_performance_opportunities()
                opportunities.extend(opps)
        
        # Prioritize and dedupe
        self.state.opportunities = self._prioritize(opportunities)
        self._emit("discovery_complete", f"Found {len(opportunities)} opportunities")
    
    async def _work_on_next(self) -> None:
        """Work on the next highest priority opportunity."""
        if not self.state.opportunities:
            return
        
        opp = self.state.opportunities.pop(0)
        self.state.current_task = opp
        self._emit("work_start", f"Starting: {opp.description}")
        
        try:
            # Generate proposal using mirror neurons
            proposal = await self._generate_proposal(opp)
            
            if proposal:
                self.state.proposals_created += 1
                
                # Decide: auto-apply or queue
                if (
                    self.config.auto_apply_enabled
                    and opp.risk_level in [RiskLevel.TRIVIAL, RiskLevel.LOW]
                    and self.state.proposals_auto_applied < self.config.max_auto_apply
                ):
                    await self._auto_apply(proposal)
                else:
                    await self._queue_for_review(proposal)
                
                self.state.consecutive_failures = 0
            else:
                self.state.consecutive_failures += 1
                
        except Exception as e:
            self._emit("error", f"Failed: {e}")
            self.state.consecutive_failures += 1
        
        self.state.completed.append({
            "opportunity": opp.id,
            "timestamp": datetime.now().isoformat(),
        })
        self.state.current_task = None
    
    def _should_stop(self) -> bool:
        """Check if loop should stop."""
        if self._stop_requested:
            return True
        
        # Time limit
        runtime = (datetime.now() - self.state.started_at).total_seconds()
        if runtime > self.config.max_hours * 3600:
            self._emit("limit", "Max runtime reached")
            return True
        
        # Proposal limit
        if self.state.proposals_created >= self.config.max_proposals:
            self._emit("limit", "Max proposals reached")
            return True
        
        # Consecutive failures
        if self.state.consecutive_failures >= 3:
            self._emit("limit", "Too many consecutive failures")
            return True
        
        return False
    
    def _setup_signals(self) -> None:
        """Setup graceful shutdown signals."""
        def handle_signal(signum, frame):
            self._emit("signal", f"Received signal {signum}, stopping gracefully...")
            self._stop_requested = True
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    
    async def _checkpoint(self) -> None:
        """Save current state to disk."""
        self.state.checkpoint_at = datetime.now()
        checkpoint_path = self.storage / f"{self.state.session_id}.json"
        
        import json
        with open(checkpoint_path, "w") as f:
            json.dump(self._serialize_state(), f, indent=2, default=str)
        
        self._emit("checkpoint", f"Saved to {checkpoint_path}")
    
    def _emit(self, event: str, message: str) -> None:
        """Emit a progress event."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
```

---

## Usage Examples

### Basic Autonomous Run

```bash
# Run for up to 2 hours, auto-apply low-risk changes
sunwell autonomous start \
    --goals "improve error handling" \
    --max-hours 2 \
    --auto-apply
```

### Conservative Mode (Review Everything)

```bash
# Generate proposals but don't apply any automatically
sunwell autonomous start \
    --goals "refactor, optimize" \
    --review-all

# Later, review what was found
sunwell autonomous review
```

### Overnight Run

```bash
# Run overnight with generous limits
sunwell autonomous start \
    --goals "comprehensive improvement" \
    --max-hours 8 \
    --max-changes 100 \
    --checkpoint 30

# Check in the morning
sunwell autonomous status
sunwell autonomous report
```

### Resume After Interrupt

```bash
# Start a session
sunwell autonomous start --goals "testing"
# ... Ctrl+C to stop ...

# Later, resume where you left off
sunwell autonomous resume auto_2026-01-15_19-45
```

---

## Safety Considerations

### What CAN'T Autonomous Mode Do

Even in autonomous mode, these constraints are absolute:

1. **Cannot modify core modules** — `sunwell/core/*`, `sunwell/mirror/safety.py`
2. **Cannot escalate trust** — Trust levels are immutable
3. **Cannot bypass safety checks** — All proposals go through validation
4. **Cannot disable interruption** — Signal handlers are always active
5. **Cannot exceed rate limits** — Same limits as manual mode

### Automatic Pausing

Autonomous mode automatically pauses when:

- 3 consecutive failures occur
- Runtime exceeds configured max
- Proposal count exceeds configured max
- Available memory drops below threshold
- Stop signal received

### Human Review Queue

Medium+ risk changes are always queued:

```bash
$ sunwell autonomous review

📋 Proposals Awaiting Review (5)

[prop_abc123] Add JSON validation to config parser
  Risk: MEDIUM (changes parsing behavior)
  Affects: sunwell/core/config.py
  
  [A]pprove  [R]eject  [S]kip  [D]etails  [Q]uit
```

---

## Success Criteria

### Phase 1: Core Loop
- [ ] Basic autonomous loop runs
- [ ] Graceful Ctrl+C handling
- [ ] Checkpoint saving/loading
- [ ] Resume capability

### Phase 2: Discovery
- [ ] Goal-based opportunity finding
- [ ] Priority scoring
- [ ] Risk assessment

### Phase 3: Safety
- [ ] Auto-apply only low-risk
- [ ] Review queue for medium+
- [ ] Rate limiting enforced
- [ ] All stop signals work

### Phase 4: Observability
- [ ] Real-time progress output
- [ ] Status command works
- [ ] Session reports generated
- [ ] Metrics tracked

---

## Future Directions

### Scheduled Runs

```bash
# Run every night at 2 AM
sunwell autonomous schedule \
    --cron "0 2 * * *" \
    --goals "maintenance" \
    --max-hours 4
```

### Multi-Goal Optimization

```yaml
goals:
  - name: "error handling"
    priority: 0.9
    max_proposals: 20
  - name: "performance"
    priority: 0.7
    max_proposals: 10
```

### Learning From Results

Track which proposals succeed/fail after application, and use that to improve future prioritization.

---

## Appendix: Quick Reference

```bash
# Start
sunwell autonomous start --goals "X, Y" [--max-hours N] [--auto-apply]

# Monitor  
sunwell autonomous status [SESSION]

# Stop gracefully
sunwell autonomous stop [SESSION]
# Or: Ctrl+C

# Resume
sunwell autonomous resume SESSION

# Review pending
sunwell autonomous review

# Reports
sunwell autonomous list
sunwell autonomous report SESSION
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-15 | Initial draft |
