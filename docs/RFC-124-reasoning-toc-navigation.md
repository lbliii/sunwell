# RFC-124: Reasoning-based ToC Navigation

**Status**: Ready for Review  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Updated**: 2026-01-24  
**Depends on**: RFC-108 (SmartContext), RFC-045 (Project Intelligence)

## Summary

Add reasoning-based document/codebase navigation using hierarchical Table of Contents (ToC) indexes that live in the LLM's context window. Instead of relying solely on vector similarity, let the Naaru reason about WHERE to look based on document structure.

**Key insight**: Semantic similarity ≠ relevance. When a user asks "how does authentication work?", the answer is in `auth/` or `middleware.py`, not necessarily the chunk with the highest embedding similarity to the word "authentication".

## Motivation

### Problem

Sunwell's current RAG (`IndexingService`, `SmartContext`) relies on vector embeddings:

```python
# Current approach: sunwell/indexing/service.py:248-263
result = await self._embedder.embed([text])
query_vector = result.vectors[0].tolist()

for chunk in self._index.chunks:
    score = self._cosine_similarity(query_vector, chunk_embedding)
```

This fails in predictable ways:

1. **Query-knowledge mismatch**: "Where do we handle rate limiting?" → Matches chunks containing "rate" and "limit" words, misses `middleware/throttle.py`
2. **Semantic similarity ≠ relevance**: A docstring saying "this handles authentication" ranks higher than the actual auth implementation
3. **No structural awareness**: Ignores that `auth/` is a directory full of auth-related code
4. **Cross-reference blindness**: Comments like `# See security/audit.py for audit logging` aren't followed

### Inspiration: PageIndex

PageIndex ([pageindex.ai/blog/pageindex-intro](https://pageindex.ai/blog/pageindex-intro)) proposes "vectorless RAG" where:

1. Build a JSON-based hierarchical ToC
2. Put the ToC **in context** (not external vector DB)
3. LLM **reasons** about which section to read
4. Iteratively navigate: read ToC → select → extract → repeat if needed

This is how humans navigate codebases: scan structure, make educated guesses about where things live, refine.

### User Stories

**"Where is X implemented?":**
> "I need to understand how Sunwell handles model routing. Where should I look?"
> 
> Current: Vector search returns scattered snippets with "model" and "routing" keywords.
> Proposed: Naaru reads project ToC, reasons: "model routing → likely `routing/` or `models/router.py` → navigates there directly.

**"How does this module work?":**
> "Explain how the Naaru orchestration works."
> 
> Current: Retrieves chunks that mention "Naaru", may miss key coordination logic.
> Proposed: Naaru reads `naaru/` ToC structure, systematically reads overview → planners → convergence → resonance.

**"Find related code":**
> "This auth code mentions 'see middleware for token validation'. Find it."
>
> Current: No awareness of cross-references.
> Proposed: Parses comment, navigates to `middleware/` and locates token validation.

---

## Goals

1. **Hierarchical project ToC**: Build navigable structure from AST/file analysis
2. **In-context navigation**: ToC lives in LLM context, not external DB
3. **Reasoning-based selection**: Naaru decides where to look based on query intent
4. **Iterative refinement**: Navigate → extract → is it enough? → navigate more
5. **Graceful integration**: Augments existing vector RAG, doesn't replace it

## Non-Goals

- Replacing vector embeddings entirely (they're still useful for similarity)
- Deep semantic parsing of all languages (Python first, others later)
- Real-time ToC updates (rebuild on explicit refresh)
- Cross-project navigation

---

## Existing Infrastructure

| Feature | Existing Code | Gap Filled by This RFC |
|---------|---------------|------------------------|
| File chunking | `IndexingService` at `indexing/service.py:71` | Hierarchical structure over flat chunks |
| AST analysis | `CodebaseAnalyzer` at `intelligence/codebase.py:101` | ToC generation from call/import graphs |
| Multi-topology | `UnifiedMemoryStore` at `simulacrum/topology/unified_store.py:37` | Structural dimension for navigation |
| Fallback chain | `SmartContext` at `indexing/fallback.py:31` | New "structural reasoning" tier |
| Project context | `ProjectContext` at `intelligence/context.py:31` | ToC integration |

---

## Design Alternatives

### Option A: In-Context JSON ToC (Recommended)

Store project structure as a navigable JSON tree. Put the ToC directly in the LLM's context for reasoning.

**Pros**:
- LLM can reason about structure without external lookups
- Fast (no embeddings needed for navigation)
- Matches PageIndex's proven approach
- Works offline

**Cons**:
- ToC consumes context window tokens (see token budget analysis below)
- Requires rebuild on project changes
- Deep hierarchies need pagination (strategy defined below)

**Token budget analysis**:

| Project Size | Files | Nodes (est.) | Tokens/Node | Total Tokens | Strategy |
|--------------|-------|--------------|-------------|--------------|----------|
| Small (<100 files) | 100 | ~150 | 15 | ~2,250 | Full ToC in context |
| Medium (100-500 files) | 300 | ~500 | 15 | ~7,500 | Depth=2 + on-demand expansion |
| Large (500-1000 files) | 800 | ~1,200 | 15 | ~18,000 | Depth=1 + subtree pagination |
| Very large (>1000 files) | 1500+ | ~2,500+ | 15 | ~37,500+ | Hybrid mode required |

**Compact node format** (~15 tokens per node):
```json
{"id":"naaru.harmonic","t":"module","s":"Harmonic resonance coordination","c":["naaru.planners"]}
```

**Pagination strategy for large codebases**:
1. **Depth-limited initial view**: Show root + depth=1 children (~50-100 nodes, ~1,500 tokens)
2. **On-demand expansion**: Navigator requests subtree expansion via `get_subtree(node_id)`
3. **Subtree budget**: Each expansion adds ~500 tokens max
4. **Total budget cap**: 3,000 tokens for ToC across all iterations

### Option B: External ToC with Tool Calls

Store ToC externally, expose via tools (`navigate_to`, `list_children`, `read_node`).

**Pros**:
- Unlimited ToC size
- Caching/persistence

**Cons**:
- Tool call latency
- Multiple round-trips needed
- Loses the "reason in context" advantage

### Option C: Hybrid (Vector + ToC)

Use ToC for initial navigation, vector search for content within selected sections.

**Pros**:
- Best of both approaches
- Precision + coverage

**Cons**:
- Implementation complexity
- Two indexes to maintain

**Recommendation**: **Option A (In-Context JSON ToC)** for v1, with **Option C (Hybrid)** as the enhancement path. The in-context approach is simpler and matches PageIndex's validated design.

---

## Design

### Part 1: Data Model

```python
# sunwell/navigation/toc.py

from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True, slots=True)
class TocNode:
    """Single node in the Table of Contents tree.
    
    Designed for in-context consumption by the LLM.
    """
    
    node_id: str
    """Unique identifier (e.g., 'sunwell.planning.naaru.harmonic')."""
    
    title: str
    """Human-readable title."""
    
    node_type: str
    """Type: 'module', 'class', 'function', 'directory', 'file'."""
    
    summary: str
    """1-2 sentence description of what this contains."""
    
    path: str
    """File path (for navigation)."""
    
    line_range: tuple[int, int] | None = None
    """Start/end lines for code entities."""
    
    children: tuple[str, ...] = ()
    """Child node IDs (for tree traversal)."""
    
    cross_refs: tuple[str, ...] = ()
    """Detected cross-references ('see X', 'imports Y')."""
    
    concepts: tuple[str, ...] = ()
    """Semantic concepts this node relates to (for reasoning hints)."""


@dataclass
class ProjectToc:
    """Complete project Table of Contents.
    
    Storage: `.sunwell/navigation/toc.json`
    """
    
    root_id: str
    """Root node ID."""
    
    nodes: dict[str, TocNode] = field(default_factory=dict)
    """All nodes indexed by ID."""
    
    # Indexes for fast lookup
    path_to_node: dict[str, str] = field(default_factory=dict)
    """File path → node ID."""
    
    concept_index: dict[str, list[str]] = field(default_factory=dict)
    """Concept → node IDs that contain it."""
    
    # Metadata
    generated_at: str = ""
    file_count: int = 0
    node_count: int = 0
    
    def to_context_json(self, max_depth: int = 3) -> str:
        """Serialize ToC for LLM context window.
        
        Produces compact JSON optimized for in-context reasoning.
        
        Args:
            max_depth: Maximum tree depth to include.
            
        Returns:
            JSON string suitable for LLM context.
        """
        ...
    
    def get_subtree(self, node_id: str, depth: int = 2) -> str:
        """Get JSON for a specific subtree.
        
        Used for iterative navigation: expand a section.
        """
        ...
```

### Part 2: ToC Generation

```python
# sunwell/navigation/generator.py

import ast
from pathlib import Path
from sunwell.navigation.toc import TocNode, ProjectToc
from sunwell.intelligence.codebase import CodebaseAnalyzer

class TocGenerator:
    """Generate hierarchical ToC from codebase analysis.
    
    Process:
    1. Scan directory structure → module tree
    2. Parse Python AST → classes, functions
    3. Extract docstrings → summaries
    4. Detect cross-references → links
    5. Classify concepts → semantic tags
    """
    
    def __init__(self, root: Path):
        self.root = root
        self._analyzer = CodebaseAnalyzer()
    
    async def generate(self) -> ProjectToc:
        """Full ToC generation.
        
        Time: ~1-5 seconds for typical project (<1000 files).
        """
        toc = ProjectToc(root_id=self.root.name)
        
        # 1. Build directory tree
        await self._build_directory_nodes(toc)
        
        # 2. Parse Python files for classes/functions
        await self._build_code_nodes(toc)
        
        # 3. Extract cross-references
        self._extract_cross_refs(toc)
        
        # 4. Generate summaries (docstring-first, fallback to inference)
        self._generate_summaries(toc)
        
        # 5. Classify concepts (keyword extraction, no LLM)
        self._classify_concepts(toc)
        
        return toc
    
    def _generate_summaries(self, toc: ProjectToc) -> None:
        """Generate node summaries from docstrings.
        
        Strategy (no LLM in v1):
        1. Docstring present → Use first sentence
        2. No docstring, class → "Class with methods: {method_names[:3]}"
        3. No docstring, function → "Function in {module_name}"
        4. Directory → "{n} files: {top_children[:3]}"
        
        LLM-based summaries deferred to Phase 4 (hybrid mode).
        """
        for node_id, node in toc.nodes.items():
            if node.summary:
                continue  # Already has summary
            
            if node.node_type == "directory":
                children = [n for n in toc.nodes.values() if n.path.startswith(node.path)]
                summary = f"{len(children)} items"
            elif node.node_type in ("class", "function", "module"):
                # Try to extract docstring
                summary = self._extract_docstring_summary(node) or f"{node.node_type.title()} in {node.path}"
            else:
                summary = node.title
            
            toc.nodes[node_id] = TocNode(**{**node.__dict__, "summary": summary})
    
    def _classify_concepts(self, toc: ProjectToc) -> None:
        """Classify nodes by semantic concept using keyword extraction.
        
        Algorithm (deterministic, no LLM):
        1. Extract keywords from: node title, path components, docstring
        2. Map keywords to predefined concept categories
        3. Build reverse index: concept → [node_ids]
        
        Concept categories (extensible):
        - auth: authentication, authorization, token, session, login
        - api: endpoint, route, handler, request, response
        - data: model, schema, database, query, orm
        - config: settings, configuration, environment, options
        - test: test, mock, fixture, assert
        - util: util, helper, common, shared
        """
        CONCEPT_KEYWORDS: dict[str, set[str]] = {
            "auth": {"auth", "authentication", "authorization", "token", "session", "login", "permission", "role"},
            "api": {"api", "endpoint", "route", "handler", "request", "response", "rest", "http"},
            "data": {"model", "schema", "database", "query", "orm", "entity", "repository", "store"},
            "config": {"config", "settings", "configuration", "environment", "options", "env"},
            "test": {"test", "mock", "fixture", "assert", "spec", "integration"},
            "util": {"util", "helper", "common", "shared", "tools", "utils"},
            "core": {"core", "base", "protocol", "interface", "abstract"},
            "cli": {"cli", "command", "arg", "parser", "console"},
        }
        
        for node_id, node in toc.nodes.items():
            # Extract keywords from title and path
            text = f"{node.title} {node.path} {node.summary}".lower()
            words = set(re.findall(r'[a-z]+', text))
            
            # Match to concepts
            matched_concepts = []
            for concept, keywords in CONCEPT_KEYWORDS.items():
                if words & keywords:
                    matched_concepts.append(concept)
                    # Update concept index
                    toc.concept_index.setdefault(concept, []).append(node_id)
            
            if matched_concepts:
                toc.nodes[node_id] = TocNode(**{**node.__dict__, "concepts": tuple(matched_concepts)})
        
        return toc
    
    async def _build_directory_nodes(self, toc: ProjectToc) -> None:
        """Build nodes from directory structure."""
        for path in self.root.rglob("*"):
            if self._should_skip(path):
                continue
            
            if path.is_dir():
                node = TocNode(
                    node_id=self._path_to_id(path),
                    title=path.name,
                    node_type="directory",
                    summary=self._infer_directory_purpose(path),
                    path=str(path.relative_to(self.root)),
                )
                toc.nodes[node.node_id] = node
                
    async def _build_code_nodes(self, toc: ProjectToc) -> None:
        """Build nodes from Python AST analysis."""
        for py_file in self.root.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            
            try:
                tree = ast.parse(py_file.read_text())
                
                # Module node
                module_node = self._create_module_node(py_file, tree)
                toc.nodes[module_node.node_id] = module_node
                
                # Class/function nodes
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_node = self._create_class_node(py_file, node)
                        toc.nodes[class_node.node_id] = class_node
                        
                    elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                        # Only top-level and class methods
                        if self._is_significant_function(node):
                            func_node = self._create_function_node(py_file, node)
                            toc.nodes[func_node.node_id] = func_node
                            
            except SyntaxError:
                continue
    
    def _extract_cross_refs(self, toc: ProjectToc) -> None:
        """Detect and link cross-references.
        
        Three extraction strategies:
        1. Comment patterns: '# See: path/to/file.py'
        2. Import statements: 'from sunwell.auth import TokenValidator'
        3. Type annotations: 'def validate(token: auth.Token) -> bool'
        """
        import re
        
        # Pattern 1: Comment-based references
        see_pattern = re.compile(
            r'#\s*[Ss]ee:?\s*([a-zA-Z0-9_/\.]+)',
            re.IGNORECASE
        )
        
        for node_id, node in toc.nodes.items():
            if node.node_type not in ("file", "module"):
                continue
                
            path = self.root / node.path
            if not path.exists():
                continue
                
            content = path.read_text()
            refs: list[str] = []
            
            # Strategy 1: Comment patterns
            refs.extend(see_pattern.findall(content))
            
            # Strategy 2: Import statements (AST-based)
            try:
                tree = ast.parse(content)
                for ast_node in ast.walk(tree):
                    if isinstance(ast_node, ast.Import):
                        for alias in ast_node.names:
                            refs.append(f"import:{alias.name}")
                    elif isinstance(ast_node, ast.ImportFrom):
                        if ast_node.module:
                            refs.append(f"import:{ast_node.module}")
            except SyntaxError:
                pass
            
            # Strategy 3: Type annotation references (regex for speed)
            # Matches: 'auth.Token', 'models.User', etc.
            type_pattern = re.compile(r':\s*([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)')
            type_refs = type_pattern.findall(content)
            refs.extend(f"type:{t}" for t in type_refs)
            
            if refs:
                # Deduplicate and update node
                unique_refs = tuple(sorted(set(refs)))
                toc.nodes[node_id] = TocNode(
                    **{**node.__dict__, "cross_refs": unique_refs}
                )
```

### Part 3: Navigation Engine

```python
# sunwell/navigation/navigator.py

from dataclasses import dataclass
from sunwell.navigation.toc import ProjectToc, TocNode
from sunwell.models.protocol import ModelProtocol

@dataclass
class NavigationResult:
    """Result of a navigation query."""
    
    path: str
    """Selected path to read."""
    
    reasoning: str
    """Why this path was selected."""
    
    confidence: float
    """Navigation confidence (0.0-1.0)."""
    
    content: str | None = None
    """Content if already read."""
    
    follow_up: list[str] = None
    """Suggested paths to explore next."""


class TocNavigator:
    """LLM-powered navigation using ToC reasoning.
    
    The navigator puts the ToC in context and asks the LLM
    to reason about where to look, rather than using embeddings.
    """
    
    def __init__(
        self,
        toc: ProjectToc,
        model: ModelProtocol,
        max_depth: int = 3,
    ):
        self.toc = toc
        self.model = model
        self.max_depth = max_depth
    
    async def navigate(
        self,
        query: str,
        history: list[str] | None = None,
    ) -> NavigationResult:
        """Navigate to relevant code section.
        
        Args:
            query: What the user is looking for.
            history: Previous navigation steps (for context).
            
        Returns:
            NavigationResult with selected path and reasoning.
        """
        # Build navigation prompt
        toc_context = self.toc.to_context_json(max_depth=self.max_depth)
        
        prompt = f"""You are navigating a codebase to find relevant code.

## Project Structure (Table of Contents)

{toc_context}

## Query

{query}

## Previous Steps

{self._format_history(history) if history else "None - this is the first navigation."}

## Instructions

Based on the project structure, decide which path to explore.
Consider:
1. Directory/module names that match the query intent
2. Class/function names that suggest relevant functionality
3. Cross-references that might lead to the answer
4. What you've already explored (don't repeat)

Respond in JSON:
{{
    "selected_path": "path/to/explore",
    "reasoning": "Why this path is likely to contain what we need",
    "confidence": 0.0-1.0,
    "follow_up": ["other/paths", "to/consider"]
}}
"""
        
        response = await self.model.generate(prompt)
        return self._parse_response(response)
    
    async def iterative_search(
        self,
        query: str,
        max_iterations: int = 3,
    ) -> list[NavigationResult]:
        """Iteratively navigate until sufficient content found.
        
        Implements the PageIndex loop:
        1. Read ToC
        2. Select section
        3. Extract content
        4. Is it enough? → Yes: stop, No: repeat
        """
        results = []
        history = []
        
        for i in range(max_iterations):
            result = await self.navigate(query, history)
            
            # Read the selected content
            content = await self._read_path(result.path)
            result.content = content
            results.append(result)
            
            # Check if we have enough
            if await self._is_sufficient(query, results):
                break
            
            history.append(f"Explored {result.path}: {result.reasoning}")
        
        return results
```

### Part 4: SmartContext Integration

Integrate ToC navigation into the existing fallback chain:

```python
# sunwell/indexing/fallback.py (modified)

@dataclass
class SmartContext:
    """Context provider with reasoning-based navigation.
    
    Fallback chain (updated):
    1. Semantic index (quality=1.0) - Best, uses embeddings
    2. ToC navigation (quality=0.85) - Reasoning-based, uses structure  ← NEW
    3. Grep search (quality=0.6) - Fallback, keyword matching
    4. File listing (quality=0.3) - Minimal, just shows structure
    """
    
    indexer: IndexingService | None
    navigator: TocNavigator | None  # NEW
    workspace_root: Path
    
    async def get_context(self, query: str, max_chunks: int = 5) -> ContextResult:
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
        
        # Tier 2: ToC reasoning navigation (NEW)
        # Only attempt for structural queries (heuristic: contains "where", "how", "find")
        if self.navigator and self._is_structural_query(query):
            try:
                results = await self.navigator.iterative_search(query, max_iterations=2)
                if results and any(r.content for r in results):
                    return ContextResult(
                        source="toc_navigation",
                        quality=0.85,
                        content=self._format_navigation_results(results),
                        chunks_used=len(results),
                    )
            except (TimeoutError, ModelError) as e:
                # Log but don't fail - fall through to grep
                logger.warning(f"ToC navigation failed: {e}")
            except Exception:
                pass  # Unexpected error - fall through silently
    
    def _is_structural_query(self, query: str) -> bool:
        """Heuristic: is this a structural navigation query?
        
        Structural queries benefit from ToC navigation:
        - "Where is authentication implemented?"
        - "How does the routing work?"
        - "Find the model validation code"
        
        Content queries should use vector search:
        - "What does this error message mean?"
        - "Show me examples of batch processing"
        """
        structural_signals = ["where", "how does", "find the", "locate", "which file", "which module"]
        query_lower = query.lower()
        return any(signal in query_lower for signal in structural_signals)
        
        # Tier 3: Grep-based search (fallback)
        # ... existing code ...
```

### Part 5: CLI Commands

```bash
# Generate/rebuild ToC
sunwell nav build [--force]

# Show ToC structure
sunwell nav show [--depth 3]

# Navigate to find code
sunwell nav find "how does authentication work"

# Show ToC stats
sunwell nav stats
```

---

## Implementation Plan

### Phase 1: ToC Generation (Week 1)
- [ ] `TocNode` and `ProjectToc` data models
- [ ] Directory tree scanning with skip patterns (`.git`, `__pycache__`, `node_modules`)
- [ ] Python AST parsing for classes/functions
- [ ] Summary extraction from docstrings (no LLM)
- [ ] Keyword-based concept classification
- [ ] JSON serialization with depth-limited `to_context_json()`
- [ ] Cross-reference extraction (comments + imports + type annotations)
- [ ] Persistence to `.sunwell/navigation/toc.json`

### Phase 2: Navigation Engine (Week 2)
- [ ] `TocNavigator` with single-step navigation
- [ ] `iterative_search` for multi-step exploration (max 3 iterations)
- [ ] Sufficiency check (quick LLM call: "is this enough?")
- [ ] Navigation result caching (LRU, 100 entries)
- [ ] Subtree expansion for large codebases (`get_subtree()`)
- [ ] Model config: Haiku/GPT-4o-mini for navigation

### Phase 3: SmartContext Integration (Week 3)
- [ ] Add ToC as Tier 2 in fallback chain
- [ ] Graceful degradation: skip ToC if unavailable/failed
- [ ] Query classification: structural vs. content queries
- [ ] CLI commands (`sunwell nav build`, `sunwell nav find`, `sunwell nav stats`)
- [ ] Performance benchmarking vs vector-only
- [ ] Integration tests with Sunwell codebase

### Phase 4: Hybrid Mode + Enhancements (Future)
- [ ] Hybrid: ToC navigation → vector search within selected section
- [ ] LLM-generated summaries for docstring-less nodes
- [ ] Incremental ToC updates on file changes (file watcher)
- [ ] TypeScript AST support
- [ ] User feedback learning (navigation corrections)

---

## Performance Expectations

| Metric | Vector-only | ToC Navigation | Hybrid |
|--------|------------|----------------|--------|
| **Cold start** | 5-30s (embedding) | 1-5s (AST) | 5-30s |
| **Query latency** | 10-50ms | 100-500ms (LLM) | 100-500ms |
| **Relevance (structural queries)** | 60-70% | 85-95% | 90%+ |
| **Relevance (content queries)** | 85-90% | 70-80% | 90%+ |
| **Context tokens** | 0 (external) | 1,500-3,000 | 1,500-3,000 |
| **Cost per query** | ~$0.0001 | ~$0.005-0.018 | ~$0.005-0.018 |

ToC navigation excels at structural queries ("where is X?", "how does Y work?") while vector search excels at content queries ("find code that does Z").

---

## LLM Cost Analysis

Navigation requires LLM calls for reasoning. Cost breakdown per query:

| Operation | LLM Calls | Input Tokens | Output Tokens | Cost (GPT-4o) |
|-----------|-----------|--------------|---------------|---------------|
| **Single navigation** | 1 | ~1,500 (ToC) + ~100 (query) | ~150 | ~$0.005 |
| **Iterative search (2 iter)** | 2 + 1 (sufficiency) | ~3,200 + ~500 | ~400 | ~$0.012 |
| **Iterative search (3 iter)** | 3 + 2 (sufficiency) | ~4,800 + ~1,000 | ~600 | ~$0.018 |

**Cost comparison vs. vector search**:
- Vector search: $0.0001/query (embedding only, cached)
- ToC navigation: $0.005-0.018/query (LLM reasoning)
- **ToC is ~50-180x more expensive per query**

**Mitigation strategies**:
1. **Use ToC only as fallback** (Tier 2 in SmartContext) — vector search handles most queries
2. **Cache navigation paths** — Same query pattern → same navigation result
3. **Smaller model for navigation** — Claude Haiku or GPT-4o-mini for navigation reasoning
4. **Query classification** — Only route structural queries to ToC navigator

**Recommended model config**:
```python
# Navigation uses cheaper, faster model
NAVIGATION_MODEL = "claude-3-haiku"  # or "gpt-4o-mini"
SUFFICIENCY_MODEL = "claude-3-haiku"  # Quick yes/no check

# Main reasoning uses primary model
PRIMARY_MODEL = "claude-sonnet"  # or "gpt-4o"
```

---

## Testing Strategy

### Unit Tests
- ToC generation produces valid tree structure
- Cross-reference detection finds `# See:` patterns
- JSON serialization fits within token budget

### Integration Tests
- Navigation finds correct module for "authentication" → `auth/`
- Iterative search converges within 3 iterations
- Fallback chain respects priority order

### Benchmark
- Compare navigation accuracy vs vector-only on 100 queries
- Measure latency distribution for typical project sizes
- Token consumption for various project structures

---

## Future Extensions

1. **Language support**: Extend AST parsing to TypeScript, Go, Rust
2. **Semantic concepts**: Use embeddings to classify node concepts
3. **Incremental updates**: File watcher for ToC refresh
4. **Cross-project navigation**: Link related projects via shared concepts
5. **User feedback**: Learn from navigation corrections

---

## References

- [PageIndex: Next-Generation Vectorless, Reasoning-based RAG](https://pageindex.ai/blog/pageindex-intro)
- [Chroma Context Rot Study](https://docs.trychroma.com/) - Context window degradation
- RFC-108: SmartContext with Graceful Fallback
- RFC-045: Project Intelligence
- RFC-014: Multi-Topology Memory

---

## Resolved Design Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Token budget** | 3,000 max (1,500 initial + 1,500 expansion) | Fits all models; pagination handles larger projects |
| **Summary quality** | Docstrings only (v1), LLM deferred to Phase 4 | Avoids generation-time cost; keeps build fast |
| **Rebuild frequency** | Explicit `sunwell nav build` + auto-rebuild if stale (>24h) | Balances freshness vs. overhead |
| **Language priority** | Python → TypeScript → others as needed | Python has best AST support; TS is common |
| **Navigation model** | Haiku/GPT-4o-mini for navigation, primary for content | 10x cost reduction on navigation |
| **Cache strategy** | LRU cache (100 entries) for query→path mappings | Repeated queries hit cache |

## Remaining Open Questions

1. **Concept taxonomy**: Should categories be configurable per-project, or fixed?
2. **Stale detection**: How to detect ToC drift without rescanning all files?
3. **Hybrid trigger**: In Phase 4, what determines when to use vector vs. ToC?

---

## Success Criteria

- [ ] ToC generation completes in <5s for projects with <1000 files
- [ ] Navigation finds correct module 85%+ of the time for structural queries
- [ ] Integration with SmartContext requires <50 lines of changes
- [ ] Context consumption <2000 tokens for typical project ToC
