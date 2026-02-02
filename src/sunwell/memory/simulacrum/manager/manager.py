"""SimulacrumManager - Orchestrate multiple simulacrums.

RFC-014 Extension: Multi-Simulacrum Support

Just as humans switch mental contexts when moving between tasks,
the agent can maintain and switch between multiple simulacrums:

- **Project simulacrums**: One per codebase/project
- **Role simulacrums**: "code-reviewer", "docs-writer", "debugger"
- **Topic simulacrums**: "security", "performance", "api-design"

Key capabilities:
- Switch simulacrums explicitly or via intelligent routing
- Query across simulacrums for cross-domain knowledge
- Consolidate/merge simulacrums as they mature
- Track usage patterns to suggest relevant simulacrums

Example flow:
1. User asks about API security
2. Agent activates "security" simulacrum (with API security learnings)
3. User pivots to performance tuning
4. Agent switches to "performance" simulacrum
5. When both topics intersect, agent queries both simulacrums
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sunwell.foundation.utils import safe_json_dump, safe_json_load

logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING

from sunwell.memory.simulacrum.core.store import SimulacrumStore, StorageConfig
from sunwell.memory.simulacrum.manager.metadata import (
    ArchiveMetadata,
    PendingDomain,
    SimulacrumMetadata,
)
from sunwell.memory.simulacrum.manager.policy import LifecyclePolicy, SpawnPolicy

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.topology.memory_node import MemoryNode


@dataclass(slots=True)
class SimulacrumManager:
    """Manages multiple simulacrums with switching and cross-query capabilities.

    Usage:
        manager = SimulacrumManager(base_path=Path("./simulacrums"))

        # Create/load simulacrums
        manager.create("security", "Security analysis and threat modeling")
        manager.create("performance", "Performance optimization patterns")

        # Switch active simulacrum
        manager.activate("security")

        # Query across all simulacrums
        results = manager.query_all("rate limiting best practices")

        # Consolidate related simulacrums
        manager.merge("api-security", into="security")

        # Auto-spawning: detects when queries don't fit existing simulacrums
        result = manager.route_query("How do I implement OAuth2?")
        # → May auto-create "authentication" simulacrum if novel enough
    """

    base_path: Path
    """Root directory for all simulacrums."""

    storage_config: StorageConfig = field(default_factory=StorageConfig)
    """Default storage config for new simulacrums."""

    spawn_policy: SpawnPolicy = field(default_factory=SpawnPolicy)
    """Policy for automatic simulacrum creation."""

    lifecycle_policy: LifecyclePolicy = field(default_factory=LifecyclePolicy)
    """Policy for simulacrum archival, cleanup, and shrinking."""

    # Current state
    _active_name: str | None = field(default=None, init=False)
    _active_store: SimulacrumStore | None = field(default=None, init=False)

    # Registry
    _metadata: dict[str, SimulacrumMetadata] = field(default_factory=dict, init=False)
    _stores: dict[str, SimulacrumStore] = field(default_factory=dict, init=False)

    # Archive registry
    _archived: dict[str, ArchiveMetadata] = field(default_factory=dict, init=False)

    # Auto-spawn tracking
    _pending_domains: list[PendingDomain] = field(default_factory=list, init=False)
    _recent_unmatched_queries: list[str] = field(default_factory=list, init=False)

    # Optional embedder for cross-simulacrum queries
    _embedder: EmbeddingProtocol | None = field(default=None, init=False)

    def __post_init__(self):
        self.base_path = Path(self.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._load_registry()

    def _load_registry(self) -> None:
        """Load simulacrum registry from disk. Gracefully handles missing/corrupt files."""
        registry_path = self.base_path / "registry.json"
        data = safe_json_load(registry_path, default={})
        if data:
            for name, meta_dict in data.get("simulacrums", {}).items():
                self._metadata[name] = SimulacrumMetadata.from_dict(meta_dict)
            for name, archive_dict in data.get("archived", {}).items():
                self._archived[name] = ArchiveMetadata.from_dict(archive_dict)

    def _save_registry(self) -> None:
        """Save simulacrum registry to disk with atomic write."""
        registry_path = self.base_path / "registry.json"
        data = {
            "simulacrums": {
                name: meta.to_dict() for name, meta in self._metadata.items()
            },
            "archived": {
                name: meta.to_dict() for name, meta in self._archived.items()
            },
            "updated_at": datetime.now().isoformat(),
        }
        if not safe_json_dump(data, registry_path):
            logger.error("Failed to save simulacrum registry")

    def set_embedder(self, embedder: EmbeddingProtocol) -> None:
        """Set embedder for semantic operations."""
        self._embedder = embedder
        # Update active store if any
        if self._active_store:
            self._active_store.set_embedder(embedder)

    # === Simulacrum Lifecycle ===

    def create(
        self,
        name: str,
        description: str,
        domains: tuple[str, ...] = (),
    ) -> SimulacrumStore:
        """Create a new simulacrum.

        Args:
            name: Unique identifier (e.g., "security", "docs-api")
            description: What this simulacrum is for
            domains: Domain tags for routing

        Returns:
            The new SimulacrumStore
        """
        if name in self._metadata:
            raise ValueError(f"Simulacrum '{name}' already exists")

        # Create store
        store_path = self.base_path / name
        store = SimulacrumStore(
            base_path=store_path,
            config=self.storage_config,
        )

        if self._embedder:
            store.set_embedder(self._embedder)

        # Create metadata
        meta = SimulacrumMetadata(
            name=name,
            description=description,
            domains=domains,
        )

        self._metadata[name] = meta
        self._stores[name] = store
        self._save_registry()

        return store

    def list_simulacrums(self) -> list[SimulacrumMetadata]:
        """List all available simulacrums, sorted by recent access."""
        return sorted(
            self._metadata.values(),
            key=lambda m: m.last_accessed,
            reverse=True,
        )

    def get(self, name: str) -> SimulacrumStore:
        """Get a simulacrum store by name (lazy-loads if needed)."""
        if name not in self._metadata:
            raise KeyError(f"Simulacrum '{name}' not found")

        if name not in self._stores:
            # Lazy load
            store_path = self.base_path / name
            store = SimulacrumStore(
                base_path=store_path,
                config=self.storage_config,
            )
            if self._embedder:
                store.set_embedder(self._embedder)
            self._stores[name] = store

        return self._stores[name]

    def delete(self, name: str, confirm: bool = False) -> None:
        """Delete a simulacrum.

        Args:
            name: Simulacrum to delete
            confirm: Must be True to actually delete
        """
        if not confirm:
            raise ValueError("Must set confirm=True to delete a simulacrum")

        if name not in self._metadata:
            raise KeyError(f"Simulacrum '{name}' not found")

        # Remove from memory
        if name in self._stores:
            del self._stores[name]
        del self._metadata[name]

        # Remove from disk
        import shutil
        store_path = self.base_path / name
        if store_path.exists():
            shutil.rmtree(store_path)

        # Clear active if it was this one
        if self._active_name == name:
            self._active_name = None
            self._active_store = None

        self._save_registry()

    # === Activation / Switching ===

    def activate(self, name: str) -> SimulacrumStore:
        """Activate a simulacrum, making it the current context.

        Args:
            name: Simulacrum to activate

        Returns:
            The activated SimulacrumStore
        """
        store = self.get(name)

        # Save current simulacrum state
        if self._active_store:
            self._active_store.save_session()

        # Update metadata
        meta = self._metadata[name]
        meta.last_accessed = datetime.now().isoformat()
        meta.access_count += 1

        # Update stats from store
        stats = store.stats()
        meta.node_count = stats.get("unified_store", {}).get("total_nodes", 0)
        meta.learning_count = stats.get("dag_stats", {}).get("learnings", 0)

        self._active_name = name
        self._active_store = store
        self._save_registry()

        return store

    @property
    def active(self) -> SimulacrumStore | None:
        """Get the currently active simulacrum."""
        return self._active_store

    @property
    def active_name(self) -> str | None:
        """Get the name of the currently active simulacrum."""
        return self._active_name

    # === Intelligent Routing ===

    def suggest(self, query: str, top_k: int = 3) -> list[tuple[SimulacrumMetadata, float]]:
        """Suggest relevant simulacrums for a query.

        Uses domain tags and description matching to find relevant simulacrums.

        Args:
            query: The user's query/task
            top_k: Number of suggestions to return

        Returns:
            List of (metadata, relevance_score) tuples
        """
        query_lower = query.lower()
        scores: list[tuple[SimulacrumMetadata, float]] = []

        for meta in self._metadata.values():
            score = 0.0

            # Check domain tags
            for domain in meta.domains:
                if domain.lower() in query_lower:
                    score += 0.4

            # Check description keywords
            desc_words = set(meta.description.lower().split())
            query_words = set(query_lower.split())
            overlap = len(desc_words & query_words)
            if overlap > 0:
                score += 0.3 * min(overlap / 3, 1.0)

            # Recency bonus (slight preference for recently used)
            if meta.access_count > 0:
                score += 0.1

            # Name match
            if meta.name.lower() in query_lower:
                score += 0.5

            if score > 0:
                scores.append((meta, min(score, 1.0)))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def auto_activate(self, query: str, threshold: float = 0.3) -> SimulacrumStore | None:
        """Automatically activate the best simulacrum for a query.

        Args:
            query: The user's query
            threshold: Minimum relevance score to activate

        Returns:
            The activated store, or None if no good match
        """
        suggestions = self.suggest(query, top_k=1)
        if suggestions and suggestions[0][1] >= threshold:
            return self.activate(suggestions[0][0].name)
        return None

    # === Auto-Spawning ===

    def route_query(
        self,
        query: str,
        activate: bool = True,
    ) -> tuple[SimulacrumStore | None, bool, str]:
        """Smart routing: find, activate, or spawn a simulacrum for a query.

        This is the main entry point for auto-spawning. It:
        1. Tries to find an existing simulacrum that matches
        2. If no match, tracks the query as "unmatched"
        3. When enough unmatched queries accumulate in a coherent domain,
           auto-spawns a new simulacrum

        Args:
            query: The user's query
            activate: Whether to activate the matched/spawned simulacrum

        Returns:
            Tuple of (store, was_spawned, explanation)
        """
        # 1. Try to find existing match
        suggestions = self.suggest(query, top_k=1)

        if suggestions and suggestions[0][1] >= self.spawn_policy.novelty_threshold:
            # Good match exists
            meta, score = suggestions[0]
            store = self.activate(meta.name) if activate else self.get(meta.name)
            return store, False, f"Matched existing simulacrum: {meta.name} ({score:.0%})"

        # 2. No good match - this is a potentially novel domain
        if not self.spawn_policy.enabled:
            # Spawning disabled, just use best match if any
            if suggestions and activate:
                return self.activate(suggestions[0][0].name), False, "Using closest match (spawning disabled)"
            return None, False, "No matching simulacrum (spawning disabled)"

        # 3. Track as unmatched and check for spawn conditions
        spawn_result = self._track_and_maybe_spawn(query)

        if spawn_result:
            store, name = spawn_result
            if activate:
                self.activate(name)
            return store, True, f"Auto-spawned new simulacrum: {name}"

        # 4. Not ready to spawn yet - use best available or none
        if suggestions and suggestions[0][1] >= 0.2 and activate:
            return self.activate(suggestions[0][0].name), False, f"Using closest match: {suggestions[0][0].name}"

        return None, False, "Query tracked; waiting for more context before spawning"

    def _track_and_maybe_spawn(self, query: str) -> tuple[SimulacrumStore, str] | None:
        """Track unmatched query and spawn if conditions are met.

        Returns (store, name) if spawned, None otherwise.
        """
        # Check simulacrum limit
        if len(self._metadata) >= self.spawn_policy.max_simulacrums:
            return None

        # Add to recent unmatched
        self._recent_unmatched_queries.append(query)

        # Keep only recent queries (sliding window)
        max_tracked = self.spawn_policy.min_queries_before_spawn * 3
        if len(self._recent_unmatched_queries) > max_tracked:
            self._recent_unmatched_queries = self._recent_unmatched_queries[-max_tracked:]

        # Try to find or create a pending domain for this query
        best_domain = self._find_or_create_pending_domain(query)
        best_domain.add_query(query)

        # Check spawn conditions
        if len(best_domain.queries) >= self.spawn_policy.min_queries_before_spawn:
            coherence = best_domain.coherence_score()
            if coherence >= self.spawn_policy.domain_coherence_threshold:
                return self._spawn_from_pending(best_domain)

        return None

    def _find_or_create_pending_domain(self, query: str) -> PendingDomain:
        """Find a pending domain this query belongs to, or create new."""
        query_words = set(query.lower().split())

        best_match: PendingDomain | None = None
        best_overlap = 0

        for domain in self._pending_domains:
            # Check keyword overlap with existing pending domain
            domain_words = set(domain.keywords.keys())
            overlap = len(query_words & domain_words)

            if overlap > best_overlap:
                best_overlap = overlap
                best_match = domain

        # If good match found, use it
        if best_match and best_overlap >= 2:
            return best_match

        # Create new pending domain
        new_domain = PendingDomain()
        self._pending_domains.append(new_domain)

        # Limit pending domains
        if len(self._pending_domains) > 10:
            # Remove oldest
            self._pending_domains = self._pending_domains[-10:]

        return new_domain

    def _spawn_from_pending(self, domain: PendingDomain) -> tuple[SimulacrumStore, str]:
        """Create a simulacrum from a pending domain."""
        # Generate name from top keywords
        top_kw = domain.top_keywords(3)
        name = "-".join(top_kw) if top_kw else f"auto-{len(self._metadata)}"

        # Ensure unique name
        base_name = name
        counter = 1
        while name in self._metadata:
            name = f"{base_name}-{counter}"
            counter += 1

        # Generate description
        if len(domain.queries) > 0:
            description = f"Auto-created for topics: {', '.join(top_kw)}"
        else:
            description = "Auto-created simulacrum"

        # Create the simulacrum
        store = self.create(
            name=name,
            description=description,
            domains=tuple(top_kw),
        )

        # Mark as auto-spawned
        self._metadata[name].auto_spawned = True
        self._metadata[name].spawn_trigger_queries = tuple(domain.queries[:5])

        # Remove from pending
        if domain in self._pending_domains:
            self._pending_domains.remove(domain)

        # Clear matched queries from unmatched list
        for q in domain.queries:
            if q in self._recent_unmatched_queries:
                self._recent_unmatched_queries.remove(q)

        self._save_registry()

        return store, name

    def check_spawn_status(self) -> dict:
        """Get current auto-spawn tracking status.

        Useful for debugging and transparency about what the manager is tracking.
        """
        pending_info = []
        for i, domain in enumerate(self._pending_domains):
            pending_info.append({
                "index": i,
                "query_count": len(domain.queries),
                "top_keywords": domain.top_keywords(5),
                "coherence": round(domain.coherence_score(), 2),
                "ready_to_spawn": (
                    len(domain.queries) >= self.spawn_policy.min_queries_before_spawn
                    and domain.coherence_score() >= self.spawn_policy.domain_coherence_threshold
                ),
            })

        return {
            "spawn_enabled": self.spawn_policy.enabled,
            "novelty_threshold": self.spawn_policy.novelty_threshold,
            "min_queries": self.spawn_policy.min_queries_before_spawn,
            "coherence_threshold": self.spawn_policy.domain_coherence_threshold,
            "unmatched_queries": len(self._recent_unmatched_queries),
            "pending_domains": pending_info,
            "simulacrum_count": len(self._metadata),
            "max_simulacrums": self.spawn_policy.max_simulacrums,
        }

    # === Cross-Simulacrum Operations ===

    def query_all(
        self,
        query: str,
        limit_per_simulacrum: int = 5,
    ) -> list[tuple[str, MemoryNode, float]]:
        """Query across all simulacrums.

        Useful when you need knowledge that might exist in different contexts.

        Args:
            query: Search query
            limit_per_simulacrum: Max results per simulacrum

        Returns:
            List of (simulacrum_name, node, score) tuples
        """
        results: list[tuple[str, MemoryNode, float]] = []

        for name, _meta in self._metadata.items():
            store = self.get(name)
            if store.unified_store:
                nodes = store.unified_store.query(
                    text_query=query,
                    limit=limit_per_simulacrum,
                )
                for node, score in nodes:
                    results.append((name, node, score))

        # Sort by score across all simulacrums
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def find_related_simulacrums(self, name: str) -> list[tuple[str, float]]:
        """Find simulacrums related to a given one by domain overlap.

        Useful for suggesting consolidation candidates.
        """
        if name not in self._metadata:
            return []

        source = self._metadata[name]
        source_domains = set(source.domains)

        related: list[tuple[str, float]] = []
        for other_name, other_meta in self._metadata.items():
            if other_name == name:
                continue

            other_domains = set(other_meta.domains)
            if source_domains and other_domains:
                overlap = len(source_domains & other_domains)
                union = len(source_domains | other_domains)
                jaccard = overlap / union if union > 0 else 0
                if jaccard > 0:
                    related.append((other_name, jaccard))

        related.sort(key=lambda x: x[1], reverse=True)
        return related

    # === Consolidation / Merging ===

    def merge(
        self,
        source: str,
        into: str,
        delete_source: bool = False,
    ) -> int:
        """Merge one simulacrum into another.

        Consolidates memory nodes and learnings from source into target.

        Args:
            source: Simulacrum to merge from
            into: Simulacrum to merge into
            delete_source: If True, delete source after merge

        Returns:
            Number of nodes merged
        """
        source_store = self.get(source)
        target_store = self.get(into)

        merged_count = 0

        # Merge unified store nodes
        if source_store.unified_store and target_store.unified_store:
            for node in source_store.unified_store._nodes.values():
                # Check for duplicates by content hash
                exists = any(
                    n.content == node.content
                    for n in target_store.unified_store._nodes.values()
                )
                if not exists:
                    target_store.unified_store.add_node(node)
                    merged_count += 1

            # Merge concept graph edges
            for edges in source_store.unified_store._concept_graph._edges.values():
                for edge in edges:
                    target_store.unified_store._concept_graph.add_edge(edge)

        # Merge learnings from DAG
        source_dag = source_store.get_dag()
        target_dag = target_store.get_dag()

        for learning in source_dag.get_active_learnings():
            # Check for duplicates
            exists = any(
                l.fact == learning.fact
                for l in target_dag.get_active_learnings()
            )
            if not exists:
                target_dag.add_learning(learning)
                merged_count += 1

        # Save target
        target_store.save_session()

        # Update target metadata
        target_meta = self._metadata[into]
        target_stats = target_store.stats()
        target_meta.node_count = target_stats.get("unified_store", {}).get("total_nodes", 0)
        target_meta.learning_count = target_stats.get("dag_stats", {}).get("learnings", 0)

        # Optionally delete source
        if delete_source:
            self.delete(source, confirm=True)

        self._save_registry()
        return merged_count

    # === Lifecycle Management (Archive, Cleanup, Shrink) ===

    def check_health(self) -> dict:
        """Check simulacrum health and return cleanup recommendations.

        Returns dict with:
        - stale: Simulacrums not accessed recently
        - empty: Simulacrums with no useful content
        - merge_candidates: Similar simulacrums that could be merged
        - archive_candidates: Ready for cold storage
        """

        now = datetime.now()
        stale: list[tuple[str, int]] = []  # (name, days_since_access)
        empty: list[str] = []
        archive_candidates: list[str] = []

        for name, meta in self._metadata.items():
            # Parse last_accessed
            try:
                last_access = datetime.fromisoformat(meta.last_accessed)
                days_since = (now - last_access).days
            except (ValueError, TypeError):
                days_since = 999

            # Check staleness
            if days_since >= self.lifecycle_policy.stale_days:
                stale.append((name, days_since))

            # Check archive threshold
            if days_since >= self.lifecycle_policy.archive_days:
                archive_candidates.append(name)

            # Check emptiness (but protect recently spawned)
            if meta.auto_spawned:
                try:
                    created = datetime.fromisoformat(meta.created_at)
                    days_old = (now - created).days
                except (ValueError, TypeError):
                    days_old = 999

                if days_old < self.lifecycle_policy.protect_recently_spawned_days:
                    continue  # Protected

            if (meta.node_count < self.lifecycle_policy.min_useful_nodes and
                meta.learning_count < self.lifecycle_policy.min_useful_learnings):
                empty.append(name)

        # Find merge candidates
        merge_candidates: list[tuple[str, str, float]] = []
        names = list(self._metadata.keys())
        for i, name1 in enumerate(names):
            for name2 in names[i+1:]:
                related = self.find_related_simulacrums(name1)
                for rel_name, similarity in related:
                    if rel_name == name2 and similarity >= self.lifecycle_policy.merge_similarity_threshold:
                        merge_candidates.append((name1, name2, similarity))

        return {
            "stale": stale,
            "empty": empty,
            "archive_candidates": archive_candidates,
            "merge_candidates": merge_candidates,
            "total_simulacrums": len(self._metadata),
            "total_archived": len(self._archived),
        }

    def archive(self, name: str, reason: str = "manual") -> ArchiveMetadata:
        """Archive a simulacrum to cold storage.

        The simulacrum data is compressed using zstd (Python 3.14+) and moved
        to an archive directory. Falls back to gzip if zstd unavailable.
        It can be restored later if needed.

        Args:
            name: Simulacrum to archive
            reason: Why it's being archived ("stale", "manual", "merged", "empty")

        Returns:
            ArchiveMetadata for the archived simulacrum
        """
        import shutil

        if name not in self._metadata:
            raise KeyError(f"Simulacrum '{name}' not found")

        if name == self._active_name:
            raise ValueError("Cannot archive the active simulacrum. Switch first.")

        meta = self._metadata[name]

        # Create archive directory
        archive_dir = self.base_path / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        archive_name = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Archive with zstd compression (Python 3.14+)
        source_dir = self.base_path / name
        if source_dir.exists():
            import io
            import tarfile

            from compression import zstd

            archive_path = archive_dir / f"{archive_name}.tar.zst"

            # Create tar archive in memory, then compress with zstd
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                tar.add(source_dir, arcname=name)
            tar_data = tar_buffer.getvalue()

            # Compress with zstd (level 3 = good balance of speed/ratio)
            compressed = zstd.compress(tar_data, level=3)
            archive_path.write_bytes(compressed)

        # Create archive metadata
        archive_meta = ArchiveMetadata(
            name=name,
            description=meta.description,
            domains=meta.domains,
            archived_at=datetime.now().isoformat(),
            original_created_at=meta.created_at,
            last_accessed=meta.last_accessed,
            node_count=meta.node_count,
            learning_count=meta.learning_count,
            archive_reason=reason,
            archive_path=str(archive_path),
        )

        # Add to archive registry
        self._archived[name] = archive_meta

        # Remove from active registry
        del self._metadata[name]
        if name in self._stores:
            del self._stores[name]

        # Remove source directory
        if source_dir.exists():
            shutil.rmtree(source_dir)

        self._save_registry()

        return archive_meta

    def restore(self, name: str) -> SimulacrumStore:
        """Restore an archived simulacrum.

        Args:
            name: Name of archived simulacrum to restore

        Returns:
            The restored SimulacrumStore
        """
        import io
        import tarfile

        from compression import zstd

        if name not in self._archived:
            raise KeyError(f"No archived simulacrum '{name}' found")

        archive_meta = self._archived[name]
        archive_path = Path(archive_meta.archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive file not found: {archive_path}")

        # Only zstd format supported
        if not (archive_path.suffix == ".zst" or str(archive_path).endswith(".tar.zst")):
            raise ValueError(
                f"Unsupported archive format: {archive_path}. "
                "Only .tar.zst archives are supported. Manually decompress and re-archive."
            )

        compressed_data = archive_path.read_bytes()
        tar_data = zstd.decompress(compressed_data)

        tar_buffer = io.BytesIO(tar_data)
        with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
            tar.extractall(self.base_path)

        # Restore metadata
        restored_meta = SimulacrumMetadata(
            name=name,
            description=archive_meta.description,
            domains=archive_meta.domains,
            created_at=archive_meta.original_created_at,
            last_accessed=datetime.now().isoformat(),
            access_count=0,  # Reset
            node_count=archive_meta.node_count,
            learning_count=archive_meta.learning_count,
        )

        self._metadata[name] = restored_meta

        # Remove from archive
        del self._archived[name]
        archive_path.unlink(missing_ok=True)

        self._save_registry()

        return self.get(name)

    def list_archived(self) -> list[ArchiveMetadata]:
        """List all archived simulacrums."""
        return sorted(
            self._archived.values(),
            key=lambda a: a.archived_at,
            reverse=True,
        )

    def cleanup(self, dry_run: bool = True) -> dict:
        """Run automatic cleanup based on lifecycle policy.

        Args:
            dry_run: If True, only report what would be done

        Returns:
            Dict with actions taken (or would be taken)
        """
        health = self.check_health()
        actions = {
            "archived": [],
            "merged": [],
            "deleted": [],
            "dry_run": dry_run,
        }

        # Archive stale simulacrums
        if self.lifecycle_policy.auto_archive:
            for name in health["archive_candidates"]:
                if name == self._active_name:
                    continue
                if dry_run:
                    actions["archived"].append(f"{name} (would archive)")
                else:
                    self.archive(name, reason="stale")
                    actions["archived"].append(name)

        # Merge empty auto-spawned simulacrums
        if self.lifecycle_policy.auto_merge_empty:
            for name in health["empty"]:
                if name == self._active_name:
                    continue
                if name not in self._metadata:
                    continue  # Already processed

                meta = self._metadata[name]
                if not meta.auto_spawned:
                    continue  # Only auto-merge auto-spawned ones

                # Find best merge target
                related = self.find_related_simulacrums(name)
                if related:
                    target, _ = related[0]
                    if dry_run:
                        actions["merged"].append(f"{name} → {target} (would merge)")
                    else:
                        self.merge(name, into=target, delete_source=True)
                        actions["merged"].append(f"{name} → {target}")
                else:
                    # No related simulacrum, just delete
                    if dry_run:
                        actions["deleted"].append(f"{name} (would delete)")
                    else:
                        self.delete(name, confirm=True)
                        actions["deleted"].append(name)

        return actions

    def shrink(self, name: str, keep_recent_days: int = 30) -> dict:
        """Shrink a simulacrum by pruning old, low-value content.

        This keeps the simulacrum active but reduces its size by:
        - Removing old, low-confidence nodes
        - Compressing conversation history
        - Pruning weak concept graph edges

        Args:
            name: Simulacrum to shrink
            keep_recent_days: Keep all content from this many days

        Returns:
            Dict with shrink statistics
        """
        store = self.get(name)
        stats = {"nodes_removed": 0, "edges_pruned": 0}

        if store.unified_store:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=keep_recent_days)
            cutoff_str = cutoff.isoformat()

            # Find old, low-value nodes
            to_remove = []
            for node_id, node in store.unified_store._nodes.items():
                # Keep if recent
                if node.created_at > cutoff_str:
                    continue

                # Keep if high-confidence facets
                if node.facets and node.facets.confidence:
                    from sunwell.memory.simulacrum.topology.facets import ConfidenceLevel
                    if node.facets.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH):
                        continue

                # Keep if many incoming edges (important node)
                if len(node.incoming_edges) >= 3:
                    continue

                to_remove.append(node_id)

            # Remove nodes
            for node_id in to_remove:
                store.unified_store.remove_node(node_id)
                stats["nodes_removed"] += 1

            # Prune weak edges
            stats["edges_pruned"] = store.unified_store._concept_graph.prune(
                min_confidence=0.3
            )

            # Save
            store.unified_store.save()

        # Update metadata
        store_stats = store.stats()
        self._metadata[name].node_count = store_stats.get("unified_store", {}).get("total_nodes", 0)
        self._save_registry()

        return stats

    # === Persistence ===

    def save_all(self) -> None:
        """Save all loaded simulacrums."""
        for store in self._stores.values():
            store.save_session()
        self._save_registry()

    def stats(self) -> dict:
        """Get manager-wide statistics."""
        total_nodes = 0
        total_learnings = 0

        for meta in self._metadata.values():
            total_nodes += meta.node_count
            total_learnings += meta.learning_count

        return {
            "simulacrum_count": len(self._metadata),
            "active": self._active_name,
            "total_nodes": total_nodes,
            "total_learnings": total_learnings,
            "simulacrums": [
                {
                    "name": m.name,
                    "domains": list(m.domains),
                    "nodes": m.node_count,
                    "learnings": m.learning_count,
                    "accesses": m.access_count,
                }
                for m in self.list_simulacrums()
            ],
        }
