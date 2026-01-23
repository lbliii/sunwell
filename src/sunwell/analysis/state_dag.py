"""State DAG builder for existing project scanning (RFC-100).

The State DAG represents "what exists and its health" in a project:
- Nodes: Artifacts that exist (files, modules, docs, packages)
- Edges: Relationships (imports, links, toctree, dependencies)
- Colors: Health scores (🟢 healthy → 🔴 needs attention)

This enables brownfield workflows where users can:
1. Scan existing project: `sunwell scan ~/my-docs`
2. See project health visualization in Studio
3. Click red nodes to give intent and spawn Execution DAGs
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from sunwell.lens.loader import Lens

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HealthProbeResult:
    """Result from a health probe execution."""

    probe_name: str
    """Name of the probe that produced this result."""

    score: float
    """Health score from 0.0 (unhealthy) to 1.0 (healthy)."""

    issues: tuple[str, ...]
    """List of issues found by the probe."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional probe-specific metadata."""


@dataclass(frozen=True, slots=True)
class StateDagNode:
    """A node in the State DAG representing an existing artifact."""

    id: str
    """Unique identifier for this node."""

    path: Path
    """Path to the artifact (file or directory)."""

    artifact_type: str
    """Type of artifact: 'file', 'module', 'package', 'doc', 'directory'."""

    title: str
    """Human-readable title for display."""

    health_score: float
    """Aggregate health score from 0.0-1.0."""

    health_probes: tuple[HealthProbeResult, ...]
    """Results from individual health probes."""

    last_modified: datetime | None = None
    """When the artifact was last modified."""

    line_count: int | None = None
    """Number of lines (for files)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional artifact-specific metadata."""

    @property
    def confidence_band(self) -> str:
        """Map health score to confidence band.

        Returns:
            'high' (🟢 90-100%), 'moderate' (🟡 70-89%),
            'low' (🟠 50-69%), 'uncertain' (🔴 <50%)
        """
        score_pct = self.health_score * 100
        if score_pct >= 90:
            return "high"
        elif score_pct >= 70:
            return "moderate"
        elif score_pct >= 50:
            return "low"
        else:
            return "uncertain"


@dataclass(frozen=True, slots=True)
class StateDagEdge:
    """An edge in the State DAG representing a relationship."""

    source: str
    """ID of the source node."""

    target: str
    """ID of the target node."""

    edge_type: str
    """Type of relationship: 'import', 'link', 'toctree', 'depends'."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional edge-specific metadata."""


@dataclass
class StateDag:
    """The complete State DAG for a project."""

    root: Path
    """Project root directory."""

    nodes: list[StateDagNode]
    """All nodes in the DAG."""

    edges: list[StateDagEdge]
    """All edges in the DAG."""

    scanned_at: datetime = field(default_factory=datetime.now)
    """When the scan was performed."""

    lens_name: str | None = None
    """Name of the lens used for scanning."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional scan metadata."""

    @property
    def overall_health(self) -> float:
        """Calculate overall project health score."""
        if not self.nodes:
            return 1.0
        return sum(n.health_score for n in self.nodes) / len(self.nodes)

    @property
    def unhealthy_nodes(self) -> list[StateDagNode]:
        """Get nodes with health score < 0.7 (🟡 threshold)."""
        return [n for n in self.nodes if n.health_score < 0.7]

    @property
    def critical_nodes(self) -> list[StateDagNode]:
        """Get nodes with health score < 0.5 (🔴 threshold)."""
        return [n for n in self.nodes if n.health_score < 0.5]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "root": str(self.root),
            "scanned_at": self.scanned_at.isoformat(),
            "lens_name": self.lens_name,
            "overall_health": self.overall_health,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "unhealthy_count": len(self.unhealthy_nodes),
            "critical_count": len(self.critical_nodes),
            "nodes": [
                {
                    "id": n.id,
                    "path": str(n.path),
                    "artifact_type": n.artifact_type,
                    "title": n.title,
                    "health_score": n.health_score,
                    "confidence_band": n.confidence_band,
                    "health_probes": [
                        {
                            "probe_name": p.probe_name,
                            "score": p.score,
                            "issues": list(p.issues),
                        }
                        for p in n.health_probes
                    ],
                    "last_modified": n.last_modified.isoformat() if n.last_modified else None,
                    "line_count": n.line_count,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type,
                }
                for e in self.edges
            ],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class Scanner(Protocol):
    """Protocol for lens-specific scanners."""

    async def scan_nodes(self, root: Path) -> list[StateDagNode]:
        """Scan the project and return nodes."""
        ...

    async def extract_edges(
        self, root: Path, nodes: list[StateDagNode]
    ) -> list[StateDagEdge]:
        """Extract edges between nodes."""
        ...

    async def run_health_probes(
        self, root: Path,
        nodes: list[StateDagNode],
        source_contexts: list[Any] | None = None,
    ) -> dict[str, list[HealthProbeResult]]:
        """Run health probes and return results keyed by node ID.

        Args:
            root: Project root directory.
            nodes: All discovered nodes.
            source_contexts: Optional list of SourceContext for drift detection (RFC-103).
        """
        ...


class StateDagBuilder:
    """Builds a State DAG from an existing project.

    The builder uses lens-specific scanners to:
    1. Discover nodes (files, modules, packages)
    2. Extract edges (imports, links, dependencies)
    3. Run health probes (linting, coverage, drift detection)

    Example:
        builder = StateDagBuilder(root=Path("~/my-docs"), lens=tech_writer_lens)
        dag = await builder.build()
        # dag.nodes contains all discovered artifacts with health scores

    RFC-103: Workspace-aware scanning with source context:
        from sunwell.analysis.source_context import SourceContext
        ctx = await SourceContext.build(Path("~/acme-core"))
        builder = StateDagBuilder(root=docs_path, source_contexts=[ctx])
        dag = await builder.build()
        # dag includes drift detection against linked source
    """

    def __init__(
        self,
        root: Path,
        lens: Lens | None = None,
        source_contexts: list[Any] | None = None,
    ):
        """Initialize the State DAG builder.

        Args:
            root: Project root directory
            lens: Optional lens for domain-specific scanning
            source_contexts: Optional list of SourceContext for drift detection (RFC-103)
        """
        self.root = Path(root).expanduser().resolve()
        self.lens = lens
        self.source_contexts = source_contexts or []
        self._scanner: Scanner | None = None

    async def build(self) -> StateDag:
        """Build the complete State DAG.

        Returns:
            StateDag with all nodes, edges, and health scores.
        """
        logger.info(f"Building State DAG for {self.root}")

        # Get the appropriate scanner
        scanner = await self._get_scanner()

        # Phase 1: Discover nodes
        nodes = await scanner.scan_nodes(self.root)
        logger.info(f"Discovered {len(nodes)} nodes")

        # Phase 2: Extract edges
        edges = await scanner.extract_edges(self.root, nodes)
        logger.info(f"Extracted {len(edges)} edges")

        # Phase 3: Run health probes (RFC-103: pass source contexts for drift detection)
        health_results = await scanner.run_health_probes(
            self.root,
            nodes,
            source_contexts=self.source_contexts,
        )

        # Phase 4: Merge health results into nodes
        enriched_nodes = self._enrich_nodes_with_health(nodes, health_results)

        lens_name = None
        if self.lens:
            lens_name = self.lens.metadata.get("name") if hasattr(self.lens, "metadata") else None

        return StateDag(
            root=self.root,
            nodes=enriched_nodes,
            edges=edges,
            lens_name=lens_name,
            metadata={
                "source_roots": [str(ctx.root) for ctx in self.source_contexts],
            } if self.source_contexts else {},
        )

    async def _get_scanner(self) -> Scanner:
        """Get the appropriate scanner for this project."""
        if self._scanner:
            return self._scanner

        # Try to get lens-specific scanner
        if self.lens and hasattr(self.lens, "get_scanner"):
            self._scanner = self.lens.get_scanner()
            return self._scanner

        # Auto-detect based on project markers
        from sunwell.analysis.scanners.code import CodeScanner
        from sunwell.analysis.scanners.docs import DocsScanner

        if self._is_docs_project():
            self._scanner = DocsScanner()
        else:
            self._scanner = CodeScanner()

        return self._scanner

    def _is_docs_project(self) -> bool:
        """Detect if this is a documentation project."""
        doc_markers = [
            "conf.py",  # Sphinx
            "mkdocs.yml",  # MkDocs
            "docusaurus.config.js",  # Docusaurus
            "book.toml",  # mdBook
            "_quarto.yml",  # Quarto
        ]
        for marker in doc_markers:
            if (self.root / marker).exists():
                return True

        # Check for high markdown density
        md_count = len(list(self.root.glob("**/*.md")))
        py_count = len(list(self.root.glob("**/*.py")))
        return md_count > py_count * 2  # Mostly markdown = docs project

    def _enrich_nodes_with_health(
        self,
        nodes: list[StateDagNode],
        health_results: dict[str, list[HealthProbeResult]],
    ) -> list[StateDagNode]:
        """Merge health probe results into nodes."""
        enriched = []
        for node in nodes:
            probes = health_results.get(node.id, [])
            if probes:
                # Calculate aggregate health score (average of probe scores)
                avg_score = sum(p.score for p in probes) / len(probes)
                enriched.append(
                    StateDagNode(
                        id=node.id,
                        path=node.path,
                        artifact_type=node.artifact_type,
                        title=node.title,
                        health_score=avg_score,
                        health_probes=tuple(probes),
                        last_modified=node.last_modified,
                        line_count=node.line_count,
                        metadata=node.metadata,
                    )
                )
            else:
                enriched.append(node)
        return enriched


async def scan_project(
    root: Path,
    lens: Lens | None = None,
    source_contexts: list[Any] | None = None,
) -> StateDag:
    """Convenience function to scan a project and build a State DAG.

    Args:
        root: Project root directory
        lens: Optional lens for domain-specific scanning
        source_contexts: Optional list of SourceContext for drift detection (RFC-103)

    Returns:
        Complete State DAG with health scores
    """
    builder = StateDagBuilder(root=root, lens=lens, source_contexts=source_contexts)
    return await builder.build()
