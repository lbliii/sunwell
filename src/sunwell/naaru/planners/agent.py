"""Agent planner for RFC-032 Agent Mode, RFC-034 Contract-Aware Planning.

This planner decomposes arbitrary user goals into executable tasks
using LLM-based planning. RFC-034 adds contract-aware decomposition
for parallel execution.

RFC-035 adds schema-aware planning for domain-agnostic projects.
"""


import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.naaru.planners.protocol import PlanningError, PlanningStrategy
from sunwell.naaru.types import Task, TaskMode, TaskStatus

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol, Tool
    from sunwell.project.schema import ProjectSchema


@dataclass
class AgentPlanner:
    """Plans arbitrary user tasks using LLM decomposition (RFC-032, RFC-034).

    Takes a high-level goal and breaks it into executable steps,
    identifying tools needed and dependencies between steps.

    RFC-034 adds contract-aware planning:
    - Identifies interface definitions that can parallelize
    - Groups tasks into phases (contracts → implementations → integration)
    - Tracks resource conflicts for safe parallel execution

    Example:
        >>> planner = AgentPlanner(
        ...     model=my_model,
        ...     available_tools=frozenset(["write_file", "run_command"]),
        ...     strategy=PlanningStrategy.CONTRACT_FIRST,
        ... )
        >>> tasks = await planner.plan(["Build a React forum app"])
        >>> for task in tasks:
        ...     print(f"{task.id}: {task.description} ({task.mode})")
    """

    model: ModelProtocol
    available_tools: frozenset[str] = field(default_factory=frozenset)
    tool_definitions: tuple[Tool, ...] = ()  # Full Tool objects with schemas
    max_subtasks: int = 20
    max_planning_attempts: int = 3
    strategy: PlanningStrategy = PlanningStrategy.CONTRACT_FIRST  # RFC-034 default

    # RFC-035: Schema-aware planning
    project_schema: ProjectSchema | None = None
    """Project schema for domain-agnostic planning.

    When set, the planner injects artifact type and phase information
    into the planning prompt, enabling domain-specific task decomposition.
    """

    _goals: list[str] = field(default_factory=list, init=False)

    @property
    def mode(self) -> TaskMode:
        """This planner produces composite tasks."""
        return TaskMode.COMPOSITE

    async def plan(
        self,
        goals: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Decompose user goals into executable tasks.

        Args:
            goals: User-specified goals
            context: Optional context (cwd, files, etc.)

        Returns:
            List of Tasks with dependencies

        Raises:
            PlanningError: If planning fails after retries
        """
        self._goals = goals
        prompt = self._build_planning_prompt(goals, context)

        for attempt in range(self.max_planning_attempts):
            try:
                from sunwell.models.protocol import GenerateOptions

                result = await self.model.generate(
                    prompt,
                    options=GenerateOptions(temperature=0.2, max_tokens=2000),
                )

                tasks = self._parse_tasks(result.content or "")

                if tasks:
                    return tasks

            except (json.JSONDecodeError, PlanningError) as e:
                if attempt < self.max_planning_attempts - 1:
                    # Retry with error context
                    prompt = self._add_error_context(prompt, str(e))
                    continue
                raise PlanningError(f"Planning failed after {attempt + 1} attempts: {e}") from e

        # Final fallback: single task from goal with inferred target_path
        goal = goals[0] if goals else "Execute user goal"
        target_path = self._infer_target_path(goal)

        return [
            Task(
                id="fallback",
                description=goal,
                mode=TaskMode.GENERATE,
                tools=frozenset(["write_file"]) if "write_file" in self.available_tools else frozenset(),
                target_path=target_path,
                details={"fallback": True},
            )
        ]

    def _build_planning_prompt(
        self,
        goals: list[str],
        context: dict[str, Any] | None,
    ) -> str:
        """Build the planning prompt for the LLM.

        RFC-034: Prompt varies based on planning strategy.
        RFC-035: Adds schema context when available.
        """
        context_str = self._format_context(context)
        goal = goals[0] if goals else "No goal specified"

        # Build detailed tool documentation from Tool definitions
        tools_docs = self._format_tool_documentation()

        # Build example based on available tools and strategy
        example_tasks = self._build_example_tasks()

        # RFC-034: Strategy-specific prompt sections
        if self.strategy == PlanningStrategy.CONTRACT_FIRST:
            prompt = self._build_contract_first_prompt(goal, context_str, tools_docs, example_tasks)
        elif self.strategy == PlanningStrategy.RESOURCE_AWARE:
            prompt = self._build_resource_aware_prompt(goal, context_str, tools_docs, example_tasks)
        else:
            prompt = self._build_sequential_prompt(goal, context_str, tools_docs, example_tasks)

        # RFC-035: Inject schema context if available
        if self.project_schema:
            schema_context = self._schema_context(self.project_schema)
            prompt = prompt.replace(
                "CONTEXT:",
                f"CONTEXT:\n{schema_context}\n",
            )

        return prompt

    def _build_sequential_prompt(
        self,
        goal: str,
        context_str: str,
        tools_docs: str,
        example_tasks: str,
    ) -> str:
        """Build the original RFC-032 sequential planning prompt."""
        return f"""You are a task planner. Decompose this goal into concrete, executable steps.

GOAL: {goal}

CONTEXT:
{context_str}

AVAILABLE TOOLS (use ONLY these exact names):
{tools_docs}

⚠️ CRITICAL RULES:
1. Use ONLY tools from the list above. Do NOT invent tools.
2. If a tool isn't listed, you cannot use it (e.g., no run_command unless listed).

TASK MODES - Choose based on the action:
- "research" = READ existing files to understand them (use read_file, list_files, search_files)
- "generate" = CREATE new files that don't exist (use write_file)
- "modify"   = EDIT existing files (use edit_file - safer than write_file, preserves unchanged content)
- "execute"  = RUN shell commands (use run_command IF available)

⚠️ IMPORTANT: For modifying existing files, PREFER edit_file over write_file!
- edit_file replaces specific content while preserving the rest of the file
- write_file OVERWRITES the entire file (only use for creating NEW files)

WHEN TO USE RESEARCH:
- Before modifying existing code (read it first!)
- When you need to understand existing files
- When analyzing code to generate documentation
- When the goal mentions "analyze", "review", or "understand"

Output a JSON array of tasks:
- id: unique identifier
- description: what to do
- mode: one of "research", "generate", "modify", "execute"
- tools: array of tool names from AVAILABLE TOOLS
- depends_on: array of task IDs that must complete first (use [] if none)
- target_path: FULL file path with filename (e.g., "src/main.py", NOT "src/")
- verification: how to verify success

DEPENDENCY RULES:
- Research tasks should come BEFORE tasks that depend on that knowledge
- File modifications depend on reading the file first
- Tests depend on the code they test

Example with proper dependencies:
```json
{example_tasks}
```

Decompose into {self.max_subtasks} or fewer tasks. Output ONLY valid JSON:"""

    def _build_contract_first_prompt(
        self,
        goal: str,
        context_str: str,
        tools_docs: str,
        example_tasks: str,
    ) -> str:
        """Build the RFC-034 contract-first planning prompt."""
        return f"""You are a task planner with parallel execution awareness.

GOAL: {goal}

CONTEXT:
{context_str}

AVAILABLE TOOLS (use ONLY these exact names):
{tools_docs}

=== PLANNING STRATEGY: CONTRACT-FIRST ===

1. IDENTIFY CONTRACTS FIRST
   When building systems with multiple components, identify the INTERFACES first:
   - Protocols/ABCs that define behavior
   - Type definitions shared between components
   - API schemas that components must conform to

   Contracts can be defined IN PARALLEL because they don't modify shared state.

2. GROUP BY PHASE
   Organize tasks into phases where tasks within a phase can run concurrently:
   - Phase 1: Define contracts/interfaces (all parallel)
   - Phase 2: Implement against contracts (parallel if no file conflicts)
   - Phase 3: Integration/testing (may require sequential)

3. TRACK ARTIFACTS
   For each task, identify:
   - PRODUCES: What artifacts does this create? (types, files, modules)
   - REQUIRES: What artifacts must exist first?
   - MODIFIES: What files does this touch? (tasks with overlapping modifies cannot parallelize)

=== OUTPUT FORMAT ===

Output a JSON array of tasks. Each task has:
- id: unique identifier (e.g., "1a", "1b", "2a")
- description: what to do
- mode: "generate" | "modify" | "execute" | "research"
- tools: array of tools needed (from AVAILABLE TOOLS)
- depends_on: task IDs that must complete first
- target_path: FULL file path including filename (e.g., "app/models.py", NOT just "app/")

RFC-034 ADDITIONS:
- parallel_group: phase name (e.g., "contracts", "implementations", "tests")
- is_contract: true if this defines an interface, false for implementations
- produces: array of artifacts this creates (e.g., ["UserProtocol", "user_types.py"])
- requires: array of artifacts needed (e.g., ["UserProtocol"])
- modifies: array of files this task may write to
- contract: interface this implementation must satisfy (for implementations only)

=== EXAMPLE ===

Goal: "Build a REST API with user authentication"

```json
[
  {{
    "id": "1a",
    "description": "Define User protocol with required fields and methods",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": [],
    "target_path": "src/protocols/user.py",
    "parallel_group": "contracts",
    "is_contract": true,
    "produces": ["UserProtocol"],
    "requires": [],
    "modifies": ["src/protocols/user.py"]
  }},
  {{
    "id": "1b",
    "description": "Define Auth interface with authenticate/authorize methods",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": [],
    "target_path": "src/protocols/auth.py",
    "parallel_group": "contracts",
    "is_contract": true,
    "produces": ["AuthInterface"],
    "requires": [],
    "modifies": ["src/protocols/auth.py"]
  }},
  {{
    "id": "2a",
    "description": "Implement User model conforming to UserProtocol",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": ["1a"],
    "target_path": "src/models/user.py",
    "parallel_group": "implementations",
    "is_contract": false,
    "produces": ["UserModel"],
    "requires": ["UserProtocol"],
    "modifies": ["src/models/user.py"],
    "contract": "UserProtocol"
  }},
  {{
    "id": "2b",
    "description": "Implement Auth service using UserProtocol",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": ["1a", "1b"],
    "target_path": "src/services/auth.py",
    "parallel_group": "implementations",
    "is_contract": false,
    "produces": ["AuthService"],
    "requires": ["UserProtocol", "AuthInterface"],
    "modifies": ["src/services/auth.py"],
    "contract": "AuthInterface"
  }}
]
```

Note how:
- Tasks 1a and 1b are in "contracts" group → can run in parallel
- Tasks 2a and 2b are in "implementations" group → can run in parallel (different files)
- Task 2b depends on both 1a and 1b (needs both protocols)

Decompose into {self.max_subtasks} or fewer tasks. Output ONLY valid JSON:"""

    def _build_resource_aware_prompt(
        self,
        goal: str,
        context_str: str,
        tools_docs: str,
        example_tasks: str,
    ) -> str:
        """Build the RFC-034 resource-aware planning prompt."""
        return f"""You are a task planner optimizing for parallel execution.

GOAL: {goal}

CONTEXT:
{context_str}

AVAILABLE TOOLS (use ONLY these exact names):
{tools_docs}

=== PLANNING STRATEGY: RESOURCE-AWARE ===

Your goal is to MAXIMIZE PARALLELIZATION by minimizing file conflicts.

1. MINIMIZE FILE OVERLAP
   - Split tasks so each writes to different files when possible
   - Avoid tasks that modify the same file unless sequential

2. TRACK MODIFIES CAREFULLY
   - `modifies` array MUST list ALL files a task might write to
   - Two tasks with overlapping `modifies` cannot run in parallel

3. GROUP BY INDEPENDENCE
   - parallel_group should contain tasks that:
     a) Have no dependency relationship
     b) Have non-overlapping `modifies` sets

=== OUTPUT FORMAT ===

Output a JSON array of tasks with ALL RFC-034 fields:
- id, description, mode, tools, depends_on, target_path
- parallel_group: group name for concurrent execution
- produces: artifacts created
- requires: artifacts needed
- modifies: files written (CRITICAL for conflict detection)
- is_contract: whether this defines an interface
- contract: interface to conform to (if applicable)

=== PARALLELIZATION RULES ===

Tasks A and B can run in parallel if:
1. A doesn't depend on B, and B doesn't depend on A
2. A.requires doesn't include anything in B.produces (and vice versa)
3. A.modifies ∩ B.modifies = ∅ (no file overlap)

Decompose into {self.max_subtasks} or fewer tasks. Output ONLY valid JSON:"""

    def _format_tool_documentation(self) -> str:
        """Format tool documentation with descriptions for the LLM.

        Uses full Tool definitions when available, falls back to names only.
        """
        if self.tool_definitions:
            # Use full tool documentation with descriptions
            lines = []
            for tool in sorted(self.tool_definitions, key=lambda t: t.name):
                lines.append(f"- {tool.name}: {tool.description}")
            return "\n".join(lines)
        elif self.available_tools:
            # Fallback to just names (less reliable)
            return "\n".join(f"- {name}" for name in sorted(self.available_tools))
        else:
            return "none"

    def _build_example_tasks(self) -> str:
        """Build example tasks JSON based on available tools."""
        import json

        # Choose example based on available tools - always show research pattern
        if "run_command" in self.available_tools:
            # Full example with run_command
            examples = [
                {
                    "id": "1",
                    "description": "Create project directory",
                    "mode": "execute",
                    "tools": ["run_command"],
                    "depends_on": [],
                    "target_path": "myapp",
                    "verification": "directory exists",
                },
                {
                    "id": "2",
                    "description": "Create main module",
                    "mode": "generate",
                    "tools": ["write_file"],
                    "depends_on": ["1"],
                    "target_path": "myapp/main.py",
                    "verification": "file exists",
                },
            ]
        elif "write_file" in self.available_tools and "read_file" in self.available_tools:
            # Show research → generate pattern (most common case)
            examples = [
                {
                    "id": "1",
                    "description": "Read existing code to understand structure",
                    "mode": "research",
                    "tools": ["read_file", "list_files"],
                    "depends_on": [],
                    "target_path": "src/",
                    "verification": "understand file layout",
                },
                {
                    "id": "2",
                    "description": "Create main module based on research",
                    "mode": "generate",
                    "tools": ["write_file"],
                    "depends_on": ["1"],
                    "target_path": "src/main.py",
                    "verification": "file created",
                },
                {
                    "id": "3",
                    "description": "Create tests for main module",
                    "mode": "generate",
                    "tools": ["write_file"],
                    "depends_on": ["2"],
                    "target_path": "tests/test_main.py",
                    "verification": "tests exist",
                },
            ]
        elif "write_file" in self.available_tools:
            # Write-only example
            examples = [
                {
                    "id": "1",
                    "description": "Create config file",
                    "mode": "generate",
                    "tools": ["write_file"],
                    "depends_on": [],
                    "target_path": "config.json",
                    "verification": "file exists",
                },
                {
                    "id": "2",
                    "description": "Create main module using config",
                    "mode": "generate",
                    "tools": ["write_file"],
                    "depends_on": ["1"],
                    "target_path": "main.py",
                    "verification": "file imports config",
                },
            ]
        else:
            # Read-only example
            examples = [
                {
                    "id": "1",
                    "description": "List files in directory",
                    "mode": "research",
                    "tools": ["list_files"],
                    "depends_on": [],
                    "verification": "files listed",
                },
                {
                    "id": "2",
                    "description": "Read main module to understand it",
                    "mode": "research",
                    "tools": ["read_file"],
                    "depends_on": ["1"],
                    "target_path": "main.py",
                    "verification": "content understood",
                },
            ]

        return json.dumps(examples, indent=2)

    def _format_context(self, context: dict[str, Any] | None) -> str:
        """Format context for the planning prompt."""
        if not context:
            return "No additional context."

        lines = []

        # RFC-126: Include full workspace context if available
        if "workspace_context" in context:
            lines.append(context["workspace_context"])
        else:
            # Fallback to individual fields
            if "cwd" in context:
                lines.append(f"Current directory: {context['cwd']}")
            if "project_name" in context:
                lines.append(f"Project: {context['project_name']}")
            if "project_type" in context and context["project_type"] != "unknown":
                ptype = context["project_type"]
                framework = context.get("project_framework")
                lines.append(f"Type: {ptype}" + (f" ({framework})" if framework else ""))
            if "key_files" in context:
                files = context["key_files"][:10]
                lines.append(f"Key files: {', '.join(files)}")
            if "entry_points" in context:
                entries = context["entry_points"][:5]
                lines.append(f"Entry points: {', '.join(entries)}")

        if "files" in context:
            files = context["files"][:20]  # Limit
            lines.append(f"Existing files: {', '.join(str(f) for f in files)}")
        if "recent_commands" in context:
            cmds = context["recent_commands"][:5]
            lines.append(f"Recent commands: {', '.join(cmds)}")

        return "\n".join(lines) or "No additional context."

    def _schema_context(self, schema: ProjectSchema) -> str:
        """Generate schema-aware planning context (RFC-035).

        Injects artifact types and planning phases from the project schema
        into the planning prompt, enabling domain-specific decomposition.

        Args:
            schema: The project schema

        Returns:
            Context string for prompt injection
        """
        lines = [
            f"## Project Schema: {schema.name}",
            f"Type: {schema.project_type}",
            "",
            "### Artifact Types",
        ]

        for name, artifact_type in schema.artifact_types.items():
            lines.append(f"- **{name}**: {artifact_type.description}")

            if artifact_type.fields.required:
                required = ", ".join(artifact_type.fields.required)
                lines.append(f"  - Required fields: {required}")

            if artifact_type.produces_pattern:
                lines.append(f"  - Produces: {artifact_type.produces_pattern}")

            if artifact_type.requires_patterns:
                requires = ", ".join(artifact_type.requires_patterns)
                lines.append(f"  - Requires: {requires}")

            if artifact_type.is_contract:
                lines.append("  - (Contract type - can parallelize)")

        if schema.planning_config.phases:
            lines.extend(["", "### Planning Phases"])
            for phase in schema.planning_config.phases:
                parallel_status = "⚡ parallel" if phase.parallel else "→ sequential"
                lines.append(f"- **{phase.name}** ({parallel_status})")
                if phase.artifact_types:
                    types = ", ".join(phase.artifact_types)
                    lines.append(f"  - Artifact types: {types}")
                if phase.maps_to:
                    lines.append(f"  - Maps to parallel_group: {phase.maps_to}")

        lines.extend([
            "",
            "### Planning Guidelines (Schema-Aware)",
            "When decomposing tasks:",
            "1. Respect artifact dependency order (requires → produces)",
            "2. Assign parallel_group based on phase mappings",
            "3. Use is_contract=True for definition tasks, False for content tasks",
            "4. Map artifact types to their produces patterns",
        ])

        return "\n".join(lines)

    def _add_error_context(self, prompt: str, error: str) -> str:
        """Add error context for retry."""
        return f"""Previous attempt failed with: {error}

Please ensure your response is ONLY valid JSON with no extra text.

{prompt}"""

    def _infer_target_path(self, goal: str) -> str | None:
        """Infer a target path from the goal description.

        Looks for common patterns like:
        - "save it in the X folder" -> X/output.txt
        - "create X file" -> X
        - "build X app" -> X/
        """
        import re

        goal_lower = goal.lower()

        # Pattern: "in the X/ folder" or "in X/"
        folder_match = re.search(r"in (?:the )?(\w+/)?\s*folder", goal_lower)
        if folder_match and folder_match.group(1):
            folder = folder_match.group(1).rstrip("/")
            return f"{folder}/index.html" if "app" in goal_lower else f"{folder}/output.txt"

        # Pattern: "save in X" or "save to X"
        save_match = re.search(r"save (?:it )?(?:in|to) (?:the )?(\S+)", goal_lower)
        if save_match:
            path = save_match.group(1).rstrip("/")
            # If it looks like a directory (no extension), add a default file
            if "/" in path or "." not in path:
                return f"{path}/index.html" if "app" in goal_lower else f"{path}/output.txt"
            return path

        # Pattern: "create X.ext" or "build X.ext"
        file_match = re.search(r"(?:create|build|write|make) (?:a )?(\w+\.\w+)", goal_lower)
        if file_match:
            return file_match.group(1)

        # Pattern: "X app" -> X/
        app_match = re.search(r"(\w+)\s+app", goal_lower)
        if app_match:
            return f"{app_match.group(1)}/index.html"

        # Default: no path inferred
        return None

    def _parse_tasks(self, response: str) -> list[Task]:
        """Parse LLM response into Task objects with robust error handling.

        RFC-034: Also parses contract-aware fields (produces, requires, modifies, etc.)
        """
        tasks_data = self._extract_json(response)

        if not tasks_data:
            # Fallback: create single task from goal with inferred target_path
            goal = self._goals[0] if self._goals else "Execute user goal"
            target_path = self._infer_target_path(goal)

            return [
                Task(
                    id="1",
                    description=goal,
                    mode=TaskMode.GENERATE,
                    tools=frozenset(["write_file"]) if "write_file" in self.available_tools else frozenset(),
                    target_path=target_path,
                    details={"fallback": True, "raw_response": response[:500]},
                )
            ]

        tasks = []
        invalid_tools: list[str] = []

        for i, item in enumerate(tasks_data[: self.max_subtasks]):
            try:
                # Parse mode
                mode_str = item.get("mode", "generate")
                try:
                    mode = TaskMode(mode_str)
                except ValueError:
                    mode = TaskMode.GENERATE

                # Validate tools are available
                requested_tools = set(item.get("tools", []))
                invalid = requested_tools - self.available_tools
                if invalid:
                    invalid_tools.extend(
                        [f"Task {item.get('id', str(i + 1))}: {', '.join(invalid)}"]
                    )
                    # Continue anyway but log warning - will fail at execution

                # RFC-034: Parse contract-aware fields
                produces = frozenset(item.get("produces", []))
                requires = frozenset(item.get("requires", []))
                modifies = frozenset(item.get("modifies", []))

                # Auto-populate modifies from target_path if not specified
                target_path = item.get("target_path")
                if target_path and not modifies:
                    modifies = frozenset([target_path])

                task = Task(
                    id=str(item.get("id", str(i + 1))),
                    description=item.get("description", f"Task {i + 1}"),
                    mode=mode,
                    tools=frozenset(requested_tools),
                    target_path=target_path,
                    depends_on=tuple(str(d) for d in item.get("depends_on", [])),
                    # RFC-034: Contract-aware fields
                    produces=produces,
                    requires=requires,
                    modifies=modifies,
                    parallel_group=item.get("parallel_group"),
                    is_contract=item.get("is_contract", False),
                    contract=item.get("contract"),
                    # Existing fields
                    verification=item.get("verification"),
                    status=TaskStatus.PENDING,
                )
                tasks.append(task)
            except (KeyError, ValueError):
                # Skip malformed task
                continue

        if not tasks:
            raise PlanningError(f"Could not parse any valid tasks from response: {response[:200]}")

        # Warn about invalid tools but don't fail - let execution handle it
        if invalid_tools:
            import warnings

            warnings.warn(
                f"Tasks reference unavailable tools: {'; '.join(invalid_tools)}. "
                f"Available tools: {', '.join(sorted(self.available_tools))}",
                UserWarning, stacklevel=2,
            )

        return tasks

    def _extract_json(self, response: str) -> list[dict] | None:
        """Extract JSON array from LLM response using multiple strategies."""
        # Strategy 1: Find JSON array with regex
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Strategy 2: Try parsing entire response as JSON
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "tasks" in data:
                return data["tasks"]
        except json.JSONDecodeError:
            pass

        # Strategy 3: Look for code block with JSON
        code_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        return None
