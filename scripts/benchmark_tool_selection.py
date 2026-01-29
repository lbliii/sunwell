#!/usr/bin/env python3
"""Benchmark tool selection accuracy with and without DAG-based selection.

This script measures how well models select appropriate tools when given:
1. Full tool catalog (40+ tools) - baseline
2. DAG-filtered tools (5-15 tools) - with selection

The hypothesis (backed by research) is that small models show dramatic
accuracy improvement with fewer, more relevant tools.

Usage:
    python scripts/benchmark_tool_selection.py --model qwen2.5:1.5b
    python scripts/benchmark_tool_selection.py --model gpt-4o-mini --runs 10
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunwell.models import GenerateOptions, Message, Tool
from sunwell.models.adapters import OllamaModel, OpenAIModel
from sunwell.tools.definitions.builtins import ALL_BUILTIN_TOOLS, EXPERTISE_TOOLS
from sunwell.tools.selection.graph import DEFAULT_TOOL_DAG
from sunwell.tools.selection.selector import MultiSignalToolSelector, SelectionTrace

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# BENCHMARK SCENARIOS
# =============================================================================

@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """A benchmark scenario with expected tool selection."""
    
    name: str
    query: str
    expected_tools: frozenset[str]
    """Tools that should be selected (any of these is correct)."""
    
    anti_tools: frozenset[str] = frozenset()
    """Tools that should NOT be selected."""
    
    used_tools: frozenset[str] = frozenset()
    """Tools already used (for DAG progression)."""


# Scenarios that test tool selection accuracy
SCENARIOS: tuple[BenchmarkScenario, ...] = (
    # Discovery scenarios (entry points)
    BenchmarkScenario(
        name="list_python_files",
        query="List all Python files in the src directory",
        expected_tools=frozenset({"list_files", "find_files"}),
        anti_tools=frozenset({"edit_file", "write_file", "git_commit"}),
    ),
    BenchmarkScenario(
        name="search_error_handling",
        query="Search for error handling code in the codebase",
        expected_tools=frozenset({"search_files"}),
        anti_tools=frozenset({"write_file", "git_commit", "run_command"}),
    ),
    BenchmarkScenario(
        name="check_git_status",
        query="Show me the current git status",
        expected_tools=frozenset({"git_status", "git_info"}),
        anti_tools=frozenset({"git_commit", "git_merge", "write_file"}),
    ),
    
    # Read scenarios (after discovery)
    BenchmarkScenario(
        name="read_config",
        query="Read the configuration file at config.yaml",
        expected_tools=frozenset({"read_file"}),
        anti_tools=frozenset({"edit_file", "write_file", "git_commit"}),
        used_tools=frozenset({"list_files"}),  # Discovered files first
    ),
    
    # Edit scenarios (after reading)
    BenchmarkScenario(
        name="fix_typo",
        query="Fix the typo in line 42 of main.py",
        expected_tools=frozenset({"edit_file", "patch_file"}),
        anti_tools=frozenset({"write_file", "delete_file", "git_commit"}),
        used_tools=frozenset({"list_files", "read_file"}),  # Read the file first
    ),
    
    # Git scenarios (after editing)
    BenchmarkScenario(
        name="stage_changes",
        query="Stage the changes I just made",
        expected_tools=frozenset({"git_add"}),
        anti_tools=frozenset({"git_commit", "git_merge", "write_file"}),
        used_tools=frozenset({"list_files", "read_file", "edit_file"}),
    ),
    BenchmarkScenario(
        name="commit_changes",
        query="Commit the staged changes with message 'Fix typo'",
        expected_tools=frozenset({"git_commit"}),
        anti_tools=frozenset({"write_file", "edit_file", "git_merge"}),
        used_tools=frozenset({"list_files", "read_file", "edit_file", "git_add"}),
    ),
    
    # Complex scenarios
    BenchmarkScenario(
        name="run_tests",
        query="Run the test suite",
        expected_tools=frozenset({"run_command"}),
        anti_tools=frozenset({"edit_file", "git_commit"}),
    ),
    BenchmarkScenario(
        name="show_env",
        query="What environment variables are available?",
        expected_tools=frozenset({"list_env"}),
        anti_tools=frozenset({"run_command", "read_file", "git_status"}),
    ),
)


# =============================================================================
# BENCHMARK EXECUTION
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    
    scenario_name: str
    with_selection: bool
    tool_count: int
    selected_tool: str | None
    correct: bool
    anti_selected: bool
    latency_ms: float
    error: str | None = None
    trace: SelectionTrace | None = None


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results."""
    
    model: str
    runs: int
    with_selection_accuracy: float
    without_selection_accuracy: float
    with_selection_anti_rate: float
    without_selection_anti_rate: float
    with_selection_avg_tools: float
    without_selection_avg_tools: float
    with_selection_avg_latency_ms: float
    without_selection_avg_latency_ms: float
    results: list[BenchmarkResult] = field(default_factory=list)


def get_all_tools() -> tuple[Tool, ...]:
    """Get all available tools."""
    all_tools = {**ALL_BUILTIN_TOOLS, **EXPERTISE_TOOLS}
    return tuple(all_tools.values())


async def run_scenario(
    model: Any,
    scenario: BenchmarkScenario,
    tools: tuple[Tool, ...],
    with_selection: bool,
    enable_trace: bool = False,
) -> BenchmarkResult:
    """Run a single benchmark scenario.
    
    Args:
        model: The model to test
        scenario: The scenario to run
        tools: Available tools
        with_selection: Whether to use DAG-based selection
        enable_trace: Whether to capture detailed selection trace
        
    Returns:
        BenchmarkResult with accuracy metrics
    """
    start_time = time.perf_counter()
    trace = None
    
    # Apply DAG selection if enabled
    if with_selection:
        selector = MultiSignalToolSelector(
            enable_learned_boost=False,  # Pure DAG test
            enable_project_filter=False,  # Pure DAG test
        )
        if enable_trace:
            tools, trace = selector.select_with_trace(
                query=scenario.query,
                task_type="general",
                used_tools=scenario.used_tools,
                available_tools=tools,
            )
        else:
            tools = selector.select(
                query=scenario.query,
                task_type="general",
                used_tools=scenario.used_tools,
                available_tools=tools,
            )
    
    tool_count = len(tools)
    
    try:
        # Generate with tool calling
        messages = (Message(role="user", content=scenario.query),)
        options = GenerateOptions(temperature=0.0)  # Deterministic
        
        result = await model.generate(
            messages,  # positional arg (prompt)
            tools=tools,
            options=options,
        )
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        # Check if model selected a tool
        if result.tool_calls:
            selected_tool = result.tool_calls[0].name
            correct = selected_tool in scenario.expected_tools
            anti_selected = selected_tool in scenario.anti_tools
        else:
            selected_tool = None
            correct = False
            anti_selected = False
        
        return BenchmarkResult(
            scenario_name=scenario.name,
            with_selection=with_selection,
            tool_count=tool_count,
            selected_tool=selected_tool,
            correct=correct,
            anti_selected=anti_selected,
            latency_ms=latency_ms,
            trace=trace,
        )
        
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return BenchmarkResult(
            scenario_name=scenario.name,
            with_selection=with_selection,
            tool_count=tool_count,
            selected_tool=None,
            correct=False,
            anti_selected=False,
            latency_ms=latency_ms,
            error=str(e),
            trace=trace,
        )


def create_model(model_name: str):
    """Create a model instance based on the model name.
    
    Args:
        model_name: Model name (e.g., "qwen2.5:1.5b" for Ollama, "gpt-4o-mini" for OpenAI)
        
    Returns:
        Model instance
    """
    # Check if it's an OpenAI model
    if model_name.startswith("gpt-") or model_name.startswith("o1"):
        return OpenAIModel(model=model_name)
    # Default to Ollama for local models
    return OllamaModel(model=model_name)


async def run_benchmark(
    model_name: str,
    runs: int = 3,
    enable_trace: bool = False,
) -> BenchmarkSummary:
    """Run the full benchmark suite.
    
    Args:
        model_name: Name of the model to test
        runs: Number of runs per scenario
        enable_trace: Whether to capture detailed selection traces
        
    Returns:
        BenchmarkSummary with aggregated results
    """
    logger.info(f"Starting benchmark with model: {model_name}")
    
    # Initialize model
    model = create_model(model_name)
    
    all_tools = get_all_tools()
    logger.info(f"Total tools available: {len(all_tools)}")
    
    results: list[BenchmarkResult] = []
    
    for run in range(runs):
        logger.info(f"Run {run + 1}/{runs}")
        
        for scenario in SCENARIOS:
            # Without selection (baseline)
            result_without = await run_scenario(
                model=model,
                scenario=scenario,
                tools=all_tools,
                with_selection=False,
                enable_trace=False,  # No trace for baseline
            )
            results.append(result_without)
            
            # With selection (DAG-based)
            result_with = await run_scenario(
                model=model,
                scenario=scenario,
                tools=all_tools,
                with_selection=True,
                enable_trace=enable_trace,
            )
            results.append(result_with)
            
            # Log progress
            status_without = '✓' if result_without.correct else '✗'
            status_with = '✓' if result_with.correct else '✗'
            
            log_msg = (
                f"  {scenario.name}: "
                f"without={result_without.selected_tool} ({status_without}), "
                f"with={result_with.selected_tool} ({status_with})"
            )
            
            # Show winning signals if trace is available
            if result_with.trace and result_with.selected_tool:
                # Find the selected tool's signals
                for ts in result_with.trace.top_tools:
                    if ts.name == result_with.selected_tool:
                        signals = ts.active_signals()
                        if signals:
                            log_msg += f" [signals: {', '.join(signals)}]"
                        break
            
            logger.info(log_msg)
    
    # Calculate summary statistics
    with_results = [r for r in results if r.with_selection]
    without_results = [r for r in results if not r.with_selection]
    
    with_correct = sum(1 for r in with_results if r.correct)
    without_correct = sum(1 for r in without_results if r.correct)
    
    with_anti = sum(1 for r in with_results if r.anti_selected)
    without_anti = sum(1 for r in without_results if r.anti_selected)
    
    return BenchmarkSummary(
        model=model_name,
        runs=runs,
        with_selection_accuracy=with_correct / len(with_results) if with_results else 0,
        without_selection_accuracy=without_correct / len(without_results) if without_results else 0,
        with_selection_anti_rate=with_anti / len(with_results) if with_results else 0,
        without_selection_anti_rate=without_anti / len(without_results) if without_results else 0,
        with_selection_avg_tools=sum(r.tool_count for r in with_results) / len(with_results) if with_results else 0,
        without_selection_avg_tools=sum(r.tool_count for r in without_results) / len(without_results) if without_results else 0,
        with_selection_avg_latency_ms=sum(r.latency_ms for r in with_results) / len(with_results) if with_results else 0,
        without_selection_avg_latency_ms=sum(r.latency_ms for r in without_results) / len(without_results) if without_results else 0,
        results=results,
    )


def print_summary(summary: BenchmarkSummary) -> None:
    """Print benchmark summary in a nice format."""
    print("\n" + "=" * 60)
    print(f"BENCHMARK RESULTS: {summary.model}")
    print("=" * 60)
    
    print(f"\nRuns per scenario: {summary.runs}")
    print(f"Total scenarios: {len(SCENARIOS)}")
    
    print("\n--- Accuracy ---")
    print(f"Without selection: {summary.without_selection_accuracy:.1%}")
    print(f"With selection:    {summary.with_selection_accuracy:.1%}")
    improvement = summary.with_selection_accuracy - summary.without_selection_accuracy
    print(f"Improvement:       {improvement:+.1%}")
    
    print("\n--- Anti-Tool Selection (Bad Choices) ---")
    print(f"Without selection: {summary.without_selection_anti_rate:.1%}")
    print(f"With selection:    {summary.with_selection_anti_rate:.1%}")
    
    print("\n--- Tool Count ---")
    print(f"Without selection: {summary.without_selection_avg_tools:.1f} tools")
    print(f"With selection:    {summary.with_selection_avg_tools:.1f} tools")
    reduction = (1 - summary.with_selection_avg_tools / summary.without_selection_avg_tools) * 100
    print(f"Reduction:         {reduction:.1f}%")
    
    print("\n--- Latency ---")
    print(f"Without selection: {summary.without_selection_avg_latency_ms:.0f}ms")
    print(f"With selection:    {summary.with_selection_avg_latency_ms:.0f}ms")
    
    print("\n" + "=" * 60)


def print_trace_details(summary: BenchmarkSummary) -> None:
    """Print detailed signal breakdown for each scenario."""
    print("\n" + "=" * 60)
    print("SIGNAL BREAKDOWN BY SCENARIO")
    print("=" * 60)
    
    # Group results by scenario
    with_results = [r for r in summary.results if r.with_selection and r.trace]
    
    for result in with_results:
        trace = result.trace
        if not trace:
            continue
        
        status = "✓ CORRECT" if result.correct else "✗ WRONG"
        print(f"\n--- {result.scenario_name} ({status}) ---")
        print(f"Query: {trace.query[:60]}...")
        print(f"Selected: {result.selected_tool}")
        
        if trace.planned_tools:
            print(f"Planned: {', '.join(trace.planned_tools)}")
        if trace.semantic_hits:
            print(f"Semantic hits: {', '.join(trace.semantic_hits[:5])}")
        
        print(f"\nTop 5 tools with scores:")
        for i, ts in enumerate(trace.top_tools[:5], 1):
            signals = ts.active_signals()
            signal_breakdown = []
            for sig in signals:
                score = ts.signal_dict().get(sig, 0)
                signal_breakdown.append(f"{sig}={score:.0f}")
            
            marker = " ← SELECTED" if ts.name == result.selected_tool else ""
            signal_str = ", ".join(signal_breakdown) if signal_breakdown else "base"
            print(f"  {i}. {ts.name}: {ts.total_score:.0f} [{signal_str}]{marker}")


def main() -> None:
    """Run the benchmark."""
    parser = argparse.ArgumentParser(description="Benchmark tool selection accuracy")
    parser.add_argument(
        "--model",
        default="qwen2.5:1.5b",
        help="Model to benchmark (default: qwen2.5:1.5b)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per scenario (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file for detailed results",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Show detailed signal breakdown for each scenario",
    )
    args = parser.parse_args()
    
    summary = asyncio.run(run_benchmark(args.model, args.runs, enable_trace=args.trace))
    
    print_summary(summary)
    
    if args.trace:
        print_trace_details(summary)
    
    if args.output:
        # Save detailed results
        output_data = {
            "model": summary.model,
            "runs": summary.runs,
            "accuracy": {
                "with_selection": summary.with_selection_accuracy,
                "without_selection": summary.without_selection_accuracy,
            },
            "anti_rate": {
                "with_selection": summary.with_selection_anti_rate,
                "without_selection": summary.without_selection_anti_rate,
            },
            "avg_tools": {
                "with_selection": summary.with_selection_avg_tools,
                "without_selection": summary.without_selection_avg_tools,
            },
            "avg_latency_ms": {
                "with_selection": summary.with_selection_avg_latency_ms,
                "without_selection": summary.without_selection_avg_latency_ms,
            },
            "results": [
                {
                    "scenario": r.scenario_name,
                    "with_selection": r.with_selection,
                    "tool_count": r.tool_count,
                    "selected_tool": r.selected_tool,
                    "correct": r.correct,
                    "anti_selected": r.anti_selected,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in summary.results
            ],
        }
        args.output.write_text(json.dumps(output_data, indent=2))
        logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
