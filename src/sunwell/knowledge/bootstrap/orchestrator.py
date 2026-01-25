"""Bootstrap Orchestrator — RFC-050.

Coordinates all scanners and populates RFC-045 intelligence stores.
"""


import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sunwell.knowledge.bootstrap.ownership import OwnershipMap
from sunwell.knowledge.bootstrap.scanners.code import CodeScanner
from sunwell.knowledge.bootstrap.scanners.config import ConfigScanner
from sunwell.knowledge.bootstrap.scanners.docs import DocScanner
from sunwell.knowledge.bootstrap.scanners.git import GitScanner
from sunwell.knowledge.bootstrap.types import (
    BootstrapDecision,
    BootstrapPatterns,
    BootstrapResult,
    CodeEvidence,
    CommitInfo,
    ConfigEvidence,
    DocEvidence,
    GitEvidence,
)

if TYPE_CHECKING:
    from sunwell.knowledge.codebase.context import ProjectContext


class BootstrapOrchestrator:
    """Orchestrate the bootstrap process."""

    def __init__(
        self,
        root: Path,
        context: ProjectContext,
        use_llm: bool = True,
        verbose: bool = False,
        max_commits: int = 1000,
        max_age_days: int = 365,
        blame_limit: int = 50,
    ):
        """Initialize bootstrap orchestrator.

        Args:
            root: Project root directory
            context: RFC-045 ProjectContext to populate
            use_llm: Whether to use LLM for ambiguous decision extraction
            verbose: Whether to print verbose output
            max_commits: Maximum commits to scan
            max_age_days: Ignore commits older than this
            blame_limit: Maximum files to git blame
        """
        self.root = Path(root)
        self.context = context
        self.use_llm = use_llm
        self.verbose = verbose

        self.git_scanner = GitScanner(
            root,
            max_commits=max_commits,
            max_age_days=max_age_days,
            blame_limit=blame_limit,
        )
        self.code_scanner = CodeScanner(root)
        self.doc_scanner = DocScanner(root)
        self.config_scanner = ConfigScanner(root)

    async def bootstrap(self) -> BootstrapResult:
        """Run full bootstrap process.

        Stages:
        1. SCAN — Run all scanners in parallel (deterministic, no LLM)
        2. EXTRACT — Convert raw evidence to intelligence candidates
        3. INFER — Optional LLM for ambiguous cases
        4. POPULATE — Fill RFC-045 stores
        5. REPORT — Generate summary

        Returns:
            BootstrapResult with statistics and evidence
        """
        start = datetime.now()
        warnings: list[str] = []

        # Stage 1: Scan all sources in parallel
        if self.verbose:
            print("Stage 1: Scanning project...")

        git_evidence, code_evidence, doc_evidence, config_evidence = await asyncio.gather(
            self.git_scanner.scan(),
            self.code_scanner.scan(),
            self.doc_scanner.scan(),
            self.config_scanner.scan(),
        )

        # Stage 2: Convert evidence to intelligence
        if self.verbose:
            print("Stage 2: Extracting intelligence...")

        decisions = await self._infer_decisions(git_evidence, doc_evidence, config_evidence)
        patterns = self._infer_patterns(code_evidence, config_evidence)

        # Stage 3: Populate RFC-045 stores
        if self.verbose:
            print("Stage 3: Populating intelligence stores...")

        decisions_count = await self._populate_decisions(decisions)
        patterns_count = await self._populate_patterns(patterns)
        await self._populate_codebase_graph(code_evidence)

        # Populate ownership map
        ownership_map = OwnershipMap(self.root / ".sunwell" / "intelligence")
        ownership_domains = ownership_map.populate_from_blame(git_evidence.blame_map)

        # Stage 4: Build report
        duration = datetime.now() - start

        if self.verbose:
            print(f"Bootstrap complete in {duration.total_seconds():.1f}s")

        return BootstrapResult(
            duration=duration,
            decisions_inferred=decisions_count,
            patterns_detected=patterns_count,
            codebase_functions=len(code_evidence.module_structure.functions),
            codebase_classes=len(code_evidence.module_structure.classes),
            ownership_domains=len(ownership_domains),
            average_confidence=0.72,  # Bootstrap default
            warnings=tuple(warnings),
            git_evidence=git_evidence,
            code_evidence=code_evidence,
            doc_evidence=doc_evidence,
            config_evidence=config_evidence,
        )

    async def _infer_decisions(
        self,
        git: GitEvidence,
        doc: DocEvidence,
        config: ConfigEvidence,
    ) -> list[BootstrapDecision]:
        """Infer decisions from git commits, docs, and config.

        Sources (in priority order):
        1. Doc decision sections (most explicit)
        2. Commit messages with decision language
        3. Config file choices (implicit decisions)
        """
        decisions: list[BootstrapDecision] = []

        # From documentation
        for section in doc.decision_sections:
            if section.question and section.choice:
                decisions.append(BootstrapDecision(
                    source="doc",
                    source_file=section.source_file,
                    commit_sha=None,
                    question=section.question,
                    choice=section.choice,
                    rationale=section.rationale,
                    confidence=0.75,  # Docs may be stale
                ))

        # From commits
        decision_commits = [c for c in git.commits if c.is_decision]

        if self.use_llm and decision_commits:
            # Use LLM to extract structured decisions from commit messages
            decisions.extend(await self._llm_extract_decisions(decision_commits))
        else:
            # Simple heuristic extraction
            for commit in decision_commits[:20]:  # Limit for performance
                if extracted := self._heuristic_extract_decision(commit):
                    decisions.append(extracted)

        # From config (implicit decisions)
        config_decisions = self._extract_config_decisions(config)
        decisions.extend(config_decisions)

        return decisions

    def _heuristic_extract_decision(self, commit: CommitInfo) -> BootstrapDecision | None:
        """Extract decision from commit message using heuristics."""
        message = commit.message

        # Look for patterns like "switched to X", "chose X", "using X instead of Y"
        import re

        # Pattern: "switched to X" or "moved to X"
        match = re.search(r"(switched|moved|migrated)\s+to\s+(\w+(?:\s+\w+)?)", message, re.I)
        if match:
            return BootstrapDecision(
                source="commit",
                source_file=None,
                commit_sha=commit.sha[:8],
                question=f"What to use for {match.group(1)}?",
                choice=match.group(2),
                rationale=message,
                confidence=0.65,
            )

        # Pattern: "chose X over Y" or "using X instead of Y"
        pattern = r"(chose|selected|using)\s+(\w+)\s+(over|instead of)\s+(\w+)"
        match = re.search(pattern, message, re.I)
        if match:
            return BootstrapDecision(
                source="commit",
                source_file=None,
                commit_sha=commit.sha[:8],
                question=f"Which approach: {match.group(2)} or {match.group(4)}?",
                choice=match.group(2),
                rationale=f"Chose {match.group(2)} {match.group(3)} {match.group(4)}",
                confidence=0.70,
            )

        # Pattern: "feat: add X" with "because" clause
        match = re.search(r"(?:feat|add):\s*(.+?)\s+because\s+(.+)", message, re.I)
        if match:
            return BootstrapDecision(
                source="commit",
                source_file=None,
                commit_sha=commit.sha[:8],
                question=f"Should we add {match.group(1)}?",
                choice=f"Yes, add {match.group(1)}",
                rationale=match.group(2),
                confidence=0.60,
            )

        return None

    async def _llm_extract_decisions(
        self,
        commits: list[CommitInfo],
    ) -> list[BootstrapDecision]:
        """Use LLM to extract structured decisions from commit messages.

        This is optional and only used when --use-llm is enabled.
        """
        # TODO: Implement LLM extraction in future iteration
        # For now, fall back to heuristic extraction
        decisions = []
        for commit in commits[:10]:  # Limit LLM calls
            if extracted := self._heuristic_extract_decision(commit):
                decisions.append(extracted)
        return decisions

    def _extract_config_decisions(self, config: ConfigEvidence) -> list[BootstrapDecision]:
        """Extract implicit decisions from config files."""
        decisions: list[BootstrapDecision] = []

        # Formatter decision
        if config.formatter:
            decisions.append(BootstrapDecision(
                source="config",
                source_file=Path("pyproject.toml"),
                commit_sha=None,
                question="Which code formatter to use?",
                choice=config.formatter,
                rationale="Configured in pyproject.toml",
                confidence=0.85,  # Config is explicit
            ))

        # Linter decision
        if config.linter:
            decisions.append(BootstrapDecision(
                source="config",
                source_file=Path("pyproject.toml"),
                commit_sha=None,
                question="Which linter to use?",
                choice=config.linter,
                rationale="Configured in pyproject.toml",
                confidence=0.85,
            ))

        # Type checker decision
        if config.type_checker:
            decisions.append(BootstrapDecision(
                source="config",
                source_file=Path("pyproject.toml"),
                commit_sha=None,
                question="Which type checker to use?",
                choice=config.type_checker,
                rationale="Configured in pyproject.toml",
                confidence=0.85,
            ))

        # Test framework decision
        if config.test_framework:
            decisions.append(BootstrapDecision(
                source="config",
                source_file=Path("pyproject.toml"),
                commit_sha=None,
                question="Which test framework to use?",
                choice=config.test_framework,
                rationale="Detected from configuration",
                confidence=0.90,
            ))

        # CI provider decision
        if config.ci_provider and config.ci_provider != "none":
            ci_path = (
                Path(".github/workflows") if config.ci_provider == "github"
                else Path(".gitlab-ci.yml")
            )
            decisions.append(BootstrapDecision(
                source="config",
                source_file=ci_path,
                commit_sha=None,
                question="Which CI/CD platform to use?",
                choice=config.ci_provider,
                rationale="Detected from CI configuration files",
                confidence=0.90,
            ))

        return decisions

    def _infer_patterns(
        self,
        code: CodeEvidence,
        config: ConfigEvidence,
    ) -> BootstrapPatterns:
        """Build BootstrapPatterns from code and config analysis."""
        # Map type hint level
        type_level: Literal["none", "public", "all"] = "public"
        if code.type_hint_usage.level == "comprehensive":
            type_level = "all"
        elif code.type_hint_usage.level == "none":
            type_level = "none"

        return BootstrapPatterns(
            naming_conventions={
                "function": code.naming_patterns.function_style,
                "class": code.naming_patterns.class_style,
                "constant": code.naming_patterns.constant_style,
            },
            import_style=code.import_patterns.style,
            type_annotation_level=type_level,
            docstring_style=(
                code.docstring_style.style
                if code.docstring_style.style != "mixed" else "google"
            ),
            docstring_consistency=code.docstring_style.consistency,
            line_length=config.line_length or 100,
            formatter=config.formatter,
            linter=config.linter,
            type_checker=config.type_checker,
        )

    async def _populate_decisions(
        self,
        decisions: list[BootstrapDecision],
    ) -> int:
        """Populate DecisionMemory with bootstrapped decisions."""
        count = 0

        for decision in decisions:
            # Check for duplicates
            existing = await self.context.decisions.find_relevant_decisions(
                decision.question,
                top_k=1,
            )

            if existing and self._is_similar(existing[0].question, decision.question):
                continue  # Skip duplicate

            await self.context.decisions.record_decision(
                category=decision.infer_category(),
                question=decision.question,
                choice=decision.choice,
                rejected=[],  # Bootstrap doesn't know what was rejected
                rationale=decision.rationale or "Inferred from bootstrap scan",
                source="bootstrap",
                confidence=decision.confidence,
                metadata={
                    "source_type": decision.source,
                    "source_file": str(decision.source_file) if decision.source_file else None,
                    "commit_sha": decision.commit_sha,
                },
            )
            count += 1

        return count

    def _is_similar(self, q1: str, q2: str) -> bool:
        """Check if two questions are similar (simple word overlap)."""
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        return overlap / total > 0.6 if total > 0 else False

    async def _populate_patterns(
        self,
        patterns: BootstrapPatterns,
    ) -> int:
        """Populate PatternProfile with bootstrapped patterns."""
        from sunwell.knowledge.codebase.patterns import PatternProfile

        bootstrapped_profile = PatternProfile.bootstrap(patterns)

        # Merge with existing profile (bootstrap doesn't override user-confirmed)
        existing = self.context.patterns

        # Only update fields that don't have user-confirmed evidence
        fields_updated = 0
        for field in ["naming_conventions", "import_style", "type_annotation_level",
                      "docstring_style", "line_length", "formatter", "linter", "type_checker"]:
            existing_evidence = existing.evidence.get(field, [])
            has_user_evidence = any("bootstrap:" not in e for e in existing_evidence)

            if not has_user_evidence:
                # Safe to update from bootstrap
                setattr(existing, field, getattr(bootstrapped_profile, field))
                conf = bootstrapped_profile.confidence.get(field, 0.75)
                existing.confidence[field] = conf
                evidence = bootstrapped_profile.evidence.get(field, ["bootstrap:scan"])
                existing.evidence[field] = evidence
                fields_updated += 1

        # Save patterns to disk
        intelligence_path = self.root / ".sunwell" / "intelligence"
        existing.save(intelligence_path)

        return fields_updated

    async def _populate_codebase_graph(self, code: CodeEvidence) -> None:
        """Populate CodebaseGraph with discovered structure."""
        # TODO: Integrate with CodebaseGraph.build_from_scan()
        # For now, this is a placeholder for the RFC-045 CodebaseGraph integration
        pass
