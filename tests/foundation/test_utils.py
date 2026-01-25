"""Tests for foundation utilities.

RFC-138: Module Architecture Consolidation
"""

import json
import tempfile
from pathlib import Path

import pytest

from sunwell.foundation.utils import (
    compute_file_hash,
    compute_hash,
    compute_string_hash,
    ensure_dir,
    normalize_path,
    relative_to_cwd,
    safe_json_dumps,
    safe_json_loads,
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
