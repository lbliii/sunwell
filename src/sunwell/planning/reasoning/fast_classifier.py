"""Fast JSON Classifier for Small Models.

The key insight: small models (1-3B) can't follow tool schemas, but they CAN
output structured JSON when the format is explicit in the prompt.

Pattern:
    [Clear task] + [Exact JSON format] + [Constrained options] = Fast, reliable results

Usage:
    classifier = FastClassifier(model)

    # Define a classification task
    result = await classifier.classify(
        task="Assess severity",
        context={"signal": "race condition", "file": "cache.py"},
        options=["critical", "high", "medium", "low"],
        output_key="severity",
    )
    # Returns: {"severity": "high", "confidence": 0.8, "rationale": "..."}

This is 10-25x faster than tool-calling with comparable accuracy for
constrained classification tasks.

See: RFC-073 (Reasoned Decisions)
"""


import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.models import GenerateOptions

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

# Pre-compiled regex patterns
_MARKDOWN_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Result from fast classification."""

    value: Any
    """The classification result (enum value, bool, score, etc.)."""

    confidence: float
    """Model's confidence in the classification (0.0-1.0)."""

    rationale: str
    """Brief explanation for the classification."""

    raw_response: str = ""
    """Raw model response (for debugging)."""

    @property
    def is_confident(self) -> bool:
        """True if confidence >= 70%."""
        return self.confidence >= 0.70


# =============================================================================
# Pre-built Classification Templates
# =============================================================================


@dataclass(frozen=True, slots=True)
class ClassificationTemplate:
    """A reusable classification template."""

    name: str
    """Template name for logging/debugging."""

    prompt_template: str
    """Prompt template with {context} placeholder."""

    output_key: str
    """Key to extract from JSON response."""

    options: tuple[str, ...] | None = None
    """Valid options (None = any value)."""

    default: Any = None
    """Default value if classification fails."""


# Common templates
SEVERITY_TEMPLATE = ClassificationTemplate(
    name="severity",
    prompt_template="""Assess severity. Respond with ONLY JSON.

Signal: {signal_type}
Content: "{content}"
File: {file_path}

{{"severity": "critical"|"high"|"medium"|"low", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:""",
    output_key="severity",
    options=("critical", "high", "medium", "low"),
    default="medium",
)

COMPLEXITY_TEMPLATE = ClassificationTemplate(
    name="complexity",
    prompt_template="""Classify task complexity. Respond with ONLY JSON.

Task: "{task}"

{{"complexity": "trivial"|"standard"|"complex", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:""",
    output_key="complexity",
    options=("trivial", "standard", "complex"),
    default="standard",
)

INTENT_TEMPLATE = ClassificationTemplate(
    name="intent",
    prompt_template="""Classify user intent. Respond with ONLY JSON.

Request: "{request}"

{{"intent": "code"|"explain"|"debug"|"chat"|"search"|"review", "confidence": 0.0-1.0}}

JSON:""",
    output_key="intent",
    options=("code", "explain", "debug", "chat", "search", "review"),
    default="code",
)

RISK_TEMPLATE = ClassificationTemplate(
    name="risk",
    prompt_template="""Assess risk level. Respond with ONLY JSON.

Action: {action}
File: {file_path}
Change: "{change_description}"

{{"risk": "safe"|"moderate"|"dangerous"|"forbidden", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:""",
    output_key="risk",
    options=("safe", "moderate", "dangerous", "forbidden"),
    default="moderate",
)

BINARY_TEMPLATE = ClassificationTemplate(
    name="binary",
    prompt_template="""Answer yes or no. Respond with ONLY JSON.

Question: {question}
Context: {context}

{{"answer": true|false, "confidence": 0.0-1.0, "rationale": "why"}}

JSON:""",
    output_key="answer",
    options=None,  # Boolean
    default=False,
)

SCORE_TEMPLATE = ClassificationTemplate(
    name="score",
    prompt_template="""Score from 1-10. Respond with ONLY JSON.

Task: {task}
Criteria: {criteria}
Item: {item}

{{"score": 1-10, "confidence": 0.0-1.0, "rationale": "why"}}

JSON:""",
    output_key="score",
    options=None,  # Numeric
    default=5,
)


# =============================================================================
# Fast Classifier
# =============================================================================


@dataclass(slots=True)
class FastClassifier:
    """Fast JSON-based classifier for small models.

    Instead of tool calling (which small models handle poorly), this uses
    explicit JSON output format in the prompt.

    Performance:
        - Small model (1-3B): ~1-2s per classification
        - Large model with tools (7B+): ~10-30s per classification
        - 10-25x speedup with comparable accuracy for constrained tasks
    """

    model: ModelProtocol
    """The model to use (recommended: llama3.2:3b, qwen2.5:1.5b)."""

    temperature: float = 0.1
    """Low temperature for consistent classifications."""

    _cache: dict[str, ClassificationResult] = field(
        default_factory=dict, repr=False
    )
    """Simple cache for repeated classifications."""

    async def classify(
        self,
        task: str,
        context: dict[str, Any],
        options: list[str] | tuple[str, ...] | None = None,
        output_key: str = "value",
        default: Any = None,
    ) -> ClassificationResult:
        """Classify with custom prompt.

        Args:
            task: What to classify (e.g., "Assess severity")
            context: Context dict with placeholders for prompt
            options: Valid options (None = any value)
            output_key: Key to extract from JSON response
            default: Default value if classification fails

        Returns:
            ClassificationResult with value, confidence, rationale
        """
        # Build prompt
        options_str = "|".join(f'"{o}"' for o in options) if options else "your answer"
        context_str = self._format_context(context)

        prompt = f"""{task}. Respond with ONLY valid JSON.

{context_str}

{{"{output_key}": {options_str}, "confidence": 0.0-1.0, "rationale": "brief explanation"}}

JSON:"""

        return await self._execute(prompt, output_key, options, default)

    async def classify_with_template(
        self,
        template: ClassificationTemplate,
        context: dict[str, Any],
    ) -> ClassificationResult:
        """Classify using a pre-built template.

        Args:
            template: Classification template
            context: Context dict to fill template placeholders

        Returns:
            ClassificationResult
        """
        prompt = template.prompt_template.format(**context)
        return await self._execute(
            prompt, template.output_key, template.options, template.default
        )

    async def batch_classify(
        self,
        classifications: list[tuple[ClassificationTemplate, dict[str, Any]]],
    ) -> list[ClassificationResult]:
        """Classify multiple items (sequential, for now).

        TODO: Could be parallelized if model supports concurrent requests.
        """
        results = []
        for template, context in classifications:
            result = await self.classify_with_template(template, context)
            results.append(result)
        return results

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def severity(self, signal_type: str, content: str, file_path: str) -> str:
        """Quick severity classification."""
        result = await self.classify_with_template(
            SEVERITY_TEMPLATE,
            {"signal_type": signal_type, "content": content, "file_path": file_path},
        )
        return result.value

    async def complexity(self, task: str) -> str:
        """Quick complexity classification."""
        result = await self.classify_with_template(
            COMPLEXITY_TEMPLATE, {"task": task}
        )
        return result.value

    async def intent(self, request: str) -> str:
        """Quick intent classification."""
        result = await self.classify_with_template(
            INTENT_TEMPLATE, {"request": request}
        )
        return result.value

    async def risk(
        self, action: str, file_path: str, change_description: str
    ) -> str:
        """Quick risk classification."""
        result = await self.classify_with_template(
            RISK_TEMPLATE,
            {
                "action": action,
                "file_path": file_path,
                "change_description": change_description,
            },
        )
        return result.value

    async def yes_no(self, question: str, context: str = "") -> bool:
        """Quick yes/no classification."""
        result = await self.classify_with_template(
            BINARY_TEMPLATE, {"question": question, "context": context}
        )
        return bool(result.value)

    async def score(self, task: str, criteria: str, item: str) -> int:
        """Quick 1-10 scoring."""
        result = await self.classify_with_template(
            SCORE_TEMPLATE, {"task": task, "criteria": criteria, "item": item}
        )
        return int(result.value) if result.value else 5

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dict for prompt."""
        lines = []
        for key, value in context.items():
            if isinstance(value, str):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    async def _execute(
        self,
        prompt: str,
        output_key: str,
        options: tuple[str, ...] | list[str] | None,
        default: Any,
    ) -> ClassificationResult:
        """Execute classification and parse result."""
        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=self.temperature),
            )
            raw = result.text.strip()
            return self._parse_response(raw, output_key, options, default)

        except Exception as e:
            return ClassificationResult(
                value=default,
                confidence=0.0,
                rationale=f"Classification failed: {e}",
                raw_response="",
            )

    def _parse_response(
        self,
        raw: str,
        output_key: str,
        options: tuple[str, ...] | list[str] | None,
        default: Any,
    ) -> ClassificationResult:
        """Parse JSON response from model."""
        text = raw

        # Handle markdown code blocks
        if "```" in text:
            match = _MARKDOWN_CODE_BLOCK_RE.search(text)
            if match:
                text = match.group(1).strip()

        # Extract JSON object
        match = _JSON_OBJECT_RE.search(text)
        if match:
            text = match.group(0)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ClassificationResult(
                value=default,
                confidence=0.0,
                rationale=f"Failed to parse JSON: {text[:100]}",
                raw_response=raw,
            )

        # Extract value
        value = data.get(output_key, default)

        # Validate against options
        if options and value not in options:
            # Try to find closest match
            value_lower = str(value).lower() if value else ""
            for opt in options:
                if opt.lower() in value_lower or value_lower in opt.lower():
                    value = opt
                    break
            else:
                value = default

        confidence = float(data.get("confidence", 0.5))
        rationale = data.get("rationale", "")

        return ClassificationResult(
            value=value,
            confidence=confidence,
            rationale=rationale,
            raw_response=raw,
        )


# =============================================================================
# Utility Functions
# =============================================================================


def get_recommended_model() -> str:
    """Get recommended model for fast classification.

    Based on benchmarks:
    - llama3.2:3b: 100% accuracy, 1.3s average (BEST)
    - qwen2.5:1.5b: 100% accuracy, 1.7s average
    - gemma3:1b: 67% accuracy, 1.2s (faster but less accurate)
    """
    return "llama3.2:3b"
