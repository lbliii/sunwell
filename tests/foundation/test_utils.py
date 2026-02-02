"""Tests for foundation utilities.

RFC-138: Module Architecture Consolidation
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.foundation.utils import (
    absolute_timestamp,
    absolute_timestamp_full,
    compute_file_hash,
    compute_hash,
    compute_string_hash,
    ensure_dir,
    format_for_summary,
    normalize_path,
    relative_to_cwd,
    safe_json_dump,
    safe_json_dumps,
    safe_json_load,
    safe_json_loads,
    safe_jsonl_append,
    safe_jsonl_load,
    safe_yaml_dump,
    safe_yaml_load,
    sanitize_filename,
    slugify,
    validate_slug,
)


class TestStrings:
    """Tests for string utilities."""

    def test_slugify_basic(self) -> None:
        assert slugify("Hello World") == "hello-world"
        assert slugify("test-file") == "test-file"
        assert slugify("Test File 123") == "test-file-123"

    def test_slugify_special_chars(self) -> None:
        assert slugify("file@name#test") == "file-name-test"
        assert slugify("  spaced  ") == "spaced"
        assert slugify("") == "unnamed"

    def test_slugify_preserves_hyphens(self) -> None:
        assert slugify("already-slug") == "already-slug"


class TestValidation:
    """Tests for validation utilities."""

    def test_validate_slug_valid(self) -> None:
        validate_slug("valid-slug")
        validate_slug("test123")
        validate_slug("a")

    def test_validate_slug_invalid_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid slug format"):
            validate_slug("Invalid Slug")
        with pytest.raises(ValueError, match="Invalid slug format"):
            validate_slug("invalid_slug")

    def test_validate_slug_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="path traversal"):
            validate_slug("../etc/passwd")
        with pytest.raises(ValueError, match="path traversal"):
            validate_slug("file/name")
        with pytest.raises(ValueError, match="path traversal"):
            validate_slug("file\\name")


class TestHashing:
    """Tests for hashing utilities."""

    def test_compute_hash(self) -> None:
        result = compute_hash(b"hello")
        assert len(result) == 64  # SHA-256 hex digest
        assert isinstance(result, str)
        # Known hash for "hello"
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_compute_string_hash(self) -> None:
        result = compute_string_hash("hello")
        assert len(result) == 64
        # Should match compute_hash of UTF-8 encoded string
        assert result == compute_hash("hello".encode("utf-8"))

    def test_compute_file_hash(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello", encoding="utf-8")

        result = compute_file_hash(test_file)
        assert len(result) == 64
        assert result == compute_string_hash("hello")

    def test_compute_file_hash_nonexistent(self) -> None:
        with pytest.raises(FileNotFoundError):
            compute_file_hash(Path("/nonexistent/file.txt"))


class TestPaths:
    """Tests for path utilities."""

    def test_normalize_path_string(self) -> None:
        result = normalize_path("test.txt")
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_normalize_path_path(self) -> None:
        p = Path("test.txt")
        result = normalize_path(p)
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_sanitize_filename_basic(self) -> None:
        assert sanitize_filename("test.txt") == "test.txt"
        assert sanitize_filename("file-name") == "file-name"

    def test_sanitize_filename_invalid_chars(self) -> None:
        assert sanitize_filename("file/name") == "file-name"
        assert sanitize_filename("file:name") == "file-name"
        assert sanitize_filename("file\\name") == "file-name"

    def test_sanitize_filename_windows_reserved(self) -> None:
        assert sanitize_filename("CON.txt").startswith("_")
        assert sanitize_filename("PRN").startswith("_")

    def test_sanitize_filename_empty(self) -> None:
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("   ") == "unnamed"

    def test_ensure_dir(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new" / "subdir"
        result = ensure_dir(new_dir)
        assert result.exists()
        assert result.is_dir()
        assert result == new_dir

    def test_ensure_dir_existing(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing"
        existing.mkdir()
        result = ensure_dir(existing)
        assert result.exists()

    def test_relative_to_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "file.txt"
        test_file.touch()

        result = relative_to_cwd(test_file)
        assert result == Path("file.txt")

    def test_relative_to_cwd_outside_cwd(self, tmp_path: Path) -> None:
        outside = Path("/tmp")
        result = relative_to_cwd(outside)
        assert result.is_absolute()


class TestSerialization:
    """Tests for serialization utilities."""

    def test_safe_json_loads_valid(self) -> None:
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_json_loads_list(self) -> None:
        result = safe_json_loads('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_safe_json_loads_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid JSON"):
            safe_json_loads("{invalid}")

    def test_safe_json_dumps_basic(self) -> None:
        result = safe_json_dumps({"key": "value"})
        assert result == '{"key":"value"}'

    def test_safe_json_dumps_with_indent(self) -> None:
        result = safe_json_dumps({"key": "value"}, indent=2)
        assert "  " in result  # Should have indentation

    def test_safe_yaml_load(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\nnumber: 42\n", encoding="utf-8")

        result = safe_yaml_load(yaml_file)
        assert result == {"key": "value", "number": 42}

    def test_safe_yaml_load_nonexistent(self) -> None:
        with pytest.raises(FileNotFoundError):
            safe_yaml_load(Path("/nonexistent/file.yaml"))

    def test_safe_yaml_load_invalid(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: content: [", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid YAML"):
            safe_yaml_load(yaml_file)

    def test_safe_yaml_dump(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "output.yaml"
        data = {"key": "value", "number": 42}

        safe_yaml_dump(data, yaml_file)
        assert yaml_file.exists()

        # Verify content
        content = yaml_file.read_text(encoding="utf-8")
        assert "key: value" in content
        assert "number: 42" in content

    def test_safe_yaml_load_not_dict(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "list.yaml"
        yaml_file.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ValueError, match="must contain a dict"):
            safe_yaml_load(yaml_file)


class TestCrashTolerantJsonIO:
    """Tests for crash-tolerant JSON file I/O (safe_json_load/dump)."""

    def test_safe_json_load_valid(self, tmp_path: Path) -> None:
        """Load valid JSON file."""
        json_file = tmp_path / "data.json"
        json_file.write_text('{"key": "value", "num": 42}', encoding="utf-8")

        result = safe_json_load(json_file)
        assert result == {"key": "value", "num": 42}

    def test_safe_json_load_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns default."""
        result = safe_json_load(tmp_path / "nonexistent.json")
        assert result is None

        result = safe_json_load(tmp_path / "nonexistent.json", default={})
        assert result == {}

        result = safe_json_load(tmp_path / "nonexistent.json", default={"version": 1})
        assert result == {"version": 1}

    def test_safe_json_load_corrupted_file(self, tmp_path: Path) -> None:
        """Corrupted JSON returns default instead of raising."""
        json_file = tmp_path / "bad.json"
        json_file.write_text("{invalid json content", encoding="utf-8")

        result = safe_json_load(json_file)
        assert result is None

        result = safe_json_load(json_file, default={"fallback": True})
        assert result == {"fallback": True}

    def test_safe_json_load_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns default."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("", encoding="utf-8")

        result = safe_json_load(json_file, default={})
        assert result == {}

    def test_safe_json_dump_basic(self, tmp_path: Path) -> None:
        """Basic JSON dump creates file."""
        json_file = tmp_path / "output.json"
        data = {"key": "value", "list": [1, 2, 3]}

        success = safe_json_dump(data, json_file)
        assert success is True
        assert json_file.exists()

        # Verify content
        loaded = json.loads(json_file.read_text(encoding="utf-8"))
        assert loaded == data

    def test_safe_json_dump_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Creates parent directories if needed."""
        json_file = tmp_path / "deep" / "nested" / "dir" / "data.json"

        success = safe_json_dump({"test": True}, json_file)
        assert success is True
        assert json_file.exists()

    def test_safe_json_dump_atomic_no_partial_write(self, tmp_path: Path) -> None:
        """Atomic write shouldn't leave partial files on serialization error."""
        json_file = tmp_path / "atomic.json"

        # Write some initial data
        safe_json_dump({"initial": "data"}, json_file)

        # Try to write unserializable data (should fail)
        class NotSerializable:
            pass

        success = safe_json_dump({"bad": NotSerializable()}, json_file)
        assert success is False

        # Original file should be unchanged (atomic = no partial writes)
        loaded = json.loads(json_file.read_text(encoding="utf-8"))
        assert loaded == {"initial": "data"}

    def test_safe_json_dump_overwrites_existing(self, tmp_path: Path) -> None:
        """Overwrites existing file completely."""
        json_file = tmp_path / "overwrite.json"

        safe_json_dump({"version": 1, "old_key": "old_value"}, json_file)
        safe_json_dump({"version": 2, "new_key": "new_value"}, json_file)

        loaded = json.loads(json_file.read_text(encoding="utf-8"))
        assert loaded == {"version": 2, "new_key": "new_value"}
        assert "old_key" not in loaded

    def test_safe_json_dump_non_atomic_mode(self, tmp_path: Path) -> None:
        """Non-atomic mode also works."""
        json_file = tmp_path / "non_atomic.json"

        success = safe_json_dump({"test": True}, json_file, atomic=False)
        assert success is True
        assert json_file.exists()


class TestJsonlIO:
    """Tests for JSONL (JSON Lines) I/O."""

    def test_safe_jsonl_append_creates_file(self, tmp_path: Path) -> None:
        """Appending to non-existent file creates it."""
        jsonl_file = tmp_path / "events.jsonl"

        success = safe_jsonl_append({"event": "first"}, jsonl_file)
        assert success is True
        assert jsonl_file.exists()

        content = jsonl_file.read_text(encoding="utf-8")
        assert content == '{"event": "first"}\n'

    def test_safe_jsonl_append_multiple(self, tmp_path: Path) -> None:
        """Multiple appends create multiple lines."""
        jsonl_file = tmp_path / "events.jsonl"

        safe_jsonl_append({"id": 1}, jsonl_file)
        safe_jsonl_append({"id": 2}, jsonl_file)
        safe_jsonl_append({"id": 3}, jsonl_file)

        lines = jsonl_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0]) == {"id": 1}
        assert json.loads(lines[2]) == {"id": 3}

    def test_safe_jsonl_load_empty(self, tmp_path: Path) -> None:
        """Loading non-existent file returns empty list."""
        result = safe_jsonl_load(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_safe_jsonl_load_valid(self, tmp_path: Path) -> None:
        """Load valid JSONL file."""
        jsonl_file = tmp_path / "data.jsonl"
        jsonl_file.write_text(
            '{"id": 1, "name": "first"}\n'
            '{"id": 2, "name": "second"}\n'
            '{"id": 3, "name": "third"}\n',
            encoding="utf-8",
        )

        result = safe_jsonl_load(jsonl_file)
        assert len(result) == 3
        assert result[0] == {"id": 1, "name": "first"}
        assert result[2] == {"id": 3, "name": "third"}

    def test_safe_jsonl_load_skips_corrupted_lines(self, tmp_path: Path) -> None:
        """Corrupted lines are skipped, valid lines are kept."""
        jsonl_file = tmp_path / "partial.jsonl"
        jsonl_file.write_text(
            '{"id": 1}\n'
            '{bad json}\n'  # Corrupted
            '{"id": 2}\n'
            'not json at all\n'  # Corrupted
            '{"id": 3}\n',
            encoding="utf-8",
        )

        result = safe_jsonl_load(jsonl_file)
        assert len(result) == 3
        assert result == [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_safe_jsonl_load_skips_empty_lines(self, tmp_path: Path) -> None:
        """Empty lines are skipped."""
        jsonl_file = tmp_path / "sparse.jsonl"
        jsonl_file.write_text(
            '{"id": 1}\n'
            '\n'
            '   \n'
            '{"id": 2}\n',
            encoding="utf-8",
        )

        result = safe_jsonl_load(jsonl_file)
        assert len(result) == 2

    def test_safe_jsonl_roundtrip(self, tmp_path: Path) -> None:
        """Append then load preserves data."""
        jsonl_file = tmp_path / "roundtrip.jsonl"

        records = [
            {"type": "start", "ts": "2025-01-01"},
            {"type": "event", "data": [1, 2, 3]},
            {"type": "end", "ts": "2025-01-02"},
        ]

        for record in records:
            safe_jsonl_append(record, jsonl_file)

        loaded = safe_jsonl_load(jsonl_file)
        assert loaded == records


class TestTimestamps:
    """Tests for timestamp utilities (first-person voice support)."""

    def test_absolute_timestamp_current_year(self) -> None:
        """Timestamp for current year omits year."""
        now = datetime.now()
        dt = datetime(now.year, 2, 15)
        result = absolute_timestamp(dt)
        assert result == "On Feb 15"
        assert str(now.year) not in result

    def test_absolute_timestamp_previous_year(self) -> None:
        """Timestamp for previous year includes year."""
        now = datetime.now()
        dt = datetime(now.year - 1, 12, 25)
        result = absolute_timestamp(dt)
        assert result == f"On Dec 25, {now.year - 1}"

    def test_absolute_timestamp_defaults_to_now(self) -> None:
        """Without argument, uses current time."""
        result = absolute_timestamp()
        assert result.startswith("On ")
        # Should contain month abbreviation
        assert any(m in result for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])

    def test_absolute_timestamp_full_current_year(self) -> None:
        """Full timestamp includes time component."""
        now = datetime.now()
        dt = datetime(now.year, 3, 10, 14, 30)
        result = absolute_timestamp_full(dt)
        assert "On Mar 10" in result
        assert "2:30 PM" in result

    def test_absolute_timestamp_full_previous_year(self) -> None:
        """Full timestamp for previous year includes year and time."""
        now = datetime.now()
        dt = datetime(now.year - 1, 7, 4, 9, 15)
        result = absolute_timestamp_full(dt)
        assert f"On Jul 4, {now.year - 1}" in result
        assert "9:15 AM" in result

    def test_format_for_summary(self) -> None:
        """format_for_summary is alias for absolute_timestamp."""
        dt = datetime(2025, 6, 15)
        assert format_for_summary(dt) == absolute_timestamp(dt)
