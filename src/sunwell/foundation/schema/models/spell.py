"""Spells - Portable Workflow Incantations (RFC-021).

Spells are magical incantations that trigger specific workflows with full
execution context. Like WoW spells, they provide:

- Incantation: The trigger command (::security, ::audit)
- Instructions: How to approach the task
- Template: Expected output format
- Reagents: Components to load (heuristics, personas)
- Validation: Quality gates with enforcement modes

Moved from sunwell.core.models.spell to foundation since the data types
are stdlib-only. The routing integration (to_routing_decision) stays in
core.models.spell as a standalone function.

Terminology:
- Spell: A reusable task definition
- Incantation: The ::command that casts the spell
- Spellbook: Collection of spells in a lens
- Grimoire: Manages spell discovery and resolution
- Reagents: Components required to cast (heuristics, personas)
- Cantrips: Built-in default spells
- Cast: Execute a spell
"""


import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from sunwell.foundation.utils import safe_yaml_load

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens


class ReagentType(str, Enum):
    """Types of reagents that can be loaded by a spell."""

    HEURISTIC = "heuristic"
    PERSONA = "persona"
    VALIDATOR = "validator"
    LENS = "lens"


class ReagentMode(str, Enum):
    """How a reagent should be loaded."""

    INCLUDE = "include"  # Force-add to context
    BOOST = "boost"  # Increase retrieval priority


class ValidationMode(str, Enum):
    """How strictly to enforce quality gates."""

    LOG = "log"  # Log failures, return result anyway
    WARN = "warn"  # Log + annotate result with warnings
    BLOCK = "block"  # Retry or fail if gates not met


@dataclass(frozen=True, slots=True)
class Reagent:
    """A component required to cast a spell.

    Like WoW reagents, these are loaded when casting.
    """

    type: ReagentType
    name: str
    source: str | None = None  # Lens name for cross-lens refs
    mode: ReagentMode = ReagentMode.INCLUDE

    def __str__(self) -> str:
        source_str = f"{self.source}:" if self.source else ""
        return f"{self.type.value}:{source_str}{self.name}"


@dataclass(frozen=True, slots=True)
class SpellExample:
    """Good or bad example for a spell."""

    content: str
    quality: Literal["good", "bad"]
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class SpellValidation:
    """Validation configuration for a spell."""

    mode: ValidationMode = ValidationMode.WARN
    gates: tuple[str, ...] = ()
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Spell:
    """A portable workflow incantation with full execution context.

    Spells are magical incantations that trigger specific workflows
    with complete context — like WoW's spell system.

    Note: to_routing_decision() was extracted to
    sunwell.core.models.spell.spell_to_routing_decision() during
    the layer burn-down to keep this class in foundation (stdlib-only).
    """

    # Identity
    incantation: str  # "::security", "::audit", etc.
    description: str  # Human-readable description
    aliases: tuple[str, ...] = ()  # Short forms ["::sec", "::s"]

    # Routing (RFC-020)
    intent: str = "unknown"  # code_review, documentation, etc.
    focus: tuple[str, ...] = ()  # Keywords for retrieval boosting
    complexity: str = "moderate"  # simple, moderate, complex
    top_k: int | None = None  # Override default retrieval count
    threshold: float | None = None  # Override default threshold

    # Context
    instructions: str = ""  # Detailed task guidance
    template: str = ""  # Expected output structure
    examples: tuple[SpellExample, ...] = ()

    # Reagents (Modules)
    reagents: tuple[Reagent, ...] = ()

    # Validation
    validation: SpellValidation = field(default_factory=SpellValidation)

    # Workflow
    skill: str | None = None  # Execute a specific skill

    # Merge behavior
    merge: bool = False  # Merge with lower layers
    instructions_append: str = ""  # Append to instructions (for merge)

    def all_incantations(self) -> tuple[str, ...]:
        """Return all incantations including aliases."""
        return (self.incantation,) + self.aliases

    def to_system_context(self, template_vars: dict[str, str] | None = None) -> str:
        """Generate system prompt additions from spell context."""
        parts = []
        vars_ = template_vars or {}

        if self.instructions:
            instructions = self._apply_template_vars(self.instructions, vars_)
            parts.append(f"## Task Instructions\n\n{instructions}")

        if self.template:
            template = self._apply_template_vars(self.template, vars_)
            parts.append(f"## Expected Output Format\n\n{template}")

        if self.validation.gates:
            gates = "\n".join(f"- [ ] {g}" for g in self.validation.gates)
            parts.append(f"## Quality Checklist\n\n{gates}")

        if self.examples:
            good = [e for e in self.examples if e.quality == "good"]
            bad = [e for e in self.examples if e.quality == "bad"]

            if good:
                parts.append(
                    "## Good Examples\n\n"
                    + "\n\n".join(f"```\n{e.content}\n```" for e in good)
                )
            if bad:
                parts.append(
                    "## Avoid These Patterns\n\n"
                    + "\n\n".join(
                        f"```\n{e.content}\n```\n*Why:* {e.explanation}" for e in bad
                    )
                )

        return "\n\n---\n\n".join(parts)

    def _apply_template_vars(self, text: str, vars_: dict[str, str]) -> str:
        """Apply template variables to text."""
        result = text
        for key, value in vars_.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result

    def merge_with(self, base: Spell) -> Spell:
        """Merge this spell with a base spell (for override layers)."""
        if not self.merge:
            return self  # Full override

        # Merge fields
        merged_focus = tuple(set(base.focus) | set(self.focus))
        merged_gates = base.validation.gates + self.validation.gates
        merged_reagents = self._dedupe_reagents(base.reagents + self.reagents)

        # Instructions: append if instructions_append set
        merged_instructions = base.instructions
        if self.instructions:
            merged_instructions = self.instructions
        if self.instructions_append:
            merged_instructions = f"{merged_instructions}\n\n{self.instructions_append}"

        return Spell(
            incantation=self.incantation,
            description=self.description or base.description,
            aliases=self.aliases or base.aliases,
            intent=self.intent if self.intent != "unknown" else base.intent,
            focus=merged_focus,
            complexity=self.complexity
            if self.complexity != "moderate"
            else base.complexity,
            top_k=self.top_k or base.top_k,
            threshold=self.threshold or base.threshold,
            instructions=merged_instructions,
            template=self.template or base.template,
            examples=self.examples or base.examples,
            reagents=merged_reagents,
            validation=SpellValidation(
                mode=self.validation.mode,
                gates=merged_gates,
                must_contain=self.validation.must_contain
                or base.validation.must_contain,
                must_not_contain=self.validation.must_not_contain
                or base.validation.must_not_contain,
            ),
            skill=self.skill or base.skill,
            merge=False,  # Result is fully resolved
        )

    def _dedupe_reagents(self, reagents: tuple[Reagent, ...]) -> tuple[Reagent, ...]:
        """Deduplicate reagents by type+name."""
        seen: set[tuple[ReagentType, str, str | None]] = set()
        result = []
        for r in reagents:
            key = (r.type, r.name, r.source)
            if key not in seen:
                seen.add(key)
                result.append(r)
        return tuple(result)


@dataclass(slots=True)
class SpellResult:
    """Result from casting a spell, including validation outcomes."""

    spell: Spell
    content: str
    validation_passed: bool = True
    validation_warnings: tuple[str, ...] = ()
    gate_results: dict[str, bool] = field(default_factory=dict)

    def with_warnings(self, warnings: list[str]) -> SpellResult:
        """Return a new result with added warnings."""
        return SpellResult(
            spell=self.spell,
            content=self.content,
            validation_passed=self.validation_passed,
            validation_warnings=tuple(list(self.validation_warnings) + warnings),
            gate_results=self.gate_results,
        )


@dataclass(slots=True)
class Grimoire:
    """Loads and manages spells from all sources.

    The Grimoire is the spellbook manager — it discovers spells from
    user config, project config, active lens, and built-in cantrips.

    Resolution order (highest priority first):
    1. User spells (~/.sunwell/spells.yaml)
    2. Project spells (.sunwell/spells.yaml)
    3. Active lens spellbook
    4. Built-in cantrips
    """

    user_path: str = "~/.sunwell/spells.yaml"
    project_path: str = ".sunwell/spells.yaml"

    _user_spells: dict[str, Spell] = field(default_factory=dict)
    _project_spells: dict[str, Spell] = field(default_factory=dict)
    _lens_spells: dict[str, Spell] = field(default_factory=dict)
    _cantrips: dict[str, Spell] = field(default_factory=dict)

    # Alias resolution cache
    _alias_map: dict[str, str] = field(default_factory=dict)

    def load(self, lens: Lens | None = None) -> None:
        """Load spells from all sources (gather the spellbooks)."""
        # Load user spells
        user_path = Path(os.path.expanduser(self.user_path))
        if user_path.exists():
            self._user_spells = self._load_yaml(user_path)

        # Load project spells
        project_path = Path(self.project_path)
        if project_path.exists():
            self._project_spells = self._load_yaml(project_path)

        # Load lens spells
        if lens and hasattr(lens, "spellbook") and lens.spellbook:
            for spell in lens.spellbook:
                self._lens_spells[spell.incantation] = spell
                for alias in spell.aliases:
                    self._alias_map[alias] = spell.incantation

        # Load cantrips (built-in defaults)
        self._cantrips = self._get_cantrips()

        # Build alias map for all layers
        self._build_alias_map()

    def _load_yaml(self, path: Path) -> dict[str, Spell]:
        """Load spells from a YAML spellbook."""
        data = safe_yaml_load(path)

        spells = {}
        for spell_data in data.get("spellbook", []):
            spell = parse_spell(spell_data)
            spells[spell.incantation] = spell

        return spells

    def _get_cantrips(self) -> dict[str, Spell]:
        """Get built-in cantrip spells (simple, always-available)."""
        return {
            "::a": Spell(
                incantation="::a",
                aliases=("::audit",),
                description="Audit code or documentation for accuracy",
                intent="code_review",
                focus=("audit", "validation", "accuracy"),
            ),
            "::review": Spell(
                incantation="::review",
                aliases=("::r",),
                description="General code review",
                intent="code_review",
                focus=("quality", "patterns", "issues"),
            ),
            "::test": Spell(
                incantation="::test",
                aliases=("::t",),
                description="Generate or review tests",
                intent="testing",
                focus=("testing", "coverage", "edge cases"),
            ),
            "::doc": Spell(
                incantation="::doc",
                aliases=("::d", "::write"),
                description="Write or improve documentation",
                intent="documentation",
                focus=("clarity", "examples", "structure"),
            ),
            "::help": Spell(
                incantation="::help",
                aliases=("::?", "::h"),
                description="Show available spells and help",
                intent="explanation",
                focus=("help", "commands", "usage"),
            ),
            "::security": Spell(
                incantation="::security",
                aliases=("::sec", "::s"),
                description="Security-focused code review",
                intent="code_review",
                focus=("security", "vulnerability", "injection", "auth"),
                complexity="complex",
                instructions="""Perform a security-focused code review:

1. **Input Validation** - Check all user inputs for sanitization
2. **Authentication & Session** - Verify password hashing, session management
3. **Authorization** - Verify access control checks, look for IDOR
4. **Cryptography** - Verify secure algorithms
5. **Information Disclosure** - Check error messages, debug info
""",
            ),
            "::perf": Spell(
                incantation="::perf",
                aliases=("::performance",),
                description="Performance-focused analysis",
                intent="analysis",
                focus=("performance", "optimization", "complexity", "N+1"),
            ),
            "::refactor": Spell(
                incantation="::refactor",
                aliases=("::ref",),
                description="Code refactoring suggestions",
                intent="refactoring",
                focus=("refactoring", "clean code", "patterns", "DRY"),
            ),
        }

    def _build_alias_map(self) -> None:
        """Build alias -> incantation mapping for all layers."""
        for source in [
            self._cantrips,
            self._lens_spells,
            self._project_spells,
            self._user_spells,
        ]:
            for incantation, spell in source.items():
                for alias in spell.aliases:
                    self._alias_map[alias] = incantation

    def resolve(self, incantation: str) -> Spell | None:
        """Resolve an incantation (or alias) to a spell.

        Resolution order: user -> project -> lens -> cantrips
        Merges spells if `merge: true` is set.
        """
        # Normalize: lowercase and ensure :: prefix
        incantation = incantation.lower().strip()
        if not incantation.startswith("::"):
            incantation = f"::{incantation}"

        # Resolve alias to primary incantation
        primary = self._alias_map.get(incantation, incantation)

        # Collect spells from all layers (in reverse priority)
        layers = [
            self._cantrips.get(primary),
            self._lens_spells.get(primary),
            self._project_spells.get(primary),
            self._user_spells.get(primary),
        ]

        # Filter None and merge
        spells = [s for s in layers if s is not None]
        if not spells:
            return None

        # Start with base, merge higher layers
        result = spells[0]
        for spell in spells[1:]:
            result = spell.merge_with(result)

        return result

    def list_spells(self) -> list[Spell]:
        """List all available spells."""
        seen: set[str] = set()
        result = []

        # Process in priority order
        for source in [
            self._user_spells,
            self._project_spells,
            self._lens_spells,
            self._cantrips,
        ]:
            for incantation in source:
                if incantation not in seen:
                    seen.add(incantation)
                    resolved = self.resolve(incantation)
                    if resolved:
                        result.append(resolved)

        return sorted(result, key=lambda s: s.incantation)

    def set_lens(self, lens: Lens) -> None:
        """Update the active lens and reload lens spells."""
        self._lens_spells.clear()
        self._alias_map.clear()

        if hasattr(lens, "spellbook") and lens.spellbook:
            for spell in lens.spellbook:
                self._lens_spells[spell.incantation] = spell

        self._build_alias_map()

    def get_template_vars(
        self,
        filename: str | None = None,
        filepath: str | None = None,
        language: str | None = None,
        lens_name: str | None = None,
        project: str | None = None,
        custom_vars: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Get template variables for spell context."""
        now = datetime.now()
        vars_: dict[str, str] = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        }

        if filename:
            vars_["filename"] = filename
        if filepath:
            vars_["filepath"] = filepath
        if language:
            vars_["language"] = language
        if lens_name:
            vars_["lens"] = lens_name
        if project:
            vars_["project"] = project

        # Merge custom vars
        if custom_vars:
            vars_.update(custom_vars)

        return vars_


def parse_spell(data: dict[str, Any]) -> Spell:
    """Parse a spell from YAML data."""
    # Parse reagents
    reagents = []
    for r in data.get("reagents", []):
        reagents.append(
            Reagent(
                type=ReagentType(r.get("type", "heuristic")),
                name=r["name"],
                source=r.get("source"),
                mode=ReagentMode(r.get("mode", "include")),
            )
        )

    # Parse validation
    validation_data = data.get("validation", {})
    validation = SpellValidation(
        mode=ValidationMode(validation_data.get("mode", "warn")),
        gates=tuple(validation_data.get("gates", [])),
        must_contain=tuple(validation_data.get("must_contain", [])),
        must_not_contain=tuple(validation_data.get("must_not_contain", [])),
    )

    # Parse examples
    examples = []
    for e in data.get("examples", []):
        examples.append(
            SpellExample(
                content=e["content"],
                quality=e.get("quality", "good"),
                explanation=e.get("explanation", ""),
            )
        )

    return Spell(
        incantation=data["incantation"],
        description=data.get("description", ""),
        aliases=tuple(data.get("aliases", [])),
        intent=data.get("intent", "unknown"),
        focus=tuple(data.get("focus", [])),
        complexity=data.get("complexity", "moderate"),
        top_k=data.get("top_k"),
        threshold=data.get("threshold"),
        instructions=data.get("instructions", ""),
        template=data.get("template", ""),
        examples=tuple(examples),
        reagents=tuple(reagents),
        validation=validation,
        skill=data.get("skill"),
        merge=data.get("merge", False),
        instructions_append=data.get("instructions_append", ""),
    )


def validate_spell_output(content: str, spell: Spell) -> SpellResult:
    """Validate spell output against quality gates.

    Returns SpellResult with validation status and warnings.
    """
    warnings: list[str] = []
    gate_results: dict[str, bool] = {}
    validation = spell.validation

    # Check must_contain
    for pattern in validation.must_contain:
        if pattern.lower() not in content.lower():
            warnings.append(f"Missing required content: {pattern}")
            gate_results[f"must_contain:{pattern}"] = False
        else:
            gate_results[f"must_contain:{pattern}"] = True

    # Check must_not_contain
    for pattern in validation.must_not_contain:
        if pattern.lower() in content.lower():
            warnings.append(f"Contains forbidden content: {pattern}")
            gate_results[f"must_not_contain:{pattern}"] = False
        else:
            gate_results[f"must_not_contain:{pattern}"] = True

    # Gates are informational - we note them but don't auto-check
    for gate in validation.gates:
        gate_results[f"gate:{gate}"] = True  # Assume passing, user validates

    validation_passed = len(warnings) == 0

    return SpellResult(
        spell=spell,
        content=content,
        validation_passed=validation_passed,
        validation_warnings=tuple(warnings),
        gate_results=gate_results,
    )
