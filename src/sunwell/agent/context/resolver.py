"""Context resolver for RFC-024.

Resolves @ references to actual content with size management.
"""


import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sunwell.context.constants import MAX_CONTEXT_CHARS, MAX_INLINE_CHARS, MAX_TOTAL_CONTEXT
from sunwell.context.ide import IDEContext
from sunwell.context.reference import ContextReference, ResolvedContext


@dataclass(frozen=True, slots=True)
class ExpandedTask:
    """Task with expanded context references."""

    original: str
    """Original task text with @ references."""

    expanded: str
    """Task with inline references replaced/summarized."""

    context_blocks: tuple[ResolvedContext, ...]
    """Large contexts that couldn't be inlined."""

    total_context_chars: int
    """Total size of context blocks."""


class ContextResolver:
    """Resolves @ references to actual content with size management.

    Security:
    - File paths are validated to stay within workspace
    - Environment variables use allowlist (see RFC-024)
    - Git operations are read-only

    Size management:
    - Small content (<500 chars) is inlined directly
    - Large content is returned as context blocks
    - Very large content is truncated with indicator
    """

    def __init__(
        self,
        workspace_root: Path,
        ide_context: IDEContext | None = None,
        max_inline: int = MAX_INLINE_CHARS,
        max_context: int = MAX_CONTEXT_CHARS,
    ):
        """Initialize resolver.

        Args:
            workspace_root: Root directory for file operations
            ide_context: Optional IDE context for @file, @selection, etc.
            max_inline: Max chars for inline expansion (default: 500)
            max_context: Max chars per context block (default: 8192)
        """
        self.workspace = workspace_root.resolve()
        self.ide = ide_context
        self.max_inline = max_inline
        self.max_context = max_context

    async def resolve(self, ref: ContextReference) -> ResolvedContext:
        """Resolve a reference to its content with size limits.

        Args:
            ref: The reference to resolve

        Returns:
            ResolvedContext with content and metadata
        """
        try:
            content = await self._fetch_content(ref)
        except Exception as e:
            return ResolvedContext.from_error(ref, str(e))

        original_size = len(content)
        truncated = False

        # Apply size limits
        if len(content) > self.max_context:
            content = content[:self.max_context]
            truncated = True

        return ResolvedContext(
            ref=ref,
            content=content,
            truncated=truncated,
            original_size=original_size if truncated else 0,
        )

    async def _fetch_content(self, ref: ContextReference) -> str:
        """Fetch raw content for a reference.

        Raises:
            ValueError: For unknown reference types or missing required data
            PermissionError: For security violations
            FileNotFoundError: For missing files
        """
        if ref.ref_type == "file":
            return await self._resolve_file(ref.modifier)

        elif ref.ref_type == "dir":
            return await self._resolve_dir(ref.modifier)

        elif ref.ref_type == "git":
            return await self._resolve_git(ref.modifier)

        elif ref.ref_type == "selection":
            return self._resolve_selection()

        elif ref.ref_type == "clipboard":
            return await self._read_clipboard()

        elif ref.ref_type == "env":
            return self._resolve_env(ref.modifier)

        raise ValueError(f"Unknown reference type: {ref.ref_type}")

    async def _resolve_file(self, path: str | None) -> str:
        """Resolve @file or @file:path."""
        if path:
            target = self.workspace / path
        else:
            # Use IDE focused file if available
            if self.ide and self.ide.focused_file:
                target = Path(self.ide.focused_file)
            else:
                raise ValueError(
                    "No file specified and no IDE context available. "
                    "Use @file:path/to/file.py to specify a file, or "
                    "provide IDE context via --ide-context or SUNWELL_IDE_CONTEXT."
                )

        if not target.exists():
            raise FileNotFoundError(f"File not found: {target}")

        # Security: ensure within workspace (if relative path was given)
        if path:
            try:
                target.resolve().relative_to(self.workspace.resolve())
            except ValueError:
                raise PermissionError(f"Path escapes workspace: {target}")

        return target.read_text(encoding="utf-8", errors="replace")

    async def _resolve_dir(self, path: str | None) -> str:
        """Resolve @dir or @dir:path to directory listing."""
        target = self.workspace / (path or ".")

        if not target.is_dir():
            raise ValueError(f"Not a directory: {target}")

        # Security: ensure within workspace
        try:
            target.resolve().relative_to(self.workspace.resolve())
        except ValueError:
            raise PermissionError(f"Path escapes workspace: {target}")

        files = []
        for f in sorted(target.iterdir()):
            if f.name.startswith("."):
                continue  # Skip hidden files
            suffix = "/" if f.is_dir() else ""
            files.append(f"{f.name}{suffix}")

        return "\n".join(files[:100]) or "(empty directory)"

    async def _resolve_git(self, modifier: str | None) -> str:
        """Resolve @git references."""
        # Check we're in a git repo
        if not (self.workspace / ".git").exists():
            raise ValueError("Not a git repository")

        if modifier is None or modifier == "status":
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, cwd=self.workspace, timeout=10
            )
            return result.stdout.strip() or "Working tree clean"

        elif modifier == "staged":
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True, text=True, cwd=self.workspace, timeout=30
            )
            return result.stdout.strip() or "Nothing staged"

        elif modifier == "branch":
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=self.workspace, timeout=5
            )
            return result.stdout.strip() or "(detached HEAD)"

        elif modifier == "diff":
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True, text=True, cwd=self.workspace, timeout=30
            )
            return result.stdout.strip() or "No unstaged changes"

        elif modifier.startswith("HEAD"):
            # @git:HEAD or @git:HEAD~3
            if "~" in modifier:
                # Show log of last N commits
                result = subprocess.run(
                    ["git", "log", modifier, "--oneline"],
                    capture_output=True, text=True, cwd=self.workspace, timeout=10
                )
            else:
                # Show current commit
                result = subprocess.run(
                    ["git", "log", "-1", "--format=%H %s"],
                    capture_output=True, text=True, cwd=self.workspace, timeout=5
                )

            if result.returncode != 0:
                raise ValueError(f"Invalid git reference: {modifier}")
            return result.stdout.strip()

        raise ValueError(f"Unknown git modifier: {modifier}")

    def _resolve_selection(self) -> str:
        """Resolve @selection from IDE context."""
        if not self.ide:
            raise ValueError(
                "No IDE context available for @selection. "
                "Provide context via --ide-context or SUNWELL_IDE_CONTEXT env var. "
                "See 'IDE Context Bridge' section for integration details."
            )

        if not self.ide.selection:
            raise ValueError(
                "No text selected in IDE. "
                "Select text in your editor before using @selection."
            )

        return self.ide.selection

    async def _read_clipboard(self) -> str:
        """Read clipboard contents."""
        try:
            # Try pbpaste (macOS)
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass

        try:
            # Try xclip (Linux)
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass

        try:
            # Try xsel (Linux alternative)
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass

        raise ValueError(
            "Could not read clipboard. Install xclip (Linux) or use macOS."
        )

    def _resolve_env(self, name: str | None) -> str:
        """Resolve @env:NAME with security restrictions."""
        from sunwell.tools.builtins import ENV_ALLOWLIST, ENV_BLOCKLIST_PATTERNS
        from sunwell.tools.handlers import _is_env_blocked

        if not name:
            raise ValueError("Environment variable name required: @env:NAME")

        # Check blocklist
        if _is_env_blocked(name, ENV_BLOCKLIST_PATTERNS):
            raise PermissionError(
                f"Environment variable '{name}' may contain secrets and cannot be accessed."
            )

        # Check allowlist
        if name not in ENV_ALLOWLIST:
            raise PermissionError(
                f"Environment variable '{name}' is not in the allowlist. "
                f"Only safe, non-secret variables are accessible."
            )

        value = os.environ.get(name)
        if value is None:
            return "(not set)"

        return value


async def preprocess_task(
    task: str,
    resolver: ContextResolver,
    max_total_context: int = MAX_TOTAL_CONTEXT,
) -> ExpandedTask:
    """Expand @ references in task before routing.

    Args:
        task: Task text that may contain @ references
        resolver: ContextResolver for resolving references
        max_total_context: Maximum total context size

    Returns:
        ExpandedTask with expanded text and context blocks
    """
    refs = ContextReference.parse(task)

    if not refs:
        return ExpandedTask(
            original=task,
            expanded=task,
            context_blocks=(),
            total_context_chars=0,
        )

    # Resolve each reference
    resolved = []
    for ref in refs:
        ctx = await resolver.resolve(ref)
        resolved.append(ctx)

    # Build expanded task with inline/context split
    expanded = task
    context_blocks = []
    total_chars = 0

    for ctx in resolved:
        if not ctx.success:
            # Error - keep the error message inline
            expanded = expanded.replace(ctx.ref.raw, ctx.summary)
        elif len(ctx.content) <= resolver.max_inline:
            # Small content: inline directly
            expanded = expanded.replace(ctx.ref.raw, ctx.content)
        else:
            # Large content: reference inline, full content as context block
            expanded = expanded.replace(ctx.ref.raw, ctx.summary)
            context_blocks.append(ctx)
            total_chars += len(ctx.content)

    # Check total context budget
    if total_chars > max_total_context:
        # Truncate oldest/largest contexts to fit
        context_blocks = _fit_context_budget(context_blocks, max_total_context)
        total_chars = sum(len(c.content) for c in context_blocks)

    return ExpandedTask(
        original=task,
        expanded=expanded,
        context_blocks=tuple(context_blocks),
        total_context_chars=total_chars,
    )


def _fit_context_budget(
    contexts: list[ResolvedContext],
    budget: int,
) -> list[ResolvedContext]:
    """Truncate contexts to fit within budget.

    Strategy: Keep smaller contexts, truncate larger ones.
    """
    # Sort by size (keep smaller ones)
    sorted_contexts = sorted(contexts, key=lambda c: len(c.content))

    result = []
    remaining = budget

    for ctx in sorted_contexts:
        if len(ctx.content) <= remaining:
            result.append(ctx)
            remaining -= len(ctx.content)
        elif remaining > 0:
            # Truncate this context to fit
            truncated = ResolvedContext(
                ref=ctx.ref,
                content=ctx.content[:remaining],
                truncated=True,
                original_size=len(ctx.content),
            )
            result.append(truncated)
            remaining = 0

    return result
