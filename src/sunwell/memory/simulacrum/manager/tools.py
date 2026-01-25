"""Tool handler and tool definitions for simulacrum management.

RFC-025: Extracted from manager.py to slim it down.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.models.protocol import Tool

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.manager.manager import SimulacrumManager


SIMULACRUM_TOOLS: dict[str, Tool] = {
    "list_simulacrums": Tool(
        name="list_simulacrums",
        description=(
            "List all available simulacrums. Returns their names, descriptions, "
            "and domain tags. Use this to see what contexts are available."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),

    "switch_simulacrum": Tool(
        name="switch_simulacrum",
        description=(
            "Switch to a different simulacrum context. Use when the conversation "
            "shifts to a new domain or when you need specialized knowledge. "
            "Example: switch to 'security' simulacrum when discussing vulnerabilities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the simulacrum to activate",
                },
            },
            "required": ["name"],
        },
    ),

    "create_simulacrum": Tool(
        name="create_simulacrum",
        description=(
            "Create a new simulacrum for a new domain or project. "
            "Use when the current conversation introduces a distinct new context "
            "that deserves its own memory space."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name for the new simulacrum (e.g., 'api-security')",
                },
                "description": {
                    "type": "string",
                    "description": "What this simulacrum is for",
                },
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Domain tags for routing (e.g., ['security', 'api'])",
                },
            },
            "required": ["name", "description"],
        },
    ),

    "suggest_simulacrum": Tool(
        name="suggest_simulacrum",
        description=(
            "Get suggestions for which simulacrum might be relevant "
            "for a given topic or query. Use to decide if you should switch contexts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or query to find relevant simulacrums for",
                },
            },
            "required": ["topic"],
        },
    ),

    "query_all_simulacrums": Tool(
        name="query_all_simulacrums",
        description=(
            "Search across ALL simulacrums for relevant information. "
            "Use when you need knowledge that might exist in different contexts, "
            "or when you're unsure which simulacrum has the answer."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results per simulacrum",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    ),

    "current_simulacrum": Tool(
        name="current_simulacrum",
        description="Get information about the currently active simulacrum.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),

    "route_query": Tool(
        name="route_query",
        description=(
            "Smart routing for a query: finds the best simulacrum, or auto-spawns "
            "a new one if the topic is novel. Use this instead of manual switching "
            "when you're unsure which simulacrum to use. The system will track queries "
            "and create new simulacrums when it detects coherent new domains."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query/topic to route",
                },
                "activate": {
                    "type": "boolean",
                    "description": "Whether to activate the matched/spawned simulacrum",
                    "default": True,
                },
            },
            "required": ["query"],
        },
    ),

    "spawn_status": Tool(
        name="spawn_status",
        description=(
            "Check the auto-spawn tracking status. Shows pending domains being "
            "tracked, their coherence scores, and whether they're ready to become "
            "new simulacrums. Useful for understanding why/when new simulacrums appear."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),

    "simulacrum_health": Tool(
        name="simulacrum_health",
        description=(
            "Check the health of all simulacrums. Returns info about stale simulacrums, "
            "empty ones, merge candidates, and archive candidates. Use this to understand "
            "which simulacrums need attention."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),

    "archive_simulacrum": Tool(
        name="archive_simulacrum",
        description=(
            "Archive a simulacrum to cold storage. The simulacrum data is compressed "
            "and stored, freeing up active memory. It can be restored later. "
            "Use for simulacrums that aren't needed now but might be useful later."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of simulacrum to archive",
                },
                "reason": {
                    "type": "string",
                    "description": "Why archiving (stale, manual, empty)",
                    "default": "manual",
                },
            },
            "required": ["name"],
        },
    ),

    "restore_simulacrum": Tool(
        name="restore_simulacrum",
        description=(
            "Restore an archived simulacrum back to active use. "
            "Use when you need knowledge from a previously archived context."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of archived simulacrum to restore",
                },
            },
            "required": ["name"],
        },
    ),

    "list_archived": Tool(
        name="list_archived",
        description="List all archived simulacrums that can be restored.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),

    "cleanup_simulacrums": Tool(
        name="cleanup_simulacrums",
        description=(
            "Run automatic cleanup: archive stale simulacrums, merge empty ones. "
            "Use dry_run=true first to see what would happen."
        ),
        parameters={
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only report what would be done",
                    "default": True,
                },
            },
            "required": [],
        },
    ),

    "shrink_simulacrum": Tool(
        name="shrink_simulacrum",
        description=(
            "Shrink a simulacrum by removing old, low-value content while keeping "
            "important knowledge. Use when a simulacrum has grown too large."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of simulacrum to shrink",
                },
                "keep_recent_days": {
                    "type": "integer",
                    "description": "Keep all content from this many days",
                    "default": 30,
                },
            },
            "required": ["name"],
        },
    ),
}


@dataclass(slots=True)
class SimulacrumToolHandler:
    """Handles simulacrum management tool calls."""

    manager: SimulacrumManager

    async def handle(self, tool_name: str, arguments: dict) -> str:
        """Handle a simulacrum tool call."""
        if tool_name == "list_simulacrums":
            return self._list_simulacrums()

        elif tool_name == "switch_simulacrum":
            return self._switch_simulacrum(arguments["name"])

        elif tool_name == "create_simulacrum":
            return self._create_simulacrum(
                name=arguments["name"],
                description=arguments["description"],
                domains=tuple(arguments.get("domains", [])),
            )

        elif tool_name == "suggest_simulacrum":
            return self._suggest_simulacrum(arguments["topic"])

        elif tool_name == "query_all_simulacrums":
            return await self._query_all(
                query=arguments["query"],
                limit=arguments.get("limit", 3),
            )

        elif tool_name == "current_simulacrum":
            return self._current_simulacrum()

        elif tool_name == "route_query":
            return self._route_query(
                query=arguments["query"],
                activate=arguments.get("activate", True),
            )

        elif tool_name == "spawn_status":
            return self._spawn_status()

        elif tool_name == "simulacrum_health":
            return self._simulacrum_health()

        elif tool_name == "archive_simulacrum":
            return self._archive_simulacrum(
                name=arguments["name"],
                reason=arguments.get("reason", "manual"),
            )

        elif tool_name == "restore_simulacrum":
            return self._restore_simulacrum(arguments["name"])

        elif tool_name == "list_archived":
            return self._list_archived()

        elif tool_name == "cleanup_simulacrums":
            return self._cleanup_simulacrums(
                dry_run=arguments.get("dry_run", True),
            )

        elif tool_name == "shrink_simulacrum":
            return self._shrink_simulacrum(
                name=arguments["name"],
                keep_recent_days=arguments.get("keep_recent_days", 30),
            )

        return f"Unknown simulacrum tool: {tool_name}"

    def _list_simulacrums(self) -> str:
        simulacrums = self.manager.list_simulacrums()
        if not simulacrums:
            return "No simulacrums exist yet. Create one with create_simulacrum."

        lines = ["Available simulacrums:"]
        for meta in simulacrums:
            active = " (active)" if meta.name == self.manager.active_name else ""
            domains = f" [{', '.join(meta.domains)}]" if meta.domains else ""
            lines.append(
                f"- **{meta.name}**{active}: {meta.description}{domains} "
                f"({meta.node_count} nodes, {meta.learning_count} learnings)"
            )
        return "\n".join(lines)

    def _switch_simulacrum(self, name: str) -> str:
        try:
            self.manager.activate(name)
            meta = self.manager._metadata[name]
            return (
                f"✓ Switched to simulacrum: **{name}**\n"
                f"  {meta.description}\n"
                f"  {meta.node_count} nodes, {meta.learning_count} learnings available"
            )
        except KeyError:
            available = ", ".join(m.name for m in self.manager.list_simulacrums())
            return f"Simulacrum '{name}' not found. Available: {available}"

    def _create_simulacrum(
        self,
        name: str,
        description: str,
        domains: tuple[str, ...],
    ) -> str:
        try:
            self.manager.create(name, description, domains)
            return (
                f"✓ Created simulacrum: **{name}**\n"
                f"  {description}\n"
                f"  Domains: {', '.join(domains) if domains else 'none'}\n"
                f"  Use switch_simulacrum to activate it."
            )
        except ValueError as e:
            return f"Error: {e}"

    def _suggest_simulacrum(self, topic: str) -> str:
        suggestions = self.manager.suggest(topic)
        if not suggestions:
            return (
                f"No relevant simulacrums found for '{topic}'. "
                "Consider creating a new one with create_simulacrum."
            )

        lines = [f"Suggested simulacrums for '{topic}':"]
        for meta, score in suggestions:
            active = " (currently active)" if meta.name == self.manager.active_name else ""
            lines.append(
                f"- **{meta.name}** ({score:.0%} relevance){active}: {meta.description}"
            )
        return "\n".join(lines)

    async def _query_all(self, query: str, limit: int) -> str:
        results = self.manager.query_all(query, limit_per_simulacrum=limit)
        if not results:
            return f"No results found for '{query}' across any simulacrum."

        lines = [f"Results for '{query}' across all simulacrums:"]
        current_hs = None
        for hs_name, node, score in results[:15]:  # Cap total results
            if hs_name != current_hs:
                lines.append(f"\n**From {hs_name}:**")
                current_hs = hs_name
            lines.append(f"- [{score:.0%}] {node.content[:150]}...")

        return "\n".join(lines)

    def _current_simulacrum(self) -> str:
        name = self.manager.active_name
        if not name:
            return "No simulacrum is currently active. Use switch_simulacrum to activate one."

        meta = self.manager._metadata[name]
        store = self.manager.active
        stats = store.stats() if store else {}

        auto_tag = " (auto-spawned)" if meta.auto_spawned else ""

        return (
            f"**Active Simulacrum: {name}**{auto_tag}\n"
            f"  Description: {meta.description}\n"
            f"  Domains: {', '.join(meta.domains) if meta.domains else 'none'}\n"
            f"  Created: {meta.created_at[:10]}\n"
            f"  Accesses: {meta.access_count}\n"
            f"  Memory nodes: {stats.get('unified_store', {}).get('total_nodes', 0)}\n"
            f"  Learnings: {stats.get('dag_stats', {}).get('learnings', 0)}"
        )

    def _route_query(self, query: str, activate: bool) -> str:
        store, was_spawned, explanation = self.manager.route_query(query, activate=activate)

        if was_spawned:
            return f"🆕 {explanation}\nA new simulacrum was created because this topic is novel."
        elif store:
            return f"✓ {explanation}"
        else:
            return f"⏳ {explanation}"

    def _spawn_status(self) -> str:
        status = self.manager.check_spawn_status()

        lines = [
            "**Auto-Spawn Status**",
            f"  Enabled: {status['spawn_enabled']}",
            f"  Novelty threshold: {status['novelty_threshold']:.0%}",
            f"  Min queries before spawn: {status['min_queries']}",
            f"  Coherence threshold: {status['coherence_threshold']:.0%}",
            f"  Simulacrums: {status['simulacrum_count']}/{status['max_simulacrums']}",
            f"  Unmatched queries tracked: {status['unmatched_queries']}",
        ]

        if status['pending_domains']:
            lines.append("\n**Pending Domains** (potential new simulacrums):")
            for domain in status['pending_domains']:
                ready = "✓ Ready" if domain['ready_to_spawn'] else "○ Accumulating"
                keywords = ', '.join(domain['top_keywords'][:3]) if domain['top_keywords'] else 'none'
                lines.append(
                    f"  - {ready}: {domain['query_count']} queries, "
                    f"coherence={domain['coherence']:.0%}, "
                    f"keywords=[{keywords}]"
                )
        else:
            lines.append("\nNo pending domains (all queries matched existing simulacrums)")

        return "\n".join(lines)

    def _simulacrum_health(self) -> str:
        health = self.manager.check_health()

        lines = ["**Simulacrum Health Report**"]
        lines.append(f"Total active: {health['total_simulacrums']}")
        lines.append(f"Total archived: {health['total_archived']}")

        if health["stale"]:
            lines.append("\n**⚠️ Stale Simulacrums** (not accessed recently):")
            for name, days in health["stale"][:5]:
                lines.append(f"  - {name}: {days} days since last access")

        if health["empty"]:
            lines.append("\n**📭 Empty/Low-Value Simulacrums:**")
            for name in health["empty"][:5]:
                lines.append(f"  - {name}")

        if health["archive_candidates"]:
            lines.append("\n**📦 Archive Candidates** (very stale):")
            for name in health["archive_candidates"][:5]:
                lines.append(f"  - {name}")

        if health["merge_candidates"]:
            lines.append("\n**🔀 Merge Candidates** (similar domains):")
            for name1, name2, sim in health["merge_candidates"][:5]:
                lines.append(f"  - {name1} ↔ {name2} ({sim:.0%} overlap)")

        if not any([health["stale"], health["empty"], health["archive_candidates"], health["merge_candidates"]]):
            lines.append("\n✅ All simulacrums are healthy!")

        return "\n".join(lines)

    def _archive_simulacrum(self, name: str, reason: str) -> str:
        try:
            meta = self.manager.archive(name, reason=reason)
            return (
                f"✅ Archived simulacrum: **{name}**\n"
                f"  Reason: {reason}\n"
                f"  Saved to: {meta.archive_path}\n"
                f"  Use restore_simulacrum to bring it back."
            )
        except KeyError:
            return f"❌ Simulacrum '{name}' not found."
        except ValueError as e:
            return f"❌ Cannot archive: {e}"

    def _restore_simulacrum(self, name: str) -> str:
        try:
            self.manager.restore(name)
            return f"✅ Restored simulacrum: **{name}**\nIt's now available for use."
        except KeyError:
            available = ", ".join(self.manager._archived.keys())
            return f"❌ No archived simulacrum '{name}'. Archived: {available or 'none'}"
        except FileNotFoundError as e:
            return f"❌ Archive file missing: {e}"

    def _list_archived(self) -> str:
        archived = self.manager.list_archived()
        if not archived:
            return "No archived simulacrums. Use archive_simulacrum to archive stale ones."

        lines = ["**Archived Simulacrums** (can be restored):"]
        for meta in archived:
            lines.append(
                f"- **{meta.name}**: {meta.description[:40]}...\n"
                f"    Archived: {meta.archived_at[:10]} | Reason: {meta.archive_reason}\n"
                f"    Had: {meta.node_count} nodes, {meta.learning_count} learnings"
            )
        return "\n".join(lines)

    def _cleanup_simulacrums(self, dry_run: bool) -> str:
        actions = self.manager.cleanup(dry_run=dry_run)

        mode = "DRY RUN - No changes made" if dry_run else "CLEANUP COMPLETE"
        lines = [f"**{mode}**"]

        if actions["archived"]:
            lines.append("\n📦 Archived:")
            for item in actions["archived"]:
                lines.append(f"  - {item}")

        if actions["merged"]:
            lines.append("\n🔀 Merged:")
            for item in actions["merged"]:
                lines.append(f"  - {item}")

        if actions["deleted"]:
            lines.append("\n🗑️ Deleted:")
            for item in actions["deleted"]:
                lines.append(f"  - {item}")

        if not any([actions["archived"], actions["merged"], actions["deleted"]]):
            lines.append("\n✅ Nothing to clean up!")
        elif dry_run:
            lines.append("\nRun with dry_run=false to execute these changes.")

        return "\n".join(lines)

    def _shrink_simulacrum(self, name: str, keep_recent_days: int) -> str:
        try:
            stats = self.manager.shrink(name, keep_recent_days=keep_recent_days)
            return (
                f"✅ Shrunk simulacrum: **{name}**\n"
                f"  Removed {stats['nodes_removed']} old nodes\n"
                f"  Pruned {stats['edges_pruned']} weak edges\n"
                f"  Kept all content from last {keep_recent_days} days"
            )
        except KeyError:
            return f"❌ Simulacrum '{name}' not found."
