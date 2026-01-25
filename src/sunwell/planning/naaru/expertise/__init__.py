"""Expertise-Aware Planning (RFC-039).

Provides automatic domain detection, lens discovery, and expertise injection
for artifact planning. Enables the goal-first interface to leverage domain
expertise without requiring explicit lens specification.

Architecture:
```
Goal → DomainClassifier → LensDiscovery → ExpertiseExtractor
                                                ↓
                          ExpertiseContext (heuristics, validators)
                                                ↓
                    ExpertiseAwareArtifactPlanner (heuristic-informed)
```

Example:
    >>> from sunwell.planning.naaru.expertise import (
    ...     DomainClassifier,
    ...     LensDiscovery,
    ...     ExpertiseExtractor,
    ...     ExpertiseAwareArtifactPlanner,
    ... )
    >>>
    >>> classifier = DomainClassifier()
    >>> domain, confidence = classifier.classify("Write docs for the CLI")
    >>> # domain = "documentation", confidence = 0.9
    >>>
    >>> discovery = LensDiscovery()
    >>> lenses = await discovery.discover(domain)
    >>> # lenses = [tech-writer.lens, ...]
    >>>
    >>> extractor = ExpertiseExtractor(lenses)
    >>> expertise = await extractor.extract("Write docs for the CLI")
    >>> # expertise.heuristics = [Progressive Disclosure, Diataxis, ...]
"""

from sunwell.planning.naaru.expertise.classifier import (
    Domain,
    DomainClassification,
    DomainClassifier,
)
from sunwell.planning.naaru.expertise.context import (
    ExpertiseContext,
    HeuristicSummary,
)
from sunwell.planning.naaru.expertise.discovery import (
    LensDiscovery,
    LensSource,
)
from sunwell.planning.naaru.expertise.extractor import (
    ExpertiseExtractor,
)

__all__ = [
    # Classification
    "Domain",
    "DomainClassifier",
    "DomainClassification",
    # Discovery
    "LensDiscovery",
    "LensSource",
    # Extraction
    "ExpertiseExtractor",
    "ExpertiseContext",
    "HeuristicSummary",
]
