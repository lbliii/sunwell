"""Tool handlers for local execution (RFC-012, RFC-024).

Implements the core tool handlers that execute locally within Sunwell's process.
Security is enforced via path jailing and blocked patterns.

RFC-024 additions:
- Git operation handlers (status, diff, log, blame, show, add, restore, commit, etc.)
- Environment variable handlers with allowlist/blocklist security
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.skills.sandbox import ScriptSandbox


# =============================================================================
# Security
# =============================================================================

# Default blocked patterns (can be extended via config)
DEFAULT_BLOCKED_PATTERNS = frozenset({
    ".env",
    ".env.*",
    "**/.git/**",
    "**/.git",
    "**/node_modules/**",
    "**/__pycache__/**",
    "*.pem",
    "*.key",
    "**/secrets/**",
    "**/.ssh/**",
    "**/credentials/**",
    "**/*.secret",
})


class PathSecurityError(PermissionError):
    """Raised when a path access is blocked for security reasons."""
    pass


# =============================================================================
# Core Tool Handlers
# =============================================================================

class CoreToolHandlers:
    """Handlers for built-in tools. Execute locally, no servers.
    
    Security: All path operations use _safe_path() which:
    1. Resolves to absolute path
    2. Ensures path stays within workspace (jail)
    3. Checks against blocked patterns
    """
    
    def __init__(
        self, 
        workspace: Path, 
        sandbox: "ScriptSandbox | None" = None,
        blocked_patterns: frozenset[str] = DEFAULT_BLOCKED_PATTERNS,
    ):
        """Initialize handlers.
        
        Args:
            workspace: Root directory for all file operations (the "jail")
            sandbox: ScriptSandbox for run_command (RFC-011)
            blocked_patterns: Glob patterns to block access to
        """
        self.workspace = workspace.resolve()
        self.sandbox = sandbox
        self.blocked_patterns = blocked_patterns
    
    def _safe_path(self, user_path: str, *, allow_write: bool = False) -> Path:
        """Canonicalize path and enforce security restrictions.
        
        Args:
            user_path: User-provided path (may be relative or absolute)
            allow_write: If True, path must not match write-protected patterns
            
        Returns:
            Resolved absolute path within workspace
            
        Raises:
            PathSecurityError: If path escapes workspace or matches blocked pattern
        """
        # Resolve path relative to workspace
        requested = (self.workspace / user_path).resolve()
        
        # SECURITY: Ensure path is within workspace (prevent traversal)
        try:
            requested.relative_to(self.workspace)
        except ValueError:
            raise PathSecurityError(
                f"Path escapes workspace: {user_path} → {requested}"
            )
        
        # SECURITY: Check against blocked patterns
        relative_str = str(requested.relative_to(self.workspace))
        for pattern in self.blocked_patterns:
            # Check both the full relative path and just the filename
            if fnmatch.fnmatch(relative_str, pattern):
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
            if fnmatch.fnmatch(requested.name, pattern):
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
            # Also check without ** prefix for patterns like "**/.git/**"
            simple_pattern = pattern.lstrip("**/").rstrip("/**")
            if simple_pattern and simple_pattern in relative_str:
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
        
        return requested
    
    async def read_file(self, args: dict) -> str:
        """Read file contents. Respects blocked patterns."""
        path = self._safe_path(args["path"])
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {args['path']}")
        if not path.is_file():
            raise ValueError(f"Not a file: {args['path']}")
        
        # Size limit to prevent memory issues
        size = path.stat().st_size
        if size > 1_000_000:  # 1MB limit
            return f"File too large ({size:,} bytes). Use search_files to find specific content."
        
        content = path.read_text(encoding="utf-8", errors="replace")
        return f"```\n{content}\n```\n({len(content):,} bytes)"
    
    async def write_file(self, args: dict) -> str:
        """Write file contents. Creates parent directories."""
        path = self._safe_path(args["path"], allow_write=True)
        
        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)
        
        content = args["content"]
        path.write_text(content, encoding="utf-8")
        
        return f"✓ Wrote {args['path']} ({len(content):,} bytes)"
    
    async def list_files(self, args: dict) -> str:
        """List files in directory. Respects blocked patterns."""
        path = self._safe_path(args.get("path", "."))
        pattern = args.get("pattern", "*")
        
        if not path.is_dir():
            raise ValueError(f"Not a directory: {args.get('path', '.')}")
        
        files = []
        for f in sorted(path.glob(pattern)):
            try:
                # Filter out blocked paths
                relative = str(f.relative_to(self.workspace))
                self._safe_path(relative)
                files.append(relative)
            except PathSecurityError:
                continue  # Skip blocked files silently
        
        return "\n".join(files[:100]) or "(no matching files)"
    
    async def search_files(self, args: dict) -> str:
        """Search for pattern in files using ripgrep."""
        search_path = self._safe_path(args.get("path", "."))
        pattern = args["pattern"]
        glob_pattern = args.get("glob", "**/*")
        
        # Prefer ripgrep, fallback to grep
        rg_path = shutil.which("rg")
        if rg_path:
            cmd = [
                rg_path, 
                "-n",  # Line numbers
                "--max-filesize", "1M",
                "--glob", glob_pattern,
                pattern, 
                "."
            ]
        else:
            # grep fallback (less features)
            cmd = ["grep", "-rn", pattern, "."]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=search_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout[:10_000]  # Limit output size
            if result.returncode == 0:
                lines = output.strip().split('\n')
                return f"Found {len(lines)} matches:\n{output}" if output else "No matches found"
            elif result.returncode == 1:
                return "No matches found"
            else:
                return f"Search error: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return "Search timed out after 30s"
        except FileNotFoundError:
            return "Search tools (rg, grep) not available"
    
    async def run_command(self, args: dict) -> str:
        """Run shell command in sandbox (RFC-011 ScriptSandbox)."""
        cwd = self._safe_path(args.get("cwd", "."))
        command = args["command"]
        timeout = min(args.get("timeout", 30), 300)  # Max 5 minutes
        
        # If we have a sandbox from RFC-011, use it
        if self.sandbox:
            from sunwell.skills.types import Script
            
            # Wrap command in a bash script
            script = Script(
                name="cmd.sh",
                content=f"#!/bin/bash\n{command}",
                language="bash",
            )
            
            result = await self.sandbox.execute(script)
            
            output_parts = [f"Exit code: {result.exit_code}"]
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout[:5000]}")
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr[:2000]}")
            if result.timed_out:
                output_parts.append("(command timed out)")
            
            return "\n".join(output_parts)
        
        # Fallback: direct subprocess execution (less secure)
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            output_parts = [f"Exit code: {result.returncode}"]
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout[:5000]}")
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr[:2000]}")
            
            return "\n".join(output_parts)
            
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Command failed: {e}"
    
    async def git_info(self, args: dict) -> str:
        """Get git repository information (read-only, safe)."""
        include_status = args.get("include_status", True)
        commit_count = min(args.get("commit_count", 5), 20)  # Cap at 20
        
        # Check if we're in a git repo
        git_dir = self.workspace / ".git"
        if not git_dir.exists():
            return "Not a git repository (no .git directory found)"
        
        info_parts = []
        
        # Get remote URLs
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                info_parts.append(f"**Remotes:**\n{result.stdout.strip()}")
        except Exception:
            pass
        
        # Get current branch
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                branch = result.stdout.strip() or "(detached HEAD)"
                info_parts.append(f"**Branch:** {branch}")
        except Exception:
            pass
        
        # Get recent commits
        try:
            result = subprocess.run(
                ["git", "log", f"-{commit_count}", "--oneline"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                info_parts.append(f"**Recent commits:**\n{result.stdout.strip()}")
        except Exception:
            pass
        
        # Get status (optional)
        if include_status:
            try:
                result = subprocess.run(
                    ["git", "status", "--short"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    status = result.stdout.strip() or "(clean working tree)"
                    info_parts.append(f"**Status:**\n{status}")
            except Exception:
                pass
        
        return "\n\n".join(info_parts) if info_parts else "Could not retrieve git information"
    
    # =========================================================================
    # RFC-024: Git Tools
    # =========================================================================
    
    def _check_git_repo(self) -> None:
        """Verify we're in a git repository."""
        if not (self.workspace / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")
    
    async def git_status(self, args: dict) -> str:
        """Get git status."""
        self._check_git_repo()
        short = args.get("short", False)
        
        cmd = ["git", "status"]
        if short:
            cmd.append("--short")
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        return result.stdout.strip() or "Working tree clean"
    
    async def git_diff(self, args: dict) -> str:
        """Show git diff."""
        self._check_git_repo()
        
        cmd = ["git", "diff"]
        
        if args.get("staged"):
            cmd.append("--cached")
        
        if commit := args.get("commit"):
            cmd.append(commit)
        
        if path := args.get("path"):
            # Validate path is within workspace
            self._safe_path(path)
            cmd.extend(["--", path])
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        output = result.stdout.strip()
        if not output:
            return "No changes" if args.get("staged") else "No unstaged changes"
        
        # Truncate very long diffs
        if len(output) > 50000:
            output = output[:50000] + "\n... (truncated, diff too large)"
        
        return output
    
    async def git_log(self, args: dict) -> str:
        """Show git log."""
        self._check_git_repo()
        
        n = min(args.get("n", 10), 100)  # Cap at 100
        oneline = args.get("oneline", True)
        
        cmd = ["git", "log", f"-{n}"]
        
        if oneline:
            cmd.append("--oneline")
        
        if since := args.get("since"):
            cmd.extend(["--since", since])
        
        if path := args.get("path"):
            self._safe_path(path)
            cmd.extend(["--", path])
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=15,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        return result.stdout.strip() or "No commits found"
    
    async def git_blame(self, args: dict) -> str:
        """Show git blame for a file."""
        self._check_git_repo()
        
        path = args.get("path")
        if not path:
            raise ValueError("path is required for git_blame")
        
        # Validate path
        self._safe_path(path)
        
        cmd = ["git", "blame", path]
        
        if lines := args.get("lines"):
            cmd.extend(["-L", lines])
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        output = result.stdout.strip()
        if len(output) > 30000:
            output = output[:30000] + "\n... (truncated)"
        
        return output
    
    async def git_show(self, args: dict) -> str:
        """Show commit details."""
        self._check_git_repo()
        
        commit = args.get("commit", "HEAD")
        
        cmd = ["git", "show", commit, "--stat"]
        
        if path := args.get("path"):
            self._safe_path(path)
            cmd.extend(["--", path])
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        output = result.stdout.strip()
        if len(output) > 30000:
            output = output[:30000] + "\n... (truncated)"
        
        return output
    
    async def git_add(self, args: dict) -> str:
        """Stage files for commit."""
        self._check_git_repo()
        
        paths = args.get("paths", [])
        add_all = args.get("all", False)
        
        if add_all:
            cmd = ["git", "add", "-A"]
        elif paths:
            # Validate each path
            for p in paths:
                self._safe_path(p)
            cmd = ["git", "add", "--"] + paths
        else:
            return "No files specified. Use 'paths' or 'all: true'"
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        # Return status to show what was staged
        status_result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        return f"✓ Files staged\n{status_result.stdout.strip()}"
    
    async def git_restore(self, args: dict) -> str:
        """Restore files or unstage."""
        self._check_git_repo()
        
        paths = args.get("paths")
        if not paths:
            raise ValueError("paths is required for git_restore")
        
        staged = args.get("staged", False)
        source = args.get("source")
        
        # Validate paths
        for p in paths:
            self._safe_path(p)
        
        cmd = ["git", "restore"]
        
        if staged:
            cmd.append("--staged")
        
        if source:
            cmd.extend(["--source", source])
        
        cmd.extend(["--"] + paths)
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        action = "unstaged" if staged else "restored"
        return f"✓ {len(paths)} file(s) {action}"
    
    async def git_commit(self, args: dict) -> str:
        """Create a commit."""
        self._check_git_repo()
        
        message = args.get("message")
        if not message:
            raise ValueError("message is required for git_commit")
        
        amend = args.get("amend", False)
        
        cmd = ["git", "commit", "-m", message]
        if amend:
            cmd.append("--amend")
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        return result.stdout.strip()
    
    async def git_branch(self, args: dict) -> str:
        """List, create, or delete branches."""
        self._check_git_repo()
        
        name = args.get("name")
        delete = args.get("delete", False)
        force = args.get("force", False)
        
        if not name:
            # List branches
            result = subprocess.run(
                ["git", "branch", "-vv"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            return result.stdout.strip() or "No branches"
        
        if delete:
            flag = "-D" if force else "-d"
            cmd = ["git", "branch", flag, name]
        else:
            cmd = ["git", "branch", name]
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        if delete:
            return f"✓ Branch '{name}' deleted"
        return f"✓ Branch '{name}' created"
    
    async def git_checkout(self, args: dict) -> str:
        """Switch branches or create new branch."""
        self._check_git_repo()
        
        target = args.get("target")
        if not target:
            raise ValueError("target is required for git_checkout")
        
        create = args.get("create", False)
        
        cmd = ["git", "checkout"]
        if create:
            cmd.append("-b")
        cmd.append(target)
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        # stderr often contains the success message for checkout
        output = result.stderr.strip() or result.stdout.strip()
        return f"✓ {output}" if output else f"✓ Switched to '{target}'"
    
    async def git_stash(self, args: dict) -> str:
        """Stash operations."""
        self._check_git_repo()
        
        action = args.get("action", "push")
        message = args.get("message")
        index = args.get("index", 0)
        
        if action == "push":
            cmd = ["git", "stash", "push"]
            if message:
                cmd.extend(["-m", message])
        elif action == "pop":
            cmd = ["git", "stash", "pop", f"stash@{{{index}}}"]
        elif action == "apply":
            cmd = ["git", "stash", "apply", f"stash@{{{index}}}"]
        elif action == "drop":
            cmd = ["git", "stash", "drop", f"stash@{{{index}}}"]
        elif action == "list":
            cmd = ["git", "stash", "list"]
        else:
            return f"Unknown stash action: {action}"
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        output = result.stdout.strip() or result.stderr.strip()
        if action == "list" and not output:
            return "No stashes"
        return output or f"✓ Stash {action} completed"
    
    async def git_reset(self, args: dict) -> str:
        """Reset HEAD to specified state."""
        self._check_git_repo()
        
        target = args.get("target", "HEAD")
        mode = args.get("mode", "mixed")
        paths = args.get("paths")
        
        if paths:
            # Path-based reset (unstage)
            for p in paths:
                self._safe_path(p)
            cmd = ["git", "reset", "HEAD", "--"] + paths
        else:
            # Full reset
            cmd = ["git", "reset", f"--{mode}", target]
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        if paths:
            return f"✓ Unstaged {len(paths)} file(s)"
        return f"✓ Reset to {target} ({mode})"
    
    async def git_merge(self, args: dict) -> str:
        """Merge branch."""
        self._check_git_repo()
        
        branch = args.get("branch")
        if not branch:
            raise ValueError("branch is required for git_merge")
        
        no_ff = args.get("no_ff", False)
        message = args.get("message")
        
        cmd = ["git", "merge", branch]
        if no_ff:
            cmd.append("--no-ff")
        if message:
            cmd.extend(["-m", message])
        
        result = subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode != 0:
            # Check for merge conflicts
            if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
                return f"Merge conflicts:\n{result.stdout}\n\nResolve conflicts and commit."
            return f"Error: {result.stderr}"
        
        return result.stdout.strip() or f"✓ Merged '{branch}'"
    
    # =========================================================================
    # RFC-024: Environment Tools
    # =========================================================================
    
    async def get_env(self, args: dict) -> str:
        """Get environment variable with security restrictions."""
        from sunwell.tools.builtins import ENV_ALLOWLIST, ENV_BLOCKLIST_PATTERNS
        
        name = args.get("name")
        if not name:
            raise ValueError("name is required for get_env")
        
        # Check blocklist first (secrets)
        if _is_env_blocked(name, ENV_BLOCKLIST_PATTERNS):
            return f"[BLOCKED] Environment variable '{name}' may contain secrets and cannot be accessed."
        
        # Check allowlist
        if name not in ENV_ALLOWLIST:
            return (
                f"[NOT ALLOWED] Environment variable '{name}' is not in the allowlist. "
                f"Use list_env to see available variables."
            )
        
        value = os.environ.get(name)
        if value is None:
            return f"[NOT SET] Environment variable '{name}' is not set."
        
        return value
    
    async def list_env(self, args: dict) -> str:
        """List available environment variables."""
        from sunwell.tools.builtins import ENV_ALLOWLIST
        
        filter_prefix = args.get("filter", "").upper()
        
        available = []
        for name in sorted(ENV_ALLOWLIST):
            if filter_prefix and not name.startswith(filter_prefix):
                continue
            value = os.environ.get(name)
            if value:
                # Truncate long values
                display = value if len(value) <= 50 else f"{value[:47]}..."
                available.append(f"{name}={display}")
        
        if not available:
            return "No matching environment variables found."
        
        return "\n".join(available)


# =============================================================================
# Environment Security Helpers
# =============================================================================

def _is_env_blocked(name: str, blocklist_patterns: tuple[str, ...]) -> bool:
    """Check if an environment variable name matches blocked patterns."""
    name_upper = name.upper()
    for pattern in blocklist_patterns:
        if fnmatch.fnmatch(name_upper, pattern):
            return True
    return False