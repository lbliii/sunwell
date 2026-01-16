#!/usr/bin/env python3
"""Demo of RFC-015 Mirror Neurons - Self-Introspection Toolkit.

This demo shows how Sunwell can examine and understand itself,
analyze its own behavior patterns, and propose improvements.

Usage:
    python examples/mirror_demo.py
"""

import asyncio
import json
from pathlib import Path

from sunwell.mirror import (
    MirrorHandler,
    SourceIntrospector,
    PatternAnalyzer,
    FailureAnalyzer,
    ProposalManager,
)
from sunwell.mirror.safety import validate_diff_safety


def banner(text: str) -> None:
    """Print a section banner."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60 + "\n")


async def demo_introspection():
    """Demonstrate source code introspection."""
    banner("1. Source Code Introspection")
    
    # Find Sunwell root (parent of examples directory)
    sunwell_root = Path(__file__).parent.parent
    introspector = SourceIntrospector(sunwell_root)
    
    # List available modules
    print("Available Sunwell modules:")
    modules = introspector.list_modules()
    for mod in modules[:10]:  # First 10
        print(f"  - {mod}")
    print(f"  ... and {len(modules) - 10} more\n")
    
    # Get structure of the tools module
    print("Structure of sunwell.tools.executor:")
    structure = introspector.get_module_structure("sunwell.tools.executor")
    for cls in structure["classes"]:
        print(f"  class {cls['name']}")
        for method in cls["methods"][:5]:
            print(f"    - {method}()")
        if len(cls["methods"]) > 5:
            print(f"    ... and {len(cls['methods']) - 5} more methods")
    
    # Find a specific symbol
    print("\nFinding 'ToolExecutor' class:")
    symbol = introspector.find_symbol("sunwell.tools.executor", "ToolExecutor")
    print(f"  Type: {symbol['type']}")
    print(f"  Lines: {symbol['start_line']}-{symbol['end_line']}")
    print(f"  Methods: {len(symbol['methods'])}")
    print(f"  Docstring preview: {symbol['docstring'][:100]}...")


async def demo_pattern_analysis():
    """Demonstrate behavior pattern analysis."""
    banner("2. Behavior Pattern Analysis")
    
    from dataclasses import dataclass
    from datetime import datetime, timedelta
    import random
    
    # Create mock audit log entries
    @dataclass
    class MockEntry:
        tool_name: str
        success: bool
        execution_time_ms: int
        timestamp: datetime
        error: str | None = None
    
    # Simulate some tool usage patterns
    tools = ["read_file", "write_file", "search_files", "run_command"]
    entries = []
    
    for i in range(50):
        tool = random.choice(tools)
        success = random.random() > 0.1  # 90% success rate
        time_ms = random.randint(5, 100)
        timestamp = datetime.now() - timedelta(minutes=random.randint(0, 60))
        error = None if success else random.choice(["Not found", "Permission denied", "Timeout"])
        
        entries.append(MockEntry(tool, success, time_ms, timestamp, error))
    
    analyzer = PatternAnalyzer()
    
    # Analyze tool usage
    print("Tool Usage Patterns:")
    usage = analyzer.analyze_tool_usage(entries, "session")
    for tool, count in sorted(usage["tool_counts"].items(), key=lambda x: -x[1]):
        rate = usage["success_rates"][tool]
        print(f"  {tool}: {count} calls ({rate*100:.0f}% success)")
    
    # Analyze latency
    print("\nLatency Analysis:")
    latency = analyzer.analyze_latency(entries, "session")
    print(f"  Average: {latency['overall']['avg_ms']:.1f}ms")
    print(f"  Min: {latency['overall']['min_ms']}ms")
    print(f"  Max: {latency['overall']['max_ms']}ms")
    
    # Analyze errors
    print("\nError Analysis:")
    errors = analyzer.analyze_errors(entries, "session")
    print(f"  Total errors: {errors['total_errors']}")
    print(f"  Error rate: {errors['error_rate']*100:.1f}%")
    if errors["by_category"]:
        print("  By category:")
        for cat, count in errors["by_category"].items():
            print(f"    - {cat}: {count}")


async def demo_failure_analysis():
    """Demonstrate failure diagnosis."""
    banner("3. Failure Diagnosis")
    
    analyzer = FailureAnalyzer()
    
    errors = [
        "Permission denied: /etc/passwd",
        "Rate limit exceeded. Please wait.",
        "File not found: config.yaml",
        "Connection timeout after 30s",
        "Some weird error nobody has seen before",
    ]
    
    print("Analyzing error messages:\n")
    for error in errors:
        result = analyzer.analyze(error)
        print(f"Error: {error}")
        print(f"  Category: {result['category']}")
        print(f"  Confidence: {result['confidence']*100:.0f}%")
        print(f"  Suggestion: {result['suggestion']}")
        print()


async def demo_proposals():
    """Demonstrate the proposal system."""
    banner("4. Self-Improvement Proposals")
    
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        manager = ProposalManager(Path(tmp))
        
        # Create a proposal
        print("Creating improvement proposal...")
        proposal = manager.create_proposal(
            proposal_type="heuristic",
            title="Add brevity check for responses",
            rationale=(
                "Analysis shows average response length of 847 tokens with "
                "40% edit rate for truncation. Users prefer concise responses."
            ),
            evidence=[
                "Session avg: 847 tokens",
                "User edit rate: 40% (truncation)",
                "Explicit feedback: 'too verbose'",
            ],
            diff="""
+ - name: "brevity_check"
+   rule: "Target responses under 400 tokens unless complexity requires more"
+   trigger: "response_length > 400"
+   action: "compress and summarize"
            """.strip(),
        )
        
        print(f"  Created: {proposal.id}")
        print(f"  Status: {proposal.status.value}")
        print(f"  Type: {proposal.type.value}")
        
        # Submit for review
        print("\nSubmitting for review...")
        proposal = manager.submit_for_review(proposal.id)
        print(f"  Status: {proposal.status.value}")
        
        # Approve
        print("\nApproving proposal...")
        proposal = manager.approve_proposal(proposal.id)
        print(f"  Status: {proposal.status.value}")
        
        # Apply
        print("\nApplying proposal...")
        proposal = manager.apply_proposal(proposal.id, "original_heuristics: []")
        print(f"  Status: {proposal.status.value}")
        print(f"  Applied at: {proposal.applied_at}")
        
        # Show stats
        print("\nProposal Statistics:")
        stats = manager.get_stats()
        print(f"  Total: {stats['total']}")
        for status, count in stats["by_status"].items():
            print(f"    {status}: {count}")


async def demo_safety():
    """Demonstrate safety guardrails."""
    banner("5. Safety Guardrails")
    
    print("Testing diff safety validation:\n")
    
    test_cases = [
        ("+ brevity_check: true", True, "Safe heuristic addition"),
        ("trust_level = FULL", False, "Trust escalation attempt"),
        ("exec(user_input)", False, "Code execution attempt"),
        ("safety_policy.rate_limits = 999", False, "Safety policy modification"),
        ("+ new_validator: check_length", True, "Safe validator addition"),
        ("os.system('rm -rf /')", False, "Shell command injection"),
    ]
    
    for diff, expected_safe, description in test_cases:
        is_safe, reason = validate_diff_safety(diff)
        status = "✓" if is_safe == expected_safe else "✗"
        result = "SAFE" if is_safe else "BLOCKED"
        print(f"  {status} {description}")
        print(f"    Diff: {diff[:50]}...")
        print(f"    Result: {result}")
        if not is_safe:
            print(f"    Reason: {reason}")
        print()


async def demo_handler():
    """Demonstrate the integrated handler."""
    banner("6. Integrated Mirror Handler")
    
    import tempfile
    
    sunwell_root = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as tmp:
        handler = MirrorHandler(
            sunwell_root=sunwell_root,
            storage_path=Path(tmp),
        )
        
        # Introspect source
        print("Introspecting sunwell.mirror module...")
        result = await handler.handle("introspect_source", {
            "module": "sunwell.mirror",
        })
        data = json.loads(result)
        if "structure" in data:
            classes = [c["name"] for c in data["structure"]["classes"]]
            print(f"  Classes found: {', '.join(classes)}")
        
        # Create and track a proposal
        print("\nCreating proposal via handler...")
        result = await handler.handle("propose_improvement", {
            "scope": "heuristic",
            "problem": "Demo improvement",
            "evidence": ["Evidence from demo"],
            "diff": "+ demo_setting: true",
        })
        data = json.loads(result)
        if "proposal_id" in data:
            print(f"  Proposal ID: {data['proposal_id']}")
            print(f"  Status: {data['status']}")
        
        # Check rate limits
        print("\nRate limit status:")
        limits = handler.get_rate_limits()
        print(f"  Proposals: {limits['proposals']['used']}/{limits['proposals']['limit']} used")
        print(f"  Applications: {limits['applications']['used']}/{limits['applications']['limit']} used")


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  RFC-015 Mirror Neurons Demo")
    print("  Self-Introspection and Self-Programming Toolkit")
    print("="*60)
    
    await demo_introspection()
    await demo_pattern_analysis()
    await demo_failure_analysis()
    await demo_proposals()
    await demo_safety()
    await demo_handler()
    
    banner("Demo Complete!")
    print("""
Mirror neurons give Sunwell the ability to:
  1. Introspect - Read and understand its own source code
  2. Analyze - Detect patterns in its behavior
  3. Diagnose - Identify and explain failures
  4. Propose - Generate improvement proposals
  5. Apply - Make changes with safety guardrails
  6. Learn - Persist insights for future sessions

This closes the loop from "AI that uses heuristics" to 
"AI that evolves its own heuristics."
""")


if __name__ == "__main__":
    asyncio.run(main())
