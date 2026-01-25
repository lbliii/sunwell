"""Tests for tool description engineering."""

import pytest

from sunwell.models.capability.tool_engineering import (
    ToolQuality,
    audit_tool,
    audit_tool_set,
    enhance_tool_description,
    get_quality_summary,
)
from sunwell.models.core.protocol import Tool


class TestAuditTool:
    """Test individual tool auditing."""

    def test_good_tool_high_score(self):
        """Well-documented tool should score high."""
        tool = Tool(
            name="read_file",
            description="Read the contents of a file at the specified path and return the text content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file to read",
                    }
                },
                "required": ["path"],
            },
        )
        quality = audit_tool(tool)

        assert quality.score >= 0.8
        assert len(quality.issues) == 0

    def test_short_description_penalized(self):
        """Short descriptions should be penalized."""
        tool = Tool(
            name="test",
            description="Does stuff",
            parameters={},
        )
        quality = audit_tool(tool)

        assert quality.score < 0.8
        assert any("too short" in issue.lower() for issue in quality.issues)

    def test_vague_language_penalized(self):
        """Vague language should be detected."""
        tool = Tool(
            name="process",
            description="Processes various data from different sources to produce some output.",
            parameters={},
        )
        quality = audit_tool(tool)

        assert quality.score < 1.0
        assert any("vague" in issue.lower() for issue in quality.issues)

    def test_marketing_language_penalized(self):
        """Marketing language should be detected."""
        tool = Tool(
            name="amazing_tool",
            description="A powerful and flexible tool that makes everything easy and awesome.",
            parameters={},
        )
        quality = audit_tool(tool)

        assert quality.score < 1.0
        assert any("marketing" in issue.lower() for issue in quality.issues)

    def test_undocumented_params_penalized(self):
        """Undocumented parameters should be detected."""
        tool = Tool(
            name="process",
            description="Process data with various options and configurations for best results.",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string"},  # No description
                    "output": {"type": "string"},  # No description
                },
                "required": ["input"],
            },
        )
        quality = audit_tool(tool)

        assert quality.score < 1.0
        assert any("undocumented" in issue.lower() for issue in quality.issues)


class TestAuditToolSet:
    """Test batch tool auditing."""

    def test_audit_multiple_tools(self):
        """Should audit all tools in set."""
        tools = (
            Tool(
                name="good_tool",
                description="A well-documented tool that performs a specific action.",
                parameters={},
            ),
            Tool(
                name="bad_tool",
                description="Stuff",
                parameters={},
            ),
        )
        audits = audit_tool_set(tools)

        assert len(audits) == 2
        assert "good_tool" in audits
        assert "bad_tool" in audits
        assert audits["good_tool"].score > audits["bad_tool"].score


class TestEnhanceToolDescription:
    """Test tool description enhancement."""

    def test_removes_marketing_language(self):
        """Should remove marketing words."""
        tool = Tool(
            name="test",
            description="A powerful and flexible tool.",
            parameters={},
        )
        enhanced = enhance_tool_description(tool)

        assert "powerful" not in enhanced.description.lower()
        assert "flexible" not in enhanced.description.lower()

    def test_preserves_good_description(self):
        """Should not change good descriptions."""
        original_desc = "Read file contents from the specified path."
        tool = Tool(
            name="read_file",
            description=original_desc,
            parameters={},
        )
        enhanced = enhance_tool_description(tool)

        assert enhanced.description == original_desc


class TestGetQualitySummary:
    """Test quality summary statistics."""

    def test_summary_statistics(self):
        """Should calculate correct statistics."""
        audits = {
            "tool1": ToolQuality(score=0.9, issues=(), suggestions=()),
            "tool2": ToolQuality(score=0.7, issues=("issue1",), suggestions=()),
            "tool3": ToolQuality(score=0.5, issues=("issue1", "issue2"), suggestions=()),
        }
        summary = get_quality_summary(audits)

        assert summary["count"] == 3
        assert 0.69 < summary["average_score"] < 0.71
        assert summary["min_score"] == 0.5
        assert summary["max_score"] == 0.9
        assert summary["issues_count"] == 3
        assert summary["tools_below_threshold"] == 1

    def test_empty_audits(self):
        """Should handle empty audit set."""
        summary = get_quality_summary({})

        assert summary["count"] == 0
        assert summary["average_score"] == 0.0


class TestToolQuality:
    """Test ToolQuality dataclass."""

    def test_immutable(self):
        """ToolQuality should be immutable."""
        quality = ToolQuality(score=0.8, issues=(), suggestions=())
        with pytest.raises(AttributeError):
            quality.score = 0.5  # type: ignore
