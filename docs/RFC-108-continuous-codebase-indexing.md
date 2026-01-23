# RFC-108: Continuous Project Indexing — Always Smart, Zero Friction

**Status**: ✅ Implemented  
**Created**: 2026-01-23  
**Authors**: Sunwell Team  
**Priority**: P0 — Core Infrastructure  
**Confidence**: 95% 🟢  
**Depends on**: RFC-107 (Shortcut Execution Path), RFC-045 (Project Intelligence)

---

## Summary

Make Sunwell always smart by removing the `--smart` flag and making semantic indexing the default. Solve the cold start problem with background indexing, file watching, and graceful fallback.

**Target state**: Open a project → index builds in background → all queries benefit from semantic search → zero user friction.

**One-liner**: Cursor indexes your codebase automatically. Sunwell indexes your **entire project** — code, prose, scripts, docs, anything.

**Domain-agnostic**: Sunwell handles any creative or technical project:
- **Code projects** — Python, TypeScript, Rust, Go...
- **Prose projects** — Novels, short stories, essays
- **Script projects** — Screenplays, stage plays, podcasts
- **Documentation** — Technical docs, wikis, knowledge bases
- **Mixed projects** — Any combination of the above

**S-tier differentiators**:
- **Content-aware chunking** — AST for code, paragraphs for prose, scenes for scripts
- **Project type detection** — Automatically adapts chunking strategy
- **Priority indexing** — Hot files first (README, outline, entry points, recent edits)
- **Transparent context** — "Used 3 chunks for this answer" with sources
- **Studio command palette** — Keyboard shortcuts for power users

---

## Motivation

### Why `--smart` Exists Today

```python
# cli/chat.py - current state
@click.option("--smart", is_flag=True, help="Enable RAG retrieval")
```

The flag exists because:

1. **Cold start**: First indexing takes 10-30 seconds, blocks interaction
2. **Dependency**: Requires Ollama with embedding model installed
3. **Failure risk**: If embedding fails, chat fails
4. **Historical**: Added when feature was experimental

### Why This Is Wrong

```bash
# Current (bad UX)
sunwell chat                  # Dumb mode, no project awareness
sunwell chat --smart          # Smart mode, but blocks on first run

# What Cursor does (good UX)
cursor .                      # Always smart, indexes in background
```

**Cursor's secret**: Index builds automatically, incrementally, in the background. The user never thinks about it.

### Impact on RFC-107

With `::a-2 docs/api.md`, the skill needs to search the project. Currently:

- **With `--smart`**: Semantic search via embeddings ✅
- **Without `--smart`**: Falls back to grep/keyword search ⚠️

Skills should always have the best available context without the user needing to know about flags.

---

## Goals

### P0: Core Functionality
1. **Remove `--smart` flag** — All modes are smart by default
2. **Background indexing** — Never block the user
3. **Incremental updates** — Only re-index changed files
4. **File watching** — Auto-update on save (Studio)
5. **Graceful fallback** — Work without embeddings, just less smart
6. **Pre-warm on project open** — Index ready when needed
7. **Project type detection** — Detect code/prose/script/docs/mixed
8. **Content-aware chunking** — Appropriate strategy per content type

### P1: Power User Features
9. **Priority indexing** — Hot files first (varies by project type)
10. **Large project strategy** — Graceful handling of 10k+ file projects
11. **Settings panel** — User control over indexing behavior
12. **Keyboard shortcuts** — `Cmd+Shift+I` to show index status

### P2: Delight
13. **Transparent context** — Show what chunks were used for each answer
14. **Index inspector** — Power user tool to browse/test index
15. **Observability** — Health metrics for debugging

## Non-Goals

1. Cloud-based indexing — Keep everything local
2. Real-time streaming updates — Batch updates are fine
3. Distributed indexing — Single-machine only
4. Format conversion — Index files as-is, don't convert formats

---

## User Journeys

### Journey 1: First-Time Project Open (CLI)

```
User: sunwell chat
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Sunwell Chat                                                │
│ Index: Building (0%)... [uses grep fallback meanwhile]      │
│                                                             │
│ You: How does authentication work?                          │
│                                                             │
│ Assistant: [answers using grep results]                     │
│ [dim] Context: grep fallback (3 files matched)              │
│                                                             │
│ Index: Ready (423 chunks from 67 files)                     │
│                                                             │
│ You: What about the token refresh logic?                    │
│                                                             │
│ Assistant: [answers using semantic search - better quality] │
│ [dim] Context: semantic (auth/tokens.py:45-89, 0.94)        │
└─────────────────────────────────────────────────────────────┘
```

**Stack trace**:
1. `cli/chat.py` → Creates `IndexingService`, calls `start()` (non-blocking)
2. `IndexingService._background_index()` runs in asyncio task
3. First query hits `SmartContext.get_context()` → falls back to grep
4. When `IndexingService._ready.set()` fires → future queries use semantic
5. CLI shows "Index: Ready" notification

**Error states**:
- Ollama not installed → grep fallback + "Install Ollama for better results" hint
- Index build fails → grep fallback + error in `/index status`
- Timeout on large repo → partial index usable, continues in background

---

### Journey 1b: First-Time Novel Project (CLI)

```
User: cd ~/writing/my-novel && sunwell chat
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Sunwell Chat                                                │
│ Project: Prose detected (manuscript/, outline.md)           │
│ Index: Building (0%)... [uses grep fallback meanwhile]      │
│                                                             │
│ You: What's the relationship between Sarah and Marcus?      │
│                                                             │
│ Assistant: [answers using grep results from chapters/]      │
│ [dim] Context: grep fallback (chapters/03-*.md, 05-*.md)    │
│                                                             │
│ Index: Ready (89 chunks from 23 files)                      │
│                                                             │
│ You: Find scenes where they argue                           │
│                                                             │
│ Assistant: [semantic search finds relevant scenes]          │
│ [dim] Context: semantic (chapters/07-confrontation.md, 0.91)│
│              (chapters/12-revelation.md, 0.87)              │
└─────────────────────────────────────────────────────────────┘
```

**Key differences from code project**:
- Detects `manuscript/` directory → sets `ProjectType.PROSE`
- Priority files: `outline.md`, `characters.md`, `chapters/01-*.md`
- Chunking: Paragraphs with section headers, not AST
- Semantic search: Finds narrative moments, character interactions

---

### Journey 2: First-Time Project Open (Studio)

```
┌─────────────────────────────────────────────────────────────────┐
│  Sunwell Studio                          ⟳ Indexing 45%        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Toast notification slides in from bottom-right]               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 🔮 Indexing your project...                               │  │
│  │    67 files found, processing auth/, models/, ...         │  │
│  │    ETA: ~12 seconds                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [After completion, toast updates]                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ✅ Index ready                                             │  │
│  │    423 chunks from 67 files                               │  │
│  │    [Dismiss] [View Details]                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [Header status pill changes]                                   │
│  ⟳ Indexing 45%  →  🔮 Indexed (423)                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Stack trace**:
1. `stores/project.svelte.ts` → `openProject()` triggers `initIndexing()`
2. `stores/indexing.svelte.ts` → calls Tauri `start_indexing_service`
3. `src-tauri/src/indexing.rs` → spawns `sunwell index build --json --progress`
4. Python streams JSON progress → Rust parses → emits `index-status` event
5. `IndexStatus.svelte` reacts to status changes
6. Toast component shows progress, then completion

**Animations**:
- Status pill: `opacity 0 → 1` on mount, `background-color` transition on ready
- Toast: slide-up entrance (200ms ease-out), fade-out on dismiss
- Progress: CSS `width` transition on progress bar

---

### Journey 3: Index Stale (File Changed Externally)

```
User edits src/auth.py in VSCode
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ [watchfiles detects change]                                 │
│                                                             │
│ IndexingService:                                            │
│   _pending_updates.add(Path("src/auth.py"))                 │
│   [debounce 500ms]                                          │
│   _update_files([Path("src/auth.py")])                      │
│     - Remove old chunks for auth.py                         │
│     - Re-chunk with AST parser                              │
│     - Embed new chunks                                      │
│     - Update cache                                          │
│                                                             │
│ Studio header: 🔮 Indexed (423) → 🔮 Indexed (425)          │
│                                                             │
│ [No user action required]                                   │
└─────────────────────────────────────────────────────────────┘
```

**Edge cases**:
- File deleted → Remove chunks, no re-index
- Many files changed (git checkout) → Batch update, single progress indicator
- watchfiles unavailable → Fall back to mtime polling on query

---

### Journey 4: Large Monorepo (10k+ Files)

```
User opens monorepo with 15,000 files
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Priority Index (5 seconds)                         │
│   - README.md, CONTRIBUTING.md                              │
│   - pyproject.toml, package.json, Cargo.toml                │
│   - Entry points (src/*/main.py, src/index.ts)              │
│   - Recently modified files (git log --oneline -20)         │
│   → 200 chunks ready, index is "warm"                       │
│                                                             │
│ Phase 2: Full Index (background, 2-5 minutes)               │
│   - Remaining files by directory                            │
│   - Streaming progress: "Indexed 3,421 / 15,000 files"      │
│   - Memory budget: Max 1000 chunks in memory at once        │
│   → Full 8,500 chunks ready                                 │
│                                                             │
│ User experience:                                            │
│   - Query works immediately (Phase 1 chunks)                │
│   - Quality improves as Phase 2 progresses                  │
│   - Status shows: "🔮 Indexed (8.5k) [95% complete]"        │
└─────────────────────────────────────────────────────────────┘
```

**Priority queue**:
```python
PRIORITY_FILES = [
    "README*", "CONTRIBUTING*", "CHANGELOG*",  # Documentation
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",  # Config
    "src/*/main.py", "src/index.ts", "main.go",  # Entry points
    # + files from `git log --oneline -20 --name-only`
]
```

---

### Journey 5: Offline / No Ollama

```
User runs sunwell chat without Ollama installed
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ IndexingService._create_embedder() → raises Exception       │
│ _background_index() catches, sets fallback_mode = "grep"    │
│ _ready.set() → index is "ready" in degraded mode            │
│                                                             │
│ CLI output:                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Sunwell Chat                                            │ │
│ │ ⚠️  Running without semantic search (Ollama not found)  │ │
│ │     Install: curl -fsSL https://ollama.com/install.sh | │ │
│ │     Then: ollama pull all-minilm                        │ │
│ │     [Continue with grep-based search]                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Queries use grep fallback, still functional                 │
│                                                             │
│ Studio: Shows "⚠️ Grep mode" instead of "🔮 Indexed"        │
│         Settings panel has "Install Ollama" button          │
└─────────────────────────────────────────────────────────────┘
```

---

## State Machine

```
                         ┌──────────────┐
                         │   NO_INDEX   │
                         └──────┬───────┘
                                │ project_opened
                                ▼
       ┌────────────────────────────────────────────────┐
       │                                                │
       ▼                                                │
┌─────────────┐         ┌─────────────┐                │
│  CHECKING   │────────▶│   LOADING   │                │
└─────────────┘  found  └──────┬──────┘                │
       │                       │                        │
       │ not_found             │ loaded                 │
       ▼                       ▼                        │
┌─────────────┐         ┌─────────────┐                │
│  BUILDING   │────────▶│   VERIFYING │                │
└─────────────┘  done   └──────┬──────┘                │
       │                       │                        │
       │ progress              │ fresh                  │
       ▼                       ▼                        │
┌─────────────┐         ┌─────────────┐                │
│  BUILDING   │         │    READY    │◀───────────────┘
│   (n/m)     │         └──────┬──────┘     update_complete
└─────────────┘                │
                               │ file_changed
                               ▼
                        ┌─────────────┐
                        │  UPDATING   │
                        └──────┬──────┘
                               │ done
                               ▼
                        ┌─────────────┐
                        │    READY    │
                        └─────────────┘

Error States (can occur from any state):
  BUILDING → ERROR (embedder failed) → DEGRADED (grep mode)
  LOADING  → ERROR (corrupt cache)   → BUILDING
  UPDATING → ERROR (file read fail)  → READY (skip file)
```

---

## Project Type Detection

Sunwell automatically detects project type and adapts its indexing strategy accordingly.

### Project Types

```yaml
CODE:
  markers: [pyproject.toml, package.json, Cargo.toml, go.mod, *.csproj]
  extensions: [.py, .js, .ts, .jsx, .tsx, .go, .rs, .java, .kt, .c, .cpp, .h]
  chunking: AST-aware (functions, classes, modules)
  priority_files: [README.md, main.py, src/index.ts, Makefile]
  
PROSE:
  markers: [manuscript/, chapters/, novel.md, story.md, *.scriv]
  extensions: [.md, .txt, .rtf, .docx, .odt]
  chunking: Paragraph/section-aware (preserve narrative flow)
  priority_files: [outline.md, synopsis.md, characters.md, chapters/01-*.md]
  
SCRIPT:
  markers: [*.fountain, *.fdx, screenplay/, script/]
  extensions: [.fountain, .fdx, .highland, .md]
  chunking: Scene/beat-aware (INT./EXT. markers, sluglines)
  priority_files: [outline.md, treatment.md, script.fountain]
  
DOCS:
  markers: [docs/, documentation/, conf.py, mkdocs.yml, docusaurus.config.js]
  extensions: [.md, .rst, .mdx, .adoc]
  chunking: Heading-aware (preserve hierarchy, cross-references)
  priority_files: [index.md, README.md, getting-started.md, overview.md]
  
MIXED:
  detection: Multiple markers from different types
  chunking: Per-file detection (code files get AST, prose gets paragraphs)
  priority_files: [README.md] + type-specific priorities
```

### Detection Algorithm

```python
# src/sunwell/indexing/project_type.py

from enum import Enum
from pathlib import Path


class ProjectType(Enum):
    CODE = "code"
    PROSE = "prose"
    SCRIPT = "script"
    DOCS = "docs"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# Marker files/directories that indicate project type
PROJECT_MARKERS: dict[ProjectType, list[str]] = {
    ProjectType.CODE: [
        "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
        "setup.py", "pom.xml", "build.gradle", "*.csproj", "*.sln",
        "src/", "lib/",
    ],
    ProjectType.PROSE: [
        "manuscript/", "chapters/", "novel.md", "story.md",
        "*.scriv", "draft/", "writing/",
    ],
    ProjectType.SCRIPT: [
        "*.fountain", "*.fdx", "screenplay/", "script/",
        "*.highland", "teleplay/",
    ],
    ProjectType.DOCS: [
        "docs/", "documentation/", "conf.py", "mkdocs.yml",
        "docusaurus.config.js", ".readthedocs.yml", "antora.yml",
    ],
}


def detect_project_type(workspace_root: Path) -> ProjectType:
    """Detect project type from marker files.
    
    Returns the dominant type, or MIXED if multiple types detected.
    """
    detected: set[ProjectType] = set()
    
    for ptype, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                if list(workspace_root.glob(marker)):
                    detected.add(ptype)
            elif (workspace_root / marker).exists():
                detected.add(ptype)
    
    if len(detected) == 0:
        return ProjectType.UNKNOWN
    if len(detected) == 1:
        return detected.pop()
    if len(detected) > 1:
        return ProjectType.MIXED
    
    return ProjectType.UNKNOWN


def detect_file_type(file_path: Path) -> ProjectType:
    """Detect content type for a single file.
    
    Used in MIXED projects to choose the right chunker.
    """
    ext = file_path.suffix.lower()
    
    CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".kt", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".rb", ".php"}
    SCRIPT_EXTENSIONS = {".fountain", ".fdx", ".highland"}
    
    if ext in CODE_EXTENSIONS:
        return ProjectType.CODE
    if ext in SCRIPT_EXTENSIONS:
        return ProjectType.SCRIPT
    
    # For .md/.txt, check content patterns
    if ext in {".md", ".txt"}:
        try:
            content = file_path.read_text()[:2000]  # First 2KB
            
            # Screenplay markers
            if "INT." in content or "EXT." in content or "FADE IN:" in content:
                return ProjectType.SCRIPT
            
            # Documentation markers
            if "```" in content or "##" in content[:500]:
                return ProjectType.DOCS
            
            # Default prose for plain text
            return ProjectType.PROSE
        except Exception:
            return ProjectType.DOCS
    
    return ProjectType.DOCS  # Default for unknown
```

### Priority Files by Project Type

```python
# src/sunwell/indexing/priority.py

PRIORITY_FILES: dict[ProjectType, list[str]] = {
    ProjectType.CODE: [
        # Documentation
        "README*", "CONTRIBUTING*", "CHANGELOG*",
        # Config
        "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
        # Entry points
        "src/*/main.py", "src/*/__main__.py", "src/index.ts", "main.go",
        "src/main.rs", "src/lib.rs",
        # CLI
        "src/*/cli.py", "cli/*.py",
    ],
    ProjectType.PROSE: [
        # Planning
        "outline*", "synopsis*", "treatment*",
        # Characters
        "characters*", "cast*", "dramatis*",
        # World
        "world*", "setting*", "locations*",
        # Recent chapters (glob by number)
        "chapters/[0-9][0-9]-*.md", "manuscript/[0-9][0-9]-*.md",
    ],
    ProjectType.SCRIPT: [
        # Planning
        "outline*", "treatment*", "beat-sheet*",
        # Character
        "characters*", "cast*",
        # The script itself
        "*.fountain", "*.fdx", "script.*",
    ],
    ProjectType.DOCS: [
        # Navigation
        "index.md", "README.md", "overview*",
        # Getting started
        "get-started*", "quickstart*", "installation*",
        # Config
        "conf.py", "mkdocs.yml", "_config.yml",
    ],
}


def get_priority_files(workspace_root: Path, project_type: ProjectType) -> list[Path]:
    """Get priority files for the detected project type."""
    patterns = PRIORITY_FILES.get(project_type, PRIORITY_FILES[ProjectType.DOCS])
    
    priority_files: list[Path] = []
    seen: set[Path] = set()
    
    for pattern in patterns:
        for path in workspace_root.glob(pattern):
            if path.is_file() and path not in seen:
                priority_files.append(path)
                seen.add(path)
    
    # Also include recently modified files from git
    recent = _get_recently_modified(workspace_root)
    for path in recent:
        if path not in seen:
            priority_files.append(path)
            seen.add(path)
    
    return priority_files[:200]  # Cap at 200 for fast startup
```

---

## Content-Aware Chunking

Different content types require different chunking strategies to preserve semantic meaning.

### Chunking Strategy Matrix

| Content Type | Chunking Strategy | Boundary Markers | Overlap |
|--------------|-------------------|------------------|---------|
| **Python** | AST (functions, classes) | `def`, `class`, decorators | By definition |
| **JavaScript/TypeScript** | AST (functions, classes, exports) | `function`, `class`, `export` | By definition |
| **Prose** | Paragraphs + section headers | Blank lines, `#` headers | 1 paragraph |
| **Screenplay** | Scenes | `INT.`, `EXT.`, `FADE` | None (scenes are atomic) |
| **Documentation** | Heading sections | `#`, `##`, `###` | None (sections are atomic) |
| **Generic** | Fixed-size with overlap | Line count | 10 lines |

### Prose Chunker

```python
# src/sunwell/indexing/chunkers/prose.py

"""Chunking for prose content (novels, stories, essays).

Preserves narrative flow by chunking at natural boundaries:
- Section headers (# Chapter, ## Scene)
- Paragraph breaks (blank lines)
- Scene breaks (*** or ---)
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sunwell.workspace.indexer import CodeChunk, _content_hash


@dataclass(frozen=True, slots=True)
class ProseChunk(CodeChunk):
    """Extended chunk for prose content."""
    
    section_title: str | None = None
    """Chapter/section title if applicable."""
    
    word_count: int = 0
    """Word count for this chunk."""


class ProseChunker:
    """Chunk prose by paragraphs and sections."""
    
    MIN_WORDS = 50      # Minimum words per chunk
    MAX_WORDS = 800     # Maximum words per chunk (about 1 page)
    OVERLAP_WORDS = 50  # Overlap for context continuity
    
    # Patterns
    SECTION_HEADER = re.compile(r'^#+\s+(.+)$', re.MULTILINE)
    SCENE_BREAK = re.compile(r'^(\*{3,}|—{3,}|-{3,})$', re.MULTILINE)
    PARAGRAPH_BREAK = re.compile(r'\n\s*\n')
    
    def chunk(self, file_path: Path) -> list[ProseChunk]:
        """Parse and chunk a prose file."""
        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return []
        
        # First, split by major sections (# headers)
        sections = self._split_by_headers(content)
        
        chunks: list[ProseChunk] = []
        
        for section_title, section_content, start_line in sections:
            # Then chunk each section by paragraphs
            section_chunks = self._chunk_section(
                file_path, section_title, section_content, start_line
            )
            chunks.extend(section_chunks)
        
        return chunks
    
    def _split_by_headers(self, content: str) -> list[tuple[str | None, str, int]]:
        """Split content by markdown headers.
        
        Returns: [(title, content, start_line), ...]
        """
        lines = content.split('\n')
        sections = []
        current_title = None
        current_start = 1
        current_lines = []
        
        for i, line in enumerate(lines, 1):
            header_match = self.SECTION_HEADER.match(line)
            if header_match:
                # Save previous section
                if current_lines:
                    sections.append((
                        current_title,
                        '\n'.join(current_lines),
                        current_start,
                    ))
                # Start new section
                current_title = header_match.group(1)
                current_start = i
                current_lines = [line]
            else:
                current_lines.append(line)
        
        # Don't forget the last section
        if current_lines:
            sections.append((
                current_title,
                '\n'.join(current_lines),
                current_start,
            ))
        
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
        
        chunks = []
        current_chunk_paragraphs = []
        current_word_count = 0
        chunk_start_line = start_line
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_words = len(para.split())
            
            # If adding this paragraph exceeds max, save current chunk
            if current_word_count + para_words > self.MAX_WORDS and current_chunk_paragraphs:
                chunk_content = '\n\n'.join(current_chunk_paragraphs)
                chunks.append(ProseChunk(
                    file_path=file_path,
                    start_line=chunk_start_line,
                    end_line=chunk_start_line + chunk_content.count('\n'),
                    content=chunk_content,
                    chunk_type="prose",
                    name=section_title,
                    _content_hash=_content_hash(chunk_content),
                    section_title=section_title,
                    word_count=current_word_count,
                ))
                
                # Start new chunk with overlap (keep last paragraph)
                if current_chunk_paragraphs:
                    current_chunk_paragraphs = [current_chunk_paragraphs[-1]]
                    current_word_count = len(current_chunk_paragraphs[0].split())
                else:
                    current_chunk_paragraphs = []
                    current_word_count = 0
                chunk_start_line = chunk_start_line + chunk_content.count('\n')
            
            current_chunk_paragraphs.append(para)
            current_word_count += para_words
        
        # Save final chunk
        if current_chunk_paragraphs and current_word_count >= self.MIN_WORDS:
            chunk_content = '\n\n'.join(current_chunk_paragraphs)
            chunks.append(ProseChunk(
                file_path=file_path,
                start_line=chunk_start_line,
                end_line=chunk_start_line + chunk_content.count('\n'),
                content=chunk_content,
                chunk_type="prose",
                name=section_title,
                _content_hash=_content_hash(chunk_content),
                section_title=section_title,
                word_count=current_word_count,
            ))
        
        return chunks
```

### Screenplay Chunker

```python
# src/sunwell/indexing/chunkers/screenplay.py

"""Chunking for screenplays (Fountain format).

Chunks by scene - the natural unit of a screenplay.
Each INT./EXT. slugline starts a new chunk.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sunwell.workspace.indexer import CodeChunk, _content_hash


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
        r'^(INT\.|EXT\.|INT/EXT\.|I/E\.|EST\.)\s*(.+)$',
        re.MULTILINE | re.IGNORECASE
    )
    
    # Scene transitions
    TRANSITION = re.compile(
        r'^(FADE IN:|FADE OUT\.|FADE TO:|CUT TO:|DISSOLVE TO:)',
        re.MULTILINE | re.IGNORECASE
    )
    
    def chunk(self, file_path: Path) -> list[SceneChunk]:
        """Parse and chunk a screenplay file."""
        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return []
        
        scenes = self._split_by_scenes(content, file_path)
        return scenes
    
    def _split_by_scenes(self, content: str, file_path: Path) -> list[SceneChunk]:
        """Split screenplay into scenes."""
        lines = content.split('\n')
        chunks = []
        
        current_scene_lines = []
        current_slugline = None
        current_start = 1
        scene_number = 0
        
        for i, line in enumerate(lines, 1):
            slugline_match = self.SLUGLINE.match(line.strip())
            
            if slugline_match:
                # Save previous scene
                if current_scene_lines:
                    scene_content = '\n'.join(current_scene_lines)
                    if scene_content.strip():
                        chunks.append(SceneChunk(
                            file_path=file_path,
                            start_line=current_start,
                            end_line=i - 1,
                            content=scene_content,
                            chunk_type="scene",
                            name=current_slugline,
                            _content_hash=_content_hash(scene_content),
                            slugline=current_slugline,
                            scene_number=scene_number if scene_number > 0 else None,
                        ))
                
                # Start new scene
                scene_number += 1
                current_slugline = line.strip()
                current_start = i
                current_scene_lines = [line]
            else:
                current_scene_lines.append(line)
        
        # Don't forget the last scene
        if current_scene_lines:
            scene_content = '\n'.join(current_scene_lines)
            if scene_content.strip():
                chunks.append(SceneChunk(
                    file_path=file_path,
                    start_line=current_start,
                    end_line=len(lines),
                    content=scene_content,
                    chunk_type="scene",
                    name=current_slugline,
                    _content_hash=_content_hash(scene_content),
                    slugline=current_slugline,
                    scene_number=scene_number if scene_number > 0 else None,
                ))
        
        return chunks
```

### Chunker Registry

```python
# src/sunwell/indexing/chunkers/__init__.py

"""Content-aware chunker registry."""

from pathlib import Path

from sunwell.indexing.project_type import ProjectType, detect_file_type
from sunwell.indexing.chunkers.python_ast import PythonASTChunker
from sunwell.indexing.chunkers.prose import ProseChunker
from sunwell.indexing.chunkers.screenplay import ScreenplayChunker
from sunwell.workspace.indexer import CodeChunk


class ChunkerRegistry:
    """Registry of content-type-specific chunkers."""
    
    def __init__(self):
        self._python = PythonASTChunker()
        self._prose = ProseChunker()
        self._screenplay = ScreenplayChunker()
    
    def chunk_file(self, file_path: Path, project_type: ProjectType) -> list[CodeChunk]:
        """Chunk a file using the appropriate chunker.
        
        For MIXED projects, detects file type individually.
        """
        if project_type == ProjectType.MIXED:
            file_type = detect_file_type(file_path)
        else:
            file_type = project_type
        
        ext = file_path.suffix.lower()
        
        # Code files
        if ext == ".py":
            return self._python.chunk(file_path)
        if ext in {".js", ".ts", ".jsx", ".tsx"}:
            # TODO: JavaScript AST chunker
            return self._generic_chunk(file_path)
        if ext in {".go", ".rs", ".java", ".kt", ".c", ".cpp"}:
            # TODO: Language-specific chunkers
            return self._generic_chunk(file_path)
        
        # Screenplay files
        if ext in {".fountain", ".fdx", ".highland"}:
            return self._screenplay.chunk(file_path)
        
        # Prose/docs (markdown, text)
        if file_type == ProjectType.PROSE:
            return self._prose.chunk(file_path)
        if file_type == ProjectType.SCRIPT:
            # Check if it looks like a screenplay
            if self._looks_like_screenplay(file_path):
                return self._screenplay.chunk(file_path)
            return self._prose.chunk(file_path)
        
        # Documentation and default
        return self._generic_chunk(file_path)
    
    def _looks_like_screenplay(self, file_path: Path) -> bool:
        """Check if a markdown file looks like a screenplay."""
        try:
            content = file_path.read_text()[:1000]
            return "INT." in content or "EXT." in content
        except Exception:
            return False
    
    def _generic_chunk(self, file_path: Path, chunk_size: int = 50) -> list[CodeChunk]:
        """Generic line-based chunking."""
        # ... (existing implementation)
```

---

## Cross-Stack Integration

### Touchpoint Matrix

| Layer | New Files | Modified Files | Purpose |
|-------|-----------|----------------|---------|
| **Python** | `indexing/__init__.py` | `cli/main.py` | Register module |
| | `indexing/service.py` | `cli/chat.py` | Background indexer |
| | `indexing/fallback.py` | `cli/do_cmd.py` | SmartContext provider |
| | `indexing/project_type.py` | `workspace/indexer.py` | Project type detection |
| | `indexing/priority.py` | | Priority file detection |
| | `indexing/metrics.py` | | Observability |
| | `indexing/chunkers/__init__.py` | | Chunker registry |
| | `indexing/chunkers/python_ast.py` | | Python AST chunking |
| | `indexing/chunkers/prose.py` | | Prose paragraph chunking |
| | `indexing/chunkers/screenplay.py` | | Screenplay scene chunking |
| | `cli/index_cmd.py` | | CLI commands |
| **Rust** | `indexing.rs` | `main.rs` | Tauri commands |
| | | `project.rs` | Trigger on open |
| | | `commands.rs` | Wire to frontend |
| **Svelte** | `lib/indexing.ts` | `App.svelte` | Client + types |
| | `stores/indexing.svelte.ts` | `stores/project.svelte.ts` | Reactive state |
| | `components/IndexStatus.svelte` | `components/InputBar.svelte` | Status pill |
| | `components/IndexInspector.svelte` | | Power user tool |
| | `components/IndexSettings.svelte` | | Settings panel |

**Total: 12 new files, 8 modified files across 3 stacks**

---

### IPC Contract

```typescript
// studio/src/lib/indexing-contract.ts

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type IndexState = 
  | 'no_index'    // No project opened
  | 'checking'    // Checking for cached index
  | 'loading'     // Loading cached index
  | 'building'    // Building from scratch
  | 'verifying'   // Verifying cache freshness
  | 'ready'       // Ready for queries
  | 'updating'    // Incremental update in progress
  | 'degraded'    // Grep fallback mode
  | 'error';      // Unrecoverable error

export type ProjectType = 'code' | 'prose' | 'script' | 'docs' | 'mixed' | 'unknown';

export interface IndexStatus {
  state: IndexState;
  projectType?: ProjectType;   // Detected project type
  progress?: number;           // 0-100 during building
  currentFile?: string;        // File being indexed
  chunkCount?: number;         // Total chunks when ready
  fileCount?: number;          // Files indexed
  lastUpdated?: string;        // ISO timestamp
  error?: string;              // Error message if state='error'
  fallbackReason?: string;     // Why we're in degraded mode
  priorityComplete?: boolean;  // Phase 1 (hot files) done
  estimatedTimeMs?: number;    // ETA for building
}

export interface IndexQuery {
  text: string;
  topK?: number;               // Default: 10
  threshold?: number;          // Default: 0.3
  fileFilter?: string[];       // Limit to specific files/dirs
}

export interface IndexChunk {
  id: string;
  filePath: string;
  startLine: number;
  endLine: number;
  content: string;
  chunkType: 'function' | 'class' | 'module' | 'block';
  name?: string;               // Function/class name
  score: number;               // Relevance score 0-1
}

export interface IndexResult {
  chunks: IndexChunk[];
  fallbackUsed: boolean;       // True if grep was used
  queryTimeMs: number;
  totalChunksSearched: number;
}

export interface IndexMetrics {
  buildTimeMs: number;
  chunkCount: number;
  fileCount: number;
  embeddingTimeMs: number;
  cacheHitRate: number;
  avgQueryLatencyMs: number;
  lastQueryLatencyMs: number;
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

export type IndexCommands = {
  /** Start indexing service for a workspace */
  start_indexing_service: (workspacePath: string) => Promise<void>;
  
  /** Stop the indexing service */
  stop_indexing_service: () => Promise<void>;
  
  /** Query the index */
  query_index: (query: IndexQuery) => Promise<IndexResult>;
  
  /** Get current status */
  get_index_status: () => Promise<IndexStatus>;
  
  /** Force rebuild (clear cache) */
  rebuild_index: () => Promise<void>;
  
  /** Get metrics for debugging */
  get_index_metrics: () => Promise<IndexMetrics>;
  
  /** Update indexing settings */
  set_index_settings: (settings: IndexSettings) => Promise<void>;
};

// ═══════════════════════════════════════════════════════════════
// TAURI EVENTS
// ═══════════════════════════════════════════════════════════════

export type IndexEvents = {
  /** Status changed (subscribe for real-time updates) */
  'index-status': IndexStatus;
  
  /** Index is ready (one-time notification) */
  'index-ready': { chunkCount: number; fileCount: number; buildTimeMs: number };
  
  /** Error occurred */
  'index-error': { message: string; recoverable: boolean };
  
  /** File was updated in index */
  'index-file-updated': { filePath: string; chunksDelta: number };
};

// ═══════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════

export interface IndexSettings {
  autoIndex: boolean;          // Index on project open (default: true)
  watchFiles: boolean;         // Update on file changes (default: true)
  embeddingModel: string;      // 'all-minilm' | 'nomic-embed-text'
  maxFileSize: number;         // Max file size in bytes (default: 100KB)
  excludePatterns: string[];   // Additional gitignore patterns
  priorityPatterns: string[];  // Files to index first
}
```

---

## Detailed Design

### Part 1: AST-Aware Chunking (Python)

```python
# src/sunwell/indexing/chunkers/python_ast.py

"""AST-aware chunking for Python files.

This is what makes Sunwell better than generic RAG:
- Chunks align with semantic boundaries (functions, classes)
- Docstrings extracted for better embedding quality
- Signatures included for precise retrieval
- Decorators kept with their functions
"""

import ast
from dataclasses import dataclass
from pathlib import Path

from sunwell.workspace.indexer import CodeChunk, _content_hash


@dataclass(frozen=True, slots=True)
class PythonChunk(CodeChunk):
    """Extended chunk with Python-specific metadata."""
    
    docstring: str | None = None
    """Extracted docstring for embedding boost."""
    
    signature: str | None = None
    """Function/method signature."""
    
    decorators: tuple[str, ...] = ()
    """Decorator names (e.g., '@dataclass', '@property')."""
    
    def to_embedding_text(self) -> str:
        """Text optimized for embedding (includes docstring prominently)."""
        parts = []
        if self.name:
            parts.append(f"# {self.name}")
        if self.docstring:
            parts.append(f'"""{self.docstring}"""')
        if self.signature:
            parts.append(self.signature)
        parts.append(self.content)
        return "\n".join(parts)


class PythonASTChunker:
    """Chunk Python by semantic boundaries, not line counts."""
    
    MIN_LINES = 3
    MAX_LINES = 150  # Allow larger chunks for classes
    
    def chunk(self, file_path: Path) -> list[PythonChunk]:
        """Parse and chunk a Python file."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return []  # Invalid Python, skip
        
        lines = content.split("\n")
        chunks: list[PythonChunk] = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                chunk = self._chunk_class(node, file_path, lines)
                if chunk:
                    chunks.append(chunk)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip methods (handled by class chunker)
                if not self._is_method(node, tree):
                    chunk = self._chunk_function(node, file_path, lines)
                    if chunk:
                        chunks.append(chunk)
        
        # If no definitions found, chunk the whole module
        if not chunks and len(lines) >= self.MIN_LINES:
            chunks.append(self._chunk_module(file_path, content, lines))
        
        return chunks
    
    def _chunk_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        lines: list[str],
    ) -> PythonChunk | None:
        """Extract a function as a chunk."""
        # Find actual start (including decorators)
        start_line = node.lineno
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)
        
        end_line = node.end_lineno or node.lineno
        
        if end_line - start_line + 1 < self.MIN_LINES:
            return None
        
        chunk_lines = lines[start_line - 1:end_line]
        content = "\n".join(chunk_lines)
        
        return PythonChunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            chunk_type="function",
            name=node.name,
            _content_hash=_content_hash(content),
            docstring=ast.get_docstring(node),
            signature=self._extract_signature(node, lines),
            decorators=tuple(self._decorator_name(d) for d in node.decorator_list),
        )
    
    def _chunk_class(
        self,
        node: ast.ClassDef,
        file_path: Path,
        lines: list[str],
    ) -> PythonChunk | None:
        """Extract a class as a chunk."""
        start_line = node.lineno
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)
        
        end_line = node.end_lineno or node.lineno
        
        # For very large classes, chunk just the signature + docstring + method names
        if end_line - start_line > self.MAX_LINES:
            return self._chunk_class_summary(node, file_path, lines)
        
        chunk_lines = lines[start_line - 1:end_line]
        content = "\n".join(chunk_lines)
        
        return PythonChunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            chunk_type="class",
            name=node.name,
            _content_hash=_content_hash(content),
            docstring=ast.get_docstring(node),
            signature=f"class {node.name}",
            decorators=tuple(self._decorator_name(d) for d in node.decorator_list),
        )
    
    def _chunk_class_summary(
        self,
        node: ast.ClassDef,
        file_path: Path,
        lines: list[str],
    ) -> PythonChunk:
        """For large classes, create a summary chunk."""
        # Extract class definition line + docstring + method signatures
        summary_parts = [lines[node.lineno - 1]]  # class Foo(Bar):
        
        docstring = ast.get_docstring(node)
        if docstring:
            summary_parts.append(f'    """{docstring}"""')
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._extract_signature(item, lines)
                if sig:
                    summary_parts.append(f"    {sig}")
                    summary_parts.append("        ...")
        
        content = "\n".join(summary_parts)
        
        return PythonChunk(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            content=content,
            chunk_type="class",
            name=node.name,
            _content_hash=_content_hash(content),
            docstring=docstring,
            signature=f"class {node.name} (summary)",
        )
    
    def _extract_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
    ) -> str | None:
        """Extract function signature from source."""
        sig_lines = []
        for i in range(node.lineno - 1, min(node.lineno + 5, len(lines))):
            line = lines[i]
            sig_lines.append(line)
            if line.rstrip().endswith(":"):
                break
        return "\n".join(sig_lines).strip()
    
    def _decorator_name(self, node: ast.expr) -> str:
        """Extract decorator name."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return "unknown"
    
    def _is_method(self, node: ast.FunctionDef, tree: ast.Module) -> bool:
        """Check if function is a method inside a class."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                if node in parent.body:
                    return True
        return False
    
    def _chunk_module(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
    ) -> PythonChunk:
        """Chunk entire module (no definitions found)."""
        return PythonChunk(
            file_path=file_path,
            start_line=1,
            end_line=len(lines),
            content=content,
            chunk_type="module",
            name=file_path.stem,
            _content_hash=_content_hash(content),
            docstring=None,
        )
```

---

### Part 2: Priority Indexing

```python
# src/sunwell/indexing/priority.py

"""Priority file detection for fast initial indexing.

Index hot files first so the index is useful within seconds,
then continue with the full index in background.
"""

import subprocess
from pathlib import Path


# Files to always index first (glob patterns)
PRIORITY_PATTERNS = [
    # Documentation
    "README*",
    "CONTRIBUTING*",
    "CHANGELOG*",
    "docs/index.*",
    
    # Config files
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    
    # Entry points
    "src/*/main.py",
    "src/*/__main__.py",
    "src/index.ts",
    "src/main.ts",
    "main.go",
    "cmd/*/main.go",
    "src/main.rs",
    "src/lib.rs",
    
    # CLI
    "src/*/cli.py",
    "src/*/cli/*.py",
    "cli/*.py",
]


def get_priority_files(workspace_root: Path, max_files: int = 200) -> list[Path]:
    """Get files to index first for fast startup.
    
    Returns files in priority order:
    1. Pattern-matched priority files
    2. Recently modified files (from git)
    3. Remaining files by modification time
    """
    priority_files: list[Path] = []
    seen: set[Path] = set()
    
    # 1. Pattern-matched files
    for pattern in PRIORITY_PATTERNS:
        for path in workspace_root.glob(pattern):
            if path.is_file() and path not in seen:
                priority_files.append(path)
                seen.add(path)
    
    # 2. Recently modified files (git log)
    recent = _get_recently_modified(workspace_root)
    for path in recent:
        if path not in seen:
            priority_files.append(path)
            seen.add(path)
    
    # 3. Cap at max_files
    return priority_files[:max_files]


def _get_recently_modified(workspace_root: Path, limit: int = 50) -> list[Path]:
    """Get recently modified files from git log."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{limit}", "--name-only", "--pretty=format:"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        
        files = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                path = workspace_root / line
                if path.exists() and path.is_file():
                    files.append(path)
        
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
```

---

### Part 3: Background Indexer Service

```python
# src/sunwell/indexing/service.py

"""Background codebase indexing service.

Provides always-on semantic search without blocking user interaction.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from watchfiles import awatch

from sunwell.indexing.chunkers import ChunkerRegistry
from sunwell.indexing.priority import get_priority_files
from sunwell.indexing.project_type import ProjectType, detect_project_type
from sunwell.workspace.indexer import CodebaseIndex, CodeChunk


class IndexState(Enum):
    """Index service state machine."""
    NO_INDEX = "no_index"
    CHECKING = "checking"
    LOADING = "loading"
    BUILDING = "building"
    VERIFYING = "verifying"
    READY = "ready"
    UPDATING = "updating"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class IndexStatus:
    """Current status of the indexing service."""
    state: IndexState
    progress: int = 0  # 0-100
    current_file: str | None = None
    chunk_count: int = 0
    file_count: int = 0
    last_updated: datetime | None = None
    error: str | None = None
    fallback_reason: str | None = None
    priority_complete: bool = False
    estimated_time_ms: int | None = None


@dataclass
class IndexingService:
    """Background codebase indexing service.
    
    Lifecycle:
    1. start() → Check cache → Load or build
    2. watch_files() → Queue changes → Debounce → Update
    3. query() → Search index → Return results
    4. stop() → Cleanup
    
    Features:
    - Priority indexing (hot files first)
    - AST-aware chunking (Python)
    - Graceful fallback (grep when no embeddings)
    - File watching (incremental updates)
    """
    
    workspace_root: Path
    cache_dir: Path = field(init=False)
    
    # Configuration
    debounce_ms: int = 500
    max_file_size: int = 100_000
    priority_file_limit: int = 200
    
    # Supported extensions (code + prose + scripts + docs)
    index_extensions: frozenset[str] = frozenset({
        # Code
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb",
        ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs",
        # Config
        ".yaml", ".yml", ".toml", ".json",
        # Documentation
        ".md", ".rst", ".mdx", ".adoc",
        # Prose
        ".txt", ".rtf",
        # Screenplays
        ".fountain", ".fdx", ".highland",
    })
    
    # State
    _status: IndexStatus = field(default_factory=lambda: IndexStatus(state=IndexState.NO_INDEX))
    _index: CodebaseIndex | None = field(default=None, init=False)
    _embedder: object | None = field(default=None, init=False)
    _ready: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _pending_updates: set[Path] = field(default_factory=set, init=False)
    _update_task: asyncio.Task | None = field(default=None, init=False)
    _watch_task: asyncio.Task | None = field(default=None, init=False)
    
    # Project detection
    _project_type: ProjectType = field(default=ProjectType.UNKNOWN, init=False)
    
    # Content-aware chunking
    _chunker_registry: ChunkerRegistry = field(default_factory=ChunkerRegistry, init=False)
    
    # Callbacks
    on_status_change: Callable[[IndexStatus], None] | None = None
    
    def __post_init__(self):
        self.cache_dir = self.workspace_root / ".sunwell" / "index"
    
    @property
    def status(self) -> IndexStatus:
        """Get current status."""
        return self._status
    
    @property
    def is_ready(self) -> bool:
        """Check if index is ready for queries."""
        return self._status.state in (IndexState.READY, IndexState.UPDATING)
    
    def _update_status(self, **kwargs) -> None:
        """Update status and notify listeners."""
        for key, value in kwargs.items():
            if hasattr(self._status, key):
                setattr(self._status, key, value)
        if self.on_status_change:
            self.on_status_change(self._status)
    
    async def start(self) -> None:
        """Start the indexing service."""
        self._update_status(state=IndexState.CHECKING)
        
        # 0. Detect project type (code, prose, script, docs, mixed)
        self._project_type = detect_project_type(self.workspace_root)
        
        # 1. Try to load cached index
        if await self._load_cached_index():
            self._update_status(state=IndexState.VERIFYING)
            if await self._verify_cache_fresh():
                self._update_status(state=IndexState.READY)
                self._ready.set()
            else:
                # Cache stale, rebuild
                asyncio.create_task(self._background_index())
        else:
            # No cache, build from scratch
            asyncio.create_task(self._background_index())
        
        # 2. Start file watcher
        self._watch_task = asyncio.create_task(self._watch_files())
    
    async def stop(self) -> None:
        """Stop the indexing service."""
        if self._watch_task:
            self._watch_task.cancel()
        if self._update_task:
            self._update_task.cancel()
    
    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for index to be ready (at least priority files)."""
        try:
            await asyncio.wait_for(self._ready.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    async def query(
        self,
        text: str,
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> list[CodeChunk]:
        """Query the index for relevant code."""
        if not self._index or not self._embedder:
            return []
        
        # Embed query
        result = await self._embedder.embed([text])
        query_vector = result.vectors[0]
        
        # Search
        return self._index.search(query_vector, top_k=top_k, threshold=threshold)
    
    async def _background_index(self) -> None:
        """Build index in background with priority files first."""
        self._update_status(state=IndexState.BUILDING, progress=0)
        
        try:
            self._embedder = await self._create_embedder()
            
            if self._embedder:
                # Phase 1: Priority files (fast)
                await self._index_priority_files()
                self._update_status(priority_complete=True)
                self._ready.set()  # Usable after priority phase
                
                # Phase 2: Remaining files (background)
                await self._index_remaining_files()
                
                await self._save_cache()
                self._update_status(state=IndexState.READY)
            else:
                # No embedder available, use degraded mode
                self._update_status(
                    state=IndexState.DEGRADED,
                    fallback_reason="Embedder not available (install Ollama)",
                )
                self._ready.set()
                
        except Exception as e:
            self._update_status(
                state=IndexState.ERROR,
                error=str(e),
            )
    
    async def _index_priority_files(self) -> None:
        """Index priority files first for fast startup.
        
        Priority files vary by project type:
        - Code: README, entry points, config files
        - Prose: outline, characters, first chapters
        - Scripts: treatment, beat sheet, script file
        - Docs: index, getting-started, overview
        """
        priority_files = get_priority_files(
            self.workspace_root,
            project_type=self._project_type,
        )
        
        if not priority_files:
            return
        
        total = len(priority_files)
        chunks = []
        
        for i, file_path in enumerate(priority_files):
            self._update_status(
                progress=int((i / total) * 50),  # 0-50% for priority
                current_file=str(file_path.relative_to(self.workspace_root)),
            )
            
            file_chunks = await self._chunk_file(file_path)
            chunks.extend(file_chunks)
        
        # Embed priority chunks
        if chunks and self._embedder:
            await self._embed_chunks(chunks)
    
    async def _index_remaining_files(self) -> None:
        """Index remaining files in background."""
        all_files = list(self._iter_indexable_files())
        priority_paths = set(get_priority_files(self.workspace_root))
        remaining = [f for f in all_files if f not in priority_paths]
        
        if not remaining:
            return
        
        total = len(remaining)
        chunks = []
        
        for i, file_path in enumerate(remaining):
            self._update_status(
                progress=50 + int((i / total) * 50),  # 50-100% for remaining
                current_file=str(file_path.relative_to(self.workspace_root)),
            )
            
            file_chunks = await self._chunk_file(file_path)
            chunks.extend(file_chunks)
            
            # Batch embed every 100 files to show progress
            if len(chunks) >= 500:
                await self._embed_chunks(chunks)
                chunks = []
        
        # Embed final batch
        if chunks and self._embedder:
            await self._embed_chunks(chunks)
    
    async def _chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Chunk a file using the appropriate content-aware chunker.
        
        Automatically selects chunking strategy based on project type and file type:
        - Python: AST-aware (functions, classes)
        - Prose: Paragraph-aware (sections, natural breaks)
        - Scripts: Scene-aware (sluglines, beats)
        - Docs: Heading-aware (sections, hierarchy)
        """
        return self._chunker_registry.chunk_file(file_path, self._project_type)
    
    def _chunk_generic(self, file_path: Path, chunk_size: int = 50) -> list[CodeChunk]:
        """Generic line-based chunking."""
        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return []
        
        lines = content.split("\n")
        if len(lines) < 3:
            return []
        
        chunks = []
        overlap = 10
        
        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i:i + chunk_size]
            if len(chunk_lines) < 3:
                continue
            
            chunk_content = "\n".join(chunk_lines)
            chunks.append(CodeChunk(
                file_path=file_path,
                start_line=i + 1,
                end_line=i + len(chunk_lines),
                content=chunk_content,
                chunk_type="block",
            ))
        
        return chunks
    
    async def _embed_chunks(self, chunks: list[CodeChunk]) -> None:
        """Embed chunks and add to index."""
        if not self._embedder or not chunks:
            return
        
        # Use embedding-optimized text for Python chunks
        texts = []
        for c in chunks:
            if hasattr(c, 'to_embedding_text'):
                texts.append(c.to_embedding_text())
            else:
                texts.append(c.content)
        
        result = await self._embedder.embed(texts)
        
        if self._index is None:
            self._index = CodebaseIndex()
        
        for chunk, vector in zip(chunks, result.vectors, strict=True):
            self._index.add_chunk(chunk, vector)
        
        self._update_status(
            chunk_count=len(self._index.chunks),
            file_count=self._index.file_count,
        )
    
    async def _watch_files(self) -> None:
        """Watch for file changes."""
        ignore_dirs = {".git", ".sunwell", "node_modules", "__pycache__", ".venv", "venv"}
        
        try:
            async for changes in awatch(
                self.workspace_root,
                recursive=True,
            ):
                for change_type, path in changes:
                    path = Path(path)
                    
                    # Skip ignored directories
                    if any(d in path.parts for d in ignore_dirs):
                        continue
                    
                    # Filter to indexable files
                    if path.suffix not in self.index_extensions:
                        continue
                    
                    self._pending_updates.add(path)
                
                # Debounce: schedule batch update
                if self._update_task is None or self._update_task.done():
                    self._update_task = asyncio.create_task(self._debounced_update())
        except Exception:
            # watchfiles not available, fall back to no watching
            pass
    
    async def _debounced_update(self) -> None:
        """Apply pending updates after debounce period."""
        await asyncio.sleep(self.debounce_ms / 1000)
        
        if not self._pending_updates:
            return
        
        paths = list(self._pending_updates)
        self._pending_updates.clear()
        
        prev_state = self._status.state
        self._update_status(state=IndexState.UPDATING)
        
        await self._update_files(paths)
        
        self._update_status(state=prev_state)
    
    async def _update_files(self, paths: list[Path]) -> None:
        """Incrementally update index for changed files."""
        if not self._index or not self._embedder:
            return
        
        for path in paths:
            # Remove old chunks for this file
            self._index.remove_file(path)
            
            # Re-chunk and embed
            if path.exists():
                chunks = await self._chunk_file(path)
                if chunks:
                    await self._embed_chunks(chunks)
        
        await self._save_cache()
    
    async def _create_embedder(self):
        """Create embedder with graceful fallback."""
        from sunwell.embedding import create_embedder
        
        try:
            return create_embedder(prefer_local=True, fallback=True)
        except Exception:
            return None
    
    def _iter_indexable_files(self):
        """Iterate over files to index."""
        ignore_dirs = {".git", ".sunwell", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        
        for path in self.workspace_root.rglob("*"):
            if path.is_file() and path.suffix in self.index_extensions:
                if not any(d in path.parts for d in ignore_dirs):
                    try:
                        if path.stat().st_size <= self.max_file_size:
                            yield path
                    except OSError:
                        continue
    
    async def _load_cached_index(self) -> bool:
        """Try to load index from cache."""
        cache_file = self.cache_dir / "index.pickle"
        meta_file = self.cache_dir / "meta.json"
        
        if not cache_file.exists() or not meta_file.exists():
            return False
        
        try:
            import json
            import pickle
            
            with open(cache_file, "rb") as f:
                self._index = pickle.load(f)
            
            meta = json.loads(meta_file.read_text())
            self._update_status(
                chunk_count=meta.get("chunk_count", 0),
                file_count=meta.get("file_count", 0),
                last_updated=datetime.fromisoformat(meta.get("updated_at", "")),
            )
            
            self._embedder = await self._create_embedder()
            return True
        except Exception:
            return False
    
    async def _verify_cache_fresh(self) -> bool:
        """Check if cached index is still fresh."""
        meta_file = self.cache_dir / "meta.json"
        
        try:
            import json
            meta = json.loads(meta_file.read_text())
            cached_hash = meta.get("content_hash")
            current_hash = await self._compute_content_hash()
            return cached_hash == current_hash
        except Exception:
            return False
    
    async def _compute_content_hash(self) -> str:
        """Compute hash of all indexable file mtimes."""
        import hashlib
        
        mtimes = []
        for path in sorted(self._iter_indexable_files()):
            try:
                mtimes.append(f"{path}:{path.stat().st_mtime}")
            except OSError:
                continue
        
        return hashlib.md5("\n".join(mtimes).encode()).hexdigest()
    
    async def _save_cache(self) -> None:
        """Save index to cache."""
        if not self._index:
            return
        
        import json
        import pickle
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Save index
        with open(self.cache_dir / "index.pickle", "wb") as f:
            pickle.dump(self._index, f)
        
        # Save metadata
        meta = {
            "content_hash": await self._compute_content_hash(),
            "chunk_count": len(self._index.chunks),
            "file_count": self._index.file_count,
            "updated_at": datetime.now().isoformat(),
        }
        (self.cache_dir / "meta.json").write_text(json.dumps(meta, indent=2))
```

---

### Part 4: Graceful Degradation

```python
# src/sunwell/indexing/fallback.py

"""SmartContext - Graceful degradation from semantic to grep to file list."""

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sunwell.indexing.service import IndexingService


@dataclass
class ContextResult:
    """Result of context retrieval."""
    source: str  # 'semantic', 'grep', 'file_list'
    quality: float  # 0.0-1.0
    content: str
    chunks_used: int = 0


@dataclass
class SmartContext:
    """Context provider that degrades gracefully.
    
    Fallback chain:
    1. Semantic index (quality=1.0) - Best, uses embeddings
    2. Grep search (quality=0.6) - Fallback, keyword matching
    3. File listing (quality=0.3) - Minimal, just shows structure
    """
    
    indexer: IndexingService | None
    workspace_root: Path
    
    async def get_context(self, query: str, max_chunks: int = 5) -> ContextResult:
        """Get best available context for a query."""
        
        # Tier 1: Full semantic search (best)
        if self.indexer and self.indexer.is_ready:
            chunks = await self.indexer.query(query, top_k=max_chunks)
            if chunks:
                return ContextResult(
                    source="semantic",
                    quality=1.0,
                    content=self._format_chunks(chunks),
                    chunks_used=len(chunks),
                )
        
        # Tier 2: Grep-based search (fallback)
        grep_results = await self._grep_search(query)
        if grep_results:
            return ContextResult(
                source="grep",
                quality=0.6,
                content=self._format_grep_results(grep_results),
                chunks_used=len(grep_results),
            )
        
        # Tier 3: File listing (minimal)
        files = self._list_relevant_files(query)
        return ContextResult(
            source="file_list",
            quality=0.3,
            content=self._format_file_list(files),
            chunks_used=0,
        )
    
    async def _grep_search(self, query: str, max_results: int = 10) -> list[dict]:
        """Fall back to grep-based keyword search."""
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        
        results = []
        for keyword in keywords[:3]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "rg", "--json", "-i", "-C", "2", keyword,
                    str(self.workspace_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                results.extend(self._parse_rg_json(stdout.decode()))
            except Exception:
                pass
        
        # Deduplicate by file:line
        seen = set()
        unique = []
        for r in results:
            key = f"{r['file']}:{r['line']}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return unique[:max_results]
    
    def _extract_keywords(self, query: str) -> list[str]:
        """Extract searchable keywords from query."""
        # Remove common words
        stopwords = {"the", "a", "an", "is", "are", "how", "does", "what", "where", "when", "why", "can", "do", "this", "that", "it", "to", "for", "in", "on", "with"}
        words = query.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords
    
    def _parse_rg_json(self, output: str) -> list[dict]:
        """Parse ripgrep JSON output."""
        import json
        results = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data.get("data", {})
                    results.append({
                        "file": match_data.get("path", {}).get("text", ""),
                        "line": match_data.get("line_number", 0),
                        "content": match_data.get("lines", {}).get("text", ""),
                    })
            except json.JSONDecodeError:
                continue
        return results
    
    def _list_relevant_files(self, query: str, max_files: int = 20) -> list[Path]:
        """List files that might be relevant based on name."""
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        
        relevant = []
        for path in self.workspace_root.rglob("*"):
            if path.is_file():
                name_lower = path.name.lower()
                if any(kw in name_lower for kw in keywords):
                    relevant.append(path)
        
        return relevant[:max_files]
    
    def _format_chunks(self, chunks) -> str:
        """Format semantic search results."""
        sections = ["## Relevant Code\n"]
        for chunk in chunks:
            sections.append(f"### {chunk.reference}\n")
            sections.append(f"```\n{chunk.content}\n```\n")
        return "\n".join(sections)
    
    def _format_grep_results(self, results: list[dict]) -> str:
        """Format grep results."""
        sections = ["## Search Results (grep)\n"]
        for r in results:
            sections.append(f"**{r['file']}:{r['line']}**\n")
            sections.append(f"```\n{r['content'].strip()}\n```\n")
        return "\n".join(sections)
    
    def _format_file_list(self, files: list[Path]) -> str:
        """Format file listing."""
        if not files:
            return "No relevant files found."
        
        sections = ["## Potentially Relevant Files\n"]
        for f in files:
            rel = f.relative_to(self.workspace_root)
            sections.append(f"- `{rel}`")
        return "\n".join(sections)
```

---

### Part 5: Observability

```python
# src/sunwell/indexing/metrics.py

"""Index health metrics for observability."""

from dataclasses import dataclass, field
from datetime import datetime
from collections import deque


@dataclass
class IndexMetrics:
    """Telemetry for index health monitoring."""
    
    build_time_ms: int = 0
    chunk_count: int = 0
    file_count: int = 0
    embedding_time_ms: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    query_latencies: deque[int] = field(default_factory=lambda: deque(maxlen=100))
    last_build: datetime | None = None
    last_query: datetime | None = None
    errors: deque[str] = field(default_factory=lambda: deque(maxlen=10))
    
    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate (0.0-1.0)."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    @property
    def avg_query_latency_ms(self) -> float:
        """Average query latency in milliseconds."""
        if not self.query_latencies:
            return 0.0
        return sum(self.query_latencies) / len(self.query_latencies)
    
    def record_query(self, latency_ms: int) -> None:
        """Record a query latency."""
        self.query_latencies.append(latency_ms)
        self.last_query = datetime.now()
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1
    
    def record_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(f"{datetime.now().isoformat()}: {error}")
    
    def is_healthy(self) -> bool:
        """Check if index is healthy."""
        # Queries should be <500ms on average
        if self.avg_query_latency_ms > 500:
            return False
        # Should have indexed something
        if self.chunk_count == 0:
            return False
        return True
    
    def to_json(self) -> dict:
        """Export metrics as JSON."""
        return {
            "build_time_ms": self.build_time_ms,
            "chunk_count": self.chunk_count,
            "file_count": self.file_count,
            "embedding_time_ms": self.embedding_time_ms,
            "cache_hit_rate": self.cache_hit_rate,
            "avg_query_latency_ms": self.avg_query_latency_ms,
            "last_build": self.last_build.isoformat() if self.last_build else None,
            "last_query": self.last_query.isoformat() if self.last_query else None,
            "is_healthy": self.is_healthy(),
            "recent_errors": list(self.errors),
        }
```

---

### Part 6: Studio Integration

#### Svelte Store

```typescript
// studio/src/stores/indexing.svelte.ts

/**
 * Indexing Store — Reactive state for codebase indexing (RFC-108)
 */

import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';

// ═══════════════════════════════════════════════════════════════
// TYPES (from IPC contract)
// ═══════════════════════════════════════════════════════════════

export type IndexState = 
  | 'no_index' | 'checking' | 'loading' | 'building' 
  | 'verifying' | 'ready' | 'updating' | 'degraded' | 'error';

export interface IndexStatus {
  state: IndexState;
  progress?: number;
  currentFile?: string;
  chunkCount?: number;
  fileCount?: number;
  lastUpdated?: string;
  error?: string;
  fallbackReason?: string;
  priorityComplete?: boolean;
  estimatedTimeMs?: number;
}

export interface IndexChunk {
  id: string;
  filePath: string;
  startLine: number;
  endLine: number;
  content: string;
  chunkType: string;
  name?: string;
  score: number;
}

export interface IndexResult {
  chunks: IndexChunk[];
  fallbackUsed: boolean;
  queryTimeMs: number;
}

export interface IndexSettings {
  autoIndex: boolean;
  watchFiles: boolean;
  embeddingModel: string;
  maxFileSize: number;
  excludePatterns: string[];
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _status = $state<IndexStatus>({ state: 'no_index' });
let _settings = $state<IndexSettings>({
  autoIndex: true,
  watchFiles: true,
  embeddingModel: 'all-minilm',
  maxFileSize: 100000,
  excludePatterns: [],
});
let _lastResult = $state<IndexResult | null>(null);
let _unsubscribe: UnlistenFn | null = null;

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

function isReady(): boolean {
  return _status.state === 'ready' || _status.state === 'updating';
}

function isBuilding(): boolean {
  return _status.state === 'building' || _status.state === 'loading';
}

function isDegraded(): boolean {
  return _status.state === 'degraded';
}

function statusLabel(): string {
  switch (_status.state) {
    case 'no_index': return 'Not indexed';
    case 'checking': return 'Checking...';
    case 'loading': return 'Loading...';
    case 'building': return `Indexing ${_status.progress ?? 0}%`;
    case 'verifying': return 'Verifying...';
    case 'ready': return `Indexed (${_status.chunkCount ?? 0})`;
    case 'updating': return 'Updating...';
    case 'degraded': return 'Grep mode';
    case 'error': return 'Error';
  }
}

function statusIcon(): string {
  switch (_status.state) {
    case 'no_index': return '⚠️';
    case 'checking':
    case 'loading':
    case 'building':
    case 'verifying':
    case 'updating': return '⟳';
    case 'ready': return '🔮';
    case 'degraded': return '⚠️';
    case 'error': return '❌';
  }
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const indexingStore = {
  get status() { return _status; },
  get settings() { return _settings; },
  get lastResult() { return _lastResult; },
  get isReady() { return isReady(); },
  get isBuilding() { return isBuilding(); },
  get isDegraded() { return isDegraded(); },
  get statusLabel() { return statusLabel(); },
  get statusIcon() { return statusIcon(); },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Initialize indexing for a workspace.
 * Call this when a project is opened.
 */
export async function initIndexing(workspacePath: string): Promise<void> {
  // Subscribe to status events
  if (_unsubscribe) {
    _unsubscribe();
  }
  
  _unsubscribe = await listen<IndexStatus>('index-status', (event) => {
    _status = event.payload;
  });
  
  // Start the service
  if (_settings.autoIndex) {
    await invoke('start_indexing_service', { workspacePath });
  }
}

/**
 * Query the index.
 */
export async function queryIndex(
  text: string, 
  topK: number = 10
): Promise<IndexResult> {
  const result = await invoke<IndexResult>('query_index', { 
    query: { text, topK } 
  });
  _lastResult = result;
  return result;
}

/**
 * Force rebuild the index.
 */
export async function rebuildIndex(): Promise<void> {
  await invoke('rebuild_index');
}

/**
 * Update settings.
 */
export async function updateSettings(settings: Partial<IndexSettings>): Promise<void> {
  _settings = { ..._settings, ...settings };
  await invoke('set_index_settings', { settings: _settings });
}

/**
 * Stop indexing service.
 */
export async function stopIndexing(): Promise<void> {
  if (_unsubscribe) {
    _unsubscribe();
    _unsubscribe = null;
  }
  await invoke('stop_indexing_service');
  _status = { state: 'no_index' };
}

/**
 * Get current status (for initial load).
 */
export async function refreshStatus(): Promise<void> {
  _status = await invoke<IndexStatus>('get_index_status');
}
```

#### Status Component

```svelte
<!-- studio/src/components/IndexStatus.svelte -->
<script lang="ts">
  import { indexingStore, rebuildIndex } from '$stores/indexing.svelte';
  import { slide, fade } from 'svelte/transition';
  
  let showPopover = $state(false);
  let popoverTimeout: number | null = null;
  
  function handleMouseEnter() {
    popoverTimeout = window.setTimeout(() => {
      showPopover = true;
    }, 300);
  }
  
  function handleMouseLeave() {
    if (popoverTimeout) {
      clearTimeout(popoverTimeout);
    }
    showPopover = false;
  }
  
  function handleClick() {
    if (indexingStore.status.state === 'error' || indexingStore.status.state === 'degraded') {
      rebuildIndex();
    }
  }
</script>

<div 
  class="index-status"
  class:ready={indexingStore.isReady}
  class:building={indexingStore.isBuilding}
  class:degraded={indexingStore.isDegraded}
  class:error={indexingStore.status.state === 'error'}
  onmouseenter={handleMouseEnter}
  onmouseleave={handleMouseLeave}
  onclick={handleClick}
  role="status"
  aria-label={indexingStore.statusLabel}
>
  <span class="icon" class:spinning={indexingStore.isBuilding}>
    {indexingStore.statusIcon}
  </span>
  <span class="label">{indexingStore.statusLabel}</span>
  
  {#if indexingStore.isBuilding && indexingStore.status.progress}
    <div class="progress-bar">
      <div 
        class="progress-fill" 
        style="width: {indexingStore.status.progress}%"
      ></div>
    </div>
  {/if}
</div>

{#if showPopover}
  <div class="popover" transition:fade={{ duration: 150 }}>
    <div class="popover-header">
      <span class="popover-icon">{indexingStore.statusIcon}</span>
      <span class="popover-title">Codebase Index</span>
    </div>
    
    <div class="popover-body">
      {#if indexingStore.isReady}
        <div class="stat">
          <span class="stat-label">Chunks</span>
          <span class="stat-value">{indexingStore.status.chunkCount?.toLocaleString()}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Files</span>
          <span class="stat-value">{indexingStore.status.fileCount?.toLocaleString()}</span>
        </div>
        {#if indexingStore.status.lastUpdated}
          <div class="stat">
            <span class="stat-label">Updated</span>
            <span class="stat-value">{new Date(indexingStore.status.lastUpdated).toLocaleString()}</span>
          </div>
        {/if}
      {:else if indexingStore.isBuilding}
        <div class="building-info">
          <p>Indexing in progress...</p>
          {#if indexingStore.status.currentFile}
            <p class="current-file">{indexingStore.status.currentFile}</p>
          {/if}
          {#if indexingStore.status.priorityComplete}
            <p class="hint">✓ Priority files indexed, search available</p>
          {/if}
        </div>
      {:else if indexingStore.isDegraded}
        <div class="degraded-info">
          <p>Running in fallback mode</p>
          <p class="reason">{indexingStore.status.fallbackReason}</p>
          <button class="retry-btn" onclick={() => rebuildIndex()}>
            Retry with embeddings
          </button>
        </div>
      {:else if indexingStore.status.state === 'error'}
        <div class="error-info">
          <p>Indexing failed</p>
          <p class="error">{indexingStore.status.error}</p>
          <button class="retry-btn" onclick={() => rebuildIndex()}>
            Retry
          </button>
        </div>
      {/if}
    </div>
    
    <div class="popover-footer">
      <button class="action-btn" onclick={() => rebuildIndex()}>
        Rebuild Index
      </button>
    </div>
  </div>
{/if}

<style>
  .index-status {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
  }
  
  .index-status:hover {
    background: var(--bg-hover);
  }
  
  .index-status.ready {
    background: color-mix(in srgb, var(--success) 15%, transparent);
    color: var(--success);
  }
  
  .index-status.building {
    background: color-mix(in srgb, var(--info) 15%, transparent);
    color: var(--info);
  }
  
  .index-status.degraded {
    background: color-mix(in srgb, var(--warning) 15%, transparent);
    color: var(--warning);
  }
  
  .index-status.error {
    background: color-mix(in srgb, var(--error) 15%, transparent);
    color: var(--error);
  }
  
  .icon {
    font-size: 14px;
  }
  
  .icon.spinning {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  .progress-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--bg-secondary);
    border-radius: 0 0 6px 6px;
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--info);
    transition: width 0.3s ease;
  }
  
  .popover {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 280px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-lg);
    z-index: 100;
  }
  
  .popover-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }
  
  .popover-title {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .popover-body {
    padding: 12px 16px;
  }
  
  .stat {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
  }
  
  .stat-label {
    color: var(--text-secondary);
  }
  
  .stat-value {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .current-file {
    font-size: 11px;
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .hint {
    font-size: 11px;
    color: var(--success);
    margin-top: 8px;
  }
  
  .reason, .error {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 4px;
  }
  
  .error {
    color: var(--error);
  }
  
  .retry-btn, .action-btn {
    margin-top: 8px;
    padding: 6px 12px;
    font-size: 12px;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    transition: background 0.2s;
  }
  
  .retry-btn {
    background: var(--info);
    color: white;
  }
  
  .popover-footer {
    padding: 8px 16px;
    border-top: 1px solid var(--border);
  }
  
  .action-btn {
    width: 100%;
    background: var(--bg-secondary);
    color: var(--text-secondary);
  }
  
  .action-btn:hover {
    background: var(--bg-hover);
  }
</style>
```

---

### Part 7: Tauri Backend

```rust
// studio/src-tauri/src/indexing.rs

//! Codebase indexing Tauri commands (RFC-108)

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Arc;
use tauri::{AppHandle, Manager, State};
use tokio::sync::RwLock;

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IndexState {
    NoIndex,
    Checking,
    Loading,
    Building,
    Verifying,
    Ready,
    Updating,
    Degraded,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexStatus {
    pub state: IndexState,
    pub progress: Option<u32>,
    pub current_file: Option<String>,
    pub chunk_count: Option<u32>,
    pub file_count: Option<u32>,
    pub last_updated: Option<String>,
    pub error: Option<String>,
    pub fallback_reason: Option<String>,
    pub priority_complete: Option<bool>,
    pub estimated_time_ms: Option<u32>,
}

impl Default for IndexStatus {
    fn default() -> Self {
        Self {
            state: IndexState::NoIndex,
            progress: None,
            current_file: None,
            chunk_count: None,
            file_count: None,
            last_updated: None,
            error: None,
            fallback_reason: None,
            priority_complete: None,
            estimated_time_ms: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexQuery {
    pub text: String,
    pub top_k: Option<u32>,
    pub threshold: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexChunk {
    pub id: String,
    pub file_path: String,
    pub start_line: u32,
    pub end_line: u32,
    pub content: String,
    pub chunk_type: String,
    pub name: Option<String>,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexResult {
    pub chunks: Vec<IndexChunk>,
    pub fallback_used: bool,
    pub query_time_ms: u32,
    pub total_chunks_searched: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexSettings {
    pub auto_index: bool,
    pub watch_files: bool,
    pub embedding_model: String,
    pub max_file_size: u32,
    pub exclude_patterns: Vec<String>,
}

impl Default for IndexSettings {
    fn default() -> Self {
        Self {
            auto_index: true,
            watch_files: true,
            embedding_model: "all-minilm".to_string(),
            max_file_size: 100_000,
            exclude_patterns: vec![],
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

pub struct IndexingState {
    pub status: Arc<RwLock<IndexStatus>>,
    pub settings: Arc<RwLock<IndexSettings>>,
    pub workspace_root: Arc<RwLock<Option<PathBuf>>>,
    pub child_process: Arc<RwLock<Option<tokio::process::Child>>>,
}

impl Default for IndexingState {
    fn default() -> Self {
        Self {
            status: Arc::new(RwLock::new(IndexStatus::default())),
            settings: Arc::new(RwLock::new(IndexSettings::default())),
            workspace_root: Arc::new(RwLock::new(None)),
            child_process: Arc::new(RwLock::new(None)),
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub async fn start_indexing_service(
    app: AppHandle,
    state: State<'_, IndexingState>,
    workspace_path: String,
) -> Result<(), String> {
    let path = PathBuf::from(&workspace_path);
    *state.workspace_root.write().await = Some(path.clone());
    
    let app_clone = app.clone();
    let status = state.status.clone();
    let child_holder = state.child_process.clone();
    
    // Spawn background indexing task
    tokio::spawn(async move {
        use tokio::io::{AsyncBufReadExt, BufReader};
        
        let mut child = match tokio::process::Command::new("sunwell")
            .args(["index", "build", "--json", "--progress"])
            .current_dir(&path)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
        {
            Ok(c) => c,
            Err(e) => {
                let mut s = status.write().await;
                s.state = IndexState::Error;
                s.error = Some(format!("Failed to start sunwell: {}", e));
                let _ = app_clone.emit("index-status", s.clone());
                return;
            }
        };
        
        // Store child process for cleanup
        *child_holder.write().await = Some(child);
        
        // Get the child back (this is a bit awkward but necessary)
        let mut child = child_holder.write().await.take().unwrap();
        
        if let Some(stdout) = child.stdout.take() {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();
            
            while let Ok(Some(line)) = lines.next_line().await {
                if let Ok(update) = serde_json::from_str::<IndexStatus>(&line) {
                    *status.write().await = update.clone();
                    let _ = app_clone.emit("index-status", update);
                }
            }
        }
        
        let exit_status = child.wait().await;
        
        // Check exit status
        if let Ok(status_code) = exit_status {
            if !status_code.success() {
                let mut s = status.write().await;
                s.state = IndexState::Error;
                s.error = Some(format!("Indexing exited with code {:?}", status_code.code()));
                let _ = app_clone.emit("index-status", s.clone());
            }
        }
    });
    
    Ok(())
}

#[tauri::command]
pub async fn stop_indexing_service(
    state: State<'_, IndexingState>,
) -> Result<(), String> {
    if let Some(mut child) = state.child_process.write().await.take() {
        let _ = child.kill().await;
    }
    
    let mut status = state.status.write().await;
    *status = IndexStatus::default();
    
    Ok(())
}

#[tauri::command]
pub async fn query_index(
    query: IndexQuery,
    state: State<'_, IndexingState>,
) -> Result<IndexResult, String> {
    let workspace_root = state.workspace_root.read().await;
    let Some(root) = workspace_root.as_ref() else {
        return Ok(IndexResult {
            chunks: vec![],
            fallback_used: true,
            query_time_ms: 0,
            total_chunks_searched: 0,
        });
    };
    
    let top_k = query.top_k.unwrap_or(10);
    
    let output = std::process::Command::new("sunwell")
        .args([
            "index", "query", 
            "--json", 
            "--top-k", &top_k.to_string(),
            &query.text,
        ])
        .current_dir(root)
        .output()
        .map_err(|e| e.to_string())?;
    
    if output.status.success() {
        serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
    } else {
        Ok(IndexResult {
            chunks: vec![],
            fallback_used: true,
            query_time_ms: 0,
            total_chunks_searched: 0,
        })
    }
}

#[tauri::command]
pub async fn get_index_status(
    state: State<'_, IndexingState>,
) -> Result<IndexStatus, String> {
    Ok(state.status.read().await.clone())
}

#[tauri::command]
pub async fn rebuild_index(
    app: AppHandle,
    state: State<'_, IndexingState>,
) -> Result<(), String> {
    let workspace_root = state.workspace_root.read().await;
    let Some(root) = workspace_root.as_ref() else {
        return Err("No workspace opened".into());
    };
    
    // Clear cache
    let cache_dir = root.join(".sunwell").join("index");
    if cache_dir.exists() {
        let _ = std::fs::remove_dir_all(&cache_dir);
    }
    
    // Restart indexing
    drop(workspace_root);
    start_indexing_service(app, state, root.to_string_lossy().to_string()).await
}

#[tauri::command]
pub async fn set_index_settings(
    settings: IndexSettings,
    state: State<'_, IndexingState>,
) -> Result<(), String> {
    *state.settings.write().await = settings;
    Ok(())
}

#[tauri::command]
pub async fn get_index_metrics(
    state: State<'_, IndexingState>,
) -> Result<serde_json::Value, String> {
    let workspace_root = state.workspace_root.read().await;
    let Some(root) = workspace_root.as_ref() else {
        return Err("No workspace opened".into());
    };
    
    let output = std::process::Command::new("sunwell")
        .args(["index", "metrics", "--json"])
        .current_dir(root)
        .output()
        .map_err(|e| e.to_string())?;
    
    if output.status.success() {
        serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
    } else {
        Err("Failed to get metrics".into())
    }
}
```

---

### Part 8: CLI Commands

```python
# src/sunwell/cli/index_cmd.py

"""CLI commands for codebase indexing (RFC-108)."""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from sunwell.indexing.service import IndexingService, IndexState


console = Console()


@click.group()
def index() -> None:
    """Codebase indexing commands."""
    pass


@index.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output for Studio integration")
@click.option("--progress", is_flag=True, help="Stream progress updates")
@click.option("--force", is_flag=True, help="Force full rebuild (ignore cache)")
def build(json_output: bool, progress: bool, force: bool) -> None:
    """Build or update the codebase index."""
    asyncio.run(_build_index(json_output, progress, force))


async def _build_index(json_output: bool, progress: bool, force: bool) -> None:
    """Build index with progress reporting."""
    cwd = Path.cwd()
    
    # Clear cache if forced
    if force:
        cache_dir = cwd / ".sunwell" / "index"
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
    
    service = IndexingService(workspace_root=cwd)
    
    if json_output:
        # Stream JSON for Tauri
        def on_status(status):
            print(json.dumps({
                "state": status.state.value,
                "progress": status.progress,
                "current_file": status.current_file,
                "chunk_count": status.chunk_count,
                "file_count": status.file_count,
                "last_updated": status.last_updated.isoformat() if status.last_updated else None,
                "error": status.error,
                "fallback_reason": status.fallback_reason,
                "priority_complete": status.priority_complete,
            }), flush=True)
        
        service.on_status_change = on_status
        await service.start()
        await service.wait_ready(timeout=300)  # 5 min timeout for large repos
        
    elif progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress_bar:
            task = progress_bar.add_task("Indexing...", total=100)
            
            def on_status(status):
                progress_bar.update(
                    task,
                    completed=status.progress,
                    description=f"Indexing: {status.current_file or '...'}"
                )
            
            service.on_status_change = on_status
            await service.start()
            await service.wait_ready(timeout=300)
            
            progress_bar.update(task, completed=100, description="Done!")
        
        console.print(f"[green]✓[/green] Indexed {service.status.chunk_count} chunks from {service.status.file_count} files")
    else:
        # Simple output
        console.print("[dim]Building index...[/dim]")
        await service.start()
        await service.wait_ready(timeout=300)
        
        if service.status.state == IndexState.READY:
            project_type = service._project_type.value.title()
            console.print(f"[green]✓[/green] Indexed {service.status.chunk_count} chunks from {service.status.file_count} files")
            console.print(f"[dim]Project type: {project_type}[/dim]")
        elif service.status.state == IndexState.DEGRADED:
            console.print(f"[yellow]⚠️[/yellow] Running in fallback mode: {service.status.fallback_reason}")
        else:
            console.print(f"[red]✗[/red] Indexing failed: {service.status.error}")


@index.command()
@click.argument("query")
@click.option("--top-k", default=10, help="Number of results")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def query(query: str, top_k: int, json_output: bool) -> None:
    """Query the codebase index."""
    asyncio.run(_query_index(query, top_k, json_output))


async def _query_index(query_text: str, top_k: int, json_output: bool) -> None:
    """Query the index."""
    cwd = Path.cwd()
    service = IndexingService(workspace_root=cwd)
    
    await service.start()
    if not await service.wait_ready(timeout=5):
        if json_output:
            print(json.dumps({"error": "Index not ready", "chunks": [], "fallback_used": True}))
        else:
            console.print("[yellow]Index not ready. Building...[/yellow]")
        return
    
    import time
    start = time.perf_counter()
    chunks = await service.query(query_text, top_k=top_k)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    
    if json_output:
        print(json.dumps({
            "chunks": [
                {
                    "id": c.id,
                    "file_path": str(c.file_path),
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "content": c.content,
                    "chunk_type": c.chunk_type,
                    "name": c.name,
                    "score": 0.0,  # TODO: Add score to query result
                }
                for c in chunks
            ],
            "fallback_used": False,
            "query_time_ms": elapsed_ms,
            "total_chunks_searched": service.status.chunk_count or 0,
        }))
    else:
        if not chunks:
            console.print("[dim]No results found[/dim]")
            return
        
        table = Table(title=f"Results for: {query_text}")
        table.add_column("File", style="cyan")
        table.add_column("Lines", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Name")
        
        for chunk in chunks:
            table.add_row(
                str(chunk.file_path.relative_to(cwd)),
                f"{chunk.start_line}-{chunk.end_line}",
                chunk.chunk_type,
                chunk.name or "",
            )
        
        console.print(table)
        console.print(f"[dim]Query time: {elapsed_ms}ms[/dim]")


@index.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def status(json_output: bool) -> None:
    """Show index status."""
    asyncio.run(_show_status(json_output))


async def _show_status(json_output: bool) -> None:
    """Show current index status."""
    cwd = Path.cwd()
    cache_dir = cwd / ".sunwell" / "index"
    meta_file = cache_dir / "meta.json"
    
    if not meta_file.exists():
        if json_output:
            print(json.dumps({"state": "no_index", "error": "No index found"}))
        else:
            console.print("[yellow]No index found. Run `sunwell index build`[/yellow]")
        return
    
    import json as json_lib
    meta = json_lib.loads(meta_file.read_text())
    
    if json_output:
        print(json.dumps({
            "state": "ready",
            "chunk_count": meta.get("chunk_count", 0),
            "file_count": meta.get("file_count", 0),
            "last_updated": meta.get("updated_at"),
            "content_hash": meta.get("content_hash"),
        }))
    else:
        console.print("[bold]Index Status[/bold]")
        console.print(f"  State: [green]Ready[/green]")
        console.print(f"  Chunks: {meta.get('chunk_count', 0)}")
        console.print(f"  Files: {meta.get('file_count', 0)}")
        console.print(f"  Updated: {meta.get('updated_at', 'unknown')}")


@index.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def metrics(json_output: bool) -> None:
    """Show index metrics for debugging."""
    # Placeholder - metrics would come from IndexingService
    if json_output:
        print(json.dumps({
            "build_time_ms": 0,
            "avg_query_latency_ms": 0,
            "cache_hit_rate": 0,
            "is_healthy": True,
        }))
    else:
        console.print("[dim]Metrics not yet implemented[/dim]")


@index.command()
def clear() -> None:
    """Clear the index cache."""
    cache_dir = Path.cwd() / ".sunwell" / "index"
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)
        console.print("[green]✓[/green] Index cache cleared")
    else:
        console.print("[yellow]No index cache found[/yellow]")
```

---

## Implementation Plan

### Phase 1: Core Service (8 hours)

| Task | Description | Size | Files |
|------|-------------|------|-------|
| 1.1 | Create `IndexingService` with state machine | L | `indexing/service.py` |
| 1.2 | Implement project type detection | M | `indexing/project_type.py` |
| 1.3 | Implement chunker registry | S | `indexing/chunkers/__init__.py` |
| 1.4 | Implement AST-aware Python chunker | M | `indexing/chunkers/python_ast.py` |
| 1.5 | Implement prose paragraph chunker | M | `indexing/chunkers/prose.py` |
| 1.6 | Implement screenplay scene chunker | M | `indexing/chunkers/screenplay.py` |
| 1.7 | Implement priority file detection | S | `indexing/priority.py` |
| 1.8 | Implement file watching with `watchfiles` | M | `indexing/service.py` |
| 1.9 | Implement graceful fallback (`SmartContext`) | M | `indexing/fallback.py` |
| 1.10 | Add observability metrics | S | `indexing/metrics.py` |

### Phase 2: CLI Integration (3 hours)

| Task | Description | Size | Files |
|------|-------------|------|-------|
| 2.1 | Remove `--smart` flag from chat | S | `cli/chat.py` |
| 2.2 | Add `sunwell index` command group | M | `cli/index_cmd.py` |
| 2.3 | Integrate service into chat loop | M | `cli/chat.py` |
| 2.4 | Update `do_cmd` to use `SmartContext` | S | `cli/do_cmd.py` |
| 2.5 | Add JSON streaming for Studio | S | `cli/index_cmd.py` |

### Phase 3: Studio Integration (4 hours)

| Task | Description | Size | Files |
|------|-------------|------|-------|
| 3.1 | Add Tauri indexing commands | M | `src-tauri/src/indexing.rs` |
| 3.2 | Register commands in main.rs | S | `src-tauri/src/main.rs` |
| 3.3 | Create `indexing.svelte.ts` store | M | `stores/indexing.svelte.ts` |
| 3.4 | Create `IndexStatus.svelte` component | M | `components/IndexStatus.svelte` |
| 3.5 | Wire to App.svelte header | S | `App.svelte` |
| 3.6 | Trigger indexing on project open | S | `stores/project.svelte.ts` |

### Phase 4: Testing & Polish (3 hours)

| Task | Description | Size | Files |
|------|-------------|------|-------|
| 4.1 | Unit tests for IndexingService | M | `tests/test_indexing.py` |
| 4.2 | Unit tests for AST chunker | M | `tests/test_python_ast.py` |
| 4.3 | Integration tests for fallback | S | `tests/test_fallback.py` |
| 4.4 | Performance testing (large repos) | M | Manual |
| 4.5 | Documentation | S | This RFC |

**Total: ~18 hours**

---

## Success Criteria

| Criterion | Test | Pass/Fail |
|-----------|------|-----------|
| No `--smart` flag | `sunwell chat --help` has no `--smart` option | |
| Background indexing | Chat responds immediately, index builds in parallel | |
| Project type detection | Code/prose/script/docs correctly identified | |
| Priority indexing | Hot files indexed within 5 seconds | |
| Incremental updates | File save triggers partial re-index only | |
| Graceful fallback | Works without Ollama (grep-based search) | |
| AST chunking (code) | Python functions/classes extracted as single chunks | |
| Paragraph chunking (prose) | Novels chunked by paragraphs/sections | |
| Scene chunking (scripts) | Screenplays chunked by INT./EXT. scenes | |
| Studio status | Index status visible in header pill | |
| Studio popover | Click shows details (chunks, files, project type) | |
| Query works | Semantic search returns relevant results | |
| Large project | 10k files indexes in <3 minutes | |

---

## Migration

### For Users

```bash
# Old way (deprecated)
sunwell chat --smart

# New way (just works)
sunwell chat
```

### Breaking Changes

- `--smart` flag removed (always enabled)
- `--rag` flag removed (always enabled)
- Index cache location unchanged (`.sunwell/index/`)

### Environment Variables

```bash
# Disable auto-indexing (for CI or low-resource environments)
SUNWELL_NO_INDEX=1 sunwell chat

# Force specific embedding model
SUNWELL_EMBEDDING_MODEL=nomic-embed-text sunwell chat
```

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Background task crashes | Index never ready | Low | Graceful fallback to grep |
| Large repos slow | Bad first experience | Medium | Priority indexing, streaming progress |
| watchfiles unavailable | No incremental updates | Low | Fallback to mtime check on query |
| Memory pressure | OOM on huge repos | Low | Streaming embedding, chunk limits |
| AST parsing fails | Chunk quality degraded | Low | Fallback to line-based chunking |
| Ollama not installed | No semantic search | Medium | Clear messaging, one-click install |

---

## Related RFCs

- **RFC-107**: Shortcut Execution Path — Uses `SmartContext` for skill execution
- **RFC-045**: Project Intelligence — Decision/pattern stores (uses same index)
- **RFC-050**: Fast Bootstrap — Initial project scanning (feeds priority files)
- **RFC-070**: DORI Lens Migration — Skills use context from index
- **RFC-103**: Workspace-Aware Scanning — Links source repos to docs

---

## Appendix: Embedding Model Comparison

| Model | Dimensions | Speed | Quality | Local |
|-------|------------|-------|---------|-------|
| `all-minilm` | 384 | ⚡ Fast | Good | ✅ Ollama |
| `nomic-embed-text` | 768 | Medium | Better | ✅ Ollama |
| `text-embedding-3-small` | 1536 | Medium | Best | ❌ OpenAI |
| `HashEmbedding` (fallback) | 256 | ⚡⚡ | Basic | ✅ Local |

**Default**: `all-minilm` via Ollama (best speed/quality tradeoff for code)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-23 | Initial draft |
| 2026-01-23 | Enhanced: Added user journeys, state machine, IPC contract, AST chunking (P0), observability |
| 2026-01-23 | Domain-agnostic: Renamed to "Project Indexing", added project type detection (code/prose/script/docs/mixed), prose chunker, screenplay chunker, chunker registry |