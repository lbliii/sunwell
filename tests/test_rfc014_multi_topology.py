# tests/test_rfc014_multi_topology.py
"""Tests for RFC-014: Multi-Topology Memory.

Validates correctness and complexity bounds for:
- Spatial memory (position-aware retrieval)
- Topological memory (concept graph)
- Structural memory (document hierarchy)
- Multi-faceted memory (cross-dimensional filtering)
- Unified store (hybrid queries)
"""

import pytest
import numpy as np
from pathlib import Path

from sunwell.simulacrum.topology import (
    SpatialContext, SpatialQuery, spatial_match, PositionType,
    ConceptGraph, ConceptEdge, RelationType,
    DocumentTree, DocumentSection, SectionType, infer_section_type,
    FacetedIndex, FacetQuery, ContentFacets, DiataxisType, PersonaType,
    VerificationState, ConfidenceLevel,
    MemoryNode, UnifiedMemoryStore,
)
from sunwell.simulacrum.extractors.spatial_extractor import SpatialExtractor
from sunwell.simulacrum.extractors.structural_chunker import StructuralChunker


class TestSpatialMemory:
    """Tests for spatial context matching."""
    
    def test_spatial_match_exact_section(self):
        """Section constraint filters correctly."""
        ctx = SpatialContext(
            position_type=PositionType.DOCUMENT,
            file_path="docs/rfc.md",
            section_path=("Design", "Architecture", "Caching"),
            heading_level=3,
        )
        
        query = SpatialQuery(section_contains="Caching")
        assert spatial_match(ctx, query) == 1.0
        
        query_miss = SpatialQuery(section_contains="Limitations")
        assert spatial_match(ctx, query_miss) == 0.0
    
    def test_spatial_match_file_pattern(self):
        """Glob patterns match file paths."""
        ctx = SpatialContext(
            position_type=PositionType.DOCUMENT,
            file_path="src/sunwell/simulacrum/store.py",
        )
        
        assert spatial_match(ctx, SpatialQuery(file_pattern="src/**/*.py")) == 1.0
        assert spatial_match(ctx, SpatialQuery(file_pattern="docs/*.md")) == 0.0
    
    def test_spatial_match_module_prefix(self):
        """Module prefix filtering works for code."""
        ctx = SpatialContext(
            position_type=PositionType.CODE,
            module_path="sunwell.simulacrum.store",
            class_name="UnifiedMemoryStore",
        )
        
        assert spatial_match(ctx, SpatialQuery(module_prefix="sunwell.simulacrum")) == 1.0
        assert spatial_match(ctx, SpatialQuery(module_prefix="sunwell.tools")) == 0.0
    
    def test_spatial_match_class_constraint(self):
        """Class name constraint works."""
        ctx = SpatialContext(
            position_type=PositionType.CODE,
            module_path="sunwell.simulacrum.store",
            class_name="UnifiedMemoryStore",
            function_name="query",
        )
        
        assert spatial_match(ctx, SpatialQuery(in_class="UnifiedMemoryStore")) == 1.0
        assert spatial_match(ctx, SpatialQuery(in_class="OtherClass")) == 0.0
    
    def test_spatial_context_str(self):
        """String representation is correct."""
        doc_ctx = SpatialContext(
            position_type=PositionType.DOCUMENT,
            file_path="docs/rfc.md",
            line_range=(10, 20),
            section_path=("Design", "Architecture"),
        )
        assert "docs/rfc.md:10" in str(doc_ctx)
        assert "Design > Architecture" in str(doc_ctx)
        
        code_ctx = SpatialContext(
            position_type=PositionType.CODE,
            module_path="sunwell.core",
            class_name="Agent",
            function_name="run",
        )
        assert "sunwell.core.Agent.run" == str(code_ctx)


class TestConceptGraph:
    """Tests for topological memory."""
    
    def test_add_and_get_edges(self):
        """Basic edge operations work."""
        graph = ConceptGraph()
        edge = ConceptEdge("A", "B", RelationType.ELABORATES)
        graph.add_edge(edge)
        
        outgoing = graph.get_outgoing("A")
        assert len(outgoing) == 1
        assert outgoing[0].target_id == "B"
        
        incoming = graph.get_incoming("B")
        assert len(incoming) == 1
        assert incoming[0].source_id == "A"
    
    def test_bidirectional_edges(self):
        """Bidirectional relationships create reverse edges."""
        graph = ConceptGraph()
        edge = ConceptEdge("A", "B", RelationType.CONTRADICTS)
        graph.add_edge(edge)
        
        # Both directions should have edges
        assert len(graph.get_outgoing("A")) == 1
        assert len(graph.get_outgoing("B")) == 1
    
    def test_find_path_bfs(self):
        """Shortest path found via BFS."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.ELABORATES))
        graph.add_edge(ConceptEdge("B", "C", RelationType.ELABORATES))
        graph.add_edge(ConceptEdge("A", "C", RelationType.RELATES_TO))  # Direct but different
        
        path = graph.find_path("A", "C")
        assert path is not None
        assert len(path) == 1  # Direct A→C is shortest
    
    def test_find_path_no_path(self):
        """No path returns None."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.ELABORATES))
        
        path = graph.find_path("A", "Z")
        assert path is None
    
    def test_find_dependencies_transitive(self):
        """Transitive dependency resolution works."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.DEPENDS_ON))
        graph.add_edge(ConceptEdge("B", "C", RelationType.DEPENDS_ON))
        graph.add_edge(ConceptEdge("C", "D", RelationType.DEPENDS_ON))
        
        deps = graph.find_dependencies("A")
        assert set(deps) == {"B", "C", "D"}
    
    def test_prune_removes_low_confidence(self):
        """Pruning removes edges below threshold."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.ELABORATES, confidence=0.9))
        graph.add_edge(ConceptEdge("A", "C", RelationType.ELABORATES, confidence=0.2))
        
        removed = graph.prune(min_confidence=0.5)
        assert removed == 1
        assert len(graph.get_outgoing("A")) == 1
    
    def test_neighborhood_bounded_by_depth(self):
        """Neighborhood expansion respects max_depth."""
        graph = ConceptGraph()
        # Create chain: A → B → C → D → E
        for src, tgt in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]:
            graph.add_edge(ConceptEdge(src, tgt, RelationType.ELABORATES))
        
        n1 = graph.get_neighborhood("A", depth=1)
        assert n1 == {"A", "B"}
        
        n2 = graph.get_neighborhood("A", depth=2)
        assert n2 == {"A", "B", "C"}
    
    def test_graph_serialization(self):
        """Graph serializes and deserializes correctly."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.ELABORATES, evidence="test"))
        
        data = graph.to_dict()
        loaded = ConceptGraph.from_dict(data)
        
        assert len(loaded.get_outgoing("A")) == 1
        assert loaded.get_outgoing("A")[0].evidence == "test"
    
    def test_graph_stats(self):
        """Stats property works."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.ELABORATES))
        graph.add_edge(ConceptEdge("A", "C", RelationType.ELABORATES))
        
        stats = graph.stats
        assert stats["total_edges"] == 2
        assert stats["nodes_with_edges"] == 1
        assert stats["max_out_degree"] == 2


class TestFacetedIndex:
    """Tests for multi-faceted retrieval."""
    
    def test_inverted_index_intersection(self):
        """Query uses set intersection for efficiency."""
        index = FacetedIndex()
        
        # Add nodes with different facets
        index.add("n1", ContentFacets(diataxis_type=DiataxisType.TUTORIAL))
        index.add("n2", ContentFacets(diataxis_type=DiataxisType.TUTORIAL))
        index.add("n3", ContentFacets(diataxis_type=DiataxisType.REFERENCE))
        
        results = index.query(FacetQuery(diataxis_type=DiataxisType.TUTORIAL))
        assert len(results) == 2
        assert {r[0] for r in results} == {"n1", "n2"}
    
    def test_persona_filtering(self):
        """Persona filtering works."""
        index = FacetedIndex()
        
        index.add("n1", ContentFacets(primary_persona=PersonaType.NOVICE))
        index.add("n2", ContentFacets(primary_persona=PersonaType.EXPERT))
        index.add("n3", ContentFacets(
            primary_persona=PersonaType.PRAGMATIST,
            secondary_personas=(PersonaType.NOVICE,)
        ))
        
        results = index.query(FacetQuery(persona=PersonaType.NOVICE))
        # n1 (primary) and n3 (secondary) should match
        assert len(results) == 2
    
    def test_confidence_filtering(self):
        """Min confidence filtering works."""
        index = FacetedIndex()
        
        index.add("n1", ContentFacets(confidence=ConfidenceLevel.HIGH))
        index.add("n2", ContentFacets(confidence=ConfidenceLevel.MODERATE))
        index.add("n3", ContentFacets(confidence=ConfidenceLevel.LOW))
        
        results = index.query(FacetQuery(min_confidence=ConfidenceLevel.MODERATE))
        # n1 (HIGH) and n2 (MODERATE) should match
        assert len(results) == 2
        assert {r[0] for r in results} == {"n1", "n2"}
    
    def test_domain_tag_filtering(self):
        """Domain tag AND filtering works."""
        index = FacetedIndex()
        
        index.add("n1", ContentFacets(domain_tags=("cli", "api")))
        index.add("n2", ContentFacets(domain_tags=("cli",)))
        index.add("n3", ContentFacets(domain_tags=("api",)))
        
        # AND logic: both cli AND api required
        results = index.query(FacetQuery(domain_tags=("cli", "api")))
        assert len(results) == 1
        assert results[0][0] == "n1"
    
    def test_combined_query(self):
        """Multiple facet constraints work together."""
        index = FacetedIndex()
        
        index.add("n1", ContentFacets(
            diataxis_type=DiataxisType.TUTORIAL,
            primary_persona=PersonaType.NOVICE,
        ))
        index.add("n2", ContentFacets(
            diataxis_type=DiataxisType.TUTORIAL,
            primary_persona=PersonaType.EXPERT,
        ))
        index.add("n3", ContentFacets(
            diataxis_type=DiataxisType.REFERENCE,
            primary_persona=PersonaType.NOVICE,
        ))
        
        results = index.query(FacetQuery(
            diataxis_type=DiataxisType.TUTORIAL,
            persona=PersonaType.NOVICE,
        ))
        assert len(results) == 1
        assert results[0][0] == "n1"
    
    def test_remove_node(self):
        """Removing nodes updates all indexes."""
        index = FacetedIndex()
        
        index.add("n1", ContentFacets(
            diataxis_type=DiataxisType.TUTORIAL,
            domain_tags=("cli",)
        ))
        
        index.remove("n1")
        
        results = index.query(FacetQuery(diataxis_type=DiataxisType.TUTORIAL))
        assert len(results) == 0


class TestStructural:
    """Tests for structural memory."""
    
    def test_infer_section_type(self):
        """Section type inference works."""
        assert infer_section_type("Installation Guide") == SectionType.INSTALLATION
        assert infer_section_type("API Reference") == SectionType.API
        assert infer_section_type("Known Limitations") == SectionType.LIMITATIONS
        assert infer_section_type("Random Title") == SectionType.UNKNOWN
    
    def test_document_tree_hierarchy(self):
        """Document tree maintains hierarchy correctly."""
        tree = DocumentTree(file_path="test.md")
        
        root = DocumentSection(id="root", title="RFC", level=1)
        child = DocumentSection(id="child", title="Summary", level=2, parent_id="root")
        root.child_ids.append("child")
        
        tree.add_section(root)
        tree.add_section(child)
        
        assert tree.root_id == "root"
        assert tree.get_children("root") == [child]
        assert tree.get_ancestors("child") == [root]
    
    def test_section_path(self):
        """Section path generation works."""
        tree = DocumentTree(file_path="test.md")
        
        root = DocumentSection(id="root", title="RFC", level=1)
        child = DocumentSection(id="child", title="Design", level=2, parent_id="root")
        grandchild = DocumentSection(id="grandchild", title="Cache", level=3, parent_id="child")
        
        root.child_ids.append("child")
        child.child_ids.append("grandchild")
        
        tree.add_section(root)
        tree.add_section(child)
        tree.add_section(grandchild)
        
        path = tree.get_section_path("grandchild")
        assert path == ["RFC", "Design", "Cache"]


class TestStructuralChunker:
    """Tests for structure-aware document chunking."""
    
    def test_parse_markdown(self):
        """Markdown parsing creates correct tree."""
        chunker = StructuralChunker()
        
        content = """# Title

Introduction text.

## Section 1

Section 1 content.

### Subsection 1.1

Subsection content.

## Section 2

More content here.
"""
        
        tree = chunker.parse_document("test.md", content)
        
        assert tree.root_id != ""
        root = tree.get_section(tree.root_id)
        assert root is not None
        assert root.title == "Title"
        assert len(root.child_ids) == 2
    
    def test_chunk_by_structure(self):
        """Chunking respects document structure."""
        chunker = StructuralChunker()
        
        content = """# RFC-014

## Summary

This is the summary.

## Design

This is the design.
"""
        
        chunks = chunker.chunk_document("rfc.md", content)
        
        # Should have chunks for Summary and Design sections (plus possibly title)
        assert len(chunks) >= 2
        
        # Check that spatial context includes section path
        for chunk, spatial, section in chunks:
            if "summary" in chunk.summary.lower():
                assert "Summary" in spatial.section_path


class TestSpatialExtractor:
    """Tests for spatial context extraction."""
    
    def test_from_markdown(self):
        """Markdown extraction creates spatial contexts."""
        content = """# Title

## Section 1

Content here.

## Section 2

More content.
"""
        
        chunks = SpatialExtractor.from_markdown("test.md", content)
        
        assert len(chunks) >= 2
        for text, ctx in chunks:
            assert ctx.position_type == PositionType.DOCUMENT
            assert ctx.file_path == "test.md"
    
    def test_from_python(self):
        """Python extraction identifies classes and functions."""
        content = '''
class MyClass:
    """A test class."""
    
    def my_method(self):
        pass

def standalone_function():
    pass
'''
        
        chunks = SpatialExtractor.from_python("module.py", content)
        
        # Should find class and function
        assert len(chunks) >= 2
        
        class_found = False
        func_found = False
        for text, ctx in chunks:
            if ctx.class_name == "MyClass":
                class_found = True
            if ctx.function_name == "standalone_function":
                func_found = True
        
        assert class_found
        assert func_found


class TestFacetExtractor:
    """Tests for facet extraction."""
    
    def test_detect_diataxis_type(self):
        """Diataxis type detection works."""
        from sunwell.simulacrum.extractors.facet_extractor import extract_facets_from_text
        
        tutorial_text = "In this tutorial, you will learn step by step how to..."
        facets = extract_facets_from_text(tutorial_text)
        assert facets.diataxis_type == DiataxisType.TUTORIAL
        
        reference_text = "The API specification defines the following parameters..."
        facets = extract_facets_from_text(reference_text)
        assert facets.diataxis_type == DiataxisType.REFERENCE
    
    def test_detect_persona(self):
        """Persona detection works."""
        from sunwell.simulacrum.extractors.facet_extractor import extract_facets_from_text
        
        beginner_text = "This beginner introduction covers the basic concepts..."
        facets = extract_facets_from_text(beginner_text)
        assert facets.primary_persona == PersonaType.NOVICE
        
        expert_text = "This advanced deep dive covers performance optimization..."
        facets = extract_facets_from_text(expert_text)
        assert facets.primary_persona == PersonaType.EXPERT
    
    def test_detect_domains(self):
        """Domain tag detection works."""
        from sunwell.simulacrum.extractors.facet_extractor import extract_facets_from_text
        
        cli_text = "Run the following command in your terminal..."
        facets = extract_facets_from_text(cli_text)
        assert "cli" in facets.domain_tags


class TestUnifiedStore:
    """Integration tests for unified memory store."""
    
    def test_add_and_get_node(self, tmp_path):
        """Basic node operations work."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        node = MemoryNode(id="test", content="hello world")
        store.add_node(node)
        
        retrieved = store.get_node("test")
        assert retrieved is not None
        assert retrieved.content == "hello world"
    
    def test_query_by_facets(self, tmp_path):
        """Facet-based querying works."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        store.add_node(MemoryNode(
            id="n1",
            content="Tutorial content",
            facets=ContentFacets(diataxis_type=DiataxisType.TUTORIAL),
        ))
        store.add_node(MemoryNode(
            id="n2",
            content="Reference content",
            facets=ContentFacets(diataxis_type=DiataxisType.REFERENCE),
        ))
        
        results = store.query_facets(FacetQuery(diataxis_type=DiataxisType.TUTORIAL))
        assert len(results) == 1
        assert results[0][0].id == "n1"
    
    def test_query_spatial(self, tmp_path):
        """Spatial querying works."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        store.add_node(MemoryNode(
            id="n1",
            content="Design section content",
            spatial=SpatialContext(
                position_type=PositionType.DOCUMENT,
                section_path=("Design", "Architecture"),
            ),
        ))
        
        results = store.query_spatial(SpatialQuery(section_contains="Design"))
        assert len(results) == 1
        assert results[0][0].id == "n1"
    
    def test_hybrid_query_combines_filters(self, tmp_path):
        """Hybrid query intersects spatial + facet constraints."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        # Add nodes
        store.add_node(MemoryNode(
            id="n1",
            content="Caching improves performance",
            spatial=SpatialContext(
                position_type=PositionType.DOCUMENT,
                section_path=("Design", "Caching"),
            ),
            facets=ContentFacets(diataxis_type=DiataxisType.EXPLANATION),
        ))
        store.add_node(MemoryNode(
            id="n2",
            content="Caching tutorial",
            spatial=SpatialContext(
                position_type=PositionType.DOCUMENT,
                section_path=("Tutorial", "Caching"),
            ),
            facets=ContentFacets(diataxis_type=DiataxisType.TUTORIAL),
        ))
        
        results = store.query(
            text_query="caching",
            spatial_query=SpatialQuery(section_contains="Design"),
            facet_query=FacetQuery(diataxis_type=DiataxisType.EXPLANATION),
        )
        
        assert len(results) == 1
        assert results[0][0].id == "n1"
    
    def test_save_load_roundtrip(self, tmp_path):
        """Store persists and loads correctly."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        store.add_node(MemoryNode(
            id="test",
            content="hello world",
            facets=ContentFacets(diataxis_type=DiataxisType.TUTORIAL),
        ))
        store.save()
        
        loaded = UnifiedMemoryStore.load(tmp_path, embedding_dims=384)
        assert loaded.get_node("test") is not None
        assert loaded.get_node("test").content == "hello world"
    
    def test_graph_operations(self, tmp_path):
        """Graph-based queries work."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        store.add_node(MemoryNode(id="A", content="Content A"))
        store.add_node(MemoryNode(id="B", content="Content B"))
        
        # Add relationship
        store._concept_graph.add_edge(ConceptEdge(
            source_id="A",
            target_id="B",
            relation=RelationType.ELABORATES,
        ))
        
        elaborations = store.find_elaborations("B")
        assert len(elaborations) == 1
        assert elaborations[0].id == "A"
    
    def test_stats(self, tmp_path):
        """Stats property works."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        store.add_node(MemoryNode(id="test", content="hello"))
        
        stats = store.stats
        assert stats["total_nodes"] == 1


class TestMemoryNode:
    """Tests for MemoryNode serialization."""
    
    def test_to_dict_and_from_dict(self):
        """Node serialization roundtrip works."""
        node = MemoryNode(
            id="test",
            content="hello world",
            spatial=SpatialContext(
                position_type=PositionType.DOCUMENT,
                file_path="test.md",
                section_path=("Design", "Cache"),
            ),
            facets=ContentFacets(
                diataxis_type=DiataxisType.EXPLANATION,
                primary_persona=PersonaType.PRAGMATIST,
                domain_tags=("api", "cli"),
            ),
        )
        
        data = node.to_dict()
        loaded = MemoryNode.from_dict(data)
        
        assert loaded.id == node.id
        assert loaded.content == node.content
        assert loaded.spatial.section_path == node.spatial.section_path
        assert loaded.facets.diataxis_type == node.facets.diataxis_type
        assert loaded.facets.domain_tags == node.facets.domain_tags
    
    def test_summary(self):
        """Summary generation works."""
        node = MemoryNode(
            id="test",
            content="This is a long piece of content that should be truncated in the summary.",
            spatial=SpatialContext(
                position_type=PositionType.DOCUMENT,
                file_path="test.md",
            ),
            facets=ContentFacets(diataxis_type=DiataxisType.TUTORIAL),
        )
        
        summary = node.summary()
        assert "(tutorial)" in summary
