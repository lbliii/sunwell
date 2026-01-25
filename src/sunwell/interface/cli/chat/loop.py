"""Chat loop wrapper for CLI command integration."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.context.assembler import ContextAssembler
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.models import ModelProtocol


async def chat_loop(
    dag: "ConversationDAG",
    store: "SimulacrumStore",
    assembler: "ContextAssembler",
    initial_model: "ModelProtocol",
    initial_model_name: str,
    system_prompt: str,
    tools_enabled: bool,
    trust_level: str,
    smart: bool,
    lens: "Lens | None",
    mirror_enabled: bool,
    model_routing_enabled: bool,
    memory_path: Path,
    naaru_enabled: bool,
    identity_enabled: bool,
) -> None:
    """Run the chat loop with the provided configuration.
    
    This is a wrapper around _run_unified_loop that adapts the parameters
    from the CLI command to the unified loop interface.
    """
    from sunwell.interface.cli.chat import _run_unified_loop
    from sunwell.tools.execution import ToolExecutor
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.knowledge.project import ProjectResolutionError, resolve_project
    
    # Resolve workspace from dag or memory_path
    workspace = dag.workspace if hasattr(dag, "workspace") else memory_path.parent
    
    # Set up tool executor if tools are enabled
    tool_executor = None
    if tools_enabled:
        from sunwell.knowledge.project import (
            ProjectResolutionError,
            create_project_from_workspace,
            resolve_project,
        )
        
        workspace_root = workspace
        try:
            project = resolve_project(cwd=workspace)
            workspace_root = project.root
        except ProjectResolutionError:
            project = create_project_from_workspace(workspace)
            workspace_root = project.root
        
        policy = ToolPolicy(trust_level=ToolTrust.from_string(trust_level))
        tool_executor = ToolExecutor(
            project=project,
            sandbox=None,
            policy=policy,
        )
    
    # Run the unified loop
    await _run_unified_loop(
        model=initial_model,
        workspace=workspace,
        trust_level=trust_level,
        auto_confirm=False,
        stream_progress=True,
        dag=dag,
        store=store,
        memory_path=memory_path,
        lens=lens,
    )
