"""Tests for main.py GoalFirstGroup parsing patterns.

Tests the custom Click group that handles:
- Goal-first pattern: `sunwell "Build API"`
- Shortcut pattern: `sunwell -s a-2 file.md`
- Path pattern: `sunwell .` and `sunwell ~/path`
"""

from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from sunwell.interface.cli.core.main import GoalFirstGroup, main


class TestGoalFirstGroupParsing:
    """Tests for GoalFirstGroup.parse_args behavior."""

    def test_empty_args_proceeds_normally(self) -> None:
        """Empty args list returns without modifying context."""
        group = GoalFirstGroup("test")

        # Create a minimal context
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        # Call parse_args with empty list
        with patch.object(click.Group, "parse_args", return_value=[]):
            result = group.parse_args(ctx, [])

        # No special keys should be set
        assert "_goal" not in ctx.obj
        assert "_open_path" not in ctx.obj
        assert "_positional_target" not in ctx.obj

    def test_goal_first_captures_goal(self) -> None:
        """First arg that's not a command is captured as goal."""
        group = GoalFirstGroup("test")

        # Add a command so we can test non-command detection
        @group.command()
        def config() -> None:
            pass

        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["Build a REST API with auth"])

        assert ctx.obj.get("_goal") == "Build a REST API with auth"

    def test_goal_first_removes_goal_from_args(self) -> None:
        """Goal is removed from args passed to parent."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        captured_args = []

        def mock_parse(ctx, args):
            captured_args.extend(args)
            return []

        with patch.object(click.Group, "parse_args", side_effect=mock_parse):
            group.parse_args(ctx, ["Build API", "--verbose"])

        # Goal should not be in args passed to parent
        assert "Build API" not in captured_args
        assert "--verbose" in captured_args

    def test_command_name_not_treated_as_goal(self) -> None:
        """Known command names are not treated as goals."""
        group = GoalFirstGroup("test")

        @group.command()
        def config() -> None:
            pass

        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["config", "show"])

        # config is a command, not a goal
        assert "_goal" not in ctx.obj

    def test_path_dot_captured_as_open_path(self) -> None:
        """'.' is captured as _open_path for project opening."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["."])

        assert ctx.obj.get("_open_path") == "."
        assert "_goal" not in ctx.obj

    def test_path_dotdot_captured_as_open_path(self) -> None:
        """'..' is captured as _open_path."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, [".."])

        assert ctx.obj.get("_open_path") == ".."

    def test_path_absolute_captured_as_open_path(self) -> None:
        """Absolute path is captured as _open_path."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["/home/user/project"])

        assert ctx.obj.get("_open_path") == "/home/user/project"

    def test_path_tilde_captured_as_open_path(self) -> None:
        """Tilde path is captured as _open_path."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["~/projects/my-app"])

        assert ctx.obj.get("_open_path") == "~/projects/my-app"

    def test_path_relative_captured_as_open_path(self) -> None:
        """Relative path starting with ./ is captured as _open_path."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["./subdir"])

        assert ctx.obj.get("_open_path") == "./subdir"

    def test_shortcut_captures_target(self) -> None:
        """Shortcut with target captures _positional_target."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["-s", "a-2", "docs/api.md"])

        assert ctx.obj.get("_positional_target") == "docs/api.md"

    def test_shortcut_captures_context_string(self) -> None:
        """Shortcut with multiple args after target captures context."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["-s", "a-2", "docs/api.md", "focus", "on", "API"])

        assert ctx.obj.get("_positional_target") == "docs/api.md"
        assert ctx.obj.get("_context_str") == "focus on API"

    def test_shortcut_long_form(self) -> None:
        """--skill long form works same as -s."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["--skill", "health", "src/"])

        assert ctx.obj.get("_positional_target") == "src/"

    def test_shortcut_removes_positional_from_args(self) -> None:
        """Positional args are removed before passing to parent."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        captured_args = []

        def mock_parse(ctx, args):
            captured_args.extend(args)
            return []

        with patch.object(click.Group, "parse_args", side_effect=mock_parse):
            group.parse_args(ctx, ["-s", "a-2", "file.md", "--verbose"])

        # file.md should be removed
        assert "file.md" not in captured_args
        # But -s, a-2, and --verbose should remain
        assert "-s" in captured_args
        assert "a-2" in captured_args
        assert "--verbose" in captured_args

    def test_options_not_treated_as_goal(self) -> None:
        """Arguments starting with - are not treated as goals."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["--verbose", "-q"])

        assert "_goal" not in ctx.obj

    def test_shortcut_stops_at_option(self) -> None:
        """Positional collection stops when option is encountered."""
        group = GoalFirstGroup("test")
        ctx = click.Context(group)
        ctx.ensure_object(dict)

        with patch.object(click.Group, "parse_args", return_value=[]):
            group.parse_args(ctx, ["-s", "a-2", "file.md", "--verbose", "ignored"])

        # Only file.md should be captured (before --verbose)
        assert ctx.obj.get("_positional_target") == "file.md"
        # ignored should not be in context_str
        assert ctx.obj.get("_context_str") is None


class TestMainCommandWithRunner:
    """Integration tests using Click's test runner."""

    def test_help_shows_without_error(self) -> None:
        """--help flag works correctly."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "sunwell" in result.output.lower() or "goal" in result.output.lower()

    def test_version_shows_without_error(self) -> None:
        """--version flag works correctly."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        # Should show version info

    def test_config_show_invokable(self) -> None:
        """config show subcommand is invokable."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "show"])

        # May succeed or fail based on config, but shouldn't crash
        assert result.exit_code in (0, 1, 2)

    def test_lens_list_invokable(self) -> None:
        """lens list subcommand is invokable."""
        runner = CliRunner()
        result = runner.invoke(main, ["lens", "list"])

        # May succeed or fail, but shouldn't crash
        assert result.exit_code in (0, 1, 2)

    def test_setup_help_works(self) -> None:
        """setup --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--help"])

        assert result.exit_code == 0


class TestCommandTiering:
    """Tests for command visibility tiering (RFC-109)."""

    def test_tier_1_2_commands_visible(self) -> None:
        """Tier 1-2 commands are not hidden."""
        visible_commands = {"config", "project", "session", "lens", "setup"}
        
        for cmd_name in visible_commands:
            cmd = main.commands.get(cmd_name)
            if cmd:
                assert not cmd.hidden, f"{cmd_name} should be visible (not hidden)"

    def test_tier_3_commands_hidden(self) -> None:
        """Tier 3 commands are hidden but accessible."""
        hidden_commands = {"benchmark", "demo", "eval", "runtime"}
        commands = main.list_commands(None)
        
        for cmd_name in hidden_commands:
            if cmd_name in commands:
                cmd = main.commands.get(cmd_name)
                if cmd:
                    assert cmd.hidden, f"{cmd_name} should be hidden"

    def test_tier_4_internal_commands_hidden(self) -> None:
        """Tier 4 internal commands are hidden."""
        internal_commands = {"backlog", "dag", "scan", "workspace", "workflow"}
        commands = main.list_commands(None)
        
        for cmd_name in internal_commands:
            if cmd_name in commands:
                cmd = main.commands.get(cmd_name)
                if cmd:
                    assert cmd.hidden, f"{cmd_name} should be hidden"


class TestAllCommandsFlag:
    """Tests for --all-commands hidden flag."""

    def test_all_commands_flag_exists(self) -> None:
        """--all-commands flag is defined on main."""
        param_names = {p.name for p in main.params if hasattr(p, "name")}
        # Check that all_commands exists (Click converts to underscore)
        assert "all_commands" in param_names
