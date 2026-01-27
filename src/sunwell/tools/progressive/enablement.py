"""Progressive tool enablement (RFC-134).

Dynamic tool availability based on execution state:
- Start conservative with read-only tools
- Unlock write tools as trust builds
- Require validation passes before dangerous operations

This is a safety feature that prevents runaway agents while still
allowing full capabilities when trust is established.

Unlock profiles allow customization of the unlock speed:
- CAUTIOUS: Default, requires 5 turns for shell (safest)
- STANDARD: 3 turns for shell, 1 validation (balanced)
- TRUSTED: 2 turns for all tools, no validation (fast)
- UNRESTRICTED: All tools immediately (FULL trust only)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from sunwell.tools.core.constants import TRUST_LEVEL_TOOLS
from sunwell.tools.core.types import ToolTrust

if TYPE_CHECKING:
    pass


class UnlockProfile(Enum):
    """Unlock speed profiles for progressive tool enablement.

    Different profiles balance safety vs. velocity based on use case.
    """

    CAUTIOUS = "cautious"
    """Most conservative. Current default behavior.
    - Turn 2: edit_file
    - Turn 3 + 1 validation: write tools
    - Turn 4 + 1 validation: file management (delete, rename)
    - Turn 5 + 2 validations: shell/git write
    """

    STANDARD = "standard"
    """Balanced profile for trusted environments.
    - Turn 1: edit_file
    - Turn 2 + 1 validation: write tools + file management
    - Turn 3 + 1 validation: shell/git write
    """

    TRUSTED = "trusted"
    """Fast unlock for high-trust scenarios.
    - Turn 1: edit_file, write tools
    - Turn 2: file management, shell/git write
    No validation gates required.
    """

    UNRESTRICTED = "unrestricted"
    """All tools immediately available.
    Only available with FULL trust level.
    """


# Profile-specific unlock requirements
# Format: (min_turn, min_validations)
PROFILE_REQUIREMENTS: dict[UnlockProfile, dict[str, tuple[int, int]]] = {
    UnlockProfile.CAUTIOUS: {
        "edit": (2, 0),
        "write": (3, 1),
        "file_management": (4, 1),
        "shell": (5, 2),
    },
    UnlockProfile.STANDARD: {
        "edit": (1, 0),
        "write": (2, 1),
        "file_management": (2, 1),
        "shell": (3, 1),
    },
    UnlockProfile.TRUSTED: {
        "edit": (1, 0),
        "write": (1, 0),
        "file_management": (2, 0),
        "shell": (2, 0),
    },
    UnlockProfile.UNRESTRICTED: {
        "edit": (1, 0),
        "write": (1, 0),
        "file_management": (1, 0),
        "shell": (1, 0),
    },
}


# Read-only tools available at all turns (safe discovery)
_READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "list_files",
    "search_files",
    "find_files",  # Safe discovery by path pattern
    "list_backups",  # View available backups (read-only)
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
    "copy_file",  # File management - creates files
    "patch_file",  # Unified diff application (creates backup)
    "undo_file",  # Restore from backup (modifies files)
    "restore_file",  # Restore from specific backup
    "git_add",
    "git_restore",
})

# File management tools (require turn 4+ and validation pass - potentially destructive)
_FILE_MANAGEMENT_TOOLS: frozenset[str] = frozenset({
    "delete_file",
    "rename_file",
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
    tools as the agent demonstrates safe behavior. The unlock speed
    can be configured via the `profile` parameter.

    Default (CAUTIOUS) behavior:
    - Turn 1: Read-only (read_file, list_files, search_files)
    - Turn 2+: + edit_file (if WORKSPACE trust)
    - Turn 3+ & 1 validation pass: + write_file, mkdir
    - Turn 4+ & 1 validation pass: + delete_file, rename_file
    - Turn 5+ & 2 validation passes: + run_command (if SHELL trust)

    FULL trust with UNRESTRICTED profile bypasses all restrictions.
    """

    base_trust: ToolTrust
    """Base trust level from session configuration."""

    profile: UnlockProfile = UnlockProfile.CAUTIOUS
    """Unlock speed profile. Determines how quickly tools become available."""

    turn: int = 1
    """Current turn number (1-indexed)."""

    validation_passes: int = 0
    """Number of successful validation gate passes."""

    validation_failures: int = 0
    """Number of validation failures (can reduce available tools)."""

    # Track which tools have been used successfully
    _successful_tools: set[str] = field(default_factory=set, init=False)
    """Tools that have been used without errors."""

    def _check_category_unlocked(self, category: str) -> bool:
        """Check if a tool category is unlocked based on profile requirements.

        Args:
            category: One of 'edit', 'write', 'file_management', 'shell'

        Returns:
            True if the category is unlocked
        """
        reqs = PROFILE_REQUIREMENTS[self.profile]
        if category not in reqs:
            return False

        min_turn, min_validations = reqs[category]
        return self.turn >= min_turn and self.validation_passes >= min_validations

    def get_available_tools(self) -> frozenset[str]:
        """Return tools available at current state.

        Returns:
            Frozenset of tool names available for use
        """
        # FULL trust with UNRESTRICTED profile bypasses all restrictions
        if self.base_trust == ToolTrust.FULL and self.profile == UnlockProfile.UNRESTRICTED:
            return TRUST_LEVEL_TOOLS[ToolTrust.FULL]

        # If too many validation failures, restrict to read-only
        if self.validation_failures >= 3:
            return frozenset(_READ_ONLY_TOOLS)

        # Start with read-only tools (always available)
        tools: set[str] = set(_READ_ONLY_TOOLS)

        # Check each category against profile requirements
        if self._check_category_unlocked("edit"):
            if self.base_trust.includes(ToolTrust.WORKSPACE):
                tools.update(_EDIT_TOOLS)

        if self._check_category_unlocked("write"):
            if self.base_trust.includes(ToolTrust.WORKSPACE):
                tools.update(_WRITE_TOOLS)

        if self._check_category_unlocked("file_management"):
            if self.base_trust.includes(ToolTrust.WORKSPACE):
                tools.update(_FILE_MANAGEMENT_TOOLS)

        if self._check_category_unlocked("shell"):
            if self.base_trust.includes(ToolTrust.SHELL):
                tools.update(_SHELL_TOOLS)

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
            "file_management": bool(_FILE_MANAGEMENT_TOOLS & available),
            "shell": bool(_SHELL_TOOLS & available),
        }

    def get_unlock_requirements(self) -> dict[str, str]:
        """Get requirements for unlocking each category.

        Uses profile-specific requirements to determine what's needed.

        Returns:
            Dict mapping category to requirement description
        """
        requirements: dict[str, str] = {}
        reqs = PROFILE_REQUIREMENTS[self.profile]

        # Helper to build requirement string for a category
        def build_requirement(category: str, trust_level: ToolTrust) -> str | None:
            if category not in reqs:
                return None

            min_turn, min_validations = reqs[category]
            needs: list[str] = []

            if self.turn < min_turn:
                needs.append(f"wait {min_turn - self.turn} more turn(s)")
            if self.validation_passes < min_validations:
                remaining = min_validations - self.validation_passes
                needs.append(f"pass {remaining} validation gate(s)")
            if not self.base_trust.includes(trust_level):
                needs.append(f"{trust_level.value.upper()} trust level")

            return "Need: " + ", ".join(needs) if needs else None

        # Check each category
        if not self.is_tool_available("edit_file"):
            req = build_requirement("edit", ToolTrust.WORKSPACE)
            if req:
                requirements["edit"] = req

        if not self.is_tool_available("write_file"):
            req = build_requirement("write", ToolTrust.WORKSPACE)
            if req:
                requirements["write"] = req

        if not self.is_tool_available("delete_file"):
            req = build_requirement("file_management", ToolTrust.WORKSPACE)
            if req:
                requirements["file_management"] = req

        if not self.is_tool_available("run_command"):
            req = build_requirement("shell", ToolTrust.SHELL)
            if req:
                requirements["shell"] = req

        return requirements

    def to_dict(self) -> dict:
        """Convert to dict for serialization/debugging."""
        return {
            "base_trust": self.base_trust.value,
            "profile": self.profile.value,
            "turn": self.turn,
            "validation_passes": self.validation_passes,
            "validation_failures": self.validation_failures,
            "available_tools": list(self.get_available_tools()),
            "unlock_status": self.get_unlock_status(),
            "unlock_requirements": self.get_unlock_requirements(),
        }

    def with_profile(self, profile: UnlockProfile) -> "ProgressivePolicy":
        """Create a new policy with a different unlock profile.

        Args:
            profile: The new unlock profile to use

        Returns:
            New ProgressivePolicy with the specified profile
        """
        return ProgressivePolicy(
            base_trust=self.base_trust,
            profile=profile,
            turn=self.turn,
            validation_passes=self.validation_passes,
            validation_failures=self.validation_failures,
        )
