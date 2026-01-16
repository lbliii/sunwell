#!/usr/bin/env python3
"""RFC-014 Integration Demo - Using Multi-Topology Memory in Real Sessions.

This example demonstrates how to use the full RFC-014 integration:
1. Create a SimulacrumStore with unified memory
2. Ingest documents with automatic extraction
3. Use memory tools via the RuntimeEngine
4. Query memory using different topologies

Run with:
    python examples/rfc014_integration.py
"""

import asyncio
from pathlib import Path
import tempfile
import shutil

from sunwell.simulacrum import (
    SimulacrumStore,
    StorageConfig,
    ConversationDAG,
    UnifiedContextAssembler,
    DiataxisType,
    PersonaType,
    SpatialQuery,
    FacetQuery,
    RelationType,
)


async def main():
    """Demonstrate RFC-014 integration."""
    
    # Create a temporary directory for our session
    temp_dir = Path(tempfile.mkdtemp(prefix="sunwell_rfc014_"))
    print(f"📁 Session directory: {temp_dir}\n")
    
    try:
        # =================================================================
        # Step 1: Create SimulacrumStore with RFC-014 enabled
        # =================================================================
        print("=" * 60)
        print("Step 1: Creating SimulacrumStore with RFC-014 Memory")
        print("=" * 60)
        
        store = SimulacrumStore(
            base_path=temp_dir,
            config=StorageConfig(
                hot_max_turns=50,
                auto_cleanup=True,
            ),
        )
        
        print(f"✅ SimulacrumStore created")
        print(f"   - Unified store: {store.unified_store is not None}")
        print(f"   - Memory handler: {store.memory_handler is not None}")
        print()
        
        # =================================================================
        # Step 2: Ingest Some Documents
        # =================================================================
        print("=" * 60)
        print("Step 2: Ingesting Documents")
        print("=" * 60)
        
        # Sample documentation
        docs = {
            "getting-started.md": """# Getting Started with Sunwell

## Overview
Sunwell is a framework for building AI assistants with persistent memory.

## Installation

```bash
pip install sunwell
```

## Quick Start

```python
from sunwell import Simulacrum

# Create a new simulacrum
hs = Simulacrum.create("my-project")

# Add a message
await hs.add_user_message("Hello!")
```

## Next Steps
See the Tutorial for a complete walkthrough.
""",
            "tutorial.md": """# Sunwell Tutorial

This tutorial teaches you how to build a simple assistant.

## Prerequisites
- Python 3.10+
- Basic Python knowledge

## Step 1: Create the Lens

A Lens defines your assistant's expertise:

```python
from sunwell import Lens

lens = Lens.create("helper")
lens.add_heuristic("Be concise", "Always give short answers")
```

## Step 2: Run the Engine

```python
from sunwell import RuntimeEngine

engine = RuntimeEngine(model=my_model, lens=lens)
result = await engine.execute("What is Python?")
```

## Troubleshooting
If you get import errors, check your Python version.
""",
            "reference/api.md": """# API Reference

## Simulacrum Class

### Methods

#### create(name: str) -> Simulacrum
Create a new simulacrum with the given name.

**Parameters:**
- name: The simulacrum name

**Returns:** A new Simulacrum instance

#### add_user_message(content: str) -> str
Add a user message to working memory.

**Parameters:**
- content: The message content

**Returns:** The message ID

#### add_learning(fact: str, category: str) -> str
Add a learning to long-term memory.

**Parameters:**
- fact: The fact to remember
- category: Category for the learning

**Returns:** The learning ID
""",
        }
        
        total_nodes = 0
        for file_path, content in docs.items():
            nodes = await store.ingest_document(file_path, content)
            print(f"   📄 {file_path}: {nodes} nodes")
            total_nodes += nodes
        
        print(f"\n✅ Ingested {len(docs)} documents → {total_nodes} memory nodes")
        print()
        
        # =================================================================
        # Step 3: Use UnifiedContextAssembler for Queries
        # =================================================================
        print("=" * 60)
        print("Step 3: Querying with Multi-Topology Context")
        print("=" * 60)
        
        # Create the assembler
        dag = store.get_dag()
        assembler = UnifiedContextAssembler(
            dag=dag,
            store=store.unified_store,
        )
        
        # Query 1: General query
        print("\n📌 Query 1: 'How do I install Sunwell?'")
        ctx = await assembler.assemble(
            query="How do I install Sunwell?",
            system_prompt="You are a helpful assistant.",
        )
        print(f"   Found {len(ctx.memory_nodes)} relevant nodes")
        print(f"   Sources: {ctx.retrieval_sources}")
        if ctx.memory_nodes:
            top = ctx.memory_nodes[0]
            print(f"   Top result: {top[0].content[:100]}...")
        
        # Query 2: Filter by Diataxis type
        print("\n📌 Query 2: 'Tutorial content only'")
        ctx = await assembler.assemble(
            query="How to create a lens",
            system_prompt="You are a helpful assistant.",
            diataxis_type=DiataxisType.TUTORIAL,
        )
        print(f"   Found {len(ctx.memory_nodes)} tutorial nodes")
        if ctx.memory_nodes:
            for node, score in ctx.memory_nodes[:3]:
                facet_type = node.facets.diataxis_type.value if node.facets and node.facets.diataxis_type else "unknown"
                print(f"   - [{facet_type}] {node.content[:60]}... (score: {score:.2f})")
        
        # Query 3: Spatial query - specific file
        print("\n📌 Query 3: 'Content from reference docs'")
        ctx = await assembler.assemble(
            query="API methods",
            system_prompt="You are a helpful assistant.",
            spatial_query=SpatialQuery(file_pattern="reference/"),
        )
        print(f"   Found {len(ctx.memory_nodes)} nodes from reference/")
        if ctx.memory_nodes:
            for node, score in ctx.memory_nodes[:3]:
                file_path = node.spatial.file_path if node.spatial else "unknown"
                print(f"   - [{file_path}] {node.content[:60]}...")
        
        # Query 4: Follow relationships
        print("\n📌 Query 4: 'Follow concept relationships'")
        ctx = await assembler.assemble(
            query="Getting started basics",
            system_prompt="You are a helpful assistant.",
            follow_relations=[RelationType.ELABORATES, RelationType.FOLLOWS],
        )
        print(f"   Found {len(ctx.memory_nodes)} nodes (including related)")
        print(f"   Sources: {ctx.retrieval_sources}")
        
        print()
        
        # =================================================================
        # Step 4: Test Memory Tool Handler Directly
        # =================================================================
        print("=" * 60)
        print("Step 4: Testing Memory Tools")
        print("=" * 60)
        
        handler = store.memory_handler
        if handler:
            # Search memory
            print("\n📌 search_memory('installation')")
            result = await handler.handle("search_memory", {
                "query": "installation",
                "limit": 3,
            })
            print(f"   Result: {result[:200]}...")
            
            # Add a learning
            print("\n📌 add_learning('Sunwell is a memory framework')")
            result = await handler.handle("add_learning", {
                "fact": "Sunwell is a memory framework for AI assistants",
                "category": "product",
            })
            print(f"   Result: {result}")
            
            # Find related concepts
            print("\n📌 find_related('Sunwell installation')")
            result = await handler.handle("find_related", {
                "topic": "Sunwell installation",
                "relationship": "any",
            })
            print(f"   Result: {result[:200]}...")
        
        print()
        
        # =================================================================
        # Step 5: Session Statistics
        # =================================================================
        print("=" * 60)
        print("Step 5: Session Statistics")
        print("=" * 60)
        
        stats = store.stats()
        print(f"\n📊 Storage Stats:")
        print(f"   - Session ID: {stats['session_id']}")
        print(f"   - Hot turns: {stats['hot_turns']}")
        print(f"   - DAG learnings: {stats['dag_stats'].get('learnings', 0)}")
        
        if "unified_store" in stats:
            us = stats["unified_store"]
            print(f"\n📊 Unified Store (RFC-014):")
            print(f"   - Total nodes: {us['total_nodes']}")
            print(f"   - Total edges: {us['total_edges']}")
            print(f"   - Facet index size: {us['facet_index_size']}")
        
        # =================================================================
        # Step 6: Save Session
        # =================================================================
        print("\n" + "=" * 60)
        print("Step 6: Saving Session")
        print("=" * 60)
        
        saved_path = store.save_session("demo_session")
        print(f"\n✅ Session saved to: {saved_path}")
        
        # List what was created
        print(f"\n📁 Files created:")
        for f in sorted(temp_dir.rglob("*")):
            if f.is_file():
                size = f.stat().st_size
                print(f"   - {f.relative_to(temp_dir)}: {size:,} bytes")
        
        print("\n" + "=" * 60)
        print("✅ RFC-014 Integration Demo Complete!")
        print("=" * 60)
        print("""
Summary:
- SimulacrumStore now integrates UnifiedMemoryStore automatically
- Document ingestion extracts spatial, structural, and faceted metadata
- UnifiedContextAssembler enables multi-topology queries
- MemoryToolHandler provides tool-calling interface for LLMs
- RuntimeEngine can expose memory tools to models

The model can now:
- search_memory: Find relevant context across all topologies
- find_related: Navigate the concept graph
- add_learning: Store new facts persistently
- mark_dead_end: Avoid repeating failed approaches
- find_contradictions: Detect conflicting information
""")
        
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up {temp_dir}...")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
