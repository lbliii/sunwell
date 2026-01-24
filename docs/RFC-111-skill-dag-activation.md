# RFC-111: Skill DAG Activation — From Theory to Dominance

**Status**: ✅ Implemented (Phases 0-6) — COMPLETE  
**Author**: AI Assistant  
**Created**: 2026-01-23  
**Priority**: P0 — Foundation for Competitive Moat  
**Related**: RFC-087 (Skill-Lens DAG), RFC-110 (Unified Execution Engine)

---

## Executive Summary

Sunwell has built **half** of a sophisticated Skill DAG engine—the graph layer (`SkillGraph`, `SkillCache`) is solid, but the **compiler** that transforms skills into executable tasks is missing. Meanwhile, Anthropic shipped "Agent Skills" with a flat, dependency-free model that can't parallelize, can't cache based on data flow, and can't compose skills intelligently.

**This RFC builds `SkillCompiler` — the bridge between skill DAGs and Naaru execution.**

### Core Insight: Skills Compile to Tasks

```
SkillGraph → SkillCompiler.compile() → TaskGraph → Naaru → Results
```

This follows RFC-110's "one executor" principle. No new executor class — skills compile to tasks that Naaru already knows how to execute.

We will:
1. **Build `SkillCompiler`** — transforms SkillGraph → TaskGraph (Phase 0, Week 1)
2. **Wire to Agent** — Agent uses compiler before Naaru (Phase 1, Week 2)
3. **Populate skills with DAG metadata** (`depends_on`/`produces`/`requires`)
4. **Add progressive disclosure** — lazy skill loading during compilation
5. **Natural language to DAG** — users state goals, AI builds the graph
6. **Skill auto-composition** — skills that generate skill graphs
7. **Self-learning skills** — Agent creates skills from successful patterns
8. **Cross-platform export** — Anthropic-compatible for ecosystem reach

**Scope**: 6 weeks

**Result**: Sunwell becomes the only AI agent where **DAGs are invisible but powerful** — users get build-system orchestration without adding execution complexity.

---

## Why This Matters

### The UX Thesis: "DAGs Aren't Fun" — Until AI Writes Them

DAGs have a reputation problem. Anyone who's written Airflow pipelines or Terraform configs knows:

```
The power of DAGs: Parallelism, caching, dependencies, observability
The pain of DAGs:  Manually specifying every edge, debugging cycles, YAML hell
```

**Anthropic's bet**: Avoid DAGs entirely. Keep skills flat and simple.  
**Sunwell's bet**: Keep DAG power, but **AI writes the DAG for you**.

#### How Sunwell Makes DAGs Fun

| Traditional DAG Pain | Sunwell Solution |
|----------------------|------------------|
| Manually specify dependencies | AI infers from `requires`/`produces` contracts |
| Debug circular dependencies | Validation at resolution time with clear errors |
| Can't see what's happening | Studio shows live wave execution |
| YAML hell for complex graphs | Natural language → generated DAG |
| Rigid, breaks when things change | Self-healing: AI fixes broken dependencies |

#### The Key Insight

```
Old world: Human writes DAG → Machine executes DAG
Sunwell:   Human states goal → AI generates DAG → Machine executes DAG → AI improves DAG
```

The user never sees "depends_on" unless they want to. They say:
- "Audit this documentation"
- "Build an API with auth"
- "Refactor this module"

Sunwell:
1. **Analyzes** the goal
2. **Composes** a skill graph (DAG)
3. **Executes** in parallel waves with caching
4. **Learns** patterns for next time

**DAGs aren't fun when you write them. DAGs ARE fun when you watch them execute in parallel and skip cached steps.**

---

### Anthropic's Agent Skills (Jan 2026)

```yaml
Strengths:
  - Progressive disclosure (name/desc → body → files)
  - Clean SKILL.md file format
  - Easy to author

Limitations:
  - No skill dependencies
  - No data flow between skills (produces/requires)
  - No parallel execution
  - No caching based on inputs
  - No skill composition
  - Skills are islands, not a pipeline
```

### Sunwell's Skill DAG — Current State

```yaml
EXISTS (ready to use):
  - SkillGraph with topological sort        # src/sunwell/skills/graph.py:74
  - execution_waves() for parallelism       # src/sunwell/skills/graph.py:276
  - SkillCache with content + input hash    # src/sunwell/skills/cache.py:129
  - SkillDependency type with contracts     # src/sunwell/skills/types.py:31
  - Event schema for DAG execution          # src/sunwell/agent/event_schema.py:476
  - Naaru Task execution with waves         # src/sunwell/naaru/executor.py

DOES NOT EXIST (must build):
  - SkillCompiler (SkillGraph → TaskGraph)  # Bridge between skills and tasks
  - SkillCompilationCache                   # Cache compiled plans
  - Agent integration with SkillCompiler    # Wire compiler into Agent.run()

NOT WIRED:
  - 0 skills have depends_on
  - 0 skills have produces/requires
  - Agent uses Task graph directly, not via Skills
  - No progressive disclosure
```

**Key Insight**: The graph layer is solid. We need a **compiler** to bridge skills to tasks, not a new executor.

### The Opportunity

| Capability | Anthropic | Sunwell (After This RFC) |
|------------|-----------|--------------------------|
| Skill dependencies | ❌ | ✅ `depends_on` DAG |
| Data flow contracts | ❌ | ✅ `produces`/`requires` |
| Parallel execution | ❌ | ✅ Wave-based |
| Input-aware caching | ❌ | ✅ Hash of requires values |
| Progressive disclosure | ✅ | ✅ (added) |
| Skill composition | ❌ | ✅ Lens `extends`/`compose` |
| Skill auto-generation | ❌ | ✅ (new) |
| Self-learning skills | ❌ | ✅ (new) |

---

## Architecture Impact

### RFC-110 Alignment: One Executor

RFC-110 established: **Agent is THE brain. Naaru is THE executor. No more executor classes.**

This RFC respects that principle. **Skills do NOT get their own executor.**

### The Insight: Skills Are Planning, Not Execution

```
┌─────────────────────────────────────────────────────────────┐
│                      PLANNING LAYER                          │
│                                                             │
│  User Goal → Lens → SkillGraph → SkillCompiler → TaskGraph  │
│                                                             │
│  "What should we do?" — declarative, cacheable, reviewable  │
└────────────────────────────┬────────────────────────────────┘
                             │ compile()
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     EXECUTION LAYER                          │
│                                                             │
│  TaskGraph → Naaru.execute_tasks() → Tools → Results        │
│                                                             │
│  "How do we do it?" — parallel, observable, recoverable     │
└─────────────────────────────────────────────────────────────┘
```

**Skills compile to Tasks. Naaru executes Tasks. One execution path.**

### Current vs Proposed

```yaml
CURRENT (Agent uses Naaru directly):
  User Goal → Agent → HarmonicPlanner → TaskGraph → Naaru → Tools

PROPOSED (Agent uses Skills as planning layer):
  User Goal → Agent → Lens.skills → SkillGraph → SkillCompiler 
           → TaskGraph → Naaru → Tools
```

The key addition is `SkillCompiler` — a **compiler**, not an executor.

### Why This Pattern?

This is how mature build systems work:

| System | Planning | Execution |
|--------|----------|-----------|
| **Bazel** | BUILD rules → Action graph | Action executor |
| **Airflow** | DAG definition → Task instances | Executor (Celery, K8s) |
| **Sunwell** | SkillGraph → TaskGraph | Naaru |

**Separation of concerns**: Skill DAG logic lives in the compiler. Execution logic stays in Naaru.

### The Unlock: Task Composition and Decomposition

By compiling skills to tasks, we get **two layers of DAG intelligence**:

```
┌─────────────────────────────────────────────────────────────┐
│  SKILL DAG (Coarse-Grained)                                 │
│                                                             │
│  audit-documentation ──depends_on──▶ extract-api-surface    │
│                       ──depends_on──▶ search-codebase       │
│                                                             │
│  "What capabilities are needed?"                            │
└────────────────────────────┬────────────────────────────────┘
                             │ SkillCompiler.compile()
                             │ 
                             │ COMPOSITION: One skill → multiple tasks
                             │ DECOMPOSITION: Complex skill → subtask graph
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  TASK DAG (Fine-Grained)                                    │
│                                                             │
│  skill:extract-api-surface                                  │
│    └─▶ task:read-source-files (can parallel with ↓)        │
│    └─▶ task:parse-ast                                       │
│    └─▶ task:extract-signatures                              │
│                                                             │
│  skill:search-codebase                                      │
│    └─▶ task:build-search-index (can parallel with ↑)       │
│    └─▶ task:execute-queries                                 │
│                                                             │
│  "What work units can run in parallel?"                     │
└─────────────────────────────────────────────────────────────┘
```

**Key insight**: The compiler can:

1. **Compose tasks**: A skill produces multiple related tasks that form a subgraph
2. **Decompose skills**: Complex skills become pipelines of smaller tasks
3. **Discover parallelism**: Independent tasks from different skills run concurrently
4. **Preserve dependencies**: Skill-level deps become task-level deps

**Example: Audit Skill Decomposition**

```python
# SkillCompiler expands one skill into a task subgraph

def compile_skill(self, skill: Skill) -> list[Task]:
    """A single skill may produce multiple tasks."""
    
    if skill.name == "audit-documentation":
        # Decompose into parallel subtasks
        return [
            Task(id=f"{skill.name}:gather", 
                 description="Gather evidence from sources",
                 produces={"evidence"}),
            Task(id=f"{skill.name}:analyze",
                 description="Analyze claims against evidence", 
                 depends_on={f"{skill.name}:gather"},
                 produces={"analysis"}),
            Task(id=f"{skill.name}:report",
                 description="Generate audit report",
                 depends_on={f"{skill.name}:analyze"},
                 produces={"report"}),
        ]
    
    # Simple skills map 1:1
    return [Task(id=f"skill:{skill.name}", ...)]
```

**Result**: Naaru sees the fine-grained task graph and automatically parallelizes:

```
Wave 1: [read-source-files, build-search-index]  # PARALLEL
Wave 2: [parse-ast, execute-queries]              # PARALLEL  
Wave 3: [extract-signatures]
Wave 4: [audit:gather]
Wave 5: [audit:analyze]
Wave 6: [audit:report]
```

**This is the power of compilation**: Skills express intent at a high level. The compiler expands to optimal task graphs. Naaru executes with maximum parallelism.

### What This Means for Existing Code

| Component | Change |
|-----------|--------|
| `Agent` | Calls `SkillCompiler.compile()` before Naaru |
| `Naaru` | Unchanged — still executes TaskGraphs |
| `SkillGraph` | Already exists — unchanged |
| `SkillCache` | Repurposed: caches compiled TaskGraphs |
| `skills/__init__.py` | Add `SkillCompiler` exports |

**No new executor class. RFC-110 compatibility preserved.**

---

## Design

### Phase 0: Build the Compiler (P0 — PREREQUISITE)

> **Prerequisites**: This RFC assumes RFC-110 (Unified Execution Engine) architecture where Agent uses Naaru internally for task execution. If RFC-110 is not yet implemented, Phase 1 may need adjustment.

Before wiring anything, we must:
1. Create `SkillCompiler` that transforms SkillGraph → TaskGraph
2. Export compiler from `skills/__init__.py`

#### 0.1 Update skills/__init__.py

```python
# src/sunwell/skills/__init__.py — ADD compiler exports

from sunwell.skills.cache import SkillCache, SkillCacheEntry, SkillCacheKey
from sunwell.skills.compiler import SkillCompiler, SkillCompilationCache  # NEW
from sunwell.skills.graph import (
    CircularDependencyError,
    MissingDependencyError,
    SkillGraph,
    SkillGraphError,
    UnsatisfiedRequiresError,
)
# ... existing exports unchanged

__all__ = [
    # ... existing exports ...
    # NEW: Compiler exports
    "SkillCompiler",
    "SkillCompilationCache",
]
```

**Skills compile to Tasks. Naaru executes Tasks.**

#### 0.2 SkillCompiler

```python
# src/sunwell/skills/compiler.py — NEW

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.naaru.types import Task, TaskGraph
    from sunwell.skills.graph import SkillGraph
    from sunwell.skills.types import Skill

@dataclass
class SkillCompiler:
    """Compile SkillGraph into TaskGraph for Naaru execution.
    
    This is the bridge between RFC-111 (Skill DAG) and RFC-110 (Unified Execution).
    
    Skills are PLANNING abstractions — they describe capabilities.
    Tasks are EXECUTION abstractions — they describe work.
    
    The compiler transforms declarative skills into procedural tasks
    that Naaru can execute in parallel waves.
    """
    
    lens: Lens
    """Lens providing skill context."""
    
    cache: SkillCompilationCache | None = None
    """Optional cache for compiled results."""
    
    def compile(
        self,
        skill_graph: SkillGraph,
        context: dict[str, Any],
        target_skills: set[str] | None = None,
    ) -> TaskGraph:
        """Compile skills into executable tasks.
        
        Args:
            skill_graph: Graph of skills with dependencies
            context: Execution context (target files, user input, etc.)
            target_skills: Optional subset of skills to compile (includes deps)
        
        Returns:
            TaskGraph ready for Naaru.execute_tasks()
        
        Example:
            >>> compiler = SkillCompiler(lens=my_lens)
            >>> skill_graph = SkillGraph.from_skills(lens.skills)
            >>> task_graph = compiler.compile(skill_graph, {"target": "docs/"})
            >>> results = await naaru.execute_tasks(task_graph)
        """
        from sunwell.naaru.types import Task, TaskMode
        from sunwell.naaru.artifacts import TaskGraph
        
        # Check cache first
        if self.cache:
            cache_key = self.cache.compute_key(skill_graph, context)
            if cached := self.cache.get(cache_key):
                return cached
        
        # Extract subgraph if targeting specific skills
        if target_skills:
            skill_graph = skill_graph.subgraph_for(target_skills)
        
        # Validate graph
        errors = skill_graph.validate()
        if errors:
            raise SkillCompilationError(f"Invalid skill graph: {errors}")
        
        # Compile each skill to a task
        tasks: list[Task] = []
        skill_to_task_id: dict[str, str] = {}
        
        for skill in skill_graph:
            task_id = f"skill:{skill.name}"
            skill_to_task_id[skill.name] = task_id
            
            # Map skill dependencies to task dependencies
            task_deps = frozenset(
                skill_to_task_id[dep.skill_name]
                for dep in skill.depends_on
                if dep.skill_name in skill_to_task_id
            )
            
            task = Task(
                id=task_id,
                description=f"[{skill.name}] {skill.description}",
                mode=TaskMode.GENERATE,
                depends_on=task_deps,
                produces=frozenset(skill.produces),
                
                # Skill metadata flows to task context
                context={
                    "skill_name": skill.name,
                    "skill_instructions": skill.instructions,
                    "skill_requires": list(skill.requires),
                    "skill_produces": list(skill.produces),
                    "lens_context": self.lens.to_context() if self.lens else {},
                    **{k: context.get(k) for k in skill.requires if k in context},
                },
            )
            tasks.append(task)
        
        task_graph = TaskGraph.from_tasks(tasks)
        
        # Cache the compiled result
        if self.cache:
            self.cache.set(cache_key, task_graph)
        
        return task_graph
    
    def compile_for_shortcut(
        self,
        shortcut: str,
        target: str,
        skill_graph: SkillGraph,
    ) -> TaskGraph:
        """Compile skills for a shortcut execution.
        
        Shortcuts like `-s a-2` map to specific skills.
        This compiles just those skills (plus dependencies).
        """
        from sunwell.cli.shortcuts import SHORTCUT_SKILL_MAP
        
        target_skills = SHORTCUT_SKILL_MAP.get(shortcut, set())
        context = {"target": target, "shortcut": shortcut}
        
        return self.compile(skill_graph, context, target_skills)


class SkillCompilationError(Exception):
    """Error during skill compilation."""
    pass
```

#### 0.3 SkillCompilationCache

```python
# src/sunwell/skills/compiler.py — continued

@dataclass
class SkillCompilationCache:
    """Cache compiled TaskGraphs from SkillGraphs.
    
    Key insight: If skills haven't changed, the compiled TaskGraph
    is identical. Cache it to skip recompilation.
    
    Naaru's execution cache handles caching actual results.
    This cache handles caching the PLAN.
    """
    
    _cache: dict[str, TaskGraph] = field(default_factory=dict)
    max_size: int = 100
    
    def compute_key(self, skill_graph: SkillGraph, context: dict) -> str:
        """Compute cache key from graph content and context."""
        import hashlib
        import json
        
        hasher = hashlib.sha256()
        hasher.update(skill_graph.content_hash().encode())
        hasher.update(json.dumps(sorted(context.items()), default=str).encode())
        return hasher.hexdigest()[:16]
    
    def get(self, key: str) -> TaskGraph | None:
        """Get cached TaskGraph if available."""
        return self._cache.get(key)
    
    def set(self, key: str, task_graph: TaskGraph) -> None:
        """Cache a compiled TaskGraph."""
        if len(self._cache) >= self.max_size:
            # Simple LRU: remove oldest
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = task_graph
```

#### 0.4 Integration with Agent

```python
# src/sunwell/agent/core.py — UPDATED

@dataclass
class Agent:
    """THE execution engine for Sunwell (RFC-110, RFC-111)."""
    
    # ... existing fields ...
    
    # NEW: Skill compilation
    _skill_compiler: SkillCompiler | None = field(default=None, init=False)
    _compilation_cache: SkillCompilationCache = field(
        default_factory=SkillCompilationCache, init=False
    )
    
    async def _plan_with_skills(
        self,
        goal: str,
        signals: AdaptiveSignals,
        context: dict[str, Any],
    ) -> TaskGraph:
        """Plan using lens skills (RFC-111).
        
        If lens has skills with DAG metadata, compile them to tasks.
        Otherwise fall back to HarmonicPlanner.
        """
        if not self.lens or not self.lens.skills:
            # No skills — use existing planning
            return await self._harmonic_plan(goal, context)
        
        # Build skill graph from lens
        skill_graph = SkillGraph.from_skills(self.lens.skills)
        
        # Check if skills have DAG metadata
        has_dag_metadata = any(
            skill.depends_on or skill.produces or skill.requires
            for skill in self.lens.skills
        )
        
        if not has_dag_metadata:
            # Skills exist but no DAG — use existing planning
            return await self._harmonic_plan(goal, context)
        
        # Compile skills to tasks
        compiler = SkillCompiler(
            lens=self.lens,
            cache=self._compilation_cache,
        )
        
        return compiler.compile(skill_graph, context)
```

**Key point**: Agent calls `compiler.compile()`, then passes result to Naaru. One execution path.

---

### Part 1: Wire the DAG (P0)

#### 1.1 Agent Uses SkillCompiler

Currently, `Agent` uses `TaskGraph` + Naaru for execution. Skills are available on the Lens but **never compiled to tasks**.

```python
# agent/core.py — CURRENT (uses Tasks, not Skills)
# See src/sunwell/agent/core.py:645-731

async def _execute_with_gates(self, options: RunOptions) -> AsyncIterator[AgentEvent]:
    """Execute tasks with validation gates."""
    while self._task_graph.has_pending_tasks():
        ready = self._task_graph.get_ready_tasks()
        for task in ready:
            # Task execution — no skill compilation here!
            artifact = await self._execute_task(task)
            ...

# agent/core.py — AFTER (adds skill compilation path)

async def _plan_with_skills(
    self,
    goal: str,
    signals: AdaptiveSignals,
    context: dict[str, Any],
) -> TaskGraph:
    """Plan using lens skills via SkillCompiler (RFC-111).
    
    If lens has skills with DAG metadata, compile them to tasks.
    Otherwise fall back to HarmonicPlanner.
    """
    from sunwell.skills.compiler import SkillCompiler
    from sunwell.skills.graph import SkillGraph
    
    if not self.lens or not self.lens.skills:
        # No skills — use existing planning
        return await self._harmonic_plan(goal, context)
    
    # Build skill graph from lens
    skill_graph = SkillGraph.from_skills(self.lens.skills)
    
    # Check if skills have DAG metadata
    has_dag_metadata = any(
        skill.depends_on or skill.produces or skill.requires
        for skill in self.lens.skills
    )
    
    if not has_dag_metadata:
        # Skills exist but no DAG — use existing planning
        return await self._harmonic_plan(goal, context)
    
    # Compile skills to tasks
    compiler = SkillCompiler(
        lens=self.lens,
        cache=self._compilation_cache,
    )
    
    # Returns TaskGraph ready for Naaru
    return compiler.compile(skill_graph, context)
```

**Key insight**: Agent calls `compiler.compile()` to get a TaskGraph. Naaru executes the TaskGraph. **No new executor class.**

#### 1.2 Shortcut Execution Uses Compiler

```python
# cli/main.py — Shortcut path

async def execute_shortcut(shortcut: str, target: Path) -> None:
    """Execute a shortcut through the compiler path."""
    from sunwell.skills.compiler import SkillCompiler
    from sunwell.skills.graph import SkillGraph
    
    # Resolve lens for shortcut
    lens = await resolve_lens_for_shortcut(shortcut)
    
    # Build skill graph and compile to tasks
    skill_graph = SkillGraph.from_skills(lens.skills)
    compiler = SkillCompiler(lens=lens)
    
    # compile_for_shortcut extracts subgraph + compiles
    task_graph = compiler.compile_for_shortcut(
        shortcut=shortcut,
        target=str(target),
        skill_graph=skill_graph,
    )
    
    # Agent executes the TaskGraph via Naaru
    agent = Agent(model=model, lens=lens)
    async for event in agent.run_task_graph(task_graph):
        yield event
```

---

### Part 2: Populate Skills with DAG Metadata (P0)

Update all skill definitions to declare their data dependencies.

#### 2.1 Core Skills Library

```yaml
# skills/core-skills.yaml — UPDATED

skills:
  # ============================================================================
  # LAYER 0: Foundation (No Dependencies)
  # ============================================================================
  
  - name: read-file
    description: Read a file from the workspace
    type: inline
    preset: read-only
    produces: [file_content, file_path, file_type]
    instructions: |
      Read the specified file and return its contents.
      
      ## Output
      Set context keys:
      - file_content: The raw file contents
      - file_path: Absolute path to file
      - file_type: Detected file type (python, markdown, etc.)

  - name: list-workspace
    description: List files matching a pattern
    type: inline
    preset: read-only
    produces: [file_list, workspace_structure]
    instructions: |
      List files in the workspace matching the given pattern.
      
      ## Output
      - file_list: List of matching file paths
      - workspace_structure: Tree representation

  # ============================================================================
  # LAYER 1: Analysis (Depends on Layer 0)
  # ============================================================================
  
  - name: extract-api-surface
    description: Extract public API from source code
    type: inline
    preset: safe-shell
    depends_on:
      - source: read-file
    requires: [file_content, file_type]
    produces: [api_surface, exports, imports]
    instructions: |
      Extract the public API from the source code.
      
      ## Input
      - file_content: Source code to analyze
      - file_type: Language for parsing
      
      ## Output
      - api_surface: Structured API (functions, classes, types)
      - exports: Public exports
      - imports: Dependencies

  - name: analyze-code-structure
    description: Analyze code architecture and patterns
    type: inline
    preset: read-only
    depends_on:
      - source: read-file
    requires: [file_content]
    produces: [code_structure, complexity_metrics, patterns_detected]
    instructions: |
      Analyze the code structure and identify patterns.
      
      ## Output
      - code_structure: AST-level structure
      - complexity_metrics: Cyclomatic complexity, etc.
      - patterns_detected: Design patterns found

  - name: search-codebase
    description: Semantic search across the codebase
    type: inline
    preset: search-only
    depends_on:
      - source: list-workspace
    requires: [file_list]
    produces: [search_results, relevant_files]
    instructions: |
      Search the codebase for relevant code.
      
      ## Output
      - search_results: Ranked matches with snippets
      - relevant_files: Most relevant file paths

  # ============================================================================
  # LAYER 2: Synthesis (Depends on Layer 1)
  # ============================================================================
  
  - name: audit-documentation
    description: Audit docs against source code for accuracy
    type: inline
    preset: read-only
    depends_on:
      - source: extract-api-surface
      - source: search-codebase
    requires: [api_surface, search_results]
    produces: [audit_report, issues_found, confidence_scores]
    instructions: |
      Verify documentation claims against source code.
      
      ## Input
      - api_surface: Extracted API for verification
      - search_results: Evidence from codebase
      
      ## Output
      - audit_report: Full audit with findings
      - issues_found: List of discrepancies
      - confidence_scores: Per-claim confidence

  - name: generate-api-reference
    description: Generate API reference documentation
    type: inline
    preset: workspace-write
    depends_on:
      - source: extract-api-surface
    requires: [api_surface, exports]
    produces: [api_reference_doc, doc_path]
    instructions: |
      Generate comprehensive API reference.
      
      ## Input
      - api_surface: Extracted API
      - exports: Public exports to document
      
      ## Output
      - api_reference_doc: Markdown documentation
      - doc_path: Where to save

  # ============================================================================
  # LAYER 3: Refinement (Depends on Layer 2)
  # ============================================================================
  
  - name: fix-documentation-issues
    description: Auto-fix issues found by audit
    type: inline
    preset: workspace-write
    depends_on:
      - source: audit-documentation
    requires: [audit_report, issues_found]
    produces: [fixes_applied, updated_docs]
    instructions: |
      Fix documentation issues found by audit.
      
      ## Input
      - audit_report: Full audit results
      - issues_found: Specific issues to fix
      
      ## Output
      - fixes_applied: What was changed
      - updated_docs: New documentation content
```

#### 2.2 Execution Visualization — Making DAGs Fun

**CLI Experience** (for power users who want to see the DAG):

```
sunwell -s a-2 docs/api.md

📊 Skill Graph for deep-audit
├── Wave 1: [read-file, list-workspace]     # Parallel
├── Wave 2: [extract-api-surface, search-codebase]  # Parallel
├── Wave 3: [audit-documentation]
└── Wave 4: [fix-documentation-issues]

⚡ Execution:
  Wave 1: 2 skills in parallel... ✓ 450ms
  Wave 2: 2 skills in parallel... ✓ 1200ms
    💨 extract-api-surface: cache hit (saved ~800ms)
  Wave 3: audit-documentation... ✓ 2100ms
  Wave 4: fix-documentation-issues... ✓ 1500ms

📈 Summary: 5250ms total (800ms saved from cache)
```

**Studio Experience** (visual, interactive):

```
┌─────────────────────────────────────────────────────────────────────┐
│  🎯 Goal: "Audit docs/api.md against source code"                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   ┌──────────────┐                                    │
│  │read-file │   │list-workspace│   Wave 1 ████████████ ✓ 450ms     │
│  │  ✓ 200ms │   │    ✓ 250ms   │                                    │
│  └────┬─────┘   └──────┬───────┘                                    │
│       │                │                                             │
│       ▼                ▼                                             │
│  ┌────────────┐  ┌─────────────┐                                    │
│  │extract-api │  │search-code  │   Wave 2 ████████████ ✓ 1.2s      │
│  │ 💨 CACHED  │  │   ✓ 1.2s    │                                    │
│  └─────┬──────┘  └──────┬──────┘                                    │
│        │                │                                            │
│        └───────┬────────┘                                            │
│                ▼                                                     │
│        ┌──────────────┐                                              │
│        │audit-docs    │            Wave 3 ████████████ ✓ 2.1s       │
│        │   ✓ 2.1s     │                                              │
│        └──────┬───────┘                                              │
│               │                                                      │
│               ▼                                                      │
│        ┌──────────────┐                                              │
│        │fix-issues    │            Wave 4 ████████████ ✓ 1.5s       │
│        │   ✓ 1.5s     │                                              │
│        └──────────────┘                                              │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  ⚡ Total: 5.25s │ 💨 Saved: 800ms (cache) │ 🔀 Parallelism: 2x     │
└─────────────────────────────────────────────────────────────────────┘
```

**Why This Is Fun**:
1. **Watch parallelism happen** — Skills animate executing simultaneously
2. **See cache hits glow** — Skipped skills show "💨 CACHED" with time saved
3. **Understand the flow** — Data dependencies are visible edges
4. **Feel the speed** — Progress bars show waves completing

**The Invisible DAG**:
For users who don't care about the graph, we show:

```
✨ Auditing docs/api.md...

  Reading files...          ✓
  Analyzing code...         ✓ (cached)
  Searching codebase...     ✓
  Running audit...          ✓
  Fixing issues...          ✓

Done in 5.2s (saved 0.8s from cache)
```

Same DAG underneath. Zero complexity exposed. Users only see the DAG if they want to.

---

### Part 3: Progressive Disclosure (P1)

Adopt Anthropic's insight: don't load all skill content upfront.

#### 3.1 Skill Metadata vs Full Skill

```python
# skills/types.py — NEW

@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Lightweight skill info for routing and DAG construction.
    
    This is the ONLY thing loaded initially. Full instructions
    are loaded lazily when the skill executes.
    """
    
    name: str
    description: str
    skill_type: SkillType
    
    # DAG fields (needed for graph construction)
    depends_on: tuple[SkillDependency, ...] = ()
    produces: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()
    
    # Reference to full skill (lazy loaded)
    source_path: Path | None = None
    
    def matches_intent(self, query: str) -> float:
        """Score how well this skill matches a user intent."""
        query_lower = query.lower()
        score = 0.0
        
        # Name match
        if self.name in query_lower:
            score += 0.5
        
        # Trigger match
        for trigger in self.triggers:
            if trigger in query_lower:
                score += 0.3
        
        # Description keyword match
        desc_words = set(self.description.lower().split())
        query_words = set(query_lower.split())
        overlap = len(desc_words & query_words)
        score += overlap * 0.1
        
        return min(score, 1.0)
```

#### 3.2 Lazy Loading in Graph

```python
# skills/graph.py — UPDATED

@dataclass
class SkillGraph:
    """DAG of skills with lazy loading support."""
    
    _metadata: dict[str, SkillMetadata] = field(default_factory=dict)
    """Always loaded: name, desc, depends_on, produces, requires."""
    
    _full_skills: dict[str, Skill] = field(default_factory=dict)
    """Loaded on demand when skill executes."""
    
    _loader: SkillLoader | None = None
    
    def add_metadata(self, meta: SkillMetadata) -> None:
        """Add skill metadata (lightweight, always loaded)."""
        self._metadata[meta.name] = meta
        # Build edge from depends_on
        deps = frozenset(d.skill_name for d in meta.depends_on)
        self._edges[meta.name] = deps
    
    async def get_full_skill(self, name: str) -> Skill:
        """Load full skill content when needed.
        
        This is called during wave execution, not during graph construction.
        If skill is cached, we may never load the full content at all.
        """
        if name not in self._full_skills:
            meta = self._metadata[name]
            if meta.source_path and self._loader:
                self._full_skills[name] = await self._loader.load_full(meta.source_path)
            else:
                raise ValueError(f"Cannot load full skill for {name}")
        return self._full_skills[name]
    
    @classmethod
    async def from_lens_lazy(cls, lens: Lens, loader: SkillLoader) -> SkillGraph:
        """Build graph from lens with lazy loading.
        
        Only loads metadata initially. Full skills loaded during execution.
        """
        graph = cls(_loader=loader)
        
        for skill in lens.skills:
            meta = SkillMetadata(
                name=skill.name,
                description=skill.description,
                skill_type=skill.skill_type,
                depends_on=skill.depends_on,
                produces=skill.produces,
                requires=skill.requires,
                triggers=skill.triggers,
                source_path=skill.path,
            )
            graph.add_metadata(meta)
        
        return graph
```

#### 3.3 Cache-Aware Lazy Loading in Compiler

```python
# skills/compiler.py — UPDATED with lazy loading

@dataclass
class SkillCompiler:
    """Compile SkillGraph into TaskGraph with lazy loading support."""
    
    lens: Lens
    cache: SkillCompilationCache | None = None
    
    def compile(
        self,
        skill_graph: SkillGraph,
        context: dict[str, Any],
        target_skills: set[str] | None = None,
    ) -> TaskGraph:
        """Compile skills to tasks, using metadata-only until needed.
        
        The compiler checks cache BEFORE loading full skill content.
        If a skill's compiled task is cached, we never load instructions.
        """
        # Check compilation cache first
        if self.cache:
            cache_key = self.cache.compute_key(skill_graph, context)
            if cached := self.cache.get(cache_key):
                return cached
        
        tasks: list[Task] = []
        
        for skill_name in skill_graph.topological_order():
            # Use metadata for cache check (lightweight)
            meta = skill_graph.get_metadata(skill_name)
            task_cache_key = SkillCacheKey.compute_from_metadata(
                meta, context, self.lens.version
            )
            
            if self.cache and self.cache.has_task(task_cache_key):
                # SKIP loading full skill — use cached task
                tasks.append(self.cache.get_task(task_cache_key))
                continue
            
            # Only now load full skill content (lazy)
            full_skill = skill_graph.get_full_skill(skill_name)
            
            # Compile skill to task
            task = self._compile_skill_to_task(full_skill, context)
            tasks.append(task)
            
            # Cache the compiled task
            if self.cache:
                self.cache.set_task(task_cache_key, task)
        
        task_graph = TaskGraph.from_tasks(tasks)
        
        # Cache full compilation result
        if self.cache:
            self.cache.set(cache_key, task_graph)
        
        return task_graph
```

**Benefit**: If a skill is cached, we never load its instructions at all. This reduces context size AND speeds up compilation.

---

### Part 4: Natural Language to DAG (P1)

**The core UX innovation**: Users never write DAGs. They state goals. Sunwell generates the DAG.

#### 4.1 Goal → DAG Translation

```python
# agent/planner.py — NEW

@dataclass
class GoalPlanner:
    """Translate natural language goals into skill DAGs.
    
    This is what makes DAGs fun: you don't write them.
    """
    
    model: ModelProtocol
    skill_library: SkillLibrary
    
    async def plan(self, goal: str) -> SkillGraph:
        """Convert a goal into an executable skill graph.
        
        Example:
            goal: "Audit the API documentation for accuracy"
            
            Returns DAG:
                read-file → extract-api → audit-docs → fix-issues
        """
        
        # 1. Identify what capabilities are needed
        capabilities = await self._identify_capabilities(goal)
        # ["read files", "extract API", "compare docs to code", "fix issues"]
        
        # 2. Match to existing skills
        matched_skills = self._match_skills(capabilities)
        # [read-file, extract-api-surface, audit-documentation, fix-issues]
        
        # 3. Infer dependencies from produces/requires
        graph = self._build_graph_from_contracts(matched_skills)
        # Automatically: extract-api depends on read-file (needs file_content)
        
        # 4. Fill gaps with generated skills
        gaps = self._find_capability_gaps(capabilities, matched_skills)
        if gaps:
            generated = await self._generate_skills_for_gaps(gaps)
            graph = self._merge_skills(graph, generated)
        
        return graph
    
    def _build_graph_from_contracts(self, skills: list[Skill]) -> SkillGraph:
        """Auto-infer dependencies from produces/requires.
        
        This is the magic: users declare contracts, not edges.
        The DAG builds itself.
        """
        graph = SkillGraph()
        
        # Index what each skill produces
        producers: dict[str, str] = {}  # context_key → skill_name
        for skill in skills:
            for key in skill.produces:
                producers[key] = skill.name
        
        # Build edges from requires → produces
        for skill in skills:
            dependencies = []
            for required_key in skill.requires:
                if required_key in producers:
                    dependencies.append(SkillDependency(source=producers[required_key]))
            
            # Create skill with inferred dependencies
            skill_with_deps = replace(skill, depends_on=tuple(dependencies))
            graph.add_skill(skill_with_deps)
        
        return graph
```

#### 4.2 The User Experience

**What the user types**:
```
sunwell "Audit the API docs in docs/api.md against the source code and fix any issues"
```

**What Sunwell does internally**:
```
1. GoalPlanner.plan() → identifies needed capabilities
2. Matches to skills: [read-file, extract-api-surface, audit-documentation, fix-issues]
3. Infers DAG from contracts:
   - extract-api-surface requires [file_content] → depends on read-file
   - audit-documentation requires [api_surface] → depends on extract-api-surface
   - fix-issues requires [audit_report] → depends on audit-documentation
4. Executes DAG in parallel waves
```

**What the user sees**:
```
✨ Planning audit workflow...

📊 Generated execution plan:
   Wave 1: read-file, list-workspace
   Wave 2: extract-api-surface, search-codebase  
   Wave 3: audit-documentation
   Wave 4: fix-documentation-issues

⚡ Executing... (Ctrl+C to cancel)

   [████████████████████] Wave 1 complete (0.4s)
   [████████████████████] Wave 2 complete (1.2s) 💨 1 cached
   [████████████████████] Wave 3 complete (2.1s)
   [████████████████████] Wave 4 complete (1.5s)

✅ Done in 5.2s (saved 0.8s from cache)

📝 Fixed 3 issues in docs/api.md
```

**The user never wrote a DAG.** They stated a goal. Sunwell figured out the rest.

---

### Part 5: Skill Auto-Composition (P2)

Skills that generate other skills — dynamic capability expansion.

#### 5.1 Meta-Skills

```yaml
# skills/meta-skills.yaml

skills:
  - name: analyze-and-plan
    description: Analyze a goal and generate a skill graph to accomplish it
    type: inline
    preset: read-only
    produces: [execution_plan, generated_skills]
    instructions: |
      ## Goal
      Given a complex task, decompose it into a skill graph.
      
      ## Process
      1. Analyze the goal to identify subtasks
      2. Map subtasks to existing skills where possible
      3. Generate inline skill definitions for gaps
      4. Produce a DAG with dependencies
      
      ## Output Format
      ```yaml
      skills:
        - name: step-1
          description: ...
          produces: [step_1_output]
        - name: step-2
          depends_on: [step-1]
          requires: [step_1_output]
          produces: [step_2_output]
      ```
      
      This output will be parsed and executed as a skill graph.

  - name: compose-skills
    description: Compose multiple skills into a reusable workflow
    type: inline
    preset: workspace-write
    requires: [skill_names, composition_type]
    produces: [composed_skill, skill_path]
    instructions: |
      ## Goal
      Take a list of skills and compose them into a new reusable skill.
      
      ## Composition Types
      - sequence: Execute in order with data flow
      - parallel: Execute independently and merge results
      - conditional: Execute based on context values
      
      ## Output
      A new skill definition saved to skills/ directory.
```

#### 4.2 Dynamic Skill Generation

```python
# agent/composer.py — NEW

@dataclass
class SkillComposer:
    """Dynamically compose and generate skills."""
    
    model: ModelProtocol
    skill_library: SkillLibrary
    
    async def compose_for_goal(self, goal: str) -> SkillGraph:
        """Generate a skill graph to accomplish a complex goal.
        
        This is Sunwell's secret weapon: the agent can CREATE
        its own capability graphs, not just execute predefined ones.
        """
        
        # 1. Analyze goal to identify required capabilities
        capabilities = await self._identify_capabilities(goal)
        
        # 2. Match to existing skills
        matched, gaps = self._match_skills(capabilities)
        
        # 3. Generate inline skills for gaps
        generated = await self._generate_skills_for_gaps(gaps)
        
        # 4. Build optimized DAG
        all_skills = matched + generated
        graph = self._build_dag(all_skills)
        
        # 5. Validate dependencies
        errors = graph.validate()
        if errors:
            # Self-heal: ask model to fix
            graph = await self._self_heal_graph(graph, errors)
        
        return graph
    
    async def _generate_skills_for_gaps(
        self, 
        gaps: list[CapabilityGap]
    ) -> list[Skill]:
        """Generate inline skills for capability gaps.
        
        This is where Sunwell creates new skills on-the-fly.
        """
        generated = []
        
        for gap in gaps:
            prompt = f"""
Generate a skill definition to provide this capability:

Capability: {gap.description}
Required inputs: {gap.requires}
Expected outputs: {gap.produces}

Generate a complete skill in YAML format with:
- name (lowercase, hyphenated)
- description
- depends_on (if any known skills should run first)
- requires (context keys needed)
- produces (context keys output)
- instructions (clear steps)
"""
            
            result = await self.model.generate(prompt)
            skill = self._parse_skill_yaml(result.content)
            generated.append(skill)
        
        return generated
```

---

### Part 6: Self-Learning Skills (P2)

The agent creates reusable skills from successful execution patterns.

#### 6.1 Pattern Extraction

```python
# agent/learning.py — EXTENDED

@dataclass
class SkillLearner:
    """Extract reusable skills from successful executions."""
    
    simulacrum: SimulacrumStore
    
    async def extract_skill_from_session(
        self, 
        session_id: str,
        success_criteria: str,
    ) -> Skill | None:
        """Extract a reusable skill from a successful session.
        
        When a user accomplishes something complex, we can:
        1. Analyze the execution trace
        2. Identify the pattern of steps
        3. Generate a reusable skill definition
        4. Save it to the local skill library
        """
        
        # Get session from Simulacrum
        session = await self.simulacrum.get_session(session_id)
        if not session or not session.succeeded:
            return None
        
        # Extract the pattern
        pattern = self._extract_pattern(session)
        
        # Generate skill definition
        skill = await self._generate_skill_from_pattern(
            pattern,
            success_criteria,
        )
        
        return skill
    
    async def _generate_skill_from_pattern(
        self,
        pattern: ExecutionPattern,
        success_criteria: str,
    ) -> Skill:
        """Generate a skill definition from an execution pattern."""
        
        prompt = f"""
Based on this successful execution pattern, generate a reusable skill:

## Steps Taken
{pattern.steps_description}

## Tools Used
{pattern.tools_used}

## Context Required
{pattern.context_keys}

## Success Criteria
{success_criteria}

Generate a skill that:
1. Can reproduce this pattern
2. Has clear requires/produces contracts
3. Works for similar tasks in the future
"""
        
        result = await self.model.generate(prompt)
        return self._parse_skill(result.content)
```

#### 6.2 Skill Library Growth

```python
# skills/library.py — NEW

@dataclass
class SkillLibrary:
    """Local skill library that grows through learning."""
    
    library_path: Path  # e.g., .sunwell/skills/
    
    async def save_learned_skill(
        self, 
        skill: Skill,
        source: str,  # "learned", "composed", "imported"
    ) -> Path:
        """Save a skill to the local library.
        
        Skills can come from:
        - Learning: Extracted from successful sessions
        - Composition: Combined from existing skills
        - Import: Copied from another project/Fount
        """
        
        # Create skill directory
        skill_dir = self.library_path / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # Write SKILL.yaml (Anthropic-compatible format)
        skill_file = skill_dir / "SKILL.yaml"
        skill_file.write_text(self._skill_to_yaml(skill))
        
        # Write provenance
        meta_file = skill_dir / "META.yaml"
        meta_file.write_text(f"""
source: {source}
created: {datetime.now().isoformat()}
version: 1.0.0
""")
        
        return skill_dir
    
    def discover_skills(self) -> list[SkillMetadata]:
        """Discover all skills in the library."""
        skills = []
        
        for skill_dir in self.library_path.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.yaml"
                if skill_file.exists():
                    meta = self._load_metadata(skill_file)
                    skills.append(meta)
        
        return skills
```

---

### Part 7: Cross-Platform Portability (P3)

Export skills in Anthropic-compatible format for ecosystem reach.

#### 7.1 Export to Agent Skills Format

```python
# skills/interop.py — EXTENDED

class SkillExporter:
    """Export Sunwell skills to various formats."""
    
    def to_anthropic_skill(self, skill: Skill, output_dir: Path) -> Path:
        """Export to Anthropic Agent Skills format (SKILL.md).
        
        This enables sharing with Claude Code, Claude.ai, etc.
        Note: DAG features (depends_on, produces) are lost.
        """
        
        skill_dir = output_dir / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # Create SKILL.md
        skill_md = f"""---
name: {skill.name}
description: {skill.description}
---

{skill.instructions}
"""
        
        (skill_dir / "SKILL.md").write_text(skill_md)
        
        # Export scripts
        for script in skill.scripts:
            (skill_dir / script.name).write_text(script.content)
        
        return skill_dir
    
    def to_sunwell_skill(self, skill: Skill, output_dir: Path) -> Path:
        """Export to Sunwell format (SKILL.yaml) with full DAG support."""
        
        skill_dir = output_dir / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill_yaml = f"""
name: {skill.name}
description: {skill.description}
type: {skill.skill_type.value}

# DAG metadata (Sunwell-specific)
depends_on:
{self._format_depends_on(skill.depends_on)}
requires: {list(skill.requires)}
produces: {list(skill.produces)}

instructions: |
{self._indent(skill.instructions, 2)}
"""
        
        (skill_dir / "SKILL.yaml").write_text(skill_yaml)
        return skill_dir
```

---

## Implementation Plan

### Phase 0: Build the Compiler (Week 1) — PREREQUISITE

> ⚠️ **This phase must complete before any wiring can happen.**
> 
> **Prerequisite**: RFC-110 (Unified Execution Engine) should be implemented first, or this RFC should be adjusted to work with the existing Agent architecture.

| Day | Task | Deliverable | File |
|-----|------|-------------|------|
| 1 | Create `SkillCompiler` | SkillGraph → TaskGraph | `src/sunwell/skills/compiler.py` |
| 1 | Create `SkillCompilationCache` | Cache compiled plans | `src/sunwell/skills/compiler.py` |
| 2 | Create `SkillCompilationError` | Error handling | `src/sunwell/skills/compiler.py` |
| 2 | Export compiler from `skills/__init__.py` | Public API | `src/sunwell/skills/__init__.py` |
| 3 | Add compiler tests | Coverage | `tests/test_skill_compiler.py` |
| 3 | Integration test: Compiler + SkillGraph → TaskGraph | E2E validation | `tests/test_skill_compile_e2e.py` |

**Exit Criteria**:
```bash
python -c "from sunwell.skills import SkillCompiler"  # Must work
pytest tests/test_skill_compiler.py  # Must pass
```

**RFC-110 Compliance**: No new executor class. Naaru remains THE executor.

### Phase 1: Wire the DAG (Week 2)

| Day | Task | Deliverable |
|-----|------|-------------|
| 4 | Add skill execution path to Agent | Agent can execute skills |
| 4 | Add DAG event emissions | Observability in Studio |
| 5 | Update shortcuts to use subgraph extraction | `-s a-2` uses DAG |
| 5 | Add `sunwell skills graph <lens>` CLI | Visualization |
| 6 | Update `core-skills.yaml` with depends_on/produces/requires | Skills have DAG metadata |
| 6 | Add tests for wave execution via Agent | Coverage |

### Phase 2: Progressive Disclosure (Week 3)

| Day | Task | Deliverable |
|-----|------|-------------|
| 7 | Add `SkillMetadata` type | Lightweight loading |
| 7 | Update `SkillGraph.from_lens_lazy()` | Lazy construction |
| 8 | Update executor to load skills on-demand | No unnecessary loads |
| 8 | Skip full load on cache hit | Context reduction |

### Phase 3: Natural Language to DAG (Week 3-4)

| Day | Task | Deliverable |
|-----|------|-------------|
| 9 | Add `GoalPlanner` | Goal → capability mapping |
| 9 | Add contract-based DAG inference | Auto-build edges from produces/requires |
| 10 | Add gap detection and skill generation | Fill missing capabilities |
| 10 | Integration tests | End-to-end "goal → DAG → execute" |

### Phase 4: Auto-Composition (Week 4)

| Day | Task | Deliverable |
|-----|------|-------------|
| 11 | Add `SkillComposer` | Dynamic skill generation |
| 11 | Add `analyze-and-plan` meta-skill | Complex goal decomposition |
| 12 | Add `compose-skills` meta-skill | Skill combination |
| 12 | Integration tests | End-to-end verification |

### Phase 5: Self-Learning (Week 5)

| Day | Task | Deliverable |
|-----|------|-------------|
| 13 | Add `SkillLearner` | Pattern extraction |
| 13 | Add `SkillLibrary` | Local skill storage |
| 14 | Integrate with Simulacrum | Learn from sessions |
| 14 | Add CLI for skill management | `sunwell skills learn` |

### Phase 6: Interoperability (Week 6)

| Day | Task | Deliverable |
|-----|------|-------------|
| 15 | Add Anthropic export format | SKILL.md output |
| 15 | Add skill import from directories | Anthropic compatibility |

### Timeline Summary

| Phase | Week | Focus | Exit Criteria | Status |
|-------|------|-------|---------------|--------|
| **0** | 1 | Build compiler | `from sunwell.skills import SkillCompiler` works | ✅ |
| **1** | 2 | Wire to Agent | `sunwell -s a-2 file.md` uses skill DAG | ✅ |
| **2** | 3 | Progressive disclosure | Lazy skill loading during compilation | ✅ |
| **3** | 3-4 | NL → DAG | "Audit docs" generates skill graph automatically | ✅ |
| **4** | 4 | Auto-composition | `compose-skills` meta-skill works | ✅ |
| **5** | 5 | Self-learning | `sunwell skills learn` extracts skills from sessions | ✅ |
| **6** | 6 | Interop | `sunwell skills export --format anthropic` works | ✅ |

**Total**: 6 weeks from RFC approval to feature-complete

**RFC-110 Compliance**: Skills compile to Tasks. Naaru executes Tasks. One execution path.

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Skills using depends_on | 0 | 100% |
| Skills using produces/requires | 0 | 100% |
| Agent path using DAG | 0% | 100% |
| Average wave parallelism | 1.0 | >2.0 |
| Cache hit rate (repeat tasks) | 0% | >60% |
| Context tokens saved (lazy load) | 0 | >30% reduction |
| Self-generated skills (after 30 days) | 0 | >10 |

---

## Competitive Positioning

After this RFC:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT CAPABILITY COMPARISON                       │
├─────────────────────────────────────────────────────────────────────┤
│                          │ Anthropic  │ Sunwell   │ Advantage       │
│ ─────────────────────────│────────────│───────────│─────────────────│
│ Skill definition         │ SKILL.md   │ SKILL.yaml│ Equal           │
│ Progressive disclosure   │ ✅          │ ✅         │ Equal           │
│ Skill dependencies       │ ❌          │ ✅ DAG     │ SUNWELL         │
│ Data flow contracts      │ ❌          │ ✅         │ SUNWELL         │
│ Parallel execution       │ ❌          │ ✅ Waves   │ SUNWELL         │
│ Input-aware caching      │ ❌          │ ✅         │ SUNWELL         │
│ Lens composition         │ ❌          │ ✅         │ SUNWELL         │
│ Dynamic skill generation │ ❌          │ ✅         │ SUNWELL         │
│ Self-learning skills     │ ❌          │ ✅         │ SUNWELL         │
│ Build-system semantics   │ ❌          │ ✅ Bazel   │ SUNWELL         │
└─────────────────────────────────────────────────────────────────────┘
```

**Sunwell becomes the only AI agent with build-system-grade orchestration.**

---

## Design Alternatives Considered

### Alternative A: Replace Naaru with Skills

**Approach**: Delete the Task abstraction. Skills become the only execution unit.

**Pros**:
- Simpler mental model (one abstraction)
- No Skills-vs-Tasks confusion

**Cons**:
- Breaks all existing CLI, shortcuts, Studio
- Tasks are procedural ("do X"), Skills are declarative ("I can do X")
- Different purposes — wrong to unify

**Decision**: ❌ Rejected

---

### Alternative B: Add IncrementalSkillExecutor (Original RFC-111 Draft)

**Approach**: Build a separate executor for skills alongside Naaru.

**Pros**:
- Skills get their own optimized execution path
- Full control over skill-specific caching

**Cons**:
- **Contradicts RFC-110** — adds executor proliferation
- Two parallel execution systems to maintain
- Confuses "where does execution happen?"

**Decision**: ❌ Rejected — RFC-110 explicitly deletes skill executors

---

### Alternative C: Skills Compile to Tasks (CHOSEN)

**Approach**: Skills are a PLANNING abstraction. `SkillCompiler` transforms SkillGraph → TaskGraph. Naaru executes Tasks.

```
User Goal → Agent → SkillGraph → SkillCompiler → TaskGraph → Naaru → Tools
                      ↑ PLANNING                    ↑ EXECUTION
```

**Pros**:
- **RFC-110 compliant** — Naaru remains THE executor
- Clean separation: Skills = planning, Tasks = execution
- Reuses Naaru's parallelism, caching, observability
- Compilation can be cached independently

**Cons**:
- Two DAG representations (skills, tasks) — but they serve different purposes
- Compilation adds a step — but it's fast and cacheable

**Decision**: ✅ **Chosen** — best long-term architecture

This is the pattern used by mature build systems:
- **Bazel**: BUILD rules → Actions → Execution
- **Airflow**: DAG → Task Instances → Executor
- **Sunwell**: Skills → Tasks → Naaru

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| DAG overhead for simple tasks | Use `subgraph_for()` to extract minimal graph |
| Circular dependencies | Validation at resolution time with clear errors |
| Cache staleness | Content + input hash ensures correctness |
| Generated skills are low quality | Validation gates + human review for persistence |
| Complexity for users | Hide DAG by default, expose via `--verbose` |
| Two DAG layers confusing | Clear docs: Skills = planning, Tasks = execution |
| Compilation overhead | Cache compiled TaskGraphs (fast recompilation) |
| Skills → Tasks mapping loses info | Preserve skill metadata in Task.context |

---

## Non-Goals

1. **NOT replacing lenses** — Skills complement lenses (action vs. judgment)
2. **NOT abandoning YAML** — Keep YAML for skill definitions
3. **NOT requiring DAG for all skills** — Skills without deps work fine (wave 1)
4. **NOT auto-learning without consent** — Users opt-in to skill persistence

---

## Summary

This RFC activates Sunwell's skill DAG infrastructure using the **compiler pattern**:

| Component | Status | This RFC |
|-----------|--------|----------|
| `SkillGraph` | ✅ Exists | Wire to Agent |
| `SkillCache` | ✅ Exists | Repurpose for compilation cache |
| `SkillCompiler` | ❌ Missing | **Build in Phase 0** |
| `SkillCompilationCache` | ❌ Missing | **Build in Phase 0** |
| Skill metadata (depends_on/produces) | ❌ Empty | Populate in Phase 1 |
| Progressive disclosure | ❌ Missing | Add in Phase 2 |
| Natural language → DAG | ❌ Missing | Add in Phase 3 |

### Key Architecture Decision

**Skills compile to Tasks. Naaru executes Tasks.**

This follows RFC-110's "one executor" principle while getting RFC-111's DAG benefits:
- No new executor class (RFC-110 compliant)
- Skill dependencies preserved (compiles to Task dependencies)
- Parallel execution via Naaru (already works)
- Caching at compilation layer (new) AND execution layer (existing)

### The Unlock: Two-Layer DAG Intelligence

Compilation enables **task composition and decomposition**:

```
Skill DAG (coarse)  →  Compiler  →  Task DAG (fine)  →  Naaru (parallel)
```

- **Composition**: One skill can produce multiple related tasks
- **Decomposition**: Complex skills become pipelines of smaller tasks
- **Parallelization**: Naaru sees the fine-grained graph and maximizes concurrency

**Skills express WHAT. Tasks express HOW. Naaru parallelizes WHERE possible.**

**The conventional wisdom**: "DAGs aren't fun."  
**Sunwell's answer**: DAGs aren't fun *when you write them*. But when AI writes them, compiles them to efficient task graphs, executes in parallel waves, and learns from patterns — DAGs become delightful.

**The thesis stands**: Sunwell becomes the only AI agent with build-system-grade orchestration — without adding executor complexity.

---

## Appendix: Full Skill Library with DAG Metadata

See `skills/core-skills-dag.yaml` for the complete updated skill library.

## Appendix: Event Schema for DAG Execution

See `schemas/agent-events.schema.json` for new DAG-related events:
- `skill_graph_resolved`
- `skill_wave_start`
- `skill_wave_complete`
- `skill_cache_hit`
- `skill_execute_start`
- `skill_execute_complete`
