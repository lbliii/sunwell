"""Monorepo Detection (RFC-079).

Detect and surface sub-projects in monorepos.
"""

import json
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import yaml


@dataclass(frozen=True, slots=True)
class SubProject:
    """A sub-project within a monorepo."""

    name: str
    """Sub-project name."""

    path: Path
    """Sub-project root path."""

    manifest: Path
    """Path to manifest file (package.json, pyproject.toml, etc.)."""

    project_type: str = "unknown"
    """Detected project type (code, docs, etc.)."""

    description: str = ""
    """Description from manifest if available."""


def detect_sub_projects(path: Path) -> list[SubProject]:
    """Detect sub-projects in a monorepo.

    Checks common monorepo patterns:
    - npm workspaces (packages/*, apps/*)
    - pnpm workspaces
    - Cargo workspaces
    - Python services pattern

    Args:
        path: Monorepo root path.

    Returns:
        List of detected sub-projects.
    """
    sub_projects: list[SubProject] = []

    # Check common monorepo patterns
    patterns = [
        ("packages/*/package.json", "code"),
        ("apps/*/package.json", "code"),
        ("services/*/pyproject.toml", "code"),
        ("crates/*/Cargo.toml", "code"),
        ("libs/*/package.json", "code"),
        ("modules/*/pyproject.toml", "code"),
    ]

    for pattern, proj_type in patterns:
        for manifest in path.glob(pattern):
            name = manifest.parent.name
            description = _get_description(manifest)
            sub_projects.append(
                SubProject(
                    name=name,
                    path=manifest.parent,
                    manifest=manifest,
                    project_type=proj_type,
                    description=description,
                )
            )

    # Check for workspace definitions
    pnpm_workspace = path / "pnpm-workspace.yaml"
    if pnpm_workspace.exists():
        sub_projects.extend(_parse_pnpm_workspace(path, pnpm_workspace))

    cargo_toml = path / "Cargo.toml"
    if cargo_toml.exists():
        sub_projects.extend(_parse_cargo_workspace(path, cargo_toml))

    package_json = path / "package.json"
    if package_json.exists():
        sub_projects.extend(_parse_npm_workspaces(path, package_json))

    # Check for documentation as sub-project
    docs_path = path / "docs"
    if docs_path.is_dir():
        if (docs_path / "conf.py").exists():
            sub_projects.append(
                SubProject(
                    name="docs",
                    path=docs_path,
                    manifest=docs_path / "conf.py",
                    project_type="documentation",
                    description="Sphinx documentation",
                )
            )
        elif (path / "mkdocs.yml").exists() or (path / "mkdocs.yaml").exists():
            mkdocs_file = (
                path / "mkdocs.yml"
                if (path / "mkdocs.yml").exists()
                else path / "mkdocs.yaml"
            )
            sub_projects.append(
                SubProject(
                    name="docs",
                    path=docs_path,
                    manifest=mkdocs_file,
                    project_type="documentation",
                    description="MkDocs documentation",
                )
            )

    # Deduplicate by path
    seen_paths: set[Path] = set()
    unique_projects: list[SubProject] = []
    for proj in sub_projects:
        if proj.path not in seen_paths:
            seen_paths.add(proj.path)
            unique_projects.append(proj)

    return unique_projects


def _get_description(manifest: Path) -> str:
    """Extract description from manifest file."""
    try:
        if manifest.name == "package.json":
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return data.get("description", "")

        elif manifest.name == "pyproject.toml":
            data = tomllib.loads(manifest.read_text(encoding="utf-8"))
            return data.get("project", {}).get("description", "")

        elif manifest.name == "Cargo.toml":
            data = tomllib.loads(manifest.read_text(encoding="utf-8"))
            return data.get("package", {}).get("description", "")

    except (json.JSONDecodeError, OSError):
        pass

    return ""


def _parse_pnpm_workspace(root: Path, workspace_file: Path) -> list[SubProject]:
    """Parse pnpm-workspace.yaml for sub-projects."""
    sub_projects: list[SubProject] = []

    try:
        data = yaml.safe_load(workspace_file.read_text(encoding="utf-8"))
        packages = data.get("packages", [])

        for pattern in packages:
            # Handle glob patterns like "packages/*"
            if "*" in pattern:
                base_dir = pattern.replace("/*", "").replace("/**", "")
                base_path = root / base_dir
                if base_path.is_dir():
                    for sub_dir in base_path.iterdir():
                        if sub_dir.is_dir():
                            manifest = sub_dir / "package.json"
                            if manifest.exists():
                                sub_projects.append(
                                    SubProject(
                                        name=sub_dir.name,
                                        path=sub_dir,
                                        manifest=manifest,
                                        project_type="code",
                                        description=_get_description(manifest),
                                    )
                                )
            else:
                # Exact path
                sub_path = root / pattern
                manifest = sub_path / "package.json"
                if manifest.exists():
                    sub_projects.append(
                        SubProject(
                            name=sub_path.name,
                            path=sub_path,
                            manifest=manifest,
                            project_type="code",
                            description=_get_description(manifest),
                        )
                    )

    except (yaml.YAMLError, OSError):
        pass

    return sub_projects


def _parse_cargo_workspace(root: Path, cargo_toml: Path) -> list[SubProject]:
    """Parse Cargo.toml workspace members."""
    sub_projects: list[SubProject] = []

    try:
        data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        workspace = data.get("workspace", {})
        members = workspace.get("members", [])

        for member in members:
            if "*" in member:
                # Handle glob patterns
                base_dir = member.replace("/*", "").replace("/**", "")
                base_path = root / base_dir
                if base_path.is_dir():
                    for sub_dir in base_path.iterdir():
                        manifest = sub_dir / "Cargo.toml"
                        if manifest.exists():
                            sub_projects.append(
                                SubProject(
                                    name=sub_dir.name,
                                    path=sub_dir,
                                    manifest=manifest,
                                    project_type="code",
                                    description=_get_description(manifest),
                                )
                            )
            else:
                sub_path = root / member
                manifest = sub_path / "Cargo.toml"
                if manifest.exists():
                    sub_projects.append(
                        SubProject(
                            name=sub_path.name,
                            path=sub_path,
                            manifest=manifest,
                            project_type="code",
                            description=_get_description(manifest),
                        )
                    )

    except OSError:
        pass

    return sub_projects


def _parse_npm_workspaces(root: Path, package_json: Path) -> list[SubProject]:
    """Parse package.json workspaces field."""
    sub_projects: list[SubProject] = []

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        workspaces = data.get("workspaces", [])

        # Handle both array and object format
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])

        for workspace in workspaces:
            if "*" in workspace:
                # Handle glob patterns like "packages/*"
                base_dir = workspace.replace("/*", "").replace("/**", "")
                base_path = root / base_dir
                if base_path.is_dir():
                    for sub_dir in base_path.iterdir():
                        if sub_dir.is_dir():
                            manifest = sub_dir / "package.json"
                            if manifest.exists():
                                sub_projects.append(
                                    SubProject(
                                        name=sub_dir.name,
                                        path=sub_dir,
                                        manifest=manifest,
                                        project_type="code",
                                        description=_get_description(manifest),
                                    )
                                )
            else:
                sub_path = root / workspace
                manifest = sub_path / "package.json"
                if manifest.exists():
                    sub_projects.append(
                        SubProject(
                            name=sub_path.name,
                            path=sub_path,
                            manifest=manifest,
                            project_type="code",
                            description=_get_description(manifest),
                        )
                    )

    except (json.JSONDecodeError, OSError):
        pass

    return sub_projects


def is_monorepo(path: Path) -> bool:
    """Check if a project is likely a monorepo.

    Args:
        path: Project root path.

    Returns:
        True if monorepo indicators are found.
    """
    indicators = [
        # Workspace config files
        (path / "pnpm-workspace.yaml").exists(),
        (path / "lerna.json").exists(),
        (path / "nx.json").exists(),
        (path / "turbo.json").exists(),
        # Directory patterns
        (path / "packages").is_dir(),
        (path / "apps").is_dir(),
        (path / "services").is_dir(),
        (path / "crates").is_dir(),
    ]

    # Also check package.json for workspaces field
    package_json = path / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if "workspaces" in data:
                indicators.append(True)
        except (json.JSONDecodeError, OSError):
            pass

    # Also check Cargo.toml for workspace
    cargo_toml = path / "Cargo.toml"
    if cargo_toml.exists():
        try:
            data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
            if "workspace" in data:
                indicators.append(True)
        except OSError:
            pass

    return any(indicators)
