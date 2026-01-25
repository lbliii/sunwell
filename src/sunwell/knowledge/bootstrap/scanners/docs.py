"""Documentation Scanner — RFC-050.

Extract context from README and other documentation files.
"""


import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sunwell.knowledge.bootstrap.types import (
    ArchitectureSection,
    ContributionGuidelines,
    DecisionSection,
    DocEvidence,
    SetupInstructions,
)


@dataclass(frozen=True, slots=True)
class MarkdownSection:
    """A parsed markdown section."""

    level: int
    heading: str
    content: str


class DocScanner:
    """Extract intelligence from documentation files."""

    DOC_FILES = [
        "README.md",
        "README.rst",
        "README",
        "ARCHITECTURE.md",
        "DESIGN.md",
        "DECISIONS.md",
        "ADR.md",
        "docs/architecture.md",
        "docs/design.md",
        "CONTRIBUTING.md",
    ]

    ARCHITECTURE_KEYWORDS = [
        "architecture",
        "design",
        "structure",
        "overview",
        "how it works",
        "internals",
        "modules",
        "components",
        "system",
    ]

    DECISION_KEYWORDS = [
        "decision",
        "why",
        "rationale",
        "choice",
        "chose",
        "trade-off",
        "tradeoff",
        "comparison",
        " vs ",
        "instead of",
        "over",
    ]

    def __init__(self, root: Path):
        """Initialize documentation scanner.

        Args:
            root: Project root directory
        """
        self.root = Path(root)

    async def scan(self) -> DocEvidence:
        """Scan documentation files."""
        docs = self._find_doc_files()

        architecture_sections: list[ArchitectureSection] = []
        decision_sections: list[DecisionSection] = []

        for doc_path in docs:
            try:
                content = doc_path.read_text(encoding="utf-8", errors="replace")
                sections = self._parse_markdown_sections(content)

                for section in sections:
                    if self._is_architecture_section(section):
                        architecture_sections.append(
                            ArchitectureSection(
                                source_file=doc_path.relative_to(self.root),
                                heading=section.heading,
                                content=section.content[:2000],  # Limit content size
                                mentions_modules=self._extract_module_mentions(
                                    section.content
                                ),
                            )
                        )

                    if self._is_decision_section(section):
                        decision_sections.append(
                            self._extract_decision(doc_path, section)
                        )
            except (OSError, UnicodeDecodeError):
                continue

        return DocEvidence(
            project_name=self._extract_project_name(),
            project_description=self._extract_description(),
            architecture_sections=tuple(architecture_sections),
            decision_sections=tuple(decision_sections),
            setup_instructions=self._extract_setup(),
            contribution_guidelines=self._extract_contributing(),
        )

    def _find_doc_files(self) -> list[Path]:
        """Find documentation files in project."""
        found: list[Path] = []

        for pattern in self.DOC_FILES:
            # Handle glob patterns
            if "*" in pattern:
                found.extend(self.root.glob(pattern))
            else:
                path = self.root / pattern
                if path.exists():
                    found.append(path)

        return found

    def _parse_markdown_sections(self, content: str) -> list[MarkdownSection]:
        """Parse markdown into sections by heading."""
        sections: list[MarkdownSection] = []
        lines = content.split("\n")

        current_heading = ""
        current_level = 0
        current_content: list[str] = []

        for line in lines:
            # Check for markdown heading
            if line.startswith("#"):
                # Save previous section
                if current_heading:
                    sections.append(MarkdownSection(
                        level=current_level,
                        heading=current_heading,
                        content="\n".join(current_content).strip(),
                    ))

                # Parse new heading
                match = re.match(r"^(#+)\s*(.+)$", line)
                if match:
                    current_level = len(match.group(1))
                    current_heading = match.group(2).strip()
                    current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_heading:
            sections.append(MarkdownSection(
                level=current_level,
                heading=current_heading,
                content="\n".join(current_content).strip(),
            ))

        return sections

    def _is_architecture_section(self, section: MarkdownSection) -> bool:
        """Detect architecture/design sections."""
        heading_lower = section.heading.lower()
        return any(kw in heading_lower for kw in self.ARCHITECTURE_KEYWORDS)

    def _is_decision_section(self, section: MarkdownSection) -> bool:
        """Detect decision/rationale sections."""
        heading_lower = section.heading.lower()
        return any(kw in heading_lower for kw in self.DECISION_KEYWORDS)

    def _extract_module_mentions(self, content: str) -> tuple[str, ...]:
        """Extract module/package names mentioned in content."""
        # Look for backtick-quoted names that might be modules
        pattern = r"`([a-z_][a-z0-9_]*)`"
        matches = re.findall(pattern, content, re.IGNORECASE)

        # Filter to likely module names (not common words)
        common_words = {"true", "false", "none", "null", "int", "str", "bool", "list", "dict"}
        modules = [m for m in matches if m.lower() not in common_words and len(m) > 2]

        return tuple(set(modules))

    def _extract_decision(
        self,
        source: Path,
        section: MarkdownSection,
    ) -> DecisionSection:
        """Extract structured decision from section."""
        content = section.content

        # Simple heuristics for question/choice/rationale
        question = None
        choice = None
        rationale = None

        # Look for question patterns
        match = re.search(r"\b(why|how|what|which)\b[^.?]*\?", content, re.IGNORECASE)
        if match:
            question = match.group(0).strip()

        # Look for choice patterns
        match = re.search(
            r"\b(chose|selected|decided on|using|use|went with)\s+(\w+(?:\s+\w+)?)",
            content,
            re.IGNORECASE,
        )
        if match:
            choice = match.group(2).strip()

        # Look for rationale patterns
        match = re.search(
            r"\b(because|since|due to|in order to|so that)\b([^.]+)",
            content,
            re.IGNORECASE,
        )
        if match:
            rationale = match.group(0).strip()

        return DecisionSection(
            source_file=source.relative_to(self.root),
            heading=section.heading,
            content=content[:1000],  # Limit content size
            question=question,
            choice=choice,
            rationale=rationale,
        )

    def _extract_project_name(self) -> str | None:
        """Extract project name from README or pyproject.toml."""
        # Try pyproject.toml first
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
            except OSError:
                pass

        # Try README
        for readme_name in ["README.md", "README.rst", "README"]:
            readme = self.root / readme_name
            if readme.exists():
                try:
                    content = readme.read_text()
                    # Look for first H1 heading
                    match = re.match(r"^#\s*(.+)$", content, re.MULTILINE)
                    if match:
                        return match.group(1).strip()
                except OSError:
                    pass

        return None

    def _extract_description(self) -> str | None:
        """Extract one-line project description."""
        # Try pyproject.toml first
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
            except OSError:
                pass

        # Try README - first non-empty line after title
        readme = self.root / "README.md"
        if readme.exists():
            try:
                content = readme.read_text()
                lines = content.split("\n")
                found_title = False
                for line in lines:
                    line = line.strip()
                    if line.startswith("#"):
                        found_title = True
                        continue
                    is_content = (
                        found_title and line and
                        not line.startswith("#") and
                        "![" not in line and "[!" not in line
                    )
                    if is_content:
                        return line[:200]  # Limit length
            except OSError:
                pass

        return None

    def _extract_setup(self) -> SetupInstructions | None:
        """Extract setup instructions from README."""
        readme = self.root / "README.md"
        if not readme.exists():
            return None

        try:
            content = readme.read_text().lower()
        except OSError:
            return None

        has_install = "install" in content or "setup" in content
        has_requirements = (self.root / "requirements.txt").exists()
        has_dev_setup = "development" in content or "contributing" in content

        # Detect package manager
        package_manager: Literal["pip", "uv", "poetry", "conda", "unknown"] = "unknown"
        if "uv " in content or "uv pip" in content:
            package_manager = "uv"
        elif "poetry " in content or "poetry install" in content:
            package_manager = "poetry"
        elif "conda " in content or "conda install" in content:
            package_manager = "conda"
        elif "pip " in content or "pip install" in content:
            package_manager = "pip"

        return SetupInstructions(
            has_install_section=has_install,
            has_requirements=has_requirements,
            has_dev_setup=has_dev_setup,
            package_manager=package_manager,
        )

    def _extract_contributing(self) -> ContributionGuidelines | None:
        """Extract contribution guidelines."""
        contributing = self.root / "CONTRIBUTING.md"
        has_contributing = contributing.exists()

        if not has_contributing:
            return None

        try:
            content = contributing.read_text().lower()
        except OSError:
            content = ""

        has_code_style = "style" in content or "format" in content or "lint" in content

        # Check for PR/issue templates
        github_dir = self.root / ".github"
        has_pr_template = (
            (github_dir / "pull_request_template.md").exists() or
            (github_dir / "PULL_REQUEST_TEMPLATE.md").exists()
        )
        has_issue_template = (
            (github_dir / "ISSUE_TEMPLATE").exists() or
            (github_dir / "ISSUE_TEMPLATE.md").exists()
        )

        return ContributionGuidelines(
            has_contributing=has_contributing,
            has_code_style=has_code_style,
            has_pr_template=has_pr_template,
            has_issue_template=has_issue_template,
        )
