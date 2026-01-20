"""Binding - Your attuned instance of a lens.

Like a soul stone from WoW - you attune once, it remembers everything:
- Which lens (expertise)
- Which model (provider, name)
- Which simulacrum (memory)
- Your personal settings

Usage:
    # Attune once
    sunwell bind my-project --lens tech-writer.lens --provider openai

    # Use forever (no flags needed!)
    sunwell ask my-project "Write API docs"
    sunwell ask my-project "What did we discuss?"

    # Or set a default
    sunwell default my-project
    sunwell ask "Write docs"  # Uses default binding
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Binding:
    """Your personal attunement to a lens.

    Stores all the config so you don't need flags:
    - lens: Path to the lens file
    - provider: LLM provider (openai, anthropic, etc.)
    - model: Model name (gpt-4o, claude-sonnet-4-20250514, etc.)
    - simulacrum: Name of associated simulacrum
    - settings: Personal overrides
    """

    name: str
    """Binding name (e.g., "my-project", "docs-writer")."""

    lens_path: str
    """Path to lens file."""

    provider: str = "openai"
    """LLM provider."""

    model: str = "gpt-4o"
    """Model name."""

    simulacrum: str | None = None
    """Associated simulacrum name (defaults to binding name)."""

    # Execution settings
    tier: int = 1
    """Default execution tier (0=fast, 1=standard, 2=deep)."""

    stream: bool = True
    """Stream output by default."""

    verbose: bool = False
    """Verbose output by default."""

    auto_learn: bool = True
    """Auto-extract learnings from responses."""

    # Workspace settings
    workspace_patterns: list[str] = field(default_factory=list)
    """File patterns to include as context."""

    index_workspace: bool = True
    """Auto-index workspace for code context."""

    # Tool settings (RFC-012)
    tools_enabled: bool = False
    """Enable tool calling (read/write files, run commands)."""

    trust_level: str = "workspace"
    """Tool trust level: discovery, read_only, workspace, shell."""

    allowed_tools: list[str] = field(default_factory=list)
    """Restrict to specific tools (empty = all allowed by trust level)."""

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    use_count: int = 0

    def __post_init__(self):
        """Set simulacrum name if not provided."""
        if self.simulacrum is None:
            self.simulacrum = self.name

    def touch(self) -> None:
        """Update last_used and increment use_count."""
        self.last_used = datetime.now().isoformat()
        self.use_count += 1

    def save(self, path: Path) -> None:
        """Save binding to file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "lens_path": self.lens_path,
            "provider": self.provider,
            "model": self.model,
            "simulacrum": self.simulacrum,
            "tier": self.tier,
            "stream": self.stream,
            "verbose": self.verbose,
            "auto_learn": self.auto_learn,
            "workspace_patterns": self.workspace_patterns,
            "index_workspace": self.index_workspace,
            "tools_enabled": self.tools_enabled,
            "trust_level": self.trust_level,
            "allowed_tools": self.allowed_tools,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> Binding:
        """Load binding from file."""
        with open(path) as f:
            data = json.load(f)

        # Migration: support old "headspace" field name
        simulacrum = data.get("simulacrum") or data.get("headspace")

        return cls(
            name=data["name"],
            lens_path=data["lens_path"],
            provider=data.get("provider", "openai"),
            model=data.get("model", "gpt-4o"),
            simulacrum=simulacrum,
            tier=data.get("tier", 1),
            stream=data.get("stream", True),
            verbose=data.get("verbose", False),
            auto_learn=data.get("auto_learn", True),
            workspace_patterns=data.get("workspace_patterns", []),
            index_workspace=data.get("index_workspace", True),
            tools_enabled=data.get("tools_enabled", False),
            trust_level=data.get("trust_level", "workspace"),
            allowed_tools=data.get("allowed_tools", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_used=data.get("last_used", datetime.now().isoformat()),
            use_count=data.get("use_count", 0),
        )


class BindingManager:
    """Manages bindings (soul stones).

    Storage: .sunwell/bindings/<name>.json
    Default: .sunwell/default_binding (contains name of default)
    """

    def __init__(self, root: Path | None = None):
        """Initialize binding manager.

        Args:
            root: Project root (defaults to cwd).
        """
        self.root = root or Path.cwd()
        self.bindings_dir = self.root / ".sunwell" / "bindings"
        self.default_file = self.root / ".sunwell" / "default_binding"

    def create(
        self,
        name: str,
        lens_path: str,
        provider: str = "openai",
        model: str | None = None,
        **settings,
    ) -> Binding:
        """Create a new binding (attune to a lens)."""
        # Auto-select model based on provider if not specified
        if model is None:
            model = {
                "openai": "gpt-4o",
                "anthropic": "claude-sonnet-4-20250514",
                "ollama": "gemma3:4b",
            }.get(provider, "gpt-4o")

        binding = Binding(
            name=name,
            lens_path=lens_path,
            provider=provider,
            model=model,
            **settings,
        )

        self._save(binding)
        return binding

    def get(self, name: str) -> Binding | None:
        """Get a binding by name."""
        path = self.bindings_dir / f"{name}.json"
        if not path.exists():
            return None
        return Binding.load(path)

    def get_or_default(self, name: str | None = None) -> Binding | None:
        """Get binding by name, or default if no name provided."""
        if name:
            return self.get(name)
        return self.get_default()

    def get_default(self) -> Binding | None:
        """Get the default binding."""
        if not self.default_file.exists():
            return None

        default_name = self.default_file.read_text().strip()
        return self.get(default_name)

    def set_default(self, name: str) -> bool:
        """Set the default binding."""
        binding = self.get(name)
        if not binding:
            return False

        self.default_file.parent.mkdir(parents=True, exist_ok=True)
        self.default_file.write_text(name)
        return True

    def list_all(self) -> list[Binding]:
        """List all bindings."""
        if not self.bindings_dir.exists():
            return []

        bindings = []
        for path in self.bindings_dir.glob("*.json"):
            try:
                bindings.append(Binding.load(path))
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(bindings, key=lambda b: b.last_used, reverse=True)

    def delete(self, name: str) -> bool:
        """Delete a binding."""
        path = self.bindings_dir / f"{name}.json"
        if not path.exists():
            return False

        path.unlink()

        # Clear default if this was it
        if self.default_file.exists() and self.default_file.read_text().strip() == name:
            self.default_file.unlink()

        return True

    def use(self, name: str) -> Binding | None:
        """Get a binding and mark it as used."""
        binding = self.get(name)
        if binding:
            binding.touch()
            self._save(binding)
        return binding

    def _save(self, binding: Binding) -> None:
        """Save a binding."""
        path = self.bindings_dir / f"{binding.name}.json"
        binding.save(path)


# Convenience function for CLI
def get_binding_or_create_temp(
    binding_name: str | None,
    lens_path: str | None,
    provider: str | None,
    model: str | None,
    simulacrum: str | None,
) -> tuple[Binding | None, bool]:
    """Get existing binding or create temporary one from CLI args.

    Returns (binding, is_temporary).
    """
    manager = BindingManager()

    # If binding name provided, try to load it
    if binding_name:
        binding = manager.use(binding_name)
        if binding:
            # Override with any CLI args provided
            if provider:
                binding.provider = provider
            if model:
                binding.model = model
            if simulacrum:
                binding.simulacrum = simulacrum
            return binding, False

    # Try default binding
    if not lens_path:
        default = manager.get_default()
        if default:
            default.touch()
            if provider:
                default.provider = provider
            if model:
                default.model = model
            if simulacrum:
                default.simulacrum = simulacrum
            return default, False

    # Create temporary binding (not saved)
    if lens_path:
        temp = Binding(
            name="_temp",
            lens_path=lens_path,
            provider=provider or "openai",
            model=model or "gpt-4o",
            simulacrum=simulacrum,
        )
        return temp, True

    return None, False
