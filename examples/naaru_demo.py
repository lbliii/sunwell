#!/usr/bin/env python3
"""Demo of Naaru Architecture (RFC-019) for Local Model Intelligence.

The Naaru is Sunwell's coordinated intelligence architecture that maximizes
quality and throughput from small local models.

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │  ← Coordinates everything
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared working memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │  ← Parallel helpers
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

Components:
- **Naaru**: The coordinator (illuminate goals)
- **Harmonic Synthesis**: Multi-persona generation with voting
- **Convergence**: Shared working memory (7±2 slots)
- **Shards**: Parallel CPU helpers while GPU generates
- **Resonance**: Feedback loop for rejected proposals
- **Tiered Validation**: FunctionGemma → Full LLM cascade

Usage:
    python examples/naaru_demo.py                    # Basic mode (no LLM)
    python examples/naaru_demo.py --llm             # Full LLM mode
    python examples/naaru_demo.py --synth gemma3:1b --judge gemma3:4b
    
    # Enable specific features:
    python examples/naaru_demo.py --synth gemma3:1b --harmonic     # Multi-persona
    python examples/naaru_demo.py --synth gemma3:1b --tiered       # FunctionGemma
    python examples/naaru_demo.py --synth gemma3:1b --resonance 3  # Feedback loop
"""

import argparse
import asyncio
from pathlib import Path


async def main():
    """Run the Naaru demo."""
    parser = argparse.ArgumentParser(description="Naaru Architecture Demo (RFC-019)")
    parser.add_argument("--llm", action="store_true",
                       help="Enable LLM for both synthesis AND judging (same model)")
    parser.add_argument("--model", default="gemma3:1b",
                       help="Ollama model for --llm mode (default: gemma3:1b)")
    parser.add_argument("--synth", default=None,
                       help="Synthesis model (enables LLM synthesis)")
    parser.add_argument("--judge", default=None,
                       help="Judge model (enables LLM judging)")
    parser.add_argument("--threshold", type=float, default=6.0,
                       help="Quality threshold to approve (0-10, default: 6.0)")
    parser.add_argument("--temp", type=float, default=0.3,
                       help="Synthesis temperature (default: 0.3)")
    parser.add_argument("--time", type=int, default=120,
                       help="Illumination time in seconds (default: 120)")
    parser.add_argument("--harmonic", action="store_true",
                       help="Enable Harmonic Synthesis (multi-persona generation)")
    parser.add_argument("--tiered", action="store_true",
                       help="Enable Tiered Validation (FunctionGemma first)")
    parser.add_argument("--resonance", type=int, default=2,
                       help="Resonance max attempts (feedback loop, default: 2)")
    parser.add_argument("--convergence", type=int, default=7,
                       help="Convergence capacity (working memory slots, default: 7)")
    args = parser.parse_args()
    
    sunwell_root = Path(__file__).parent.parent
    
    # Import Naaru components
    from sunwell.naaru import Naaru, NaaruConfig, Convergence, ShardPool
    
    # Create models based on flags
    synthesis_model = None
    judge_model = None
    synth_name = None
    judge_name = None
    
    from sunwell.models.ollama import OllamaModel
    
    if args.llm:
        synthesis_model = OllamaModel(model=args.model)
        judge_model = synthesis_model
        synth_name = args.model
        judge_name = args.model
    
    if args.synth:
        synthesis_model = OllamaModel(model=args.synth)
        synth_name = args.synth
    
    if args.judge:
        judge_model = OllamaModel(model=args.judge)
        judge_name = args.judge
    
    # Print header
    print()
    print("╔" + "═" * 70 + "╗")
    print("║" + " ✨ NAARU ARCHITECTURE DEMO (RFC-019)".ljust(70) + "║")
    print("║" + " Coordinated Intelligence for Local Models".ljust(70) + "║")
    print("╠" + "═" * 70 + "╣")
    print("║" + "".ljust(70) + "║")
    print("║" + "              ┌─────────────────┐".ljust(70) + "║")
    print("║" + "              │      NAARU      │  The Light".ljust(70) + "║")
    print("║" + "              └────────┬────────┘".ljust(70) + "║")
    print("║" + "                       │".ljust(70) + "║")
    print("║" + "        ╔══════════════╧══════════════╗".ljust(70) + "║")
    conv_label = f"CONVERGENCE ({args.convergence} slots)"
    print("║" + f"        ║    {conv_label.ljust(22)}║".ljust(70) + "║")
    print("║" + "        ╚══════════════╤══════════════╝".ljust(70) + "║")
    print("║" + "                       │".ljust(70) + "║")
    print("║" + "     ┌─────────────────┼─────────────────┐".ljust(70) + "║")
    print("║" + "     ▼                 ▼                 ▼".ljust(70) + "║")
    print("║" + " ┌────────┐       ┌────────┐       ┌────────┐".ljust(70) + "║")
    print("║" + " │ SHARD  │       │ SHARD  │       │ SHARD  │".ljust(70) + "║")
    print("║" + " │ Memory │       │Context │       │ Verify │".ljust(70) + "║")
    print("║" + " └────────┘       └────────┘       └────────┘".ljust(70) + "║")
    print("║" + "".ljust(70) + "║")
    print("╚" + "═" * 70 + "╝")
    print()
    
    # Print config
    print("📋 Configuration:")
    if synth_name:
        mode_status = " [🎵 HARMONIC]" if args.harmonic else ""
        print(f"   Synthesis: {synth_name} (temp={args.temp}){mode_status}")
    if judge_name:
        tiered_status = " [⚡ TIERED]" if args.tiered else ""
        print(f"   Judge: {judge_name} (threshold={args.threshold}){tiered_status}")
    print(f"   Resonance: max {args.resonance} refinement attempts")
    print(f"   Convergence: {args.convergence} slots (Miller's Law)")
    print()
    
    # Create Convergence (working memory) and ShardPool
    convergence = Convergence(capacity=args.convergence)
    shard_pool = ShardPool(convergence=convergence)
    
    # Create Naaru configuration
    # Note: NaaruConfig uses thematic field names (see RFC-019)
    config = NaaruConfig(
        harmonic_synthesis=args.harmonic,
        convergence=args.convergence,
        resonance=args.resonance,
        discernment=args.tiered,
        voice_temperature=args.temp,
        purity_threshold=args.threshold,
    )
    
    # Create the Naaru
    naaru = Naaru(
        sunwell_root=sunwell_root,
        synthesis_model=synthesis_model,
        judge_model=judge_model,
        config=config,
        convergence=convergence,
        shard_pool=shard_pool,
    )
    
    # Illuminate!
    results = await naaru.illuminate(
        goals=["improve error handling", "add documentation"],
        max_time_seconds=args.time,
    )
    
    # Show detailed stats
    print("\n🔬 Detailed Worker Stats:")
    for worker_name, stats in results["worker_stats"].items():
        print(f"   {worker_name}:")
        for key, value in stats.items():
            print(f"      {key}: {value}")
    
    print("\n📡 Message Bus Traffic:")
    for msg_type, count in results["bus_stats"]["by_type"].items():
        print(f"   {msg_type}: {count} messages")
    
    print("\n📊 Convergence Stats:")
    conv_stats = convergence.get_stats()
    for key, value in conv_stats.items():
        print(f"   {key}: {value}")


async def demo_components():
    """Demo individual Naaru components."""
    from sunwell.naaru import (
        Convergence, Slot, SlotSource,
        Shard, ShardPool, ShardType,
        Resonance, ResonanceConfig,
    )
    
    print("\n" + "=" * 60)
    print("🧩 Component Demo")
    print("=" * 60)
    
    # 1. Convergence Demo
    print("\n📦 Convergence (Working Memory):")
    convergence = Convergence(capacity=7)
    
    await convergence.add(Slot(
        id="memories:testing",
        content=["Use pytest fixtures", "Test edge cases"],
        relevance=0.9,
        source=SlotSource.MEMORY_FETCHER,
    ))
    
    slot = await convergence.get("memories:testing")
    print(f"   Added slot: {slot.id}")
    print(f"   Content: {slot.content}")
    print(f"   Stats: {convergence.get_stats()}")
    
    # 2. Shards Demo
    print("\n⚡ Shards (Parallel Helpers):")
    pool = ShardPool(convergence=convergence)
    
    task = {"description": "Add error handling", "category": "error_handling"}
    result = await pool.prepare_for_task(task)
    print(f"   Prepared for task: {task['category']}")
    print(f"   Slots ready: {result['slots_ready']}")
    
    # 3. Quick validation demo
    print("\n✓ Quick Validation:")
    code = '''
def example(x: int) -> int:
    """Example function."""
    return x * 2
'''
    check = await pool.quick_validate({"diff": code})
    print(f"   Quick score: {check['quick_score']}/10")
    print(f"   Checks: {sum(1 for v in check['checks'].values() if v)}/{len(check['checks'])} passed")
    
    print("\n✅ Component demo complete!")


if __name__ == "__main__":
    import sys
    
    if "--components" in sys.argv:
        asyncio.run(demo_components())
    else:
        asyncio.run(main())
