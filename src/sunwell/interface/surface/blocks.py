"""Block Types — Universal Surface Elements (RFC-080).

Blocks are lightweight surface elements with embedded actions and provider binding.
They can appear anywhere: Home, workspace sidebars, floating overlays, search results.
Blocks share the same registry pattern as RFC-072 PrimitiveDef.
"""

from dataclasses import dataclass

from sunwell.surface.types import PrimitiveSize


@dataclass(frozen=True, slots=True)
class BlockAction:
    """An action that a block can perform.

    Actions are displayed as buttons/icons within the block UI.
    """

    id: str
    """Unique identifier: "complete", "skip", "open"."""

    label: str
    """Display label: "+1", "Skip", "Open"."""

    icon: str | None = None
    """Optional icon: "✓", "→", "▶"."""

    requires_selection: bool = False
    """Whether this action needs an item selected first."""


@dataclass(frozen=True, slots=True)
class BlockDef:
    """Definition of a block — a universal surface element.

    Blocks are lightweight surface elements with embedded actions and provider binding.
    They can appear anywhere: Home, workspace sidebars, floating overlays, search results.
    """

    id: str
    """Unique identifier (e.g., "HabitsBlock", "ProjectsBlock")."""

    category: str
    """Category: "data", "actions", "conversation", "workspace"."""

    component: str
    """Svelte component name to render."""

    provider: str | None = None
    """RFC-078 provider to bind: "habits", "calendar", "contacts", etc."""

    actions: tuple[BlockAction, ...] = ()
    """Actions this block can perform (displayed as buttons)."""

    default_size: PrimitiveSize = "widget"
    """Default size: "widget", "panel", "full"."""

    contextual: bool = False
    """Whether this block appears based on context (vs. explicit request)."""

    refresh_events: tuple[str, ...] = ()
    """Events that trigger data refresh."""


class BlockRegistry:
    """Registry of available blocks.

    Mirrors PrimitiveRegistry pattern from RFC-072.
    Blocks can appear anywhere: Home, workspace sidebars, floating overlays.
    """

    def __init__(self, blocks: list[BlockDef]) -> None:
        """Initialize registry with block definitions.

        Args:
            blocks: List of block definitions
        """
        self._blocks: dict[str, BlockDef] = {b.id: b for b in blocks}

    def __contains__(self, block_id: str) -> bool:
        """Check if a block ID exists in registry."""
        return block_id in self._blocks

    def __getitem__(self, block_id: str) -> BlockDef:
        """Get a block definition by ID.

        Raises:
            KeyError: If block not found
        """
        return self._blocks[block_id]

    def get(self, block_id: str) -> BlockDef | None:
        """Get a block definition by ID, or None if not found."""
        return self._blocks.get(block_id)

    def list_all(self) -> list[BlockDef]:
        """Get all block definitions."""
        return list(self._blocks.values())

    def list_by_category(self, category: str) -> list[BlockDef]:
        """Get blocks by category."""
        return [b for b in self._blocks.values() if b.category == category]

    def list_contextual(self) -> list[BlockDef]:
        """Get blocks that appear contextually."""
        return [b for b in self._blocks.values() if b.contextual]

    def list_by_provider(self, provider: str) -> list[BlockDef]:
        """Get blocks that use a specific provider."""
        return [b for b in self._blocks.values() if b.provider == provider]

    @classmethod
    def default(cls) -> BlockRegistry:
        """Create registry with all default blocks."""
        return cls(DEFAULT_BLOCKS)


# =============================================================================
# DEFAULT BLOCK DEFINITIONS
# =============================================================================

DEFAULT_BLOCKS: list[BlockDef] = [
    # -------------------------------------------------------------------------
    # Data Blocks — Display provider data with quick actions
    # -------------------------------------------------------------------------
    BlockDef(
        id="HabitsBlock",
        category="data",
        component="HabitsBlock",
        provider="habits",
        actions=(
            BlockAction(id="complete", label="+1", icon="✓"),
            BlockAction(id="skip", label="Skip today", icon="→"),
        ),
        default_size="widget",
        contextual=True,
        refresh_events=("habit_completed", "habit_created"),
    ),
    BlockDef(
        id="ProjectsBlock",
        category="data",
        component="ProjectsBlock",
        provider="projects",
        actions=(
            BlockAction(id="open", label="Open", icon="▶", requires_selection=True),
            BlockAction(id="resume", label="Resume", requires_selection=True),
            BlockAction(id="archive", label="Archive", requires_selection=True),
        ),
        default_size="widget",
        contextual=True,
    ),
    BlockDef(
        id="CalendarBlock",
        category="data",
        component="CalendarBlock",
        provider="calendar",
        actions=(BlockAction(id="add_event", label="+ Event", icon="📅"),),
        default_size="widget",
        contextual=True,
    ),
    BlockDef(
        id="ContactsBlock",
        category="data",
        component="ContactsBlock",
        provider="contacts",
        actions=(
            BlockAction(id="call", label="Call", icon="📞", requires_selection=True),
            BlockAction(id="message", label="Message", icon="💬", requires_selection=True),
            BlockAction(id="email", label="Email", icon="✉️", requires_selection=True),
        ),
        default_size="widget",
    ),
    BlockDef(
        id="FilesBlock",
        category="data",
        component="FilesBlock",
        provider="files",
        actions=(
            BlockAction(id="open", label="Open", icon="▶", requires_selection=True),
            BlockAction(id="preview", label="Preview", icon="👁", requires_selection=True),
        ),
        default_size="widget",
    ),
    BlockDef(
        id="GitBlock",
        category="data",
        component="GitBlock",
        provider="git",
        actions=(
            BlockAction(id="stage", label="Stage", requires_selection=True),
            BlockAction(id="commit", label="Commit"),
            BlockAction(id="push", label="Push"),
        ),
        default_size="widget",
    ),
    BlockDef(
        id="BookmarksBlock",
        category="data",
        component="BookmarksBlock",
        provider="bookmarks",
        actions=(
            BlockAction(id="open", label="Open", icon="▶", requires_selection=True),
            BlockAction(id="delete", label="Delete", icon="✕", requires_selection=True),
        ),
        default_size="widget",
    ),
    BlockDef(
        id="ListBlock",
        category="data",
        component="ListBlock",
        provider="lists",
        actions=(
            BlockAction(id="check", label="Check", icon="✓", requires_selection=True),
            BlockAction(id="add", label="Add", icon="+"),
            BlockAction(id="delete", label="Delete", icon="✕", requires_selection=True),
        ),
        default_size="widget",
    ),
    BlockDef(
        id="NotesBlock",
        category="data",
        component="NotesBlock",
        provider="notes",
        actions=(
            BlockAction(id="open", label="Open", icon="▶", requires_selection=True),
            BlockAction(id="create", label="New", icon="+"),
        ),
        default_size="widget",
    ),
    BlockDef(
        id="SearchBlock",
        category="data",
        component="SearchBlock",
        provider="search",
        actions=(BlockAction(id="open", label="Open", icon="▶", requires_selection=True),),
        default_size="widget",
    ),
    # -------------------------------------------------------------------------
    # Conversation Blocks — AI responses
    # -------------------------------------------------------------------------
    BlockDef(
        id="ConversationBlock",
        category="conversation",
        component="ConversationBlock",
        actions=(
            BlockAction(id="follow_up", label="Ask more"),
            BlockAction(id="dismiss", label="Dismiss", icon="✕"),
        ),
        default_size="widget",
    ),
    # -------------------------------------------------------------------------
    # Workspace Blocks — Transition to full workspace
    # -------------------------------------------------------------------------
    BlockDef(
        id="WorkspaceBlock",
        category="workspace",
        component="WorkspaceBlock",
        actions=(
            BlockAction(id="open_workspace", label="Open", icon="▶"),
            BlockAction(id="customize", label="Customize", icon="⚙"),
        ),
        default_size="panel",
    ),
    # -------------------------------------------------------------------------
    # Inference Blocks — Model visibility (RFC-081)
    # -------------------------------------------------------------------------
    BlockDef(
        id="ThinkingBlock",
        category="inference",
        component="ThinkingBlock",
        actions=(
            BlockAction(id="cancel", label="Cancel", icon="✕"),
            BlockAction(id="dismiss", label="Dismiss", icon="↓"),
        ),
        default_size="widget",
        contextual=True,
        refresh_events=("inference_started", "inference_complete"),
    ),
    BlockDef(
        id="ModelComparisonBlock",
        category="inference",
        component="ModelComparisonBlock",
        provider="model_metrics",
        actions=(
            BlockAction(id="set_default", label="Set Default", requires_selection=True),
            BlockAction(id="clear_history", label="Clear History"),
        ),
        default_size="panel",
    ),
    # -------------------------------------------------------------------------
    # Writer Blocks — Universal Writing Environment (RFC-086)
    # -------------------------------------------------------------------------
    BlockDef(
        id="ValidationBlock",
        category="feedback",
        component="ValidationBlock",
        actions=(
            BlockAction(id="jump_to", label="Jump", icon="→", requires_selection=True),
            BlockAction(id="fix_all", label="Fix All", icon="✓"),
            BlockAction(id="dismiss", label="Dismiss", icon="✕", requires_selection=True),
        ),
        default_size="panel",
        contextual=True,
        refresh_events=("document_changed", "validation_complete"),
    ),
    BlockDef(
        id="SkillsBlock",
        category="actions",
        component="SkillsBlock",
        provider="lens_skills",
        actions=(
            BlockAction(id="execute", label="Run", icon="▶", requires_selection=True),
            BlockAction(id="configure", label="Configure", icon="⚙", requires_selection=True),
        ),
        default_size="panel",
        refresh_events=("lens_changed",),
    ),
    BlockDef(
        id="DiataxisBlock",
        category="feedback",
        component="DiataxisBlock",
        actions=(
            BlockAction(id="reclassify", label="Reclassify", icon="↻"),
            BlockAction(id="split", label="Split", icon="✂"),
        ),
        default_size="widget",
        contextual=True,
        refresh_events=("document_changed",),
    ),
    BlockDef(
        id="WorkflowPanel",
        category="workflow",
        component="WorkflowPanel",
        provider="workflow_engine",
        actions=(
            BlockAction(id="stop", label="Stop", icon="⏹"),
            BlockAction(id="skip", label="Skip Step", icon="⏭"),
            BlockAction(id="resume", label="Resume", icon="▶"),
        ),
        default_size="panel",
        contextual=True,
        refresh_events=("workflow_step_complete", "workflow_paused", "workflow_error"),
    ),
    BlockDef(
        id="HeuristicsBlock",
        category="feedback",
        component="HeuristicsBlock",
        provider="lens_heuristics",
        actions=(
            BlockAction(id="show_examples", label="Examples", requires_selection=True),
            BlockAction(id="toggle_active", label="Toggle", requires_selection=True),
        ),
        default_size="widget",
        contextual=False,
        refresh_events=("lens_changed",),
    ),
]
