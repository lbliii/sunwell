"""Skill compilation for DAG-based execution (RFC-111).

This module implements the SkillCompiler component of RFC-111: Skill DAG Activation.
It provides the bridge between RFC-087 (Skill DAG) and RFC-110 (Unified Execution).

Key insight: Skills are PLANNING abstractions. Tasks are EXECUTION abstractions.
The compiler transforms declarative skills into procedural tasks that Naaru can execute.

Pattern follows mature build systems:
- Bazel: BUILD rules → Actions → Execution
- Airflow: DAG → Task Instances → Executor
- Sunwell: Skills → Tasks → Naaru

Example:
    >>> from sunwell.skills import SkillCompiler, SkillGraph
    >>> compiler = SkillCompiler(lens=my_lens)
    >>> skill_graph = SkillGraph.from_skills(lens.skills)
    >>> task_graph = compiler.compile(skill_graph, {"target": "docs/"})
    >>> results = await naaru.execute_tasks(task_graph)
"""

import hashlib
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.naaru.types import Task, TaskMode, TaskStatus

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.skills.graph import SkillGraph
    from sunwell.skills.types import Skill, SkillMetadata


# =============================================================================
# EXCEPTIONS
# =============================================================================


class SkillCompilationError(Exception):
    """Error during skill compilation.

    Raised when:
    - Skill graph validation fails (cycles, missing deps)
    - Required context keys not provided
    - Skill produces/requires contract violations
    """

    def __init__(
        self,
        message: str,
        skill_name: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        self.skill_name = skill_name
        self.errors = errors or []
        super().__init__(message)


# =============================================================================
# COMPILATION CACHE
# =============================================================================


@dataclass(slots=True)
class CompiledTaskGraph:
    """Result of skill compilation — ready for Naaru execution.

    This is the output of SkillCompiler.compile(). It contains:
    - Tasks in topological order
    - Execution waves for parallelism
    - Metadata for observability
    """

    tasks: list[Task] = field(default_factory=list)
    """Tasks in dependency order."""

    waves: list[list[str]] = field(default_factory=list)
    """Task IDs grouped by parallel execution waves."""

    skill_to_task: dict[str, str] = field(default_factory=dict)
    """Mapping from skill name to task ID."""

    content_hash: str = ""
    """Hash of source skills for cache invalidation."""

    def has_pending_tasks(self, completed_ids: set[str]) -> bool:
        """Check if there are pending tasks."""
        return len(completed_ids) < len(self.tasks)

    def get_ready_tasks(
        self,
        completed_ids: set[str],
        completed_artifacts: set[str] | None = None,
    ) -> list[Task]:
        """Get tasks that are ready to execute."""
        return [
            t
            for t in self.tasks
            if t.id not in completed_ids
            and t.is_ready(completed_ids, completed_artifacts)
        ]

    def get_wave_for_task(self, task_id: str) -> int:
        """Get wave number for a task."""
        for i, wave in enumerate(self.waves):
            if task_id in wave:
                return i
        return -1


class SkillCompilationCache:
    """Cache compiled TaskGraphs from SkillGraphs (RFC-111).

    Key insight: If skills haven't changed, the compiled TaskGraph
    is identical. Cache it to skip recompilation.

    Naaru's execution cache handles caching actual results.
    This cache handles caching the PLAN.

    Thread-safe via internal locking. Uses OrderedDict for O(1) LRU.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._cache: OrderedDict[str, CompiledTaskGraph] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def compute_key(self, skill_graph: SkillGraph, context: dict[str, Any]) -> str:
        """Compute cache key from graph content and context."""
        hasher = hashlib.sha256()
        hasher.update(skill_graph.content_hash().encode())

        # Sort context for deterministic hashing
        context_str = json.dumps(
            {k: str(v) for k, v in sorted(context.items())},
            sort_keys=True,
        )
        hasher.update(context_str.encode())

        return hasher.hexdigest()[:16]

    def get(self, key: str) -> CompiledTaskGraph | None:
        """Get cached TaskGraph if available."""
        with self._lock:
            if key in self._cache:
                self._hits += 1
                # Move to end for LRU
                self._cache.move_to_end(key)
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, task_graph: CompiledTaskGraph) -> None:
        """Cache a compiled TaskGraph."""
        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            # Remove existing if present, then add at end
            if key in self._cache:
                del self._cache[key]
            self._cache[key] = task_graph

    def has(self, key: str) -> bool:
        """Check if key exists without updating access order."""
        with self._lock:
            return key in self._cache

    def clear(self) -> None:
        """Clear all cached compilations."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int | float]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


# =============================================================================
# SKILL COMPILER
# =============================================================================


@dataclass(slots=True)
class SkillCompiler:
    """Compile SkillGraph into TaskGraph for Naaru execution (RFC-111).

    This is the bridge between RFC-111 (Skill DAG) and RFC-110 (Unified Execution).

    Skills are PLANNING abstractions — they describe capabilities.
    Tasks are EXECUTION abstractions — they describe work.

    The compiler transforms declarative skills into procedural tasks
    that Naaru can execute in parallel waves.

    Attributes:
        lens: Lens providing skill context
        cache: Optional cache for compiled results
    """

    lens: Lens | None = None
    """Lens providing skill context."""

    cache: SkillCompilationCache | None = None
    """Optional cache for compiled results."""

    def compile(
        self,
        skill_graph: SkillGraph,
        context: dict[str, Any] | None = None,
        target_skills: set[str] | None = None,
    ) -> CompiledTaskGraph:
        """Compile skills into executable tasks.

        Args:
            skill_graph: Graph of skills with dependencies
            context: Execution context (target files, user input, etc.)
            target_skills: Optional subset of skills to compile (includes deps)

        Returns:
            CompiledTaskGraph ready for Naaru execution

        Raises:
            SkillCompilationError: If skill graph validation fails

        Example:
            >>> compiler = SkillCompiler(lens=my_lens)
            >>> skill_graph = SkillGraph.from_skills(lens.skills)
            >>> task_graph = compiler.compile(skill_graph, {"target": "docs/"})
            >>> results = await naaru.execute_tasks(task_graph)
        """
        context = context or {}

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
            raise SkillCompilationError(
                f"Invalid skill graph: {errors}",
                errors=errors,
            )

        # Compile each skill to a task
        tasks: list[Task] = []
        skill_to_task: dict[str, str] = {}

        for skill in skill_graph:
            task_id = f"skill:{skill.name}"
            skill_to_task[skill.name] = task_id

            # Map skill dependencies to task dependencies
            task_deps = tuple(
                skill_to_task[dep.skill_name]
                for dep in skill.depends_on
                if dep.skill_name in skill_to_task
            )

            task = self._compile_skill_to_task(
                skill=skill,
                task_id=task_id,
                task_deps=task_deps,
                context=context,
            )
            tasks.append(task)

        # Compute execution waves from task graph
        waves = self._compute_waves(tasks, skill_to_task)

        result = CompiledTaskGraph(
            tasks=tasks,
            waves=waves,
            skill_to_task=skill_to_task,
            content_hash=skill_graph.content_hash(),
        )

        # Cache the compiled result
        if self.cache:
            self.cache.set(cache_key, result)

        return result

    def _compile_skill_to_task(
        self,
        skill: Skill,
        task_id: str,
        task_deps: tuple[str, ...],
        context: dict[str, Any],
    ) -> Task:
        """Convert a single skill to a task.

        This is where skill contracts (produces/requires) become task contracts.
        Skill metadata flows into task context for execution.
        """
        # Build task context from skill metadata
        task_context: dict[str, Any] = {
            "skill_name": skill.name,
            "skill_instructions": skill.instructions,
            "skill_requires": list(skill.requires),
            "skill_produces": list(skill.produces),
        }

        # Add lens context if available
        if self.lens:
            task_context["lens_name"] = self.lens.metadata.name
            task_context["lens_version"] = str(self.lens.metadata.version)

        # Add requested context values (from skill.requires)
        for key in skill.requires:
            if key in context:
                task_context[key] = context[key]

        return Task(
            id=task_id,
            description=f"[{skill.name}] {skill.description}",
            mode=TaskMode.GENERATE,
            depends_on=task_deps,
            produces=frozenset(skill.produces),
            requires=frozenset(skill.requires),
            status=TaskStatus.PENDING,
            details=task_context,
        )

    def _compute_waves(
        self,
        tasks: list[Task],
        skill_to_task: dict[str, str],
    ) -> list[list[str]]:
        """Group tasks into parallel execution waves.

        Each wave contains tasks whose dependencies are satisfied
        by previous waves. Tasks in the same wave can run in parallel.
        """
        if not tasks:
            return []

        task_by_id = {t.id: t for t in tasks}
        completed: set[str] = set()
        pending = {t.id for t in tasks}
        waves: list[list[str]] = []

        while pending:
            # Find all tasks whose dependencies are satisfied
            ready = [
                task_id
                for task_id in pending
                if all(dep in completed for dep in task_by_id[task_id].depends_on)
            ]

            if not ready:
                # Deadlock — should have been caught by validation
                raise SkillCompilationError(
                    f"Execution deadlock with pending tasks: {pending}"
                )

            waves.append(ready)
            completed.update(ready)
            pending -= set(ready)

        return waves

    def compile_for_shortcut(
        self,
        shortcut: str,
        target: str,
        skill_graph: SkillGraph,
    ) -> CompiledTaskGraph:
        """Compile skills for a shortcut execution.

        Shortcuts like `-s a-2` map to specific skills.
        This compiles just those skills (plus dependencies).

        Args:
            shortcut: Shortcut identifier (e.g., "a", "a-2")
            target: Target path or file
            skill_graph: Full skill graph to extract from

        Returns:
            CompiledTaskGraph for the shortcut's skills
        """
        # Map shortcuts to skills (extensible)
        shortcut_skills: dict[str, set[str]] = {
            "a": {"audit-documentation"},
            "a-2": {"audit-documentation", "fix-documentation-issues"},
            "d": {"create-api-reference"},
            "q": {"create-quickstart"},
        }

        target_skills = shortcut_skills.get(shortcut, set())
        context = {"target": target, "shortcut": shortcut}

        return self.compile(skill_graph, context, target_skills or None)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def has_dag_metadata(skills: tuple[Skill, ...] | list[Skill]) -> bool:
    """Check if any skills have DAG metadata.

    Returns True if at least one skill has depends_on, produces, or requires.
    This determines whether to use skill compilation vs legacy planning.
    """
    return any(
        skill.depends_on or skill.produces or skill.requires
        for skill in skills
    )
