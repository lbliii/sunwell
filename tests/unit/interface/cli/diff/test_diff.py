"""Tests for inline diff visualization."""

import pytest

from sunwell.interface.cli.diff.renderer import (
    DiffRenderer,
    DiffStats,
    generate_unified_diff,
)
from sunwell.interface.cli.diff.preview import (
    ChangeType,
    FileChange,
)


class TestDiffStats:
    """Test DiffStats dataclass."""
    
    def test_total_changes(self) -> None:
        """Total changes is additions + deletions."""
        stats = DiffStats(additions=5, deletions=3, hunks=2)
        assert stats.total_changes == 8
    
    def test_format_both(self) -> None:
        """Format with additions and deletions."""
        stats = DiffStats(additions=10, deletions=5, hunks=3)
        assert stats.format() == "+10, -5"
    
    def test_format_additions_only(self) -> None:
        """Format with only additions."""
        stats = DiffStats(additions=10, deletions=0, hunks=1)
        assert stats.format() == "+10"
    
    def test_format_deletions_only(self) -> None:
        """Format with only deletions."""
        stats = DiffStats(additions=0, deletions=5, hunks=1)
        assert stats.format() == "-5"
    
    def test_format_no_changes(self) -> None:
        """Format with no changes."""
        stats = DiffStats(additions=0, deletions=0, hunks=0)
        assert stats.format() == "no changes"


class TestGenerateUnifiedDiff:
    """Test unified diff generation."""
    
    def test_simple_modification(self) -> None:
        """Generate diff for simple change."""
        old = "line 1\nline 2\nline 3\n"
        new = "line 1\nmodified line 2\nline 3\n"
        
        diff = generate_unified_diff("test.txt", old, new)
        
        assert "--- a/test.txt" in diff
        assert "+++ b/test.txt" in diff
        assert "-line 2" in diff
        assert "+modified line 2" in diff
    
    def test_new_file(self) -> None:
        """Generate diff for new file."""
        old = ""
        new = "new content\n"
        
        diff = generate_unified_diff("new.txt", old, new)
        
        assert "+new content" in diff
    
    def test_deleted_file(self) -> None:
        """Generate diff for deleted file."""
        old = "old content\n"
        new = ""
        
        diff = generate_unified_diff("deleted.txt", old, new)
        
        assert "-old content" in diff
    
    def test_no_changes(self) -> None:
        """No diff for identical content."""
        content = "same\n"
        
        diff = generate_unified_diff("same.txt", content, content)
        
        assert diff == ""


class TestDiffRenderer:
    """Test DiffRenderer class."""
    
    def test_count_stats(self) -> None:
        """Count additions, deletions, hunks."""
        renderer = DiffRenderer()
        
        lines = [
            "--- a/file.txt",
            "+++ b/file.txt",
            "@@ -1,3 +1,3 @@",
            " line 1",
            "-old line",
            "+new line",
            " line 3",
            "@@ -10,2 +10,3 @@",
            " context",
            "+added",
        ]
        
        stats = renderer._count_stats(lines)
        
        assert stats.additions == 2
        assert stats.deletions == 1
        assert stats.hunks == 2
    
    def test_style_line_addition(self) -> None:
        """Style addition lines green."""
        renderer = DiffRenderer()
        styled = renderer._style_line("+added line")
        assert styled.plain == "+added line"
    
    def test_style_line_deletion(self) -> None:
        """Style deletion lines red."""
        renderer = DiffRenderer()
        styled = renderer._style_line("-removed line")
        assert styled.plain == "-removed line"
    
    def test_style_line_hunk_header(self) -> None:
        """Style hunk headers."""
        renderer = DiffRenderer()
        styled = renderer._style_line("@@ -1,3 +1,3 @@")
        assert styled.plain == "@@ -1,3 +1,3 @@"
    
    def test_style_line_context(self) -> None:
        """Style context lines."""
        renderer = DiffRenderer()
        styled = renderer._style_line(" context line")
        assert styled.plain == " context line"


class TestFileChange:
    """Test FileChange dataclass."""
    
    def test_create_change(self) -> None:
        """Create a file change."""
        from pathlib import Path
        
        change = FileChange(
            path=Path("test.py"),
            change_type=ChangeType.CREATE,
            new_content="print('hello')\n",
        )
        
        assert change.path == Path("test.py")
        assert change.change_type == ChangeType.CREATE
        assert change.old_content == ""
        assert change.new_content == "print('hello')\n"
    
    def test_diff_property(self) -> None:
        """FileChange.diff generates unified diff."""
        from pathlib import Path
        
        change = FileChange(
            path=Path("test.py"),
            change_type=ChangeType.MODIFY,
            old_content="old\n",
            new_content="new\n",
        )
        
        diff = change.diff
        
        assert "-old" in diff
        assert "+new" in diff
    
    def test_stats_property(self) -> None:
        """FileChange.stats returns DiffStats."""
        from pathlib import Path
        
        change = FileChange(
            path=Path("test.py"),
            change_type=ChangeType.MODIFY,
            old_content="a\nb\n",
            new_content="a\nc\n",
        )
        
        stats = change.stats
        
        assert stats.additions == 1
        assert stats.deletions == 1


class TestChangeType:
    """Test ChangeType enum."""
    
    def test_values(self) -> None:
        """All expected values exist."""
        assert ChangeType.CREATE.value == "create"
        assert ChangeType.MODIFY.value == "modify"
        assert ChangeType.DELETE.value == "delete"
