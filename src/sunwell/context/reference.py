"""Context reference parsing for RFC-024.

Grammar:
    reference     := "@" ref_type (":" ref_modifier)?
    ref_type      := "file" | "dir" | "selection" | "clipboard" | "git" | "env"
    ref_modifier  := identifier | path

Examples:
    @file              → currently focused file (from IDE context)
    @file:auth.py      → specific file
    @dir               → current directory listing
    @dir:src/          → specific directory listing
    @selection         → selected text (from IDE)
    @clipboard         → clipboard contents
    @git               → git status summary
    @git:staged        → staged changes diff
    @git:HEAD          → current commit diff
    @git:HEAD~3        → last 3 commits
    @git:branch        → current branch name
    @env:PATH          → environment variable (allowlist only)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Valid reference types (module-level constant)
_VALID_TYPES: frozenset[str] = frozenset({
    "file", "dir", "selection", "clipboard", "git", "env",
})

# Pattern to match @ references (module-level constant)
# Matches @word or @word:modifier (modifier can include paths with /, ~, etc.)
_PATTERN = re.compile(r'@(\w+)(?::([^\s,;"\'\]})]+))?')


@dataclass(frozen=True, slots=True)
class ContextReference:
    """Parsed @ reference."""
    
    ref_type: str
    """Reference type: file, dir, git, selection, clipboard, env."""
    
    modifier: str | None
    """Optional modifier after : (e.g., file path, git ref)."""
    
    raw: str
    """Original text (e.g., @file:auth.py)."""
    
    @classmethod
    def parse(cls, text: str) -> list[ContextReference]:
        """Extract all @ references from text.
        
        Args:
            text: Input text that may contain @ references
            
        Returns:
            List of parsed ContextReference objects
            
        Example:
            >>> refs = ContextReference.parse("review @file and check @git:staged")
            >>> len(refs)
            2
            >>> refs[0].ref_type
            'file'
            >>> refs[1].modifier
            'staged'
        """
        refs = []
        for match in _PATTERN.finditer(text):
            ref_type = match.group(1).lower()
            modifier = match.group(2)
            raw = match.group(0)
            
            # Only include valid reference types
            if ref_type in _VALID_TYPES:
                refs.append(cls(
                    ref_type=ref_type,
                    modifier=modifier,
                    raw=raw,
                ))
        
        return refs
    
    @classmethod
    def is_reference(cls, text: str) -> bool:
        """Check if text contains any @ references."""
        return bool(_PATTERN.search(text))
    
    def __str__(self) -> str:
        """Return the raw reference string."""
        return self.raw


@dataclass
class ResolvedContext:
    """Result of resolving a context reference."""
    
    ref: ContextReference
    """The original reference that was resolved."""
    
    content: str
    """The resolved content."""
    
    truncated: bool = False
    """Whether content was truncated due to size limits."""
    
    original_size: int = 0
    """Original size before truncation (0 if not truncated)."""
    
    error: str | None = None
    """Error message if resolution failed."""
    
    @property
    def success(self) -> bool:
        """Whether resolution was successful."""
        return self.error is None
    
    @property
    def summary(self) -> str:
        """Short summary for inline use."""
        if self.error:
            return f"[{self.ref.raw}: ERROR - {self.error}]"
        if self.truncated:
            return f"[{self.ref.raw}: {self.original_size:,} chars, truncated to {len(self.content):,}]"
        return f"[{self.ref.raw}: {len(self.content):,} chars]"
    
    @classmethod
    def from_error(cls, ref: ContextReference, error: str) -> ResolvedContext:
        """Create a failed resolution result."""
        return cls(
            ref=ref,
            content=f"[Error resolving {ref.raw}: {error}]",
            error=error,
        )
