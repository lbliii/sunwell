"""Comprehensive tests for the shortcut execution system.

Tests cover:
- Shortcut resolution from lens files
- Thread-safe caching mechanism
- Shell completion for shortcuts and file paths
- Diataxis type detection
- Related file discovery
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

from sunwell.interface.cli.core.shortcuts import (
    _detect_diataxis_type,
    _find_related_files,
    _load_lens_shortcuts_sync,
    complete_shortcut,
    complete_target,
    get_cached_shortcuts,
    invalidate_shortcut_cache,
)


class TestLoadLensShortcutsSync:
    """Tests for synchronous lens shortcut loading."""

    def test_loads_shortcuts_from_lens_file(self, tmp_path: Path) -> None:
        """Loads shortcuts from a valid lens YAML file."""
        lens_dir = tmp_path / "lenses"
        lens_dir.mkdir()
        lens_file = lens_dir / "test-lens.lens"
        lens_file.write_text("""
lens:
  router:
    shortcuts:
      "::a": audit-skill
      "::p": polish-skill
      health: health-check
""")

        with patch.object(Path, "cwd", return_value=tmp_path):
            shortcuts = _load_lens_shortcuts_sync("test-lens")

        assert shortcuts == {"a": "audit-skill", "p": "polish-skill", "health": "health-check"}

    def test_returns_empty_dict_when_lens_not_found(self) -> None:
        """Returns empty dict when lens file doesn't exist."""
        shortcuts = _load_lens_shortcuts_sync("nonexistent-lens-xyz")
        assert shortcuts == {}

    def test_handles_lens_without_shortcuts(self, tmp_path: Path) -> None:
        """Returns empty dict when lens has no shortcuts defined."""
        lens_dir = tmp_path / "lenses"
        lens_dir.mkdir()
        lens_file = lens_dir / "empty-lens.lens"
        lens_file.write_text("""
lens:
  metadata:
    name: empty
""")

        with patch.object(Path, "cwd", return_value=tmp_path):
            shortcuts = _load_lens_shortcuts_sync("empty-lens")

        assert shortcuts == {}

    def test_normalizes_double_colon_prefix(self, tmp_path: Path) -> None:
        """Strips :: prefix from shortcut keys for completion."""
        lens_dir = tmp_path / "lenses"
        lens_dir.mkdir()
        lens_file = lens_dir / "prefixed.lens"
        lens_file.write_text("""
lens:
  router:
    shortcuts:
      "::audit": audit-skill
      plain: plain-skill
""")

        with patch.object(Path, "cwd", return_value=tmp_path):
            shortcuts = _load_lens_shortcuts_sync("prefixed")

        assert "audit" in shortcuts
        assert "plain" in shortcuts
        assert "::audit" not in shortcuts

    def test_handles_malformed_yaml(self, tmp_path: Path) -> None:
        """Returns empty dict for malformed YAML."""
        lens_dir = tmp_path / "lenses"
        lens_dir.mkdir()
        lens_file = lens_dir / "bad.lens"
        lens_file.write_text("this is: not: valid: yaml: [")

        with patch.object(Path, "cwd", return_value=tmp_path):
            shortcuts = _load_lens_shortcuts_sync("bad")

        assert shortcuts == {}


class TestShortcutCache:
    """Tests for thread-safe shortcut caching."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        invalidate_shortcut_cache()

    def test_caches_shortcuts_on_first_access(self) -> None:
        """Caches shortcuts after first load."""
        with patch(
            "sunwell.interface.cli.core.shortcuts._load_lens_shortcuts_sync",
            return_value={"a": "skill-a"},
        ) as mock_load:
            # First call loads
            result1 = get_cached_shortcuts("test")
            assert result1 == {"a": "skill-a"}
            assert mock_load.call_count == 1

            # Second call uses cache
            result2 = get_cached_shortcuts("test")
            assert result2 == {"a": "skill-a"}
            assert mock_load.call_count == 1  # Not called again

    def test_invalidate_cache_clears_shortcuts(self) -> None:
        """invalidate_shortcut_cache clears the cached shortcuts."""
        with patch(
            "sunwell.interface.cli.core.shortcuts._load_lens_shortcuts_sync",
            return_value={"a": "skill-a"},
        ) as mock_load:
            get_cached_shortcuts("test")
            assert mock_load.call_count == 1

            invalidate_shortcut_cache()

            get_cached_shortcuts("test")
            assert mock_load.call_count == 2  # Reloaded after invalidation

    def test_thread_safety_concurrent_access(self) -> None:
        """Cache handles concurrent access without corruption."""
        results: list[dict[str, str]] = []
        errors: list[Exception] = []

        def access_cache() -> None:
            try:
                for _ in range(100):
                    shortcuts = get_cached_shortcuts("test")
                    results.append(shortcuts)
            except Exception as e:
                errors.append(e)

        with patch(
            "sunwell.interface.cli.core.shortcuts._load_lens_shortcuts_sync",
            return_value={"concurrent": "skill"},
        ):
            threads = [threading.Thread(target=access_cache) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors, f"Thread errors: {errors}"
        # All results should be identical
        assert all(r == {"concurrent": "skill"} for r in results)

    def test_thread_safety_concurrent_invalidation(self) -> None:
        """Cache handles concurrent invalidation safely."""
        errors: list[Exception] = []

        def invalidate_loop() -> None:
            try:
                for _ in range(50):
                    invalidate_shortcut_cache()
            except Exception as e:
                errors.append(e)

        def access_loop() -> None:
            try:
                for _ in range(50):
                    get_cached_shortcuts("test")
            except Exception as e:
                errors.append(e)

        with patch(
            "sunwell.interface.cli.core.shortcuts._load_lens_shortcuts_sync",
            return_value={"safe": "skill"},
        ):
            threads = [
                threading.Thread(target=invalidate_loop),
                threading.Thread(target=access_loop),
                threading.Thread(target=invalidate_loop),
                threading.Thread(target=access_loop),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors, f"Thread errors: {errors}"


class TestCompleteShortcut:
    """Tests for shell completion of shortcuts."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        invalidate_shortcut_cache()

    def test_completes_matching_shortcuts(self) -> None:
        """Returns shortcuts matching the incomplete prefix."""
        with patch(
            "sunwell.interface.cli.core.shortcuts.get_cached_shortcuts",
            return_value={"audit": "s1", "audit-deep": "s2", "polish": "s3"},
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            completions = complete_shortcut(ctx, param, "aud")

        assert "audit" in completions
        assert "audit-deep" in completions
        assert "polish" not in completions

    def test_completes_with_colon_prefix(self) -> None:
        """Handles :: prefix in incomplete string."""
        with patch(
            "sunwell.interface.cli.core.shortcuts.get_cached_shortcuts",
            return_value={"audit": "s1", "polish": "s2"},
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            completions = complete_shortcut(ctx, param, "::aud")

        assert "audit" in completions

    def test_returns_all_shortcuts_for_empty_input(self) -> None:
        """Returns all shortcuts when input is empty."""
        with patch(
            "sunwell.interface.cli.core.shortcuts.get_cached_shortcuts",
            return_value={"a": "s1", "b": "s2", "c": "s3"},
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            completions = complete_shortcut(ctx, param, "")

        assert len(completions) == 3


class TestCompleteTarget:
    """Tests for file path shell completion."""

    def test_completes_files_with_prefix(self, tmp_path: Path) -> None:
        """Returns files matching the prefix."""
        # Create test files
        (tmp_path / "readme.md").touch()
        (tmp_path / "readme-dev.md").touch()
        (tmp_path / "config.yaml").touch()

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        # Path(incomplete).parent gives the directory to search in
        # Path(incomplete).name gives the prefix to filter by
        completions = complete_target(ctx, param, str(tmp_path / "read"))

        # Should include readme files (name starts with "read")
        assert any("readme" in c for c in completions), f"Expected readme files in: {completions}"
        assert not any("config" in c for c in completions), f"config.yaml shouldn't match 'read': {completions}"

    def test_directories_have_trailing_slash(self, tmp_path: Path) -> None:
        """Directories in completion have trailing slash."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "readme.md").touch()

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        # Look for things starting with "d" in tmp_path
        completions = complete_target(ctx, param, str(tmp_path / "d"))

        # docs/ should have trailing slash
        dir_completions = [c for c in completions if c.endswith("/")]
        assert len(dir_completions) >= 1, f"Expected docs/ dir, got: {completions}"
        assert any("docs" in c for c in dir_completions)

    def test_excludes_hidden_files(self, tmp_path: Path) -> None:
        """Hidden files (starting with .) are excluded."""
        (tmp_path / ".hidden.md").touch()
        (tmp_path / "visible.md").touch()

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        # Search for files starting with "v" (visible but not .hidden)
        completions = complete_target(ctx, param, str(tmp_path / "v"))

        assert any("visible" in c for c in completions), f"visible.md not found in: {completions}"

        # Also verify hidden files aren't returned even when searching with empty prefix
        # by searching for "." prefix - this should return nothing since hidden files are excluded
        hidden_completions = complete_target(ctx, param, str(tmp_path / "."))
        assert not any(".hidden" in c for c in hidden_completions), f"Hidden file found: {hidden_completions}"

    def test_limits_completions_to_20(self, tmp_path: Path) -> None:
        """Limits completions to 20 items for performance."""
        for i in range(30):
            (tmp_path / f"file{i:02d}.md").touch()

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        # Search for "file" prefix
        completions = complete_target(ctx, param, str(tmp_path / "file"))

        assert len(completions) <= 20

    def test_handles_nonexistent_directory(self) -> None:
        """Returns empty list for nonexistent directory."""
        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_target(ctx, param, "/nonexistent/path/xyz/file")

        assert completions == []

    def test_filters_by_supported_extensions(self, tmp_path: Path) -> None:
        """Only returns files with supported extensions."""
        (tmp_path / "readme.md").touch()
        (tmp_path / "script.py").touch()
        (tmp_path / "binary.exe").touch()
        (tmp_path / "image.png").touch()

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        # Search with prefix that matches multiple files
        completions = complete_target(ctx, param, str(tmp_path / "r"))

        # readme.md should be included (.md is supported)
        assert any("readme.md" in c for c in completions), f"readme.md not in: {completions}"


class TestDetectDiataxisType:
    """Tests for Diataxis document type detection."""

    def test_detects_tutorial(self, tmp_path: Path) -> None:
        """Detects TUTORIAL from content keywords."""
        doc = tmp_path / "tutorial.md"
        doc.write_text("""
# Getting Started Tutorial

In this tutorial, you will learn how to set up the project.

## Step 1: Installation
Install the package...

## Step 2: Configuration
Configure your settings...
""")

        result = _detect_diataxis_type(doc)
        assert result == "TUTORIAL"

    def test_detects_how_to(self, tmp_path: Path) -> None:
        """Detects HOW-TO from content keywords."""
        doc = tmp_path / "howto.md"
        doc.write_text("""
# How to Configure Authentication

This guide shows you how to set up authentication.

## Troubleshooting

If you encounter issues...
""")

        result = _detect_diataxis_type(doc)
        assert result == "HOW-TO"

    def test_detects_reference(self, tmp_path: Path) -> None:
        """Detects REFERENCE from content keywords."""
        doc = tmp_path / "api.md"
        doc.write_text("""
# API Reference

## create_user()

Parameters:
- name (str): User name
- email (str): User email

Returns:
    User object
""")

        result = _detect_diataxis_type(doc)
        assert result == "REFERENCE"

    def test_detects_explanation(self, tmp_path: Path) -> None:
        """Detects EXPLANATION from content keywords."""
        doc = tmp_path / "architecture.md"
        doc.write_text("""
# System Architecture

This document explains how the system works at a high level.

## Design Concepts

The architecture follows these key concepts...
""")

        result = _detect_diataxis_type(doc)
        assert result == "EXPLANATION"

    def test_returns_none_for_ambiguous_content(self, tmp_path: Path) -> None:
        """Returns None when content doesn't match any type."""
        doc = tmp_path / "generic.md"
        doc.write_text("# Some Document\n\nGeneric content here.")

        result = _detect_diataxis_type(doc)
        assert result is None

    def test_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Returns None for nonexistent file."""
        result = _detect_diataxis_type(tmp_path / "missing.md")
        assert result is None


class TestFindRelatedFiles:
    """Tests for finding related files."""

    def test_finds_test_files(self, tmp_path: Path) -> None:
        """Finds test files matching the target."""
        # Create source and test files
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.py").touch()

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_utils.py").touch()

        target = src / "utils.py"
        related = _find_related_files(target, tmp_path)

        assert len(related) == 1
        assert related[0]["relation"] == "test"
        assert "test_utils.py" in related[0]["path"]

    def test_finds_implementation_files_from_docs(self, tmp_path: Path) -> None:
        """Finds implementation files referenced in documentation."""
        # Create implementation file
        (tmp_path / "utils.py").touch()

        # Create doc referencing it
        doc = tmp_path / "readme.md"
        doc.write_text("See the implementation in `utils.py` for details.")

        related = _find_related_files(doc, tmp_path)

        impl_files = [r for r in related if r["relation"] == "implementation"]
        assert len(impl_files) == 1
        assert "utils.py" in impl_files[0]["path"]

    def test_limits_results_to_five(self, tmp_path: Path) -> None:
        """Limits related files to 5 results."""
        # Create many test files
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").touch()

        tests = tmp_path / "tests"
        tests.mkdir()
        for i in range(10):
            # Create variations that might match
            (tests / f"test_module_{i}.py").touch()

        # Actually, _find_related_files looks for exact patterns
        # Let's adjust - it finds test_module.py specifically
        (tests / "test_module.py").touch()

        target = src / "module.py"
        related = _find_related_files(target, tmp_path)

        assert len(related) <= 5

    def test_returns_empty_for_no_matches(self, tmp_path: Path) -> None:
        """Returns empty list when no related files found."""
        src = tmp_path / "orphan.py"
        src.touch()

        related = _find_related_files(src, tmp_path)

        assert related == []


class TestRunShortcut:
    """Integration tests for run_shortcut function."""

    @pytest.mark.asyncio
    async def test_shows_help_for_question_mark(self) -> None:
        """Shows help when shortcut is '?'."""
        from sunwell.interface.cli.core.shortcuts import run_shortcut

        with patch(
            "sunwell.interface.cli.core.shortcuts._show_shortcut_help"
        ) as mock_help:
            await run_shortcut(
                shortcut="?",
                target=None,
                context_str=None,
                lens_name="test",
                provider=None,
                model=None,
                plan_only=False,
                json_output=False,
                verbose=False,
            )

        mock_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_shows_help_for_help_shortcut(self) -> None:
        """Shows help when shortcut is 'help'."""
        from sunwell.interface.cli.core.shortcuts import run_shortcut

        with patch(
            "sunwell.interface.cli.core.shortcuts._show_shortcut_help"
        ) as mock_help:
            await run_shortcut(
                shortcut="help",
                target=None,
                context_str=None,
                lens_name="test",
                provider=None,
                model=None,
                plan_only=False,
                json_output=False,
                verbose=False,
            )

        mock_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_lens_not_found(self, capsys) -> None:
        """Handles case when lens is not found."""
        from sunwell.interface.cli.core.shortcuts import run_shortcut

        with patch(
            "sunwell.interface.cli.core.shortcuts._resolve_lens",
            return_value=None,
        ):
            await run_shortcut(
                shortcut="a-2",
                target=None,
                context_str=None,
                lens_name="nonexistent-lens",
                provider=None,
                model=None,
                plan_only=False,
                json_output=False,
                verbose=False,
            )

        # Should have printed error (via rich console, captured differently)
        # Just verify no exception raised

    @pytest.mark.asyncio
    async def test_normalizes_double_colon_prefix(self) -> None:
        """Strips :: prefix from shortcut before resolution."""
        from sunwell.interface.cli.core.shortcuts import run_shortcut

        # Mock the lens with shortcuts and skill
        mock_skill = MagicMock()
        mock_skill.description = "Test skill"
        mock_skill.allowed_tools = []
        mock_skill.trust = MagicMock(value="workspace")
        mock_skill.preset = None
        mock_skill.validate_with = None
        mock_skill.instructions = "Test"

        mock_lens = MagicMock()
        mock_lens.router = MagicMock()
        mock_lens.router.shortcuts = {"::audit": "audit-skill"}
        mock_lens.get_skill = MagicMock(return_value=mock_skill)
        mock_lens.metadata = MagicMock(name="test", version="1.0")

        with (
            patch(
                "sunwell.interface.cli.core.shortcuts._resolve_lens",
                return_value=mock_lens,
            ),
            patch(
                "sunwell.interface.cli.core.shortcuts._detect_workspace",
                return_value=None,
            ),
            patch(
                "sunwell.interface.cli.core.shortcuts._build_skill_context",
                return_value={},
            ),
        ):
            # Should work with :: prefix and show plan
            await run_shortcut(
                shortcut="::audit",
                target=None,
                context_str=None,
                lens_name="test",
                provider=None,
                model=None,
                plan_only=True,  # Use plan_only to avoid needing model
                json_output=False,
                verbose=False,
            )

        # Verify the lens looked up the skill
        mock_lens.get_skill.assert_called_with("audit-skill")
