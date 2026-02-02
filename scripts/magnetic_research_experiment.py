#!/usr/bin/env python3
"""Magnetic Research Experiment - GitHub Pattern Discovery.

Search GitHub for related projects and analyze them using magnetic search
to extract common patterns, architecture, and best practices.

Usage:
    python scripts/magnetic_research_experiment.py "todo app in svelte"
    python scripts/magnetic_research_experiment.py "auth system in fastapi" --max-repos 5
    python scripts/magnetic_research_experiment.py "cli tool in python" --output report.md
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunwell.research.analyzer import MagneticAnalyzer
from sunwell.research.fetcher import RepoFetcher
from sunwell.research.github import GitHubSearcher
from sunwell.research.reporter import ResearchReporter
from sunwell.research.synthesizer import PatternSynthesizer
from sunwell.research.types import ResearchIntent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_query(query: str) -> tuple[str, str | None]:
    """Parse query to extract search terms and language hint.

    Args:
        query: User query like "todo app in svelte" or "auth system fastapi"

    Returns:
        Tuple of (search_terms, language_hint)
    """
    query = query.lower().strip()

    # Language mappings
    language_hints = {
        "python": "python",
        "py": "python",
        "fastapi": "python",
        "django": "python",
        "flask": "python",
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "typescript",
        "ts": "typescript",
        "svelte": "svelte",
        "sveltekit": "svelte",
        "react": "javascript",
        "vue": "vue",
        "go": "go",
        "golang": "go",
        "rust": "rust",
    }

    detected_language = None
    search_terms = query

    # Check for "in <language>" pattern
    if " in " in query:
        parts = query.rsplit(" in ", 1)
        search_terms = parts[0]
        lang_hint = parts[1].strip()
        detected_language = language_hints.get(lang_hint, lang_hint)

    # Also check for language keywords in the query
    for keyword, lang in language_hints.items():
        if keyword in query.split():
            detected_language = lang
            break

    return search_terms, detected_language


async def run_research(
    query: str,
    max_repos: int = 3,
    min_stars: int = 50,
    focus: str = "architecture",
    output_file: Path | None = None,
    cleanup: bool = True,
) -> str:
    """Run the full research pipeline.

    Args:
        query: Research query (e.g., "todo app in svelte")
        max_repos: Maximum repositories to analyze
        min_stars: Minimum stars filter for search
        focus: Research focus ("architecture", "patterns", "examples")
        output_file: Optional file to write report
        cleanup: Whether to clean up cloned repos

    Returns:
        Markdown research report
    """
    # Parse query
    search_terms, language = parse_query(query)
    logger.info("Research query: %s (language: %s)", search_terms, language or "any")

    # Map focus to intent
    intent_map = {
        "architecture": ResearchIntent.ARCHITECTURE,
        "patterns": ResearchIntent.PATTERNS,
        "examples": ResearchIntent.EXAMPLES,
        "best-practices": ResearchIntent.BEST_PRACTICES,
    }
    intent = intent_map.get(focus, ResearchIntent.ARCHITECTURE)

    # Initialize components
    searcher = GitHubSearcher()
    fetcher = RepoFetcher()
    analyzer = MagneticAnalyzer()
    synthesizer = PatternSynthesizer()
    reporter = ResearchReporter()

    try:
        # Step 1: Search GitHub
        logger.info("Searching GitHub for: %s", search_terms)
        repos = await searcher.search(
            query=search_terms,
            language=language,
            min_stars=min_stars,
            max_results=max_repos,
        )

        if not repos:
            logger.warning("No repositories found matching query")
            return f"# Research: {query}\n\nNo repositories found matching your query."

        logger.info("Found %d repositories", len(repos))
        for repo in repos:
            logger.info("  - %s (%d⭐)", repo.full_name, repo.stars)

        # Step 2: Fetch repositories
        logger.info("Cloning repositories...")
        fetched = await fetcher.fetch(repos)

        if not fetched:
            logger.warning("Failed to clone any repositories")
            return f"# Research: {query}\n\nFailed to clone repositories."

        logger.info("Cloned %d repositories", len(fetched))

        # Step 3: Analyze each repository
        logger.info("Analyzing repositories...")
        analyses = []
        for repo in fetched:
            logger.info("  Analyzing %s...", repo.repo.full_name)
            analysis = analyzer.analyze(repo, intent)
            analyses.append(analysis)
            logger.info(
                "    Found %d classes/functions, %d patterns",
                len(analysis.structure),
                len(analysis.patterns),
            )

        # Step 4: Synthesize patterns
        logger.info("Synthesizing patterns across repositories...")
        patterns = synthesizer.synthesize(analyses)

        # Step 5: Generate report
        logger.info("Generating report...")
        report = reporter.format_markdown(query, repos, analyses, patterns)

        # Write to file if specified
        if output_file:
            output_file.write_text(report)
            logger.info("Report written to: %s", output_file)

        return report

    finally:
        # Cleanup
        await searcher.close()
        if cleanup:
            await fetcher.cleanup()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Research GitHub repositories using magnetic search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s "todo app in svelte"
    %(prog)s "auth system in fastapi" --max-repos 5
    %(prog)s "cli tool in python" --output report.md --focus patterns
        """,
    )

    parser.add_argument(
        "query",
        help="Research query (e.g., 'todo app in svelte')",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=3,
        help="Maximum repositories to analyze (default: 3)",
    )
    parser.add_argument(
        "--min-stars",
        type=int,
        default=50,
        help="Minimum stars filter (default: 50)",
    )
    parser.add_argument(
        "--focus",
        choices=["architecture", "patterns", "examples", "best-practices"],
        default="architecture",
        help="Research focus (default: architecture)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file for report (default: stdout)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't clean up cloned repositories",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run research
    report = asyncio.run(
        run_research(
            query=args.query,
            max_repos=args.max_repos,
            min_stars=args.min_stars,
            focus=args.focus,
            output_file=args.output,
            cleanup=not args.no_cleanup,
        )
    )

    # Print to stdout if no output file
    if not args.output:
        print(report)


if __name__ == "__main__":
    main()
