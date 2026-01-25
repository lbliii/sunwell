"""Evaluation Executors (RFC-098).

Provides two execution strategies for evaluation:
1. SingleShotExecutor: Baseline single-turn generation with tools
2. SunwellFullStackExecutor: Full cognitive stack via Naaru

Both get identical tool capabilities for fair comparison.
The difference is the cognitive architecture.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path

from sunwell.foundation.utils import safe_yaml_load
from sunwell.benchmark.eval.types import FullStackTask, SingleShotResult, SunwellResult
from sunwell.models import GenerateOptions, ModelProtocol, Tool

logger = logging.getLogger(__name__)


class EvaluationError(Exception):
    """Error during evaluation execution."""

    pass


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

# Tools available to both single-shot and Sunwell executors
EVALUATION_TOOLS: tuple[Tool, ...] = (
    Tool(
        name="create_file",
        description="Create a file with the given content",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file to create",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    ),
    Tool(
        name="read_file",
        description="Read the content of an existing file",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file to read",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="list_dir",
        description="List files and directories in a path",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the directory",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="run_command",
        description="Run a shell command (e.g., to test the code)",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run",
                },
            },
            "required": ["command"],
        },
    ),
)


def _get_tools_for_task(task: FullStackTask) -> tuple[Tool, ...]:
    """Get the tools available for a given task."""
    return tuple(
        tool for tool in EVALUATION_TOOLS if tool.name in task.available_tools
    )


def _format_tools_description(tools: tuple[Tool, ...]) -> str:
    """Format tools for inclusion in prompt."""
    lines = []
    for tool in tools:
        lines.append(f"- {tool.name}: {tool.description}")
        props = tool.parameters.get("properties", {})
        for prop_name, prop_def in props.items():
            lines.append(f"    - {prop_name}: {prop_def.get('description', '')}")
    return "\n".join(lines)


# =============================================================================
# SINGLE-SHOT EXECUTOR
# =============================================================================


class SingleShotExecutor:
    """Execute a single-turn generation with tools.

    This is the baseline comparison — what you'd get from raw model prompting
    with tool calling, but no cognitive architecture (no Lens, no Judge,
    no Resonance, no Memory).

    The model gets ONE turn to:
    1. Generate a plan
    2. Create all files using tools
    3. No feedback, no second chances
    """

    def __init__(self, model: ModelProtocol) -> None:
        """Initialize executor with a model.

        Args:
            model: A model implementing the ModelProtocol.

        Raises:
            EvaluationError: If model doesn't support tool calling.
        """
        self.model = model

    async def run(
        self,
        task: FullStackTask,
        output_dir: Path,
        *,
        on_file_created: Callable[[str], None] | None = None,
    ) -> SingleShotResult:
        """Run single-shot generation with tool calling.

        The model gets ONE turn to:
        1. Generate a plan
        2. Create all files using tools
        3. No feedback, no second chances

        Args:
            task: The evaluation task to run.
            output_dir: Directory to write generated files.
            on_file_created: Callback when a file is created.

        Returns:
            SingleShotResult with files created and timing.

        Raises:
            EvaluationError: If execution fails.
        """
        tools = _get_tools_for_task(task)

        prompt = f"""You are building a software project.

Task: {task.prompt}

You have access to these tools:
{_format_tools_description(tools)}

Create a complete, working implementation. You have ONE turn.
Output all files needed for a working application.

Use the tools to create the files. Do not just output code in your response -
use the create_file tool for each file you need to create.
"""

        start_time = time.monotonic()
        files_created: list[str] = []
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            # Single generation with tool calls
            result = await self.model.generate(
                prompt,
                tools=tools,
                tool_choice="auto",
                options=GenerateOptions(
                    temperature=0.7,
                    max_tokens=4096,
                ),
            )

            if result.usage:
                total_input_tokens = result.usage.prompt_tokens
                total_output_tokens = result.usage.completion_tokens

            # Execute tool calls (file creation)
            for tool_call in result.tool_calls:
                if tool_call.name == "create_file":
                    args = tool_call.arguments
                    path = output_dir / args["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(args["content"])
                    files_created.append(args["path"])
                    if on_file_created:
                        on_file_created(args["path"])

        except Exception as e:
            logger.warning(f"Single-shot execution error: {e}")
            raise EvaluationError(f"Single-shot execution failed: {e}") from e

        elapsed = time.monotonic() - start_time

        return SingleShotResult(
            files=tuple(files_created),
            output_dir=output_dir,
            time_seconds=elapsed,
            turns=1,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )


# =============================================================================
# SUNWELL FULL-STACK EXECUTOR
# =============================================================================


class SunwellFullStackExecutor:
    """Execute using full Sunwell cognitive architecture via Naaru.

    DOGFOODING: Routes through Naaru.process() — the unified entry point.
    This ensures we use:
    - Convergence (shared working memory)
    - Resonance (feedback refinement)
    - Lens (specialized knowledge)
    - All routing/sharding infrastructure

    The difference from single-shot:
    - Lens provides specialized domain knowledge
    - Judge evaluates quality and identifies issues
    - Resonance refines based on feedback
    - Multiple turns of iteration
    """

    def __init__(
        self,
        model: ModelProtocol,
        lens_name: str | None = None,
    ) -> None:
        """Initialize executor.

        Args:
            model: A model implementing the ModelProtocol.
            lens_name: Optional lens to use (auto-detected if not specified).
        """
        self.model = model
        self.lens_name = lens_name

    async def run(
        self,
        task: FullStackTask,
        output_dir: Path,
        *,
        on_file_created: Callable[[str], None] | None = None,
        on_judge: Callable[[float, list[str]], None] | None = None,
        on_resonance: Callable[[int], None] | None = None,
    ) -> SunwellResult:
        """Run full Sunwell stack.

        Uses the cognitive architecture with:
        - Lens-enhanced prompting
        - Judge evaluation
        - Resonance refinement

        Args:
            task: The evaluation task to run.
            output_dir: Directory to write generated files.
            on_file_created: Callback when a file is created.
            on_judge: Callback when judge evaluates (score, issues).
            on_resonance: Callback when resonance iterates (iteration number).

        Returns:
            SunwellResult with full tracking.
        """
        from sunwell.benchmark.demo.judge import DemoJudge
        from sunwell.interface.surface.lens_detection import get_lens_for_project

        start_time = time.monotonic()
        files_created: list[str] = []
        judge_scores: list[float] = []
        total_input_tokens = 0
        total_output_tokens = 0
        resonance_count = 0

        # Auto-detect lens if not specified
        lens = self.lens_name or get_lens_for_project(output_dir)

        # Load lens heuristics
        lens_heuristics = self._load_lens_heuristics(lens)

        tools = _get_tools_for_task(task)

        # Build lens-enhanced prompt
        prompt = self._build_lens_enhanced_prompt(task, lens_heuristics, tools)

        # Initialize judge (Resonance is used via re-prompting with feedback)
        judge = DemoJudge(self.model)

        # Phase 1: Initial generation
        try:
            result = await self.model.generate(
                prompt,
                tools=tools,
                tool_choice="auto",
                options=GenerateOptions(
                    temperature=0.3,  # Lower for more consistent output
                    max_tokens=4096,
                ),
            )

            if result.usage:
                total_input_tokens += result.usage.prompt_tokens
                total_output_tokens += result.usage.completion_tokens

            # Execute tool calls
            for tool_call in result.tool_calls:
                if tool_call.name == "create_file":
                    args = tool_call.arguments
                    path = output_dir / args["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(args["content"])
                    files_created.append(args["path"])
                    if on_file_created:
                        on_file_created(args["path"])

        except Exception as e:
            logger.warning(f"Sunwell initial generation error: {e}")
            raise EvaluationError(f"Sunwell execution failed: {e}") from e

        # Phase 2: Judge evaluation
        # Read all created files for judge
        all_code = self._read_all_files(output_dir, files_created)
        expected_features = (
            frozenset(task.expected_features)
            if task.expected_features
            else frozenset(["working_code"])
        )

        judgment = await judge.evaluate(all_code, expected_features)
        judge_scores.append(judgment.score)

        if on_judge:
            on_judge(judgment.score, list(judgment.feedback))

        # Phase 3: Resonance refinement (if needed)
        if judgment.score < 8.0 and judgment.feedback:
            resonance_count += 1
            if on_resonance:
                on_resonance(resonance_count)

            # Build feedback for resonance
            feedback_parts = list(judgment.feedback)
            if judgment.features_missing:
                feedback_parts.append(f"Missing features: {', '.join(judgment.features_missing)}")

            # Attempt refinement via re-generation with feedback
            refinement_prompt = self._build_refinement_prompt(
                task, feedback_parts, files_created, tools
            )

            try:
                refine_result = await self.model.generate(
                    refinement_prompt,
                    tools=tools,
                    tool_choice="auto",
                    options=GenerateOptions(
                        temperature=0.4,
                        max_tokens=4096,
                    ),
                )

                if refine_result.usage:
                    total_input_tokens += refine_result.usage.prompt_tokens
                    total_output_tokens += refine_result.usage.completion_tokens

                # Execute refined tool calls (updates existing files)
                for tool_call in refine_result.tool_calls:
                    if tool_call.name == "create_file":
                        args = tool_call.arguments
                        path = output_dir / args["path"]
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(args["content"])
                        if args["path"] not in files_created:
                            files_created.append(args["path"])
                            if on_file_created:
                                on_file_created(args["path"])

                # Re-evaluate
                all_code = self._read_all_files(output_dir, files_created)
                judgment = await judge.evaluate(all_code, expected_features)
                judge_scores.append(judgment.score)

                if on_judge:
                    on_judge(judgment.score, list(judgment.feedback))

            except Exception as e:
                logger.warning(f"Resonance refinement error: {e}")

        elapsed = time.monotonic() - start_time

        return SunwellResult(
            files=tuple(files_created),
            output_dir=output_dir,
            time_seconds=elapsed,
            turns=len(judge_scores),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            lens_used=lens,
            judge_scores=tuple(judge_scores),
            resonance_iterations=resonance_count,
        )

    def _load_lens_heuristics(self, lens_name: str) -> list[str]:
        """Load heuristics from a lens file."""
        try:
            import yaml

            lens_paths = [
                Path("lenses") / lens_name,
                Path.home() / ".sunwell" / "lenses" / lens_name,
                Path(__file__).parent.parent.parent.parent / "lenses" / lens_name,
            ]

            for path in lens_paths:
                if path.exists():
                    lens_data = safe_yaml_load(path)
                    heuristics = lens_data.get("lens", {}).get("heuristics", [])
                    # Extract high-priority heuristics
                    sorted_h = sorted(
                        heuristics, key=lambda h: h.get("priority", 0), reverse=True
                    )
                    return [h.get("name", "") for h in sorted_h[:5]]
            return []
        except Exception:
            return []

    def _build_lens_enhanced_prompt(
        self,
        task: FullStackTask,
        heuristics: list[str],
        tools: tuple[Tool, ...],
    ) -> str:
        """Build a prompt enhanced with lens heuristics."""
        requirements = [
            "Include type hints for all parameters and return values",
            "Write docstrings for public functions and classes",
            "Handle edge cases and errors appropriately",
            "Follow Python best practices",
            "Create a well-organized file structure",
        ]

        if heuristics:
            requirements.extend(heuristics)

        return f"""You are an expert Python developer building a production-quality project.

Task: {task.prompt}

Requirements:
{chr(10).join(f'- {r}' for r in requirements)}

You have access to these tools:
{_format_tools_description(tools)}

Create a complete, working implementation with proper structure.
Use the create_file tool to create each file you need.
Be thorough - include all necessary files for the application to work.
"""

    def _build_refinement_prompt(
        self,
        task: FullStackTask,
        feedback: list[str],
        existing_files: list[str],
        tools: tuple[Tool, ...],
    ) -> str:
        """Build a prompt for refinement based on feedback."""
        return f"""You previously generated code for this task, but there are issues to fix.

Original Task: {task.prompt}

Existing files created: {', '.join(existing_files)}

Issues found:
{chr(10).join(f'- {f}' for f in feedback)}

You have access to these tools:
{_format_tools_description(tools)}

Please fix these issues by updating or creating files as needed.
Use the create_file tool to update files with fixes.
"""

    def _read_all_files(self, output_dir: Path, files: list[str]) -> str:
        """Read all created files into a single string for evaluation."""
        parts = []
        for file_path in files:
            full_path = output_dir / file_path
            if full_path.exists() and full_path.suffix == ".py":
                try:
                    content = full_path.read_text()
                    parts.append(f"# File: {file_path}\n{content}")
                except Exception:
                    pass
        return "\n\n".join(parts)
