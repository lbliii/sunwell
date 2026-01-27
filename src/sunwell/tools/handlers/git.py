"""Git operation handlers."""

import subprocess

from sunwell.tools.handlers.base import BaseHandler


class GitHandlers(BaseHandler):
    """Git operation handlers."""

    def _check_git_repo(self) -> None:
        """Verify we're in a git repository."""
        if not (self.workspace / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

    def _run_git(
        self,
        cmd: list[str],
        timeout: int = 10,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command with standard error handling."""
        return subprocess.run(
            cmd,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    async def git_init(self, args: dict) -> str:
        """Initialize a new git repository."""
        path = args.get("path", ".")
        target = self._safe_path(path)

        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.is_dir():
            raise ValueError(f"Path exists but is not a directory: {path}")

        if (target / ".git").exists():
            return f"Already a git repository: {path}"

        # Run git init in the target directory, not workspace root
        result = subprocess.run(
            ["git", "init"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return result.stdout.strip() or f"Initialized git repository in {path}"

    async def git_info(self, args: dict) -> str:
        """Get git repository information."""
        include_status = args.get("include_status", True)
        commit_count = min(args.get("commit_count", 5), 20)

        git_dir = self.workspace / ".git"
        if not git_dir.exists():
            return "Not a git repository (no .git directory found)"

        info_parts = []

        try:
            result = self._run_git(["git", "remote", "-v"], 5)
            if result.returncode == 0 and result.stdout.strip():
                info_parts.append(f"**Remotes:**\n{result.stdout.strip()}")
        except Exception:
            pass

        try:
            result = self._run_git(["git", "branch", "--show-current"], 5)
            if result.returncode == 0:
                branch = result.stdout.strip() or "(detached HEAD)"
                info_parts.append(f"**Branch:** {branch}")
        except Exception:
            pass

        try:
            result = self._run_git(["git", "log", f"-{commit_count}", "--oneline"], 5)
            if result.returncode == 0 and result.stdout.strip():
                info_parts.append(f"**Recent commits:**\n{result.stdout.strip()}")
        except Exception:
            pass

        if include_status:
            try:
                result = self._run_git(["git", "status", "--short"], 5)
                if result.returncode == 0:
                    status = result.stdout.strip() or "(clean working tree)"
                    info_parts.append(f"**Status:**\n{status}")
            except Exception:
                pass

        return "\n\n".join(info_parts) if info_parts else "Could not retrieve git information"

    async def git_status(self, args: dict) -> str:
        """Get git status."""
        self._check_git_repo()
        short = args.get("short", False)

        cmd = ["git", "status"]
        if short:
            cmd.append("--short")

        result = self._run_git(cmd)

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
            self._safe_path(path)
            cmd.extend(["--", path])

        result = self._run_git(cmd, 30)

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        output = result.stdout.strip()
        if not output:
            return "No changes" if args.get("staged") else "No unstaged changes"

        if len(output) > 50000:
            output = output[:50000] + "\n... (truncated, diff too large)"

        return output

    async def git_log(self, args: dict) -> str:
        """Show git log."""
        self._check_git_repo()

        n = min(args.get("n", 10), 100)
        oneline = args.get("oneline", True)

        cmd = ["git", "log", f"-{n}"]

        if oneline:
            cmd.append("--oneline")

        if since := args.get("since"):
            cmd.extend(["--since", since])

        if path := args.get("path"):
            self._safe_path(path)
            cmd.extend(["--", path])

        result = self._run_git(cmd, 15)

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return result.stdout.strip() or "No commits found"

    async def git_blame(self, args: dict) -> str:
        """Show git blame for a file."""
        self._check_git_repo()

        path = args.get("path")
        if not path:
            raise ValueError("path is required for git_blame")

        self._safe_path(path)

        cmd = ["git", "blame", path]

        if lines := args.get("lines"):
            cmd.extend(["-L", lines])

        result = self._run_git(cmd, 30)

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

        result = self._run_git(cmd, 30)

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
            for p in paths:
                self._safe_path(p)
            cmd = ["git", "add", "--"] + paths
        else:
            return "No files specified. Use 'paths' or 'all: true'"

        result = self._run_git(cmd, 30)

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        status_result = self._run_git(["git", "status", "--short"], 5)

        return f"✓ Files staged\n{status_result.stdout.strip()}"

    async def git_restore(self, args: dict) -> str:
        """Restore files or unstage."""
        self._check_git_repo()

        paths = args.get("paths")
        if not paths:
            raise ValueError("paths is required for git_restore")

        staged = args.get("staged", False)
        source = args.get("source")

        for p in paths:
            self._safe_path(p)

        cmd = ["git", "restore"]

        if staged:
            cmd.append("--staged")

        if source:
            cmd.extend(["--source", source])

        cmd.extend(["--"] + paths)

        result = self._run_git(cmd, 30)

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

        result = self._run_git(cmd, 30)

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
            result = self._run_git(["git", "branch", "-vv"])
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            return result.stdout.strip() or "No branches"

        if delete:
            flag = "-D" if force else "-d"
            cmd = ["git", "branch", flag, name]
        else:
            cmd = ["git", "branch", name]

        result = self._run_git(cmd)

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

        result = self._run_git(cmd, 30)

        if result.returncode != 0:
            return f"Error: {result.stderr}"

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

        result = self._run_git(cmd, 30)

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
            for p in paths:
                self._safe_path(p)
            cmd = ["git", "reset", "HEAD", "--"] + paths
        else:
            cmd = ["git", "reset", f"--{mode}", target]

        result = self._run_git(cmd, 30)

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

        result = self._run_git(cmd, 60)

        if result.returncode != 0:
            if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
                return f"Merge conflicts:\n{result.stdout}\n\nResolve conflicts and commit."
            return f"Error: {result.stderr}"

        return result.stdout.strip() or f"✓ Merged '{branch}'"
