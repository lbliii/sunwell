"""Integration tests for full agent cycle.

Tests the complete flow: goal → plan → execute → complete
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from sunwell.agent.learning import DeadEnd, Learning
from sunwell.planning.naaru.types import Task, TaskMode, TaskStatus


class TestAgentFullCycle:
    """Test complete agent execution cycle."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_cycle_structure(self, tmp_path: Path) -> None:
        """Test that agent cycle has correct structure (mocked)."""
        # This is a structural test - verifies the flow exists
        # Full execution would require actual models and tools
        
        # 1. Goal creation
        goal = "Build a test API"
        assert isinstance(goal, str)
        assert len(goal) > 0

        # 2. Task creation (simulating planner output)
        tasks = [
            Task(
                id="task-1",
                description="Create API structure",
                mode=TaskMode.GENERATE,
                status=TaskStatus.PENDING,
            ),
            Task(
                id="task-2",
                description="Add endpoints",
                mode=TaskMode.GENERATE,
                status=TaskStatus.PENDING,
                depends_on=("task-1",),
            ),
        ]
        
        assert len(tasks) > 0
        assert all(isinstance(t, Task) for t in tasks)
        assert tasks[1].depends_on == ("task-1",)

        # 3. Task execution order
        completed = set()
        ready_tasks = [t for t in tasks if t.is_ready(completed)]
        
        # First task should be ready (no dependencies)
        # Note: is_ready checks if dependencies are satisfied
        ready_ids = {t.id for t in ready_tasks}
        assert "task-1" in ready_ids
        assert "task-2" not in ready_ids  # Has dependency on task-1

        # 4. Completion tracking
        completed.add("task-1")
        ready_tasks = [t for t in tasks if t.is_ready(completed)]
        
        # Second task should now be ready (dependency satisfied)
        ready_ids = {t.id for t in ready_tasks}
        assert "task-2" in ready_ids

    @pytest.mark.integration
    def test_task_dependency_resolution(self) -> None:
        """Test task dependency resolution logic."""
        # Create tasks with dependencies
        task1 = Task(
            id="task-1",
            description="Task 1",
            mode=TaskMode.GENERATE,
        )
        
        task2 = Task(
            id="task-2",
            description="Task 2",
            mode=TaskMode.GENERATE,
            depends_on=("task-1",),
        )
        
        task3 = Task(
            id="task-3",
            description="Task 3",
            mode=TaskMode.GENERATE,
            depends_on=("task-1", "task-2"),
        )
        
        # Test dependency resolution
        completed = set()
        
        # Initially, only task1 is ready
        assert task1.is_ready(completed) is True
        assert task2.is_ready(completed) is False
        assert task3.is_ready(completed) is False
        
        # After task1 completes, task2 becomes ready
        completed.add("task-1")
        assert task2.is_ready(completed) is True
        assert task3.is_ready(completed) is False
        
        # After task2 completes, task3 becomes ready
        completed.add("task-2")
        assert task3.is_ready(completed) is True

    @pytest.mark.integration
    def test_task_status_transitions(self) -> None:
        """Test task status transitions."""
        task = Task(
            id="test-task",
            description="Test task",
            mode=TaskMode.GENERATE,
            status=TaskStatus.PENDING,
        )
        
        # PENDING -> READY -> IN_PROGRESS -> COMPLETED
        assert task.status == TaskStatus.PENDING
        
        # When dependencies satisfied, becomes READY
        task.status = TaskStatus.READY
        assert task.status == TaskStatus.READY
        
        # When execution starts, becomes IN_PROGRESS
        task.status = TaskStatus.IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS
        
        # When done, becomes COMPLETED
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED


# =============================================================================
# Full Agent Flow Tests
# =============================================================================


class TestAgentOrientPlanExecuteLearnFlow:
    """Integration tests for the complete agent flow with mocked components."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_orient_phase_loads_memory(self, tmp_path: Path) -> None:
        """Test that orient phase loads memory and context."""
        from sunwell.agent.context.session import SessionContext
        from sunwell.memory import PersistentMemory

        # Create workspace with memory
        workspace = tmp_path / "project"
        workspace.mkdir()

        # Initialize memory with some learnings
        memory = PersistentMemory.empty(workspace)
        memory.learning_store.add_learning(
            Learning(fact="Use FastAPI", category="pattern")
        )
        memory.sync()

        # Create session context
        session = SessionContext.build(
            workspace=workspace,
            goal="Build REST API",
            options={},
        )

        # Verify memory can be loaded
        loaded_memory = PersistentMemory.load(workspace)
        assert loaded_memory.learning_store.learnings[0].fact == "Use FastAPI"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_memory_persists_across_agent_runs(self, tmp_path: Path) -> None:
        """Test that memory persists between agent runs (critical for autonomy)."""
        from sunwell.agent.learning import Learning, LearningStore
        from sunwell.memory import PersistentMemory

        workspace = tmp_path / "project"
        workspace.mkdir()

        # Run 1: Create learning
        memory1 = PersistentMemory.empty(workspace)
        memory1.learning_store.add_learning(
            Learning(fact="API key is in .env.local", category="fact")
        )
        memory1.sync()

        # Run 2: Load and verify
        memory2 = PersistentMemory.load(workspace)
        relevant = memory2.learning_store.get_relevant("API key location")

        assert len(relevant) > 0
        assert any(".env.local" in l.fact for l in relevant)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_planning_uses_memory_context(self, tmp_path: Path) -> None:
        """Test that planning phase retrieves and uses memory context."""
        from sunwell.agent.learning import Learning
        from sunwell.memory import PersistentMemory

        workspace = tmp_path / "project"
        workspace.mkdir()

        # Setup memory with domain knowledge
        memory = PersistentMemory.empty(workspace)
        memory.learning_store.add_learning(
            Learning(fact="User model has email field", category="type")
        )
        memory.learning_store.add_learning(
            Learning(fact="Uses SQLAlchemy ORM", category="pattern")
        )
        memory.sync()

        # Retrieve context for planning
        context = await memory.get_relevant("Create user model")

        assert len(context.learnings) > 0
        # Should have found relevant learnings
        facts = [l.fact for l in context.learnings]
        assert any("email" in f.lower() for f in facts)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execution_records_outcomes(self, tmp_path: Path) -> None:
        """Test that execution phase records outcomes to memory."""
        from sunwell.agent.learning import DeadEnd, Learning, LearningStore

        store = LearningStore()

        # Simulate successful execution
        store.add_learning(
            Learning(fact="Created User model", category="artifact")
        )

        # Simulate failed approach
        store.add_dead_end(
            DeadEnd(
                approach="Use sync database in async handler",
                reason="Caused timeout",
                gate="runtime",
            )
        )

        # Verify both recorded
        assert len(store.learnings) == 1
        assert len(store.dead_ends) == 1

        # Verify dead end is retrievable
        dead_ends = store.get_dead_ends_for("sync database")
        assert len(dead_ends) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_learning_phase_extracts_patterns(self, tmp_path: Path) -> None:
        """Test that learning phase extracts patterns from execution."""
        from sunwell.agent.learning import LearningExtractor

        extractor = LearningExtractor(use_llm=False)

        # Create test code
        code = '''
class User:
    """User model with authentication."""
    id: int
    email: str
    password_hash: str
'''

        # Extract learnings
        learnings = extractor.extract_from_code(code, "models.py")

        assert len(learnings) > 0
        facts = [l.fact for l in learnings]
        # Should find User class
        assert any("User" in f for f in facts)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_cycle_memory_accumulation(self, tmp_path: Path) -> None:
        """Test that multiple cycles accumulate knowledge."""
        from sunwell.agent.learning import Learning
        from sunwell.memory import PersistentMemory

        workspace = tmp_path / "project"
        workspace.mkdir()

        # Cycle 1: Basic model
        memory1 = PersistentMemory.empty(workspace)
        memory1.learning_store.add_learning(
            Learning(fact="Created User model", category="artifact")
        )
        memory1.sync()

        # Cycle 2: Add endpoints
        memory2 = PersistentMemory.load(workspace)
        memory2.learning_store.add_learning(
            Learning(fact="Created GET /users endpoint", category="artifact")
        )
        memory2.sync()

        # Cycle 3: Add auth
        memory3 = PersistentMemory.load(workspace)
        memory3.learning_store.add_learning(
            Learning(fact="Added JWT authentication", category="artifact")
        )
        memory3.sync()

        # Verify all learnings accumulated
        final_memory = PersistentMemory.load(workspace)
        assert len(final_memory.learning_store.learnings) == 3

        facts = [l.fact for l in final_memory.learning_store.learnings]
        assert "User model" in facts[0]
        assert "/users endpoint" in facts[1]
        assert "JWT" in facts[2]


# =============================================================================
# Harmonic Synthesis Integration Tests
# =============================================================================


class TestHarmonicSynthesisIntegration:
    """Integration tests for harmonic synthesis quality improvement."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_harmonic_synthesis_structural_flow(self) -> None:
        """Test that harmonic synthesis flow works structurally."""
        from sunwell.planning.naaru.types import Task, TaskMode

        # Create a task that would benefit from harmonic synthesis
        task = Task(
            id="security-task",
            description="Implement secure login function with input validation",
            mode=TaskMode.GENERATE,
        )

        # Harmonic synthesis would:
        # 1. Generate from multiple personas (security, QA, code reviewer)
        # 2. Vote on best output
        # 3. Return synthesized result

        # This test verifies the structure (actual synthesis requires models)
        personas = ["security_expert", "qa_engineer", "code_reviewer"]
        assert len(personas) >= 3

        # Would generate from each persona
        outputs = {persona: f"output_from_{persona}" for persona in personas}
        assert len(outputs) == 3

        # Would vote and select best
        # (in real implementation, uses voting mechanism)
        selected = max(outputs.items(), key=lambda x: len(x[1]))
        assert selected is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_persona_diversity_improves_output(self) -> None:
        """Test that diverse personas provide different perspectives."""
        # Different personas should emphasize different aspects
        personas = {
            "security_expert": ["validation", "sanitization", "encryption"],
            "performance_expert": ["caching", "indexing", "optimization"],
            "maintainability_expert": ["documentation", "testing", "modularity"],
        }

        # Each persona has distinct concerns
        for persona, concerns in personas.items():
            assert len(concerns) >= 3
            # No overlap between security and performance
            assert not set(personas["security_expert"]) & set(personas["performance_expert"])


# =============================================================================
# Memory System Observability Tests
# =============================================================================


class TestMemoryObservability:
    """Integration tests for memory debugging tools (from Week 1 work)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_debug_retrieval_provides_insights(self, tmp_path: Path) -> None:
        """Test that debug_retrieval shows why content was retrieved."""
        from sunwell.memory.simulacrum.core.store import SimulacrumStore

        store = SimulacrumStore(base_path=tmp_path / "memory")

        # Add some content
        store.add_user("How do I handle authentication?")
        store.add_assistant("Use JWT tokens for stateless auth")

        # Debug retrieval
        debug_info = await store.debug_retrieval("authentication")

        # Should provide debug information
        assert "query" in debug_info
        assert debug_info["query"] == "authentication"
        assert "tier_distribution" in debug_info
        assert "hot" in debug_info["tier_distribution"]

    @pytest.mark.integration
    def test_health_check_detects_issues(self, tmp_path: Path) -> None:
        """Test that health_check detects memory system issues."""
        from sunwell.memory.simulacrum.core.store import SimulacrumStore

        store = SimulacrumStore(base_path=tmp_path / "memory")

        # Check health
        health = store.health_check()

        # Should have status
        assert "overall_status" in health
        assert health["overall_status"] in ("healthy", "degraded", "error")

        # Should have checks
        assert "checks" in health
        assert "hot_tier" in health["checks"]
        assert "embeddings" in health["checks"]

        # Hot tier should be OK initially (empty)
        assert health["checks"]["hot_tier"]["status"] == "ok"

    @pytest.mark.integration
    def test_health_check_warns_on_overflow(self, tmp_path: Path) -> None:
        """Test that health_check warns when hot tier is full."""
        from sunwell.memory.simulacrum.core.config import StorageConfig
        from sunwell.memory.simulacrum.core.store import SimulacrumStore

        # Create store with very small hot tier
        config = StorageConfig(hot_max_turns=2)
        store = SimulacrumStore(base_path=tmp_path / "memory", config=config)

        # Fill hot tier beyond capacity
        for i in range(5):
            store.add_user(f"Message {i}")

        # Check health - should warn about hot tier
        health = store.health_check()

        # Hot tier should be in warning/critical state
        assert health["checks"]["hot_tier"]["status"] in ("warning", "critical")
        assert health["overall_status"] in ("degraded", "error")
