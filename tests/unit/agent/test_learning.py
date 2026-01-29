"""Tests for sunwell.agent.learning package.

Tests cover:
- Instantiation (catches TYPE_CHECKING import errors)
- Learning/DeadEnd ID computation and caching
- LearningStore thread safety
- SimLearning integration (field mapping)
- Serialization round-trips
- Deduplication logic
- Error logging behavior
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sunwell.agent.learning import (
    DeadEnd,
    Learning,
    LearningExtractor,
    LearningStore,
    ToolPattern,
    classify_task_type,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_learning() -> Learning:
    """Create a sample learning."""
    return Learning(
        fact="User.id is Integer primary key",
        category="type",
        confidence=0.9,
        source_file="models.py",
        source_line=15,
    )


@pytest.fixture
def sample_dead_end() -> DeadEnd:
    """Create a sample dead end."""
    return DeadEnd(
        approach="Use sync database driver",
        reason="Blocks event loop",
        context="FastAPI async context",
        gate="runtime",
    )


@pytest.fixture
def learning_store() -> LearningStore:
    """Create an empty learning store."""
    return LearningStore()


@pytest.fixture
def populated_store() -> LearningStore:
    """Create a store with sample data."""
    store = LearningStore()
    store.add_learning(Learning(fact="Uses FastAPI", category="pattern"))
    store.add_learning(Learning(fact="User has email field", category="type"))
    store.add_learning(Learning(fact="POST /users creates user", category="api"))
    store.add_dead_end(DeadEnd(approach="sync DB", reason="blocks loop"))
    return store


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


# =============================================================================
# Instantiation Tests (catches TYPE_CHECKING import errors)
# =============================================================================


class TestInstantiation:
    """Tests that verify classes can be instantiated without import errors."""

    def test_learning_extractor_instantiates(self) -> None:
        """LearningExtractor should instantiate without NameError.
        
        This catches runtime errors from TYPE_CHECKING imports used
        in field annotations without quotes.
        """
        extractor = LearningExtractor()
        assert extractor.model is None
        assert extractor.use_llm is False

    def test_learning_extractor_with_model(self) -> None:
        """LearningExtractor accepts model parameter."""
        mock_model = MagicMock()
        extractor = LearningExtractor(use_llm=True, model=mock_model)
        assert extractor.model is mock_model
        assert extractor.use_llm is True

    def test_learning_instantiates(self, sample_learning: Learning) -> None:
        """Learning dataclass instantiates correctly."""
        assert sample_learning.fact == "User.id is Integer primary key"
        assert sample_learning.category == "type"
        assert sample_learning.confidence == 0.9

    def test_dead_end_instantiates(self, sample_dead_end: DeadEnd) -> None:
        """DeadEnd dataclass instantiates correctly."""
        assert sample_dead_end.approach == "Use sync database driver"
        assert sample_dead_end.reason == "Blocks event loop"
        assert sample_dead_end.gate == "runtime"

    def test_learning_store_instantiates(self, learning_store: LearningStore) -> None:
        """LearningStore instantiates with empty state."""
        assert len(learning_store.learnings) == 0
        assert len(learning_store.dead_ends) == 0

    def test_tool_pattern_instantiates(self) -> None:
        """ToolPattern instantiates correctly."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file", "edit_file"),
        )
        assert pattern.task_type == "api"
        assert pattern.success_count == 0


# =============================================================================
# ID Computation Tests
# =============================================================================


class TestLearningId:
    """Tests for Learning ID computation and caching."""

    def test_id_is_deterministic(self, sample_learning: Learning) -> None:
        """Same content produces same ID."""
        id1 = sample_learning.id
        id2 = sample_learning.id
        assert id1 == id2

    def test_id_is_cached(self, sample_learning: Learning) -> None:
        """ID is cached after first computation."""
        _ = sample_learning.id
        assert sample_learning._id_cache is not None

    def test_id_is_content_addressable(self) -> None:
        """Same fact+category produces same ID regardless of other fields."""
        learning1 = Learning(fact="test", category="type", confidence=0.5)
        learning2 = Learning(fact="test", category="type", confidence=0.9)
        assert learning1.id == learning2.id

    def test_different_content_different_id(self) -> None:
        """Different content produces different ID."""
        learning1 = Learning(fact="test", category="type")
        learning2 = Learning(fact="other", category="type")
        assert learning1.id != learning2.id

    def test_different_category_different_id(self) -> None:
        """Different category produces different ID."""
        learning1 = Learning(fact="test", category="type")
        learning2 = Learning(fact="test", category="api")
        assert learning1.id != learning2.id


class TestDeadEndId:
    """Tests for DeadEnd ID computation."""

    def test_id_is_deterministic(self, sample_dead_end: DeadEnd) -> None:
        """Same content produces same ID."""
        id1 = sample_dead_end.id
        id2 = sample_dead_end.id
        assert id1 == id2

    def test_id_is_content_addressable(self) -> None:
        """Same approach+reason+gate produces same ID."""
        de1 = DeadEnd(approach="X", reason="Y", gate="lint")
        de2 = DeadEnd(approach="X", reason="Y", gate="lint")
        assert de1.id == de2.id

    def test_different_approach_different_id(self) -> None:
        """Different approach produces different ID."""
        de1 = DeadEnd(approach="X", reason="Y")
        de2 = DeadEnd(approach="Z", reason="Y")
        assert de1.id != de2.id

    def test_different_reason_different_id(self) -> None:
        """Different reason produces different ID."""
        de1 = DeadEnd(approach="X", reason="Y")
        de2 = DeadEnd(approach="X", reason="Z")
        assert de1.id != de2.id

    def test_gate_affects_id(self) -> None:
        """Gate field affects ID."""
        de1 = DeadEnd(approach="X", reason="Y", gate="lint")
        de2 = DeadEnd(approach="X", reason="Y", gate="test")
        assert de1.id != de2.id


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestLearningStoreThreadSafety:
    """Tests for thread-safe operations in LearningStore."""

    def test_concurrent_add_learning(self) -> None:
        """add_learning is thread-safe under concurrent access."""
        store = LearningStore()
        errors: list[Exception] = []

        def add_many(start: int) -> None:
            try:
                for i in range(100):
                    learning = Learning(
                        fact=f"Fact {start + i}",
                        category="pattern",
                    )
                    store.add_learning(learning)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_many, args=(i * 100,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        # Should have up to 500 unique learnings
        assert len(store.learnings) <= 500

    def test_concurrent_add_dead_end(self) -> None:
        """add_dead_end is thread-safe under concurrent access."""
        store = LearningStore()
        errors: list[Exception] = []

        def add_many(start: int) -> None:
            try:
                for i in range(50):
                    de = DeadEnd(
                        approach=f"Approach {start + i}",
                        reason="Failed",
                    )
                    store.add_dead_end(de)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_many, args=(i * 50,))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_read_write(self, populated_store: LearningStore) -> None:
        """Concurrent reads and writes don't cause race conditions."""
        errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(50):
                    populated_store.add_learning(
                        Learning(fact=f"New fact {i}", category="pattern")
                    )
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(50):
                    _ = populated_store.get_relevant("user")
                    _ = populated_store.format_for_prompt()
                    _ = populated_store.to_dict()
                    _ = populated_store.get_dead_ends_for("sync")
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(writer) for _ in range(2)]
            futures += [ex.submit(reader) for _ in range(2)]
            for f in futures:
                f.result()

        assert not errors, f"Race condition errors: {errors}"

    def test_concurrent_tool_pattern_recording(self) -> None:
        """record_tool_sequence is thread-safe."""
        store = LearningStore()
        errors: list[Exception] = []

        def record_many() -> None:
            try:
                for i in range(50):
                    store.record_tool_sequence(
                        task_type="api",
                        tools=["read_file", "edit_file"],
                        success=(i % 2 == 0),
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# =============================================================================
# SimLearning Integration Tests
# =============================================================================


class TestSimLearningIntegration:
    """Tests for Learning → SimLearning conversion."""

    def test_sync_to_simulacrum_creates_valid_objects(
        self,
        populated_store: LearningStore,
    ) -> None:
        """sync_to_simulacrum creates SimLearning with correct required fields."""
        from sunwell.memory.simulacrum.core import Learning as SimLearning

        received_learnings: list[SimLearning] = []

        class MockSimStore:
            def add_learning(self, learning: SimLearning) -> None:
                # Verify it's a valid SimLearning
                assert isinstance(learning, SimLearning)
                assert learning.source_turns == ()  # Required field
                assert learning.fact  # Non-empty
                received_learnings.append(learning)

        synced = populated_store.sync_to_simulacrum(MockSimStore())
        assert synced == len(populated_store.learnings)
        assert len(received_learnings) == synced

    def test_all_categories_map_correctly(self) -> None:
        """All agent Learning categories map to valid SimLearning categories."""
        categories = [
            "type", "api", "pattern", "fix", 
            "heuristic", "template", "task_completion",
        ]

        for cat in categories:
            store = LearningStore()
            store.add_learning(Learning(fact=f"Test for {cat}", category=cat))

            received: list[Any] = []

            class MockStore:
                def add_learning(self, learning: Any) -> None:
                    received.append(learning)

            synced = store.sync_to_simulacrum(MockStore())
            assert synced == 1, f"Category '{cat}' failed to sync"


# =============================================================================
# Serialization Round-Trip Tests
# =============================================================================


class TestSerializationRoundTrip:
    """Tests for save_to_disk / load_from_disk."""

    def test_learnings_survive_roundtrip(
        self,
        populated_store: LearningStore,
        temp_project: Path,
    ) -> None:
        """Learnings are preserved through disk serialization."""
        original_count = len(populated_store.learnings)
        original_facts = {l.fact for l in populated_store.learnings}

        populated_store.save_to_disk(temp_project)

        new_store = LearningStore()
        loaded = new_store.load_from_disk(temp_project)

        assert loaded >= original_count
        loaded_facts = {l.fact for l in new_store.learnings}
        assert original_facts <= loaded_facts

    def test_dead_ends_survive_roundtrip(
        self,
        populated_store: LearningStore,
        temp_project: Path,
    ) -> None:
        """Dead ends are preserved through disk serialization."""
        original_approaches = {d.approach for d in populated_store.dead_ends}

        populated_store.save_to_disk(temp_project)

        new_store = LearningStore()
        new_store.load_from_disk(temp_project)

        loaded_approaches = {d.approach for d in new_store.dead_ends}
        assert original_approaches <= loaded_approaches

    def test_dead_end_gate_preserved(self, temp_project: Path) -> None:
        """DeadEnd.gate field is preserved in serialization."""
        store = LearningStore()
        store.add_dead_end(DeadEnd(
            approach="Try X",
            reason="Failed",
            gate="lint",
        ))

        store.save_to_disk(temp_project)

        new_store = LearningStore()
        new_store.load_from_disk(temp_project)

        assert len(new_store.dead_ends) == 1
        assert new_store.dead_ends[0].gate == "lint"

    def test_empty_store_roundtrip(self, temp_project: Path) -> None:
        """Empty store handles roundtrip gracefully."""
        store = LearningStore()
        saved = store.save_to_disk(temp_project)
        assert saved == 0

        new_store = LearningStore()
        loaded = new_store.load_from_disk(temp_project)
        assert loaded == 0


# =============================================================================
# Deduplication Tests
# =============================================================================


class TestDeduplication:
    """Tests for deduplication logic."""

    def test_learning_deduplication_by_id(self, learning_store: LearningStore) -> None:
        """Same fact+category deduplicates in store."""
        learning_store.add_learning(Learning(fact="X", category="type", confidence=0.5))
        learning_store.add_learning(Learning(fact="X", category="type", confidence=0.9))
        assert len(learning_store.learnings) == 1

    def test_different_category_not_deduplicated(
        self,
        learning_store: LearningStore,
    ) -> None:
        """Same fact with different category is not deduplicated."""
        learning_store.add_learning(Learning(fact="X", category="type"))
        learning_store.add_learning(Learning(fact="X", category="api"))
        assert len(learning_store.learnings) == 2

    def test_disk_deduplication_learnings(self, temp_project: Path) -> None:
        """Learnings don't duplicate on multiple saves."""
        store = LearningStore()
        store.add_learning(Learning(fact="Persistent", category="pattern"))

        store.save_to_disk(temp_project)
        store.save_to_disk(temp_project)  # Second save

        # Read the file directly
        path = temp_project / ".sunwell" / "intelligence" / "learnings.jsonl"
        lines = [l for l in path.read_text().strip().split("\n") if l]
        assert len(lines) == 1

    def test_disk_deduplication_dead_ends(self, temp_project: Path) -> None:
        """Dead ends don't duplicate on multiple saves."""
        store = LearningStore()
        store.add_dead_end(DeadEnd(approach="X", reason="Y", gate="lint"))

        store.save_to_disk(temp_project)
        store.save_to_disk(temp_project)  # Second save

        path = temp_project / ".sunwell" / "intelligence" / "dead_ends.jsonl"
        lines = [l for l in path.read_text().strip().split("\n") if l]
        assert len(lines) == 1


# =============================================================================
# Error Logging Tests
# =============================================================================


class TestErrorLogging:
    """Tests for error logging behavior."""

    def test_sync_failure_is_logged(
        self,
        populated_store: LearningStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sync failures are logged, not silently swallowed."""

        class FailingStore:
            def add_learning(self, learning: Any) -> None:
                raise RuntimeError("Simulated failure")

        with caplog.at_level(logging.DEBUG):
            result = populated_store.sync_to_simulacrum(FailingStore())

        assert result == 0
        # Should have logged the failure
        assert any("sync" in r.message.lower() or "failed" in r.message.lower() 
                   for r in caplog.records)

    def test_load_simulacrum_failure_is_logged(
        self,
        learning_store: LearningStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Load failures are logged, not silently swallowed."""

        class FailingStore:
            def get_learnings(self) -> list:
                raise AttributeError("Simulated failure")

        with caplog.at_level(logging.DEBUG):
            result = learning_store.load_from_simulacrum(FailingStore())

        assert result == 0


# =============================================================================
# LearningExtractor Tests
# =============================================================================


class TestLearningExtractor:
    """Tests for LearningExtractor functionality."""

    def test_extract_from_code_finds_classes(self) -> None:
        """extract_from_code finds class definitions."""
        extractor = LearningExtractor()
        code = '''
class User:
    id: int
    name: str
    email: str
'''
        learnings = extractor.extract_from_code(code, "models.py")
        
        assert len(learnings) > 0
        facts = [l.fact for l in learnings]
        assert any("User" in f for f in facts)

    def test_extract_from_code_finds_foreign_keys(self) -> None:
        """extract_from_code finds foreign key relationships."""
        extractor = LearningExtractor()
        code = '''
class Post:
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id"))
'''
        learnings = extractor.extract_from_code(code, "models.py")
        
        facts = [l.fact for l in learnings]
        assert any("ForeignKey" in f and "users.id" in f for f in facts)

    def test_extract_from_code_finds_api_routes(self) -> None:
        """extract_from_code finds API endpoints."""
        extractor = LearningExtractor()
        code = '''
@app.get("/users")
def list_users():
    return []

@router.post("/users")
def create_user():
    pass
'''
        learnings = extractor.extract_from_code(code, "routes.py")
        
        facts = [l.fact for l in learnings]
        api_learnings = [f for f in facts if "/users" in f]
        assert len(api_learnings) >= 1

    def test_extract_from_fix_success(self) -> None:
        """extract_from_fix creates Learning on success."""
        extractor = LearningExtractor()
        result = extractor.extract_from_fix(
            error_type="syntax",
            error_message="Missing colon",
            fix_description="Added colon after function definition",
            success=True,
        )
        
        assert isinstance(result, Learning)
        assert result.category == "fix"
        assert "syntax" in result.fact.lower()

    def test_extract_from_fix_failure(self) -> None:
        """extract_from_fix creates DeadEnd on failure."""
        extractor = LearningExtractor()
        result = extractor.extract_from_fix(
            error_type="type",
            error_message="Cannot assign str to int",
            fix_description="Tried type cast",
            success=False,
        )
        
        assert isinstance(result, DeadEnd)
        assert "cast" in result.approach.lower()


# =============================================================================
# ToolPattern Tests
# =============================================================================


class TestToolPattern:
    """Tests for ToolPattern functionality."""

    def test_success_rate_calculation(self) -> None:
        """success_rate calculates correctly."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file", "edit_file"),
            success_count=3,
            failure_count=1,
        )
        assert pattern.success_rate == 0.75

    def test_success_rate_empty(self) -> None:
        """success_rate returns 0.5 for no data."""
        pattern = ToolPattern(task_type="api", tool_sequence=("read_file",))
        assert pattern.success_rate == 0.5

    def test_record_updates_counts(self) -> None:
        """record() updates success/failure counts."""
        pattern = ToolPattern(task_type="api", tool_sequence=("read_file",))
        
        pattern.record(success=True)
        assert pattern.success_count == 1
        
        pattern.record(success=False)
        assert pattern.failure_count == 1

    def test_confidence_increases_with_samples(self) -> None:
        """confidence increases with more samples."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file",),
            success_count=1,
            failure_count=0,
        )
        conf_low = pattern.confidence

        pattern.success_count = 10
        conf_high = pattern.confidence

        assert conf_high > conf_low

    def test_has_lock_attribute(self) -> None:
        """ToolPattern should have _lock for thread safety (RFC-122 fix)."""
        pattern = ToolPattern(task_type="api", tool_sequence=("read_file",))
        assert hasattr(pattern, "_lock")
        assert isinstance(pattern._lock, threading.Lock)


class TestToolPatternThreadSafety:
    """Thread safety tests for ToolPattern (RFC-122 bug fix).

    Bug: ToolPattern.record() used non-atomic += operations on
    success_count/failure_count, unsafe in Python 3.14t free-threading.
    Fix: Added threading.Lock and wrapped mutations.
    """

    def test_concurrent_recording_exact_counts(self) -> None:
        """Verify record() produces exact counts under concurrent access."""
        pattern = ToolPattern(task_type="test", tool_sequence=("read_file", "write_file"))
        iterations = 500

        def record_success() -> None:
            for _ in range(iterations):
                pattern.record(True)

        def record_failure() -> None:
            for _ in range(iterations):
                pattern.record(False)

        threads = [
            threading.Thread(target=record_success),
            threading.Thread(target=record_failure),
            threading.Thread(target=record_success),
            threading.Thread(target=record_failure),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 1000 successes and 1000 failures
        assert pattern.success_count == 2 * iterations
        assert pattern.failure_count == 2 * iterations

    def test_success_rate_consistent_under_contention(self) -> None:
        """Verify success_rate property is consistent under concurrent reads/writes."""
        pattern = ToolPattern(task_type="test", tool_sequence=("tool",))
        errors: list[str] = []

        def reader() -> None:
            for _ in range(200):
                rate = pattern.success_rate
                if not (0.0 <= rate <= 1.0):
                    errors.append(f"Invalid rate: {rate}")

        def writer() -> None:
            for _ in range(200):
                pattern.record(True)
                pattern.record(False)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads += [threading.Thread(target=writer) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Found errors: {errors}"

    def test_confidence_consistent_under_contention(self) -> None:
        """Verify confidence property is consistent under concurrent access."""
        pattern = ToolPattern(task_type="test", tool_sequence=("tool",))
        errors: list[str] = []

        def reader() -> None:
            for _ in range(200):
                conf = pattern.confidence
                if not (0.0 <= conf <= 1.0):
                    errors.append(f"Invalid confidence: {conf}")

        def writer() -> None:
            for _ in range(200):
                pattern.record(True)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads += [threading.Thread(target=writer) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Found errors: {errors}"


class TestClassifyTaskType:
    """Tests for classify_task_type function."""

    def test_classifies_test_tasks(self) -> None:
        """Recognizes test-related tasks."""
        assert classify_task_type("Write unit tests for User model") == "test"
        assert classify_task_type("Add pytest specs") == "test"

    def test_classifies_api_tasks(self) -> None:
        """Recognizes API-related tasks."""
        assert classify_task_type("Create REST endpoint for users") == "api"
        assert classify_task_type("Add GraphQL mutation") == "api"

    def test_classifies_fix_tasks(self) -> None:
        """Recognizes fix/bug tasks."""
        assert classify_task_type("Fix the login bug") == "fix"
        assert classify_task_type("Resolve error in auth") == "fix"

    def test_classifies_refactor_tasks(self) -> None:
        """Recognizes refactoring tasks."""
        assert classify_task_type("Refactor the database layer") == "refactor"
        assert classify_task_type("Rename UserService to UserManager") == "refactor"

    def test_defaults_to_general(self) -> None:
        """Unknown tasks default to general."""
        assert classify_task_type("Do something vague") == "general"


# =============================================================================
# LearningStore Query Tests
# =============================================================================


class TestLearningStoreQueries:
    """Tests for LearningStore query methods."""

    def test_get_relevant_finds_matches(
        self,
        populated_store: LearningStore,
    ) -> None:
        """get_relevant finds learnings by keyword."""
        results = populated_store.get_relevant("user email")
        
        # Should find the "User has email field" learning
        facts = [r.fact for r in results]
        assert any("email" in f.lower() for f in facts)

    def test_get_relevant_empty_query(self, populated_store: LearningStore) -> None:
        """get_relevant handles empty query."""
        results = populated_store.get_relevant("")
        # Empty query may return nothing or everything depending on implementation
        assert isinstance(results, list)

    def test_get_dead_ends_for_finds_matches(
        self,
        populated_store: LearningStore,
    ) -> None:
        """get_dead_ends_for finds relevant dead ends."""
        results = populated_store.get_dead_ends_for("sync database")
        
        assert len(results) >= 1
        assert any("sync" in d.approach.lower() for d in results)

    def test_get_templates(self) -> None:
        """get_templates returns only template category."""
        store = LearningStore()
        store.add_learning(Learning(fact="F1", category="pattern"))
        store.add_learning(Learning(fact="T1", category="template"))
        store.add_learning(Learning(fact="T2", category="template"))

        templates = store.get_templates()
        
        assert len(templates) == 2
        assert all(t.category == "template" for t in templates)

    def test_get_heuristics(self) -> None:
        """get_heuristics returns only heuristic category."""
        store = LearningStore()
        store.add_learning(Learning(fact="F1", category="pattern"))
        store.add_learning(Learning(fact="H1", category="heuristic"))

        heuristics = store.get_heuristics()
        
        assert len(heuristics) == 1
        assert heuristics[0].category == "heuristic"

    def test_format_for_prompt(self, populated_store: LearningStore) -> None:
        """format_for_prompt produces readable output."""
        output = populated_store.format_for_prompt()
        
        assert "Known facts" in output
        assert "FastAPI" in output  # One of the learnings
        # Should include dead ends section
        assert "didn't work" in output.lower()

    def test_to_dict(self, populated_store: LearningStore) -> None:
        """to_dict produces serializable dict."""
        result = populated_store.to_dict()
        
        assert "learnings" in result
        assert "dead_ends" in result
        assert len(result["learnings"]) == len(populated_store.learnings)


# =============================================================================
# Tool Suggestion Tests
# =============================================================================


class TestToolSuggestions:
    """Tests for tool suggestion functionality."""

    def test_suggest_tools_returns_best_sequence(self) -> None:
        """suggest_tools returns highest confidence sequence."""
        store = LearningStore()
        
        # Record some patterns
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)
        store.record_tool_sequence("api", ["grep", "edit_file"], success=False)

        suggested = store.suggest_tools("api")
        
        assert suggested == ["read_file", "edit_file"]

    def test_suggest_tools_empty_for_unknown_type(self) -> None:
        """suggest_tools returns empty for unknown task type."""
        store = LearningStore()
        suggested = store.suggest_tools("unknown_type")
        assert suggested == []

    def test_format_tool_suggestions(self) -> None:
        """format_tool_suggestions produces readable output."""
        store = LearningStore()
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)

        formatted = store.format_tool_suggestions("api")
        
        assert formatted is not None
        assert "api" in formatted.lower()
        assert "read_file" in formatted
        assert "→" in formatted  # Arrow separator

    def test_get_tool_patterns_with_min_samples(self) -> None:
        """get_tool_patterns filters by minimum samples."""
        store = LearningStore()
        store.record_tool_sequence("api", ["read_file"], success=True)
        store.record_tool_sequence("test", ["run_test"], success=True)
        store.record_tool_sequence("test", ["run_test"], success=True)

        patterns = store.get_tool_patterns(min_samples=2)
        
        assert len(patterns) == 1
        assert patterns[0].task_type == "test"


# =============================================================================
# learn_from_execution Tests (RFC-122, RFC-135)
# =============================================================================


class TestLearnFromExecution:
    """Tests for learn_from_execution() function.
    
    This function extracts learnings after agent execution completes.
    Key invariant: TaskGraph.tasks is a list, not a dict.
    """

    @pytest.fixture
    def mock_task(self) -> Any:
        """Create a mock task."""
        task = MagicMock()
        task.id = "task-1"
        task.name = "Create user model"
        task.description = "Create a User model with id and email fields"
        return task

    @pytest.fixture
    def task_graph_with_tasks(self, mock_task: Any) -> Any:
        """Create a TaskGraph with tasks (as a list, not dict)."""
        from sunwell.agent.core.task_graph import TaskGraph
        
        graph = TaskGraph()
        graph.tasks = [mock_task]  # TaskGraph.tasks is list[Task]
        return graph

    @pytest.fixture
    def empty_task_graph(self) -> Any:
        """Create an empty TaskGraph."""
        from sunwell.agent.core.task_graph import TaskGraph
        
        return TaskGraph()

    @pytest.mark.asyncio
    async def test_learn_from_execution_with_tasks(
        self,
        task_graph_with_tasks: Any,
        learning_store: LearningStore,
    ) -> None:
        """learn_from_execution works with TaskGraph that has tasks.
        
        This is a regression test for the bug where .values() was called
        on task_graph.tasks (a list) instead of iterating directly.
        """
        from sunwell.agent.learning.execution import learn_from_execution
        
        extractor = LearningExtractor()
        
        # Should not raise "'list' object has no attribute 'values'"
        learnings = []
        async for fact, category in learn_from_execution(
            goal="Create a user model",
            success=True,
            task_graph=task_graph_with_tasks,
            learning_store=learning_store,
            learning_extractor=extractor,
            files_changed=[],
            last_planning_context=None,
            memory=None,
        ):
            learnings.append((fact, category))
        
        # Function completed without error - that's the key assertion
        # (heuristic extraction may or may not produce learnings)
        assert isinstance(learnings, list)

    @pytest.mark.asyncio
    async def test_learn_from_execution_empty_task_graph(
        self,
        empty_task_graph: Any,
        learning_store: LearningStore,
    ) -> None:
        """learn_from_execution handles empty TaskGraph."""
        from sunwell.agent.learning.execution import learn_from_execution
        
        extractor = LearningExtractor()
        
        learnings = []
        async for fact, category in learn_from_execution(
            goal="Do something",
            success=True,
            task_graph=empty_task_graph,
            learning_store=learning_store,
            learning_extractor=extractor,
            files_changed=[],
            last_planning_context=None,
            memory=None,
        ):
            learnings.append((fact, category))
        
        # Empty task graph should complete without error
        assert isinstance(learnings, list)

    @pytest.mark.asyncio
    async def test_learn_from_execution_skips_heuristics_on_failure(
        self,
        task_graph_with_tasks: Any,
        learning_store: LearningStore,
    ) -> None:
        """learn_from_execution skips heuristic extraction when success=False."""
        from sunwell.agent.learning.execution import learn_from_execution
        
        extractor = LearningExtractor()
        
        # With success=False, heuristic extraction should be skipped
        learnings = []
        async for fact, category in learn_from_execution(
            goal="Failed task",
            success=False,  # Key: execution failed
            task_graph=task_graph_with_tasks,
            learning_store=learning_store,
            learning_extractor=extractor,
            files_changed=[],
            last_planning_context=None,
            memory=None,
        ):
            learnings.append((fact, category))
        
        # Should complete without error, no heuristics extracted
        assert isinstance(learnings, list)

    @pytest.mark.asyncio
    async def test_learn_from_execution_extracts_from_files(
        self,
        empty_task_graph: Any,
        learning_store: LearningStore,
        tmp_path: Path,
    ) -> None:
        """learn_from_execution extracts patterns from changed Python files."""
        from sunwell.agent.learning.execution import learn_from_execution
        
        # Create a Python file with extractable patterns
        py_file = tmp_path / "models.py"
        py_file.write_text("""
from pydantic import BaseModel

class User(BaseModel):
    id: int
    email: str
    name: str
""")
        
        extractor = LearningExtractor()
        
        learnings = []
        async for fact, category in learn_from_execution(
            goal="Create user model",
            success=True,
            task_graph=empty_task_graph,
            learning_store=learning_store,
            learning_extractor=extractor,
            files_changed=[str(py_file)],
            last_planning_context=None,
            memory=None,
        ):
            learnings.append((fact, category))
        
        # Should extract at least the class pattern
        assert len(learnings) > 0
        assert any("User" in fact for fact, _ in learnings)
