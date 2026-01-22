"""CLI commands for Security-First Skill Execution (RFC-089).

Provides:
- sunwell security analyze: Analyze DAG/skill permissions before execution
- sunwell security approve: Interactive approval flow
- sunwell security audit: Query audit log
- sunwell security verify: Verify audit log integrity
- sunwell security scan: Scan content for security issues
- sunwell security policy: Show/validate security policy
"""


import hashlib
import json as json_lib
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def security() -> None:
    """Security-First Skill Execution — Declarative permission graphs.

    Skills declare exact permissions. Before execution, you see the complete
    permission scope. Runtime sandboxes enforce boundaries. Audit logs track
    everything.

    Examples:

        sunwell security analyze my-dag          # Analyze DAG permissions
        sunwell security approve                 # Interactive approval
        sunwell security audit                   # View audit log
        sunwell security verify                  # Verify audit integrity
        sunwell security scan --file output.txt # Scan for security issues
    """
    pass


# =============================================================================
# ANALYZE COMMAND
# =============================================================================


@security.command()
@click.argument("target", required=False)
@click.option("--skill", "-s", help="Analyze a specific skill by name")
@click.option("--dag", "-d", help="Analyze a DAG by ID")
@click.option("--lens", "-l", help="Lens file to load skills from")
@click.option("--detailed", is_flag=True, help="Include per-skill breakdown")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def analyze(
    ctx,
    target: str | None,
    skill: str | None,
    dag: str | None,
    lens: str | None,
    detailed: bool,
    json_output: bool,
) -> None:
    """Analyze permissions and risk for a skill or DAG.

    Shows the complete permission scope and risk assessment before execution.

    Examples:

        sunwell security analyze                   # Analyze current lens
        sunwell security analyze --skill deploy    # Analyze specific skill
        sunwell security analyze --lens my.lens    # Analyze lens file
        sunwell security analyze my-dag --json     # JSON output for CI
    """
    from sunwell.security.analyzer import PermissionAnalyzer, PermissionScope

    analyzer = PermissionAnalyzer()

    # Load skills from lens if specified
    if lens or target:
        lens_path = Path(lens or target or ".")
        skills = _load_skills_from_lens(lens_path)

        if not skills:
            console.print(f"[red]No skills found in {lens_path}[/red]")
            return

        # Filter to specific skill if requested
        if skill:
            skills = [s for s in skills if s.name == skill]
            if not skills:
                console.print(f"[red]Skill '{skill}' not found[/red]")
                return

        # Analyze each skill
        total_scope = PermissionScope()
        all_flags: list[str] = []

        for s in skills:
            scope, risk = analyzer.analyze_skill(s)
            total_scope = total_scope.merge_with(scope)
            all_flags.extend(risk.flags)

        # Compute overall risk
        final_risk = analyzer._compute_risk(total_scope, all_flags)

        if detailed:
            analysis = analyzer.analyze_skills_detailed(skills)

            if json_output:
                dag_name = _derive_dag_name(lens_path)
                dag_id = _compute_dag_id(skills)
                output = _build_detailed_output(dag_id, dag_name, analysis)
                console.print(json_lib.dumps(output, indent=2))
                return

            _print_skill_breakdown(analysis)
            _print_permission_analysis(
                skills, analysis.aggregated_permissions, analysis.aggregated_risk
            )
            return

        if json_output:
            output = {
                "skills": len(skills),
                "permissions": total_scope.to_dict(),
                "risk": final_risk.to_dict(),
            }
            console.print(json_lib.dumps(output, indent=2))
            return

        # Human-readable output
        _print_permission_analysis(skills, total_scope, final_risk)

    else:
        console.print("[yellow]No target specified. Use --lens, --skill, or provide a path.[/yellow]")
        console.print("\nExamples:")
        console.print("  sunwell security analyze --lens coder.lens")
        console.print("  sunwell security analyze ./skills/deploy.skill.yaml")


def _load_skills_from_lens(path: Path) -> list:
    """Load skills from a lens file."""
    from sunwell.skills.types import Skill, SkillType

    if not path.exists():
        # Try finding in standard locations
        for loc in [Path.cwd(), Path.home() / ".sunwell" / "lenses"]:
            candidate = loc / path
            if candidate.exists():
                path = candidate
                break

    if not path.exists():
        return []

    # Try to parse as YAML lens
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            return []

        # Extract skills from lens structure
        skills_data = data.get("skills", [])
        skills = []

        for s in skills_data:
            try:
                skills.append(
                    Skill(
                        name=s.get("name", "unknown"),
                        description=s.get("description", ""),
                        skill_type=SkillType.INLINE,
                        instructions=s.get("instructions", ""),
                        preset=s.get("preset"),
                        permissions=s.get("permissions"),
                        security=s.get("security"),
                    )
                )
            except Exception:
                continue

        return skills

    except Exception:
        return []


def _print_permission_analysis(skills, scope, risk) -> None:
    """Print human-readable permission analysis."""
    # Header
    risk_colors = {
        "low": "green",
        "medium": "yellow",
        "high": "orange1",
        "critical": "red",
    }
    color = risk_colors.get(risk.level, "white")

    console.print()


def _print_skill_breakdown(analysis) -> None:
    """Print per-skill permission breakdown."""
    if not analysis.skill_breakdown:
        return

    console.print("\n[bold]Skill Breakdown:[/bold]\n")
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", width=3)
    table.add_column("Skill", style="cyan", width=20)
    table.add_column("Preset", style="dim", width=16)
    table.add_column("Read", width=6)
    table.add_column("Write", width=6)
    table.add_column("Net", width=6)
    table.add_column("Shell", width=6)
    table.add_column("Risk", width=8)

    highest_risk = analysis.highest_risk_skill

    for i, entry in enumerate(analysis.skill_breakdown, start=1):
        permissions = entry.permissions
        risk_label = entry.risk_contribution
        if entry.skill_name == highest_risk:
            risk_label = f"{risk_label} ⚠️"

        table.add_row(
            str(i),
            entry.skill_name,
            entry.preset or "-",
            "✅" if permissions.filesystem_read else "❌",
            "✅" if permissions.filesystem_write else "❌",
            "✅" if permissions.network_allow else "❌",
            "✅" if permissions.shell_allow else "❌",
            risk_label,
        )

    console.print(table)

    if highest_risk:
        console.print(f"\n⚠️ Highest risk: {highest_risk}")


def _compute_dag_id(skills) -> str:
    """Compute a stable DAG ID based on skill names."""
    names = sorted(s.name for s in skills)
    content = "|".join(names)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _derive_dag_name(lens_path: Path) -> str:
    """Derive a human-readable DAG name from the lens path."""
    return lens_path.stem if lens_path.name else "unknown"


def _scope_to_api_dict(scope) -> dict[str, list[str]]:
    """Convert a PermissionScope to API (camelCase) dict."""
    return {
        "filesystemRead": sorted(scope.filesystem_read),
        "filesystemWrite": sorted(scope.filesystem_write),
        "networkAllow": sorted(scope.network_allow),
        "networkDeny": sorted(scope.network_deny),
        "shellAllow": sorted(scope.shell_allow),
        "shellDeny": sorted(scope.shell_deny),
        "envRead": sorted(scope.env_read),
        "envWrite": sorted(scope.env_write),
    }


def _build_detailed_output(dag_id: str, dag_name: str, analysis) -> dict:
    """Build detailed security approval JSON payload."""
    breakdown = [
        {
            "skillName": entry.skill_name,
            "preset": entry.preset,
            "permissions": _scope_to_api_dict(entry.permissions),
            "riskContribution": entry.risk_contribution,
            "riskReason": entry.risk_reason,
        }
        for entry in analysis.skill_breakdown
    ]

    output = {
        "dagId": dag_id,
        "dagName": dag_name,
        "skillCount": len(analysis.skill_breakdown),
        "permissions": _scope_to_api_dict(analysis.aggregated_permissions),
        "risk": analysis.aggregated_risk.to_dict(),
        "timestamp": datetime.now().isoformat(),
        "skillBreakdown": breakdown,
    }

    if analysis.highest_risk_skill:
        output["highestRiskSkill"] = analysis.highest_risk_skill

    return output
    console.print(
        Panel(
            f"[bold]Permission Analysis[/bold]\n"
            f"Skills: {len(skills)} | "
            f"Risk: [{color}]{risk.level.upper()}[/{color}] ({risk.score:.0%})",
            title="🔒 Security Analysis",
        )
    )

    # Permissions table
    if not scope.is_empty():
        console.print("\n[bold]Permissions Requested:[/bold]")

        if scope.filesystem_read:
            console.print("\n  📁 [cyan]Filesystem Read:[/cyan]")
            for p in sorted(scope.filesystem_read):
                console.print(f"     {p}")

        if scope.filesystem_write:
            console.print("\n  ✏️  [yellow]Filesystem Write:[/yellow]")
            for p in sorted(scope.filesystem_write):
                console.print(f"     {p}")

        if scope.network_allow:
            console.print("\n  🌐 [blue]Network:[/blue]")
            for h in sorted(scope.network_allow):
                console.print(f"     {h}")

        if scope.shell_allow:
            console.print("\n  💻 [magenta]Shell Commands:[/magenta]")
            for c in sorted(scope.shell_allow):
                console.print(f"     {c}")

        if scope.env_read:
            console.print("\n  🔑 [cyan]Environment Read:[/cyan]")
            for e in sorted(scope.env_read):
                console.print(f"     {e}")

    else:
        console.print("\n  [dim]No permissions declared (ambient mode)[/dim]")

    # Risk flags
    if risk.flags:
        console.print("\n[bold red]⚠️  Risk Flags:[/bold red]")
        for flag in risk.flags:
            console.print(f"  • {flag}")

    # Recommendations
    if risk.recommendations:
        console.print("\n[bold]💡 Recommendations:[/bold]")
        for rec in risk.recommendations:
            console.print(f"  • {rec}")

    console.print()


# =============================================================================
# APPROVE COMMAND
# =============================================================================


@security.command()
@click.option("--dag", "-d", help="DAG ID to approve")
@click.option("--remember", is_flag=True, help="Remember approval for session")
@click.option("--trust-all", is_flag=True, help="Bypass security checks (DANGEROUS)")
@click.option("--json", "json_output", is_flag=True, help="Read JSON from stdin")
@click.pass_context
def approve(
    ctx,
    dag: str | None,
    remember: bool,
    trust_all: bool,
    json_output: bool,
) -> None:
    """Interactive approval flow for DAG execution.

    Reviews permissions and prompts for user approval.

    Examples:

        sunwell security approve --dag my-dag
        sunwell security approve --trust-all     # DANGEROUS: bypass all checks
        echo '{"dagId": "x", "approved": true}' | sunwell security approve --json
    """
    if trust_all:
        console.print(
            Panel(
                "[bold red]⚠️  TRUST ALL MODE[/bold red]\n\n"
                "This bypasses ALL security checks. The agent will have:\n"
                "• Full filesystem access\n"
                "• Unrestricted network access\n"
                "• Any shell command execution\n\n"
                "This action will be logged to the audit trail.",
                title="🚨 Security Warning",
                border_style="red",
            )
        )

        if not click.confirm("Are you sure you want to proceed?", default=False):
            console.print("Cancelled")
            return

        # Log to audit
        _log_trust_all_approval()
        console.print("[yellow]Trust-all mode enabled for this session[/yellow]")
        return

    if json_output:
        # Read JSON from stdin
        try:
            data = json_lib.load(sys.stdin)
            dag_id = data.get("dagId", "")
            approved = data.get("approved", False)

            if approved:
                console.print(json_lib.dumps({"success": True, "dagId": dag_id}))
            else:
                console.print(json_lib.dumps({"success": False, "dagId": dag_id}))
            return

        except Exception as e:
            console.print(json_lib.dumps({"error": str(e)}))
            sys.exit(1)

    if dag:
        # Interactive approval for specific DAG
        console.print(f"[yellow]Interactive approval for DAG: {dag}[/yellow]")
        console.print("[dim]Use 'sunwell security analyze' to review permissions first[/dim]")

        if click.confirm("Approve execution?", default=True):
            if remember:
                console.print("[green]✓ Approved and remembered for session[/green]")
            else:
                console.print("[green]✓ Approved[/green]")
        else:
            console.print("[red]✗ Rejected[/red]")
    else:
        console.print("[yellow]No DAG specified. Use --dag <dag-id>[/yellow]")


def _log_trust_all_approval() -> None:
    """Log trust-all approval to audit."""
    from sunwell.security.analyzer import PermissionScope
    from sunwell.security.audit import AuditLogManager, LocalAuditLog

    audit_path = Path.home() / ".sunwell" / "security" / "audit.log"
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    key = os.environ.get("SUNWELL_AUDIT_KEY", "sunwell-default-key").encode()
    backend = LocalAuditLog(audit_path, key)
    manager = AuditLogManager(backend)

    manager.record_execution(
        skill_name="trust-all",
        dag_id="cli-session",
        permissions=PermissionScope(),
        inputs_hash="",
        outputs_hash=None,
        details="Trust-all mode enabled via CLI",
    )


# =============================================================================
# AUDIT COMMAND
# =============================================================================


@security.command()
@click.option("--skill", "-s", help="Filter by skill name")
@click.option("--action", "-a", type=click.Choice(["execute", "violation", "denied", "error"]),
              help="Filter by action type")
@click.option("--since", help="Show entries since (ISO date or relative like '1h', '1d')")
@click.option("--limit", "-n", default=50, help="Maximum entries to show")
@click.option("--verify", is_flag=True, help="Verify audit log integrity")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def audit(
    ctx,
    skill: str | None,
    action: str | None,
    since: str | None,
    limit: int,
    verify: bool,
    json_output: bool,
) -> None:
    """Query the security audit log.

    Shows recent security events with filtering options.

    Examples:

        sunwell security audit                     # Recent entries
        sunwell security audit --skill deploy      # Filter by skill
        sunwell security audit --action violation  # Show violations only
        sunwell security audit --since 1d          # Last 24 hours
        sunwell security audit --verify            # Verify integrity
    """
    from sunwell.security.audit import LocalAuditLog

    audit_path = Path.home() / ".sunwell" / "security" / "audit.log"

    if not audit_path.exists():
        if json_output:
            console.print(json_lib.dumps({"entries": [], "message": "No audit log exists"}))
        else:
            console.print("[dim]No audit log exists yet[/dim]")
        return

    key = os.environ.get("SUNWELL_AUDIT_KEY", "sunwell-default-key").encode()
    backend = LocalAuditLog(audit_path, key)

    if verify:
        valid, message = backend.verify_integrity()

        if json_output:
            console.print(json_lib.dumps({"valid": valid, "message": message}))
        else:
            if valid:
                console.print(f"[green]✓ {message}[/green]")
            else:
                console.print(f"[red]✗ {message}[/red]")
        return

    # Parse since filter
    since_dt = None
    if since:
        since_dt = _parse_since(since)

    # Query entries
    entries = list(backend.query(
        skill_name=skill,
        action=action,
        since=since_dt,
        limit=limit,
    ))

    if json_output:
        output = [e.to_dict() for e in entries]
        console.print(json_lib.dumps(output, indent=2, default=str))
        return

    # Human-readable output
    if not entries:
        console.print("[dim]No matching audit entries[/dim]")
        return

    console.print(f"\n🔐 [bold]Security Audit Log[/bold] ({len(entries)} entries)\n")

    table = Table()
    table.add_column("Time", style="dim", width=16)
    table.add_column("Skill", style="cyan", width=15)
    table.add_column("Action", width=10)
    table.add_column("Details", no_wrap=False)

    action_styles = {
        "execute": "[green]execute[/green]",
        "violation": "[red]violation[/red]",
        "denied": "[yellow]denied[/yellow]",
        "error": "[orange1]error[/orange1]",
    }

    for entry in entries[:limit]:
        time_str = entry.timestamp.strftime("%m-%d %H:%M:%S")
        action_str = action_styles.get(entry.action, entry.action)
        details = entry.details[:60] + "..." if len(entry.details) > 60 else entry.details

        table.add_row(time_str, entry.skill_name, action_str, details)

    console.print(table)


def _parse_since(since: str) -> datetime:
    """Parse 'since' argument to datetime."""
    from datetime import timedelta

    # Try relative formats: 1h, 2d, 30m
    if since[-1] in ("h", "d", "m"):
        try:
            value = int(since[:-1])
            unit = since[-1]

            if unit == "h":
                return datetime.now() - timedelta(hours=value)
            elif unit == "d":
                return datetime.now() - timedelta(days=value)
            elif unit == "m":
                return datetime.now() - timedelta(minutes=value)
        except ValueError:
            pass

    # Try ISO format
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        pass

    # Default to 24 hours ago
    return datetime.now() - timedelta(days=1)


# =============================================================================
# VERIFY COMMAND (alias for audit --verify)
# =============================================================================


@security.command("verify")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def verify_cmd(ctx, json_output: bool) -> None:
    """Verify audit log integrity.

    Checks that the audit chain is intact and signatures are valid.

    Examples:

        sunwell security verify
        sunwell security verify --json   # For CI integration
    """
    ctx.invoke(audit, verify=True, json_output=json_output)


# =============================================================================
# SCAN COMMAND
# =============================================================================


@security.command()
@click.option("--file", "-f", "file_path", type=click.Path(exists=True),
              help="File to scan")
@click.option("--stdin", is_flag=True, help="Read content from stdin")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def scan(ctx, file_path: str | None, stdin: bool, json_output: bool) -> None:
    """Scan content for security issues.

    Detects credential leaks, path traversal, shell injection, and PII.

    Examples:

        sunwell security scan --file output.log
        cat output.txt | sunwell security scan --stdin
        sunwell security scan --file log.txt --json
    """
    from sunwell.security.analyzer import PermissionScope
    from sunwell.security.monitor import SecurityMonitor

    monitor = SecurityMonitor()

    # Get content
    if stdin:
        content = sys.stdin.read()
    elif file_path:
        with open(file_path) as f:
            content = f.read()
    else:
        console.print("[yellow]Specify --file or --stdin[/yellow]")
        return

    # Scan
    permissions = PermissionScope()
    violations = monitor.scan_content(content, permissions)

    if json_output:
        output = [v.to_dict() for v in violations]
        console.print(json_lib.dumps(output, indent=2))
        return

    # Human-readable output
    if not violations:
        console.print("[green]✓ No security issues detected[/green]")
        return

    console.print(f"\n[red]⚠️  Found {len(violations)} security issue(s)[/red]\n")

    for v in violations:
        type_icons = {
            "credential_leak": "🔑",
            "path_traversal": "📁",
            "shell_injection": "💻",
            "pii_exposure": "👤",
        }
        icon = type_icons.get(v.type, "⚠️")

        console.print(f"  {icon} [bold]{v.type}[/bold]")
        console.print(f"     Content: {v.content[:50]}...")
        console.print(f"     Position: {v.position}")
        console.print()


# =============================================================================
# POLICY COMMAND
# =============================================================================


@security.command()
@click.option("--validate", is_flag=True, help="Validate policy file")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def policy(ctx, validate: bool, json_output: bool) -> None:
    """Show or validate security policy.

    Security policies define organization-wide security rules.

    Examples:

        sunwell security policy                  # Show current policy
        sunwell security policy --validate       # Validate policy file
    """
    policy_path = Path.cwd() / ".sunwell" / "security-policy.yaml"

    if not policy_path.exists():
        policy_path = Path.home() / ".sunwell" / "security-policy.yaml"

    if not policy_path.exists():
        if json_output:
            console.print(json_lib.dumps({"policy": None, "message": "No policy file found"}))
        else:
            console.print("[dim]No security policy file found[/dim]")
            console.print("\nCreate one at:")
            console.print("  .sunwell/security-policy.yaml (project)")
            console.print("  ~/.sunwell/security-policy.yaml (global)")
        return

    # Load and display policy
    try:
        import yaml

        with open(policy_path) as f:
            policy_data = yaml.safe_load(f)

        if validate:
            # Validate policy structure
            errors = _validate_policy(policy_data)
            if errors:
                if json_output:
                    console.print(json_lib.dumps({"valid": False, "errors": errors}))
                else:
                    console.print("[red]Policy validation failed:[/red]")
                    for e in errors:
                        console.print(f"  • {e}")
            else:
                if json_output:
                    console.print(json_lib.dumps({"valid": True}))
                else:
                    console.print("[green]✓ Policy is valid[/green]")
            return

        if json_output:
            console.print(json_lib.dumps(policy_data, indent=2))
            return

        # Human-readable output
        console.print(f"\n🛡️ [bold]Security Policy[/bold] ({policy_path})\n")

        if "policies" in policy_data:
            for p in policy_data["policies"]:
                console.print(f"  [cyan]{p.get('name', 'unnamed')}[/cyan]")
                if "environments" in p:
                    console.print(f"    Environments: {', '.join(p['environments'])}")
                if "deny" in p:
                    for k, v in p["deny"].items():
                        console.print(f"    Deny {k}: {v}")
                if "recommend" in p:
                    console.print(f"    Recommend: {p['recommend']}")
                console.print()

    except Exception as e:
        if json_output:
            console.print(json_lib.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading policy: {e}[/red]")


def _validate_policy(policy_data: dict) -> list[str]:
    """Validate security policy structure."""
    errors = []

    if not isinstance(policy_data, dict):
        return ["Policy must be a YAML dictionary"]

    if "version" not in policy_data:
        errors.append("Missing 'version' field")

    if "policies" not in policy_data:
        errors.append("Missing 'policies' field")
    elif not isinstance(policy_data["policies"], list):
        errors.append("'policies' must be a list")
    else:
        for i, p in enumerate(policy_data["policies"]):
            if "name" not in p:
                errors.append(f"Policy {i}: missing 'name'")
            if "deny" not in p and "require_approval" not in p:
                errors.append(f"Policy {i}: must have 'deny' or 'require_approval'")

    return errors


# =============================================================================
# DIFF COMMAND
# =============================================================================


@security.command()
@click.argument("old_lens", type=click.Path(exists=True))
@click.argument("new_lens", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def diff(ctx, old_lens: str, new_lens: str, json_output: bool) -> None:
    """Compare permissions between two lens versions.

    Shows what permissions were added, removed, or changed.

    Examples:

        sunwell security diff old.lens new.lens
        sunwell security diff v1.lens v2.lens --json
    """
    from sunwell.security.analyzer import PermissionAnalyzer

    analyzer = PermissionAnalyzer()

    old_skills = _load_skills_from_lens(Path(old_lens))
    new_skills = _load_skills_from_lens(Path(new_lens))

    # Compute permission scopes
    from sunwell.security.analyzer import PermissionScope

    old_scope = PermissionScope()
    for s in old_skills:
        scope, _ = analyzer.analyze_skill(s)
        old_scope = old_scope.merge_with(scope)

    new_scope = PermissionScope()
    for s in new_skills:
        scope, _ = analyzer.analyze_skill(s)
        new_scope = new_scope.merge_with(scope)

    # Compute diffs
    added = {
        "filesystem_read": new_scope.filesystem_read - old_scope.filesystem_read,
        "filesystem_write": new_scope.filesystem_write - old_scope.filesystem_write,
        "network_allow": new_scope.network_allow - old_scope.network_allow,
        "shell_allow": new_scope.shell_allow - old_scope.shell_allow,
        "env_read": new_scope.env_read - old_scope.env_read,
    }

    removed = {
        "filesystem_read": old_scope.filesystem_read - new_scope.filesystem_read,
        "filesystem_write": old_scope.filesystem_write - new_scope.filesystem_write,
        "network_allow": old_scope.network_allow - new_scope.network_allow,
        "shell_allow": old_scope.shell_allow - new_scope.shell_allow,
        "env_read": old_scope.env_read - new_scope.env_read,
    }

    has_changes = any(added.values()) or any(removed.values())

    if json_output:
        output = {
            "added": {k: list(v) for k, v in added.items() if v},
            "removed": {k: list(v) for k, v in removed.items() if v},
            "has_changes": has_changes,
        }
        console.print(json_lib.dumps(output, indent=2))
        return

    # Human-readable output
    console.print(f"\n🔄 [bold]Permission Diff[/bold]")
    console.print(f"   Old: {old_lens}")
    console.print(f"   New: {new_lens}\n")

    if not has_changes:
        console.print("[green]No permission changes[/green]")
        return

    # Show added
    for category, values in added.items():
        if values:
            console.print(f"[green]+ {category}:[/green]")
            for v in sorted(values):
                console.print(f"    + {v}")

    # Show removed
    for category, values in removed.items():
        if values:
            console.print(f"[red]- {category}:[/red]")
            for v in sorted(values):
                console.print(f"    - {v}")

    console.print()
