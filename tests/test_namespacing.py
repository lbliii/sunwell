"""Tests for tool namespacing."""

import pytest

from sunwell.models.capability.namespacing import (
    denamespacify_tool_call,
    merge_registries,
    namespace_tools,
    parse_namespaced_name,
    resolve_tool,
)
from sunwell.models.protocol import Tool, ToolCall


class TestNamespaceTools:
    """Test tool namespacing."""

    def test_adds_namespace_prefix(self):
        """Should add namespace to tool names."""
        tools = (Tool(name="read_file", description="Read a file", parameters={}),)

        namespaced = namespace_tools(tools, "files")

        assert namespaced[0].name == "files.read_file"
        assert "[files]" in namespaced[0].description

    def test_custom_separator(self):
        """Should support custom separator."""
        tools = (Tool(name="test", description="Test", parameters={}),)

        namespaced = namespace_tools(tools, "ns", separator="/")

        assert namespaced[0].name == "ns/test"


class TestParseNamespacedName:
    """Test namespaced name parsing."""

    def test_with_namespace(self):
        """Should parse namespace and name."""
        namespace, name = parse_namespaced_name("files.read_file")

        assert namespace == "files"
        assert name == "read_file"

    def test_without_namespace(self):
        """Should handle non-namespaced names."""
        namespace, name = parse_namespaced_name("read_file")

        assert namespace is None
        assert name == "read_file"

    def test_custom_separator(self):
        """Should support custom separator."""
        namespace, name = parse_namespaced_name("files/read_file", separator="/")

        assert namespace == "files"
        assert name == "read_file"


class TestResolveTool:
    """Test tool resolution."""

    def test_resolve_namespaced(self):
        """Should resolve namespaced tool."""
        registries = {
            "files": {"read_file": Tool(name="read_file", description="Read", parameters={})}
        }

        tool = resolve_tool("files.read_file", registries)

        assert tool is not None
        assert tool.name == "read_file"

    def test_resolve_non_namespaced(self):
        """Should search all registries for non-namespaced names."""
        registries = {
            "files": {"read_file": Tool(name="read_file", description="Read", parameters={})}
        }

        tool = resolve_tool("read_file", registries)

        assert tool is not None

    def test_not_found(self):
        """Should return None for unknown tools."""
        registries = {"files": {}}

        tool = resolve_tool("unknown", registries)

        assert tool is None


class TestDenamespacifyToolCall:
    """Test tool call de-namespacing."""

    def test_with_namespace(self):
        """Should extract namespace from tool call."""
        call = ToolCall(id="1", name="files.read_file", arguments={})

        namespace, new_call = denamespacify_tool_call(call)

        assert namespace == "files"
        assert new_call.name == "read_file"
        assert new_call.id == "1"

    def test_without_namespace(self):
        """Should handle non-namespaced calls."""
        call = ToolCall(id="1", name="read_file", arguments={})

        namespace, new_call = denamespacify_tool_call(call)

        assert namespace is None
        assert new_call.name == "read_file"


class TestMergeRegistries:
    """Test registry merging."""

    def test_merge_multiple(self):
        """Should merge registries with namespacing."""
        registries = {
            "files": {"read": Tool(name="read", description="Read", parameters={})},
            "web": {"fetch": Tool(name="fetch", description="Fetch", parameters={})},
        }

        merged = merge_registries(registries)

        assert "files.read" in merged
        assert "web.fetch" in merged
        assert len(merged) == 2
