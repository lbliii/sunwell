"""Chunking for prose content (novels, stories, essays) - RFC-108.

Preserves narrative flow by chunking at natural boundaries:
- Section headers (# Chapter, ## Scene)
- Paragraph breaks (blank lines)
- Scene breaks (*** or ---)
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sunwell.knowledge.workspace.indexer import CodeChunk, _content_hash


@dataclass(frozen=True, slots=True)
class ProseChunk(CodeChunk):
    """Extended chunk for prose content."""

    section_title: str | None = None
    """Chapter/section title if applicable."""

    word_count: int = 0
    """Word count for this chunk."""


class ProseChunker:
    """Chunk prose by paragraphs and sections.

    Optimized for novels, stories, and essays where narrative flow
    matters more than code structure.
    """

    MIN_WORDS = 50  # Minimum words per chunk
    MAX_WORDS = 800  # Maximum words per chunk (about 1 page)
    OVERLAP_WORDS = 50  # Overlap for context continuity

    # Patterns
    SECTION_HEADER = re.compile(r"^#+\s+(.+)$", re.MULTILINE)
    SCENE_BREAK = re.compile(r"^(\*{3,}|—{3,}|-{3,})$", re.MULTILINE)
    PARAGRAPH_BREAK = re.compile(r"\n\s*\n")

    def chunk(self, file_path: Path) -> list[CodeChunk]:
        """Parse and chunk a prose file.

        Args:
            file_path: Path to the prose file.

        Returns:
            List of ProseChunk objects.
        """
        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return []

        # First, split by major sections (# headers)
        sections = self._split_by_headers(content)

        chunks: list[CodeChunk] = []

        for section_title, section_content, start_line in sections:
            # Then chunk each section by paragraphs
            section_chunks = self._chunk_section(
                file_path, section_title, section_content, start_line
            )
            chunks.extend(section_chunks)

        return chunks

    def _split_by_headers(
        self, content: str
    ) -> list[tuple[str | None, str, int]]:
        """Split content by markdown headers.

        Returns: [(title, content, start_line), ...]
        """
        lines = content.split("\n")
        sections: list[tuple[str | None, str, int]] = []
        current_title: str | None = None
        current_start = 1
        current_lines: list[str] = []

        for i, line in enumerate(lines, 1):
            header_match = self.SECTION_HEADER.match(line)
            if header_match:
                # Save previous section
                if current_lines:
                    sections.append(
                        (
                            current_title,
                            "\n".join(current_lines),
                            current_start,
                        )
                    )
                # Start new section
                current_title = header_match.group(1)
                current_start = i
                current_lines = [line]
            else:
                current_lines.append(line)

        # Don't forget the last section
        if current_lines:
            sections.append(
                (
                    current_title,
                    "\n".join(current_lines),
                    current_start,
                )
            )

        return sections

    def _chunk_section(
        self,
        file_path: Path,
        section_title: str | None,
        content: str,
        start_line: int,
    ) -> list[ProseChunk]:
        """Chunk a section into appropriately-sized pieces."""
        # Split by paragraphs
        paragraphs = self.PARAGRAPH_BREAK.split(content)

        chunks: list[ProseChunk] = []
        current_chunk_paragraphs: list[str] = []
        current_word_count = 0
        chunk_start_line = start_line

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_words = len(para.split())

            # If adding this paragraph exceeds max, save current chunk
            if (
                current_word_count + para_words > self.MAX_WORDS
                and current_chunk_paragraphs
            ):
                chunk_content = "\n\n".join(current_chunk_paragraphs)
                chunks.append(
                    ProseChunk(
                        file_path=file_path,
                        start_line=chunk_start_line,
                        end_line=chunk_start_line + chunk_content.count("\n"),
                        content=chunk_content,
                        chunk_type="prose",
                        name=section_title,
                        _content_hash=_content_hash(chunk_content),
                        section_title=section_title,
                        word_count=current_word_count,
                    )
                )

                # Start new chunk with overlap (keep last paragraph)
                if current_chunk_paragraphs:
                    current_chunk_paragraphs = [current_chunk_paragraphs[-1]]
                    current_word_count = len(current_chunk_paragraphs[0].split())
                else:
                    current_chunk_paragraphs = []
                    current_word_count = 0
                chunk_start_line = chunk_start_line + chunk_content.count("\n")

            current_chunk_paragraphs.append(para)
            current_word_count += para_words

        # Save final chunk
        if current_chunk_paragraphs and current_word_count >= self.MIN_WORDS:
            chunk_content = "\n\n".join(current_chunk_paragraphs)
            chunks.append(
                ProseChunk(
                    file_path=file_path,
                    start_line=chunk_start_line,
                    end_line=chunk_start_line + chunk_content.count("\n"),
                    content=chunk_content,
                    chunk_type="prose",
                    name=section_title,
                    _content_hash=_content_hash(chunk_content),
                    section_title=section_title,
                    word_count=current_word_count,
                )
            )

        return chunks
