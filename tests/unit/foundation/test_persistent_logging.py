"""Tests for persistent logging with session rotation."""

import logging
import time
from pathlib import Path

import pytest

from sunwell.foundation.logging import configure_logging


@pytest.fixture
def temp_sunwell_dir(tmp_path, monkeypatch):
    """Create temporary .sunwell directory for testing."""
    sunwell_dir = tmp_path / ".sunwell"
    sunwell_dir.mkdir()

    # Make configure_logging find our temp directory
    monkeypatch.chdir(tmp_path)

    yield sunwell_dir

    # Cleanup: clear logging handlers
    root = logging.getLogger()
    root.handlers.clear()


def test_creates_log_directory(temp_sunwell_dir):
    """Test that logging creates .sunwell/logs/ directory."""
    configure_logging(persist=True)

    log_dir = temp_sunwell_dir / "logs"
    assert log_dir.exists()
    assert log_dir.is_dir()


def test_creates_session_log_file(temp_sunwell_dir):
    """Test that each session gets a timestamped log file."""
    configure_logging(persist=True)

    log_dir = temp_sunwell_dir / "logs"
    log_files = list(log_dir.glob("session_*.log"))

    assert len(log_files) == 1
    assert log_files[0].name.startswith("session_")
    assert log_files[0].suffix == ".log"


def test_logs_written_to_file(temp_sunwell_dir):
    """Test that log messages are written to session file."""
    configure_logging(persist=True, level=logging.DEBUG)

    logger = logging.getLogger("test.module")
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    # Flush handlers
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_dir = temp_sunwell_dir / "logs"
    log_files = list(log_dir.glob("session_*.log"))
    log_content = log_files[0].read_text()

    # All messages should be in file (file captures DEBUG+)
    assert "Debug message" in log_content
    assert "Info message" in log_content
    assert "Warning message" in log_content
    assert "Error message" in log_content
    assert "test.module" in log_content


def test_file_uses_debug_format(temp_sunwell_dir):
    """Test that log files always use detailed debug format."""
    configure_logging(persist=True, level=logging.WARNING)  # Console: WARNING

    logger = logging.getLogger("test.format")
    logger.warning("Test message")

    for handler in logging.getLogger().handlers:
        handler.flush()

    log_dir = temp_sunwell_dir / "logs"
    log_files = list(log_dir.glob("session_*.log"))
    log_content = log_files[0].read_text()

    # Should include timestamp, module name, level
    assert "test.format" in log_content
    assert "[WARNING]" in log_content
    # Should have timestamp (YYYY-MM-DD format)
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2}", log_content)


def test_cleanup_old_sessions(temp_sunwell_dir):
    """Test that old session logs are cleaned up."""
    log_dir = temp_sunwell_dir / "logs"
    log_dir.mkdir()

    # Create 12 fake old session logs
    for i in range(12):
        fake_log = log_dir / f"session_2026-01-{i+1:02d}_12-00-00.log"
        fake_log.write_text(f"Session {i}")
        # Small delay to ensure different mtimes
        time.sleep(0.001)

    # Configure logging (should trigger cleanup, keeping last 10)
    configure_logging(persist=True)

    remaining_logs = list(log_dir.glob("session_*.log"))

    # Should have 10 old + 1 new = 11 total
    assert len(remaining_logs) == 11


def test_persist_can_be_disabled(temp_sunwell_dir):
    """Test that persistent logging can be disabled."""
    configure_logging(persist=False)

    log_dir = temp_sunwell_dir / "logs"

    # Directory should not be created if persist=False
    if log_dir.exists():
        log_files = list(log_dir.glob("session_*.log"))
        assert len(log_files) == 0


def test_handles_file_logging_failure(temp_sunwell_dir, monkeypatch, capsys):
    """Test that logging continues if file handler fails."""
    # Make directory creation fail
    def mock_mkdir(*args, **kwargs):
        raise PermissionError("No permission")

    monkeypatch.setattr(Path, "mkdir", mock_mkdir)

    # Should not raise, just warn to stderr
    configure_logging(persist=True, level=logging.WARNING)

    # Logging to console should still work
    logger = logging.getLogger("test.fallback")
    logger.warning("Test warning")

    # Check stderr for warning about file logging failure
    captured = capsys.readouterr()
    assert "Could not enable persistent logging" in captured.err or "No permission" in captured.err
