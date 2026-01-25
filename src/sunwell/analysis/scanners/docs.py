"""Documentation-specific scanner for State DAG (RFC-100).

Scans documentation projects (Sphinx, MkDocs, Docusaurus, etc.) to build
a State DAG with:
- Nodes: Individual doc files, directories, index pages
- Edges: Toctree relationships, cross-references, internal links
- Health probes: Orphan detection, broken links, drift detection, readability
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from sunwell.analysis.state_dag import (
    HealthProbeResult,
    Scanner,
    StateDagEdge,
    StateDagNode,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL CONSTANTS
# ═══════════════════════════════════════════════════════════════

_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "__pycache__", "node_modules", "_build", "build",
    "dist", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "htmlcov", "site", ".cursor", ".idea", ".vscode",
})

_SKIP_PREFIXES: tuple[str, ...] = (".venv", "venv", ".env", "env")

# ═══════════════════════════════════════════════════════════════
# PRE-COMPILED REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════

# Title extraction
_RE_MD_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_RE_RST_H1 = re.compile(r"^(.+)\n={3,}$", re.MULTILINE)

# Toctree extraction
_RE_MYST_TOCTREE = re.compile(r"```\{toctree\}.*?```", re.DOTALL)
_RE_RST_TOCTREE = re.compile(r"\.\.\s+toctree::\s*\n((?:\s+.+\n?)+)")

# Cross-references
_RE_MYST_REFS = re.compile(r"\{(?:ref|doc)\}`([^`]+)`")
_RE_RST_REFS = re.compile(r":(?:ref|doc):`([^`]+)`")

# Markdown links
_RE_MD_LINKS = re.compile(r"\[.+?\]\(([^)]+)\)")


class DocsScanner(Scanner):
    """Scanner for documentation projects.

    Supports:
    - Sphinx (conf.py)
    - MkDocs (mkdocs.yml)
    - MyST Markdown
    - reStructuredText

    Health probes:
    - orphan_check: Files not in toctree
    - link_check: Broken internal links
    - freshness: Stale files (not updated recently)
    - readability: Basic readability metrics
    """

    async def scan_nodes(self, root: Path) -> list[StateDagNode]:
        """Scan documentation project for nodes.

        Discovers:
        - All .md and .rst files
        - Directory indices (index.md, index.rst)
        - Special files (conf.py, mkdocs.yml)

        Args:
            root: Project root directory

        Returns:
            List of StateDagNode for each artifact
        """
        nodes: list[StateDagNode] = []
        doc_extensions = {".md", ".rst", ".mdx"}

        # Find all documentation files
        for ext in doc_extensions:
            for path in root.glob(f"**/*{ext}"):
                # Skip hidden directories and build artifacts
                if self._should_skip(path):
                    continue

                node = await self._create_node(path, root)
                nodes.append(node)

        # Add directory nodes for directories with multiple docs
        nodes.extend(await self._create_directory_nodes(root, nodes))

        logger.info(f"DocsScanner found {len(nodes)} nodes")
        return nodes

    async def extract_edges(
        self, root: Path, nodes: list[StateDagNode]
    ) -> list[StateDagEdge]:
        """Extract edges between documentation nodes.

        Extracts:
        - Toctree relationships (parent → child)
        - Cross-references ({ref}, :ref:, :doc:)
        - Internal links ([text](path), `text <path>`_)

        Args:
            root: Project root directory
            nodes: Already discovered nodes

        Returns:
            List of StateDagEdge representing relationships
        """
        edges: list[StateDagEdge] = []
        node_ids = {n.id for n in nodes}
        node_by_path = {str(n.path.relative_to(root)): n.id for n in nodes}

        for node in nodes:
            if node.artifact_type == "directory":
                continue

            try:
                content = node.path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # Extract toctree edges (Sphinx/MyST)
            toctree_refs = self._extract_toctree(content, node.path, root)
            for ref in toctree_refs:
                ref_id = self._resolve_reference(ref, node.path, root, node_by_path)
                if ref_id and ref_id in node_ids and ref_id != node.id:
                    edges.append(
                        StateDagEdge(
                            source=node.id,
                            target=ref_id,
                            edge_type="toctree",
                        )
                    )

            # Extract cross-references
            xrefs = self._extract_cross_references(content)
            for ref in xrefs:
                ref_id = self._resolve_reference(ref, node.path, root, node_by_path)
                if ref_id and ref_id in node_ids and ref_id != node.id:
                    edges.append(
                        StateDagEdge(
                            source=node.id,
                            target=ref_id,
                            edge_type="link",
                        )
                    )

            # Extract markdown links
            md_links = self._extract_markdown_links(content)
            for link in md_links:
                ref_id = self._resolve_reference(link, node.path, root, node_by_path)
                if ref_id and ref_id in node_ids and ref_id != node.id:
                    edges.append(
                        StateDagEdge(
                            source=node.id,
                            target=ref_id,
                            edge_type="link",
                        )
                    )

        logger.info(f"DocsScanner extracted {len(edges)} edges")
        return edges

    async def run_health_probes(
        self,
        root: Path,
        nodes: list[StateDagNode],
        source_contexts: list | None = None,
    ) -> dict[str, list[HealthProbeResult]]:
        """Run health probes on all nodes.

        Probes:
        - orphan_check: Is this file in any toctree?
        - freshness: How recently was it updated?
        - size_check: Is the file too long or too short?
        - broken_links: Any broken internal links?
        - drift_detection: Does the doc match the source code? (RFC-103)

        Args:
            root: Project root directory
            nodes: All discovered nodes
            source_contexts: Optional list of SourceContext for drift detection (RFC-103)

        Returns:
            Dict mapping node ID to list of health probe results
        """
        from sunwell.analysis.probes.drift import DriftProbe

        results: dict[str, list[HealthProbeResult]] = {}

        # Build toctree index for orphan detection
        toctree_children = await self._build_toctree_index(root, nodes)

        # Create drift probe if source contexts provided (RFC-103)
        drift_probe = DriftProbe(source_contexts) if source_contexts else None

        for node in nodes:
            probes: list[HealthProbeResult] = []

            if node.artifact_type != "directory":
                # Orphan check
                orphan_result = self._probe_orphan(node, toctree_children, root)
                probes.append(orphan_result)

                # Freshness check
                freshness_result = self._probe_freshness(node)
                probes.append(freshness_result)

                # Size check
                size_result = self._probe_size(node)
                probes.append(size_result)

                # Broken links check
                link_result = await self._probe_broken_links(node, root, nodes)
                probes.append(link_result)

                # RFC-103: Drift detection (if source contexts provided)
                if drift_probe:
                    drift_result = await drift_probe.run(node)
                    probes.append(drift_result)

            results[node.id] = probes

        return results

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped during scanning."""
        for part in path.parts:
            if part in _SKIP_DIRS:
                return True
            if any(part.startswith(prefix) for prefix in _SKIP_PREFIXES):
                return True
        return False

    async def _create_node(self, path: Path, root: Path) -> StateDagNode:
        """Create a StateDagNode for a documentation file."""
        rel_path = path.relative_to(root)
        node_id = str(rel_path).replace("/", "-").replace("\\", "-").replace(".", "-")

        # Get file stats
        stat = path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime)

        # Count lines
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            line_count = len(content.splitlines())
        except Exception:
            line_count = 0

        # Determine title from content or filename
        title = await self._extract_title(path)

        # Determine artifact type
        artifact_type = "doc"
        if path.name in ("index.md", "index.rst", "README.md"):
            artifact_type = "index"

        return StateDagNode(
            id=node_id,
            path=path,
            artifact_type=artifact_type,
            title=title,
            health_score=1.0,  # Will be updated by health probes
            health_probes=(),
            last_modified=last_modified,
            line_count=line_count,
        )

    async def _create_directory_nodes(
        self, root: Path, file_nodes: list[StateDagNode]
    ) -> list[StateDagNode]:
        """Create nodes for directories containing multiple docs."""
        dir_counts: dict[Path, int] = {}
        for node in file_nodes:
            parent = node.path.parent
            if parent != root:
                dir_counts[parent] = dir_counts.get(parent, 0) + 1

        dir_nodes: list[StateDagNode] = []
        for dir_path, count in dir_counts.items():
            if count >= 2:  # Only create node for directories with 2+ files
                rel_path = dir_path.relative_to(root)
                node_id = f"dir-{str(rel_path).replace('/', '-').replace('\\', '-')}"

                # Check if directory has an index file
                has_index = any(
                    (dir_path / idx).exists()
                    for idx in ("index.md", "index.rst", "README.md")
                )

                dir_nodes.append(
                    StateDagNode(
                        id=node_id,
                        path=dir_path,
                        artifact_type="directory",
                        title=dir_path.name,
                        health_score=1.0,
                        health_probes=(),
                        metadata={"file_count": count, "has_index": has_index},
                    )
                )

        return dir_nodes

    async def _extract_title(self, path: Path) -> str:
        """Extract title from document content or use filename."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")

            # Try to find H1 heading
            # Markdown: # Title
            md_h1 = _RE_MD_H1.search(content)
            if md_h1:
                return md_h1.group(1).strip()

            # RST: Title\n=====
            rst_h1 = _RE_RST_H1.search(content)
            if rst_h1:
                return rst_h1.group(1).strip()

            # Fallback to filename
            return path.stem.replace("-", " ").replace("_", " ").title()

        except Exception:
            return path.stem.replace("-", " ").replace("_", " ").title()

    def _extract_toctree(
        self, content: str, file_path: Path, root: Path
    ) -> list[str]:
        """Extract toctree entries from content."""
        refs: list[str] = []

        # MyST toctree (```{toctree} ... ```)
        for match in _RE_MYST_TOCTREE.finditer(content):
            block = match.group(0)
            # Extract entries (lines that don't start with :)
            for line in block.split("\n"):
                line = line.strip()
                if line and not line.startswith(":") and not line.startswith("`"):
                    refs.append(line)

        # RST toctree (.. toctree::)
        for match in _RE_RST_TOCTREE.finditer(content):
            block = match.group(1)
            for line in block.split("\n"):
                line = line.strip()
                if line and not line.startswith(":"):
                    refs.append(line)

        return refs

    def _extract_cross_references(self, content: str) -> list[str]:
        """Extract Sphinx/MyST cross-references."""
        refs: list[str] = []

        # MyST {ref}`label` or {doc}`path`
        refs.extend(_RE_MYST_REFS.findall(content))

        # RST :ref:`label` or :doc:`path`
        refs.extend(_RE_RST_REFS.findall(content))

        return refs

    def _extract_markdown_links(self, content: str) -> list[str]:
        """Extract markdown-style links."""
        # [text](path) but not external links
        links = _RE_MD_LINKS.findall(content)
        return [
            link
            for link in links
            if not link.startswith(("http://", "https://", "mailto:", "#"))
        ]

    def _resolve_reference(
        self,
        ref: str,
        source_path: Path,
        root: Path,
        node_by_path: dict[str, str],
    ) -> str | None:
        """Resolve a reference to a node ID."""
        # Remove any anchor
        ref = ref.split("#")[0].strip()
        if not ref:
            return None

        # Try as relative path from source
        source_dir = source_path.parent
        for ext in ("", ".md", ".rst", "/index.md", "/index.rst"):
            candidate = (source_dir / (ref + ext)).resolve()
            try:
                rel = candidate.relative_to(root)
                rel_str = str(rel)
                if rel_str in node_by_path:
                    return node_by_path[rel_str]
            except ValueError:
                pass

        # Try as absolute path from root
        for ext in ("", ".md", ".rst", "/index.md", "/index.rst"):
            candidate = (root / (ref.lstrip("/") + ext)).resolve()
            try:
                rel = candidate.relative_to(root)
                rel_str = str(rel)
                if rel_str in node_by_path:
                    return node_by_path[rel_str]
            except ValueError:
                pass

        return None

    async def _build_toctree_index(
        self, root: Path, nodes: list[StateDagNode]
    ) -> set[str]:
        """Build set of all files referenced in any toctree."""
        toctree_children: set[str] = set()
        node_by_path = {str(n.path.relative_to(root)): n.id for n in nodes}

        for node in nodes:
            if node.artifact_type == "directory":
                continue

            try:
                content = node.path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            refs = self._extract_toctree(content, node.path, root)
            for ref in refs:
                ref_id = self._resolve_reference(ref, node.path, root, node_by_path)
                if ref_id:
                    toctree_children.add(ref_id)

        return toctree_children

    def _probe_orphan(
        self, node: StateDagNode, toctree_children: set[str], root: Path
    ) -> HealthProbeResult:
        """Check if a file is an orphan (not in any toctree)."""
        # Index files and root level files are not orphans
        if node.artifact_type == "index":
            return HealthProbeResult(
                probe_name="orphan_check",
                score=1.0,
                issues=(),
            )

        rel_path = node.path.relative_to(root)
        if len(rel_path.parts) == 1:
            # Root level file
            return HealthProbeResult(
                probe_name="orphan_check",
                score=1.0,
                issues=(),
            )

        if node.id in toctree_children:
            return HealthProbeResult(
                probe_name="orphan_check",
                score=1.0,
                issues=(),
            )

        return HealthProbeResult(
            probe_name="orphan_check",
            score=0.3,
            issues=("File not included in any toctree (orphan)",),
        )

    def _probe_freshness(self, node: StateDagNode) -> HealthProbeResult:
        """Check if a file is stale (not updated recently)."""
        if not node.last_modified:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.5,
                issues=("Could not determine last modified date",),
            )

        days_old = (datetime.now() - node.last_modified).days

        if days_old <= 30:
            return HealthProbeResult(
                probe_name="freshness",
                score=1.0,
                issues=(),
                metadata={"days_old": days_old},
            )
        elif days_old <= 90:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.8,
                issues=(),
                metadata={"days_old": days_old},
            )
        elif days_old <= 180:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.6,
                issues=(f"File not updated in {days_old} days",),
                metadata={"days_old": days_old},
            )
        else:
            return HealthProbeResult(
                probe_name="freshness",
                score=0.4,
                issues=(f"File is {days_old} days old - may be stale",),
                metadata={"days_old": days_old},
            )

    def _probe_size(self, node: StateDagNode) -> HealthProbeResult:
        """Check if file size is appropriate."""
        if not node.line_count:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.5,
                issues=("Could not determine file size",),
            )

        lines = node.line_count

        if 50 <= lines <= 1000:
            return HealthProbeResult(
                probe_name="size_check",
                score=1.0,
                issues=(),
                metadata={"line_count": lines},
            )
        elif lines < 50:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.7,
                issues=("File is very short - may need more content",),
                metadata={"line_count": lines},
            )
        elif lines <= 2000:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.7,
                issues=("File is long - consider splitting",),
                metadata={"line_count": lines},
            )
        else:
            return HealthProbeResult(
                probe_name="size_check",
                score=0.4,
                issues=(f"File is very long ({lines} lines) - should be modularized",),
                metadata={"line_count": lines},
            )

    async def _probe_broken_links(
        self, node: StateDagNode, root: Path, all_nodes: list[StateDagNode]
    ) -> HealthProbeResult:
        """Check for broken internal links."""
        try:
            content = node.path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return HealthProbeResult(
                probe_name="broken_links",
                score=0.5,
                issues=("Could not read file to check links",),
            )

        node_by_path = {str(n.path.relative_to(root)): n.id for n in all_nodes}
        links = self._extract_markdown_links(content)
        links.extend(self._extract_cross_references(content))

        broken: list[str] = []
        for link in links:
            ref_id = self._resolve_reference(link, node.path, root, node_by_path)
            if ref_id is None:
                # Check if the file actually exists (might not be a doc file)
                link_path = link.split("#")[0].strip()
                if link_path:
                    source_dir = node.path.parent
                    candidate = source_dir / link_path
                    if not candidate.exists() and not (root / link_path.lstrip("/")).exists():
                        broken.append(link)

        if not broken:
            return HealthProbeResult(
                probe_name="broken_links",
                score=1.0,
                issues=(),
            )
        elif len(broken) <= 2:
            return HealthProbeResult(
                probe_name="broken_links",
                score=0.7,
                issues=tuple(f"Broken link: {link}" for link in broken),
            )
        else:
            return HealthProbeResult(
                probe_name="broken_links",
                score=0.4,
                issues=tuple(f"Broken link: {link}" for link in broken[:5]),
                metadata={"total_broken": len(broken)},
            )
