#!/usr/bin/env python3
"""Demo of RFC-033 Unified Naaru Architecture.

Shows how to use the composable three-layer architecture:
1. Diversity Layer - Generate multiple perspectives
2. Selection Layer - Choose the best candidate
3. Refinement Layer - Optionally improve the result
"""

import asyncio
from pathlib import Path

from sunwell.models.ollama import OllamaModel
from sunwell.naaru.unified import (
    unified_pipeline,
    create_minimal_config,
    create_cheap_diversity_config,
    create_balanced_config,
    create_quality_config,
    create_auto_config,
)
from sunwell.types.config import NaaruConfig


async def main() -> None:
    """Demonstrate unified Naaru pipeline."""
    
    # Initialize models
    model = OllamaModel(model="gemma3:1b")
    judge_model = OllamaModel(model="gemma3:4b")
    
    test_prompt = "Write a Python function to validate an email address with proper error handling."
    
    print("=" * 70)
    print("RFC-033: Unified Naaru Architecture Demo")
    print("=" * 70)
    print()
    
    # Test different configurations
    configs = [
        ("MINIMAL", create_minimal_config()),
        ("CHEAP_DIVERSITY", create_cheap_diversity_config()),
        ("BALANCED", create_balanced_config()),
        ("QUALITY", create_quality_config()),
        ("AUTO", create_auto_config()),
    ]
    
    for name, config in configs:
        print(f"\n{'='*70}")
        print(f"Configuration: {name}")
        print("=" * 70)
        print(f"Diversity: {config.diversity}")
        print(f"Selection: {config.selection}")
        print(f"Refinement: {config.refinement}")
        print(f"Cost Budget: {config.cost_budget}")
        print()
        
        try:
            result = await unified_pipeline(
                model=model,
                prompt=test_prompt,
                config=config,
                judge_model=judge_model,
            )
            
            print(f"✅ Success!")
            print(f"Strategies used:")
            print(f"  - Diversity: {result.diversity_strategy}")
            print(f"  - Selection: {result.selection_strategy}")
            print(f"  - Refinement: {result.refinement_strategy}")
            print(f"Total tokens: {result.total_tokens}")
            print(f"Candidates generated: {len(result.candidates)}")
            if result.task_analysis:
                print(f"Task analysis:")
                print(f"  - Deterministic: {result.task_analysis.is_deterministic}")
                print(f"  - Creative: {result.task_analysis.is_creative}")
                print(f"  - High Stakes: {result.task_analysis.is_high_stakes}")
                print(f"  - Complexity: {result.task_analysis.complexity}")
            print()
            print("Output preview:")
            print("-" * 40)
            print(result.text[:300] + "..." if len(result.text) > 300 else result.text)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("=" * 70)
    print("Custom Configuration Example")
    print("=" * 70)
    print()
    
    # Custom configuration
    custom_config = NaaruConfig(
        diversity="sampling",
        diversity_temps=(0.2, 0.5, 0.8),
        selection="heuristic",
        refinement="tiered",
        cost_budget="normal",
        task_type="code",
    )
    
    print("Custom config: sampling (0.2, 0.5, 0.8) + heuristic + tiered")
    result = await unified_pipeline(
        model=model,
        prompt=test_prompt,
        config=custom_config,
        judge_model=judge_model,
    )
    
    print(f"✅ Generated {len(result.candidates)} candidates")
    print(f"Selected: {result.selected.source}")
    print(f"Refined: {result.refinement.refined}")
    print(f"Total tokens: {result.total_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
