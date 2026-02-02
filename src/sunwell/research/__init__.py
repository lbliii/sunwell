"""Magnetic Research - GitHub codebase analysis for pattern discovery.

This package provides tools to search GitHub repositories and extract
architectural patterns using magnetic search techniques.

Usage:
    from sunwell.research import GitHubSearcher, RepoFetcher, MagneticAnalyzer

    async with GitHubSearcher() as searcher:
        repos = await searcher.search("todo app in svelte")

    async with RepoFetcher() as fetcher:
        fetched = await fetcher.fetch(repos)

    analyzer = MagneticAnalyzer()
    analyses = [analyzer.analyze(repo) for repo in fetched]
"""

from sunwell.research.analyzer import (
    MagneticAnalyzer,
    PythonExtractor,
    PythonGraphBuilder,
    RosettesExtractor,
)
from sunwell.research.classifier import (
    ClassifiedFragment,
    FunctionCategory,
    FunctionClassifier,
)
from sunwell.research.fetcher import RepoFetcher
from sunwell.research.github import GitHubSearcher
from sunwell.research.reporter import ResearchReporter, format_for_tool
from sunwell.research.synthesizer import PatternSynthesizer
from sunwell.research.types import (
    ClassifiedPatterns,
    ClassifiedQuery,
    CodeFragment,
    CodeGraph,
    EdgeType,
    ExtractionPattern,
    ExtractionResult,
    FetchedRepo,
    GraphEdge,
    GraphNode,
    Intent,
    IntentClassifier,
    NodeType,
    PatternGenerator,
    RepoAnalysis,
    RepoResult,
    ResearchIntent,
    SynthesizedPatterns,
)

__all__ = [
    # Core components
    "GitHubSearcher",
    "RepoFetcher",
    "MagneticAnalyzer",
    "PatternSynthesizer",
    "ResearchReporter",
    "format_for_tool",
    # Extractors and builders
    "PythonExtractor",
    "PythonGraphBuilder",
    "RosettesExtractor",
    # Function classifier
    "FunctionClassifier",
    "FunctionCategory",
    "ClassifiedFragment",
    # Intent classification
    "IntentClassifier",
    "PatternGenerator",
    "ClassifiedQuery",
    # Core types
    "NodeType",
    "EdgeType",
    "GraphNode",
    "GraphEdge",
    "CodeGraph",
    "CodeFragment",
    "ExtractionResult",
    "ExtractionPattern",
    "Intent",
    "ResearchIntent",
    # Research types
    "RepoResult",
    "FetchedRepo",
    "RepoAnalysis",
    "SynthesizedPatterns",
    "ClassifiedPatterns",
]
