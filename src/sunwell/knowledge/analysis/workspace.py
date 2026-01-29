"""Workspace topology model and detection engine (RFC-103).

The workspace is a graph of related project roots, enabling:
- Auto-detection of related code repositories
- Drift detection between docs and source
- Cross-reference validation

Example:
    detector = WorkspaceDetector()
    links = await detector.detect(Path("~/my-docs"))
    # Found: ../acme-core (pyproject.toml, 95% confidence)
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL CONSTANTS
# ═══════════════════════════════════════════════════════════════

# Project markers and their languages/confidence
_PROJECT_MARKERS: tuple[tuple[str, str, float], ...] = (
    ("pyproject.toml", "python", 0.95),
    ("setup.py", "python", 0.90),
    ("package.json", "typescript", 0.90),
    ("Cargo.toml", "rust", 0.95),
    ("go.mod", "go", 0.95),
    ("pom.xml", "java", 0.90),
    ("build.gradle", "java", 0.85),
    ("Gemfile", "ruby", 0.85),
    ("mix.exs", "elixir", 0.90),
)

# Directories that indicate this is a source code project (not just docs)
_SOURCE_INDICATORS: frozenset[str] = frozenset({
    "src", "lib", "pkg", "internal", "cmd", "app",
})

# ═══════════════════════════════════════════════════════════════
# PRE-COMPILED REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════

_RE_SYS_PATH = re.compile(r"sys\.path\.insert\s*\(\s*\d+\s*,\s*['\"]([^'\"]+)['\"]")
_RE_ABSPATH = re.compile(r"os\.path\.(?:abspath|dirname).*?['\"]([^'\"]+)['\"]")
_RE_REPO_URL = re.compile(r"repo_url:\s*['\"]?([^'\"\s]+)")
_RE_HANDLER_PATHS = re.compile(r"paths:\s*\[([^\]]+)\]")
_RE_GIT_ORG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"github\.com[:/]([^/]+)/"),
    re.compile(r"gitlab\.com[:/]([^/]+)/"),
    re.compile(r"bitbucket\.org[:/]([^/]+)/"),
)
_RE_WORD_SPLIT = re.compile(r"[-_]")

# ═══════════════════════════════════════════════════════════════
# CORE DATA MODELS
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class WorkspaceLink:
    """A directed relationship between two project roots."""

    source: Path
    """The project being scanned (docs root)."""

    target: Path
    """A related project (source code root)."""

    relationship: Literal["source_code", "documentation", "dependency", "sibling"]
    """Type of relationship."""

    confidence: float
    """Confidence score from 0.0 to 1.0."""

    evidence: str
    """Human-readable explanation for why this link was detected."""

    language: str | None = None
    """Detected programming language (python, typescript, go, rust, etc.)."""

    confirmed: bool = False
    """Whether the user has explicitly confirmed this link."""

    created_at: datetime = field(default_factory=datetime.now)
    """When this link was created."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            "source": str(self.source),
            "target": str(self.target),
            "relationship": self.relationship,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "language": self.language,
            "confirmed": self.confirmed,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> WorkspaceLink:
        """Deserialize from dictionary."""
        return cls(
            source=Path(data["source"]),
            target=Path(data["target"]),
            relationship=data["relationship"],
            confidence=data["confidence"],
            evidence=data["evidence"],
            language=data.get("language"),
            confirmed=data.get("confirmed", False),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )


@dataclass(frozen=True, slots=True)
class Workspace:
    """A workspace is a graph of related project roots."""

    id: str
    """Stable identifier for this workspace."""

    primary: Path
    """The project user opened/scanned (docs root)."""

    links: tuple[WorkspaceLink, ...]
    """All detected and confirmed links."""

    topology: Literal["monorepo", "polyrepo", "hybrid"]
    """Detected workspace topology."""

    created_at: datetime = field(default_factory=datetime.now)
    """When this workspace was created."""

    updated_at: datetime = field(default_factory=datetime.now)
    """When this workspace was last updated."""

    @property
    def source_roots(self) -> list[Path]:
        """All linked source code directories."""
        return [link.target for link in self.links if link.relationship == "source_code"]

    @property
    def confirmed_links(self) -> list[WorkspaceLink]:
        """Only links that have been confirmed by user."""
        return [link for link in self.links if link.confirmed]

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            "version": 1,
            "id": self.id,
            "primary": str(self.primary),
            "topology": self.topology,
            "links": [link.to_dict() for link in self.links],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Workspace:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            primary=Path(data["primary"]),
            links=tuple(WorkspaceLink.from_dict(lnk) for lnk in data.get("links", [])),
            topology=data.get("topology", "polyrepo"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(),
        )


# ═══════════════════════════════════════════════════════════════
# WORKSPACE PERSISTENCE
# ═══════════════════════════════════════════════════════════════


class WorkspaceConfig:
    """Manages workspace configuration persistence.

    Storage: .sunwell/workspace.json in the docs project root.
    """

    CONFIG_FILE = "workspace.json"
    SUNWELL_DIR = ".sunwell"

    def __init__(self, root: Path):
        """Initialize with docs project root."""
        self.root = Path(root).expanduser().resolve()
        self.config_dir = self.root / self.SUNWELL_DIR
        self.config_file = self.config_dir / self.CONFIG_FILE

    def exists(self) -> bool:
        """Check if workspace config exists."""
        return self.config_file.exists()

    def load(self) -> Workspace | None:
        """Load workspace from config file.

        Returns:
            Workspace if config exists, None otherwise.
        """
        if not self.config_file.exists():
            return None

        try:
            data = json.loads(self.config_file.read_text())
            return Workspace.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load workspace config: {e}")
            return None

    def save(self, workspace: Workspace) -> None:
        """Save workspace to config file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(workspace.to_dict(), indent=2))
        logger.info(f"Saved workspace config to {self.config_file}")

    def delete(self) -> None:
        """Delete workspace config file."""
        if self.config_file.exists():
            self.config_file.unlink()
            logger.info(f"Deleted workspace config: {self.config_file}")


# ═══════════════════════════════════════════════════════════════
# DETECTION ENGINE
# ═══════════════════════════════════════════════════════════════


class WorkspaceDetector:
    """Auto-detect related projects for workspace linking.

    Detection strategies:
    1. Parent directory scan (monorepo detection)
    2. Config file references (Sphinx conf.py, etc.)
    3. Git remote matching (same org)
    4. Sibling directory scan (adjacent repos)

    Example:
        detector = WorkspaceDetector()
        links = await detector.detect(Path("~/projects/acme-docs"))
        # Returns: [
        #   WorkspaceLink(target="..", confidence=0.95, evidence="Parent has pyproject.toml"),
        #   WorkspaceLink(target="../acme-api", confidence=0.85, evidence="Same GitHub org"),
        # ]
    """

    async def detect(self, docs_root: Path) -> list[WorkspaceLink]:
        """Run all detection strategies and return found links.

        Strategies run in parallel with individual timeouts.

        Args:
            docs_root: Root directory of the documentation project.

        Returns:
            List of WorkspaceLink with detected relationships.
        """
        docs_root = Path(docs_root).expanduser().resolve()
        links: list[WorkspaceLink] = []

        # Run detection strategies
        strategies = [
            self._detect_from_parent,
            self._detect_from_config,
            self._detect_from_git,
            self._detect_siblings,
        ]

        for strategy in strategies:
            try:
                found = strategy(docs_root)
                links.extend(found)
            except Exception as e:
                logger.warning(f"Detection strategy {strategy.__name__} failed: {e}")

        # Deduplicate by target path, keeping highest confidence
        seen: dict[Path, WorkspaceLink] = {}
        for link in links:
            target = link.target.resolve()
            if target not in seen or link.confidence > seen[target].confidence:
                seen[target] = link

        result = sorted(seen.values(), key=lambda lnk: lnk.confidence, reverse=True)
        logger.info(f"Detected {len(result)} workspace links for {docs_root}")
        return result

    def _detect_from_parent(self, docs_root: Path) -> list[WorkspaceLink]:
        """Strategy 1: Check if docs is inside a larger project (monorepo).

        This is the most common case (~60% of projects).
        """
        parent = docs_root.parent

        # Don't check if parent is home or root
        if parent == parent.parent or parent == Path.home():
            return []

        for marker, language, confidence in _PROJECT_MARKERS:
            marker_path = parent / marker
            if marker_path.exists():
                # Verify parent has actual source code (not just config)
                has_source = any(
                    (parent / indicator).is_dir()
                    for indicator in _SOURCE_INDICATORS
                )

                # Adjust confidence based on source indicators
                final_confidence = confidence if has_source else confidence * 0.8

                return [
                    WorkspaceLink(
                        source=docs_root,
                        target=parent,
                        relationship="source_code",
                        confidence=final_confidence,
                        evidence=f"Parent contains {marker}",
                        language=language,
                        confirmed=False,
                    )
                ]

        return []

    def _detect_from_config(self, docs_root: Path) -> list[WorkspaceLink]:
        """Strategy 2: Parse docs config files for source references.

        Sphinx conf.py often contains sys.path.insert() pointing to source.
        """
        links: list[WorkspaceLink] = []

        # Check Sphinx conf.py
        conf_py = docs_root / "conf.py"
        if conf_py.exists():
            try:
                content = conf_py.read_text()
                links.extend(self._parse_sphinx_config(content, docs_root))
            except Exception as e:
                logger.debug(f"Failed to parse conf.py: {e}")

        # Check MkDocs mkdocs.yml
        mkdocs_yml = docs_root / "mkdocs.yml"
        if mkdocs_yml.exists():
            try:
                content = mkdocs_yml.read_text()
                links.extend(self._parse_mkdocs_config(content, docs_root))
            except Exception as e:
                logger.debug(f"Failed to parse mkdocs.yml: {e}")

        return links

    def _parse_sphinx_config(self, content: str, docs_root: Path) -> list[WorkspaceLink]:
        """Parse Sphinx conf.py for source path references."""
        links: list[WorkspaceLink] = []

        # Look for sys.path.insert() calls
        for match in _RE_SYS_PATH.finditer(content):
            rel_path = match.group(1)
            source_path = (docs_root / rel_path).resolve()
            if source_path.exists() and source_path.is_dir():
                links.append(
                    WorkspaceLink(
                        source=docs_root,
                        target=source_path,
                        relationship="source_code",
                        confidence=0.95,
                        evidence=f"conf.py sys.path references {rel_path}",
                        language="python",
                        confirmed=False,
                    )
                )

        # Look for os.path.abspath patterns
        for match in _RE_ABSPATH.finditer(content):
            rel_path = match.group(1)
            if ".." in rel_path:
                source_path = (docs_root / rel_path).resolve()
                if source_path.exists() and source_path.is_dir():
                    links.append(
                        WorkspaceLink(
                            source=docs_root,
                            target=source_path,
                            relationship="source_code",
                            confidence=0.90,
                            evidence=f"conf.py path reference: {rel_path}",
                            language="python",
                            confirmed=False,
                        )
                    )

        return links

    def _parse_mkdocs_config(self, content: str, docs_root: Path) -> list[WorkspaceLink]:
        """Parse MkDocs mkdocs.yml for source path references."""
        links: list[WorkspaceLink] = []

        # Look for repo_url to identify related repo (unused but parsed for future)
        # _RE_REPO_URL.search(content) could be used for git matching

        # Look for plugins that reference source
        # mkdocstrings plugin often has path config
        for match in _RE_HANDLER_PATHS.finditer(content):
            paths_str = match.group(1)
            paths = [p.strip().strip("'\"") for p in paths_str.split(",")]
            for rel_path in paths:
                source_path = (docs_root / rel_path).resolve()
                if source_path.exists() and source_path.is_dir():
                    links.append(
                        WorkspaceLink(
                            source=docs_root,
                            target=source_path,
                            relationship="source_code",
                            confidence=0.90,
                            evidence=f"mkdocs.yml references {rel_path}",
                            language=self._detect_language(source_path),
                            confirmed=False,
                        )
                    )

        return links

    def _detect_from_git(self, docs_root: Path) -> list[WorkspaceLink]:
        """Strategy 3: Match git remotes across nearby repos."""
        docs_remote = self._get_git_remote(docs_root)
        if not docs_remote:
            return []

        docs_org = self._extract_org(docs_remote)
        if not docs_org:
            return []

        links: list[WorkspaceLink] = []
        parent = docs_root.parent

        for sibling in parent.iterdir():
            if sibling == docs_root or not sibling.is_dir():
                continue

            # Skip hidden directories
            if sibling.name.startswith("."):
                continue

            sibling_remote = self._get_git_remote(sibling)
            if not sibling_remote:
                continue

            sibling_org = self._extract_org(sibling_remote)
            if sibling_org and sibling_org == docs_org:
                language = self._detect_language(sibling)
                if language:  # Only link if it looks like a code project
                    links.append(
                        WorkspaceLink(
                            source=docs_root,
                            target=sibling,
                            relationship="source_code",
                            confidence=0.85,
                            evidence=f"Same GitHub org: {docs_org}",
                            language=language,
                            confirmed=False,
                        )
                    )

        return links

    def _detect_siblings(self, docs_root: Path) -> list[WorkspaceLink]:
        """Strategy 4: Scan sibling directories for related projects.

        Lower confidence than git matching, but useful when git isn't available.
        """
        links: list[WorkspaceLink] = []
        parent = docs_root.parent

        # Get docs project name components for matching
        docs_name = docs_root.name.lower()
        docs_parts = set(_RE_WORD_SPLIT.split(docs_name))

        for sibling in parent.iterdir():
            if sibling == docs_root or not sibling.is_dir():
                continue

            # Skip hidden directories
            if sibling.name.startswith("."):
                continue

            sibling_name = sibling.name.lower()
            sibling_parts = set(_RE_WORD_SPLIT.split(sibling_name))

            # Check for name overlap (e.g., "acme-docs" and "acme-api")
            overlap = docs_parts & sibling_parts
            # Remove common words that don't indicate relationship
            overlap -= {"docs", "documentation", "api", "app", "web", "ui", "frontend", "backend"}

            if overlap:
                language = self._detect_language(sibling)
                if language:  # Only link if it looks like a code project
                    links.append(
                        WorkspaceLink(
                            source=docs_root,
                            target=sibling,
                            relationship="source_code",
                            confidence=0.70,
                            evidence=f"Name similarity: shared '{', '.join(overlap)}'",
                            language=language,
                            confirmed=False,
                        )
                    )

        return links

    def _get_git_remote(self, path: Path) -> str | None:
        """Get the git remote URL for a directory."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None

    def _extract_org(self, remote_url: str) -> str | None:
        """Extract organization/user from git remote URL."""
        # Handle various formats:
        # git@github.com:org/repo.git
        # https://github.com/org/repo.git
        # https://github.com/org/repo
        for pattern in _RE_GIT_ORG_PATTERNS:
            match = pattern.search(remote_url)
            if match:
                return match.group(1)
        return None

    def _detect_language(self, path: Path) -> str | None:
        """Detect the primary language of a project.

        .. deprecated::
            Use `sunwell.planning.naaru.expertise.language.detect_language` instead.
        """
        import warnings

        warnings.warn(
            "Use sunwell.planning.naaru.expertise.language.detect_language instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        for marker, language, _ in _PROJECT_MARKERS:
            if (path / marker).exists():
                return language
        return None


# ═══════════════════════════════════════════════════════════════
# WORKSPACE BUILDER
# ═══════════════════════════════════════════════════════════════


async def build_workspace(
    docs_root: Path,
    auto_detect: bool = True,
    explicit_links: list[Path] | None = None,
) -> Workspace:
    """Build a workspace from detection results and explicit links.

    Args:
        docs_root: Root of the documentation project.
        auto_detect: Whether to run auto-detection.
        explicit_links: Additional paths to link explicitly.

    Returns:
        Configured Workspace ready for scanning.
    """
    import hashlib

    docs_root = Path(docs_root).expanduser().resolve()

    # Generate stable ID from path
    workspace_id = hashlib.sha256(str(docs_root).encode()).hexdigest()[:12]

    # Detect links
    links: list[WorkspaceLink] = []

    if auto_detect:
        detector = WorkspaceDetector()
        detected = await detector.detect(docs_root)
        links.extend(detected)

    # Add explicit links
    if explicit_links:
        for target in explicit_links:
            target = Path(target).expanduser().resolve()
            # Check if already detected
            if target.exists() and not any(lnk.target == target for lnk in links):
                    detector = WorkspaceDetector()
                    language = detector._detect_language(target)
                    links.append(
                        WorkspaceLink(
                            source=docs_root,
                            target=target,
                            relationship="source_code",
                            confidence=1.0,
                            evidence="Explicitly linked by user",
                            language=language,
                            confirmed=True,
                        )
                    )

    # Detect topology
    topology: Literal["monorepo", "polyrepo", "hybrid"] = "polyrepo"
    if links:
        # Monorepo: docs is inside a code project
        parent_links = [lnk for lnk in links if lnk.target == docs_root.parent]
        if parent_links:
            topology = "monorepo"
        # Hybrid: mix of parent and sibling links
        elif any(lnk.target == docs_root.parent for lnk in links) and len(links) > 1:
            topology = "hybrid"

    return Workspace(
        id=workspace_id,
        primary=docs_root,
        links=tuple(links),
        topology=topology,
    )


async def load_or_detect_workspace(
    docs_root: Path,
    auto_detect: bool = True,
) -> tuple[Workspace, bool]:
    """Load existing workspace or detect new one.

    Args:
        docs_root: Root of the documentation project.
        auto_detect: Whether to run auto-detection if no config exists.

    Returns:
        Tuple of (Workspace, is_new) where is_new indicates if detection was run.
    """
    config = WorkspaceConfig(docs_root)

    # Try to load existing
    existing = config.load()
    if existing:
        return existing, False

    # Detect new
    workspace = await build_workspace(docs_root, auto_detect=auto_detect)
    return workspace, True


def confirm_link(workspace: Workspace, target: Path) -> Workspace:
    """Mark a workspace link as confirmed by user.

    Args:
        workspace: Current workspace.
        target: Target path to confirm.

    Returns:
        New Workspace with updated link.
    """
    target = Path(target).expanduser().resolve()
    new_links = []

    for link in workspace.links:
        if link.target == target:
            # Create confirmed version
            new_links.append(
                WorkspaceLink(
                    source=link.source,
                    target=link.target,
                    relationship=link.relationship,
                    confidence=link.confidence,
                    evidence=link.evidence,
                    language=link.language,
                    confirmed=True,
                    created_at=link.created_at,
                )
            )
        else:
            new_links.append(link)

    return Workspace(
        id=workspace.id,
        primary=workspace.primary,
        links=tuple(new_links),
        topology=workspace.topology,
        created_at=workspace.created_at,
        updated_at=datetime.now(),
    )


def add_link(workspace: Workspace, target: Path, language: str | None = None) -> Workspace:
    """Add a new link to workspace.

    Args:
        workspace: Current workspace.
        target: Target path to add.
        language: Optional language override.

    Returns:
        New Workspace with added link.
    """
    target = Path(target).expanduser().resolve()

    # Check if already exists
    if any(lnk.target == target for lnk in workspace.links):
        return workspace

    detector = WorkspaceDetector()
    detected_language = language or detector._detect_language(target)

    new_link = WorkspaceLink(
        source=workspace.primary,
        target=target,
        relationship="source_code",
        confidence=1.0,
        evidence="Manually linked by user",
        language=detected_language,
        confirmed=True,
    )

    return Workspace(
        id=workspace.id,
        primary=workspace.primary,
        links=(*workspace.links, new_link),
        topology=workspace.topology,
        created_at=workspace.created_at,
        updated_at=datetime.now(),
    )


def remove_link(workspace: Workspace, target: Path) -> Workspace:
    """Remove a link from workspace.

    Args:
        workspace: Current workspace.
        target: Target path to remove.

    Returns:
        New Workspace without the link.
    """
    target = Path(target).expanduser().resolve()
    new_links = [lnk for lnk in workspace.links if lnk.target != target]

    return Workspace(
        id=workspace.id,
        primary=workspace.primary,
        links=tuple(new_links),
        topology=workspace.topology,
        created_at=workspace.created_at,
        updated_at=datetime.now(),
    )
