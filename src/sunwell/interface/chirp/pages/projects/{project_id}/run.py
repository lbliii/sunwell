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
    from sunwell.skills import create_default_skill_executor
    from sunwell.tools.execution import ToolExecutor
    from sunwell.tools.providers.web_search import (
        WebSearchHandler,
        create_web_search_provider,
    )

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

        # Load memory
        memory = None
        try:
            memory = PersistentMemory.load(project.root)
        except Exception:
            memory = PersistentMemory.empty(project.root)

        # Create skill executor (research skill) when web search is available
        skill_executor = None
        web_handler = None
        try:
            web_provider = create_web_search_provider("auto")
            web_handler = WebSearchHandler(provider=web_provider)
            skill_executor = create_default_skill_executor(
                project.root, web_search_handler=web_handler, memory=memory
            )
        except (ValueError, Exception):
            pass

        # Create tool executor with optional skill executor and web search
        tool_executor = ToolExecutor(
            project=project,
            web_search_handler=web_handler,
            skill_executor=skill_executor,
        )

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
            message=f"✅ Agent execution started for {project.name}!",
            session_id=session.session_id,
        )

    except Exception as e:
        return Response(
            f"Failed to start agent execution: {str(e)}",
            status=500,
        )
