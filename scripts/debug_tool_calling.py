#!/usr/bin/env python3
"""Direct tool calling diagnostic script.

Bypasses the full benchmark suite to test tool calling directly with
the OllamaModel adapter. This helps isolate whether tool calling issues
are in:
1. The model itself
2. The Sunwell OllamaModel adapter  
3. The journey/recorder pipeline

Usage:
    uv run python scripts/debug_tool_calling.py
    uv run python scripts/debug_tool_calling.py --model llama3.1:8b
    uv run python scripts/debug_tool_calling.py --model qwen2.5:7b --prompt "List files in current dir"
"""

import asyncio
import json
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def make_simple_tool() -> dict[str, Any]:
    """Create a simple tool definition for testing."""
    return {
        "name": "list_env",
        "description": "List environment variables. Returns all environment variable names and values.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }


def make_file_tool() -> dict[str, Any]:
    """Create a file reading tool for testing."""
    return {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read",
                }
            },
            "required": ["path"],
        },
    }


async def test_direct_ollama_api(model: str, prompt: str) -> dict[str, Any]:
    """Test tool calling directly via Ollama's OpenAI-compatible API."""
    import httpx
    
    console.print(Panel("Testing via direct Ollama API (curl equivalent)", style="cyan"))
    
    tools = [
        {"type": "function", "function": make_simple_tool()},
        {"type": "function", "function": make_file_tool()},
    ]
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "tools": tools,
        "tool_choice": "auto",
    }
    
    console.print("[dim]Request payload:[/dim]")
    console.print(Syntax(json.dumps(payload, indent=2), "json", theme="monokai"))
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "http://localhost:11434/v1/chat/completions",
            json=payload,
        )
        result = response.json()
    
    console.print("\n[dim]Response:[/dim]")
    console.print(Syntax(json.dumps(result, indent=2), "json", theme="monokai"))
    
    return result


async def test_sunwell_ollama_adapter(model: str, prompt: str) -> dict[str, Any]:
    """Test tool calling via Sunwell's OllamaModel adapter."""
    from sunwell.models.adapters.ollama import OllamaModel
    from sunwell.models.core.protocol import Tool, GenerateOptions, Message
    from sunwell.agent.runtime.model_router import get_model_capability
    
    console.print(Panel("Testing via Sunwell OllamaModel adapter", style="green"))
    
    # Check model capability first
    cap = get_model_capability(model)
    console.print(f"[dim]Model capability for {model}:[/dim]")
    if cap:
        console.print(f"  tools: {cap.tools}")
        console.print(f"  tier: {cap.tier}")
    else:
        console.print("  [yellow]Not in MODEL_REGISTRY (will assume defaults)[/yellow]")
    
    # Create tools using Sunwell's Tool type
    tools = (
        Tool(
            name="list_env",
            description="List environment variables. Returns all environment variable names and values.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="read_file",
            description="Read the contents of a file at the given path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read",
                    }
                },
                "required": ["path"],
            },
        ),
    )
    
    # Create the adapter
    ollama_model = OllamaModel(model=model)
    
    # Create proper Message objects (not raw strings!)
    messages = (
        Message(role="user", content=prompt),
    )
    
    console.print(f"\n[dim]Calling OllamaModel.generate() with prompt:[/dim]")
    console.print(f"  \"{prompt}\"")
    console.print(f"  tools: {[t.name for t in tools]}")
    console.print(f"  tool_choice: auto")
    
    # Call generate with proper Message tuple
    result = await ollama_model.generate(
        prompt=messages,
        tools=tools,
        tool_choice="auto",
        options=GenerateOptions(temperature=0.0),
    )
    
    console.print("\n[dim]GenerateResult:[/dim]")
    console.print(f"  content: {result.content[:200] if result.content else None}...")
    console.print(f"  tool_calls: {result.tool_calls}")
    console.print(f"  finish_reason: {result.finish_reason}")
    
    return {
        "content": result.content,
        "tool_calls": [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in (result.tool_calls or [])
        ],
        "finish_reason": result.finish_reason,
    }


async def test_intent_classification(model: str, prompt: str) -> dict[str, Any]:
    """Test the IntentRouter classification for the given prompt."""
    from sunwell.agent.chat.intent import IntentRouter
    from sunwell.models.adapters.ollama import OllamaModel
    
    console.print(Panel("Testing IntentRouter Classification", style="magenta"))
    
    # Create model for LLM fallback
    ollama_model = OllamaModel(model=model)
    router = IntentRouter(model=ollama_model)
    
    console.print(f"[dim]Classifying prompt: \"{prompt}\"[/dim]")
    
    classification = await router.classify(prompt)
    
    console.print(f"\n[dim]Classification Result:[/dim]")
    console.print(f"  Intent: [bold]{classification.intent.value}[/bold]")
    console.print(f"  Confidence: {classification.confidence:.2f}")
    console.print(f"  Reasoning: {classification.reasoning}")
    
    return {
        "intent": classification.intent.value,
        "confidence": classification.confidence,
        "reasoning": classification.reasoning,
    }


async def test_journey_style_execution(model_name: str, prompt: str) -> dict[str, Any]:
    """Run AgentLoop the same way the JourneyRunner does, with EventRecorder."""
    import tempfile
    from pathlib import Path
    
    from sunwell.agent import AgentLoop, LoopConfig
    from sunwell.agent.events import EventType
    from sunwell.benchmark.journeys.recorder import EventRecorder
    from sunwell.knowledge.project import create_project_from_workspace
    from sunwell.models.adapters.ollama import OllamaModel
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor
    
    console.print(Panel("Testing Journey-Style Execution (AgentLoop + EventRecorder)", style="blue"))
    
    # Create temporary workspace (like journey runner does)
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        console.print(f"[dim]Workspace: {workspace}[/dim]")
        
        # Create project
        project = create_project_from_workspace(workspace)
        
        # Create model
        model = OllamaModel(model=model_name)
        
        # Create executor (like journey runner does)
        policy = ToolPolicy(trust_level=ToolTrust.from_string("shell"))
        executor = ToolExecutor(
            project=project,
            sandbox=None,
            policy=policy,
        )
        
        # Create recorder
        recorder = EventRecorder()
        recorder.start()
        
        # Create agent loop
        loop_config = LoopConfig(max_turns=20)
        system_prompt = (
            "You are a helpful assistant with access to tools. "
            "When the user asks you to do something (create, add, update, fix, etc.), "
            "you MUST use the appropriate tools to complete the task. "
            "Do NOT ask for clarification unless absolutely necessary. "
            "Take action immediately using the tools available to you."
        )
        
        agent_loop = AgentLoop(
            model=model,
            executor=executor,
            config=loop_config,
        )
        
        console.print(f"[dim]Running AgentLoop with prompt: \"{prompt}\"[/dim]")
        console.print(f"[dim]Available tools: {[t.name for t in executor.get_tool_definitions()]}[/dim]")
        
        events: list[Any] = []
        try:
            async for event in agent_loop.run(prompt, system_prompt=system_prompt):
                events.append(event)
                recorder._handle_event(event)
                console.print(f"  Event: {event.type.value} - {event.data.get('tool', event.data.get('name', ''))[:30] if event.data else ''}")
        except Exception as e:
            console.print(f"[red]AgentLoop error: {e}[/red]")
            import traceback
            traceback.print_exc()
        
        recorder.stop()
        
        # Check what recorder captured
        console.print(f"\n[dim]EventRecorder results:[/dim]")
        console.print(f"  Total events: {len(recorder.events)}")
        console.print(f"  Tool calls recorded: {len(recorder.tool_calls)}")
        
        tool_start_events = [e for e in events if e.type == EventType.TOOL_START]
        console.print(f"  TOOL_START events in stream: {len(tool_start_events)}")
        
        if recorder.tool_calls:
            console.print(f"\n[dim]Recorded tool calls:[/dim]")
            for tc in recorder.tool_calls:
                console.print(f"  - {tc.name}: {tc.arguments}")
        else:
            console.print("[yellow]  No tool calls recorded![/yellow]")
            
            # Let's see what events we DID get
            console.print(f"\n[dim]Event types seen:[/dim]")
            event_types = {}
            for e in events:
                event_types[e.type.value] = event_types.get(e.type.value, 0) + 1
            for etype, count in sorted(event_types.items()):
                console.print(f"  - {etype}: {count}")
        
        return {
            "total_events": len(events),
            "tool_calls_recorded": len(recorder.tool_calls),
            "tool_start_in_stream": len(tool_start_events),
            "event_types": {e.type.value: 1 for e in events},
        }


@click.command()
@click.option("--model", "-m", default="llama3.1:8b", help="Model to test")
@click.option("--prompt", "-p", default="Show me environment variables", help="Prompt to send")
@click.option("--level", "-l", type=click.Choice(["api", "adapter", "loop", "all"]), default="all", help="Test level")
def main(model: str, prompt: str, level: str) -> None:
    """Debug tool calling at different levels of the Sunwell stack."""
    console.print(Panel.fit(
        f"🔧 Tool Calling Diagnostic\n\nModel: {model}\nPrompt: {prompt}\nLevel: {level}",
        title="Debug",
        border_style="blue",
    ))
    
    async def run_tests() -> None:
        results = {}
        
        if level in ("api", "all"):
            console.print("\n" + "=" * 60)
            try:
                results["direct_api"] = await test_direct_ollama_api(model, prompt)
            except Exception as e:
                console.print(f"[red]Direct API failed: {e}[/red]")
                results["direct_api"] = {"error": str(e)}
        
        if level in ("adapter", "all"):
            console.print("\n" + "=" * 60)
            try:
                results["sunwell_adapter"] = await test_sunwell_ollama_adapter(model, prompt)
            except Exception as e:
                console.print(f"[red]Sunwell adapter failed: {e}[/red]")
                import traceback
                traceback.print_exc()
                results["sunwell_adapter"] = {"error": str(e)}
        
        if level in ("loop", "all"):
            console.print("\n" + "=" * 60)
            try:
                results["intent_classification"] = await test_intent_classification(model, prompt)
            except Exception as e:
                console.print(f"[red]Intent classification failed: {e}[/red]")
                import traceback
                traceback.print_exc()
                results["intent_classification"] = {"error": str(e)}
            
            console.print("\n" + "=" * 60)
            try:
                results["journey_style"] = await test_journey_style_execution(model, prompt)
            except Exception as e:
                console.print(f"[red]Journey-style execution failed: {e}[/red]")
                import traceback
                traceback.print_exc()
                results["journey_style"] = {"error": str(e)}
        
        # Summary comparison
        console.print("\n" + "=" * 60)
        console.print(Panel("Summary Comparison", style="bold"))
        
        for name, result in results.items():
            if "error" in result:
                console.print(f"  {name}: [red]ERROR[/red] - {result['error']}")
            elif name == "direct_api":
                tool_calls = result.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                console.print(f"  {name}: [green]{len(tool_calls)} tool call(s)[/green]")
            elif name == "sunwell_adapter":
                tool_calls = result.get("tool_calls", [])
                console.print(f"  {name}: [green]{len(tool_calls)} tool call(s)[/green]")
            elif name == "intent_classification":
                intent = result.get("intent", "unknown")
                confidence = result.get("confidence", 0)
                color = "green" if intent == "task" else "yellow" if intent == "conversation" else "red"
                console.print(f"  {name}: [{color}]{intent} ({confidence:.2f})[/{color}]")
            elif name == "journey_style":
                tool_calls = result.get("tool_calls_recorded", 0)
                color = "green" if tool_calls > 0 else "red"
                console.print(f"  {name}: [{color}]{tool_calls} tool call(s) recorded[/{color}]")
    
    asyncio.run(run_tests())


if __name__ == "__main__":
    main()
