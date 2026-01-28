"""Chat loop wrapper for CLI command integration."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.simulacrum.context.assembler import ContextAssembler
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.models import ModelProtocol


async def chat_loop(
    dag: ConversationDAG,
    store: SimulacrumStore,
    assembler: ContextAssembler,
    initial_model: ModelProtocol,
    initial_model_name: str,
    system_prompt: str,
    tools_enabled: bool,
    trust_level: str,
    smart: bool,
    lens: Lens | None,
    mirror_enabled: bool,
    model_routing_enabled: bool,
    memory_path: Path,
    naaru_enabled: bool,
    identity_enabled: bool,
) -> None:
    """Run the chat loop with the provided configuration.

    This is a wrapper around run_unified_loop that adapts the parameters
    from the CLI command to the unified loop interface.
    """
    from sunwell.interface.cli.chat.unified_loop import run_unified_loop

    # Resolve workspace from dag or memory_path
    workspace = dag.workspace if hasattr(dag, "workspace") else memory_path.parent

    # Run the unified loop
    await run_unified_loop(
        model=initial_model,
        workspace=workspace,
        trust_level=trust_level,
        auto_confirm=False,
        stream_progress=True,
        dag=dag,
        store=store,
        memory_path=memory_path,
        lens=lens,
        tools_enabled=tools_enabled,
    )
