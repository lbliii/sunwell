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

RFC-122: Compound Learning
- retrieve_for_planning() for knowledge retrieval during planning
- PlanningContext for categorized knowledge injection
- Integration with Convergence for HarmonicPlanner

Key features:
- Progressive compression: 10 → 25 → 100 turn consolidation
- Semantic retrieval via embeddings
- Multi-topology retrieval (RFC-014)
- Token-budgeted context window assembly
"""


from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.foundation.types.memory import MemoryRetrievalResult
from sunwell.memory.simulacrum.core.auto_wiring import (
    extract_topology_batch,
    maybe_demote_warm_to_cold,
)
from sunwell.memory.simulacrum.core.config import StorageConfig
from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.memory.simulacrum.core.episodes import EpisodeManager
from sunwell.memory.simulacrum.core.ingestion import ingest_codebase, ingest_document
from sunwell.memory.simulacrum.core.planning_context import PlanningContext
from sunwell.memory.simulacrum.core.retrieval import (
    ContextAssembler,
    PlanningRetriever,
    SemanticRetriever,
)
from sunwell.memory.simulacrum.core.session_manager import SessionManager
from sunwell.memory.simulacrum.core.tier_manager import TierManager
from sunwell.memory.simulacrum.core.turn import Learning, Turn, TurnType
from sunwell.memory.simulacrum.core.turn_utils import estimate_token_count
from sunwell.memory.simulacrum.hierarchical.chunks import Chunk
from sunwell.memory.simulacrum.hierarchical.config import ChunkConfig

if TYPE_CHECKING:
    from sunwell.knowledge.codebase.extractor import IntelligenceExtractor
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.context.focus import Focus
    from sunwell.memory.simulacrum.extractors.topology_extractor import TopologyExtractor
    from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager
    from sunwell.memory.simulacrum.hierarchical.summarizer import Summarizer
    from sunwell.memory.simulacrum.memory_tools import MemoryToolHandler
    from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore

# RFC-022 Enhancement: Episode tracking
from sunwell.foundation.types.memory import Episode

# =============================================================================
# SimulacrumStore
# =============================================================================


@dataclass(slots=True)
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

    _intelligence_extractor: IntelligenceExtractor | None = field(default=None, init=False)
    """RFC-045: Intelligence extractor for project intelligence."""

    # RFC-084: Auto-wiring state
    _topology_extractor: TopologyExtractor | None = field(default=None, init=False)
    """Topology extractor for relationship detection."""

    _topology_extracted_chunks: set[str] = field(default_factory=set)
    """Chunk IDs that have had topology extracted."""

    _focus: Focus | None = field(default=None, init=False)
    """Focus mechanism for weighted topic tracking (RFC-084)."""

    # Modular managers
    _episode_manager: EpisodeManager | None = field(default=None, init=False)
    """Episode manager for tracking past sessions."""
    _session_manager: SessionManager | None = field(default=None, init=False)
    """Session manager for session lifecycle."""
    _tier_manager: TierManager | None = field(default=None, init=False)
    """Tier manager for hot/warm/cold storage."""

    # Retrieval modules (extracted for modularity)
    _planning_retriever: PlanningRetriever | None = field(default=None, init=False)
    """Planning context retriever (RFC-122)."""
    _semantic_retriever: SemanticRetriever | None = field(default=None, init=False)
    """Semantic retriever for parallel memory access."""
    _context_assembler: ContextAssembler | None = field(default=None, init=False)
    """Context assembler for prompt building."""

    def __post_init__(self) -> None:
        self.base_path = Path(self.base_path)
        self._ensure_dirs()
        self._init_chunk_manager()
        self._init_unified_store()
        self._init_auto_wiring()  # RFC-084
        self._init_managers()  # Initialize modular managers

    def _ensure_dirs(self) -> None:
        """Create storage directories."""
        (self.base_path / "hot").mkdir(parents=True, exist_ok=True)
        (self.base_path / "warm").mkdir(parents=True, exist_ok=True)
        (self.base_path / "cold").mkdir(parents=True, exist_ok=True)
        (self.base_path / "sessions").mkdir(parents=True, exist_ok=True)
        (self.base_path / "chunks").mkdir(parents=True, exist_ok=True)
        (self.base_path / "unified").mkdir(parents=True, exist_ok=True)  # RFC-014
        (self.base_path / "episodes").mkdir(parents=True, exist_ok=True)  # RFC-022

    def _init_managers(self) -> None:
        """Initialize modular managers."""
        self._episode_manager = EpisodeManager(self.base_path)
        self._session_manager = SessionManager(
            self.base_path,
            lambda: self._hot_dag,
            lambda dag: setattr(self, "_hot_dag", dag),
            self._unified_store,
        )
        self._tier_manager = TierManager(
            self.base_path,
            self.config,
            self._hot_dag,
        )
        # Keep tier_manager's hot_dag in sync
        self._tier_manager.update_hot_dag = lambda dag: setattr(self._tier_manager, "_hot_dag", dag)

        # Initialize retrieval modules
        self._init_retrievers()

    def _init_retrievers(self) -> None:
        """Initialize retrieval modules."""
        episodes = self._episode_manager.get_episodes(limit=100) if self._episode_manager else []

        self._planning_retriever = PlanningRetriever(
            dag=self._hot_dag,
            embedder=self._embedder,
            episodes=episodes,
        )

        self._semantic_retriever = SemanticRetriever(
            dag=self._hot_dag,
            embedder=self._embedder,
            episodes=episodes,
            chunk_manager=self._chunk_manager,
        )

        self._context_assembler = ContextAssembler(
            dag=self._hot_dag,
            chunk_manager=self._chunk_manager,
            focus=self._focus,
        )

    def _init_chunk_manager(self) -> None:
        """Initialize the hierarchical chunk manager (RFC-013)."""
        from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager

        self._chunk_manager = ChunkManager(
            base_path=self.base_path / "chunks",
            config=self.chunk_config,
            summarizer=self._summarizer,
            embedder=self._embedder,
        )

    def _init_unified_store(self) -> None:
        """Initialize the multi-topology memory store (RFC-014)."""
        from sunwell.memory.simulacrum.memory_tools import MemoryToolHandler
        from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore

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
        from sunwell.memory.simulacrum.context.focus import Focus
        from sunwell.memory.simulacrum.extractors.topology_extractor import TopologyExtractor
        from sunwell.memory.simulacrum.hierarchical.summarizer import HeuristicSummarizer

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
        # Update retrievers with new embedder
        if self._planning_retriever:
            self._planning_retriever._embedder = embedder
        if self._semantic_retriever:
            self._semantic_retriever._embedder = embedder

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

    def set_intelligence_extractor(self, extractor: IntelligenceExtractor) -> None:
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
        session_id = self._session_manager.new_session(name, project)
        self._session_id = session_id
        self._project = self._session_manager.project
        self._session_uri = self._session_manager.session_uri
        # Update tier_manager's hot_dag reference
        if self._tier_manager:
            self._tier_manager._hot_dag = self._hot_dag
        return session_id

    @property
    def session_uri(self) -> str:
        """Get the full session URI (RFC-101)."""
        return self._session_manager.session_uri

    @property
    def project(self) -> str:
        """Get the current project slug."""
        return self._session_manager.project

    def set_project(self, project: str) -> None:
        """Set the project context for session scoping.

        Args:
            project: Project slug
        """
        self._session_manager.set_project(project)
        self._project = project

    def list_sessions(self, project: str | None = None) -> list[dict[str, Any]]:
        """List all saved sessions.

        RFC-101: Can filter by project.

        Args:
            project: Optional project filter (None = all projects)

        Returns:
            List of session metadata dicts
        """
        return self._session_manager.list_sessions(project)

    def save_session(self, name: str | None = None) -> Path:
        """Save current session to disk.

        RFC-101: Saves to project-scoped directory.
        """
        # Update session manager's hot_dag reference before saving
        self._session_manager._set_hot_dag(self._hot_dag)
        return self._session_manager.save_session(name)

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
        loaded_dag = self._session_manager.load_session(session_id, project)
        self._hot_dag = loaded_dag
        self._session_id = self._session_manager._session_id
        self._project = self._session_manager.project
        self._session_uri = self._session_manager.session_uri
        # Update tier_manager's hot_dag reference
        if self._tier_manager:
            self._tier_manager._hot_dag = loaded_dag

        # Apply tiered compression if session has many turns
        if self.config.auto_cleanup and self._tier_manager:
            self._tier_manager.maybe_demote_to_warm()

        return loaded_dag

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
            turn = estimate_token_count(turn)

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
        if self.config.auto_cleanup and self._tier_manager:
            self._tier_manager.maybe_demote_to_warm()

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
            turn = estimate_token_count(turn)

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
        if self.config.auto_cleanup and self._tier_manager:
            self._tier_manager.maybe_demote_to_warm()

        # RFC-084: Auto-extract topology every N turns
        turn_count = len(self._hot_dag.turns)
        if self.config.auto_topology and turn_count % self.config.topology_interval == 0:
            if self._chunk_manager and self._topology_extractor and self._unified_store:
                await extract_topology_batch(
                    self._chunk_manager,
                    self._topology_extractor,
                    self._unified_store,
                    self._topology_extracted_chunks,
                )

        # RFC-084: Auto-demote warm chunks to cold
        if self.config.auto_cold_demotion and self._chunk_manager:
            maybe_demote_warm_to_cold(self._chunk_manager, self.config)

        return turn_id


    def add_user(self, content: str, **kwargs) -> str:
        """Convenience: add user message.

        Creates a Turn and routes through add_turn() for ChunkManager integration.
        """
        from sunwell.memory.simulacrum.core.turn import Turn

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
        from sunwell.memory.simulacrum.core.turn import Turn

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

    # === RFC-022 Enhancement: Episode Tracking ===

    # === RFC-022 Enhancement: Episode Tracking ===

    def add_episode(
        self,
        summary: str,
        outcome: str,  # succeeded, failed, partial, abandoned
        learnings_extracted: tuple[str, ...] = (),
        models_used: tuple[str, ...] = (),
    ) -> str:
        """Add an episode tracking past problem-solving attempt.

        Episodes help avoid repeating dead ends and learn from past sessions.

        Args:
            summary: Brief description of what was attempted
            outcome: 'succeeded', 'failed', 'partial', or 'abandoned'
            learnings_extracted: Key insights from this episode
            models_used: Models that were used during the episode

        Returns:
            Episode ID
        """
        turn_count = sum(1 for _ in self._hot_dag.iter_all_turns())
        return self._episode_manager.add_episode(
            summary=summary,
            outcome=outcome,
            learnings_extracted=learnings_extracted,
            models_used=models_used,
            turn_count=turn_count,
        )

    def get_episodes(self, limit: int = 50) -> list[Episode]:
        """Get recent episodes.

        Args:
            limit: Maximum episodes to return

        Returns:
            List of episodes, most recent first
        """
        return self._episode_manager.get_episodes(limit=limit)

    def get_dead_ends(self) -> list[Episode]:
        """Get failed episodes to avoid repeating mistakes.

        Returns:
            List of episodes with 'failed' outcome
        """
        return self._episode_manager.get_dead_ends()

    def get_successful_patterns(self) -> list[Episode]:
        """Get successful episodes for learning what works.

        Returns:
            List of episodes with 'succeeded' outcome
        """
        return self._episode_manager.get_successful_patterns()

    def get_episode_by_id(self, episode_id: str) -> Episode | None:
        """Get a specific episode by ID.

        Args:
            episode_id: The episode ID

        Returns:
            Episode if found, None otherwise
        """
        return self._episode_manager.get_episode_by_id(episode_id)

    # === RFC-122: Knowledge Retrieval for Planning ===

    async def retrieve_for_planning(
        self,
        goal: str,
        limit_per_category: int = 5,
    ) -> PlanningContext:
        """Retrieve all relevant knowledge for planning a task (RFC-122).

        Uses existing _embedder for semantic matching against learnings
        stored in DAG. Returns categorized results for injection into
        HarmonicPlanner via Convergence.

        Args:
            goal: Task description to match against
            limit_per_category: Max items per category

        Returns:
            PlanningContext with categorized learnings
        """
        if not self._planning_retriever:
            # Initialize if not already done
            self._init_retrievers()
            assert self._planning_retriever is not None

        # Update episodes if needed
        if self._episode_manager:
            episodes = self._episode_manager.get_episodes(limit=100)
            self._planning_retriever._episodes = episodes

        return await self._planning_retriever.retrieve(goal, limit_per_category)

    # === RFC-022: Parallel Retrieval ===

    async def retrieve_parallel(
        self,
        query: str,
        include_learnings: bool = True,
        include_episodes: bool = True,
        include_recent_turns: bool = True,
        include_chunks: bool = True,
        limit_per_type: int = 10,
    ) -> MemoryRetrievalResult:
        """Parallel retrieval across memory types with free-threading awareness.

        Uses ThreadPoolExecutor with adaptive worker count based on GIL state
        for true parallel retrieval when running on Python 3.13+ free-threaded.

        Args:
            query: Query string for semantic matching
            include_learnings: Include learnings from DAG
            include_episodes: Include episodes (past sessions)
            include_recent_turns: Include recent conversation turns
            include_chunks: Include warm/cold chunks
            limit_per_type: Max items per memory type

        Returns:
            MemoryRetrievalResult with all retrieved items
        """
        # Update episodes and chunk_manager if needed
        episodes = self._episode_manager.get_episodes(limit=100)
        self._semantic_retriever._episodes = episodes
        if self._chunk_manager:
            self._semantic_retriever._chunk_manager = self._chunk_manager

        return await self._semantic_retriever.retrieve_parallel(
            query=query,
            include_learnings=include_learnings,
            include_episodes=include_episodes,
            include_recent_turns=include_recent_turns,
            include_chunks=include_chunks,
            limit_per_type=limit_per_type,
        )

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
        return self._context_assembler.get_context_for_prompt(query, max_tokens)

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
        return await self._context_assembler.get_context_for_prompt_async(query, max_tokens)

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
        if not self._context_assembler:
            # Initialize if not already done
            self._init_retrievers()
            assert self._context_assembler is not None

        return self._context_assembler.assemble_messages(query, system_prompt, max_tokens)

    # === RFC-084: Auto-Wiring Methods ===
    # (Implementation moved to auto_wiring.py module)

    @property
    def focus(self) -> Focus | None:
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
        if not self._context_assembler:
            # Initialize if not already done
            self._init_retrievers()
            assert self._context_assembler is not None

        # Update focus if needed
        if self._focus:
            self._context_assembler._focus = self._focus

        return self._context_assembler.get_context_for_prompt_weighted(query, max_tokens)

    # === Tier Management ===

    def _flush_hot(self) -> None:
        """Flush hot tier to disk."""
        if self._tier_manager:
            self._tier_manager.flush_hot(self._session_id)
        else:
            self._hot_dag.save(self.hot_path)

    def _maybe_demote_to_warm(self) -> None:
        """Move old turns from hot to warm storage."""
        if self._tier_manager:
            self._tier_manager.maybe_demote_to_warm()
        # Fallback implementation if tier_manager not initialized
        elif len(self._hot_dag.turns) > self.config.hot_max_turns:
            turns_by_time = sorted(
                self._hot_dag.turns.values(),
                key=lambda t: t.timestamp,
            )
            to_demote = turns_by_time[:len(turns_by_time) - self.config.hot_max_turns]
            for turn in to_demote:
                self._hot_dag.compressed.add(turn.id)

    def move_to_cold(self, older_than_hours: int | None = None) -> int:
        """Archive old warm storage to cold (compressed)."""
        if self._tier_manager:
            return self._tier_manager.move_to_cold(older_than_hours)
        return 0

    def retrieve_from_warm(self, turn_id: str) -> Turn | None:
        """Retrieve a specific turn from warm storage."""
        if self._tier_manager:
            return self._tier_manager.retrieve_from_warm(turn_id)
        return None

    def search_warm(self, query: str, limit: int = 10) -> list[Turn]:
        """Simple text search over warm storage."""
        if self._tier_manager:
            return self._tier_manager.search_warm(query, limit)
        return []

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
        return await ingest_document(
            self._unified_store,
            file_path,
            content,
            extract_facets=extract_facets,
            extract_topology=extract_topology,
        )

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
        if not self._unified_store:
            return 0
        return await ingest_codebase(self._unified_store, root_path, file_patterns)

    # === Stats & Cleanup ===

    def stats(self) -> dict[str, Any]:
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
        dead_end_ids = self._hot_dag.dead_ends
        if not dead_end_ids or not self._tier_manager:
            return 0
        return self._tier_manager.cleanup_dead_ends(dead_end_ids)
