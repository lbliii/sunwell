"""Patch file tool using unified diff format."""

import re

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

# Regex for parsing unified diff hunk headers
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _parse_unified_diff(diff: str) -> list[tuple[int, int, int, int, list[str]]]:
    """Parse a unified diff into hunks.

    Returns list of (old_start, old_count, new_start, new_count, lines) tuples.
    """
    hunks: list[tuple[int, int, int, int, list[str]]] = []
    lines = diff.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip file headers (--- and +++)
        if line.startswith("---") or line.startswith("+++"):
            i += 1
            continue

        # Look for hunk header
        match = _HUNK_HEADER_RE.match(line)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1

            # Collect hunk lines
            hunk_lines: list[str] = []
            i += 1
            while i < len(lines):
                hunk_line = lines[i]
                if (
                    hunk_line.startswith("@@")
                    or hunk_line.startswith("---")
                    or hunk_line.startswith("+++")
                ):
                    break
                if hunk_line.startswith(("-", "+", " ")) or hunk_line == "":
                    hunk_lines.append(hunk_line)
                i += 1

            hunks.append((old_start, old_count, new_start, new_count, hunk_lines))
        else:
            i += 1

    return hunks


def _apply_hunks(
    content: str, hunks: list[tuple[int, int, int, int, list[str]]]
) -> str:
    """Apply diff hunks to file content."""
    lines = content.split("\n")

    # Apply hunks in reverse order to avoid line number shifts
    for old_start, old_count, new_start, new_count, hunk_lines in reversed(hunks):
        # Convert to 0-indexed
        start_idx = old_start - 1

        # Parse hunk lines into old and new
        old_lines: list[str] = []
        new_lines: list[str] = []

        for diff_line in hunk_lines:
            if diff_line.startswith("-"):
                old_lines.append(diff_line[1:])
            elif diff_line.startswith("+"):
                new_lines.append(diff_line[1:])
            elif diff_line.startswith(" "):
                old_lines.append(diff_line[1:])
                new_lines.append(diff_line[1:])
            elif diff_line == "":
                old_lines.append("")
                new_lines.append("")

        # Check that old lines match
        actual_old = lines[start_idx : start_idx + len(old_lines)]
        if actual_old != old_lines:
            # Try fuzzy match with stripped whitespace
            stripped_actual = [ln.rstrip() for ln in actual_old]
            stripped_expected = [ln.rstrip() for ln in old_lines]
            if stripped_actual != stripped_expected:
                raise ValueError(
                    f"Hunk at line {old_start} doesn't match file content.\n"
                    f"Expected:\n{chr(10).join(old_lines[:5])}\n"
                    f"Found:\n{chr(10).join(actual_old[:5])}"
                )

        # Replace old lines with new lines
        lines[start_idx : start_idx + len(old_lines)] = new_lines

    return "\n".join(lines)


@tool_metadata(
    name="patch_file",
    simple_description="Apply unified diff patch to a file",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use patch_file to apply unified diff format patches. Include @@ headers and context lines.",
)
class PatchFileTool(BaseTool):
    """Apply a unified diff patch to a file."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to patch (relative to workspace)",
            },
            "diff": {
                "type": "string",
                "description": "Unified diff content with @@ headers",
            },
        },
        "required": ["path", "diff"],
    }

    async def execute(self, arguments: dict) -> str:
        user_path = arguments["path"]
        diff = arguments["diff"]

        path = self.resolve_path(user_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {user_path}. Use write_file to create new files."
            )
        if not path.is_file():
            raise ValueError(f"Not a file: {user_path}")

        # Read original content
        content = path.read_text(encoding="utf-8")
        old_lines = content.count("\n") + 1 if content else 0

        # Create backup before patching
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(content, encoding="utf-8")

        # Parse and apply the diff
        hunks = _parse_unified_diff(diff)
        if not hunks:
            return "No valid hunks found in diff. Ensure diff uses unified format with @@ headers."

        new_content = _apply_hunks(content, hunks)

        # Write patched content
        path.write_text(new_content, encoding="utf-8")

        new_lines = new_content.count("\n") + 1 if new_content else 0

        return (
            f"✓ Patched {user_path}\n"
            f"  Applied {len(hunks)} hunk(s)\n"
            f"  Lines: {old_lines} → {new_lines}\n"
            f"  Backup: {backup_path.name}"
        )
