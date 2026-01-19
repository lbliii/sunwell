#!/usr/bin/env python3
"""Ablation study runner for Vortex components.

This script runs ablation studies to measure the contribution of each
Vortex component (locality, interference, dialectic, resonance, gradient).

Usage:
    python scripts/run_ablation_study.py --model gemma3:1b
    python scripts/run_ablation_study.py --model qwen2.5-coder:1.5b --output results/

The script:
1. Loads ablation tasks from benchmark/tasks/vortex/ablation.yaml
2. Runs each task with different component configurations
3. Measures quality (if ground truth) or diversity (if design task)
4. Generates a report showing component contributions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class AblationResult:
    """Result from running a task under one configuration."""
    
    task_id: str
    config_name: str
    synthesis: str
    total_signals: int
    distinct_cultures: int
    migrations: int
    discovery_time_s: float
    selection_time_s: float
    synthesis_time_s: float
    total_time_s: float
    discovery_tokens: int
    selection_tokens: int
    synthesis_tokens: int
    
    # Quality metrics (if applicable)
    matches_ground_truth: bool | None = None
    quality_score: float | None = None


@dataclass
class AblationStudyResult:
    """Complete ablation study results."""
    
    timestamp: str
    model: str
    tasks: list[str]
    configs: list[str]
    results: dict[str, dict[str, AblationResult]]  # task_id -> config_name -> result
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        results_dict = {}
        for task_id, config_results in self.results.items():
            results_dict[task_id] = {}
            for config_name, result in config_results.items():
                results_dict[task_id][config_name] = {
                    "synthesis": result.synthesis[:200],  # Truncate
                    "total_signals": result.total_signals,
                    "distinct_cultures": result.distinct_cultures,
                    "migrations": result.migrations,
                    "total_time_s": result.total_time_s,
                    "total_tokens": (
                        result.discovery_tokens +
                        result.selection_tokens +
                        result.synthesis_tokens
                    ),
                    "matches_ground_truth": result.matches_ground_truth,
                    "quality_score": result.quality_score,
                }
        
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "tasks": self.tasks,
            "configs": self.configs,
            "results": results_dict,
        }


async def run_ablation_study(
    model_name: str,
    tasks_file: Path,
    output_dir: Path,
    configs_to_run: list[str] | None = None,
    max_tasks: int | None = None,
) -> AblationStudyResult:
    """Run ablation study across configurations.
    
    Args:
        model_name: Ollama model to use
        tasks_file: Path to ablation tasks YAML
        output_dir: Directory to save results
        configs_to_run: Specific configs to run (default: all)
        max_tasks: Maximum tasks to run (for quick testing)
    
    Returns:
        AblationStudyResult with all results
    """
    from sunwell.models.ollama import OllamaModel
    from sunwell.vortex import Vortex, VortexConfig
    
    # Load tasks and configs
    with open(tasks_file) as f:
        data = yaml.safe_load(f)
    
    tasks = data.get("tasks", [])
    ablation_config = data.get("ablation_config", {})
    
    if max_tasks:
        tasks = tasks[:max_tasks]
    
    if configs_to_run is None:
        configs_to_run = list(ablation_config.keys())
    
    # Initialize model
    model = OllamaModel(model=model_name)
    
    # Run all combinations
    all_results: dict[str, dict[str, AblationResult]] = {}
    
    print(f"\n{'='*60}")
    print(f"ABLATION STUDY: {model_name}")
    print(f"Tasks: {len(tasks)}, Configs: {len(configs_to_run)}")
    print(f"{'='*60}\n")
    
    for task in tasks:
        task_id = task["id"]
        task_prompt = task["task"]
        ground_truth = task.get("ground_truth")
        
        all_results[task_id] = {}
        
        print(f"\n--- Task: {task_id} ---")
        
        for config_name in configs_to_run:
            config_params = ablation_config.get(config_name, {})
            
            # Build VortexConfig from params
            vortex_config = VortexConfig(
                n_islands=config_params.get("n_islands", 3),
                dialectic_enabled=config_params.get("dialectic_enabled", True),
                dialectic_threshold=config_params.get("dialectic_threshold", 0.6),
                resonance_iterations=config_params.get("resonance_iterations", 2),
                interference_perspectives=config_params.get("interference_perspectives", 3),
            )
            
            print(f"  Config: {config_name}...", end=" ", flush=True)
            
            try:
                vortex = Vortex(model, vortex_config)
                result = await vortex.solve(task_prompt)
                
                # Check ground truth if available
                matches = None
                if ground_truth:
                    # Simple containment check
                    matches = ground_truth.lower() in result.synthesis.lower()
                
                ablation_result = AblationResult(
                    task_id=task_id,
                    config_name=config_name,
                    synthesis=result.synthesis,
                    total_signals=result.total_signals,
                    distinct_cultures=result.distinct_cultures,
                    migrations=result.migrations,
                    discovery_time_s=result.discovery_time_s,
                    selection_time_s=result.selection_time_s,
                    synthesis_time_s=result.synthesis_time_s,
                    total_time_s=result.total_time_s,
                    discovery_tokens=result.discovery_tokens,
                    selection_tokens=result.selection_tokens,
                    synthesis_tokens=result.synthesis_tokens,
                    matches_ground_truth=matches,
                )
                
                all_results[task_id][config_name] = ablation_result
                
                status = "✓" if matches is None or matches else "✗"
                print(f"{status} ({result.total_time_s:.1f}s)")
                
            except Exception as e:
                print(f"✗ Error: {e}")
    
    study_result = AblationStudyResult(
        timestamp=datetime.now().isoformat(),
        model=model_name,
        tasks=[t["id"] for t in tasks],
        configs=configs_to_run,
        results=all_results,
    )
    
    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"ablation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    
    with open(output_file, "w") as f:
        json.dump(study_result.to_dict(), f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Results saved to: {output_file}")
    print(f"{'='*60}\n")
    
    return study_result


def format_ablation_report(result: AblationStudyResult) -> str:
    """Format ablation study results as a markdown report."""
    lines = [
        f"# Ablation Study Report",
        f"",
        f"**Model**: {result.model}",
        f"**Timestamp**: {result.timestamp}",
        f"**Tasks**: {len(result.tasks)}",
        f"**Configurations**: {len(result.configs)}",
        f"",
        f"## Summary",
        f"",
    ]
    
    # Component contribution summary
    lines.append("### Component Contributions")
    lines.append("")
    lines.append("| Config | Avg Time (s) | Avg Tokens | Ground Truth Match |")
    lines.append("|--------|--------------|------------|-------------------|")
    
    for config_name in result.configs:
        times = []
        tokens = []
        matches = []
        
        for task_id in result.tasks:
            if task_id in result.results and config_name in result.results[task_id]:
                r = result.results[task_id][config_name]
                times.append(r.total_time_s)
                tokens.append(r.discovery_tokens + r.selection_tokens + r.synthesis_tokens)
                if r.matches_ground_truth is not None:
                    matches.append(1 if r.matches_ground_truth else 0)
        
        avg_time = sum(times) / len(times) if times else 0
        avg_tokens = sum(tokens) / len(tokens) if tokens else 0
        match_rate = sum(matches) / len(matches) if matches else None
        
        match_str = f"{match_rate:.0%}" if match_rate is not None else "N/A"
        lines.append(f"| {config_name} | {avg_time:.1f} | {avg_tokens:.0f} | {match_str} |")
    
    lines.append("")
    lines.append("## Per-Task Results")
    lines.append("")
    
    for task_id in result.tasks:
        lines.append(f"### {task_id}")
        lines.append("")
        
        if task_id not in result.results:
            lines.append("*No results*")
            continue
        
        for config_name, r in result.results[task_id].items():
            lines.append(f"**{config_name}**:")
            lines.append(f"- Time: {r.total_time_s:.1f}s")
            lines.append(f"- Signals: {r.total_signals}")
            lines.append(f"- Cultures: {r.distinct_cultures}")
            if r.matches_ground_truth is not None:
                match_emoji = "✅" if r.matches_ground_truth else "❌"
                lines.append(f"- Match: {match_emoji}")
            lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run Vortex ablation study")
    parser.add_argument(
        "--model",
        default="gemma3:1b",
        help="Ollama model to use",
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path("benchmark/tasks/vortex/ablation.yaml"),
        help="Path to ablation tasks YAML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark/results/ablation"),
        help="Output directory",
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        help="Specific configs to run (default: all)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        help="Maximum tasks to run (for quick testing)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate markdown report",
    )
    
    args = parser.parse_args()
    
    result = asyncio.run(run_ablation_study(
        model_name=args.model,
        tasks_file=args.tasks,
        output_dir=args.output,
        configs_to_run=args.configs,
        max_tasks=args.max_tasks,
    ))
    
    if args.report:
        report = format_ablation_report(result)
        report_file = args.output / "report.md"
        report_file.write_text(report)
        print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()
