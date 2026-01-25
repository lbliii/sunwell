"""Self-Knowledge CLI commands (RFC-085).

Provides CLI access to Sunwell's self-knowledge capabilities:
- Source introspection
- Analysis patterns
- Proposal management

Example:
    >>> sunwell self source list  # List all modules
    >>> sunwell self source read sunwell.tools.executor  # Read module source
    >>> sunwell self analysis patterns --scope session  # Get usage patterns
    >>> sunwell self proposals list  # List proposals
"""


import json
import sys
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    pass


@click.group()
def self_cmd() -> None:
    """Self-knowledge and introspection commands (RFC-085)."""
    pass


# =============================================================================
# Source Commands
# =============================================================================


@self_cmd.group()
def source() -> None:
    """Source code introspection commands."""
    pass


@source.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def source_list(as_json: bool) -> None:
    """List all Sunwell modules."""
    from sunwell.self import Self

    modules = Self.get().source.list_modules()

    if as_json:
        click.echo(json.dumps(modules))
    else:
        click.echo("Sunwell Modules:")
        for module in sorted(modules):
            click.echo(f"  {module}")


@source.command("read")
@click.argument("module")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def source_read(module: str, as_json: bool) -> None:
    """Read source code for a module."""
    from sunwell.self import Self

    try:
        source_code = Self.get().source.read_module(module)
        if as_json:
            click.echo(json.dumps({"module": module, "source": source_code}))
        else:
            click.echo(source_code)
    except FileNotFoundError as e:
        if as_json:
            click.echo(json.dumps({"error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@source.command("find")
@click.argument("module")
@click.argument("symbol")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def source_find(module: str, symbol: str, as_json: bool) -> None:
    """Find a symbol in a module."""
    from sunwell.self import Self

    result = Self.get().source.find_symbol(module, symbol)

    if result is None:
        if as_json:
            click.echo(json.dumps({"error": f"Symbol '{symbol}' not found in '{module}'"}))
        else:
            click.echo(f"Symbol '{symbol}' not found in '{module}'", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps({
            "name": result.name,
            "kind": result.kind,
            "line": result.line,
            "signature": result.signature,
            "docstring": result.docstring,
        }))
    else:
        click.echo(f"Symbol: {result.name}")
        click.echo(f"Kind: {result.kind}")
        click.echo(f"Line: {result.line}")
        if result.signature:
            click.echo(f"Signature: {result.signature}")
        if result.docstring:
            click.echo(f"Docstring: {result.docstring[:200]}...")


@source.command("search")
@click.argument("query")
@click.option("--limit", default=10, help="Max results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def source_search(query: str, limit: int, as_json: bool) -> None:
    """Semantic search in Sunwell source code."""
    from sunwell.self import Self

    results = Self.get().source.search(query, limit=limit)

    if as_json:
        click.echo(json.dumps([
            {
                "module": r.module,
                "symbol": r.symbol,
                "score": r.score,
                "snippet": r.snippet,
            }
            for r in results
        ]))
    else:
        click.echo(f"Search results for '{query}':")
        for r in results:
            click.echo(f"  [{r.score:.2f}] {r.module}::{r.symbol}")
            click.echo(f"         {r.snippet[:80]}...")


# =============================================================================
# Analysis Commands
# =============================================================================


@self_cmd.group()
def analysis() -> None:
    """Execution analysis commands."""
    pass


@analysis.command("patterns")
@click.option("--scope", default="session", help="Analysis scope (session, day, all)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def analysis_patterns(scope: str, as_json: bool) -> None:
    """Analyze tool usage patterns."""
    from sunwell.self import Self

    report = Self.get().analysis.analyze_patterns()

    if as_json:
        click.echo(json.dumps({
            "tool_frequencies": report.tool_frequencies,
            "avg_latency_ms": report.avg_latency_ms,
            "error_rate": report.error_rate,
            "top_errors": report.top_errors,
        }))
    else:
        click.echo("Tool Usage Patterns:")
        click.echo(f"  Average latency: {report.avg_latency_ms:.0f}ms")
        click.echo(f"  Error rate: {report.error_rate:.1%}")
        if report.tool_frequencies:
            click.echo("\n  Tool frequencies:")
            for tool, count in sorted(
                report.tool_frequencies.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]:
                click.echo(f"    {tool}: {count}")


@analysis.command("failures")
@click.option("--limit", default=20, help="Max failures to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def analysis_failures(limit: int, as_json: bool) -> None:
    """Get recent failures."""
    from sunwell.self import Self

    failures = Self.get().analysis.get_recent_failures(limit=limit)

    if as_json:
        click.echo(json.dumps({
            "total_failures": len(failures),
            "by_category": {},  # Would need to compute
            "recent": [
                {
                    "tool_name": f.tool_name,
                    "error": f.error,
                    "timestamp": f.timestamp.isoformat() if f.timestamp else None,
                }
                for f in failures
            ],
        }))
    else:
        click.echo(f"Recent Failures ({len(failures)}):")
        for f in failures:
            click.echo(f"  [{f.tool_name}] {f.error}")


# =============================================================================
# Proposals Commands
# =============================================================================


@self_cmd.group()
def proposals() -> None:
    """Self-improvement proposal commands."""
    pass


@proposals.command("list")
@click.option("--status", help="Filter by status (draft, approved, applied, rejected)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def proposals_list(status: str | None, as_json: bool) -> None:
    """List all proposals."""
    from sunwell.self import Self
    from sunwell.self.types import ProposalStatus

    all_proposals = Self.get().proposals.list_proposals()

    if status:
        status_enum = ProposalStatus(status)
        all_proposals = [p for p in all_proposals if p.status == status_enum]

    if as_json:
        click.echo(json.dumps([
            {
                "id": p.id,
                "title": p.title,
                "status": p.status.value,
                "created_at": p.created_at.isoformat(),
                "files_changed": len(p.changes),
            }
            for p in all_proposals
        ]))
    else:
        click.echo(f"Proposals ({len(all_proposals)}):")
        for p in all_proposals:
            status_icon = {
                "draft": "📝",
                "approved": "✅",
                "applied": "🚀",
                "rejected": "❌",
                "rolled_back": "↩️",
            }.get(p.status.value, "❓")
            click.echo(f"  {status_icon} [{p.id[:8]}] {p.title} ({p.status.value})")


@proposals.command("show")
@click.argument("proposal_id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def proposals_show(proposal_id: str, as_json: bool) -> None:
    """Show details for a proposal."""
    from sunwell.self import Self

    proposal = Self.get().proposals.get_proposal(proposal_id)

    if proposal is None:
        click.echo(f"Proposal '{proposal_id}' not found", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps({
            "id": proposal.id,
            "title": proposal.title,
            "description": proposal.description,
            "status": proposal.status.value,
            "changes": [
                {
                    "path": c.path,
                    "change_type": c.change_type,
                    "diff_preview": c.diff[:500] if c.diff else None,
                }
                for c in proposal.changes
            ],
            "test_result": {
                "passed": proposal.test_result.passed,
                "tests_run": proposal.test_result.tests_run,
                "tests_passed": proposal.test_result.tests_passed,
                "tests_failed": proposal.test_result.tests_failed,
                "duration_ms": proposal.test_result.duration_ms,
            } if proposal.test_result else None,
            "created_at": proposal.created_at.isoformat(),
        }))
    else:
        click.echo(f"Proposal: {proposal.title}")
        click.echo(f"ID: {proposal.id}")
        click.echo(f"Status: {proposal.status.value}")
        click.echo(f"Description: {proposal.description}")
        click.echo(f"\nChanges ({len(proposal.changes)}):")
        for c in proposal.changes:
            click.echo(f"  {c.change_type}: {c.path}")


@proposals.command("test")
@click.argument("proposal_id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def proposals_test(proposal_id: str, as_json: bool) -> None:
    """Test a proposal in the sandbox."""
    from sunwell.self import Self

    proposal = Self.get().proposals.get_proposal(proposal_id)
    if proposal is None:
        click.echo(f"Proposal '{proposal_id}' not found", err=True)
        sys.exit(1)

    click.echo("Testing proposal in sandbox...", err=True)
    result = Self.get().proposals.test(proposal)

    if as_json:
        click.echo(json.dumps({
            "passed": result.passed,
            "tests_run": result.tests_run,
            "tests_passed": result.tests_passed,
            "tests_failed": result.tests_failed,
            "duration_ms": result.duration_ms,
        }))
    else:
        status = "✅ PASSED" if result.passed else "❌ FAILED"
        click.echo(f"\nTest Result: {status}")
        click.echo(f"  Tests run: {result.tests_run}")
        click.echo(f"  Passed: {result.tests_passed}")
        click.echo(f"  Failed: {result.tests_failed}")
        click.echo(f"  Duration: {result.duration_ms}ms")


@proposals.command("approve")
@click.argument("proposal_id")
def proposals_approve(proposal_id: str) -> None:
    """Approve a proposal for application."""
    from sunwell.self import Self

    proposal = Self.get().proposals.approve(proposal_id)
    click.echo(f"✅ Proposal '{proposal.title}' approved")


@proposals.command("apply")
@click.argument("proposal_id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def proposals_apply(proposal_id: str, as_json: bool) -> None:
    """Apply an approved proposal."""
    from sunwell.self import Self

    proposal = Self.get().proposals.get_proposal(proposal_id)
    if proposal is None:
        click.echo(f"Proposal '{proposal_id}' not found", err=True)
        sys.exit(1)

    result = Self.get().proposals.apply(proposal)

    if as_json:
        click.echo(json.dumps({
            "success": result.success,
            "commit_hash": result.commit_hash,
            "message": result.message,
        }))
    else:
        if result.success:
            click.echo("✅ Applied successfully")
            if result.commit_hash:
                click.echo(f"   Commit: {result.commit_hash}")
        else:
            click.echo(f"❌ Failed: {result.message}")
            sys.exit(1)


@proposals.command("rollback")
@click.argument("proposal_id")
def proposals_rollback(proposal_id: str) -> None:
    """Rollback an applied proposal."""
    from sunwell.self import Self

    proposal = Self.get().proposals.get_proposal(proposal_id)
    if proposal is None:
        click.echo(f"Proposal '{proposal_id}' not found", err=True)
        sys.exit(1)

    result = Self.get().proposals.rollback(proposal)

    if result.success:
        click.echo("↩️ Rolled back successfully")
        if result.commit_hash:
            click.echo(f"   Commit: {result.commit_hash}")
    else:
        click.echo(f"❌ Failed: {result.message}")
        sys.exit(1)


# =============================================================================
# Summary Command
# =============================================================================


@self_cmd.command("summary")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def summary(as_json: bool) -> None:
    """Get self-knowledge summary for dashboard."""
    from sunwell.self import Self
    from sunwell.self.types import ProposalStatus

    self_instance = Self.get()

    modules = self_instance.source.list_modules()
    proposals = self_instance.proposals.list_proposals()

    pending = sum(1 for p in proposals if p.status == ProposalStatus.DRAFT)
    applied = sum(1 for p in proposals if p.status == ProposalStatus.APPLIED)

    # Get execution stats
    patterns = self_instance.analysis.analyze_patterns()

    if as_json:
        click.echo(json.dumps({
            "modules_count": len(modules),
            "recent_executions": sum(patterns.tool_frequencies.values()),
            "error_rate": patterns.error_rate,
            "pending_proposals": pending,
            "applied_proposals": applied,
            "source_root": str(self_instance._source_root),
        }))
    else:
        click.echo("Self-Knowledge Summary")
        click.echo("=" * 40)
        click.echo(f"Source root: {self_instance._source_root}")
        click.echo(f"Modules: {len(modules)}")
        click.echo(f"Recent executions: {sum(patterns.tool_frequencies.values())}")
        click.echo(f"Error rate: {patterns.error_rate:.1%}")
        click.echo(f"Proposals: {pending} pending, {applied} applied")
