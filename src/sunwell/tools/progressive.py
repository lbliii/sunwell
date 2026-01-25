"""Progressive tool enablement (RFC-134).

Dynamic tool availability based on execution state:
- Start conservative with read-only tools
- Unlock write tools as trust builds
- Require validation passes before dangerous operations

This is a safety feature that prevents runaway agents while still
allowing full capabilities when trust is established.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sunwell.tools.types import TRUST_LEVEL_TOOLS, ToolTrust

if TYPE_CHECKING:
    pass


# Read-only tools available at all turns (safe discovery)
_READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "list_files",
    "search_files",
    # Git read-only operations
    "git_info",
    "git_status",
    "git_diff",
    "git_log",
    "git_blame",
    "git_show",
})

# Edit tools (require turn 2+)
_EDIT_TOOLS: frozenset[str] = frozenset({
    "edit_file",
})

# Write tools (require turn 3+ and validation pass)
_WRITE_TOOLS: frozenset[str] = frozenset({
    "write_file",
    "mkdir",
    "git_add",
    "git_restore",
})

# Shell/command tools (require turn 5+, 2 validation passes, and SHELL trust)
_SHELL_TOOLS: frozenset[str] = frozenset({
    "run_command",
    "git_commit",
    "git_branch",
    "git_checkout",
    "git_stash",
    "git_reset",
    "git_merge",
})


@dataclass(slots=True)
class ProgressivePolicy:
    """Dynamic tool availability based on execution state (RFC-134).

    Implements a trust ladder that starts conservative and unlocks
    tools as the agent demonstrates safe behavior:

    Turn 1: Read-only (read_file, list_files, search_files)
    Turn 2+: + edit_file (if WORKSPACE trust)
    Turn 3+ & 1 validation pass: + write_file, mkdir
    Turn 5+ & 2 validation passes: + run_command (if SHELL trust)

    FULL trust bypasses all restrictions.
    """

    base_trust: ToolTrust
    """Base trust level from session configuration."""

    turn: int = 1
    """Current turn number (1-indexed)."""

    validation_passes: int = 0
    """Number of successful validation gate passes."""

    validation_failures: int = 0
    """Number of validation failures (can reduce available tools)."""

    # Track which tools have been used successfully
    _successful_tools: set[str] = field(default_factory=set, init=False)
    """Tools that have been used without errors."""

    def get_available_tools(self) -> frozenset[str]:
        """Return tools available at current state.

        Returns:
            Frozenset of tool names available for use
        """
        # FULL trust bypasses progressive unlock
        if self.base_trust == ToolTrust.FULL:
            return TRUST_LEVEL_TOOLS[ToolTrust.FULL]

        # Start with read-only tools (always available)
        tools: set[str] = set(_READ_ONLY_TOOLS)

        # Turn 2+: Add edit_file if WORKSPACE trust
        if self.turn >= 2 and self.base_trust.includes(ToolTrust.WORKSPACE):
            tools.update(_EDIT_TOOLS)

        # Turn 3+ with validation pass: Add write tools
        if self.turn >= 3 and self.validation_passes >= 1:
            if self.base_trust.includes(ToolTrust.WORKSPACE):
                tools.update(_WRITE_TOOLS)

        # Turn 5+ with 2 validation passes: Add shell tools
        if self.turn >= 5 and self.validation_passes >= 2:
            if self.base_trust.includes(ToolTrust.SHELL):
                tools.update(_SHELL_TOOLS)

        # If too many validation failures, restrict to read-only
        if self.validation_failures >= 3:
            return frozenset(_READ_ONLY_TOOLS)

        return frozenset(tools)

    def filter_tools(self, tools: tuple) -> tuple:
        """Filter tool definitions to only available ones.

        Args:
            tools: Tuple of Tool objects

        Returns:
            Filtered tuple with only available tools
        """
        available = self.get_available_tools()
        return tuple(t for t in tools if t.name in available)

    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a specific tool is available.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is available at current state
        """
        return tool_name in self.get_available_tools()

    def advance_turn(self) -> None:
        """Advance to the next turn."""
        self.turn += 1

    def record_validation_pass(self) -> None:
        """Record a successful validation gate pass."""
        self.validation_passes += 1

    def record_validation_failure(self) -> None:
        """Record a validation gate failure."""
        self.validation_failures += 1

    def record_tool_success(self, tool_name: str) -> None:
        """Record that a tool was used successfully.

        Successful usage can accelerate tool unlocking.

        Args:
            tool_name: Name of the tool that succeeded
        """
        self._successful_tools.add(tool_name)

    def get_unlock_status(self) -> dict[str, bool]:
        """Get status of each tool category unlock.

        Returns:
            Dict mapping category to unlock status
        """
        available = self.get_available_tools()
        return {
            "read_only": bool(_READ_ONLY_TOOLS & available),
            "edit": bool(_EDIT_TOOLS & available),
            "write": bool(_WRITE_TOOLS & available),
            "shell": bool(_SHELL_TOOLS & available),
        }

    def get_unlock_requirements(self) -> dict[str, str]:
        """Get requirements for unlocking each category.

        Returns:
            Dict mapping category to requirement description
        """
        requirements: dict[str, str] = {}

        if not self.is_tool_available("edit_file"):
            if self.turn < 2:
                requirements["edit"] = f"Wait {2 - self.turn} more turn(s)"
            elif not self.base_trust.includes(ToolTrust.WORKSPACE):
                requirements["edit"] = "Requires WORKSPACE trust level"

        if not self.is_tool_available("write_file"):
            needs: list[str] = []
            if self.turn < 3:
                needs.append(f"wait {3 - self.turn} more turn(s)")
            if self.validation_passes < 1:
                needs.append("pass 1 validation gate")
            if needs:
                requirements["write"] = "Need to " + " and ".join(needs)

        if not self.is_tool_available("run_command"):
            needs: list[str] = []
            if self.turn < 5:
                needs.append(f"wait {5 - self.turn} more turn(s)")
            if self.validation_passes < 2:
                needs.append(f"pass {2 - self.validation_passes} more validation gate(s)")
            if not self.base_trust.includes(ToolTrust.SHELL):
                needs.append("SHELL trust level")
            if needs:
                requirements["shell"] = "Need: " + ", ".join(needs)

        return requirements

    def to_dict(self) -> dict:
        """Convert to dict for serialization/debugging."""
        return {
            "base_trust": self.base_trust.value,
            "turn": self.turn,
            "validation_passes": self.validation_passes,
            "validation_failures": self.validation_failures,
            "available_tools": list(self.get_available_tools()),
            "unlock_status": self.get_unlock_status(),
            "unlock_requirements": self.get_unlock_requirements(),
        }
