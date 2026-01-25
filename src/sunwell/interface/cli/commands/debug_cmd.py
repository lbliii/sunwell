"""Debug command group - Diagnostics and troubleshooting (RFC-120).

Provides tools for collecting diagnostics, debugging issues, and
generating shareable bug reports.

Example:
    sunwell debug dump
    sunwell debug dump -o my-debug.tar.gz
"""

import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from sunwell import __version__

console = Console()

# =============================================================================
# Constants
# =============================================================================

DUMP_LIMITS = {
    "events": 1000,  # Last N events
    "log_lines": 1000,  # Last N log lines
    "runs": 20,  # Most recent runs
    "plan_versions": 10,  # Per plan
    "max_total_mb": 5,  # Hard cap on tarball size
}

SANITIZE_PATTERNS = [
    r"ANTHROPIC_API_KEY=\S+",
    r"OPENAI_API_KEY=\S+",
    r"Bearer\s+\S+",
    r"token[\"']?\s*[:=]\s*[\"']?[^\s\"']+",
    r"password[\"']?\s*[:=]\s*[\"']?[^\s\"']+",
    r"secret[_-]?\w*[\"']?\s*[:=]\s*[\"']?[^\s\"']+",  # Matches secret, secret_key, secret-token
    r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[^\s\"']+",
    r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style keys
    r"sk-ant-[a-zA-Z0-9-]+",  # Anthropic-style keys
]


# =============================================================================
# CLI Group
# =============================================================================


@click.group()
def debug() -> None:
    """Debugging and diagnostics tools.

    Commands for collecting diagnostics, analyzing issues,
    and generating shareable bug reports.
    """


@debug.command()
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output file path (default: sunwell-debug-<timestamp>.tar.gz)",
)
@click.option(
    "--include-system/--no-include-system",
    default=True,
    help="Include system info (disk, memory, processes)",
)
def dump(output: str | None, include_system: bool) -> None:
    """Collect diagnostics for bug reports.

    Creates a tarball containing:
    - Sunwell version and environment info
    - Configuration (sanitized of secrets)
    - Recent events and logs
    - Run history and plan snapshots
    - Memory state (learnings, dead ends)

    \b
    Examples:
        sunwell debug dump
        sunwell debug dump -o my-debug.tar.gz
        sunwell debug dump --no-include-system

    \b
    The output is designed for sharing in bug reports.
    Secrets are automatically redacted.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    output_path = Path(output) if output else Path(f"sunwell-debug-{timestamp}.tar.gz")

    secrets_found: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Collect each component
        console.print("[dim]Collecting diagnostics...[/dim]")

        _collect_meta(root / "meta.json")
        console.print("  ✓ meta.json")

        secrets_found.extend(_collect_config(root / "config.yaml"))
        console.print("  ✓ config.yaml")

        _collect_events(root / "events.jsonl")
        console.print("  ✓ events.jsonl")

        _collect_runs(root / "runs")
        console.print("  ✓ runs/")

        _collect_plans(root / "plans")
        console.print("  ✓ plans/")

        _collect_simulacrum(root / "simulacrum.json")
        console.print("  ✓ simulacrum.json")

        _collect_logs(root / "agent.log")
        console.print("  ✓ agent.log")

        if include_system:
            _collect_system(root / "system")
            console.print("  ✓ system/")

        # Create tarball
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(root, arcname="sunwell-debug")

    # Report results
    size_kb = output_path.stat().st_size / 1024
    size_mb = size_kb / 1024

    console.print(f"\n[green]✓[/green] Debug dump saved to {output_path}")
    console.print(f"  Size: {size_kb:.1f} KB ({size_mb:.2f} MB)")

    if secrets_found:
        console.print(
            f"\n[yellow]⚠[/yellow] Sanitized {len(secrets_found)} potential secrets: "
            f"{', '.join(secrets_found[:3])}{'...' if len(secrets_found) > 3 else ''}"
        )

    console.print("\n[dim]Attach to bug reports or share in Discord[/dim]")

    # Warn if over size limit
    if size_mb > DUMP_LIMITS["max_total_mb"]:
        console.print(
            f"\n[yellow]⚠[/yellow] Dump exceeds {DUMP_LIMITS['max_total_mb']}MB limit. "
            "Consider using --no-include-system or manually removing large files."
        )


# =============================================================================
# Collectors
# =============================================================================


def _collect_meta(dest: Path) -> None:
    """Collect metadata about the environment."""
    meta = {
        "sunwell_version": __version__,
        "python_version": sys.version,
        "platform": platform.platform(),
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "collected_at": datetime.now().isoformat(),
        "cwd": str(Path.cwd()),
    }

    dest.write_text(json.dumps(meta, indent=2))


def _collect_config(dest: Path) -> list[str]:
    """Collect configuration with sanitization.

    Returns list of secret types that were sanitized.
    """
    secrets_found: list[str] = []

    # Find config file
    config_paths = [
        Path.cwd() / ".sunwell" / "config.yaml",
        Path.home() / ".sunwell" / "config.yaml",
    ]

    config_content = ""
    for config_path in config_paths:
        if config_path.exists():
            config_content = config_path.read_text()
            break

    if not config_content:
        config_content = "# No config file found"

    # Sanitize
    sanitized, found = _sanitize(config_content)
    secrets_found.extend(found)

    dest.write_text(sanitized)
    return secrets_found


def _collect_events(dest: Path) -> None:
    """Collect events with fallback strategy.

    Priority order:
    1. RFC-119 EventBus storage (.sunwell/events.jsonl)
    2. TraceLogger files (.sunwell/plans/*.trace.jsonl)
    3. ExternalEventStore (.sunwell/external/events.jsonl)
    """
    events: list[dict] = []

    # Try RFC-119 event storage first
    event_bus_path = Path.cwd() / ".sunwell" / "events.jsonl"
    if event_bus_path.exists():
        events.extend(_read_jsonl(event_bus_path, limit=DUMP_LIMITS["events"]))

    # Fallback: collect from TraceLogger files
    if not events:
        trace_dir = Path.cwd() / ".sunwell" / "plans"
        if trace_dir.exists():
            for trace_file in sorted(
                trace_dir.glob("*.trace.jsonl"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:10]:  # Limit to 10 most recent trace files
                events.extend(_read_jsonl(trace_file, limit=100))

    # Also include external events if available
    external_path = Path.cwd() / ".sunwell" / "external" / "events.jsonl"
    if external_path.exists():
        events.extend(_read_jsonl(external_path, limit=200))

    # Sort by timestamp, keep most recent
    events.sort(key=lambda e: e.get("ts", e.get("timestamp", "")), reverse=True)
    events = events[: DUMP_LIMITS["events"]]

    # Write output with truncation marker if needed
    _write_jsonl(dest, events, total_available=len(events))


def _collect_runs(dest: Path) -> None:
    """Collect recent run summaries."""
    dest.mkdir(parents=True, exist_ok=True)

    try:
        from sunwell.interface.server.runs import RunManager

        manager = RunManager()
        runs = manager.list_runs()

        # Sort by start time, take most recent
        runs = sorted(runs, key=lambda r: r.started_at, reverse=True)
        runs = runs[: DUMP_LIMITS["runs"]]

        for run in runs:
            run_data = {
                "run_id": run.run_id,
                "goal": run.goal,
                "status": run.status,
                "source": run.source,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "workspace": run.workspace,
                "lens": run.lens,
                "provider": run.provider,
                "model": run.model,
                "trust": run.trust,
                "event_count": len(run.events),
            }
            run_file = dest / f"run-{run.run_id[:8]}.json"
            run_file.write_text(json.dumps(run_data, indent=2))

    except Exception as e:
        # Write error info if we can't access runs
        (dest / "error.txt").write_text(f"Could not collect runs: {e}")


def _collect_plans(dest: Path) -> None:
    """Collect recent plan snapshots."""
    dest.mkdir(parents=True, exist_ok=True)

    try:
        from sunwell.planning.naaru.persistence import PlanStore

        store = PlanStore()
        plans = store.list_recent(limit=DUMP_LIMITS["runs"])

        for plan in plans:
            plan_data = plan.to_dict()
            # Sanitize any potential secrets in goal text
            plan_data["goal"], _ = _sanitize(plan_data.get("goal", ""))

            plan_file = dest / f"plan-{plan.goal_hash[:8]}.json"
            plan_file.write_text(json.dumps(plan_data, indent=2))

    except Exception as e:
        (dest / "error.txt").write_text(f"Could not collect plans: {e}")


def _collect_simulacrum(dest: Path) -> None:
    """Collect simulacrum memory state."""
    sim_path = Path.cwd() / ".sunwell" / "simulacrum.json"

    if sim_path.exists():
        content = sim_path.read_text()
        sanitized, _ = _sanitize(content)
        dest.write_text(sanitized)
    else:
        # Try memory store location
        memory_path = Path.cwd() / ".sunwell" / "memory"
        if memory_path.exists():
            # Collect summary stats only
            stats = {
                "exists": True,
                "path": str(memory_path),
                "files": len(list(memory_path.glob("**/*.json"))),
            }
            dest.write_text(json.dumps(stats, indent=2))
        else:
            dest.write_text(json.dumps({"exists": False}))


def _collect_logs(dest: Path) -> None:
    """Collect recent log output."""
    log_paths = [
        Path.cwd() / ".sunwell" / "agent.log",
        Path.cwd() / ".sunwell" / "sunwell.log",
        Path.home() / ".sunwell" / "agent.log",
    ]

    log_content = ""
    for log_path in log_paths:
        if log_path.exists():
            lines = log_path.read_text().splitlines()
            # Take last N lines
            lines = lines[-DUMP_LIMITS["log_lines"] :]
            log_content = "\n".join(lines)
            break

    if not log_content:
        log_content = "# No log file found"

    # Sanitize
    sanitized, _ = _sanitize(log_content)
    dest.write_text(sanitized)


def _collect_system(dest: Path) -> None:
    """Collect system information."""
    dest.mkdir(parents=True, exist_ok=True)

    # Disk usage
    try:
        total, used, free = shutil.disk_usage(Path.cwd())
        disk_info = f"""Disk Usage for {Path.cwd()}:
Total: {total // (1024**3)} GB
Used:  {used // (1024**3)} GB
Free:  {free // (1024**3)} GB
"""
        (dest / "disk.txt").write_text(disk_info)
    except Exception as e:
        (dest / "disk.txt").write_text(f"Error: {e}")

    # Memory (platform-specific)
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5
            )
            (dest / "memory.txt").write_text(result.stdout)
        elif platform.system() == "Linux":
            mem_info = Path("/proc/meminfo").read_text()
            (dest / "memory.txt").write_text(mem_info)
        else:
            (dest / "memory.txt").write_text(f"Platform: {platform.system()}")
    except Exception as e:
        (dest / "memory.txt").write_text(f"Error: {e}")

    # Relevant processes
    try:
        if platform.system() in ("Darwin", "Linux"):
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Filter to relevant processes
            lines = result.stdout.splitlines()
            header = lines[0] if lines else ""
            relevant = [
                line
                for line in lines[1:]
                if any(
                    term in line.lower()
                    for term in ["sunwell", "python", "ollama", "node"]
                )
            ]
            (dest / "processes.txt").write_text(header + "\n" + "\n".join(relevant))
        else:
            (dest / "processes.txt").write_text(f"Platform: {platform.system()}")
    except Exception as e:
        (dest / "processes.txt").write_text(f"Error: {e}")


# =============================================================================
# Helpers
# =============================================================================


def _sanitize(content: str) -> tuple[str, list[str]]:
    """Sanitize content by removing secrets.

    Returns (sanitized_content, list_of_secret_types_found).
    """
    found: list[str] = []

    for pattern in SANITIZE_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # Extract the type of secret from the pattern
            if "ANTHROPIC" in pattern:
                found.append("ANTHROPIC_API_KEY")
            elif "OPENAI" in pattern:
                found.append("OPENAI_API_KEY")
            elif "Bearer" in pattern:
                found.append("Bearer token")
            elif "sk-ant" in pattern:
                found.append("Anthropic key")
            elif "sk-" in pattern:
                found.append("API key")
            else:
                found.append("secret")

            content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)

    return content, list(set(found))


def _read_jsonl(path: Path, limit: int) -> list[dict]:
    """Read JSONL file with limit."""
    events = []
    try:
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                if len(events) >= limit:
                    break
    except Exception:
        pass
    return events


def _write_jsonl(dest: Path, events: list[dict], total_available: int) -> None:
    """Write JSONL with truncation marker if needed."""
    with open(dest, "w") as f:
        if len(events) < total_available:
            # Add truncation marker
            marker = {
                "_truncated": True,
                "_total": total_available,
                "_included": len(events),
            }
            f.write(json.dumps(marker) + "\n")

        for event in events:
            f.write(json.dumps(event) + "\n")
