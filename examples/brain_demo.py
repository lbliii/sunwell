#!/usr/bin/env python3
"""Demo of Brain-Inspired Architecture for Autonomous Mode.

Instead of a simple worker pool, this uses specialized brain regions
that communicate through a corpus callosum (message bus).

Architecture Philosophy:
- SYNTHESIS uses TIGHT prompts (System 1) - fast, intuitive generation
- VALIDATION uses DEEP prompts (System 2) - thorough, contextual judgment
- The judge has "more reign" with headspace memory context

Brain Regions:
- ANALYSIS: Reads code, finds patterns (like visual/parietal cortex)
- SYNTHESIS: LLM code generation (like frontal lobe) - tight prompts
- VALIDATION: LLM quality judge (like prefrontal cortex) - deep prompts
- MEMORY: Stores learnings (like hippocampus)
- EXECUTIVE: Coordinates everything (like anterior cingulate)

Usage:
    python examples/brain_demo.py                    # Basic mode (no LLM)
    python examples/brain_demo.py --llm             # Full LLM mode (same model)
    python examples/brain_demo.py --llm --model gemma3:4b
    
    # Mix different models for synthesis vs judge:
    python examples/brain_demo.py --synth gemma3:1b --judge-model gemma3:4b
    python examples/brain_demo.py --synth gemma3:4b --judge-model gemma3:1b
    
    # With headspace context for judge:
    python examples/brain_demo.py --synth gemma3:4b --judge-model qwen3:8b --context
"""

import argparse
import asyncio
from pathlib import Path

from sunwell.naaru import Naaru, NaaruConfig


async def main():
    """Run the brain demo."""
    parser = argparse.ArgumentParser(description="Sunwell Brain Demo")
    parser.add_argument("--llm", action="store_true", 
                       help="Enable LLM for both synthesis AND judging (same model)")
    parser.add_argument("--model", default="gemma3:1b",
                       help="Ollama model for --llm mode (default: gemma3:1b)")
    parser.add_argument("--synth", default=None,
                       help="Synthesis model (enables LLM synthesis)")
    parser.add_argument("--judge-model", default=None,
                       help="Judge model (enables LLM judging)")
    parser.add_argument("--threshold", type=float, default=6.0,
                       help="Quality threshold to approve proposals (0-10, default: 6.0)")
    parser.add_argument("--temp", type=float, default=0.3,
                       help="Synthesis temperature (lower = more precise, default: 0.3)")
    parser.add_argument("--time", type=int, default=20,
                       help="Thinking time in seconds (default: 20)")
    parser.add_argument("--context", action="store_true",
                       help="Enable headspace context for judge (System 2 deep thinking)")
    parser.add_argument("--refine", type=int, default=2,
                       help="Max refinement attempts for rejected proposals (default: 2)")
    parser.add_argument("--lens-consistency", action="store_true",
                       help="NOVEL: Use lens-weighted self-consistency for +5 quality points")
    parser.add_argument("--pipeline", action="store_true",
                       help="NOVEL: Overlap LLM generation with memory prefetching")
    args = parser.parse_args()
    
    sunwell_root = Path(__file__).parent.parent
    
    # Create models based on flags
    synthesis_model = None
    judge_model = None
    synth_name = None
    judge_name = None
    
    from sunwell.models.ollama import OllamaModel
    
    # --llm uses same model for both
    if args.llm:
        synthesis_model = OllamaModel(model=args.model)
        judge_model = synthesis_model
        synth_name = args.model
        judge_name = args.model
    
    # --synth and --judge-model allow mixing different models
    if args.synth:
        synthesis_model = OllamaModel(model=args.synth)
        synth_name = args.synth
    
    if args.judge_model:
        judge_model = OllamaModel(model=args.judge_model)
        judge_name = args.judge_model
    
    # Build headspace context for judge (System 2 deep thinking)
    headspace_context = []
    if args.context:
        # Simulate relevant memories from headspace (in production, query HeadspaceManager)
        headspace_context = [
            "Error handling should use custom exception classes, not generic Exception",
            "Always include error context (file, line, operation) in error messages",
            "Use logging.exception() to capture stack traces automatically",
            "Prefer specific pytest assertions (assert x == y) over generic assert",
            "Docstrings should follow Google/NumPy style with Args/Returns sections",
            "Type hints are required for public API functions",
            "Context managers (with statements) should be used for resource cleanup",
        ]
    
    # Print config
    if synth_name:
        if args.lens_consistency:
            mode_status = " [LENS-CONSISTENCY]"
        elif args.pipeline:
            mode_status = " [PIPELINED]"
        else:
            mode_status = " [TIGHT prompts]"
        print(f"🔧 Synthesis: {synth_name} (temp={args.temp}){mode_status}")
    if args.lens_consistency:
        print(f"   🎭 Using 3 lens personas: Security, Code Quality, QA")
    if args.pipeline:
        print(f"   🔀 Pipelined: Overlapping LLM generation with memory prefetch")
    if judge_name:
        context_status = f" + {len(headspace_context)} memories" if headspace_context else ""
        refine_status = f" | refine={args.refine}" if args.refine > 0 else ""
        print(f"🎯 Judge: {judge_name} (threshold={args.threshold}{refine_status}) [DEEP prompts{context_status}]")
    if args.refine > 0 and (synth_name or judge_name):
        print(f"🔄 Feedback Loop: Up to {args.refine} refinement attempts per proposal")
    if synth_name or judge_name:
        print()
    
    print()
    print("╔" + "═" * 70 + "╗")
    print("║" + " 🧠 SUNWELL BRAIN DEMO".ljust(70) + "║")
    print("║" + " Brain-Inspired Architecture with Specialized Regions".ljust(70) + "║")
    print("╠" + "═" * 70 + "╣")
    print("║" + "".ljust(70) + "║")
    print("║" + "  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐".ljust(70) + "║")
    print("║" + "  │  ANALYSIS   │──▶│  SYNTHESIS  │──▶│ VALIDATION  │".ljust(70) + "║")
    synthesis_label = "  (LLM Gen)  " if synth_name else "  (2 workers)"
    validation_label = "  (LLM Judge)" if judge_name else "  (1 worker) "
    print("║" + f"  │  (2 workers)│   │{synthesis_label}│   │{validation_label}│".ljust(70) + "║")
    print("║" + "  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘".ljust(70) + "║")
    print("║" + "         └─────────────────┼─────────────────┘".ljust(70) + "║")
    print("║" + "                ╔══════════╧══════════╗".ljust(70) + "║")
    print("║" + "                ║  CORPUS CALLOSUM    ║".ljust(70) + "║")
    print("║" + "                ╚══════════╤══════════╝".ljust(70) + "║")
    print("║" + "         ┌─────────────────┼─────────────────┐".ljust(70) + "║")
    print("║" + "  ┌──────┴──────┐   ┌──────┴──────┐".ljust(70) + "║")
    print("║" + "  │   MEMORY    │   │  EXECUTIVE  │".ljust(70) + "║")
    print("║" + "  │  (learnings)│   │  (control)  │".ljust(70) + "║")
    print("║" + "  └─────────────┘   └─────────────┘".ljust(70) + "║")
    print("║" + "".ljust(70) + "║")
    print("╚" + "═" * 70 + "╝")
    print()
    
    # Setup pipelining resources (if enabled)
    headspace_store = None
    embedding_model = None
    if args.pipeline:
        # Create simple mock headspace for demo (in production, use real HeadspaceStore)
        headspace_store = {"enabled": True}  # Triggers pipelined synthesis
        # Could also add: embedding_model = OllamaEmbedding(model="nomic-embed-text")
    
    # Create brain with LLM models
    # Synthesis = tight prompts (fast), Judge = deep prompts (thorough)
    # FEEDBACK LOOP: Rejected proposals get sent back for refinement
    # LENS-CONSISTENCY: Novel technique for +5 quality with small models
    # PIPELINE: Overlap generation with memory prefetching
    brain = SunwellBrain(
        sunwell_root=sunwell_root,
        num_analysis_workers=2,
        num_synthesis_workers=2,
        synthesis_model=synthesis_model,
        synthesis_temperature=args.temp,
        judge_model=judge_model,
        quality_threshold=args.threshold,
        headspace_context=headspace_context,  # Memory context for deep judge
        max_refine_attempts=args.refine,  # FEEDBACK LOOP
        use_lens_consistency=args.lens_consistency,  # NOVEL: +5 quality points
        headspace_store=headspace_store,  # PIPELINE: Memory prefetching
        embedding_model=embedding_model,  # PIPELINE: Semantic prefetch
    )
    
    # Think!
    results = await brain.think(
        goals=["improve error handling", "documentation"],
        max_time_seconds=args.time,
    )
    
    # Show detailed stats
    print("\n🔬 Detailed Worker Stats:")
    for worker_name, stats in results["worker_stats"].items():
        print(f"   {worker_name}:")
        for key, value in stats.items():
            print(f"      {key}: {value}")
    
    print("\n📡 Corpus Callosum Traffic:")
    for msg_type, count in results["corpus_stats"]["by_type"].items():
        print(f"   {msg_type}: {count} messages")


if __name__ == "__main__":
    asyncio.run(main())
