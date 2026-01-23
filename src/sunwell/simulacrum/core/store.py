"""SimulacrumStore - Portable problem context with tiered storage.

Your simulacrum persists across:
- Model switches (GPT-4 → Claude → Codex)
- Session restarts (days, weeks, months)
- Context limits (smart compression)

Three-tier architecture (RFC-013: Hierarchical Memory):
- HOT: Recent turns in memory (instant access, last 2 micro-chunks)
- WARM: CTF-encoded chunks with summaries and embeddings
- COLD: Macro-chunk summaries only, full content archived

RFC-014: Multi-Topology Memory Extension:
- Spatial: Track WHERE content came from (file, line, section)
- Topological: Model concept relationships (elaborates, contradicts, etc.)
- Structural: Understand document hierarchy
- Faceted: Tag by persona, Diataxis type, verification state

RFC-101: Session Identity System:
- URI-based identification (sunwell:session/project/slug)
- Project-scoped storage prevents collisions
- Global session index for O(1) listing

Key features:
- Progressive compression: 10 → 25 → 100 turn consolidation
- Semantic retrieval via embeddings
- Multi-topology retrieval (RFC-014)
- Token-budgeted context window assembly
"""


import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.turn import Turn, TurnType
from sunwell.simulacrum.hierarchical.chunks import Chunk, ChunkSummary
from sunwell.simulacrum.hierarchical.config import ChunkConfig

if TYPE_CHECKING:
    from typing import Any

    from sunwell.embedding.protocol import EmbeddingProtocol
    from sunwell.simulacrum.hierarchical.chunk_manager import ChunkManager
    from sunwell.simulacrum.hierarchical.summarizer import Summarizer
    from sunwell.simulacrum.memory_tools import MemoryToolHandler
    from sunwell.simulacrum.topology.unified_store import UnifiedMemoryStore


@dataclass
class StorageConfig:
    """Configuration for tiered storage."""

    hot_max_turns: int = 100
    """Max turns to keep in hot storage."""

    warm_max_age_hours: int = 24 * 7  # 1 week
    """Max age before moving to cold storage."""

    cold_compression: bool = True
    """Whether to compress cold storage."""

    auto_cleanup: bool = True
    """Auto-move old turns to cold storage."""

    # RFC-084: Auto-wiring configuration
    auto_topology: bool = True
    """Auto-extract topology relationships every N turns."""

    topology_interval: int = 10
    """Extract topology every N turns (when auto_topology=True)."""

    auto_cold_demotion: bool = True
    """Auto-demote warm chunks to cold tier based on age/count."""

    warm_retention_days: int = 7
    """Days to keep chunks in warm tier before demoting to cold."""

    max_warm_chunks: int = 50
    """Maximum warm chunks to keep (oldest demoted when exceeded)."""

    auto_summarize: bool = True
    """Auto-generate summaries for chunks (uses HeuristicSummarizer if no LLM)."""


@dataclass
class SimulacrumStore:
    """Persistent conversation memory with hierarchical chunking.

    RFC-013: Hierarchical Memory with Progressive Compression
    RFC-014: Multi-Topology Memory Extension

    Manages the lifecycle of conversation data with three tiers:
    - HOT (memory): Last 2 micro-chunks with full content
    - WARM (disk): CTF-encoded chunks with summaries and embeddings
    - COLD (archive): Macro-chunk summaries, full content archived

    Handles:
    - Automatic tier promotion/demotion via ChunkManager
    - Progressive compression (10 → 25 → 100 turns)
    - Semantic retrieval via embeddings
    - Multi-topology retrieval via UnifiedMemoryStore (RFC-014)
    - Token-budgeted context assembly
    - Session persistence/resume
    """

    base_path: Path
    """Base directory for storage."""

    config: StorageConfig = field(default_factory=StorageConfig)
    """Storage configuration."""

    chunk_config: ChunkConfig = field(default_factory=ChunkConfig)
    """Configuration for hierarchical chunking (RFC-013)."""

    # In-memory state
    _hot_dag: ConversationDAG = field(default_factory=ConversationDAG)
    """Hot tier: current conversation DAG."""

    _session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    """Current session identifier."""

    # RFC-101: Project context for session scoping
    _project: str = field(default="default")
    """Project slug for session scoping."""

    _session_uri: str | None = field(default=None, init=False)
    """Full session URI (e.g., sunwell:session/myproject/debug)."""

    # RFC-013: ChunkManager integration
    _chunk_manager: ChunkManager | None = field(default=None, init=False)
    """Hierarchical chunk manager for progressive compression."""

    # RFC-014: Multi-topology memory
    _unified_store: UnifiedMemoryStore | None = field(default=None, init=False)
    """Multi-topology memory store for spatial, topological, structural, faceted retrieval."""

    _memory_handler: MemoryToolHandler | None = field(default=None, init=False)
    """Handler for memory tools (RFC-014)."""

    # Optional injected dependencies
    _summarizer: Summarizer | None = field(default=None, init=False)
    """Summarizer for chunk summaries."""

    _embedder: EmbeddingProtocol | None = field(default=None, init=False)
    """Embedder for semantic retrieval."""

    _intelligence_extractor: Any | None = field(default=None, init=False)
    """RFC-045: Intelligence extractor for project intelligence."""

    # RFC-084: Auto-wiring state
    _topology_extractor: Any | None = field(default=None, init=False)
    """Topology extractor for relationship detection."""

    _topology_extracted_chunks: set[str] = field(default_factory=set)
    """Chunk IDs that have had topology extracted."""

    _focus: Any | None = field(default=None, init=False)
    """Focus mechanism for weighted topic tracking (RFC-084)."""

    def __post_init__(self):
        self.base_path = Path(self.base_path)
        self._ensure_dirs()
        self._init_chunk_manager()
        self._init_unified_store()
        self._init_auto_wiring()  # RFC-084

    def _ensure_dirs(self) -> None:
        """Create storage directories."""
        (self.base_path / "hot").mkdir(parents=True, exist_ok=True)
        (self.base_path / "warm").mkdir(parents=True, exist_ok=True)
        (self.base_path / "cold").mkdir(parents=True, exist_ok=True)
        (self.base_path / "sessions").mkdir(parents=True, exist_ok=True)
        (self.base_path / "chunks").mkdir(parents=True, exist_ok=True)
        (self.base_path / "unified").mkdir(parents=True, exist_ok=True)  # RFC-014

    def _init_chunk_manager(self) -> None:
        """Initialize the hierarchical chunk manager (RFC-013)."""
        from sunwell.simulacrum.hierarchical.chunk_manager import ChunkManager

        self._chunk_manager = ChunkManager(
            base_path=self.base_path / "chunks",
            config=self.chunk_config,
            summarizer=self._summarizer,
            embedder=self._embedder,
        )

    def _init_unified_store(self) -> None:
        """Initialize the multi-topology memory store (RFC-014)."""
        from sunwell.simulacrum.memory_tools import MemoryToolHandler
        from sunwell.simulacrum.topology.unified_store import UnifiedMemoryStore

        unified_path = self.base_path / "unified"

        # Try to load existing store
        if (unified_path / "nodes.json").exists():
            self._unified_store = UnifiedMemoryStore.load(unified_path)
        else:
            self._unified_store = UnifiedMemoryStore(base_path=unified_path)

        # Set embedder if available
        if self._embedder:
            self._unified_store.set_embedder(self._embedder)

        # Initialize memory tool handler
        self._memory_handler = MemoryToolHandler(
            dag=self._hot_dag,
            store=self._unified_store,
            embedder=self._embedder,
        )

    def _init_auto_wiring(self) -> None:
        """Initialize RFC-084 auto-wiring features."""
        from sunwell.simulacrum.context.focus import Focus
        from sunwell.simulacrum.extractors.topology_extractor import TopologyExtractor
        from sunwell.simulacrum.hierarchical.summarizer import HeuristicSummarizer

        # Initialize topology extractor (heuristic by default, no LLM needed)
        if self.config.auto_topology:
            self._topology_extractor = TopologyExtractor()

        # Initialize focus mechanism
        self._focus = Focus()

        # Initialize default summarizer if auto_summarize is enabled and no summarizer set
        if self.config.auto_summarize and self._summarizer is None:
            heuristic_summarizer = HeuristicSummarizer()
            # HeuristicSummarizer is used for chunk manager (duck-typed)
            if self._chunk_manager:
                self._chunk_manager.summarizer = heuristic_summarizer  # type: ignore[assignment]

    def set_summarizer(self, summarizer: Summarizer) -> None:
        """Set the summarizer for chunk processing.

        Args:
            summarizer: Summarizer instance for generating summaries
        """
        self._summarizer = summarizer
        if self._chunk_manager:
            self._chunk_manager.summarizer = summarizer

    def set_embedder(self, embedder: EmbeddingProtocol) -> None:
        """Set the embedder for semantic retrieval.

        Args:
            embedder: Embedder instance for generating embeddings
        """
        self._embedder = embedder
        if self._chunk_manager:
            self._chunk_manager.embedder = embedder
        if self._unified_store:
            self._unified_store.set_embedder(embedder)
        if self._memory_handler:
            self._memory_handler.embedder = embedder

    async def _on_chunk_demotion(self, chunk: Chunk, new_tier: str) -> None:
        """Called when a chunk is demoted to warm/cold tier (RFC-045).

        Args:
            chunk: The chunk being demoted
            new_tier: The new tier ('warm' or 'cold')
        """
        if self._intelligence_extractor and new_tier in ("warm", "cold"):
            try:
                await self._intelligence_extractor.on_chunk_demotion(chunk)
            except Exception as e:
                # Log but don't fail on intelligence extraction errors
                # These are non-critical and shouldn't block demotion
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Intelligence extraction failed for chunk {chunk.id}: {e}")

    def set_intelligence_extractor(self, extractor: Any) -> None:
        """Set the intelligence extractor for RFC-045.

        Args:
            extractor: IntelligenceExtractor instance for extracting project intelligence
        """
        self._intelligence_extractor = extractor
        # Set callback on chunk manager
        if self._chunk_manager:
            self._chunk_manager.set_demotion_callback(self._on_chunk_demotion)

    @property
    def unified_store(self) -> UnifiedMemoryStore | None:
        """Get the multi-topology memory store (RFC-014)."""
        return self._unified_store

    @property
    def memory_handler(self) -> MemoryToolHandler | None:
        """Get the memory tool handler (RFC-014)."""
        return self._memory_handler

    @property
    def hot_path(self) -> Path:
        return self.base_path / "hot" / f"{self._session_id}.json"

    @property
    def warm_path(self) -> Path:
        return self.base_path / "warm"

    @property
    def cold_path(self) -> Path:
        return self.base_path / "cold"

    # === Session Management ===

    def new_session(
        self,
        name: str | None = None,
        project: str | None = None,
    ) -> str:
        """Start a new conversation session.

        RFC-101: Sessions are now project-scoped to prevent collisions.

        Args:
            name: Optional session name (defaults to timestamp)
            project: Optional project slug (defaults to current project)

        Returns:
            Session ID (slug)
        """
        self._session_id = name or datetime.now().strftime("%Y%m%d_%H%M%S")
        if project:
            self._project = project
        self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"
        self._hot_dag = ConversationDAG()
        return self._session_id

    @property
    def session_uri(self) -> str:
        """Get the full session URI (RFC-101)."""
        if not self._session_uri:
            self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"
        return self._session_uri

    @property
    def project(self) -> str:
        """Get the current project slug."""
        return self._project

    def set_project(self, project: str) -> None:
        """Set the project context for session scoping.

        Args:
            project: Project slug
        """
        self._project = project
        # Update URI if session exists
        if self._session_id:
            self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"

    def list_sessions(self, project: str | None = None) -> list[dict]:
        """List all saved sessions.

        RFC-101: Can filter by project.

        Args:
            project: Optional project filter (None = all projects)

        Returns:
            List of session metadata dicts
        """
        sessions = []

        # RFC-101: Check project-scoped sessions first
        projects_dir = self.base_path / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    if project and project_dir.name != project:
                        continue
                    for path in project_dir.glob("*.json"):
                        if path.stem.endswith("_dag"):
                            continue
                        try:
                            with open(path) as f:
                                meta = json.load(f)
                            sessions.append({
                                "id": path.stem,
                                "uri": f"sunwell:session/{project_dir.name}/{path.stem}",
                                "project": project_dir.name,
                                "name": meta.get("name", path.stem),
                                "created": meta.get("created"),
                                "turns": meta.get("turn_count", 0),
                                "path": str(path),
                            })
                        except (json.JSONDecodeError, OSError):
                            continue

        # Legacy: Check flat sessions directory
        legacy_sessions_dir = self.base_path / "sessions"
        if legacy_sessions_dir.exists() and not project:
            for path in legacy_sessions_dir.glob("*.json"):
                if path.stem.endswith("_dag"):
                    continue
                try:
                    with open(path) as f:
                        meta = json.load(f)
                    sessions.append({
                        "id": path.stem,
                        "uri": f"sunwell:session/default/{path.stem}",
                        "project": "default",
                        "name": meta.get("name", path.stem),
                        "created": meta.get("created"),
                        "turns": meta.get("turn_count", 0),
                        "path": str(path),
                    })
                except (json.JSONDecodeError, OSError):
                    continue

        return sorted(sessions, key=lambda s: s.get("created") or "", reverse=True)

    def save_session(self, name: str | None = None) -> Path:
        """Save current session to disk.

        RFC-101: Saves to project-scoped directory.
        """
        session_name = name or self._session_id

        # RFC-101: Use project-scoped storage
        session_dir = self.base_path / "projects" / self._project
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save DAG
        dag_path = session_dir / f"{session_name}_dag.json"
        self._hot_dag.save(dag_path)

        # Save unified store (RFC-014)
        if self._unified_store:
            self._unified_store.save()

        # Save metadata with identity info (RFC-101)
        meta_path = session_dir / f"{session_name}.json"
        meta = {
            "name": session_name,
            "uri": f"sunwell:session/{self._project}/{session_name}",
            "project": self._project,
            "created": datetime.now().isoformat(),
            "turn_count": len(self._hot_dag.turns),
            "stats": self._hot_dag.stats,
            "unified_store_nodes": len(self._unified_store._nodes) if self._unified_store else 0,
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        # Also save to legacy location for backwards compat
        legacy_dir = self.base_path / "sessions"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_dag_path = legacy_dir / f"{session_name}_dag.json"
        self._hot_dag.save(legacy_dag_path)
        legacy_meta_path = legacy_dir / f"{session_name}.json"
        with open(legacy_meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        return meta_path

    def load_session(
        self,
        session_id: str,
        project: str | None = None,
    ) -> ConversationDAG:
        """Load a saved session.

        RFC-101: Supports loading by URI or slug with project context.

        Args:
            session_id: Session slug or full URI
            project: Optional project context (for slug resolution)

        Returns:
            Loaded ConversationDAG

        Raises:
            FileNotFoundError: If session not found
        """
        # Parse URI if provided
        if session_id.startswith("sunwell:session/"):
            parts = session_id[17:].split("/", 1)  # Remove "sunwell:session/"
            if len(parts) == 2:
                project = parts[0]
                session_id = parts[1]

        # Set project context
        if project:
            self._project = project

        # Try project-scoped path first (RFC-101)
        dag_path = self.base_path / "projects" / self._project / f"{session_id}_dag.json"
        if not dag_path.exists():
            # Fall back to legacy path
            dag_path = self.base_path / "sessions" / f"{session_id}_dag.json"

        if not dag_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        self._hot_dag = ConversationDAG.load(dag_path)
        self._session_id = session_id
        self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"

        # Apply tiered compression if session has many turns
        if self.config.auto_cleanup:
            self._maybe_demote_to_warm()

        return self._hot_dag

    # === Turn Operations ===

    def add_turn(self, turn: Turn) -> str:
        """Add a turn to hot storage and chunk manager.

        Args:
            turn: Turn to add

        Returns:
            The turn's content-addressable ID
        """
        turn_id = self._hot_dag.add_turn(turn)

        # Update token count if not set
        if turn.token_count == 0:
            turn = self._estimate_token_count(turn)

        # Feed to chunk manager for hierarchical processing (RFC-013)
        if self._chunk_manager:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # In async context, create task
                loop.create_task(self._chunk_manager.add_turns([turn]))
            except RuntimeError:
                # No running loop, run synchronously
                asyncio.run(self._chunk_manager.add_turns([turn]))

        # Auto-flush to disk periodically
        if len(self._hot_dag.turns) % 10 == 0:
            self._flush_hot()

        # Check if we need to move old turns to warm
        if self.config.auto_cleanup:
            self._maybe_demote_to_warm()

        return turn_id

    async def add_turn_async(self, turn: Turn) -> str:
        """Add a turn asynchronously (preferred in async contexts).

        RFC-084: Auto-wires topology extraction, cold demotion, and focus updates.

        Args:
            turn: Turn to add

        Returns:
            The turn's content-addressable ID
        """
        turn_id = self._hot_dag.add_turn(turn)

        # Update token count if not set
        if turn.token_count == 0:
            turn = self._estimate_token_count(turn)

        # RFC-084: Update focus based on content
        if self._focus:
            self._focus.update_from_query(turn.content)

        # Feed to chunk manager for hierarchical processing (RFC-013)
        if self._chunk_manager:
            await self._chunk_manager.add_turns([turn])

        # Auto-flush to disk periodically
        if len(self._hot_dag.turns) % 10 == 0:
            self._flush_hot()

        # Check if we need to move old turns to warm
        if self.config.auto_cleanup:
            self._maybe_demote_to_warm()

        # RFC-084: Auto-extract topology every N turns
        turn_count = len(self._hot_dag.turns)
        if self.config.auto_topology and turn_count % self.config.topology_interval == 0:
            await self._extract_topology_batch()

        # RFC-084: Auto-demote warm chunks to cold
        if self.config.auto_cold_demotion:
            self._maybe_demote_warm_to_cold()

        return turn_id

    def _estimate_token_count(self, turn: Turn) -> Turn:
        """Estimate token count for a turn.

        Args:
            turn: Turn to estimate

        Returns:
            Turn with token_count populated
        """
        # Rough estimate: ~1.3 tokens per word
        word_count = len(turn.content.split())
        estimated = max(1, int(word_count * 1.3))

        return Turn(
            content=turn.content,
            turn_type=turn.turn_type,
            timestamp=turn.timestamp,
            parent_ids=turn.parent_ids,
            source=turn.source,
            token_count=estimated,
            model=turn.model,
            confidence=turn.confidence,
            tags=turn.tags,
        )

    def add_user(self, content: str, **kwargs) -> str:
        """Convenience: add user message.

        Creates a Turn and routes through add_turn() for ChunkManager integration.
        """
        from sunwell.simulacrum.core.turn import Turn, TurnType

        turn = Turn(
            content=content,
            turn_type=TurnType.USER,
            **kwargs,
        )
        return self.add_turn(turn)

    def add_assistant(self, content: str, **kwargs) -> str:
        """Convenience: add assistant message.

        Creates a Turn and routes through add_turn() for ChunkManager integration.
        """
        from sunwell.simulacrum.core.turn import Turn, TurnType

        turn = Turn(
            content=content,
            turn_type=TurnType.ASSISTANT,
            **kwargs,
        )
        return self.add_turn(turn)

    def add_learning(
        self,
        fact: str,
        category: str = "fact",
        confidence: float = 1.0,
        source_turns: tuple[str, ...] | None = None,
    ) -> str:
        """Add a learning to the conversation.

        Args:
            fact: The learning/insight text
            category: Category (fact, preference, behavior, etc.)
            confidence: Confidence score (0-1)
            source_turns: Optional tuple of turn IDs this was derived from

        Returns:
            The learning's ID
        """
        from sunwell.simulacrum.core.turn import Learning

        learning = Learning(
            fact=fact,
            category=category,
            confidence=confidence,
            source_turns=source_turns or (),
        )
        return self._hot_dag.add_learning(learning)

    def get_dag(self) -> ConversationDAG:
        """Get the current conversation DAG."""
        return self._hot_dag

    # === Context Retrieval (RFC-013) ===

    def get_context_for_prompt(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get relevant context for a prompt, within token budget.

        Uses hierarchical chunking and semantic search to build
        an optimal context window.

        Args:
            query: The query/prompt to find relevant context for
            max_tokens: Maximum tokens to include in context

        Returns:
            Formatted context string for inclusion in prompts
        """
        if not self._chunk_manager:
            # Fall back to simple retrieval
            return self._simple_context(query, max_tokens)

        context_items = self._chunk_manager.get_context_window(
            max_tokens=max_tokens,
            query=query,
        )

        # Format for prompt
        parts: list[str] = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                # Full turns from hot tier
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                # Summary from cold tier
                parts.append(f"[Earlier context: {item.summary}]")
            elif hasattr(item, 'summary') and item.summary:
                parts.append(f"[Context: {item.summary}]")

        return "\n\n".join(parts)

    async def get_context_for_prompt_async(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get relevant context for a prompt with semantic retrieval.

        Async version that uses embedding-based semantic search to find
        relevant chunks from warm storage, not just recent turns.

        Args:
            query: The query/prompt to find relevant context for
            max_tokens: Maximum tokens to include in context

        Returns:
            Formatted context string for inclusion in prompts
        """
        if not self._chunk_manager:
            return self._simple_context(query, max_tokens)

        # Use async method with semantic retrieval
        context_items = await self._chunk_manager.get_context_window_async(
            max_tokens=max_tokens,
            query=query,
            semantic_limit=5,
        )

        # Format for prompt
        parts: list[str] = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                # Full turns from hot or expanded warm tier
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                # Summary from cold tier
                parts.append(f"[Earlier context: {item.summary}]")
            elif hasattr(item, "summary") and item.summary:
                parts.append(f"[Context: {item.summary}]")

        return "\n\n".join(parts)

    def _simple_context(self, query: str, max_tokens: int) -> str:
        """Simple context retrieval without ChunkManager.

        Falls back to recent turns from DAG.
        """
        recent = self._hot_dag.get_recent_turns(20)

        parts = []
        token_count = 0

        for turn in reversed(recent):
            turn_tokens = turn.token_count or len(turn.content.split())
            if token_count + turn_tokens > max_tokens:
                break
            parts.append(f"{turn.turn_type.value}: {turn.content}")
            token_count += turn_tokens

        parts.reverse()
        return "\n\n".join(parts)

    def get_relevant_chunks(
        self,
        query: str,
        limit: int = 5,
    ) -> list[Chunk]:
        """Get chunks relevant to a query using semantic search.

        Args:
            query: Search query
            limit: Maximum chunks to return

        Returns:
            List of relevant chunks
        """
        if not self._chunk_manager:
            return []
        return self._chunk_manager.get_relevant_chunks(query, limit=limit)

    def assemble_messages(
        self,
        query: str,
        system_prompt: str = "",
        max_tokens: int = 4000,
    ) -> tuple[list[dict], dict]:
        """Assemble messages for LLM using hierarchical context.

        Uses progressive compression (hot/warm/cold tiers) to build
        optimal context within token budget.

        Args:
            query: Current user query
            system_prompt: System prompt to include
            max_tokens: Token budget for context

        Returns:
            Tuple of (messages, stats) where:
            - messages: List of message dicts for LLM
            - stats: Dict with retrieval statistics
        """
        messages: list[dict] = []
        stats = {
            "retrieved_chunks": 0,
            "hot_turns": 0,
            "warm_summaries": 0,
            "cold_summaries": 0,
            "compression_applied": False,
        }

        # 1. System prompt with learnings
        system_parts = [system_prompt] if system_prompt else []

        # Add learnings from DAG
        learnings = self._hot_dag.get_active_learnings()
        if learnings:
            system_parts.append("\n\n## Key Context (from conversation history)")
            for learning in learnings:
                system_parts.append(f"- [{learning.category}] {learning.fact}")

        if system_parts:
            messages.append({
                "role": "system",
                "content": "\n".join(system_parts),
            })

        # 2. Get context from hierarchical chunks
        if self._chunk_manager:
            context_items = self._chunk_manager.get_context_window(
                max_tokens=max_tokens,
                query=query,
            )

            stats["retrieved_chunks"] = len(context_items)

            for item in context_items:
                if isinstance(item, Chunk) and item.turns:
                    # HOT tier: full turns as messages
                    stats["hot_turns"] += len(item.turns)
                    for turn in item.turns:
                        messages.append(turn.to_message())
                elif isinstance(item, ChunkSummary):
                    # COLD tier: summary only
                    stats["cold_summaries"] += 1
                    stats["compression_applied"] = True
                    messages.append({
                        "role": "assistant",
                        "content": f"[Earlier context: {item.summary}]",
                    })
                elif hasattr(item, 'summary') and item.summary:
                    # WARM tier: has summary
                    stats["warm_summaries"] += 1
                    messages.append({
                        "role": "assistant",
                        "content": f"[Context: {item.summary}]",
                    })
        else:
            # Fallback: recent turns from DAG
            recent = self._hot_dag.get_recent_turns(10)
            stats["hot_turns"] = len(recent)
            for turn in recent:
                messages.append(turn.to_message())

        return messages, stats

    # === RFC-084: Auto-Wiring Methods ===

    async def _extract_topology_batch(self) -> None:
        """Extract relationships from recent chunks (RFC-084 auto-topology)."""
        if not self._chunk_manager or not self._topology_extractor:
            return

        recent_chunks = self._chunk_manager._get_recent_chunks(limit=5)
        if len(recent_chunks) < 2:
            return

        for chunk in recent_chunks:
            if chunk.id in self._topology_extracted_chunks:
                continue

            # Get text for this chunk
            source_text = chunk.summary or self._turns_to_text(chunk)

            # Get candidate chunks (excluding self)
            candidates = [c for c in recent_chunks if c.id != chunk.id]
            candidate_ids = [c.id for c in candidates]
            candidate_texts = [c.summary or self._turns_to_text(c) for c in candidates]

            if not candidate_ids:
                continue

            # Extract relationships using heuristics
            edges = self._topology_extractor.extract_heuristic_relationships(
                source_id=chunk.id,
                source_text=source_text,
                candidate_ids=candidate_ids,
                candidate_texts=candidate_texts,
            )

            # Add edges to the concept graph
            if self._unified_store and edges:
                for edge in edges:
                    self._unified_store._concept_graph.add_edge(edge)

            self._topology_extracted_chunks.add(chunk.id)

        # Persist the graph
        if self._unified_store:
            self._unified_store.save()

    def _turns_to_text(self, chunk: Any) -> str:
        """Convert chunk turns to text for topology extraction."""
        if chunk.turns:
            return "\n".join(f"{t.turn_type.value}: {t.content[:500]}" for t in chunk.turns)
        return chunk.summary or ""

    def _maybe_demote_warm_to_cold(self) -> None:
        """Demote old warm chunks to cold tier (RFC-084 auto-cold-demotion)."""
        if not self._chunk_manager:
            return

        import time

        warm_chunks = self._chunk_manager._get_warm_chunks()
        if not warm_chunks:
            return

        now = time.time()

        # By age: older than config threshold
        for chunk in warm_chunks:
            if not chunk.timestamp_end:
                continue
            try:
                # Parse ISO timestamp
                from datetime import datetime
                chunk_time = datetime.fromisoformat(chunk.timestamp_end).timestamp()
                age_days = (now - chunk_time) / 86400
                if age_days > self.config.warm_retention_days:
                    self._chunk_manager.demote_to_cold(chunk.id)
            except (ValueError, OSError):
                continue

        # By count: keep only max_warm_chunks
        warm_chunks = self._chunk_manager._get_warm_chunks()  # Refresh after age-based demotion
        warm_chunks.sort(key=lambda c: c.turn_range[0])  # Sort by turn range (oldest first)

        while len(warm_chunks) > self.config.max_warm_chunks:
            oldest = warm_chunks.pop(0)
            self._chunk_manager.demote_to_cold(oldest.id)

    @property
    def focus(self) -> Any:
        """Get the focus mechanism (RFC-084)."""
        return self._focus

    def get_context_for_prompt_weighted(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get context with focus-weighted retrieval (RFC-084).

        Uses the focus mechanism to weight chunk relevance based on
        topic tracking across the conversation.
        """
        if not self._chunk_manager:
            return self._simple_context(query, max_tokens)

        # Update focus from query
        if self._focus:
            self._focus.update_from_query(query)

        # Get context items
        context_items = self._chunk_manager.get_context_window(
            max_tokens=max_tokens,
            query=query,
        )

        # If we have focus, apply weighting
        if self._focus and self._focus.topics:
            from sunwell.simulacrum.context.focus import FocusFilter
            focus_filter = FocusFilter(self._focus)

            # Score and reorder by focus relevance
            scored_items: list[tuple[float, Any]] = []
            for item in context_items:
                if hasattr(item, "turns") and item.turns:
                    # Score based on turns content
                    turns_scored = focus_filter.filter_turns(list(item.turns), min_relevance=0.0)
                    if turns_scored:
                        avg_score = sum(s for _, s in turns_scored) / len(turns_scored)
                    else:
                        avg_score = 0.5
                    scored_items.append((avg_score, item))
                elif hasattr(item, "summary") and item.summary:
                    # Score based on summary
                    tags = focus_filter._extract_tags(item.summary)
                    score = self._focus.matches(tags)
                    scored_items.append((score, item))
                else:
                    scored_items.append((0.5, item))

            # Sort by score descending
            scored_items.sort(key=lambda x: x[0], reverse=True)
            context_items = [item for _, item in scored_items]

        # Format for prompt
        from sunwell.simulacrum.hierarchical.chunks import Chunk, ChunkSummary
        parts: list[str] = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                parts.append(f"[Earlier context: {item.summary}]")
            elif hasattr(item, "summary") and item.summary:
                parts.append(f"[Context: {item.summary}]")

        return "\n\n".join(parts)

    # === Tier Management ===

    def _flush_hot(self) -> None:
        """Flush hot tier to disk."""
        self._hot_dag.save(self.hot_path)

    def _maybe_demote_to_warm(self) -> None:
        """Move old turns from hot to warm storage."""
        if len(self._hot_dag.turns) <= self.config.hot_max_turns:
            return

        # Find oldest turns to demote
        turns_by_time = sorted(
            self._hot_dag.turns.values(),
            key=lambda t: t.timestamp,
        )

        to_demote = turns_by_time[:len(turns_by_time) - self.config.hot_max_turns]

        # Save to warm storage
        for turn in to_demote:
            self._save_to_warm(turn)
            # Don't remove from DAG - keep structure, just mark as demoted
            self._hot_dag.compressed.add(turn.id)

    def _save_to_warm(self, turn: Turn) -> None:
        """Save a turn to warm storage."""
        # Use date-based sharding for warm storage
        date_str = turn.timestamp[:10]  # YYYY-MM-DD
        shard_path = self.warm_path / f"{date_str}.jsonl"

        with open(shard_path, "a") as f:
            data = {
                "id": turn.id,
                "content": turn.content,
                "turn_type": turn.turn_type.value,
                "timestamp": turn.timestamp,
                "parent_ids": list(turn.parent_ids),
            }
            f.write(json.dumps(data) + "\n")

    def move_to_cold(self, older_than_hours: int | None = None) -> int:
        """Archive old warm storage to cold (compressed)."""
        hours = older_than_hours or self.config.warm_max_age_hours
        cutoff = datetime.now() - timedelta(hours=hours)
        moved = 0

        for shard_file in self.warm_path.glob("*.jsonl"):
            # Parse date from filename
            try:
                file_date = datetime.strptime(shard_file.stem, "%Y-%m-%d")
            except ValueError:
                continue

            if file_date < cutoff:
                # Move to cold storage
                cold_dest = self.cold_path / shard_file.name

                if self.config.cold_compression:
                    # Compress with zstd if available
                    try:
                        import zstd
                        with open(shard_file, "rb") as src:
                            compressed = zstd.compress(src.read())
                        with open(cold_dest.with_suffix(".jsonl.zst"), "wb") as dst:
                            dst.write(compressed)
                    except ImportError:
                          # Fall back to gzip
                          import gzip
                          with (
                              open(shard_file, "rb") as src,
                              gzip.open(cold_dest.with_suffix(".jsonl.gz"), "wb") as dst,
                          ):
                              dst.write(src.read())
                else:
                    shutil.move(shard_file, cold_dest)

                # Remove original
                shard_file.unlink(missing_ok=True)
                moved += 1

        return moved

    def retrieve_from_warm(self, turn_id: str) -> Turn | None:
        """Retrieve a specific turn from warm storage."""
        for shard_file in self.warm_path.glob("*.jsonl"):
            with open(shard_file) as f:
                for line in f:
                    data = json.loads(line)
                    if data["id"] == turn_id:
                        return Turn(
                            content=data["content"],
                            turn_type=TurnType(data["turn_type"]),
                            timestamp=data["timestamp"],
                            parent_ids=tuple(data.get("parent_ids", [])),
                        )
        return None

    def search_warm(self, query: str, limit: int = 10) -> list[Turn]:
        """Simple text search over warm storage."""
        query_lower = query.lower()
        matches = []

        for shard_file in self.warm_path.glob("*.jsonl"):
            with open(shard_file) as f:
                for line in f:
                    data = json.loads(line)
                    if query_lower in data["content"].lower():
                        turn = Turn(
                            content=data["content"],
                            turn_type=TurnType(data["turn_type"]),
                            timestamp=data["timestamp"],
                            parent_ids=tuple(data.get("parent_ids", [])),
                        )
                        matches.append(turn)
                        if len(matches) >= limit:
                            return matches

        return matches

    # === RFC-014: Document/Code Ingestion ===

    async def ingest_document(
        self,
        file_path: str,
        content: str,
        *,
        extract_facets: bool = True,
        extract_topology: bool = True,
    ) -> int:
        """Ingest a document into multi-topology memory.

        This is the main entry point for adding external knowledge
        to the memory system. Documents are:
        1. Chunked structurally (respecting headings/code blocks)
        2. Annotated with spatial context (file, section path)
        3. Tagged with facets (Diataxis type, persona, domain)
        4. Optionally linked via concept relationships

        Args:
            file_path: Path to the document
            content: Document content
            extract_facets: Auto-detect Diataxis type, personas, etc.
            extract_topology: Auto-extract concept relationships

        Returns:
            Number of memory nodes created
        """
        if not self._unified_store:
            return 0

        from sunwell.simulacrum.extractors.facet_extractor import FacetExtractor
        from sunwell.simulacrum.extractors.structural_chunker import StructuralChunker
        from sunwell.simulacrum.extractors.topology_extractor import TopologyExtractor
        from sunwell.simulacrum.topology.memory_node import MemoryNode

        chunker = StructuralChunker()
        facet_extractor = FacetExtractor() if extract_facets else None

        # Chunk the document structurally
        chunks = chunker.chunk_document(file_path, content)

        nodes: list[MemoryNode] = []
        for chunk, spatial, section in chunks:
            # Extract facets if enabled
            facets = None
            if facet_extractor and section:
                facets = facet_extractor.extract_from_text(
                    chunk.summary or chunk.turns[0].content if chunk.turns else "",
                    section=section,
                    source_type="docs",
                )

            # Create memory node
            node = MemoryNode(
                id=chunk.id,
                content=chunk.summary or (chunk.turns[0].content if chunk.turns else ""),
                chunk=chunk,
                spatial=spatial,
                section=section,
                facets=facets,
            )
            nodes.append(node)
            self._unified_store.add_node(node)

        # Extract topology relationships if enabled
        if extract_topology and len(nodes) > 1:
            topology_extractor = TopologyExtractor()
            for i, node in enumerate(nodes):
                candidates = nodes[:i] + nodes[i+1:]  # All other nodes
                if len(candidates) > 10:
                    candidates = candidates[:10]  # Limit for performance

                edges = topology_extractor.extract_heuristic_relationships(
                    source_id=node.id,
                    source_text=node.content,
                    candidate_ids=[c.id for c in candidates],
                    candidate_texts=[c.content for c in candidates],
                )

                for edge in edges:
                    self._unified_store._concept_graph.add_edge(edge)

        # Save the store
        self._unified_store.save()

        return len(nodes)

    async def ingest_codebase(
        self,
        root_path: str,
        file_patterns: list[str] | None = None,
    ) -> int:
        """Ingest a codebase into multi-topology memory.

        Args:
            root_path: Root directory of the codebase
            file_patterns: Glob patterns for files to include (e.g., ["*.py", "*.md"])

        Returns:
            Number of memory nodes created
        """
        from pathlib import Path

        if not self._unified_store:
            return 0

        patterns = file_patterns or ["*.py", "*.md", "*.rst", "*.yaml", "*.json"]
        root = Path(root_path)
        total_nodes = 0

        for pattern in patterns:
            for file_path in root.rglob(pattern):
                if file_path.is_file():
                    try:
                        content = file_path.read_text()
                        nodes = await self.ingest_document(
                            str(file_path.relative_to(root)),
                            content,
                        )
                        total_nodes += nodes
                    except (UnicodeDecodeError, OSError):
                        continue  # Skip binary/unreadable files

        return total_nodes

    # === Stats & Cleanup ===

    def stats(self) -> dict:
        """Storage statistics including chunk manager (RFC-013) and unified store (RFC-014)."""
        hot_turns = len(self._hot_dag.turns)

        warm_files = list(self.warm_path.glob("*.jsonl"))
        warm_size = sum(f.stat().st_size for f in warm_files)

        cold_files = list(self.cold_path.glob("*"))
        cold_size = sum(f.stat().st_size for f in cold_files)

        stats_dict = {
            "session_id": self._session_id,
            "hot_turns": hot_turns,
            "warm_files": len(warm_files),
            "warm_size_mb": warm_size / 1024 / 1024,
            "cold_files": len(cold_files),
            "cold_size_mb": cold_size / 1024 / 1024,
            "dag_stats": self._hot_dag.stats,
        }

        # Add chunk manager stats (RFC-013)
        if self._chunk_manager:
            stats_dict["chunk_stats"] = self._chunk_manager.stats

        # Add unified store stats (RFC-014)
        if self._unified_store:
            stats_dict["unified_store"] = {
                "total_nodes": len(self._unified_store._nodes),
                "total_edges": sum(
                    len(edges) for edges in self._unified_store._concept_graph._edges.values()
                ),
                "facet_index_size": sum(
                    len(s) for s in self._unified_store._facet_index._by_diataxis.values()
                ),
            }

        return stats_dict

    def cleanup_dead_ends(self) -> int:
        """Remove dead end turns from warm/cold storage."""
        # Get all dead end IDs
        dead_end_ids = self._hot_dag.dead_ends
        if not dead_end_ids:
            return 0

        removed = 0

        # Clean warm storage
        for shard_file in self.warm_path.glob("*.jsonl"):
            lines_to_keep = []
            with open(shard_file) as f:
                for line in f:
                    data = json.loads(line)
                    if data["id"] not in dead_end_ids:
                        lines_to_keep.append(line)
                    else:
                        removed += 1

            with open(shard_file, "w") as f:
                f.writelines(lines_to_keep)

        return removed
