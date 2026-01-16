"""FunctionGemma Router - Lightweight function calling for small models.

This prototype demonstrates using FunctionGemma (270M) as a "function router"
to enable function calling capabilities for models that don't natively support it.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │  User Query                                                 │
    └─────────────────────┬───────────────────────────────────────┘
                          ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  FunctionGemma (270M) - Tool Router                         │
    │  • Parses intent                                            │
    │  • Selects function                                         │
    │  • Extracts arguments                                       │
    └─────────────────────┬───────────────────────────────────────┘
                          ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Tool Execution                                             │
    │  → Execute the selected function                            │
    └─────────────────────┬───────────────────────────────────────┘
                          ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Main Model (gemma3:1b, qwen3:8b, etc.)                     │
    │  • Natural language response                                │
    │  • Reasoning about results                                  │
    │  • Multi-turn conversation                                  │
    └─────────────────────────────────────────────────────────────┘

Benefits:
    - Small models (1B) gain function calling without fine-tuning
    - FunctionGemma is only 301MB - minimal overhead
    - Separation of concerns: router routes, responder responds
    - Works with any model as the responder

Requirements:
    - ollama pull functiongemma
    - ollama pull gemma3:1b (or any other model)
"""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Any, Awaitable

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Tool, ToolCall, Message, GenerateOptions


# =============================================================================
# Tool Registry
# =============================================================================


@dataclass
class ToolRegistry:
    """Registry for tools that can be called via FunctionGemma router."""
    
    _tools: dict[str, Tool] = field(default_factory=dict)
    _handlers: dict[str, Callable[..., Awaitable[str]]] = field(default_factory=dict)
    
    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[str]],
    ) -> None:
        """Register a tool with its handler."""
        self._tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
        )
        self._handlers[name] = handler
    
    def tool(
        self,
        name: str,
        description: str,
        parameters: dict,
    ) -> Callable[[Callable[..., Awaitable[str]]], Callable[..., Awaitable[str]]]:
        """Decorator to register a tool."""
        def decorator(fn: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
            self.register(name, description, parameters, fn)
            return fn
        return decorator
    
    def get_tools(self) -> tuple[Tool, ...]:
        """Get all registered tools."""
        return tuple(self._tools.values())
    
    async def execute(self, name: str, arguments: dict) -> str:
        """Execute a tool by name with arguments."""
        handler = self._handlers.get(name)
        if not handler:
            return f"Error: Unknown tool '{name}'"
        try:
            return await handler(**arguments)
        except Exception as e:
            return f"Error executing {name}: {e}"


# =============================================================================
# FunctionGemma Router
# =============================================================================


@dataclass
class FunctionGemmaRouter:
    """Routes function calls using FunctionGemma, synthesizes responses with main model.
    
    This enables function calling for models that don't natively support it by using
    FunctionGemma (270M) as a lightweight "routing layer" that:
    1. Decides which function to call (if any)
    2. Extracts arguments from the user query
    3. Returns structured tool calls
    
    The main model then handles response synthesis after tool execution.
    
    Includes keyword-based pre-routing for improved accuracy on small models.
    """
    
    # The main model for conversation/synthesis (e.g., gemma3:1b)
    main_model: str = "gemma3:1b"
    
    # The router model (always FunctionGemma for tool selection)
    router_model: str = "functiongemma"
    
    # Tool registry
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    
    # Ollama base URL
    base_url: str = "http://localhost:11434/v1"
    
    # Enable keyword pre-routing to help small models
    use_keyword_hints: bool = True
    
    # Internal models (initialized lazily)
    _router: OllamaModel | None = field(default=None, init=False)
    _main: OllamaModel | None = field(default=None, init=False)
    
    @property
    def router(self) -> OllamaModel:
        """Get the router model (FunctionGemma)."""
        if self._router is None:
            self._router = OllamaModel(model=self.router_model, base_url=self.base_url)
        return self._router
    
    @property
    def main(self) -> OllamaModel:
        """Get the main model for synthesis."""
        if self._main is None:
            self._main = OllamaModel(model=self.main_model, base_url=self.base_url)
        return self._main
    
    def _extract_math_expression(self, query: str) -> str | None:
        """Try to extract a math expression from the query.
        
        Returns the expression if found, None otherwise.
        """
        import re
        
        # Pattern for math expressions: numbers with operators
        # Handles: "25 * 4", "100 + 50 - 25", "(10 + 5) * 2"
        patterns = [
            r'[\d\s\+\-\*\/\(\)\.]+',  # Basic math chars
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                # Clean and validate
                expr = match.strip()
                # Must have at least one operator and two numbers
                if re.search(r'\d+\s*[\+\-\*\/]\s*\d+', expr):
                    return expr
        
        return None
    
    def _get_keyword_hint(self, query: str) -> tuple[str | None, dict | None]:
        """Detect likely tool from keywords to help guide small models.
        
        This provides a "hint" to FunctionGemma about which tool is likely
        relevant, improving accuracy for the 270M model.
        
        Returns:
            (tool_name, arguments) - arguments are pre-extracted if possible
        """
        query_lower = query.lower()
        
        # Check for non-math contexts first to avoid false positives
        # Weather keywords (check early to avoid "what is the weather" matching math)
        if any(kw in query_lower for kw in [
            "weather", "temperature", "forecast", "rain", "sunny", "cloudy",
            "humid", "hot", "cold"
        ]):
            return ("get_weather", None)
        
        # Time keywords
        if any(kw in query_lower for kw in [
            "time", "clock", "hour", "what time", "current time"
        ]):
            return ("get_current_time", None)
        
        # File keywords
        if any(kw in query_lower for kw in [
            "file", "files", "find files", "search files", ".py", ".md", ".txt",
            "python file", "markdown file"
        ]):
            return ("find_files", None)
        
        # Math/calculation - try to extract expression directly
        # Check AFTER other contexts to avoid false positives
        math_expr = self._extract_math_expression(query)
        if math_expr:
            return ("calculate", {"expression": math_expr})
        
        if any(kw in query_lower for kw in [
            "calculate", "compute", "math", "add", "subtract", "multiply", 
            "divide", "sum"
        ]):
            return ("calculate", None)
        
        return (None, None)
    
    async def route(self, query: str) -> tuple[ToolCall, ...] | None:
        """Use FunctionGemma to decide which tools to call.
        
        Optionally uses keyword hints to guide the small model toward
        the correct tool when the query contains obvious signals.
        For math expressions, can directly extract arguments.
        
        Returns:
            Tuple of ToolCalls if FunctionGemma decided to call tools,
            None if no tool call is appropriate.
        """
        tools = self.tools.get_tools()
        if not tools:
            return None
        
        # Get keyword hint to help guide small model
        hint_tool, hint_args = self._get_keyword_hint(query) if self.use_keyword_hints else (None, None)
        
        # If we have pre-extracted arguments (e.g., math expression), use them directly
        if hint_tool and hint_args:
            print(f"[Router] Direct extraction: {hint_tool}({hint_args})")
            return (ToolCall(
                id=f"direct-{hint_tool}",
                name=hint_tool,
                arguments=hint_args,
            ),)
        
        # If we have a hint but no args, try forcing that tool
        if hint_tool:
            print(f"[Router] Keyword hint detected: {hint_tool}")
            try:
                result = await self.router.generate(
                    query,
                    tools=tools,
                    tool_choice=hint_tool,  # Force the hinted tool
                    options=GenerateOptions(temperature=0.1),
                )
                if result.has_tool_calls:
                    return result.tool_calls
            except Exception:
                pass  # Fall through to auto mode
        
        # Standard auto routing via FunctionGemma
        try:
            result = await self.router.generate(
                query,
                tools=tools,
                tool_choice="auto",
                options=GenerateOptions(temperature=0.1),  # Low temp for deterministic routing
            )
            
            if result.has_tool_calls:
                return result.tool_calls
            return None
            
        except Exception as e:
            print(f"[Router] Error: {e}")
            return None
    
    async def synthesize(
        self,
        query: str,
        tool_results: list[tuple[str, str]],  # [(tool_name, result), ...]
    ) -> str:
        """Use main model to synthesize a response from tool results.
        
        Args:
            query: Original user query
            tool_results: List of (tool_name, result) tuples
        """
        # Build context for the main model
        context_parts = [f"User asked: {query}\n"]
        
        for tool_name, result in tool_results:
            context_parts.append(f"Tool '{tool_name}' returned:\n{result}\n")
        
        context_parts.append(
            "Based on the above information, provide a helpful response to the user. "
            "Be concise and focus on answering their question."
        )
        
        prompt = "\n".join(context_parts)
        
        result = await self.main.generate(
            prompt,
            options=GenerateOptions(temperature=0.7),
        )
        
        return result.text
    
    async def chat(self, query: str) -> str:
        """Process a user query with optional function calling.
        
        This is the main entry point. It:
        1. Routes the query through FunctionGemma to detect tool calls
        2. Executes any requested tools
        3. Synthesizes a response using the main model
        """
        print(f"\n{'='*60}")
        print(f"[Query] {query}")
        print(f"{'='*60}")
        
        # Step 1: Route through FunctionGemma
        print(f"\n[Router] Checking with {self.router_model}...")
        tool_calls = await self.route(query)
        
        if not tool_calls:
            # No tools needed - use main model directly
            print(f"[Router] No tool calls needed, using {self.main_model} directly")
            result = await self.main.generate(
                query,
                options=GenerateOptions(temperature=0.7),
            )
            return result.text
        
        # Step 2: Execute tool calls
        tool_results: list[tuple[str, str]] = []
        for tc in tool_calls:
            print(f"\n[Tool Call] {tc.name}({json.dumps(tc.arguments)})")
            result = await self.tools.execute(tc.name, tc.arguments)
            print(f"[Tool Result] {result[:200]}{'...' if len(result) > 200 else ''}")
            tool_results.append((tc.name, result))
        
        # Step 3: Synthesize response with main model
        print(f"\n[Synthesis] Generating response with {self.main_model}...")
        response = await self.synthesize(query, tool_results)
        
        return response


# =============================================================================
# Example Tools
# =============================================================================


def create_example_tools() -> ToolRegistry:
    """Create example tools for demonstration."""
    registry = ToolRegistry()
    
    @registry.tool(
        name="get_weather",
        description="Get weather conditions including temperature, humidity, and sky conditions for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name like Paris, Tokyo, London, New York",
                },
            },
            "required": ["city"],
        },
    )
    async def get_weather(city: str) -> str:
        """Simulated weather API."""
        # In reality, this would call a weather API
        weather_data = {
            "paris": {"temp": 18, "condition": "partly cloudy", "humidity": 65},
            "tokyo": {"temp": 24, "condition": "sunny", "humidity": 55},
            "london": {"temp": 14, "condition": "rainy", "humidity": 80},
            "new york": {"temp": 22, "condition": "clear", "humidity": 45},
            "sydney": {"temp": 20, "condition": "windy", "humidity": 60},
        }
        
        city_lower = city.lower()
        if city_lower in weather_data:
            data = weather_data[city_lower]
            return json.dumps({
                "city": city,
                "temperature_celsius": data["temp"],
                "condition": data["condition"],
                "humidity_percent": data["humidity"],
            })
        return json.dumps({"error": f"Weather data not available for {city}"})
    
    @registry.tool(
        name="calculate",
        description="Perform a mathematical calculation",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 2', '10 * 5')",
                },
            },
            "required": ["expression"],
        },
    )
    async def calculate(expression: str) -> str:
        """Safe math calculator."""
        # Only allow safe characters
        allowed = set("0123456789+-*/.(). ")
        if not all(c in allowed for c in expression):
            return json.dumps({"error": "Invalid characters in expression"})
        
        try:
            # Use eval with restricted builtins for safety
            result = eval(expression, {"__builtins__": {}}, {})
            return json.dumps({"expression": expression, "result": result})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @registry.tool(
        name="get_current_time",
        description="Get current clock time and date in a timezone. Use for questions about what time it is",
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone like UTC, Asia/Tokyo, Europe/Paris, US/Pacific",
                },
            },
            "required": ["timezone"],
        },
    )
    async def get_current_time(timezone: str) -> str:
        """Get current time in a timezone."""
        from datetime import datetime
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone)
            now = datetime.now(tz)
            return json.dumps({
                "timezone": timezone,
                "time": now.strftime("%H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "day": now.strftime("%A"),
            })
        except Exception as e:
            return json.dumps({"error": f"Invalid timezone: {timezone}"})
    
    @registry.tool(
        name="find_files",
        description="Find and list files on disk by filename pattern. Use for finding Python files, markdown files, etc.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string", 
                    "description": "Filename pattern like *.py or *.md or test_*.py",
                },
            },
            "required": ["pattern"],
        },
    )
    async def find_files(pattern: str) -> str:
        """Search for files matching a pattern."""
        from pathlib import Path
        try:
            files = list(Path(".").glob(f"**/{pattern}"))[:20]  # Limit to 20 files
            return json.dumps({
                "pattern": pattern,
                "count": len(files),
                "files": [str(f) for f in files],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    return registry


# =============================================================================
# Demo
# =============================================================================


async def main():
    """Demonstrate the FunctionGemma router pattern."""
    
    print("=" * 70)
    print("FunctionGemma Router Demo")
    print("=" * 70)
    print(f"""
This demo shows how FunctionGemma (270M) can act as a lightweight 
"function router" to enable tool use for models that don't natively 
support function calling.

Architecture:
  • Router: functiongemma (270M, 301MB) - decides which tool to call
  • Main:   gemma3:1b (815MB) - synthesizes responses
  • Total:  ~1.1GB for full function-calling capability

""")
    
    # Create router with example tools
    tools = create_example_tools()
    router = FunctionGemmaRouter(
        main_model="gemma3:1b",
        router_model="functiongemma",
        tools=tools,
    )
    
    # Test queries
    test_queries = [
        "What's the weather like in Paris?",
        "Calculate 15 * 7 + 23",
        "What time is it in Tokyo?",
        "Find all Python files in this project",
        "Tell me a joke",  # Should NOT trigger tools
    ]
    
    for query in test_queries:
        try:
            response = await router.chat(query)
            print(f"\n[Response]\n{response}")
            print("\n" + "-" * 70)
        except Exception as e:
            print(f"\n[Error] {e}")
            print("-" * 70)
        
        # Small delay between queries
        await asyncio.sleep(0.5)


async def interactive():
    """Interactive chat with the FunctionGemma router."""
    
    print("=" * 70)
    print("FunctionGemma Router - Interactive Mode")
    print("=" * 70)
    print("""
Available tools:
  • get_weather(city) - Get weather for a city
  • calculate(expression) - Do math
  • get_current_time(timezone) - Get time in a timezone
  • find_files(pattern) - Find files

Type 'quit' to exit.
""")
    
    tools = create_example_tools()
    router = FunctionGemmaRouter(
        main_model="gemma3:1b",
        router_model="functiongemma", 
        tools=tools,
    )
    
    while True:
        try:
            query = input("\nYou: ").strip()
            if query.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if not query:
                continue
                
            response = await router.chat(query)
            print(f"\nAssistant: {response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(main())
