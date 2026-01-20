"""Tests for Multi-Instance Coordination (RFC-051)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.backlog.goals import Goal, GoalScope
from sunwell.backlog.manager import Backlog, BacklogManager
from sunwell.parallel import (
    FileLockManager,
    GoalDependencyGraph,
    MergeResult,
    MultiInstanceConfig,
    ResourceGovernor,
    ResourceLimits,
    WorkerResult,
    WorkerState,
    WorkerStatus,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def tmp_locks_dir(tmp_path: Path) -> Path:
    """Create a temporary locks directory."""
    locks_dir = tmp_path / ".sunwell" / "locks"
    locks_dir.mkdir(parents=True)
    return locks_dir


@pytest.fixture
def lock_manager(tmp_locks_dir: Path) -> FileLockManager:
    """Create a FileLockManager for testing."""
    return FileLockManager(tmp_locks_dir, stale_threshold_seconds=1.0)


@pytest.fixture
def sample_goal() -> Goal:
    """Create a sample goal for testing."""
    return Goal(
        id="test-goal-1",
        title="Fix auth.py",
        description="Fix the authentication module",
        source_signals=(),
        priority=0.8,
        estimated_complexity="simple",
        requires=frozenset(),
        category="fix",
        auto_approvable=True,
        scope=GoalScope(max_files=2, max_lines_changed=100),
    )


@pytest.fixture
def sample_goals() -> dict[str, Goal]:
    """Create a set of sample goals for testing."""
    goal1 = Goal(
        id="goal-1",
        title="Fix auth.py",
        description="Fix the authentication module",
        source_signals=(),
        priority=0.8,
        estimated_complexity="simple",
        requires=frozenset(),
        category="fix",
        auto_approvable=True,
        scope=GoalScope(
            max_files=2,
            max_lines_changed=100,
            allowed_paths=frozenset({Path("src/auth.py")}),
        ),
    )

    goal2 = Goal(
        id="goal-2",
        title="Add tests for utils",
        description="Add unit tests for utils.py",
        source_signals=(),
        priority=0.6,
        estimated_complexity="moderate",
        requires=frozenset(),
        category="test",
        auto_approvable=True,
        scope=GoalScope(
            max_files=2,
            max_lines_changed=200,
            allowed_paths=frozenset({Path("tests/test_utils.py")}),
        ),
    )

    goal3 = Goal(
        id="goal-3",
        title="Refactor auth.py",
        description="Refactor the authentication module",
        source_signals=(),
        priority=0.5,
        estimated_complexity="complex",
        requires=frozenset({"goal-1"}),  # Depends on goal-1
        category="refactor",
        auto_approvable=False,
        scope=GoalScope(
            max_files=3,
            max_lines_changed=500,
            allowed_paths=frozenset({Path("src/auth.py"), Path("src/auth_utils.py")}),
        ),
    )

    return {"goal-1": goal1, "goal-2": goal2, "goal-3": goal3}


@pytest.fixture
def sample_backlog(sample_goals: dict[str, Goal]) -> Backlog:
    """Create a sample backlog for testing."""
    return Backlog(
        goals=sample_goals,
        completed=set(),
        in_progress=None,
        blocked={},
    )


# =============================================================================
# FileLockManager Tests
# =============================================================================


class TestFileLockManager:
    """Tests for FileLockManager."""

    def test_init_creates_directory(self, tmp_path: Path):
        """Test that init creates the locks directory."""
        locks_dir = tmp_path / "new_locks"
        FileLockManager(locks_dir)  # Creating the manager creates the directory
        assert locks_dir.exists()

    def test_lock_path_flattens_path(self, lock_manager: FileLockManager):
        """Test that lock path correctly flattens file paths."""
        file_path = Path("src/auth.py")
        lock_path = lock_manager._lock_path(file_path)
        assert "src_auth.py.lock" in str(lock_path)

    def test_is_locked_returns_false_for_unlocked_file(
        self, lock_manager: FileLockManager
    ):
        """Test is_locked returns False for unlocked file."""
        file_path = Path("test.py")
        assert lock_manager.is_locked(file_path) is False

    @pytest.mark.asyncio
    async def test_acquire_creates_lock(self, lock_manager: FileLockManager):
        """Test that acquire creates a lock."""
        file_path = Path("test.py")
        lock = await lock_manager.acquire(file_path, timeout=5.0)

        try:
            assert lock is not None
            assert lock.path == file_path
            assert lock.lock_file.exists()
        finally:
            await lock_manager.release(lock)

    @pytest.mark.asyncio
    async def test_acquire_blocks_second_acquisition(
        self, lock_manager: FileLockManager
    ):
        """Test that a second acquire on same file times out."""
        file_path = Path("test.py")
        lock1 = await lock_manager.acquire(file_path, timeout=5.0)

        try:
            # Second acquire should timeout
            with pytest.raises(TimeoutError):
                await lock_manager.acquire(file_path, timeout=0.2)
        finally:
            await lock_manager.release(lock1)

    @pytest.mark.asyncio
    async def test_release_allows_new_acquisition(
        self, lock_manager: FileLockManager
    ):
        """Test that release allows a new acquisition."""
        file_path = Path("test.py")

        lock1 = await lock_manager.acquire(file_path, timeout=5.0)
        await lock_manager.release(lock1)

        # Should be able to acquire again
        lock2 = await lock_manager.acquire(file_path, timeout=5.0)
        assert lock2 is not None
        await lock_manager.release(lock2)

    @pytest.mark.asyncio
    async def test_acquire_all_acquires_in_sorted_order(
        self, lock_manager: FileLockManager
    ):
        """Test that acquire_all acquires locks in sorted order."""
        files = [Path("c.py"), Path("a.py"), Path("b.py")]
        locks = await lock_manager.acquire_all(files, timeout=5.0)

        try:
            assert len(locks) == 3
            # Should be acquired in sorted order to prevent deadlocks
            assert [lock.path for lock in locks] == sorted(files, key=str)
        finally:
            await lock_manager.release_all(locks)

    @pytest.mark.asyncio
    async def test_acquire_all_releases_on_failure(
        self, lock_manager: FileLockManager, tmp_path: Path
    ):
        """Test that acquire_all releases locks if one fails."""
        # Create another manager to hold a lock
        other_manager = FileLockManager(tmp_path / ".sunwell" / "locks")

        file_a = Path("a.py")
        file_b = Path("b.py")

        # Acquire file_b with other manager
        other_lock = await other_manager.acquire(file_b, timeout=5.0)

        try:
            # This should fail because b.py is locked
            with pytest.raises(TimeoutError):
                await lock_manager.acquire_all([file_a, file_b], timeout=0.2)

            # file_a should have been released (can acquire it)
            lock_a = await lock_manager.acquire(file_a, timeout=0.2)
            assert lock_a is not None
            await lock_manager.release(lock_a)
        finally:
            await other_manager.release(other_lock)

    @pytest.mark.asyncio
    async def test_stale_lock_cleanup(self, tmp_path: Path):
        """Test that stale locks are cleaned up."""
        import time

        locks_dir = tmp_path / ".sunwell" / "locks"
        manager = FileLockManager(locks_dir, stale_threshold_seconds=0.1)

        file_path = Path("test.py")
        lock_path = manager._lock_path(file_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a lock file directly (simulating crashed worker)
        lock_path.write_text("")

        # Wait for it to become stale
        time.sleep(0.2)

        # Should detect as not locked (stale)
        assert manager.is_locked(file_path) is False


# =============================================================================
# GoalDependencyGraph Tests
# =============================================================================


class TestGoalDependencyGraph:
    """Tests for GoalDependencyGraph."""

    def test_from_backlog_creates_graph(self, sample_backlog: Backlog):
        """Test that from_backlog creates a graph."""
        graph = GoalDependencyGraph.from_backlog(sample_backlog)

        assert len(graph.dependencies) == 3
        assert "goal-1" in graph.dependencies
        assert "goal-2" in graph.dependencies
        assert "goal-3" in graph.dependencies

    def test_explicit_dependencies_tracked(self, sample_backlog: Backlog):
        """Test that explicit dependencies are tracked."""
        graph = GoalDependencyGraph.from_backlog(sample_backlog)

        # goal-3 depends on goal-1
        assert "goal-1" in graph.dependencies["goal-3"]

        # goal-1 is a dependent of goal-3
        assert "goal-3" in graph.dependents.get("goal-1", set())

    def test_file_conflicts_detected(self, sample_backlog: Backlog):
        """Test that file conflicts are detected."""
        graph = GoalDependencyGraph.from_backlog(sample_backlog)

        # goal-1 and goal-3 both touch auth.py
        assert "goal-3" in graph._conflicts.get("goal-1", set())
        assert "goal-1" in graph._conflicts.get("goal-3", set())

        # goal-2 doesn't conflict (different files)
        assert "goal-2" not in graph._conflicts.get("goal-1", set())

    def test_get_ready_goals_respects_dependencies(self, sample_backlog: Backlog):
        """Test that get_ready_goals respects dependencies."""
        graph = GoalDependencyGraph.from_backlog(sample_backlog)

        # Initially, goal-1 and goal-2 are ready
        ready = graph.get_ready_goals(completed=set())
        assert "goal-1" in ready
        assert "goal-2" in ready
        assert "goal-3" not in ready  # Depends on goal-1

        # After goal-1 is done, goal-3 becomes ready
        ready = graph.get_ready_goals(completed={"goal-1"})
        assert "goal-3" in ready

    def test_can_run_parallel_checks_dependencies(self, sample_backlog: Backlog):
        """Test that can_run_parallel checks dependencies."""
        graph = GoalDependencyGraph.from_backlog(sample_backlog)

        # goal-1 and goal-2 can run in parallel (no dependency)
        assert graph.can_run_parallel("goal-1", "goal-2") is True

        # goal-1 and goal-3 cannot (dependency + file conflict)
        assert graph.can_run_parallel("goal-1", "goal-3") is False

    def test_can_run_parallel_checks_file_conflicts(self):
        """Test that can_run_parallel checks file conflicts."""
        # Create two goals that conflict on files but have no explicit dependency
        goal_a = Goal(
            id="goal-a",
            title="Edit shared.py",
            description="Edit shared.py",
            source_signals=(),
            priority=0.8,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(allowed_paths=frozenset({Path("shared.py")})),
        )

        goal_b = Goal(
            id="goal-b",
            title="Also edit shared.py",
            description="Also edit shared.py",
            source_signals=(),
            priority=0.6,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(allowed_paths=frozenset({Path("shared.py")})),
        )

        backlog = Backlog(
            goals={"goal-a": goal_a, "goal-b": goal_b},
            completed=set(),
            in_progress=None,
            blocked={},
        )

        graph = GoalDependencyGraph.from_backlog(backlog)

        # They should not be able to run in parallel (file conflict)
        assert graph.can_run_parallel("goal-a", "goal-b") is False

    def test_get_parallelizable_groups(self, sample_backlog: Backlog):
        """Test get_parallelizable_groups returns correct groups."""
        graph = GoalDependencyGraph.from_backlog(sample_backlog)

        groups = graph.get_parallelizable_groups(
            pending=["goal-1", "goal-2", "goal-3"],
            completed=set(),
        )

        # Should have at least one group
        assert len(groups) >= 1

        # goal-1 and goal-2 should be parallelizable
        first_group = groups[0]
        assert "goal-1" in first_group or "goal-2" in first_group

    def test_estimate_affected_files_from_description(self):
        """Test file estimation from goal description."""
        graph = GoalDependencyGraph()

        goal = Goal(
            id="test-goal",
            title="Fix auth.py",
            description="Fix the bug in auth.py and update tests",
            source_signals=(),
            priority=0.8,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),  # No explicit paths
        )

        files = graph._estimate_affected_files(goal)

        # Should detect auth.py from description
        assert any("auth.py" in str(f) for f in files)


# =============================================================================
# ResourceGovernor Tests
# =============================================================================


class TestResourceGovernor:
    """Tests for ResourceGovernor."""

    @pytest.fixture
    def governor(self, tmp_path: Path) -> ResourceGovernor:
        """Create a ResourceGovernor for testing."""
        return ResourceGovernor(ResourceLimits(max_concurrent_llm_calls=2), tmp_path)

    def test_init_creates_directories(self, tmp_path: Path):
        """Test that init creates required directories."""
        ResourceGovernor(ResourceLimits(), tmp_path)
        assert (tmp_path / ".sunwell" / "resources").exists()

    @pytest.mark.asyncio
    async def test_llm_slot_acquires_and_releases(
        self, governor: ResourceGovernor
    ):
        """Test that llm_slot context manager works."""
        initial_count = governor._read_llm_count()
        assert initial_count == 0

        async with governor.llm_slot():
            count_during = governor._read_llm_count()
            assert count_during == 1

        final_count = governor._read_llm_count()
        assert final_count == 0

    @pytest.mark.asyncio
    async def test_llm_slot_respects_limit(self, governor: ResourceGovernor):
        """Test that llm_slot respects max_concurrent_llm_calls."""
        # Acquire two slots (the limit)
        await governor._acquire_llm_slot()
        await governor._acquire_llm_slot()

        count = governor._read_llm_count()
        assert count == 2

        # Clean up
        await governor._release_llm_slot()
        await governor._release_llm_slot()

    def test_reset_clears_count(self, governor: ResourceGovernor):
        """Test that reset clears the LLM count."""
        governor._write_llm_count(5)
        assert governor._read_llm_count() == 5

        governor.reset()
        assert governor._read_llm_count() == 0

    def test_get_recommended_workers(self, governor: ResourceGovernor):
        """Test that get_recommended_workers returns a positive number."""
        recommended = governor.get_recommended_workers()
        assert recommended >= 1
        assert recommended <= governor.limits.max_concurrent_llm_calls


# =============================================================================
# MultiInstanceConfig Tests
# =============================================================================


class TestMultiInstanceConfig:
    """Tests for MultiInstanceConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MultiInstanceConfig()

        assert config.num_workers == 4
        assert config.lock_timeout_seconds == 30.0
        assert config.merge_strategy == "rebase"
        assert config.auto_merge is True
        assert config.cleanup_branches is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MultiInstanceConfig(
            num_workers=8,
            lock_timeout_seconds=60.0,
            merge_strategy="squash",
            auto_merge=False,
        )

        assert config.num_workers == 8
        assert config.lock_timeout_seconds == 60.0
        assert config.merge_strategy == "squash"
        assert config.auto_merge is False


# =============================================================================
# WorkerStatus Tests
# =============================================================================


class TestWorkerStatus:
    """Tests for WorkerStatus."""

    def test_creation(self):
        """Test creating a WorkerStatus."""
        status = WorkerStatus(
            worker_id=1,
            pid=12345,
            state=WorkerState.IDLE,
            branch="sunwell/worker-1",
        )

        assert status.worker_id == 1
        assert status.pid == 12345
        assert status.state == WorkerState.IDLE
        assert status.goals_completed == 0
        assert status.goals_failed == 0

    def test_timestamps_auto_set(self):
        """Test that timestamps are automatically set."""
        status = WorkerStatus(
            worker_id=1,
            pid=12345,
            state=WorkerState.STARTING,
            branch="sunwell/worker-1",
        )

        assert status.started_at is not None
        assert status.last_heartbeat is not None


# =============================================================================
# WorkerResult Tests
# =============================================================================


class TestWorkerResult:
    """Tests for WorkerResult."""

    def test_creation(self):
        """Test creating a WorkerResult."""
        result = WorkerResult(
            worker_id=1,
            goals_completed=5,
            goals_failed=1,
            branch="sunwell/worker-1",
            duration_seconds=120.5,
            commit_shas=["abc123", "def456"],
        )

        assert result.worker_id == 1
        assert result.goals_completed == 5
        assert result.goals_failed == 1
        assert result.duration_seconds == 120.5
        assert len(result.commit_shas) == 2


# =============================================================================
# MergeResult Tests
# =============================================================================


class TestMergeResult:
    """Tests for MergeResult."""

    def test_creation(self):
        """Test creating a MergeResult."""
        result = MergeResult(
            merged=["sunwell/worker-1", "sunwell/worker-2"],
            conflicts=["sunwell/worker-3"],
        )

        assert len(result.merged) == 2
        assert len(result.conflicts) == 1


# =============================================================================
# BacklogManager Multi-Instance Extension Tests
# =============================================================================


class TestBacklogManagerMultiInstance:
    """Tests for BacklogManager multi-instance extensions (RFC-051)."""

    @pytest.mark.asyncio
    async def test_claim_goal(self, tmp_path: Path, sample_goal: Goal):
        """Test claiming a goal for a worker."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals[sample_goal.id] = sample_goal

        async with manager.exclusive_access():
            success = await manager.claim_goal(sample_goal.id, worker_id=1)

        assert success is True
        assert manager.backlog.goals[sample_goal.id].claimed_by == 1
        assert manager.backlog.goals[sample_goal.id].claimed_at is not None

    @pytest.mark.asyncio
    async def test_claim_goal_fails_if_already_claimed(
        self, tmp_path: Path, sample_goal: Goal
    ):
        """Test that claiming an already claimed goal fails."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals[sample_goal.id] = sample_goal

        async with manager.exclusive_access():
            await manager.claim_goal(sample_goal.id, worker_id=1)

        async with manager.exclusive_access():
            success = await manager.claim_goal(sample_goal.id, worker_id=2)

        assert success is False
        # Still claimed by worker 1
        assert manager.backlog.goals[sample_goal.id].claimed_by == 1

    @pytest.mark.asyncio
    async def test_get_pending_goals(self, tmp_path: Path, sample_goals: dict[str, Goal]):
        """Test getting pending goals."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals = sample_goals

        pending = await manager.get_pending_goals()

        # All goals should be pending initially
        assert len(pending) == 3

        # Complete one goal
        manager.backlog.completed.add("goal-1")
        pending = await manager.get_pending_goals()
        assert len(pending) == 2
        assert "goal-1" not in [g.id for g in pending]

    @pytest.mark.asyncio
    async def test_mark_complete(self, tmp_path: Path, sample_goal: Goal):
        """Test marking a goal as complete."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals[sample_goal.id] = sample_goal

        await manager.mark_complete(sample_goal.id)

        assert sample_goal.id in manager.backlog.completed

    @pytest.mark.asyncio
    async def test_mark_failed(self, tmp_path: Path, sample_goal: Goal):
        """Test marking a goal as failed."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals[sample_goal.id] = sample_goal

        await manager.mark_failed(sample_goal.id, error="Something went wrong")

        assert sample_goal.id in manager.backlog.blocked
        assert "Something went wrong" in manager.backlog.blocked[sample_goal.id]

    @pytest.mark.asyncio
    async def test_unclaim_goal(self, tmp_path: Path, sample_goal: Goal):
        """Test unclaiming a goal."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals[sample_goal.id] = sample_goal

        # Claim then unclaim
        async with manager.exclusive_access():
            await manager.claim_goal(sample_goal.id, worker_id=1)

        await manager.unclaim_goal(sample_goal.id)

        assert manager.backlog.goals[sample_goal.id].claimed_by is None
        assert manager.backlog.goals[sample_goal.id].claimed_at is None

    @pytest.mark.asyncio
    async def test_get_claims(self, tmp_path: Path, sample_goals: dict[str, Goal]):
        """Test getting current claims."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals = sample_goals

        async with manager.exclusive_access():
            await manager.claim_goal("goal-1", worker_id=1)
            await manager.claim_goal("goal-2", worker_id=2)

        claims = manager.get_claims()

        assert claims["goal-1"] == 1
        assert claims["goal-2"] == 2
        assert "goal-3" not in claims

    @pytest.mark.asyncio
    async def test_exclusive_access_prevents_concurrent_modification(
        self, tmp_path: Path, sample_goal: Goal
    ):
        """Test that exclusive_access prevents concurrent modification."""
        manager = BacklogManager(root=tmp_path)
        manager.backlog.goals[sample_goal.id] = sample_goal

        results = []

        async def claim_goal(worker_id: int):
            async with manager.exclusive_access():
                success = await manager.claim_goal(sample_goal.id, worker_id=worker_id)
                results.append((worker_id, success))

        # Run concurrently
        await asyncio.gather(
            claim_goal(1),
            claim_goal(2),
        )

        # Only one should succeed
        successes = [r for r in results if r[1]]
        assert len(successes) == 1


# =============================================================================
# Goal with claimed_by/claimed_at Tests
# =============================================================================


class TestGoalClaimFields:
    """Tests for Goal claimed_by and claimed_at fields (RFC-051)."""

    def test_goal_with_claim_fields(self):
        """Test creating a goal with claim fields."""
        now = datetime.now()
        goal = Goal(
            id="test-goal",
            title="Test",
            description="Test goal",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
            claimed_by=1,
            claimed_at=now,
        )

        assert goal.claimed_by == 1
        assert goal.claimed_at == now

    def test_goal_without_claim_fields(self):
        """Test creating a goal without claim fields (defaults to None)."""
        goal = Goal(
            id="test-goal",
            title="Test",
            description="Test goal",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        assert goal.claimed_by is None
        assert goal.claimed_at is None


# =============================================================================
# Coordinator Tests
# =============================================================================


class TestCoordinator:
    """Tests for Coordinator."""

    @pytest.mark.asyncio
    async def test_setup_creates_directories(self, tmp_path: Path):
        """Test that setup creates required directories."""
        # Initialize git repo
        import subprocess

        from sunwell.parallel import Coordinator

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        coordinator = Coordinator(root=tmp_path)
        await coordinator._setup()

        assert (tmp_path / ".sunwell" / "locks").exists()
        assert (tmp_path / ".sunwell" / "workers").exists()
        assert (tmp_path / ".sunwell" / "resources").exists()

    @pytest.mark.asyncio
    async def test_setup_fails_on_dirty_workdir(self, tmp_path: Path):
        """Test that setup fails if working directory is dirty."""
        # Initialize git repo
        import subprocess

        from sunwell.parallel import Coordinator

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Make directory dirty
        (tmp_path / "dirty.txt").write_text("dirty")

        coordinator = Coordinator(root=tmp_path)
        with pytest.raises(RuntimeError, match="not clean"):
            await coordinator._setup()

    def test_is_running_returns_false_initially(self, tmp_path: Path):
        """Test that is_running returns False when no workers started."""
        from sunwell.parallel import Coordinator

        coordinator = Coordinator(root=tmp_path)
        assert coordinator.is_running() is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for multi-instance coordination."""

    @pytest.mark.asyncio
    async def test_backlog_persistence_with_claims(self, tmp_path: Path):
        """Test that claims are persisted across manager instances."""
        goal = Goal(
            id="test-goal",
            title="Test",
            description="Test goal",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        # First manager claims the goal
        manager1 = BacklogManager(root=tmp_path)
        manager1.backlog.goals[goal.id] = goal
        async with manager1.exclusive_access():
            await manager1.claim_goal(goal.id, worker_id=1)

        # Second manager should see the claim
        manager2 = BacklogManager(root=tmp_path)
        manager2._load()
        assert manager2.backlog.goals[goal.id].claimed_by == 1

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_file_access(self, tmp_path: Path):
        """Test that locks prevent concurrent file access."""
        locks_dir = tmp_path / ".sunwell" / "locks"

        manager1 = FileLockManager(locks_dir)
        manager2 = FileLockManager(locks_dir)

        file_path = Path("shared.py")

        # Manager 1 acquires lock
        lock1 = await manager1.acquire(file_path, timeout=5.0)

        try:
            # Manager 2 should timeout
            with pytest.raises(TimeoutError):
                await manager2.acquire(file_path, timeout=0.2)
        finally:
            await manager1.release(lock1)

        # Now manager 2 can acquire
        lock2 = await manager2.acquire(file_path, timeout=5.0)
        await manager2.release(lock2)

    @pytest.mark.asyncio
    async def test_dependency_graph_with_real_backlog(self, tmp_path: Path):
        """Test dependency graph with a real backlog manager."""
        manager = BacklogManager(root=tmp_path)

        # Create goals
        goal1 = Goal(
            id="goal-1",
            title="Goal 1",
            description="First goal",
            source_signals=(),
            priority=0.8,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        goal2 = Goal(
            id="goal-2",
            title="Goal 2",
            description="Second goal, depends on first",
            source_signals=(),
            priority=0.6,
            estimated_complexity="moderate",
            requires=frozenset({"goal-1"}),
            category="improve",
            auto_approvable=True,
            scope=GoalScope(),
        )

        manager.backlog.goals["goal-1"] = goal1
        manager.backlog.goals["goal-2"] = goal2

        # Build graph
        graph = GoalDependencyGraph.from_backlog(manager.backlog)

        # Goal 2 depends on Goal 1
        assert "goal-1" in graph.dependencies["goal-2"]

        # Goal 1 is ready, Goal 2 is not
        ready = graph.get_ready_goals(completed=set())
        assert "goal-1" in ready
        assert "goal-2" not in ready

    @pytest.mark.asyncio
    async def test_resource_governor_concurrent_access(self, tmp_path: Path):
        """Test resource governor with concurrent access."""
        governor = ResourceGovernor(
            ResourceLimits(max_concurrent_llm_calls=2),
            tmp_path,
        )

        acquired = []
        released = []

        async def acquire_and_release(task_id: int):
            async with governor.llm_slot():
                acquired.append(task_id)
                await asyncio.sleep(0.1)
            released.append(task_id)

        # Run 4 tasks concurrently with limit of 2
        await asyncio.gather(
            acquire_and_release(1),
            acquire_and_release(2),
            acquire_and_release(3),
            acquire_and_release(4),
        )

        # All tasks should complete
        assert len(acquired) == 4
        assert len(released) == 4
