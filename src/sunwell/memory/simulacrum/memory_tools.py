# src/sunwell/simulacrum/memory_tools.py
"""Memory tools for RFC-012 tool calling integration.

Gives models explicit agency over memory operations:
- search_memory: Search conversation history and learnings
- recall_user_info: Recall stored user information
- find_related: Find related concepts via graph traversal
- find_contradictions: Find contradicting information
- add_learning: Store important facts/decisions
- mark_dead_end: Record failed approaches

Part of RFC-014: Multi-Topology Memory.
"""


from typing import TYPE_CHECKING

from sunwell.models import Tool

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore


# === Memory Tool Definitions ===

MEMORY_TOOLS: dict[str, Tool] = {
    # === Search & Recall ===

    "search_memory": Tool(
        name="search_memory",
        description=(
            "Search conversation history, learnings, and indexed content. "
            "Use when you need to recall something discussed earlier, "
            "find related context, or verify what you know."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query (e.g., 'user name', 'caching decision')",
                },
                "content_type": {
                    "type": "string",
                    "description": "Filter by content type",
                    "enum": ["any", "conversation", "learning", "decision", "dead_end"],
                    "default": "any",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),

    "recall_user_info": Tool(
        name="recall_user_info",
        description=(
            "Recall stored information about the user: name, preferences, "
            "context, constraints. Use before answering personal questions."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),

    "find_related": Tool(
        name="find_related",
        description=(
            "Find information that elaborates on, depends on, or relates to a topic. "
            "Uses the concept graph to traverse relationships."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or concept to find related information for",
                },
                "relationship": {
                    "type": "string",
                    "description": "Type of relationship to follow",
                    "enum": ["any", "elaborates", "depends_on", "contradicts", "supersedes"],
                    "default": "any",
                },
            },
            "required": ["topic"],
        },
    ),

    "find_contradictions": Tool(
        name="find_contradictions",
        description=(
            "Find information that contradicts or conflicts with a statement. "
            "Use before making claims to check for known issues."
        ),
        parameters={
            "type": "object",
            "properties": {
                "statement": {
                    "type": "string",
                    "description": "Statement to check for contradictions",
                },
            },
            "required": ["statement"],
        },
    ),

    # === Store & Track ===

    "add_learning": Tool(
        name="add_learning",
        description=(
            "Save an important fact, decision, or insight for future recall. "
            "Use when the user shares personal info, makes a decision, or "
            "when you discover something worth remembering."
        ),
        parameters={
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact or insight to remember",
                },
                "category": {
                    "type": "string",
                    "description": "Category for organization",
                    "enum": ["user_info", "decision", "preference", "constraint", "insight"],
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level 0.0-1.0",
                    "default": 1.0,
                },
            },
            "required": ["fact", "category"],
        },
    ),

    "mark_dead_end": Tool(
        name="mark_dead_end",
        description=(
            "Record that the current approach won't work, with reason. "
            "Prevents revisiting failed paths and helps future retrieval "
            "avoid suggesting the same dead ends."
        ),
        parameters={
            "type": "object",
            "properties": {
                "approach": {
                    "type": "string",
                    "description": "What approach was tried",
                },
                "reason": {
                    "type": "string",
                    "description": "Why it doesn't work",
                },
            },
            "required": ["approach", "reason"],
        },
    ),
}


class MemoryToolHandler:
    """Handles memory tool execution.

    Bridges RFC-012 tool calls to RFC-014 memory operations.
    """

    def __init__(
        self,
        dag: ConversationDAG,
        store: UnifiedMemoryStore | None = None,
        embedder: EmbeddingProtocol | None = None,
        activity_days: int = 0,
    ):
        self.dag = dag
        self.store = store
        self.embedder = embedder
        self._activity_days = activity_days

    def update_activity_days(self, activity_days: int) -> None:
        """Update the current activity day count.

        Call this at session start or when activity is recorded.
        """
        self._activity_days = activity_days

    async def handle(self, tool_name: str, arguments: dict) -> str:
        """Execute a memory tool and return result."""

        if tool_name == "search_memory":
            return await self._search_memory(
                query=arguments["query"],
                content_type=arguments.get("content_type", "any"),
                limit=arguments.get("limit", 5),
            )

        elif tool_name == "recall_user_info":
            return await self._recall_user_info()

        elif tool_name == "find_related":
            return await self._find_related(
                topic=arguments["topic"],
                relationship=arguments.get("relationship", "any"),
            )

        elif tool_name == "find_contradictions":
            return await self._find_contradictions(arguments["statement"])

        elif tool_name == "add_learning":
            return self._add_learning(
                fact=arguments["fact"],
                category=arguments["category"],
                confidence=arguments.get("confidence", 1.0),
            )

        elif tool_name == "mark_dead_end":
            return self._mark_dead_end(
                approach=arguments["approach"],
                reason=arguments["reason"],
            )

        else:
            return f"Unknown memory tool: {tool_name}"

    async def _search_memory(
        self,
        query: str,
        content_type: str,
        limit: int,
    ) -> str:
        """Search memory using hybrid retrieval."""
        results = []

        # Search learnings
        if content_type in ("any", "learning", "user_info"):
            for learning in self.dag.get_active_learnings():
                if query.lower() in learning.fact.lower():
                    results.append(f"[Learning/{learning.category}] {learning.fact}")

        # Search conversation history
        if content_type in ("any", "conversation"):
            for turn in self.dag.iter_all_turns():
                if query.lower() in turn.content.lower():
                    prefix = "User" if turn.turn_type.value == "user" else "Assistant"
                    results.append(f"[{prefix}] {turn.content[:200]}...")
                    if len(results) >= limit:
                        break

        # Search unified store if available
        if self.store and content_type in ("any", "decision", "dead_end"):
            store_results = self.store.query(text_query=query, limit=limit)
            for node, _score in store_results:
                results.append(f"[Memory] {node.content[:200]}...")

        if not results:
            return f"No results found for '{query}'"

        return "\n".join(results[:limit])

    async def _recall_user_info(self) -> str:
        """Recall all user_info category learnings."""
        user_learnings = [
            l for l in self.dag.get_active_learnings()
            if l.category == "user_info"
        ]

        if not user_learnings:
            return "No user information stored."

        return "\n".join(f"- {l.fact}" for l in user_learnings)

    async def _find_related(self, topic: str, relationship: str) -> str:
        """Find related concepts via graph traversal."""
        if not self.store:
            return "Unified memory store not available."

        # Find node matching topic
        candidates = self.store.query(text_query=topic, limit=1)
        if not candidates:
            return f"No information found about '{topic}'"

        node, _ = candidates[0]

        # Get related via graph
        if relationship == "elaborates":
            related = self.store.find_elaborations(node.id)
        elif relationship == "contradicts":
            related = self.store.find_contradictions(node.id)
        elif relationship == "depends_on":
            related = self.store.find_dependencies(node.id)
        else:
            related = self.store.find_related(node.id, depth=2)

        if not related:
            return f"No related information found for '{topic}'"

        return "\n".join(f"- {n.content[:200]}..." for n in related[:5])

    async def _find_contradictions(self, statement: str) -> str:
        """Find information contradicting a statement."""
        if not self.store:
            # Fall back to dead ends in DAG
            dead_end_turns = [
                self.dag.turns[tid]
                for tid in self.dag.dead_ends
                if tid in self.dag.turns
            ]
            if dead_end_turns:
                return "Dead ends (may conflict):\n" + "\n".join(
                    f"- {t.content[:200]}..." for t in dead_end_turns[:5]
                )
            return "No contradictions found."

        # Search and check for contradictions
        candidates = self.store.query(text_query=statement, limit=5)
        contradictions = []

        for node, _ in candidates:
            edges = self.store._concept_graph.find_contradictions(node.id)
            for edge in edges:
                if edge.target_id in self.store._nodes:
                    target = self.store._nodes[edge.target_id]
                    contradictions.append(
                        f"- {target.content[:200]}... (confidence: {edge.confidence:.2f})"
                    )

        if not contradictions:
            return "No contradictions found."

        return "Potential contradictions:\n" + "\n".join(contradictions[:5])

    def _add_learning(self, fact: str, category: str, confidence: float) -> str:
        """Add a learning to the DAG."""
        from sunwell.memory.simulacrum.core.turn import Learning

        learning = Learning(
            fact=fact,
            category=category,
            confidence=confidence,
            source_turns=(self.dag.active_head,) if self.dag.active_head else (),
            activity_day_created=self._activity_days,
        )
        self.dag.add_learning(learning)
        return f"✓ Learned: [{category}] {fact}"

    def _mark_dead_end(self, approach: str, reason: str) -> str:
        """Mark current path as dead end with context."""
        from sunwell.memory.simulacrum.core.turn import Learning

        if self.dag.active_head:
            self.dag.mark_dead_end(self.dag.active_head)

            # Add learning about the dead end
            learning = Learning(
                fact=f"Dead end: {approach} - {reason}",
                category="dead_end",
                confidence=1.0,
                source_turns=(self.dag.active_head,),
                activity_day_created=self._activity_days,
            )
            self.dag.add_learning(learning)

            return f"✓ Marked as dead end: {approach}"

        return "No active conversation to mark."
