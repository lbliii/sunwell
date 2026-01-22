"""Git Scanner — RFC-050.

Extract intelligence from git history: commits, blame, authorship.
"""


import asyncio
import re
from datetime import datetime
from pathlib import Path

from sunwell.bootstrap.types import (
    BlameRegion,
    BranchPatterns,
    CommitInfo,
    ContributorStats,
    GitEvidence,
)


class GitScanner:
    """Extract intelligence from git history."""

    # Decision signal patterns in commit messages
    DECISION_PATTERNS = [
        r"\b(decided|chose|selected|picked|switched to|moved to)\b",
        r"\b(instead of|over|rather than|not|rejected)\b",
        r"\b(because|since|due to|in order to|so that)\b",
        r"^(feat|refactor|chore|BREAKING)(\(.+\))?:",  # Conventional commits
    ]

    FIX_PATTERNS = [
        r"^fix(\(.+\))?:",
        r"\b(fix|bugfix|hotfix|patch)\b",
        r"\b(resolve|close|closes)\s+#\d+",
    ]

    REFACTOR_PATTERNS = [
        r"^refactor(\(.+\))?:",
        r"\b(refactor|restructure|reorganize|cleanup|clean up)\b",
    ]

    def __init__(
        self,
        root: Path,
        max_commits: int = 1000,
        max_age_days: int = 365,
        blame_limit: int = 50,
    ):
        """Initialize git scanner.

        Args:
            root: Project root directory
            max_commits: Maximum commits to scan
            max_age_days: Ignore commits older than this
            blame_limit: Maximum files to run git blame on
        """
        self.root = Path(root)
        self.max_commits = max_commits
        self.max_age_days = max_age_days
        self.blame_limit = blame_limit

    async def scan(self) -> GitEvidence:
        """Scan git history and extract evidence."""
        # Check if git repo exists
        if not (self.root / ".git").exists():
            return self._empty_evidence()

        commits = await self._scan_commits()
        blame_map = await self._scan_blame()
        contributor_stats = self._compute_contributor_stats(commits)
        change_frequency = self._compute_change_frequency(commits)
        branch_patterns = await self._analyze_branches()

        return GitEvidence(
            commits=commits,
            blame_map=blame_map,
            contributor_stats=contributor_stats,
            change_frequency=change_frequency,
            branch_patterns=branch_patterns,
        )

    def _empty_evidence(self) -> GitEvidence:
        """Return empty evidence when git is not available."""
        return GitEvidence(
            commits=(),
            blame_map={},
            contributor_stats={},
            change_frequency={},
            branch_patterns=BranchPatterns(
                main_branch="main",
                uses_feature_branches=False,
                branch_prefix_pattern=None,
            ),
        )

    async def _run_git(self, args: list[str]) -> str:
        """Run a git command and return output."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode("utf-8", errors="replace")

    async def _scan_commits(self) -> tuple[CommitInfo, ...]:
        """Parse recent commits for decision signals."""
        # git log with custom format: SHA|author|date|subject
        # Then file names on following lines
        result = await self._run_git([
            "log",
            f"--max-count={self.max_commits}",
            f"--since={self.max_age_days} days ago",
            "--format=%H|%an|%aI|%s",
            "--name-only",
        ])

        commits = []
        current_commit: dict | None = None
        current_files: list[str] = []

        for line in result.split("\n"):
            line = line.strip()
            if not line:
                # Blank line marks end of file list
                if current_commit:
                    current_commit["files"] = tuple(Path(f) for f in current_files if f)
                    commits.append(self._parse_commit(current_commit))
                    current_commit = None
                    current_files = []
                continue

            if "|" in line and line.count("|") >= 3:
                # New commit header
                if current_commit:
                    current_commit["files"] = tuple(Path(f) for f in current_files if f)
                    commits.append(self._parse_commit(current_commit))

                parts = line.split("|", 3)
                current_commit = {
                    "sha": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3] if len(parts) > 3 else "",
                }
                current_files = []
            elif current_commit:
                # File name
                current_files.append(line)

        # Handle last commit
        if current_commit:
            current_commit["files"] = tuple(Path(f) for f in current_files if f)
            commits.append(self._parse_commit(current_commit))

        return tuple(commits)

    def _parse_commit(self, data: dict) -> CommitInfo:
        """Parse commit data into CommitInfo."""
        message = data.get("message", "")

        return CommitInfo(
            sha=data["sha"],
            author=data["author"],
            date=datetime.fromisoformat(data["date"]),
            message=message,
            files_changed=data.get("files", ()),
            is_decision=self._detect_decision(message),
            is_fix=self._detect_fix(message),
            is_refactor=self._detect_refactor(message),
            mentioned_files=self._extract_file_mentions(message),
        )

    def _detect_decision(self, message: str) -> bool:
        """Detect if commit message contains decision language."""
        message_lower = message.lower()
        for pattern in self.DECISION_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        return False

    def _detect_fix(self, message: str) -> bool:
        """Detect if commit is a fix."""
        message_lower = message.lower()
        return any(re.search(p, message_lower) for p in self.FIX_PATTERNS)

    def _detect_refactor(self, message: str) -> bool:
        """Detect if commit is a refactor."""
        message_lower = message.lower()
        return any(re.search(p, message_lower) for p in self.REFACTOR_PATTERNS)

    def _extract_file_mentions(self, message: str) -> tuple[str, ...]:
        """Extract file/module names mentioned in commit message."""
        # Look for patterns like: in foo.py, to bar.py, file: baz.py
        pattern = r"\b(\w+\.py|\w+\.js|\w+\.ts)\b"
        matches = re.findall(pattern, message)
        return tuple(set(matches))

    async def _scan_blame(self) -> dict[Path, list[BlameRegion]]:
        """Run git blame on key files for ownership mapping.

        Only blame:
        - Files > 100 lines (significant)
        - Modified recently (active)
        - Not in vendor/generated directories
        """
        blame_map: dict[Path, list[BlameRegion]] = {}

        # Get active Python files
        active_files = await self._get_active_files()

        for file_path in active_files[: self.blame_limit]:
            try:
                regions = await self._blame_file(file_path)
                if regions:
                    blame_map[file_path] = regions
            except Exception:
                # Skip files that can't be blamed
                continue

        return blame_map

    async def _get_active_files(self) -> list[Path]:
        """Get recently modified Python files."""
        # Get files modified in last 90 days
        result = await self._run_git([
            "log",
            "--since=90 days ago",
            "--name-only",
            "--format=",
            "--diff-filter=M",
        ])

        files = set()
        for line in result.split("\n"):
            line = line.strip()
            if line and line.endswith(".py"):
                file_path = self.root / line
                if file_path.exists():
                    # Check line count (only significant files)
                    try:
                        line_count = len(file_path.read_text().split("\n"))
                        if line_count >= 50:
                            files.add(Path(line))
                    except Exception:
                        continue

        return sorted(files)

    async def _blame_file(self, file_path: Path) -> list[BlameRegion]:
        """Run git blame on a single file."""
        result = await self._run_git([
            "blame",
            "--porcelain",
            str(file_path),
        ])

        regions: list[BlameRegion] = []
        current_sha = ""
        current_author = ""
        current_date = datetime.now()
        current_start = 0

        for line in result.split("\n"):
            if line.startswith(tuple("0123456789abcdef")):
                # SHA line: sha orig_line final_line [num_lines]
                parts = line.split()
                if len(parts) >= 3:
                    new_sha = parts[0]
                    line_num = int(parts[2])

                    # If SHA changed, close previous region
                    if new_sha != current_sha and current_sha:
                        regions.append(BlameRegion(
                            start_line=current_start,
                            end_line=line_num - 1,
                            author=current_author,
                            date=current_date,
                            commit_sha=current_sha[:8],
                        ))
                        current_start = line_num

                    current_sha = new_sha

            elif line.startswith("author "):
                current_author = line[7:]
            elif line.startswith("author-time "):
                try:
                    timestamp = int(line[12:])
                    current_date = datetime.fromtimestamp(timestamp)
                except ValueError:
                    pass

        # Merge adjacent regions by same author
        return self._merge_blame_regions(regions)

    def _merge_blame_regions(self, regions: list[BlameRegion]) -> list[BlameRegion]:
        """Merge adjacent blame regions by same author."""
        if not regions:
            return []

        merged: list[BlameRegion] = []
        current = regions[0]

        for region in regions[1:]:
            if (region.author == current.author and
                region.start_line == current.end_line + 1):
                # Merge with current
                current = BlameRegion(
                    start_line=current.start_line,
                    end_line=region.end_line,
                    author=current.author,
                    date=max(current.date, region.date),
                    commit_sha=region.commit_sha,  # Use more recent commit
                )
            else:
                merged.append(current)
                current = region

        merged.append(current)
        return merged

    def _compute_contributor_stats(
        self,
        commits: tuple[CommitInfo, ...],
    ) -> dict[str, ContributorStats]:
        """Compute per-contributor statistics."""
        stats: dict[str, dict] = {}

        for commit in commits:
            author = commit.author
            if author not in stats:
                stats[author] = {
                    "commits": 0,
                    "files": set(),
                    "first_commit": commit.date,
                    "last_commit": commit.date,
                }

            stats[author]["commits"] += 1
            stats[author]["files"].update(str(f) for f in commit.files_changed)
            stats[author]["first_commit"] = min(
                stats[author]["first_commit"], commit.date
            )
            stats[author]["last_commit"] = max(
                stats[author]["last_commit"], commit.date
            )

        return {
            author: ContributorStats(
                author=author,
                commits=data["commits"],
                lines_added=0,  # Would need diff parsing
                lines_deleted=0,
                files_touched=len(data["files"]),
                first_commit=data["first_commit"],
                last_commit=data["last_commit"],
            )
            for author, data in stats.items()
        }

    def _compute_change_frequency(
        self,
        commits: tuple[CommitInfo, ...],
    ) -> dict[Path, float]:
        """Compute change frequency (changes per month) per file."""
        file_changes: dict[Path, list[datetime]] = {}

        for commit in commits:
            for file_path in commit.files_changed:
                file_changes.setdefault(file_path, []).append(commit.date)

        frequency: dict[Path, float] = {}
        now = datetime.now()

        for file_path, dates in file_changes.items():
            if not dates:
                continue
            oldest = min(dates)
            months = max(1, (now - oldest).days / 30)
            frequency[file_path] = len(dates) / months

        return frequency

    async def _analyze_branches(self) -> BranchPatterns:
        """Analyze branch naming patterns."""
        # Get current branch (for future use)
        result = await self._run_git(["branch", "--show-current"])
        _ = result.strip() or "main"  # Reserved for future branch-aware features

        # Check for main branch name
        result = await self._run_git(["branch", "-a"])
        branches = [b.strip().lstrip("* ") for b in result.split("\n") if b.strip()]

        main_branch = "main"
        for candidate in ["main", "master", "develop"]:
            if candidate in branches:
                main_branch = candidate
                break

        # Detect feature branch patterns
        prefixes = ["feature/", "fix/", "bugfix/", "hotfix/", "release/"]
        feature_branches = [b for b in branches if any(b.startswith(p) for p in prefixes)]
        uses_feature_branches = len(feature_branches) >= 2

        # Detect common prefix
        prefix_pattern = None
        if feature_branches:
            for prefix in prefixes:
                if sum(1 for b in feature_branches if b.startswith(prefix)) >= 2:
                    prefix_pattern = prefix
                    break

        return BranchPatterns(
            main_branch=main_branch,
            uses_feature_branches=uses_feature_branches,
            branch_prefix_pattern=prefix_pattern,
        )
