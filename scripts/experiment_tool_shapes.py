#!/usr/bin/env python3
"""Experiment: Compare tool shapes for model comprehension.

Tests whether domain-grouped tools improve tool selection accuracy
compared to fine-grained individual tools.

Usage:
    uv run python scripts/experiment_tool_shapes.py --model llama3.1:8b
    uv run python scripts/experiment_tool_shapes.py --model qwen2.5:3b
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Tool Shape A: Fine-grained (current approach)
# =============================================================================

TOOLS_FINE_GRAINED = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_env",
            "description": "List available environment variables",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_env",
            "description": "Get value of an environment variable",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Environment variable name"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"}
                },
                "required": ["command"]
            }
        }
    },
]


# =============================================================================
# Tool Shape B: Domain-grouped
# =============================================================================

TOOLS_DOMAIN_GROUPED = [
    {
        "type": "function",
        "function": {
            "name": "filesystem",
            "description": "Perform filesystem operations: list directories, read files, write files",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "read", "write"],
                        "description": "Action to perform"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (only for write action)"
                    }
                },
                "required": ["action", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "environment",
            "description": "Access environment variables: list all variables or get a specific one",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get"],
                        "description": "Action: 'list' for all vars, 'get' for specific var"
                    },
                    "name": {
                        "type": "string",
                        "description": "Variable name (only for 'get' action)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Execute shell commands",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
]


# =============================================================================
# Tool Shape C: Ultra-minimal (just 2 tools)
# =============================================================================

TOOLS_MINIMAL = [
    {
        "type": "function",
        "function": {
            "name": "query",
            "description": "Query information from the system (files, environment, git status, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["files", "file_content", "env_vars", "env_var", "git_status"],
                        "description": "What to query"
                    },
                    "path_or_name": {
                        "type": "string",
                        "description": "Path for files, name for env var, etc."
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify",
            "description": "Modify the system (write files, set env vars, run commands)",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["file", "command"],
                        "description": "What to modify"
                    },
                    "path_or_command": {
                        "type": "string",
                        "description": "File path or command"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content for file write"
                    }
                },
                "required": ["target", "path_or_command"]
            }
        }
    },
]


# =============================================================================
# Test Cases
# =============================================================================

TEST_CASES = [
    {
        "id": "env-list",
        "input": "Show me available environment variables",
        "expected_tool_fine": ["list_env"],
        "expected_tool_grouped": [("environment", {"action": "list"})],
        "expected_tool_minimal": [("query", {"target": "env_vars"})],
    },
    {
        "id": "env-get",
        "input": "What is the PATH environment variable?",
        "expected_tool_fine": ["get_env"],
        "expected_tool_grouped": [("environment", {"action": "get", "name": "PATH"})],
        "expected_tool_minimal": [("query", {"target": "env_var", "path_or_name": "PATH"})],
    },
    {
        "id": "file-list",
        "input": "List files in the current directory",
        "expected_tool_fine": ["list_files"],
        "expected_tool_grouped": [("filesystem", {"action": "list"})],
        "expected_tool_minimal": [("query", {"target": "files"})],
    },
    {
        "id": "file-read",
        "input": "Read the contents of main.py",
        "expected_tool_fine": ["read_file"],
        "expected_tool_grouped": [("filesystem", {"action": "read"})],
        "expected_tool_minimal": [("query", {"target": "file_content"})],
    },
    {
        "id": "command-run",
        "input": "Run 'echo hello world'",
        "expected_tool_fine": ["run_command"],
        "expected_tool_grouped": [("shell", {})],
        "expected_tool_minimal": [("modify", {"target": "command"})],
    },
]


@dataclass
class TestResult:
    test_id: str
    shape: str
    passed: bool
    tool_called: str | None
    expected: str
    latency_ms: int


async def run_test(
    model_name: str,
    test_case: dict,
    tools: list,
    shape_name: str,
    expected_key: str,
) -> TestResult:
    """Run a single test with given tool shape."""
    import httpx
    import time
    
    start = time.monotonic()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to tools. Use tools to answer questions."},
        {"role": "user", "content": test_case["input"]}
    ]
    
    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min for large models
        response = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "tools": tools,
                "stream": False,
            }
        )
        
    latency_ms = int((time.monotonic() - start) * 1000)
    
    result = response.json()
    message = result.get("message", {})
    tool_calls = message.get("tool_calls", [])
    
    # Extract tool name called
    tool_called = None
    tool_args = {}
    if tool_calls:
        tool_called = tool_calls[0].get("function", {}).get("name")
        tool_args = tool_calls[0].get("function", {}).get("arguments", {})
    
    # Check if correct tool was called
    expected = test_case[expected_key]
    if isinstance(expected[0], str):
        # Fine-grained: just check tool name
        passed = tool_called in expected
        expected_str = str(expected)
    else:
        # Grouped/minimal: check tool name and key args
        passed = False
        for exp_name, exp_args in expected:
            if tool_called == exp_name:
                # Check key arguments match
                if all(tool_args.get(k) == v for k, v in exp_args.items() if v):
                    passed = True
                    break
                # Partial match on action is enough
                if "action" in exp_args and tool_args.get("action") == exp_args["action"]:
                    passed = True
                    break
        expected_str = str(expected)
    
    return TestResult(
        test_id=test_case["id"],
        shape=shape_name,
        passed=passed,
        tool_called=f"{tool_called}({json.dumps(tool_args)})" if tool_called else None,
        expected=expected_str,
        latency_ms=latency_ms,
    )


async def run_experiment(model_name: str) -> None:
    """Run the full experiment comparing tool shapes."""
    print(f"\n{'='*70}")
    print(f"TOOL SHAPE EXPERIMENT - Model: {model_name}")
    print(f"{'='*70}\n")
    
    shapes = [
        ("fine-grained", TOOLS_FINE_GRAINED, "expected_tool_fine"),
        ("domain-grouped", TOOLS_DOMAIN_GROUPED, "expected_tool_grouped"),
        ("minimal", TOOLS_MINIMAL, "expected_tool_minimal"),
    ]
    
    all_results: list[TestResult] = []
    
    for shape_name, tools, expected_key in shapes:
        print(f"\n## Testing shape: {shape_name} ({len(tools)} tools)")
        print(f"   Tools: {[t['function']['name'] for t in tools]}")
        print()
        
        for test_case in TEST_CASES:
            result = await run_test(model_name, test_case, tools, shape_name, expected_key)
            all_results.append(result)
            
            status = "✓" if result.passed else "✗"
            print(f"   {status} {result.test_id}: called {result.tool_called or 'NONE'} ({result.latency_ms}ms)")
            if not result.passed:
                print(f"      expected: {result.expected}")
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")
    
    for shape_name, _, _ in shapes:
        shape_results = [r for r in all_results if r.shape == shape_name]
        passed = sum(1 for r in shape_results if r.passed)
        total = len(shape_results)
        avg_latency = sum(r.latency_ms for r in shape_results) // total
        
        pct = (passed / total) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"{shape_name:20} {bar} {passed}/{total} ({pct:.0f}%) avg:{avg_latency}ms")
    
    print()


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test tool shapes with different models")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model to test")
    args = parser.parse_args()
    
    await run_experiment(args.model)


if __name__ == "__main__":
    asyncio.run(main())
