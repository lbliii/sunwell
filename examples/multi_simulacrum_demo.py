#!/usr/bin/env python3
"""Multi-Simulacrum Demo - Context Switching in Action.

This example demonstrates how simulacrums mature, consolidate, and
enable context switching during a conversation:

1. Create specialized simulacrums for different domains
2. Ingest relevant content into each
3. Switch between simulacrums as conversation evolves
4. Query across all simulacrums when needed
5. Consolidate related simulacrums

Run with:
    python examples/multi_simulacrum_demo.py
"""

import asyncio
from pathlib import Path
import tempfile
import shutil

from sunwell.simulacrum.manager import (
    SimulacrumManager,
    SimulacrumToolHandler,
    SpawnPolicy,
)


async def main():
    """Demonstrate multi-simulacrum management."""
    
    # Create a temporary directory for our session
    temp_dir = Path(tempfile.mkdtemp(prefix="sunwell_multi_hs_"))
    print(f"📁 Session directory: {temp_dir}\n")
    
    try:
        # =================================================================
        # Step 1: Create SimulacrumManager
        # =================================================================
        print("=" * 60)
        print("Step 1: Creating SimulacrumManager")
        print("=" * 60)
        
        manager = SimulacrumManager(base_path=temp_dir)
        handler = SimulacrumToolHandler(manager=manager)
        
        print("✅ SimulacrumManager created")
        print()
        
        # =================================================================
        # Step 2: Create Specialized Simulacrums
        # =================================================================
        print("=" * 60)
        print("Step 2: Creating Specialized Simulacrums")
        print("=" * 60)
        
        # Security simulacrum
        security_store = manager.create(
            name="security",
            description="Security analysis, threat modeling, and vulnerability assessment",
            domains=("security", "auth", "encryption", "vulnerabilities"),
        )
        print("✅ Created 'security' simulacrum")
        
        # Performance simulacrum
        perf_store = manager.create(
            name="performance",
            description="Performance optimization, profiling, and scalability patterns",
            domains=("performance", "optimization", "caching", "scaling"),
        )
        print("✅ Created 'performance' simulacrum")
        
        # API design simulacrum
        api_store = manager.create(
            name="api-design",
            description="API design patterns, REST best practices, and schema design",
            domains=("api", "rest", "schema", "design"),
        )
        print("✅ Created 'api-design' simulacrum")
        
        # Create a specialized sub-domain simulacrum
        api_security_store = manager.create(
            name="api-security",
            description="API-specific security: rate limiting, auth tokens, CORS",
            domains=("api", "security", "rate-limiting", "auth"),
        )
        print("✅ Created 'api-security' simulacrum")
        
        print()
        
        # =================================================================
        # Step 3: Ingest Domain-Specific Content
        # =================================================================
        print("=" * 60)
        print("Step 3: Ingesting Domain-Specific Content")
        print("=" * 60)
        
        # Security content
        security_docs = {
            "threats.md": """# Threat Modeling Guide

## STRIDE Analysis
- Spoofing: Verify identity before access
- Tampering: Use signed tokens and checksums
- Repudiation: Implement audit logging
- Information Disclosure: Encrypt at rest and in transit
- Denial of Service: Rate limiting and circuit breakers
- Elevation of Privilege: Principle of least privilege
""",
            "auth.md": """# Authentication Patterns

## JWT Best Practices
- Use short expiration times (15-60 minutes)
- Implement refresh token rotation
- Store tokens securely (httpOnly cookies)
- Validate all claims on each request
""",
        }
        
        manager.activate("security")
        for path, content in security_docs.items():
            await security_store.ingest_document(path, content)
        print(f"✅ Ingested {len(security_docs)} docs into 'security' simulacrum")
        
        # Performance content
        perf_docs = {
            "caching.md": """# Caching Strategies

## Cache Levels
- L1: In-memory (fastest, limited size)
- L2: Redis/Memcached (distributed, larger)
- L3: CDN (edge caching for static assets)

## Invalidation Patterns
- TTL-based: Simple but may serve stale data
- Event-driven: More accurate but complex
- Cache-aside: Application controls caching
""",
            "profiling.md": """# Performance Profiling

## Metrics to Track
- Response time (p50, p95, p99)
- Throughput (requests/second)
- Error rate
- Resource utilization (CPU, memory)

## Tools
- cProfile for Python code profiling
- async-profiler for JVM applications
- perf for system-level profiling
""",
        }
        
        manager.activate("performance")
        for path, content in perf_docs.items():
            await perf_store.ingest_document(path, content)
        print(f"✅ Ingested {len(perf_docs)} docs into 'performance' simulacrum")
        
        # API security content (overlaps both domains)
        api_security_docs = {
            "rate-limiting.md": """# API Rate Limiting

## Algorithms
- Token bucket: Allows burst traffic
- Sliding window: More precise rate control
- Fixed window: Simplest but can be gamed

## Headers
- X-RateLimit-Limit: Max requests per window
- X-RateLimit-Remaining: Requests left
- Retry-After: When to retry (on 429)
""",
        }
        
        manager.activate("api-security")
        for path, content in api_security_docs.items():
            await api_security_store.ingest_document(path, content)
        print(f"✅ Ingested {len(api_security_docs)} docs into 'api-security' simulacrum")
        
        print()
        
        # =================================================================
        # Step 4: Demonstrate Context Switching
        # =================================================================
        print("=" * 60)
        print("Step 4: Context Switching Simulation")
        print("=" * 60)
        
        # Simulate a conversation that shifts topics
        queries = [
            ("How do I prevent unauthorized access?", "security"),
            ("My API is slow, how can I improve it?", "performance"),
            ("What's the best rate limiting approach for my REST API?", "api-security"),
            ("Should I use JWT or session cookies?", "security"),
        ]
        
        for query, expected_domain in queries:
            print(f"\n📌 User asks: '{query}'")
            
            # Get suggestion
            suggestions = manager.suggest(query)
            if suggestions:
                best_match = suggestions[0]
                print(f"   🎯 Suggested simulacrum: {best_match[0].name} ({best_match[1]:.0%} relevance)")
                
                # Auto-activate if good match
                if best_match[1] >= 0.3:
                    manager.activate(best_match[0].name)
                    print(f"   ✅ Activated: {manager.active_name}")
                    
                    # Query the now-active simulacrum
                    if manager.active and manager.active.unified_store:
                        results = manager.active.unified_store.query(
                            text_query=query,
                            limit=2,
                        )
                        if results:
                            print(f"   📚 Found {len(results)} relevant memories:")
                            for node, score in results[:2]:
                                print(f"      - {node.content[:80]}...")
        
        print()
        
        # =================================================================
        # Step 5: Cross-Simulacrum Query
        # =================================================================
        print("=" * 60)
        print("Step 5: Cross-Simulacrum Query")
        print("=" * 60)
        
        cross_query = "How do I secure and optimize my API?"
        print(f"\n📌 Cross-domain query: '{cross_query}'")
        
        all_results = manager.query_all(cross_query, limit_per_simulacrum=2)
        print(f"   Found {len(all_results)} results across all simulacrums:")
        
        by_simulacrum: dict[str, list] = {}
        for hs_name, node, score in all_results:
            if hs_name not in by_simulacrum:
                by_simulacrum[hs_name] = []
            by_simulacrum[hs_name].append((node, score))
        
        for hs_name, items in by_simulacrum.items():
            print(f"\n   From **{hs_name}**:")
            for node, score in items:
                print(f"      [{score:.0%}] {node.content[:60]}...")
        
        print()
        
        # =================================================================
        # Step 6: Find Related Simulacrums & Consolidation
        # =================================================================
        print("=" * 60)
        print("Step 6: Simulacrum Relationships & Consolidation")
        print("=" * 60)
        
        print("\n📌 Finding simulacrums related to 'api-security':")
        related = manager.find_related_simulacrums("api-security")
        for name, similarity in related:
            print(f"   - {name}: {similarity:.0%} domain overlap")
        
        # Consolidate api-security into security
        if related:
            print(f"\n📌 Merging 'api-security' into 'security'...")
            merged_count = manager.merge("api-security", into="security")
            print(f"   ✅ Merged {merged_count} items")
            print(f"   The 'api-security' simulacrum still exists (set delete_source=True to remove)")
        
        print()
        
        # =================================================================
        # Step 7: Auto-Spawning Demo
        # =================================================================
        print("=" * 60)
        print("Step 7: Auto-Spawning New Simulacrums")
        print("=" * 60)
        
        # Configure more aggressive spawning for demo
        manager.spawn_policy.min_queries_before_spawn = 3
        manager.spawn_policy.coherence_threshold = 0.3
        manager.spawn_policy.novelty_threshold = 0.5
        
        print("\n📌 Simulating queries about a completely new topic (ML/AI)...")
        print("   (These don't match any existing simulacrum)")
        
        # Queries with overlapping keywords to cluster together
        ml_queries = [
            "How do I train a machine learning model?",
            "What training data do I need for machine learning?",
            "How to train my model on GPU for machine learning?",
            "Best practices for machine learning training?",
            "Machine learning model training tips?",  # Extra to ensure spawn
        ]
        
        for i, query in enumerate(ml_queries):
            print(f"\n   Query {i+1}: '{query}'")
            store, was_spawned, explanation = manager.route_query(query)
            print(f"   → {explanation}")
            
            if was_spawned:
                print(f"   🆕 New simulacrum auto-created!")
                break
        
        # Check spawn status
        print("\n📌 Spawn status after ML queries:")
        status = manager.check_spawn_status()
        print(f"   Pending domains: {len(status['pending_domains'])}")
        for domain in status['pending_domains']:
            print(f"   - Keywords: {domain['top_keywords']}, coherence: {domain['coherence']:.0%}")
        
        # List simulacrums to see if new one was created
        print("\n📌 Current simulacrums after auto-spawn:")
        for meta in manager.list_simulacrums():
            auto_tag = " (auto)" if meta.auto_spawned else ""
            print(f"   - {meta.name}{auto_tag}: {meta.description[:50]}...")
        
        print()
        
        # =================================================================
        # Step 8: Use Simulacrum Tools (as agent would)
        # =================================================================
        print("=" * 60)
        print("Step 8: Testing Simulacrum Tools")
        print("=" * 60)
        
        # List simulacrums
        print("\n📌 list_simulacrums()")
        result = await handler.handle("list_simulacrums", {})
        print(result)
        
        # Suggest simulacrum
        print("\n📌 suggest_simulacrum('authentication tokens')")
        result = await handler.handle("suggest_simulacrum", {"topic": "authentication tokens"})
        print(result)
        
        # Current simulacrum info
        print("\n📌 current_simulacrum()")
        result = await handler.handle("current_simulacrum", {})
        print(result)
        
        print()
        
        # =================================================================
        # Step 9: Statistics
        # =================================================================
        print("=" * 60)
        print("Step 9: Manager Statistics")
        print("=" * 60)
        
        stats = manager.stats()
        print(f"\n📊 Multi-Simulacrum Stats:")
        print(f"   - Total simulacrums: {stats['simulacrum_count']}")
        print(f"   - Active: {stats['active']}")
        print(f"   - Total nodes: {stats['total_nodes']}")
        print(f"   - Total learnings: {stats['total_learnings']}")
        
        print("\n   Individual simulacrums:")
        for hs in stats['simulacrums']:
            print(f"      - {hs['name']}: {hs['nodes']} nodes, {hs['accesses']} accesses")
            print(f"        domains: {', '.join(hs['domains'])}")
        
        # Save everything
        manager.save_all()
        print("\n✅ All simulacrums saved")
        
        print("\n" + "=" * 60)
        print("✅ Multi-Simulacrum Demo Complete!")
        print("=" * 60)
        print("""
Summary:
- Multiple simulacrums can be created for different domains/roles
- The agent can switch between them as conversation evolves
- Cross-simulacrum queries find knowledge across all contexts
- Related simulacrums can be merged as they mature
- Simulacrum tools allow the LLM to manage its own contexts
- AUTO-SPAWNING: New simulacrums are created automatically when:
  • Queries don't match existing simulacrums (novel domain)
  • Enough queries accumulate (min_queries threshold)
  • Queries are coherent (coherence threshold)

This enables:
- "Let me think about this from a security perspective..." → switches simulacrum
- "I need both security AND performance info..." → queries all simulacrums
- Domain knowledge doesn't pollute unrelated contexts
- Specialized expertise accumulates in the right places
- Novel domains AUTOMATICALLY get their own simulacrum!
""")
        
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up {temp_dir}...")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
