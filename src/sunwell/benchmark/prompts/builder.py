"""Build system prompts using different strategies.

Strategies are based on prompting research:
- https://www.promptingguide.ai/techniques
- https://www.promptingguide.ai/agents/context-engineering
"""

from typing import TYPE_CHECKING

from sunwell.benchmark.types import PromptStrategy

if TYPE_CHECKING:
    from sunwell.core.heuristic import Heuristic


class PromptBuilder:
    """Build system prompts using different strategies.

    Strategies are based on prompting research:
    - https://www.promptingguide.ai/techniques
    - https://www.promptingguide.ai/agents/context-engineering
    """

    @staticmethod
    def build(
        heuristics: list[Heuristic],
        strategy: PromptStrategy,
        lens_name: str = "Expert",
    ) -> str:
        """Build a system prompt from heuristics using the specified strategy."""
        if not heuristics:
            return ""

        if strategy == PromptStrategy.RAW:
            return PromptBuilder._raw(heuristics)
        elif strategy == PromptStrategy.GUIDED:
            return PromptBuilder._guided(heuristics, lens_name)
        elif strategy == PromptStrategy.COT:
            return PromptBuilder._chain_of_thought(heuristics, lens_name)
        elif strategy == PromptStrategy.CONSTRAINTS:
            return PromptBuilder._constraints(heuristics)
        elif strategy == PromptStrategy.FEW_SHOT:
            return PromptBuilder._few_shot(heuristics, lens_name)
        else:
            return PromptBuilder._raw(heuristics)

    @staticmethod
    def _raw(heuristics: list[Heuristic]) -> str:
        """Just dump heuristics as-is."""
        return "\n\n".join(h.to_prompt_fragment() for h in heuristics)

    @staticmethod
    def _guided(heuristics: list[Heuristic], lens_name: str) -> str:
        """Add meta-instructions for applying heuristics."""
        heuristic_block = "\n\n".join(h.to_prompt_fragment() for h in heuristics)
        return f"""# Expert Guidance: {lens_name}

You have access to these professional coding principles. Apply them to your response.

{heuristic_block}

## How to Use

1. Review which heuristics apply to this task
2. Follow the "always" patterns, avoid the "never" patterns
3. Verify your code follows these principles before responding

Apply these naturally - don't just list them, embody them in your code."""

    @staticmethod
    def _chain_of_thought(heuristics: list[Heuristic], lens_name: str) -> str:
        """Chain-of-thought prompting for larger models."""
        heuristic_block = "\n\n".join(h.to_prompt_fragment() for h in heuristics)
        return f"""# Expert Principles: {lens_name}

{heuristic_block}

---

## INSTRUCTIONS (Chain-of-Thought)

Before writing code, you MUST:

1. **THINK**: Which 1-2 heuristics from above are most relevant to this task?
2. **PLAN**: How will you apply them? What patterns will you use/avoid?
3. **CODE**: Write the solution following those heuristics.
4. **VERIFY**: Does your code follow the "always" and avoid the "never" patterns?

Format your response as:

```
THINKING: [Which heuristics apply and why]
PLAN: [How you'll apply them]
```

```python
# Your code here
```"""

    @staticmethod
    def _constraints(heuristics: list[Heuristic]) -> str:
        """Extract direct MUST/MUST NOT constraints for small models."""
        must_do = []
        must_not = []

        for h in heuristics:
            if h.always:
                must_do.extend(h.always[:3])  # Top 3 per heuristic
            if h.never:
                must_not.extend(h.never[:2])  # Top 2 per heuristic

        parts = ["# Coding Requirements\n"]
        if must_do:
            parts.append("You MUST:")
            parts.extend(f"- {item}" for item in must_do[:8])
            parts.append("")
        if must_not:
            parts.append("You MUST NOT:")
            parts.extend(f"- {item}" for item in must_not[:5])
            parts.append("")

        parts.append("Write clean, professional code following these requirements.")
        return "\n".join(parts)

    @staticmethod
    def _few_shot(heuristics: list[Heuristic], lens_name: str) -> str:
        """Include an example of applying heuristics."""
        # Use first heuristic for the example
        example_h = heuristics[0] if heuristics else None
        heuristic_block = "\n\n".join(h.to_prompt_fragment() for h in heuristics)

        example = ""
        if example_h and example_h.always:
            example = f"""
## Example: Applying "{example_h.name}"

Task: Write a function to fetch user data

BAD (ignores heuristic):
```python
def get_user(id):
    return db.query(id)
```

GOOD (follows heuristic - "{example_h.always[0]}"):
```python
def get_user(user_id: int) -> User | None:
    \"\"\"Fetch user by ID.\"\"\"
    return db.query(User, user_id)
```
"""

        return f"""# Expert Principles: {lens_name}

{heuristic_block}
{example}
Apply these principles to your response. Show your work like the example above."""
