#!/usr/bin/env python3
"""Demo of Parallel Autonomous Mode with 8 workers.

With Python 3.13+ free-threading, all 8 workers run in TRUE parallel!

Usage:
    python examples/parallel_autonomous_demo.py
"""

import asyncio
from pathlib import Path

from sunwell.naaru import (
    ParallelAutonomousRunner,
    SessionConfig,
)


async def main():
    """Run parallel autonomous mode demo."""
    sunwell_root = Path(__file__).parent.parent
    
    config = SessionConfig(
        goals=[
            "improve error handling",
            "add documentation", 
            "testing",
            "code quality",
        ],
        max_hours=0.5,
        max_proposals=100,
        auto_apply_enabled=False,  # Just create proposals for demo
        verbose=True,
    )
    
    # 8 parallel workers! 🚀
    runner = ParallelAutonomousRunner(
        config=config,
        sunwell_root=sunwell_root,
        num_workers=8,
    )
    
    print("\n🚀 PARALLEL AUTONOMOUS MODE DEMO")
    print("   8 workers running in TRUE PARALLEL!")
    print("   Press Ctrl+C to stop gracefully\n")
    
    final_state = await runner.start()
    
    print(f"\n✅ Complete! {final_state.proposals_created} proposals created")


if __name__ == "__main__":
    asyncio.run(main())
