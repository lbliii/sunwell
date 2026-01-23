"""Tests for the demo module (RFC-095)."""

import pytest

from sunwell.demo import (
    BUILTIN_TASKS,
    DemoScorer,
    DemoTask,
    get_task,
    list_tasks,
)


class TestTasks:
    """Tests for demo task loading."""

    def test_list_tasks_returns_all_builtin(self):
        """Should return all built-in task names."""
        tasks = list_tasks()
        assert "divide" in tasks
        assert "add" in tasks
        assert "sort" in tasks
        assert "fibonacci" in tasks
        assert "validate_email" in tasks

    def test_get_builtin_task(self):
        """Should return a DemoTask for built-in names."""
        task = get_task("divide")
        assert isinstance(task, DemoTask)
        assert task.name == "divide"
        assert "divide" in task.prompt.lower()
        assert "type_hints" in task.expected_features

    def test_get_custom_task(self):
        """Should create a custom task from a prompt string."""
        task = get_task("Write a function to parse JSON")
        assert task.name == "custom"
        assert task.prompt == "Write a function to parse JSON"
        assert "type_hints" in task.expected_features

    def test_builtin_tasks_have_expected_features(self):
        """All built-in tasks should have non-empty expected_features."""
        for name, task in BUILTIN_TASKS.items():
            assert len(task.expected_features) > 0, f"{name} has no expected features"


class TestScorer:
    """Tests for deterministic scoring."""

    def test_score_minimal_code(self):
        """Minimal code should score low."""
        scorer = DemoScorer()
        code = "def divide(a, b): return a / b"
        score = scorer.score(code, frozenset(["type_hints", "docstring", "zero_division_handling"]))

        assert score.score < 5.0
        assert not score.features.get("type_hints", True)
        assert not score.features.get("docstring", True)

    def test_score_complete_code(self):
        """Well-written code should score high."""
        scorer = DemoScorer()
        code = '''def divide(a: float, b: float) -> float:
    """Divide two numbers.

    Args:
        a: The dividend.
        b: The divisor.

    Returns:
        The quotient.

    Raises:
        ZeroDivisionError: If b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b
'''
        score = scorer.score(code, frozenset(["type_hints", "docstring", "zero_division_handling"]))

        assert score.score >= 8.0
        assert score.features["type_hints"]
        assert score.features["docstring"]
        assert score.features["zero_division_handling"]

    def test_type_hints_detection(self):
        """Should detect type hints via AST."""
        scorer = DemoScorer()

        # With type hints
        with_hints = "def foo(x: int) -> int: return x"
        assert scorer._has_type_hints(with_hints)

        # Without type hints
        without_hints = "def foo(x): return x"
        assert not scorer._has_type_hints(without_hints)

    def test_docstring_detection(self):
        """Should detect docstrings via AST."""
        scorer = DemoScorer()

        with_doc = '''def foo():
    """A docstring."""
    pass'''
        assert scorer._has_docstring(with_doc)

        without_doc = "def foo(): pass"
        assert not scorer._has_docstring(without_doc)

    def test_error_handling_detection(self):
        """Should detect try/except or raise."""
        scorer = DemoScorer()

        with_raise = "def foo(): raise ValueError()"
        assert scorer._has_error_handling(with_raise)

        with_try = """def foo():
    try:
        x = 1
    except:
        pass"""
        assert scorer._has_error_handling(with_try)

        without = "def foo(): return 1"
        assert not scorer._has_error_handling(without)

    def test_extract_code_from_markdown(self):
        """Should extract code from markdown code blocks."""
        scorer = DemoScorer()

        markdown = """Here's the code:

```python
def foo():
    pass
```

That's it."""

        extracted = scorer._extract_code(markdown)
        assert "def foo():" in extracted
        assert "```" not in extracted

    def test_isinstance_check_detection(self):
        """Should detect isinstance() calls."""
        scorer = DemoScorer()

        with_isinstance = """def foo(x):
    if not isinstance(x, int):
        raise TypeError()
    return x"""
        assert scorer._has_isinstance_check(with_isinstance)

        without = "def foo(x): return x"
        assert not scorer._has_isinstance_check(without)


class TestIntegration:
    """Integration tests for the demo flow."""

    def test_scorer_handles_malformed_code(self):
        """Scorer should handle malformed code gracefully."""
        scorer = DemoScorer()

        # Incomplete code that won't parse
        malformed = "def foo(: return"
        score = scorer.score(malformed, frozenset(["type_hints"]))

        # Should return a score, not crash
        assert isinstance(score.score, float)

    def test_full_scoring_flow(self):
        """Test the complete scoring flow."""
        from sunwell.demo import DemoComparison

        task = get_task("divide")
        scorer = DemoScorer()

        # Simulate single-shot result
        single_shot_code = "def divide(a, b): return a / b"
        single_score = scorer.score(single_shot_code, task.expected_features)

        # Simulate Sunwell result
        sunwell_code = '''def divide(a: float, b: float) -> float:
    """Divide two numbers."""
    if not isinstance(a, (int, float)):
        raise TypeError("a must be numeric")
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b'''
        sunwell_score = scorer.score(sunwell_code, task.expected_features)

        # Sunwell should score higher
        assert sunwell_score.score > single_score.score


class TestHistory:
    """Tests for demo history persistence."""

    def test_history_entry_roundtrip(self):
        """DemoHistoryEntry should serialize and deserialize correctly."""
        from sunwell.demo.history import DemoHistoryEntry

        entry = DemoHistoryEntry(
            timestamp="2026-01-22T12:00:00",
            model_name="ollama:gemma3:4b",
            task_name="divide",
            task_prompt="Write a Python function to divide two numbers",
            single_shot_score=1.5,
            sunwell_score=8.5,
            improvement_percent=467.0,
            single_shot_code="def divide(a, b): return a / b",
            sunwell_code="def divide(a: float, b: float) -> float: ...",
            single_shot_time_ms=100,
            sunwell_time_ms=300,
        )

        # Roundtrip through dict
        data = entry.to_dict()
        restored = DemoHistoryEntry.from_dict(data)

        assert restored.timestamp == entry.timestamp
        assert restored.model_name == entry.model_name
        assert restored.single_shot_score == entry.single_shot_score
        assert restored.improvement_percent == entry.improvement_percent

    def test_get_history_summary_empty(self, tmp_path, monkeypatch):
        """Empty history should return total_runs=0."""
        from sunwell.demo import history

        # Patch to use temp directory
        monkeypatch.setattr(history, "get_history_dir", lambda: tmp_path)

        summary = history.get_history_summary()
        assert summary["total_runs"] == 0

    def test_load_history_empty(self, tmp_path, monkeypatch):
        """Empty history should return empty list."""
        from sunwell.demo import history

        monkeypatch.setattr(history, "get_history_dir", lambda: tmp_path)

        entries = history.load_history()
        assert entries == []
