#!/usr/bin/env python3
"""Smoke test for MODEL_REGISTRY tool calling accuracy.

Verifies that the claimed tool capabilities in MODEL_REGISTRY match reality
by making actual calls to Ollama. This catches misconfigurations like:
- Model marked tools=True but doesn't actually support native tools
- Model marked tools=False but does support native tools

Usage:
    uv run python scripts/smoke_test_model_capabilities.py
    uv run python scripts/smoke_test_model_capabilities.py --model llama3.1:8b
    uv run python scripts/smoke_test_model_capabilities.py --all-local

Environment:
    Requires Ollama running on localhost:11434
"""

import asyncio
import sys
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

from sunwell.agent.runtime.model_router import MODEL_REGISTRY, get_model_capability

console = Console()

# Simple tool definition for testing
TEST_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name",
                }
            },
            "required": ["location"],
        },
    },
}

# Prompt that should trigger tool use
TEST_PROMPT = "What's the weather in San Francisco?"


async def check_ollama_available() -> bool:
    """Check if Ollama is running."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def get_local_models() -> list[str]:
    """Get list of locally available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        console.print(f"[red]Failed to get local models: {e}[/red]")
        return []


async def test_model_tool_support(model: str, timeout: float = 60.0) -> dict[str, Any]:
    """Test if a model actually supports native tool calling.
    
    Returns:
        Dict with keys:
        - supports_tools: bool - whether model returned tool calls
        - error: str | None - error message if call failed
        - raw_response: dict - the raw API response
    """
    result: dict[str, Any] = {
        "model": model,
        "supports_tools": False,
        "error": None,
        "raw_response": None,
        "tool_call_count": 0,
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": TEST_PROMPT}
        ],
        "tools": [TEST_TOOL],
        "tool_choice": "auto",
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "http://localhost:11434/v1/chat/completions",
                json=payload,
            )
            
            if response.status_code != 200:
                error_text = response.text
                # Check for specific "does not support tools" error
                if "does not support tools" in error_text.lower():
                    result["error"] = "Model does not support tools (Ollama error)"
                    result["supports_tools"] = False
                else:
                    result["error"] = f"HTTP {response.status_code}: {error_text[:100]}"
                return result
            
            data = response.json()
            result["raw_response"] = data
            
            # Check if tool calls were returned
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                tool_calls = message.get("tool_calls", [])
                result["tool_call_count"] = len(tool_calls)
                result["supports_tools"] = len(tool_calls) > 0
            
    except httpx.TimeoutException:
        result["error"] = f"Timeout after {timeout}s"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def compare_with_registry(model: str, actual_supports_tools: bool) -> str:
    """Compare actual result with MODEL_REGISTRY claim.
    
    Returns:
        "match" - Registry is correct
        "false_positive" - Registry says True, but model doesn't support
        "false_negative" - Registry says False, but model does support
        "unknown" - Model not in registry
    """
    cap = get_model_capability(model)
    if cap is None:
        return "unknown"
    
    if cap.tools == actual_supports_tools:
        return "match"
    elif cap.tools and not actual_supports_tools:
        return "false_positive"
    else:
        return "false_negative"


@click.command()
@click.option("--model", "-m", help="Specific model to test")
@click.option("--all-local", is_flag=True, help="Test all locally installed models")
@click.option("--all-registry", is_flag=True, help="Test all models in MODEL_REGISTRY (local only)")
@click.option("--timeout", "-t", default=60.0, help="Timeout per model in seconds")
def main(model: str | None, all_local: bool, all_registry: bool, timeout: float) -> None:
    """Smoke test MODEL_REGISTRY tool capabilities against actual Ollama models."""
    
    async def run() -> None:
        # Check Ollama is available
        if not await check_ollama_available():
            console.print("[red]Ollama not available at localhost:11434[/red]")
            sys.exit(1)
        
        local_models = await get_local_models()
        console.print(f"[dim]Found {len(local_models)} local models[/dim]")
        
        # Determine which models to test
        models_to_test: list[str] = []
        
        if model:
            models_to_test = [model]
        elif all_local:
            models_to_test = local_models
        elif all_registry:
            # Test registry models that are available locally
            models_to_test = [
                m for m in MODEL_REGISTRY.keys()
                if m in local_models or m.split(":")[0] in [lm.split(":")[0] for lm in local_models]
            ]
        else:
            # Default: test common local models that are in registry
            common_models = [
                "gemma3:1b", "gemma3:4b", "gemma3:12b",
                "llama3.1:8b", "llama3.2:3b",
                "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b",
                "mistral:7b",
                "gpt-oss:20b",
            ]
            models_to_test = [m for m in common_models if m in local_models]
        
        if not models_to_test:
            console.print("[yellow]No models to test. Install models or specify --model[/yellow]")
            return
        
        console.print(f"\n[bold]Testing {len(models_to_test)} model(s)...[/bold]\n")
        
        # Run tests
        results: list[dict[str, Any]] = []
        for m in models_to_test:
            console.print(f"Testing [cyan]{m}[/cyan]...", end=" ")
            result = await test_model_tool_support(m, timeout=timeout)
            
            if result["error"]:
                console.print(f"[red]ERROR[/red] - {result['error']}")
            elif result["supports_tools"]:
                console.print(f"[green]✓ Tools supported[/green] ({result['tool_call_count']} calls)")
            else:
                console.print("[yellow]✗ No tools[/yellow]")
            
            results.append(result)
        
        # Summary table
        console.print("\n")
        table = Table(title="MODEL_REGISTRY Accuracy Check")
        table.add_column("Model", style="cyan")
        table.add_column("Actual", style="bold")
        table.add_column("Registry", style="dim")
        table.add_column("Status", style="bold")
        
        mismatches = []
        for r in results:
            m = r["model"]
            actual = r["supports_tools"]
            cap = get_model_capability(m)
            claimed = cap.tools if cap else None
            
            comparison = compare_with_registry(m, actual)
            
            actual_str = "[green]✓[/green]" if actual else "[red]✗[/red]"
            claimed_str = "[green]✓[/green]" if claimed else ("[red]✗[/red]" if claimed is False else "[dim]?[/dim]")
            
            if comparison == "match":
                status = "[green]Match[/green]"
            elif comparison == "false_positive":
                status = "[red]WRONG (registry says True)[/red]"
                mismatches.append((m, "tools=False", "Registry claims True but model doesn't support"))
            elif comparison == "false_negative":
                status = "[yellow]WRONG (registry says False)[/yellow]"
                mismatches.append((m, "tools=True", "Registry claims False but model DOES support"))
            elif r["error"]:
                status = f"[dim]Error[/dim]"
            else:
                status = "[dim]Not in registry[/dim]"
            
            table.add_row(m, actual_str, claimed_str, status)
        
        console.print(table)
        
        # Show recommended fixes
        if mismatches:
            console.print("\n[bold red]Registry corrections needed:[/bold red]")
            for model_name, should_be, reason in mismatches:
                console.print(f"  • {model_name}: set {should_be}")
                console.print(f"    [dim]{reason}[/dim]")
        else:
            console.print("\n[green]All registry entries match reality![/green]")
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
