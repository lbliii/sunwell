# src/sunwell/simulacrum/structural.py
"""Structural memory - understands DOCUMENT HIERARCHY.

Models headers, sections, and nesting relationships.
Enables queries like:
- "Content under 'Limitations' section"
- "All H2 sections"
- "Siblings of section X"

Part of RFC-014: Multi-Topology Memory.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class SectionType(Enum):
    """Semantic types of document sections."""
    
    # Diataxis-aligned
    OVERVIEW = "overview"
    TUTORIAL = "tutorial"
    HOWTO = "howto"
    REFERENCE = "reference"
    EXPLANATION = "explanation"
    
    # Common patterns
    INTRODUCTION = "introduction"
    INSTALLATION = "installation"
    QUICKSTART = "quickstart"
    CONFIGURATION = "configuration"
    API = "api"
    EXAMPLES = "examples"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    LIMITATIONS = "limitations"
    CHANGELOG = "changelog"
    
    # Meta
    UNKNOWN = "unknown"


@dataclass
class DocumentSection:
    """A section in a document hierarchy.
    
    Represents the tree structure:
    
    # RFC-014 (level=1)
    ## Summary (level=2)
    ## Design (level=2)
    ### Architecture (level=3)
    ### Components (level=3)
    """
    
    id: str
    """Unique identifier for this section."""
    
    title: str
    """Section heading text."""
    
    level: int
    """Heading level (1-6 for H1-H6)."""
    
    section_type: SectionType = SectionType.UNKNOWN
    """Semantic type of section (auto-detected or explicit)."""
    
    content: str = ""
    """Text content of this section (excluding subsections)."""
    
    line_start: int = 0
    """Starting line number."""
    
    line_end: int = 0
    """Ending line number."""
    
    # Hierarchy
    parent_id: str | None = None
    """ID of parent section."""
    
    child_ids: list[str] = field(default_factory=list)
    """IDs of child sections."""
    
    # Metadata
    word_count: int = 0
    """Word count of content (excluding children)."""
    
    has_code: bool = False
    """Contains code blocks."""
    
    has_admonitions: bool = False
    """Contains notes/warnings/etc."""


@dataclass
class DocumentTree:
    """Hierarchical document structure for structural retrieval.
    
    Enables queries like:
    - "Content under 'Limitations' section"
    - "All H2 sections"
    - "Siblings of section X"
    """
    
    file_path: str
    """Source file."""
    
    root_id: str = ""
    """ID of root (H1) section."""
    
    _sections: dict[str, DocumentSection] = field(default_factory=dict)
    """All sections by ID."""
    
    def add_section(self, section: DocumentSection) -> None:
        """Add a section to the tree."""
        self._sections[section.id] = section
        
        if section.level == 1 and not self.root_id:
            self.root_id = section.id
    
    def get_section(self, section_id: str) -> DocumentSection | None:
        """Get section by ID."""
        return self._sections.get(section_id)
    
    def get_children(self, section_id: str) -> list[DocumentSection]:
        """Get direct children of a section."""
        section = self._sections.get(section_id)
        if not section:
            return []
        return [self._sections[cid] for cid in section.child_ids if cid in self._sections]
    
    def get_ancestors(self, section_id: str) -> list[DocumentSection]:
        """Get all ancestors from section to root."""
        ancestors = []
        current = self._sections.get(section_id)
        
        while current and current.parent_id:
            parent = self._sections.get(current.parent_id)
            if parent:
                ancestors.append(parent)
                current = parent
            else:
                break
        
        return ancestors
    
    def get_siblings(self, section_id: str) -> list[DocumentSection]:
        """Get sibling sections (same parent, same level)."""
        section = self._sections.get(section_id)
        if not section or not section.parent_id:
            return []
        
        parent = self._sections.get(section.parent_id)
        if not parent:
            return []
        
        return [
            self._sections[cid]
            for cid in parent.child_ids
            if cid != section_id and cid in self._sections
        ]
    
    def get_section_path(self, section_id: str) -> list[str]:
        """Get path from root to section as list of titles."""
        ancestors = self.get_ancestors(section_id)
        section = self._sections.get(section_id)
        
        path = [a.title for a in reversed(ancestors)]
        if section:
            path.append(section.title)
        
        return path
    
    def find_by_title(self, title: str, fuzzy: bool = False) -> list[DocumentSection]:
        """Find sections by title."""
        results = []
        title_lower = title.lower()
        
        for section in self._sections.values():
            if fuzzy:
                if title_lower in section.title.lower():
                    results.append(section)
            else:
                if section.title.lower() == title_lower:
                    results.append(section)
        
        return results
    
    def find_by_type(self, section_type: SectionType) -> list[DocumentSection]:
        """Find all sections of a given type."""
        return [s for s in self._sections.values() if s.section_type == section_type]
    
    def find_by_level(self, level: int) -> list[DocumentSection]:
        """Find all sections at a given heading level."""
        return [s for s in self._sections.values() if s.level == level]
    
    def iter_depth_first(self) -> Iterator[DocumentSection]:
        """Iterate sections in depth-first order."""
        if not self.root_id:
            return
        
        def visit(section_id: str) -> Iterator[DocumentSection]:
            section = self._sections.get(section_id)
            if section:
                yield section
                for child_id in section.child_ids:
                    yield from visit(child_id)
        
        yield from visit(self.root_id)
    
    def to_dict(self) -> dict:
        """Serialize tree for storage."""
        return {
            "file_path": self.file_path,
            "root_id": self.root_id,
            "sections": {
                sid: {
                    "id": s.id,
                    "title": s.title,
                    "level": s.level,
                    "section_type": s.section_type.value,
                    "content": s.content,
                    "line_start": s.line_start,
                    "line_end": s.line_end,
                    "parent_id": s.parent_id,
                    "child_ids": s.child_ids,
                    "word_count": s.word_count,
                    "has_code": s.has_code,
                    "has_admonitions": s.has_admonitions,
                }
                for sid, s in self._sections.items()
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DocumentTree":
        """Deserialize tree from storage."""
        tree = cls(file_path=data["file_path"])
        tree.root_id = data.get("root_id", "")
        
        for sid, sdata in data.get("sections", {}).items():
            section = DocumentSection(
                id=sdata["id"],
                title=sdata["title"],
                level=sdata["level"],
                section_type=SectionType(sdata.get("section_type", "unknown")),
                content=sdata.get("content", ""),
                line_start=sdata.get("line_start", 0),
                line_end=sdata.get("line_end", 0),
                parent_id=sdata.get("parent_id"),
                child_ids=sdata.get("child_ids", []),
                word_count=sdata.get("word_count", 0),
                has_code=sdata.get("has_code", False),
                has_admonitions=sdata.get("has_admonitions", False),
            )
            tree._sections[sid] = section
        
        return tree


def infer_section_type(title: str) -> SectionType:
    """Infer semantic type from section title."""
    title_lower = title.lower()
    
    patterns = {
        SectionType.OVERVIEW: ["overview", "introduction", "about"],
        SectionType.INSTALLATION: ["install", "setup", "getting started"],
        SectionType.QUICKSTART: ["quickstart", "quick start", "getting started"],
        SectionType.CONFIGURATION: ["config", "configuration", "settings", "options"],
        SectionType.API: ["api", "reference", "specification"],
        SectionType.EXAMPLES: ["example", "examples", "usage", "demo"],
        SectionType.TROUBLESHOOTING: ["troubleshoot", "debug", "common issues", "faq"],
        SectionType.LIMITATIONS: ["limit", "caveat", "known issues", "restrictions"],
        SectionType.CHANGELOG: ["changelog", "history", "release notes", "what's new"],
    }
    
    for section_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in title_lower:
                return section_type
    
    return SectionType.UNKNOWN
