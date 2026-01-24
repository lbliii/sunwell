"""Lens injection experiment variants (RFC-XXX).

Systematically tests different FORMATTING approaches for injecting
the FULL lens into prompts. All strategies include the complete lens -
the variation is HOW it's structured/presented.

Key insight: The lens should ALWAYS be fully provided. The question is
what format helps the model best comprehend and apply it.

Experiment Variants (all include full lens):
1. BASELINE - Current demo approach (minimal, for comparison only)
2. MARKDOWN_FULL - Full lens as structured markdown (lens.to_context())
3. XML_STRUCTURED - Full lens with XML tags for parsing
4. EXAMPLES_PROMINENT - Full lens with examples section first
5. NEGATIVES_FIRST - Full lens with "never" rules prominent
6. ROLE_FRAMED - Full lens wrapped in expert role-play frame
7. CHECKLIST_FORMAT - Full lens as actionable checklist
8. PRIORITY_ORDERED - Full lens ordered by heuristic priority
9. SYSTEM_SPLIT - Full lens split: rules in system, task in user
10. COMPACT_DENSE - Full lens compressed to reduce tokens
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class LensStrategy(Enum):
    """Lens injection strategy variants.
    
    All strategies (except BASELINE) include the FULL lens content.
    The variation is how that content is formatted/structured.
    """

    BASELINE = "baseline"  # Current demo approach (minimal) - for comparison only
    MARKDOWN_FULL = "markdown_full"  # Full lens as markdown (default format)
    XML_STRUCTURED = "xml_structured"  # Full lens with XML tags
    EXAMPLES_PROMINENT = "examples_prominent"  # Examples section first
    NEGATIVES_FIRST = "negatives_first"  # Never rules prominent
    ROLE_FRAMED = "role_framed"  # Expert role-play wrapper
    CHECKLIST_FORMAT = "checklist_format"  # Actionable checklist
    PRIORITY_ORDERED = "priority_ordered"  # Ordered by priority
    SYSTEM_SPLIT = "system_split"  # Split lens/task into system/user
    COMPACT_DENSE = "compact_dense"  # Compressed format


@dataclass(frozen=True, slots=True)
class LensData:
    """Parsed lens data for prompt building."""

    name: str
    domain: str
    description: str
    heuristics: tuple[dict[str, Any], ...]
    communication: dict[str, Any] | None
    quality_policy: dict[str, Any] | None

    @classmethod
    def from_yaml(cls, path: Path) -> "LensData":
        """Load lens data from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        lens = data.get("lens", {})
        metadata = lens.get("metadata", {})

        return cls(
            name=metadata.get("name", "Unknown"),
            domain=metadata.get("domain", "general"),
            description=metadata.get("description", ""),
            heuristics=tuple(lens.get("heuristics", [])),
            communication=lens.get("communication"),
            quality_policy=lens.get("quality_policy"),
        )


class LensPromptBuilder(ABC):
    """Abstract base for lens-enhanced prompt builders."""

    def __init__(self, lens: LensData) -> None:
        self.lens = lens

    @abstractmethod
    def build_prompt(self, task_prompt: str) -> str:
        """Build the full prompt with lens enhancement."""
        ...

    @property
    @abstractmethod
    def strategy(self) -> LensStrategy:
        """Return the strategy identifier."""
        ...


# =============================================================================
# Helper: Full Lens Content Generators
# =============================================================================


def _get_all_heuristic_content(lens: LensData) -> dict[str, Any]:
    """Extract all content from lens heuristics for full inclusion."""
    all_always: list[str] = []
    all_never: list[str] = []
    all_examples_good: list[str] = []
    all_examples_bad: list[str] = []
    all_rules: list[tuple[str, str, float]] = []  # (name, rule, priority)

    for h in lens.heuristics:
        name = h.get("name", "")
        rule = h.get("rule", "")
        priority = h.get("priority", 0)
        all_rules.append((name, rule, priority))

        for a in h.get("always", []):
            all_always.append(a)
        for n in h.get("never", []):
            all_never.append(n)

        examples = h.get("examples", {})
        if examples.get("good"):
            g = examples["good"]
            if isinstance(g, list):
                all_examples_good.extend(g)
            else:
                all_examples_good.append(g)
        if examples.get("bad"):
            b = examples["bad"]
            if isinstance(b, list):
                all_examples_bad.extend(b)
            else:
                all_examples_bad.append(b)

    return {
        "rules": all_rules,
        "always": all_always,
        "never": all_never,
        "examples_good": all_examples_good,
        "examples_bad": all_examples_bad,
    }


# =============================================================================
# Strategy 1: BASELINE (Current Demo - Minimal, for comparison)
# =============================================================================


class BaselinePromptBuilder(LensPromptBuilder):
    """Current minimal approach - first always rule from high-priority heuristics.
    
    IMPORTANT: This is the BROKEN approach used by the current demo.
    It only uses ~8 requirements and ignores most of the lens.
    Included only for comparison to show how much better full-lens is.
    """

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.BASELINE

    def build_prompt(self, task_prompt: str) -> str:
        requirements = [
            "Include type hints for all parameters and return values",
            "Write a complete docstring with Args, Returns, and Raises sections",
            "Handle edge cases and errors appropriately",
            "Follow Python best practices",
        ]

        # Add lens rules (only first "always" from priority >= 0.85)
        sorted_h = sorted(
            self.lens.heuristics,
            key=lambda h: h.get("priority", 0),
            reverse=True,
        )
        for h in sorted_h:
            if h.get("priority", 0) >= 0.85:
                always_rules = h.get("always", [])
                if always_rules and len(requirements) < 8:
                    requirements.append(always_rules[0])

        return f"""Write production-quality Python code.

Task: {task_prompt}

Requirements:
{chr(10).join(f'- {r}' for r in requirements)}

Code only (no explanations):"""


# =============================================================================
# Strategy 2: MARKDOWN_FULL (Full lens as markdown)
# =============================================================================


class MarkdownFullPromptBuilder(LensPromptBuilder):
    """Full lens content as structured markdown - the canonical format."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.MARKDOWN_FULL

    def build_prompt(self, task_prompt: str) -> str:
        sections = [f"# Expertise: {self.lens.name}"]
        if self.lens.description:
            sections.append(self.lens.description)

        # ALL heuristics in full
        sections.append("\n## Heuristics\n")
        sorted_h = sorted(
            self.lens.heuristics,
            key=lambda h: h.get("priority", 0),
            reverse=True,
        )

        for h in sorted_h:
            sections.append(f"### {h.get('name', 'Unknown')} (priority: {h.get('priority', 0)})")
            sections.append(f"**Rule**: {h.get('rule', '')}")

            if h.get("always"):
                sections.append("**Always**:")
                for a in h["always"]:
                    sections.append(f"- {a}")

            if h.get("never"):
                sections.append("**Never**:")
                for n in h["never"]:
                    sections.append(f"- {n}")

            examples = h.get("examples", {})
            if examples.get("good"):
                sections.append(f"**Good example**: `{examples['good']}`")
            if examples.get("bad"):
                sections.append(f"**Bad example**: `{examples['bad']}`")
            sections.append("")

        # Communication style
        if self.lens.communication:
            sections.append("## Communication Style")
            if self.lens.communication.get("tone"):
                tone = self.lens.communication["tone"]
                if isinstance(tone, list):
                    sections.append(f"**Tone**: {', '.join(tone)}")
                else:
                    sections.append(f"**Tone**: {tone}")
            if self.lens.communication.get("avoid"):
                avoid = self.lens.communication["avoid"]
                if isinstance(avoid, list):
                    sections.append(f"**Avoid**: {', '.join(avoid)}")
                else:
                    sections.append(f"**Avoid**: {avoid}")

        return f"""{chr(10).join(sections)}

---

## Task
{task_prompt}

Write production-quality Python code following ALL heuristics above.
Code only (no explanations):"""


# =============================================================================
# Strategy 3: XML_STRUCTURED (Full lens with XML tags)
# =============================================================================


class XMLStructuredPromptBuilder(LensPromptBuilder):
    """Full lens content with XML tags for clear section parsing."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.XML_STRUCTURED

    def build_prompt(self, task_prompt: str) -> str:
        # Build ALL heuristics as XML
        heuristics_xml = []
        sorted_h = sorted(
            self.lens.heuristics,
            key=lambda h: h.get("priority", 0),
            reverse=True,
        )

        for h in sorted_h:  # ALL heuristics
            always = h.get("always", [])
            never = h.get("never", [])
            examples = h.get("examples", {})

            always_xml = "\n".join(f"    <rule>{a}</rule>" for a in always)
            never_xml = "\n".join(f"    <rule>{n}</rule>" for n in never)

            heuristics_xml.append(f"""  <heuristic name="{h.get('name', 'Unknown')}" priority="{h.get('priority', 0)}">
    <principle>{h.get('rule', '')}</principle>
    <always>
{always_xml}
    </always>
    <never>
{never_xml}
    </never>
    <examples>
      <good>{examples.get("good", "")}</good>
      <bad>{examples.get("bad", "")}</bad>
    </examples>
  </heuristic>""")

        # Communication style
        comm_xml = ""
        if self.lens.communication:
            tone = self.lens.communication.get("tone", [])
            avoid = self.lens.communication.get("avoid", [])
            tone_str = ", ".join(tone) if isinstance(tone, list) else str(tone)
            avoid_str = ", ".join(avoid) if isinstance(avoid, list) else str(avoid)
            comm_xml = f"""
<communication>
  <tone>{tone_str}</tone>
  <avoid>{avoid_str}</avoid>
</communication>"""

        return f"""<expertise domain="{self.lens.domain}" name="{self.lens.name}">
<description>{self.lens.description}</description>

<heuristics>
{chr(10).join(heuristics_xml)}
</heuristics>
{comm_xml}
</expertise>

<task>{task_prompt}</task>

<instructions>
Apply ALL heuristics from the expertise above.
Return ONLY Python code. No explanations, no markdown fences.
</instructions>"""


# =============================================================================
# Strategy 4: EXAMPLES_PROMINENT (Full lens, examples first)
# =============================================================================


class ExamplesProminentPromptBuilder(LensPromptBuilder):
    """Full lens with examples section prominently placed first."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.EXAMPLES_PROMINENT

    def build_prompt(self, task_prompt: str) -> str:
        content = _get_all_heuristic_content(self.lens)

        # Examples first (prominent)
        sections = [
            f"# {self.lens.name}\n",
            "## Code Quality Examples (STUDY THESE FIRST)\n",
            "### Patterns to FOLLOW:",
        ]
        for ex in content["examples_good"]:
            sections.append(f"✓ `{ex}`")

        sections.append("\n### Patterns to AVOID:")
        for ex in content["examples_bad"]:
            sections.append(f"✗ `{ex}`")

        # Then the full rules
        sections.append("\n## Complete Heuristics\n")

        sorted_rules = sorted(content["rules"], key=lambda r: r[2], reverse=True)
        for name, rule, priority in sorted_rules:
            sections.append(f"### {name} (priority: {priority})")
            sections.append(f"{rule}\n")

        # All always rules
        sections.append("## Required Practices (ALWAYS do these):\n")
        for a in content["always"]:
            sections.append(f"- {a}")

        # All never rules
        sections.append("\n## Anti-Patterns (NEVER do these):\n")
        for n in content["never"]:
            sections.append(f"- {n}")

        # Communication style
        if self.lens.communication:
            sections.append("\n## Communication Style")
            tone = self.lens.communication.get("tone", [])
            if tone:
                sections.append(f"Tone: {', '.join(tone) if isinstance(tone, list) else tone}")

        return f"""{chr(10).join(sections)}

---

## Task
{task_prompt}

Write production-quality Python code. Apply ALL heuristics above.
Code only:"""


# =============================================================================
# Strategy 5: NEGATIVES_FIRST (Full lens, never rules prominent)
# =============================================================================


class NegativesFirstPromptBuilder(LensPromptBuilder):
    """Full lens with anti-patterns/never rules given prominent placement."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.NEGATIVES_FIRST

    def build_prompt(self, task_prompt: str) -> str:
        content = _get_all_heuristic_content(self.lens)

        sections = [
            f"# {self.lens.name}\n",
            "## ⚠️ CRITICAL ANTI-PATTERNS (Read First!)\n",
            "These patterns WILL cause bugs, security issues, or maintenance problems:\n",
        ]

        # All never rules prominently
        for n in content["never"]:
            sections.append(f"❌ {n}")

        # Bad examples
        sections.append("\n### Code That Demonstrates These Problems:")
        for ex in content["examples_bad"]:
            sections.append(f"```\n{ex}\n```  ← DON'T do this")

        # Now the positive guidance
        sections.append("\n---\n")
        sections.append("## Required Practices\n")
        for a in content["always"]:
            sections.append(f"✓ {a}")

        # Good examples
        sections.append("\n### Code That Demonstrates Best Practices:")
        for ex in content["examples_good"]:
            sections.append(f"```\n{ex}\n```  ← DO this")

        # Full heuristics
        sections.append("\n## Complete Heuristics\n")
        sorted_rules = sorted(content["rules"], key=lambda r: r[2], reverse=True)
        for name, rule, priority in sorted_rules:
            sections.append(f"**{name}** (priority {priority}): {rule}")

        return f"""{chr(10).join(sections)}

---

## Task
{task_prompt}

Write Python code that avoids ALL anti-patterns and follows ALL best practices.
Code only:"""


# =============================================================================
# Strategy 6: ROLE_FRAMED (Full lens with expert role wrapper)
# =============================================================================


class RoleFramedPromptBuilder(LensPromptBuilder):
    """Full lens wrapped in expert role-play frame."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.ROLE_FRAMED

    def build_prompt(self, task_prompt: str) -> str:
        content = _get_all_heuristic_content(self.lens)

        # Get communication style
        tone = "precise, technical, and production-focused"
        if self.lens.communication and self.lens.communication.get("tone"):
            t = self.lens.communication["tone"]
            tone = ", ".join(t) if isinstance(t, list) else t

        # Role frame opening
        sections = [
            f"You are an expert {self.lens.domain} engineer who authored the following coding standards.",
            f"Your code exemplifies these principles. Your communication style: {tone}.\n",
            "## Your Professional Standards\n",
        ]

        # Full heuristics as "your standards"
        sorted_rules = sorted(content["rules"], key=lambda r: r[2], reverse=True)
        for name, rule, priority in sorted_rules:
            sections.append(f"### {name}")
            sections.append(f"*{rule}*\n")

        # All rules as practices you follow
        sections.append("## Practices You Always Follow:")
        for a in content["always"]:
            sections.append(f"- {a}")

        sections.append("\n## Anti-Patterns You Never Allow:")
        for n in content["never"]:
            sections.append(f"- {n}")

        # Examples of your code
        sections.append("\n## Examples of Code You Write:")
        for ex in content["examples_good"]:
            sections.append(f"```\n{ex}\n```")

        sections.append("\n## Code You Would REJECT in Review:")
        for ex in content["examples_bad"]:
            sections.append(f"```\n{ex}\n```")

        return f"""{chr(10).join(sections)}

---

## Request

A colleague asks: "{task_prompt}"

Write the code YOU would produce - code that exemplifies all your standards.
Just the code:"""


# =============================================================================
# Strategy 7: CHECKLIST_FORMAT (Full lens as actionable checklist)
# =============================================================================


class ChecklistFormatPromptBuilder(LensPromptBuilder):
    """Full lens content formatted as an actionable checklist."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.CHECKLIST_FORMAT

    def build_prompt(self, task_prompt: str) -> str:
        content = _get_all_heuristic_content(self.lens)

        sections = [
            f"# {self.lens.name} - Quality Checklist\n",
            "Your code MUST satisfy ALL items below.\n",
            "## ✅ Required Practices (CHECK ALL):\n",
        ]

        # All always rules as checkboxes
        for i, a in enumerate(content["always"], 1):
            sections.append(f"[ ] {i}. {a}")

        sections.append("\n## ❌ Prohibited Patterns (VERIFY NONE PRESENT):\n")
        for i, n in enumerate(content["never"], 1):
            sections.append(f"[ ] {i}. Code does NOT: {n}")

        # Heuristics as numbered principles
        sections.append("\n## 📋 Guiding Principles:\n")
        sorted_rules = sorted(content["rules"], key=lambda r: r[2], reverse=True)
        for i, (name, rule, priority) in enumerate(sorted_rules, 1):
            sections.append(f"{i}. **{name}**: {rule}")

        # Examples as reference
        sections.append("\n## 📖 Reference Examples:\n")
        sections.append("Good patterns:")
        for ex in content["examples_good"]:
            sections.append(f"  ✓ `{ex}`")
        sections.append("\nBad patterns:")
        for ex in content["examples_bad"]:
            sections.append(f"  ✗ `{ex}`")

        return f"""{chr(10).join(sections)}

---

## Task
{task_prompt}

Write Python code that passes ALL checklist items.
Code only:"""


# =============================================================================
# Strategy 8: PRIORITY_ORDERED (Full lens strictly ordered by priority)
# =============================================================================


class PriorityOrderedPromptBuilder(LensPromptBuilder):
    """Full lens content ordered strictly by heuristic priority."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.PRIORITY_ORDERED

    def build_prompt(self, task_prompt: str) -> str:
        sections = [
            f"# {self.lens.name}\n",
            "## Heuristics (ORDERED BY IMPORTANCE - Most Critical First)\n",
        ]

        # Sort all heuristics by priority
        sorted_h = sorted(
            self.lens.heuristics,
            key=lambda h: h.get("priority", 0),
            reverse=True,
        )

        for h in sorted_h:
            priority = h.get("priority", 0)
            if priority >= 0.9:
                importance = "🔴 CRITICAL"
            elif priority >= 0.8:
                importance = "🟠 HIGH"
            elif priority >= 0.7:
                importance = "🟡 MEDIUM"
            else:
                importance = "🟢 STANDARD"

            sections.append(f"### {importance}: {h.get('name', '')}")
            sections.append(f"**Principle**: {h.get('rule', '')}\n")

            if h.get("always"):
                sections.append("**Always**:")
                for a in h["always"]:
                    sections.append(f"  + {a}")

            if h.get("never"):
                sections.append("**Never**:")
                for n in h["never"]:
                    sections.append(f"  - {n}")

            examples = h.get("examples", {})
            if examples.get("good"):
                sections.append(f"**Good**: `{examples['good']}`")
            if examples.get("bad"):
                sections.append(f"**Bad**: `{examples['bad']}`")

            sections.append("")

        # Communication style
        if self.lens.communication:
            sections.append("## Communication Style")
            tone = self.lens.communication.get("tone", [])
            avoid = self.lens.communication.get("avoid", [])
            if tone:
                sections.append(f"Tone: {', '.join(tone) if isinstance(tone, list) else tone}")
            if avoid:
                sections.append(f"Avoid: {', '.join(avoid) if isinstance(avoid, list) else avoid}")

        return f"""{chr(10).join(sections)}

---

## Task
{task_prompt}

Apply ALL heuristics. CRITICAL items take precedence if trade-offs needed.
Code only:"""


# =============================================================================
# Strategy 9: SYSTEM_SPLIT (Full lens split between system/user)
# =============================================================================


class SystemSplitPromptBuilder(LensPromptBuilder):
    """Full lens - designed to be split: lens in system prompt, task in user.
    
    NOTE: This builder returns the full prompt, but the experiment runner
    could potentially split at the marker and put lens in system role.
    """

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.SYSTEM_SPLIT

    def build_prompt(self, task_prompt: str) -> str:
        content = _get_all_heuristic_content(self.lens)

        # System portion (the lens expertise)
        system_sections = [
            f"[SYSTEM CONTEXT - {self.lens.name}]\n",
            f"{self.lens.description}\n" if self.lens.description else "",
            "You are an expert following these standards:\n",
        ]

        # All heuristics
        sorted_rules = sorted(content["rules"], key=lambda r: r[2], reverse=True)
        for name, rule, priority in sorted_rules:
            system_sections.append(f"• {name}: {rule}")

        system_sections.append("\nPractices you ALWAYS follow:")
        for a in content["always"]:
            system_sections.append(f"  + {a}")

        system_sections.append("\nPatterns you NEVER use:")
        for n in content["never"]:
            system_sections.append(f"  - {n}")

        # Reference examples
        system_sections.append("\nYour code looks like:")
        for ex in content["examples_good"]:
            system_sections.append(f"  ✓ {ex}")

        system_sections.append("\nCode you reject:")
        for ex in content["examples_bad"]:
            system_sections.append(f"  ✗ {ex}")

        # Communication style
        if self.lens.communication:
            tone = self.lens.communication.get("tone", [])
            if tone:
                system_sections.append(f"\nYour style: {', '.join(tone) if isinstance(tone, list) else tone}")

        system_sections.append("\n[END SYSTEM CONTEXT]\n")

        # User portion (the task)
        user_section = f"""[USER REQUEST]
{task_prompt}

Write the code. Apply ALL your standards.
Code only:"""

        return chr(10).join(system_sections) + "\n" + user_section


# =============================================================================
# Strategy 10: COMPACT_DENSE (Full lens compressed)
# =============================================================================


class CompactDensePromptBuilder(LensPromptBuilder):
    """Full lens content compressed to reduce token count while preserving info."""

    @property
    def strategy(self) -> LensStrategy:
        return LensStrategy.COMPACT_DENSE

    def build_prompt(self, task_prompt: str) -> str:
        content = _get_all_heuristic_content(self.lens)

        # Compact format - semicolon-separated, minimal whitespace
        rules_compact = "; ".join(f"{r[0]}:{r[1]}" for r in content["rules"])
        always_compact = "; ".join(content["always"])
        never_compact = "; ".join(content["never"])
        good_compact = " | ".join(content["examples_good"])
        bad_compact = " | ".join(content["examples_bad"])

        tone = ""
        if self.lens.communication and self.lens.communication.get("tone"):
            t = self.lens.communication["tone"]
            tone = ", ".join(t) if isinstance(t, list) else t

        return f"""EXPERTISE[{self.lens.name}|{self.lens.domain}]
STYLE:{tone}
RULES:{rules_compact}
ALWAYS:{always_compact}
NEVER:{never_compact}
GOOD:{good_compact}
BAD:{bad_compact}

TASK:{task_prompt}
OUTPUT:code_only"""


# =============================================================================
# Factory and Registry
# =============================================================================


STRATEGY_BUILDERS: dict[LensStrategy, type[LensPromptBuilder]] = {
    LensStrategy.BASELINE: BaselinePromptBuilder,
    LensStrategy.MARKDOWN_FULL: MarkdownFullPromptBuilder,
    LensStrategy.XML_STRUCTURED: XMLStructuredPromptBuilder,
    LensStrategy.EXAMPLES_PROMINENT: ExamplesProminentPromptBuilder,
    LensStrategy.NEGATIVES_FIRST: NegativesFirstPromptBuilder,
    LensStrategy.ROLE_FRAMED: RoleFramedPromptBuilder,
    LensStrategy.CHECKLIST_FORMAT: ChecklistFormatPromptBuilder,
    LensStrategy.PRIORITY_ORDERED: PriorityOrderedPromptBuilder,
    LensStrategy.SYSTEM_SPLIT: SystemSplitPromptBuilder,
    LensStrategy.COMPACT_DENSE: CompactDensePromptBuilder,
}


def create_prompt_builder(
    strategy: LensStrategy,
    lens: LensData,
) -> LensPromptBuilder:
    """Create a prompt builder for a given strategy."""
    builder_cls = STRATEGY_BUILDERS.get(strategy)
    if not builder_cls:
        raise ValueError(f"Unknown strategy: {strategy}")
    return builder_cls(lens)


def load_default_lens() -> LensData:
    """Load the default coder.lens file."""
    lens_paths = [
        Path("lenses/coder.lens"),
        Path.home() / ".sunwell" / "lenses" / "coder.lens",
        Path(__file__).parent.parent.parent.parent / "lenses" / "coder.lens",
    ]

    for path in lens_paths:
        if path.exists():
            return LensData.from_yaml(path)

    raise FileNotFoundError("Could not find coder.lens")


# =============================================================================
# Experiment Result Tracking
# =============================================================================


@dataclass
class ExperimentResult:
    """Result of a single experiment run."""

    strategy: LensStrategy
    task_name: str
    score: float
    features_achieved: tuple[str, ...]
    features_missing: tuple[str, ...]
    code: str
    prompt_tokens: int
    completion_tokens: int
    time_ms: int


@dataclass
class ExperimentSummary:
    """Summary statistics for a strategy across all tasks."""

    strategy: LensStrategy
    avg_score: float
    success_rate: float  # % achieving score >= 8.0
    total_runs: int
    results: list[ExperimentResult] = field(default_factory=list)
