#!/usr/bin/env python3
"""Demo: RFC-134 Agent Loop Differentiators in Action.

This script demonstrates all 4 differentiating features:
1. Tool Call Introspection - auto-repairs malformed arguments
2. Retry with Strategy Escalation - recovers from failures
3. Tool Usage Learning - tracks successful patterns
4. Progressive Tool Enablement - unlocks tools as trust builds

Run with: python examples/demo_rfc134_features.py
"""

import asyncio
from pathlib import Path

# =============================================================================
# Feature 1: Tool Call Introspection Demo
# =============================================================================


def demo_introspection() -> None:
    """Demonstrate tool call introspection repairing malformed arguments."""
    from sunwell.agent.introspection import introspect_tool_call
    from sunwell.models.protocol import ToolCall

    print("\n" + "=" * 60)
    print("🔧 FEATURE 1: Tool Call Introspection")
    print("=" * 60)

    workspace = Path("/project")

    # Scenario 1: Markdown fences in code content
    print("\n📌 Scenario: LLM outputs markdown fences in code content")
    tc1 = ToolCall(
        id="call_1",
        name="write_file",
        arguments={
            "path": "src/main.py",
            "content": '```python\nprint("Hello, World!")\n```',
        },
    )
    print(f"   Input content: {tc1.arguments['content']!r}")

    result1 = introspect_tool_call(tc1, workspace)
    print(f"   Repaired content: {result1.tool_call.arguments['content']!r}")
    print(f"   Repairs made: {result1.repairs}")
    print(f"   ✅ Markdown fences stripped automatically!")

    # Scenario 2: Leading ./ in path
    print("\n📌 Scenario: LLM outputs relative path with ./")
    tc2 = ToolCall(
        id="call_2",
        name="read_file",
        arguments={"path": "./src/utils/helpers.py"},
    )
    print(f"   Input path: {tc2.arguments['path']!r}")

    result2 = introspect_tool_call(tc2, workspace)
    print(f"   Repaired path: {result2.tool_call.arguments['path']!r}")
    print(f"   Repairs made: {result2.repairs}")
    print(f"   ✅ Path normalized automatically!")

    # Scenario 3: Empty required argument (blocked)
    print("\n📌 Scenario: LLM outputs empty required argument")
    tc3 = ToolCall(
        id="call_3",
        name="write_file",
        arguments={"path": "", "content": "some code"},
    )
    print(f"   Input path: {tc3.arguments['path']!r}")

    result3 = introspect_tool_call(tc3, workspace)
    print(f"   Blocked: {result3.blocked}")
    print(f"   Reason: {result3.block_reason}")
    print(f"   ✅ Invalid call blocked before execution!")


# =============================================================================
# Feature 2: Tool Usage Learning Demo
# =============================================================================


def demo_tool_learning() -> None:
    """Demonstrate tool usage pattern learning."""
    from sunwell.agent.learning import LearningStore, classify_task_type

    print("\n" + "=" * 60)
    print("📚 FEATURE 3: Tool Usage Learning")
    print("=" * 60)

    store = LearningStore()

    # Simulate several sessions with different tasks
    print("\n📌 Simulating tool usage across multiple tasks...")

    # API tasks - read_file → edit_file works well
    for i in range(5):
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)
    store.record_tool_sequence("api", ["read_file", "edit_file"], success=False)
    print("   Recorded 6 API tasks using read_file → edit_file (5 success, 1 fail)")

    # Test tasks - read_file → write_file works well
    for i in range(4):
        store.record_tool_sequence("test", ["read_file", "write_file"], success=True)
    print("   Recorded 4 test tasks using read_file → write_file (4 success)")

    # New file tasks - write_file alone is less successful
    store.record_tool_sequence("new_file", ["write_file"], success=True)
    store.record_tool_sequence("new_file", ["write_file"], success=False)
    store.record_tool_sequence("new_file", ["write_file"], success=False)
    print("   Recorded 3 new_file tasks using write_file only (1 success, 2 fail)")

    # Now check suggestions
    print("\n📌 Checking learned suggestions...")

    task1 = "Add a REST API endpoint for users"
    task_type1 = classify_task_type(task1)
    suggestion1 = store.format_tool_suggestions(task_type1)
    print(f"\n   Task: '{task1}'")
    print(f"   Classified as: {task_type1}")
    print(f"   Suggestion: {suggestion1}")

    task2 = "Write unit tests for the auth module"
    task_type2 = classify_task_type(task2)
    suggestion2 = store.format_tool_suggestions(task_type2)
    print(f"\n   Task: '{task2}'")
    print(f"   Classified as: {task_type2}")
    print(f"   Suggestion: {suggestion2}")

    # Show all patterns
    print("\n📌 All learned patterns:")
    for pattern in store.get_tool_patterns(min_samples=2):
        print(
            f"   {pattern.task_type}: {' → '.join(pattern.tool_sequence)} "
            f"({pattern.success_rate:.0%} success, {pattern.success_count + pattern.failure_count} samples)"
        )

    print("\n   ✅ Patterns learned and ready for future tasks!")


# =============================================================================
# Feature 3: Progressive Tool Enablement Demo
# =============================================================================


def demo_progressive_tools() -> None:
    """Demonstrate progressive tool enablement."""
    from sunwell.tools.progressive import ProgressivePolicy
    from sunwell.tools.types import ToolTrust

    print("\n" + "=" * 60)
    print("🔐 FEATURE 4: Progressive Tool Enablement")
    print("=" * 60)

    policy = ProgressivePolicy(base_trust=ToolTrust.SHELL)

    print("\n📌 Simulating agent turns with progressive unlocking...")

    for turn in range(1, 7):
        if turn > 1:
            policy.advance_turn()

        tools = policy.get_available_tools()
        status = policy.get_unlock_status()

        # Simulate validation passes at certain turns
        if turn == 2:
            print(f"\n   [Validation gate passed on turn 2]")
            policy.record_validation_pass()
        if turn == 4:
            print(f"\n   [Validation gate passed on turn 4]")
            policy.record_validation_pass()

        print(f"\n   Turn {turn}:")
        print(f"   Available tools ({len(tools)}): {sorted(tools)[:5]}{'...' if len(tools) > 5 else ''}")
        print(f"   Unlock status: {status}")

        # Show requirements for locked tools
        requirements = policy.get_unlock_requirements()
        if requirements:
            print(f"   To unlock more: {requirements}")

    print("\n   ✅ Tools unlocked progressively based on trust!")


# =============================================================================
# Feature 4: Retry Escalation Demo (Conceptual)
# =============================================================================


def demo_retry_escalation() -> None:
    """Demonstrate the retry escalation ladder (conceptual)."""
    print("\n" + "=" * 60)
    print("🔄 FEATURE 2: Retry with Strategy Escalation")
    print("=" * 60)

    print("\n📌 The escalation ladder when a tool fails:")
    print("""
    ┌─────────────────────────────────────────────────────────────┐
    │  Failure #1: Simple Retry                                   │
    │  └─ Maybe transient error, try same approach again          │
    ├─────────────────────────────────────────────────────────────┤
    │  Failure #2: Interference Fix                               │
    │  └─ Generate 3 perspectives on why it failed                │
    │  └─ Each perspective suggests a different fix               │
    │  └─ Synthesize into corrected tool call                     │
    ├─────────────────────────────────────────────────────────────┤
    │  Failure #3: Vortex Fix                                     │
    │  └─ Generate multiple candidate fixes at different temps    │
    │  └─ Pick the most promising one                             │
    │  └─ More exploration of solution space                      │
    ├─────────────────────────────────────────────────────────────┤
    │  Failure #4+: Record Dead-End & Escalate                    │
    │  └─ Save this approach as a dead-end for future avoidance   │
    │  └─ Ask user for help                                       │
    └─────────────────────────────────────────────────────────────┘
    """)

    print("📌 Example: edit_file fails because old_content doesn't match")
    print("""
    Turn 1: edit_file(old_content="def get_user:", ...)
            ❌ Error: old_content not found in file

    Turn 2: [Simple Retry] edit_file(same args)
            ❌ Error: old_content not found in file

    Turn 3: [Interference] Ask 3 perspectives:
            - Perspective 1: "File may have been modified"
            - Perspective 2: "Whitespace mismatch (tabs vs spaces)"
            - Perspective 3: "Function was renamed"
            → Decide to read file first to get current state

    Turn 4: read_file → edit_file(corrected old_content)
            ✅ Success!

    Turn 5: Record pattern: "read_file before edit_file = safer"
    """)

    print("   ✅ Multi-strategy recovery instead of immediate failure!")


# =============================================================================
# Main Demo
# =============================================================================


def main() -> None:
    """Run all feature demos."""
    print("\n" + "🌟" * 30)
    print("   SUNWELL RFC-134: Agent Loop Differentiators Demo")
    print("🌟" * 30)

    demo_introspection()
    demo_tool_learning()
    demo_progressive_tools()
    demo_retry_escalation()

    print("\n" + "=" * 60)
    print("🎯 SUMMARY: What Makes Sunwell Different")
    print("=" * 60)
    print("""
    ┌────────────────────┬─────────────────┬─────────────────┐
    │ Feature            │ Competitors     │ Sunwell         │
    ├────────────────────┼─────────────────┼─────────────────┤
    │ Malformed args     │ ❌ Fail         │ ✅ Auto-repair  │
    │ Tool failures      │ ❌ Model decides│ ✅ Escalation   │
    │ Pattern learning   │ ❌ None         │ ✅ Automatic    │
    │ Tool trust         │ ❌ All or none  │ ✅ Progressive  │
    └────────────────────┴─────────────────┴─────────────────┘

    The result: Higher success rates, fewer user interventions,
    and an agent that gets better the more you use it.
    """)


if __name__ == "__main__":
    main()
