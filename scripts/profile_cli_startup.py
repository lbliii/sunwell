#!/usr/bin/env python
"""Profile CLI startup to find heavy imports.

This script measures the import time of each CLI module to identify
performance bottlenecks in cold start time.

Usage:
    python scripts/profile_cli_startup.py
    python scripts/profile_cli_startup.py --top 20
    python scripts/profile_cli_startup.py --threshold 100
"""

import importlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImportTiming:
    """Timing data for a single import."""

    module: str
    time_ms: float
    cumulative_ms: float
    depth: int


def profile_import(module_name: str, depth: int = 0) -> ImportTiming:
    """Profile the import time of a single module.

    Args:
        module_name: Fully qualified module name to import
        depth: Nesting depth for display

    Returns:
        ImportTiming with timing data
    """
    # Clear from cache if present (for accurate timing)
    if module_name in sys.modules:
        # Module already imported, return cached timing
        return ImportTiming(
            module=module_name,
            time_ms=0.0,
            cumulative_ms=0.0,
            depth=depth,
        )

    start = time.perf_counter()
    try:
        importlib.import_module(module_name)
    except ImportError as e:
        return ImportTiming(
            module=f"{module_name} (FAILED: {e})",
            time_ms=0.0,
            cumulative_ms=0.0,
            depth=depth,
        )
    elapsed = time.perf_counter() - start

    return ImportTiming(
        module=module_name,
        time_ms=elapsed * 1000,
        cumulative_ms=elapsed * 1000,
        depth=depth,
    )


def profile_cli_modules() -> list[ImportTiming]:
    """Profile all CLI modules.

    Returns:
        List of ImportTiming sorted by time (slowest first)
    """
    # Clear CLI modules from cache for fresh timing
    modules_to_clear = [k for k in sys.modules if "sunwell.interface.cli" in k]
    for mod in modules_to_clear:
        del sys.modules[mod]

    # CLI modules to profile
    cli_modules = [
        # Core modules
        "sunwell.interface.cli.core.async_runner",
        "sunwell.interface.cli.core.theme",
        "sunwell.interface.cli.core.error_handler",
        "sunwell.interface.cli.core.shortcuts",
        "sunwell.interface.cli.core.setup",
        "sunwell.interface.cli.core.session",
        "sunwell.interface.cli.core.lens",
        "sunwell.interface.cli.core.bind",
        "sunwell.interface.cli.core.reason",
        # Commands
        "sunwell.interface.cli.commands.config_cmd",
        "sunwell.interface.cli.commands.project_cmd",
        "sunwell.interface.cli.commands.goal",
        "sunwell.interface.cli.commands.serve_cmd",
        "sunwell.interface.cli.commands.debug_cmd",
        "sunwell.interface.cli.commands.review_cmd",
        "sunwell.interface.cli.commands.lineage_cmd",
        "sunwell.interface.cli.commands.backlog_cmd",
        "sunwell.interface.cli.commands.dag_cmd",
        "sunwell.interface.cli.commands.scan_cmd",
        "sunwell.interface.cli.commands.workspace_cmd",
        "sunwell.interface.cli.commands.workflow_cmd",
        "sunwell.interface.cli.commands.internal_cmd",
        "sunwell.interface.cli.commands.bootstrap_cmd",
        "sunwell.interface.cli.commands.skills_cmd",
        "sunwell.interface.cli.commands.epic_cmd",
        # Chat
        "sunwell.interface.cli.chat",
        # Helpers
        "sunwell.interface.cli.helpers",
    ]

    timings = []
    for mod in cli_modules:
        timing = profile_import(mod)
        timings.append(timing)

    return sorted(timings, key=lambda t: t.time_ms, reverse=True)


def profile_full_startup() -> float:
    """Profile full CLI startup time.

    Returns:
        Total startup time in milliseconds
    """
    # Clear all sunwell modules
    modules_to_clear = [k for k in sys.modules if k.startswith("sunwell")]
    for mod in modules_to_clear:
        del sys.modules[mod]

    start = time.perf_counter()
    from sunwell.interface.cli.core.main import main  # noqa: F401

    elapsed = time.perf_counter() - start
    return elapsed * 1000


def profile_dependencies() -> list[ImportTiming]:
    """Profile key dependencies that affect startup.

    Returns:
        List of ImportTiming for dependencies
    """
    deps = [
        "click",
        "rich",
        "yaml",
        "pydantic",
        "httpx",
        "anthropic",
        "openai",
    ]

    # Clear from cache
    for dep in deps:
        if dep in sys.modules:
            del sys.modules[dep]

    timings = []
    for dep in deps:
        timing = profile_import(dep)
        timings.append(timing)

    return sorted(timings, key=lambda t: t.time_ms, reverse=True)


def main_profile(top: int = 15, threshold_ms: float = 50.0) -> None:
    """Run profiling and display results.

    Args:
        top: Number of top slow imports to show
        threshold_ms: Only show imports slower than this
    """
    print("=" * 60)
    print("CLI Startup Profiler")
    print("=" * 60)

    # Profile dependencies first
    print("\n[1/3] Profiling dependencies...")
    dep_timings = profile_dependencies()
    print("\nDependency Import Times:")
    print("-" * 40)
    for t in dep_timings[:10]:
        if t.time_ms > 0:
            print(f"  {t.time_ms:7.1f}ms  {t.module}")

    # Profile CLI modules
    print("\n[2/3] Profiling CLI modules...")
    cli_timings = profile_cli_modules()
    print(f"\nTop {top} Slowest CLI Modules (>{threshold_ms}ms):")
    print("-" * 40)
    count = 0
    for t in cli_timings:
        if t.time_ms > threshold_ms:
            print(f"  {t.time_ms:7.1f}ms  {t.module}")
            count += 1
            if count >= top:
                break

    # Profile full startup
    print("\n[3/3] Profiling full CLI startup...")
    total_ms = profile_full_startup()
    print(f"\nFull CLI Startup Time: {total_ms:.0f}ms")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Target:  <500ms")
    print(f"  Current: {total_ms:.0f}ms")
    if total_ms < 500:
        print("  Status:  ✓ PASS")
    elif total_ms < 1000:
        print("  Status:  △ ACCEPTABLE")
    else:
        print("  Status:  ✗ NEEDS IMPROVEMENT")

    # Recommendations
    if total_ms > 500:
        print("\nRecommendations:")
        slow_mods = [t for t in cli_timings if t.time_ms > 100]
        if slow_mods:
            print("  1. Consider lazy loading these slow modules:")
            for t in slow_mods[:5]:
                print(f"     - {t.module} ({t.time_ms:.0f}ms)")
        print("  2. Defer heavy dependencies (pydantic, httpx) until needed")
        print("  3. Use lazy imports for rarely-used commands")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Profile CLI startup time")
    parser.add_argument("--top", type=int, default=15, help="Number of top imports to show")
    parser.add_argument(
        "--threshold", type=float, default=50.0, help="Only show imports slower than this (ms)"
    )
    args = parser.parse_args()

    main_profile(top=args.top, threshold_ms=args.threshold)
