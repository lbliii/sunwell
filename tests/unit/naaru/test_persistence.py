"""Unit tests for Naaru persistence and checkpointing."""

from pathlib import Path

import pytest

from sunwell.planning.naaru.persistence import (
    ExecutionStatus,
    hash_content,
    hash_file,
    hash_goal,
)


class TestHashFunctions:
    """Test hash utility functions."""

    def test_hash_goal(self) -> None:
        """Test hash_goal produces deterministic hashes."""
        goal1 = "Build a REST API"
        goal2 = "Build a REST API"
        goal3 = "Build a GraphQL API"
        
        hash1 = hash_goal(goal1)
        hash2 = hash_goal(goal2)
        hash3 = hash_goal(goal3)
        
        # Same goal should produce same hash
        assert hash1 == hash2
        
        # Different goals should produce different hashes
        assert hash1 != hash3
        
        # Hash should be 16 characters
        assert len(hash1) == 16
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_hash_content_string(self) -> None:
        """Test hash_content with string."""
        content = "test content"
        hash1 = hash_content(content)
        hash2 = hash_content(content)
        
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_content_bytes(self) -> None:
        """Test hash_content with bytes."""
        content = b"test content"
        hash1 = hash_content(content)
        hash2 = hash_content(content)
        
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_content_different(self) -> None:
        """Test hash_content produces different hashes for different content."""
        hash1 = hash_content("content 1")
        hash2 = hash_content("content 2")
        
        assert hash1 != hash2

    def test_hash_file_exists(self, tmp_path: Path) -> None:
        """Test hash_file with existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        hash1 = hash_file(test_file)
        hash2 = hash_file(test_file)
        
        assert hash1 is not None
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_file_not_exists(self) -> None:
        """Test hash_file with non-existent file."""
        non_existent = Path("/nonexistent/file.txt")
        result = hash_file(non_existent)
        
        assert result is None

    def test_hash_file_changes(self, tmp_path: Path) -> None:
        """Test hash_file changes when content changes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content 1")
        
        hash1 = hash_file(test_file)
        
        test_file.write_text("content 2")
        hash2 = hash_file(test_file)
        
        assert hash1 != hash2


class TestExecutionStatus:
    """Test ExecutionStatus enum."""

    def test_execution_status_values(self) -> None:
        """Test ExecutionStatus has expected values."""
        assert ExecutionStatus.PLANNED.value == "planned"
        assert ExecutionStatus.IN_PROGRESS.value == "in_progress"
        assert ExecutionStatus.PAUSED.value == "paused"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"

    def test_execution_status_from_string(self) -> None:
        """Test ExecutionStatus can be created from string."""
        assert ExecutionStatus("planned") == ExecutionStatus.PLANNED
        assert ExecutionStatus("in_progress") == ExecutionStatus.IN_PROGRESS
