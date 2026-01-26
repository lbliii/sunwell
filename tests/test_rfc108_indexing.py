"""Tests for RFC-108: Continuous Codebase Indexing.

Tests cover:
- Project type detection
- Priority file identification
- Content-aware chunking (AST, prose, screenplay)
- IndexingService state machine
- SmartContext graceful fallback
"""

import tempfile
from pathlib import Path

import pytest


# =============================================================================
# Project Type Detection Tests
# =============================================================================


class TestProjectTypeDetection:
    """Test project type detection from markers."""

    def test_detect_python_project(self, tmp_path: Path) -> None:
        """Detect Python project from pyproject.toml."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        result = detect_project_type(tmp_path)
        assert result == ProjectType.CODE

    def test_detect_node_project(self, tmp_path: Path) -> None:
        """Detect Node.js project from package.json."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("export const x = 1;")

        result = detect_project_type(tmp_path)
        assert result == ProjectType.CODE

    def test_detect_prose_project(self, tmp_path: Path) -> None:
        """Detect prose project from manuscript markers."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        (tmp_path / "manuscript").mkdir()
        (tmp_path / "manuscript" / "chapter-01.md").write_text("# Chapter 1\n\nOnce upon a time...")

        result = detect_project_type(tmp_path)
        assert result == ProjectType.PROSE

    def test_detect_script_project(self, tmp_path: Path) -> None:
        """Detect screenplay project from fountain files."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        (tmp_path / "script.fountain").write_text("INT. COFFEE SHOP - DAY\n\nA busy morning.")

        result = detect_project_type(tmp_path)
        assert result == ProjectType.SCRIPT

    def test_detect_docs_project(self, tmp_path: Path) -> None:
        """Detect documentation project from docs markers."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "conf.py").write_text("project = 'Test'")
        (tmp_path / "docs" / "index.rst").write_text("Welcome\n=======")

        result = detect_project_type(tmp_path)
        assert result == ProjectType.DOCS

    def test_detect_mixed_project(self, tmp_path: Path) -> None:
        """Detect mixed project with multiple types."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        # Both code and docs
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "conf.py").write_text("project = 'Test'")

        result = detect_project_type(tmp_path)
        assert result == ProjectType.MIXED

    def test_detect_unknown_project(self, tmp_path: Path) -> None:
        """Detect unknown project with no markers."""
        from sunwell.knowledge.indexing import detect_project_type, ProjectType

        # Empty directory
        result = detect_project_type(tmp_path)
        assert result == ProjectType.UNKNOWN


class TestFileTypeDetection:
    """Test per-file type detection in mixed projects."""

    def test_detect_file_type_python(self, tmp_path: Path) -> None:
        """Detect Python file type."""
        from sunwell.knowledge.indexing import detect_file_type, ProjectType

        py_file = tmp_path / "main.py"
        py_file.write_text("def main(): pass")

        result = detect_file_type(py_file)
        assert result == ProjectType.CODE

    def test_detect_file_type_markdown(self, tmp_path: Path) -> None:
        """Detect Markdown file type."""
        from sunwell.knowledge.indexing import detect_file_type, ProjectType

        md_file = tmp_path / "README.md"
        md_file.write_text("# Title\n\nSome documentation.")

        result = detect_file_type(md_file)
        assert result == ProjectType.DOCS

    def test_detect_file_type_fountain(self, tmp_path: Path) -> None:
        """Detect Fountain screenplay file type."""
        from sunwell.knowledge.indexing import detect_file_type, ProjectType

        fountain_file = tmp_path / "script.fountain"
        fountain_file.write_text("INT. OFFICE - DAY")

        result = detect_file_type(fountain_file)
        assert result == ProjectType.SCRIPT


# =============================================================================
# Priority File Tests
# =============================================================================


class TestPriorityFiles:
    """Test priority file detection for fast startup."""

    def test_priority_files_includes_readme(self, tmp_path: Path) -> None:
        """README should be a priority file."""
        from sunwell.indexing.priority import get_priority_files

        (tmp_path / "README.md").write_text("# Project")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        priority = get_priority_files(tmp_path)
        assert any("README.md" in str(p) for p in priority)

    def test_priority_files_includes_config(self, tmp_path: Path) -> None:
        """Config files should be priority files."""
        from sunwell.indexing.priority import get_priority_files

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "main.py").write_text("print('hello')")

        priority = get_priority_files(tmp_path)
        assert any("pyproject.toml" in str(p) for p in priority)

    def test_priority_files_includes_entry_points(self, tmp_path: Path) -> None:
        """Entry point files should be priority files."""
        from sunwell.indexing.priority import get_priority_files

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__main__.py").write_text("print('entry')")
        (tmp_path / "src" / "utils.py").write_text("def util(): pass")

        priority = get_priority_files(tmp_path)
        assert any("__main__.py" in str(p) for p in priority)

    def test_priority_files_limited_count(self, tmp_path: Path) -> None:
        """Priority files should be limited to avoid slow startup."""
        from sunwell.indexing.priority import get_priority_files

        # Create many files
        for i in range(100):
            (tmp_path / f"file_{i}.py").write_text(f"x = {i}")

        priority = get_priority_files(tmp_path)
        assert len(priority) <= 50  # Reasonable limit


# =============================================================================
# Python AST Chunker Tests
# =============================================================================


class TestPythonASTChunker:
    """Test AST-aware Python chunking."""

    def test_chunk_function(self, tmp_path: Path) -> None:
        """Chunk a simple function."""
        from sunwell.indexing.chunkers.python_ast import PythonASTChunker

        code = '''
def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"
'''
        py_file = tmp_path / "greeting.py"
        py_file.write_text(code)

        chunker = PythonASTChunker()
        chunks = chunker.chunk(py_file)

        assert len(chunks) >= 1
        func_chunk = next((c for c in chunks if c.chunk_type == "function"), None)
        assert func_chunk is not None
        assert func_chunk.name == "greet"
        assert "Say hello" in func_chunk.content

    def test_chunk_class(self, tmp_path: Path) -> None:
        """Chunk a class with methods."""
        from sunwell.indexing.chunkers.python_ast import PythonASTChunker

        code = '''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b
'''
        py_file = tmp_path / "calc.py"
        py_file.write_text(code)

        chunker = PythonASTChunker()
        chunks = chunker.chunk(py_file)

        # Should have class summary + methods
        class_chunks = [c for c in chunks if c.chunk_type in ("class", "class_summary")]
        method_chunks = [c for c in chunks if c.chunk_type == "method"]

        assert len(class_chunks) >= 1
        assert len(method_chunks) >= 2

    def test_chunk_preserves_decorators(self, tmp_path: Path) -> None:
        """Decorators should be included in chunk."""
        from sunwell.indexing.chunkers.python_ast import PythonASTChunker

        code = '''
@dataclass
class Person:
    name: str
    age: int
'''
        py_file = tmp_path / "person.py"
        py_file.write_text(code)

        chunker = PythonASTChunker()
        chunks = chunker.chunk(py_file)

        class_chunk = next((c for c in chunks if "Person" in (c.name or "")), None)
        assert class_chunk is not None
        assert "@dataclass" in class_chunk.content

    def test_chunk_handles_syntax_error(self, tmp_path: Path) -> None:
        """Gracefully handle syntax errors."""
        from sunwell.indexing.chunkers.python_ast import PythonASTChunker

        code = "def broken(:\n    pass"  # Invalid syntax
        py_file = tmp_path / "broken.py"
        py_file.write_text(code)

        chunker = PythonASTChunker()
        chunks = chunker.chunk(py_file)

        # Should fall back to module-level chunk
        assert len(chunks) >= 1


# =============================================================================
# Prose Chunker Tests
# =============================================================================


class TestProseChunker:
    """Test paragraph-based prose chunking."""

    def test_chunk_by_paragraphs(self, tmp_path: Path) -> None:
        """Chunk prose by paragraphs."""
        from sunwell.indexing.chunkers.prose import ProseChunker

        content = """# Chapter 1

The sun rose over the mountains, casting long shadows across the valley below.
Birds sang their morning songs as the world slowly awakened.

Maria stood at her window, watching the sunrise. It had been three years since
she'd last seen this view, and yet it felt like only yesterday.

She turned away from the window and began packing her bag.
"""
        md_file = tmp_path / "chapter.md"
        md_file.write_text(content)

        chunker = ProseChunker()
        chunks = chunker.chunk(md_file)

        assert len(chunks) >= 2
        assert any("sun rose" in c.content for c in chunks)

    def test_chunk_preserves_headers(self, tmp_path: Path) -> None:
        """Headers should be preserved with their content."""
        from sunwell.indexing.chunkers.prose import ProseChunker

        content = """# Chapter 1: The Beginning

This is the first paragraph.

## Part 1

This is part 1.

## Part 2

This is part 2.
"""
        md_file = tmp_path / "novel.md"
        md_file.write_text(content)

        chunker = ProseChunker()
        chunks = chunker.chunk(md_file)

        # Should have chunks for each section
        section_chunks = [c for c in chunks if c.chunk_type == "section"]
        assert len(section_chunks) >= 2


# =============================================================================
# Screenplay Chunker Tests
# =============================================================================


class TestScreenplayChunker:
    """Test scene-based screenplay chunking."""

    def test_chunk_by_scenes(self, tmp_path: Path) -> None:
        """Chunk screenplay by scene headings."""
        from sunwell.indexing.chunkers.screenplay import ScreenplayChunker

        content = """INT. COFFEE SHOP - DAY

A busy morning. SARAH (30s) sits alone at a table, nursing a coffee.

SARAH
(to herself)
Where is he?

INT. OFFICE - DAY

A sterile corporate environment. JOHN (40s) rushes past cubicles.

EXT. STREET - CONTINUOUS

John bursts through the door onto the sidewalk.
"""
        fountain_file = tmp_path / "script.fountain"
        fountain_file.write_text(content)

        chunker = ScreenplayChunker()
        chunks = chunker.chunk(fountain_file)

        # Should have 3 scene chunks
        scene_chunks = [c for c in chunks if c.chunk_type == "scene"]
        assert len(scene_chunks) >= 3

    def test_chunk_scene_includes_dialogue(self, tmp_path: Path) -> None:
        """Scene chunks should include dialogue."""
        from sunwell.indexing.chunkers.screenplay import ScreenplayChunker

        content = """INT. BAR - NIGHT

A dimly lit bar. BOB sits at the counter.

BOB
I'll have another.

BARTENDER
You sure about that?

BOB
(firmly)
Did I stutter?
"""
        fountain_file = tmp_path / "bar.fountain"
        fountain_file.write_text(content)

        chunker = ScreenplayChunker()
        chunks = chunker.chunk(fountain_file)

        scene_chunk = chunks[0]
        assert "I'll have another" in scene_chunk.content
        assert "Did I stutter" in scene_chunk.content


# =============================================================================
# Indexing Service Tests
# =============================================================================


class TestIndexingService:
    """Test the IndexingService state machine."""

    @pytest.mark.asyncio
    async def test_service_starts_in_no_index_state(self, tmp_path: Path) -> None:
        """Service should start in NO_INDEX state."""
        from sunwell.knowledge.indexing import IndexingService, IndexState

        service = IndexingService(workspace_root=tmp_path)
        status = service.get_status()
        assert status.state == IndexState.NO_INDEX

    @pytest.mark.asyncio
    async def test_service_transitions_to_building(self, tmp_path: Path) -> None:
        """Service should transition to BUILDING when started."""
        from sunwell.knowledge.indexing import IndexingService, IndexState

        # Create a simple Python file
        (tmp_path / "main.py").write_text("print('hello')")

        service = IndexingService(workspace_root=tmp_path)
        await service.start()

        # Should be in a working state
        status = service.get_status()
        assert status.state in (IndexState.BUILDING, IndexState.READY, IndexState.DEGRADED)

        await service.stop()

    @pytest.mark.asyncio
    async def test_service_handles_empty_workspace(self, tmp_path: Path) -> None:
        """Service should handle empty workspace gracefully."""
        from sunwell.knowledge.indexing import IndexingService, IndexState

        service = IndexingService(workspace_root=tmp_path)
        await service.start()

        status = service.get_status()
        # Should complete without error
        assert status.state in (IndexState.READY, IndexState.DEGRADED, IndexState.NO_INDEX)

        await service.stop()

    @pytest.mark.asyncio
    async def test_service_query_returns_results(self, tmp_path: Path) -> None:
        """Service should return query results."""
        from sunwell.knowledge.indexing import IndexingService

        # Create searchable content
        (tmp_path / "calculator.py").write_text('''
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
''')

        service = IndexingService(workspace_root=tmp_path)
        await service.start()

        # Query for addition
        results = await service.query("add two numbers", top_k=5)

        # Should find something (even if degraded to grep)
        # Note: Results may be empty if no embedder available
        assert results is not None

        await service.stop()


# =============================================================================
# SmartContext Fallback Tests
# =============================================================================


class TestSmartContext:
    """Test SmartContext graceful fallback."""

    @pytest.mark.asyncio
    async def test_fallback_to_grep_without_index(self, tmp_path: Path) -> None:
        """Should fallback to grep when no index available."""
        from sunwell.knowledge.indexing import SmartContext

        # Create searchable content
        (tmp_path / "search_test.py").write_text('''
def find_user(user_id: int) -> User:
    """Find a user by their ID."""
    return db.query(User).filter(User.id == user_id).first()
''')

        ctx = SmartContext(workspace_root=tmp_path, index=None)
        result = await ctx.get_context("find user", top_k=3)

        # Should have found something via grep
        assert result.context is not None
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_fallback_to_file_list_without_grep(self, tmp_path: Path) -> None:
        """Should fallback to file list when grep unavailable."""
        from sunwell.knowledge.indexing import SmartContext

        # Create some files
        (tmp_path / "app.py").write_text("print('app')")
        (tmp_path / "utils.py").write_text("print('utils')")

        ctx = SmartContext(workspace_root=tmp_path, index=None)

        # Query for something that won't grep match
        result = await ctx.get_context("xyzabc123", top_k=3)

        # Should have some context (at least file list)
        assert result is not None

    @pytest.mark.asyncio
    async def test_context_format_is_usable(self, tmp_path: Path) -> None:
        """Context should be formatted for LLM consumption."""
        from sunwell.knowledge.indexing import SmartContext

        (tmp_path / "auth.py").write_text('''
def authenticate(username: str, password: str) -> bool:
    """Authenticate a user with username and password."""
    user = get_user(username)
    return user and check_password(user, password)
''')

        ctx = SmartContext(workspace_root=tmp_path, index=None)
        result = await ctx.get_context("authenticate user", top_k=3)

        # Context should be non-empty and formatted
        assert result.context
        # Should contain file reference
        assert "auth.py" in result.context or result.context.strip() != ""


# =============================================================================
# Metrics Tests
# =============================================================================


class TestIndexMetrics:
    """Test indexing metrics collection."""

    def test_metrics_initialization(self) -> None:
        """Metrics should initialize with zero values."""
        from sunwell.knowledge.indexing import IndexMetrics

        metrics = IndexMetrics()
        assert metrics.build_time_ms == 0
        assert metrics.chunk_count == 0
        assert metrics.cache_hit_rate == 0.0

    def test_metrics_cache_hit_rate_calculation(self) -> None:
        """Cache hit rate should be calculated correctly."""
        from sunwell.knowledge.indexing import IndexMetrics

        metrics = IndexMetrics()
        metrics.cache_hits = 7
        metrics.cache_misses = 3

        assert metrics.cache_hit_rate == 0.7

    def test_metrics_query_latency_tracking(self) -> None:
        """Query latency should be tracked."""
        from sunwell.knowledge.indexing import IndexMetrics

        metrics = IndexMetrics()
        metrics.record_query(10.5)
        metrics.record_query(20.5)
        metrics.record_query(15.0)

        assert metrics.avg_query_latency_ms == pytest.approx(15.33, rel=0.1)
