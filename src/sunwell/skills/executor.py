"""Skill executor - runs skills with lens validation.

Implements the execution flow from RFC-011 Section 3.
RFC-087: Adds IncrementalSkillExecutor for DAG-based execution with caching.
"""


import asyncio
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.skills.sandbox import ScriptSandbox, expand_template_variables
from sunwell.skills.types import (
    Skill,
    SkillError,
    SkillOutput,
    SkillOutputMetadata,
    SkillResult,
    SkillRetryPolicy,
)

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol
    from sunwell.skills.cache import SkillCache
    from sunwell.skills.graph import SkillGraph


# =============================================================================
# RFC-087: Execution Exceptions
# =============================================================================


class SkillExecutionError(Exception):
    """Raised when skill execution fails."""

    def __init__(
        self,
        skill_name: str,
        phase: str,  # "setup", "execute", "validate"
        cause: Exception,
        recoverable: bool = False,
    ) -> None:
        self.skill_name = skill_name
        self.phase = phase
        self.cause = cause
        self.recoverable = recoverable
        super().__init__(f"Skill '{skill_name}' failed during {phase}: {cause}")


class WaveExecutionError(Exception):
    """Raised when a parallel wave fails."""

    def __init__(self, wave_index: int, failures: list[SkillExecutionError]) -> None:
        self.wave_index = wave_index
        self.failures = failures
        names = [f.skill_name for f in failures]
        super().__init__(
            f"Wave {wave_index} failed: {len(failures)} skill(s) failed: {names}"
        )


# =============================================================================
# RFC-087: Execution Context
# =============================================================================


@dataclass
class ExecutionContext:
    """Shared context for skill execution (RFC-087)."""

    data: dict[str, Any] = field(default_factory=dict)
    """Context data produced by skills (the 'produces' values)."""

    lens_version: str | None = None
    """Lens version for cache key computation."""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, key: str) -> Any:
        """Get a context value (thread-safe)."""
        with self._lock:
            return self.data.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set a context value (thread-safe)."""
        with self._lock:
            self.data[key] = value

    def update(self, values: dict[str, Any]) -> None:
        """Update multiple context values (thread-safe)."""
        with self._lock:
            self.data.update(values)

    def snapshot(self) -> dict[str, Any]:
        """Get a snapshot of current context (thread-safe)."""
        with self._lock:
            return dict(self.data)

    def has_all(self, keys: tuple[str, ...]) -> bool:
        """Check if all keys are present in context."""
        with self._lock:
            return all(k in self.data for k in keys)


@dataclass
class SkillExecutor:
    """Execute skills with lens validation.

    Implements the execution flow:
    1. Build prompt from skill instructions
    2. Execute with model
    3. Run any scripts
    4. Validate with lens (if enabled)
    5. Refine if validation fails
    """

    skill: Skill
    lens: Lens
    model: ModelProtocol

    # Configuration
    workspace_root: Path | None = None
    retry_policy: SkillRetryPolicy = field(default_factory=SkillRetryPolicy)

    # Internal state
    _sandbox: ScriptSandbox | None = field(default=None, init=False)

    async def execute(
        self,
        context: dict[str, str],
        *,
        validate: bool = True,
        dry_run: bool = False,
    ) -> SkillResult:
        """Execute skill and optionally validate with lens.

        Args:
            context: Variables for template expansion (e.g., {"name": "auth"})
            validate: Whether to run lens validators on output
            dry_run: If True, don't write any files

        Returns:
            SkillResult with content, validation status, and artifacts
        """
        start_time = time.time()
        scripts_run: list[str] = []
        refinement_count = 0

        # Initialize sandbox
        self._sandbox = self._create_sandbox()

        # 1. Build prompt from skill instructions
        prompt = self._build_skill_prompt(context)

        # 2. Execute with model
        result = await self.model.generate(prompt)
        content = result.content

        # 3. Run any scripts (if trust level allows)
        if self.skill.scripts and self._sandbox.can_execute():
            for script in self.skill.scripts:
                script_result = await self._run_script(script, context, content)
                scripts_run.append(script.name)

                # If script produces output, use it
                if script_result.stdout:
                    content = script_result.stdout

        # 4. Validate with lens (if enabled)
        validation_passed = True
        confidence = 1.0

        if validate:
            validation_result = await self._validate_with_lens(content)
            validation_passed = validation_result["passed"]
            confidence = validation_result["confidence"]

            # 5. Refine if validation fails
            max_retries = self.retry_policy.max_attempts
            while not validation_passed and refinement_count < max_retries:
                content = await self._refine(content, validation_result)
                refinement_count += 1

                # Re-validate
                validation_result = await self._validate_with_lens(content)
                validation_passed = validation_result["passed"]
                confidence = validation_result["confidence"]

        execution_time_ms = int((time.time() - start_time) * 1000)

        return SkillResult(
            content=content,
            skill_name=self.skill.name,
            lens_name=self.lens.metadata.name,
            validation_passed=validation_passed,
            confidence=confidence,
            artifacts=(),  # TODO: Track file artifacts
            execution_time_ms=execution_time_ms,
            scripts_run=tuple(scripts_run),
            refinement_count=refinement_count,
        )

    def _create_sandbox(self) -> ScriptSandbox:
        """Create sandbox with appropriate trust level."""
        read_paths = ()
        write_paths = ()

        if self.workspace_root:
            read_paths = (self.workspace_root,)

        return ScriptSandbox(
            trust=self.skill.trust,
            read_paths=read_paths,
            write_paths=write_paths,
            timeout_seconds=self.skill.timeout,
        )

    def _build_skill_prompt(self, context: dict[str, str]) -> str:
        """Build prompt from skill instructions and lens context."""
        parts = []

        # Add lens expertise context
        lens_context = self.lens.to_context()
        if lens_context:
            parts.append(lens_context)

        # Add skill instructions
        if self.skill.instructions:
            expanded = expand_template_variables(self.skill.instructions, context)
            parts.append(f"\n---\n\n## Skill: {self.skill.name}\n\n{expanded}")

        # Add templates as reference
        if self.skill.templates:
            parts.append("\n### Templates Available\n")
            for template in self.skill.templates:
                expanded = expand_template_variables(template.content, context)
                parts.append(f"\n**{template.name}**:\n```\n{expanded}\n```")

        # Add resources as reference
        if self.skill.resources:
            parts.append("\n### Resources\n")
            for resource in self.skill.resources:
                if resource.url:
                    parts.append(f"- [{resource.name}]({resource.url})")
                elif resource.path:
                    parts.append(f"- {resource.name}: `{resource.path}`")

        # Add task context
        if context.get("task"):
            parts.append(f"\n---\n\n## Task\n\n{context['task']}")

        return "\n".join(parts)

    async def _run_script(
        self,
        script,
        context: dict[str, str],
        current_content: str,
    ):
        """Run a script in the sandbox."""
        if not self._sandbox:
            raise SkillError(
                phase="execute",
                skill_name=self.skill.name,
                message="Sandbox not initialized",
                recoverable=False,
            )

        # Build args from context
        args = []
        if context.get("input_file"):
            args.append(context["input_file"])

        return await self._sandbox.execute(script, args)

    async def _validate_with_lens(self, content: str) -> dict:
        """Validate content using lens validators.

        Returns dict with:
        - passed: bool
        - confidence: float
        - feedback: list of failure messages
        """
        validation = self.skill.validate_with
        feedback = []
        scores = []

        # Get validators to run
        validators_to_run = []
        if validation.validators:
            for name in validation.validators:
                for v in self.lens.heuristic_validators:
                    if v.name == name:
                        validators_to_run.append(v)
                        break
        else:
            # Run all validators by default
            validators_to_run = list(self.lens.heuristic_validators)

        # Run validators in parallel
        if validators_to_run:

            async def validate_one(validator):
                validation_prompt = validator.to_prompt(content)
                response = await self.model.generate(validation_prompt)

                try:
                    parts = response.content.strip().split("|", 2)
                    passed = parts[0].upper() == "PASS"
                    confidence = float(parts[1]) if len(parts) > 1 else 0.5
                    message = parts[2] if len(parts) > 2 else None
                except (ValueError, IndexError):
                    passed = False
                    confidence = 0.5
                    message = response.content

                return {
                    "name": validator.name,
                    "passed": passed,
                    "confidence": confidence,
                    "message": message,
                }

            results = await asyncio.gather(*[validate_one(v) for v in validators_to_run])

            for r in results:
                scores.append(r["confidence"])
                if not r["passed"] and r["message"]:
                    feedback.append(f"{r['name']}: {r['message']}")

        # Calculate overall pass/confidence
        avg_confidence = sum(scores) / len(scores) if scores else 1.0
        passed = avg_confidence >= validation.min_confidence and not feedback

        return {
            "passed": passed,
            "confidence": avg_confidence,
            "feedback": feedback,
        }

    async def _refine(self, content: str, validation: dict) -> str:
        """Refine content based on validation feedback."""
        feedback = "\n".join(f"- {f}" for f in validation["feedback"])

        refinement_prompt = f"""The following content needs improvement based on validation feedback:

## Original Content
{content}

## Feedback to Address
{feedback}

## Task
Revise the content to address all feedback while maintaining quality. Return only the improved content."""

        result = await self.model.generate(refinement_prompt)
        return result.content


@dataclass
class SkillAwareClassifier:
    """Extends base classifier with skill matching.

    Implements implicit skill activation from RFC-011 Section 4.
    """

    lens: Lens
    embedder: object | None = None  # EmbeddingProtocol

    # Common stopwords to ignore in matching
    STOPWORDS: frozenset = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "this", "that",
        "these", "those", "it", "its", "you", "your", "my", "our", "their",
    })

    def classify(self, task: str) -> dict:
        """Match task to best skill.

        Returns:
            ClassificationResult with skill, confidence, and reason
        """
        if not hasattr(self.lens, "skills") or not self.lens.skills:
            return {"skill": None, "confidence": 1.0, "reason": "No skills available"}

        # 1. Check explicit skill mention
        task_lower = task.lower()
        for skill in self.lens.skills:
            if skill.name.replace("-", " ") in task_lower or skill.name in task_lower:
                return {
                    "skill": skill,
                    "confidence": 0.95,
                    "reason": "Explicit skill reference in task",
                }

        # 2. Check action verb + description match
        action_verbs = ["create", "generate", "extract", "convert", "write", "build", "make"]
        has_action = any(verb in task_lower for verb in action_verbs)

        if has_action:
            # Find skill with best matching description keywords (excluding stopwords)
            best_skill = None
            best_score = 0

            for skill in self.lens.skills:
                # Extract content words from description
                desc_words = set(skill.description.lower().split()) - self.STOPWORDS
                task_words = set(task_lower.split()) - self.STOPWORDS

                # Count meaningful word matches
                matches = len(desc_words & task_words)

                if matches > best_score:
                    best_score = matches
                    best_skill = skill

            if best_skill and best_score >= 1:
                return {
                    "skill": best_skill,
                    "confidence": min(0.5 + best_score * 0.15, 0.85),
                    "reason": f"Action verb + description match: {best_skill.description}",
                }

        # 3. No skill match — use lens heuristics only
        return {"skill": None, "confidence": 1.0, "reason": "No skill needed"}


# =============================================================================
# RFC-087: Incremental Skill Executor
# =============================================================================


@dataclass
class SkillExecutionPlan:
    """Execution plan with cache predictions (RFC-087)."""

    to_execute: list[str]
    """Skill names that will run."""

    to_skip: list[str]
    """Skill names with cache hits."""

    waves: list[list[str]]
    """Execution waves."""

    @property
    def skip_percentage(self) -> float:
        """Percentage of skills that will be skipped (0-100)."""
        total = len(self.to_execute) + len(self.to_skip)
        return (len(self.to_skip) / total * 100) if total > 0 else 0.0

    def to_dict(self) -> dict:
        """Serialize for JSON export."""
        return {
            "toExecute": self.to_execute,
            "toSkip": self.to_skip,
            "waves": self.waves,
            "skipPercentage": self.skip_percentage,
        }


@dataclass
class IncrementalSkillExecutor:
    """Execute skills with caching and incremental updates (RFC-087).

    This executor:
    1. Computes execution waves from the skill graph
    2. Checks cache for each skill
    3. Executes only non-cached skills in parallel waves
    4. Updates context with produces values
    5. Caches results for future runs
    """

    lens: Lens
    model: ModelProtocol
    cache: SkillCache | None = None
    workspace_root: Path | None = None

    def __post_init__(self) -> None:
        if self.cache is None:
            from sunwell.skills.cache import SkillCache

            self.cache = SkillCache()

    def plan(
        self,
        graph: SkillGraph,
        context: ExecutionContext,
    ) -> SkillExecutionPlan:
        """Plan execution, identifying what will run vs skip.

        Args:
            graph: Skill graph to execute
            context: Execution context

        Returns:
            Execution plan with cache predictions
        """
        from sunwell.skills.cache import SkillCacheKey

        to_execute: list[str] = []
        to_skip: list[str] = []
        waves = graph.execution_waves()

        for wave in waves:
            for skill_name in wave:
                skill = graph.get(skill_name)
                if skill is None:
                    continue

                cache_key = SkillCacheKey.compute(
                    skill, context.snapshot(), context.lens_version
                )

                if self.cache and self.cache.has(cache_key):
                    to_skip.append(skill_name)
                else:
                    to_execute.append(skill_name)

        return SkillExecutionPlan(
            to_execute=to_execute,
            to_skip=to_skip,
            waves=waves,
        )

    async def execute(
        self,
        graph: SkillGraph,
        context: ExecutionContext,
        on_wave_start: Any | None = None,
        on_wave_complete: Any | None = None,
        on_skill_start: Any | None = None,
        on_skill_complete: Any | None = None,
        on_cache_hit: Any | None = None,
    ) -> dict[str, SkillOutput]:
        """Execute skill graph, skipping cached results.

        Args:
            graph: Skill graph to execute
            context: Execution context
            on_wave_start: Callback(wave_index, total_waves, skill_names)
            on_wave_complete: Callback(wave_index, duration_ms, succeeded, failed)
            on_skill_start: Callback(skill_name, wave_index, requires, available_keys)
            on_skill_complete: Callback(skill_name, duration_ms, produces, cached, success, error)
            on_cache_hit: Callback(skill_name, cache_key, estimated_saved_ms)

        Returns:
            Mapping of skill name to output

        Raises:
            WaveExecutionError: If any wave fails
        """
        from sunwell.skills.cache import SkillCacheKey

        results: dict[str, SkillOutput] = {}
        waves = graph.execution_waves()
        total_waves = len(waves)

        for wave_idx, wave in enumerate(waves):
            wave_start = time.time()

            if on_wave_start:
                on_wave_start(wave_idx, total_waves, wave)

            wave_tasks: list = []
            wave_skills: list[Skill] = []
            succeeded: list[str] = []
            failed: list[str] = []

            for skill_name in wave:
                skill = graph.get(skill_name)
                if skill is None:
                    continue

                # Check cache
                cache_key = SkillCacheKey.compute(
                    skill, context.snapshot(), context.lens_version
                )

                cached_entry = self.cache.get(cache_key) if self.cache else None
                if cached_entry:
                    results[skill_name] = cached_entry.output
                    succeeded.append(skill_name)

                    # Update context with cached produces
                    for key in skill.produces:
                        if key in cached_entry.output.context:
                            context.set(key, cached_entry.output.context[key])

                    if on_cache_hit:
                        on_cache_hit(
                            skill_name,
                            str(cache_key),
                            cached_entry.execution_time_ms,
                        )
                    continue

                if on_skill_start:
                    on_skill_start(
                        skill_name,
                        wave_idx,
                        list(skill.requires),
                        list(context.snapshot().keys()),
                    )

                wave_tasks.append(self._execute_skill(skill, context))
                wave_skills.append(skill)

            if not wave_tasks:
                wave_duration = int((time.time() - wave_start) * 1000)
                if on_wave_complete:
                    on_wave_complete(wave_idx, wave_duration, succeeded, failed)
                continue

            # Execute wave in parallel
            wave_results = await asyncio.gather(*wave_tasks, return_exceptions=True)

            # Process results
            failures: list[SkillExecutionError] = []
            for skill, result in zip(wave_skills, wave_results, strict=True):
                if isinstance(result, Exception):
                    error = SkillExecutionError(
                        skill.name, "execute", result, recoverable=False
                    )
                    failures.append(error)
                    failed.append(skill.name)

                    if on_skill_complete:
                        on_skill_complete(
                            skill.name,
                            0,
                            list(skill.produces),
                            False,
                            False,
                            str(result),
                        )
                    continue

                output, execution_time_ms = result
                results[skill.name] = output
                succeeded.append(skill.name)

                # Update context with produces
                for key in skill.produces:
                    if key in output.context:
                        context.set(key, output.context[key])

                # Cache the result
                if self.cache:
                    cache_key = SkillCacheKey.compute(
                        skill, context.snapshot(), context.lens_version
                    )
                    self.cache.set(cache_key, output, skill.name, execution_time_ms)

                if on_skill_complete:
                    on_skill_complete(
                        skill.name,
                        execution_time_ms,
                        list(skill.produces),
                        False,
                        True,
                        None,
                    )

            wave_duration = int((time.time() - wave_start) * 1000)
            if on_wave_complete:
                on_wave_complete(wave_idx, wave_duration, succeeded, failed)

            if failures:
                raise WaveExecutionError(wave_idx, failures)

        return results

    async def _execute_skill(
        self,
        skill: Skill,
        context: ExecutionContext,
    ) -> tuple[SkillOutput, int]:
        """Execute a single skill.

        Args:
            skill: Skill to execute
            context: Execution context

        Returns:
            Tuple of (output, execution_time_ms)
        """
        start_time = time.time()

        # Build context dict for template expansion
        ctx_dict = context.snapshot()

        # Create single-skill executor
        executor = SkillExecutor(
            skill=skill,
            lens=self.lens,
            model=self.model,
            workspace_root=self.workspace_root,
        )

        # Execute with validation
        result = await executor.execute(ctx_dict, validate=True)

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Build context values from produces
        output_context: dict[str, Any] = {}
        for key in skill.produces:
            # Convention: skill produces its result content under its name
            if key == skill.name:
                output_context[key] = result.content
            elif key == "content":
                output_context[key] = result.content

        output = SkillOutput(
            content=result.content,
            content_type="text",
            artifacts=result.artifacts,
            metadata=SkillOutputMetadata(
                skill_name=skill.name,
                execution_time_ms=execution_time_ms,
                scripts_run=result.scripts_run,
            ),
            context=output_context,
        )

        return output, execution_time_ms
