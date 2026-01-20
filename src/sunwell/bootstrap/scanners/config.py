"""Configuration Scanner — RFC-050.

Extract patterns from configuration files: pyproject.toml, CI configs, etc.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from sunwell.bootstrap.types import ConfigEvidence


class ConfigScanner:
    """Extract patterns from configuration files."""

    def __init__(self, root: Path):
        """Initialize configuration scanner.

        Args:
            root: Project root directory
        """
        self.root = Path(root)

    async def scan(self) -> ConfigEvidence:
        """Scan configuration files."""
        evidence: dict = {}

        # Parse each config file type
        if (self.root / "pyproject.toml").exists():
            evidence.update(self._parse_pyproject())

        if (self.root / "setup.cfg").exists():
            evidence.update(self._parse_setup_cfg())

        if (self.root / ".editorconfig").exists():
            evidence.update(self._parse_editorconfig())

        if (self.root / "ruff.toml").exists():
            evidence.update(self._parse_ruff_toml())

        if (self.root / ".pre-commit-config.yaml").exists():
            evidence.update(self._parse_precommit())

        # Parse CI configs
        ci_provider, ci_checks = self._parse_ci_configs()
        evidence["ci_provider"] = ci_provider
        evidence["ci_checks"] = ci_checks

        return ConfigEvidence(
            python_version=evidence.get("python_version"),
            formatter=evidence.get("formatter"),
            linter=evidence.get("linter"),
            type_checker=evidence.get("type_checker"),
            test_framework=evidence.get("test_framework"),
            line_length=evidence.get("line_length"),
            ci_provider=ci_provider,
            ci_checks=tuple(ci_checks),
        )

    def _parse_pyproject(self) -> dict:
        """Parse pyproject.toml for tool configurations."""
        path = self.root / "pyproject.toml"
        result: dict = {}

        try:
            import tomllib
            content = tomllib.loads(path.read_text())
        except (ImportError, OSError):
            # Fall back to regex parsing
            return self._parse_pyproject_regex()

        # Python version
        if requires := content.get("project", {}).get("requires-python"):
            result["python_version"] = requires

        tool = content.get("tool", {})

        # Ruff
        if "ruff" in tool:
            result["formatter"] = "ruff"
            result["linter"] = "ruff"
            if line_length := tool["ruff"].get("line-length"):
                result["line_length"] = line_length

        # Black
        if "black" in tool:
            result["formatter"] = "black"
            if line_length := tool["black"].get("line-length"):
                result["line_length"] = line_length

        # Mypy
        if "mypy" in tool:
            result["type_checker"] = "mypy"

        # Pyright
        if "pyright" in tool:
            result["type_checker"] = "pyright"

        # ty
        if "ty" in tool:
            result["type_checker"] = "ty"

        # Pytest
        if "pytest" in tool:
            result["test_framework"] = "pytest"

        # Flake8 (not typically in pyproject.toml but some tools support it)
        if "flake8" in tool and "linter" not in result:
            result["linter"] = "flake8"

        return result

    def _parse_pyproject_regex(self) -> dict:
        """Parse pyproject.toml using regex (fallback when tomllib unavailable)."""
        path = self.root / "pyproject.toml"
        result: dict = {}

        try:
            content = path.read_text()
        except OSError:
            return result

        # Python version
        match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            result["python_version"] = match.group(1)

        # Line length
        match = re.search(r'line-length\s*=\s*(\d+)', content)
        if match:
            result["line_length"] = int(match.group(1))

        # Tool detection
        if "[tool.ruff]" in content:
            result["formatter"] = "ruff"
            result["linter"] = "ruff"
        if "[tool.black]" in content:
            result["formatter"] = "black"
        if "[tool.mypy]" in content:
            result["type_checker"] = "mypy"
        if "[tool.pyright]" in content:
            result["type_checker"] = "pyright"
        if "[tool.pytest" in content:
            result["test_framework"] = "pytest"

        return result

    def _parse_setup_cfg(self) -> dict:
        """Parse setup.cfg for tool configurations."""
        path = self.root / "setup.cfg"
        result: dict = {}

        try:
            content = path.read_text()
        except OSError:
            return result

        # Flake8
        if "[flake8]" in content and "linter" not in result:
            result["linter"] = "flake8"
            match = re.search(r'max-line-length\s*=\s*(\d+)', content)
            if match:
                result["line_length"] = int(match.group(1))

        # Mypy
        if "[mypy]" in content:
            result["type_checker"] = "mypy"

        return result

    def _parse_editorconfig(self) -> dict:
        """Parse .editorconfig for style settings."""
        path = self.root / ".editorconfig"
        result: dict = {}

        try:
            content = path.read_text()
        except OSError:
            return result

        # Max line length
        match = re.search(r'max_line_length\s*=\s*(\d+)', content)
        if match:
            result["line_length"] = int(match.group(1))

        return result

    def _parse_ruff_toml(self) -> dict:
        """Parse ruff.toml for ruff configuration."""
        path = self.root / "ruff.toml"
        result: dict = {
            "formatter": "ruff",
            "linter": "ruff",
        }

        try:
            content = path.read_text()
        except OSError:
            return result

        match = re.search(r'line-length\s*=\s*(\d+)', content)
        if match:
            result["line_length"] = int(match.group(1))

        return result

    def _parse_precommit(self) -> dict:
        """Parse .pre-commit-config.yaml for tool detection."""
        path = self.root / ".pre-commit-config.yaml"
        result: dict = {}

        try:
            content = path.read_text()
        except OSError:
            return result

        # Look for common hooks
        if "ruff" in content:
            result["linter"] = "ruff"
            result["formatter"] = "ruff"
        if "black" in content:
            result["formatter"] = "black"
        if "flake8" in content and "linter" not in result:
            result["linter"] = "flake8"
        if "mypy" in content:
            result["type_checker"] = "mypy"

        return result

    def _parse_ci_configs(self) -> tuple[
        Literal["github", "gitlab", "jenkins", "none"] | None,
        list[str],
    ]:
        """Parse CI configuration files."""
        ci_provider: Literal["github", "gitlab", "jenkins", "none"] | None = None
        ci_checks: list[str] = []

        # GitHub Actions
        github_workflows = self.root / ".github" / "workflows"
        if github_workflows.exists():
            ci_provider = "github"
            for workflow in github_workflows.glob("*.yml"):
                ci_checks.extend(self._parse_github_workflow(workflow))
            for workflow in github_workflows.glob("*.yaml"):
                ci_checks.extend(self._parse_github_workflow(workflow))

        # GitLab CI
        gitlab_ci = self.root / ".gitlab-ci.yml"
        if gitlab_ci.exists():
            ci_provider = "gitlab"
            ci_checks.extend(self._parse_gitlab_ci(gitlab_ci))

        # Jenkins
        jenkinsfile = self.root / "Jenkinsfile"
        if jenkinsfile.exists():
            ci_provider = "jenkins"
            ci_checks.extend(self._parse_jenkinsfile(jenkinsfile))

        return ci_provider, list(set(ci_checks))  # Deduplicate

    def _parse_github_workflow(self, path: Path) -> list[str]:
        """Parse GitHub Actions workflow for CI checks."""
        checks: list[str] = []

        try:
            content = path.read_text()
        except OSError:
            return checks

        # Look for common tools in run commands
        if "ruff" in content or "flake8" in content or "pylint" in content:
            checks.append("lint")
        if "pytest" in content or "python -m unittest" in content:
            checks.append("test")
        if "mypy" in content or "pyright" in content:
            checks.append("typecheck")
        if "black" in content and "black --check" in content:
            checks.append("format")
        if "coverage" in content:
            checks.append("coverage")

        return checks

    def _parse_gitlab_ci(self, path: Path) -> list[str]:
        """Parse GitLab CI config for CI checks."""
        checks: list[str] = []

        try:
            content = path.read_text()
        except OSError:
            return checks

        # Similar pattern matching
        if "ruff" in content or "flake8" in content or "lint" in content.lower():
            checks.append("lint")
        if "pytest" in content or "test" in content.lower():
            checks.append("test")
        if "mypy" in content or "pyright" in content:
            checks.append("typecheck")

        return checks

    def _parse_jenkinsfile(self, path: Path) -> list[str]:
        """Parse Jenkinsfile for CI checks."""
        checks: list[str] = []

        try:
            content = path.read_text()
        except OSError:
            return checks

        if "lint" in content.lower():
            checks.append("lint")
        if "test" in content.lower():
            checks.append("test")
        if "type" in content.lower():
            checks.append("typecheck")

        return checks
