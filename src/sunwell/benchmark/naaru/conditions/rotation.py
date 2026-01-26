"""Rotation frame definitions for Thought Rotation Protocol."""

ROTATION_FRAMES = {
    "think": "Initial reasoning and exploration. What is this about? What are the key elements?",
    "critic": "Challenge assumptions, find flaws. What could go wrong? What am I missing?",
    "advocate": "Defend and strengthen. What makes this good? How can I make it better?",
    "user": "What does the user actually need? Am I solving their real problem?",
    "expert": "Apply domain expertise. What do best practices say? What patterns apply?",
    "synthesize": "Integrate all perspectives into a coherent response.",
}

# Divergent rotation emphasizes adversarial thinking
DIVERGENT_ROTATION_FRAMES = {
    "think": "Initial exploration. Consider multiple approaches, don't commit early.",
    "adversary": (
        "ATTACK this. Find security holes, edge cases, ways it could fail."
    ),
    "advocate": "DEFEND this. Why is this approach good? What strengths does it have?",
    "naive": "Be a BEGINNER. What's confusing? What seems weird? Ask obvious questions.",
    "synthesize": (
        "Integrate: what did adversary find? advocate strengthen? naive reveal?"
    ),
}

ROTATION_SYSTEM_PROMPT = """## Thought Rotation Protocol

As you reason through this task, use these cognitive frame markers to shift perspectives.
Each frame brings a different viewpoint. Use them naturally - don't force all frames.

{frames}

Example:
<think>
Let me understand what's being asked...
</think>

<critic>
Wait, there's a potential issue here...
</critic>

<synthesize>
Integrating these perspectives, the solution is...
</synthesize>

Now respond to the task using this rotation protocol:"""


def build_rotation_prompt(frames: dict[str, str]) -> str:
    """Build the rotation system prompt from frame definitions."""
    frame_text = "\n".join(
        f"<{name}> {desc} </{name}>"
        for name, desc in frames.items()
    )
    return ROTATION_SYSTEM_PROMPT.format(frames=frame_text)


def parse_frame_usage(text: str, frames: dict[str, str]) -> dict[str, int]:
    """Parse which frames were used and approximate token counts."""
    import re

    frame_usage: dict[str, int] = {}

    for frame_name in frames:
        # Find all instances of <frame>...</frame>
        pattern = rf"<{frame_name}>(.*?)</{frame_name}>"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

        if matches:
            # Estimate tokens: ~1.33 tokens per word (words / 0.75)
            total_content = " ".join(matches)
            word_count = len(total_content.split())
            estimated_tokens = int(word_count * 1.33)
            frame_usage[frame_name] = estimated_tokens

    return frame_usage
