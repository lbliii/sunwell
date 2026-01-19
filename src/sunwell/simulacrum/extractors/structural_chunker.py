# src/sunwell/simulacrum/structural_chunker.py
"""Chunk documents by semantic structure, not arbitrary boundaries.

Key insight: A section under "## Limitations" is semantically different
from identical text under "## Features". Structure carries meaning.

Part of RFC-014: Multi-Topology Memory.
"""

from __future__ import annotations

import hashlib
import re

from sunwell.simulacrum.hierarchical.chunks import Chunk, ChunkType
from sunwell.simulacrum.topology.spatial import PositionType, SpatialContext
from sunwell.simulacrum.topology.structural import (
    DocumentSection,
    DocumentTree,
    SectionType,
    infer_section_type,
)


class StructuralChunker:
    """Chunk documents by semantic structure, not arbitrary boundaries.

    Key insight: A section under "## Limitations" is semantically different
    from identical text under "## Features". Structure carries meaning.
    """

    def __init__(
        self,
        min_chunk_size: int = 100,   # Min chars per chunk
        max_chunk_size: int = 4000,  # Max chars per chunk
        preserve_code_blocks: bool = True,
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.preserve_code_blocks = preserve_code_blocks

    def parse_document(self, file_path: str, content: str) -> DocumentTree:
        """Parse markdown into a document tree."""
        tree = DocumentTree(file_path=file_path)

        lines = content.split("\n")
        section_stack: list[DocumentSection] = []
        current_content_lines: list[str] = []

        for i, line in enumerate(lines, start=1):
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)

            if heading_match:
                # Finalize previous section's content
                if section_stack:
                    section_stack[-1].content = "\n".join(current_content_lines)
                    section_stack[-1].line_end = i - 1
                    section_stack[-1].word_count = len(section_stack[-1].content.split())
                    section_stack[-1].has_code = "```" in section_stack[-1].content

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                section_id = hashlib.md5(f"{file_path}:{i}:{title}".encode()).hexdigest()[:12]

                section = DocumentSection(
                    id=section_id,
                    title=title,
                    level=level,
                    section_type=infer_section_type(title),
                    line_start=i,
                )

                # Find parent (first section with lower level)
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()

                if section_stack:
                    section.parent_id = section_stack[-1].id
                    section_stack[-1].child_ids.append(section_id)

                tree.add_section(section)
                section_stack.append(section)
                current_content_lines = []
                i + 1
            else:
                current_content_lines.append(line)

        # Finalize last section
        if section_stack:
            section_stack[-1].content = "\n".join(current_content_lines)
            section_stack[-1].line_end = len(lines)
            section_stack[-1].word_count = len(section_stack[-1].content.split())
            section_stack[-1].has_code = "```" in section_stack[-1].content

        return tree

    def chunk_document(
        self,
        file_path: str,
        content: str,
    ) -> list[tuple[Chunk, SpatialContext, DocumentSection]]:
        """Chunk document by structure, returning enriched chunks.

        Returns list of (Chunk, SpatialContext, DocumentSection) tuples.
        """
        tree = self.parse_document(file_path, content)
        chunks = []

        for section in tree.iter_depth_first():
            if not section.content.strip():
                continue

            # Build spatial context
            section_path = tuple(tree.get_section_path(section.id))
            spatial = SpatialContext(
                position_type=PositionType.DOCUMENT,
                file_path=file_path,
                line_range=(section.line_start, section.line_end),
                section_path=section_path,
                heading_level=section.level,
            )

            # Check if section needs splitting
            if len(section.content) > self.max_chunk_size:
                sub_chunks = self._split_large_section(section, spatial, tree)
                chunks.extend(sub_chunks)
            else:
                chunk = Chunk(
                    id=f"struct_{section.id}",
                    chunk_type=ChunkType.MICRO,
                    turn_range=(section.line_start, section.line_end),
                    summary=f"{section_path[-1] if section_path else 'Untitled'}: {section.content[:100]}...",
                    token_count=int(section.word_count * 1.3),
                    themes=(section.section_type.value,) if section.section_type != SectionType.UNKNOWN else (),
                )
                chunks.append((chunk, spatial, section))

        return chunks

    def _split_large_section(
        self,
        section: DocumentSection,
        spatial: SpatialContext,
        tree: DocumentTree,
    ) -> list[tuple[Chunk, SpatialContext, DocumentSection]]:
        """Split a large section into smaller chunks.

        Respects code blocks and paragraph boundaries.
        """
        chunks = []
        content = section.content

        if self.preserve_code_blocks:
            # Split around code blocks
            parts = re.split(r'(```[\s\S]*?```)', content)
        else:
            parts = [content]

        current_chunk = ""
        chunk_idx = 0

        for part in parts:
            is_code_block = part.startswith("```")

            if is_code_block:
                # Code block: keep together if under limit, else truncate
                if len(part) <= self.max_chunk_size:
                    if len(current_chunk) + len(part) > self.max_chunk_size:
                        # Save current chunk first
                        if current_chunk.strip():
                            chunks.append(self._make_chunk(
                                section, spatial, tree, current_chunk, chunk_idx
                            ))
                            chunk_idx += 1
                        current_chunk = part
                    else:
                        current_chunk += part
                else:
                    # Very large code block: save as-is with truncation note
                    if current_chunk.strip():
                        chunks.append(self._make_chunk(
                            section, spatial, tree, current_chunk, chunk_idx
                        ))
                        chunk_idx += 1
                    truncated = part[:self.max_chunk_size - 50] + "\n... [truncated]\n```"
                    chunks.append(self._make_chunk(
                        section, spatial, tree, truncated, chunk_idx
                    ))
                    chunk_idx += 1
                    current_chunk = ""
            else:
                # Regular text: split by paragraphs
                paragraphs = part.split("\n\n")
                for para in paragraphs:
                    if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                        if current_chunk.strip():
                            chunks.append(self._make_chunk(
                                section, spatial, tree, current_chunk, chunk_idx
                            ))
                            chunk_idx += 1
                        current_chunk = para
                    else:
                        current_chunk += "\n\n" + para if current_chunk else para

        # Don't forget last chunk
        if current_chunk.strip():
            chunks.append(self._make_chunk(
                section, spatial, tree, current_chunk, chunk_idx
            ))

        return chunks

    def _make_chunk(
        self,
        section: DocumentSection,
        spatial: SpatialContext,
        tree: DocumentTree,
        content: str,
        idx: int,
    ) -> tuple[Chunk, SpatialContext, DocumentSection]:
        """Create a chunk tuple."""
        section_path = tree.get_section_path(section.id)

        chunk = Chunk(
            id=f"struct_{section.id}_{idx}",
            chunk_type=ChunkType.MICRO,
            turn_range=(section.line_start, section.line_end),
            summary=f"{section_path[-1] if section_path else 'Untitled'} (part {idx+1}): {content[:80]}...",
            token_count=int(len(content.split()) * 1.3),
            themes=(section.section_type.value,) if section.section_type != SectionType.UNKNOWN else (),
        )

        return (chunk, spatial, section)
