# RFC-051: Multi-Instance Coordination — Parallel Autonomous Agents

**Status**: Draft  
**Created**: 2026-01-19  
**Last Updated**: 2026-01-19  
**Revision**: 2 — Fixed code bugs, race conditions, merge strategy  
**Authors**: Sunwell Team  
**Depends on**: RFC-046 (Autonomous Backlog), RFC-048 (Autonomy Guardrails), RFC-049 (External Integration)  
**Enables**: Phase 4 Self-Improving System, parallel goal execution  
**Confidence**: 85% (design reviewed, implementation-ready)

---

## Revision History

| Rev | Date | Changes |
|-----|------|---------|
| 2 | 2026-01-19 | Fixed GoalDependencyGraph `_conflicts` field, added `MergeResult`/`WorkerResult` dataclasses, fixed ResourceGovernor race condition, fixed worker entry point for multiprocessing, added stale lock cleanup, corrected merge strategy direction, added signal handling |
| 1 | 2026-01-19 | Initial draft |

---

## Summary

Multi-Instance Coordination enables multiple Sunwell agent instances to work in parallel on the same codebase, dividing work intelligently and avoiding conflicts. Instead of sequential goal execution, Sunwell can spin up N workers that collaborate through a shared backlog, coordinate file access, and merge their changes safely.

**Core insight**: Many autonomous goals are independent — "add tests for auth.py" and "fix typo in README" can run simultaneously. The bottleneck isn't intelligence; it's serialization. Parallel execution multiplies throughput without multiplying errors.

**Design approach**: Process-based parallelism with file-based coordination. Each instance is a separate Python process that claims goals from a shared backlog, uses file locks to prevent conflicts, and commits atomically. No shared memory, no complex IPC — just filesystem primitives.

**One-liner**: N agents, one codebase, zero conflicts — work that took all night now takes an hour.

---

## Motivation

### The Serial Bottleneck

RFC-046 (Autonomous Backlog) enables goal-driven execution, but goals run one at a time:

```
┌────────────────────────────────────────────────────────────────────┐
│                    SERIAL EXECUTION                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Backlog: 20 goals                                                 │
│                                                                    │
│  Time →                                                            │
│  ─────────────────────────────────────────────────────────────────│
│  │ Goal 1 │ Goal 2 │ Goal 3 │ Goal 4 │ ... │ Goal 20 │            │
│  └────────┴────────┴────────┴────────┴─────┴─────────┘            │
│                                                                    │
│  If each goal takes 5 minutes:                                     │
│  Total time = 20 × 5 = 100 minutes (1.5+ hours)                    │
│                                                                    │
│  CPU utilization: ~20% (mostly waiting on LLM)                     │
│  LLM utilization: ~30% (mostly waiting on tool execution)          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

This is wasteful because:
1. **Goals are often independent** — "fix tests" and "add docstrings" don't conflict
2. **LLM has latency** — Agent waits 1-5s per inference, could be doing other work
3. **Tools are I/O-bound** — File reads/writes, git operations have idle time
4. **CPU is underutilized** — Local inference uses 20-40% during agent idle periods

### The Parallel Opportunity

```
┌────────────────────────────────────────────────────────────────────┐
│                    PARALLEL EXECUTION (N=4)                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Backlog: 20 goals                                                 │
│                                                                    │
│  Time →                                                            │
│  ─────────────────────────────────────────────────────────────────│
│  Worker 1: │ G1 │ G5 │ G9  │ G13 │ G17 │                          │
│  Worker 2: │ G2 │ G6 │ G10 │ G14 │ G18 │                          │
│  Worker 3: │ G3 │ G7 │ G11 │ G15 │ G19 │                          │
│  Worker 4: │ G4 │ G8 │ G12 │ G16 │ G20 │                          │
│  ──────────┴────┴────┴─────┴─────┴─────┘                          │
│                                                                    │
│  If each goal takes 5 minutes:                                     │
│  Total time = ceil(20/4) × 5 = 25 minutes                          │
│                                                                    │
│  Speedup: 4× (100 min → 25 min)                                    │
│  CPU utilization: ~60%                                             │
│  LLM utilization: ~70%                                             │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### What Multi-Instance Enables

| Before (Serial) | After (Parallel) |
|-----------------|------------------|
| 1 goal at a time | N goals simultaneously |
| 100% sequential | 70%+ parallelizable goals |
| Overnight backlog | Hourly completion |
| Idle CPU/GPU | Better resource utilization |
| Single point of failure | Resilient to worker crashes |

### Real-World Scenario

```
Friday 5pm: "sunwell backlog execute --workers 4"

Backlog has 15 goals:
- 8 test coverage goals (independent)
- 4 documentation goals (independent)
- 2 refactoring goals (may conflict)
- 1 dependency update (independent)

Serial: 15 goals × 5 min = 75 minutes
Parallel (4 workers): 
  - Round 1: 4 independent goals finish
  - Round 2: 4 independent goals finish
  - Round 3: 4 independent goals finish
  - Round 4: 2 conflicting goals run serial + 1 independent
  - Total: ~25 minutes
  
You check back at 5:30pm. All done.
```

---

## Goals and Non-Goals

### Goals

1. **Parallel goal execution** — Run N agent instances on independent goals
2. **Conflict-free file access** — File locks prevent simultaneous edits
3. **Shared backlog coordination** — Atomic goal claiming, no double-work
4. **Graceful degradation** — If workers crash, remaining work continues
5. **Resource-aware scaling** — Respect LLM rate limits, memory constraints
6. **Merge-safe commits** — Each worker commits to isolated branches, merge at end
7. **Observable progress** — Real-time status of all workers
8. **Simple configuration** — `--workers N` flag, sensible defaults

### Non-Goals

1. **Distributed systems** — Single machine only (multi-machine is future RFC)
2. **Shared memory parallelism** — Process-based, not thread-based
3. **GPU multiplexing** — Each worker gets full LLM access (no vLLM batching yet)
4. **Complex scheduling** — Simple work-stealing, not optimal scheduling
5. **Partial results** — Goals are atomic; partial completion not supported
6. **Cross-codebase coordination** — Single project focus

---

## Design Overview

### Process Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MULTI-INSTANCE ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ sunwell backlog execute --workers 4                                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        COORDINATOR PROCESS                            │  │
│  │                                                                       │  │
│  │  • Spawns N worker processes                                          │  │
│  │  • Monitors worker health                                             │  │
│  │  • Collects results                                                   │  │
│  │  • Orchestrates final merge                                           │  │
│  │                                                                       │  │
│  └─────────────────────────────────────────────────────────────────────┬─┘  │
│                                                                        │    │
│           ┌──────────────┬──────────────┬──────────────┐               │    │
│           │              │              │              │               │    │
│           ▼              ▼              ▼              ▼               │    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │    │
│  │  WORKER 1   │ │  WORKER 2   │ │  WORKER 3   │ │  WORKER 4   │      │    │
│  │             │ │             │ │             │ │             │      │    │
│  │  PID: 1234  │ │  PID: 1235  │ │  PID: 1236  │ │  PID: 1237  │      │    │
│  │  Branch:    │ │  Branch:    │ │  Branch:    │ │  Branch:    │      │    │
│  │  sunwell/1  │ │  sunwell/2  │ │  sunwell/3  │ │  sunwell/4  │      │    │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘      │    │
│         │              │               │               │              │    │
│         └──────────────┴───────────────┴───────────────┘              │    │
│                                  │                                    │    │
│                                  ▼                                    │    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      SHARED RESOURCES (File-Based)                    │  │
│  │                                                                       │  │
│  │  .sunwell/                                                            │  │
│  │  ├── backlog/                                                         │  │
│  │  │   ├── current.json       ← Atomic reads/writes with flock          │  │
│  │  │   └── claims.json        ← Goal → worker mapping                   │  │
│  │  │                                                                    │  │
│  │  ├── locks/                                                           │  │
│  │  │   ├── files/             ← Per-file advisory locks                 │  │
│  │  │   │   ├── src_auth.py.lock                                         │  │
│  │  │   │   └── tests_test_auth.py.lock                                  │  │
│  │  │   └── goals/             ← Per-goal locks                          │  │
│  │  │       ├── goal-001.lock                                            │  │
│  │  │       └── goal-002.lock                                            │  │
│  │  │                                                                    │  │
│  │  ├── workers/                                                         │  │
│  │  │   ├── worker-1.json      ← Worker status, current goal             │  │
│  │  │   ├── worker-2.json                                                │  │
│  │  │   ├── worker-3.json                                                │  │
│  │  │   └── worker-4.json                                                │  │
│  │  │                                                                    │  │
│  │  └── intelligence/          ← Read-only during execution              │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: SETUP                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│  1. Coordinator starts                                                      │
│  2. Snapshot current branch → base_branch                                   │
│  3. Create N worker branches: sunwell/worker-1, sunwell/worker-2, ...       │
│  4. Spawn N worker processes                                                │
│  5. Each worker checks out its branch                                       │
│                                                                             │
│  Phase 2: EXECUTION (parallel)                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  LOOP until backlog empty:                                                  │
│    Worker:                                                                  │
│      1. Acquire backlog lock                                                │
│      2. Find unclaimed, executable goal (respects dependencies)             │
│      3. Claim goal, release backlog lock                                    │
│      4. Acquire file locks for affected paths                               │
│      5. Execute goal (AdaptiveAgent)                                        │
│      6. Commit changes to worker branch                                     │
│      7. Release file locks                                                  │
│      8. Update backlog: goal complete                                       │
│      9. Repeat                                                              │
│                                                                             │
│  Phase 3: MERGE                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│  1. Wait for all workers to finish                                          │
│  2. For each worker branch (in order):                                      │
│     a. Rebase onto base_branch                                              │
│     b. If conflict: mark for human review                                   │
│     c. If clean: fast-forward base_branch                                   │
│  3. Delete worker branches                                                  │
│  4. Report results                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Conflict Prevention Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONFLICT PREVENTION LAYERS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: DEPENDENCY ANALYSIS (at planning time)                            │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Before execution, analyze goals for conflicts:                             │
│                                                                             │
│  Goal A: "Add tests for auth.py"    → touches: tests/test_auth.py          │
│  Goal B: "Fix bug in auth.py"       → touches: src/auth.py                 │
│  Goal C: "Refactor auth.py"         → touches: src/auth.py, tests/test_*   │
│                                                                             │
│  Conflict detection:                                                        │
│    A ∩ B = ∅  → Can run in parallel                                        │
│    A ∩ C = {tests/test_auth.py} → Sequential or same worker                │
│    B ∩ C = {src/auth.py} → Sequential or same worker                       │
│                                                                             │
│                                                                             │
│  Layer 2: FILE LOCKING (at execution time)                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Advisory locks prevent simultaneous file access:                           │
│                                                                             │
│  Worker 1 wants to edit src/auth.py:                                        │
│    1. Try acquire lock: .sunwell/locks/files/src_auth.py.lock               │
│    2. If locked: wait (with timeout) or skip goal                           │
│    3. If available: acquire, edit, release                                  │
│                                                                             │
│                                                                             │
│  Layer 3: BRANCH ISOLATION (at commit time)                                 │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Each worker commits to its own branch:                                     │
│                                                                             │
│    base-branch ─────────────────────────────────────────────                │
│                 \                                                           │
│                  ├─ sunwell/worker-1 ─ commit A ─ commit B                  │
│                  │                                                          │
│                  ├─ sunwell/worker-2 ─ commit C ─ commit D                  │
│                  │                                                          │
│                  └─ sunwell/worker-3 ─ commit E                             │
│                                                                             │
│  Conflicts only possible at merge time, not during execution.               │
│                                                                             │
│                                                                             │
│  Layer 4: MERGE ORDERING (at merge time)                                    │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Deterministic merge order minimizes conflicts:                             │
│                                                                             │
│  1. Sort branches by earliest commit timestamp                              │
│  2. Rebase each branch onto accumulated base                                │
│  3. If conflict detected:                                                   │
│     a. Abort rebase                                                         │
│     b. Mark branch for human review                                         │
│     c. Continue with next branch                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 0. Shared Utilities

```python
import asyncio
import subprocess
from pathlib import Path


async def run_git(root: Path, args: list[str]) -> str:
    """Run a git command asynchronously.
    
    Args:
        root: Repository root directory
        args: Git command arguments (e.g., ["status", "--porcelain"])
    
    Returns:
        Command stdout as string
    
    Raises:
        subprocess.CalledProcessError: If git command fails
    """
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode,
            ["git", *args],
            stdout,
            stderr,
        )
    
    return stdout.decode()
```

---

### 1. Worker Process

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import asyncio
import os
import signal


class WorkerState(Enum):
    """Worker lifecycle states."""
    
    STARTING = "starting"
    IDLE = "idle"
    CLAIMING = "claiming"
    EXECUTING = "executing"
    COMMITTING = "committing"
    MERGING = "merging"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class WorkerStatus:
    """Current status of a worker process."""
    
    worker_id: int
    pid: int
    state: WorkerState
    branch: str
    current_goal_id: str | None = None
    goals_completed: int = 0
    goals_failed: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now())
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now())
    error_message: str | None = None


@dataclass
class WorkerResult:
    """Result of a worker process execution."""
    
    worker_id: int
    """Which worker produced this result."""
    
    goals_completed: int
    """Number of goals successfully completed."""
    
    goals_failed: int
    """Number of goals that failed."""
    
    branch: str
    """Git branch with the worker's commits."""
    
    duration_seconds: float = 0.0
    """Total execution time."""
    
    commit_shas: list[str] = field(default_factory=list)
    """List of commit SHAs created by this worker."""


class WorkerProcess:
    """A single worker process that executes goals.
    
    Each worker:
    1. Operates on its own git branch
    2. Claims goals from shared backlog
    3. Acquires file locks before editing
    4. Commits changes atomically
    5. Reports status to coordinator
    """
    
    def __init__(
        self,
        worker_id: int,
        root: Path,
        backlog_manager: BacklogManager,
        agent: AdaptiveAgent,
        config: MultiInstanceConfig,
    ):
        self.worker_id = worker_id
        self.root = root
        self.backlog_manager = backlog_manager
        self.agent = agent
        self.config = config
        
        self.branch = f"sunwell/worker-{worker_id}"
        self.status = WorkerStatus(
            worker_id=worker_id,
            pid=os.getpid(),
            state=WorkerState.STARTING,
            branch=self.branch,
        )
        
        self._lock_manager = FileLockManager(root / ".sunwell" / "locks")
        self._status_file = root / ".sunwell" / "workers" / f"worker-{worker_id}.json"
    
    async def run(self) -> WorkerResult:
        """Main worker loop.
        
        Returns:
            WorkerResult with completed/failed goal counts.
        """
        try:
            # Setup: checkout worker branch
            await self._setup_branch()
            self._update_status(WorkerState.IDLE)
            
            # Main loop: claim and execute goals
            while True:
                # Find an executable goal
                goal = await self._claim_next_goal()
                
                if goal is None:
                    # No more work
                    break
                
                # Execute the goal
                success = await self._execute_goal(goal)
                
                if success:
                    self.status.goals_completed += 1
                else:
                    self.status.goals_failed += 1
                
                self._update_status(WorkerState.IDLE)
            
            return WorkerResult(
                worker_id=self.worker_id,
                goals_completed=self.status.goals_completed,
                goals_failed=self.status.goals_failed,
                branch=self.branch,
            )
            
        except Exception as e:
            self._update_status(WorkerState.FAILED, error=str(e))
            raise
        finally:
            self._update_status(WorkerState.STOPPED)
    
    async def _claim_next_goal(self) -> Goal | None:
        """Claim the next executable goal from backlog.
        
        Executable means:
        1. Not already claimed by another worker
        2. Dependencies satisfied
        3. No file conflicts with in-progress goals
        """
        self._update_status(WorkerState.CLAIMING)
        
        async with self.backlog_manager.exclusive_access():
            # Get all pending goals
            pending = await self.backlog_manager.get_pending_goals()
            
            for goal in pending:
                # Check if claimable
                if await self._can_claim(goal):
                    # Claim it
                    await self.backlog_manager.claim_goal(
                        goal.id, 
                        worker_id=self.worker_id
                    )
                    return goal
            
            return None  # Nothing available
    
    async def _can_claim(self, goal: Goal) -> bool:
        """Check if this worker can claim a goal.
        
        Checks:
        1. Not already claimed
        2. Dependencies satisfied
        3. Estimated files don't conflict with locked files
        """
        # Already claimed?
        if goal.claimed_by is not None:
            return False
        
        # Dependencies satisfied?
        for dep_id in goal.requires:
            dep_goal = await self.backlog_manager.get_goal(dep_id)
            if dep_goal and dep_goal.status != GoalStatus.COMPLETED:
                return False
        
        # File conflicts?
        estimated_files = await self._estimate_affected_files(goal)
        for file_path in estimated_files:
            if self._lock_manager.is_locked(file_path):
                return False
        
        return True
    
    async def _execute_goal(self, goal: Goal) -> bool:
        """Execute a single goal.
        
        Steps:
        1. Estimate affected files
        2. Acquire file locks
        3. Run agent
        4. Commit changes
        5. Release locks
        6. Mark complete
        """
        self._update_status(WorkerState.EXECUTING, goal_id=goal.id)
        
        try:
            # Estimate files we'll touch
            estimated_files = await self._estimate_affected_files(goal)
            
            # Acquire locks (with timeout)
            locks = await self._lock_manager.acquire_all(
                estimated_files,
                timeout=self.config.lock_timeout_seconds,
            )
            
            try:
                # Execute via AdaptiveAgent
                async for event in self.agent.execute(goal.description):
                    # Handle events (logging, status updates)
                    await self._handle_agent_event(event)
                
                # Commit changes
                self._update_status(WorkerState.COMMITTING)
                await self._commit_changes(goal)
                
                # Mark goal complete
                await self.backlog_manager.mark_complete(goal.id)
                
                return True
                
            finally:
                # Always release locks
                await self._lock_manager.release_all(locks)
                
        except Exception as e:
            # Mark goal failed
            await self.backlog_manager.mark_failed(goal.id, error=str(e))
            return False
    
    async def _estimate_affected_files(self, goal: Goal) -> list[Path]:
        """Estimate which files a goal will touch.
        
        Strategies:
        1. Use goal.scope.affected_paths if specified
        2. Use pattern matching on goal description
        3. Use codebase graph to find related files
        """
        if goal.scope and goal.scope.affected_paths:
            return list(goal.scope.affected_paths)
        
        # Pattern matching heuristics
        files = []
        description = goal.description.lower()
        
        # "test for X" → tests/test_X.py
        if "test" in description:
            for match in re.finditer(r"test(?:s)?\s+(?:for\s+)?(\w+)", description):
                module = match.group(1)
                files.append(Path(f"tests/test_{module}.py"))
        
        # "fix X.py" → X.py
        for match in re.finditer(r"(\w+\.py)", description):
            files.append(Path(match.group(1)))
        
        return files
    
    async def _commit_changes(self, goal: Goal) -> str:
        """Commit changes for a completed goal.
        
        Returns commit SHA.
        """
        # Stage all changes
        await run_git(self.root, ["add", "-A"])
        
        # Check if anything to commit
        result = await run_git(self.root, ["status", "--porcelain"])
        if not result.strip():
            return ""  # No changes
        
        # Commit with structured message
        commit_msg = f"""sunwell: {goal.title}

Goal ID: {goal.id}
Worker: {self.worker_id}
Category: {goal.category}

{goal.description[:200]}
"""
        await run_git(self.root, ["commit", "-m", commit_msg])
        
        # Get commit SHA
        sha = await run_git(self.root, ["rev-parse", "HEAD"])
        return sha.strip()
    
    async def _setup_branch(self) -> None:
        """Create and checkout worker branch."""
        # Create branch from current HEAD
        await run_git(self.root, ["checkout", "-b", self.branch])
    
    def _update_status(
        self, 
        state: WorkerState, 
        goal_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update worker status file."""
        self.status.state = state
        self.status.last_heartbeat = datetime.now()
        
        if goal_id is not None:
            self.status.current_goal_id = goal_id
        if error is not None:
            self.status.error_message = error
        
        # Write atomically
        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._status_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self.status), default=str))
        tmp.rename(self._status_file)
```

---

### 2. File Lock Manager

```python
import fcntl
import os
import time
from dataclasses import dataclass
from pathlib import Path
from contextlib import asynccontextmanager


@dataclass(frozen=True, slots=True)
class FileLock:
    """An acquired file lock."""
    
    path: Path
    lock_file: Path
    fd: int


class FileLockManager:
    """Manages advisory file locks for coordinating access.
    
    Uses flock() for advisory locking — works across processes on same machine.
    Handles stale lock cleanup for crashed workers.
    """
    
    def __init__(
        self, 
        locks_dir: Path, 
        stale_threshold_seconds: float = 60.0,
    ):
        self.locks_dir = locks_dir
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.stale_threshold_seconds = stale_threshold_seconds
        self._held_locks: dict[Path, FileLock] = {}
    
    def _lock_path(self, file_path: Path) -> Path:
        """Get lock file path for a given source file."""
        # Flatten path: src/auth.py → src_auth.py.lock
        flat_name = str(file_path).replace("/", "_").replace("\\", "_")
        return self.locks_dir / "files" / f"{flat_name}.lock"
    
    def is_locked(self, file_path: Path) -> bool:
        """Check if a file is locked by another process.
        
        Non-blocking check using LOCK_NB.
        Also cleans up stale locks from crashed workers.
        """
        lock_path = self._lock_path(file_path)
        
        if not lock_path.exists():
            return False
        
        # Check for stale lock (file older than threshold)
        if self._is_stale_lock(lock_path):
            self._cleanup_stale_lock(lock_path)
            return False
        
        try:
            fd = os.open(str(lock_path), os.O_RDONLY)
            try:
                # Try non-blocking lock
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Got lock → file was not locked
                fcntl.flock(fd, fcntl.LOCK_UN)
                return False
            except BlockingIOError:
                # Could not get lock → file is locked
                return True
            finally:
                os.close(fd)
        except FileNotFoundError:
            return False
    
    def _is_stale_lock(self, lock_path: Path) -> bool:
        """Check if a lock file is stale (no active holder).
        
        A lock is stale if:
        1. The lock file exists but no process holds flock on it
        2. AND it's older than stale_threshold_seconds
        """
        try:
            mtime = lock_path.stat().st_mtime
            age = time.time() - mtime
            return age > self.stale_threshold_seconds
        except FileNotFoundError:
            return False
    
    def _cleanup_stale_lock(self, lock_path: Path) -> None:
        """Remove a stale lock file."""
        try:
            # Double-check we can acquire the lock (no active holder)
            fd = os.open(str(lock_path), os.O_RDONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                # Successfully locked → no holder → safe to delete
                lock_path.unlink(missing_ok=True)
            except BlockingIOError:
                # Active holder exists, not stale
                pass
            finally:
                os.close(fd)
        except FileNotFoundError:
            pass
    
    async def acquire(
        self, 
        file_path: Path, 
        timeout: float = 30.0,
    ) -> FileLock:
        """Acquire lock on a file with timeout.
        
        Raises TimeoutError if lock cannot be acquired.
        """
        lock_path = self._lock_path(file_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create or open lock file
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        
        start = asyncio.get_event_loop().time()
        
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Got the lock
                lock = FileLock(path=file_path, lock_file=lock_path, fd=fd)
                self._held_locks[file_path] = lock
                return lock
            except BlockingIOError:
                # Lock held by another process
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    os.close(fd)
                    raise TimeoutError(f"Timeout acquiring lock for {file_path}")
                
                # Wait and retry
                await asyncio.sleep(0.1)
    
    async def acquire_all(
        self,
        file_paths: list[Path],
        timeout: float = 30.0,
    ) -> list[FileLock]:
        """Acquire locks on multiple files.
        
        Acquires in sorted order to prevent deadlocks.
        If any lock fails, releases all acquired locks.
        """
        # Sort to prevent deadlocks
        sorted_paths = sorted(file_paths, key=str)
        acquired = []
        
        try:
            for path in sorted_paths:
                lock = await self.acquire(path, timeout=timeout)
                acquired.append(lock)
            return acquired
        except Exception:
            # Release all on failure
            await self.release_all(acquired)
            raise
    
    async def release(self, lock: FileLock) -> None:
        """Release a file lock."""
        if lock.path in self._held_locks:
            del self._held_locks[lock.path]
        
        fcntl.flock(lock.fd, fcntl.LOCK_UN)
        os.close(lock.fd)
    
    async def release_all(self, locks: list[FileLock]) -> None:
        """Release multiple locks."""
        for lock in locks:
            try:
                await self.release(lock)
            except Exception:
                pass  # Best effort
```

---

### 3. Coordinator

```python
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Process, Queue
from pathlib import Path
import signal

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of merging worker branches."""
    
    merged: list[str]
    """Branches that were successfully merged."""
    
    conflicts: list[str]
    """Branches with merge conflicts (need human review)."""


@dataclass
class MultiInstanceConfig:
    """Configuration for multi-instance execution."""
    
    num_workers: int = 4
    """Number of worker processes."""
    
    lock_timeout_seconds: float = 30.0
    """Timeout for acquiring file locks."""
    
    worker_timeout_seconds: float = 3600.0
    """Maximum time for a single worker run (1 hour)."""
    
    merge_strategy: Literal["rebase", "squash"] = "rebase"
    """How to merge worker branches."""
    
    auto_merge: bool = True
    """Automatically merge clean branches."""
    
    cleanup_branches: bool = True
    """Delete worker branches after merge."""
    
    heartbeat_interval_seconds: float = 5.0
    """How often workers report status."""
    
    max_retries_per_goal: int = 2
    """How many times to retry a failed goal."""


@dataclass
class CoordinatorResult:
    """Result of multi-instance execution."""
    
    total_goals: int
    completed: int
    failed: int
    skipped: int
    
    duration_seconds: float
    workers_used: int
    
    merged_branches: list[str]
    conflict_branches: list[str]
    
    errors: list[str]


class Coordinator:
    """Orchestrates multiple worker processes.
    
    Responsibilities:
    1. Spawn worker processes
    2. Monitor worker health
    3. Handle worker failures
    4. Merge worker branches
    5. Report results
    """
    
    def __init__(
        self,
        root: Path,
        backlog_manager: BacklogManager,
        config: MultiInstanceConfig,
    ):
        self.root = root
        self.backlog_manager = backlog_manager
        self.config = config
        
        self._workers: dict[int, Process] = {}
        self._result_queue: Queue = Queue()
        self._base_branch: str = ""
    
    async def execute(self) -> CoordinatorResult:
        """Run multi-instance execution.
        
        Returns:
            CoordinatorResult with execution summary.
        """
        start_time = datetime.now()
        
        try:
            # Phase 1: Setup
            await self._setup()
            
            # Phase 2: Spawn and monitor workers
            await self._run_workers()
            
            # Phase 3: Collect results
            worker_results = self._collect_results()
            
            # Phase 4: Merge branches
            merge_result = await self._merge_branches(worker_results)
            
            # Phase 5: Cleanup
            if self.config.cleanup_branches:
                await self._cleanup_branches(worker_results)
            
            return CoordinatorResult(
                total_goals=sum(r.goals_completed + r.goals_failed for r in worker_results),
                completed=sum(r.goals_completed for r in worker_results),
                failed=sum(r.goals_failed for r in worker_results),
                skipped=0,  # TODO: track skipped
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                workers_used=len(worker_results),
                merged_branches=merge_result.merged,
                conflict_branches=merge_result.conflicts,
                errors=[],
            )
            
        except Exception as e:
            return CoordinatorResult(
                total_goals=0,
                completed=0,
                failed=0,
                skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                workers_used=0,
                merged_branches=[],
                conflict_branches=[],
                errors=[str(e)],
            )
        finally:
            await self._terminate_all_workers()
    
    async def _setup(self) -> None:
        """Setup for multi-instance execution."""
        # Record base branch
        self._base_branch = (await run_git(self.root, ["branch", "--show-current"])).strip()
        
        # Ensure clean working directory
        status = await run_git(self.root, ["status", "--porcelain"])
        if status.strip():
            raise RuntimeError("Working directory not clean. Commit or stash changes first.")
        
        # Create locks directory
        (self.root / ".sunwell" / "locks").mkdir(parents=True, exist_ok=True)
        (self.root / ".sunwell" / "workers").mkdir(parents=True, exist_ok=True)
    
    async def _run_workers(self) -> None:
        """Spawn and monitor worker processes."""
        # Spawn workers
        for worker_id in range(1, self.config.num_workers + 1):
            process = Process(
                target=_worker_entry,  # Module-level function
                args=(
                    worker_id,
                    self.root,
                    self.config,
                    self._result_queue,
                ),
            )
            process.start()
            self._workers[worker_id] = process
        
        # Monitor until all complete
        await self._monitor_workers()


def _worker_entry(
    worker_id: int,
    root: Path,
    config: MultiInstanceConfig,
    result_queue: Queue,
) -> None:
    """Entry point for worker process (module-level for pickling).
    
    Must be a top-level function because multiprocessing pickles it.
    """
    import asyncio
    
    # Setup signal handling for graceful shutdown
    shutdown_requested = False
    
    def handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
    
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    async def _run():
        # Each worker needs its own instances (fresh per process)
        backlog = BacklogManager(root)
        agent = AdaptiveAgent(
            model=create_model(),  # Fresh model instance
            cwd=root,
        )
        
        worker = WorkerProcess(
            worker_id=worker_id,
            root=root,
            backlog_manager=backlog,
            agent=agent,
            config=config,
        )
        
        result = await worker.run()
        result_queue.put(result)
    
    asyncio.run(_run())
    
    async def _monitor_workers(self) -> None:
        """Monitor worker processes until all complete."""
        while any(p.is_alive() for p in self._workers.values()):
            # Check for stuck workers
            for worker_id, process in self._workers.items():
                status_file = self.root / ".sunwell" / "workers" / f"worker-{worker_id}.json"
                if status_file.exists():
                    status = json.loads(status_file.read_text())
                    last_heartbeat = datetime.fromisoformat(status["last_heartbeat"])
                    
                    # Worker stuck?
                    if (datetime.now() - last_heartbeat).total_seconds() > 60:
                        logger.warning(f"Worker {worker_id} appears stuck")
            
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
    
    def _collect_results(self) -> list[WorkerResult]:
        """Collect results from all workers."""
        results = []
        while not self._result_queue.empty():
            results.append(self._result_queue.get())
        return results
    
    async def _merge_branches(self, worker_results: list[WorkerResult]) -> MergeResult:
        """Merge worker branches back to base.
        
        Strategy:
        1. Sort branches by first commit timestamp (deterministic order)
        2. For each branch, rebase it onto current base, then fast-forward base
        3. If conflict, mark for human review and skip
        4. Base accumulates all clean merges
        """
        merged = []
        conflicts = []
        
        # Ensure we're on base branch
        await run_git(self.root, ["checkout", self._base_branch])
        
        # Sort by first commit time for deterministic ordering
        branches_with_times: list[tuple[str, datetime]] = []
        for result in worker_results:
            if result.goals_completed > 0:
                start_time = await self._get_branch_start_time(result.branch)
                branches_with_times.append((result.branch, start_time))
        
        branches = [b for b, _ in sorted(branches_with_times, key=lambda x: x[1])]
        
        for branch in branches:
            try:
                # Rebase worker branch onto current base (updates worker branch)
                await run_git(self.root, ["checkout", branch])
                await run_git(self.root, ["rebase", self._base_branch])
                
                # Fast-forward base to include worker's changes
                await run_git(self.root, ["checkout", self._base_branch])
                await run_git(self.root, ["merge", "--ff-only", branch])
                
                merged.append(branch)
            except subprocess.CalledProcessError:
                # Conflict detected during rebase
                await run_git(self.root, ["rebase", "--abort"])
                await run_git(self.root, ["checkout", self._base_branch])
                conflicts.append(branch)
                logger.warning(f"Merge conflict in {branch}, marked for review")
        
        return MergeResult(merged=merged, conflicts=conflicts)
    
    async def _cleanup_branches(self, worker_results: list[WorkerResult]) -> None:
        """Delete worker branches."""
        for result in worker_results:
            try:
                await run_git(self.root, ["branch", "-D", result.branch])
            except Exception:
                pass  # Best effort
    
    async def _get_branch_start_time(self, branch: str) -> datetime:
        """Get the timestamp of the first commit on a branch.
        
        Used for deterministic merge ordering.
        """
        result = await run_git(
            self.root,
            ["log", branch, "--format=%cI", "--reverse", "-1"],
        )
        return datetime.fromisoformat(result.strip())
    
    async def _terminate_all_workers(self) -> None:
        """Terminate all worker processes."""
        for process in self._workers.values():
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
```

---

### 4. Goal Dependency Tracker

```python
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GoalDependencyGraph:
    """Tracks dependencies between goals for parallel scheduling.
    
    Two types of dependencies:
    1. Explicit: Goal A requires Goal B (from goal.requires)
    2. Implicit: Goal A and B touch same files (detected at planning time)
    """
    
    # goal_id → set of goal_ids it depends on
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    
    # goal_id → set of goal_ids that depend on it
    dependents: dict[str, set[str]] = field(default_factory=dict)
    
    # goal_id → estimated file paths
    file_mapping: dict[str, set[Path]] = field(default_factory=dict)
    
    # goal_id → set of conflicting goal_ids (can't run simultaneously)
    _conflicts: dict[str, set[str]] = field(default_factory=dict)
    
    @classmethod
    def from_backlog(cls, backlog: Backlog) -> GoalDependencyGraph:
        """Build dependency graph from backlog.
        
        Analyzes:
        1. Explicit dependencies (goal.requires)
        2. File overlap (goals touching same files)
        """
        graph = cls()
        
        # Add explicit dependencies
        for goal in backlog.goals.values():
            graph.dependencies[goal.id] = set(goal.requires)
            for dep_id in goal.requires:
                graph.dependents.setdefault(dep_id, set()).add(goal.id)
        
        # Estimate files per goal
        for goal in backlog.goals.values():
            graph.file_mapping[goal.id] = graph._estimate_affected_files(goal)
        
        # Add implicit dependencies from file overlap
        goal_ids = list(backlog.goals.keys())
        for i, goal_a_id in enumerate(goal_ids):
            for goal_b_id in goal_ids[i+1:]:
                files_a = graph.file_mapping.get(goal_a_id, set())
                files_b = graph.file_mapping.get(goal_b_id, set())
                
                if files_a & files_b:  # Overlap
                    # Add bidirectional soft dependency
                    # (not hard dep, just scheduling hint)
                    graph.mark_conflict(goal_a_id, goal_b_id)
        
        return graph
    
    def get_ready_goals(self, completed: set[str]) -> list[str]:
        """Get goals that are ready to execute.
        
        A goal is ready if all its dependencies are in `completed`.
        """
        ready = []
        for goal_id, deps in self.dependencies.items():
            if goal_id not in completed:
                if deps <= completed:  # All deps satisfied
                    ready.append(goal_id)
        return ready
    
    def mark_conflict(self, goal_a: str, goal_b: str) -> None:
        """Mark two goals as conflicting (can't run simultaneously)."""
        # Store in conflicts set for scheduling
        self._conflicts.setdefault(goal_a, set()).add(goal_b)
        self._conflicts.setdefault(goal_b, set()).add(goal_a)
    
    def can_run_parallel(self, goal_a: str, goal_b: str) -> bool:
        """Check if two goals can run in parallel."""
        # Check explicit dependency
        if goal_a in self.dependencies.get(goal_b, set()):
            return False
        if goal_b in self.dependencies.get(goal_a, set()):
            return False
        
        # Check file conflict
        if goal_b in self._conflicts.get(goal_a, set()):
            return False
        
        return True
    
    def _estimate_affected_files(self, goal: Goal) -> set[Path]:
        """Estimate which files a goal will touch.
        
        Uses (in priority order):
        1. goal.scope.allowed_paths if specified
        2. Pattern matching on goal description
        """
        files: set[Path] = set()
        
        # Use scope if available
        if goal.scope and goal.scope.allowed_paths:
            return set(goal.scope.allowed_paths)
        
        # Pattern matching heuristics
        description = goal.description.lower()
        
        # "test for X" → tests/test_X.py
        if "test" in description:
            for match in re.finditer(r"test(?:s)?\s+(?:for\s+)?(\w+)", description):
                module = match.group(1)
                files.add(Path(f"tests/test_{module}.py"))
        
        # "fix X.py" or "in X.py" → X.py
        for match in re.finditer(r"(\w+\.py)", description):
            files.add(Path(match.group(1)))
        
        return files
```

---

### 5. Resource Governor

```python
@dataclass
class ResourceLimits:
    """Resource limits for parallel execution."""
    
    max_concurrent_llm_calls: int = 2
    """Maximum concurrent LLM API calls (for rate limiting)."""
    
    max_memory_per_worker_mb: int = 2048
    """Maximum memory per worker process."""
    
    max_total_memory_mb: int = 8192
    """Maximum total memory for all workers."""
    
    llm_requests_per_minute: int = 60
    """LLM API rate limit."""


class ResourceGovernor:
    """Manages shared resources across worker processes.
    
    Controls:
    1. LLM API rate limiting
    2. Memory usage tracking
    3. Disk I/O throttling (future)
    """
    
    def __init__(self, limits: ResourceLimits, root: Path):
        self.limits = limits
        self.root = root
        
        # Semaphore file for LLM concurrency
        self._resources_dir = root / ".sunwell" / "resources"
        self._resources_dir.mkdir(parents=True, exist_ok=True)
        self._llm_semaphore_path = self._resources_dir / "llm_semaphore"
        self._llm_lock_path = self._resources_dir / "llm_semaphore.lock"
    
    @asynccontextmanager
    async def llm_slot(self):
        """Acquire a slot for LLM API call.
        
        Blocks if max_concurrent_llm_calls exceeded.
        """
        await self._acquire_llm_slot()
        try:
            yield
        finally:
            await self._release_llm_slot()
    
    async def _acquire_llm_slot(self) -> None:
        """Acquire LLM semaphore slot with proper locking.
        
        Uses flock to ensure atomic read-modify-write.
        """
        while True:
            # Acquire exclusive lock for atomic operation
            fd = os.open(str(self._llm_lock_path), os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                
                count = self._read_llm_count()
                if count < self.limits.max_concurrent_llm_calls:
                    self._write_llm_count(count + 1)
                    return
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            
            # Slot not available, wait and retry
            await asyncio.sleep(0.1)
    
    async def _release_llm_slot(self) -> None:
        """Release LLM semaphore slot with proper locking."""
        fd = os.open(str(self._llm_lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            count = self._read_llm_count()
            self._write_llm_count(max(0, count - 1))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    
    def _read_llm_count(self) -> int:
        """Read current LLM slot count."""
        if not self._llm_semaphore_path.exists():
            return 0
        try:
            return int(self._llm_semaphore_path.read_text().strip())
        except (ValueError, FileNotFoundError):
            return 0
    
    def _write_llm_count(self, count: int) -> None:
        """Write LLM slot count atomically."""
        tmp = self._llm_semaphore_path.with_suffix(".tmp")
        tmp.write_text(str(count))
        tmp.rename(self._llm_semaphore_path)
    
    def check_memory(self) -> bool:
        """Check if memory usage is within limits."""
        import psutil
        
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        return memory_mb < self.limits.max_memory_per_worker_mb
    
    def get_recommended_workers(self) -> int:
        """Recommend number of workers based on available resources.
        
        Considers:
        - CPU cores
        - Available memory
        - LLM rate limits
        """
        import psutil
        
        cpu_cores = psutil.cpu_count()
        available_memory_mb = psutil.virtual_memory().available / 1024 / 1024
        
        # One worker per core, max
        by_cpu = cpu_cores
        
        # Memory: each worker needs ~2GB
        by_memory = int(available_memory_mb / self.limits.max_memory_per_worker_mb)
        
        # LLM: don't exceed rate limits
        by_llm = self.limits.max_concurrent_llm_calls
        
        return max(1, min(by_cpu, by_memory, by_llm))
```

---

## Configuration

```yaml
# sunwell.yaml or pyproject.toml [tool.sunwell.parallel]

parallel:
  enabled: true
  
  # Worker configuration
  workers:
    count: 4                    # Default worker count (or "auto")
    timeout_seconds: 3600       # Max time per worker run
    heartbeat_interval: 5       # Status update frequency
    max_retries: 2              # Retries per failed goal
  
  # Locking configuration
  locks:
    timeout_seconds: 30         # Max wait for file lock
    stale_threshold_seconds: 60 # Lock considered stale after this
  
  # Merge configuration
  merge:
    strategy: "rebase"          # "rebase" or "squash"
    auto_merge: true            # Automatically merge clean branches
    cleanup_branches: true      # Delete worker branches after merge
  
  # Resource limits
  resources:
    max_concurrent_llm: 2       # Max simultaneous LLM calls
    max_memory_per_worker_mb: 2048
    max_total_memory_mb: 8192
  
  # Scheduling
  scheduling:
    conflict_strategy: "serialize"  # "serialize" or "different_workers"
    priority_boost_external: 0.2    # Priority boost for external goals
```

---

## CLI Integration

```bash
# Basic parallel execution
sunwell backlog execute --workers 4

# Auto-detect optimal worker count
sunwell backlog execute --workers auto

# Limit to specific goals
sunwell backlog execute --workers 4 --category fix,test

# Dry run (show what would execute in parallel)
sunwell backlog execute --workers 4 --dry-run

# Monitor running workers
sunwell workers status

# View worker logs
sunwell workers logs 1          # Worker 1 logs
sunwell workers logs --all      # All workers

# Manual worker management
sunwell workers stop 1          # Stop worker 1
sunwell workers stop --all      # Stop all workers

# Merge management
sunwell workers merge           # Merge all clean branches
sunwell workers merge --branch sunwell/worker-1
sunwell workers conflicts       # Show branches with conflicts

# Resource monitoring
sunwell workers resources       # Show resource usage
```

### Example Session

```
$ sunwell backlog execute --workers 4

🚀 Starting parallel execution with 4 workers

📊 Backlog Analysis:
   Total goals: 15
   Parallelizable: 12 (80%)
   Sequential (conflicts): 3

🔧 Workers:
   Worker 1: starting → sunwell/worker-1
   Worker 2: starting → sunwell/worker-2
   Worker 3: starting → sunwell/worker-3
   Worker 4: starting → sunwell/worker-4

───────────────────────────────────────────────────────────────

[00:00:05] Worker 1: Claimed "Add tests for auth.py"
[00:00:05] Worker 2: Claimed "Fix typo in README"
[00:00:06] Worker 3: Claimed "Add docstrings to utils.py"
[00:00:06] Worker 4: Claimed "Update dependencies"

[00:00:32] Worker 2: ✅ Completed "Fix typo in README"
[00:00:33] Worker 2: Claimed "Add type hints to models.py"

[00:01:45] Worker 4: ✅ Completed "Update dependencies"
[00:01:46] Worker 4: Claimed "Fix lint warnings in api/"

[00:02:12] Worker 1: ✅ Completed "Add tests for auth.py"
[00:02:13] Worker 1: Claimed "Refactor auth.py" (waiting for lock...)

[00:02:30] Worker 3: ✅ Completed "Add docstrings to utils.py"
[00:02:31] Worker 3: Claimed "Add tests for utils.py"

[00:03:15] Worker 2: ✅ Completed "Add type hints to models.py"
...

───────────────────────────────────────────────────────────────

📈 Progress: 15/15 goals completed

🔀 Merging branches:
   ✅ sunwell/worker-1 (4 commits)
   ✅ sunwell/worker-2 (5 commits)
   ✅ sunwell/worker-3 (3 commits)
   ✅ sunwell/worker-4 (3 commits)

🎉 Parallel execution complete!

   Duration: 8m 32s (vs ~38m serial)
   Speedup: 4.5×
   Goals completed: 15
   Goals failed: 0
   Branches merged: 4
   Conflicts: 0

Run `git log --oneline -20` to see changes.
```

---

## Integration with Existing Systems

### With RFC-046 (Autonomous Backlog)

```python
# BacklogManager extended for multi-instance

class BacklogManager:
    # ... existing methods ...
    
    async def claim_goal(self, goal_id: str, worker_id: int) -> bool:
        """Claim a goal for a worker.
        
        Atomic operation using file locking.
        """
        async with self.exclusive_access():
            goal = self.backlog.goals.get(goal_id)
            if goal is None or goal.claimed_by is not None:
                return False
            
            self.backlog.goals[goal_id] = dataclasses.replace(
                goal,
                claimed_by=worker_id,
                claimed_at=datetime.now(),
            )
            self._save()
            return True
    
    @asynccontextmanager
    async def exclusive_access(self):
        """Acquire exclusive access to backlog.
        
        Uses flock for cross-process safety.
        """
        lock_path = self._path / "backlog.lock"
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
```

### With RFC-048 (Autonomy Guardrails)

```python
# Guardrails check happens per-worker

class WorkerProcess:
    async def _execute_goal(self, goal: Goal) -> bool:
        # Check guardrails before execution
        can_execute, reason = await self.guardrails.check_goal(goal)
        
        if not can_execute:
            await self.backlog_manager.mark_blocked(
                goal.id, 
                reason=f"Guardrails: {reason}"
            )
            return False
        
        # ... proceed with execution
```

### With RFC-049 (External Integration)

```python
# External events boost priority for parallel scheduling

class GoalDependencyGraph:
    def get_priority_ordered_goals(self) -> list[str]:
        """Get goals sorted by priority.
        
        External goals get priority boost.
        """
        goals = []
        for goal_id, goal in self.backlog.goals.items():
            priority = goal.priority
            
            # Boost external goals
            if goal.external_ref:
                priority += self.config.priority_boost_external
            
            goals.append((goal_id, priority))
        
        return [g[0] for g in sorted(goals, key=lambda x: -x[1])]
```

---

## Backwards Compatibility

### Goal Dataclass Extension

Add optional `claimed_by` and `claimed_at` fields:

```python
@dataclass(frozen=True, slots=True)
class Goal:
    # ... existing fields ...
    
    claimed_by: int | None = None
    """Worker ID that claimed this goal (None = unclaimed)."""
    
    claimed_at: datetime | None = None
    """When the goal was claimed."""
```

Migration: Existing backlogs will deserialize with `None` defaults.

### BacklogManager Extensions

New methods (additive, no breaking changes):
- `claim_goal(goal_id, worker_id)`
- `exclusive_access()` context manager
- `get_pending_goals()`
- `mark_blocked(goal_id, reason)`

---

## Risks and Mitigations

### Risk 1: Deadlocks

**Problem**: Workers wait on each other's locks forever.

**Mitigation**:
- Acquire locks in sorted order (prevents circular wait)
- Lock timeout with automatic release
- Coordinator monitors for stuck workers

### Risk 2: Merge Conflicts

**Problem**: Worker branches conflict at merge time.

**Mitigation**:
- File locking prevents most conflicts
- Dependency analysis serializes conflicting goals
- Clear reporting of conflict branches for human review
- Conflict branches preserved, not deleted

### Risk 3: Resource Exhaustion

**Problem**: Too many workers exhaust memory/CPU.

**Mitigation**:
- ResourceGovernor enforces limits
- `--workers auto` detects optimal count
- Memory monitoring with graceful degradation
- LLM rate limiting across workers

### Risk 4: Partial Failures

**Problem**: Some workers crash, leaving work incomplete.

**Mitigation**:
- Workers update status files with heartbeats
- Coordinator detects stuck workers
- Unclaimed goals remain available
- Failed goals marked for retry

### Risk 5: Branch Pollution

**Problem**: Worker branches accumulate in repo.

**Mitigation**:
- Automatic cleanup after merge
- Prefix `sunwell/worker-*` clearly identifies branches
- Manual cleanup command available

---

## Testing Strategy

### Unit Tests

```python
class TestFileLockManager:
    async def test_prevents_concurrent_access(self):
        """Two processes can't lock same file."""
        manager1 = FileLockManager(tmp_path)
        manager2 = FileLockManager(tmp_path)
        
        lock1 = await manager1.acquire(Path("test.py"))
        
        with pytest.raises(TimeoutError):
            await manager2.acquire(Path("test.py"), timeout=0.5)
        
        await manager1.release(lock1)
        lock2 = await manager2.acquire(Path("test.py"))
        assert lock2 is not None


class TestGoalDependencyGraph:
    def test_detects_file_conflicts(self):
        """Goals touching same files are marked as conflicting."""
        graph = GoalDependencyGraph.from_backlog(
            Backlog(goals={
                "a": Goal(id="a", description="Fix auth.py"),
                "b": Goal(id="b", description="Refactor auth.py"),
            })
        )
        
        assert not graph.can_run_parallel("a", "b")
    
    def test_independent_goals_parallel(self):
        """Goals touching different files can run parallel."""
        graph = GoalDependencyGraph.from_backlog(
            Backlog(goals={
                "a": Goal(id="a", description="Fix auth.py"),
                "b": Goal(id="b", description="Add tests for utils.py"),
            })
        )
        
        assert graph.can_run_parallel("a", "b")
```

### Integration Tests

```python
class TestMultiInstance:
    async def test_parallel_execution(self, sample_project):
        """Multiple workers execute goals in parallel."""
        coordinator = Coordinator(
            root=sample_project,
            config=MultiInstanceConfig(num_workers=2),
        )
        
        result = await coordinator.execute()
        
        assert result.completed > 0
        assert result.workers_used == 2
    
    async def test_conflict_serialization(self, sample_project):
        """Conflicting goals run sequentially."""
        # Create two goals touching same file
        backlog = BacklogManager(sample_project)
        await backlog.add_goal(Goal(id="a", description="Fix auth.py"))
        await backlog.add_goal(Goal(id="b", description="Refactor auth.py"))
        
        coordinator = Coordinator(
            root=sample_project,
            config=MultiInstanceConfig(num_workers=2),
        )
        
        result = await coordinator.execute()
        
        # Both should complete (serialized, not parallel)
        assert result.completed == 2
        assert len(result.conflict_branches) == 0
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

- [ ] `FileLockManager` — Advisory file locking
- [ ] `WorkerStatus` and status file management
- [ ] `GoalDependencyGraph` — Conflict detection
- [ ] BacklogManager extensions (`claim_goal`, `exclusive_access`)
- [ ] Unit tests

### Phase 2: Worker Process (Week 2)

- [ ] `WorkerProcess` — Main worker loop
- [ ] Goal claiming logic
- [ ] File lock acquisition during execution
- [ ] Commit management per worker
- [ ] Integration with `AdaptiveAgent`

### Phase 3: Coordinator (Week 3)

- [ ] `Coordinator` — Process spawning and monitoring
- [ ] Worker health monitoring (heartbeats)
- [ ] Result collection
- [ ] Branch merging logic
- [ ] CLI: `sunwell backlog execute --workers N`

### Phase 4: Resource Management (Week 4)

- [ ] `ResourceGovernor` — LLM rate limiting
- [ ] Memory monitoring
- [ ] Auto-detection of optimal workers
- [ ] CLI: `sunwell workers status`, `sunwell workers resources`

### Phase 5: Polish & Testing (Week 5)

- [ ] End-to-end integration tests
- [ ] Performance benchmarks
- [ ] Documentation
- [ ] Edge case handling (crashes, timeouts)

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Speedup | > 2× with 4 workers | Time to complete 20 goals |
| Conflict rate | < 5% | Branches with merge conflicts |
| Worker utilization | > 60% | Time spent executing vs waiting |
| Crash recovery | 100% | Work continues after worker crash |
| Memory overhead | < 500MB per worker | Peak memory usage |

---

## Open Questions

### Q1: Optimal Worker Count

**Question**: How many workers should `--workers auto` select?

**Proposed answer**: `min(cpu_cores, available_memory / 2GB, llm_rate_limit / 20)`

### Q2: GPU Sharing

**Question**: How do workers share GPU for local inference?

**Proposed answer**: First version uses API (Ollama handles multiplexing). GPU sharing is future work.

### Q3: Cross-Machine Coordination

**Question**: Can workers run on different machines?

**Proposed answer**: Not in this RFC. Requires distributed locking (Redis/etcd). Future RFC-052.

---

## Future Work

1. **Distributed execution** — Workers on multiple machines
2. **GPU multiplexing** — vLLM batching for local inference
3. **Smart scheduling** — ML-based goal ordering
4. **Speculative execution** — Start conflicting goals, discard loser
5. **Checkpoint/resume** — Resume partial execution after interruption

---

## Summary

Multi-Instance Coordination enables parallel autonomous execution through:

| Component | Purpose |
|-----------|---------|
| **Coordinator** | Spawns workers, monitors health, merges results |
| **WorkerProcess** | Claims goals, executes, commits to isolated branch |
| **FileLockManager** | Prevents concurrent file access |
| **GoalDependencyGraph** | Detects conflicts, enables parallel scheduling |
| **ResourceGovernor** | Manages LLM rate limits, memory |

### The Result

```
Before (Serial):                    After (Parallel, 4 workers):
────────────────                    ────────────────────────────
20 goals × 5 min = 100 min          20 goals / 4 = ~25 min
CPU utilization: 20%                CPU utilization: 60%
LLM utilization: 30%                LLM utilization: 70%

"Let it run overnight"              "Done before lunch"
```

**N agents, one codebase, zero conflicts.**

---

## References

### RFCs

- RFC-046: Autonomous Backlog — `src/sunwell/backlog/`
- RFC-048: Autonomy Guardrails — `src/sunwell/guardrails/`
- RFC-049: External Integration — `src/sunwell/external/`

### Implementation Files (to be created)

```
src/sunwell/parallel/
├── __init__.py
├── types.py              # WorkerStatus, WorkerResult, etc.
├── coordinator.py        # Coordinator process
├── worker.py             # WorkerProcess
├── locks.py              # FileLockManager
├── dependencies.py       # GoalDependencyGraph
├── resources.py          # ResourceGovernor
└── config.py             # MultiInstanceConfig

# Modified files
src/sunwell/backlog/goals.py      # Add claimed_by, claimed_at
src/sunwell/backlog/manager.py    # Add claim_goal(), exclusive_access()
src/sunwell/cli/main.py           # Add 'workers' command group
```

---

*Last updated: 2026-01-19 (Revision 2)*
