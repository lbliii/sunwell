"""Start agent execution in a project."""

from chirp import Fragment, Response


def post(project_id: str, goal: str = "") -> Fragment | Response:
    """Start an agent execution in this project.

    Args:
        project_id: Project ID to run agent in
        goal: Optional goal description from form

    Returns:
        Success fragment or error response
    """
    from sunwell.agent.background.manager import BackgroundManager
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.helpers.models import create_model
    from sunwell.knowledge import ProjectRegistry
    from sunwell.memory.facade.persistent import PersistentMemory
    from sunwell.tools.execution import ToolExecutor

    registry = ProjectRegistry()
    project = registry.get(project_id)

    if not project:
        return Response(
            f"Project not found: {project_id}",
            status=404,
        )

    if not project.root.exists():
        return Response(
            "Project path no longer exists",
            status=400,
        )

    # Use provided goal or default
    if not goal:
        goal = f"Analyze and improve code in {project.name}"

    try:
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

        # Spawn background session using helper
        from sunwell.interface.chirp.helpers.background import spawn_background_session

        session = spawn_background_session(
            manager=manager,
            goal=goal,
            model=model,
            tool_executor=tool_executor,
            memory=memory,
        )

        return Fragment(
            "projects/{project_id}/_action_status.html",
            "action_status",
            success=True,
            message=f"Agent execution started for {project.name}! Session ID: {session.session_id}",
        )

    except Exception as e:
        return Response(
            f"Failed to start agent execution: {str(e)}",
            status=500,
        )
