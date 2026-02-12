"""Start agent execution for a goal."""

from pathlib import Path

from chirp import Fragment, Response
from sunwell.interface.chirp.services import BacklogService


def post(goal_id: str, backlog_svc: BacklogService) -> Fragment | Response:
    """Start an agent execution for this goal.

    Args:
        goal_id: Goal ID to run agent for

    Returns:
        Success fragment or error response
    """
    from sunwell.agent.background.manager import BackgroundManager
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.helpers.models import create_model
    from sunwell.knowledge import ProjectRegistry
    from sunwell.memory.facade.persistent import PersistentMemory
    from sunwell.tools.execution import ToolExecutor

    # Get all goals and find the matching one
    goals = backlog_svc.list_goals()
    goal = None
    for g in goals:
        if g["id"] == goal_id:
            goal = g
            break

    if not goal:
        return Response(
            f"Goal not found: {goal_id}",
            status=404,
        )

    try:
        # Get current project from registry
        registry = ProjectRegistry()
        project = None

        # Try to get default project
        if registry.default_project_id:
            project = registry.get(registry.default_project_id)

        # If no default, use current directory
        if not project:
            cwd = Path.cwd()
            project_list = registry.list_projects()
            # Try to find project matching cwd
            for p in project_list:
                if p.root == cwd:
                    project = p
                    break

        if not project:
            return Response(
                "No project found. Please set a default project or run from a project directory.",
                status=400,
            )

        # Get config for model settings
        cfg = get_config()

        # Prefer Ollama for local execution (since it's always available)
        # Use naaru.wisdom model if configured, otherwise fallback to llama3.1:8b
        provider = "ollama"
        model_name = "llama3.1:8b"

        if hasattr(cfg, "naaru") and cfg.naaru.wisdom:
            model_name = cfg.naaru.wisdom

        model = create_model(provider, model_name)

        # Create tool executor
        tool_executor = ToolExecutor(project=project)

        # Load memory
        memory = None
        try:
            memory = PersistentMemory.load(project.root)
        except Exception:
            # If memory doesn't exist or fails to load, create empty
            memory = PersistentMemory.empty(project.root)

        # Create background manager
        manager = BackgroundManager(workspace=project.root)

        # Use goal description as the agent's goal
        goal_text = goal.get("description", f"Work on goal {goal_id}")

        # Spawn background session using helper
        from sunwell.interface.chirp.helpers.background import spawn_background_session

        session = spawn_background_session(
            manager=manager,
            goal=goal_text,
            model=model,
            tool_executor=tool_executor,
            memory=memory,
        )

        return Fragment(
            "backlog/goals/{goal_id}/_status.html",
            "action_status",
            message=f"Agent execution started for goal! Session ID: {session.session_id}",
        )

    except Exception as e:
        return Response(
            f"Failed to start agent execution: {str(e)}",
            status=500,
        )
