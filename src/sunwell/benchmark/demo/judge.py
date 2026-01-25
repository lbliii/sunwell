"""Lightweight judge for demo feedback generation (RFC-095).

A single-LLM-call judge optimized for speed and clarity rather than
benchmark-grade accuracy. Generates feedback for Resonance refinement.
"""

import logging
from dataclasses import dataclass
from typing import Any

from sunwell.foundation.utils import safe_json_loads

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DemoJudgment:
    """Result from demo judge evaluation.

    Attributes:
        score: Quality score from 0-10.
        feedback: List of specific issues found.
        features_missing: Set of expected features that are absent.
    """

    score: float
    feedback: tuple[str, ...]
    features_missing: frozenset[str]


# Feature names mapped to natural language descriptions for the prompt
FEATURE_DESCRIPTIONS: dict[str, str] = {
    "type_hints": "type annotations on parameters and return value",
    "docstring": "a docstring explaining the function",
    "error_handling": "proper error handling with try/except or raise",
    "zero_division_handling": "check for division by zero",
    "type_validation": "validation of input types using isinstance()",
    "empty_list_handling": "handling of empty list input",
    "negative_input_handling": "handling of negative input values",
    "memoization_or_iteration": "optimization via memoization or iteration",
    "regex_pattern": "use of regular expressions for pattern matching",
    "edge_case_handling": "handling of edge cases",
}


class DemoJudge:
    """Lightweight judge for demo feedback generation.

    Uses a single LLM call to identify missing features, optimized for
    speed and clarity rather than benchmark-grade accuracy.

    Evidence: This pattern is validated in THESIS-VERIFICATION.md:399-468
    where judge feedback drives Resonance refinement.
    """

    def __init__(self, model: Any) -> None:
        """Initialize judge with a model.

        Args:
            model: A model implementing the ModelProtocol (generate method).
        """
        self.model = model

    async def evaluate(
        self,
        code: str,
        expected_features: frozenset[str],
    ) -> DemoJudgment:
        """Evaluate code and generate feedback for Resonance.

        Args:
            code: Python code to evaluate.
            expected_features: Set of feature names expected in good output.

        Returns:
            DemoJudgment with score, feedback, and missing features.
        """
        # Build feature descriptions for the prompt
        feature_list = [
            FEATURE_DESCRIPTIONS.get(f, f) for f in expected_features
        ]

        prompt = f"""Evaluate this Python code for quality:

```python
{code}
```

Check for these features:
{chr(10).join(f'- {f}' for f in feature_list)}

Return ONLY valid JSON (no markdown, no explanation):
{{"score": <0-10>, "missing": ["feature1", ...], "feedback": ["issue1", ...]}}

Be specific about what's missing. If the code is minimal or incomplete,
list all missing features.
"""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self.model.generate(
                prompt,
                options=GenerateOptions(
                    temperature=0.1,  # Low temperature for consistent evaluation
                    max_tokens=512,
                ),
            )

            response_text = result.content or ""

            # Try to extract JSON from the response
            parsed = self._parse_json_response(response_text)

            # Map feedback to our feature names
            missing = self._map_missing_features(
                parsed.get("missing", []),
                expected_features,
            )

            return DemoJudgment(
                score=float(parsed.get("score", 2.0)),
                feedback=tuple(parsed.get("feedback", ["Evaluation incomplete"])),
                features_missing=frozenset(missing),
            )

        except Exception as e:
            logger.warning(f"Judge evaluation failed: {e}")
            # Return a default low-quality judgment
            return DemoJudgment(
                score=2.0,
                feedback=("Evaluation failed - assuming low quality",),
                features_missing=expected_features,
            )

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response, handling common issues."""
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        # Try to find JSON object
        text = text.strip()

        # Find the JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end > start:
            json_text = text[start:end]
            try:
                return safe_json_loads(json_text)
            except ValueError:
                pass

        # Fallback: return empty dict
        return {}

    def _map_missing_features(
        self,
        reported_missing: list[str],
        expected_features: frozenset[str],
    ) -> list[str]:
        """Map reported missing features back to our canonical names.

        The LLM might report features using different wording. This
        attempts to match them to our expected feature names.
        """
        result = []
        reported_lower = [m.lower() for m in reported_missing]

        for feature in expected_features:
            # Check if feature or its description appears in reported missing
            feature_desc = FEATURE_DESCRIPTIONS.get(feature, "").lower()
            feature_lower = feature.lower().replace("_", " ")

            for reported in reported_lower:
                if (
                    feature_lower in reported
                    or reported in feature_lower
                    or any(word in reported for word in feature_desc.split())
                ):
                    result.append(feature)
                    break
            else:
                # Check for keyword matches
                keywords = {
                    "type_hints": ["type", "annotation", "hint"],
                    "docstring": ["docstring", "documentation", "doc"],
                    "zero_division_handling": ["zero", "division"],
                    "type_validation": ["isinstance", "type check", "validation"],
                    "error_handling": ["error", "exception", "raise", "try"],
                    "empty_list_handling": ["empty", "length"],
                    "negative_input_handling": ["negative", "< 0"],
                    "memoization_or_iteration": ["memo", "cache", "iteration", "loop"],
                    "regex_pattern": ["regex", "pattern", "re."],
                    "edge_case_handling": ["edge", "corner", "special"],
                }
                for keyword in keywords.get(feature, []):
                    if any(keyword in r for r in reported_lower):
                        result.append(feature)
                        break

        return result
