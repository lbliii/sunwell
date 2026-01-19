# src/sunwell/simulacrum/spatial_extractor.py
"""Extract spatial context from content sources.

Supports:
- Markdown documents (section paths, heading levels)
- Python code (module paths, class/function names)

Part of RFC-014: Multi-Topology Memory.
"""

from __future__ import annotations

import re
from pathlib import Path

from sunwell.simulacrum.topology.spatial import SpatialContext, PositionType


class SpatialExtractor:
    """Extract spatial context from content sources."""
    
    @staticmethod
    def from_markdown(
        file_path: str,
        content: str,
        line_start: int = 1,
    ) -> list[tuple[str, SpatialContext]]:
        """Extract chunks with spatial context from markdown.
        
        Returns list of (chunk_text, spatial_context) pairs.
        """
        chunks = []
        current_section_path: list[str] = []
        current_level = 0
        current_chunk_lines: list[str] = []
        chunk_start_line = line_start
        
        lines = content.split("\n")
        
        for i, line in enumerate(lines, start=line_start):
            # Detect heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # Save previous chunk
                if current_chunk_lines:
                    chunk_text = "\n".join(current_chunk_lines)
                    if chunk_text.strip():
                        ctx = SpatialContext(
                            position_type=PositionType.DOCUMENT,
                            file_path=file_path,
                            line_range=(chunk_start_line, i - 1),
                            section_path=tuple(current_section_path),
                            heading_level=current_level,
                        )
                        chunks.append((chunk_text, ctx))
                
                # Update section path
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Pop sections at same or higher level
                while len(current_section_path) >= level:
                    current_section_path.pop()
                
                current_section_path.append(title)
                current_level = level
                current_chunk_lines = [line]
                chunk_start_line = i
            else:
                current_chunk_lines.append(line)
        
        # Don't forget last chunk
        if current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            if chunk_text.strip():
                ctx = SpatialContext(
                    position_type=PositionType.DOCUMENT,
                    file_path=file_path,
                    line_range=(chunk_start_line, len(lines)),
                    section_path=tuple(current_section_path),
                    heading_level=current_level,
                )
                chunks.append((chunk_text, ctx))
        
        return chunks
    
    @staticmethod
    def from_python(
        file_path: str,
        content: str,
    ) -> list[tuple[str, SpatialContext]]:
        """Extract chunks with spatial context from Python code.
        
        Uses AST to identify module/class/function boundaries.
        """
        import ast
        
        chunks = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to treating entire file as one chunk
            return [(content, SpatialContext(
                position_type=PositionType.CODE,
                file_path=file_path,
                module_path=file_path.replace("/", ".").replace(".py", ""),
            ))]
        
        module_path = file_path.replace("/", ".").replace(".py", "")
        if module_path.startswith("src."):
            module_path = module_path[4:]
        
        def extract_node(
            node: ast.AST,
            class_name: str | None = None,
            depth: int = 0,
        ) -> None:
            """Recursively extract code chunks."""
            
            if isinstance(node, ast.ClassDef):
                # Extract class
                chunk_text = ast.get_source_segment(content, node)
                if chunk_text:
                    ctx = SpatialContext(
                        position_type=PositionType.CODE,
                        file_path=file_path,
                        line_range=(node.lineno, node.end_lineno or node.lineno),
                        module_path=module_path,
                        class_name=node.name,
                        scope_depth=depth,
                    )
                    chunks.append((chunk_text, ctx))
                
                # Recurse into class body
                for child in node.body:
                    extract_node(child, class_name=node.name, depth=depth + 1)
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Extract function
                chunk_text = ast.get_source_segment(content, node)
                if chunk_text:
                    ctx = SpatialContext(
                        position_type=PositionType.CODE,
                        file_path=file_path,
                        line_range=(node.lineno, node.end_lineno or node.lineno),
                        module_path=module_path,
                        class_name=class_name,
                        function_name=node.name,
                        scope_depth=depth,
                    )
                    chunks.append((chunk_text, ctx))
        
        # Extract top-level items
        for node in ast.iter_child_nodes(tree):
            extract_node(node, depth=0)
        
        return chunks
    
    @staticmethod
    def from_url(
        url: str,
        content: str,
        anchor: str | None = None,
    ) -> SpatialContext:
        """Create spatial context for external content."""
        return SpatialContext(
            position_type=PositionType.EXTERNAL,
            url=url,
            anchor=anchor,
        )
    
    @staticmethod
    def from_conversation(
        turn_index: int,
        content: str,
    ) -> SpatialContext:
        """Create spatial context for conversation content."""
        return SpatialContext(
            position_type=PositionType.CONVERSATION,
            line_range=(turn_index, turn_index),
        )
    
    @classmethod
    def extract_from_file(
        cls,
        file_path: str | Path,
    ) -> list[tuple[str, SpatialContext]]:
        """Auto-detect file type and extract chunks with spatial context."""
        path = Path(file_path)
        
        if not path.exists():
            return []
        
        content = path.read_text()
        file_path_str = str(path)
        
        if path.suffix in {".md", ".markdown", ".rst", ".txt"}:
            return cls.from_markdown(file_path_str, content)
        elif path.suffix == ".py":
            return cls.from_python(file_path_str, content)
        else:
            # Fallback: single chunk with basic context
            return [(content, SpatialContext(
                position_type=PositionType.DOCUMENT,
                file_path=file_path_str,
            ))]
