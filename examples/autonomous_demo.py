#!/usr/bin/env python3
"""Demo of RFC-016 Autonomous Mode - Self-Directed Evolution.

This demo shows Sunwell running autonomously, discovering opportunities
for self-improvement and working on them until interrupted.

Usage:
    python examples/autonomous_demo.py
    
    Press Ctrl+C to gracefully stop at any time.
"""

import asyncio
from pathlib import Path

from sunwell.naaru import (
    AutonomousRunner,
    SessionConfig,
)


async def main():
    """Run autonomous mode demo."""
    # Find sunwell root
    sunwell_root = Path(__file__).parent.parent
    
    # Configure session
    config = SessionConfig(
        goals=["improve error handling", "add documentation"],
        max_hours=0.1,  # 6 minutes max for demo
        max_proposals=10,
        max_auto_apply=3,
        auto_apply_enabled=True,
        checkpoint_interval_minutes=1,
        min_seconds_between_changes=2,  # Fast for demo
        verbose=True,
    )
    
    # Create and run
    runner = AutonomousRunner(
        config=config,
        sunwell_root=sunwell_root,
    )
    
    print("\n🚀 Starting Autonomous Mode Demo")
    print("   Press Ctrl+C to stop gracefully\n")
    
    final_state = await runner.start()
    
    print(f"\n✅ Demo complete! Final status: {final_state.status.value}")
    print(f"   Session saved to: .sunwell/autonomous/{final_state.session_id}.json")


if __name__ == "__main__":
    asyncio.run(main())
