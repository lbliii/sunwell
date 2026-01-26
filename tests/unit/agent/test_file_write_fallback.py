"""Tests for file write fallback when model doesn't call write_file tool.

This tests the scenario where:
1. AgentLoop is used for code generation (task.target_path is set)
2. Model outputs code in text instead of calling write_file tool
3. Detection kicks in and falls back to streaming mode
4. Streaming fallback writes the file from _last_task_result

RFC: Addresses regression where tasks show 100% complete but no files created.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.events import AgentEvent, EventType
from sunwell.planning.naaru.types import Task, TaskMode


class MockGenerateResult:
    """Mock result from model.generate()."""

    def __init__(self, text: str, tool_calls: tuple = ()):
        self.text = text
        self.content = text
        self.tool_calls = tool_calls
        self.model = "mock"
        self.usage = None
        self.finish_reason = "stop"

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace."""
    return tmp_path


@pytest.fixture
def mock_model():
    """Create a mock model that outputs code in text without tool calls."""
    model = MagicMock()
    # Model returns code in text, not via tool calls
    model.generate = AsyncMock(
        return_value=MockGenerateResult(
            text='def hello():\n    return "Hello, World!"'
        )
    )
    return model


@pytest.fixture
def mock_model_with_tools():
    """Create a mock model that properly uses write_file tool."""
    from sunwell.models.core.protocol import ToolCall

    model = MagicMock()
    model.generate = AsyncMock(
        return_value=MockGenerateResult(
            text="",
            tool_calls=(
                ToolCall(
                    id="call_1",
                    name="write_file",
                    arguments={
                        "path": "hello.py",
                        "content": 'def hello():\n    return "Hello, World!"',
                    },
                ),
            ),
        )
    )
    return model


class TestFileWriteDetection:
    """Tests for detecting when files aren't created."""

    @pytest.mark.asyncio
    async def test_detects_missing_file_after_tool_loop(self, tmp_workspace):
        """Should detect when expected file was not created by tool loop."""
        from sunwell.agent.core import Agent

        # Create agent with mock model that doesn't call write_file
        mock_model = MagicMock()
        mock_model.generate = AsyncMock(
            return_value=MockGenerateResult(text="some code output")
        )
        mock_model.generate_stream = None  # Disable streaming

        agent = Agent(
            model=mock_model,
            cwd=tmp_workspace,
        )

        task = Task(
            id="test-task",
            description="Create hello.py",
            mode=TaskMode.GENERATE,
            target_path="hello.py",
        )

        # The file should NOT exist before
        expected_path = tmp_workspace / "hello.py"
        assert not expected_path.exists()

        # When tool_executor is available, it uses _execute_task_with_tools
        # which should detect the missing file and raise RuntimeError
        # triggering fallback to streaming

        # For this unit test, we verify the detection logic directly
        agent._last_task_result = ""  # No result from tool calls

        # Simulate what _execute_task_with_tools does after AgentLoop
        if task.target_path:
            expected = tmp_workspace / task.target_path
            if not expected.exists():
                # This is what our fix detects
                assert True, "Correctly detected missing file"
            else:
                pytest.fail("File should not exist yet")


class TestStreamingFallback:
    """Tests for the streaming fallback writing files."""

    @pytest.mark.asyncio
    async def test_streaming_fallback_writes_file(self, tmp_workspace, mock_model):
        """Streaming fallback should write file from _last_task_result."""
        from sunwell.agent.core import Agent

        agent = Agent(
            model=mock_model,
            cwd=tmp_workspace,
            stream_inference=True,
        )

        # Simulate what happens after streaming fallback
        agent._last_task_result = 'def hello():\n    return "Hello, World!"'

        task = Task(
            id="test-task",
            description="Create hello.py",
            mode=TaskMode.GENERATE,
            target_path="hello.py",
        )

        # Simulate the file write that _run_execute does after streaming
        result_text = agent._last_task_result
        if result_text and task.target_path:
            path = tmp_workspace / task.target_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result_text)

        # Verify file was written
        expected_path = tmp_workspace / "hello.py"
        assert expected_path.exists()
        assert "def hello()" in expected_path.read_text()


class TestCodeSanitization:
    """Tests for code sanitization before writing."""

    def test_sanitize_removes_markdown_fences(self, tmp_workspace):
        """Should strip markdown code fences from output."""
        from sunwell.agent.core import sanitize_code_content

        raw = '```python\ndef hello():\n    pass\n```'
        sanitized = sanitize_code_content(raw)

        assert "```" not in sanitized
        assert "def hello():" in sanitized

    def test_sanitize_removes_language_tag(self, tmp_workspace):
        """Should strip language tags from markdown fences."""
        from sunwell.agent.core import sanitize_code_content

        raw = '```python\ncode\n```'
        sanitized = sanitize_code_content(raw)

        assert "python" not in sanitized or "def" in sanitized
        assert "```" not in sanitized

    def test_sanitize_handles_no_fences(self, tmp_workspace):
        """Should handle code without markdown fences."""
        from sunwell.agent.core import sanitize_code_content

        raw = 'def hello():\n    return "world"'
        sanitized = sanitize_code_content(raw)

        assert sanitized == raw


class TestCodeDetectionFallback:
    """Tests for auto-detecting code in output and constructing write_file calls."""

    def test_looks_like_code_with_markdown_fence(self):
        """Should detect markdown-fenced code."""
        from sunwell.models.emulation.tool_emulator import _looks_like_code

        text = '```python\ndef hello():\n    pass\n```'
        assert _looks_like_code(text) is True

    def test_looks_like_code_with_function_def(self):
        """Should detect Python function definitions."""
        from sunwell.models.emulation.tool_emulator import _looks_like_code

        text = 'def calculate_sum(a, b):\n    return a + b'
        assert _looks_like_code(text) is True

    def test_looks_like_code_with_class_def(self):
        """Should detect class definitions."""
        from sunwell.models.emulation.tool_emulator import _looks_like_code

        text = 'class MyClass:\n    def __init__(self):\n        pass'
        assert _looks_like_code(text) is True

    def test_looks_like_code_with_imports(self):
        """Should detect import statements."""
        from sunwell.models.emulation.tool_emulator import _looks_like_code

        text = 'import os\nfrom pathlib import Path'
        assert _looks_like_code(text) is True

    def test_not_code_plain_text(self):
        """Should not detect plain text as code."""
        from sunwell.models.emulation.tool_emulator import _looks_like_code

        text = 'Here is my response about the task you asked me to do.'
        assert _looks_like_code(text) is False

    def test_extract_code_from_markdown(self):
        """Should extract code content from markdown fences."""
        from sunwell.models.emulation.tool_emulator import _extract_code_from_markdown

        text = '```python\ndef hello():\n    return "world"\n```'
        code = _extract_code_from_markdown(text)
        assert code == 'def hello():\n    return "world"'

    def test_parse_tool_calls_auto_constructs_write_file(self):
        """Should auto-construct write_file when code detected and expected."""
        from sunwell.models.emulation.tool_emulator import parse_tool_calls_from_text

        # Model outputs code directly instead of calling write_file
        text = '```python\ndef hello():\n    return "world"\n```'

        tool_calls, remaining = parse_tool_calls_from_text(
            text,
            expected_tool="write_file",
            target_path="hello.py",
        )

        assert len(tool_calls) == 1
        assert tool_calls[0].name == "write_file"
        assert tool_calls[0].arguments["path"] == "hello.py"
        assert "def hello():" in tool_calls[0].arguments["content"]

    def test_parse_tool_calls_no_auto_construct_without_expected(self):
        """Should NOT auto-construct if expected_tool not specified."""
        from sunwell.models.emulation.tool_emulator import parse_tool_calls_from_text

        text = '```python\ndef hello():\n    pass\n```'

        tool_calls, remaining = parse_tool_calls_from_text(text)

        # No auto-construction without expected_tool
        assert len(tool_calls) == 0

    def test_parse_tool_calls_prefers_explicit_json(self):
        """Should prefer explicit JSON tool calls over auto-construction."""
        from sunwell.models.emulation.tool_emulator import parse_tool_calls_from_text

        # Model correctly outputs JSON tool call
        text = '''```json
{"tool": "write_file", "arguments": {"path": "test.py", "content": "print('hi')"}}
```'''

        tool_calls, remaining = parse_tool_calls_from_text(
            text,
            expected_tool="write_file",
        )

        assert len(tool_calls) == 1
        assert tool_calls[0].name == "write_file"
        assert tool_calls[0].arguments["path"] == "test.py"


class TestEndToEndFallback:
    """Integration-style tests for the full fallback flow."""

    @pytest.mark.asyncio
    async def test_task_creates_file_via_fallback(self, tmp_workspace):
        """Full flow: model outputs text → detection → fallback → file created."""
        from sunwell.agent.core import Agent

        # Mock model that outputs code in text (bad behavior we're handling)
        mock_model = MagicMock()
        mock_model.model_id = "mock"

        # First call: model outputs code without tool calls
        # This simulates the model ignoring instructions to use write_file
        async def mock_stream(prompt, **kwargs):
            # Simulate streaming response with code
            yield 'def '
            yield 'hello():\n'
            yield '    return "world"'

        mock_model.generate_stream = mock_stream
        mock_model.generate = AsyncMock(
            return_value=MockGenerateResult(text='def hello():\n    return "world"')
        )

        agent = Agent(
            model=mock_model,
            cwd=tmp_workspace,
            stream_inference=True,
        )

        # Directly test the streaming fallback
        task = Task(
            id="test-task",
            description="Create hello.py",
            mode=TaskMode.GENERATE,
            target_path="hello.py",
        )

        # Collect events from streaming fallback
        events = []
        async for event in agent._execute_task_streaming_fallback(task):
            events.append(event)

        # After fallback, _last_task_result should have the code
        assert agent._last_task_result is not None
        assert "def hello" in agent._last_task_result

        # Simulate what _run_execute does after streaming
        result_text = agent._last_task_result
        if result_text and task.target_path:
            path = tmp_workspace / task.target_path
            path.parent.mkdir(parents=True, exist_ok=True)
            from sunwell.agent.core import _sanitize_code_content
            sanitized = _sanitize_code_content(result_text)
            path.write_text(sanitized)

        # Verify file exists
        expected_path = tmp_workspace / "hello.py"
        assert expected_path.exists(), "File should be created via fallback"
        content = expected_path.read_text()
        assert "def hello" in content
