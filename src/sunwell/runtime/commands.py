"""Chat command parsing and handling (RFC-012).

Implements the `::command` syntax for in-chat commands:
- ::help - Show available commands
- ::skills - List skills from current lens
- ::tools - List available tools
- ::save <path> - Save last output to file
- ::clear - Clear conversation history
- ::exit - Exit chat session

Why double-colon?
| Syntax | Risk       | Example False Positive           |
|--------|------------|----------------------------------|
| /cmd   | High       | "good/bad", "/usr/bin", "yes/no" |
| !cmd   | High       | Bash history expansion           |
| @cmd   | Medium     | Bash arrays, email-like text     |
| ::cmd  | Very low   | Almost never in natural English  |
"""


import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.lens import Lens


# =============================================================================
# Types
# =============================================================================

@dataclass(frozen=True, slots=True)
class ParsedInput:
    """Parsed user input, either a command or regular message."""

    command: str | None  # None if regular message
    args: str
    raw: str

    @property
    def is_command(self) -> bool:
        """Check if this is a command."""
        return self.command is not None


@dataclass(slots=True)
class ChatSession:
    """Session state for command handlers."""

    lens: Lens | None = None
    last_response: str = ""
    conversation_history: list[dict] = field(default_factory=list)


# Type for command handlers
CommandHandler = Callable[[str, ChatSession], Awaitable[str | None]]


# =============================================================================
# Input Parsing
# =============================================================================

# Command pattern: ::word with optional arguments
COMMAND_PATTERN = re.compile(r'^::([a-zA-Z][\w-]*)\s*(.*)', re.DOTALL)


def parse_input(text: str) -> ParsedInput:
    """Parse user input for ::commands.

    Examples:
        parse_input("::save notes.md")  → ParsedInput(command="save", args="notes.md", ...)
        parse_input("::help")           → ParsedInput(command="help", args="", ...)
        parse_input("hello world")      → ParsedInput(command=None, args="", raw="hello world")
        parse_input("good/bad choice")  → ParsedInput(command=None, ...)  # No false positive
    """
    text = text.strip()

    if text.startswith("::"):
        match = COMMAND_PATTERN.match(text)
        if match:
            return ParsedInput(
                command=match.group(1).lower(),
                args=match.group(2).strip(),
                raw=text,
            )

    return ParsedInput(command=None, args="", raw=text)


# =============================================================================
# Terminal Highlighting
# =============================================================================

# ANSI color codes
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

HIGHLIGHT_PATTERN = re.compile(r'(^|(?<=\s))(::[\w-]+)')


def highlight_commands(text: str) -> str:
    """Highlight ::commands with ANSI colors."""
    return HIGHLIGHT_PATTERN.sub(rf'\1{BOLD}{CYAN}\2{RESET}', text)


# =============================================================================
# Command Registry
# =============================================================================

class CommandRegistry:
    """Registry for ::command handlers."""

    def __init__(self):
        self._handlers: dict[str, CommandHandler] = {}
        self._descriptions: dict[str, str] = {}

    def register(
        self,
        name: str,
        description: str = "",
    ) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a command handler.

        Usage:
            @commands.register("help", "Show available commands")
            async def cmd_help(args: str, session: ChatSession) -> str:
                return "Help text..."
        """
        def decorator(fn: CommandHandler) -> CommandHandler:
            self._handlers[name] = fn
            self._descriptions[name] = description or fn.__doc__ or ""
            return fn
        return decorator

    def get(self, name: str) -> CommandHandler | None:
        """Get handler for a command name."""
        return self._handlers.get(name)

    async def execute(
        self,
        command: str,
        args: str,
        session: ChatSession,
    ) -> str | None:
        """Execute a command, return response or None."""
        handler = self._handlers.get(command)
        if handler:
            return await handler(args, session)
        return f"Unknown command: ::{command}. Try ::help for available commands."

    def get_help(self) -> str:
        """Get formatted help text for all commands."""
        lines = ["Available commands:"]
        for name, desc in sorted(self._descriptions.items()):
            lines.append(f"  ::{name:<12} {desc}")
        return "\n".join(lines)

    @property
    def commands(self) -> list[str]:
        """Get list of registered command names."""
        return list(self._handlers.keys())


# =============================================================================
# Default Commands
# =============================================================================

# Global registry for default commands
commands = CommandRegistry()


@commands.register("help", "Show available commands")
async def cmd_help(args: str, session: ChatSession) -> str:
    """Show available commands."""
    return """Available commands:

[bold]Session Management:[/bold]
  ::help          Show this help
  ::clear         Clear conversation history
  ::save <path>   Save last response to file
  ::read <path>   Read a file into context
  ::exit          Exit chat session

[bold]Lens & Skills:[/bold]
  ::skills        List available skills
  ::lens          Show current lens info
  ::lens <name>   Switch to different lens

[bold]Tools (RFC-012):[/bold]
  ::tools         List available tools
  ::trust         Show current trust level
  ::trust <level> Set trust level

[bold]Context:[/bold]
  ::focus <scope> Narrow context (code, docs, tests)
  ::context       Show current context

[bold]Headspace:[/bold]
  ::learn <fact>  Add a learning
  ::learnings     Show all learnings
  ::dead-end      Mark current path as dead end
"""


@commands.register("clear", "Clear conversation history")
async def cmd_clear(args: str, session: ChatSession) -> str:
    """Clear conversation history."""
    session.conversation_history.clear()
    return "✓ Conversation history cleared"


@commands.register("save", "Save last response to file")
async def cmd_save(args: str, session: ChatSession) -> str:
    """Save last assistant output to file."""
    if not args:
        return "Usage: ::save <path>"

    if not session.last_response:
        return "No output to save yet"

    try:
        path = Path(args).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(session.last_response)
        return f"✓ Saved to {path} ({len(session.last_response):,} bytes)"
    except Exception as e:
        return f"Failed to save: {e}"


@commands.register("read", "Read a file into context")
async def cmd_read(args: str, session: ChatSession) -> str:
    """Read a file and add to context."""
    if not args:
        return "Usage: ::read <path>"

    try:
        path = Path(args).expanduser()
        if not path.exists():
            return f"File not found: {path}"

        content = path.read_text()
        lines = content.split('\n')

        # Add to conversation as a system message
        session.conversation_history.append({
            "role": "user",
            "content": f"[File: {path}]\n```\n{content}\n```"
        })

        preview = '\n'.join(lines[:10])
        if len(lines) > 10:
            preview += f"\n... ({len(lines) - 10} more lines)"

        return f"Read {path} ({len(lines)} lines). Preview:\n```\n{preview}\n```"
    except Exception as e:
        return f"Failed to read: {e}"


@commands.register("skills", "List available skills")
async def cmd_skills(args: str, session: ChatSession) -> str:
    """List skills from current lens."""
    if not session.lens:
        return "No lens loaded"

    if not hasattr(session.lens, 'skills') or not session.lens.skills:
        return "No skills defined in current lens"

    lines = ["Available skills:"]
    for skill in session.lens.skills:
        trust_icon = {"full": "🔓", "sandboxed": "🔒", "none": "📝"}.get(skill.trust.value, "❓")
        lines.append(f"  {trust_icon} {skill.name}: {skill.description}")

    return "\n".join(lines)


@commands.register("lens", "Show or switch lens")
async def cmd_lens(args: str, session: ChatSession) -> str:
    """Show current lens info or switch to different lens."""
    if not args:
        # Show current lens
        if not session.lens:
            return "No lens loaded"

        meta = session.lens.metadata
        return f"""Current lens: {meta.name} v{meta.version}
Domain: {meta.domain or 'general'}
Description: {meta.description or 'No description'}
Heuristics: {len(session.lens.heuristics)}
Skills: {len(session.lens.skills) if hasattr(session.lens, 'skills') else 0}"""

    # Switch lens (requires lens loader integration)
    return f"Switching lens not yet implemented. Use: sunwell chat --lens {args}"


@commands.register("tools", "List available tools")
async def cmd_tools(args: str, session: ChatSession) -> str:
    """List available tools."""
    from sunwell.tools.builtins import CORE_TOOLS

    lines = ["Available tools:"]
    for name, tool in CORE_TOOLS.items():
        lines.append(f"  • {name}: {tool.description[:60]}...")

    return "\n".join(lines)


@commands.register("exit", "Exit chat session")
async def cmd_exit(args: str, session: ChatSession) -> str:
    """Exit chat session."""
    # This is handled specially in the chat loop
    return "Exiting..."


@commands.register("context", "Show current context")
async def cmd_context(args: str, session: ChatSession) -> str:
    """Show current context state."""
    history_count = len(session.conversation_history)
    lens_name = session.lens.metadata.name if session.lens else "None"

    return f"""Current context:
Lens: {lens_name}
Conversation turns: {history_count}
Last response: {len(session.last_response):,} bytes"""


# =============================================================================
# RFC-107: Shortcut Commands
# =============================================================================


@commands.register("a", "Quick audit (alias for audit-documentation skill)")
async def cmd_audit(args: str, session: ChatSession) -> str:
    """Execute audit-documentation skill."""
    return await _execute_skill_shortcut("::a", args, session)


@commands.register("a-2", "Deep audit with triangulation")
async def cmd_audit_deep(args: str, session: ChatSession) -> str:
    """Execute audit-documentation-deep skill."""
    return await _execute_skill_shortcut("::a-2", args, session)


@commands.register("p", "Polish documentation")
async def cmd_polish(args: str, session: ChatSession) -> str:
    """Execute polish-documentation skill."""
    return await _execute_skill_shortcut("::p", args, session)


@commands.register("health", "Documentation health check")
async def cmd_health(args: str, session: ChatSession) -> str:
    """Execute check-health skill."""
    return await _execute_skill_shortcut("::health", args, session)


@commands.register("score", "Calculate confidence scores")
async def cmd_score(args: str, session: ChatSession) -> str:
    """Execute score-confidence skill."""
    return await _execute_skill_shortcut("::score", args, session)


@commands.register("drift", "Find stale documentation")
async def cmd_drift(args: str, session: ChatSession) -> str:
    """Execute detect-drift skill."""
    return await _execute_skill_shortcut("::drift", args, session)


@commands.register("lint", "Validate document structure")
async def cmd_lint(args: str, session: ChatSession) -> str:
    """Execute lint-structure skill."""
    return await _execute_skill_shortcut("::lint", args, session)


@commands.register("vdr", "VDR/VPR checklist assessment")
async def cmd_vdr(args: str, session: ChatSession) -> str:
    """Execute assess-vdr skill."""
    return await _execute_skill_shortcut("::vdr", args, session)


async def _execute_skill_shortcut(shortcut: str, args: str, session: ChatSession) -> str:
    """Execute a skill via shortcut.

    RFC-107: Implements chat-mode shortcut execution.
    """
    if not session.lens:
        return "No lens loaded. Use --lens when starting chat."

    if not session.lens.router or not session.lens.router.shortcuts:
        return "Current lens has no shortcuts defined."

    skill_name = session.lens.router.shortcuts.get(shortcut)
    if not skill_name:
        return f"Shortcut {shortcut} not defined in current lens."

    skill = session.lens.get_skill(skill_name)
    if not skill:
        return f"Skill {skill_name} not found in lens."

    # Build context from args
    context: dict[str, str] = {}
    if args:
        context["task"] = args

        # If args looks like a file path, read it
        target_path = Path(args).expanduser()
        if target_path.exists():
            context["target_file"] = str(target_path)
            import contextlib

            with contextlib.suppress(Exception):
                context["file_content"] = target_path.read_text()

    # Return info about what would run (full execution requires model integration)
    tools = ", ".join(skill.allowed_tools) if skill.allowed_tools else "none"
    task = context.get("task", "none")
    target = context.get("target_file", "none")
    cmd_hint = f"sunwell do {shortcut} {args or '<target>'}"
    skill_info = f"""**Skill**: {skill_name}
**Description**: {skill.description}
**Trust Level**: {skill.trust.value}
**Allowed Tools**: {tools}

**Context**:
- Task: {task}
- Target file: {target}

[Note: Full skill execution requires running `{cmd_hint}` from CLI]"""

    return skill_info


# =============================================================================
# Integration Helper
# =============================================================================

async def handle_command(
    user_input: str,
    session: ChatSession,
    registry: CommandRegistry = commands,
) -> tuple[bool, str | None]:
    """Process user input, handling commands if present.

    Returns:
        Tuple of (is_command, response)
        - If is_command is True, response contains the command result
        - If is_command is False, response is None (input was not a command)
    """
    parsed = parse_input(user_input)

    if not parsed.is_command:
        return False, None

    response = await registry.execute(parsed.command, parsed.args, session)  # type: ignore
    return True, response
