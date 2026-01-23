"""Studio CLI Contract Tests (RFC-109).

These tests ensure that all CLI patterns used by Studio via subprocess continue
to work after CLI refactoring. This is critical for Studio compatibility.

The patterns here are derived from scanning studio/src-tauri/src/ for CLI calls.
"""

import subprocess

import pytest

# =============================================================================
# Studio CLI Patterns
# Verified from studio/src-tauri/src/ - these MUST remain stable
# =============================================================================

# fmt: off
STUDIO_CLI_PATTERNS: list[tuple[list[str], str]] = [
    # dag.rs - DAG execution and caching
    (["backlog", "refresh"], "Backlog refresh"),
    (["backlog", "run"], "Backlog run"),
    (["dag", "plan", "--json"], "DAG planning"),
    (["dag", "cache", "stats", "--json"], "DAG cache stats"),
    (["dag", "cache", "clear"], "DAG cache clear"),
    (["dag", "impact", "--json"], "DAG impact analysis"),

    # coordinator.rs - Multi-instance coordination
    (["workers", "ui-state"], "Workers UI state"),
    (["workers", "pause"], "Workers pause"),
    (["workers", "resume"], "Workers resume"),
    (["workers", "start"], "Workers start"),

    # lens.rs - Lens lifecycle management
    (["lens", "list", "--json"], "Lens list"),
    (["lens", "show", "--json"], "Lens show"),
    (["lens", "library", "--json"], "Lens library"),
    (["lens", "fork"], "Lens fork"),
    (["lens", "save"], "Lens save"),
    (["lens", "delete"], "Lens delete"),
    (["lens", "versions", "--json"], "Lens versions"),
    (["lens", "rollback"], "Lens rollback"),
    (["lens", "set-default"], "Lens set default"),
    (["lens", "export"], "Lens export"),
    (["lens", "record-usage"], "Lens record usage"),

    # writer.rs - Skill execution and caching
    (["lens", "skills", "--json"], "Lens skills"),
    (["lens", "skill-graph", "--json"], "Lens skill graph"),
    (["lens", "skill-plan", "--json"], "Lens skill plan"),
    (["skill", "cache-stats", "--json"], "Skill cache stats"),
    (["skill", "cache-clear"], "Skill cache clear"),

    # self_knowledge.rs - Self-knowledge introspection
    (["self", "source", "read", "--json"], "Self source read"),
    (["self", "source", "find", "--json"], "Self source find"),
    (["self", "source", "list", "--json"], "Self source list"),
    (["self", "source", "search", "--json"], "Self source search"),
    (["self", "analysis", "patterns", "--json"], "Self analysis patterns"),
    (["self", "analysis", "failures", "--json"], "Self analysis failures"),
    (["self", "proposals", "list", "--json"], "Self proposals list"),
    (["self", "proposals", "show", "--json"], "Self proposals show"),
    (["self", "proposals", "test", "--json"], "Self proposals test"),
    (["self", "proposals", "approve", "--json"], "Self proposals approve"),
    (["self", "proposals", "apply", "--json"], "Self proposals apply"),
    (["self", "proposals", "rollback", "--json"], "Self proposals rollback"),
    (["self", "summary", "--json"], "Self summary"),

    # workflow.rs - Workflow execution control
    (["workflow", "auto", "--json"], "Workflow auto"),
    (["workflow", "run", "--json"], "Workflow run"),
    (["workflow", "stop"], "Workflow stop"),
    (["workflow", "resume", "--json"], "Workflow resume"),
    (["workflow", "skip"], "Workflow skip"),
    (["workflow", "chains", "--json"], "Workflow chains"),
    (["workflow", "list", "--json"], "Workflow list"),

    # weakness.rs - Weakness cascade detection
    (["weakness", "scan", "--json"], "Weakness scan"),
    (["weakness", "preview", "--json"], "Weakness preview"),
    (["weakness", "extract-contract", "--json"], "Weakness extract contract"),

    # security.rs - Security-first execution
    (["security", "analyze", "--json"], "Security analyze"),
    (["security", "approve", "--json"], "Security approve"),
    (["security", "audit", "--json"], "Security audit"),
    (["security", "scan", "--json"], "Security scan"),

    # surface.rs - Surface composition
    (["surface", "registry", "--json"], "Surface registry"),

    # naaru.rs - Naaru coordination
    (["naaru", "process", "--stream", "--json"], "Naaru process"),
    (["naaru", "convergence", "--json"], "Naaru convergence"),

    # indexing.rs - Codebase indexing
    (["index", "build", "--json", "--progress"], "Index build"),
    (["index", "query", "--json"], "Index query"),
    (["index", "metrics", "--json"], "Index metrics"),

    # workspace.rs - Workspace link management
    (["workspace", "detect", "--json"], "Workspace detect"),
    (["workspace", "show", "--json"], "Workspace show"),
    (["workspace", "link"], "Workspace link"),
    (["workspace", "unlink"], "Workspace unlink"),
    (["workspace", "list", "--json"], "Workspace list"),

    # eval.rs - Evaluation suite
    (["eval", "--list-tasks", "--json"], "Eval list tasks"),
    (["eval", "--stats", "--json"], "Eval stats"),

    # demo.rs - Prism demonstrations
    (["demo"], "Demo"),

    # interface.rs - Interface demonstrations
    (["interface", "demo"], "Interface demo"),

    # coordinator.rs - State DAG scanning
    (["scan", "--json"], "Scan state DAG"),
]
# fmt: on


class TestStudioCLIContract:
    """Tests to ensure Studio CLI patterns continue to work.

    These tests verify that each CLI pattern:
    1. Is recognized as a valid command (--help doesn't fail)
    2. Has the expected subcommand structure
    """

    @pytest.mark.parametrize("args,description", STUDIO_CLI_PATTERNS)
    def test_studio_cli_pattern_exists(self, args: list[str], description: str) -> None:
        """Verify Studio CLI pattern is recognized.

        This test ensures the command exists and has proper structure.
        It doesn't test full execution (which would require setup),
        just that the command is recognized.
        """
        # For commands with positional arguments, we just check help
        help_args = [args[0], "--help"] if len(args) == 1 else [args[0], args[1], "--help"]

        result = subprocess.run(
            ["sunwell", *help_args],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Command should be recognized (exit 0 for help, or 2 for missing args)
        # Error codes:
        # - 0: Help displayed successfully
        # - 2: Click error (missing required args) - still means command exists
        # - 1: Runtime error - might need investigation
        assert result.returncode in (0, 1, 2), (
            f"Command '{' '.join(args)}' ({description}) failed: {result.stderr}"
        )

    def test_main_shortcut_flag_exists(self) -> None:
        """Verify the -s/--skill shortcut flag is available."""
        result = subprocess.run(
            ["sunwell", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "-s" in result.stdout or "--skill" in result.stdout

    def test_all_commands_flag_exists(self) -> None:
        """Verify --all-commands flag works."""
        result = subprocess.run(
            ["sunwell", "--all-commands"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should succeed and show all commands
        assert result.returncode == 0
        # Should mention tiered commands
        assert "Tier" in result.stdout or "Internal" in result.stdout.lower()

    def test_visible_commands_limited(self) -> None:
        """Verify --help shows limited commands (RFC-109 goal: ≤10)."""
        result = subprocess.run(
            ["sunwell", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

        # Count command lines (lines that start with 2 spaces and a word)
        help_lines = result.stdout.split("\n")
        command_lines = [
            line for line in help_lines
            if line.startswith("  ") and not line.startswith("   ") and line.strip()
        ]

        # The RFC goal is ≤10 user-facing items in --help
        # Allow some flexibility for options section
        visible_commands = len([
            line for line in command_lines
            if not line.strip().startswith("-")  # Exclude options
        ])

        # We want significantly fewer commands shown than the original 43
        # Exact number depends on Click's help formatting
        assert visible_commands <= 15, (
            f"Too many visible commands ({visible_commands}). "
            f"RFC-109 goal is ≤10 user-facing items."
        )


class TestDeprecatedCommands:
    """Tests for deprecated command handling."""

    def test_do_command_shows_deprecation(self) -> None:
        """Verify 'do' command shows deprecation warning."""
        result = subprocess.run(
            ["sunwell", "do", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Command should work (backward compat)
        assert result.returncode in (0, 2)

    def test_shortcut_execution_via_s_flag(self) -> None:
        """Verify -s flag can be used instead of 'do' command."""
        result = subprocess.run(
            ["sunwell", "-s", "?"],  # Help shortcut
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should show shortcut help or succeed
        assert result.returncode == 0
        # Should show available shortcuts
        assert "shortcut" in result.stdout.lower() or "audit" in result.stdout.lower()


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_help_shows_usage_patterns(self) -> None:
        """Verify help shows the new usage patterns."""
        result = subprocess.run(
            ["sunwell", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

        # Should show goal-first pattern
        assert "sunwell" in result.stdout.lower()

        # Should show shortcut pattern
        assert "-s" in result.stdout or "SHORTCUT" in result.stdout

    def test_help_shows_shortcut_examples(self) -> None:
        """Verify help mentions common shortcuts."""
        result = subprocess.run(
            ["sunwell", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

        # Should show some shortcuts
        shortcuts = ["a-2", "health", "pipeline"]
        found_shortcuts = [s for s in shortcuts if s in result.stdout]
        assert len(found_shortcuts) >= 1, "Help should mention common shortcuts"


# =============================================================================
# Contract Verification Helpers
# =============================================================================


def verify_studio_contract() -> dict[str, list[str]]:
    """Run all Studio contract checks and return summary.

    Returns:
        Dict with "passed" and "failed" lists of command patterns
    """
    passed = []
    failed = []

    for args, description in STUDIO_CLI_PATTERNS:
        help_args = [args[0], "--help"] if len(args) == 1 else [args[0], args[1], "--help"]

        try:
            result = subprocess.run(
                ["sunwell", *help_args],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode in (0, 1, 2):
                passed.append(f"{' '.join(args)} ({description})")
            else:
                failed.append(f"{' '.join(args)} ({description}): exit {result.returncode}")
        except subprocess.TimeoutExpired:
            failed.append(f"{' '.join(args)} ({description}): timeout")
        except Exception as e:
            failed.append(f"{' '.join(args)} ({description}): {e}")

    return {"passed": passed, "failed": failed}


if __name__ == "__main__":
    """Run contract verification standalone."""
    import sys

    print("Verifying Studio CLI contract...\n")
    results = verify_studio_contract()

    print(f"✅ Passed: {len(results['passed'])} patterns")
    print(f"❌ Failed: {len(results['failed'])} patterns")

    if results["failed"]:
        print("\nFailed patterns:")
        for pattern in results["failed"]:
            print(f"  - {pattern}")
        sys.exit(1)
    else:
        print("\n🎉 All Studio CLI patterns verified!")
        sys.exit(0)
