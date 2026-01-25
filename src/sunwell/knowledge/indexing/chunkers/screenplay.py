"""Chunking for screenplays (Fountain format) - RFC-108.

Chunks by scene - the natural unit of a screenplay.
Each INT./EXT. slugline starts a new chunk.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sunwell.knowledge.workspace.indexer import CodeChunk, _content_hash


@dataclass(frozen=True, slots=True)
class SceneChunk(CodeChunk):
    """A scene from a screenplay."""

    slugline: str | None = None
    """Scene heading (INT./EXT. line)."""

    scene_number: int | None = None
    """Scene number if present."""


class ScreenplayChunker:
    """Chunk screenplays by scene.

    Recognizes Fountain format (.fountain) and generic screenplay patterns.
    """

    # Fountain scene heading pattern
    # Matches: INT. LOCATION - TIME, EXT. LOCATION - TIME, etc.
    SLUGLINE = re.compile(
        r"^(INT\.|EXT\.|INT/EXT\.|I/E\.|EST\.)\s*(.+)$", re.MULTILINE | re.IGNORECASE
    )

    # Scene transitions
    TRANSITION = re.compile(
        r"^(FADE IN:|FADE OUT\.|FADE TO:|CUT TO:|DISSOLVE TO:)",
        re.MULTILINE | re.IGNORECASE,
    )

    def chunk(self, file_path: Path) -> list[CodeChunk]:
        """Parse and chunk a screenplay file.

        Args:
            file_path: Path to the screenplay file.

        Returns:
            List of SceneChunk objects.
        """
        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return []

        scenes = self._split_by_scenes(content, file_path)
        return scenes

    def _split_by_scenes(
        self, content: str, file_path: Path
    ) -> list[SceneChunk]:
        """Split screenplay into scenes."""
        lines = content.split("\n")
        chunks: list[SceneChunk] = []

        current_scene_lines: list[str] = []
        current_slugline: str | None = None
        current_start = 1
        scene_number = 0

        for i, line in enumerate(lines, 1):
            slugline_match = self.SLUGLINE.match(line.strip())

            if slugline_match:
                # Save previous scene
                if current_scene_lines:
                    scene_content = "\n".join(current_scene_lines)
                    if scene_content.strip():
                        chunks.append(
                            SceneChunk(
                                file_path=file_path,
                                start_line=current_start,
                                end_line=i - 1,
                                content=scene_content,
                                chunk_type="scene",
                                name=current_slugline,
                                _content_hash=_content_hash(scene_content),
                                slugline=current_slugline,
                                scene_number=scene_number if scene_number > 0 else None,
                            )
                        )

                # Start new scene
                scene_number += 1
                current_slugline = line.strip()
                current_start = i
                current_scene_lines = [line]
            else:
                current_scene_lines.append(line)

        # Don't forget the last scene
        if current_scene_lines:
            scene_content = "\n".join(current_scene_lines)
            if scene_content.strip():
                chunks.append(
                    SceneChunk(
                        file_path=file_path,
                        start_line=current_start,
                        end_line=len(lines),
                        content=scene_content,
                        chunk_type="scene",
                        name=current_slugline,
                        _content_hash=_content_hash(scene_content),
                        slugline=current_slugline,
                        scene_number=scene_number if scene_number > 0 else None,
                    )
                )

        return chunks
