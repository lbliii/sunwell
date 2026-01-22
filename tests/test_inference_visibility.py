"""Tests for Inference Visibility (RFC-081).

Tests for:
- ThinkingDetector: Parsing <think> blocks from streams
- InferenceMetrics: Recording and calculating performance stats
- Event factories: Model visibility events
"""

import pytest

from sunwell.adaptive.events import (
    EventType,
    model_complete_event,
    model_start_event,
    model_thinking_event,
    model_tokens_event,
)
from sunwell.adaptive.metrics import (
    InferenceMetrics,
    ModelPerformanceProfile,
    load_profiles_from_disk,
    recommend_model,
    save_profiles_to_disk,
)
from sunwell.adaptive.thinking import ThinkingDetector


# =============================================================================
# ThinkingDetector Tests
# =============================================================================


class TestThinkingDetector:
    """Tests for thinking block detection in streaming output."""

    def test_detect_think_block(self):
        """Detect a complete <think> block."""
        detector = ThinkingDetector()

        # Feed chunks that form a complete think block
        blocks = detector.feed("<think>")
        assert len(blocks) == 1
        assert blocks[0].phase == "think"
        assert blocks[0].is_complete is False

        blocks = detector.feed("This is my reasoning process.")
        assert len(blocks) == 0  # Still accumulating

        blocks = detector.feed("</think>")
        assert len(blocks) == 1
        assert blocks[0].phase == "think"
        assert blocks[0].is_complete is True
        assert "reasoning process" in blocks[0].content

    def test_detect_critic_block(self):
        """Detect a <critic> block."""
        detector = ThinkingDetector()

        detector.feed("<critic>")
        blocks = detector.feed("Let me evaluate this approach.</critic>")

        # Should have one completed block
        completed = [b for b in blocks if b.is_complete]
        assert len(completed) == 1
        assert completed[0].phase == "critic"

    def test_detect_synthesize_block(self):
        """Detect a <synthesize> block."""
        detector = ThinkingDetector()

        detector.feed("<synthesize>Combining insights...</synthesize>")
        # The completed block should be detected
        assert not detector.is_thinking()

    def test_no_false_positives(self):
        """Don't detect blocks in regular text."""
        detector = ThinkingDetector()

        blocks = detector.feed("Here is some normal code output.")
        assert len(blocks) == 0
        assert not detector.is_thinking()

    def test_is_thinking_state(self):
        """Track whether currently inside a thinking block."""
        detector = ThinkingDetector()

        assert not detector.is_thinking()

        detector.feed("<think>Starting to think...")
        assert detector.is_thinking()

        detector.feed("</think>")
        assert not detector.is_thinking()

    def test_get_current_thinking(self):
        """Get partial thinking content while in a block."""
        detector = ThinkingDetector()

        detector.feed("<think>Step 1: ")
        content = detector.get_current_thinking()
        assert content is not None
        assert "Step 1" in content

        detector.feed("Analyze the problem.</think>")
        assert detector.get_current_thinking() is None  # Block closed

    def test_reset(self):
        """Reset clears all state."""
        detector = ThinkingDetector()

        detector.feed("<think>Some content")
        assert detector.is_thinking()

        detector.reset()
        assert not detector.is_thinking()
        assert detector.get_current_thinking() is None


# =============================================================================
# InferenceMetrics Tests
# =============================================================================


class TestInferenceMetrics:
    """Tests for inference performance tracking."""

    def test_record_and_retrieve(self):
        """Record samples and calculate stats."""
        metrics = InferenceMetrics()

        metrics.record("gpt-oss:20b", duration_s=10.0, tokens=300, ttft_ms=1500)
        metrics.record("gpt-oss:20b", duration_s=12.0, tokens=400, ttft_ms=1800)

        stats = metrics.get_model_stats("gpt-oss:20b")
        assert stats["sample_count"] == 2
        assert stats["total_tokens"] == 700
        assert 25 < stats["avg_tokens_per_second"] < 35  # ~30 tok/s
        assert 1600 < stats["avg_ttft_ms"] < 1700  # ~1650ms

    def test_empty_model_stats(self):
        """Empty stats for unknown model."""
        metrics = InferenceMetrics()

        stats = metrics.get_model_stats("unknown-model")
        assert stats == {}

    def test_estimate_time(self):
        """Estimate generation time from history."""
        metrics = InferenceMetrics()

        # Record samples to establish baseline
        metrics.record("gemma3:4b", duration_s=5.0, tokens=400, ttft_ms=200)
        metrics.record("gemma3:4b", duration_s=6.0, tokens=480, ttft_ms=250)

        # Estimate for 500 tokens
        estimated = metrics.estimate_time("gemma3:4b", prompt_tokens=100, expected_output=500)
        assert estimated is not None
        assert 5 < estimated < 10  # Should be ~6-7 seconds

    def test_estimate_time_no_data(self):
        """Return None when no historical data."""
        metrics = InferenceMetrics()

        estimated = metrics.estimate_time("unknown", prompt_tokens=100)
        assert estimated is None

    def test_get_all_models(self):
        """List all models with recorded data."""
        metrics = InferenceMetrics()

        metrics.record("model-a", duration_s=1, tokens=100)
        metrics.record("model-b", duration_s=2, tokens=200)
        metrics.record("model-a", duration_s=1, tokens=100)

        models = metrics.get_all_models()
        assert "model-a" in models
        assert "model-b" in models
        assert len(models) == 2


class TestModelPerformanceProfile:
    """Tests for accumulated model performance profiles."""

    def test_update_from_sample(self):
        """Update profile with new samples."""
        profile = ModelPerformanceProfile(model="test-model")

        profile.update_from_sample(duration_s=10.0, tokens=300, ttft_ms=1000)
        assert profile.samples == 1
        assert profile.total_tokens == 300
        assert profile.avg_tokens_per_second == 30.0
        assert profile.avg_ttft_ms == 1000.0

        profile.update_from_sample(duration_s=10.0, tokens=200, ttft_ms=800)
        assert profile.samples == 2
        assert profile.total_tokens == 500
        assert profile.avg_tokens_per_second == 25.0  # 500/20
        assert profile.avg_ttft_ms == 900.0  # (1000+800)/2

    def test_gate_pass_rate(self):
        """Calculate quality from gate results."""
        profile = ModelPerformanceProfile(model="test-model")

        # No data yet
        assert profile.gate_pass_rate is None

        profile.record_gate_result(passed=True)
        profile.record_gate_result(passed=True)
        profile.record_gate_result(passed=False)

        assert profile.gate_pass_rate == pytest.approx(2 / 3)

    def test_quality_speed_score(self):
        """Combined quality * speed score."""
        profile = ModelPerformanceProfile(model="test-model")
        profile.avg_tokens_per_second = 50.0  # 50% of "fast" (100)
        profile.record_gate_result(passed=True)
        profile.record_gate_result(passed=True)

        # 100% pass rate * 0.5 speed = 0.5
        assert profile.quality_speed_score == pytest.approx(0.5)


class TestRecommendModel:
    """Tests for model recommendation."""

    def test_recommend_by_speed(self):
        """Recommend fastest model."""
        profiles = {
            "fast": ModelPerformanceProfile(model="fast"),
            "slow": ModelPerformanceProfile(model="slow"),
        }
        profiles["fast"].samples = 10
        profiles["fast"].avg_tokens_per_second = 80.0
        profiles["slow"].samples = 10
        profiles["slow"].avg_tokens_per_second = 20.0

        result = recommend_model(profiles, "code", user_preference="speed")
        assert result == "fast"

    def test_recommend_by_quality(self):
        """Recommend highest quality model."""
        profiles = {
            "quality": ModelPerformanceProfile(model="quality"),
            "fast": ModelPerformanceProfile(model="fast"),
        }
        profiles["quality"].samples = 10
        profiles["quality"].gates_passed = 9
        profiles["quality"].gates_failed = 1
        profiles["fast"].samples = 10
        profiles["fast"].gates_passed = 5
        profiles["fast"].gates_failed = 5

        result = recommend_model(profiles, "code", user_preference="quality")
        assert result == "quality"

    def test_recommend_no_data(self):
        """Return None with insufficient data."""
        profiles = {
            "new": ModelPerformanceProfile(model="new"),
        }
        profiles["new"].samples = 2  # Less than 5

        result = recommend_model(profiles, "code")
        assert result is None


# =============================================================================
# Event Factory Tests
# =============================================================================


class TestInferenceMetricsPersistence:
    """Tests for disk persistence of inference metrics."""

    def test_save_and_load_metrics(self, tmp_path):
        """Save metrics to disk and load them back."""
        metrics = InferenceMetrics()
        metrics.record("model-a", duration_s=10.0, tokens=300, ttft_ms=1500)
        metrics.record("model-a", duration_s=12.0, tokens=400, ttft_ms=1800)
        metrics.record("model-b", duration_s=5.0, tokens=200)

        # Save to disk
        saved = metrics.save_to_disk(tmp_path)
        assert saved == 2  # Two models

        # Load into new instance
        loaded_metrics = InferenceMetrics()
        loaded = loaded_metrics.load_from_disk(tmp_path)
        assert loaded == 2

        # Verify data
        stats_a = loaded_metrics.get_model_stats("model-a")
        assert stats_a["sample_count"] == 2
        assert stats_a["total_tokens"] == 700

        stats_b = loaded_metrics.get_model_stats("model-b")
        assert stats_b["sample_count"] == 1

    def test_load_nonexistent_file(self, tmp_path):
        """Loading from nonexistent file returns 0."""
        metrics = InferenceMetrics()
        loaded = metrics.load_from_disk(tmp_path)
        assert loaded == 0

    def test_merge_metrics(self):
        """Merge samples from two metrics instances."""
        metrics1 = InferenceMetrics()
        metrics1.record("model-a", duration_s=10.0, tokens=300)

        metrics2 = InferenceMetrics()
        metrics2.record("model-a", duration_s=12.0, tokens=400)
        metrics2.record("model-b", duration_s=5.0, tokens=200)

        merged = metrics1.merge_from(metrics2)
        assert merged == 2  # Two samples merged

        # model-a should have 2 samples now
        stats = metrics1.get_model_stats("model-a")
        assert stats["sample_count"] == 2


class TestProfilePersistence:
    """Tests for disk persistence of model profiles."""

    def test_save_and_load_profiles(self, tmp_path):
        """Save profiles to disk and load them back."""
        profiles = {
            "model-a": ModelPerformanceProfile(model="model-a"),
            "model-b": ModelPerformanceProfile(model="model-b"),
        }
        profiles["model-a"].samples = 10
        profiles["model-a"].avg_tokens_per_second = 30.0
        profiles["model-a"].gates_passed = 8
        profiles["model-a"].gates_failed = 2

        # Save
        saved = save_profiles_to_disk(profiles, tmp_path)
        assert saved == 2

        # Load
        loaded = load_profiles_from_disk(tmp_path)
        assert len(loaded) == 2
        assert loaded["model-a"].samples == 10
        assert loaded["model-a"].avg_tokens_per_second == 30.0
        assert loaded["model-a"].gates_passed == 8

    def test_load_nonexistent_profiles(self, tmp_path):
        """Loading from nonexistent file returns empty dict."""
        loaded = load_profiles_from_disk(tmp_path)
        assert loaded == {}


class TestModelEvents:
    """Tests for model visibility event factories."""

    def test_model_start_event(self):
        """Create model start event."""
        event = model_start_event(
            task_id="task-1",
            model="gpt-oss:20b",
            prompt_tokens=500,
            estimated_time_s=15.0,
        )

        assert event.type == EventType.MODEL_START
        assert event.data["task_id"] == "task-1"
        assert event.data["model"] == "gpt-oss:20b"
        assert event.data["prompt_tokens"] == 500
        assert event.data["estimated_time_s"] == 15.0

    def test_model_tokens_event(self):
        """Create model tokens event."""
        event = model_tokens_event(
            task_id="task-1",
            tokens="def hello():",
            token_count=150,
            tokens_per_second=30.5,
        )

        assert event.type == EventType.MODEL_TOKENS
        assert event.data["tokens"] == "def hello():"
        assert event.data["token_count"] == 150
        assert event.data["tokens_per_second"] == 30.5

    def test_model_thinking_event(self):
        """Create model thinking event."""
        event = model_thinking_event(
            task_id="task-1",
            phase="think",
            content="Let me analyze this...",
            is_complete=True,
        )

        assert event.type == EventType.MODEL_THINKING
        assert event.data["phase"] == "think"
        assert event.data["is_complete"] is True

    def test_model_complete_event(self):
        """Create model complete event."""
        event = model_complete_event(
            task_id="task-1",
            total_tokens=450,
            duration_s=15.0,
            tokens_per_second=30.0,
            time_to_first_token_ms=1500,
        )

        assert event.type == EventType.MODEL_COMPLETE
        assert event.data["total_tokens"] == 450
        assert event.data["duration_s"] == 15.0
        assert event.data["time_to_first_token_ms"] == 1500
