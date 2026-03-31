#!/usr/bin/env python
"""Direct test of background agent execution (bypassing web UI)."""

import time
from pathlib import Path

def test_agent_execution():
    """Test spawning a background agent task."""
    from sunwell.agent.background.manager import BackgroundManager
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.helpers.models import create_model
    from sunwell.knowledge import ProjectRegistry
    from sunwell.memory.facade.persistent import PersistentMemory
    from sunwell.tools.execution import ToolExecutor
    from sunwell.interface.chirp.helpers.background import spawn_background_session

    print("🧪 Testing Direct Agent Execution\n")

    # Get sunwell project
    workspace = Path('/Users/llane/Documents/github/python/sunwell')
    print(f"📁 Workspace: {workspace}")

    registry = ProjectRegistry()
    project = registry.get('sunwell')
    if not project:
        print("❌ Project not found")
        return

    print(f"✅ Project loaded: {project.name}")

    # Get config and create model
    cfg = get_config()
    provider = "ollama"
    model_name = "gemma3:4b"  # Using available model

    print(f"🤖 Creating model: {provider}/{model_name}")
    model = create_model(provider, model_name)
    print("✅ Model created")

    # Create tool executor
    print("🔧 Creating tool executor...")
    tool_executor = ToolExecutor(project=project)
    print("✅ Tool executor created")

    # Load memory
    print("🧠 Loading memory...")
    try:
        memory = PersistentMemory.load(workspace)
        print("✅ Memory loaded")
    except Exception as e:
        print(f"⚠️  Creating new memory: {e}")
        memory = PersistentMemory.empty(workspace)

    # Create background manager
    print("📊 Creating background manager...")
    manager = BackgroundManager(workspace=workspace)
    print("✅ Manager created")

    # Spawn session using helper
    print("\n🚀 Spawning background session...")
    goal = "Add a docstring to the spawn_background_session function explaining what it does"

    try:
        session = spawn_background_session(
            manager=manager,
            goal=goal,
            model=model,
            tool_executor=tool_executor,
            memory=memory,
        )

        print(f"✅ Session spawned: {session.session_id}")
        print(f"   Status: {session.status.value}")
        print(f"   Goal: {goal}")

        # Wait and check status
        print("\n⏳ Waiting 15 seconds for agent to work...")
        time.sleep(15)

        # Check status
        updated_session = manager.get_session(session.session_id)
        if updated_session:
            print(f"\n📊 Session Status after 15s:")
            print(f"   ID: {updated_session.session_id}")
            print(f"   Status: {updated_session.status.value}")

            if updated_session.status.value == 'running':
                print(f"   ✨ Agent is still working...")
            elif updated_session.status.value == 'completed':
                print(f"   ✅ Completed!")
                print(f"   Tasks: {updated_session.tasks_completed}")
                print(f"   Files changed: {len(updated_session.files_changed)}")
                if updated_session.files_changed:
                    print(f"   Changed files: {updated_session.files_changed}")
            elif updated_session.status.value == 'failed':
                print(f"   ❌ Failed!")
                print(f"   Error: {updated_session.error}")

    except Exception as e:
        print(f"❌ Error spawning session: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agent_execution()
