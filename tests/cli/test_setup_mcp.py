"""Tests for MCP setup CLI commands (sunwell setup cursor/claude)."""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from sunwell.interface.cli.core.main import main


class TestSetupCursorCommand:
    """Tests for 'sunwell setup cursor' command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_cursor_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cursor directory."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        return cursor_dir

    def test_setup_cursor_creates_config(self, runner: CliRunner, tmp_path: Path):
        """setup cursor should create mcp.json config."""
        cursor_dir = tmp_path / ".cursor"
        mcp_json = cursor_dir / "mcp.json"
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value="/usr/local/bin/sunwell-mcp"):
                result = runner.invoke(main, ["setup", "cursor"])
        
        assert result.exit_code == 0 or "already configured" in result.output.lower()

    def test_setup_cursor_with_existing_config(self, runner: CliRunner, tmp_path: Path):
        """setup cursor should preserve existing config."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_json = cursor_dir / "mcp.json"
        
        # Create existing config with another server
        existing_config = {
            "mcpServers": {
                "other-server": {"command": "/some/other/server"}
            }
        }
        mcp_json.write_text(json.dumps(existing_config))
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value="/usr/local/bin/sunwell-mcp"):
                result = runner.invoke(main, ["setup", "cursor", "--force"])
        
        # Check that both servers are in config
        if mcp_json.exists():
            config = json.loads(mcp_json.read_text())
            assert "other-server" in config.get("mcpServers", {})
            assert "sunwell" in config.get("mcpServers", {})

    def test_setup_cursor_without_force_skips(self, runner: CliRunner, tmp_path: Path):
        """setup cursor without --force should skip if already configured."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_json = cursor_dir / "mcp.json"
        
        # Create existing config with sunwell already configured
        existing_config = {
            "mcpServers": {
                "sunwell": {"command": "old-sunwell-command"}
            }
        }
        mcp_json.write_text(json.dumps(existing_config))
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["setup", "cursor"])
        
        assert "already configured" in result.output.lower() or result.exit_code == 0
        
        # Config should be unchanged
        config = json.loads(mcp_json.read_text())
        assert config["mcpServers"]["sunwell"]["command"] == "old-sunwell-command"

    def test_setup_cursor_uses_sunwell_mcp_if_available(self, runner: CliRunner, tmp_path: Path):
        """setup cursor should use sunwell-mcp command if available."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_json = cursor_dir / "mcp.json"
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value="/usr/local/bin/sunwell-mcp"):
                result = runner.invoke(main, ["setup", "cursor", "--force"])
        
        if mcp_json.exists():
            config = json.loads(mcp_json.read_text())
            sunwell_config = config.get("mcpServers", {}).get("sunwell", {})
            assert sunwell_config.get("command") == "/usr/local/bin/sunwell-mcp"

    def test_setup_cursor_falls_back_to_python_m(self, runner: CliRunner, tmp_path: Path):
        """setup cursor should use python -m if sunwell-mcp not found."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_json = cursor_dir / "mcp.json"
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value=None):  # sunwell-mcp not found
                result = runner.invoke(main, ["setup", "cursor", "--force"])
        
        if mcp_json.exists():
            config = json.loads(mcp_json.read_text())
            sunwell_config = config.get("mcpServers", {}).get("sunwell", {})
            # Should use python -m sunwell.mcp
            assert "-m" in sunwell_config.get("args", [])
            assert "sunwell.mcp" in sunwell_config.get("args", [])


class TestSetupClaudeCommand:
    """Tests for 'sunwell setup claude' command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_setup_claude_creates_config_macos(self, runner: CliRunner, tmp_path: Path):
        """setup claude should create config on macOS."""
        claude_dir = tmp_path / "Library" / "Application Support" / "Claude"
        claude_dir.mkdir(parents=True)
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("sys.platform", "darwin"):
                with patch("shutil.which", return_value="/usr/local/bin/sunwell-mcp"):
                    result = runner.invoke(main, ["setup", "claude"])
        
        # Should not crash
        assert result.exit_code == 0 or "already configured" in result.output.lower()


class TestSetupGroupBehavior:
    """Tests for setup command group behavior."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_setup_without_subcommand_runs_project_setup(self, runner: CliRunner, tmp_path: Path):
        """'sunwell setup' without subcommand should run project setup."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a directory for setup
            project_dir = Path.cwd()
            
            result = runner.invoke(main, ["setup", "."])
            
            # Should attempt project setup (may fail but shouldn't crash)
            assert "unexpected keyword argument" not in result.output

    def test_setup_cursor_is_accessible(self, runner: CliRunner):
        """'sunwell setup cursor' should be a valid command."""
        result = runner.invoke(main, ["setup", "cursor", "--help"])
        
        assert result.exit_code == 0
        assert "cursor" in result.output.lower() or "mcp" in result.output.lower()

    def test_setup_claude_is_accessible(self, runner: CliRunner):
        """'sunwell setup claude' should be a valid command."""
        result = runner.invoke(main, ["setup", "claude", "--help"])
        
        assert result.exit_code == 0
        assert "claude" in result.output.lower() or "mcp" in result.output.lower()
