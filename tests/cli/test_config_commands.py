"""Tests for the config command group."""

import pytest
from click.testing import CliRunner

from sunwell.interface.cli.commands.config_cmd import config


class TestConfigShow:
    """Tests for 'sunwell config show' command."""

    def test_config_show_runs_without_error(self) -> None:
        """config show runs successfully."""
        runner = CliRunner()
        result = runner.invoke(config, ["show"])

        # Should not crash
        assert result.exit_code == 0

    def test_config_show_displays_sections(self) -> None:
        """config show displays expected configuration sections."""
        runner = CliRunner()
        result = runner.invoke(config, ["show"])

        # Check for main sections
        assert "Simulacrum" in result.output or "Configuration" in result.output


class TestConfigInit:
    """Tests for 'sunwell config init' command."""

    def test_config_init_creates_file(self, tmp_path) -> None:
        """config init creates a config file."""
        runner = CliRunner()
        config_path = tmp_path / "config.yaml"

        result = runner.invoke(config, ["init", "--path", str(config_path)])

        assert result.exit_code == 0
        assert config_path.exists()
        assert "Config file created" in result.output


class TestConfigGet:
    """Tests for 'sunwell config get' command."""

    def test_config_get_valid_key(self) -> None:
        """config get returns value for valid key."""
        runner = CliRunner()
        result = runner.invoke(config, ["get", "model.default_provider"])

        # Should return a value (even if default)
        assert result.exit_code == 0
        # Output should be the value (like "ollama" or "anthropic")
        assert result.output.strip() != ""

    def test_config_get_invalid_key(self) -> None:
        """config get returns error for invalid key."""
        runner = CliRunner()
        result = runner.invoke(config, ["get", "nonexistent.key.path"])

        assert result.exit_code == 1
        assert "Key not found" in result.output


class TestConfigSet:
    """Tests for 'sunwell config set' command."""

    def test_config_set_creates_value(self, tmp_path) -> None:
        """config set creates a new value in config file."""
        runner = CliRunner()
        config_path = tmp_path / ".sunwell" / "config.yaml"
        config_path.parent.mkdir(parents=True)

        result = runner.invoke(
            config, ["set", "model.default_provider", "test-provider", "--path", str(config_path)]
        )

        assert result.exit_code == 0
        assert "Set model.default_provider" in result.output
        assert config_path.exists()

    def test_config_set_boolean_parsing(self, tmp_path) -> None:
        """config set correctly parses boolean values."""
        runner = CliRunner()
        config_path = tmp_path / "config.yaml"

        runner.invoke(config, ["set", "test.bool_true", "true", "--path", str(config_path)])
        runner.invoke(config, ["set", "test.bool_false", "false", "--path", str(config_path)])

        import yaml

        with config_path.open() as f:
            data = yaml.safe_load(f)

        assert data["test"]["bool_true"] is True
        assert data["test"]["bool_false"] is False

    def test_config_set_numeric_parsing(self, tmp_path) -> None:
        """config set correctly parses numeric values."""
        runner = CliRunner()
        config_path = tmp_path / "config.yaml"

        runner.invoke(config, ["set", "test.integer", "42", "--path", str(config_path)])
        runner.invoke(config, ["set", "test.float", "3.14", "--path", str(config_path)])

        import yaml

        with config_path.open() as f:
            data = yaml.safe_load(f)

        assert data["test"]["integer"] == 42
        assert data["test"]["float"] == 3.14


class TestConfigUnset:
    """Tests for 'sunwell config unset' command."""

    def test_config_unset_removes_key(self, tmp_path) -> None:
        """config unset removes a key from config file."""
        runner = CliRunner()
        config_path = tmp_path / "config.yaml"

        # First set a value
        runner.invoke(config, ["set", "test.key", "value", "--path", str(config_path)])

        # Then unset it
        result = runner.invoke(config, ["unset", "test.key", "--path", str(config_path)])

        assert result.exit_code == 0
        assert "Removed" in result.output

        # Verify key is gone
        import yaml

        with config_path.open() as f:
            data = yaml.safe_load(f)

        assert "key" not in data.get("test", {})

    def test_config_unset_nonexistent_key(self, tmp_path) -> None:
        """config unset handles nonexistent key gracefully."""
        runner = CliRunner()
        config_path = tmp_path / "config.yaml"

        # Create empty config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}")

        result = runner.invoke(config, ["unset", "nonexistent.key", "--path", str(config_path)])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestConfigStructure:
    """Tests for config command structure."""

    def test_config_is_group(self) -> None:
        """config is a click group with subcommands."""
        assert hasattr(config, "commands")
        assert "show" in config.commands
        assert "init" in config.commands
        assert "get" in config.commands
        assert "set" in config.commands
        assert "unset" in config.commands

    def test_config_help(self) -> None:
        """config --help shows subcommands."""
        runner = CliRunner()
        result = runner.invoke(config, ["--help"])

        assert result.exit_code == 0
        assert "show" in result.output
        assert "init" in result.output
        assert "get" in result.output
