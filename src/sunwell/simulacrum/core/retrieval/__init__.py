"""Retrieval modules for SimulacrumStore.

Extracted from store.py for modularity and testability.
"""

from sunwell.simulacrum.core.retrieval.context_assembler import ContextAssembler
from sunwell.simulacrum.core.retrieval.planning_retriever import PlanningRetriever
from sunwell.simulacrum.core.retrieval.semantic_retriever import SemanticRetriever
from sunwell.simulacrum.core.retrieval.similarity import cosine_similarity, keyword_similarity

__all__ = [
    "ContextAssembler",
    "PlanningRetriever",
    "SemanticRetriever",
    "cosine_similarity",
    "keyword_similarity",
]
