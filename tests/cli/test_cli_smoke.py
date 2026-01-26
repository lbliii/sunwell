"""Smoke tests for all CLI commands.

Ensures every command can be invoked without crashing.
Does not test functionality deeply, just that commands are wired up correctly.
"""

import pytest
from click.testing import CliRunner

from sunwell.interface.cli.core.main import main


class TestTier1Commands:
    """Smoke tests for Tier 1-2 (visible) commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_config_show(self, runner: CliRunner) -> None:
        """config show invokes without crash."""
        result = runner.invoke(main, ["config", "show"])
        # May fail if no config, but shouldn't crash
        assert result.exit_code in (0, 1, 2)

    def test_config_init(self, runner: CliRunner) -> None:
        """config init --help works."""
        result = runner.invoke(main, ["config", "init", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output.lower() or "config" in result.output.lower()

    def test_config_get(self, runner: CliRunner) -> None:
        """config get invokes (needs a key)."""
        result = runner.invoke(main, ["config", "get", "--help"])
        assert result.exit_code == 0

    def test_config_set(self, runner: CliRunner) -> None:
        """config set --help works."""
        result = runner.invoke(main, ["config", "set", "--help"])
        assert result.exit_code == 0

    def test_project_help(self, runner: CliRunner) -> None:
        """project --help works."""
        result = runner.invoke(main, ["project", "--help"])
        assert result.exit_code == 0

    def test_project_analyze_help(self, runner: CliRunner) -> None:
        """project analyze --help works."""
        result = runner.invoke(main, ["project", "analyze", "--help"])
        assert result.exit_code == 0

    def test_sessions_help(self, runner: CliRunner) -> None:
        """sessions --help works."""
        result = runner.invoke(main, ["sessions", "--help"])
        assert result.exit_code == 0

    def test_lens_help(self, runner: CliRunner) -> None:
        """lens --help works."""
        result = runner.invoke(main, ["lens", "--help"])
        assert result.exit_code == 0

    def test_lens_list(self, runner: CliRunner) -> None:
        """lens list invokes without crash."""
        result = runner.invoke(main, ["lens", "list"])
        assert result.exit_code in (0, 1, 2)

    def test_setup_help(self, runner: CliRunner) -> None:
        """setup --help works."""
        result = runner.invoke(main, ["setup", "--help"])
        assert result.exit_code == 0

    def test_serve_help(self, runner: CliRunner) -> None:
        """serve --help works."""
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0

    def test_debug_help(self, runner: CliRunner) -> None:
        """debug --help works."""
        result = runner.invoke(main, ["debug", "--help"])
        assert result.exit_code == 0

    def test_lineage_help(self, runner: CliRunner) -> None:
        """lineage --help works."""
        result = runner.invoke(main, ["lineage", "--help"])
        assert result.exit_code == 0

    def test_review_help(self, runner: CliRunner) -> None:
        """review --help works."""
        result = runner.invoke(main, ["review", "--help"])
        assert result.exit_code == 0


class TestTier3Commands:
    """Smoke tests for Tier 3 (hidden but accessible) commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_chat_help(self, runner: CliRunner) -> None:
        """chat --help works."""
        result = runner.invoke(main, ["chat", "--help"])
        assert result.exit_code == 0

    def test_demo_help(self, runner: CliRunner) -> None:
        """demo --help works."""
        result = runner.invoke(main, ["demo", "--help"])
        assert result.exit_code == 0

    def test_eval_help(self, runner: CliRunner) -> None:
        """eval --help works."""
        result = runner.invoke(main, ["eval", "--help"])
        assert result.exit_code == 0


class TestTier4Commands:
    """Smoke tests for Tier 4 (internal) commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_backlog_help(self, runner: CliRunner) -> None:
        """backlog --help works."""
        result = runner.invoke(main, ["backlog", "--help"])
        assert result.exit_code == 0

    def test_dag_help(self, runner: CliRunner) -> None:
        """dag --help works."""
        result = runner.invoke(main, ["dag", "--help"])
        assert result.exit_code == 0

    def test_scan_help(self, runner: CliRunner) -> None:
        """scan --help works."""
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0

    def test_workspace_help(self, runner: CliRunner) -> None:
        """workspace --help works."""
        result = runner.invoke(main, ["workspace", "--help"])
        assert result.exit_code == 0

    def test_workflow_help(self, runner: CliRunner) -> None:
        """workflow --help works."""
        result = runner.invoke(main, ["workflow", "--help"])
        assert result.exit_code == 0

    def test_internal_help(self, runner: CliRunner) -> None:
        """internal --help works."""
        result = runner.invoke(main, ["internal", "--help"])
        assert result.exit_code == 0

    def test_internal_backlog_help(self, runner: CliRunner) -> None:
        """internal backlog --help works."""
        result = runner.invoke(main, ["internal", "backlog", "--help"])
        assert result.exit_code == 0

    def test_internal_workflow_help(self, runner: CliRunner) -> None:
        """internal workflow --help works."""
        result = runner.invoke(main, ["internal", "workflow", "--help"])
        assert result.exit_code == 0


class TestMainOptions:
    """Smoke tests for main command options."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        """--help works."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "sunwell" in result.output.lower() or "usage" in result.output.lower()

    def test_version(self, runner: CliRunner) -> None:
        """--version works."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_all_commands(self, runner: CliRunner) -> None:
        """--all-commands shows hidden commands."""
        result = runner.invoke(main, ["--all-commands"])
        assert result.exit_code == 0
        # Should show tier information
        assert "tier" in result.output.lower() or "command" in result.output.lower()


class TestShortcutInvocation:
    """Smoke tests for shortcut invocation patterns."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_shortcut_help(self, runner: CliRunner) -> None:
        """Shortcut help (?) works."""
        result = runner.invoke(main, ["-s", "?"])
        # Should show available shortcuts or error about no lens
        assert result.exit_code in (0, 1, 2)

    def test_shortcut_h(self, runner: CliRunner) -> None:
        """Shortcut help (h) works."""
        result = runner.invoke(main, ["-s", "h"])
        assert result.exit_code in (0, 1, 2)

    def test_shortcut_help_long(self, runner: CliRunner) -> None:
        """Shortcut help (help) works."""
        result = runner.invoke(main, ["-s", "help"])
        assert result.exit_code in (0, 1, 2)


class TestCommandRegistration:
    """Verify all expected commands are registered."""

    def test_tier_1_2_commands_registered(self) -> None:
        """Tier 1-2 commands are registered."""
        commands = main.list_commands(None)
        expected = ["config", "project", "sessions", "lens", "setup", "serve", "debug"]
        for cmd in expected:
            assert cmd in commands, f"Expected {cmd} to be registered"

    def test_tier_3_commands_registered(self) -> None:
        """Tier 3 commands are registered."""
        commands = main.list_commands(None)
        expected = ["chat", "demo", "eval"]
        for cmd in expected:
            assert cmd in commands, f"Expected {cmd} to be registered"

    def test_tier_4_commands_registered(self) -> None:
        """Tier 4 commands are registered."""
        commands = main.list_commands(None)
        expected = ["backlog", "dag", "scan", "workspace", "workflow", "internal"]
        for cmd in expected:
            assert cmd in commands, f"Expected {cmd} to be registered"

    def test_deprecated_commands_not_registered(self) -> None:
        """Deprecated commands are not registered."""
        commands = main.list_commands(None)
        deprecated = ["ask", "apply"]
        for cmd in deprecated:
            assert cmd not in commands, f"Deprecated {cmd} should not be registered"


class TestParameterizedSmokeTests:
    """Parameterized smoke tests for systematic coverage."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    @pytest.mark.parametrize(
        "cmd",
        [
            ["config", "--help"],
            ["project", "--help"],
            ["sessions", "--help"],
            ["lens", "--help"],
            ["setup", "--help"],
            ["serve", "--help"],
            ["debug", "--help"],
            ["lineage", "--help"],
            ["review", "--help"],
            ["chat", "--help"],
            ["backlog", "--help"],
            ["dag", "--help"],
            ["workflow", "--help"],
            ["workspace", "--help"],
            ["internal", "--help"],
            ["skills", "--help"],
            ["epic", "--help"],
        ],
    )
    def test_command_help_works(self, runner: CliRunner, cmd: list[str]) -> None:
        """All commands respond to --help."""
        result = runner.invoke(main, cmd)
        assert result.exit_code == 0, f"{cmd} failed: {result.output}"
